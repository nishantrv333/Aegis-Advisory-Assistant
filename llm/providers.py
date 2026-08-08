"""
Concrete LLMClient implementations.

Note how small each one is. All the retry/parse/fallback logic lives in the
base class, so adding a provider is ~20 lines. That is the point of the
abstraction: Groq for fast, free development; Claude for production quality;
Mock so the system (and the eval suite) runs with no API key at all.
"""

from __future__ import annotations

import hashlib
import json
import time
from typing import Any

from config import settings
from llm.base import LLMClient, LLMError, LLMResponse


class GroqClient(LLMClient):
    provider = "groq"

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        try:
            from groq import Groq
        except ImportError as exc:  # pragma: no cover
            raise LLMError("groq SDK not installed. Run: pip install groq") from exc

        key = api_key or settings.groq_api_key
        if not key:
            raise LLMError("GROQ_API_KEY is not set")
        self.model = model or settings.groq_model
        self._client = Groq(api_key=key)

    def _complete(self, system: str, user: str, temperature: float, max_tokens: int) -> LLMResponse:
        t0 = time.perf_counter()
        completion = self._client.chat.completions.create(
            model=self.model,
            temperature=temperature,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        usage: dict[str, Any] = {}
        if getattr(completion, "usage", None):
            usage = {
                "prompt_tokens": completion.usage.prompt_tokens,
                "completion_tokens": completion.usage.completion_tokens,
            }
        return LLMResponse(
            text=completion.choices[0].message.content or "",
            model=self.model,
            provider=self.provider,
            usage=usage,
            latency_ms=round((time.perf_counter() - t0) * 1000, 1),
        )


class AnthropicClient(LLMClient):
    """The production swap-in. Same interface, different SDK."""

    provider = "anthropic"

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        try:
            import anthropic
        except ImportError as exc:  # pragma: no cover
            raise LLMError("anthropic SDK not installed. Run: pip install anthropic") from exc

        key = api_key or settings.anthropic_api_key
        if not key:
            raise LLMError("ANTHROPIC_API_KEY is not set")
        self.model = model or settings.anthropic_model
        self._client = anthropic.Anthropic(api_key=key)

    def _complete(self, system: str, user: str, temperature: float, max_tokens: int) -> LLMResponse:
        t0 = time.perf_counter()
        message = self._client.messages.create(
            model=self.model,
            system=system,
            temperature=temperature,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": user}],
        )
        text = "".join(block.text for block in message.content if block.type == "text")
        return LLMResponse(
            text=text,
            model=self.model,
            provider=self.provider,
            usage={
                "prompt_tokens": message.usage.input_tokens,
                "completion_tokens": message.usage.output_tokens,
            },
            latency_ms=round((time.perf_counter() - t0) * 1000, 1),
        )


class MockClient(LLMClient):
    """
    Deterministic stand-in used by the eval suite and by anyone who clones
    this repo without an API key.

    It does not pretend to be a language model. It returns well-formed,
    schema-correct output derived from the prompt so that every non-LLM part
    of the pipeline (routing, retrieval, rules, assembly, tracing) can be
    tested in isolation from model variance. Agents also pass a deterministic
    `fallback` to complete_json, so a mocked run and a failed-LLM run take the
    same path.
    """

    provider = "mock"
    model = "deterministic-stub"

    def _complete(self, system: str, user: str, temperature: float, max_tokens: int) -> LLMResponse:
        digest = hashlib.sha256((system + user).encode()).hexdigest()[:8]
        payload = {
            "_mock": True,
            "_note": "Deterministic stub output; agents fall back to rule-based assembly.",
            "_digest": digest,
        }
        return LLMResponse(
            text=json.dumps(payload),
            model=self.model,
            provider=self.provider,
            usage={"prompt_tokens": len(system + user) // 4, "completion_tokens": 12},
            latency_ms=0.4,
        )


def get_llm_client(provider: str | None = None) -> LLMClient:
    """
    Factory. Falls back to the mock client rather than crashing, so a missing
    key degrades the demo instead of breaking it.
    """
    provider = (provider or settings.llm_provider).lower()
    try:
        if provider == "groq":
            return GroqClient()
        if provider == "anthropic":
            return AnthropicClient()
        if provider == "mock":
            return MockClient()
        raise LLMError(f"Unknown LLM_PROVIDER '{provider}'")
    except LLMError:
        if provider == "mock":
            raise
        return MockClient()
