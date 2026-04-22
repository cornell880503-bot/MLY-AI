# P72 Alpha Gateway

> **Actionable Intelligence from Unstructured Data.**  
> Secure, audited LLM access for quantitative traders and cross-border researchers.  
> Built to demonstrate production-grade AI PM thinking: masking pipeline, multi-agent workflows, SQL analytics, feedback collection, and terminal-native visualization.

---

## What This Is

P72 Alpha Gateway is a CLI tool that acts as a secure gateway between analysts and external LLMs (Gemini). Every prompt is **masked before transmission** — tickers, internal project names, and SQL schema references are replaced with opaque tokens. Every interaction is **logged to SQLite** with token counts, cost estimates, response latency, user identity, and satisfaction ratings.

The tool covers five capabilities spanning a typical cross-border quant workflow:

| Command | Feature | What It Does |
|---------|---------|-------------|
| `p72-ai research` | Alpha Discovery | RAG over internal docs → masked research brief |
| `p72-ai code` | Quant Coding | Code generation → Security validation (two agents) |
| `p72-ai test` | Risk Red-Teaming | Adversarial stress-test of a strategy under a market regime |
| `p72-ai alpha` | Alpha Intelligence | Cross-language (CN/EN) research doc → structured investment brief |
| `p72-ai verify` | Thesis Verification | Bull/Bear/Synthesizer debate → CIO risk-adjusted verdict |
| `p72-ai query` | NL Database Query | Natural language → SQLite → Rich table + optional chart |
| `p72-ai --dashboard` | Analytics Dashboard | ORM-based usage telemetry + satisfaction ratings |
| `p72-ai report` | PM Analytics Report | Raw SQL analytics + ASCII bar chart + PM insights |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     p72-ai CLI                              │
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
             │                │ • execute_query()   │
             │                └─────────────────────┘
    ┌────────▼──────────────────────────────────────┐
    │              Agent System (mly_ai/agents.py)  │
    │                                               │
    │  ResearchAgent      — RAG + brief synthesis   │
    │  WorkerCodeAgent    — Python code generation  │
    │  SecurityValidator  — Static + LLM audit      │
    │  RiskManagerAgent   — Adversarial red-teaming │
    │  AlphaIntelAgent    — CN/EN cross-lang intel  │
    │  BullCaseAgent      — Bull thesis from RAG    │
    │  BearCaseAgent      — Contrarian bear case    │
    │  SynthesizerAgent   — CIO risk-adj verdict    │
    │  TextToSQLAgent     — NL → SQLite query       │
    └────────────────┬──────────────────────────────┘
                     │
    ┌────────────────▼──────────────────────────────┐
    │   Gemini (via OpenAI-compatible endpoint)     │
    │   model: models/gemini-3-flash-preview        │
    └───────────────────────────────────────────────┘
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

### research — Alpha Discovery

```bash
p72-ai research --ticker AAPL --query "momentum alpha signals and earnings catalyst"
```

- Retrieves internal documents via simulated RAG
- Masks the ticker before sending to Gemini
- Returns a structured research brief with source citations
- Prompts for a 1–5 satisfaction rating

### code — Quant Code Generation

```bash
p72-ai code --logic "60-day rolling Sharpe ratio with dynamic position sizing"
```

- **Phase 1:** WorkerCodeAgent generates type-annotated, vectorised Python
- **Phase 2:** SecurityValidatorAgent runs 14 static regex checks + LLM audit
- Displays Security Score, Risk Level, and APPROVED/REVIEW REQUIRED verdict
- Shows syntax-highlighted code with line numbers

### test — Strategy Red-Teaming

```bash
p72-ai test --strategy /tmp/strat.py --regime "2020 Covid Crash"
```

- RiskManagerAgent acts as an adversarial Chief Risk Officer
- Outputs Risk Score (1–100), Regime Impact, Vulnerabilities, Tail-Risk Scenarios, Missing Controls

### alpha — Cross-Language Intelligence Brief

```bash
# Analyze a Chinese research PDF
p72-ai alpha --file private_data/BABA_cn_research.md --ticker BABA

# Analyze any research document (PDF or text)
p72-ai alpha --file /tmp/report.pdf --ticker BABA
```

