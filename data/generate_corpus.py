"""
Synthetic research corpus.

21 fictional fund factsheets, market commentaries, house-view notes and one
internal policy note. Every fund, figure, author and date is invented.

The documents are deliberately written with distinct vocabulary so that
retrieval quality is measurable: the eval suite asserts which document each
golden query should surface, and that only works if the corpus is not a wall
of interchangeable finance boilerplate.

Run:  python data/generate_corpus.py
"""

from __future__ import annotations

from pathlib import Path

OUT = Path(__file__).parent / "corpus"

DOCS: dict[str, str] = {}

DOCS["fund_aurora_global_equity.md"] = """---
doc_id: FS-AGE-2026Q2
title: Aurora Global Equity Fund Factsheet
type: fund_factsheet
instrument_id: AGE
date: 2026-06-30
tags: [equity, global, developed markets, core holding]
---

# Aurora Global Equity Fund

**Synthetic document. Fictional fund, fictional figures.**

Aurora is a core global developed-market equity strategy holding 60 to 80
positions with a median holding period of four years. The manager, Ines
Villalobos, has run the strategy since its fictional launch in 2014.

**Risk rating:** 6 of 7 (High). **OCF:** 0.82%. **Dealing:** daily.

Aurora returned 9.6% year to date against 8.1% for its composite benchmark.
Attribution was dominated by semiconductor and industrial automation names;
an underweight to European utilities detracted 40 basis points. Regional
weights are 62% North America, 21% Europe, 11% Japan, 6% other developed.

The manager has trimmed the technology overweight from 31% to 26% over the
quarter, citing valuation dispersion rather than a change of view on
earnings. Cash sits at 2.4%.

**Suitability note:** as a single-sleeve equity holding this fund carries
full equity drawdown risk. It is generally unsuitable as a majority position
for clients with a Conservative profile or a horizon under five years.
Maximum peak-to-trough drawdown since launch was 24.8%.
"""

DOCS["fund_helvetia_short_duration_bond.md"] = """---
doc_id: FS-HSD-2026Q2
title: Helvetia Short-Duration Bond Fund Factsheet
type: fund_factsheet
instrument_id: HSD
date: 2026-06-30
tags: [fixed income, short duration, capital preservation, low risk]
---

# Helvetia Short-Duration Bond Fund

**Synthetic document. Fictional fund, fictional figures.**

Helvetia holds investment-grade government and corporate paper with a
weighted average duration of 1.8 years. It exists to be dull: the mandate
caps duration at 2.5 years and prohibits sub-investment-grade credit.

**Risk rating:** 2 of 7 (Low). **OCF:** 0.29%. **Dealing:** daily.

Year-to-date return is 2.1%. Yield to maturity is 4.15%. Average credit
quality is A+, with 38% in sovereigns and 62% in corporates, of which none
sits below BBB-.

Because the fund's duration is short, a 100 basis point parallel shift in
the yield curve moves the price by roughly 1.8%. That insensitivity is the
product, not a limitation of it.

**Suitability note:** commonly used as the ballast sleeve for Conservative
and Balanced mandates, and for clients with liquidity needs inside three
years. Not a growth asset. Real returns after inflation have been close to
zero over rolling five-year windows.
"""

DOCS["fund_meridian_em_debt.md"] = """---
doc_id: FS-MED-2026Q2
title: Meridian Emerging Market Debt Fund Factsheet
type: fund_factsheet
instrument_id: MED
date: 2026-06-30
tags: [emerging markets, sovereign debt, hard currency, high risk]
---

# Meridian Emerging Market Debt Fund

**Synthetic document. Fictional fund, fictional figures.**

Meridian invests in hard-currency sovereign and quasi-sovereign emerging
market debt, with up to 25% in local-currency instruments. Country exposure
is capped at 12% per issuer.

**Risk rating:** 5 of 7 (High). **OCF:** 0.95%. **Dealing:** daily.

Return year to date is 5.2%. The largest exposures are to fictional issuers
in Latin America and South-East Asia. Spread duration is 6.1 years, which
makes the fund materially sensitive to global risk appetite as well as to
US Treasury yields.

Currency is the dominant swing factor in the local-currency sleeve. Dollar
strength has historically been the single largest source of drawdown for
this strategy, ahead of default losses.

**Suitability note:** despite sitting in a fixed income wrapper, this is a
high-risk holding. Clients frequently misread "bond fund" as "defensive".
Advisers should be explicit that drawdowns of 15% or more are within the
normal range for the asset class.
"""

