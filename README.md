# MLY-AI — Millennium AI Infrastructure Gateway

> Secure, audited LLM access for quantitative traders and researchers.  
> Built to demonstrate production-grade AI PM thinking: masking pipeline, multi-agent workflows, SQL analytics, feedback collection, and terminal-native visualization.

---

## What This Is

MLY-AI is a CLI tool that acts as a secure gateway between Millennium's analysts and external LLMs (Gemini). Every prompt is **masked before transmission** — tickers, internal project names, and SQL schema references are replaced with opaque tokens. Every interaction is **logged to SQLite** with token counts, cost estimates, response latency, user identity, and satisfaction ratings.

The demo covers three scenes from a typical quant workflow, each showcasing a distinct AI capability:

| Scene | Command | What It Does |
|-------|---------|-------------|
| 1 — Alpha Discovery | `mly-ai research` | RAG over internal docs → masked research brief |
| 2 — Quant Coding | `mly-ai code` | Code generation → Security validation (two agents) |
| 3 — Risk Red-Teaming | `mly-ai test` | Adversarial stress-test of a strategy under a market regime |
| Analytics Dashboard | `mly-ai --dashboard` | ORM-based usage telemetry + satisfaction ratings |
| PM Report | `mly-ai report` | Raw SQL analytics + ASCII bar chart + PM insights |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        mly-ai CLI                           │
│          (Typer + Rich — mly_ai/cli.py)                     │
└────────────┬──────────────────────────┬────────────────────┘
             │                          │
    ┌────────▼────────┐       ┌─────────▼──────────┐
    │ Masking Pipeline│       │  SQLite Database    │
    │ mly_ai/masking  │       │  mly_ai/database    │
    │                 │       │  ~/.mly-ai/mly_ai.db│
    │ • Tickers       │       │                     │
    │ • Project names │       │ • log_interaction() │
    │ • SQL schemas   │       │ • update_feedback() │
    └────────┬────────┘       │ • get_analytics()   │
             │                │ • get_sql_analytics()│
             │                └─────────────────────┘
    ┌────────▼──────────────────────────────────────┐
    │              Agent System (mly_ai/agents.py)  │
    │                                               │
    │  ResearchAgent      — RAG + brief synthesis   │
    │  WorkerCodeAgent    — Python code generation  │
    │  SecurityValidator  — Static + LLM audit      │
    │  RiskManagerAgent   — Adversarial red-teaming │
    └────────────────┬──────────────────────────────┘
                     │
    ┌────────────────▼──────────────────────────────┐
    │   Gemini (via OpenAI-compatible endpoint)     │
    │   model: models/gemini-3-flash-preview        │
    └───────────────────────────────────────────────┘
```

### Multi-Agent Pipeline (Scene 2)

```
User input
  → MaskingPipeline.mask()          # Tickers/projects/schemas → tokens
  → WorkerCodeAgent.run()           # Generate Python strategy code
  → SecurityValidatorAgent.run()    # Static regex + LLM security audit
  → MaskingPipeline.unmask()        # Restore original identifiers
  → Display + Feedback prompt
  → Database.log_interaction()      # Store tokens, cost, latency, user
```

---

## Setup

### Requirements

- Python 3.10+
- A [Google AI Studio](https://aistudio.google.com/) API key (free tier works)

### Install

```bash
git clone <repo-url>
cd mly-ai
pip install -e .
```

### Configure

```bash
# Required
export GEMINI_API_KEY="AIza..."

# Optional — sets your name in analytics
export MLY_USER="yourname"
```

---

## Usage

### Scene 1 — Alpha Discovery

```bash
mly-ai research --ticker AAPL --query "momentum alpha signals and earnings catalyst"
```

- Retrieves internal documents via simulated RAG
- Masks the ticker before sending to Gemini
- Returns a structured research brief with source citations
- Prompts for a 1–5 satisfaction rating

### Scene 2 — Quant Code Generation

```bash
mly-ai code --logic "60-day rolling Sharpe ratio with dynamic position sizing"
```

- **Phase 1:** WorkerCodeAgent generates type-annotated, vectorised Python
- **Phase 2:** SecurityValidatorAgent runs 14 static regex checks + LLM audit
- Displays Security Score, Risk Level, and APPROVED/REVIEW REQUIRED verdict
- Shows syntax-highlighted code with line numbers

### Scene 3 — Strategy Red-Teaming

```bash
# Save Scene 2 output or any strategy file
mly-ai test --strategy /tmp/strat.py --regime "2020 Covid Crash"

