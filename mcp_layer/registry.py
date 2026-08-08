"""
The tool registry.

This is the in-process transport for the MCP-shaped protocol: agents call
`registry.call(name, args, trace)` and get a ToolResult, exactly as they
would over stdio. Validation, tracing and error containment happen here, in
one place, for every tool.
"""

from __future__ import annotations

from typing import Any, Callable

from core.trace import Trace
from mcp_layer.protocol import (
    JSONSchema,
    Tool,
    ToolResult,
    ToolSpec,
    ToolValidationError,
    validate_arguments,
)


class ToolServer:
    """A named group of tools. One server per capability domain, like MCP."""

    def __init__(self, name: str, description: str = "") -> None:
        self.name = name
        self.description = description
        self._tools: dict[str, Tool] = {}

    def tool(self, name: str, description: str, input_schema: JSONSchema) -> Callable:
        def decorator(fn: Callable[[dict[str, Any]], ToolResult]) -> Callable:
            self._tools[name] = Tool(
                spec=ToolSpec(
                    name=name,
                    description=description,
                    input_schema=input_schema,
                    server=self.name,
                ),
                handler=fn,
            )
            return fn

        return decorator

    def list_tools(self) -> list[ToolSpec]:
        return [t.spec for t in self._tools.values()]

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)


class ToolRegistry:
    """Aggregates every tool server behind one namespace."""

    def __init__(self) -> None:
        self._servers: dict[str, ToolServer] = {}
        self._index: dict[str, tuple[ToolServer, Tool]] = {}

    def mount(self, server: ToolServer) -> None:
        self._servers[server.name] = server
        for tool in server.list_tools():
            entry = server.get(tool.name)
            assert entry is not None
            self._index[tool.name] = (server, entry)

    def list_tools(self) -> list[ToolSpec]:
        return [tool.spec for _, tool in self._index.values()]

    def describe(self) -> str:
        """Compact catalogue for injecting into an LLM planning prompt."""
        lines = []
        for spec in self.list_tools():
            params = ", ".join(spec.input_schema.get("properties", {}).keys())
            lines.append(f"- {spec.name}({params}): {spec.description}")
        return "\n".join(lines)

    def call(self, name: str, arguments: dict[str, Any], trace: Trace) -> ToolResult:
        entry = self._index.get(name)
        if entry is None:
            trace.note("tool.unknown", f"Tool '{name}' is not registered")
            return ToolResult.error(f"Unknown tool '{name}'")

        server, tool = entry
        with trace.span(
            "tool",
            name,
            label=f"tool · {name}",
            input=arguments,
            server=server.name,
        ) as span:
            try:
                cleaned = validate_arguments(tool.spec.input_schema, arguments)
            except ToolValidationError as exc:
                span.status = "error"
                span.error = str(exc)
                return ToolResult.error(f"Invalid arguments for '{name}': {exc}")

            try:
                result = tool.handler(cleaned)
            except Exception as exc:
                span.status = "error"
                span.error = f"{type(exc).__name__}: {exc}"
                return ToolResult.error(f"Tool '{name}' failed: {exc}")

            span.output = result.structured
            if result.is_error:
                span.status = "error"
                span.error = str(result.structured.get("error", "tool reported an error"))
            return result


registry = ToolRegistry()
