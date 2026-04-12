# Quantitative Risk Management Frameworks — Internal Reference
**Classification:** Millennium Internal — Risk & Compliance  
**Owner:** RiskSentinel Platform Team  
**Version:** 4.2  

---

## 1. Firm-Wide Risk Limits

All strategies deployed on Millennium's TradingEdge platform must comply with
the following hard limits before live execution approval:

| Risk Metric              | Hard Limit         | Soft Limit (Alert)  |
|--------------------------|--------------------|---------------------|
| Portfolio VaR (95 %, 1D) | 2 % of AUM         | 1.5 % of AUM        |
| CVaR / Expected Shortfall| 3.5 % of AUM       | 2.5 % of AUM        |
| Max Single-Name Exposure | 8 % of portfolio   | 5 % of portfolio    |
| Gross Leverage           | 8x                 | 6x                  |
| Net Leverage             | 2x                 | 1.5x                |
| Sector Concentration     | 30 % gross         | 20 % gross          |
| Max Daily Loss (stop)    | 5 % of AUM         | 3 % of AUM          |
| Liquidity Ratio          | 15-day ADV ≤ 20 %  | ≤ 15 %              |

---

## 2. Strategy Approval Checklist

Before any new strategy is onboarded to TradingEdge, the following must pass:

### 2.1 Backtesting Standards
- [ ] Minimum backtest period: 10 years (must include GFC and COVID)
- [ ] Out-of-sample period: ≥ 3 years
- [ ] Transaction cost model includes: commissions + slippage + market impact
- [ ] No look-ahead bias: all data aligned to point-in-time
- [ ] Walk-forward validation completed with rolling 12-month windows
- [ ] Monte Carlo simulation: 10,000 paths, minimum 1,000 paths profitable

### 2.2 Statistical Robustness
- [ ] Sharpe ratio ≥ 0.8 (net of all costs) over full period
- [ ] Maximum drawdown ≤ 25 % in backtested period
- [ ] Calmar ratio ≥ 0.5
- [ ] Skewness of returns: not more negative than -1.5
- [ ] No single trade contributing more than 15 % of total returns

### 2.3 Code Review (Security)
All strategy code is reviewed by the SignalForge compliance scanner before
deployment. Common rejection reasons:
- Use of `eval()` or `exec()` with dynamic strings
- Network calls to external endpoints (all data must come from DataVault APIs)
- Hardcoded credentials or API keys
- File system writes outside approved `/tmp/millennium_sandbox/` directory
- Use of `pickle` for untrusted data deserialisation
- Subprocess calls that could exfiltrate positions data

---

## 3. Risk Model Architecture

### 3.1 Factor Risk Model (QuantPulse v7)

Millennium's proprietary factor model decomposes portfolio risk into:

**Macro Factors (10):**
1. Market Beta
2. Interest Rate Duration
3. Credit Spread
4. USD Strength
5. Oil/Commodity
6. VIX / Vol-of-Vol
7. Inflation Expectations (breakeven)
8. China Growth Proxy
9. Growth vs Value
10. Momentum (12-1 month)

**Industry Factors (24):** GICS level-2 classification

**Statistical Factors (5):** PCA-extracted from residual covariance

### 3.2 Stress Testing Protocol

All portfolios are stress-tested monthly against the following scenarios
(see `market_regimes.md` for full scenario definitions):

1. 2008 GFC (severe)
2. 2020 COVID Crash
3. 2022 Rate Shock
4. Flash Crash (microstructure)
5. Firm-specific tail (custom per strategy)

### 3.3 Liquidity Risk

The AlphaStream liquidity module monitors:
- ADV-weighted time-to-liquidate at 10 %, 20 %, 30 % market participation
- Bid-ask spread evolution under stress (using 2020 regime as baseline)
- Portfolio-level liquidation cost (LiquidityMesh model)

---

## 4. Common Strategy Vulnerabilities (Red-Team Checklist)

Risk Managers use this checklist during adversarial reviews:

### 4.1 Data Assumptions
- Does the strategy assume clean, continuous data? (Gaps, halts, corporate actions)
- Does it assume fixed tick size? (Decimalization, exchange rule changes)
- Does it assume T+2 settlement? (Could fail with T+1 or instant settlement)

### 4.2 Execution Assumptions
- Does it assume infinite liquidity at mid-price? (Dangerous for >1 % ADV strategies)
- Does it ignore market impact? (Position sizing must account for Kyle lambda)
- Does it assume simultaneous fills for multi-leg strategies? (Leg risk)

### 4.3 Regime Assumptions
- Does the strategy implicitly assume a low-VIX environment?
- Does it assume positive equity-bond correlation or negative? (Both have failed)
- Does it rely on mean-reversion that breaks in trending markets?
- Does it have hidden exposure to carry (borrowing short, lending long in volatility)?

### 4.4 Overfitting Red Flags
- More parameters than number of regime-changes in backtest
- Sharpe > 3.0 in backtest (likely overfitted unless HFT with real edge)
- Maximum drawdown in backtest < 5 % over 10+ years (suspicious)
- Parameter sensitivity: if ±10 % parameter change degrades Sharpe > 30 %, suspect

---

## 5. Emergency Protocols

### 5.1 Stop-Loss Triggers
When a strategy hits the daily 5 % loss limit:
1. TradingEdge auto-halts new order generation immediately.
2. OmegaBook sends alert to pod head and Risk Desk.
3. Positions are liquidated at 15 % market participation rate (to minimise impact).
4. Strategy quarantined for 48-hour review.

### 5.2 Liquidity Crisis Mode
If market-wide liquidity drops below crisis threshold (defined as bid-ask spreads
> 5x normal across ≥ 3 major asset classes):
1. All new position-opening trades halted.
2. Gross leverage reduced to 4x within 5 trading days.
3. Portfolio shifted to ≥ 20-day ADV coverage on all positions.

---

*Classification: Millennium Internal. RiskSentinel platform enforces these limits programmatically.*
