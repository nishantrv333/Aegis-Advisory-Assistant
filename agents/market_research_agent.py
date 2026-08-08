"""
Market research agent (RAG).

Three stages: plan the queries, retrieve, then summarise under citation
constraints.

Query planning matters more than people expect. One long query mixing a
client's holdings, the rates outlook and a thematic question retrieves a
muddle; several focused queries retrieve cleanly and the union is better than
either. So the agent fans out, one query per topic, and merges the results.

Citations are assigned before the model is called, not after. Every retrieved
chunk gets a stable marker (S1, S2, …) and the model is instructed to cite
only those markers. Any marker it invents is stripped during validation, so
the citation list in the final briefing can only ever contain chunks that
were actually retrieved.
"""

from __future__ import annotations

import re
from typing import Any

from agents.base import BaseAgent
from core.a2a import AgentCard, Message, Response
from core.trace import Trace

MAX_QUERIES = 4
_MARKER = re.compile(r"\[S(\d+)\]")

PLANNER_SYSTEM = """You plan retrieval queries for a private bank's research index.
The index contains synthetic fund factsheets, market commentary, house views,
research notes and one internal suitability policy note.

Given an adviser's request and a client's portfolio, produce up to 4 short,
focused search queries. One topic per query. Prefer the vocabulary a research
analyst would use over the adviser's phrasing.

Return JSON: {"queries": ["...", "..."], "reasoning": "one sentence"}"""

SUMMARY_SYSTEM = """You are a research analyst at a private bank, writing for an
adviser who is about to meet a client.

Rules:
- Use ONLY the numbered sources provided. Never use outside knowledge.
- Cite with the exact markers given, like [S1] or [S2, S4]. Every factual claim
  needs a marker.
- If the sources do not answer part of the request, say so plainly.
- Neutral, specific, no sales language. British English.
- All source material is synthetic demo data; do not imply otherwise.

Return JSON:
{
  "summary": "3-5 sentences of market context relevant to this client, with [S#] markers",
  "key_points": [{"point": "one sentence with [S#] markers", "sources": ["S1"]}],
  "relevance_to_client": "2-3 sentences connecting the research to this client's mandate"
}"""


