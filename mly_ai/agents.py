"""
Agent System — Multi-agent workflows for the P72 Alpha Gateway scenes.

Agents:
  ResearchAgent       — Alpha discovery via simulated RAG (Scene 1)
  WorkerCodeAgent     — High-performance quant code generation (Scene 2)
  SecurityValidator   — Code security audit, second-pass validator (Scene 2)
  RiskManagerAgent    — Adversarial strategy red-teaming (Scene 3)
  AlphaIntelAgent     — Cross-language intelligence synthesizer (Feature A)
  BullCaseAgent       — Bull thesis builder from RAG context (Feature B)
  BearCaseAgent       — Contrarian bear case generator (Feature B)
  SynthesizerAgent    — Risk-adjusted synthesis of bull/bear debate (Feature B)
  TextToSQLAgent      — Natural language to SQLite query translator (Feature C)

All agents talk to Gemini via Google's OpenAI-compatible endpoint using the
openai SDK. Set GEMINI_API_KEY to authenticate.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

MODEL = "models/gemini-3.1-flash-lite-preview"
PRIVATE_DATA_DIR = Path(__file__).parent.parent / "private_data"

# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------


class _BaseAgent:
    def __init__(self, client: Any) -> None:
        self.client = client
        self.last_input_tokens: int = 0
        self.last_output_tokens: int = 0

    def _chat(
        self,
        *,
        system: str,
        messages: List[Dict],
        max_tokens: int = 2048,
    ) -> str:
        # OpenAI-compatible format: system message prepended to messages list
        full_messages = [{"role": "system", "content": system}] + messages
        response = self.client.chat.completions.create(
            model=MODEL,
            max_tokens=max_tokens,
            messages=full_messages,
        )
        self.last_input_tokens = response.usage.prompt_tokens
        self.last_output_tokens = response.usage.completion_tokens
        return response.choices[0].message.content


# ---------------------------------------------------------------------------
# RAG Retriever — reads from ./private_data/
# ---------------------------------------------------------------------------


class _RAGRetriever:
    """Simulated retrieval-augmented generation over the local knowledge base."""

    def __init__(self, data_dir: Path = PRIVATE_DATA_DIR) -> None:
        self._dir = data_dir

    def retrieve(
        self,
        ticker: str | None = None,
        query: str | None = None,
        max_docs: int = 4,
    ) -> List[Dict]:
        """Return the most relevant documents from the private data store."""
        if not self._dir.exists():
            return []

        docs: List[Dict] = []
        for path in self._dir.glob("*.md"):
            try:
                content = path.read_text(encoding="utf-8")
            except OSError:
                continue
            score = self._score(content, path.name, ticker, query)
            if score > 0:
                docs.append({"source": path.name, "content": content, "score": score})

        docs.sort(key=lambda d: d["score"], reverse=True)
        return docs[:max_docs]

    @staticmethod
    def _score(
        content: str,
        filename: str,
        ticker: str | None,
        query: str | None,
    ) -> float:
        score = 0.0
        low_content = content.lower()
        low_file = filename.lower()

        if ticker:
            tl = ticker.lower()
            if tl in low_file:
                score += 4.0
            score += min(low_content.count(tl) * 1.5, 6.0)

        if query:
            words = [w.lower() for w in re.findall(r"\w+", query) if len(w) > 3]
            for w in words:
                if w in low_content:
                    score += 0.4

        return min(score, 10.0)


# ---------------------------------------------------------------------------
# Scene 1 — Research Agent
# ---------------------------------------------------------------------------


class ResearchAgent(_BaseAgent):
    """Synthesises internal RAG documents into an alpha-discovery brief."""

    def __init__(self, client: Any) -> None:
        super().__init__(client)
        self._retriever = _RAGRetriever()

    def run(
        self,
        masked_ticker: str,
        masked_query: str,
        original_ticker: str | None = None,
    ) -> Tuple[str, int, int]:
        """
        Args:
            masked_ticker:   Ticker token (already masked) — used in LLM prompt.
            masked_query:    Query string (already masked) — used in LLM prompt.
            original_ticker: Real ticker symbol — used for RAG retrieval only,
                             never sent to the LLM.

        Returns:
            (response_text, input_tokens, output_tokens)
        """
        # RAG uses the original ticker so documents are found correctly.
        # Only the LLM prompt receives the masked token.
        rag_ticker = original_ticker or masked_ticker
        docs = self._retriever.retrieve(ticker=rag_ticker, query=masked_query)

        # Mask the original ticker inside retrieved document content so the
        # LLM only ever sees the masked token — not the real symbol.
        if original_ticker and original_ticker != masked_ticker:
            docs = [
                {
                    **d,
                    "content": re.sub(
                        rf"\b{re.escape(original_ticker)}\b",
                        masked_ticker,
                        d["content"],
                    ),
                }
                for d in docs
            ]

        rag_block = self._build_rag_block(docs)

        system = (
            "You are a Senior Quantitative Research Analyst at a top-tier hedge fund.\n"
            "Your role is to synthesise internal research documents into high-fidelity "
            "investment briefs.\n"
            "RULES:\n"
            "• Cite every factual claim with [Source: <filename>].\n"
            "• Be precise and data-driven; no generic platitudes.\n"
            "• Structure the brief with clear sections.\n"
            "• Flag data gaps explicitly when documents are insufficient."
        )

        user_prompt = (
            f"{rag_block}\n\n"
            f"**RESEARCH REQUEST**\n"
            f"Asset: {masked_ticker}\n"
            f"Query: {masked_query}\n\n"
            "Produce a professional research brief with the following sections:\n"
            "1. Executive Summary\n"
            "2. Key Findings (cite sources)\n"
            "3. Alpha Signals Identified\n"
            "4. Risk Factors & Caveats\n"
            "5. Sources Cited"
        )

        text = self._chat(
            system=system,
            messages=[{"role": "user", "content": user_prompt}],
            max_tokens=2500,
        )
        return text, self.last_input_tokens, self.last_output_tokens

    @staticmethod
    def _build_rag_block(docs: List[Dict]) -> str:
        if not docs:
            return (
                "<research_context>\n"
                "No matching internal documents found. "
                "Rely on established financial knowledge and flag this clearly.\n"
                "</research_context>"
            )
        parts = []
        for d in docs:
            excerpt = d["content"][:2000]
            parts.append(f"### Source: {d['source']}\n{excerpt}")
        joined = "\n\n---\n\n".join(parts)
        return f"<research_context>\n{joined}\n</research_context>"


# ---------------------------------------------------------------------------
# Scene 2a — Worker Code Agent
# ---------------------------------------------------------------------------


class WorkerCodeAgent(_BaseAgent):
    """Generates high-performance, type-annotated Python trading code."""

    def run(self, masked_logic: str) -> Tuple[str, int, int]:
        """
        Args:
            masked_logic: Natural language description (already masked).

        Returns:
            (python_code, input_tokens, output_tokens)
        """
        system = (
            "You are a Senior Quantitative Developer specialising in high-performance "
            "Python trading systems at a top-tier hedge fund.\n"
            "RULES:\n"
            "• Output ONLY valid Python code — no markdown fences, no prose.\n"
            "• Use pandas and numpy for all numerical work.\n"
            "• Include full type hints on every function.\n"
            "• Add Google-style docstrings with Args/Returns/Raises sections.\n"
            "• Provide a realistic __main__ block with synthetic sample data.\n"
            "• NEVER include network calls, file writes outside /tmp, or subprocess usage."
        )

        user_prompt = (
            "Generate a complete, immediately executable Python script "
            "that implements the following trading logic:\n\n"
            f"{masked_logic}\n\n"
            "Requirements:\n"
            "- Modular functions with single responsibilities\n"
            "- Vectorised pandas/numpy operations (no Python loops over rows)\n"
            "- Sensible parameter defaults with type annotations\n"
            "- Working __main__ example using randomly generated OHLCV data\n"
            "- Comments only where logic is non-obvious"
        )

        code = self._chat(
            system=system,
            messages=[{"role": "user", "content": user_prompt}],
            max_tokens=3500,
        )
        return code, self.last_input_tokens, self.last_output_tokens


# ---------------------------------------------------------------------------
# Scene 2b — Security Validator Agent
# ---------------------------------------------------------------------------

_STATIC_RULES: List[Tuple[str, str]] = [
    (r"\bimport\s+subprocess\b",                    "Subprocess / shell execution"),
    (r"\bos\.system\s*\(",                          "os.system() shell call"),
    (r"\bsocket\.(?:connect|create_connection)\b",  "Raw socket network I/O"),
    (r"\brequests\.(get|post|put|delete|patch)\b",  "HTTP outbound request (requests)"),
    (r"\burllib\.request\b",                        "HTTP outbound request (urllib)"),
    (r"\bhttpx?\.\w+\s*\(",                         "HTTP outbound request (httpx)"),
    (r"\beval\s*\(",                                "Dangerous eval()"),
    (r"\bexec\s*\(",                                "Dangerous exec()"),
    (r"\b__import__\s*\(",                          "Dynamic __import__()"),
    (r"\bpickle\.loads?\b",                         "Unsafe pickle deserialisation"),
    (r"\bopen\s*\([^)]+['\"][wa]['\"]",             "File write/append operation"),
    (r"\bshutil\.(rmtree|move|copy)\b",             "Filesystem mutation (shutil)"),
    (r"\bparamiko\b",                               "SSH library (paramiko)"),
    (r"\bcryptography\b",                           "Cryptography library detected"),
]


class SecurityValidatorAgent(_BaseAgent):
    """
    Two-pass security auditor:
      Pass 1 — regex-based static analysis (fast, no LLM cost).
      Pass 2 — LLM semantic review for context-aware judgement.
    """

    def run(self, code: str) -> Tuple[Dict, int, int]:
        """
        Returns:
            (security_report_dict, input_tokens, output_tokens)
        """
        static_hits = [
            desc
            for pattern, desc in _STATIC_RULES
            if re.search(pattern, code, re.IGNORECASE | re.MULTILINE)
        ]

        system = (
            "You are a Security Engineer specialising in quantitative trading platforms.\n"
            "Review Python code strictly for security and compliance risks.\n"
            "Flag only genuine vulnerabilities, not style issues.\n"
            "Be concise and specific."
        )

        user_prompt = (
            "Conduct a security audit of the following Python trading code.\n\n"
            f"Static analysis already flagged: "
            f"{static_hits if static_hits else ['None']}\n\n"
            "Audit focus areas:\n"
            "1. Unauthorised network / data exfiltration\n"
            "2. Unsafe builtins (eval, exec, __import__, pickle)\n"
            "3. Filesystem risks (writes, deletes outside /tmp)\n"
            "4. Supply-chain / dependency risks\n"
            "5. Logic that could expose internal data\n\n"
            f"```python\n{code}\n```\n\n"
            "Reply in EXACTLY this format (no extra text):\n"
            "SECURITY_SCORE: <1-10 where 10 = perfectly safe>\n"
            "RISK_LEVEL: <LOW|MEDIUM|HIGH|CRITICAL>\n"
            "FINDINGS:\n"
            "- <finding or 'None identified'>\n"
            "RECOMMENDATIONS:\n"
            "- <recommendation or 'No action required'>\n"
            "APPROVED: <YES|NO>"
        )

        raw = self._chat(
            system=system,
            messages=[{"role": "user", "content": user_prompt}],
            max_tokens=900,
        )

        report = self._parse(raw, static_hits)
        return report, self.last_input_tokens, self.last_output_tokens

    @staticmethod
    def _parse(raw: str, static_hits: List[str]) -> Dict:
        def _extract(pattern: str, text: str, default: str = "") -> str:
            m = re.search(pattern, text, re.IGNORECASE)
            return m.group(1).strip() if m else default

        score_str = _extract(r"SECURITY_SCORE:\s*(\d+)", raw, "5")
        risk = _extract(r"RISK_LEVEL:\s*(\w+)", raw, "UNKNOWN")
        approved_str = _extract(r"APPROVED:\s*(\w+)", raw, "NO")

        return {
            "security_score": int(score_str) if score_str.isdigit() else 5,
            "risk_level": risk.upper(),
            "approved": approved_str.upper() == "YES",
            "static_findings": static_hits,
            "full_report": raw,
        }


# ---------------------------------------------------------------------------
# Scene 3 — Risk Manager Agent
# ---------------------------------------------------------------------------


class RiskManagerAgent(_BaseAgent):
    """
    Adversarial agent that red-teams a trading strategy under a given market
    regime, acting as a sceptical Chief Risk Officer.
    """

    def run(
        self,
        masked_strategy_code: str,
        regime: str,
    ) -> Tuple[Dict, int, int]:
        """
        Args:
            masked_strategy_code: Strategy source code (already masked).
            regime: Market condition label (e.g. '2020 Covid Crash').

        Returns:
            (risk_report_dict, input_tokens, output_tokens)
        """
        system = (
            "You are a Chief Risk Officer with 25 years of experience stress-testing "
            "quantitative strategies across every major market dislocation.\n"
            "Your mandate is adversarial: find every way this strategy can fail.\n"
            "Be specific, quantitative, and brutal. "
            "Do not soften findings or add encouraging language."
        )

        user_prompt = (
            f"Conduct a full adversarial risk assessment of the strategy below "
            f"under the market regime: **{regime}**\n\n"
            f"```python\n{masked_strategy_code}\n```\n\n"
            "Your assessment MUST cover:\n"
            "1. How '{regime}' specifically breaks this strategy's assumptions\n"
            "2. Coding or mathematical logic flaws\n"
            "3. Hidden assumptions baked into the algorithm\n"
            "4. Three concrete tail-risk scenarios with realistic loss magnitudes\n"
            "5. Missing risk controls (position limits, stop-losses, circuit breakers)\n\n"
            "Reply in EXACTLY this format:\n"
            "RISK_SCORE: <1-100 where 100 = certain blow-up>\n"
            "REGIME_IMPACT: <LOW|MEDIUM|HIGH|CATASTROPHIC>\n"
            "VULNERABILITIES:\n"
            "- <vulnerability>\n"
            "TAIL_RISK_SCENARIOS:\n"
            "1. <scenario with estimated loss magnitude>\n"
            "2. <scenario with estimated loss magnitude>\n"
            "3. <scenario with estimated loss magnitude>\n"
            "MISSING_CONTROLS:\n"
            "- <missing control>\n"
            "VERDICT: <one definitive sentence>"
        )

        raw = self._chat(
            system=system,
            messages=[{"role": "user", "content": user_prompt}],
            max_tokens=2000,
        )

        report = self._parse(raw, regime)
        return report, self.last_input_tokens, self.last_output_tokens

    @staticmethod
    def _parse(raw: str, regime: str) -> Dict:
        def _extract(pattern: str, default: str = "") -> str:
            m = re.search(pattern, raw, re.IGNORECASE)
            return m.group(1).strip() if m else default

        score_str = _extract(r"RISK_SCORE:\s*(\d+)", "50")
        impact = _extract(r"REGIME_IMPACT:\s*(\w+)", "UNKNOWN")
        verdict = _extract(r"VERDICT:\s*(.+?)(?:\n|$)", "Assessment incomplete.")

        return {
            "risk_score": int(score_str) if score_str.isdigit() else 50,
            "regime_impact": impact.upper(),
            "verdict": verdict,
            "regime": regime,
            "full_report": raw,
        }


# ---------------------------------------------------------------------------
# Feature A — Alpha Intelligence Agent
# ---------------------------------------------------------------------------


class AlphaIntelAgent(_BaseAgent):
    """Cross-language intelligence synthesizer for Chinese/English research documents."""

    def run(self, content: str, ticker: str | None = None) -> Tuple[str, int, int]:
        system = (
            "You are a senior cross-border research analyst fluent in both Chinese and English "
            "financial markets. You specialize in extracting actionable intelligence from "
            "Chinese-language research reports and translating insights for Western PMs.\n"
            "RULES:\n"
            "• If the input is in Chinese, translate key data points; do NOT translate the entire document.\n"
            "• Output ONLY the three sections below, no preamble.\n"
            "• Be specific and data-driven. Cite numbers where available.\n"
            "• The Differentiated Signal must explicitly state how it differs from market consensus."
        )
        ticker_clause = f" Focus your analysis on {ticker}." if ticker else ""
        user_prompt = (
            f"Analyze the following research document and produce a structured English investment brief.{ticker_clause}\n\n"
            f"DOCUMENT:\n{content[:6000]}\n\n"
            "Output EXACTLY in this format:\n"
            "## MACRO CONTEXT\n<2-3 sentences on the macroeconomic backdrop>\n\n"
            "## TICKER IMPACT\n<Specific impact on the target asset — price drivers, catalysts, risks>\n\n"
            "## DIFFERENTIATED SIGNAL\n<What does this source reveal that consensus is missing? Be explicit about the delta.>"
        )
        text = self._chat(system=system, messages=[{"role": "user", "content": user_prompt}], max_tokens=1800)
        return text, self.last_input_tokens, self.last_output_tokens


# ---------------------------------------------------------------------------
# Feature B — Verify Agents (Bull / Bear / Synthesizer)
# ---------------------------------------------------------------------------


class BullCaseAgent(_BaseAgent):
    """Generates a structured bull thesis from internal RAG context."""

    def __init__(self, client: Any) -> None:
        super().__init__(client)
        self._retriever = _RAGRetriever()

    def run(self, masked_ticker: str, masked_thesis: str, original_ticker: str | None = None) -> Tuple[str, int, int]:
        rag_ticker = original_ticker or masked_ticker
        docs = self._retriever.retrieve(ticker=rag_ticker, query=masked_thesis)
        if original_ticker and original_ticker != masked_ticker:
            docs = [
                {**d, "content": re.sub(rf"\b{re.escape(original_ticker)}\b", masked_ticker, d["content"])}
                for d in docs
            ]
        rag_block = ResearchAgent._build_rag_block(docs)  # reuse static method
        system = (
            "You are a bullish sell-side analyst. Your job is to construct the strongest possible "
            "bull case for the given investment thesis using the provided internal research.\n"
            "Be specific. Cite data points. Do not hedge or add caveats."
        )
        user_prompt = (
            f"{rag_block}\n\n"
            f"Asset: {masked_ticker}\n"
            f"Thesis to support: {masked_thesis}\n\n"
            "Build the bull case in EXACTLY this format:\n"
            "BULL_SCORE: <1-100 conviction>\n"
            "KEY_DRIVERS:\n- <driver>\nCATALYSTS:\n- <catalyst>\nSUPPORTING_DATA:\n- <data point>"
        )
        text = self._chat(system=system, messages=[{"role": "user", "content": user_prompt}], max_tokens=1200)
        return text, self.last_input_tokens, self.last_output_tokens


class BearCaseAgent(_BaseAgent):
    """Contrarian agent — finds friction and contradictions in the bull case."""

    def run(self, masked_ticker: str, bull_case: str, masked_thesis: str) -> Tuple[str, int, int]:
        system = (
            "You are a skeptical risk analyst and contrarian investor. "
            "Your job is to DESTROY the bull case presented to you.\n"
            "Simulate external market intelligence: macro headwinds, regulatory risks, "
            "competitive threats, positioning crowding, valuation traps.\n"
            "Be brutal. Every point must directly contradict a specific bull claim."
        )
        user_prompt = (
            f"Asset: {masked_ticker}\n"
            f"Original thesis: {masked_thesis}\n\n"
            f"BULL CASE TO CHALLENGE:\n{bull_case}\n\n"
            "Produce the bear case in EXACTLY this format:\n"
            "BEAR_SCORE: <1-100 risk level>\n"
            "CONTRADICTIONS:\n- <specific rebuttal to a bull point>\n"
            "EXTERNAL_FRICTION:\n- <macro/regulatory/competitive risk>\n"
            "MOST_DANGEROUS_ASSUMPTION:\n<single sentence identifying the bull case's fatal flaw>"
        )
        text = self._chat(system=system, messages=[{"role": "user", "content": user_prompt}], max_tokens=1200)
        return text, self.last_input_tokens, self.last_output_tokens


class SynthesizerAgent(_BaseAgent):
    """Synthesizes bull/bear debate into a risk-adjusted final view."""

    def run(self, masked_ticker: str, bull_case: str, bear_case: str) -> Tuple[Dict, int, int]:
        system = (
            "You are a Chief Investment Officer with 30 years of experience. "
            "You have heard the bull and bear cases. Now give the definitive risk-adjusted verdict.\n"
            "Your job is to identify the DELTA — what one side knows that the other is missing."
        )
        user_prompt = (
            f"Asset: {masked_ticker}\n\n"
            f"BULL CASE:\n{bull_case}\n\n"
            f"BEAR CASE:\n{bear_case}\n\n"
            "Produce the synthesis in EXACTLY this format:\n"
            "CONVICTION: <STRONG_BUY|BUY|HOLD|SELL|STRONG_SELL>\n"
            "CONVICTION_SCORE: <1-100>\n"
            "DELTA: <one paragraph — what the bull knows that bear misses, AND what bear knows that bull ignores>\n"
            "RECOMMENDED_ACTION: <specific, actionable — position size, entry condition, stop-loss>\n"
            "KEY_RISK: <single most important risk to monitor>"
        )
        raw = self._chat(system=system, messages=[{"role": "user", "content": user_prompt}], max_tokens=1000)
        report = self._parse_synthesis(raw)
        return report, self.last_input_tokens, self.last_output_tokens

    @staticmethod
    def _parse_synthesis(raw: str) -> Dict:
        def _extract(pattern: str, default: str = "") -> str:
            m = re.search(pattern, raw, re.IGNORECASE | re.DOTALL)
            return m.group(1).strip() if m else default

        score_str = _extract(r"CONVICTION_SCORE:\s*(\d+)", "50")
        return {
            "conviction": _extract(r"CONVICTION:\s*(\w+)", "HOLD"),
            "conviction_score": int(score_str) if score_str.isdigit() else 50,
            "delta": _extract(r"DELTA:\s*(.+?)(?=\nRECOMMENDED_ACTION:|\Z)", ""),
            "recommended_action": _extract(r"RECOMMENDED_ACTION:\s*(.+?)(?=\nKEY_RISK:|\Z)", ""),
            "key_risk": _extract(r"KEY_RISK:\s*(.+?)(?:\n|$)", ""),
            "full_report": raw,
        }


# ---------------------------------------------------------------------------
# Feature C — Text-to-SQL Agent
# ---------------------------------------------------------------------------

_INTERACTIONS_SCHEMA = """
Table: interactions
Columns:
  id INTEGER PRIMARY KEY
  timestamp DATETIME
  feature VARCHAR(50)         -- values: 'research','code','test','alpha','verify','query'
  input_summary TEXT
  masked_tickers INTEGER
  masked_projects INTEGER
  masked_schemas INTEGER
  total_masked INTEGER
  input_tokens INTEGER
  output_tokens INTEGER
  estimated_cost_usd REAL
  success BOOLEAN
  session_id VARCHAR(36)
  user_name VARCHAR(100)
  user_rating INTEGER          -- 1-5 satisfaction score
  user_comment TEXT
  response_time_ms INTEGER
"""


class TextToSQLAgent(_BaseAgent):
    """Translates natural language questions into SQLite queries over the interactions table."""

    def run(self, question: str) -> Tuple[str, int, int]:
        system = (
            "You are a SQLite expert. Translate natural language questions into valid SQLite SELECT queries.\n"
            "Output ONLY the SQL query — no markdown, no explanation, no semicolons at the end.\n"
            "Use only columns that exist in the schema. Always add LIMIT 100 unless the user specifies otherwise.\n"
            f"Schema:\n{_INTERACTIONS_SCHEMA}"
        )
        user_prompt = f"Question: {question}\n\nSQLite query:"
        sql = self._chat(system=system, messages=[{"role": "user", "content": user_prompt}], max_tokens=300)
        # Strip markdown fences if model adds them
        sql = re.sub(r"```(?:sql)?\s*", "", sql).strip().rstrip(";")
        return sql, self.last_input_tokens, self.last_output_tokens
