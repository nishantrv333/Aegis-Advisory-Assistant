"""
Execution tracing.

Every agent hop, tool call and LLM call in Aegis is wrapped in a trace span.
The trace is a first-class output of the system, not a debug aid: in a
regulated setting you have to be able to answer "why did the machine say
that?" months after the fact.

A Trace is a flat, ordered list of TraceEvents. Each event carries a parent
id, so the UI can render the flat list as a tree without the writer needing
to build one.
"""

from __future__ import annotations

import time
import uuid
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterator, Literal

EventKind = Literal["agent", "tool", "llm", "retrieval", "rule", "note"]
EventStatus = Literal["running", "ok", "error"]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _truncate(value: Any, limit: int = 4000) -> Any:
    """Keep the trace readable. Big blobs are summarised, not dumped."""
    if isinstance(value, str) and len(value) > limit:
        return value[:limit] + f"… [+{len(value) - limit} chars]"
    if isinstance(value, dict):
        return {k: _truncate(v, limit) for k, v in value.items()}
    if isinstance(value, list):
        if len(value) > 40:
            return [_truncate(v, limit) for v in value[:40]] + [f"… [+{len(value) - 40} items]"]
        return [_truncate(v, limit) for v in value]
    return value


@dataclass
class TraceEvent:
    id: str
    parent_id: str | None
    kind: EventKind
    name: str
    label: str
    started_at: str
    ended_at: str | None = None
    duration_ms: float | None = None
    status: EventStatus = "running"
    input: Any = None
    output: Any = None
    error: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class Trace:
    """Collects TraceEvents for one /briefing request."""

    def __init__(self, run_id: str | None = None) -> None:
        self.run_id = run_id or uuid.uuid4().hex[:12]
        self.events: list[TraceEvent] = []
        self._stack: list[str] = []
        self._t0 = time.perf_counter()
        self._subscribers: list[Any] = []

    # -- subscription (used by the SSE endpoint to stream events live) ----
    def subscribe(self, queue: Any) -> None:
        self._subscribers.append(queue)

    def _publish(self, event: TraceEvent) -> None:
        for q in self._subscribers:
            try:
                q.put_nowait(event.to_dict())
            except Exception:  # pragma: no cover - a slow client must not break a run
                pass

    # -- span API ---------------------------------------------------------
    @contextmanager
    def span(
        self,
        kind: EventKind,
        name: str,
        label: str | None = None,
        input: Any = None,
        **meta: Any,
    ) -> Iterator[TraceEvent]:
        event = TraceEvent(
            id=uuid.uuid4().hex[:10],
            parent_id=self._stack[-1] if self._stack else None,
            kind=kind,
            name=name,
            label=label or name,
            started_at=_now_iso(),
            input=_truncate(input),
            meta=meta,
        )
        self.events.append(event)
        self._stack.append(event.id)
        self._publish(event)
        t0 = time.perf_counter()
        try:
            yield event
        except Exception as exc:
            event.status = "error"
            event.error = f"{type(exc).__name__}: {exc}"
            raise
        else:
            if event.status == "running":
                event.status = "ok"
        finally:
            event.ended_at = _now_iso()
            event.duration_ms = round((time.perf_counter() - t0) * 1000, 1)
            self._stack.pop()
            self._publish(event)

    def note(self, name: str, label: str, output: Any = None, **meta: Any) -> None:
        """A zero-duration marker (decisions, fallbacks, plan choices)."""
        event = TraceEvent(
            id=uuid.uuid4().hex[:10],
            parent_id=self._stack[-1] if self._stack else None,
            kind="note",
            name=name,
            label=label,
            started_at=_now_iso(),
            ended_at=_now_iso(),
            duration_ms=0.0,
            status="ok",
            output=_truncate(output),
            meta=meta,
        )
        self.events.append(event)
        self._publish(event)

    # -- output -----------------------------------------------------------
    @property
    def elapsed_ms(self) -> float:
        return round((time.perf_counter() - self._t0) * 1000, 1)

    def to_list(self) -> list[dict[str, Any]]:
        return [e.to_dict() for e in self.events]

    def summary(self) -> dict[str, Any]:
        by_kind: dict[str, int] = {}
        for e in self.events:
            by_kind[e.kind] = by_kind.get(e.kind, 0) + 1
        return {
            "run_id": self.run_id,
            "events": len(self.events),
            "by_kind": by_kind,
            "errors": sum(1 for e in self.events if e.status == "error"),
            "elapsed_ms": self.elapsed_ms,
        }
