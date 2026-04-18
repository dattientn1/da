"""Simulated broker for both backtest and paper trading.

Both modes use the same fill model — only the data source differs (replayed
historical klines vs live polled klines). No real orders are ever sent.
"""
from __future__ import annotations

from datetime import datetime

from ..config import ExecutionConfig
from ..portfolio import Portfolio, Position, Trade
from .simulator import fill_buy, fill_sell


class SimulatedBroker:
    def __init__(self, cfg: ExecutionConfig):
        self.cfg = cfg

    def open_long(
        self,
        portfolio: Portfolio,
        ts: datetime,
        price: float,
        qty: float,
        stop_loss: float | None,
        take_profit: float | None,
    ) -> Position | None:
        if qty <= 0 or portfolio.is_in_position:
            return None
        fill = fill_buy(price, qty, self.cfg.taker_fee, self.cfg.slippage)
        cost = fill.fill_price * qty + fill.fee_usdt
        if cost > portfolio.cash:
            return None
        portfolio.cash -= cost
        portfolio.position = Position(
            entry_time=ts,
            entry_price=fill.fill_price,
            qty=qty,
            stop_loss=stop_loss,
            take_profit=take_profit,
        )
        # Stash fee on the position via attribute hack: track on Trade close instead.
        portfolio.position.__dict__["_open_fee"] = fill.fee_usdt
        return portfolio.position

    def close(
        self,
        portfolio: Portfolio,
        ts: datetime,
        price: float,
        reason: str,
        llm_decision: str | None = None,
        llm_rationale: str | None = None,
    ) -> Trade | None:
        if portfolio.position is None:
            return None
        pos = portfolio.position
        fill = fill_sell(price, pos.qty, self.cfg.taker_fee, self.cfg.slippage)
        proceeds = fill.fill_price * pos.qty - fill.fee_usdt
        portfolio.cash += proceeds
        open_fee = pos.__dict__.get("_open_fee", 0.0)
        total_fees = open_fee + fill.fee_usdt
        pnl = (fill.fill_price - pos.entry_price) * pos.qty - total_fees
        trade = Trade(
            entry_time=pos.entry_time,
            exit_time=ts,
            entry_price=pos.entry_price,
            exit_price=fill.fill_price,
            qty=pos.qty,
            pnl=pnl,
            fees=total_fees,
            reason=reason,
            llm_decision=llm_decision,
            llm_rationale=llm_rationale,
        )
        portfolio.trades.append(trade)
        portfolio.position = None
        return trade