class MarketResearchAgent(BaseAgent):
    card = AgentCard(
        name="market_research",
        title="Market Research Agent",
        description=(
            "Runs vector search over the research corpus and summarises what is relevant to "
            "the client, with citations back to specific source passages."
        ),
        accepts=["research"],
        produces=["market_context", "citations"],
    )

    def handle(self, message: Message, trace: Trace) -> Response:
        query: str = message.payload.get("query", "")
        context: dict[str, Any] = message.payload.get("portfolio_context") or {}
        suggested: list[str] = message.payload.get("research_queries") or []
        instruments: list[str] = message.payload.get("candidate_instruments") or []

        queries = self._plan_queries(query, context, suggested, instruments, trace)
        trace.note("research.queries", f"{len(queries)} retrieval queries planned", output=queries)

        sources, per_query = self._retrieve(queries, trace)
        if not sources:
            return self.ok(
                message,
                {
                    "queries": queries,
                    "sources": [],
                    "market_context": {
                        "summary": "No relevant passages were retrieved from the research index.",
                        "key_points": [],
                        "relevance_to_client": "",
                    },
                },
            )

        summarised = self._summarise(query, context, sources, trace)
        return self.ok(
            message,
            {
                "queries": queries,
                "retrieval_by_query": per_query,
                "sources": sources,
                "market_context": summarised,
            },
            artifacts=[{"type": "citations", "sources": sources}],
        )

    # -- stage 1: plan -----------------------------------------------------
    def _plan_queries(
        self,
        query: str,
        context: dict[str, Any],
        suggested: list[str],
        instruments: list[str],
        trace: Trace,
    ) -> list[str]:
        if suggested:
            trace.note("research.plan", "Using queries supplied by the orchestrator")
            base = suggested[:MAX_QUERIES]
        else:
            fallback = self._heuristic_queries(query, context)
            plan = self.llm.complete_json(
                PLANNER_SYSTEM,
                f"Adviser request: {query}\n\nClient context: {_context_blurb(context)}",
                trace=trace,
                label="research.plan_queries",
                fallback={"queries": fallback, "reasoning": "heuristic fallback"},
            )
            queries = [q for q in plan.get("queries", []) if isinstance(q, str) and q.strip()]
            base = (queries or fallback)[:MAX_QUERIES]

        return base + self._instrument_queries(instruments, context, base, trace)

    def _instrument_queries(
        self,
        instruments: list[str],
        context: dict[str, Any],
        existing: list[str],
        trace: Trace,
    ) -> list[str]:
        """
        Always search for the specific products in play, by their proper names.

        An adviser writes "the client is asking about the Solaris AI fund".
        mostly filler, with the one word that matters buried in it. Retrieval
        on that string is weak. But by this point the orchestrator has already
        resolved which instruments are actually being proposed, so the agent
        can ask a clean question about each one instead of hoping the
        adviser's phrasing retrieves well. Where nothing is proposed, it falls
        back to the client's largest risk positions, which is what a
        pre-meeting review is about anyway.
        """
        targets = list(instruments)
        if not targets:
            targets = [h["instrument_id"] for h in (context.get("top_holdings") or [])][:2]
        if not targets:
            return []

        queries: list[str] = []
        for instrument_id in targets[:2]:
            result = self.registry.call(
                "portfolio.lookup_instrument", {"instrument_id": instrument_id}, trace
            )
            name = result.structured.get("name")
            if not name or any(name in q for q in existing + queries):
                continue
            queries.append(f"{name} outlook, risks and suitability")

        if queries:
            trace.note(
                "research.instrument_queries",
                f"Added {len(queries)} product-specific quer(y/ies) for {targets[:2]}",
                output=queries,
            )
        return queries

    @staticmethod
    def _heuristic_queries(query: str, context: dict[str, Any]) -> list[str]:
        """No-LLM path: build queries from the client's actual holdings."""
        queries = [query.strip()] if query.strip() else []
        classes = list((context.get("allocation_by_asset_class") or {}).keys())
        for asset_class in classes[:2]:
            queries.append(f"{asset_class} outlook and positioning")
        profile = context.get("risk_profile")
        if profile:
            queries.append(f"asset allocation house view for a {profile} mandate")
        return queries[:MAX_QUERIES]

    # -- stage 2: retrieve -------------------------------------------------
    def _retrieve(
        self, queries: list[str], trace: Trace
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """
        Fan out, then fuse with Reciprocal Rank Fusion.

        The obvious merge, pooling every hit and sorting by similarity score, is
        wrong, and wrong in a way that is easy to miss. Cosine scores from
        different queries are not on the same scale: a broad query
        ("multi-asset outlook") returns generically-matching passages at 0.25
        while a specific one ("the client is asking about the Solaris AI fund")
        returns exactly the right passage at 0.18, because the conversational
        filler dilutes it. Sorting the pool by score therefore evicts the
        precise answer in favour of vague ones, and adding queries makes recall
        worse. That is what the eval caught.

        RRF fuses by rank rather than score: a passage that ranked first for
        any query outranks one that ranked third for several. Ranks are
        comparable across queries; scores are not.
        """
        k_rrf = 60  # standard damping constant
        fused: dict[str, float] = {}
        best: dict[str, dict[str, Any]] = {}
        per_query: list[dict[str, Any]] = []

        for query in queries:
            with trace.span("retrieval", "research.search", label=f"retrieve · {query[:60]}",
                            input={"query": query}) as span:
                result = self.registry.call("research.search", {"query": query, "k": 4}, trace)
                hits = result.structured.get("hits", [])
                span.output = [
                    {"doc_id": h["doc_id"], "section": h["section"], "score": h["score"]}
                    for h in hits
                ]
            per_query.append({"query": query, "hits": [h["chunk_id"] for h in hits]})

            for rank, hit in enumerate(hits, start=1):
                chunk_id = hit["chunk_id"]
                fused[chunk_id] = fused.get(chunk_id, 0.0) + 1.0 / (k_rrf + rank)
                if chunk_id not in best or hit["score"] > best[chunk_id]["score"]:
                    best[chunk_id] = hit

        ranked = sorted(best.values(), key=lambda h: fused[h["chunk_id"]], reverse=True)[:8]
        sources = [
            {
                "marker": f"S{i}",
                "chunk_id": hit["chunk_id"],
                "doc_id": hit["doc_id"],
                "title": hit["title"],
                "section": hit["section"],
                "source_file": hit["source_file"],
                "doc_type": hit["doc_type"],
                "score": hit["score"],
                "fusion_score": round(fused[hit["chunk_id"]], 5),
                "snippet": _snippet(hit["text"]),
            }
            for i, hit in enumerate(ranked, start=1)
        ]
        trace.note(
            "research.fusion",
            f"{len(sources)} passages from {len({s['doc_id'] for s in sources})} documents, "
            f"fused across {len(queries)} queries by reciprocal rank",
            output=[f"{s['marker']}={s['doc_id']} (rrf {s['fusion_score']})" for s in sources],
        )
        return sources, per_query

    # -- stage 3: summarise ------------------------------------------------
    def _summarise(
        self,
        query: str,
        context: dict[str, Any],
        sources: list[dict[str, Any]],
        trace: Trace,
    ) -> dict[str, Any]:
        source_block = "\n\n".join(
            f"[{s['marker']}] {s['title']} · {s['section']} (doc_id {s['doc_id']})\n{s['snippet']}"
            for s in sources
        )
        user = (
            f"Adviser request: {query}\n\n"
            f"Client context: {_context_blurb(context)}\n\n"
            f"Sources:\n{source_block}"
        )
        fallback = _deterministic_summary(sources)
        result = self.llm.complete_json(
            SUMMARY_SYSTEM,
            user,
            trace=trace,
            label="research.summarise",
            fallback=fallback,
        )
        if "summary" not in result:
            result = fallback
        return _validate_citations(result, sources, trace)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _snippet(text: str, limit: int = 700) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[:limit].rsplit(" ", 1)[0] + "…"


def _context_blurb(context: dict[str, Any]) -> str:
    if not context:
        return "not supplied"
    allocation = context.get("allocation_by_asset_class") or {}
    return (
        f"risk profile {context.get('risk_profile', '?')}, "
        f"horizon {context.get('horizon_years', '?')}y, "
        f"allocation {allocation}, "
        f"largest position {(context.get('largest_position') or {}).get('name', '?')}"
    )


def _deterministic_summary(sources: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Used when no LLM is available, or when the model returns unusable output.
    It extracts rather than generates, so it is accurate but flat, which is the right
    failure mode for a compliance-sensitive surface.
    """
    points = []
    for source in sources[:4]:
        sentence = source["snippet"].split(". ")[0].strip().rstrip(".")
        points.append(
            {"point": f"{sentence}. [{source['marker']}]", "sources": [source["marker"]]}
        )
    docs = ", ".join(sorted({s["doc_id"] for s in sources[:4]}))
    return {
        "summary": (
            f"Retrieved {len(sources)} passages from the research index covering {docs}. "
            "Narrative summarisation was unavailable, so the key points below are extracted "
            "directly from the source passages."
        ),
        "key_points": points,
        "relevance_to_client": (
            "Review the cited passages directly. No model-generated interpretation was applied."
        ),
        "_generated_by": "deterministic_fallback",
    }


def _validate_citations(
    result: dict[str, Any], sources: list[dict[str, Any]], trace: Trace
) -> dict[str, Any]:
    """Strip any citation marker the model invented. Hallucinated sources are the
    one failure mode a briefing tool cannot ship with."""
    valid = {s["marker"] for s in sources}
    removed: set[str] = set()

    def clean(text: str) -> str:
        return re.sub(
            r"\s*\[S\d+(?:\s*,\s*S\d+)*\]",
            lambda m: _clean_group(m, valid, removed),
            text,
        )

    for key in ("summary", "relevance_to_client"):
        if isinstance(result.get(key), str):
            result[key] = clean(result[key]).strip()

    cleaned_points = []
    for point in result.get("key_points", []) or []:
        if isinstance(point, str):
            point = {"point": point, "sources": []}
        if not isinstance(point, dict):
            continue
        point["point"] = clean(str(point.get("point", "")))
        point["sources"] = [s for s in point.get("sources", []) if s in valid]
        cleaned_points.append(point)
    result["key_points"] = cleaned_points

    used = set()
    for text in [result.get("summary", ""), result.get("relevance_to_client", "")] + [
        p["point"] for p in cleaned_points
    ]:
        used.update(f"S{n}" for n in _MARKER.findall(str(text)))
    result["cited_markers"] = sorted(used, key=lambda m: int(m[1:]))

    if removed:
        trace.note(
            "research.citation_guard",
            f"Removed {len(removed)} hallucinated citation marker(s): {sorted(removed)}",
        )
    return result


def _clean_group(match: re.Match, valid: set[str], removed: set[str]) -> str:
    markers = re.findall(r"S\d+", match.group(0))
    kept = [m for m in markers if m in valid]
    removed.update(m for m in markers if m not in valid)
    return f" [{', '.join(kept)}]" if kept else ""
