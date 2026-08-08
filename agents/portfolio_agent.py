"""
Portfolio agent.

The thinnest agent in the system, on purpose. It fetches the client's profile
and holdings and derives a few facts the downstream agents need: the
allocation split, the largest position, whether the review is stale.

Why wrap the tools in an agent at all rather than let the orchestrator call
them directly? Because "what does this client look like" is one capability
with one owner. When the real book-of-record has six endpoints, retry
semantics and an entitlements check, that complexity lands here and nothing
upstream changes.
"""

from __future__ import annotations

from typing import Any

from agents.base import BaseAgent
from core.a2a import AgentCard, Message, Response
from core.trace import Trace

# "Growth assets" here means anything rated 4 or above on the 1-7 risk scale.
# Defining it by risk rating rather than by asset-class label keeps it
# consistent with the house-view allocation targets in the corpus.
GROWTH_ASSET_MIN_RISK = 4


class PortfolioAgent(BaseAgent):
    card = AgentCard(
        name="portfolio",
        title="Portfolio Agent",
        description=(
            "Retrieves a client's risk profile, mandate constraints, holdings, weights and "
            "performance from the book of record."
        ),
        accepts=["profile_and_holdings"],
        produces=["client_profile", "portfolio_snapshot"],
    )

    def handle(self, message: Message, trace: Trace) -> Response:
        client_id = str(message.payload.get("client_id", "")).strip()
        if not client_id:
            return self.fail(message, "client_id is required")

        profile = self.call_tool(
            "portfolio.get_client_profile", {"client_id": client_id}, trace
        )
        if "error" in profile:
            return self.fail(message, profile["error"])

        holdings = self.call_tool("portfolio.get_holdings", {"client_id": client_id}, trace)
        if "error" in holdings:
            return self.fail(message, holdings["error"])

        derived = self._derive(profile, holdings)
        trace.note(
            "portfolio.derived",
            f"{derived['growth_asset_pct']}% growth assets, "
            f"largest position {derived['largest_position']['weight_pct']}%",
            output=derived,
        )

        return self.ok(
            message,
            {
                "client_profile": profile,
                "portfolio_snapshot": holdings,
                "derived": derived,
            },
        )

    @staticmethod
    def _derive(profile: dict[str, Any], holdings: dict[str, Any]) -> dict[str, Any]:
        positions = holdings["holdings"]
        growth = sum(
            h["weight_pct"] for h in positions if h["risk_rating"] >= GROWTH_ASSET_MIN_RISK
        )
        by_class: dict[str, float] = {}
        for h in positions:
            by_class[h["asset_class"]] = round(by_class.get(h["asset_class"], 0.0) + h["weight_pct"], 2)

        largest = max(positions, key=lambda h: h["weight_pct"])
        best = max(positions, key=lambda h: h["ytd_return_pct"])
        worst = min(positions, key=lambda h: h["ytd_return_pct"])

        return {
            "growth_asset_pct": round(growth, 2),
            "allocation_by_asset_class": dict(
                sorted(by_class.items(), key=lambda kv: kv[1], reverse=True)
            ),
            "largest_position": {
                "instrument_id": largest["instrument_id"],
                "name": largest["name"],
                "weight_pct": largest["weight_pct"],
            },
            "best_performer": {"name": best["name"], "ytd_return_pct": best["ytd_return_pct"]},
            "worst_performer": {"name": worst["name"], "ytd_return_pct": worst["ytd_return_pct"]},
            "held_instrument_ids": [h["instrument_id"] for h in positions],
            "top_holdings": [
                {"instrument_id": h["instrument_id"], "name": h["name"], "weight_pct": h["weight_pct"]}
                for h in sorted(
                    (p for p in positions if p["risk_rating"] >= GROWTH_ASSET_MIN_RISK),
                    key=lambda h: h["weight_pct"],
                    reverse=True,
                )[:3]
            ],
            "risk_profile": profile["risk_profile"],
            "horizon_years": profile["investment_horizon_years"],
        }
