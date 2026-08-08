"""
MCP-shaped tool protocol.

Aegis models its tools on the Model Context Protocol rather than on ad-hoc
Python functions. Concretely that means:

  * every tool advertises a name, a human description, and a JSON Schema for
    its inputs (MCP's `tools/list`)
  * every call is `(name, arguments_dict) -> ToolResult` (MCP's `tools/call`)
  * results are content blocks with an `isError` flag, not raised exceptions
  * arguments are validated against the schema before the tool ever runs

Because the tools obey that contract, `mcp_layer/stdio_server.py` can expose
any of them as a genuine MCP server over JSON-RPC/stdio with no changes to
the tool itself, and the in-process registry used by the API is just a
faster transport for the same protocol.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Callable

JSONSchema = dict[str, Any]


@dataclass
class ToolSpec:
    """What `tools/list` returns for one tool."""

    name: str
    description: str
    input_schema: JSONSchema
    server: str = "aegis"

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema,
            "server": self.server,
        }


@dataclass
class ToolResult:
    """What `tools/call` returns. Errors are values, not exceptions."""

    content: list[dict[str, Any]] = field(default_factory=list)
    structured: dict[str, Any] = field(default_factory=dict)
    is_error: bool = False

    @classmethod
    def ok(cls, structured: dict[str, Any], text: str | None = None) -> "ToolResult":
        blocks = [{"type": "text", "text": text}] if text else []
        return cls(content=blocks, structured=structured, is_error=False)

    @classmethod
    def error(cls, message: str) -> "ToolResult":
        return cls(
            content=[{"type": "text", "text": message}],
            structured={"error": message},
            is_error=True,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "content": self.content,
            "structuredContent": self.structured,
            "isError": self.is_error,
        }


@dataclass
class Tool:
    spec: ToolSpec
    handler: Callable[[dict[str, Any]], ToolResult]


class ToolValidationError(ValueError):
    pass


_TYPES: dict[str, tuple[type, ...]] = {
    "string": (str,),
    "number": (int, float),
    "integer": (int,),
    "boolean": (bool,),
    "array": (list,),
    "object": (dict,),
}


def validate_arguments(schema: JSONSchema, arguments: dict[str, Any]) -> dict[str, Any]:
    """
    Small, dependency-free JSON Schema check covering the subset the tools
    use: required, type, enum, default. Enough to stop a hallucinated
    argument reaching a tool, which is the actual risk here.
    """
    if not isinstance(arguments, dict):
        raise ToolValidationError("arguments must be an object")

    properties: dict[str, JSONSchema] = schema.get("properties", {})
    required: list[str] = schema.get("required", [])
    cleaned: dict[str, Any] = {}

    for key in required:
        if key not in arguments or arguments[key] is None:
            raise ToolValidationError(f"missing required argument '{key}'")

    for key, value in arguments.items():
        if key not in properties:
            if schema.get("additionalProperties") is False:
                raise ToolValidationError(f"unexpected argument '{key}'")
            cleaned[key] = value
            continue

        prop = properties[key]
        expected = prop.get("type")
        if expected and expected in _TYPES and value is not None:
            if expected == "number" and isinstance(value, bool):
                raise ToolValidationError(f"'{key}' must be a number")
            if not isinstance(value, _TYPES[expected]):
                raise ToolValidationError(
                    f"'{key}' must be of type {expected}, got {type(value).__name__}"
                )
        if "enum" in prop and value not in prop["enum"]:
            raise ToolValidationError(f"'{key}' must be one of {prop['enum']}")
        cleaned[key] = value

    for key, prop in properties.items():
        if key not in cleaned and "default" in prop:
            cleaned[key] = prop["default"]

    return cleaned


def spec_dicts(specs: list[ToolSpec]) -> list[dict[str, Any]]:
    return [s.to_dict() for s in specs]


def asdict_safe(obj: Any) -> Any:
    try:
        return asdict(obj)
    except TypeError:
        return obj
