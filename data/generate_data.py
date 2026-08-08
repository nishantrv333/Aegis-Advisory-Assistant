"""
Synthetic data generator.

Everything below is invented. No real person, account, fund or price appears
anywhere in this repository. The names are fictional and the numbers are
made up to exercise the compliance rules. Each client is built to
trigger (or cleanly pass) a specific rule so the eval suite has known
ground truth.

Run:  python data/generate_data.py
"""

from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).parent

# --------------------------------------------------------------------------
# Fund universe. `risk_rating` is a 1-7 SRI-style scale (fictional).
# --------------------------------------------------------------------------
INSTRUMENTS = [
    {
        "instrument_id": "AGE",
        "name": "Aurora Global Equity Fund",
        "asset_class": "Global Equity",
        "risk_rating": 6,
        "risk_band": "High",
        "liquidity": "Daily",
        "ocf_pct": 0.82,
        "sectors": ["Technology", "Financials", "Healthcare", "Energy"],
        "registered_jurisdictions": ["GB", "IE", "CH", "SG", "AE"],
        "leverage": False,
        "doc": "fund_aurora_global_equity.md",
    },
    {
        "instrument_id": "HSD",
        "name": "Helvetia Short-Duration Bond Fund",
        "asset_class": "Fixed Income",
        "risk_rating": 2,
        "risk_band": "Low",
        "liquidity": "Daily",
        "ocf_pct": 0.29,
        "sectors": ["Government", "Investment Grade Credit"],
        "registered_jurisdictions": ["GB", "IE", "CH", "SG", "AE"],
        "leverage": False,
        "doc": "fund_helvetia_short_duration_bond.md",
    },
    {
        "instrument_id": "MED",
        "name": "Meridian Emerging Market Debt Fund",
        "asset_class": "Emerging Market Debt",
        "risk_rating": 5,
        "risk_band": "High",
        "liquidity": "Daily",
        "ocf_pct": 0.95,
        "sectors": ["Sovereign", "Quasi-Sovereign"],
        "registered_jurisdictions": ["GB", "IE", "CH", "AE"],
        "leverage": False,
        "doc": "fund_meridian_em_debt.md",
    },
    {
        "instrument_id": "CBM",
        "name": "Castellan Balanced Multi-Asset Fund",
        "asset_class": "Multi-Asset",
        "risk_rating": 4,
        "risk_band": "Medium",
        "liquidity": "Daily",
        "ocf_pct": 0.61,
        "sectors": ["Equity", "Fixed Income", "Alternatives"],
        "registered_jurisdictions": ["GB", "IE", "CH", "SG", "AE"],
        "leverage": False,
        "doc": "fund_castellan_balanced.md",
    },
    {
        "instrument_id": "NII",
        "name": "Northwind Infrastructure Income Fund",
        "asset_class": "Infrastructure",
        "risk_rating": 4,
        "risk_band": "Medium",
        "liquidity": "Monthly",
        "ocf_pct": 0.88,
        "sectors": ["Utilities", "Transport", "Renewables"],
        "registered_jurisdictions": ["GB", "IE", "CH"],
        "leverage": False,
        "doc": "fund_northwind_infrastructure.md",
    },
    {
        "instrument_id": "SAA",
        "name": "Solaris AI & Automation Thematic Fund",
        "asset_class": "Thematic Equity",
        "risk_rating": 6,
        "risk_band": "High",
        "liquidity": "Daily",
        "ocf_pct": 1.05,
        "sectors": ["Technology", "Semiconductors", "Industrials"],
        "registered_jurisdictions": ["GB", "IE", "AE"],
        "leverage": False,
        "doc": "fund_solaris_ai_thematic.md",
    },
    {
        "instrument_id": "ZPM",
        "name": "Zephyr Precious Metals Fund",
        "asset_class": "Commodities",
        "risk_rating": 6,
        "risk_band": "High",
        "liquidity": "Daily",
        "ocf_pct": 0.74,
        "sectors": ["Mining", "Materials"],
        "registered_jurisdictions": ["GB", "CH", "AE"],
        "leverage": False,
        "doc": "fund_zephyr_precious_metals.md",
    },
    {
        "instrument_id": "BPC",
        "name": "Bramble Private Credit Fund II",
        "asset_class": "Private Credit",
        "risk_rating": 5,
        "risk_band": "High",
        "liquidity": "Quarterly, 5% gate, 90-day notice",
        "ocf_pct": 1.35,
        "sectors": ["Direct Lending", "Speciality Finance"],
        "registered_jurisdictions": ["GB", "IE", "CH"],
        "leverage": True,
        "doc": "fund_bramble_private_credit.md",
    },
    {
        "instrument_id": "LSN",
        "name": "Lyra 3x Leveraged Equity Note 2029",
        "asset_class": "Structured Product",
        "risk_rating": 7,
        "risk_band": "High",
        "liquidity": "Secondary market only",
        "ocf_pct": 1.60,
        "sectors": ["Equity Derivatives"],
        "registered_jurisdictions": ["GB", "CH"],
        "leverage": True,
        "doc": "fund_lyra_structured_note.md",
    },
    {
        "instrument_id": "GILT",
        "name": "UK Gilt Ladder (2027-2032)",
        "asset_class": "Government Bonds",
        "risk_rating": 1,
        "risk_band": "Low",
        "liquidity": "Daily",
        "ocf_pct": 0.10,
        "sectors": ["Government"],
        "registered_jurisdictions": ["GB", "IE", "CH", "SG", "AE"],
        "leverage": False,
        "doc": "commentary_rates_outlook.md",
    },
    {
        "instrument_id": "CASH",
        "name": "GBP Cash & Money Market",
        "asset_class": "Cash",
        "risk_rating": 1,
        "risk_band": "Low",
        "liquidity": "Daily",
        "ocf_pct": 0.05,
        "sectors": ["Cash"],
        "registered_jurisdictions": ["GB", "IE", "CH", "SG", "AE"],
        "leverage": False,
        "doc": "commentary_rates_outlook.md",
    },
]

