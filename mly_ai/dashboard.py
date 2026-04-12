"""
Dashboard — Rich-powered analytics display for mly-ai --dashboard.

Renders four sections:
  1. KPI banner (total calls, cost, masked count, success rate)
  2. Feature usage table with inline bar charts
  3. Security masking breakdown
  4. Recent activity log (last 5 interactions)
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict

from rich import box
from rich.columns import Columns
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

console = Console()


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def render_dashboard(analytics: Dict) -> None:
    """Render the complete analytics dashboard to the terminal."""
    console.print()
    console.rule("[bold cyan]  MLY-AI  |  ANALYTICS DASHBOARD  [/bold cyan]")
    console.print(
        f"[dim]  Report generated: "
        f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  |  "
        f"DB path: ~/.mly-ai/mly_ai.db[/dim]\n"
    )

    if analytics["total_calls"] == 0:
        console.print(
            Panel(
                "[yellow]No interactions have been recorded yet.\n"
                "Run [bold]mly-ai research[/bold], [bold]mly-ai code[/bold], "
                "or [bold]mly-ai test[/bold] to generate telemetry.[/yellow]",
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
    _render_recent_activity(analytics)
    console.print()
    console.rule("[dim]End of Report[/dim]")


# ---------------------------------------------------------------------------
# Section renderers
# ---------------------------------------------------------------------------


def _render_kpis(analytics: Dict) -> None:
    """Four KPI cards in a horizontal grid."""
    total_calls = analytics["total_calls"]
    total_cost = analytics["total_cost"]
    total_masked = analytics["total_masked"]
    success_rate = analytics["success_rate"]
    total_tokens = analytics["total_tokens"]

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
            _card(str(total_calls), "Total API Calls", "cyan"),
            _card(f"${total_cost:.4f}", "Est. Total Cost (USD)", "green"),
            _card(f"{total_tokens:,}", "Total Tokens", "blue"),
            _card(str(total_masked), "Sensitive Items Masked", "yellow"),
            _card(f"{success_rate:.1f}%", "Success Rate", "magenta"),
        ],
        equal=True,
        expand=False,
    )
    console.print(cards)


def _render_feature_usage(analytics: Dict) -> None:
    """Feature usage table with proportional bar chart column."""
    feature_counts: Dict[str, int] = analytics["feature_counts"]
    total: int = analytics["total_calls"]

    table = Table(
        title="[bold]Feature Usage[/bold]",
        box=box.ROUNDED,
        border_style="blue",
        header_style="bold blue",
        show_lines=False,
    )
    table.add_column("Feature", style="bold", width=14)
    table.add_column("Calls", justify="right", width=8)
    table.add_column("Usage", width=26)
    table.add_column("Share", justify="right", width=8)
    table.add_column("Avg Cost / Call", justify="right", width=16)

    _ICONS = {"research": "[blue]RESEARCH[/blue]", "code": "[green]CODE    [/green]", "test": "[red]TEST    [/red]"}
    _COLORS = {"research": "blue", "code": "green", "test": "red"}

    for feature in ["research", "code", "test"]:
        count = feature_counts.get(feature, 0)
        pct = (count / total * 100) if total else 0.0
        bar_fill = int(pct / 5)
        color = _COLORS[feature]
        bar = f"[{color}]{'█' * bar_fill}[/{color}][dim]{'░' * (20 - bar_fill)}[/dim]"
        # Rough per-feature cost would need per-feature DB query; use overall avg
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
    """Privacy masking breakdown table."""
    breakdown: Dict[str, int] = analytics["masked_breakdown"]
    total_masked: int = analytics["total_masked"]

    table = Table(
        title="[bold]Security Masking Report  —  Risk Mitigation[/bold]",
        box=box.ROUNDED,
        border_style="yellow",
        header_style="bold yellow",
        show_lines=True,
    )
    table.add_column("Entity Type", style="yellow", width=22)
    table.add_column("Count Redacted", justify="right", width=16)
    table.add_column("Description", width=44)

    rows = [
        ("Stock / Asset Tickers", breakdown.get("tickers", 0),
         "Equity, options & derivative symbols masked"),
        ("Internal Project Names", breakdown.get("projects", 0),
         "Proprietary system & codename references masked"),
        ("SQL Schema References", breakdown.get("schemas", 0),
         "Database schema.table identifiers masked"),
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


def _render_recent_activity(analytics: Dict) -> None:
    """Last five interactions log."""
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
    table.add_column("Feature", width=12)
    table.add_column("Masked", justify="right", width=9)
    table.add_column("Est. Cost", justify="right", width=12)
    table.add_column("Status", justify="center", width=10)

    _FC = {"research": "blue", "code": "green", "test": "red"}

    for item in recent:
        c = _FC.get(item["feature"], "white")
        status = "[green]  OK  [/green]" if item["success"] else "[red] FAIL [/red]"
        table.add_row(
            item["timestamp"],
            f"[{c}]{item['feature'].upper():<8}[/{c}]",
            str(item["masked"]),
            f"${item['cost']:.5f}",
            status,
        )

    console.print(table)
