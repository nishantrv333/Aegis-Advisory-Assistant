"""Mount every tool server onto the shared registry, once, at import time."""

from mcp_layer.registry import registry
from tools import compliance_server, portfolio_server, research_server

for _server in (portfolio_server.server, research_server.server, compliance_server.server):
    registry.mount(_server)

__all__ = ["registry"]
