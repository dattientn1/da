"""Typer CLI entry point.

Examples:
    paxg backtest --days 14
    paxg backtest --days 14 --llm-review
    paxg paper --duration 14d
    paxg paper --duration 30m --no-llm-review
"""
from __future__ import annotations

import typer

from .config import load_config

app = typer.Typer(no_args_is_help=True, add_completion=False)


@app.command()
def backtest(
    days: int = typer.Option(14, help="Lookback window in days."),
    llm_review: bool = typer.Option(
        False, "--llm-review/--no-llm-review", help="Run each signal through Claude reviewer."
    ),
    no_cache: bool = typer.Option(False, help="Force re-fetch from BingX, ignore parquet cache."),
    config_path: str = typer.Option("config.yaml", "--config"),
) -> None:
    """Replay historical klines through the strategy."""
    from .backtest import run_backtest

    cfg = load_config(config_path)
    run_backtest(cfg, days=days, llm_review=llm_review, use_cache=not no_cache)


@app.command()
def paper(
    duration: str = typer.Option("14d", help="Duration: e.g. 14d, 6h, 30m."),
    llm_review: bool = typer.Option(
        True, "--llm-review/--no-llm-review", help="Run each signal through Claude reviewer."
    ),
    config_path: str = typer.Option("config.yaml", "--config"),
) -> None:
    """Live polling paper trader. Never sends real orders."""
    from .paper import run_paper

    cfg = load_config(config_path)
    run_paper(cfg, duration=duration, llm_review=llm_review)


if __name__ == "__main__":
    app()
