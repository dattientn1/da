from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class SignalAction(str, Enum):
    OPEN_LONG = "OPEN_LONG"
    CLOSE = "CLOSE"
    HOLD = "HOLD"


@dataclass(frozen=True)
class Signal:
    timestamp: datetime
    action: SignalAction
    price: float
    stop_loss: float | None = None
    take_profit: float | None = None
    reason: str = ""
    indicators: dict | None = None