DOCS["fund_castellan_balanced.md"] = """---
doc_id: FS-CBM-2026Q2
title: Castellan Balanced Multi-Asset Fund Factsheet
type: fund_factsheet
instrument_id: CBM
date: 2026-06-30
tags: [multi-asset, balanced, diversified, medium risk]
---

# Castellan Balanced Multi-Asset Fund

**Synthetic document. Fictional fund, fictional figures.**

Castellan runs a 55/35/10 split across equity, fixed income and
alternatives, rebalanced quarterly with a tactical band of plus or minus
ten percentage points on the equity sleeve.

**Risk rating:** 4 of 7 (Medium). **OCF:** 0.61%. **Dealing:** daily.

Year to date the fund returned 4.9%. Equity contributed 3.8 points, fixed
income 0.7, and the alternatives sleeve, chiefly listed infrastructure and
gold, contributed 0.4. Realised volatility over twelve months was 7.9%.

The tactical overlay is currently 3 points underweight equity and holds an
elevated 8% cash position, reflecting the house view that policy rates fall
more slowly than forward markets imply.

**Suitability note:** the default one-fund solution for Balanced mandates
and a common core sleeve inside Conservative portfolios where the client
accepts moderate equity exposure. Worst twelve-month period since launch
was minus 11.2%.
"""

DOCS["fund_northwind_infrastructure.md"] = """---
doc_id: FS-NII-2026Q2
title: Northwind Infrastructure Income Fund Factsheet
type: fund_factsheet
instrument_id: NII
date: 2026-06-30
tags: [infrastructure, real assets, income, inflation linkage, monthly dealing]
---

# Northwind Infrastructure Income Fund

**Synthetic document. Fictional fund, fictional figures.**

Northwind holds listed and semi-listed infrastructure: regulated utilities,
toll transport, and contracted renewables. Around 61% of underlying revenues
carry explicit inflation linkage, which is the reason clients hold it.

**Risk rating:** 4 of 7 (Medium). **OCF:** 0.88%. **Dealing:** monthly, with
a 15-day notice period.

Year-to-date return is 3.4% with a distribution yield of 4.6% paid
quarterly. The fund's sensitivity to long-dated real yields is high; in the
2022 rate shock the strategy fell 17% despite stable underlying cash flows.

**Suitability note:** monthly dealing makes this unsuitable as an emergency
liquidity sleeve. Suitable for Balanced and Growth mandates seeking
inflation-linked income over horizons of five years or more.
"""

DOCS["fund_solaris_ai_thematic.md"] = """---
doc_id: FS-SAA-2026Q2
title: Solaris AI & Automation Thematic Fund Factsheet
type: fund_factsheet
instrument_id: SAA
date: 2026-06-30
tags: [thematic, artificial intelligence, automation, concentrated, high risk]
---

# Solaris AI & Automation Thematic Fund

**Synthetic document. Fictional fund, fictional figures.**

Solaris holds 28 to 35 positions across semiconductors, data-centre
infrastructure, industrial automation and enterprise software. It is a
deliberately concentrated expression of a single theme.

**Risk rating:** 6 of 7 (High). **OCF:** 1.05%. **Dealing:** daily.

The fund returned 18.4% year to date, the strongest in the fictional
Aegis-covered range, and 61% of that came from six holdings. Tracking error
against global equity is 9.2%.

The manager notes that the strategy's fortunes are tied to the capital
expenditure cycle of a small number of hyperscale buyers. A pause in that
cycle would affect revenue expectations across most of the portfolio
simultaneously, and the diversification inside the fund is lower than the
holding count suggests.

**Suitability note:** thematic satellite only. House guidance is a maximum
of 10% of total portfolio value for Balanced mandates and 20% for Growth
and Aggressive mandates. Unsuitable for Conservative profiles in any size.
"""

