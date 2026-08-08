"""
Aegis evaluation harness.

    python eval/run_eval.py                  # full end-to-end suite
    python eval/run_eval.py --retrieval-only # RAG only, no agents
    python eval/run_eval.py --provider groq  # run against the real model
    python eval/run_eval.py --case G04       # one case, verbose

Runs the golden set through the whole pipeline and prints a pass/fail table.

Two notes on methodology, because they are the questions worth asking of any
eval like this:

1. It defaults to the mock LLM and the offline embedder. That makes the suite
   deterministic, since the same input gives the same result every time, so a
   failure means something in the retrieval, routing or rules logic actually
   broke, not that a model phrased something differently today. Point it at
   Groq or Anthropic with --provider to check the model-dependent paths.

2. Retrieval is scored as recall@k over document ids: did the passage that
   answers the query make it into the briefing's citations? That is the
   property the downstream summary depends on. It says nothing about whether
   the summary used the passage well, which needs a different kind of eval.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from eval.golden_set import GOLDEN_SET  # noqa: E402

GREEN, RED, YELLOW, DIM, BOLD, RESET = (
    "\033[32m", "\033[31m", "\033[33m", "\033[2m", "\033[1m", "\033[0m"
)


def _c(text: str, colour: str, enabled: bool) -> str:
    return f"{colour}{text}{RESET}" if enabled else text


def run_case(orchestrator, case: dict, colour: bool, verbose: bool) -> dict:
    from core.trace import Trace

    trace = Trace()
    t0 = time.perf_counter()
    result = orchestrator.run(case["client_id"], case["query"], trace)
    elapsed = (time.perf_counter() - t0) * 1000

    checks: list[tuple[str, bool, str]] = []

    if result.get("error") or not result.get("briefing"):
        return {
            "case": case,
            "checks": [("run", False, result.get("error", "no briefing returned"))],
            "passed": False,
            "unexpected": ["run"],
            "fixed": [],
            "elapsed_ms": elapsed,
            "trace": trace,
        }

    briefing = result["briefing"]
    compliance = briefing["compliance"]
    cited_docs = {c["doc_id"] for c in briefing["citations"]}
    raised = {f["rule_id"] for f in compliance["flags"]}

    # 1. retrieval -----------------------------------------------------------
    missing_docs = [d for d in case["expected_docs"] if d not in cited_docs]
    checks.append(
        (
            "retrieval",
            not missing_docs,
            f"missing {missing_docs}" if missing_docs else f"{len(cited_docs)} docs cited",
        )
    )

    # 2. compliance status ---------------------------------------------------
    status_ok = compliance["status"] == case["expected_status"]
    checks.append(
        (
            "status",
            status_ok,
            f"{compliance['status']}"
            + ("" if status_ok else f" (expected {case['expected_status']})"),
        )
    )

    # 3. expected rules fired ------------------------------------------------
    missing_rules = [r for r in case["expected_rules"] if r not in raised]
    checks.append(
        (
            "rules_fired",
            not missing_rules,
            f"missing {missing_rules}" if missing_rules else (", ".join(sorted(raised)) or "none"),
        )
    )

    # 4. forbidden rules did not fire ----------------------------------------
    wrong = [r for r in case["forbidden_rules"] if r in raised]
    checks.append(
        ("no_false_flags", not wrong, f"unexpected {wrong}" if wrong else "clean")
    )

    # 5. citation integrity --------------------------------------------------
    import re

    valid = {c["marker"] for c in briefing["citations"]}
    prose = " ".join(
        [briefing.get("headline", ""), briefing.get("summary", "")]
        + [p.get("point", "") for p in briefing.get("talking_points", [])]
        + [briefing["market_context"].get("summary", "")]
    )
    dangling = {f"S{n}" for n in re.findall(r"\[S(\d+)", prose)} - valid
    checks.append(
        (
            "citations_resolve",
            not dangling,
            f"dangling {sorted(dangling)}" if dangling else f"{len(valid)} sources",
        )
    )

    if verbose:
        print(f"\n{_c('trace', DIM, colour)}")
        for event in trace.events:
            print(f"  {event.kind:<9} {event.status:<7} {event.label[:78]}")
        print(f"\n{_c('headline', DIM, colour)} {briefing['headline']}")

    known = set(case.get("known_failures", []))
    unexpected = [name for name, ok, _ in checks if not ok and name not in known]
    fixed = [name for name, ok, _ in checks if ok and name in known]

    return {
        "case": case,
        "checks": checks,
        "passed": all(ok for _, ok, _ in checks),
        "unexpected": unexpected,
        "fixed": fixed,
        "elapsed_ms": elapsed,
        "trace": trace,
    }


def run_retrieval_only(colour: bool) -> int:
    """RAG in isolation: no agents, no model, just the index."""
    from rag.store import get_store

    store = get_store()
    print(f"\n{_c('RETRIEVAL ONLY', BOLD, colour)}  embedding={store.embedding_name} "
          f"chunks={store.count()}\n")
    header = f"{'CASE':<6}{'EXPECTED DOC':<20}{'RANK':<6}{'RESULT':<8}TOP HITS"
    print(header)
    print("-" * len(header))

    failures = 0
    ranks = []
    for case in GOLDEN_SET:
        hits = store.search(case["query"], k=5)
        docs = [h.doc_id for h in hits]
        known = "retrieval" in case.get("known_failures", [])
        for expected in case["expected_docs"]:
            rank = docs.index(expected) + 1 if expected in docs else 0
            ok = rank > 0
            if ok:
                ranks.append(rank)
            elif not known:
                failures += 1

            if ok:
                label, colour_code = "PASS", GREEN
            elif known:
                label, colour_code = "KNOWN", YELLOW
            else:
                label, colour_code = "FAIL", RED

            print(
                f"{case['id']:<6}{expected:<20}{(str(rank) if rank else '·'):<6}"
                f"{_c(label, colour_code, colour):<8}"
                f"{DIM if colour else ''}{', '.join(dict.fromkeys(docs))[:60]}{RESET if colour else ''}"
            )

    total = len(GOLDEN_SET)
    mrr = sum(1 / r for r in ranks) / total if total else 0
    found = len(ranks)
    print(f"\nrecall@5 {found}/{total}   MRR {mrr:.3f}")
    if failures:
        print(f"{failures} unexpected failure(s)")
    return 1 if failures else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Aegis golden set.")
    parser.add_argument("--provider", default="mock", choices=["mock", "groq", "anthropic"],
                        help="LLM provider (default: mock, for determinism)")
    parser.add_argument("--embedding", default="hash", choices=["hash", "auto"],
                        help="Embedding mode (default: hash, for determinism)")
    parser.add_argument("--case", help="Run a single case id, e.g. G04")
    parser.add_argument("--retrieval-only", action="store_true",
                        help="Test the RAG index without running the agents")
    parser.add_argument("--verbose", action="store_true", help="Print the trace for each case")
    parser.add_argument("--no-colour", action="store_true")
    args = parser.parse_args()

    os.environ["LLM_PROVIDER"] = args.provider
    os.environ["EMBEDDING_MODE"] = args.embedding
    colour = not args.no_colour and sys.stdout.isatty()

    if args.retrieval_only:
        return run_retrieval_only(colour)

    from agents import build_system

    orchestrator, router = build_system()
    from rag.store import get_store

    store = get_store()

    cases = [c for c in GOLDEN_SET if not args.case or c["id"] == args.case.upper()]
    if not cases:
        print(f"No case matching '{args.case}'")
        return 1

    print(f"\n{_c('AEGIS EVAL', BOLD, colour)}   "
          f"llm={orchestrator.llm.provider}/{orchestrator.llm.model}   "
          f"embedding={store.embedding_name}   chunks={store.count()}   "
          f"agents={len(router.cards())}")
    if orchestrator.llm.provider == "mock":
        print(f"{_c('Deterministic mode. Agents use their rule-based fallbacks. '
                   'Use --provider groq to exercise the model paths.', DIM, colour)}")
    print()

    header = (f"{'CASE':<6}{'SCENARIO':<42}{'RETR':<7}{'STATUS':<8}{'RULES':<7}"
              f"{'FALSE+':<8}{'CITES':<7}{'MS':<7}RESULT")
    print(header)
    print("-" * len(header))

    results = []
    for case in cases:
        result = run_case(orchestrator, case, colour, args.verbose)
        results.append(result)
        cells = {name: ok for name, ok, _ in result["checks"]}
        mark = lambda key: _c("ok", GREEN, colour) if cells.get(key) else _c("FAIL", RED, colour)
        if result["passed"]:
            verdict = _c("PASS", GREEN, colour)
        elif not result["unexpected"]:
            verdict = _c("KNOWN", YELLOW, colour)
        else:
            verdict = _c("FAIL", RED, colour)
        print(
            f"{case['id']:<6}{case['name'][:40]:<42}"
            f"{mark('retrieval'):<7}{mark('status'):<8}{mark('rules_fired'):<7}"
            f"{mark('no_false_flags'):<8}{mark('citations_resolve'):<7}"
            f"{result['elapsed_ms']:<7.0f}{verdict}"
        )

    passed = sum(1 for r in results if r["passed"])
    known = sum(1 for r in results if not r["passed"] and not r["unexpected"])
    failed = sum(1 for r in results if r["unexpected"])
    print("-" * len(header))
    print(f"{passed}/{len(results)} cases passed"
          + (f", {known} failing as expected" if known else "")
          + f"   {sum(r['elapsed_ms'] for r in results) / len(results):.0f} ms mean")

    for result in results:
        if result["fixed"]:
            print(f"\n{_c('NOTE', YELLOW, colour)} {result['case']['id']} now passes "
                  f"{result['fixed']}, which it was not expected to. "
                  f"Remove known_failures from the golden set.")

    if known:
        print(f"\n{_c('EXPECTED FAILURES', BOLD, colour)}")
        for result in results:
            if result["passed"] or result["unexpected"]:
                continue
            case = result["case"]
            print(f"  {case['id']} {case['name']}: {', '.join(case.get('known_failures', []))}")
            print(f"    {case.get('known_failure_reason', '')}")

    if failed:
        print(f"\n{_c('FAILURES', BOLD, colour)}")
        for result in results:
            if not result["unexpected"]:
                continue
            case = result["case"]
            print(f"\n  {_c(case['id'], YELLOW, colour)} {case['name']}")
            print(f"    query:     {case['query']}")
            print(f"    rationale: {case['rationale']}")
            for name, ok, detail in result["checks"]:
                if not ok:
                    print(f"    {_c('✗', RED, colour)} {name}: {detail}")

    # Aggregate metrics, the numbers you would actually track over time.
    checks = [(n, ok) for r in results for n, ok, _ in r["checks"]]
    print(f"\n{_c('BY CHECK', BOLD, colour)}")
    for name in ["retrieval", "status", "rules_fired", "no_false_flags", "citations_resolve"]:
        relevant = [ok for n, ok in checks if n == name]
        if relevant:
            rate = sum(relevant) / len(relevant)
            print(f"  {name:<20}{sum(relevant)}/{len(relevant)}  {rate:6.1%}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
