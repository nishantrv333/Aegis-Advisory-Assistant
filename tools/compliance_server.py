"""
Compliance tool server.

Seven illustrative suitability rules, all deterministic Python. No LLM is
involved in deciding whether something is flagged.

That is a design decision, not a shortcut. A language model is a good
summariser and a poor auditor: you cannot reproduce its judgement, diff it
between releases, or show a reviewer the line of code that produced a flag.
The rules engine is testable and boring; the model's job is to explain what
the engine found, never to overrule it.

These rules are invented for a demo. They are not the FCA Handbook, MiFID II,
or anyone's actual policy.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from mcp_layer.protocol import ToolResult
from mcp_layer.registry import ToolServer
from tools.portfolio_server import all_instruments, get_client_record, get_instrument

server = ToolServer(
    name="compliance",
    description="Deterministic suitability rule checks over synthetic client data.",
)

# Highest instrument risk rating (1-7) tolerated by each risk profile.
MAX_RISK_BY_PROFILE = {"Conservative": 4, "Balanced": 5, "Growth": 6, "Aggressive": 7}
CONCENTRATION_LIMIT_PCT = 25.0
# The limit is about risk-asset concentration, so cash, gilts and short-duration
# investment grade (risk 1-2) are out of scope. Otherwise every conservative
# portfolio flags for holding a large, deliberately boring bond sleeve.
CONCENTRATION_MIN_RISK = 3
SUITABILITY_REVIEW_MONTHS = 12
SHORT_HORIZON_YEARS = 5

RULES = [
    {
        "id": "R1",
        "name": "Risk profile alignment",
        "description": (
            "An instrument's risk rating must not exceed the maximum for the client's risk "
            "profile (Conservative 4, Balanced 5, Growth 6, Aggressive 7)."
        ),
        "severity": "high",
    },
    {
        "id": "R2",
        "name": "Single-position concentration",
        "description": (
            f"No single risk-asset position (risk rating {CONCENTRATION_MIN_RISK} or above) "
            f"should exceed {CONCENTRATION_LIMIT_PCT:.0f}% of portfolio value. Cash, gilts and "
            "short-duration investment grade are out of scope."
        ),
        "severity": "medium",
    },
    {
        "id": "R3",
        "name": "Liquidity match",
        "description": (
            "Instruments dealing less frequently than daily must not be recommended to clients "
            f"with High liquidity needs or a horizon under {SHORT_HORIZON_YEARS} years."
        ),
        "severity": "high",
    },
    {
        "id": "R4",
        "name": "Complex and leveraged products",
        "description": (
            "Leveraged or structured products must not be recommended to Retail-classified "
            "clients without a completed appropriateness assessment."
        ),
        "severity": "high",
    },
    {
        "id": "R5",
        "name": "ESG mandate exclusions",
        "description": (
            "Instruments with sector exposure on the client's documented exclusion list must "
            "not be recommended."
        ),
        "severity": "high",
    },
    {
        "id": "R6",
        "name": "Suitability review currency",
        "description": (
            f"Advice must not be given where the suitability review is more than "
            f"{SUITABILITY_REVIEW_MONTHS} months old."
        ),
        "severity": "high",
    },
    {
        "id": "R7",
        "name": "Cross-border registration",
        "description": (
            "An instrument must be registered for distribution in the client's domicile."
        ),
        "severity": "high",
    },
]

RULE_BY_ID = {r["id"]: r for r in RULES}


def _flag(rule_id: str, instrument_id: str | None, detail: str, remediation: str) -> dict[str, Any]:
    rule = RULE_BY_ID[rule_id]
    return {
        "rule_id": rule_id,
        "rule_name": rule["name"],
        "severity": rule["severity"],
        "instrument_id": instrument_id,
        "detail": detail,
        "remediation": remediation,
    }


def _months_since(iso_date: str, today: date | None = None) -> int:
    today = today or date.today()
    then = datetime.strptime(iso_date, "%Y-%m-%d").date()
    return (today.year - then.year) * 12 + (today.month - then.month)


def _resolve_proposals(raw: list[Any]) -> tuple[list[dict[str, Any]], list[str]]:
    """Accept ids ('BPC') or objects ({'instrument_id': 'BPC', 'weight_pct': 8})."""
    resolved: list[dict[str, Any]] = []
    unknown: list[str] = []
    for item in raw or []:
        if isinstance(item, dict):
            ident = str(item.get("instrument_id") or item.get("id") or "").strip().upper()
            weight = item.get("weight_pct")
        else:
            ident, weight = str(item).strip().upper(), None
        if not ident:
            continue
        instrument = get_instrument(ident)
        if instrument is None:
            unknown.append(ident)
            continue
        resolved.append({**instrument, "proposed_weight_pct": weight})
    return resolved, unknown


@server.tool(
    name="compliance.check_suitability",
    description=(
        "Run the suitability rule set for a client, over their existing holdings and any "
        "proposed instruments. Returns pass/review/fail plus itemised flags with remediation. "
        "Proposals may be instrument ids or objects with instrument_id and weight_pct."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "client_id": {"type": "string", "description": "Client reference, e.g. '4521'"},
            "proposed_instruments": {
                "type": "array",
                "description": "Instruments under consideration for this client",
                "default": [],
            },
            "include_existing_holdings": {
                "type": "boolean",
                "description": "Also check the current book, not just the proposals",
                "default": True,
            },
        },
        "required": ["client_id"],
        "additionalProperties": False,
    },
)
def check_suitability(args: dict[str, Any]) -> ToolResult:
    client = get_client_record(args["client_id"])
    if client is None:
        return ToolResult.error(f"No client with id '{args['client_id']}'")

    proposals, unknown = _resolve_proposals(args.get("proposed_instruments") or [])
    include_existing = bool(args.get("include_existing_holdings", True))

    flags: list[dict[str, Any]] = []
    checks_run: list[str] = []

    profile = client["risk_profile"]
    max_risk = MAX_RISK_BY_PROFILE.get(profile, 5)
    classification = client["investor_classification"]
    horizon = client["investment_horizon_years"]
    liquidity_needs = client["liquidity_needs"]
    exclusions = {e.lower() for e in client.get("esg_exclusions", [])}
    domicile = client["domicile"]

    # --- R6: file-level check, runs whether or not anything is proposed ----
    checks_run.append("R6")
    months = _months_since(client["last_suitability_review"])
    if months > SUITABILITY_REVIEW_MONTHS:
        flags.append(
            _flag(
                "R6",
                None,
                f"Suitability review dated {client['last_suitability_review']} is {months} months "
                f"old, exceeding the {SUITABILITY_REVIEW_MONTHS}-month limit.",
                "Complete a fresh suitability review before giving advice on this file.",
            )
        )

    # --- R2: concentration across existing book ---------------------------
    if include_existing:
        checks_run.append("R2")
        for holding in client["portfolio"]["holdings"]:
            if holding["risk_rating"] < CONCENTRATION_MIN_RISK:
                continue
            if holding["weight_pct"] > CONCENTRATION_LIMIT_PCT:
                flags.append(
                    _flag(
                        "R2",
                        holding["instrument_id"],
                        f"{holding['name']} is {holding['weight_pct']}% of the portfolio, above "
                        f"the {CONCENTRATION_LIMIT_PCT:.0f}% single-position limit.",
                        "Discuss trimming toward the limit, or document a rationale for the "
                        "overweight and the client's acknowledgement.",
                    )
                )

        # Existing high-risk holdings against profile
        checks_run.append("R1-existing")
        for holding in client["portfolio"]["holdings"]:
            if holding["risk_rating"] > max_risk:
                flags.append(
                    _flag(
                        "R1",
                        holding["instrument_id"],
                        f"Existing holding {holding['name']} is risk {holding['risk_rating']}/7, "
                        f"above the maximum of {max_risk}/7 for a {profile} profile.",
                        "Review whether this legacy position is still suitable and document the "
                        "outcome.",
                    )
                )

    # --- Proposal-level checks --------------------------------------------
    for instrument in proposals:
        iid = instrument["instrument_id"]

        checks_run.append(f"R1:{iid}")
        if instrument["risk_rating"] > max_risk:
            flags.append(
                _flag(
                    "R1",
                    iid,
                    f"{instrument['name']} is risk {instrument['risk_rating']}/7 against a maximum "
                    f"of {max_risk}/7 for a {profile} profile.",
                    "Do not recommend, or reduce to a satellite size with documented rationale "
                    "and client acknowledgement.",
                )
            )

        checks_run.append(f"R3:{iid}")
        illiquid = instrument["liquidity"].lower() != "daily"
        if illiquid and (liquidity_needs == "High" or horizon < SHORT_HORIZON_YEARS):
            flags.append(
                _flag(
                    "R3",
                    iid,
                    f"{instrument['name']} deals {instrument['liquidity'].lower()}, against "
                    f"{liquidity_needs.lower()} liquidity needs and a {horizon}-year horizon.",
                    "Explain dealing frequency, notice periods and gates in writing, or select a "
                    "daily-dealing alternative.",
                )
            )

        checks_run.append(f"R4:{iid}")
        complex_product = instrument["leverage"] or instrument["asset_class"] == "Structured Product"
        if complex_product and classification == "Retail":
            flags.append(
                _flag(
                    "R4",
                    iid,
                    f"{instrument['name']} is leveraged or structured and the client is "
                    f"classified {classification}.",
                    "Blocked pending a completed complex products appropriateness assessment and "
                    "second-line sign-off.",
                )
            )

        checks_run.append(f"R5:{iid}")
        if client.get("esg_mandate") and exclusions:
            breached = [s for s in instrument["sectors"] if s.lower() in exclusions]
            if breached:
                flags.append(
                    _flag(
                        "R5",
                        iid,
                        f"{instrument['name']} has exposure to {', '.join(breached)}, which is on "
                        f"the client's documented exclusion list.",
                        "Remove from the recommendation, or obtain a formal, documented mandate "
                        "variation before proceeding.",
                    )
                )

        checks_run.append(f"R7:{iid}")
        if domicile not in instrument["registered_jurisdictions"]:
            flags.append(
                _flag(
                    "R7",
                    iid,
                    f"{instrument['name']} is not registered for distribution in {domicile} "
                    f"(registered: {', '.join(instrument['registered_jurisdictions'])}).",
                    "Do not solicit. Check for an equivalent share class registered in the "
                    "client's domicile.",
                )
            )

        if instrument.get("proposed_weight_pct") is not None:
            checks_run.append(f"R2:{iid}")
            weight = float(instrument["proposed_weight_pct"])
            if weight > CONCENTRATION_LIMIT_PCT:
                flags.append(
                    _flag(
                        "R2",
                        iid,
                        f"Proposed weight of {weight}% in {instrument['name']} exceeds the "
                        f"{CONCENTRATION_LIMIT_PCT:.0f}% single-position limit.",
                        "Reduce the proposed size or document the rationale for the exception.",
                    )
                )

    severities = {f["severity"] for f in flags}
    if "high" in severities:
        status = "fail"
    elif flags:
        status = "review"
    else:
        status = "pass"

    payload = {
        "client_id": client["client_id"],
        "status": status,
        "risk_profile": profile,
        "investor_classification": classification,
        "proposals_checked": [p["instrument_id"] for p in proposals],
        "unknown_instruments": unknown,
        "existing_holdings_checked": include_existing,
        "rules_evaluated": sorted(set(checks_run)),
        "flag_count": len(flags),
        "flags": flags,
        "disclaimer": (
            "Illustrative rules for a demonstration project. Not regulatory advice."
        ),
    }
    if unknown:
        payload["warning"] = f"Unrecognised instruments skipped: {', '.join(unknown)}"

    label = {"pass": "PASS", "review": "REVIEW", "fail": "FAIL"}[status]
    summary = f"{label}. {len(flags)} flag(s) across {len(proposals)} proposal(s)."
    return ToolResult.ok(payload, summary)


@server.tool(
    name="compliance.list_rules",
    description="Return the illustrative suitability rule set with ids, names and severities.",
    input_schema={"type": "object", "properties": {}, "additionalProperties": False},
)
def list_rules(_args: dict[str, Any]) -> ToolResult:
    return ToolResult.ok(
        {
            "rules": RULES,
            "thresholds": {
                "max_risk_by_profile": MAX_RISK_BY_PROFILE,
                "concentration_limit_pct": CONCENTRATION_LIMIT_PCT,
                "concentration_min_risk_rating": CONCENTRATION_MIN_RISK,
                "suitability_review_months": SUITABILITY_REVIEW_MONTHS,
                "short_horizon_years": SHORT_HORIZON_YEARS,
            },
            "disclaimer": "Illustrative only. Not regulatory advice.",
        },
        f"{len(RULES)} illustrative suitability rules.",
    )


@server.tool(
    name="compliance.list_instruments",
    description="List the synthetic product universe available for recommendation.",
    input_schema={"type": "object", "properties": {}, "additionalProperties": False},
)
def list_instruments(_args: dict[str, Any]) -> ToolResult:
    rows = [
        {
            "instrument_id": i["instrument_id"],
            "name": i["name"],
            "asset_class": i["asset_class"],
            "risk_rating": i["risk_rating"],
            "liquidity": i["liquidity"],
        }
        for i in all_instruments()
    ]
    return ToolResult.ok({"instruments": rows}, f"{len(rows)} synthetic instruments.")
