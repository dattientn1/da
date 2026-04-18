from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from paxg_agent.agent.reviewer import ReviewDecision
from paxg_agent.notifier import TelegramNotifier
from paxg_agent.portfolio import Trade
from paxg_agent.streaming_writer import StreamingWriter


def test_writer_appends_headers_once(tmp_path: Path) -> None:
    w = StreamingWriter(tmp_path)
    ts = datetime(2026, 4, 1, 12, 0, tzinfo=timezone.utc)
    w.append_equity(ts, 10_000.0, 2400.0)
    w.append_equity(ts, 10_010.0, 2401.0)
    rows = pd.read_csv(w.equity_path)
    assert list(rows.columns) == ["timestamp", "equity", "price"]
    assert len(rows) == 2


def test_writer_trade_and_llm(tmp_path: Path) -> None:
    w = StreamingWriter(tmp_path)
    ts = datetime(2026, 4, 1, tzinfo=timezone.utc)
    trade = Trade(
        entry_time=ts, exit_time=ts, entry_price=2000.0, exit_price=2080.0,
        qty=1.0, pnl=78.0, fees=2.0, reason="take-profit",
    )
    w.append_trade(trade)
    df = pd.read_csv(w.trades_path)
    assert df.iloc[0]["pnl"] == 78.0

    decision = ReviewDecision("VETO", 0.0, 0.9, "FOMC tonight", "Hawkish Fed expected")
    w.append_llm(ts, decision, proposed_entry=2000.0, proposed_qty=0.5)
    llm_df = pd.read_csv(w.llm_path)
    assert llm_df.iloc[0]["decision"] == "VETO"
    assert llm_df.iloc[0]["proposed_qty"] == 0.5


def test_telegram_disabled_when_env_missing(monkeypatch) -> None:
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    n = TelegramNotifier.from_env()
    assert n.enabled is False
    # Must be a silent no-op — no exception, no network call
    n.notify("test")
    n.trade_open(datetime.now(timezone.utc), "PAXG-USDT", 1.0, 2000.0, 1960.0, 2080.0)
    n.error("oops")
