"""
Orchestrator.

Decides which agents to call, in what order, and passes each one the context
the previous ones produced.

The planning is LLM-driven but guardrailed, and the guardrails are the point:

  * the plan is chosen from registered agent cards, and any agent the model
    invents is dropped rather than attempted
  * `portfolio` is forced first, because every other agent needs the client's profile
  * `compliance` is forced in, always. A model that could route around the
    suitability check by omitting it from a plan is not a design you can put
    in a bank
  * `synthesis` is forced last

So the model has real latitude over which research queries to run, which
instruments to put in front of the rules engine, whether the research step is
worth doing at all, but inside a shape that cannot produce an unchecked
recommendation. If the model is unavailable, the deterministic plan runs and
the output is structurally identical.
"""

from __future__ import annotations

from typing import Any

from agents.base import BaseAgent, match_instruments
from core.a2a import AgentCard, Message, Response, Router
from core.trace import Trace
from llm.base import LLMClient
from mcp_layer.registry import ToolRegistry

PLANNER_SYSTEM = """You are the orchestrator of a private bank's briefing assistant.

Given an adviser's request and the agents available, produce an execution plan.

Guidance:
- `portfolio` always runs first and is added automatically, so do not include it.
- `compliance` always runs and is added automatically, so do not include it.
- `synthesis` always runs last and is added automatically, so do not include it.
- Decide whether `market_research` is needed. It usually is, unless the request
  is purely about the client's own holdings or compliance position.
- Identify any instruments the adviser is proposing or asking about, by their
  ticker-style id, so the rules engine can check them.
- Suggest up to 4 focused retrieval queries if research is needed.

Return JSON:
{
  "reasoning": "one or two sentences on why this plan",
  "run_research": true,
  "research_queries": ["...", "..."],
  "candidate_instruments": ["SAA"],
  "intent": "meeting_prep | recommendation_check | portfolio_review | market_question"
}"""


