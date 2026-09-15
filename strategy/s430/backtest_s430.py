# -*- coding: utf-8 -*-
"""Standalone backtest runner สำหรับ S430 Triple EMA Stochastic RSI Strategy
โดยเฉพาะ (ไม่ใช้ sim_strategy_backtest.py ร่วมกับ strategy อื่น) — เหมือน
backtest_s422.py ตรงที่ strategy430.compute_series() คำนวณ EMA/StochRSI/ATR
ทั้งช่วงราคาด้วย numpy ในครั้งเดียว (ไม่มี state สะสมข้ามบาร์แบบ zigzag ของ
S420) ลูปหลักแค่เดินผ่านค่าที่คำนวณไว้แล้วเพื่อจำลอง entry/exit

รองรับ TF กว้างกว่า strategy อื่น (M1/M15/M30/H1/H4/H12/D1 — ไม่มี M5 ตามที่
ผู้ใช้กำหนด) เพราะกลยุทธ์นี้ใช้ EMA(350)/RSI(160) ยาวมาก เหมาะกับ TF สูงกว่า
M1 เป็นพิเศษ

Usage:
    python backtest_s430.py --start 2026-06-01 --end 2026-08-11 --tf H1
    python backtest_s430.py --days 60 --tf H1
    python backtest_s430.py --days 60 --tf all
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import re
import sys
import time as _time
from datetime import datetime, timedelta, timezone

import MetaTrader5 as mt5

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (_ROOT, _HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import config
from strategy430 import DEFAULT_CFG, compute_series

BKK = timezone(timedelta(hours=7))
TF_MAP = {"M1": mt5.TIMEFRAME_M1, "M15": mt5.TIMEFRAME_M15, "M30": mt5.TIMEFRAME_M30,
          "H1": mt5.TIMEFRAME_H1, "H4": mt5.TIMEFRAME_H4, "H12": mt5.TIMEFRAME_H12,
          "D1": mt5.TIMEFRAME_D1}
TF_SECONDS = {"M1": 60, "M15": 900, "M30": 1800, "H1": 3600, "H4": 14400, "H12": 43200, "D1": 86400}

# จำนวนแท่งย้อนหลังพอสำหรับ warm-up ของ EMA_LEN_SLOW (default 350) + RSI_LEN
# (160) + STOCH_LEN (90) + SMOOTH_K/D (14+4) — เผื่อเยอะกว่า default หลายเท่า
# เพราะ cfg อาจปรับความยาวให้มากขึ้นได้ผ่าน --cfg-json
LOOKBACK_BARS = 3000
MIN_LOOKBACK_BARS = 700
DEFAULT_DAYS = 60


def parse_bkk(value):
    parsed = datetime.fromisoformat(value) if value else datetime.now(BKK)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=BKK)
    return parsed.astimezone(BKK)


def fmt_bkk(dt):
    return dt.astimezone(BKK).strftime("%Y-%m-%d %H:%M:%S")


def _csv_path_for_tf(csv_path, tf_name):
    if "." in csv_path:
        stem, ext = csv_path.rsplit(".", 1)
        return f"{stem}_{tf_name}.{ext}"
    return f"{csv_path}_{tf_name}"


# --- MT5 Timezone Rule ของโปรเจกต์นี้ (เดียวกับ backtest_s420.py) ---
def bar_time_to_bkk(raw_time):
    return datetime.fromtimestamp(int(raw_time), tz=BKK) - timedelta(hours=1)


def bkk_to_query(dt_bkk):
    return dt_bkk + timedelta(hours=1)


def prepare_rates(tf_name, start_bkk, end_bkk, lookback_bars):
    history_days = math.ceil(lookback_bars * TF_SECONDS[tf_name] / 86400.0) + 7
    fetch_start = bkk_to_query(start_bkk - timedelta(days=history_days))
    fetch_end = bkk_to_query(end_bkk)
    if not config.mt5_initialize(mt5):
        raise RuntimeError("MT5 initialization failed")
    acc = mt5.account_info()
    if acc is not None:
        print(f"MT5 account: login={acc.login} server={acc.server} name={acc.name} "
              f"balance={acc.balance:.2f} {acc.currency}")
    else:
        print("MT5 account: ไม่พบข้อมูลบัญชี (account_info() คืนค่า None)")

    tick = mt5.symbol_info_tick(config.SYMBOL)
    if tick is not None:
        server_bkk = bar_time_to_bkk(tick.time)
        print(f"เวลาปัจจุบันของ broker (raw MT5): {datetime.fromtimestamp(int(tick.time), tz=BKK).strftime('%Y-%m-%d %H:%M:%S')}  "
              f"|  เวลาจริง BKK (แก้ตาม MT5 Timezone Rule): {fmt_bkk(server_bkk)}")
    else:
        print("เวลาปัจจุบันของ broker: ไม่พบ tick ล่าสุด (symbol_info_tick() คืนค่า None)")

    rates = mt5.copy_rates_range(config.SYMBOL, TF_MAP[tf_name], fetch_start, fetch_end)
    mt5.shutdown()
    if rates is None or len(rates) <= MIN_LOOKBACK_BARS:
        raise RuntimeError("not enough MT5 rates")
    bars = list(rates)
    start_query = bkk_to_query(start_bkk)
    start_index = next(
        (index for index, bar in enumerate(bars)
         if int(bar["time"]) >= int(start_query.timestamp())),
        None,
    )
    if start_index is None or start_index < MIN_LOOKBACK_BARS:
        raise RuntimeError(
            f"ประวัติ {tf_name} ก่อน --start มีแค่ {start_index} แท่ง ต่ำกว่าขั้นต่ำที่ต้องการ "
            f"({MIN_LOOKBACK_BARS} แท่ง) — ลองขยับ --start ให้ใกล้ปัจจุบันขึ้น หรือเช็คว่า broker "
            f"มีประวัติ {tf_name} ย้อนหลังพอหรือไม่"
        )
    if start_index < lookback_bars:
        print(f"หมายเหตุ: ประวัติก่อน --start มีแค่ {start_index} แท่ง (น้อยกว่า LOOKBACK_BARS={lookback_bars} "
              f"ที่ตั้งใจไว้) — ใช้เท่าที่มีแทน EMA/RSI warm-up อาจแม่นน้อยลงช่วงต้น backtest")
    return bars, start_index


def backtest(tf_name, spread, lot, start_bkk, end_bkk, cfg=None,
             pct_equity=None, commission_pct=None, starting_balance=1000000.0,
             pyramid_max=10):
    """คำนวณ EMA/StochRSI/ATR series ทั้งช่วงครั้งเดียว (compute_series) แล้ว
    เดินลูปจำลอง entry/exit ด้วย ATR-based SL/TP ตายตัว

    pct_equity/commission_pct = None (default) -> โหมดเดิม: fixed lot + flat
    spread, **1 ไม้ต่อครั้ง ไม่ pyramid** (ตรง convention S420-S429 ของ
    โปรเจกต์ — ดู docstring ของ strategy430.py ข้อ 1)

    ใส่ค่า -> **--tv-mode**: percent_of_equity sizing + percent commission +
    **pyramiding สูงสุด `pyramid_max` ไม้ทิศเดียวกันพร้อมกัน** ตรงกับ Pine
    ต้นฉบับเป๊ะ (default_qty_type=percent_of_equity/25... ที่นี่ default 100
    ตาม input จริงของสคริปต์ผู้ใช้, commission ไม่ได้ตั้งใน Pine เอง default
    0 แต่เปิดให้ตั้งได้ผ่าน --commission-pct เผื่อเทียบ, pyramiding=10)
    สัญญาณทิศตรงข้ามจะ**ปิดไม้เดิมทั้งหมดก่อน** (net-flip แบบเดียวกับโหมด
    netting ปกติของ Pine ที่ไม่ได้เปิด hedging) แล้วค่อยเปิดไม้ใหม่ — เป็นการ
    ลดความซับซ้อนของ Pine's exact partial-netting order execution (ที่ปกติ
    reduce ทีละ entry ไม่ได้ flip เต็มทันที) ยอมรับว่าไม่ exact 100% แต่ใกล้
    เคียงมากพอสำหรับเทียบสเกล/เทรนด์ของผลลัพธ์
    qty ต่อไม้ = equity ปัจจุบัน (นับเฉพาะกำไร/ขาดทุนที่ realize แล้ว ไม่รวม
    floating ของไม้ pyramid ที่ยังเปิดอยู่ — simplification เดียวกับที่ใช้ใน
    --tv-mode ของ backtest_s426.py) * pct_equity/100 / ราคา fill"""
    detector_cfg = dict(DEFAULT_CFG)
    detector_cfg.update(cfg or {})
    lookback_bars = max(LOOKBACK_BARS,
                         int(detector_cfg["EMA_LEN_SLOW"]) + int(detector_cfg["RSI_LEN"]) +
                         int(detector_cfg["STOCH_LEN"]) + int(detector_cfg["SMOOTH_K"]) +
                         int(detector_cfg["SMOOTH_D"]) + 50)
    bars_raw, start_index = prepare_rates(tf_name, start_bkk, end_bkk, lookback_bars)

    series, err = compute_series(bars_raw, detector_cfg)
    if series is None:
        raise RuntimeError(f"compute_series failed: {err}")

    bars_tail = series["bars"]  # ความยาวเท่ากับ bars_raw (compute_series ไม่ตัดหัวเหมือน s422)
    close, k, d, atr = series["close"], series["k"], series["d"], series["atr"]
    ema_slow, ema_mid, ema_fast = series["ema_slow"], series["ema_mid"], series["ema_fast"]

    tv_mode = pct_equity is not None
    contract_multiplier = 100.0 * lot
    allow_buy, allow_sell = bool(detector_cfg["ALLOW_BUY"]), bool(detector_cfg["ALLOW_SELL"])
    sl_mult, tp_mult = float(detector_cfg["ATR_SL_MULT"]), float(detector_cfg["ATR_TP_MULT"])
    long_limit, short_limit = float(detector_cfg["LONG_STOCH_LIMIT"]), float(detector_cfg["SHORT_STOCH_LIMIT"])

    trades = []
    signals = 0
    positions = []  # list เสมอ (tv_mode: อาจมีหลายไม้ทิศเดียวกัน, ปกติ: ยาวสุด 1 ไม้)
    equity = starting_balance

    def close_one(pos, j, exit_price, outcome):
        nonlocal equity
        side = pos["side"]
        if tv_mode:
            qty = pos["qty"]
            gross = side * (exit_price - pos["entry"]) * qty
            commission = (pos["entry"] * qty + exit_price * qty) * (commission_pct / 100.0)
            pnl = gross - commission
        else:
            pnl = (side * (exit_price - pos["entry"]) - spread) * contract_multiplier
        equity += pnl
        trades.append({
            "entry_time": fmt_bkk(pos["entry_time"]),
            "exit_time": fmt_bkk(bar_time_to_bkk(bars_tail[j + 1]["time"])),
            "direction": "BUY" if side > 0 else "SELL",
            "entry": round(pos["entry"], 2),
            "sl": round(pos["sl"], 2), "tp": round(pos["tp"], 2),
            "outcome": outcome, "profit": round(pnl, 2),
            "pattern": pos["pattern"], "reason": pos["reason"],
        })

    def open_one(j, side_wanted, fill_price, entry_ref, atr_j, entry_time):
        nonlocal signals
        signal_name = "BUY" if side_wanted > 0 else "SELL"
        sl = entry_ref - sl_mult * atr_j if side_wanted > 0 else entry_ref + sl_mult * atr_j
        tp = entry_ref + tp_mult * atr_j if side_wanted > 0 else entry_ref - tp_mult * atr_j
        if tv_mode:
            # เพดานทุนรวมต่อทิศทาง = equity * pct_equity/100 (ไม่ใช่คิดเต็ม % ซ้ำทุกไม้) —
            # ยืนยันจากภาพ trade list จริงของผู้ใช้: ไม้ pyramid ที่ยิงซ้อนไม้แรกในบาร์
            # เดียวกัน (เช่น 16 มิ.ย. 15:00 @ 4335.10) ได้ size เหลือแค่เศษทุนที่ยังไม่ได้
            # ใช้ (0.07 lot ~$303) ไม่ใช่เต็ม 100% ซ้ำ (232.28 lot ~$1.01M) — ถ้าไม่มีเพดานนี้
            # backtest จะเปิดไม้ซ้อนเต็มขนาดได้ไม่จำกัด ประเมินความเสี่ยงเกินจริงมาก (เจอ
            # จริง: กลุ่มไม้ 11-12 มิ.ย. ที่ backtest เดิมเปิด SELL เต็มขนาดซ้อน 3 ไม้ ขาดทุน
            # รวม -75,000 กว่า ซึ่งเกินจริงเทียบกับที่ TV แสดง)
            committed = sum(p["qty"] * p["entry"] for p in positions if p["side"] == side_wanted)
            headroom = max(0.0, equity * pct_equity / 100.0 - committed)
            qty = headroom / fill_price
            if qty <= 0.0:
                return  # ไม่มีทุนเหลือให้เปิดไม้ใหม่ในทิศนี้แล้ว
        else:
            qty = None
        signals += 1
        positions.append({
            "side": side_wanted, "entry": fill_price, "sl": sl, "tp": tp, "qty": qty,
            "entry_time": entry_time, "pattern": f"S430 {signal_name} Triple EMA StochRSI",
            "reason": f"k={k[j]:.2f} d={d[j]:.2f} close={entry_ref:.2f} ATR={atr_j:.2f}",
        })

    total_bars = len(bars_tail) - 1 - start_index
    progress_step = max(1, total_bars // 20)
    progress_start = _time.time()

    import numpy as np

    for j in range(start_index, len(bars_tail) - 1):
        done = j - start_index
        if done % progress_step == 0 and done > 0:
            pct = 100.0 * done / total_bars
            elapsed = _time.time() - progress_start
            eta = elapsed / done * (total_bars - done)
            print(f"  [{tf_name}] {done}/{total_bars} แท่ง ({pct:.0f}%) "
                  f"| เวลาที่ใช้ {elapsed:.0f}s | เหลืออีกประมาณ {eta:.0f}s", flush=True)

        event = bars_tail[j]

        # --- เช็คปิดไม้เดิมก่อน (วนทุกไม้ที่เปิดอยู่ — tv_mode อาจมีหลายไม้) ---
        still_open = []
        for pos in positions:
            side = pos["side"]
            if side > 0 and (event["high"] >= pos["tp"] or event["low"] <= pos["sl"]):
                hit_tp = event["high"] >= pos["tp"]
                close_one(pos, j, pos["tp"] if hit_tp else pos["sl"], "TP" if hit_tp else "SL")
            elif side < 0 and (event["low"] <= pos["tp"] or event["high"] >= pos["sl"]):
                hit_tp = event["low"] <= pos["tp"]
                close_one(pos, j, pos["tp"] if hit_tp else pos["sl"], "TP" if hit_tp else "SL")
            else:
                still_open.append(pos)
        positions = still_open

        if j < 1 or np.isnan(k[j]) or np.isnan(d[j]) or np.isnan(k[j - 1]) or np.isnan(d[j - 1]):
            continue

        trend_long = close[j] > ema_slow[j] and close[j] > ema_mid[j] and close[j] > ema_fast[j]
        trend_short = close[j] < ema_slow[j] and close[j] < ema_mid[j] and close[j] < ema_fast[j]
        cross_up = k[j - 1] <= d[j - 1] and k[j] > d[j]
        cross_down = k[j - 1] >= d[j - 1] and k[j] < d[j]
        signal_long = allow_buy and trend_long and cross_up and k[j] < long_limit
        signal_short = allow_sell and trend_short and cross_down and k[j] > short_limit

        if not (signal_long or signal_short):
            continue
        atr_j = float(atr[j])
        if not atr_j or atr_j <= 0.0 or math.isnan(atr_j):
            continue
        fill_price = float(bars_tail[j + 1]["open"])
        entry_time = bar_time_to_bkk(bars_tail[j + 1]["time"])
        entry_ref = float(close[j])  # SL/TP คำนวณจาก close แท่งสัญญาณ (ตรงกับ Pine)
        side_wanted = 1 if signal_long else -1

        if positions and positions[0]["side"] != side_wanted:
            for pos in positions:  # net-flip: ปิดไม้ฝั่งตรงข้ามทั้งหมดก่อน
                close_one(pos, j, fill_price, "REV")
            positions = []

        if not tv_mode:
            if not positions:
                open_one(j, side_wanted, fill_price, entry_ref, atr_j, entry_time)
        elif len(positions) < pyramid_max:
            open_one(j, side_wanted, fill_price, entry_ref, atr_j, entry_time)

    profits = [trade["profit"] for trade in trades]
    wins = sum(profit > 0.0 for profit in profits)
    gross_win = sum(profit for profit in profits if profit > 0.0)
    gross_loss = -sum(profit for profit in profits if profit < 0.0)
    net = sum(profits)
    dd_equity = peak = max_drawdown = 0.0
    for profit in profits:
        dd_equity += profit
        peak = max(peak, dd_equity)
        max_drawdown = max(max_drawdown, peak - dd_equity)
    calendar_days = max(1.0, (end_bkk - start_bkk).total_seconds() / 86400.0)
    summary = {
        "strategy": "S430", "tf": tf_name,
        "start": fmt_bkk(start_bkk), "end": fmt_bkk(end_bkk),
        "days": round(calendar_days, 1), "spread": spread, "lot": lot,
        "tv_mode": tv_mode, "pct_equity": pct_equity, "commission_pct": commission_pct,
        "pyramid_max": pyramid_max if tv_mode else 1,
        "final_equity": round(equity, 2) if tv_mode else None,
        "signals": signals, "closed": len(trades), "wins": wins,
        "win_rate": wins / len(trades) * 100.0 if trades else None,
        "net_profit": net,
        "net_profit_pct": (net / starting_balance * 100.0) if tv_mode else None,
        "pnl_per_day": net / calendar_days,
        "profit_factor": gross_win / gross_loss if gross_loss else (math.inf if gross_win else None),
        "max_drawdown": max_drawdown,
    }
    return summary, trades



_LOG_FILLED_RE = re.compile(
    r"^\[(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\] TG_SENT \| .*?\*(?P<label>[^*]+?)\* "
    r"limit filled \| \S+ (?P<dir>BUY|SELL) @ (?P<entry>[\d.]+) \| "
    r"SL `(?P<sl>[\d.]+)` TP `(?P<tp>[\d.]+)` \| Ticket: `(?P<ticket>\d+)`"
)
_LOG_MARKET_RE = re.compile(
    r"^\[(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\] TG_SENT \| .*?\*(?P<label>[^*]+?)\* "
    r"opened \| \S+ (?P<dir>BUY|SELL) @ (?P<entry>[\d.]+) \| "
    r"SL `(?P<sl>[\d.]+)` TP `(?P<tp>[\d.]+)` \| Ticket: `(?P<ticket>\d+)`"
)
_LOG_CLOSED_RE = re.compile(
    r"^\[(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\] POSITION_CLOSED \| .*? \| "
    r"ticket=(?P<ticket>\d+) \| side=(?P<dir>BUY|SELL) \| symbol=(?P<symbol>\S+) \| "
    r"tf=(?P<tf>\w+) \| .*? \| open_price=(?P<open>[\d.]+) \| close_price=(?P<close>[\d.]+) \| "
    r"sl=(?P<sl>[\d.]+) \| tp=(?P<tp>[\d.]+) \| profit=(?P<profit>-?[\d.]+) \| "
    r"reason=(?P<reason>.*?) \| close_time="
)


def _parse_log_bkk(ts_str):
    return datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=BKK)


def _fetch_real_trades(profile_dir, start_bkk, end_bkk, comment_prefix):
    log_path = os.path.join(profile_dir, "logs", "bot.log")
    fills = {}
    closes = {}
    with open(log_path, "r", encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            m = _LOG_FILLED_RE.match(line) or _LOG_MARKET_RE.match(line)
            if m:
                fills[m.group("ticket")] = {
                    "open_time": _parse_log_bkk(m.group("ts")),
                    "direction": m.group("dir"),
                    "entry": float(m.group("entry")),
                    "sl": float(m.group("sl")),
                    "tp": float(m.group("tp")),
                    "label": m.group("label"),
                }
                continue
            m = _LOG_CLOSED_RE.match(line)
            if m:
                closes[m.group("ticket")] = {
                    "close_time": _parse_log_bkk(m.group("ts")),
                    "tf": m.group("tf"),
                    "direction": m.group("dir"),
                    "open_price": float(m.group("open")),
                    "close_price": float(m.group("close")),
                    "sl": float(m.group("sl")),
                    "tp": float(m.group("tp")),
                    "profit": float(m.group("profit")),
                    "reason": m.group("reason"),
                }

    real_trades = []
    for ticket, close in closes.items():
        if not (start_bkk <= close["close_time"] <= end_bkk):
            continue
        fill = fills.get(ticket)
        if fill is not None and comment_prefix and comment_prefix not in fill["label"]:
            continue
        real_trades.append({
            "ticket": ticket,
            "tf": close["tf"],
            "direction": close["direction"],
            "entry": fill["entry"] if fill else close["open_price"],
            "sl": fill["sl"] if fill else close["sl"],
            "tp": fill["tp"] if fill else close["tp"],
            "open_time": fill["open_time"] if fill else close["close_time"],
            "close_time": close["close_time"],
            "profit": close["profit"],
            "reason": close["reason"],
            "label": fill["label"] if fill else "",
        })
    real_trades.sort(key=lambda t: t["open_time"])
    return real_trades


def _compare_trades(bt_trades, real_trades, tolerance):
    candidates = []
    for bi, bt in enumerate(bt_trades):
        for ri, rt in enumerate(real_trades):
            if bt["direction"] != rt["direction"]:
                continue
            price_diff = abs(bt["entry"] - rt["entry"])
            if price_diff > tolerance:
                continue
            time_diff = abs((bt["open_time"] - rt["open_time"]).total_seconds())
            if time_diff > 3600:
                continue
            candidates.append((price_diff + time_diff / 3600.0, bi, ri))
    candidates.sort(key=lambda c: c[0])

    used_bt, used_real = set(), set()
    matched = []
    for _, bi, ri in candidates:
        if bi in used_bt or ri in used_real:
            continue
        used_bt.add(bi)
        used_real.add(ri)
        matched.append((bt_trades[bi], real_trades[ri]))

    bt_only = [bt for bi, bt in enumerate(bt_trades) if bi not in used_bt]
    real_only = [rt for ri, rt in enumerate(real_trades) if ri not in used_real]
    return matched, bt_only, real_only


def _compare_csv_path(csv_path, tf_name, suffix):
    stem, ext = (csv_path.rsplit(".", 1) if "." in csv_path else (csv_path, "csv"))
    return f"{stem}_{tf_name}_{suffix}.{ext}"


def _write_csv(path, rows, fieldnames):
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"เขียน {len(rows)} แถวลง {path}")


def run_compare(all_bt_trades, start_bkk, end_bkk, args):
    print("\n\n===== เทียบกับของจริงจาก bot.log (--compare) =====")
    real_trades_all = _fetch_real_trades(args.compare_profile_dir, start_bkk, end_bkk,
                                          args.compare_comment_prefix)
    print(f"อ่าน bot.log จาก {args.compare_profile_dir} ได้ {len(real_trades_all)} ไม้จริง "
          f"ในช่วง {start_bkk} - {end_bkk}")

    bt_trades = [{
        "tf": t["tf"], "direction": t["direction"], "entry": float(t["entry"]),
        "sl": t.get("sl"), "tp": t.get("tp"),
        "open_time": datetime.strptime(t["entry_time"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=BKK),
        "close_time": datetime.strptime(t["exit_time"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=BKK),
        "profit": float(t["profit"]), "outcome": t.get("outcome"),
    } for t in all_bt_trades if t.get("exit_time")]

    tf_list = sorted({t["tf"] for t in bt_trades} | {t["tf"] for t in real_trades_all})
    compare_fields = ["TF", "Direction", "BT_Open_Time", "MT5_Open_Time", "BT_Entry", "MT5_Entry",
                       "BT_SL", "MT5_SL", "BT_TP", "MT5_TP", "BT_Close_Time", "MT5_Close_Time",
                       "BT_Profit", "MT5_Profit", "MT5_Ticket", "MT5_Reason"]
    real_fields = ["Ticket", "TF", "Direction", "Open_Time", "Close_Time", "Entry", "SL", "TP",
                   "Profit", "Reason"]
    bt_fields = ["TF", "Direction", "Open_Time", "Close_Time", "Entry", "SL", "TP", "Profit", "Outcome"]

    grand_matched = grand_bt_only = grand_real_only = 0
    for tf_name in tf_list:
        bt_tf = [t for t in bt_trades if t["tf"] == tf_name]
        real_tf = [t for t in real_trades_all if t["tf"] == tf_name]
        matched, bt_only, real_only = _compare_trades(bt_tf, real_tf, args.compare_tolerance)
        grand_matched += len(matched)
        grand_bt_only += len(bt_only)
        grand_real_only += len(real_only)

        print(f"\n[{tf_name}] backtest={len(bt_tf)} จริง={len(real_tf)} "
              f"matched={len(matched)} bt_only={len(bt_only)} real_only={len(real_only)}")

        compare_rows = [{
            "TF": tf_name, "Direction": bt["direction"],
            "BT_Open_Time": bt["open_time"].strftime("%Y-%m-%d %H:%M:%S"),
            "MT5_Open_Time": rt["open_time"].strftime("%Y-%m-%d %H:%M:%S"),
            "BT_Entry": round(bt["entry"], 2), "MT5_Entry": round(rt["entry"], 2),
            "BT_SL": bt["sl"], "MT5_SL": round(rt["sl"], 2),
            "BT_TP": bt["tp"], "MT5_TP": round(rt["tp"], 2),
            "BT_Close_Time": bt["close_time"].strftime("%Y-%m-%d %H:%M:%S"),
            "MT5_Close_Time": rt["close_time"].strftime("%Y-%m-%d %H:%M:%S"),
            "BT_Profit": round(bt["profit"], 2), "MT5_Profit": round(rt["profit"], 2),
            "MT5_Ticket": rt["ticket"], "MT5_Reason": rt["reason"],
        } for bt, rt in matched]
        real_only_rows = [{
            "Ticket": rt["ticket"], "TF": rt["tf"], "Direction": rt["direction"],
            "Open_Time": rt["open_time"].strftime("%Y-%m-%d %H:%M:%S"),
            "Close_Time": rt["close_time"].strftime("%Y-%m-%d %H:%M:%S"),
            "Entry": round(rt["entry"], 2), "SL": round(rt["sl"], 2), "TP": round(rt["tp"], 2),
            "Profit": round(rt["profit"], 2), "Reason": rt["reason"],
        } for rt in real_only]
        bt_only_rows = [{
            "TF": bt["tf"], "Direction": bt["direction"],
            "Open_Time": bt["open_time"].strftime("%Y-%m-%d %H:%M:%S"),
            "Close_Time": bt["close_time"].strftime("%Y-%m-%d %H:%M:%S"),
            "Entry": round(bt["entry"], 2), "SL": bt["sl"], "TP": bt["tp"],
            "Profit": round(bt["profit"], 2), "Outcome": bt["outcome"],
        } for bt in bt_only]
        real_rows = [{
            "Ticket": rt["ticket"], "TF": rt["tf"], "Direction": rt["direction"],
            "Open_Time": rt["open_time"].strftime("%Y-%m-%d %H:%M:%S"),
            "Close_Time": rt["close_time"].strftime("%Y-%m-%d %H:%M:%S"),
            "Entry": round(rt["entry"], 2), "SL": round(rt["sl"], 2), "TP": round(rt["tp"], 2),
            "Profit": round(rt["profit"], 2), "Reason": rt["reason"],
        } for rt in real_tf]

        _write_csv(_compare_csv_path(args.csv, tf_name, "compare"), compare_rows, compare_fields)
        _write_csv(_compare_csv_path(args.csv, tf_name, "mt5_real"), real_rows, real_fields)
        _write_csv(_compare_csv_path(args.csv, tf_name, "mt5_not_match"), real_only_rows, real_fields)
        _write_csv(_compare_csv_path(args.csv, tf_name, "backtest_not_match"), bt_only_rows, bt_fields)

        if matched:
            bt_sum = sum(bt["profit"] for bt, _ in matched)
            real_sum = sum(rt["profit"] for _, rt in matched)
            print(f"  รวม P&L คู่ matched — backtest: {bt_sum:.2f} | จริง: {real_sum:.2f}")

    print(f"\n===== รวมทุก TF: matched={grand_matched} bt_only={grand_bt_only} "
          f"real_only={grand_real_only} =====")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--start", help="BKK ISO datetime เริ่ม backtest (เช่น 2026-06-01)")
    parser.add_argument("--end", help="BKK ISO datetime สิ้นสุด backtest; default = ตอนนี้")
    parser.add_argument("--days", type=int, help="จำนวนวันย้อนหลังจาก --end (ใช้แทน --start ได้)")
    parser.add_argument("--tf", choices=tuple(TF_MAP) + ("all",), default="H1",
                         help="timeframe เดียว หรือ 'all' เพื่อรันทุก timeframe แล้วสรุปเทียบกัน")
    parser.add_argument("--spread", type=float, default=0.20)
    parser.add_argument("--balance", type=float, default=100.0,
                         help="ยอดเงินสมมติ (USD) ใช้คำนวณ lot อัตโนมัติ = balance/10000 "
                              "(100->0.01, 1000->0.10, 10000->1.00, 100000->10.00) ใส่ --lot เพื่อ override ค่านี้")
    parser.add_argument("--lot", type=float, default=None,
                         help="ขนาด lot คงที่ (ถ้าไม่ใส่ จะคำนวณจาก --balance อัตโนมัติ)")
    parser.add_argument("--cfg-json", default="{}",
                         help="JSON object ส่งเข้า cfg ของ detect_s430 (เช่น EMA_LEN_SLOW/RSI_LEN/ATR_SL_MULT)")
    parser.add_argument("--csv", default=os.path.join(_HERE, "s430_trades.csv"),
                         help="path ไฟล์ CSV ผลลัพธ์ (default = s430_trades.csv ในโฟลเดอร์นี้ ไม่ใช่ CWD)")
    parser.add_argument("--compare", action="store_true",
                         help="หลัง backtest เสร็จ อ่าน logs/bot.log ของ profile จริง มาเทียบกับไม้ "
                              "backtest (จับคู่ด้วยทิศ/ราคา/เวลาใกล้เคียง) เขียนไฟล์ "
                              "{csv}_{TF}_compare/mt5_real/mt5_not_match/backtest_not_match.csv")
    parser.add_argument("--compare-profile-dir",
                         default=os.path.join(_ROOT, "profiles", "demo", "demo-iux-2101183587"),
                         help="path โฟลเดอร์ profile ที่มี profile.env ของ terminal จริงที่จะเทียบ")
    parser.add_argument("--compare-comment-prefix", default="S430",
                         help="กรอง deal ที่มี comment ขึ้นต้น/มีคำนี้เท่านั้น (default S430)")
    parser.add_argument("--compare-tolerance", type=float, default=1.0,
                         help="ระยะห่างราคาสูงสุด (USD) ที่ยังนับว่า match กัน (default 1.0)")
    parser.add_argument("--tv-mode", action="store_true",
                         help="เทียบ exact-match กับ TradingView: percent_of_equity sizing + "
                              "percent commission + pyramiding (default_qty_value=100, "
                              "pyramiding=10 ตาม Pine ต้นฉบับ) เปิดโหมดนี้จะ set ALLOW_SELL=True "
                              "อัตโนมัติด้วย (trade_direction=Both ตามที่ผู้ใช้ยืนยันว่าตั้งใน TV)")
    parser.add_argument("--pct-equity", type=float, default=100.0,
                         help="%% ของ equity ต่อไม้ (เฉพาะ --tv-mode, default 100 ตาม input จริงของ Pine)")
    parser.add_argument("--commission-pct", type=float, default=0.0,
                         help="%% commission ต่อ order (เฉพาะ --tv-mode, default 0 — Pine ต้นฉบับไม่ได้ตั้ง commission)")
    parser.add_argument("--pyramid-max", type=int, default=10,
                         help="จำนวนไม้ทิศเดียวกันสูงสุดพร้อมกัน (เฉพาะ --tv-mode, default 10 ตาม Pine pyramiding=10)")
    parser.add_argument("--tv-balance", type=float, default=1000000.0,
                         help="ยอดเงินตั้งต้น (เฉพาะ --tv-mode, default 1,000,000 ตาม TV ที่ผู้ใช้ทดสอบ)")
    args = parser.parse_args()

    if args.start and args.days:
        parser.error("ใส่ได้แค่ --start หรือ --days อย่างใดอย่างหนึ่ง ไม่ใช่ทั้งคู่")

    lot = args.lot if args.lot is not None else args.balance / 10000.0
    print(f"lot={lot:.2f}" + (f" (คำนวณจาก --balance={args.balance:g})" if args.lot is None else " (ระบุตรงผ่าน --lot)"))

    end_bkk = parse_bkk(args.end)
    if args.start:
        start_bkk = parse_bkk(args.start)
    elif args.days:
        start_bkk = end_bkk - timedelta(days=args.days)
    else:
        start_bkk = end_bkk - timedelta(days=DEFAULT_DAYS)

    if start_bkk >= end_bkk:
        parser.error("--start ต้องมาก่อน --end")

    try:
        detector_cfg = json.loads(args.cfg_json)
        if not isinstance(detector_cfg, dict):
            raise ValueError("cfg must be a JSON object")
    except (json.JSONDecodeError, ValueError) as exc:
        parser.error(f"invalid --cfg-json: {exc}")

    if args.tv_mode:
        detector_cfg.setdefault("ALLOW_SELL", True)
        print(f"TV mode เปิด: pct_equity={args.pct_equity:g}% commission={args.commission_pct:g}% "
              f"pyramid_max={args.pyramid_max} starting_balance={args.tv_balance:g} ALLOW_SELL="
              f"{detector_cfg['ALLOW_SELL']}")

    tf_list = tuple(TF_MAP) if args.tf == "all" else (args.tf,)
    pct_equity = args.pct_equity if args.tv_mode else None

    results = []
    all_bt_trades = []
    for tf_name in tf_list:
        print(f"\n===== TF={tf_name} =====")
        try:
            summary, trades = backtest(tf_name, args.spread, lot, start_bkk, end_bkk, detector_cfg,
                                        pct_equity=pct_equity, commission_pct=args.commission_pct,
                                        starting_balance=args.tv_balance, pyramid_max=args.pyramid_max)
        except RuntimeError as exc:
            print(f"ข้าม TF={tf_name}: {exc}")
            continue
        print(summary)
        for t in trades:
            t["tf"] = tf_name
        all_bt_trades.extend(trades)

        csv_path = _csv_path_for_tf(args.csv, tf_name)  # ต่อท้าย TF เสมอ ไม่ว่าจะรันกี่ TF ก็ตาม
        with open(csv_path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=(trades[0].keys() if trades else (
                "entry_time", "exit_time", "direction", "entry", "sl", "tp",
                "outcome", "profit", "pattern", "reason",
            )))
            writer.writeheader()
            writer.writerows(trades)
        print(f"เขียน {len(trades)} ไม้ลง {csv_path}")

        win_rate_str = f"{summary['win_rate']:.2f}%" if summary["win_rate"] is not None else "N/A"
        print("-" * 40)
        print(f"P&L        : {summary['net_profit']:.2f} USD")
        print(f"Win Rate   : {win_rate_str}")
        print(f"Win/Order  : {summary['wins']}/{summary['closed']}")
        print("-" * 40)
        results.append((tf_name, summary))

    if len(tf_list) > 1:
        print("\n===== สรุปเทียบทุก TF =====")
        header = f"{'TF':<6}{'P&L':>12}{'WinRate':>10}{'Win/Order':>12}{'PF':>10}{'MaxDD':>10}"
        print(header)
        for tf_name, summary in results:
            wr = f"{summary['win_rate']:.1f}%" if summary["win_rate"] is not None else "N/A"
            wo = f"{summary['wins']}/{summary['closed']}"
            if summary["profit_factor"] is None:
                pf = "N/A"
            elif summary["profit_factor"] == float("inf"):
                pf = "inf"
            else:
                pf = f"{summary['profit_factor']:.2f}"
            print(f"{tf_name:<6}{summary['net_profit']:>12.2f}{wr:>10}{wo:>12}{pf:>10}{summary['max_drawdown']:>10.2f}")

    if args.compare:
        run_compare(all_bt_trades, start_bkk, end_bkk, args)


if __name__ == "__main__":
    main()
