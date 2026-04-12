"""
Database Layer — SQLite persistence for interaction logging and analytics.

Every CLI invocation is recorded with token counts, cost estimates, and
masking metrics so the --dashboard command can surface ROI telemetry.
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Dict, List

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    create_engine,
    func,
)
from sqlalchemy.orm import DeclarativeBase, sessionmaker


# ---------------------------------------------------------------------------
# ORM model
# ---------------------------------------------------------------------------

class Base(DeclarativeBase):
    pass


class Interaction(Base):
    """One row per mly-ai command execution."""

    __tablename__ = "interactions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    feature = Column(String(50), nullable=False)   # research | code | test
    input_summary = Column(Text, nullable=True)
    masked_tickers = Column(Integer, default=0, nullable=False)
    masked_projects = Column(Integer, default=0, nullable=False)
    masked_schemas = Column(Integer, default=0, nullable=False)
    total_masked = Column(Integer, default=0, nullable=False)
    input_tokens = Column(Integer, default=0, nullable=False)
    output_tokens = Column(Integer, default=0, nullable=False)
    estimated_cost_usd = Column(Float, default=0.0, nullable=False)
    success = Column(Boolean, default=True, nullable=False)
    error_message = Column(Text, nullable=True)
    session_id = Column(String(36), nullable=True)


# ---------------------------------------------------------------------------
# Database facade
# ---------------------------------------------------------------------------

class Database:
    """
    Thin wrapper around SQLAlchemy providing log + analytics helpers.

    The DB file lives at ``~/.mly-ai/mly_ai.db`` by default so it persists
    across working directories.
    """

    # Claude Sonnet 4.6 — USD per million tokens (as of 2025)
    _INPUT_COST_PER_MTOK: float = 3.00
    _OUTPUT_COST_PER_MTOK: float = 15.00

    def __init__(self, db_path: str | None = None) -> None:
        if db_path is None:
            store = os.path.join(os.path.expanduser("~"), ".mly-ai")
            os.makedirs(store, exist_ok=True)
            db_path = os.path.join(store, "mly_ai.db")

        self.db_path = db_path
        self._engine = create_engine(f"sqlite:///{db_path}", echo=False)
        Base.metadata.create_all(self._engine)
        self._Session = sessionmaker(bind=self._engine)

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def log_interaction(
        self,
        *,
        feature: str,
        input_summary: str,
        masked_counts: Dict[str, int],
        input_tokens: int = 0,
        output_tokens: int = 0,
        success: bool = True,
        error_message: str | None = None,
        session_id: str | None = None,
    ) -> int:
        """Persist one interaction. Returns the new row ID."""
        cost = self.estimate_cost(input_tokens, output_tokens)
        total = sum(masked_counts.values())

        with self._Session() as session:
            row = Interaction(
                timestamp=datetime.utcnow(),
                feature=feature,
                input_summary=(input_summary or "")[:500],
                masked_tickers=masked_counts.get("tickers", 0),
                masked_projects=masked_counts.get("projects", 0),
                masked_schemas=masked_counts.get("schemas", 0),
                total_masked=total,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                estimated_cost_usd=cost,
                success=success,
                error_message=error_message,
                session_id=session_id,
            )
            session.add(row)
            session.commit()
            return row.id

    # ------------------------------------------------------------------
    # Read / analytics
    # ------------------------------------------------------------------

    def get_analytics(self) -> Dict:
        """Aggregate all interactions for the dashboard."""
        with self._Session() as session:
            rows: List[Interaction] = session.query(Interaction).all()

        if not rows:
            return {
                "total_calls": 0,
                "total_cost": 0.0,
                "total_tokens": 0,
                "feature_counts": {},
                "total_masked": 0,
                "masked_breakdown": {"tickers": 0, "projects": 0, "schemas": 0},
                "success_rate": 0.0,
                "recent": [],
            }

        total_calls = len(rows)
        total_cost = sum(r.estimated_cost_usd for r in rows)
        total_tokens = sum(r.input_tokens + r.output_tokens for r in rows)
        total_masked = sum(r.total_masked for r in rows)

        feature_counts: Dict[str, int] = {}
        for r in rows:
            feature_counts[r.feature] = feature_counts.get(r.feature, 0) + 1

        masked_breakdown = {
            "tickers": sum(r.masked_tickers for r in rows),
            "projects": sum(r.masked_projects for r in rows),
            "schemas": sum(r.masked_schemas for r in rows),
        }

        success_rate = (sum(1 for r in rows if r.success) / total_calls) * 100

        recent = sorted(rows, key=lambda r: r.timestamp, reverse=True)[:5]
        recent_data = [
            {
                "timestamp": r.timestamp.strftime("%Y-%m-%d %H:%M"),
                "feature": r.feature,
                "masked": r.total_masked,
                "cost": r.estimated_cost_usd,
                "success": r.success,
            }
            for r in recent
        ]

        return {
            "total_calls": total_calls,
            "total_cost": total_cost,
            "total_tokens": total_tokens,
            "feature_counts": feature_counts,
            "total_masked": total_masked,
            "masked_breakdown": masked_breakdown,
            "success_rate": success_rate,
            "recent": recent_data,
        }

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Return estimated USD cost for a token pair."""
        return (
            (input_tokens / 1_000_000) * self._INPUT_COST_PER_MTOK
            + (output_tokens / 1_000_000) * self._OUTPUT_COST_PER_MTOK
        )
