# Dashboard API

## `GET /api/snapshot`
Nhận `symbol` và `timeframe` qua query string; trả snapshot đã đóng gồm giá cuối, chỉ báo, thời điểm quan sát và cờ stale. Ví dụ: `GET /api/snapshot?symbol=BTC%2FUSDT&timeframe=1h`.

```json
{
  "symbol": "BTC/USDT",
  "timeframe": "1h",
  "last_price": 103.0,
  "indicators": {"rsi": 52.1},
  "timestamp": "2025-01-01T03:00:00Z",
  "as_of": "2025-01-01T03:00:00Z",
  "stale": false
}
```

## `GET /api/paper/state`
Không có tham số; trả tài khoản paper hiện tại với cash, equity, vị thế và fills đã ghi nhận.

```json
{
  "cash": 9899.96,
  "equity": 10000.0,
  "positions": {},
  "fills": []
}
```

## `POST /api/paper/order`
Body JSON gồm `symbol`, `side` (`buy` hoặc `sell`), `quantity` và `price`; endpoint chỉ tạo paper fill sau khi risk gate chấp thuận.

```json
{
  "order": {
    "order_id": "paper-1",
    "symbol": "BTC/USDT",
    "side": "buy",
    "quantity": 0.01,
    "price": 100.0,
    "fee": 0.0004
  },
  "paper": true,
  "risk_gated": true
}
```

## `GET /api/analysis/run`
Không có tham số; chạy pipeline phân tích offline của symbol mặc định `BTC/USDT` và trả báo cáo pipeline. Lỗi đã biết trả JSON với HTTP 503.

```json
{
  "reports": [
    {"agent": "technical_analyst", "bias": "neutral", "confidence": 0.6}
  ]
}
```

## `GET /api/risk/state`
Không có tham số; trả trạng thái risk đã chuẩn hóa gồm kill switch, PnL ngày theo phần trăm, exposure, số giao dịch, cooldown và lý do reject gần nhất.

```json
{
  "kill_switch": false,
  "daily_pnl_pct": 0.5,
  "exposure": 750.0,
  "trades_today": 1,
  "cooldown_active": true,
  "last_rejection_reasons": ["loss cooldown active"]
}
```

## `POST /api/risk/check`
Body JSON gồm `equity`, `entry`, `stop_loss`, `take_profit` và `size`; trả quyết định risk, lý do và size đã điều chỉnh, không đặt lệnh.

```json
{
  "approved": true,
  "reasons": [],
  "adjusted_size": 5.0
}
```

## `GET /api/quota`
Không có tham số; trả quota theo từng tier, với usage và limit cho cửa sổ 5 giờ và 7 ngày cùng cờ đánh dấu.

```json
{
  "tiers": {
    "tier4_cio": {
      "windows": {
        "5h": {"used": 1, "limit": 10},
        "7d": {"used": 1, "limit": 30}
      },
      "flagged": true,
      "highlighted": true
    }
  }
}
```

## `POST /api/order/prefill`
Body JSON gồm `symbol`, `side` (`LONG`, `SHORT`, `buy` hoặc `sell`) và snapshot có timeframe `1h`, giá cuối cùng cùng ATR; trả entry, stop, target và tỷ lệ reward/risk để điền form paper order.

```json
{
  "symbol": "BTC/USDT",
  "side": "LONG",
  "entry": 100.0,
  "stop": 98.5,
  "target": 104.725,
  "reward": 4.725,
  "risk": 1.5,
  "reward_risk": 3.15
}
```

## Error responses
Các endpoint trả lỗi JSON dạng `{"error":"..."}`; HTTP 400 dùng cho input không hợp lệ, 404 cho route hoặc dữ liệu không tồn tại, 503 cho lỗi phân tích đã biết và 500 cho lỗi không mong đợi sau khi server ghi traceback.
