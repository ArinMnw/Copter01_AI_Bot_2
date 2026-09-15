# -*- coding: utf-8 -*-
"""Standalone backtest runner สำหรับ S423 "Always Winning Holy Grail - Not"
(ดู docstring ของ strategy423.py สำหรับที่มา/มุกของสคริปต์นี้) — ไม่ผ่าน
engine กลาง (sim_strategy_backtest.py) เพราะ default ไม่มี SL จริง (ผิด
convention RR>=1.5 ของ engine นั้น) จำลองแบบ stateful เอง: ถ้าไม่มีไม้เปิดอยู่
ให้เข้า BUY ทันทีทุกบาร์ ถือจนกว่าจะโดน TP หรือ SL (ถ้าตั้ง SL_POINTS ผ่าน
--cfg-json — default ยังคงตรงต้นฉบับคือไม่มี SL เลย)

จำกัดเฉพาะ TF M1/M5 ตามที่ขอ (Pine ต้นฉบับไม่ได้ผูก TF ไว้ แต่ยิ่ง TF เล็ก
ยิ่งเห็นพฤติกรรม "ชนะถี่ๆ" ของมุกนี้ชัดกว่า)

Usage:
    python backtest_s423.py --days 30 --tf M1
    python backtest_s423.py --start 2026-06-01 --end 2026-08-11 --tf M5
    python backtest_s423.py --days 30 --tf all   (= M1+M5 เท่านั้น)
    python backtest_s423.py --days 180 --tf all --cfg-json "{\"SL_POINTS\": 10}"
"""

from __future__ import annotations

import argparse
import csv
import re
import json
import math
import os
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
from strategy423 import DEFAULT_CFG

BKK = timezone(timedelta(hours=7))
# จำกัดเฉพาะ M1/M5 ตามที่ขอ — ต่างจาก backtest_s420/421/422 ที่รองรับครบทุก TF
TF_MAP = {"M1": mt5.TIMEFRAME_M1, "M5": mt5.TIMEFRAME_M5}
TF_SECONDS = {"M1": 60, "M5": 300}

LOOKBACK_BARS = 5  # ไม่มี indicator ต้องอุ่นเครื่องเลย เผื่อไว้นิดหน่อยพอ
MIN_LOOKBACK_BARS = 5
DEFAULT_DAYS = 30


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


def bar_time_to_bkk(raw_time):
    return datetime.fromtimestamp(int(raw_time), tz=BKK) - timedelta(hours=1)


def bkk_to_query(dt_bkk):
    return dt_bkk + timedelta(hours=1)


def prepare_rates(tf_name, start_bkk, end_bkk):
    history_days = math.ceil(LOOKBACK_BARS * TF_SECONDS[tf_name] / 86400.0) + 2
    fetch_start = bkk_to_query(start_bkk - timedelta(days=history_days))
    fetch_end = bkk_to_query(end_bkk)
    if not config.mt5_initialize(mt5):
        raise RuntimeError("MT5 initialization failed")
    acc = mt5.account_info()
    if acc is not None:
        print(f"MT5 account: login={acc.login} server={acc.server} name={acc.name} "
              f"balance={acc.balance:.2f} {acc.currency}")
    tick = mt5.symbol_info_tick(config.SYMBOL)
    if tick is not None:
        server_bkk = bar_time_to_bkk(tick.time)
        print(f"เวลาปัจจุบันของ broker (raw MT5): {datetime.fromtimestamp(int(tick.time), tz=BKK).strftime('%Y-%m-%d %H:%M:%S')}  "
              f"|  เวลาจริง BKK (แก้ตาม MT5 Timezone Rule): {fmt_bkk(server_bkk)}")

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
        raise RuntimeError(f"ประวัติ {tf_name} ก่อน --start ไม่พอ ({start_index} แท่ง)")
    return bars, start_index


