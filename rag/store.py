"""
Retrieval layer.

ChromaDB is the vector store. Two things here are worth more than the Chroma
wiring itself:

1. **Chunking that preserves citation.** Documents are split on markdown
   headings and then on size, and every chunk carries its doc_id, title and
   section back through retrieval. Citations in the final briefing point at a
   chunk, not vaguely at a document, so a reviewer can check the claim.

2. **A pluggable embedding function with an offline fallback.** Chroma's
   default embedder downloads an ONNX MiniLM model on first use. On a
   locked-down network that fails, so `HashingEmbedding` provides a
   deterministic bag-of-words embedder that needs no download. Retrieval
   quality is lower, but the system stays runnable and the eval suite stays
   deterministic, which is the trade you want in CI.
"""

from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from config import settings

_FRONT_MATTER = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_TOKEN = re.compile(r"[a-z0-9]+")

_STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "to", "in", "is", "are", "for", "on",
    "at", "by", "with", "as", "that", "this", "it", "be", "from", "has", "have",
    "was", "were", "which", "not", "but", "their", "its", "we", "our",
}


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------
@dataclass
class Chunk:
    chunk_id: str
    doc_id: str
    source_file: str
    title: str
    doc_type: str
    section: str
    text: str
    tags: str


def _parse_front_matter(raw: str) -> tuple[dict[str, str], str]:
    match = _FRONT_MATTER.match(raw)
    if not match:
        return {}, raw
    meta: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        meta[key.strip()] = value.strip().strip("[]")
    return meta, raw[match.end():]


def _split_sections(body: str) -> list[tuple[str, str]]:
    sections: list[tuple[str, str]] = []
    current_heading = "Overview"
    buffer: list[str] = []
    for line in body.splitlines():
        if line.startswith("#"):
            if buffer and any(b.strip() for b in buffer):
                sections.append((current_heading, "\n".join(buffer).strip()))
            current_heading = line.lstrip("#").strip() or "Overview"
            buffer = []
        else:
            buffer.append(line)
    if buffer and any(b.strip() for b in buffer):
        sections.append((current_heading, "\n".join(buffer).strip()))
    return sections or [("Overview", body.strip())]


def _window(text: str, size: int, overlap: int) -> list[str]:
    if len(text) <= size:
        return [text]
    parts: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        if end < len(text):
            pivot = text.rfind(". ", start + size // 2, end)
            if pivot != -1:
                end = pivot + 1
        parts.append(text[start:end].strip())
        if end >= len(text):
            break
        start = max(end - overlap, start + 1)
    return [p for p in parts if p]


def chunk_document(path: Path, chunk_chars: int, overlap: int) -> list[Chunk]:
    raw = path.read_text()
    meta, body = _parse_front_matter(raw)
    doc_id = meta.get("doc_id", path.stem)
    title = meta.get("title", path.stem.replace("_", " ").title())
    doc_type = meta.get("type", "document")
    tags = meta.get("tags", "")

    chunks: list[Chunk] = []
    for heading, section_text in _split_sections(body):
        for i, piece in enumerate(_window(section_text, chunk_chars, overlap)):
            chunks.append(
                Chunk(
                    chunk_id=f"{doc_id}::{len(chunks):02d}",
                    doc_id=doc_id,
                    source_file=path.name,
                    title=title,
                    doc_type=doc_type,
                    section=heading,
                    text=f"{title}: {heading}\n{piece}",
                    tags=tags,
                )
            )
    return chunks


# ---------------------------------------------------------------------------
# Embeddings
# ---------------------------------------------------------------------------
class HashingEmbedding:
    """
    Deterministic, dependency-free embedder: hashed bag of words with sublinear
    term weighting and L2 normalisation, so cosine distance behaves sensibly.

    Not competitive with a real sentence encoder, but it is reproducible, needs
    no network, and is good enough for keyword-heavy financial documents.
    """

    label = "hashing-bow-512"
    dims = 512

    # -- ChromaDB EmbeddingFunction interface -----------------------------
    def __call__(self, input: list[str]) -> list[list[float]]:
        return [self._embed(text) for text in input]

    @staticmethod
    def name() -> str:
        return "hashing-bow-512"

    @staticmethod
    def build_from_config(config: dict[str, Any]) -> "HashingEmbedding":
        return HashingEmbedding()

    def get_config(self) -> dict[str, Any]:
        return {"dims": self.dims}

    def default_space(self) -> str:
        return "cosine"

    def supported_spaces(self) -> list[str]:
        return ["cosine"]

    def is_legacy(self) -> bool:
        return False

    # -- convenience ------------------------------------------------------
    def embed_documents(self, input: list[str]) -> list[list[float]]:
        return [self._embed(t) for t in input]

    def embed_query(self, input: list[str] | str) -> list[list[float]] | list[float]:
        if isinstance(input, str):
            return self._embed(input)
        return [self._embed(t) for t in input]

    def _embed(self, text: str) -> list[float]:
        counts: dict[int, float] = {}
        tokens = [t for t in _TOKEN.findall(text.lower()) if t not in _STOPWORDS and len(t) > 2]
        for token in tokens:
            for form in (token, token[:6]):  # crude stemming: helps recall
                idx = int(hashlib.md5(form.encode()).hexdigest()[:8], 16) % self.dims
                counts[idx] = counts.get(idx, 0.0) + 1.0
        vector = [0.0] * self.dims
        for idx, count in counts.items():
            vector[idx] = 1.0 + math.log(count)
        norm = math.sqrt(sum(v * v for v in vector)) or 1.0
        return [v / norm for v in vector]


def _resolve_embedding(mode: str) -> tuple[Any, str]:
    if mode == "hash":
        return HashingEmbedding(), HashingEmbedding.label
    try:
        from chromadb.utils import embedding_functions

        fn = embedding_functions.DefaultEmbeddingFunction()
        fn(["warmup"])  # force model download here, not mid-request
        return fn, "chroma-default-minilm"
    except Exception:
        return HashingEmbedding(), HashingEmbedding.label + " (fallback)"


# ---------------------------------------------------------------------------
# Store
# ---------------------------------------------------------------------------
@dataclass
class Retrieved:
    chunk_id: str
    doc_id: str
    title: str
    section: str
    source_file: str
    doc_type: str
    text: str
    score: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "doc_id": self.doc_id,
            "title": self.title,
            "section": self.section,
            "source_file": self.source_file,
            "doc_type": self.doc_type,
            "text": self.text,
            "score": self.score,
        }


