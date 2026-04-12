"""
Masking Pipeline — Pre/post-processing to protect Millennium's sensitive data.

Detects and masks three entity classes before any LLM transmission:
  1. Stock tickers / asset symbols (explicit + pattern-based)
  2. Internal project / system names
  3. SQL schema references (schema.table notation)

Post-processing (unmask) swaps tokens back so users see original names.
"""

from __future__ import annotations

import re
import uuid
from typing import Dict, List, Tuple

# ---------------------------------------------------------------------------
# Static vocabularies
# ---------------------------------------------------------------------------

# Common English words and known abbreviations that look like tickers — skip.
_TICKER_STOP_WORDS: frozenset[str] = frozenset({
    "A", "I", "AM", "AN", "AS", "AT", "BE", "BY", "DO", "GO", "IF", "IN",
    "IS", "IT", "NO", "OF", "OK", "ON", "OR", "PM", "SO", "TO", "UP", "US",
    "WE", "AND", "ARE", "BUT", "CAN", "FOR", "HAD", "HAS", "HER", "HIM",
    "HIS", "HOW", "ITS", "MAY", "NOT", "NOW", "OUR", "OUT", "OWN", "THE",
    "TOO", "WAS", "WHO", "WHY", "YES", "YET", "YOU", "ALSO", "BACK", "BEEN",
    "BEST", "BOTH", "CALL", "CAME", "COME", "DOES", "DONE", "DOWN", "EACH",
    "EVEN", "EVER", "FIND", "FIVE", "FROM", "GIVE", "GOOD", "HAVE", "HERE",
    "HIGH", "HOLD", "INTO", "JUST", "KEEP", "KNOW", "LAST", "LEFT", "LIKE",
    "LONG", "LOOK", "MADE", "MAKE", "MANY", "MORE", "MOST", "MUCH", "MUST",
    "NAME", "NEED", "NEXT", "NONE", "NOTE", "ONLY", "OPEN", "OVER", "PART",
    "PAST", "PUTS", "REAL", "REST", "RISK", "SAID", "SAME", "SEND", "SHOW",
    "SIDE", "SOME", "SUCH", "TAKE", "THAN", "THAT", "THEM", "THEN", "THEY",
    "THIS", "THUS", "TIME", "TURN", "TYPE", "USED", "VERY", "WANT", "WAYS",
    "WELL", "WERE", "WHAT", "WHEN", "WITH", "WORK", "YEAR", "YOUR",
    # Finance/tech acronyms that aren't tickers
    "AI", "API", "ATR", "BB", "CL", "CPI", "CSV", "DB", "DC", "EMM", "EMA",
    "ETF", "FED", "FX", "GDP", "HL", "HFT", "IPO", "IR", "MACD", "ML",
    "NAV", "NYSE", "OTC", "PNL", "ROI", "RSI", "SEC", "SMA", "SP", "SQL",
    "TR", "UI", "VIX", "VO", "CEO", "CFO", "COO", "CTO", "ESG", "YOY",
    "QOQ", "MOM", "EBIT", "EBITDA", "DCF", "IRR", "NPV", "CAGR",
})

# Millennium's internal project / system names (simulated)
_INTERNAL_PROJECTS: list[str] = [
    "AlphaStream", "QuantPulse", "RiskSentinel", "DataVault", "TradingEdge",
    "SignalForge", "OmegaBook", "DeltaEngine", "PrismAlpha", "NexusQuant",
    "VaultX", "EdgeRunner", "Midas", "PhoenixAlpha", "ThetaCore",
    "LiquidityMesh", "ArbitrageCore", "CrystalAlpha", "NovaSigma",
]

# SQL table names common in proprietary trading databases
_SQL_TABLES: list[str] = [
    "trades", "positions", "pnl", "portfolio", "orders", "executions",
    "accounts", "strategies", "signals", "risk_limits", "hedges",
    "settlements", "blotter", "allocations", "mandates", "fills",
    "instruments", "benchmarks", "drawdowns",
]


# ---------------------------------------------------------------------------
# MaskingPipeline
# ---------------------------------------------------------------------------

