"""Fill model: applies fees and slippage to a requested price.

Spot-only. Long opens fill above quoted price (taker buy), closes fill below
(taker sell). Fee is taken in USDT on the notional; slippage is multiplicative.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class FillResult:
    fill_price: float
    fee_usdt: float


def fill_buy(price: float, qty: float, taker_fee: float, slippage: float) -> FillResult:
    fill_price = price * (1.0 + slippage)
    fee = fill_price * qty * taker_fee
    return FillResult(fill_price=fill_price, fee_usdt=fee)


def fill_sell(price: float, qty: float, taker_fee: float, slippage: float) -> FillResult:
    fill_price = price * (1.0 - slippage)
    fee = fill_price * qty * taker_fee
    return FillResult(fill_price=fill_price, fee_usdt=fee)
