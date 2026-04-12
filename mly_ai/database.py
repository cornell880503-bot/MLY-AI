"""
Database Layer — SQLite persistence for interaction logging and analytics.

Every CLI invocation is recorded with token counts, cost estimates, masking
metrics, user identity, response latency, and satisfaction ratings so the
--dashboard and report commands can surface ROI and adoption telemetry.
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Dict, List

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    create_engine,
    text,
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

    id               = Column(Integer, primary_key=True, autoincrement=True)
    timestamp        = Column(DateTime, default=datetime.utcnow, nullable=False)
    feature          = Column(String(50), nullable=False)   # research | code | test
    input_summary    = Column(Text, nullable=True)
    masked_tickers   = Column(Integer, default=0, nullable=False)
    masked_projects  = Column(Integer, default=0, nullable=False)
    masked_schemas   = Column(Integer, default=0, nullable=False)
    total_masked     = Column(Integer, default=0, nullable=False)
    input_tokens     = Column(Integer, default=0, nullable=False)
    output_tokens    = Column(Integer, default=0, nullable=False)
    estimated_cost_usd = Column(Float, default=0.0, nullable=False)
    success          = Column(Boolean, default=True, nullable=False)
    error_message    = Column(Text, nullable=True)
    session_id       = Column(String(36), nullable=True)
    # --- PM analytics additions ---
    user_name        = Column(String(100), nullable=True)   # MLY_USER env or system user
    user_rating      = Column(Integer, nullable=True)       # 1–5 satisfaction score
    user_comment     = Column(Text, nullable=True)          # optional free-text feedback
    response_time_ms = Column(Integer, nullable=True)       # end-to-end latency in ms


# ---------------------------------------------------------------------------
# Database facade
# ---------------------------------------------------------------------------

class Database:
    """
    Thin wrapper around SQLAlchemy providing log + analytics helpers.

    The DB file lives at ``~/.mly-ai/mly_ai.db`` by default so it persists
    across working directories.
    """

    # Gemini 3 Flash Preview — USD per million tokens
    _INPUT_COST_PER_MTOK: float = 0.075
    _OUTPUT_COST_PER_MTOK: float = 0.30

    def __init__(self, db_path: str | None = None) -> None:
        if db_path is None:
            store = os.path.join(os.path.expanduser("~"), ".mly-ai")
            os.makedirs(store, exist_ok=True)
            db_path = os.path.join(store, "mly_ai.db")

        self.db_path = db_path
        self._engine = create_engine(f"sqlite:///{db_path}", echo=False)
        Base.metadata.create_all(self._engine)
        self._migrate()
        self._Session = sessionmaker(bind=self._engine)

    def _migrate(self) -> None:
        """Add new columns to an existing DB without dropping data.

        SQLAlchemy's create_all() does not ALTER existing tables, so we
        inspect the live schema via PRAGMA and issue ALTER TABLE ADD COLUMN
        for any column that is missing. This is idempotent and safe.
        """
        new_columns = [
            ("user_name",        "VARCHAR(100)"),
            ("user_rating",      "INTEGER"),
            ("user_comment",     "TEXT"),
            ("response_time_ms", "INTEGER"),
        ]
        with self._engine.connect() as conn:
            existing = {
                row[1]
                for row in conn.execute(
                    text("PRAGMA table_info(interactions)")
                ).fetchall()
            }
            for col_name, col_type in new_columns:
                if col_name not in existing:
                    conn.execute(
                        text(
                            f"ALTER TABLE interactions "
                            f"ADD COLUMN {col_name} {col_type}"
                        )
                    )
            conn.commit()

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
        user_name: str | None = None,
        response_time_ms: int | None = None,
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
                user_name=user_name,
                response_time_ms=response_time_ms,
            )
            session.add(row)
            session.commit()
            return row.id

    def update_feedback(
        self,
        interaction_id: int,
        rating: int,
        comment: str | None = None,
    ) -> None:
        """Store a user satisfaction rating against an existing interaction."""
        with self._Session() as session:
            row = session.get(Interaction, interaction_id)
            if row:
                row.user_rating = rating
                row.user_comment = comment
                session.commit()

    # ------------------------------------------------------------------
    # ORM analytics (dashboard)
    # ------------------------------------------------------------------

    def get_analytics(self) -> Dict:
        """Aggregate all interactions for the --dashboard view."""
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
                "satisfaction": {},
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
                "user": r.user_name or "—",
                "rating": r.user_rating,
            }
            for r in recent
        ]

        # Per-feature satisfaction summary
        satisfaction: Dict[str, Dict] = {}
        for f in ["research", "code", "test"]:
            rated = [r for r in rows if r.feature == f and r.user_rating is not None]
            total_f = len([r for r in rows if r.feature == f])
            satisfaction[f] = {
                "avg_rating": round(sum(r.user_rating for r in rated) / len(rated), 1) if rated else None,
                "rated": len(rated),
                "total": total_f,
            }

        return {
            "total_calls": total_calls,
            "total_cost": total_cost,
            "total_tokens": total_tokens,
            "feature_counts": feature_counts,
            "total_masked": total_masked,
            "masked_breakdown": masked_breakdown,
            "success_rate": success_rate,
            "recent": recent_data,
            "satisfaction": satisfaction,
        }

    # ------------------------------------------------------------------
    # Raw SQL analytics (report command — demonstrates SQL proficiency)
    # ------------------------------------------------------------------

    def get_sql_analytics(self, days: int = 30) -> Dict[str, Any]:
        """
        Run raw SQL queries against the interactions table.
        Returns structured results for the `mly-ai report` command.

        Raw SQL is used intentionally here to demonstrate SQL proficiency
        and to enable queries that aggregate across multiple dimensions
        more naturally than the ORM allows.
        """
        _DAILY_SQL = f"""
            SELECT
                DATE(timestamp)                          AS day,
                COUNT(*)                                 AS calls,
                SUM(total_masked)                        AS items_protected,
                ROUND(SUM(estimated_cost_usd), 5)        AS cost_usd,
                ROUND(AVG(response_time_ms), 0)          AS avg_latency_ms
            FROM interactions
            WHERE timestamp >= DATE('now', '-{days} days')
            GROUP BY DATE(timestamp)
            ORDER BY day DESC
        """

        _USER_SQL = """
            SELECT
                COALESCE(user_name, 'anonymous')         AS user,
                COUNT(*)                                 AS calls,
                ROUND(AVG(user_rating), 2)               AS avg_rating,
                SUM(total_masked)                        AS items_masked,
                ROUND(SUM(estimated_cost_usd), 4)        AS total_cost_usd
            FROM interactions
            GROUP BY user_name
            ORDER BY calls DESC
        """

        _SATISFACTION_SQL = """
            SELECT
                feature,
                COUNT(*)                                 AS total_calls,
                COUNT(user_rating)                       AS rated_calls,
                ROUND(AVG(user_rating), 2)               AS avg_rating,
                ROUND(AVG(response_time_ms) / 1000.0, 1) AS avg_latency_sec
            FROM interactions
            GROUP BY feature
            ORDER BY total_calls DESC
        """

        _PEAK_SQL = """
            SELECT
                DATE(timestamp)  AS day,
                COUNT(*)         AS calls
            FROM interactions
            GROUP BY DATE(timestamp)
            ORDER BY calls DESC
            LIMIT 1
        """

        with self._engine.connect() as conn:
            daily = [dict(r._mapping) for r in conn.execute(text(_DAILY_SQL))]
            users = [dict(r._mapping) for r in conn.execute(text(_USER_SQL))]
            satisfaction = [dict(r._mapping) for r in conn.execute(text(_SATISFACTION_SQL))]
            peak = conn.execute(text(_PEAK_SQL)).fetchone()

        return {
            "daily": daily,
            "users": users,
            "satisfaction": satisfaction,
            "peak_day": dict(peak._mapping) if peak else None,
            "sql_queries": {
                "daily_trend": _DAILY_SQL.strip(),
                "user_breakdown": _USER_SQL.strip(),
                "feature_satisfaction": _SATISFACTION_SQL.strip(),
            },
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
