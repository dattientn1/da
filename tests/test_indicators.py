import numpy as np
import pandas as pd

from paxg_agent.indicators import atr, ema, rsi, add_indicators


def test_ema_matches_pandas_ewm():
    s = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
    out = ema(s, 3)
    # First value of EMA with adjust=False equals seed value.
    assert out.iloc[0] == 1.0
    # Increasing series → EMA strictly increasing.
    assert (out.diff().dropna() > 0).all()


def test_rsi_extremes():
    # All-up moves -> RSI should approach 100
    up = pd.Series(np.arange(1, 50, dtype=float))
    out = rsi(up, 14)
    assert out.iloc[-1] > 90
    # All-down moves -> RSI should approach 0
    down = pd.Series(np.arange(50, 1, -1, dtype=float))
    out = rsi(down, 14)
    assert out.iloc[-1] < 10


def test_atr_positive():
    n = 30
    rng = np.random.default_rng(0)
    close = pd.Series(np.cumsum(rng.normal(0, 1, n)) + 100)
    high = close + rng.uniform(0.1, 1.0, n)
    low = close - rng.uniform(0.1, 1.0, n)
    out = atr(high, low, close, 14)
    assert out.dropna().min() > 0


def test_add_indicators_columns():
    n = 100
    rng = np.random.default_rng(1)
    idx = pd.date_range("2026-01-01", periods=n, freq="1h", tz="UTC")
    close_arr = np.cumsum(rng.normal(0, 1, n)) + 2000
    df = pd.DataFrame(
        {
            "open": close_arr - 1,
            "high": close_arr + 2,
            "low": close_arr - 2,
            "close": close_arr,
            "volume": np.ones(n),
        },
        index=idx,
    )
    out = add_indicators(df, 20, 50, 14, 14)
    for col in ("ema_fast", "ema_slow", "rsi", "atr"):
        assert col in out.columns
    assert not out["ema_fast"].isna().all()