# Other regimes to try
mly-ai test --strategy /tmp/strat.py --regime "2019 Bull Market"
mly-ai test --strategy /tmp/strat.py --regime "2022 Rate Hike Cycle"
mly-ai test --strategy /tmp/strat.py --regime "2008 Financial Crisis"
```

- RiskManagerAgent acts as an adversarial Chief Risk Officer
- Outputs Risk Score (1–100), Regime Impact, Vulnerabilities, Tail-Risk Scenarios, Missing Controls
- Key insight: **a poorly designed strategy scores high-risk even in a bull market** — the agent audits strategy logic, not just market conditions

### Analytics Dashboard

```bash
mly-ai --dashboard
```

Shows: Total calls, cost, tokens, items masked, success rate, avg satisfaction, avg response time, feature usage bars, security masking breakdown, per-feature satisfaction ratings, recent activity table.

### PM Analytics Report

```bash
mly-ai report           # 30-day default
mly-ai report --days 7  # Custom window
```

Shows:
1. **SQL Queries panel** — prints the actual SQL being run (demonstrates SQL proficiency)
2. **Daily usage chart** — ASCII bar chart via `plotext`
3. **User adoption table** — per-user call counts and satisfaction scores
4. **Feature satisfaction table** — avg rating and latency per feature
5. **Cost projection** — 30-day and annual estimates
6. **PM Insights** — auto-generated bullets (most active user, peak day, items protected)

---

## Key Design Decisions

### Masking Pipeline

Four-layer masking runs before every LLM call:
1. **Explicit tickers** from CLI flags — always masked first
2. **Internal project names** — matched against a vocabulary of proprietary codenames
3. **SQL schema references** — `schema.table` notation
4. **Context-aware tickers** — `$AAPL` or `TSLA stock` patterns

Tokens use format `[[TICKER_A1B2C3D4]]`. A stop-word list prevents common English words (THE, API, SQL, etc.) from being masked.

For RAG (Scene 1): the **original ticker** is used for document retrieval locally; only the **masked token** is sent to the LLM. Retrieved document content is also masked before inclusion in the prompt.

### SQL Analytics

`get_sql_analytics()` uses raw SQL via `sqlalchemy.text()` — intentionally not using the ORM — to make SQL proficiency visible and enable multi-dimensional aggregations:

```sql
-- Daily usage trend
SELECT DATE(timestamp) AS day, COUNT(*) AS calls,
       SUM(total_masked) AS items_protected,
       ROUND(AVG(response_time_ms), 0) AS avg_latency_ms
FROM interactions
WHERE timestamp >= DATE('now', '-30 days')
GROUP BY DATE(timestamp)
ORDER BY day DESC
```

### Feedback Collection

After every command, users are prompted:
```
  Rate this response [1-5, Enter to skip]:
  Optional comment (Enter to skip):
```

Ratings are stored back to the interaction row via `update_feedback()`. Per-feature and per-user satisfaction aggregations appear in both `--dashboard` and `report`.

### Schema Migration

`Database._migrate()` uses `PRAGMA table_info` + `ALTER TABLE ADD COLUMN` to safely add new columns to existing databases without data loss. This is idempotent — safe to run on every startup.

---

## File Structure

```
mly-ai/
├── mly_ai/
│   ├── __init__.py
│   ├── cli.py          # Typer commands, user tracking, feedback loop
│   ├── agents.py       # ResearchAgent, WorkerCodeAgent, SecurityValidator, RiskManager
│   ├── masking.py      # 4-layer masking pipeline
│   ├── database.py     # SQLAlchemy ORM + raw SQL analytics
│   └── dashboard.py    # Rich terminal UI (dashboard + report)
├── private_data/       # Simulated internal research documents (RAG source)
│   ├── AAPL_analysis.md
│   ├── TSLA_analysis.md
│   ├── market_regimes.md
│   ├── risk_frameworks.md
│   └── quant_strategies.md
├── pyproject.toml
└── requirements.txt
```

---

## Dependencies

| Package | Purpose |
|---------|---------|
| `openai` | Gemini via OpenAI-compatible endpoint |
| `typer[all]` | CLI framework |
| `rich` | Terminal UI (tables, panels, syntax highlighting) |
| `sqlalchemy` | ORM + raw SQL execution |
| `pandas` / `numpy` | Used in generated strategy code |
| `plotext` | Terminal-native ASCII bar charts |

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GEMINI_API_KEY` | Yes | Google AI Studio API key |
| `MLY_USER` | No | Your name — appears in analytics. Falls back to system login. |
