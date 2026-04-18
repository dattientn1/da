"""Append-mode CSV writers so a long paper run survives crash / Ctrl+C.

Three streams:
  - trades.csv      — closed trades, written on each CLOSE
  - equity.csv      — equity per evaluated tick
  - llm_decisions.csv — every LLM review (incl. VETO / REDUCE_SIZE)
"""
from __future__ import annotations

import csv
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from .agent.reviewer import ReviewDecision
from .portfolio import Trade


@dataclass
class StreamingWriter:
    out_dir: Path

    def __post_init__(self) -> None:
        self.out_dir.mkdir(parents=True, exist_ok=True)

    @property
    def trades_path(self) -> Path:
        return self.out_dir / "trades.csv"

    @property
    def equity_path(self) -> Path:
        return self.out_dir / "equity.csv"

    @property
    def llm_path(self) -> Path:
        return self.out_dir / "llm_decisions.csv"

    def append_trade(self, trade: Trade) -> None:
        self._append(self.trades_path, asdict(trade))

    def append_equity(self, ts: datetime, equity: float, price: float) -> None:
        self._append(self.equity_path, {"timestamp": ts, "equity": equity, "price": price})

    def append_llm(
        self,
        ts: datetime,
        decision: ReviewDecision,
        proposed_entry: float,
        proposed_qty: float,
    ) -> None:
        self._append(
            self.llm_path,
            {
                "timestamp": ts,
                "decision": decision.decision,
                "size_multiplier": decision.size_multiplier,
                "confidence": decision.confidence,
                "proposed_entry": proposed_entry,
                "proposed_qty": proposed_qty,
                "rationale": decision.rationale,
                "news_summary": decision.news_summary,
            },
        )

    @staticmethod
    def _append(path: Path, row: dict[str, Any]) -> None:
        new_file = not path.exists()
        with path.open("a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(row.keys()))
            if new_file:
                writer.writeheader()
            writer.writerow({k: _stringify(v) for k, v in row.items()})


def _stringify(v: Any) -> str:
    if isinstance(v, datetime):
        return v.isoformat()
    return str(v)
