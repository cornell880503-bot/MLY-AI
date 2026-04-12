"""
MLY-AI CLI — Millennium AI Infrastructure Gateway

Entry points:
  mly-ai research --ticker <TICKER> --query <TEXT>
  mly-ai code     --logic <DESCRIPTION>
  mly-ai test     --strategy <FILE> --regime <CONDITION>
  mly-ai          --dashboard

All prompts are masked before LLM transmission.
All interactions are logged to ~/.mly-ai/mly_ai.db.
"""

from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path
from typing import Optional

from openai import OpenAI
import typer
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text

from mly_ai.agents import (
    ResearchAgent,
    RiskManagerAgent,
    SecurityValidatorAgent,
    WorkerCodeAgent,
)
from mly_ai.dashboard import render_dashboard
from mly_ai.database import Database
from mly_ai.masking import MaskingPipeline

# ---------------------------------------------------------------------------
# Globals
# ---------------------------------------------------------------------------

app = typer.Typer(
    name="mly-ai",
    help=(
        "[bold cyan]MLY-AI[/bold cyan]  —  Millennium AI Infrastructure Gateway\n\n"
        "Secure, audited LLM access for traders and quantitative researchers.\n"
        "Every prompt is masked before transmission. Every call is logged."
    ),
    add_completion=False,
    rich_markup_mode="rich",
    no_args_is_help=False,
)

console = Console()
db = Database()
masker = MaskingPipeline()
SESSION_ID = str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_GEMINI_BASE_URL = "https://generativeai.googleapis.com/v1beta/openai/"