def backtest(tf_name, spread, lot, start_bkk, end_bkk, cfg=None):
    """ไม่มีไม้เปิดอยู่ -> เข้า BUY ทันทีทุกบาร์ ถือจนกว่าจะโดน TP หรือ SL —
    default SL_POINTS=999999999999999 ตรงกับ Pine เป๊ะ (ใหญ่จนแทบเป็นไปไม่ได้
    ที่จะโดนจริง แต่ยังเป็น SL จริงในโค้ด ไม่ใช่ None) — ถ้า backtest จบช่วงเวลา
    โดยยังถือไม้ค้างอยู่ จะนับเป็น 'OPEN' ไม่ปิดไม้ทิ้ง (mark-to-market ด้วย
    ราคาแท่งสุดท้ายเพื่อรายงาน unrealized P&L)."""
    detector_cfg = dict(DEFAULT_CFG)
    detector_cfg.update(cfg or {})
    tp_points, point_value = float(detector_cfg["TP_POINTS"]), float(detector_cfg["POINT_VALUE"])
    tp_distance = tp_points * point_value
    sl_points = detector_cfg["SL_POINTS"]
    sl_distance = float(sl_points) * point_value if sl_points is not None else None

    bars, start_index = prepare_rates(tf_name, start_bkk, end_bkk)
    contract_multiplier = 100.0 * lot

    trades = []
    signals = 0
    position = None  # {"entry","tp","entry_time"}

    total_bars = len(bars) - 1 - start_index
    progress_step = max(1, total_bars // 20)
    progress_start = _time.time()

    for index in range(start_index, len(bars) - 1):
        done = index - start_index
        if done % progress_step == 0 and done > 0:
            pct = 100.0 * done / total_bars
            elapsed = _time.time() - progress_start
            eta = elapsed / done * (total_bars - done)
            print(f"  [{tf_name}] {done}/{total_bars} แท่ง ({pct:.0f}%) "
                  f"| เวลาที่ใช้ {elapsed:.0f}s | เหลืออีกประมาณ {eta:.0f}s", flush=True)

        event = bars[index]

        # --- เช็ค TP/SL (SL default ใหญ่มาก แทบไม่มีทางโดน แต่ยังเช็คจริงตามโค้ด) ---
        if position is not None:
            hit_sl = position["sl"] is not None and event["low"] <= position["sl"]
            hit_tp = event["high"] >= position["tp"]
            if hit_sl or hit_tp:
                # ถ้าทั้งคู่โดนในแท่งเดียวกัน ใช้ SL ก่อนแบบระมัดระวัง (worst-case)
                exit_price = position["sl"] if hit_sl else position["tp"]
                outcome = "SL" if hit_sl else "TP"
                pnl = (exit_price - position["entry"] - spread) * contract_multiplier
                trades.append({
                    "entry_time": fmt_bkk(position["entry_time"]),
                    "exit_time": fmt_bkk(bar_time_to_bkk(event["time"])),
                    "direction": "BUY", "entry": round(position["entry"], 2),
                    "sl": round(position["sl"], 2) if position["sl"] is not None else None,
                    "tp": round(position["tp"], 2),
                    "outcome": outcome, "profit": round(pnl, 2),
                    "pattern": "S423 Always-Long",
                    "reason": f"Hit {outcome}",
                })
                position = None

        # --- ไม่มีไม้เปิดอยู่ -> เข้าใหม่ทันที (ไม่มีเงื่อนไขใดๆ) ---
        if position is None:
            signals += 1
            fill_price = float(bars[index + 1]["open"])
            position = {
                "entry": fill_price, "tp": fill_price + tp_distance,
                "sl": fill_price - sl_distance if sl_distance is not None else None,
                "entry_time": bar_time_to_bkk(bars[index + 1]["time"]),
            }

    open_note = None
    if position is not None:
        last_close = float(bars[-1]["close"])
        unrealized = (last_close - position["entry"] - spread) * contract_multiplier
        open_note = (f"ไม้ค้างอยู่ตอนจบ backtest: entry={position['entry']:.2f} "
                      f"TP={position['tp']:.2f} unrealized={unrealized:.2f} USD (ยังไม่นับเป็น P&L)")

    profits = [trade["profit"] for trade in trades]
    wins = sum(profit > 0.0 for profit in profits)  # ถ้าไม่ตั้ง SL_POINTS จะเป็น 100% เสมอ (ตรงต้นฉบับ)
    gross_win = sum(profit for profit in profits if profit > 0.0)
    gross_loss = -sum(profit for profit in profits if profit < 0.0)
    net = sum(profits)
    calendar_days = max(1.0, (end_bkk - start_bkk).total_seconds() / 86400.0)
    summary = {
        "strategy": "S423", "tf": tf_name,
        "start": fmt_bkk(start_bkk), "end": fmt_bkk(end_bkk),
        "days": round(calendar_days, 1), "spread": spread, "lot": lot,
        "signals": signals, "closed": len(trades), "wins": wins,
        "win_rate": wins / len(trades) * 100.0 if trades else None,
        "net_profit": net,
        "pnl_per_day": net / calendar_days,
        "profit_factor": gross_win / gross_loss if gross_loss else (math.inf if gross_win else None),
        "open_position_note": open_note,
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
    """ดึงไม้จริงจาก bot.log ของ profile ตรงๆ (ไม่ใช้ MT5 deal history) — จับคู่
    เวลา "limit filled"/"opened" (มี label/SL/TP ตามที่ live คำนวณจริง) กับ
    "POSITION_CLOSED" (มี tf/close_price/profit/reason) ด้วย ticket คืน list
    ของ {ticket, tf, direction, entry, sl, tp, open_time, close_time, profit,
    reason, label}"""
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
    """จับคู่ไม้ backtest กับไม้จริงด้วยทิศทาง + ราคา entry ใกล้เคียงกัน
    (ภายใน tolerance) + เวลาเปิดห่างกันไม่เกิน 1 ชม. คืน (matched, bt_only,
    real_only) — จับคู่แบบ greedy ทีละคู่ที่ใกล้กันที่สุดก่อน"""
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
    parser.add_argument("--tf", choices=tuple(TF_MAP) + ("all",), default="M1",
                         help="M1 หรือ M5 เท่านั้น (หรือ 'all' = ทั้งคู่)")
    parser.add_argument("--spread", type=float, default=0.20)
    parser.add_argument("--balance", type=float, default=100.0,
                         help="ยอดเงินสมมติ (USD) ใช้คำนวณ lot อัตโนมัติ = balance/10000")
    parser.add_argument("--lot", type=float, default=None,
                         help="ขนาด lot คงที่ (ถ้าไม่ใส่ จะคำนวณจาก --balance อัตโนมัติ)")
    parser.add_argument("--cfg-json", default="{}",
                         help="JSON object ส่งเข้า cfg (เช่น TP_POINTS/POINT_VALUE)")
    parser.add_argument("--csv", default=os.path.join(_HERE, "s423_trades.csv"),
                         help="path ไฟล์ CSV ผลลัพธ์ (default = s423_trades.csv ในโฟลเดอร์นี้)")
    parser.add_argument("--compare", action="store_true",
                         help="หลัง backtest เสร็จ อ่าน logs/bot.log ของ profile จริง มาเทียบกับไม้ "
                              "backtest (จับคู่ด้วยทิศ/ราคา/เวลาใกล้เคียง) เขียนไฟล์ "
                              "{csv}_{TF}_compare/mt5_real/mt5_not_match/backtest_not_match.csv")
    parser.add_argument("--compare-profile-dir",
                         default=os.path.join(_ROOT, "profiles", "demo", "demo-iux-2101183587"),
                         help="path โฟลเดอร์ profile ที่มี profile.env ของ terminal จริงที่จะเทียบ")
    parser.add_argument("--compare-comment-prefix", default="S423",
                         help="กรอง deal ที่มี comment ขึ้นต้น/มีคำนี้เท่านั้น (default S423)")
    parser.add_argument("--compare-tolerance", type=float, default=1.0,
                         help="ระยะห่างราคาสูงสุด (USD) ที่ยังนับว่า match กัน (default 1.0)")
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

    tf_list = tuple(TF_MAP) if args.tf == "all" else (args.tf,)

    results = []
    all_bt_trades = []
    for tf_name in tf_list:
        print(f"\n===== TF={tf_name} =====")
        try:
            summary, trades = backtest(tf_name, args.spread, lot, start_bkk, end_bkk, detector_cfg)
        except RuntimeError as exc:
            print(f"ข้าม TF={tf_name}: {exc}")
            continue
        print(summary)
        for t in trades:
            t["tf"] = tf_name
        all_bt_trades.extend(trades)
        if summary.get("open_position_note"):
            print(f"หมายเหตุ: {summary['open_position_note']}")

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
        header = f"{'TF':<6}{'P&L':>12}{'WinRate':>10}{'Win/Order':>12}{'PF':>10}"
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
            print(f"{tf_name:<6}{summary['net_profit']:>12.2f}{wr:>10}{wo:>12}{pf:>10}")

    if args.compare:
        run_compare(all_bt_trades, start_bkk, end_bkk, args)


if __name__ == "__main__":
    main()
