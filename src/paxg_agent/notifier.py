"""Telegram notifier — no-op when env vars are not set.

Configure by setting:
    TELEGRAM_BOT_TOKEN=...   (BotFather)
    TELEGRAM_CHAT_ID=...     (your chat or group id)

Get TELEGRAM_CHAT_ID by sending any message to your bot, then:
    curl https://api.telegram.org/bot<TOKEN>/getUpdates
"""
from __future__ import annotations

import os
from dataclasses import dataclass

import httpx


@dataclass
class TelegramNotifier:
    bot_token: str | None = None
    chat_id: str | None = None
    timeout: float = 10.0
    enabled: bool = False

    @classmethod
    def from_env(cls) -> "TelegramNotifier":
        token = os.getenv("TELEGRAM_BOT_TOKEN") or None
        chat = os.getenv("TELEGRAM_CHAT_ID") or None
        return cls(bot_token=token, chat_id=chat, enabled=bool(token and chat))

    def notify(self, text: str) -> None:
        """Best-effort send. Never raises — Telegram outage must not kill the bot."""
        if not self.enabled:
            return
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        try:
            with httpx.Client(timeout=self.timeout) as c:
                c.post(
                    url,
                    json={
                        "chat_id": self.chat_id,
                        "text": text,
                        "parse_mode": "Markdown",
                        "disable_web_page_preview": True,
                    },
                )
        except Exception:
            # Swallow — don't let comms failures crash the trading loop.
            pass

    # Convenience formatters

    def trade_open(self, ts, symbol: str, qty: float, entry: float, stop: float, tp: float) -> None:
        self.notify(
            f"🟢 *OPEN LONG* `{symbol}`\n"
            f"`{ts}`\n"
            f"qty: `{qty:.4f}`  entry: `{entry:.2f}`\n"
            f"stop: `{stop:.2f}`  tp: `{tp:.2f}`"
        )

    def trade_close(self, ts, symbol: str, exit_price: float, pnl: float, reason: str) -> None:
        emoji = "✅" if pnl > 0 else "❌"
        self.notify(
            f"{emoji} *CLOSE* `{symbol}`\n"
            f"`{ts}`\n"
            f"exit: `{exit_price:.2f}`  pnl: `{pnl:+.2f}` USDT\n"
            f"reason: _{reason}_"
        )

    def llm_block(self, ts, decision: str, rationale: str, news: str) -> None:
        # Only notify on non-APPROVE so we're not spammed
        if decision == "APPROVE":
            return
        self.notify(
            f"⚠️ *LLM {decision}* signal\n"
            f"`{ts}`\n"
            f"news: _{news[:200]}_\n"
            f"why: {rationale[:300]}"
        )

    def info(self, text: str) -> None:
        self.notify(f"ℹ️ {text}")

    def error(self, text: str) -> None:
        self.notify(f"🛑 *ERROR* {text}")
