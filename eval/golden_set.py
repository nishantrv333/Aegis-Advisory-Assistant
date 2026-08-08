"""
Golden set.

Ten end-to-end cases. Each one runs the full pipeline (orchestrator, tools,
retrieval, rules engine, synthesis) and asserts three things:

  retrieval   the briefing cites the document that actually answers the query
  compliance  the rules engine returns the right status and raises the right rules
  integrity   every citation marker in the prose resolves to a retrieved source

`expected_rules` is a *subset* assertion, not an exact match. A client can
legitimately trip several rules at once (4526 proposes an illiquid product AND
already holds a position above the concentration limit), and pinning the exact
set would make the suite brittle against reasonable data changes. What must
never happen is the designed rule failing to fire, or the status being wrong.

`forbidden_rules` catches the opposite failure: a rule firing where it must not.
"""

from __future__ import annotations

GOLDEN_SET = [
    {
        "id": "G01",
        "name": "High-risk thematic into a Conservative profile",
        "client_id": "4521",
        "query": "Prep me for tomorrow's meeting. The client is asking about the Solaris AI fund",
        "expected_docs": ["FS-SAA-2026Q2"],
        "expected_status": "fail",
        "expected_rules": ["R1"],
        "forbidden_rules": [],
        "rationale": "Risk 6 instrument against a Conservative profile capped at 4.",
    },
    {
        "id": "G02",
        "name": "Illiquid product against a short horizon",
        "client_id": "4526",
        "query": "Client wants to put £150k into Bramble private credit. Can we do it?",
        "expected_docs": ["FS-BPC-2026Q2"],
        "expected_status": "fail",
        "expected_rules": ["R3", "R4"],
        "forbidden_rules": ["R6"],
        "rationale": "Quarterly dealing with gates against High liquidity needs and a 2-year horizon.",
    },
    {
        "id": "G03",
        "name": "Complex leveraged product for a Retail client",
        "client_id": "4527",
        "query": "The client has read about the Lyra leveraged note and wants in",
        "expected_docs": ["FS-LSN-2026Q2"],
        "expected_status": "fail",
        "expected_rules": ["R4"],
        "forbidden_rules": ["R6", "R7"],
        "rationale": "Leveraged structured product recommended to a Retail-classified client.",
    },
    {
        "id": "G04",
        "name": "ESG mandate breach",
        "client_id": "4523",
        "query": "Would the Zephyr precious metals fund work as a diversifier here?",
        "expected_docs": ["FS-ZPM-2026Q2"],
        "expected_status": "fail",
        "expected_rules": ["R5"],
        "forbidden_rules": ["R6"],
        "rationale": "Mining exposure against a documented Mining/Energy/Defence exclusion list.",
    },
    {
        "id": "G05",
        "name": "Cross-border registration",
        "client_id": "4525",
        "query": "Can we add Bramble private credit for this client?",
        "expected_docs": ["FS-BPC-2026Q2"],
        "expected_status": "fail",
        "expected_rules": ["R7"],
        "forbidden_rules": ["R4"],
        "rationale": "Fund is not registered for distribution in Singapore; client is Elective Professional so R4 must not fire.",
    },
    {
        "id": "G06",
        "name": "Stale suitability review blocks advice",
        "client_id": "4524",
        "query": "Annual review. Is the suitability documentation up to date before I advise?",
        "expected_docs": ["POL-SUIT-2026"],
        "expected_status": "fail",
        "expected_rules": ["R6"],
        "forbidden_rules": ["R1", "R3", "R4", "R5", "R7"],
        "rationale": "Review dated Jan 2025 is more than twelve months old.",
    },
    {
        "id": "G07",
        "name": "Concentration in the existing book",
        "client_id": "4522",
        "query": "Review concentration risk in the AI and automation theme before I see him",
        "expected_docs": ["CM-AICAPEX-2026Q3"],
        "expected_status": "review",
        "expected_rules": ["R2"],
        "forbidden_rules": ["R1", "R6"],
        "rationale": "Single position at 31% against a 25% limit; medium severity means review, not fail.",
    },
    {
        "id": "G08",
        "name": "Clean pass, well-constructed portfolio",
        "client_id": "4528",
        "query": "What's the house view on asset allocation I should bring to the meeting?",
        "expected_docs": ["HV-AA-2026Q3"],
        "expected_status": "pass",
        "expected_rules": [],
        "forbidden_rules": ["R1", "R2", "R3", "R4", "R5", "R6", "R7"],
        "rationale": "Control case. No flags should be raised at all.",
    },
    {
        "id": "G09",
        "name": "Rates question, no proposal",
        "client_id": "4521",
        "query": "The client is worried about interest rates and her gilt ladder",
        "expected_docs": ["CM-RATES-2026Q3"],
        "expected_status": "pass",
        "expected_rules": [],
        "forbidden_rules": ["R1", "R2", "R6"],
        "rationale": "No instrument proposed, and the existing book is within Conservative limits.",
    },
    {
        "id": "G10",
        "name": "Suitable proposal that still surfaces an existing flag",
        "client_id": "4522",
        "query": "Should we increase emerging market debt exposure for this client?",
        "expected_docs": ["CM-EM-2026Q3"],
        "expected_status": "review",
        "expected_rules": ["R2"],
        "forbidden_rules": ["R1"],
        "rationale": "EM debt at risk 5 is fine for a Growth profile, but the existing 31% position still flags.",
    },
]
