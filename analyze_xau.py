#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
analyze_xau.py — วิเคราะห์ผลเทรด XAUUSD 26 พ.ค. ถึงปัจจุบัน
ขั้นที่ 1: parse log → OLD realized P/L + breakdown + cascade clusters + ORDER_FAILED
"""
import os, re, sys, io
from datetime import datetime
from collections import defaultdict, Counter

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.abspath(__file__))
BOT_LOG = os.path.join(ROOT, "logs", "bot.log")

WIN_START = "2026-05-26"
SYM = "XAUUSD"

_TS = re.compile(r"^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]\s+(\S+)")

def field(line, key):
    m = re.search(rf"{key}=([^|]+?)(?:\s*\||$)", line)
    return m.group(1).strip() if m else None

def main():
    closes = []          # POSITION_CLOSED (XAU)
    order_failed = Counter()
    order_created = 0
    of_first, of_last = None, None
    of_by_day = Counter()

    with open(BOT_LOG, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            m = _TS.match(line)
            if not m:
                continue
            ts, kind = m.group(1), m.group(2)
            if ts[:10] < WIN_START:
                continue
            if kind == "POSITION_CLOSED" and "symbol=XAUUSD" in line:
                closes.append({
                    "ts": ts,
                    "ticket": field(line, "ticket"),
                    "side": field(line, "side"),
                    "tf": field(line, "tf"),
                    "sid": field(line, "sid"),
                    "trend_filter": field(line, "trend_filter"),
                    "open": float(field(line, "open_price") or 0),
                    "close": float(field(line, "close_price") or 0),
                    "sl": float(field(line, "sl") or 0),
                    "tp": float(field(line, "tp") or 0),
                    "profit": float(field(line, "profit") or 0),
                    "reason": field(line, "reason") or "",
                    "is_sl": "SL Hit" in line,
                    "is_tp": "TP Hit" in line,
                })
            elif kind == "ORDER_FAILED":
                # reason ของ ORDER_FAILED อยู่หลัง | ตัวแรก
                mm = re.search(r"ORDER_FAILED \| (.+?)(?:\s*\| tf=|\s*\| sid=|$)", line)
                rkey = (mm.group(1).strip() if mm else "?")[:60]
                order_failed[rkey] += 1
                of_by_day[ts[:10]] += 1
                if of_first is None:
                    of_first = ts
                of_last = ts
            elif kind == "ORDER_CREATED":
                order_created += 1

    # ── OLD realized P/L ──
    total = sum(c["profit"] for c in closes)
    sl_loss = sum(c["profit"] for c in closes if c["is_sl"])
    tp_gain = sum(c["profit"] for c in closes if c["is_tp"])
    bot_close = sum(c["profit"] for c in closes if not c["is_sl"] and not c["is_tp"])
    n_sl = sum(1 for c in closes if c["is_sl"])
    n_tp = sum(1 for c in closes if c["is_tp"])
    n_bot = len(closes) - n_sl - n_tp

    print("=" * 78)
    print(f"  XAUUSD — สรุปผลจริง (OLD) ตั้งแต่ {WIN_START} | closes={len(closes)}")
    print(f"  ช่วง: {closes[0]['ts']}  ->  {closes[-1]['ts']}")
    print("=" * 78)
    print(f"  รวม realized P/L : {total:>10.2f} USD")
    print(f"    SL Hit  ({n_sl:>4d}) : {sl_loss:>10.2f}")
    print(f"    TP Hit  ({n_tp:>4d}) : {tp_gain:>10.2f}")
    print(f"    Bot/อื่น ({n_bot:>4d}) : {bot_close:>10.2f}")
    print()

    # by sid
    print("  ── by Strategy (sid) ──")
    by_sid = defaultdict(lambda: [0, 0.0, 0, 0])  # n, pnl, n_sl, n_tp
    for c in closes:
        r = by_sid[c["sid"]]
        r[0] += 1; r[1] += c["profit"]
        if c["is_sl"]: r[2] += 1
        if c["is_tp"]: r[3] += 1
    for sid in sorted(by_sid, key=lambda s: by_sid[s][1]):
        n, pnl, nsl, ntp = by_sid[sid]
        print(f"    S{str(sid):<3}: n={n:>4d}  P/L={pnl:>9.2f}  SL={nsl:>3d} TP={ntp:>3d}")
    print()

    # by side
    print("  ── by side ──")
    for side in ("BUY", "SELL"):
        cs = [c for c in closes if c["side"] == side]
        print(f"    {side}: n={len(cs):>4d}  P/L={sum(c['profit'] for c in cs):>9.2f}  "
              f"SL={sum(1 for c in cs if c['is_sl']):>3d} TP={sum(1 for c in cs if c['is_tp']):>3d}")
    print()

    # by day
    print("  ── by day ──")
    by_day = defaultdict(lambda: [0, 0.0])
    for c in closes:
        d = by_day[c["ts"][:10]]
        d[0] += 1; d[1] += c["profit"]
    for day in sorted(by_day):
        print(f"    {day}: n={by_day[day][0]:>4d}  P/L={by_day[day][1]:>9.2f}")
    print()

    # ── ORDER_FAILED ──
    print("=" * 78)
    print(f"  🔴 ORDER_FAILED รวม {sum(order_failed.values())} ครั้ง  ({of_first} -> {of_last})")
    print("=" * 78)
    for r, n in order_failed.most_common(10):
        print(f"    {n:>7d}  {r}")
    print("  ── ORDER_FAILED by day ──")
    for day in sorted(of_by_day):
        print(f"    {day}: {of_by_day[day]:>8d}")
    print(f"  ORDER_CREATED (สำเร็จ) รวม: {order_created}")

    # ── cascade clusters: SL ติดกันฝั่งเดียว ──
    print()
    print("=" * 78)
    print("  CASCADE: ช่วง SL ฝั่งเดียวกันติดกัน ≥3 ครั้ง (group guard ควร trigger)")
    print("=" * 78)
    sl_closes = [c for c in closes if c["is_sl"]]
    sl_closes.sort(key=lambda c: c["ts"])
    runs = []
    cur = []
    for c in sl_closes:
        if cur and c["side"] == cur[-1]["side"]:
            # gap เวลาไม่เกิน 30 นาที ถือว่า run เดียวกัน
            dt1 = datetime.strptime(c["ts"], "%Y-%m-%d %H:%M:%S")
            dt0 = datetime.strptime(cur[-1]["ts"], "%Y-%m-%d %H:%M:%S")
            if (dt1 - dt0).total_seconds() <= 1800:
                cur.append(c); continue
        if len(cur) >= 3:
            runs.append(cur)
        cur = [c]
    if len(cur) >= 3:
        runs.append(cur)

    total_cascade_loss = 0.0
    total_avoidable = 0.0
    for run in runs:
        loss = sum(c["profit"] for c in run)
        # avoidable = ตั้งแต่ตัวที่ 3 เป็นต้นไป (2 ตัวแรก trigger guard)
        avoidable = sum(c["profit"] for c in run[2:])
        total_cascade_loss += loss
        total_avoidable += avoidable
        print(f"  {run[0]['side']:>4} | {run[0]['ts']} -> {run[-1]['ts']} | "
              f"n={len(run):>2d} | loss={loss:>8.2f} | ตั้งแต่ตัวที่3={avoidable:>8.2f}")
    print("-" * 78)
    print(f"  รวม cascade loss: {total_cascade_loss:.2f} | "
          f"avoidable (ตัวที่3+): {total_avoidable:.2f}")

if __name__ == "__main__":
    main()