DOCS["fund_zephyr_precious_metals.md"] = """---
doc_id: FS-ZPM-2026Q2
title: Zephyr Precious Metals Fund Factsheet
type: fund_factsheet
instrument_id: ZPM
date: 2026-06-30
tags: [commodities, gold, mining, diversifier, esg exclusions]
---

# Zephyr Precious Metals Fund

**Synthetic document. Fictional fund, fictional figures.**

Zephyr holds physical gold and silver exposure alongside listed precious
metals miners, split roughly 55/45. The mining sleeve is the source of both
the fund's upside gearing and its volatility.

**Risk rating:** 6 of 7 (High). **OCF:** 0.74%. **Dealing:** daily.

Year to date the fund returned 11.8%. Correlation to global equity over the
last three years was 0.18, which is the diversification case for holding it.

**ESG note:** the mining sleeve includes extractive operations in
jurisdictions with limited environmental disclosure. This fund does not meet
the criteria of any sustainability-labelled mandate and is explicitly
excluded under client mandates carrying a Mining or Energy exclusion.

**Suitability note:** diversifier sleeve, typically capped at 5 to 8% of
portfolio value. Unsuitable for Conservative profiles and for clients with
formal ESG exclusion lists covering mining or extractives.
"""

DOCS["fund_bramble_private_credit.md"] = """---
doc_id: FS-BPC-2026Q2
title: Bramble Private Credit Fund II Factsheet
type: fund_factsheet
instrument_id: BPC
date: 2026-06-30
tags: [private credit, direct lending, illiquid, semi-liquid, gates, leverage]
---

# Bramble Private Credit Fund II

**Synthetic document. Fictional fund, fictional figures.**

Bramble II makes senior secured loans to mid-market borrowers, with a
smaller speciality finance sleeve. The vehicle uses fund-level leverage of
up to 0.4 times net asset value.

**Risk rating:** 5 of 7 (High). **OCF:** 1.35% plus performance fee.

**Liquidity, and please read this carefully.** Dealing is quarterly, subject to a 5%
investor-level gate and 90 days' notice. In a stressed quarter a redeeming
investor may receive a fraction of their request and wait multiple quarters
for the balance. Valuations are manager-marked monthly, not observable
market prices.

Year-to-date return is 6.1% with a running yield of 8.9%.

**Suitability note:** unsuitable where a client has High liquidity needs, a
horizon under seven years, or a known capital call in the near term. The
combination of gates and manager-marked valuations means the reported
volatility of this strategy materially understates its true risk.
"""

DOCS["fund_lyra_structured_note.md"] = """---
doc_id: FS-LSN-2026Q2
title: Lyra 3x Leveraged Equity Note 2029 Product Summary
type: fund_factsheet
instrument_id: LSN
date: 2026-06-30
tags: [structured product, leverage, complex, barrier, capital at risk]
---

# Lyra 3x Leveraged Equity Note 2029

**Synthetic document. Fictional product, fictional figures.**

A three-year note offering three times the upside of a fictional equity
index, capped at 45%, with a 60% European barrier on the downside. If the
index closes below the barrier at maturity, the investor takes the full
index loss with no leverage applied on the way down.

**Risk rating:** 7 of 7 (High). **Fees:** 1.60% embedded. **Liquidity:**
secondary market only; the issuer provides indicative bids but is not
obliged to make a market.

The payoff is asymmetric in the investor's disfavour below the barrier and
capped in their favour above it. Understanding it requires familiarity with
option payoff structures.

**Suitability note:** this is a complex, leveraged instrument. Under the
firm's illustrative policy it may only be recommended to clients classified
as Professional or Elective Professional who have completed a complex
products appropriateness assessment. It must not be recommended to Retail
clients.
"""

DOCS["commentary_rates_outlook.md"] = """---
doc_id: CM-RATES-2026Q3
title: Rates and Central Bank Outlook, Q3 2026
type: market_commentary
date: 2026-07-15
author: Aegis Investment Office (fictional)
tags: [interest rates, central banks, gilts, bank of england, duration]
---

# Rates and central bank outlook

**Synthetic commentary. Illustrative views, not investment advice.**

Our fictional house view is that policy rates fall more slowly than forward
markets currently price. We expect two cuts from the Bank of England over
the next twelve months against the three priced by the market, and one from
the Federal Reserve against two priced.

The reasoning is services inflation, which has proved persistent at around
4.1% year on year while headline inflation has fallen. Wage growth has
decelerated but remains above the level consistent with target inflation.

For portfolios this argues for holding duration at neutral rather than
extending it. Short-duration credit continues to offer most of the yield
with a fraction of the interest rate risk, and gilt ladders remain an
efficient way to lock in known cash flows against dated liabilities.

We would revisit this stance if services inflation prints below 3.5% for two
consecutive months, or if unemployment rises above 5.2%.
"""