INSTRUMENT_BY_ID = {i["instrument_id"]: i for i in INSTRUMENTS}


def _holding(instrument_id: str, weight: float, ytd: float, total: float) -> dict:
    inst = INSTRUMENT_BY_ID[instrument_id]
    return {
        "instrument_id": instrument_id,
        "name": inst["name"],
        "asset_class": inst["asset_class"],
        "risk_rating": inst["risk_rating"],
        "risk_band": inst["risk_band"],
        "weight_pct": weight,
        "value_gbp": round(total * weight / 100, 2),
        "ytd_return_pct": ytd,
    }


# --------------------------------------------------------------------------
# Clients. Each one is built to exercise a named compliance rule.
# --------------------------------------------------------------------------
CLIENT_BLUEPRINTS = [
    {
        "client_id": "4521",
        "name": "Margaret Ellwood-Vance (SYNTHETIC)",
        "segment": "Private Client",
        "domicile": "GB",
        "risk_profile": "Conservative",
        "investor_classification": "Retail",
        "horizon_years": 4,
        "liquidity_needs": "High",
        "esg_mandate": False,
        "esg_exclusions": [],
        "last_suitability_review": "2026-05-14",
        "adviser": "J. Okonkwo (synthetic)",
        "total_value_gbp": 2_450_000,
        "objectives": [
            "Preserve capital in real terms",
            "Fund a property purchase in roughly three years",
            "Predictable income to supplement pension drawdown",
        ],
        "constraints": [
            "No single position above 20% of the portfolio",
            "At least 10% held in cash or near-cash",
        ],
        "holdings": [
            ("HSD", 34.0, 2.1),
            ("GILT", 26.0, 1.7),
            ("CBM", 22.0, 4.9),
            ("NII", 6.0, 3.4),
            ("CASH", 12.0, 0.0),
        ],
        "next_meeting": "2026-08-08",
        "notes": "Risk-averse; reacted badly to 2022 drawdown. Values plain explanations.",
        "designed_to_test": "R1 low-risk profile vs high-risk proposals",
    },
    {
        "client_id": "4522",
        "name": "Devesh Ramanathan (SYNTHETIC)",
        "segment": "Private Client",
        "domicile": "GB",
        "risk_profile": "Growth",
        "investor_classification": "Elective Professional",
        "horizon_years": 15,
        "liquidity_needs": "Low",
        "esg_mandate": False,
        "esg_exclusions": [],
        "last_suitability_review": "2026-06-02",
        "adviser": "P. Lindqvist (synthetic)",
        "total_value_gbp": 8_900_000,
        "objectives": [
            "Long-horizon capital growth",
            "Meaningful exposure to the automation and AI capex cycle",
        ],
        "constraints": ["Comfortable with volatility; wants concentration monitored"],
        "holdings": [
            ("SAA", 31.0, 18.4),
            ("AGE", 27.0, 9.6),
            ("MED", 14.0, 5.2),
            ("CBM", 16.0, 4.9),
            ("CASH", 12.0, 0.0),
        ],
        "next_meeting": "2026-08-11",
        "notes": "Founder, sold a logistics software business. Technically literate.",
        "designed_to_test": "R2 single-position concentration above threshold",
    },
    {
        "client_id": "4523",
        "name": "Aoife Brennan-Marsh (SYNTHETIC)",
        "segment": "Private Client",
        "domicile": "IE",
        "risk_profile": "Balanced",
        "investor_classification": "Retail",
        "horizon_years": 10,
        "liquidity_needs": "Medium",
        "esg_mandate": True,
        "esg_exclusions": ["Mining", "Energy", "Defence"],
        "last_suitability_review": "2026-04-28",
        "adviser": "J. Okonkwo (synthetic)",
        "total_value_gbp": 3_150_000,
        "objectives": [
            "Balanced growth consistent with a stated sustainability mandate",
            "No exposure to extractive industries",
        ],
        "constraints": ["Formal ESG exclusion list on file: mining, energy, defence"],
        "holdings": [
            ("CBM", 38.0, 4.9),
            ("HSD", 22.0, 2.1),
            ("NII", 18.0, 3.4),
            ("AGE", 12.0, 9.6),
            ("CASH", 10.0, 0.0),
        ],
        "next_meeting": "2026-08-13",
        "notes": "Trustee of a family foundation; sustainability mandate is non-negotiable.",
        "designed_to_test": "R5 ESG mandate breach",
    },
    {
        "client_id": "4524",
        "name": "Harold Pemberton-Ives (SYNTHETIC)",
        "segment": "Private Client",
        "domicile": "GB",
        "risk_profile": "Conservative",
        "investor_classification": "Retail",
        "horizon_years": 6,
        "liquidity_needs": "Medium",
        "esg_mandate": False,
        "esg_exclusions": [],
        "last_suitability_review": "2025-01-09",
        "adviser": "P. Lindqvist (synthetic)",
        "total_value_gbp": 1_780_000,
        "objectives": ["Steady income", "Modest real growth"],
        "constraints": ["Prefers to avoid single-country concentration"],
        "holdings": [
            ("HSD", 40.0, 2.1),
            ("GILT", 20.0, 1.7),
            ("CBM", 25.0, 4.9),
            ("CASH", 15.0, 0.0),
        ],
        "next_meeting": "2026-08-10",
        "notes": "Annual review is overdue, so chase documentation before advising.",
        "designed_to_test": "R6 stale suitability review",
    },
    {
        "client_id": "4525",
        "name": "Wei-Lin Cheong (SYNTHETIC)",
        "segment": "UHNW",
        "domicile": "SG",
        "risk_profile": "Aggressive",
        "investor_classification": "Elective Professional",
        "horizon_years": 20,
        "liquidity_needs": "Low",
        "esg_mandate": False,
        "esg_exclusions": [],
        "last_suitability_review": "2026-06-19",
        "adviser": "R. Achterberg (synthetic)",
        "total_value_gbp": 21_400_000,
        "objectives": [
            "Aggressive growth with tolerance for illiquidity",
            "Diversify away from single-market equity risk",
        ],
        "constraints": ["Singapore resident, so cross-border registration must be checked"],
        "holdings": [
            ("AGE", 33.0, 9.6),
            ("SAA", 19.0, 18.4),
            ("CBM", 20.0, 4.9),
            ("MED", 13.0, 5.2),
            ("CASH", 15.0, 0.0),
        ],
        "next_meeting": "2026-08-12",
        "notes": "Books through the Singapore branch; product registration is the usual blocker.",
        "designed_to_test": "R7 cross-border registration",
    },
    {
        "client_id": "4526",
        "name": "Sofia Delacroix-Owen (SYNTHETIC)",
        "segment": "Private Client",
        "domicile": "GB",
        "risk_profile": "Balanced",
        "investor_classification": "Retail",
        "horizon_years": 2,
        "liquidity_needs": "High",
        "esg_mandate": False,
        "esg_exclusions": [],
        "last_suitability_review": "2026-03-30",
        "adviser": "R. Achterberg (synthetic)",
        "total_value_gbp": 1_240_000,
        "objectives": [
            "Bridge liquidity ahead of a business buy-out in 2028",
            "Keep pace with inflation without locking capital up",
        ],
        "constraints": ["Must be able to redeem the full portfolio within 30 days"],
        "holdings": [
            ("CBM", 30.0, 4.9),
            ("HSD", 28.0, 2.1),
            ("AGE", 14.0, 9.6),
            ("GILT", 10.0, 1.7),
            ("CASH", 18.0, 0.0),
        ],
        "next_meeting": "2026-08-14",
        "notes": "Short horizon and a hard liquidity date. Illiquid products are out.",
        "designed_to_test": "R3 illiquidity vs horizon/liquidity needs",
    },
    {
        "client_id": "4527",
        "name": "Tomasz Wielgus (SYNTHETIC)",
        "segment": "Private Client",
        "domicile": "GB",
        "risk_profile": "Balanced",
        "investor_classification": "Retail",
        "horizon_years": 12,
        "liquidity_needs": "Low",
        "esg_mandate": False,
        "esg_exclusions": [],
        "last_suitability_review": "2026-05-02",
        "adviser": "P. Lindqvist (synthetic)",
        "total_value_gbp": 4_600_000,
        "objectives": ["Long-term growth", "Interested in structured payoffs"],
        "constraints": ["Retail classification, so complex products need extra justification"],
        "holdings": [
            ("AGE", 24.0, 9.6),
            ("CBM", 26.0, 4.9),
            ("HSD", 20.0, 2.1),
            ("NII", 16.0, 3.4),
            ("CASH", 14.0, 0.0),
        ],
        "next_meeting": "2026-08-17",
        "notes": "Has asked twice about leveraged notes after reading about them.",
        "designed_to_test": "R4 complex/leveraged product for a retail client",
    },
    {
        "client_id": "4528",
        "name": "Beatrix Nkemdirim (SYNTHETIC)",
        "segment": "Private Client",
        "domicile": "GB",
        "risk_profile": "Growth",
        "investor_classification": "Retail",
        "horizon_years": 18,
        "liquidity_needs": "Low",
        "esg_mandate": False,
        "esg_exclusions": [],
        "last_suitability_review": "2026-07-01",
        "adviser": "J. Okonkwo (synthetic)",
        "total_value_gbp": 5_050_000,
        "objectives": ["Long-horizon growth", "Gradual diversification into real assets"],
        "constraints": ["No single position above 25%"],
        "holdings": [
            ("AGE", 22.0, 9.6),
            ("CBM", 24.0, 4.9),
            ("NII", 18.0, 3.4),
            ("HSD", 21.0, 2.1),
            ("CASH", 15.0, 0.0),
        ],
        "next_meeting": "2026-08-18",
        "notes": "Control case: a well-constructed portfolio that should pass cleanly.",
        "designed_to_test": "Clean pass, no flags expected",
    },
]