class Orchestrator(BaseAgent):
    card = AgentCard(
        name="orchestrator",
        title="Orchestrator Agent",
        description="Plans and sequences the specialist agents for a briefing request.",
        accepts=["briefing"],
        produces=["briefing", "plan"],
    )

    def __init__(self, registry: ToolRegistry, llm: LLMClient, router: Router) -> None:
        super().__init__(registry, llm)
        self.router = router

    # -- entry point -------------------------------------------------------
    def run(self, client_id: str, query: str, trace: Trace) -> dict[str, Any]:
        with trace.span(
            "agent",
            "orchestrator",
            label="orchestrator · plan and execute",
            input={"client_id": client_id, "query": query},
        ):
            plan = self._plan(client_id, query, trace)

            # 1. Portfolio. Forced first; everything downstream depends on it.
            portfolio_response = self._dispatch(
                "portfolio", "profile_and_holdings", {"client_id": client_id}, trace
            )
            if portfolio_response.status != "ok":
                return {
                    "error": portfolio_response.error,
                    "plan": plan,
                    "briefing": None,
                }
            portfolio = portfolio_response.data

            # 2. Market research. The one optional step.
            research: dict[str, Any] = {}
            if plan["run_research"]:
                research_response = self._dispatch(
                    "market_research",
                    "research",
                    {
                        "query": query,
                        "research_queries": plan["research_queries"],
                        "candidate_instruments": plan["candidate_instruments"]
                        or match_instruments(query),
                        "portfolio_context": portfolio.get("derived", {}),
                    },
                    trace,
                )
                if research_response.status == "ok":
                    research = research_response.data
                else:
                    trace.note(
                        "orchestrator.degraded",
                        "Market research failed; continuing without market context",
                        output=research_response.error,
                    )
            else:
                trace.note("orchestrator.skip", "Plan skipped market research for this request")

            # 3. Compliance. Forced, and not skippable by the plan.
            candidates = plan["candidate_instruments"] or match_instruments(query)
            compliance_response = self._dispatch(
                "compliance",
                "check",
                {
                    "client_id": client_id,
                    "query": query,
                    "proposed_instruments": candidates,
                },
                trace,
            )
            compliance = compliance_response.data if compliance_response.status == "ok" else {
                "status": "error",
                "flag_count": 0,
                "flags": [],
                "adviser_note": f"Compliance check failed: {compliance_response.error}",
                "actions_before_meeting": ["Re-run the suitability check before advising."],
            }

            # 4. Synthesis. Forced last.
            synthesis_response = self._dispatch(
                "synthesis",
                "synthesise",
                {
                    "query": query,
                    "portfolio": portfolio,
                    "research": research,
                    "compliance": compliance,
                },
                trace,
            )
            if synthesis_response.status != "ok":
                return {"error": synthesis_response.error, "plan": plan, "briefing": None}

            return {"plan": plan, "briefing": synthesis_response.data["briefing"]}

    # -- planning ----------------------------------------------------------
    def _plan(self, client_id: str, query: str, trace: Trace) -> dict[str, Any]:
        fallback = {
            "reasoning": "Default plan: full briefing across all agents.",
            "run_research": True,
            "research_queries": [],
            "candidate_instruments": match_instruments(query),
            "intent": "meeting_prep",
            "_generated_by": "deterministic_fallback",
        }

        cards = "\n".join(
            f"- {c['name']}: {c['description']} (produces {', '.join(c['produces'])})"
            for c in self.router.cards()
        )
        raw = self.llm.complete_json(
            PLANNER_SYSTEM,
            f"Adviser request: {query}\nClient id: {client_id}\n\nAvailable agents:\n{cards}\n\n"
            f"Available tools:\n{self.registry.describe()}",
            trace=trace,
            label="orchestrator.plan",
            fallback=fallback,
        )

        plan = {
            "reasoning": str(raw.get("reasoning") or fallback["reasoning"]),
            "run_research": bool(raw.get("run_research", True)),
            "research_queries": [
                str(q) for q in (raw.get("research_queries") or []) if str(q).strip()
            ][:4],
            "candidate_instruments": self._validate_instruments(
                raw.get("candidate_instruments") or [], trace
            ),
            "intent": str(raw.get("intent") or "meeting_prep"),
            "forced_steps": ["portfolio", "compliance", "synthesis"],
            "_generated_by": raw.get("_generated_by", "llm"),
        }
        if not plan["candidate_instruments"]:
            plan["candidate_instruments"] = match_instruments(query)

        trace.note(
            "orchestrator.plan",
            f"Intent '{plan['intent']}' · research={plan['run_research']} · "
            f"instruments={plan['candidate_instruments'] or 'none'}",
            output=plan,
        )
        return plan

    @staticmethod
    def _validate_instruments(raw: list[Any], trace: Trace) -> list[str]:
        """Drop anything not in the product universe, because a hallucinated ticker
        must never reach the rules engine."""
        from tools.portfolio_server import get_instrument

        valid, rejected = [], []
        for item in raw:
            ident = str(item).strip().upper()
            if get_instrument(ident):
                valid.append(ident)
            elif ident:
                rejected.append(ident)
        if rejected:
            trace.note(
                "orchestrator.instrument_guard",
                f"Dropped {len(rejected)} unrecognised instrument id(s): {rejected}",
            )
        return valid

    # -- dispatch ----------------------------------------------------------
    def _dispatch(
        self, recipient: str, task: str, payload: dict[str, Any], trace: Trace
    ) -> Response:
        if not self.router.has(recipient):
            trace.note("orchestrator.unavailable", f"Agent '{recipient}' is not registered")
            return Response(
                sender="orchestrator",
                correlation_id=trace.run_id,
                status="error",
                error=f"Agent '{recipient}' is not registered",
            )
        message = Message(
            sender="orchestrator",
            recipient=recipient,
            task=task,
            payload=payload,
            correlation_id=trace.run_id,
        )
        return self.router.send(message, trace)

    def handle(self, message: Message, trace: Trace) -> Response:
        result = self.run(
            str(message.payload.get("client_id", "")), message.payload.get("query", ""), trace
        )
        if result.get("error"):
            return self.fail(message, result["error"])
        return self.ok(message, result)
