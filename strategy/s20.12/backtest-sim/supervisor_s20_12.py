"""
supervisor_s20_12.py — S20.12 Live Supervisor

รันทุกวินาทีที่ :01 ของแต่ละนาที (sync กับขอบนาที):
  1. เรียก run_sim() โดยตรง (MT5 connection เดิม ไม่มี subprocess overhead)
  2. โหลด SIM trades ที่ได้จาก run_sim
  3. หา order ที่ SIM_Close <= now และยังไม่ได้ประมวลผล
  4. ถ้า MT5 position ยังเปิดอยู่ → force-close ทันที
  5. ขยับ current_start = earliest pending SIM_Open - 1 นาที
  6. Sleep จนถึง :01 ของนาทีถัดไป

รัน:
  python strategy/s20.12/backtest-sim/supervisor_s20_12.py --start "03-07-2026 12:04" --compound 2
"""

import argparse
import sys
import os
import time
from datetime import datetime, timedelta, timezone

script_dir = os.path.dirname(os.path.abspath(__file__))
root_dir   = os.path.dirname(os.path.dirname(os.path.dirname(script_dir)))
sys.path.insert(0, root_dir)

import json
import MetaTrader5 as mt5
import config
from mt5_utils import connect_mt5
from sim_core import run_sim

STATE_FMT  = "%d-%m-%Y %H:%M"
# state files เก็บตาม profile dir → demo/real มี state แยกกัน ไม่ชนกัน
STATE_FILE     = os.path.join(config.PROFILE_DIR, ".supervisor_s2012_state")
BOT_STATE_FILE = config.STATE_FILE  # bot_state.json ของ main bot (อ่าน s20_12_enabled)


def _is_s20_12_enabled() -> bool:
    """อ่าน bot_state.json ทุก cycle เพื่อรับ Telegram toggle แบบ real-time"""
    try:
        with open(BOT_STATE_FILE, encoding="utf-8") as f:
            return bool(json.load(f).get("s20_12_enabled", True))
    except Exception:
        return True  # อ่านไม่ได้ → assume enabled


def _load_state(fallback: datetime) -> datetime:
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE) as f:
                saved = datetime.strptime(f.read().strip(), STATE_FMT)
            print(f"📂 Resume จาก state: {saved.strftime(STATE_FMT)}")
            return saved
        except Exception:
            pass
    return fallback


def _save_state(dt: datetime):
    with open(STATE_FILE, "w") as f:
        f.write(dt.strftime(STATE_FMT))


def _clear_state():
    if os.path.exists(STATE_FILE):
        os.remove(STATE_FILE)


def _sleep_until_next_01():
    """Sleep จนถึงวินาทีที่ :01 ของนาทีถัดไป"""
    target = (datetime.now() + timedelta(minutes=1)).replace(second=1, microsecond=0)
    wait   = (target - datetime.now()).total_seconds()
    # กัน edge case: backtest ใช้เวลานานจน :01 ผ่านไปแล้ว
    while wait <= 0:
        target += timedelta(minutes=1)
        wait = (target - datetime.now()).total_seconds()
    print(f"  💤 รอจนถึง {target.strftime('%H:%M:%S')} ({wait:.0f}s)")
    time.sleep(wait)


def parse_args():
    parser = argparse.ArgumentParser(description="S20.12 Live Supervisor — force-close ตาม SIM backtest clock")
    parser.add_argument("--start",    type=str, required=True,
                        help="เวลาเริ่มต้น dd-MM-yyyy HH:mm (BKK) — เวลาที่เปิด run_supervised.bat")
    parser.add_argument("--compound", type=float, default=2.0,  help="Risk %% สำหรับ backtest (default 2)")
    parser.add_argument("--symbol",   type=str,  default="",    help="Symbol override")
    parser.add_argument("--tf",       type=str,  default="all", help="Timeframe สำหรับ backtest (default all)")
    return parser.parse_args()


def _hhmm(dt) -> tuple:
    if dt is None:
        return (-1, -1)
    if hasattr(dt, "hour"):
        return (dt.hour, dt.minute)
    return (-1, -1)


def _mt5_to_bkk_naive(ts: int) -> datetime:
    dt_aware = config.mt5_ts_to_bkk(ts)
    if hasattr(dt_aware, "tzinfo") and dt_aware.tzinfo is not None:
        return dt_aware.replace(tzinfo=None)
    return dt_aware


def find_open_position(sim_type: str, sim_open: datetime, symbol: str, positions):
    """หา open position ที่ตรงกับ SIM order (type + open HH:MM + comment มี 20.12)"""
    want_type = mt5.POSITION_TYPE_BUY if sim_type == "BUY" else mt5.POSITION_TYPE_SELL
    for pos in positions:
        if pos.symbol != symbol:
            continue
        if pos.type != want_type:
            continue
        comment = getattr(pos, "comment", "") or ""
        if "20.12" not in comment:
            continue
        if _hhmm(_mt5_to_bkk_naive(pos.time)) == _hhmm(sim_open):
            return pos
    return None