class ResearchStore:
    """Thin, opinionated wrapper over a Chroma collection."""

    def __init__(self, embedding_mode: str | None = None, persist: bool = True) -> None:
        import chromadb

        mode = embedding_mode or settings.embedding_mode
        self.embedding_fn, self.embedding_name = _resolve_embedding(mode)

        if persist:
            settings.chroma_path.mkdir(parents=True, exist_ok=True)
            self._client = chromadb.PersistentClient(path=str(settings.chroma_path))
        else:
            self._client = chromadb.EphemeralClient()

        suffix = "hash" if "hashing" in self.embedding_name else "dense"
        self.collection_name = f"{settings.collection_name}_{suffix}"
        self._collection = self._client.get_or_create_collection(
            name=self.collection_name,
            embedding_function=self.embedding_fn,
            metadata={"hnsw:space": "cosine"},
        )

    # -- ingest -----------------------------------------------------------
    def count(self) -> int:
        return self._collection.count()

    def ingest(self, corpus_path: Path | None = None, force: bool = False) -> dict[str, Any]:
        corpus_path = corpus_path or settings.corpus_path
        files = sorted(corpus_path.glob("*.md"))
        if not files:
            raise FileNotFoundError(
                f"No corpus documents in {corpus_path}. Run: python data/generate_corpus.py"
            )

        if self.count() > 0 and not force:
            return {
                "status": "already_indexed",
                "chunks": self.count(),
                "documents": len(files),
                "embedding": self.embedding_name,
            }

        if force:
            self._client.delete_collection(self.collection_name)
            self._collection = self._client.get_or_create_collection(
                name=self.collection_name,
                embedding_function=self.embedding_fn,
                metadata={"hnsw:space": "cosine"},
            )

        chunks: list[Chunk] = []
        for path in files:
            chunks.extend(chunk_document(path, settings.chunk_chars, settings.chunk_overlap))

        self._collection.add(
            ids=[c.chunk_id for c in chunks],
            documents=[c.text for c in chunks],
            metadatas=[
                {
                    "doc_id": c.doc_id,
                    "title": c.title,
                    "section": c.section,
                    "source_file": c.source_file,
                    "doc_type": c.doc_type,
                    "tags": c.tags,
                }
                for c in chunks
            ],
        )
        return {
            "status": "indexed",
            "chunks": len(chunks),
            "documents": len(files),
            "embedding": self.embedding_name,
        }

    # -- query ------------------------------------------------------------
    def search(
        self,
        query: str,
        k: int | None = None,
        doc_types: Iterable[str] | None = None,
    ) -> list[Retrieved]:
        k = k or settings.retrieval_k
        where = None
        types = list(doc_types) if doc_types else None
        if types:
            where = {"doc_type": {"$in": types}}

        result = self._collection.query(
            query_texts=[query],
            n_results=min(k, max(self.count(), 1)),
            where=where,
        )

        hits: list[Retrieved] = []
        ids = result.get("ids", [[]])[0]
        docs = result.get("documents", [[]])[0]
        metas = result.get("metadatas", [[]])[0]
        distances = result.get("distances", [[]])[0]

        for chunk_id, text, meta, distance in zip(ids, docs, metas, distances):
            hits.append(
                Retrieved(
                    chunk_id=chunk_id,
                    doc_id=str(meta.get("doc_id", "")),
                    title=str(meta.get("title", "")),
                    section=str(meta.get("section", "")),
                    source_file=str(meta.get("source_file", "")),
                    doc_type=str(meta.get("doc_type", "")),
                    text=text,
                    score=round(1.0 - float(distance), 4),
                )
            )
        return hits


_store: ResearchStore | None = None


def get_store(embedding_mode: str | None = None, persist: bool = True) -> ResearchStore:
    """Module-level singleton. Building the index on every request would be wasteful."""
    global _store
    if _store is None:
        _store = ResearchStore(embedding_mode=embedding_mode, persist=persist)
        _store.ingest()
    return _store


def reset_store() -> None:
    global _store
    _store = None
