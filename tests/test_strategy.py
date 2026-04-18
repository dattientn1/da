import numpy as np
import pandas as pd

from paxg_agent.config import StrategyConfig
from paxg_agent.indicators import add_indicators
from paxg_agent.strategy.base import SignalAction
from paxg_agent.strategy.hybrid import HybridStrategy


def _synth_df(n: int = 400, seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    # Trending up with noise so EMA fast > EMA slow most of the time.
    drift = np.cumsum(rng.normal(0.05, 1.0, n))
    close = pd.Series(drift + 2000)
    high = close + rng.uniform(0.5, 2.0, n)
    low = close - rng.uniform(0.5, 2.0, n)
    return pd.DataFrame(
        {
            "open": close.shift(1).fillna(close.iloc[0]),
            "high": high,
            "low": low,
            "close": close,
            "volume": np.ones(n),
        },
        index=pd.date_range("2026-01-01", periods=n, freq="1h", tz="UTC"),
    )


def test_strategy_runs_without_errors():
    cfg = StrategyConfig(
        name="test",
        ema_fast=20,
        ema_slow=50,
        rsi_period=14,
        rsi_oversold=30,
        rsi_overbought=70,
        atr_period=14,
        atr_stop_mult=2.0,
        atr_take_profit_mult=3.0,
    )
    df = add_indicators(_synth_df(), cfg.ema_fast, cfg.ema_slow, cfg.rsi_period, cfg.atr_period)
    strat = HybridStrategy(cfg)

    prev = None
    actions: set[SignalAction] = set()
    for ts, row in df.iterrows():
        sig = strat.generate(row, prev, in_position=False)
        actions.add(sig.action)
        prev = row

    # Should at least produce HOLD signals; OPEN_LONG depends on RSI behaviour.
    assert SignalAction.HOLD in actions
