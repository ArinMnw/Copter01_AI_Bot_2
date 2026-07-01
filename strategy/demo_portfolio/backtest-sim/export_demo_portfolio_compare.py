"""
export_demo_portfolio_compare.py — เปรียบเทียบไม้จริงบน MT5 ของ P13/P16 กับที่ตั้งไว้ (SL/TP/RR)
ออกเป็น CSV รูปแบบเดียวกับ s20_6_backtest_summary.csv (Trades/WinRate/P&L/AvgWin/AvgLoss/MaxSLStreak)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ใช้ demo_portfolio_state.json (ticket ที่เราวางเอง) + mt5.history_deals_get() (ผลจริงที่ broker
ปิดให้) จับคู่ด้วย position_id — ต่างจาก backtest (ที่จำลอง SL/TP ล่วงหน้า) เพราะนี่คือของจริงที่
เกิดขึ้นบน MT5 แล้ว

รัน:  python export_demo_portfolio_compare.py [P13|P16|all] [--days N] [--env demo|real]
ผลลัพธ์ (อยู่ที่ ../excel/):
  - demo_portfolio_trades_detail.csv   (รายไม้: entry/exit/sl/tp/RR จริง vs ที่ตั้งใจ)
  - demo_portfolio_summary.csv         (สรุปรายleg สไตล์เดียวกับ s20_6_backtest_summary.csv)
"""

import argparse
import sys
import csv
import json
import os
from datetime import datetime, timezone, timedelta

# ไฟล์นี้อยู่ที่ strategy/p13/backtest-sim/ — ต้องขึ้นไป 3 ชั้นถึง project root เพื่อ import
# config ได้ (pattern เดียวกับ strategy/s20.6/backtest-sim/)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

import MetaTrader5 as mt5
import config

# demo_portfolio_state.json อยู่ที่ project root เสมอ (ไฟล์ live ของบอทหลัก ไม่ย้ายตาม script นี้)
STATE_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "..", "demo_portfolio_state.json")