def _get_client() -> OpenAI:
    """Initialise the Gemini client via OpenAI-compatible endpoint."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        console.print(
            Panel(
                "[red]Environment variable [bold]GEMINI_API_KEY[/bold] is not set.\n\n"
                "Export your key before running mly-ai:\n"
                "  [bold]export GEMINI_API_KEY='AIza...'[/bold]\n\n"
                "Get a free key at: https://aistudio.google.com/apikey[/red]",
                title="[bold red]Configuration Error[/bold red]",
                border_style="red",
                padding=(1, 2),
            )
        )
        raise typer.Exit(code=1)
    return OpenAI(api_key=api_key, base_url=_GEMINI_BASE_URL)


def _header(title: str, subtitle: str = "") -> None:
    text = Text()
    text.append("MLY-AI", style="bold cyan")
    text.append("  |  ", style="dim")
    text.append(title, style="bold white")
    if subtitle:
        text.append(f"\n{subtitle}", style="dim italic")
    console.print(Panel(text, border_style="cyan", box=box.DOUBLE_EDGE, padding=(0, 2)))


def _footer(in_tok: int, out_tok: int, masked_total: int) -> None:
    cost = db.estimate_cost(in_tok, out_tok)
    console.print(
        f"\n[dim]  Tokens: {in_tok:,} in / {out_tok:,} out  "
        f"|  Est. cost: ${cost:.5f}  "
        f"|  Items masked: {masked_total}  "
        f"|  Session: {SESSION_ID[:8]}...[/dim]"
    )


# ---------------------------------------------------------------------------
# App callback — handles --dashboard and bare invocation
# ---------------------------------------------------------------------------


@app.callback(invoke_without_command=True)
def _main(
    ctx: typer.Context,
    dashboard: bool = typer.Option(
        False,
        "--dashboard",
        "-d",
        help="Display the analytics & ROI dashboard.",
        is_eager=True,
    ),
) -> None:
    """
    [bold cyan]MLY-AI[/bold cyan]  —  Millennium AI Infrastructure Gateway

    Run a subcommand to get started:

      [blue]mly-ai research[/blue]  --ticker AAPL --query "earnings trend Q3"
      [green]mly-ai code[/green]     --logic  "rolling Sharpe with 60-day window"
      [red]mly-ai test[/red]     --strategy ./strat.py --regime "2020 Covid Crash"
      [cyan]mly-ai[/cyan]         --dashboard
    """
    if dashboard:
        _header("ANALYTICS DASHBOARD", "Usage telemetry and ROI metrics")
        analytics = db.get_analytics()
        render_dashboard(analytics)
        raise typer.Exit()

    if ctx.invoked_subcommand is None:
        console.print(ctx.get_help())


# ---------------------------------------------------------------------------
# Scene 1 — research
# ---------------------------------------------------------------------------


@app.command("research")
def research(
    ticker: str = typer.Option(..., "--ticker", "-t", help="Asset ticker (e.g. AAPL)"),
    query: str = typer.Option(..., "--query", "-q", help="Research question"),
) -> None:
    """
    [blue]Scene 1: Alpha Discovery[/blue]

    Simulates a RAG system over internal documents, masks sensitive identifiers,
    and produces a high-fidelity research brief with source citations.
    """
    _header(
        "RESEARCH  |  ALPHA DISCOVERY",
        f"Ticker: {ticker.upper()}  |  Query: {query[:60]}{'...' if len(query) > 60 else ''}",
    )

    client = _get_client()
    agent = ResearchAgent(client)

    # ── Masking ────────────────────────────────────────────────────────
    raw_input = f"Ticker: {ticker.upper()}. {query}"
    masked_text, mapping = masker.mask(raw_input, explicit_tickers=[ticker])
    counts = masker.count_masked(mapping)

    # Recover the masked ticker token to pass to the agent
    masked_ticker = ticker.upper()
    for token, original in mapping.items():
        if original == ticker.upper():
            masked_ticker = token
            break

    # Strip the "Ticker: <TOKEN>. " prefix to get the clean masked query
    prefix = f"Ticker: {masked_ticker}. "
    masked_query = masked_text[len(prefix):] if masked_text.startswith(prefix) else masked_text

    console.print(
        f"\n[dim]  Masking pipeline: {counts['tickers']} ticker(s), "
        f"{counts['projects']} project name(s), {counts['schemas']} schema(s) masked[/dim]"
    )

    # ── Research ───────────────────────────────────────────────────────
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as prog:
        prog.add_task("[cyan]Retrieving documents and synthesising brief...", total=None)
        try:
            response_masked, in_tok, out_tok = agent.run(masked_ticker, masked_query)
        except Exception as exc:
            console.print(f"\n[red]Research agent failed: {exc}[/red]")
            db.log_interaction(
                feature="research",
                input_summary=f"{ticker} | {query[:120]}",
                masked_counts=counts,
                success=False,
                error_message=str(exc),
                session_id=SESSION_ID,
            )
            raise typer.Exit(code=1)

    response = masker.unmask(response_masked, mapping)

    db.log_interaction(
        feature="research",
        input_summary=f"{ticker} | {query[:120]}",
        masked_counts=counts,
        input_tokens=in_tok,
        output_tokens=out_tok,
        success=True,
        session_id=SESSION_ID,
    )

    console.print()
    console.print(
        Panel(
            response,
            title=f"[bold blue]RESEARCH BRIEF  |  {ticker.upper()}[/bold blue]",
            border_style="blue",
            padding=(1, 2),
        )
    )
    _footer(in_tok, out_tok, sum(counts.values()))


# ---------------------------------------------------------------------------
# Scene 2 — code
# ---------------------------------------------------------------------------


@app.command("code")
def code(
    logic: str = typer.Option(
        ..., "--logic", "-l", help="Natural language description of the trading logic"
    ),
) -> None:
    """
    [green]Scene 2: Quant Coding[/green]

    Generates high-performance Python/Pandas trading code from a plain-English
    description. A Security Validator agent then audits the output for risks.
    """
    _header(
        "CODE  |  QUANT CODING",
        f"Logic: {logic[:70]}{'...' if len(logic) > 70 else ''}",
    )

    client = _get_client()
    worker = WorkerCodeAgent(client)
    validator = SecurityValidatorAgent(client)

    # ── Masking ────────────────────────────────────────────────────────
    masked_logic, mapping = masker.mask(logic)
    counts = masker.count_masked(mapping)
    console.print(
        f"\n[dim]  Masking pipeline: {sum(counts.values())} item(s) masked[/dim]"
    )

    # ── Phase 1: Code Generation ───────────────────────────────────────
    console.print("\n[bold green]Phase 1[/bold green]  Worker Agent — generating code...")
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as prog:
        prog.add_task("[green]Writing Python script...", total=None)
        try:
            raw_code, in1, out1 = worker.run(masked_logic)
        except Exception as exc:
            console.print(f"\n[red]Code generation failed: {exc}[/red]")
            db.log_interaction(
                feature="code",
                input_summary=logic[:120],
                masked_counts=counts,
                success=False,
                error_message=str(exc),
                session_id=SESSION_ID,
            )
            raise typer.Exit(code=1)

    console.print("[green]  Code generated.[/green]")
    final_code = masker.unmask(raw_code, mapping)

    # ── Phase 2: Security Validation ──────────────────────────────────
    console.print("\n[bold yellow]Phase 2[/bold yellow]  Security Validator — scanning for vulnerabilities...")
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as prog:
        prog.add_task("[yellow]Running security audit...", total=None)
        try:
            sec_report, in2, out2 = validator.run(final_code)
        except Exception as exc:
            console.print(f"\n[yellow]  Security audit warning: {exc}[/yellow]")
            sec_report = {
                "security_score": "N/A",
                "risk_level": "UNKNOWN",
                "approved": False,
                "static_findings": [],
                "full_report": str(exc),
            }
            in2, out2 = 0, 0

    in_tok = in1 + in2
    out_tok = out1 + out2

    db.log_interaction(
        feature="code",
        input_summary=logic[:120],
        masked_counts=counts,
        input_tokens=in_tok,
        output_tokens=out_tok,
        success=True,
        session_id=SESSION_ID,
    )

    # ── Security Summary ───────────────────────────────────────────────
    risk = sec_report.get("risk_level", "UNKNOWN")
    _RISK_COLOR = {
        "LOW": "green", "MEDIUM": "yellow",
        "HIGH": "red", "CRITICAL": "bold red",
    }
    rc = _RISK_COLOR.get(risk, "white")
    approved_txt = "[green]APPROVED[/green]" if sec_report.get("approved") else "[red]REVIEW REQUIRED[/red]"

    sec_table = Table(
        title="Security Validation Report",
        box=box.ROUNDED,
        border_style="yellow",
        header_style="bold yellow",
    )
    sec_table.add_column("Metric", style="yellow", width=20)
    sec_table.add_column("Result", width=30)
    sec_table.add_row("Security Score", f"{sec_report.get('security_score', 'N/A')} / 10")
    sec_table.add_row("Risk Level", f"[{rc}]{risk}[/{rc}]")
    sec_table.add_row(
        "Static Findings",
        str(len(sec_report.get("static_findings", [])))
        + (" — " + ", ".join(sec_report["static_findings"][:2])
           if sec_report.get("static_findings") else ""),
    )
    sec_table.add_row("Verdict", approved_txt)
    console.print()
    console.print(sec_table)

    # ── Generated Code ─────────────────────────────────────────────────
    console.print()
    console.print(
        Panel(
            Syntax(final_code, "python", theme="monokai", line_numbers=True, word_wrap=True),
            title="[bold green]GENERATED CODE[/bold green]",
            border_style="green",
        )
    )
    _footer(in_tok, out_tok, sum(counts.values()))


# ---------------------------------------------------------------------------
# Scene 3 — test
# ---------------------------------------------------------------------------


@app.command("test")
def test(
    strategy: str = typer.Option(..., "--strategy", "-s", help="Path to strategy .py file"),
    regime: str = typer.Option(
        ..., "--regime", "-r", help="Market condition (e.g. '2020 Covid Crash')"
    ),
) -> None:
    """
    [red]Scene 3: Strategy Red-Teaming[/red]

    Parses a strategy script and unleashes an adversarial Risk Manager agent
    that stress-tests it under the specified market regime.
    Outputs a Risk Score and a structured list of vulnerabilities.
    """
    _header(
        "TEST  |  STRATEGY RED-TEAMING",
        f"File: {Path(strategy).name}  |  Regime: {regime}",
    )

    # ── Load strategy file ─────────────────────────────────────────────
    strat_path = Path(strategy)
    if not strat_path.exists():
        console.print(f"[red]  Strategy file not found: {strategy}[/red]")
        raise typer.Exit(code=1)

    try:
        strategy_code = strat_path.read_text(encoding="utf-8")
    except OSError as exc:
        console.print(f"[red]  Cannot read strategy file: {exc}[/red]")
        raise typer.Exit(code=1)

    console.print(
        f"\n[dim]  Loaded: {strat_path.name}  ({len(strategy_code):,} chars, "
        f"{strategy_code.count(chr(10))} lines)[/dim]"
    )

    client = _get_client()
    risk_agent = RiskManagerAgent(client)

    # ── Masking ────────────────────────────────────────────────────────
    masked_code, mapping = masker.mask(strategy_code)
    counts = masker.count_masked(mapping)
    console.print(
        f"[dim]  Masking pipeline: {sum(counts.values())} item(s) masked[/dim]"
    )

    # ── Risk Assessment ───────────────────────────────────────────────
    console.print(f"\n[bold red]Risk Manager Agent[/bold red]  — stress-testing under [italic]{regime}[/italic]...")
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as prog:
        prog.add_task(f"[red]Simulating '{regime}' scenario...", total=None)
        try:
            risk_report, in_tok, out_tok = risk_agent.run(masked_code, regime)
        except Exception as exc:
            console.print(f"\n[red]  Risk assessment failed: {exc}[/red]")
            db.log_interaction(
                feature="test",
                input_summary=f"{strat_path.name} | {regime}",
                masked_counts=counts,
                success=False,
                error_message=str(exc),
                session_id=SESSION_ID,
            )
            raise typer.Exit(code=1)

    db.log_interaction(
        feature="test",
        input_summary=f"{strat_path.name} | {regime}",
        masked_counts=counts,
        input_tokens=in_tok,
        output_tokens=out_tok,
        success=True,
        session_id=SESSION_ID,
    )

    # ── Risk Score Panel ───────────────────────────────────────────────
    risk_score: int = risk_report.get("risk_score", 50)
    impact: str = risk_report.get("regime_impact", "UNKNOWN")
    verdict: str = risk_report.get("verdict", "")

    score_color = "green" if risk_score < 30 else "yellow" if risk_score < 60 else "red"
    _IC = {"LOW": "green", "MEDIUM": "yellow", "HIGH": "red", "CATASTROPHIC": "bold red"}
    ic = _IC.get(impact, "white")

    bar_fill = int(risk_score / 5)
    score_bar = (
        f"[{score_color}]{'█' * bar_fill}[/{score_color}]"
        f"[dim]{'░' * (20 - bar_fill)}[/dim]"
    )

    score_table = Table(
        title=f"Risk Assessment  |  {strat_path.name}",
        box=box.DOUBLE_EDGE,
        border_style=score_color,
        header_style="bold white",
    )
    score_table.add_column("Metric", style="bold", width=22)
    score_table.add_column("Value", width=46)
    score_table.add_row(
        "RISK SCORE",
        f"[{score_color}]{risk_score} / 100[/{score_color}]  {score_bar}",
    )
    score_table.add_row("Market Regime", regime)
    score_table.add_row("Regime Impact", f"[{ic}]{impact}[/{ic}]")
    score_table.add_row("Verdict", verdict[:80])
    console.print()
    console.print(score_table)

    # ── Full Report ────────────────────────────────────────────────────
    full = masker.unmask(risk_report.get("full_report", ""), mapping)
    console.print()
    console.print(
        Panel(
            full,
            title=f"[bold red]RISK REPORT  |  {regime}[/bold red]",
            border_style="red",
            padding=(1, 2),
        )
    )
    _footer(in_tok, out_tok, sum(counts.values()))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main_entry() -> None:
    app()


if __name__ == "__main__":
    main_entry()
