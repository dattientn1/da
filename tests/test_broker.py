from datetime import datetime, timezone

from paxg_agent.config import ExecutionConfig
from paxg_agent.execution.broker import SimulatedBroker
from paxg_agent.execution.simulator import fill_buy, fill_sell
from paxg_agent.portfolio import Portfolio


def test_fill_applies_slippage_and_fee():
    fill = fill_buy(price=2000.0, qty=1.0, taker_fee=0.001, slippage=0.0005)
    assert fill.fill_price == 2001.0
    assert fill.fee_usdt == 2.001  # 2001 * 1.0 * 0.001

    fill = fill_sell(price=2000.0, qty=1.0, taker_fee=0.001, slippage=0.0005)
    assert fill.fill_price == 1999.0
    assert fill.fee_usdt == 1.999


def test_full_round_trip_pnl():
    cfg = ExecutionConfig(taker_fee=0.001, slippage=0.0005)
    broker = SimulatedBroker(cfg)
    p = Portfolio(cash=10_000.0)
    ts = datetime(2026, 4, 1, tzinfo=timezone.utc)

    pos = broker.open_long(p, ts, price=2000.0, qty=1.0, stop_loss=1960.0, take_profit=2080.0)
    assert pos is not None
    # Cash spent: 2001 * 1 + fee 2.001 = 2003.001
    assert abs(p.cash - (10_000.0 - 2003.001)) < 1e-6

    trade = broker.close(p, ts, price=2080.0, reason="take-profit")
    assert trade is not None
    # Sell fill: 2080 * (1 - 0.0005) = 2078.96; fee = 2078.96 * 0.001 = 2.07896
    # PnL = (2078.96 - 2001) * 1 - (2.001 + 2.07896) = 77.96 - 4.07996 = 73.88004
    assert abs(trade.pnl - 73.88004) < 1e-3
    assert p.position is None


def test_position_size_respects_risk():
    p = Portfolio(cash=10_000.0)
    # risk 1% of 10k = $100; entry-stop = $40 → qty = 2.5
    qty = p.position_size(equity=10_000.0, risk_pct=0.01, entry=2000.0, stop=1960.0)
    assert abs(qty - 2.5) < 1e-9


def test_cannot_open_when_in_position():
    cfg = ExecutionConfig(taker_fee=0.001, slippage=0.0005)
    broker = SimulatedBroker(cfg)
    p = Portfolio(cash=10_000.0)
    ts = datetime(2026, 4, 1, tzinfo=timezone.utc)
    broker.open_long(p, ts, 2000.0, 1.0, 1960.0, 2080.0)
    second = broker.open_long(p, ts, 2010.0, 1.0, 1970.0, 2090.0)
    assert second is None
