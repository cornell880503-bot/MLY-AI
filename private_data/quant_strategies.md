# Quantitative Strategy Templates & Performance Archive
**Classification:** Millennium Internal — Alpha Research  
**Owner:** QuantPulse / SignalForge Team  
**Updated:** Q4 2025  

---

## Overview

This document catalogues strategy archetypes, their historical performance
characteristics, and known failure modes. Use this as reference context when
generating new strategy code via `mly-ai code` or red-teaming with `mly-ai test`.

---

## Strategy Archetype 1: Cross-Sectional Momentum (CSM)

**Description:** Rank universe by trailing 12-1 month return. Long top decile, short bottom decile. Monthly rebalance.

### Performance Metrics (US Large-Cap, 2005–2025)
| Metric              | Value      |
|---------------------|------------|
| Annualised Return   | +11.2 %    |
| Sharpe Ratio        | 0.92       |
| Max Drawdown        | -42 %      |
| Calmar Ratio        | 0.27       |
| Annual Turnover     | ~200 %     |

### Known Failure Modes
- **Momentum Crashes (HIGH severity):** Factor reverses violently after bear markets.
  Worst episodes: Mar–Apr 2009 (-42 %), Apr–May 2020 (-23 %).
- **Crowding Risk:** When a significant fraction of AUM chases momentum, the factor
  becomes self-defeating. Internal EdgeRunner crowding indicator currently at 72/100.
- **Transaction Costs:** High turnover makes net-of-cost implementation challenging
  for large AUM. Alpha degrades above ~$2 B.

### Code Template (SignalForge Reference Implementation)

```python
import pandas as pd
import numpy as np

def compute_momentum_signal(
    prices: pd.DataFrame,
    lookback: int = 252,
    skip: int = 21,
) -> pd.Series:
    """
    Compute cross-sectional momentum signal (12-1 month).
    
    Args:
        prices: Daily adjusted close prices (rows=dates, cols=tickers).
        lookback: Lookback window in trading days (default 252 = 12 months).
        skip: Skip most recent N days to avoid reversal bias.
    
    Returns:
        Series of z-scored momentum signals, indexed by ticker.
    """
    log_returns = np.log(prices / prices.shift(1))
    momentum = log_returns.rolling(lookback - skip).sum()
    # Cross-sectional z-score
    signal = (momentum.iloc[-1] - momentum.iloc[-1].mean()) / momentum.iloc[-1].std()
    return signal.dropna()
```

---

## Strategy Archetype 2: Statistical Arbitrage (Pairs Trading)

**Description:** Identify cointegrated pairs. Trade spread mean-reversion. Signal entry at ±2σ, exit at 0σ.

### Performance Metrics (US Equities, 2010–2025)
| Metric              | Value      |
|---------------------|------------|
| Annualised Return   | +8.4 %     |
| Sharpe Ratio        | 1.24       |
| Max Drawdown        | -18 %      |
| Calmar Ratio        | 0.47       |
| Annual Turnover     | ~400 %     |

### Known Failure Modes
- **Cointegration Breakdown:** Fundamental changes (mergers, regulatory shifts) permanently break pair relationships. No stop-loss can compensate.
- **Crowded Unwinds:** During COVID Crash, stat-arb pairs diverged by 8–15 σ as funds simultaneously deleveraged.
- **Capacity Constraint:** Strategy alpha is highly sensitive to ADV limits. Above 5 % ADV, slippage absorbs most returns.

---

## Strategy Archetype 3: Volatility Risk Premium (VRP) Harvesting

**Description:** Systematically sell short-dated options (delta-hedged) to capture the implied-realised vol spread.

### Performance Metrics (SPX, 2005–2025)
| Metric              | Value      |
|---------------------|------------|
| Annualised Return   | +14.7 %    |
| Sharpe Ratio        | 1.31       |
| Max Drawdown        | -54 %      |
| Calmar Ratio        | 0.27       |
| Annual Turnover     | ~1,200 %   |

### Known Failure Modes
- **Tail Events:** Short vol strategies are inherently short gamma. A VIX spike from 20 to 80 generates losses equivalent to 3–5 years of premium collected.
- **Gap Risk:** Weekend gaps (e.g., geopolitical events) cannot be hedged. 
- **VIX regime change:** The XIV collapse (Feb 5, 2018, -96 % in one day) is the canonical example.

---

## Strategy Archetype 4: Multi-Factor Long/Short Equity

**Description:** Combine value, quality, and momentum signals. Long high-scoring, short low-scoring stocks. Monthly rebalance.

### Factor Weights (Internal QuantPulse Configuration)
| Factor                  | Weight | Source           |
|-------------------------|--------|------------------|
| Price-to-Book (inverse) | 15 %   | DataVault pricing|
| Earnings Yield          | 20 %   | DataVault fundamentals|
| ROE (trailing 12M)      | 15 %   | DataVault financials|
| ROIC                    | 10 %   | DataVault financials|
| Price Momentum (12-1M)  | 20 %   | SignalForge price|
| Earnings Revision       | 20 %   | AlphaStream estimates|

### Performance Metrics (Global Equities, 2000–2025)
| Metric              | Value      |
|---------------------|------------|
| Annualised Return   | +12.8 %    |
| Sharpe Ratio        | 1.18       |
| Max Drawdown        | -31 %      |
| Calmar Ratio        | 0.41       |

---

## Strategy Archetype 5: Trend-Following (CTA-style)

**Description:** Time-series momentum across asset classes. Long/short based on 12-month trend direction. Monthly rebalance.

### Performance Metrics (Multi-Asset, 2000–2025)
| Metric              | Value      |
|---------------------|------------|
| Annualised Return   | +9.6 %     |
| Sharpe Ratio        | 0.87       |
| Max Drawdown        | -22 %      |
| Calmar Ratio        | 0.44       |

### Key Advantage
- Historically performs well during sustained trend regimes (2022 rate shock: +27 %).
- Crisis alpha: typically positive during prolonged drawdowns (2008: +22 %).

### Known Failure Modes
- **Whipsaw Markets:** Choppy, range-bound markets (2011, Q4 2018) generate consecutive stop-outs.
- **Trend Reversal Lag:** By construction, trend-following buys highs and sells lows; entry timing can be poor.

---

## Implementation Standards (All Strategies)

All implementations reviewed by SignalForge must:
1. Use pandas vectorised operations only (no row-by-row loops).
2. Implement point-in-time data alignment (no future data leakage).
3. Include explicit transaction cost model.
4. Provide sensitivity analysis for key parameters.
5. Pass RiskSentinel pre-deployment checklist (see `risk_frameworks.md`).

---

*Internal reference only. Do not share outside Millennium. Maintained by QuantPulse Team.*
