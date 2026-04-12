# Market Regime Reference Guide — Internal Knowledge Base
**Classification:** Millennium Internal — Quantitative Research  
**Maintained by:** RiskSentinel Team / QuantPulse Library  

---

## Overview

This document catalogues historical and hypothetical market regimes used for
strategy stress-testing in the mly-ai `test` command. Each regime is
characterised by its volatility environment, correlation structure, liquidity
conditions, and the primary factor exposures that drove performance.

---

## Regime 1: 2020 Covid Crash (Feb 19 – Mar 23, 2020)

**Duration:** ~33 calendar days  
**Severity:** S&P 500 drawdown of -34 % (fastest bear market in history)

### Characteristics
- **Volatility:** VIX peaked at 82.7 (exceeding 2008 GFC peak of 80.7).
- **Correlation:** Cross-asset correlation surged to 0.92+; classic diversification failed.
- **Liquidity:** Treasury market briefly dislocated; bid-ask spreads on investment-grade ETFs blew out 10–15x.
- **Factor Performance:**
  - Value: -18 % (relative)
  - Momentum: -22 % (reversal of prior trend)
  - Low-vol: -14 % (failed defensive properties)
  - Quality: +3 % (outperformed on relative basis)
- **Sector Impact:** Travel/Leisure (-55 %), Energy (-50 %), Financials (-40 %), Tech (-30 %), Utilities (-15 %).

### Strategies That Broke
- Long/short equity with >2x gross leverage: margin calls forced indiscriminate selling.
- Mean-reversion strategies: volatility regime invalidated historical half-life assumptions.
- Carry trades: all carry positions unwound simultaneously.
- Stat-arb pairs: correlations collapsed → pairs diverged beyond backtest assumptions.

### Lessons for Stress-Testing
1. Assume liquidity disappears for 3+ weeks.
2. Assume correlations converge to 1 across all risk assets.
3. Assume funding is unavailable for leveraged positions.
4. Valuation-based entry signals fail in panic-driven regimes.

---

## Regime 2: 2008 Global Financial Crisis (Sep–Nov 2008 Core Phase)

**Duration:** ~90 trading days (acute phase)  
**Severity:** S&P 500 -47 % peak-to-trough (Oct 2007 – Mar 2009)

### Characteristics
- **Volatility:** VIX peaked at 80.7 on Nov 20, 2008.
- **Correlation:** Credit spreads and equity vol became perfectly correlated.
- **Liquidity:** Interbank lending froze; LIBOR-OIS spread peaked at 364 bps.
- **Key Risks:** Counterparty risk, mark-to-model asset valuation, rehypothecation.

### Strategies That Broke
- Leverage: Bear Stearns and Lehman prime brokerage failures wiped out hedge funds with concentrated collateral.
- Fixed-income relative value: Flight-to-quality disrupted all spread relationships.
- Structured credit: Model assumptions on default correlation (Gaussian copula) catastrophically underestimated tail correlation.

---

## Regime 3: 2022 Rate Shock (Jan – Oct 2022)

**Duration:** ~9 months  
**Severity:** S&P 500 -25 %; NASDAQ -33 %; Bloomberg US Aggregate Bond Index -16 %

### Characteristics
- **Regime Trigger:** Fed pivot from 0 % to 4.5 % in 10 months (fastest hiking cycle since 1980).
- **Volatility:** Sustained elevated vol (VIX 25–35 range) without a single panic spike.
- **Correlation:** Equity-bond correlation flipped positive (+0.6), destroying 60/40 portfolio thesis.
- **Factor Performance:**
  - Value: +16 % (best relative year in a decade)
  - Growth: -31 % (duration-sensitive DCF compression)
  - Momentum: +18 % (early adopters of short growth)
  - Quality: -8 % (high-multiple quality priced like growth)

### Strategies That Broke
- Long duration equity (unprofitable tech/biotech): DCF values destroyed by discount rate surge.
- Risk parity: Both equity and bond legs fell simultaneously.
- SPAC / pre-revenue growth: Liquidity dried up; secondary market discounts of 30–50 %.

---

## Regime 4: 2010 Flash Crash (May 6, 2010)

**Duration:** ~36 minutes  
**Severity:** DJIA -9.2 % intraday (recovered same day)

### Characteristics
- **Trigger:** Large sell order in E-mini S&P futures interacted with HFT liquidity withdrawal.
- **Unique Feature:** Intraday nature — end-of-day P&L looked normal, but intraday drawdowns were extreme.
- **Liquidity:** Market makers withdrew quotes; some stocks traded at $0.01.

### Strategies That Broke
- Market-making algorithms that failed to handle zero-bid situations.
- Stop-loss orders that executed at distressed prices.
- Any strategy relying on continuous quote availability.

---

## Regime 5: 2022 UK Gilts Crisis (Sep–Oct 2022)

**Duration:** ~3 weeks  
**Severity:** 30-year UK gilt yield +150 bps in 3 days; GBP/USD -4 % in one session

### Lessons
- Sovereign bonds are not risk-free in a liability-driven investment (LDI) deleveraging spiral.
- Margin calls can force sales of "safe" assets at distressed prices.
- Contagion can spread through collateral chains faster than risk models assume.

---

## Hypothetical Regimes for Stress-Testing

### H1: AI Bubble Burst (2026 Hypothesis)
- Trigger: Large-cap AI revenue miss + regulatory crackdown.
- Assumed drawdown: Tech -40 %, Utilities/Staples +10 %.
- Duration: 6 months.

### H2: China Invasion of Taiwan (Tail Risk)
- Assumed drawdown: Global equities -30 % in week 1.
- USD surges; Asia ex-Japan -60 %.
- Semiconductor supply chain disruption.

### H3: US Dollar Crisis
- Trigger: Debt-ceiling standoff + credit downgrade.
- DXY -15 %; Gold +30 %; TIPS +10 %; Equities -20 %.

---

*Maintained by RiskSentinel. Reference this document in mly-ai test --regime arguments.*
