"""
Shared agent scaffolding.

An Aegis agent is a small object with three things: a capability card, a
handle() method taking an A2A Message, and access to the tool registry and
an LLMClient. Nothing else. Agents do not import one another and do not
reach into the router. That keeps the dependency graph a star rather than a
web, and means any agent can be tested on its own.
"""

from __future__ import annotations

import re
from typing import Any

from core.a2a import AgentCard, Message, Response
from core.trace import Trace
from llm.base import LLMClient
from mcp_layer.registry import ToolRegistry


class BaseAgent:
    card: AgentCard

    def __init__(self, registry: ToolRegistry, llm: LLMClient) -> None:
        self.registry = registry
        self.llm = llm

    def handle(self, message: Message, trace: Trace) -> Response:  # pragma: no cover
        raise NotImplementedError

    # -- convenience ------------------------------------------------------
    def call_tool(self, name: str, arguments: dict[str, Any], trace: Trace) -> dict[str, Any]:
        """Call a tool and return its structured payload. Errors come back as data."""
        result = self.registry.call(name, arguments, trace)
        return result.structured

    def ok(self, message: Message, data: dict[str, Any], artifacts: list | None = None) -> Response:
        return Response(
            sender=self.card.name,
            correlation_id=message.correlation_id,
            status="ok",
            data=data,
            artifacts=artifacts or [],
        )

    def fail(self, message: Message, error: str) -> Response:
        return Response(
            sender=self.card.name,
            correlation_id=message.correlation_id,
            status="error",
            error=error,
        )


# ---------------------------------------------------------------------------
# Instrument matching
# ---------------------------------------------------------------------------
_TICKER = re.compile(r"\b([A-Z]{3,4})\b")


def match_instruments(text: str) -> list[str]:
    """
    Pull instrument references out of free text: explicit tickers, full fund
    names, and distinctive single words from a fund's name.

    Deliberately conservative. A false positive here means the compliance
    agent checks something nobody asked about, which is noisy but harmless;
    the orchestrator's LLM-proposed candidates are the primary path and this
    is the backstop for when the model returns nothing.
    """
    from tools.portfolio_server import all_instruments

    if not text:
        return []

    lowered = text.lower()
    found: list[str] = []

    for instrument in all_instruments():
        iid = instrument["instrument_id"]
        name = instrument["name"].lower()
        if iid in _TICKER.findall(text):
            found.append(iid)
            continue
        if name in lowered:
            found.append(iid)
            continue
        # distinctive first word of the fund name, e.g. "bramble", "lyra"
        head = name.split()[0]
        if len(head) >= 4 and re.search(rf"\b{re.escape(head)}\b", lowered):
            found.append(iid)

    seen: set[str] = set()
    ordered = []
    for iid in found:
        if iid not in seen and iid != "CASH":
            seen.add(iid)
            ordered.append(iid)
    return ordered
