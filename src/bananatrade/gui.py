"""BananaTrade desktop control panel (Tkinter, no extra dependencies).

Start: double-click ``BananaTrade.bat`` in the project folder, or
    .venv\\Scripts\\python -m bananatrade.gui

The panel only calls the same code path as ``bananatrade run <SYMBOL> --broker mt5``.
All existing safety stays in force: demo-only account guard, dry-run by default,
3% daily-loss kill switch, one position per symbol, mandatory SL/TP.
Sending orders requires ticking a box AND confirming a dialog, and only ever on a demo account.
"""

from __future__ import annotations

import csv
import os
import queue
import threading
import time
from collections.abc import Callable, Mapping
from datetime import datetime
from pathlib import Path
from typing import Any

from .config import Config

ROOT = Path(__file__).resolve().parents[2]
DECISIONS = ROOT / "trades" / "decisions.csv"
TIMEFRAMES: dict[str, tuple[int, int]] = {"M15 (15 phút)": (15, 900), "H1 (1 giờ)": (16385, 3600)}
SYMBOLS = ("EURUSD", "XAUUSD", "GBPUSD", "USDJPY", "BTCUSD")


# ---------------------------------------------------------------- pure logic (unit-tested)

def build_config(timeframe_label: str, risk_pct_text: str, volume_max_text: str, send_orders: bool) -> Config:
    """Validate the form and return a Config. Raises ValueError with a Vietnamese message."""
    if timeframe_label not in TIMEFRAMES:
        raise ValueError("Khung giờ không hợp lệ")
    try:
        risk_pct = float(risk_pct_text.replace(",", ".")) / 100.0
    except ValueError as exc:
        raise ValueError("Rủi ro mỗi lệnh phải là số, ví dụ 1") from exc
    if not 0 < risk_pct <= 0.05:
        raise ValueError("Rủi ro mỗi lệnh phải trong khoảng 0–5%")
    volume_max: float | None = None
    if volume_max_text.strip():
        try:
            volume_max = float(volume_max_text.replace(",", "."))
        except ValueError as exc:
            raise ValueError("Lot tối đa phải là số, ví dụ 0.1") from exc
        if volume_max <= 0:
            raise ValueError("Lot tối đa phải lớn hơn 0")
    return Config(
        risk_pct=risk_pct,
        mt5_timeframe=TIMEFRAMES[timeframe_label][0],
        mt5_volume_max=volume_max,
        mt5_execution_enabled=bool(send_orders),
    )


_REASON_VI = (
    ("below threshold", "Tín hiệu chưa đủ mạnh"),
    ("ensemble signal is NEUTRAL", "Chưa có tín hiệu mua/bán"),
    ("VOLATILE regime", "Thị trường đang biến động mạnh — đứng ngoài"),
    ("exceeds max_spread", "Spread quá cao"),
    ("risk budget below symbol minimum lot", "Vốn quá nhỏ: lot nhỏ nhất vượt mức rủi ro cho phép"),
    ("risk check failed", "Bị chặn bởi kiểm tra rủi ro"),
    ("entry filter", "Bị bộ lọc ONNX chặn"),
    ("execution model rejected", "Mô hình vào lệnh từ chối"),
    ("missing valid entry price", "Không lấy được giá vào lệnh"),
    ("signal calculation failed", "Lỗi tính tín hiệu"),
    ("risk checks passed", "Đã qua kiểm tra rủi ro"),
    ("confidence gate passed", "Tín hiệu đủ mạnh"),
)


def translate_reason(reason: str) -> str:
    for needle, text in _REASON_VI:
        if needle in reason:
            return f"{text}  ({reason})"
    return reason


def describe_result(result: Mapping[str, Any]) -> dict[str, str]:
    """Turn the run result into display strings."""
    account = result.get("account", {}) or {}
    decision = result.get("decision", {}) or {}
    execution = result.get("execution", {}) or {}
    side = str(decision.get("side", "NONE"))
    headline = {"BUY": "MUA", "SELL": "BÁN"}.get(side, "KHÔNG VÀO LỆNH")
    if side != "NONE":
        headline += f"  {decision.get('volume')} lot @ {decision.get('entry')}  SL {decision.get('sl')}  TP {decision.get('tp')}"
    if execution.get("sent"):
        exec_text = f"ĐÃ GỬI LỆNH (demo), mã lệnh {execution.get('order_id')}"
    elif execution.get("dry_run"):
        exec_text = "Chế độ thử (dry-run): không gửi lệnh — " + str(execution.get("message", ""))
    else:
        exec_text = str(execution.get("message", ""))
    pnl = float(account.get("daily_pnl", 0.0) or 0.0)
    return {
        "symbol": str(result.get("symbol", "")),
        "equity": f"{float(account.get('equity', 0.0) or 0.0):,.2f}",
        "daily_pnl": f"{pnl:+,.2f}",
        "open_count": str(account.get("open_count", 0)),
        "headline": headline,
        "side": side,
        "confidence": f"{float(decision.get('confidence', 0.0) or 0.0):.2f}",
        "reasons": "\n".join(translate_reason(str(r)) for r in decision.get("reasons", []) or []),
        "execution": exec_text,
    }


