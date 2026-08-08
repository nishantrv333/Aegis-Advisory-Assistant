"""
The LLM abstraction.

Agents depend on this interface and never on a vendor SDK. Groq is used for
development because it is free and very fast to iterate against; the same
agents run against Anthropic's Claude API by changing one env var.

Two methods, deliberately:
  complete()      -> free text
  complete_json() -> parsed dict, with repair and a caller-supplied fallback

complete_json is where most of the value is. Getting structured output out of
an LLM reliably is the difference between a demo and something you would put
in front of an adviser, so the retry/repair/fallback logic lives here once
rather than being reimplemented in every agent.
"""

from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from core.trace import Trace


@dataclass
class LLMResponse:
    text: str
    model: str
    provider: str
    usage: dict[str, Any] = field(default_factory=dict)
    latency_ms: float | None = None


class LLMError(RuntimeError):
    pass


class LLMClient(ABC):
    """Provider-agnostic chat completion client."""

    provider: str = "abstract"
    model: str = "unknown"

    @abstractmethod
    def _complete(self, system: str, user: str, temperature: float, max_tokens: int) -> LLMResponse:
        """Provider-specific call. Implementations do nothing but talk to their SDK."""

    # -- public API -------------------------------------------------------
    def complete(
        self,
        system: str,
        user: str,
        *,
        trace: Trace | None = None,
        label: str = "llm.complete",
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        from config import settings

        temperature = settings.llm_temperature if temperature is None else temperature
        max_tokens = settings.llm_max_tokens if max_tokens is None else max_tokens

        if trace is None:
            return self._complete(system, user, temperature, max_tokens)

        with trace.span(
            "llm",
            label,
            label=f"LLM · {self.provider}/{self.model}",
            input={"system": system, "user": user, "temperature": temperature},
            provider=self.provider,
            model=self.model,
        ) as span:
            response = self._complete(system, user, temperature, max_tokens)
            span.output = response.text
            span.meta["usage"] = response.usage
            return response

    def complete_json(
        self,
        system: str,
        user: str,
        *,
        trace: Trace | None = None,
        label: str = "llm.complete_json",
        fallback: dict[str, Any] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        """Ask for JSON and actually get a dict back, or the fallback."""
        system = system.rstrip() + (
            "\n\nRespond with a single valid JSON object and nothing else. "
            "No prose before or after, no markdown code fences."
        )
        try:
            response = self.complete(
                system,
                user,
                trace=trace,
                label=label,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except Exception as exc:
            if trace:
                trace.note("llm.failed", f"LLM call failed, using fallback: {exc}")
            if fallback is None:
                raise LLMError(str(exc)) from exc
            return dict(fallback)

        parsed = extract_json(response.text)
        if parsed is None:
            if trace:
                trace.note(
                    "llm.unparseable",
                    "Model did not return valid JSON, so using the deterministic fallback",
                    output=response.text[:400],
                )
            if fallback is None:
                raise LLMError("Model did not return parseable JSON")
            return dict(fallback)
        return parsed


def extract_json(text: str) -> dict[str, Any] | None:
    """Pull the first JSON object out of a model response, tolerantly."""
    if not text:
        return None
    candidate = text.strip()

    fenced = re.search(r"```(?:json)?\s*(.*?)```", candidate, re.DOTALL)
    if fenced:
        candidate = fenced.group(1).strip()

    for attempt in (candidate, _first_balanced_object(candidate)):
        if not attempt:
            continue
        try:
            value = json.loads(attempt)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    return None


def _first_balanced_object(text: str) -> str | None:
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    in_string = False
    escaped = False
    for i, ch in enumerate(text[start:], start=start):
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None
