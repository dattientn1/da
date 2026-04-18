"""Backtest/paper-run reporting: stats, equity curve, trade log."""
from __future__ import annotations

import json
import math
from dataclasses import asdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from .portfolio import Portfolio


def summarize(p: Portfolio, starting_capital: float) -> dict:
    if not p.equity_curve:
        return {"error": "no equity points"}

    equity_df = pd.DataFrame(p.equity_curve, columns=["timestamp", "equity"]).set_index(
        "timestamp"
    )
    final_equity = float(equity_df["equity"].iloc[-1])
    total_return = (final_equity - starting_capital) / starting_capital

    # Hourly returns -> Sharpe (assume 24*365 = 8760 hours/yr scaling)
    rets = equity_df["equity"].pct_change().dropna()
    sharpe = (
        float(rets.mean() / rets.std() * math.sqrt(8760))
        if len(rets) > 1 and rets.std() > 0
        else 0.0
    )

    rolling_max = equity_df["equity"].cummax()
    drawdown = (equity_df["equity"] - rolling_max) / rolling_max
    max_drawdown = float(drawdown.min()) if len(drawdown) else 0.0

    wins = [t for t in p.trades if t.pnl > 0]
    losses = [t for t in p.trades if t.pnl <= 0]
    win_rate = len(wins) / len(p.trades) if p.trades else 0.0
    avg_win = sum(t.pnl for t in wins) / len(wins) if wins else 0.0
    avg_loss = sum(t.pnl for t in losses) / len(losses) if losses else 0.0
    total_fees = sum(t.fees for t in p.trades)

    return {
        "starting_capital": starting_capital,
        "final_equity": final_equity,
        "total_return_pct": total_return * 100,
        "sharpe_annualized": sharpe,
        "max_drawdown_pct": max_drawdown * 100,
        "trades": len(p.trades),
        "win_rate_pct": win_rate * 100,
        "avg_win_usdt": avg_win,
        "avg_loss_usdt": avg_loss,
        "total_fees_usdt": total_fees,
    }


def write_reports(p: Portfolio, starting_capital: float, out_dir: str | Path = "results") -> dict:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    summary = summarize(p, starting_capital)
    (out / "summary.json").write_text(json.dumps(summary, indent=2, default=str))

    if p.trades:
        trades_df = pd.DataFrame([asdict(t) for t in p.trades])
        trades_df.to_csv(out / "trades.csv", index=False)

    if p.equity_curve:
        eq = pd.DataFrame(p.equity_curve, columns=["timestamp", "equity"]).set_index(
            "timestamp"
        )
        eq.to_csv(out / "equity.csv")
        fig, ax = plt.subplots(figsize=(11, 5))
        ax.plot(eq.index, eq["equity"], label="Equity (USDT)")
        ax.axhline(starting_capital, color="grey", linestyle="--", label="Starting capital")
        ax.set_title("PAXG/USDT sandbox equity curve")
        ax.set_ylabel("USDT")
        ax.grid(alpha=0.3)
        ax.legend()
        fig.tight_layout()
        fig.savefig(out / "equity.png", dpi=120)
        plt.close(fig)

    return summary
