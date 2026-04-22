"""
Dashboard — Rich-powered analytics displays for mly-ai.

Two entry points:
  render_dashboard(analytics)  — called by mly-ai --dashboard
  render_report(report_data)   — called by mly-ai report (SQL-driven PM analytics)
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List

from rich import box
from rich.columns import Columns
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

console = Console()


# ===========================================================================
# --dashboard  (existing dashboard, extended)
# ===========================================================================


def render_dashboard(analytics: Dict) -> None:
    """Render the analytics dashboard to the terminal."""
    console.print()
    console.rule("[bold cyan]  P72  |  ANALYTICS DASHBOARD  [/bold cyan]")
    console.print(
        f"[dim]  Report generated: "
        f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  |  "
        f"DB path: ~/.mly-ai/mly_ai.db[/dim]\n"
    )

    if analytics["total_calls"] == 0:
        console.print(
            Panel(
                "[yellow]No interactions have been recorded yet.\n"
                "Run [bold]p72-ai research[/bold], [bold]p72-ai code[/bold], "
                "or [bold]p72-ai test[/bold] to generate telemetry.[/yellow]",
                title="[bold yellow]Dashboard Empty[/bold yellow]",
                border_style="yellow",
                padding=(1, 4),
            )
        )
        return

    _render_kpis(analytics)
    console.print()
    _render_feature_usage(analytics)
    console.print()
    _render_security_metrics(analytics)
    console.print()
    _render_satisfaction(analytics)
    console.print()
    _render_recent_activity(analytics)
    console.print()
    console.rule("[dim]End of Report[/dim]")


def _render_kpis(analytics: Dict) -> None:
    def _card(value: str, title: str, style: str) -> Panel:
        return Panel(
            Text(value, style=f"bold {style}", justify="center"),
            title=f"[dim]{title}[/dim]",
            border_style=style,
            width=20,
            padding=(0, 1),
        )

    avg_r = analytics.get("avg_rating")
    avg_ms = analytics.get("avg_response_ms")

    cards = Columns(
        [
            _card(str(analytics["total_calls"]),         "Total API Calls",       "cyan"),
            _card(f"${analytics['total_cost']:.4f}",     "Est. Total Cost (USD)", "green"),
            _card(f"{analytics['total_tokens']:,}",      "Total Tokens",          "blue"),
            _card(str(analytics["total_masked"]),         "Items Masked",          "yellow"),
            _card(f"{analytics['success_rate']:.1f}%",  "Success Rate",          "magenta"),
            _card(
                f"{avg_r}★" if avg_r else "N/A",
                "Avg Satisfaction",
                "yellow",
            ),
            _card(
                f"{int(avg_ms):,}ms" if avg_ms else "N/A",
                "Avg Response Time",
                "cyan",
            ),
        ],
        equal=True,
        expand=False,
    )
    console.print(cards)


def _render_feature_usage(analytics: Dict) -> None:
    table = Table(
        title="[bold]Feature Usage[/bold]",
        box=box.ROUNDED,
        border_style="blue",
        header_style="bold blue",
        show_lines=False,
    )
    table.add_column("Feature",        style="bold",    width=14)
    table.add_column("Calls",          justify="right", width=8)
    table.add_column("Usage",          width=26)
    table.add_column("Share",          justify="right", width=8)
    table.add_column("Avg Cost/Call",  justify="right", width=16)

    total = analytics["total_calls"]
    _ICONS = {
        "research": "[blue]RESEARCH[/blue]",
        "code":     "[green]CODE    [/green]",
        "test":     "[red]TEST    [/red]",
    }
    _COLORS = {"research": "blue", "code": "green", "test": "red"}

    for feature in ["research", "code", "test"]:
        count = analytics["feature_counts"].get(feature, 0)
        pct = (count / total * 100) if total else 0.0
        bar_fill = int(pct / 5)
        color = _COLORS[feature]
        bar = f"[{color}]{'█' * bar_fill}[/{color}][dim]{'░' * (20 - bar_fill)}[/dim]"
        avg_cost = (analytics["total_cost"] / total) if total else 0.0
        table.add_row(
            _ICONS.get(feature, feature.upper()),
            str(count),
            bar,
            f"{pct:.1f}%",
            f"${avg_cost:.5f}",
        )
    console.print(table)


def _render_security_metrics(analytics: Dict) -> None:
    breakdown = analytics["masked_breakdown"]
    total_masked = analytics["total_masked"]

    table = Table(
        title="[bold]Security Masking Report  —  Risk Mitigation[/bold]",
        box=box.ROUNDED,
        border_style="yellow",
        header_style="bold yellow",
        show_lines=True,
    )
    table.add_column("Entity Type",    style="yellow", width=22)
    table.add_column("Count Redacted", justify="right", width=16)
    table.add_column("Description",    width=44)

    rows = [
        ("Stock / Asset Tickers",   breakdown.get("tickers", 0),  "Equity, options & derivative symbols masked"),
        ("Internal Project Names",  breakdown.get("projects", 0), "Proprietary system & codename references masked"),
        ("SQL Schema References",   breakdown.get("schemas", 0),  "Database schema.table identifiers masked"),
    ]
    for label, count, desc in rows:
        pct = (count / total_masked * 100) if total_masked else 0
        table.add_row(label, f"{count}  ({pct:.0f}%)", desc)

    table.add_section()
    table.add_row(
        "[bold white]TOTAL PROTECTED[/bold white]",
        f"[bold white]{total_masked}[/bold white]",
        "[bold white]Sensitive items kept off external LLMs[/bold white]",
    )
    console.print(table)


def _render_satisfaction(analytics: Dict) -> None:
    """User satisfaction ratings per feature."""
    satisfaction = analytics.get("satisfaction", {})
    if not any(v.get("rated") for v in satisfaction.values()):
        console.print(
            "[dim]  No satisfaction ratings yet — ratings are collected after each command.[/dim]"
        )
        return

    table = Table(
        title="[bold]User Satisfaction  —  Post-Response Ratings[/bold]",
        box=box.ROUNDED,
        border_style="yellow",
        header_style="bold yellow",
    )
    table.add_column("Feature",    style="bold",    width=14)
    table.add_column("Avg Rating", justify="center", width=14)
    table.add_column("Responses",  justify="center", width=14)
    table.add_column("Bar",        width=22)

    _FC = {"research": "blue", "code": "green", "test": "red"}

    for feature in ["research", "code", "test"]:
        data = satisfaction.get(feature, {})
        avg = data.get("avg_rating")
        rated = data.get("rated", 0)
        total = data.get("total", 0)
        color = _FC.get(feature, "white")

        if avg is not None:
            bar_fill = int(avg / 5 * 10)
            bar = f"[{color}]{'█' * bar_fill}[/{color}][dim]{'░' * (10 - bar_fill)}[/dim]"
            avg_str = f"{avg}★"
        else:
            bar = "[dim]──────────[/dim]"
            avg_str = "—"

        table.add_row(
            f"[{color}]{feature.upper()}[/{color}]",
            avg_str,
            f"{rated}/{total}",
            bar,
        )
    console.print(table)


def _render_recent_activity(analytics: Dict) -> None:
    recent = analytics["recent"]
    if not recent:
        return

    table = Table(
        title="[bold]Recent Activity  —  Last 5 Interactions[/bold]",
        box=box.SIMPLE_HEAD,
        border_style="dim",
        header_style="bold white",
        show_lines=False,
    )
    table.add_column("Timestamp (UTC)", style="dim", width=18)
    table.add_column("User",            width=14)
    table.add_column("Feature",         width=12)
    table.add_column("Masked",          justify="right", width=9)
    table.add_column("Est. Cost",       justify="right", width=12)
    table.add_column("Rating",          justify="center", width=8)
    table.add_column("Status",          justify="center", width=10)

    _FC = {"research": "blue", "code": "green", "test": "red"}

    for item in recent:
        c = _FC.get(item["feature"], "white")
        status = "[green]  OK  [/green]" if item["success"] else "[red] FAIL [/red]"
        rating = item.get("rating")
        rating_str = ("★" * rating + "☆" * (5 - rating)) if rating else "—"
        table.add_row(
            item["timestamp"],
            item.get("user", "—")[:12],
            f"[{c}]{item['feature'].upper():<8}[/{c}]",
            str(item["masked"]),
            f"${item['cost']:.5f}",
            rating_str,
            status,
        )
    console.print(table)


# ===========================================================================
# mly-ai report  (PM analytics with SQL + plotext chart)
# ===========================================================================


def render_report(report_data: Dict, days: int = 30) -> None:
    """Render the PM analytics report with SQL-driven metrics and ASCII chart."""
    console.print()
    console.rule("[bold cyan]  P72  |  PM ANALYTICS REPORT  [/bold cyan]")
    console.print(
        f"[dim]  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  "
        f"|  {days}-day window[/dim]\n"
    )

    if not report_data.get("daily"):
        console.print(
            Panel(
                "[yellow]No interaction data yet.\n"
                "Run mly-ai commands first, then rate the responses to populate this report.[/yellow]",
                title="[bold yellow]No Data[/bold yellow]",
                border_style="yellow",
            )
        )
        return

    _render_report_kpis(report_data)
    console.print()
    _render_sql_panel(report_data)
    console.print()
    _render_usage_chart(report_data, days)
    console.print()
    _render_user_breakdown(report_data)
    console.print()
    _render_feature_satisfaction_report(report_data)
    console.print()
    _render_cost_projection(report_data)
    console.print()
    _render_pm_insights(report_data)
    console.print()
    console.rule("[dim]End of PM Report[/dim]")


def _render_report_kpis(report_data: Dict) -> None:
    avg_r = report_data.get("avg_rating")
    rated = report_data.get("rated_count", 0)
    peak  = report_data.get("peak_dow", "N/A")
    proj  = report_data.get("projected_monthly_cost") or 0.0
    active = report_data.get("active_days", 0)

    def _card(value: str, title: str, style: str) -> Panel:
        return Panel(
            Text(value, style=f"bold {style}", justify="center"),
            title=f"[dim]{title}[/dim]",
            border_style=style,
            width=22,
            padding=(0, 1),
        )

    cards = Columns(
        [
            _card(f"{avg_r}★" if avg_r else "No ratings yet", "Avg Satisfaction (1-5)", "yellow"),
            _card(str(rated),                                  "Rated Interactions",     "green"),
            _card(peak,                                        "Peak Usage Day",         "blue"),
            _card(f"${proj:.4f}",                             "Proj. 30-day Cost",      "cyan"),
            _card(str(active),                                 "Active Days",            "magenta"),
        ],
        equal=True,
        expand=False,
    )
    console.print(cards)


def _render_sql_panel(report_data: Dict) -> None:
    """Show the raw SQL queries being executed — demonstrates SQL proficiency."""
    queries = report_data.get("sql_queries", {})
    if not queries:
        return

    sql_text = ""
    labels = {
        "daily_trend":           "-- Daily usage trend (last N days)",
        "user_breakdown":        "-- Per-user engagement breakdown",
        "feature_satisfaction":  "-- Feature-level satisfaction & latency",
    }
    for key, label in labels.items():
        if key in queries:
            sql_text += f"{label}\n{queries[key]}\n\n"

    from rich.syntax import Syntax
    console.print(
        Panel(
            Syntax(sql_text.strip(), "sql", theme="monokai", word_wrap=True),
            title="[bold yellow]SQL Queries — Analytics Engine[/bold yellow]",
            border_style="yellow",
            padding=(0, 1),
        )
    )


def _render_usage_chart(report_data: Dict, days: int = 30) -> None:
    """ASCII time-series bar chart via plotext."""
    daily = report_data.get("daily", [])
    if not daily:
        console.print("[dim]  No daily data for chart.[/dim]")
        return

    try:
        import plotext as plt

        dates  = [d["day"] for d in daily]
        counts = [d["calls"] for d in daily]

        plt.clf()
        plt.date_form("Y-m-d")
        plt.bar(dates, counts)
        plt.title(f"Daily API Call Volume — Last {days} Days")
        plt.xlabel("Date")
        plt.ylabel("Calls")
        plt.theme("dark")
        plt.plotsize(80, 18)
        chart_str = plt.build()

        console.print(
            Panel(
                chart_str,
                title="[bold cyan]Usage Trend[/bold cyan]",
                border_style="cyan",
                padding=(0, 1),
            )
        )
    except ImportError:
        # Graceful fallback: ASCII bars without plotext
        console.print("[dim]  (plotext not installed — showing text chart)[/dim]")
        max_calls = max(d["calls"] for d in daily) or 1
        for d in daily[-14:]:
            bar_len = int(d["calls"] / max_calls * 30)
            bar = "█" * bar_len
            console.print(f"  [dim]{d['day']}[/dim]  [cyan]{bar}[/cyan]  {d['calls']}")


def _render_user_breakdown(report_data: Dict) -> None:
    users = report_data.get("users", [])
    if not users:
        return

    table = Table(
        title="[bold]User Engagement  —  Adoption by Team Member[/bold]",
        box=box.ROUNDED,
        border_style="green",
        header_style="bold green",
    )
    table.add_column("User",         style="bold",    width=20)
    table.add_column("Calls",        justify="right", width=8)
    table.add_column("Avg Rating",   justify="center", width=13)
    table.add_column("Items Masked", justify="right", width=14)
    table.add_column("Total Cost",   justify="right", width=14)

    for u in users:
        rating_str = f"{u['avg_rating']}★" if u["avg_rating"] else "—"
        table.add_row(
            u["user"],
            str(u["calls"]),
            rating_str,
            str(u["items_masked"] or 0),
            f"${u['total_cost_usd']:.5f}" if u["total_cost_usd"] else "$0.00000",
        )
    console.print(table)


def _render_feature_satisfaction_report(report_data: Dict) -> None:
    sat = report_data.get("satisfaction", [])
    if not sat:
        return

    table = Table(
        title="[bold]Feature Satisfaction  &  Latency[/bold]",
        box=box.ROUNDED,
        border_style="yellow",
        header_style="bold yellow",
    )
    table.add_column("Feature",        style="bold",    width=14)
    table.add_column("Calls",          justify="right", width=8)
    table.add_column("Rated",          justify="right", width=8)
    table.add_column("Avg Rating",     justify="center", width=13)
    table.add_column("Avg Latency",    justify="right", width=14)

    _FC = {"research": "blue", "code": "green", "test": "red"}

    for row in sat:
        c = _FC.get(row["feature"], "white")
        rating_str = f"{row['avg_rating']}★" if row["avg_rating"] else "—"
        lat = row.get("avg_latency_sec")
        lat_str = f"{lat}s" if lat else "—"
        table.add_row(
            f"[{c}]{row['feature'].upper()}[/{c}]",
            str(row["total_calls"]),
            str(row["rated_calls"]),
            rating_str,
            lat_str,
        )
    console.print(table)


def _render_cost_projection(report_data: Dict) -> None:
    proj  = report_data.get("projected_monthly_cost") or 0.0
    active = report_data.get("active_days", 0)

    body = (
        f"Based on [bold]{active}[/bold] active day(s) in the current window:\n\n"
        f"  Projected 30-day cost:    [bold cyan]${proj:.4f}[/bold cyan]\n"
        f"  Projected annual cost:    [bold cyan]${proj * 12:.4f}[/bold cyan]\n\n"
        f"[dim]Formula: (total cost ÷ active days) × 30[/dim]"
    )
    console.print(
        Panel(
            body,
            title="[bold]Cost Projection[/bold]",
            border_style="cyan",
            padding=(1, 2),
        )
    )


def _render_pm_insights(report_data: Dict) -> None:
    """Auto-generated PM-language insight bullets from the SQL data."""
    insights: List[str] = []

    users = report_data.get("users", [])
    if users:
        top = users[0]
        insights.append(
            f"Most active user: [bold]{top['user']}[/bold] "
            f"with [bold]{top['calls']}[/bold] call(s)"
        )

    sat = report_data.get("satisfaction", [])
    if sat:
        rated = [s for s in sat if s.get("avg_rating")]
        if rated:
            best = max(rated, key=lambda s: s["avg_rating"])
            insights.append(
                f"Highest satisfaction: [bold]{best['feature']}[/bold] "
                f"({best['avg_rating']}★ avg)"
            )

    daily = report_data.get("daily", [])
    if daily:
        peak = max(daily, key=lambda d: d["calls"])
        insights.append(
            f"Peak usage day: [bold]{peak['day']}[/bold] "
            f"with [bold]{peak['calls']}[/bold] call(s)"
        )

    # Total items protected across all time (from all interactions)
    total_masked = sum(d.get("items_protected") or 0 for d in daily)
    if total_masked:
        insights.append(
            f"Sensitive items protected from external LLMs: [bold yellow]{total_masked}[/bold yellow]"
        )

    proj = report_data.get("projected_monthly_cost") or 0
    insights.append(
        f"Projected monthly LLM spend: [bold cyan]${proj:.4f}[/bold cyan]"
    )

    if not insights:
        return

    bullets = "\n".join(f"  • {i}" for i in insights)
    console.print(
        Panel(
            bullets,
            title="[bold white]PM Insights[/bold white]",
            border_style="white",
            padding=(1, 2),
        )
    )
