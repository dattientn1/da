"""EMA crossover + RSI mean-reversion entry, ATR-based exits.

Spot only — long entries only.
"""
from __future__ import annotations

import pandas as pd

from ..config import StrategyConfig
from .base import Signal, SignalAction


class HybridStrategy:
    def __init__(self, cfg: StrategyConfig):
        self.cfg = cfg

    def generate(
        self,
        row: pd.Series,
        prev_row: pd.Series | None,
        in_position: bool,
        position_stop: float | None = None,
        position_take_profit: float | None = None,
    ) -> Signal:
        ts = row.name.to_pydatetime() if hasattr(row.name, "to_pydatetime") else row.name
        price = float(row["close"])
        ind = {
            "ema_fast": float(row["ema_fast"]),
            "ema_slow": float(row["ema_slow"]),
            "rsi": float(row["rsi"]),
            "atr": float(row["atr"]),
        }

        # Skip until indicators are warmed up
        if pd.isna(ind["ema_slow"]) or pd.isna(ind["rsi"]) or pd.isna(ind["atr"]):
            return Signal(ts, SignalAction.HOLD, price, reason="warmup", indicators=ind)

        # Exit logic
        if in_position:
            if position_stop is not None and float(row["low"]) <= position_stop:
                return Signal(
                    ts,
                    SignalAction.CLOSE,
                    position_stop,
                    reason=f"stop-loss hit ({position_stop:.2f})",
                    indicators=ind,
                )
            if position_take_profit is not None and float(row["high"]) >= position_take_profit:
                return Signal(
                    ts,
                    SignalAction.CLOSE,
                    position_take_profit,
                    reason=f"take-profit hit ({position_take_profit:.2f})",
                    indicators=ind,
                )
            if ind["rsi"] >= self.cfg.rsi_overbought:
                return Signal(
                    ts,
                    SignalAction.CLOSE,
                    price,
                    reason=f"RSI overbought ({ind['rsi']:.1f})",
                    indicators=ind,
                )
            return Signal(ts, SignalAction.HOLD, price, reason="hold position", indicators=ind)

        # Entry logic
        if prev_row is None or pd.isna(prev_row["rsi"]):
            return Signal(ts, SignalAction.HOLD, price, reason="warmup", indicators=ind)

        prev_rsi = float(prev_row["rsi"])
        trend_up = ind["ema_fast"] > ind["ema_slow"]
        rsi_cross_up = prev_rsi <= self.cfg.rsi_oversold and ind["rsi"] > self.cfg.rsi_oversold

        if trend_up and rsi_cross_up:
            stop = price - self.cfg.atr_stop_mult * ind["atr"]
            take = price + self.cfg.atr_take_profit_mult * ind["atr"]
            return Signal(
                ts,
                SignalAction.OPEN_LONG,
                price,
                stop_loss=stop,
                take_profit=take,
                reason=(
                    f"trend up (EMA{self.cfg.ema_fast}>{self.cfg.ema_slow}) "
                    f"+ RSI cross-up from oversold ({prev_rsi:.1f}->{ind['rsi']:.1f})"
                ),
                indicators=ind,
            )
        return Signal(ts, SignalAction.HOLD, price, reason="no setup", indicators=ind)