class MaskingPipeline:
    """
    Stateless masking pipeline.

    Usage::

        pipeline = MaskingPipeline()
        masked_text, mapping = pipeline.mask(raw_text, explicit_tickers=["AAPL"])
        # ... send masked_text to LLM ...
        final_text = pipeline.unmask(llm_response, mapping)
    """

    def __init__(self) -> None:
        self._sql_re = re.compile(
            r"\b(\w+)\.(" + "|".join(_SQL_TABLES) + r")\b",
            re.IGNORECASE,
        )
        # Dollar-sign prefix OR ticker followed by financial keywords
        self._ctx_ticker_re = re.compile(
            r"\$([A-Z]{1,5})\b"
            r"|"
            r"\b([A-Z]{1,5})\b(?=\s+(?:stock|equity|share|shares|position|"
            r"trade|call|put|option|options|future|futures|contract|etf|"
            r"warrant|bond|note|swap|spread|leg|ticker|symbol))",
            re.IGNORECASE,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def mask(
        self,
        text: str,
        explicit_tickers: List[str] | None = None,
    ) -> Tuple[str, Dict[str, str]]:
        """
        Mask sensitive entities in *text*.

        Args:
            text: Raw user input or prompt text.
            explicit_tickers: Tickers known from CLI flags (always masked).

        Returns:
            ``(masked_text, mapping)`` where *mapping* maps token → original.
        """
        mapping: Dict[str, str] = {}
        result = text

        # 1. Explicit tickers from CLI args — highest priority
        if explicit_tickers:
            for raw in explicit_tickers:
                ticker = raw.strip().upper()
                if not ticker:
                    continue
                # Deduplicate: same ticker gets one token
                existing_token = self._find_token_for_value(ticker, mapping)
                token = existing_token or self._token("TICKER")
                if not existing_token:
                    mapping[token] = ticker
                result = re.sub(rf"\b{re.escape(ticker)}\b", token, result)

        # 2. Internal project names (case-sensitive match)
        for project in _INTERNAL_PROJECTS:
            if project in result:
                existing_token = self._find_token_for_value(project, mapping)
                token = existing_token or self._token("PROJ")
                if not existing_token:
                    mapping[token] = project
                result = result.replace(project, token)

        # 3. SQL schema references (e.g. millennium_db.trades)
        for match in list(self._sql_re.finditer(result)):
            original = match.group()
            if "[[" in original:  # already tokenised
                continue
            existing_token = self._find_token_for_value(original, mapping)
            token = existing_token or self._token("SCHEMA")
            if not existing_token:
                mapping[token] = original
            result = result.replace(original, token, 1)

        # 4. Context-aware ticker detection in the remaining text
        for match in list(self._ctx_ticker_re.finditer(result)):
            raw_ticker = (match.group(1) or match.group(2)).upper()
            if raw_ticker in _TICKER_STOP_WORDS:
                continue
            if "[[" in match.group():
                continue
            existing_token = self._find_token_for_value(raw_ticker, mapping)
            token = existing_token or self._token("TICKER")
            if not existing_token:
                mapping[token] = raw_ticker
            result = re.sub(rf"\b{re.escape(raw_ticker)}\b", token, result)

        return result, mapping

    def unmask(self, text: str, mapping: Dict[str, str]) -> str:
        """Replace all tokens in *text* with their original values."""
        result = text
        for token, original in mapping.items():
            result = result.replace(token, original)
        return result

    def count_masked(self, mapping: Dict[str, str]) -> Dict[str, int]:
        """Return per-category masked item counts."""
        counts = {"tickers": 0, "projects": 0, "schemas": 0}
        for token in mapping:
            if "TICKER" in token:
                counts["tickers"] += 1
            elif "PROJ" in token:
                counts["projects"] += 1
            elif "SCHEMA" in token:
                counts["schemas"] += 1
        return counts

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _token(prefix: str) -> str:
        return f"[[{prefix}_{uuid.uuid4().hex[:8].upper()}]]"

    @staticmethod
    def _find_token_for_value(
        value: str, mapping: Dict[str, str]
    ) -> str | None:
        """Return the existing token for *value* if already in mapping."""
        for tok, orig in mapping.items():
            if orig == value:
                return tok
        return None