def friendly_error(exc: BaseException) -> str:
    text = str(exc)
    name = type(exc).__name__
    if name == "MT5Unavailable":
        return 'Chưa cài gói MetaTrader5. Chạy: .venv\\Scripts\\python -m pip install -e ".[mt5]"'
    if name == "LiveAccountRefused":
        return "Tài khoản đang đăng nhập KHÔNG phải demo — bot từ chối giao dịch. Hãy đăng nhập tài khoản demo trong MT5."
    if name == "MT5ConnectionError" or "IPC" in text or "Authorization" in text:
        return f"Không kết nối được MT5. Hãy mở MetaTrader 5 và đăng nhập tài khoản demo. ({text})"
    if isinstance(exc, KeyError) and "symbol not found" in text:
        return f"Không tìm thấy mã giao dịch. Gõ đúng tên như trong Market Watch. ({text})"
    if name == "MT5OrderRefused":
        if "kill switch" in text:
            return f"Kill-switch: lỗ trong ngày đã chạm 3% — dừng vào lệnh mới. ({text})"
        return f"Lệnh bị chặn bởi chốt an toàn: {text}"
    return f"{name}: {text}"


def read_decisions(path: Path = DECISIONS, limit: int = 200) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    return rows[-limit:][::-1]


# ---------------------------------------------------------------- worker

def _run_once(symbol: str, config: Config) -> dict[str, Any]:
    from .cli import _run_mt5_once  # imported lazily so the window opens even if MT5 is missing

    return _run_mt5_once(config, symbol)


def _probe(symbol: str) -> dict[str, Any]:
    from .brokers.mt5_client import MT5Client
    from .brokers.mt5_executor import MT5Executor

    client = MT5Client(cache_dir=ROOT / "data" / "history")
    client.connect()
    try:
        status = MT5Executor(Config(), client.mt5).status()
        resolved = client.resolve_symbol(symbol)
        spec = client.symbol_spec(resolved)
        state = client.account_state(resolved)
        account = client.mt5.account_info()
        return {
            "demo": status.get("account_mode") == "DEMO",
            "server": getattr(account, "server", ""),
            "currency": getattr(account, "currency", ""),
            "leverage": getattr(account, "leverage", ""),
            "symbol": resolved,
            "spread": spec.spread,
            "volume_min": spec.volume_min,
            **state,
        }
    finally:
        client.shutdown()


# ---------------------------------------------------------------- UI

