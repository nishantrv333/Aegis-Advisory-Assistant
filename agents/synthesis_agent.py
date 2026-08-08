"""
Synthesis agent.

Takes the outputs of the other agents and produces the briefing an adviser
actually reads. The model writes the prose sections, the headline summary and
talking points, while the structured sections (portfolio snapshot,
compliance flags, citations) are assembled in Python and passed through
untouched.

That split is deliberate. Numbers and flags should never be retyped by a
language model: every restatement is an opportunity to drift. The model gets
the parts where fluency helps and nothing depends on exact reproduction.

The output schema is fixed, so the UI never has to guess what it received.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from agents.base import BaseAgent
from core.a2a import AgentCard, Message, Response
from core.trace import Trace

SYNTHESIS_SYSTEM = """You prepare pre-meeting briefings for private bank advisers.

You receive: a client profile, a portfolio snapshot, cited market research, and
the output of a compliance rules engine.

Rules:
- Cite market claims with the [S#] markers exactly as they appear in the research
  you were given. Do not invent markers.
- Never contradict or soften the compliance result. If the status is FAIL, the
  talking points must reflect that the recommendation cannot proceed as framed.
- Talking points are for the adviser to raise with the client. Make them
  specific to this client's objectives and holdings, not generic.
- British English. No sales language. All data is synthetic demo data.

Return JSON:
{
  "headline": "one sentence the adviser reads first",
  "summary": "3-5 sentences covering position, context and anything blocking",
  "talking_points": [
    {"point": "what to raise", "why": "why it matters to this client", "sources": ["S1"]}
  ],
  "questions_to_ask": ["question for the client", "..."],
  "watch_items": ["something to monitor after the meeting", "..."]
}"""


class SynthesisAgent(BaseAgent):
    card = AgentCard(
        name="synthesis",
        title="Synthesis Agent",
        description=(
            "Combines portfolio, research and compliance output into the final structured "
            "client briefing."
        ),
        accepts=["synthesise"],
        produces=["briefing"],
    )

    def handle(self, message: Message, trace: Trace) -> Response:
        payload = message.payload
        query: str = payload.get("query", "")
        portfolio: dict[str, Any] = payload.get("portfolio") or {}
        research: dict[str, Any] = payload.get("research") or {}
        compliance: dict[str, Any] = payload.get("compliance") or {}

        profile = portfolio.get("client_profile") or {}
        snapshot = portfolio.get("portfolio_snapshot") or {}
        derived = portfolio.get("derived") or {}
        sources = research.get("sources") or []
        market_context = research.get("market_context") or {}

        narrative = self._write_narrative(
            query, profile, derived, snapshot, market_context, sources, compliance, trace
        )
        narrative = _strip_unknown_markers(narrative, {s["marker"] for s in sources})

        briefing = {
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "query": query,
            "data_notice": "All client, portfolio and market data in this briefing is synthetic.",
            "client": {
                "client_id": profile.get("client_id"),
                "name": profile.get("name"),
                "risk_profile": profile.get("risk_profile"),
                "investor_classification": profile.get("investor_classification"),
                "horizon_years": profile.get("investment_horizon_years"),
                "liquidity_needs": profile.get("liquidity_needs"),
                "next_meeting": profile.get("next_meeting"),
                "adviser": profile.get("adviser"),
                "objectives": profile.get("objectives", []),
                "constraints": profile.get("constraints", []),
                "esg_mandate": profile.get("esg_mandate"),
                "esg_exclusions": profile.get("esg_exclusions", []),
            },
            "headline": narrative.get("headline", ""),
            "summary": narrative.get("summary", ""),
            "portfolio_snapshot": {
                "as_of": snapshot.get("as_of"),
                "total_value_gbp": snapshot.get("total_value_gbp"),
                "currency": snapshot.get("currency", "GBP"),
                "holdings": snapshot.get("holdings", []),
                "allocation_by_asset_class": derived.get("allocation_by_asset_class", {}),
                "growth_asset_pct": derived.get("growth_asset_pct"),
                "largest_position": derived.get("largest_position"),
                "cash_pct": snapshot.get("cash_pct"),
                "weighted_risk_rating": snapshot.get("weighted_risk_rating"),
                "performance": snapshot.get("performance", {}),
            },
            "market_context": {
                "summary": market_context.get("summary", ""),
                "key_points": market_context.get("key_points", []),
                "relevance_to_client": market_context.get("relevance_to_client", ""),
                "queries_run": research.get("queries", []),
            },
            "compliance": {
                "status": compliance.get("status", "not_run"),
                "flag_count": compliance.get("flag_count", 0),
                "flags": compliance.get("flags", []),
                "adviser_note": compliance.get("adviser_note", ""),
                "actions_before_meeting": compliance.get("actions_before_meeting", []),
                "proposals_checked": compliance.get("proposals_checked", []),
                "rules_evaluated": compliance.get("rules_evaluated", []),
                "disclaimer": compliance.get(
                    "disclaimer", "Illustrative rules. Not regulatory advice."
                ),
            },
            "talking_points": narrative.get("talking_points", []),
            "questions_to_ask": narrative.get("questions_to_ask", []),
            "watch_items": narrative.get("watch_items", []),
            "citations": sources,
        }

        trace.note(
            "synthesis.assembled",
            f"Briefing assembled with {len(briefing['talking_points'])} talking points and "
            f"{len(sources)} citations",
            output={
                "compliance_status": briefing["compliance"]["status"],
                "citations": [s["marker"] for s in sources],
            },
        )
        return self.ok(message, {"briefing": briefing})

    def _write_narrative(
        self,
        query: str,
        profile: dict[str, Any],
        derived: dict[str, Any],
        snapshot: dict[str, Any],
        market_context: dict[str, Any],
        sources: list[dict[str, Any]],
        compliance: dict[str, Any],
        trace: Trace,
    ) -> dict[str, Any]:
        fallback = _deterministic_narrative(profile, derived, snapshot, market_context, compliance)

        source_block = "\n".join(
            f"[{s['marker']}] {s['title']} · {s['section']}: {s['snippet'][:280]}"
            for s in sources
        )
        flag_block = "\n".join(
            f"- [{f['rule_id']} · {f['severity']}] {f['rule_name']}: {f['detail']}"
            for f in compliance.get("flags", [])
        ) or "none"

        user = f"""Adviser request: {query}

CLIENT
{profile.get('name')} ({profile.get('client_id')}), {profile.get('risk_profile')} profile,
{profile.get('investor_classification')}, {profile.get('investment_horizon_years')}-year horizon,
{profile.get('liquidity_needs')} liquidity needs.
Objectives: {'; '.join(profile.get('objectives', []))}
Constraints: {'; '.join(profile.get('constraints', []))}
Adviser notes: {profile.get('adviser_notes', '')}

PORTFOLIO
Total £{snapshot.get('total_value_gbp', 0):,.0f} as at {snapshot.get('as_of')}.
Allocation: {derived.get('allocation_by_asset_class')}
Growth assets: {derived.get('growth_asset_pct')}%. Cash: {snapshot.get('cash_pct')}%.
Largest position: {(derived.get('largest_position') or {}).get('name')} at
{(derived.get('largest_position') or {}).get('weight_pct')}%.
Performance: {snapshot.get('performance')}

MARKET RESEARCH (cite these markers only)
{market_context.get('summary', '')}
{source_block}

COMPLIANCE RESULT, status {compliance.get('status', 'not_run').upper()}
{flag_block}
"""
        result = self.llm.complete_json(
            SYNTHESIS_SYSTEM,
            user,
            trace=trace,
            label="synthesis.write_briefing",
            fallback=fallback,
            max_tokens=2000,
        )
        if not isinstance(result.get("headline"), str) or not result.get("summary"):
            return fallback
        for key in ("talking_points", "questions_to_ask", "watch_items"):
            if not isinstance(result.get(key), list) or not result[key]:
                result[key] = fallback[key]
        result["talking_points"] = [
            p if isinstance(p, dict) else {"point": str(p), "why": "", "sources": []}
            for p in result["talking_points"]
        ][:6]
        return result


# ---------------------------------------------------------------------------
def _deterministic_narrative(
    profile: dict[str, Any],
    derived: dict[str, Any],
    snapshot: dict[str, Any],
    market_context: dict[str, Any],
    compliance: dict[str, Any],
) -> dict[str, Any]:
    """Assembled from facts already computed. Used with no API key, or if the
    model returns something unusable."""
    status = compliance.get("status", "not_run")
    flags = compliance.get("flags", [])
    name = profile.get("name", "the client")
    largest = derived.get("largest_position") or {}
    performance = snapshot.get("performance") or {}

    headline = {
        "fail": f"{len(flags)} suitability issue(s) must be resolved before advising {name}.",
        "review": f"Portfolio review for {name}. {len(flags)} item(s) need documenting.",
        "pass": f"Portfolio review for {name}. No suitability issues outstanding.",
    }.get(status, f"Portfolio review for {name}.")

    summary = (
        f"{name} holds £{snapshot.get('total_value_gbp', 0):,.0f} across "
        f"{len(snapshot.get('holdings', []))} positions, {derived.get('growth_asset_pct')}% in "
        f"growth assets, against a {profile.get('risk_profile')} profile and a "
        f"{profile.get('investment_horizon_years')}-year horizon. "
        f"Year-to-date return is {performance.get('ytd_return_pct')}% "
        f"({performance.get('vs_benchmark_ytd_pct')}% versus benchmark). "
        f"The largest position is {largest.get('name')} at {largest.get('weight_pct')}%. "
        f"The suitability check returned {status.upper()}."
    )

    talking_points = []
    for flag in flags[:3]:
        talking_points.append(
            {
                "point": f"{flag['rule_name']}: {flag['detail']}",
                "why": flag["remediation"],
                "sources": [],
            }
        )
    for point in (market_context.get("key_points") or [])[:3]:
        talking_points.append(
            {
                "point": point.get("point", ""),
                "why": "Relevant market context for this mandate.",
                "sources": point.get("sources", []),
            }
        )
    if not talking_points:
        talking_points.append(
            {
                "point": f"Confirm objectives are unchanged: {'; '.join(profile.get('objectives', []))}.",
                "why": "No flags or research points were raised for this request.",
                "sources": [],
            }
        )

    return {
        "headline": headline,
        "summary": summary,
        "talking_points": talking_points[:6],
        "questions_to_ask": [
            "Have your objectives or time horizon changed since the last review?",
            "Has your liquidity position changed, or any expected calls on capital?",
            "Are you comfortable with the current largest position size?",
        ],
        "watch_items": [f["detail"] for f in flags[:3]]
        or ["No outstanding items from this review."],
        "_generated_by": "deterministic_fallback",
    }


def _strip_unknown_markers(narrative: dict[str, Any], valid: set[str]) -> dict[str, Any]:
    import re

    def clean(text: str) -> str:
        def repl(match: "re.Match") -> str:
            kept = [m for m in re.findall(r"S\d+", match.group(0)) if m in valid]
            return f" [{', '.join(kept)}]" if kept else ""

        return re.sub(r"\s*\[S\d+(?:\s*,\s*S\d+)*\]", repl, text).strip()

    for key in ("headline", "summary"):
        if isinstance(narrative.get(key), str):
            narrative[key] = clean(narrative[key])
    for point in narrative.get("talking_points", []):
        if isinstance(point, dict):
            point["point"] = clean(str(point.get("point", "")))
            point["why"] = clean(str(point.get("why", "")))
            point["sources"] = [s for s in point.get("sources", []) if s in valid]
    return narrative
