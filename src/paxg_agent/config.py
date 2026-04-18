from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import yaml
from dotenv import load_dotenv


@dataclass(frozen=True)
class MarketConfig:
    symbol: str
    timeframe: str
    exchange_base_url: str


@dataclass(frozen=True)
class PortfolioConfig:
    starting_capital_usdt: float
    risk_per_trade: float
    max_concurrent_positions: int


@dataclass(frozen=True)
class ExecutionConfig:
    taker_fee: float
    slippage: float


@dataclass(frozen=True)
class StrategyConfig:
    name: str
    ema_fast: int
    ema_slow: int
    rsi_period: int
    rsi_oversold: float
    rsi_overbought: float
    atr_period: int
    atr_stop_mult: float
    atr_take_profit_mult: float


@dataclass(frozen=True)
class LLMConfig:
    model: str
    enabled_in_backtest: bool
    enabled_in_paper: bool
    max_tokens: int


@dataclass(frozen=True)
class PaperConfig:
    poll_interval_seconds: int
    duration_default: str


@dataclass(frozen=True)
class AppConfig:
    market: MarketConfig
    portfolio: PortfolioConfig
    execution: ExecutionConfig
    strategy: StrategyConfig
    llm: LLMConfig
    paper: PaperConfig
    anthropic_api_key: str | None


def load_config(path: str | Path = "config.yaml") -> AppConfig:
    load_dotenv()
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return AppConfig(
        market=MarketConfig(**data["market"]),
        portfolio=PortfolioConfig(**data["portfolio"]),
        execution=ExecutionConfig(**data["execution"]),
        strategy=StrategyConfig(**data["strategy"]),
        llm=LLMConfig(**data["llm"]),
        paper=PaperConfig(**data["paper"]),
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
    )
