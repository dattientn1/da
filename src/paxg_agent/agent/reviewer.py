"""LLM trade reviewer.

Each rule-based signal is sent to Claude with three sources of context the bot
itself can't reason about:
  1. Recent OHLCV + indicator snapshot (passed inline).
  2. Live market news / geopolitics — via Anthropic-hosted `web_search` server tool.
  3. CFTC COT positioning hints (gold futures long/short of large speculators) —
     same web_search tool; the model is instructed to look it up.

Output is a JSON object: {decision, rationale, confidence, news_summary}.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from anthropic import Anthropic

from ..config import LLMConfig

SYSTEM_PROMPT = """You are a risk-control reviewer for a PAXG/USDT spot trading bot.
PAXG is tokenised gold (1 token = 1 troy ounce of physical gold), so the price
tracks the spot gold market closely.

The bot generates rule-based long entry signals from technical indicators
(EMA20/50 crossover + RSI14 mean reversion + ATR14 stops). Spot only — no shorts,
no leverage.

Your job is to APPROVE, REDUCE_SIZE, or VETO the proposed trade. You should:

1. Read the technical context provided in the user message.
2. ALWAYS use the `web_search` tool BEFORE deciding to check:
   - Geopolitical news in the last 24-72h that affects gold (wars, sanctions,
     central-bank moves, elections, energy crises, USD strength).
   - Macro events imminent or just released: FOMC decisions, CPI/PCE prints,
     NFP, Fed speakers, ECB/BOJ moves.
   - CFTC Commitments of Traders (COT) — large speculators net long/short on
     gold futures (GC). Extreme positioning often precedes reversals.
   - Any "big players betting heavily on long/short" before scheduled events.
3. Synthesize: does the technical setup line up with the macro/news flow, or
   does it conflict?

Decision rules:
  - APPROVE: technical setup + news/positioning agree, or news is neutral.
  - REDUCE_SIZE: setup is okay but there is event risk inside the next 24h
    (e.g. FOMC tomorrow) or positioning is stretched.
  - VETO: news clearly contradicts the trade (e.g. opening LONG right before
    an expected hawkish Fed) or extreme crowd positioning the wrong way.

Respond with EXACTLY one JSON object, no prose around it:
{
  "decision": "APPROVE" | "REDUCE_SIZE" | "VETO",
  "size_multiplier": float between 0.0 and 1.0,
  "confidence": float between 0.0 and 1.0,
  "rationale": "1-3 sentences citing the specific news/positioning that drove the call",
  "news_summary": "1-2 sentence headline of what's moving gold right now"
}
size_multiplier is 1.0 for APPROVE, 0.0 for VETO, 0.25-0.75 for REDUCE_SIZE.
"""


@dataclass
class ReviewDecision:
    decision: str  # APPROVE | REDUCE_SIZE | VETO
    size_multiplier: float
    confidence: float
    rationale: str
    news_summary: str

    @classmethod
    def approved_default(cls) -> "ReviewDecision":
        return cls("APPROVE", 1.0, 1.0, "LLM review disabled", "")

    @classmethod
    def vetoed_error(cls, msg: str) -> "ReviewDecision":
        return cls("VETO", 0.0, 0.0, f"LLM error: {msg}", "")


class LLMReviewer:
    def __init__(self, cfg: LLMConfig, api_key: str | None):
        self.cfg = cfg
        self._client: Anthropic | None = (
            Anthropic(api_key=api_key) if api_key else None
        )

    @property
    def available(self) -> bool:
        return self._client is not None

    def review(
        self,
        signal_indicators: dict[str, float],
        proposed_entry: float,
        proposed_stop: float,
        proposed_take_profit: float,
        proposed_qty: float,
        portfolio_equity: float,
        recent_candles: list[dict[str, Any]],
    ) -> ReviewDecision:
        if self._client is None:
            return ReviewDecision.approved_default()

        now = datetime.now(timezone.utc).isoformat()
        ctx = {
            "timestamp_utc": now,
            "symbol": "PAXG-USDT",
            "proposed_trade": {
                "side": "LONG",
                "entry": proposed_entry,
                "stop_loss": proposed_stop,
                "take_profit": proposed_take_profit,
                "quantity": proposed_qty,
                "risk_dollars": (proposed_entry - proposed_stop) * proposed_qty,
                "portfolio_equity_usdt": portfolio_equity,
            },
            "indicators": signal_indicators,
            "recent_candles_1h": recent_candles[-12:],
        }

        user_msg = (
            "Review this proposed trade. Use web_search to look up gold news,"
            " imminent macro events, and COT positioning before deciding.\n\n"
            f"Context:\n```json\n{json.dumps(ctx, indent=2, default=str)}\n```"
        )

        try:
            response = self._client.messages.create(
                model=self.cfg.model,
                max_tokens=self.cfg.max_tokens,
                system=[
                    {
                        "type": "text",
                        "text": SYSTEM_PROMPT,
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
                tools=[{"type": "web_search_20260209", "name": "web_search"}],
                messages=[{"role": "user", "content": user_msg}],
            )
        except Exception as e:  # noqa: BLE001 — surface at call site
            return ReviewDecision.vetoed_error(str(e))

        text = "".join(
            block.text for block in response.content if getattr(block, "type", None) == "text"
        ).strip()

        return self._parse_decision(text)

    @staticmethod
    def _parse_decision(text: str) -> ReviewDecision:
        # Tolerate code fences / surrounding prose by extracting first {...}
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1:
            return ReviewDecision.vetoed_error(f"no JSON in reply: {text[:120]}")
        try:
            data = json.loads(text[start : end + 1])
        except json.JSONDecodeError as e:
            return ReviewDecision.vetoed_error(f"JSON parse: {e}")

        decision = str(data.get("decision", "VETO")).upper()
        if decision not in {"APPROVE", "REDUCE_SIZE", "VETO"}:
            decision = "VETO"
        size_mult = float(data.get("size_multiplier", 0.0 if decision == "VETO" else 1.0))
        size_mult = max(0.0, min(1.0, size_mult))
        return ReviewDecision(
            decision=decision,
            size_multiplier=size_mult,
            confidence=float(data.get("confidence", 0.5)),
            rationale=str(data.get("rationale", "")),
            news_summary=str(data.get("news_summary", "")),
        )
