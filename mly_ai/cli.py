"""
P72 Alpha Gateway CLI

Tagline: Actionable Intelligence from Unstructured Data.

Entry points:
  p72-ai research --ticker <TICKER> --query <TEXT>
  p72-ai code     --logic <DESCRIPTION>
  p72-ai test     --strategy <FILE> --regime <CONDITION>
  p72-ai alpha    --file <PATH> [--ticker <TICKER>]
  p72-ai verify   --ticker <TICKER> --thesis <TEXT>
  p72-ai query    --q <QUESTION> [--viz]
  p72-ai report   [--days N]
  p72-ai          --dashboard

All prompts are masked before LLM transmission.
All interactions are logged to ~/.mly-ai/mly_ai.db.
"""

from __future__ import annotations

import os
import sys
import time
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
    AlphaIntelAgent,
    BearCaseAgent,
    BullCaseAgent,
    ResearchAgent,
    RiskManagerAgent,
    SecurityValidatorAgent,
    SynthesizerAgent,
    TextToSQLAgent,
    WorkerCodeAgent,
)
from mly_ai.dashboard import render_dashboard, render_report
from mly_ai.database import Database
from mly_ai.masking import MaskingPipeline

# ---------------------------------------------------------------------------
# Globals
# ---------------------------------------------------------------------------

