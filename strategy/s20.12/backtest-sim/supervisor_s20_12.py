"""
supervisor_s20_12.py — S20.12 Live Supervisor

รันทุกวินาทีที่ :01 ของแต่ละนาที (sync กับขอบนาที):
  1. เรียก run_sim() โดยตรง (MT5 connection เดิม ไม่มี subprocess overhead)
  2. โหลด SIM trades ที่ได้จาก run_sim
  3. หา order ที่ SIM_Close <= now และยังไม่ได้ประมวลผล
  4. ถ้า MT5 position ยังเปิดอยู่ → force-close ทันที
  5. ขยับ current_start = earliest pending SIM_Open ที่มี MT5 position จริงให้ตามอยู่
  6. Sleep จนถึง :01 ของนาทีถัดไป

รัน:
  python strategy/s20.12/backtest-sim/supervisor_s20_12.py --start "03-07-2026 12:04" --compound 2
"""

import argparse
import sys
import os
import time
import re
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
LOG_FILE       = os.path.join(config.PROFILE_DIR, "logs", "s20_12_supervisor.log")


class _Tee:
    def __init__(self, *streams):
        self.streams = streams

    def write(self, data):
        for stream in self.streams:
            stream.write(data)
            stream.flush()

    def flush(self):
        for stream in self.streams:
            stream.flush()


def _install_log_tee():
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    log = open(LOG_FILE, "a", encoding="utf-8", buffering=1)
    sys.stdout = _Tee(sys.stdout, log)
    sys.stderr = _Tee(sys.stderr, log)


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


def _sleep_until_first_cycle(start_dt: datetime):
    """First cycle ต้องไม่เร็วกว่า start_dt:01 เพื่อกัน start กลางนาทีแล้วยิงก่อนรอบที่ตั้งใจ"""
    target = start_dt.replace(second=1, microsecond=0)
    now = datetime.now()
    if target <= now:
        _sleep_until_next_01()
        return
    wait = (target - now).total_seconds()
    print(f"  💤 รอเริ่มรอบแรก {target.strftime('%H:%M:%S')} ({wait:.0f}s)")
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
    # Position timestamps are historical. Do not call config.mt5_ts_to_bkk()
    # here because it refreshes the live MT5 timezone cache from the supplied
    # timestamp; old open times can drift the long-running supervisor by +1h.
    mt5_server_tz = 1  # IUX MT5 server time confirmed in this repo/profile.
    return (
        datetime.fromtimestamp(int(ts), tz=timezone.utc)
        + timedelta(hours=config.TZ_OFFSET - mt5_server_tz)
    ).replace(tzinfo=None)


def _comment_tf(comment: str) -> str:
    m = re.match(r"^(\[[\w-]+\]|M\d+|H\d+|D\d+)", str(comment or ""))
    return m.group(1) if m else ""


def _is_s20_12_comment(comment: str, sim_tf: str = "") -> tuple[bool, str]:
    comment = str(comment or "")
    tf = _comment_tf(comment)
    tf_ok = not sim_tf or tf == sim_tf
    if "20.12" in comment and tf_ok:
        return True, "exact"
    # Fallback for comments/metadata that may be parsed or truncated as S20.
    # Keep it TF-gated so plain S20 on another TF cannot be matched accidentally.
    if tf_ok and re.search(r"_S20(?:\b|_)", comment):
        return True, "tf_s20_fallback"
    return False, ""


def _to_float(value):
    try:
        if value is None or value == "":
            return None
        return float(value)
    except Exception:
        return None


def _price_close(actual, expected, tol: float = 0.08) -> bool:
    expected = _to_float(expected)
    if expected is None:
        return True
    try:
        return abs(float(actual) - expected) <= tol
    except Exception:
        return False


def _sim_prices_match(pos, sim_sl=None, sim_tp=None) -> bool:
    return _price_close(getattr(pos, "sl", None), sim_sl) and _price_close(getattr(pos, "tp", None), sim_tp)


