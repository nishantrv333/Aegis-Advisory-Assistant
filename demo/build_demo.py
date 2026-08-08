"""
Build the static demo published to GitHub Pages.

    python demo/build_demo.py

Runs the real pipeline locally for a set of scenarios, records the actual
trace and briefing each one produces, and writes them into `docs/` alongside
a copy of the UI. GitHub Pages serves `docs/` as a static site, and the page
detects that there is no backend and replays the recorded runs instead of
calling the API.

The important property: these are recordings of genuine executions, not
hand-written fixtures. The orchestrator really planned, the rules engine
really fired, the retriever really scored those passages. Only the playback
timing is synthesised, because a deterministic run completes in about ten
milliseconds and would otherwise appear instantly.

It records in deterministic mode (mock LLM, offline embedder) so the demo is
reproducible and needs no API key. Pass --provider groq to record runs with
real model-written prose instead.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

SCENARIOS = [
    ("4521", "Prep me for tomorrow's meeting. The client is asking about the Solaris AI fund"),
    ("4526", "Client wants to put £150k into Bramble private credit. Can we do it?"),
    ("4527", "The client has read about the Lyra leveraged note and wants in"),
    ("4522", "Review the portfolio and flag anything I should raise on concentration"),
    ("4523", "Would the Zephyr precious metals fund work as a diversifier here?"),
    ("4524", "Routine annual review. Anything blocking?"),
    ("4525", "Can we add Bramble private credit for this client?"),
    ("4528", "What's the market context I should bring to the meeting?"),
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Record runs and build the static demo.")
    parser.add_argument("--provider", default="mock", choices=["mock", "groq", "anthropic"])
    parser.add_argument("--embedding", default="hash", choices=["hash", "auto"])
    parser.add_argument("--out", default="docs")
    args = parser.parse_args()

    os.environ["LLM_PROVIDER"] = args.provider
    os.environ["EMBEDDING_MODE"] = args.embedding

    from agents import build_system
    from core.trace import Trace
    from mcp_layer.registry import registry
    from rag.store import get_store
    from tools.portfolio_server import get_client_record

    orchestrator, router = build_system()
    store = get_store()

    out = ROOT / args.out
    runs_dir = out / "runs"
    if out.exists():
        shutil.rmtree(out)
    runs_dir.mkdir(parents=True)

    for name in ("style.css", "app.js"):
        shutil.copy(ROOT / "static" / name, out / name)

    # FastAPI serves assets from /static, but Pages serves this site from
    # /<repo-name>/, so absolute paths would 404. Relative paths work in both.
    html = (ROOT / "static" / "index.html").read_text().replace('"/static/', '"./')
    (out / "index.html").write_text(html)

    # GitHub Pages runs Jekyll by default, which ignores files it doesn't
    # recognise. This switches it off so everything is served verbatim.
    (out / ".nojekyll").write_text("")

    records = []
    for client_id, query in SCENARIOS:
        trace = Trace()
        result = orchestrator.run(client_id, query, trace)
        if result.get("error"):
            print(f"  ! {client_id} failed: {result['error']}")
            continue

        filename = f"{client_id}-{len(records):02d}.json"
        (runs_dir / filename).write_text(
            json.dumps(
                {
                    "run_id": trace.run_id,
                    "client_id": client_id,
                    "query": query,
                    "plan": result["plan"],
                    "briefing": result["briefing"],
                    "trace": trace.to_list(),
                    "trace_summary": trace.summary(),
                },
                indent=1,
                ensure_ascii=False,
            )
        )

        client = get_client_record(client_id) or {}
        status = result["briefing"]["compliance"]["status"]
        flags = {f["rule_id"] for f in result["briefing"]["compliance"]["flags"]}
        records.append(
            {
                "file": filename,
                "run_id": trace.run_id,
                "client_id": client_id,
                "client_label": (
                    f"{client_id} · {client.get('name', '').replace(' (SYNTHETIC)', '')} · "
                    f"{client.get('risk_profile', '')}"
                ),
                "query": query,
                "status": status,
            }
        )
        print(f"  recorded {client_id}  {status:<6} {sorted(flags) or '·'}  "
              f"{trace.summary()['events']} events")

    manifest = {
        "meta": {
            "llm": f"{orchestrator.llm.provider}/{orchestrator.llm.model}",
            "embedding": store.embedding_name,
            "chunks": store.count(),
            "agents": len(router.cards()),
            "tools": len(registry.list_tools()),
            "recorded": True,
        },
        "runs": records,
    }
    (runs_dir / "manifest.json").write_text(json.dumps(manifest, indent=1, ensure_ascii=False))

    print(f"\nWrote {len(records)} recorded runs to {out}/")
    print("Preview locally:  python -m http.server -d docs 8080")
    print("Publish:          push, then GitHub Settings > Pages > Deploy from branch > /docs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