app = typer.Typer(
    name="p72-ai",
    help=(
        "[bold cyan]P72[/bold cyan]  —  P72 Alpha Gateway\n\n"
        "Actionable Intelligence from Unstructured Data.\n"
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

_GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"


def _get_user() -> str:
    """Resolve the current user from MLY_USER env var or system login."""
    env_user = os.environ.get("MLY_USER", "").strip()
    if env_user:
        return env_user
    try:
        return os.getlogin()
    except OSError:
        return os.environ.get("USER", os.environ.get("USERNAME", "anonymous"))


CURRENT_USER = _get_user()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_client() -> OpenAI:
    """Initialise the Gemini client via OpenAI-compatible endpoint."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        console.print(
            Panel(
                "[red]Environment variable [bold]GEMINI_API_KEY[/bold] is not set.\n\n"
                "Export your key before running mly-ai:\n"
                "  [bold]export GEMINI_API_KEY='AIza...'[/bold][/red]",
                title="[bold red]Configuration Error[/bold red]",
                border_style="red",
                padding=(1, 2),
            )
        )
        raise typer.Exit(code=1)
    return OpenAI(api_key=api_key, base_url=_GEMINI_BASE_URL)


def _header(title: str, subtitle: str = "") -> None:
    text = Text()
    text.append("P72", style="bold cyan")
    text.append("  |  ", style="dim")
    text.append(title, style="bold white")
    if subtitle:
        text.append(f"\n{subtitle}", style="dim italic")
    console.print(Panel(text, border_style="cyan", box=box.DOUBLE_EDGE, padding=(0, 2)))


def _footer(in_tok: int, out_tok: int, masked_total: int, response_ms: int = 0) -> None:
    cost = db.estimate_cost(in_tok, out_tok)
    rt_str = f"  |  Response time: {response_ms:,}ms" if response_ms else ""
    console.print(
        f"\n[dim]  Tokens: {in_tok:,} in / {out_tok:,} out  "
        f"|  Est. cost: ${cost:.5f}  "
        f"|  Items masked: {masked_total}"
        f"{rt_str}"
        f"  |  User: {CURRENT_USER}  "
        f"|  Session: {SESSION_ID[:8]}...[/dim]"
    )


def _collect_feedback() -> tuple[int | None, str | None]:
    """Prompt for a 1–5 star rating. Non-blocking — Enter skips."""
    console.print()
    try:
        raw = console.input(
            "[dim]  Rate this response [1-5, Enter to skip]: [/dim]"
        ).strip()
    except (EOFError, KeyboardInterrupt):
        return None, None

    if not raw:
        return None, None

    if raw.isdigit() and 1 <= int(raw) <= 5:
        rating = int(raw)
        stars = "★" * rating + "☆" * (5 - rating)
        try:
            comment = console.input(
                "[dim]  Optional comment (Enter to skip): [/dim]"
            ).strip() or None
        except (EOFError, KeyboardInterrupt):
            comment = None
        console.print(f"[green]  Saved: {stars}  Thanks![/green]")
        return rating, comment

    console.print("[dim]  Skipped.[/dim]")
    return None, None


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
    [bold cyan]P72[/bold cyan]  —  P72 Alpha Gateway

    Actionable Intelligence from Unstructured Data.

    Run a subcommand to get started:

      [blue]p72-ai research[/blue]  --ticker AAPL --query "earnings trend Q3"
      [green]p72-ai code[/green]     --logic  "rolling Sharpe with 60-day window"
      [red]p72-ai test[/red]     --strategy ./strat.py --regime "2020 Covid Crash"
      [magenta]p72-ai alpha[/magenta]    --file report.pdf --ticker BABA
      [yellow]p72-ai verify[/yellow]   --ticker TSLA --thesis "EV market leader"
      [cyan]p72-ai query[/cyan]    --q "top 5 features by cost" --viz
      [cyan]p72-ai report[/cyan]   --days 30
      [cyan]p72-ai[/cyan]          --dashboard
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

    masked_ticker = ticker.upper()
    for token, original in mapping.items():
        if original == ticker.upper():
            masked_ticker = token
            break

    prefix = f"Ticker: {masked_ticker}. "
    masked_query = masked_text[len(prefix):] if masked_text.startswith(prefix) else masked_text

    console.print(
        f"\n[dim]  Masking pipeline: {counts['tickers']} ticker(s), "
        f"{counts['projects']} project name(s), {counts['schemas']} schema(s) masked"
        f"  |  User: {CURRENT_USER}[/dim]"
    )

    # ── Research ───────────────────────────────────────────────────────
    t_start = time.time()
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as prog:
        prog.add_task("[cyan]Retrieving documents and synthesising brief...", total=None)
        try:
            response_masked, in_tok, out_tok = agent.run(
                masked_ticker, masked_query, original_ticker=ticker.upper()
            )
        except Exception as exc:
            console.print(f"\n[red]Research agent failed: {exc}[/red]")
            db.log_interaction(
                feature="research",
                input_summary=f"{ticker} | {query[:120]}",
                masked_counts=counts,
                success=False,
                error_message=str(exc),
                session_id=SESSION_ID,
                user_name=CURRENT_USER,
                response_time_ms=int((time.time() - t_start) * 1000),
            )
            raise typer.Exit(code=1)

    response_ms = int((time.time() - t_start) * 1000)
    response = masker.unmask(response_masked, mapping)

    row_id = db.log_interaction(
        feature="research",
        input_summary=f"{ticker} | {query[:120]}",
        masked_counts=counts,
        input_tokens=in_tok,
        output_tokens=out_tok,
        success=True,
        session_id=SESSION_ID,
        user_name=CURRENT_USER,
        response_time_ms=response_ms,
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
    _footer(in_tok, out_tok, sum(counts.values()), response_ms)

    rating, comment = _collect_feedback()
    if rating is not None:
        db.update_feedback(row_id, rating, comment)


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
        f"\n[dim]  Masking pipeline: {sum(counts.values())} item(s) masked"
        f"  |  User: {CURRENT_USER}[/dim]"
    )

    t_start = time.time()

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
                user_name=CURRENT_USER,
                response_time_ms=int((time.time() - t_start) * 1000),
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

    response_ms = int((time.time() - t_start) * 1000)
    in_tok = in1 + in2
    out_tok = out1 + out2

    row_id = db.log_interaction(
        feature="code",
        input_summary=logic[:120],
        masked_counts=counts,
        input_tokens=in_tok,
        output_tokens=out_tok,
        success=True,
        session_id=SESSION_ID,
        user_name=CURRENT_USER,
        response_time_ms=response_ms,
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

    console.print()
    console.print(
        Panel(
            Syntax(final_code, "python", theme="monokai", line_numbers=True, word_wrap=True),
            title="[bold green]GENERATED CODE[/bold green]",
            border_style="green",
        )
    )
    _footer(in_tok, out_tok, sum(counts.values()), response_ms)

    rating, comment = _collect_feedback()
    if rating is not None:
        db.update_feedback(row_id, rating, comment)


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
        f"{strategy_code.count(chr(10))} lines)  |  User: {CURRENT_USER}[/dim]"
    )

    client = _get_client()
    risk_agent = RiskManagerAgent(client)

    masked_code, mapping = masker.mask(strategy_code)
    counts = masker.count_masked(mapping)
    console.print(
        f"[dim]  Masking pipeline: {sum(counts.values())} item(s) masked[/dim]"
    )

    console.print(f"\n[bold red]Risk Manager Agent[/bold red]  — stress-testing under [italic]{regime}[/italic]...")
    t_start = time.time()
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
                user_name=CURRENT_USER,
                response_time_ms=int((time.time() - t_start) * 1000),
            )
            raise typer.Exit(code=1)

    response_ms = int((time.time() - t_start) * 1000)

    row_id = db.log_interaction(
        feature="test",
        input_summary=f"{strat_path.name} | {regime}",
        masked_counts=counts,
        input_tokens=in_tok,
        output_tokens=out_tok,
        success=True,
        session_id=SESSION_ID,
        user_name=CURRENT_USER,
        response_time_ms=response_ms,
    )

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
    _footer(in_tok, out_tok, sum(counts.values()), response_ms)

    rating, comment = _collect_feedback()
    if rating is not None:
        db.update_feedback(row_id, rating, comment)


# ---------------------------------------------------------------------------
# PM Analytics Report
# ---------------------------------------------------------------------------


@app.command("report")
def report(
    days: int = typer.Option(30, "--days", "-n", help="Lookback window in days."),
) -> None:
    """
    [cyan]PM Analytics Report[/cyan]

    SQL-driven product metrics: satisfaction scores, user engagement,
    cost projections, and a time-series usage chart.

    Demonstrates data analysis and visualization proficiency.
    """
    _header(
        "PM ANALYTICS REPORT",
        f"SQL-driven insights  |  {days}-day trend window  |  User: {CURRENT_USER}",
    )
    report_data = db.get_sql_analytics(days=days)
    render_report(report_data, days=days)


# ---------------------------------------------------------------------------
# Feature A — alpha
# ---------------------------------------------------------------------------


@app.command("alpha")
def alpha(
    file: str = typer.Option(..., "--file", "-f", help="Path to research document (.pdf or text)"),
    ticker: Optional[str] = typer.Option(None, "--ticker", "-t", help="Optional ticker focus"),
) -> None:
    """
    [magenta]Feature A: Alpha Intelligence[/magenta]

    Reads a research document (PDF or text), extracts cross-language insights,
    and produces a structured English investment brief with macro context,
    ticker impact, and a differentiated signal vs. consensus.
    """
    file_path = Path(file)
    _header(
        "ALPHA  |  INTELLIGENCE BRIEF",
        f"File: {file_path.name}"
        + (f"  |  Ticker: {ticker.upper()}" if ticker else ""),
    )

    if not file_path.exists():
        console.print(f"[red]  File not found: {file}[/red]")
        raise typer.Exit(code=1)

    # ── Read file ─────────────────────────────────────────────────────
    try:
        if file_path.suffix.lower() == ".pdf":
            import pypdf
            reader = pypdf.PdfReader(str(file_path))
            content = "\n".join(
                page.extract_text() or "" for page in reader.pages
            )
        else:
            content = file_path.read_text(encoding="utf-8")
    except Exception as exc:
        console.print(f"[red]  Cannot read file: {exc}[/red]")
        raise typer.Exit(code=1)

    client = _get_client()
    agent = AlphaIntelAgent(client)

    # ── Masking ────────────────────────────────────────────────────────
    explicit = [ticker] if ticker else []
    masked_content, mapping = masker.mask(content, explicit_tickers=explicit)
    counts = masker.count_masked(mapping)

    masked_ticker: Optional[str] = None
    if ticker:
        for token, original in mapping.items():
            if original == ticker.upper():
                masked_ticker = token
                break
        if masked_ticker is None:
            masked_ticker = ticker.upper()

    console.print(
        f"\n[dim]  Masking pipeline: {sum(counts.values())} item(s) masked"
        f"  |  User: {CURRENT_USER}[/dim]"
    )

    # ── Run agent ──────────────────────────────────────────────────────
    t_start = time.time()
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as prog:
        prog.add_task("[magenta]Synthesizing cross-language intelligence...", total=None)
        try:
            response_masked, in_tok, out_tok = agent.run(masked_content, ticker=masked_ticker)
        except Exception as exc:
            console.print(f"\n[red]Alpha agent failed: {exc}[/red]")
            db.log_interaction(
                feature="alpha",
                input_summary=f"{file_path.name}" + (f" | {ticker}" if ticker else ""),
                masked_counts=counts,
                success=False,
                error_message=str(exc),
                session_id=SESSION_ID,
                user_name=CURRENT_USER,
                response_time_ms=int((time.time() - t_start) * 1000),
            )
            raise typer.Exit(code=1)

    response_ms = int((time.time() - t_start) * 1000)
    response = masker.unmask(response_masked, mapping)

    row_id = db.log_interaction(
        feature="alpha",
        input_summary=f"{file_path.name}" + (f" | {ticker}" if ticker else ""),
        masked_counts=counts,
        input_tokens=in_tok,
        output_tokens=out_tok,
        success=True,
        session_id=SESSION_ID,
        user_name=CURRENT_USER,
        response_time_ms=response_ms,
    )

    console.print()
    console.print(
        Panel(
            response,
            title=f"[bold magenta]ALPHA BRIEF  |  {file_path.name}[/bold magenta]",
            border_style="magenta",
            padding=(1, 2),
        )
    )
    _footer(in_tok, out_tok, sum(counts.values()), response_ms)

    rating, comment = _collect_feedback()
    if rating is not None:
        db.update_feedback(row_id, rating, comment)


# ---------------------------------------------------------------------------
# Feature B — verify
# ---------------------------------------------------------------------------


@app.command("verify")
def verify(
    ticker: str = typer.Option(..., "--ticker", "-t", help="Asset ticker to verify"),
    thesis: str = typer.Option(..., "--thesis", help="Investment thesis to stress-test"),
) -> None:
    """
    [yellow]Feature B: Thesis Verification[/yellow]

    Three-agent debate: BullCaseAgent builds the strongest possible bull case
    from internal RAG data; BearCaseAgent tears it apart; SynthesizerAgent
    delivers a risk-adjusted CIO verdict with conviction score.
    """
    _header(
        "VERIFY  |  THESIS STRESS-TEST",
        f"Ticker: {ticker.upper()}  |  Thesis: {thesis[:60]}{'...' if len(thesis) > 60 else ''}",
    )

    client = _get_client()

    # ── Masking ────────────────────────────────────────────────────────
    raw_input = f"Ticker: {ticker.upper()}. {thesis}"
    masked_text, mapping = masker.mask(raw_input, explicit_tickers=[ticker])
    counts = masker.count_masked(mapping)

    masked_ticker = ticker.upper()
    for token, original in mapping.items():
        if original == ticker.upper():
            masked_ticker = token
            break

    prefix = f"Ticker: {masked_ticker}. "
    masked_thesis = masked_text[len(prefix):] if masked_text.startswith(prefix) else masked_text

    console.print(
        f"\n[dim]  Masking pipeline: {counts['tickers']} ticker(s), "
        f"{counts['projects']} project name(s), {counts['schemas']} schema(s) masked"
        f"  |  User: {CURRENT_USER}[/dim]"
    )

    t_start = time.time()

    # ── Phase 1: Bull Case ─────────────────────────────────────────────
    console.print("\n[bold green]Phase 1[/bold green]  Bull Case Agent...")
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as prog:
        prog.add_task("[green]Building bull case from internal data...", total=None)
        try:
            bull_agent = BullCaseAgent(client)
            bull_case, in1, out1 = bull_agent.run(
                masked_ticker, masked_thesis, original_ticker=ticker.upper()
            )
        except Exception as exc:
            console.print(f"\n[red]Bull case agent failed: {exc}[/red]")
            db.log_interaction(
                feature="verify",
                input_summary=f"{ticker} | {thesis[:120]}",
                masked_counts=counts,
                success=False,
                error_message=str(exc),
                session_id=SESSION_ID,
                user_name=CURRENT_USER,
                response_time_ms=int((time.time() - t_start) * 1000),
            )
            raise typer.Exit(code=1)

    console.print("[green]  Bull case built.[/green]")

    # ── Phase 2: Bear Case ─────────────────────────────────────────────
    console.print("\n[bold red]Phase 2[/bold red]  Bear Case Agent...")
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as prog:
        prog.add_task("[red]Running contrarian analysis...", total=None)
        try:
            bear_agent = BearCaseAgent(client)
            bear_case, in2, out2 = bear_agent.run(masked_ticker, bull_case, masked_thesis)
        except Exception as exc:
            console.print(f"\n[red]Bear case agent failed: {exc}[/red]")
            db.log_interaction(
                feature="verify",
                input_summary=f"{ticker} | {thesis[:120]}",
                masked_counts=counts,
                success=False,
                error_message=str(exc),
                session_id=SESSION_ID,
                user_name=CURRENT_USER,
                response_time_ms=int((time.time() - t_start) * 1000),
            )
            raise typer.Exit(code=1)

    console.print("[red]  Bear case complete.[/red]")

    # ── Phase 3: Synthesis ─────────────────────────────────────────────
    console.print("\n[bold yellow]Phase 3[/bold yellow]  Synthesizer Agent...")
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as prog:
        prog.add_task("[yellow]Synthesizing risk-adjusted view...", total=None)
        try:
            synth_agent = SynthesizerAgent(client)
            synthesis, in3, out3 = synth_agent.run(masked_ticker, bull_case, bear_case)
        except Exception as exc:
            console.print(f"\n[red]Synthesizer agent failed: {exc}[/red]")
            db.log_interaction(
                feature="verify",
                input_summary=f"{ticker} | {thesis[:120]}",
                masked_counts=counts,
                success=False,
                error_message=str(exc),
                session_id=SESSION_ID,
                user_name=CURRENT_USER,
                response_time_ms=int((time.time() - t_start) * 1000),
            )
            raise typer.Exit(code=1)

    response_ms = int((time.time() - t_start) * 1000)
    in_tok = in1 + in2 + in3
    out_tok = out1 + out2 + out3

    # Unmask all responses
    bull_unmasked = masker.unmask(bull_case, mapping)
    bear_unmasked = masker.unmask(bear_case, mapping)
    synth_full = masker.unmask(synthesis.get("full_report", ""), mapping)

    row_id = db.log_interaction(
        feature="verify",
        input_summary=f"{ticker} | {thesis[:120]}",
        masked_counts=counts,
        input_tokens=in_tok,
        output_tokens=out_tok,
        success=True,
        session_id=SESSION_ID,
        user_name=CURRENT_USER,
        response_time_ms=response_ms,
    )

    # ── Summary Table ──────────────────────────────────────────────────
    conviction = synthesis.get("conviction", "HOLD")
    conv_score = synthesis.get("conviction_score", 50)
    key_risk = masker.unmask(synthesis.get("key_risk", ""), mapping)
    rec_action = masker.unmask(synthesis.get("recommended_action", ""), mapping)

    _CONV_COLOR = {
        "STRONG_BUY": "bold green", "BUY": "green",
        "HOLD": "yellow",
        "SELL": "red", "STRONG_SELL": "bold red",
    }
    cc = _CONV_COLOR.get(conviction.upper(), "white")

    score_color = "green" if conv_score >= 70 else "yellow" if conv_score >= 40 else "red"
    bar_fill = int(conv_score / 5)
    score_bar = (
        f"[{score_color}]{'█' * bar_fill}[/{score_color}]"
        f"[dim]{'░' * (20 - bar_fill)}[/dim]"
    )

    summary_table = Table(
        title=f"Thesis Verification  |  {ticker.upper()}",
        box=box.DOUBLE_EDGE,
        border_style="yellow",
        header_style="bold white",
    )
    summary_table.add_column("Metric", style="bold", width=22)
    summary_table.add_column("Value", width=54)
    summary_table.add_row("CONVICTION", f"[{cc}]{conviction}[/{cc}]")
    summary_table.add_row(
        "CONVICTION SCORE",
        f"[{score_color}]{conv_score} / 100[/{score_color}]  {score_bar}",
    )
    summary_table.add_row("KEY RISK", key_risk[:80])
    summary_table.add_row("RECOMMENDED ACTION", rec_action[:80])
    console.print()
    console.print(summary_table)

    # ── Full synthesis panel ───────────────────────────────────────────
    console.print()
    console.print(
        Panel(
            synth_full,
            title="[bold yellow]CIO SYNTHESIS[/bold yellow]",
            border_style="yellow",
            padding=(1, 2),
        )
    )

    # ── Bull / Bear panels ─────────────────────────────────────────────
    console.print()
    console.print(
        Panel(
            bull_unmasked,
            title="[bold green]BULL CASE[/bold green]",
            border_style="green",
            padding=(1, 2),
        )
    )
    console.print()
    console.print(
        Panel(
            bear_unmasked,
            title="[bold red]BEAR CASE[/bold red]",
            border_style="red",
            padding=(1, 2),
        )
    )

    _footer(in_tok, out_tok, sum(counts.values()), response_ms)

    rating, comment = _collect_feedback()
    if rating is not None:
        db.update_feedback(row_id, rating, comment)


# ---------------------------------------------------------------------------
# Feature C — query
# ---------------------------------------------------------------------------


@app.command("query")
def query(
    q: str = typer.Option(..., "--q", help="Natural language question about interactions"),
    viz: bool = typer.Option(False, "--viz", help="Render a bar chart if numeric data available"),
) -> None:
    """
    [cyan]Feature C: Natural Language Query[/cyan]

    Translates a plain-English question into SQLite SQL (TextToSQLAgent),
    executes it against the interactions database, and renders results as
    a Rich table. Use --viz to add a plotext bar chart.
    """
    _header(
        "QUERY  |  NATURAL LANGUAGE DATABASE",
        f"Question: {q[:70]}{'...' if len(q) > 70 else ''}",
    )

    client = _get_client()
    sql_agent = TextToSQLAgent(client)

    # ── Generate SQL ───────────────────────────────────────────────────
    t_start = time.time()
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as prog:
        prog.add_task("[cyan]Translating question to SQL...", total=None)
        try:
            sql, in_tok, out_tok = sql_agent.run(q)
        except Exception as exc:
            console.print(f"\n[red]SQL agent failed: {exc}[/red]")
            db.log_interaction(
                feature="query",
                input_summary=q[:120],
                masked_counts={"tickers": 0, "projects": 0, "schemas": 0},
                success=False,
                error_message=str(exc),
                session_id=SESSION_ID,
                user_name=CURRENT_USER,
                response_time_ms=int((time.time() - t_start) * 1000),
            )
            raise typer.Exit(code=1)

    # ── Show generated SQL ─────────────────────────────────────────────
    console.print()
    console.print(
        Panel(
            Syntax(sql, "sql", theme="monokai", word_wrap=True),
            title="[bold cyan]Generated SQL[/bold cyan]",
            border_style="cyan",
            padding=(0, 1),
        )
    )

    # ── Execute query ──────────────────────────────────────────────────
    try:
        results = db.execute_query(sql)
    except Exception as exc:
        console.print(f"\n[red]  Query execution failed: {exc}[/red]")
        db.log_interaction(
            feature="query",
            input_summary=q[:120],
            masked_counts={"tickers": 0, "projects": 0, "schemas": 0},
            input_tokens=in_tok,
            output_tokens=out_tok,
            success=False,
            error_message=str(exc),
            session_id=SESSION_ID,
            user_name=CURRENT_USER,
            response_time_ms=int((time.time() - t_start) * 1000),
        )
        raise typer.Exit(code=1)

    response_ms = int((time.time() - t_start) * 1000)

    db.log_interaction(
        feature="query",
        input_summary=q[:120],
        masked_counts={"tickers": 0, "projects": 0, "schemas": 0},
        input_tokens=in_tok,
        output_tokens=out_tok,
        success=True,
        session_id=SESSION_ID,
        user_name=CURRENT_USER,
        response_time_ms=response_ms,
    )

    if not results:
        console.print("\n[dim]  No results returned.[/dim]")
        _footer(in_tok, out_tok, 0, response_ms)
        return

    # ── Optional viz ──────────────────────────────────────────────────
    if viz:
        columns = list(results[0].keys())
        # Find first numeric column
        numeric_col: Optional[str] = None
        for col in columns:
            if isinstance(results[0][col], (int, float)):
                numeric_col = col
                break

        if numeric_col and len(columns) >= 1:
            x_col = columns[0]
            try:
                import plotext as plt

                x_vals = [str(r[x_col]) for r in results]
                y_vals = [float(r[numeric_col] or 0) for r in results]

                plt.clf()
                plt.bar(x_vals, y_vals)
                plt.title(f"{numeric_col} by {x_col}")
                plt.xlabel(x_col)
                plt.ylabel(numeric_col)
                plt.theme("dark")
                plt.plotsize(80, 18)
                chart_str = plt.build()

                console.print()
                console.print(
                    Panel(
                        chart_str,
                        title=f"[bold cyan]{numeric_col} by {x_col}[/bold cyan]",
                        border_style="cyan",
                        padding=(0, 1),
                    )
                )
            except ImportError:
                console.print("[dim]  (plotext not installed — skipping chart)[/dim]")
            except Exception as exc:
                console.print(f"[dim]  Chart error: {exc}[/dim]")
        else:
            console.print("[dim]  --viz: no numeric column found; skipping chart.[/dim]")

    # ── Results table ──────────────────────────────────────────────────
    columns = list(results[0].keys())
    result_table = Table(
        title=f"Query Results  ({len(results)} row{'s' if len(results) != 1 else ''})",
        box=box.ROUNDED,
        border_style="cyan",
        header_style="bold cyan",
    )
    for col in columns:
        result_table.add_column(col, overflow="fold")

    for row in results:
        result_table.add_row(*[str(v) if v is not None else "—" for v in row.values()])

    console.print()
    console.print(result_table)

    _footer(in_tok, out_tok, 0, response_ms)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main_entry() -> None:
    app()


if __name__ == "__main__":
    main_entry()