def main() -> None:  # pragma: no cover - interactive
    import tkinter as tk
    from tkinter import messagebox, ttk

    root = tk.Tk()
    root.title("BananaTrade — Bảng điều khiển MT5")
    root.geometry("900x680")
    root.minsize(780, 560)
    results: queue.Queue[tuple[str, Any]] = queue.Queue()
    state = {"busy": False, "auto": False, "next": 0.0}

    style = ttk.Style()
    style.configure("Big.TLabel", font=("Segoe UI", 15, "bold"))
    style.configure("Mode.TLabel", font=("Segoe UI", 11, "bold"))

    # ---- settings
    top = ttk.LabelFrame(root, text=" Cài đặt ", padding=10)
    top.pack(fill="x", padx=10, pady=(10, 5))
    symbol_var = tk.StringVar(value="EURUSD")
    tf_var = tk.StringVar(value=next(iter(TIMEFRAMES)))
    risk_var = tk.StringVar(value="1")
    vmax_var = tk.StringVar(value="")
    send_var = tk.BooleanVar(value=False)
    ttk.Label(top, text="Mã giao dịch").grid(row=0, column=0, sticky="w")
    ttk.Combobox(top, textvariable=symbol_var, values=SYMBOLS, width=12).grid(row=0, column=1, padx=6)
    ttk.Label(top, text="Khung giờ").grid(row=0, column=2, sticky="w")
    ttk.Combobox(top, textvariable=tf_var, values=list(TIMEFRAMES), state="readonly", width=14).grid(row=0, column=3, padx=6)
    ttk.Label(top, text="Rủi ro mỗi lệnh (%)").grid(row=0, column=4, sticky="w")
    ttk.Entry(top, textvariable=risk_var, width=6).grid(row=0, column=5, padx=6)
    ttk.Label(top, text="Lot tối đa (trống = lot nhỏ nhất)").grid(row=1, column=0, columnspan=2, sticky="w", pady=(8, 0))
    ttk.Entry(top, textvariable=vmax_var, width=8).grid(row=1, column=2, sticky="w", pady=(8, 0))
    mode_label = ttk.Label(top, style="Mode.TLabel")
    mode_label.grid(row=1, column=4, columnspan=2, sticky="e", pady=(8, 0))

    def refresh_mode() -> None:
        if send_var.get():
            mode_label.configure(text="● GỬI LỆNH THẬT (chỉ demo)", foreground="#c62828")
        else:
            mode_label.configure(text="● CHẾ ĐỘ THỬ — không gửi lệnh", foreground="#2e7d32")

    def toggle_send() -> None:
        if send_var.get():
            ok = messagebox.askyesno(
                "Xác nhận gửi lệnh",
                "Bot sẽ GỬI LỆNH lên MT5 khi có tín hiệu.\n\n"
                "• Chỉ hoạt động trên tài khoản DEMO (tài khoản thật sẽ bị từ chối).\n"
                "• Kill-switch dừng khi lỗ 3% trong ngày.\n\n"
                "Chiến lược hiện chưa được chứng minh có lãi. Tiếp tục?",
                icon="warning",
            )
            if not ok:
                send_var.set(False)
        refresh_mode()

    ttk.Checkbutton(top, text="Gửi lệnh thật (demo)", variable=send_var, command=toggle_send).grid(row=1, column=3, sticky="w", pady=(8, 0))
    refresh_mode()

    # ---- buttons
    bar = ttk.Frame(root, padding=(10, 0))
    bar.pack(fill="x")
    status_var = tk.StringVar(value="Sẵn sàng. Mở MT5 và đăng nhập tài khoản demo, rồi bấm “Kiểm tra kết nối”.")

    def log(msg: str) -> None:
        log_box.configure(state="normal")
        log_box.insert("end", f"[{datetime.now().astimezone():%H:%M:%S}] {msg}\n")
        log_box.see("end")
        log_box.configure(state="disabled")

    def start_job(kind: str, fn: Callable[[], Any]) -> None:
        if state["busy"]:
            return
        state["busy"] = True
        status_var.set("Đang chạy…")

        def work() -> None:
            try:
                results.put((kind, fn()))
            except Exception as exc:  # noqa: BLE001 - shown to the user
                results.put(("error", exc))

        threading.Thread(target=work, daemon=True).start()

    def on_probe() -> None:
        start_job("probe", lambda: _probe(symbol_var.get().strip()))

    def on_run() -> None:
        try:
            cfg = build_config(tf_var.get(), risk_var.get(), vmax_var.get(), send_var.get())
        except ValueError as exc:
            messagebox.showerror("Cài đặt sai", str(exc))
            return
        sym = symbol_var.get().strip()
        start_job("run", lambda: _run_once(sym, cfg))

    def on_auto() -> None:
        state["auto"] = not state["auto"]
        auto_btn.configure(text="■ Dừng tự động" if state["auto"] else "▶ Chạy tự động")
        if state["auto"]:
            state["next"] = 0.0
            log("Bật chạy tự động: bot kiểm tra mỗi khi có nến mới.")
        else:
            log("Đã dừng chạy tự động.")

    ttk.Button(bar, text="🔌 Kiểm tra kết nối", command=on_probe).pack(side="left", padx=(0, 6))
    ttk.Button(bar, text="▶ Chạy 1 lần", command=on_run).pack(side="left", padx=6)
    auto_btn = ttk.Button(bar, text="▶ Chạy tự động", command=on_auto)
    auto_btn.pack(side="left", padx=6)
    ttk.Button(bar, text="📄 Mở nhật ký (Excel)", command=lambda: os.startfile(DECISIONS) if DECISIONS.exists() else messagebox.showinfo("Nhật ký", "Chưa có quyết định nào.")).pack(side="right")  # type: ignore[attr-defined]

    # ---- account + decision
    mid = ttk.Frame(root, padding=10)
    mid.pack(fill="x")
    acc = ttk.LabelFrame(mid, text=" Tài khoản ", padding=10)
    acc.pack(side="left", fill="y")
    acc_vars = {k: tk.StringVar(value="—") for k in ("conn", "symbol", "equity", "daily_pnl", "open_count")}
    for i, (key, label) in enumerate((("conn", "Kết nối"), ("symbol", "Mã"), ("equity", "Vốn (equity)"),
                                      ("daily_pnl", "Lời/lỗ hôm nay"), ("open_count", "Lệnh đang mở"))):
        ttk.Label(acc, text=label + ":").grid(row=i, column=0, sticky="w")
        ttk.Label(acc, textvariable=acc_vars[key], font=("Segoe UI", 10, "bold")).grid(row=i, column=1, sticky="w", padx=8)
    dec = ttk.LabelFrame(mid, text=" Quyết định gần nhất ", padding=10)
    dec.pack(side="left", fill="both", expand=True, padx=(10, 0))
    headline = ttk.Label(dec, text="—", style="Big.TLabel")
    headline.pack(anchor="w")
    detail_var = tk.StringVar(value="")
    ttk.Label(dec, textvariable=detail_var, wraplength=520, justify="left").pack(anchor="w", pady=(6, 0))

    # ---- history + log
    nb = ttk.Notebook(root)
    nb.pack(fill="both", expand=True, padx=10, pady=(0, 6))
    hist_frame = ttk.Frame(nb)
    cols = ("timestamp", "symbol", "side", "confidence", "volume", "reasons")
    hist = ttk.Treeview(hist_frame, columns=cols, show="headings", height=8)
    for c, w in zip(cols, (170, 80, 60, 80, 60, 400), strict=True):
        hist.heading(c, text={"timestamp": "Thời gian (UTC)", "symbol": "Mã", "side": "Lệnh", "confidence": "Độ tin cậy", "volume": "Lot", "reasons": "Lý do"}[c])
        hist.column(c, width=w, anchor="w")
    hist.pack(fill="both", expand=True)
    nb.add(hist_frame, text="Lịch sử quyết định")
    log_frame = ttk.Frame(nb)
    log_box = tk.Text(log_frame, height=8, state="disabled", wrap="word")
    log_box.pack(fill="both", expand=True)
    nb.add(log_frame, text="Nhật ký hoạt động")

    def refresh_history() -> None:
        hist.delete(*hist.get_children())
        for row in read_decisions():
            hist.insert("", "end", values=[row.get(c, "") for c in cols])

    ttk.Label(root, textvariable=status_var, relief="sunken", anchor="w", padding=4).pack(fill="x", side="bottom")
    ttk.Label(root, text="Không phải lời khuyên đầu tư. Chiến lược hiện chưa được chứng minh có lãi — hãy dùng tài khoản demo.",
              foreground="#777").pack(side="bottom", pady=(0, 2))

    def poll() -> None:
        try:
            while True:
                kind, payload = results.get_nowait()
                state["busy"] = False
                if kind == "error":
                    msg = friendly_error(payload)
                    status_var.set("Lỗi — xem nhật ký hoạt động")
                    acc_vars["conn"].set("Lỗi")
                    log("LỖI: " + msg)
                    if not state["auto"]:
                        messagebox.showerror("BananaTrade", msg)
                elif kind == "probe":
                    acc_vars["conn"].set(("DEMO ✔ " if payload["demo"] else "KHÔNG PHẢI DEMO ✖ ") + str(payload["server"]))
                    acc_vars["symbol"].set(f"{payload['symbol']} (spread {payload['spread']:.5g}, lot min {payload['volume_min']})")
                    acc_vars["equity"].set(f"{payload['equity']:,.2f} {payload['currency']}")
                    acc_vars["daily_pnl"].set(f"{payload['daily_pnl']:+,.2f}")
                    acc_vars["open_count"].set(str(payload["open_count"]))
                    status_var.set("Kết nối MT5 OK." if payload["demo"] else "Cảnh báo: tài khoản không phải demo — bot sẽ từ chối giao dịch.")
                    log(f"Kết nối OK: {payload['server']}, đòn bẩy 1:{payload['leverage']}, mã {payload['symbol']}")
                else:
                    d = describe_result(payload)
                    acc_vars["conn"].set("OK")
                    acc_vars["symbol"].set(d["symbol"])
                    acc_vars["equity"].set(d["equity"])
                    acc_vars["daily_pnl"].set(d["daily_pnl"])
                    acc_vars["open_count"].set(d["open_count"])
                    headline.configure(text=d["headline"], foreground={"BUY": "#2e7d32", "SELL": "#c62828"}.get(d["side"], "#555"))
                    detail_var.set(f"Độ tin cậy: {d['confidence']}\n{d['reasons']}\n\n{d['execution']}")
                    status_var.set(f"Xong lúc {datetime.now().astimezone():%H:%M:%S}")
                    log(f"{d['symbol']}: {d['headline']} — {d['execution']}")
                    refresh_history()
        except queue.Empty:
            pass
        if state["auto"] and not state["busy"] and time.time() >= state["next"]:
            interval = TIMEFRAMES.get(tf_var.get(), (15, 900))[1]
            # align to the next bar close + 5s so each run sees a freshly closed candle
            state["next"] = (time.time() // interval + 1) * interval + 5
            on_run()
            status_var.set(f"Tự động — lần chạy tiếp lúc {datetime.fromtimestamp(state["next"]).astimezone():%H:%M:%S}")
        root.after(500, poll)

    refresh_history()
    poll()
    root.mainloop()


if __name__ == "__main__":  # pragma: no cover
    main()
