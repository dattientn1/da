"""Local cache for OHLCV data, stored as parquet under data/."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

CACHE_DIR = Path("data")


def cache_path(symbol: str, timeframe: str) -> Path:
    safe_symbol = symbol.replace("/", "_").replace("-", "_")
    return CACHE_DIR / f"{safe_symbol}_{timeframe}.parquet"


def save(df: pd.DataFrame, symbol: str, timeframe: str) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = cache_path(symbol, timeframe)
    df.to_parquet(path)
    return path


def load(symbol: str, timeframe: str) -> pd.DataFrame | None:
    path = cache_path(symbol, timeframe)
    if not path.exists():
        return None
    return pd.read_parquet(path)
