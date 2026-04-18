"""BingX public spot market data client.

Only public endpoints are used (no API key needed):
- GET /openApi/spot/v2/market/kline
- GET /openApi/spot/v1/ticker/24hr
"""
from __future__ import annotations

from dataclasses import dataclass

import httpx
import pandas as pd

DEFAULT_BASE_URL = "https://open-api.bingx.com"
KLINE_PATH = "/openApi/spot/v2/market/kline"
TICKER_PATH = "/openApi/spot/v1/ticker/24hr"

# BingX returns at most 1000 candles per request.
MAX_LIMIT = 1000


@dataclass
class BingXClient:
    base_url: str = DEFAULT_BASE_URL
    timeout: float = 15.0

    def _get(self, path: str, params: dict) -> dict:
        with httpx.Client(timeout=self.timeout) as client:
            r = client.get(self.base_url + path, params=params)
            r.raise_for_status()
            payload = r.json()
        if isinstance(payload, dict) and payload.get("code") not in (0, None):
            raise RuntimeError(f"BingX error {payload.get('code')}: {payload.get('msg')}")
        return payload

    def fetch_klines(
        self,
        symbol: str = "PAXG-USDT",
        interval: str = "1h",
        limit: int = 500,
        start_time_ms: int | None = None,
        end_time_ms: int | None = None,
    ) -> pd.DataFrame:
        """Fetch historical OHLCV candles, returned newest-first by BingX.

        Returns a DataFrame indexed by timestamp (UTC), oldest first, with columns
        open/high/low/close/volume.
        """
        params: dict = {
            "symbol": symbol,
            "interval": interval,
            "limit": min(limit, MAX_LIMIT),
        }
        if start_time_ms is not None:
            params["startTime"] = start_time_ms
        if end_time_ms is not None:
            params["endTime"] = end_time_ms

        payload = self._get(KLINE_PATH, params)
        rows = payload.get("data", []) if isinstance(payload, dict) else []
        if not rows:
            return pd.DataFrame(
                columns=["open", "high", "low", "close", "volume"]
            ).rename_axis("timestamp")

        # BingX kline row: [openTime, open, high, low, close, volume, closeTime, ...]
        df = pd.DataFrame(
            rows,
            columns=[
                "timestamp",
                "open",
                "high",
                "low",
                "close",
                "volume",
                "close_time",
                "quote_volume",
            ][: len(rows[0])],
        )
        df["timestamp"] = pd.to_datetime(df["timestamp"].astype("int64"), unit="ms", utc=True)
        for col in ("open", "high", "low", "close", "volume"):
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df = df[["timestamp", "open", "high", "low", "close", "volume"]]
        df = df.sort_values("timestamp").set_index("timestamp")
        return df

    def fetch_ticker(self, symbol: str = "PAXG-USDT") -> dict:
        return self._get(TICKER_PATH, {"symbol": symbol})