- Reads PDF (via `pypdf`) or plain text research documents
- Handles Chinese-language input: extracts key data points without full translation
- Runs through the masking pipeline before LLM transmission
- Outputs three structured sections:
  - **MACRO CONTEXT** — macroeconomic backdrop
  - **TICKER IMPACT** — specific price drivers, catalysts, risks
  - **DIFFERENTIATED SIGNAL** — what this source reveals that consensus is missing

### verify — Thesis Verification (Bull/Bear/Synthesizer)

```bash
p72-ai verify --ticker BABA --thesis "Alibaba Cloud AI pivot creates structural re-rating opportunity"
```

Three-agent adversarial debate:

- **Phase 1 — BullCaseAgent:** Builds the strongest bull case from internal RAG documents
- **Phase 2 — BearCaseAgent:** Destroys the bull case with contradictions and external friction
- **Phase 3 — SynthesizerAgent:** CIO-level synthesis with conviction score, delta analysis, and recommended action

Output includes:
- Summary table: CONVICTION label, CONVICTION SCORE (1–100), KEY RISK, RECOMMENDED ACTION
- Full CIO synthesis panel
- Collapsible bull and bear case panels

### query — Natural Language Database Query

```bash
# Simple query
p72-ai query --q "how many calls were made per feature this week"

# With visualization
p72-ai query --q "total cost per feature" --viz

# Other examples
p72-ai query --q "average response time by feature"
p72-ai query --q "top 5 most expensive interactions"
p72-ai query --q "daily call volume last 7 days"
```

- TextToSQLAgent translates the question to a valid SQLite SELECT
- Shows the generated SQL in a syntax-highlighted panel
- Executes safely (only SELECT allowed) against the interactions database
- Renders results as a Rich table
- `--viz` adds a plotext bar chart when numeric data is present

### Analytics Dashboard

```bash
p72-ai --dashboard
```

Shows: Total calls, cost, tokens, items masked, success rate, avg satisfaction, avg response time, feature usage bars, security masking breakdown, per-feature satisfaction ratings, recent activity table.

### PM Analytics Report

```bash
p72-ai report           # 30-day default
p72-ai report --days 7  # Custom window
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

### Cross-Language Support (Feature A)

`AlphaIntelAgent` handles Chinese-language research documents without sending full translations to the LLM. The agent is instructed to extract key data points from Chinese text while producing English output — preserving fidelity while minimizing token usage.

### Multi-Agent Debate (Feature B)

The verify command implements a structured adversarial workflow:
```
BullCaseAgent (RAG-grounded) → BearCaseAgent (external friction) → SynthesizerAgent (CIO verdict)
```
Each agent receives the previous agent's output, creating a genuine debate rather than parallel independent analyses.

### SQL Analytics

`get_sql_analytics()` uses raw SQL via `sqlalchemy.text()` — intentionally not using the ORM — to make SQL proficiency visible and enable multi-dimensional aggregations. `execute_query()` accepts only SELECT statements for safe user-driven queries.

### Feedback Collection

After every command (except `query`), users are prompted:
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
p72-alpha-gateway/
├── mly_ai/
│   ├── __init__.py
│   ├── cli.py          # Typer commands: research, code, test, alpha, verify, query, report
│   ├── agents.py       # 9 agents across 5 features
│   ├── masking.py      # 4-layer masking pipeline
│   ├── database.py     # SQLAlchemy ORM + raw SQL analytics + execute_query
│   └── dashboard.py    # Rich terminal UI (dashboard + report)
├── private_data/       # Simulated internal research documents (RAG source)
│   ├── AAPL_analysis.md
│   ├── TSLA_analysis.md
│   ├── BABA_cn_research.md   # Chinese-language BABA research (Feature A)
│   ├── china_macro_cn.md     # Chinese macro strategy brief (Feature A)
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
| `pypdf` | PDF text extraction for `p72-ai alpha` |

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GEMINI_API_KEY` | Yes | Google AI Studio API key |
| `MLY_USER` | No | Your name — appears in analytics. Falls back to system login. |
