"""
Agent-to-agent (A2A) messaging.

Agents in Aegis never import each other. They exchange typed envelopes
through a router, which is what makes the system genuinely multi-agent
rather than one class calling another class's method.

The envelope mirrors the shape used by A2A-style protocols: a stable
correlation id for the whole run, a task name, a structured payload, and an
artifact list on the way back. Swapping the in-process router for HTTP or a
queue is a change to Router only, with no agent changes.
"""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol

from core.trace import Trace


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


@dataclass
class AgentCard:
    """Capability advertisement, so the orchestrator can plan over agents."""

    name: str
    title: str
    description: str
    accepts: list[str]
    produces: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Message:
    """One request from one agent to another."""

    sender: str
    recipient: str
    task: str
    payload: dict[str, Any] = field(default_factory=dict)
    correlation_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    message_id: str = field(default_factory=lambda: uuid.uuid4().hex[:10])
    created_at: str = field(default_factory=_now)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Response:
    """One reply. `status` is part of the contract, not an exception."""

    sender: str
    correlation_id: str
    status: str = "ok"  # ok | error | refused
    data: dict[str, Any] = field(default_factory=dict)
    artifacts: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class Agent(Protocol):
    card: AgentCard

    def handle(self, message: Message, trace: Trace) -> Response: ...


class Router:
    """In-process message bus with tracing on every hop."""

    def __init__(self) -> None:
        self._agents: dict[str, Agent] = {}

    def register(self, agent: Agent) -> None:
        self._agents[agent.card.name] = agent

    def cards(self) -> list[dict[str, Any]]:
        return [a.card.to_dict() for a in self._agents.values()]

    def has(self, name: str) -> bool:
        return name in self._agents

    def send(self, message: Message, trace: Trace) -> Response:
        agent = self._agents.get(message.recipient)
        if agent is None:
            trace.note(
                "a2a.unroutable",
                f"No agent registered as '{message.recipient}'",
                output={"known": sorted(self._agents)},
            )
            return Response(
                sender="router",
                correlation_id=message.correlation_id,
                status="error",
                error=f"Unknown agent '{message.recipient}'",
            )

        with trace.span(
            "agent",
            message.recipient,
            label=f"{message.sender} → {message.recipient} · {message.task}",
            input=message.payload,
            task=message.task,
        ) as span:
            try:
                response = agent.handle(message, trace)
            except Exception as exc:  # an agent failing must not kill the run
                span.status = "error"
                span.error = f"{type(exc).__name__}: {exc}"
                return Response(
                    sender=message.recipient,
                    correlation_id=message.correlation_id,
                    status="error",
                    error=f"{type(exc).__name__}: {exc}",
                )
            span.output = response.data
            if response.status != "ok":
                span.status = "error"
                span.error = response.error
            return response
