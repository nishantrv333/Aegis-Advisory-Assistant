"""
Aegis configuration.

Everything that might differ between a laptop, CI, and a bank's own
environment is read from the environment here, so no other module needs to
know about os.environ.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

try:  # optional: keeps `python -c "import config"` working without deps
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover
    pass

ROOT = Path(__file__).parent.resolve()


def _bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class Settings:
    # --- LLM -------------------------------------------------------------
    # "groq" | "anthropic" | "mock". "mock" needs no API key and makes the
    # whole system runnable (and evaluable) offline.
    llm_provider: str = os.getenv("LLM_PROVIDER", "groq")
    groq_api_key: str | None = os.getenv("GROQ_API_KEY")
    groq_model: str = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    anthropic_api_key: str | None = os.getenv("ANTHROPIC_API_KEY")
    anthropic_model: str = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5")
    llm_temperature: float = float(os.getenv("LLM_TEMPERATURE", "0.2"))
    llm_max_tokens: int = int(os.getenv("LLM_MAX_TOKENS", "1600"))

    # --- RAG -------------------------------------------------------------
    chroma_path: Path = field(default_factory=lambda: ROOT / os.getenv("CHROMA_PATH", ".chroma"))
    corpus_path: Path = field(default_factory=lambda: ROOT / "data" / "corpus")
    collection_name: str = os.getenv("CHROMA_COLLECTION", "aegis_market_research")
    # "auto" tries Chroma's bundled MiniLM model and falls back to the local
    # hashing embedder if the model can't be downloaded. "hash" forces the
    # offline embedder (used by CI / the eval script).
    embedding_mode: str = os.getenv("EMBEDDING_MODE", "auto")
    chunk_chars: int = int(os.getenv("CHUNK_CHARS", "900"))
    chunk_overlap: int = int(os.getenv("CHUNK_OVERLAP", "150"))
    retrieval_k: int = int(os.getenv("RETRIEVAL_K", "5"))

    # --- Data ------------------------------------------------------------
    clients_path: Path = field(default_factory=lambda: ROOT / "data" / "clients.json")

    # --- App -------------------------------------------------------------
    verbose_trace: bool = _bool("VERBOSE_TRACE", True)


settings = Settings()