DOCS["commentary_equity_outlook.md"] = """---
doc_id: CM-EQ-2026Q3
title: Global Equity Outlook, Q3 2026
type: market_commentary
date: 2026-07-18
author: Aegis Investment Office (fictional)
tags: [equities, valuation, earnings, concentration, market breadth]
---

# Global equity outlook

**Synthetic commentary. Illustrative views, not investment advice.**

Index-level valuations look stretched, but the aggregate figure conceals an
unusually wide dispersion. The largest ten constituents of the global index
account for a fictional 29% of market capitalisation and trade at a 68%
premium to the remaining constituents.

Market breadth has improved modestly this quarter: the equal-weighted index
outperformed the capitalisation-weighted index in two of the last three
months, the first such run in eighteen months.

Earnings revisions are positive in aggregate but negative in consumer
discretionary and European industrials. We remain neutral equity overall,
with a preference for quality balance sheets over momentum, and we are
cautious about adding to concentrated thematic exposure at current levels.

The principal risk to this view is that the capital expenditure cycle
driving current earnings growth proves shorter than expected. See the
separate note on AI capital expenditure.
"""

DOCS["commentary_em_outlook.md"] = """---
doc_id: CM-EM-2026Q3
title: Emerging Markets Outlook, Q3 2026
type: market_commentary
date: 2026-07-20
author: Aegis Investment Office (fictional)
tags: [emerging markets, sovereign debt, dollar, local currency, risk appetite]
---

# Emerging markets outlook

**Synthetic commentary. Illustrative views, not investment advice.**

Emerging market hard-currency spreads have compressed to a fictional 291
basis points, close to the tightest decile of the past decade. That leaves
limited room for further spread-driven return and makes the asset class
increasingly a carry trade rather than a valuation opportunity.

Local-currency debt is the more interesting side of the market. Real policy
rates across the larger emerging economies remain high, and several central
banks began cutting ahead of developed-market peers, which supports local
bond prices.

The dominant risk is dollar strength. A sustained rally in the dollar has
historically been the largest single driver of emerging market debt
drawdowns, exceeding the contribution of actual defaults.

We are neutral on the asset class and would not increase allocations for
clients whose risk profile makes a 15% drawdown unacceptable.
"""

DOCS["commentary_credit_spreads.md"] = """---
doc_id: CM-CRED-2026Q3
title: Credit Spreads and Corporate Balance Sheets, Q3 2026
type: market_commentary
date: 2026-07-22
author: Aegis Investment Office (fictional)
tags: [credit, investment grade, high yield, spreads, refinancing wall]
---

# Credit spreads and corporate balance sheets

**Synthetic commentary. Illustrative views, not investment advice.**

Investment grade spreads sit at a fictional 94 basis points and high yield
at 318. Both are tight relative to history, and both are being supported by
strong technical demand rather than by improving fundamentals.

Interest coverage ratios have deteriorated for a third consecutive quarter
in the lower-quality half of the high yield universe. The 2027-2028
refinancing wall is the specific thing to watch: issuers that borrowed at
2021 coupons will refinance at materially higher ones.

We prefer investment grade to high yield and short duration to long. In
private credit, dispersion between managers is now wider than the spread
premium over public markets, which means manager selection matters more
than the allocation decision itself.
"""

DOCS["commentary_gbp_usd.md"] = """---
doc_id: CM-FX-2026Q3
title: Sterling and Dollar, Currency Note Q3 2026
type: market_commentary
date: 2026-07-24
author: Aegis Investment Office (fictional)
tags: [currency, sterling, dollar, hedging, unhedged exposure]
---

# Sterling and the dollar

**Synthetic commentary. Illustrative views, not investment advice.**

For a sterling-based client, currency is often the largest unmanaged risk in
a global portfolio. A typical 60% North American equity weight leaves around
half of total portfolio value exposed to the dollar.

Our fictional base case is a modestly weaker dollar over twelve months as
rate differentials narrow, with wide error bars.

The practical guidance is unchanged: hedge the fixed income sleeve, where
currency volatility swamps the underlying return, and leave equity largely
unhedged, where currency is a smaller share of total volatility and hedging
costs compound. Clients with near-term sterling liabilities are the
exception and should hedge more of the portfolio.
"""

