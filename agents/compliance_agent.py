"""
Compliance agent.

The division of labour here is the important bit:

    rules engine  ->  decides.   Deterministic Python, in the tool server.
    language model ->  explains. Never changes status, never adds a flag.

The agent calls the rule tool, then optionally asks the model to write a
plain-English note for the adviser. Before returning, it re-asserts the
engine's `status` and `flags` over whatever the model produced. If the model
returns nothing usable, the deterministic explanation is used instead and the
output is identical in structure.

This is what makes the component auditable: the answer to "why was this
flagged" is a rule id and a line number, not a prompt.
"""

from __future__ import annotations

from typing import Any

from agents.base import BaseAgent, match_instruments
from core.a2a import AgentCard, Message, Response
from core.trace import Trace

EXPLAIN_SYSTEM = """You write compliance notes for advisers at a private bank.

You are given the output of a deterministic suitability rules engine. Your job
is to explain it, not to judge it. You must not change the status, add flags,
remove flags, or soften a finding.

Write plainly, in British English, for an adviser preparing for a meeting.
State what was checked, what was flagged and what they must do before the
meeting. If nothing was flagged, say so without padding.

Return JSON:
{
  "adviser_note": "2-4 sentences",
  "actions_before_meeting": ["imperative action", "..."]
}"""


class ComplianceAgent(BaseAgent):
    card = AgentCard(
        name="compliance",
        title="Compliance Agent",
        description=(
            "Runs the deterministic suitability rule set against the client's holdings and any "
            "proposed instruments, and explains the result."
        ),
        accepts=["check"],
        produces=["compliance_result"],
    )

    def handle(self, message: Message, trace: Trace) -> Response:
        client_id = str(message.payload.get("client_id", "")).strip()
        if not client_id:
            return self.fail(message, "client_id is required")

        proposals = self._resolve_proposals(message.payload, trace)

        result = self.call_tool(
            "compliance.check_suitability",
            {
                "client_id": client_id,
                "proposed_instruments": proposals,
                "include_existing_holdings": True,
            },
            trace,
        )
        if "error" in result and "status" not in result:
            return self.fail(message, result["error"])

        trace.note(
            "compliance.decision",
            f"Status {result['status'].upper()}, {result['flag_count']} flag(s) from "
            f"{len(result['rules_evaluated'])} rule evaluations",
            output={"status": result["status"], "flags": [f["rule_id"] for f in result["flags"]]},
        )

        explanation = self._explain(result, trace)

        # The engine is authoritative. Re-assert it after the model has spoken.
        payload = {
            "status": result["status"],
            "flag_count": result["flag_count"],
            "flags": result["flags"],
            "proposals_checked": result["proposals_checked"],
            "rules_evaluated": result["rules_evaluated"],
            "adviser_note": explanation["adviser_note"],
            "actions_before_meeting": explanation["actions_before_meeting"],
            "disclaimer": result["disclaimer"],
        }
        if result.get("warning"):
            payload["warning"] = result["warning"]
        return self.ok(message, payload)

    # -- proposal resolution ----------------------------------------------
    def _resolve_proposals(self, payload: dict[str, Any], trace: Trace) -> list[str]:
        """
        Work out what is actually being proposed, in priority order:
        the orchestrator's plan, then instruments named in the query itself.
        """
        explicit = payload.get("proposed_instruments") or []
        if explicit:
            trace.note(
                "compliance.proposals",
                f"Checking {len(explicit)} instrument(s) proposed by the orchestrator",
                output=explicit,
            )
            return [str(i).upper() for i in explicit]

        inferred = match_instruments(payload.get("query", ""))
        if inferred:
            trace.note(
                "compliance.proposals",
                f"No explicit proposals, so inferred {inferred} from the request text",
                output=inferred,
            )
            return inferred

        trace.note(
            "compliance.proposals",
            "No proposals identified, checking the existing book only",
        )
        return []

    # -- explanation -------------------------------------------------------
    def _explain(self, result: dict[str, Any], trace: Trace) -> dict[str, Any]:
        fallback = _deterministic_explanation(result)
        if result["flag_count"] == 0 and result["status"] == "pass":
            return fallback  # nothing worth spending a model call on

        summary_lines = [
            f"Status: {result['status'].upper()}",
            f"Client risk profile: {result['risk_profile']}",
            f"Investor classification: {result['investor_classification']}",
            f"Instruments checked: {', '.join(result['proposals_checked']) or 'none'}",
            "Flags:",
        ]
        for flag in result["flags"]:
            summary_lines.append(
                f"- [{flag['rule_id']} · {flag['severity']}] {flag['rule_name']}: "
                f"{flag['detail']} Remediation: {flag['remediation']}"
            )

        explanation = self.llm.complete_json(
            EXPLAIN_SYSTEM,
            "\n".join(summary_lines),
            trace=trace,
            label="compliance.explain",
            fallback=fallback,
        )
        if not isinstance(explanation.get("adviser_note"), str):
            return fallback
        actions = explanation.get("actions_before_meeting")
        if not isinstance(actions, list) or not actions:
            explanation["actions_before_meeting"] = fallback["actions_before_meeting"]
        explanation["actions_before_meeting"] = [
            str(a) for a in explanation["actions_before_meeting"]
        ][:6]
        return explanation


def _deterministic_explanation(result: dict[str, Any]) -> dict[str, Any]:
    if result["status"] == "pass":
        return {
            "adviser_note": (
                f"All {len(result['rules_evaluated'])} suitability checks passed. No flags were "
                "raised against the current holdings or the instruments considered."
            ),
            "actions_before_meeting": ["No compliance actions outstanding."],
            "_generated_by": "deterministic_fallback",
        }

    highs = [f for f in result["flags"] if f["severity"] == "high"]
    note = (
        f"The suitability check returned {result['status'].upper()} with "
        f"{result['flag_count']} flag(s), of which {len(highs)} are high severity. "
        "Each flag below cites the rule that produced it."
    )
    return {
        "adviser_note": note,
        "actions_before_meeting": [f["remediation"] for f in result["flags"]][:6],
        "_generated_by": "deterministic_fallback",
    }