def close_position(pos, symbol: str) -> bool:
    """Force-close MT5 position ด้วย market order"""
    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        print(f"     ❌ ดึง tick ไม่ได้ — ข้าม position {pos.ticket}")
        return False

    close_type = mt5.ORDER_TYPE_SELL if pos.type == mt5.POSITION_TYPE_BUY else mt5.ORDER_TYPE_BUY
    price      = tick.bid if pos.type == mt5.POSITION_TYPE_BUY else tick.ask

    request = {
        "action":       mt5.TRADE_ACTION_DEAL,
        "symbol":       symbol,
        "volume":       pos.volume,
        "type":         close_type,
        "position":     pos.ticket,
        "price":        price,
        "deviation":    30,
        "magic":        0,
        "comment":      "S20.12_supervisor",
        "type_time":    mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    result = mt5.order_send(request)
    if result and result.retcode == mt5.TRADE_RETCODE_DONE:
        print(f"     ✅ ปิด ticket={pos.ticket} สำเร็จ")
        return True
    retcode = result.retcode if result else "N/A"
    print(f"     ❌ ปิดล้มเหลว ticket={pos.ticket} retcode={retcode}")
    return False


def main():
    args      = parse_args()
    fallback  = datetime.strptime(args.start, "%d-%m-%Y %H:%M")
    current_start = _load_state(fallback)
    processed   = set()   # (SIM_Open_str, SIM_Type) ที่ force-close ไปแล้วในรอบนี้
    was_enabled = None    # track transition disabled → enabled

    if not connect_mt5():
        print("❌ MT5 initialize failed")
        return

    symbol = config.profile_symbol(args.symbol or config.SYMBOL, mt5, set_runtime=True)
    mt5.symbol_select(symbol, True)

    resumed = current_start != fallback
    print(f"🚀 Supervisor S20.12 | symbol={symbol} | "
          f"{'resume=' if resumed else 'start='}{current_start.strftime(STATE_FMT)} | sync=:01/min")
    print("=" * 60)

    # บันทึก state ทันที — ถ้า crash ก่อนเจอ order แรก restart จะรู้ว่าต้องเริ่มจากไหน
    _save_state(current_start)

    # รอจนถึง :01 ของนาทีถัดไปก่อน cycle แรก
    # ป้องกันกรณีรัน bat กลางนาที เช่น 12:00:35 → รอถึง 12:01:01
    _sleep_until_next_01()

    while True:
        now = datetime.now()
        print(f"\n[{now.strftime('%H:%M:%S')}] ─── รอบใหม่ ───")

        enabled = _is_s20_12_enabled()
        if not enabled:
            print(f"  ⏸️  S20.12 disabled (Telegram toggle) — skip")
            was_enabled = False
            _sleep_until_next_01()
            continue

        # transition disabled → enabled: reset current_start = now เพื่อไม่ backtest ย้อนหลัง
        if was_enabled is False:
            current_start = now - timedelta(minutes=1)
            processed.clear()
            print(f"  ▶️  S20.12 enabled — reset start → {current_start.strftime('%H:%M')}")
            _save_state(current_start)
        was_enabled = True

        print(f"  ▶ run_sim --start {current_start.strftime('%d-%m-%Y %H:%M')} --tf {args.tf}")

        # ── 1. รัน simulation โดยตรง (ไม่มี subprocess) ──────────────
        df = run_sim(symbol, current_start, end_dt_bkk=None, tf=args.tf, compound=args.compound)

        if df is None or df.empty:
            print("  ⚠️ run_sim ไม่มี trade — รอรอบหน้า")
            _sleep_until_next_01()
            continue

        import pandas as pd
        df["Time (BKK)"] = pd.to_datetime(df["Time (BKK)"])
        df["Close Time"] = pd.to_datetime(df["Close Time"])

        # ── 2. ดึง open positions ─────────────────────────────────────
        positions = mt5.positions_get(symbol=symbol) or []

        # ── 3. หา SIM order ที่ควรปิดแล้ว ────────────────────────────
        due = df[df["Close Time"] <= now]
        for _, row in due.iterrows():
            key = (str(row["Time (BKK)"]), row["Type"])
            if key in processed:
                continue

            sim_open  = row["Time (BKK)"].to_pydatetime()
            sim_close = row["Close Time"].to_pydatetime()
            sim_type  = row["Type"]
            reason    = row.get("Reason", "")

            print(f"  📋 SIM {sim_type} open={sim_open.strftime('%H:%M')} "
                  f"close={sim_close.strftime('%H:%M')} [{reason}]")

            if reason == "SL":
                print(f"     → SIM ปิดด้วย SL — ให้ MT5 จัดการ SL เอง (ไม่ force-close)")
                processed.add(key)
                continue

            pos = find_open_position(sim_type, sim_open, symbol, positions)
            if pos is None:
                print(f"     → ไม่มี open position ที่ match (MT5 ปิดไปแล้ว หรือ live ไม่มี order นี้)")
            else:
                print(f"     → พบ ticket={pos.ticket} ยังเปิดอยู่ — force-close ทันที")
                close_position(pos, symbol)
                positions = mt5.positions_get(symbol=symbol) or []

            processed.add(key)

        # ── 4. ขยับ current_start และบันทึก state ───────────────────────
        pending = df[df["Close Time"] > now]
        if not pending.empty:
            earliest_open = pending["Time (BKK)"].min().to_pydatetime()
            next_start    = earliest_open - timedelta(minutes=1)
            if next_start > current_start:
                print(f"  ⏩ ขยับ --start: {current_start.strftime('%H:%M')} → "
                      f"{next_start.strftime('%H:%M')} "
                      f"(next SIM open={earliest_open.strftime('%H:%M')})")
                current_start = next_start
                _save_state(current_start)
        else:
            print(f"  ℹ️  ไม่มี pending SIM order — คง --start ไว้เดิม")

        _sleep_until_next_01()


if __name__ == "__main__":
    main()
