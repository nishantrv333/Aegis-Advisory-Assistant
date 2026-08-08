"""Agents and the wiring that assembles them into a working system."""

from __future__ import annotations

from agents.compliance_agent import ComplianceAgent
from agents.market_research_agent import MarketResearchAgent
from agents.orchestrator import Orchestrator
from agents.portfolio_agent import PortfolioAgent
from agents.synthesis_agent import SynthesisAgent
from core.a2a import Router
from llm.base import LLMClient
from llm.providers import get_llm_client
from mcp_layer.registry import registry
import tools  # noqa: F401 (importing mounts every tool server


def build_system(llm: LLMClient | None = None) -> tuple[Orchestrator, Router]:
    """
    Compose the system. This is the only place agents, tools and the model
    provider are wired together, which is what makes each of them testable in
    isolation and swappable without touching the others.
    """
    llm = llm or get_llm_client()
    router = Router()
    for agent_cls in (PortfolioAgent, MarketResearchAgent, ComplianceAgent, SynthesisAgent):
        router.register(agent_cls(registry, llm))
    orchestrator = Orchestrator(registry, llm, router)
    return orchestrator, router


__all__ = [
    "Orchestrator",
    "PortfolioAgent",
    "MarketResearchAgent",
    "ComplianceAgent",
    "SynthesisAgent",
    "build_system",
]
