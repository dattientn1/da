"""Live paper-trading loop: poll BingX, evaluate on closed candles, never send real orders."""
from __future__ import annotations

import re
import time
from datetime import datetime, timedelta, timezone

import pandas as pd
from rich.console import Console

from .agent.reviewer import LLMReviewer
from .config import AppConfig
from .data.bingx_client import BingXClient
from .execution.broker import SimulatedBroker
from .indicators import add_indicators
from .portfolio import Portfolio
from .reporting import write_reports
from .strategy.base import SignalAction
from .strategy.hybrid import HybridStrategy

console = Console()


def parse_duration(s: str) -> timedelta:
    m = re.fullmatch(r"(\d+)([smhd])", s.strip())
    if not m:
        raise ValueError(f"invalid duration {s!r}, use e.g. 14d, 6h, 30m")
    n, unit = int(m.group(1)), m.group(2)
    return {"s": timedelta(seconds=n), "m": timedelta(minutes=n), "h": timedelta(hours=n), "d": timedelta(days=n)}[unit]


def run_paper(cfg: AppConfig, duration: str | None = None, llm_review: bool | None = None) -> dict:
    use_llm = cfg.llm.enabled_in_paper if llm_review is None else llm_review
    reviewer = LLMReviewer(cfg.llm, cfg.anthropic_api_key) if use_llm else None
    if use_llm and (reviewer is None or not reviewer.available):
        console.log("[yellow]LLM review requested but no ANTHROPIC_API_KEY set — disabling.[/]")
        reviewer = None

    dur = parse_duration(duration or cfg.paper.duration_default)
    deadline = datetime.now(timezone.utc) + dur
    console.log(f"[bold]Paper trading until[/] {deadline.isoformat()} ({dur})")

    client = BingXClient(base_url=cfg.market.exchange_base_url)
    portfolio = Portfolio(cash=cfg.portfolio.starting_capital_usdt)
    broker = SimulatedBroker(cfg.execution)
    strategy = HybridStrategy(cfg.strategy)

    last_seen_ts: pd.Timestamp | None = None
    prev_row: pd.Series | None = None

    while datetime.now(timezone.utc) < deadline:
        try:
            df = client.fetch_klines(
                symbol=cfg.market.symbol, interval=cfg.market.timeframe, limit=200
            )
        except Exception as e:  # noqa: BLE001
            console.log(f"[yellow]fetch error: {e}; retrying in {cfg.paper.poll_interval_seconds}s[/]")
            time.sleep(cfg.paper.poll_interval_seconds)
            continue

        if df.empty:
            time.sleep(cfg.paper.poll_interval_seconds)
            continue

        df = add_indicators(
            df,
            cfg.strategy.ema_fast,
            cfg.strategy.ema_slow,
            cfg.strategy.rsi_period,
            cfg.strategy.atr_period,
        )

        # The last row is the *forming* candle; the second-to-last is the most recently closed.
        if len(df) < 2:
            time.sleep(cfg.paper.poll_interval_seconds)
            continue
        closed = df.iloc[:-1]
        latest_closed_ts = closed.index[-1]

        if last_seen_ts is None or latest_closed_ts > last_seen_ts:
            row = closed.iloc[-1]
            ts = row.name
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
                if reviewer is not None:
                    recent = closed.tail(12).reset_index().to_dict(orient="records")
                    decision = reviewer.review(
                        signal_indicators=signal.indicators or {},
                        proposed_entry=signal.price,
                        proposed_stop=signal.stop_loss,
                        proposed_take_profit=signal.take_profit or 0.0,
                        proposed_qty=qty,
                        portfolio_equity=equity,
                        recent_candles=recent,
                    )
                    console.log(
                        f"[cyan]LLM[/] {decision.decision} ({decision.confidence:.2f})"
                        f" news=[i]{decision.news_summary[:80]}[/i]"
                        f" — {decision.rationale[:120]}"
                    )
                    qty *= decision.size_multiplier
                if qty > 0:
                    pos = broker.open_long(
                        portfolio, ts, signal.price, qty, signal.stop_loss, signal.take_profit
                    )
                    if pos is not None:
                        console.log(
                            f"[green]OPEN[/] {ts} qty={qty:.4f} @ {pos.entry_price:.2f}"
                        )
            elif signal.action == SignalAction.CLOSE:
                trade = broker.close(portfolio, ts, signal.price, signal.reason)
                if trade is not None:
                    console.log(f"[red]CLOSE[/] {ts} pnl={trade.pnl:+.2f} USDT ({signal.reason})")

            portfolio.record_equity(ts, float(row["close"]))
            last_seen_ts = latest_closed_ts
            prev_row = row

        time.sleep(cfg.paper.poll_interval_seconds)

    if portfolio.position is not None and last_seen_ts is not None:
        last_price = float(closed.iloc[-1]["close"])
        broker.close(portfolio, last_seen_ts, last_price, "end-of-paper mark-to-close")
        portfolio.record_equity(last_seen_ts, last_price)

    summary = write_reports(portfolio, cfg.portfolio.starting_capital_usdt)
    console.print_json(data=summary)
    return summary