DOCS["commentary_ai_capex.md"] = """---
doc_id: CM-AICAPEX-2026Q3
title: The AI Capital Expenditure Cycle, Q3 2026
type: market_commentary
date: 2026-07-26
author: Aegis Investment Office (fictional)
tags: [artificial intelligence, capital expenditure, semiconductors, data centres, thematic risk]
---

# The AI capital expenditure cycle

**Synthetic commentary. Illustrative views, not investment advice.**

Aggregate capital expenditure by the largest hyperscale buyers is running at
a fictional $412bn annualised, up 38% year on year. Roughly 44% of that
spend lands with a small group of semiconductor and networking suppliers.

The concentration cuts both ways. It has produced exceptional earnings
growth for those suppliers, and it means the revenue base of an entire
thematic sector depends on the capital allocation decisions of fewer than
ten companies.

Two constraints are worth watching: grid connection queues for new data
centre capacity, and the depreciation schedules being applied to accelerator
hardware. If useful life assumptions prove optimistic, reported earnings
across the buyer group fall without any change in demand.

For clients holding concentrated thematic exposure, this is the argument for
position sizing discipline rather than for exit.
"""

DOCS["house_view_asset_allocation.md"] = """---
doc_id: HV-AA-2026Q3
title: House View, Strategic and Tactical Asset Allocation Q3 2026
type: house_view
date: 2026-07-01
author: Aegis Investment Committee (fictional)
tags: [asset allocation, house view, tactical, strategic, model portfolios]
---

# House view: asset allocation

**Synthetic house view. Illustrative only.**

Tactical positions against strategic weights this quarter:

- Equity: neutral. Valuation is unattractive but earnings momentum is intact.
- Government bonds: neutral duration, preference for the 2 to 5 year part of
  the curve.
- Investment grade credit: modest overweight, funded from high yield.
- High yield: underweight, on spread levels rather than default expectations.
- Real assets: modest overweight, chiefly listed infrastructure.
- Cash: overweight, at 6 to 8% for most mandates, held as optionality.

Model allocations by risk profile are unchanged: Conservative 25% growth
assets, Balanced 50%, Growth 70%, Aggressive 85%.

The committee's stated conviction level this quarter is low. Where
conviction is low, the correct response is smaller active positions, not
more of them.
"""

DOCS["house_view_alternatives.md"] = """---
doc_id: HV-ALTS-2026Q3
title: House View, Alternatives and Private Markets Q3 2026
type: house_view
date: 2026-07-03
author: Aegis Investment Committee (fictional)
tags: [alternatives, private markets, illiquidity premium, gates, allocation limits]
---

# House view: alternatives and private markets

**Synthetic house view. Illustrative only.**

The committee's position is that the illiquidity premium in private credit
has compressed to the point where it no longer compensates for the
governance and liquidity costs in most private client portfolios.

Illustrative allocation limits: private markets exposure should not exceed
15% of total portfolio value for Growth and Aggressive mandates, 5% for
Balanced, and zero for Conservative mandates or any client with High
liquidity needs.

Semi-liquid structures deserve particular scrutiny. Quarterly dealing with
gates offers the appearance of liquidity without the substance, and clients
routinely misunderstand what a gate does until it is applied.

Listed infrastructure and listed real assets remain the committee's
preferred route into real asset exposure for portfolios below £10m, on
governance grounds rather than expected return.
"""