def find_open_position(
    sim_type: str,
    sim_open: datetime,
    symbol: str,
    positions,
    sim_tf: str = "",
    sim_sl=None,
    sim_tp=None,
):
    """Find the live S20.12 position matching a SIM row."""
    want_type = mt5.POSITION_TYPE_BUY if sim_type == "BUY" else mt5.POSITION_TYPE_SELL
    for pos in positions:
        if pos.symbol != symbol:
            continue
        if pos.type != want_type:
            continue
        if _hhmm(_mt5_to_bkk_naive(pos.time)) != _hhmm(sim_open):
            continue
        if not _sim_prices_match(pos, sim_sl, sim_tp):
            continue
        comment = getattr(pos, "comment", "") or ""
        ok, mode = _is_s20_12_comment(comment, sim_tf)
        if ok:
            if mode != "exact":
                print(
                    f"     match fallback ticket={pos.ticket} comment={comment!r} "
                    f"sim_tf={sim_tf or '-'} open={sim_open.strftime('%H:%M')} "
                    f"sl={getattr(pos, 'sl', 0)} tp={getattr(pos, 'tp', 0)}"
            )
            return pos
    return None


def wait_for_open_position(
    sim_type: str,
    sim_open: datetime,
    sim_close: datetime,
    symbol: str,
    sim_tf: str = "",
    sim_sl=None,
    sim_tp=None,
    deadline_sec: int = 6,
):
    """Poll briefly for just-filled positions when SIM closes in the same minute."""
    deadline = sim_close + timedelta(seconds=deadline_sec)
    last_positions = mt5.positions_get(symbol=symbol) or []
    pos = find_open_position(sim_type, sim_open, symbol, last_positions, sim_tf, sim_sl, sim_tp)
    if pos is not None:
        return pos, last_positions

    now = datetime.now()
    if now >= deadline:
        return None, last_positions

    print(f"     wait fill-match until {deadline.strftime('%H:%M:%S')} (tf/type/sl/tp)")
    while datetime.now() < deadline:
        time.sleep(0.5)
        last_positions = mt5.positions_get(symbol=symbol) or []
        pos = find_open_position(sim_type, sim_open, symbol, last_positions, sim_tf, sim_sl, sim_tp)
        if pos is not None:
            print(f"     delayed match ticket={pos.ticket} at {datetime.now().strftime('%H:%M:%S')}")
            return pos, last_positions
    return None, last_positions


def _live_s20_12_positions(symbol: str, positions):
    live = []
    for pos in positions:
        if pos.symbol != symbol:
            continue
        comment = getattr(pos, "comment", "") or ""
        if comment.startswith(("H12_S20.12", "D1_S20.12")):
            continue
        if "20.12" in comment:
            live.append(pos)
    return live


def _earliest_live_s20_12_open(symbol: str, positions):
    live = _live_s20_12_positions(symbol, positions)
    if not live:
        return None, None
    pos = min(live, key=lambda p: _mt5_to_bkk_naive(p.time))
    return _mt5_to_bkk_naive(pos.time).replace(second=0, microsecond=0), pos.ticket


def close_position(pos, symbol: str, reason: str = "") -> bool:
    """Force-close MT5 position ด้วย market order"""
    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        print(f"     ❌ ดึง tick ไม่ได้ — ข้าม position {pos.ticket}")
        return False

    close_type = mt5.ORDER_TYPE_SELL if pos.type == mt5.POSITION_TYPE_BUY else mt5.ORDER_TYPE_BUY
    price      = tick.bid if pos.type == mt5.POSITION_TYPE_BUY else tick.ask
    symbol_info = mt5.symbol_info(symbol)

    filling_modes = []
    for mode in (
        getattr(symbol_info, "filling_mode", None),
        mt5.ORDER_FILLING_IOC,
        mt5.ORDER_FILLING_FOK,
        mt5.ORDER_FILLING_RETURN,
    ):
        if mode is not None and mode not in filling_modes:
            filling_modes.append(mode)

    request = {
        "action":       mt5.TRADE_ACTION_DEAL,
        "symbol":       symbol,
        "volume":       pos.volume,
        "type":         close_type,
        "position":     pos.ticket,
        "price":        price,
        "deviation":    30,
        "magic":        0,
        "comment":      f"S20.12_supervisor_{reason}"[:31] if reason else "S20.12_supervisor",
        "type_time":    mt5.ORDER_TIME_GTC,
    }

    attempts = [(mode, {**request, "type_filling": mode}) for mode in filling_modes]
    attempts.append((None, dict(request)))
    for mode, req in attempts:
        result = mt5.order_send(req)
        if result and result.retcode == mt5.TRADE_RETCODE_DONE:
            mode_label = "default" if mode is None else str(mode)
            print(f"     close success ticket={pos.ticket} filling={mode_label}")
            return True
        retcode = result.retcode if result else "N/A"
        print(f"     close attempt failed ticket={pos.ticket} filling={mode} retcode={retcode}")

    result = mt5.order_send(request)
    if result and result.retcode == mt5.TRADE_RETCODE_DONE:
        print(f"     ✅ ปิด ticket={pos.ticket} สำเร็จ")
        return True
    retcode = result.retcode if result else "N/A"
    print(f"     ❌ ปิดล้มเหลว ticket={pos.ticket} retcode={retcode}")
    return False