def build_clients() -> list[dict]:
    clients = []
    for bp in CLIENT_BLUEPRINTS:
        total = bp["total_value_gbp"]
        holdings = [_holding(i, w, y, total) for i, w, y in bp["holdings"]]
        weighted_risk = sum(h["risk_rating"] * h["weight_pct"] for h in holdings) / 100
        ytd = round(sum(h["ytd_return_pct"] * h["weight_pct"] for h in holdings) / 100, 2)
        clients.append(
            {
                "client_id": bp["client_id"],
                "name": bp["name"],
                "data_notice": "SYNTHETIC. Fictional client, not a real person",
                "segment": bp["segment"],
                "domicile": bp["domicile"],
                "adviser": bp["adviser"],
                "risk_profile": bp["risk_profile"],
                "investor_classification": bp["investor_classification"],
                "investment_horizon_years": bp["horizon_years"],
                "liquidity_needs": bp["liquidity_needs"],
                "esg_mandate": bp["esg_mandate"],
                "esg_exclusions": bp["esg_exclusions"],
                "last_suitability_review": bp["last_suitability_review"],
                "next_meeting": bp["next_meeting"],
                "objectives": bp["objectives"],
                "constraints": bp["constraints"],
                "adviser_notes": bp["notes"],
                "designed_to_test": bp["designed_to_test"],
                "portfolio": {
                    "total_value_gbp": total,
                    "currency": "GBP",
                    "as_of": "2026-08-06",
                    "holdings": holdings,
                    "largest_position_pct": max(h["weight_pct"] for h in holdings),
                    "cash_pct": next(
                        (h["weight_pct"] for h in holdings if h["instrument_id"] == "CASH"), 0.0
                    ),
                    "weighted_risk_rating": round(weighted_risk, 2),
                },
                "performance": {
                    "ytd_return_pct": ytd,
                    "one_year_return_pct": round(ytd * 1.9, 2),
                    "three_year_annualised_pct": round(ytd * 1.35, 2),
                    "benchmark": "Synthetic composite benchmark",
                    "vs_benchmark_ytd_pct": round(ytd - 4.4, 2),
                    "volatility_pct": round(2.4 + weighted_risk * 1.9, 2),
                    "max_drawdown_pct": round(-(3.0 + weighted_risk * 2.6), 2),
                },
            }
        )
    return clients


def main() -> None:
    clients = build_clients()
    (HERE / "clients.json").write_text(
        json.dumps(
            {
                "_notice": "SYNTHETIC DATA, generated for a portfolio demo. No real clients.",
                "generated_by": "data/generate_data.py",
                "clients": clients,
            },
            indent=2,
        )
    )
    (HERE / "instruments.json").write_text(
        json.dumps(
            {
                "_notice": "SYNTHETIC DATA, fictional funds. Not investable products.",
                "instruments": INSTRUMENTS,
            },
            indent=2,
        )
    )
    print(f"Wrote {len(clients)} synthetic clients and {len(INSTRUMENTS)} synthetic instruments.")


if __name__ == "__main__":
    main()
