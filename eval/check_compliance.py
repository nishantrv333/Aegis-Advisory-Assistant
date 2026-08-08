"""
The blocking check.

`run_eval.py` reports on everything and exits non-zero if anything fails,
which includes the one documented retrieval gap (G07). That is the right
behaviour for a suite you read, and the wrong behaviour for a gate: a build
that is permanently red teaches everyone to ignore it.

So the two are separated by how much a regression matters:

  retrieval        reported, not blocking. Recall degrading is a quality
                   problem you want visible in the log.
  compliance       blocking, and asserted exactly. Status must match, the
                   designed rules must fire, and forbidden rules must not.

A suitability engine that silently changes its mind between commits is the
one failure this project cannot ship, so that is the thing wired to the gate.

    python eval/check_compliance.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("LLM_PROVIDER", "mock")
os.environ.setdefault("EMBEDDING_MODE", "hash")

from eval.golden_set import GOLDEN_SET  # noqa: E402


def main() -> int:
    from agents import build_system
    from core.trace import Trace

    orchestrator, _ = build_system()

    print(f"\nCOMPLIANCE GATE   llm={orchestrator.llm.provider}   {len(GOLDEN_SET)} cases\n")
    header = f"{'CASE':<6}{'CLIENT':<9}{'EXPECTED':<10}{'ACTUAL':<10}{'RULES':<22}RESULT"
    print(header)
    print("-" * len(header))

    failures: list[str] = []

    for case in GOLDEN_SET:
        trace = Trace()
        result = orchestrator.run(case["client_id"], case["query"], trace)

        if result.get("error") or not result.get("briefing"):
            failures.append(f"{case['id']}: run failed: {result.get('error')}")
            print(f"{case['id']:<6}{case['client_id']:<9}{'·':<10}{'ERROR':<10}{'·':<22}FAIL")
            continue

        compliance = result["briefing"]["compliance"]
        status = compliance["status"]
        raised = {f["rule_id"] for f in compliance["flags"]}

        problems = []
        if status != case["expected_status"]:
            problems.append(f"status {status}, expected {case['expected_status']}")

        missing = [r for r in case["expected_rules"] if r not in raised]
        if missing:
            problems.append(f"designed rules did not fire: {missing}")

        forbidden = [r for r in case["forbidden_rules"] if r in raised]
        if forbidden:
            problems.append(f"forbidden rules fired: {forbidden}")

        ok = not problems
        if not ok:
            failures.append(f"{case['id']} ({case['name']}): " + "; ".join(problems))

        print(
            f"{case['id']:<6}{case['client_id']:<9}{case['expected_status']:<10}{status:<10}"
            f"{(', '.join(sorted(raised)) or '·'):<22}{'ok' if ok else 'FAIL'}"
        )

    print("-" * len(header))

    if failures:
        print(f"\n{len(failures)} compliance regression(s):\n")
        for failure in failures:
            print(f"  ✗ {failure}")
        print(
            "\nThe suitability engine is deterministic, so this is never flaky. "
            "Either a rule changed or a client fixture did."
        )
        return 1

    print(f"\nAll {len(GOLDEN_SET)} compliance cases correct.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
