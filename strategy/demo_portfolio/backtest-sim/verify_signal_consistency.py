"""
verify_signal_consistency.py — เทียบ "logic-level": ไม้จริงที่เข้าไปแล้วบน MT5 vs สิ่งที่
backtest logic (detect_s<N> ตัวเดียวกับ live) ควรจะให้ผลลัพธ์ ณ เวลานั้นเป๊ะๆ
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ต่างจาก backtest_demo_portfolio.py (backtest สถิติระยะยาว) และ export_demo_portfolio_compare.py
(สรุปผลจริงสะสม) — สคริปต์นี้ตรวจ **ทีละไม้** ว่า signal/SL/TP ที่เกิดขึ้นจริงตรงกับที่ logic
เดียวกันควรให้ผล ณ เวลานั้นหรือไม่ (fetch ข้อมูลย้อนหลังด้วย copy_rates_from ให้ตรงเวลาเป๊ะ ไม่ใช่
"ตอนนี้") — ใช้ยืนยันว่า live กับ backtest ไม่ drift ออกจากกัน ไม่ต้องรอสะสมข้อมูลนาน

รัน:  python verify_signal_consistency.py [P13|P16|all] [--limit 20] [--env demo|real]
ผลลัพธ์: พิมพ์ MATCH/MISMATCH ทีละไม้ + สรุปท้าย, เขียน CSV ที่ ../excel/signal_consistency_check.csv
"""

import argparse
import csv
import json
import os
import sys
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

import MetaTrader5 as mt5
import config
import demo_portfolio as dp
import sim_s30_backtest as s30sim

STATE_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "..", "demo_portfolio_state.json")
_TF_MAP = {"M5": mt5.TIMEFRAME_M5, "M15": mt5.TIMEFRAME_M15}


