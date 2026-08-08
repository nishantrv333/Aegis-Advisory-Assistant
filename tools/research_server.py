"""
Research tool server.

Exposes the ChromaDB index as an MCP-style tool. Retrieval returns citable
chunks. Every hit carries doc_id, title and section, because a briefing
that cites "our research" is worthless to the adviser who has to stand
behind it.
"""

from __future__ import annotations

from typing import Any

from config import settings
from mcp_layer.protocol import ToolResult
from mcp_layer.registry import ToolServer
from rag.store import get_store

server = ToolServer(
    name="research",
    description="Vector search over the synthetic market commentary and fund factsheet corpus.",
)

DOC_TYPES = ["fund_factsheet", "market_commentary", "house_view", "research_note", "policy_note"]


@server.tool(
    name="research.search",
    description=(
        "Semantic search over synthetic fund factsheets, market commentary, house views, "
        "research notes and internal policy notes. Returns citable chunks with source ids. "
        "Use one focused query per topic rather than one long combined query."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Natural-language search query"},
            "k": {"type": "integer", "description": "Number of chunks to return", "default": 5},
            "doc_type": {
                "type": "string",
                "description": "Optional filter by document type",
                "enum": DOC_TYPES,
            },
        },
        "required": ["query"],
        "additionalProperties": False,
    },
)
def search(args: dict[str, Any]) -> ToolResult:
    store = get_store()
    k = int(args.get("k") or settings.retrieval_k)
    doc_types = [args["doc_type"]] if args.get("doc_type") else None

    hits = store.search(args["query"], k=k, doc_types=doc_types)
    payload = {
        "query": args["query"],
        "embedding_model": store.embedding_name,
        "hit_count": len(hits),
        "hits": [h.to_dict() for h in hits],
    }
    if not hits:
        return ToolResult.ok(payload, "No matching passages.")

    summary = "; ".join(f"{h.doc_id} ({h.score:.2f})" for h in hits[:5])
    return ToolResult.ok(payload, f"{len(hits)} passages: {summary}")


@server.tool(
    name="research.index_status",
    description="Report how many chunks are indexed and which embedding model is in use.",
    input_schema={"type": "object", "properties": {}, "additionalProperties": False},
)
def index_status(_args: dict[str, Any]) -> ToolResult:
    store = get_store()
    payload = {
        "chunks_indexed": store.count(),
        "collection": store.collection_name,
        "embedding_model": store.embedding_name,
        "corpus_path": str(settings.corpus_path),
    }
    return ToolResult.ok(payload, f"{payload['chunks_indexed']} chunks via {store.embedding_name}.")
