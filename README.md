# PAXG Trading Agent

Agentic sandbox để giao dịch spot **PAXG/USDT** trên BingX (PAXG = 1 token gắn 1 oz vàng vật chất).
Mục tiêu là test chiến lược trong 2 tuần — backtest lịch sử và/hoặc paper trading live — **không gửi lệnh thật**.

## Kiến trúc

- **Bot rule-based** (`strategy/hybrid.py`): EMA20/50 crossover + RSI(14) cross-up từ oversold + ATR(14) cho stop/take-profit.
- **LLM reviewer** (`agent/reviewer.py`): mỗi tín hiệu được Claude review qua tool `web_search` (Anthropic-hosted) để check:
  - Tin địa chính trị 24-72h gần nhất ảnh hưởng giá vàng (chiến tranh, sanctions, Fed, USD).
  - Macro events sắp tới: FOMC, CPI/PCE, NFP, ECB/BOJ.
  - **CFTC COT** — large speculators long/short ròng trên gold futures (GC). Positioning cực đoan thường đi trước đảo chiều.
- **Simulated broker** (`execution/`): áp fee taker 0.1% + slippage 0.05% mỗi fill, không bao giờ kết nối API ký lệnh.
- **Sandbox 2 mode chung 1 broker**:
  - `paxg backtest` — replay 2 tuần kline lịch sử, ra báo cáo trong vài giây/phút.
  - `paxg paper` — poll BingX 60s/lần, evaluate trên candle vừa đóng, log từng quyết định.

## Cài đặt

```bash
pip install -e .          # hoặc: pip install -e .[dev] để cài pytest
cp .env.example .env      # điền ANTHROPIC_API_KEY
```

## Chạy

```bash
# 1. Backtest 2 tuần, deterministic (không gọi LLM)
paxg backtest --days 14

# 2. Backtest có LLM review — tốn token, mỗi signal 1 round trip + web_search
paxg backtest --days 14 --llm-review

# 3. Paper trading 14 ngày, có LLM review (mặc định bật)
paxg paper --duration 14d

# 4. Paper trading dry-run 30 phút để test loop
paxg paper --duration 30m
```

Sau khi chạy, mở `results/`:
- `summary.json` — return, Sharpe, max drawdown, win rate, fees.
- `trades.csv` — log từng lệnh kèm `llm_decision` + `llm_rationale`.
- `equity.png` — đường vốn theo thời gian.

## Tests

```bash
pip install -e .[dev]
pytest -v
```

Cover indicators, fill model (fee + slippage), position sizing, broker round-trip PnL.

## Cấu hình

Tất cả tham số chiến lược, vốn, risk, fee nằm trong `config.yaml`. Ví dụ:

```yaml
portfolio:
  starting_capital_usdt: 10000.0
  risk_per_trade: 0.01
strategy:
  ema_fast: 20
  ema_slow: 50
  rsi_oversold: 30
  atr_stop_mult: 2.0
  atr_take_profit_mult: 3.0
llm:
  model: claude-sonnet-4-6
  enabled_in_backtest: false
  enabled_in_paper: true
```

## Ngoài phạm vi v1

- Đặt lệnh thật trên BingX (cần wire signed endpoints + key — code đã có ô `BINGX_API_KEY`).
- Multi-symbol, futures, leverage, short.
- COT data tự động qua API (hiện tại Claude tự dùng `web_search` để tra).
- Web UI — chỉ có CLI + file output.