def _load_state():
    with open(STATE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _leg_labels():
    """ดึง label เต็มของแต่ละ leg จาก demo_portfolio.py โดยไม่ต้อง import ทั้งไฟล์ (กัน
    dependency กับ MT5 connection ตอน import strategy files)"""
    import demo_portfolio as dp
    return {k: v[0] for k, v in dp._LEG_DEFS.items()}


def fetch_trade_rows(portfolios, days=None):
    """คืน list ของ dict รายไม้ พร้อมผลจริงจาก MT5 deal history — days=None แปลว่าเอาทุกไม้
    เท่าที่มีใน state (ไม่กรองเวลา), ระบุ days=N เพื่อเอาเฉพาะไม้ที่เกิดใน N วันล่าสุด"""
    state = _load_state()
    magic_map = {"P13": 990013, "P16": 990016}
    labels = _leg_labels()

    cutoff = None
    if days is not None:
        cutoff = datetime.now(timezone.utc).astimezone() - timedelta(days=days)

    # ticket -> trade log entry (สำหรับไม้ที่วางสำเร็จเท่านั้น + อยู่ในช่วงเวลาที่กำหนด)
    tickets = {t["ticket"]: t for t in state["trades"]
               if t.get("success") and t.get("ticket")
               and any(t["leg"].startswith(f"{p}-") for p in portfolios)
               and (cutoff is None or datetime.fromisoformat(t["ts"]) >= cutoff)}
    if not tickets:
        return []

    date_from = datetime.now(timezone.utc) - timedelta(days=200)
    date_to = datetime.now(timezone.utc) + timedelta(days=1)
    deals = mt5.history_deals_get(date_from, date_to)
    closing_deal = {}
    if deals:
        for d in deals:
            if d.entry == mt5.DEAL_ENTRY_OUT and d.position_id in tickets:
                closing_deal[d.position_id] = d

    open_positions = {p.ticket: p for p in (mt5.positions_get(symbol=config.SYMBOL) or [])}

    rows = []
    for ticket, t in tickets.items():
        portfolio, key = t["leg"].split("-", 1)
        sl, tp, entry_sig = t["sl"], t["tp"], t["signal"]
        risk = None
        rr_expected = None
        entry_price = None

        deal = closing_deal.get(ticket)
        pos = open_positions.get(ticket)
        if deal is not None:
            close_price = float(deal.price)
            profit = float(deal.profit) + float(deal.swap) + float(deal.commission)
            # จัดคลาสจาก "ปิดตรงราคาไหน" ด้วย tolerance แคบ (ไม่ใช่ distance เทียบ — เคยพลาดตรงนี้
            # มาก่อน: distance-based จะ mislabel ไม้ที่โดน generic-management ปิดกลางทางว่าเป็น
            # TP/SL ทั้งที่จริงไม่ใช่ — ราคาปิดจริงต้องตรง sl/tp แบบ near-exact เท่านั้นถึงนับ)
            tol = max(abs(tp - sl) * 0.02, 0.05)  # 2% ของระยะ SL-TP หรืออย่างน้อย 5 cent
            if abs(close_price - tp) <= tol:
                status = "TP"
            elif abs(close_price - sl) <= tol:
                status = "SL"
            else:
                status = "OTHER"  # ปิดโดยกลไกอื่น (ไม่ใช่ SL/TP จริง — เช่นบั๊ก generic-management)
            close_time = datetime.fromtimestamp(deal.time, tz=timezone.utc).astimezone(
                timezone(timedelta(hours=config.TZ_OFFSET))).isoformat()
        elif pos is not None:
            close_price = None
            profit = float(pos.profit) + float(pos.swap)
            status = "OPEN"
            close_time = ""
        else:
            close_price = None
            profit = None
            status = "UNKNOWN"  # ปิดไปแล้วแต่หา deal ไม่เจอ (นอกช่วง 200 วัน หรือ history ยังไม่ sync)
            close_time = ""

        rows.append({
            "portfolio": portfolio, "leg": key, "label": labels.get(key, key),
            "ticket": ticket, "signal": entry_sig,
            "entry_ts": t["ts"], "sl": sl, "tp": tp,
            "close_time": close_time, "close_price": close_price,
            "status": status, "profit_usd": profit,
        })
    return rows


def write_detail_csv(rows, path):
    fields = ["portfolio", "leg", "label", "ticket", "signal", "entry_ts", "sl", "tp",
              "close_time", "close_price", "status", "profit_usd"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in sorted(rows, key=lambda x: x["entry_ts"]):
            w.writerow(r)
    print(f"-> {path} ({len(rows)} rows)")


def write_summary_csv(rows, path):
    """สรุปรายleg สไตล์เดียวกับ s20_6_backtest_summary.csv:
    Portfolio,Leg,Trades,WinRate(%),P/L($),AvgWin($),AvgLoss($),MaxSLStreak,OtherClose

    Win/Loss ใช้ profit จริง (profit_usd > 0) เป็นเกณฑ์ — ไม่ใช่ label TP/SL (เคยพลาดตรงนี้:
    label TP/SL เป็นแค่ "ปิดใกล้ราคาไหน" ไม่ใช่ตัวชี้กำไร/ขาดทุนจริง). OtherClose = จำนวนไม้ที่ปิด
    ไม่ตรง SL/TP เป๊ะๆ (อาจเป็นบั๊ก generic-management เก่าที่ยังไม่ถูก sid=21 ป้องกัน — ควรเป็น 0
    สำหรับไม้ที่เปิดหลัง fix)"""
    by_leg = {}
    for r in rows:
        if r["status"] not in ("TP", "SL", "OTHER"):  # ข้ามเฉพาะ OPEN/UNKNOWN (ยังไม่ปิดจบ)
            continue
        key = (r["portfolio"], r["leg"], r["label"])
        by_leg.setdefault(key, []).append(r)

    fields = ["Portfolio", "Leg", "Label", "Trades", "WinRate(%)", "P/L($)",
              "AvgWin($)", "AvgLoss($)", "MaxSLStreak", "OtherClose"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for (portfolio, leg, label), trades in sorted(by_leg.items()):
            trades_sorted = sorted(trades, key=lambda x: x["entry_ts"])
            wins = [t["profit_usd"] for t in trades_sorted if t["profit_usd"] > 0]
            losses = [t["profit_usd"] for t in trades_sorted if t["profit_usd"] <= 0]
            other_close = sum(1 for t in trades_sorted if t["status"] == "OTHER")
            n = len(trades_sorted)
            win_rate = 100.0 * len(wins) / n if n else 0.0
            pnl = sum(t["profit_usd"] for t in trades_sorted)
            avg_win = sum(wins) / len(wins) if wins else 0.0
            avg_loss = sum(losses) / len(losses) if losses else 0.0

            max_streak = 0
            cur_streak = 0
            for t in trades_sorted:
                if t["profit_usd"] <= 0:
                    cur_streak += 1
                    max_streak = max(max_streak, cur_streak)
                else:
                    cur_streak = 0

            w.writerow({
                "Portfolio": portfolio, "Leg": leg, "Label": label, "Trades": n,
                "WinRate(%)": round(win_rate, 1), "P/L($)": round(pnl, 2),
                "AvgWin($)": round(avg_win, 2), "AvgLoss($)": round(avg_loss, 2),
                "MaxSLStreak": max_streak, "OtherClose": other_close,
            })
    print(f"-> {path} ({len(by_leg)} legs)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("portfolio", nargs="?", default="all", choices=["P13", "P16", "all"])
    ap.add_argument("--days", type=float, default=None,
                     help="เอาเฉพาะไม้ที่เกิดใน N วันล่าสุด (default: ทุกไม้เท่าที่มีใน state)")
    ap.add_argument("--env", choices=["demo", "real"], default="demo",
                     help="เลือกบัญชี MT5 ที่จะดึงผลจริง (default: demo)")
    args = ap.parse_args()
    portfolios = ["P13", "P16"] if args.portfolio == "all" else [args.portfolio]

    if args.env == "real":
        login = os.getenv("MT5_LOGIN_REAL", "")
        password = os.getenv("MT5_PASSWORD_REAL", "")
        server = os.getenv("MT5_SERVER_REAL", "")
        if not (login and password and server):
            print("❌ --env real ต้องตั้ง MT5_LOGIN_REAL/MT5_PASSWORD_REAL/MT5_SERVER_REAL ก่อน")
            return
        config.MT5_LOGIN, config.MT5_PASSWORD, config.MT5_SERVER = int(login), password, server

    # ใช้ config.mt5_initialize() แทน mt5.initialize() ตรงๆ — บังคับ login เข้าบัญชีที่เลือก
    # (demo/real ตาม --env) เสมอ ไม่สนใจว่า terminal จะเปิดบัญชีไหนค้างอยู่ + resolve SYMBOL
    # ให้ถูกต้องอัตโนมัติ (เจอปัญหานี้จริงตอนทดสอบ 2026-07-01 — terminal สลับบัญชีเอง)
    if not config.mt5_initialize(mt5):
        print(f"MT5 initialize ล้มเหลว: {mt5.last_error()}")
        return
    print(f"เชื่อมต่อ [{args.env}]: {config.SYMBOL} @ {config.MT5_SERVER} (login={config.MT5_LOGIN})")

    rows = fetch_trade_rows(portfolios, days=args.days)
    days_label = f"{args.days} วันล่าสุด" if args.days is not None else "ทุกไม้ (ไม่กรองเวลา)"
    print(f"total tracked trades: {len(rows)} ({days_label})")
    if not rows:
        print("ยังไม่มีไม้ในระบบ — รอสัญญาณแรกก่อน")
        mt5.shutdown()
        return

    excel_dir = os.path.join(os.path.dirname(__file__), "..", "excel")
    os.makedirs(excel_dir, exist_ok=True)
    detail_path = os.path.join(excel_dir, "demo_portfolio_trades_detail.csv")
    summary_path = os.path.join(excel_dir, "demo_portfolio_summary.csv")
    write_detail_csv(rows, detail_path)
    write_summary_csv(rows, summary_path)

    mt5.shutdown()


if __name__ == "__main__":
    main()