def main():
    _install_log_tee()
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

    # รอจนถึง start_dt:01 ก่อน cycle แรก
    # ป้องกันกรณีรัน bat 12:00 แต่ตั้ง start=12:02 → ต้องเริ่มรอบแรก 12:02:01
    _sleep_until_first_cycle(current_start)

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
        positions = mt5.positions_get(symbol=symbol) or []
        live_anchor, live_ticket = _earliest_live_s20_12_open(symbol, positions)
        if live_anchor is not None and live_anchor < current_start:
            print(f"  ANCHOR live S20.12 ticket={live_ticket} open={live_anchor.strftime('%H:%M')} "
                  f"-> rewind --start from {current_start.strftime('%H:%M')}")
            current_start = live_anchor
            _save_state(current_start)
            print(f"  RUN_AGAIN run_sim --start {current_start.strftime('%d-%m-%Y %H:%M')} --tf {args.tf}")

        df = run_sim(symbol, current_start, end_dt_bkk=None, tf=args.tf, compound=args.compound)

        if df is None or df.empty:
            positions = mt5.positions_get(symbol=symbol) or []
            live_anchor, live_ticket = _earliest_live_s20_12_open(symbol, positions)
            if live_anchor is not None:
                if live_anchor != current_start:
                    print(f"  ANCHOR run_sim empty but live S20.12 ticket={live_ticket} "
                          f"-> keep --start at {live_anchor.strftime('%H:%M')}")
                    current_start = live_anchor
                    _save_state(current_start)
                else:
                    print(f"  ANCHOR run_sim empty but live S20.12 ticket={live_ticket} "
                          f"-> keep --start {current_start.strftime('%H:%M')}")
                _sleep_until_next_01()
                continue
            current_start = now.replace(second=0, microsecond=0)
            _save_state(current_start)
            print(f"  ⚠️ run_sim ไม่มี trade — ขยับ --start ไป {current_start.strftime('%H:%M')}")
            _sleep_until_next_01()
            continue

        import pandas as pd
        df["Time (BKK)"] = pd.to_datetime(df["Time (BKK)"])
        df["Close Time"] = pd.to_datetime(df["Close Time"])

        # ── 2. ดึง open positions ─────────────────────────────────────
        positions = mt5.positions_get(symbol=symbol) or []

        # ── 3. หา SIM order ที่ควรปิดแล้ว ────────────────────────────
        due = df[df["Close Time"] <= now]
        unmatched_due_anchors = []
        for _, row in due.iterrows():
            sim_tf = str(row.get("TF", "") or "")
            key = (sim_tf, str(row["Time (BKK)"]), row["Type"])
            if key in processed:
                continue

            sim_open  = row["Time (BKK)"].to_pydatetime()
            sim_close = row["Close Time"].to_pydatetime()
            sim_type  = row["Type"]
            reason    = row.get("Reason", "")
            sim_sl     = row.get("SL", None)
            sim_tp     = row.get("TP", None)

            print(f"  📋 SIM {sim_type} open={sim_open.strftime('%H:%M')} "
                  f"close={sim_close.strftime('%H:%M')} [{reason}]")

            reason_norm = str(reason).strip().upper()
            if reason_norm == "SL":
                print("     → SIM ปิดด้วย SL — ให้ MT5/broker จัดการ SL เอง (ไม่ force-close)")
                processed.add(key)
                continue

            pos = find_open_position(sim_type, sim_open, symbol, positions, sim_tf, sim_sl, sim_tp)
            if pos is None:
                pos, positions = wait_for_open_position(
                    sim_type, sim_open, sim_close, symbol, sim_tf, sim_sl, sim_tp
                )
            if pos is None:
                if (datetime.now() - sim_close).total_seconds() <= 90:
                    print("     → ยังไม่เจอ match แต่ SIM เพิ่ง close — ไม่ mark processed, จะ keep --start ไว้ retry")
                    unmatched_due_anchors.append(sim_open)
                else:
                    print(f"     → ไม่มี open position ที่ match (MT5 ปิดไปแล้ว หรือ live ไม่มี order นี้)")
                    processed.add(key)
            else:
                print(f"     → พบ ticket={pos.ticket} ยังเปิดอยู่ — force-close ทันทีตาม SIM reason={reason_norm}")
                if close_position(pos, symbol, reason_norm):
                    processed.add(key)
                    positions = mt5.positions_get(symbol=symbol) or []
                else:
                    print("     → close fail — จะ retry รอบถัดไป")

        # ── 4. ขยับ current_start และบันทึก state ───────────────────────
        # ใช้เฉพาะ pending SIM ที่มี live position match อยู่จริงเท่านั้น
        # ไม่ให้ SIM-only order ที่ live ไม่ได้เปิด ลาก --start ให้ย้อนรันข้อมูลเก่าเรื่อย ๆ
        positions = mt5.positions_get(symbol=symbol) or []
        live_anchor, live_ticket = _earliest_live_s20_12_open(symbol, positions)

        pending = df[df["Close Time"] > now]
        tracked_pending = []
        for _, row in pending.iterrows():
            sim_open = row["Time (BKK)"].to_pydatetime()
            sim_type = row["Type"]
            sim_tf = str(row.get("TF", "") or "")
            pos = find_open_position(
                sim_type, sim_open, symbol, positions, sim_tf, row.get("SL", None), row.get("TP", None)
            )
            if pos is None:
                print(f"  ↪ pending SIM open={sim_open.strftime('%H:%M')} {sim_type} ไม่มี live position match — ไม่ใช้ลาก --start")
                continue
            tracked_pending.append((sim_open, pos.ticket))

        if tracked_pending:
            earliest_open, ticket = min(tracked_pending, key=lambda item: item[0])
            next_start = min(earliest_open, live_anchor) if live_anchor is not None else earliest_open
            if next_start > current_start:
                print(f"  ⏩ ขยับ --start: {current_start.strftime('%H:%M')} → "
                      f"{next_start.strftime('%H:%M')} "
                      f"(tracked pending ticket={ticket})")
                current_start = next_start
                _save_state(current_start)
            elif live_anchor is not None and live_anchor < current_start:
                print(f"  ANCHOR live S20.12 ticket={live_ticket} still open "
                      f"-> rewind --start to {live_anchor.strftime('%H:%M')}")
                current_start = live_anchor
                _save_state(current_start)
        elif unmatched_due_anchors:
            retry_start = min(unmatched_due_anchors).replace(second=0, microsecond=0)
            if retry_start != current_start:
                print(f"  ANCHOR unmatched fresh SIM close -> keep --start at {retry_start.strftime('%H:%M')}")
                current_start = retry_start
                _save_state(current_start)
            else:
                print(f"  ANCHOR unmatched fresh SIM close -> keep --start {current_start.strftime('%H:%M')}")
        else:
            next_start = live_anchor if live_anchor is not None else now.replace(second=0, microsecond=0)
            if next_start > current_start:
                print(f"  ℹ️  ไม่มี pending SIM ที่มี live match — ขยับ --start: {current_start.strftime('%H:%M')} → {next_start.strftime('%H:%M')}")
                current_start = next_start
                _save_state(current_start)
            elif next_start < current_start:
                print(f"  ANCHOR live S20.12 ticket={live_ticket} still open "
                      f"-> rewind --start to {next_start.strftime('%H:%M')}")
                current_start = next_start
                _save_state(current_start)
            else:
                print(f"  ℹ️  ไม่มี pending SIM ที่มี live match — คง --start ไว้เดิม")

        _sleep_until_next_01()


if __name__ == "__main__":
    main()
