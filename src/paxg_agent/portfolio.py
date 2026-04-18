from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Position:
    entry_time: datetime
    entry_price: float
    qty: float
    stop_loss: float | None
    take_profit: float | None


@dataclass
class Trade:
    entry_time: datetime
    exit_time: datetime
    entry_price: float
    exit_price: float
    qty: float
    pnl: float
    fees: float
    reason: str
    llm_decision: str | None = None
    llm_rationale: str | None = None


@dataclass
class Portfolio:
    cash: float
    position: Position | None = None
    trades: list[Trade] = field(default_factory=list)
    equity_curve: list[tuple[datetime, float]] = field(default_factory=list)

    @property
    def is_in_position(self) -> bool:
        return self.position is not None

    def equity(self, mark_price: float) -> float:
        if self.position is None:
            return self.cash
        return self.cash + self.position.qty * mark_price

    def position_size(self, equity: float, risk_pct: float, entry: float, stop: float) -> float:
        risk_per_unit = max(entry - stop, 1e-9)
        risk_dollars = equity * risk_pct
        qty = risk_dollars / risk_per_unit
        max_qty_by_cash = (self.cash * 0.99) / entry
        return max(min(qty, max_qty_by_cash), 0.0)

    def record_equity(self, ts: datetime, mark_price: float) -> None:
        self.equity_curve.append((ts, self.equity(mark_price)))