def _load_state():
    with open(STATE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _fetch_bars_ending_at(symbol, tf_str, end_ts, count):
    """ดึงแท่งย้อนหลัง count แท่ง 'สิ้นสุดที่' end_ts เป๊ะ (ไม่ใช่ 'ล่าสุดตอนนี้') — ใช้
    copy_rates_from ซึ่งคืนแท่งที่ <= date_from เรียงจากเก่าไปใหม่ ตัวสุดท้ายคือแท่งใกล้ end_ts ที่สุด"""
    date_from = datetime.fromtimestamp(end_ts, tz=timezone.utc) + timedelta(seconds=1)
    rates = mt5.copy_rates_from(symbol, _TF_MAP[tf_str], date_from, count)
    return rates


def verify_one_trade(trade, tol_price=0.05):
    """คืน dict ผลตรวจ 1 ไม้: recomputed signal/sl/tp เทียบกับที่บันทึกไว้จริง

    ต้องใช้ "entry_bar_ts" (MT5 server timestamp ดิบของแท่งที่ยิง signal จริง) ไม่ใช่ "ts"
    (BKK wall-clock ที่แปลงแล้ว) — เคยลองคำนวณ MT5 timestamp ย้อนกลับจาก wall-clock มาก่อน
    แล้วพลาด (คลาดเคลื่อนจาก MT5-server-clock offset) ทำให้ fetch ผิดช่วงเวลาไปหลายสิบนาที
    ไม้เก่าที่ log ไว้ก่อนจะมี field นี้ (ก่อน 2026-07-01) จะถูก SKIP แทนที่จะเดา"""
    portfolio, key = trade["leg"].split("-", 1)
    label, detect_fn, cfg, needs_htf, extra_kind = dp._LEG_DEFS[key]

    entry_ts = trade.get("entry_bar_ts")
    if entry_ts is None:
        return {"ticket": trade["ticket"], "leg": trade["leg"], "result": "SKIP_NO_RAW_TS",
                "detail": "ไม้นี้ log ไว้ก่อนมี entry_bar_ts — ไม่มีเวลาดิบให้ fetch ย้อนหลังตรงเป๊ะ ข้ามการตรวจ"}
    entry_ts = int(entry_ts)

    entry_bars = _fetch_bars_ending_at(config.SYMBOL, "M5", entry_ts, 400)
    if entry_bars is None or len(entry_bars) < 30:
        return {"ticket": trade["ticket"], "leg": trade["leg"], "result": "NO_DATA",
                "detail": "ดึงแท่ง M5 ย้อนหลังไม่ได้"}

    htf_ctx = None
    if needs_htf and cfg.get("CONFIRMATION_TYPE", "htf_trend") != "none":
        htf_bars = _fetch_bars_ending_at(config.SYMBOL, "M15", entry_ts, 200)
        if htf_bars is not None:
            htf_series = s30sim.build_htf_series(htf_bars, cfg)
            htf_ctx = s30sim.htf_lookup(htf_series, entry_ts)

    dt_bkk = config.mt5_ts_to_bkk(entry_ts)
    kwargs = {"tf": "M5", "dt_bkk": dt_bkk, "cfg": cfg, "htf_ctx": htf_ctx}
    if extra_kind == "bar_dt_list":
        kwargs["bar_dt_list"] = [config.mt5_ts_to_bkk(int(b["time"])) for b in entry_bars[:-1]]
    elif extra_kind == "prev_week_hl":
        kwargs["prev_week_hl"] = dp._prev_week_hl_now(entry_ts)  # ใช้ W1 history เดียวกัน ไม่ผูกเวลา "ตอนนี้"

    try:
        res = detect_fn(entry_bars, **kwargs)
    except Exception as e:
        return {"ticket": trade["ticket"], "leg": trade["leg"], "result": "ERROR",
                "detail": f"{type(e).__name__}: {e}"}

    recomputed_signal = res.get("signal")
    actual_signal = trade["signal"]

    if recomputed_signal not in ("BUY", "SELL"):
        return {"ticket": trade["ticket"], "leg": trade["leg"], "result": "NO_SIGNAL",
                "detail": f"actual={actual_signal} but recompute=WAIT ({res.get('reason','')[:60]})"}

    if recomputed_signal != actual_signal:
        return {"ticket": trade["ticket"], "leg": trade["leg"], "result": "SIGNAL_MISMATCH",
                "detail": f"actual={actual_signal} recompute={recomputed_signal}"}

    sl_diff = abs(float(res["sl"]) - float(trade["sl"]))
    tp_diff = abs(float(res["tp"]) - float(trade["tp"]))
    if sl_diff > tol_price or tp_diff > tol_price:
        return {"ticket": trade["ticket"], "leg": trade["leg"], "result": "SL_TP_MISMATCH",
                "detail": f"sl_diff={sl_diff:.3f} tp_diff={tp_diff:.3f} "
                          f"(actual sl={trade['sl']} tp={trade['tp']}, recompute sl={res['sl']} tp={res['tp']})"}

    return {"ticket": trade["ticket"], "leg": trade["leg"], "result": "MATCH",
            "detail": f"signal={actual_signal} sl={trade['sl']} tp={trade['tp']} ตรงกันเป๊ะ"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("portfolio", nargs="?", default="all", choices=["P13", "P16", "all"])
    ap.add_argument("--days", type=float, default=7,
                     help="ตรวจไม้ทุกตัวที่เกิดใน N วันล่าสุด (default 7) — ครอบคลุมทุก leg "
                          "เท่ากัน ไม่ถูก leg ที่ยิงถี่แย่งที่ (ต่างจาก --limit เดิมที่นับจำนวน "
                          "ไม้รวมไม่สนใจว่าอยู่ leg ไหน)")
    ap.add_argument("--limit", type=int, default=None,
                     help="จำกัดจำนวนไม้สูงสุดที่ตรวจ (optional, กันช้าเกินไปถ้า --days กว้างมาก)")
    ap.add_argument("--env", choices=["demo", "real"], default="demo")
    args = ap.parse_args()

    if args.env == "real":
        login = os.getenv("MT5_LOGIN_REAL", "")
        password = os.getenv("MT5_PASSWORD_REAL", "")
        server = os.getenv("MT5_SERVER_REAL", "")
        if not (login and password and server):
            print("❌ --env real ต้องตั้ง MT5_LOGIN_REAL/MT5_PASSWORD_REAL/MT5_SERVER_REAL ก่อน")
            return
        config.MT5_LOGIN, config.MT5_PASSWORD, config.MT5_SERVER = int(login), password, server

    if not config.mt5_initialize(mt5):
        print(f"MT5 initialize ล้มเหลว: {mt5.last_error()}")
        return
    print(f"เชื่อมต่อ [{args.env}]: {config.SYMBOL} @ {config.MT5_SERVER} (login={config.MT5_LOGIN})")

    state = _load_state()
    portfolios = ["P13", "P16"] if args.portfolio == "all" else [args.portfolio]
    cutoff = datetime.now(timezone.utc).astimezone() - timedelta(days=args.days)
    trades = [t for t in state["trades"] if t.get("success")
              and any(t["leg"].startswith(f"{p}-") for p in portfolios)
              and datetime.fromisoformat(t["ts"]) >= cutoff]
    trades = sorted(trades, key=lambda t: t["ts"])
    if args.limit:
        trades = trades[-args.limit:]

    n_per_leg = {}
    for t in trades:
        n_per_leg[t["leg"]] = n_per_leg.get(t["leg"], 0) + 1
    print(f"ตรวจ {len(trades)} ไม้ ภายใน {args.days} วันล่าสุด "
          f"({len(n_per_leg)} leg: {', '.join(f'{k}={v}' for k, v in sorted(n_per_leg.items()))})\n")
    results = []
    for t in trades:
        r = verify_one_trade(t)
        results.append(r)
        mark = "✅" if r["result"] == "MATCH" else "❌"
        print(f"{mark} [{r['result']}] ticket={r['ticket']} leg={r['leg']} — {r['detail']}")

    mt5.shutdown()

    n_match = sum(1 for r in results if r["result"] == "MATCH")
    n_skip = sum(1 for r in results if r["result"] == "SKIP_NO_RAW_TS")
    n_checked = len(results) - n_skip
    print(f"\nสรุป: {n_match}/{n_checked} ไม้ที่ตรวจได้ตรงกัน (logic-level)"
          + (f" — ข้าม {n_skip} ไม้ (ไม่มี entry_bar_ts, log ไว้ก่อน 2026-07-01)" if n_skip else ""))

    excel_dir = os.path.join(os.path.dirname(__file__), "..", "excel")
    os.makedirs(excel_dir, exist_ok=True)
    out_path = os.path.join(excel_dir, "signal_consistency_check.csv")
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["ticket", "leg", "result", "detail"])
        w.writeheader()
        w.writerows(results)
    print(f"-> {out_path}")


if __name__ == "__main__":
    main()
