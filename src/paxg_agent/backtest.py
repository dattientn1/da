"""Replay 2 weeks of historical PAXG/USDT klines through the strategy."""
from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

import pandas as pd
from rich.console import Console
from rich.table import Table

from .agent.reviewer import LLMReviewer, ReviewDecision
from .config import AppConfig
from .data.bingx_client import BingXClient
from .data import store
from .execution.broker import SimulatedBroker
from .indicators import add_indicators
from .portfolio import Portfolio
from .reporting import write_reports
from .strategy.base import SignalAction
from .strategy.hybrid import HybridStrategy

console = Console()


def fetch_two_weeks(cfg: AppConfig, days: int = 14, use_cache: bool = True) -> pd.DataFrame:
    if use_cache:
        cached = store.load(cfg.market.symbol, cfg.market.timeframe)
        if cached is not None and not cached.empty:
            min_ts = cached.index.min()
            max_ts = cached.index.max()
            console.log(f"Loaded {len(cached)} cached candles ({min_ts} → {max_ts})")
            cutoff = pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=days)
            sliced = cached[cached.index >= cutoff]
            if len(sliced) > 100:
                return sliced

    client = BingXClient(base_url=cfg.market.exchange_base_url)
    end_ms = int(time.time() * 1000)
    start_ms = end_ms - days * 24 * 60 * 60 * 1000
    df = client.fetch_klines(
        symbol=cfg.market.symbol,
        interval=cfg.market.timeframe,
        limit=1000,
        start_time_ms=start_ms,
        end_time_ms=end_ms,
    )
    console.log(f"Fetched {len(df)} candles from BingX ({df.index.min()} → {df.index.max()})")
    store.save(df, cfg.market.symbol, cfg.market.timeframe)
    return df


def run_backtest(
    cfg: AppConfig, days: int = 14, llm_review: bool | None = None, use_cache: bool = True
) -> dict:
    use_llm = cfg.llm.enabled_in_backtest if llm_review is None else llm_review
    reviewer = LLMReviewer(cfg.llm, cfg.anthropic_api_key) if use_llm else None
    if use_llm and (reviewer is None or not reviewer.available):
        console.log("[yellow]LLM review requested but no ANTHROPIC_API_KEY set — disabling.[/]")
        reviewer = None

    df = fetch_two_weeks(cfg, days=days, use_cache=use_cache)
    df = add_indicators(
        df, cfg.strategy.ema_fast, cfg.strategy.ema_slow, cfg.strategy.rsi_period, cfg.strategy.atr_period
    )

    portfolio = Portfolio(cash=cfg.portfolio.starting_capital_usdt)
    broker = SimulatedBroker(cfg.execution)
    strategy = HybridStrategy(cfg.strategy)

    prev_row: pd.Series | None = None
    rows = list(df.itertuples(name=None))  # (ts, open, high, low, close, volume, ema_fast, ema_slow, rsi, atr)
    cols = ["open", "high", "low", "close", "volume", "ema_fast", "ema_slow", "rsi", "atr"]

    for raw in rows:
        ts = raw[0]
        row = pd.Series(dict(zip(cols, raw[1:])), name=ts)
        signal = strategy.generate(
            row,
            prev_row,
            in_position=portfolio.is_in_position,
            position_stop=portfolio.position.stop_loss if portfolio.position else None,
            position_take_profit=portfolio.position.take_profit if portfolio.position else None,
        )

        if signal.action == SignalAction.OPEN_LONG and signal.stop_loss is not None:
            equity = portfolio.equity(signal.price)
            qty = portfolio.position_size(
                equity, cfg.portfolio.risk_per_trade, signal.price, signal.stop_loss
            )
            decision: ReviewDecision | None = None
            if reviewer is not None:
                recent_dicts = (
                    df.loc[:ts]
                    .tail(12)
                    .reset_index()
                    .to_dict(orient="records")
                )
                decision = reviewer.review(
                    signal_indicators=signal.indicators or {},
                    proposed_entry=signal.price,
                    proposed_stop=signal.stop_loss,
                    proposed_take_profit=signal.take_profit or 0.0,
                    proposed_qty=qty,
                    portfolio_equity=equity,
                    recent_candles=recent_dicts,
                )
                console.log(
                    f"[cyan]LLM[/] {ts} {decision.decision} ({decision.confidence:.2f}) — {decision.rationale[:100]}"
                )
                qty *= decision.size_multiplier
            if qty > 0:
                pos = broker.open_long(
                    portfolio, ts, signal.price, qty, signal.stop_loss, signal.take_profit
                )
                if pos is not None:
                    console.log(
                        f"[green]OPEN[/] {ts} qty={qty:.4f} @ {pos.entry_price:.2f} "
                        f"stop={signal.stop_loss:.2f} tp={signal.take_profit:.2f}"
                    )

        elif signal.action == SignalAction.CLOSE:
            llm_dec = (
                portfolio.position.__dict__.get("_llm_decision")
                if portfolio.position
                else None
            )
            llm_rat = (
                portfolio.position.__dict__.get("_llm_rationale")
                if portfolio.position
                else None
            )
            trade = broker.close(
                portfolio, ts, signal.price, signal.reason, llm_decision=llm_dec, llm_rationale=llm_rat
            )
            if trade is not None:
                console.log(
                    f"[red]CLOSE[/] {ts} pnl={trade.pnl:+.2f} USDT ({signal.reason})"
                )

        portfolio.record_equity(ts, float(row["close"]))
        prev_row = row

    # Mark to last close if still in position
    if portfolio.position is not None and len(df):
        last = df.iloc[-1]
        broker.close(portfolio, df.index[-1], float(last["close"]), "end-of-backtest mark-to-close")
        portfolio.record_equity(df.index[-1], float(last["close"]))

    summary = write_reports(portfolio, cfg.portfolio.starting_capital_usdt)
    _print_summary(summary)
    return summary


def _print_summary(summary: dict) -> None:
    table = Table(title="Backtest summary")
    table.add_column("Metric")
    table.add_column("Value", justify="right")
    for k, v in summary.items():
        if isinstance(v, float):
            table.add_row(k, f"{v:,.2f}")
        else:
            table.add_row(k, str(v))
    console.print(table)