DOCS["research_uk_property.md"] = """---
doc_id: RS-UKPROP-2026
title: UK Commercial Property Research Note
type: research_note
date: 2026-06-12
author: Aegis Research (fictional)
tags: [uk property, real estate, valuation, offices, logistics]
---

# UK commercial property

**Synthetic research. Fictional figures.**

Capital values across the fictional UK all-property index have stabilised
after a 26% peak-to-trough decline, but the recovery is narrow. Logistics
and prime retail parks account for essentially all of the improvement;
secondary offices continue to fall.

Yields on prime logistics sit at 5.1% against 7.9% on secondary offices,
and the gap reflects capital expenditure requirements as much as rental
prospects. Energy performance retrofit costs on older office stock are the
under-discussed liability.

Open-ended property funds remain structurally mismatched: daily-dealing
vehicles holding assets that take months to sell. For clients who want
property exposure with genuine liquidity, listed real estate is the more
honest instrument, at the cost of equity-like volatility in the short run.
"""

DOCS["research_japan_equities.md"] = """---
doc_id: RS-JPEQ-2026
title: Japanese Equities Research Note
type: research_note
date: 2026-06-20
author: Aegis Research (fictional)
tags: [japan, equities, corporate governance, buybacks, yen]
---

# Japanese equities

**Synthetic research. Fictional figures.**

The governance reform story remains the substantive case for Japan. A
fictional 51% of listed companies now trade above one times book value,
against 39% three years ago, and buyback announcements reached a record in
the first half.

Cross-shareholding unwinds are the mechanism that matters. As companies
release long-held stakes in each other, the released capital is being
returned rather than redeployed, which supports valuations directly.

Currency remains the complication for sterling investors. Yen weakness has
consumed a meaningful share of local-currency returns over three years, and
the hedging decision has mattered more to realised outcomes than stock
selection.

We rate Japan a modest overweight within developed-market equity, expressed
through diversified regional exposure rather than a dedicated single-country
sleeve for most private client portfolios.
"""

DOCS["research_esg_transition.md"] = """---
doc_id: RS-ESG-2026
title: Transition Investing and Exclusion Mandates Research Note
type: research_note
date: 2026-06-25
author: Aegis Research (fictional)
tags: [esg, sustainability, exclusions, transition, mandate design]
---

# Transition investing and exclusion mandates

**Synthetic research. Fictional figures.**

Exclusion-based mandates are simple to administer and easy to explain, which
is why most private client sustainability mandates still use them. The cost
is tracking error: a mandate excluding mining, energy and defence carried a
fictional 2.4% annualised tracking error against global equity over five
years, most of it concentrated in 2022.

Advisers should document exclusions precisely at the instrument level rather
than at the sector label. A precious metals fund holding listed miners
breaches a Mining exclusion even when it is described as a diversifier or a
commodity holding, and this is a recurring source of mandate breaches in
practice.

Transition-tilted strategies are the more analytically defensible approach
but require clients to accept holding companies they may find
objectionable today on the argument that they will change.
"""

DOCS["policy_suitability_note.md"] = """---
doc_id: POL-SUIT-2026
title: Internal Note, Suitability Considerations for Advisory Recommendations
type: policy_note
date: 2026-05-30
author: Aegis Advisory Standards (fictional)
tags: [suitability, compliance, risk profile, appropriateness, documentation]
---

# Suitability considerations for advisory recommendations

**Synthetic internal note. Illustrative only. Not regulatory advice, and
not a substitute for the firm's actual policies.**

A recommendation is assessed against four things: the client's risk
profile, their investment horizon and liquidity needs, their knowledge and
experience, and any mandate constraints they have documented.

Recurring failure patterns seen in file reviews:

1. High-risk instruments recommended into Conservative profiles on the
   argument that the position is small. Position size mitigates but does not
   remove the mismatch, and the rationale must be documented.
2. Illiquid or gated products recommended to clients with near-term capital
   needs. Dealing frequency, notice periods and gates must be explained in
   writing before the recommendation is made.
3. Complex or leveraged products recommended to Retail clients without a
   completed appropriateness assessment.
4. Concentration building passively through performance rather than through
   a decision. Positions should be reviewed against limits at every meeting.
5. Advice given on a file where the suitability review is more than twelve
   months old.

Where a flag is raised, the recommendation is not automatically prohibited.
It requires documented rationale, client acknowledgement, and in several
cases second-line sign-off before it proceeds.
"""


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for existing in OUT.glob("*.md"):
        existing.unlink()
    for name, text in DOCS.items():
        (OUT / name).write_text(text.strip() + "\n")
    print(f"Wrote {len(DOCS)} synthetic corpus documents to {OUT}")


if __name__ == "__main__":
    main()
