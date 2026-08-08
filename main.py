"""
Aegis API layer.

    uvicorn main:app --reload

Two ways to run a briefing:

  POST /api/briefing          synchronous; returns the briefing and the full trace
  GET  /api/briefing/stream   server-sent events; trace events arrive as they happen

The streaming endpoint is what makes the orchestration legible in the UI. The
orchestrator runs in a worker thread and publishes trace events to a queue as
it goes, so the browser sees each agent and tool call appear in real time
rather than receiving a finished transcript.
"""

from __future__ import annotations

import asyncio
import json
import queue
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from agents import build_system
from config import ROOT, settings
from core.trace import Trace
from mcp_layer.registry import registry
from rag.store import get_store

_system: dict[str, Any] = {}


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Build the index and wire the agents once, at startup, not per request."""
    orchestrator, router = build_system()
    store = get_store()
    _system.update(
        {
            "orchestrator": orchestrator,
            "router": router,
            "llm": orchestrator.llm,
            "chunks": store.count(),
            "embedding": store.embedding_name,
        }
    )
    print(
        f"[aegis] ready. llm={orchestrator.llm.provider}/{orchestrator.llm.model} "
        f"embedding={store.embedding_name} chunks={store.count()} "
        f"agents={len(router.cards())} tools={len(registry.list_tools())}"
    )
    yield
    _system.clear()


app = FastAPI(
    title="Aegis",
    description=(
        "Agentic wealth advisory briefing assistant. Portfolio demonstration project. "
        "All data is synthetic."
    ),
    version="0.1.0",
    lifespan=lifespan,
)


class BriefingRequest(BaseModel):
    client_id: str = Field(..., examples=["4521"])
    query: str = Field(..., examples=["Prep me for tomorrow's meeting with client 4521"])


def _run(client_id: str, query: str, trace: Trace) -> dict[str, Any]:
    orchestrator = _system.get("orchestrator")
    if orchestrator is None:  # pragma: no cover (only if lifespan didn't run
        raise RuntimeError("Aegis is not initialised")
    return orchestrator.run(client_id, query, trace)


# ---------------------------------------------------------------------------
# Briefing
# ---------------------------------------------------------------------------
@app.post("/api/briefing")
def create_briefing(request: BriefingRequest) -> dict[str, Any]:
    trace = Trace()
    result = _run(request.client_id.strip().lstrip("#"), request.query.strip(), trace)
    if result.get("error"):
        raise HTTPException(status_code=422, detail=result["error"])
    return {
        "run_id": trace.run_id,
        "plan": result["plan"],
        "briefing": result["briefing"],
        "trace": trace.to_list(),
        "trace_summary": trace.summary(),
    }


# The brief specifies POST /briefing; /api/briefing is the canonical path and
# this keeps both working.
app.add_api_route("/briefing", create_briefing, methods=["POST"])


def _sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


@app.get("/api/briefing/stream")
async def stream_briefing(client_id: str, query: str) -> StreamingResponse:
    trace = Trace()
    events: queue.Queue = queue.Queue()
    trace.subscribe(events)

    client_id = client_id.strip().lstrip("#")
    query = query.strip()

    async def generate() -> AsyncIterator[str]:
        yield _sse("start", {"run_id": trace.run_id, "client_id": client_id, "query": query})
        task = asyncio.create_task(asyncio.to_thread(_run, client_id, query, trace))

        while True:
            drained = False
            while True:
                try:
                    yield _sse("trace", events.get_nowait())
                    drained = True
                except queue.Empty:
                    break
            if task.done():
                break
            if not drained:
                await asyncio.sleep(0.04)

        while True:  # anything published between the last drain and completion
            try:
                yield _sse("trace", events.get_nowait())
            except queue.Empty:
                break

        try:
            result = task.result()
        except Exception as exc:
            yield _sse("error", {"error": f"{type(exc).__name__}: {exc}"})
            return

        if result.get("error"):
            yield _sse("error", {"error": result["error"]})
            return

        yield _sse(
            "result",
            {
                "run_id": trace.run_id,
                "plan": result["plan"],
                "briefing": result["briefing"],
                "trace_summary": trace.summary(),
            },
        )

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ---------------------------------------------------------------------------
# Introspection endpoints, useful in the UI and when explaining the system
# ---------------------------------------------------------------------------
@app.get("/api/clients")
def list_clients() -> dict[str, Any]:
    result = registry.call("portfolio.list_clients", {}, Trace())
    return result.structured


@app.get("/api/agents")
def list_agents() -> dict[str, Any]:
    router = _system.get("router")
    return {"agents": router.cards() if router else []}


@app.get("/api/tools")
def list_tools() -> dict[str, Any]:
    return {"tools": [spec.to_dict() for spec in registry.list_tools()]}


@app.get("/api/rules")
def list_rules() -> dict[str, Any]:
    return registry.call("compliance.list_rules", {}, Trace()).structured


@app.get("/api/health")
def health() -> dict[str, Any]:
    llm = _system.get("llm")
    return {
        "status": "ok",
        "llm_provider": getattr(llm, "provider", settings.llm_provider),
        "llm_model": getattr(llm, "model", None),
        "using_mock_llm": getattr(llm, "provider", "") == "mock",
        "embedding_model": _system.get("embedding"),
        "chunks_indexed": _system.get("chunks"),
        "agents": len(_system.get("router").cards()) if _system.get("router") else 0,
        "tools": len(registry.list_tools()),
        "data_notice": "All client and market data in this system is synthetic.",
    }


# ---------------------------------------------------------------------------
# Static UI
# ---------------------------------------------------------------------------
STATIC_DIR = Path(ROOT) / "static"


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
