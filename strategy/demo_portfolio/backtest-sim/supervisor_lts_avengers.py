"""
supervisor_lts_avengers.py — LTS_AUS3 / LTS_AHR3 Live Order Supervisor (backtest-driven)

แนวคิดเดียวกับ strategy/s20.12/backtest-sim/supervisor_s20_12.py (รัน backtest จริง
ทุกรอบ แล้วเอาผลมาสั่ง order สด) แต่ต่างกันตรงจุดสำคัญ 2 อย่าง:

  1. S20.12 มี scanner หลัก (scanner.py, ทุก 5 วิ) คอยเข้า order เองอยู่แล้ว —
     supervisor_s20_12.py แค่คอย "force-close" ให้ตรงกับที่ backtest บอกว่าควรปิดแล้ว
     ส่วนตัวนี้ **ต้องเข้า order เองด้วย** เพราะ LTS_AUS3/LTS_AHR3 ไม่มี generic scanner
     คอยเข้า order ให้ — ของเดิม (demo_scan_lts_tf_aligned ใน main.py/demo_portfolio.py
     ที่ทำไว้เมื่อวาน) ถูกปิดไปแล้ว แทนที่ด้วยตัวนี้ทั้งหมด (ตามที่พี่เลือก "แทนที่")

  2. ไม่ต้อง force-close เลย เพราะ order ของ LTS ตั้ง SL/TP จริงติดกับ order บน broker
     อยู่แล้ว (mt5.order_send ใส่ sl/tp ไปตรงๆ) broker จะปิดเองเมื่อราคาถึง — ต่างจาก
     บาง sub-pattern ของ S20.12 ที่ต้องมีซอฟต์แวร์คอยปิดเอง

หลักการทำงาน:
  1. รันทุก 15 นาที ตรง :00:01 / :15:01 / :30:01 / :45:01 (BKK) — sync กับแท่ง M15
     (TF ที่ละเอียดสุดที่ AUS3/AHR3 ใช้ — M30/H1 คำนวณซ้ำได้แต่ผลจะไม่เปลี่ยนจนกว่า
     แท่งของมันเองจะปิด ไม่มีผลเสีย แค่คำนวณเกินไปเฉยๆ)
  2. เรียก run_lts_af_backtest(portfolio, days, start_str=current_start, end_str=None,
     apply_circuit_breaker=False) ตรงๆ — ฟังก์ชันเดียวกับที่ CLI backtest ใช้ (ไม่มี
     logic แยกใหม่) ปิด circuit breaker เพราะรันช่วงสั้น (ไม่เห็นประวัติเต็มของ leg)
     จะทำให้จำลอง "แพ้ติดกัน 3 ไม้" ผิดพลาด (นับจากศูนย์ทุกรอบ) — ตามที่พี่เลือกไว้
  3. เทียบผลลัพธ์กับ position ที่เปิดอยู่จริงใน MT5 (แยกด้วย magic + leg key ใน comment)
     - เจอ signal ใหม่ที่ยังไม่มี position ตรงกัน และยัง "สด" พอ (ไม่เกิน
       STALE_ENTRY_SEC วินาทีจาก fill_time_ts) → เข้า order จริงด้วย SL/TP จาก backtest
       ผ่าน dp._af_order_volume()/_place_market_order() — ฟังก์ชันเดียวกับที่ live
       ปกติใช้ (ได้ dynamic lot / weight scaling / safety-skip ใกล้ TP ติดมาด้วยเลย)
     - signal ที่เก่าเกินไป (สายเกินจะเข้าจริง) → ข้าม ไม่เข้า แค่บันทึกว่า "จัดการแล้ว"
  4. เก็บ state (ไม้ที่เข้าไปแล้ว/ข้ามไปแล้ว) ลงไฟล์กัน entry ซ้ำตอน restart
  5. ขยับ current_start ไปข้างหน้าเท่าที่ signal ทุกตัวก่อนจุดนั้น "จัดการแล้ว" ครบ —
     ลดช่วงเวลาที่ fetch_bars_range ต้องดึงย้อนหลังทุกรอบ (แต่ยังมี extra_bars=700
     สำหรับ warmup indicator เป็นค่าพื้นฐานเสมอ ลดได้แค่ช่วง "signal window" ไม่ใช่
     ทั้งหมด — ดู docstring ของ fetch_bars_range)

รัน (ต้องรันแยก 2 process ถ้าจะทำทั้ง AUS3 และ AHR3):
  python strategy/demo_portfolio/backtest-sim/supervisor_lts_avengers.py --portfolio LTS_AUS3 --start "29-08-2026 10:15"
  python strategy/demo_portfolio/backtest-sim/supervisor_lts_avengers.py --portfolio LTS_AHR3 --start "29-08-2026 10:15"
"""

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta

script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, script_dir)
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(script_dir)))
sys.path.insert(0, root_dir)

import MetaTrader5 as mt5  # noqa: E402
import config  # noqa: E402
import demo_portfolio as dp  # noqa: E402
import run_backtest_sim as rbs  # noqa: E402

STATE_FMT = "%d-%m-%Y %H:%M"
STALE_ENTRY_SEC = 20 * 60  # signal เก่ากว่านี้ (นับจาก fill_time_ts) ไม่เข้าจริง แค่ mark processed
BACKTEST_DAYS_FALLBACK = 30  # ใช้ตอน current_start หายจาก state (ไม่เคยรันมาก่อน)


def _state_paths(portfolio_name: str, profile_dir: str):
    """profile_dir ต้องมาจาก rbs.setup_mt5_for_portfolio() ที่ resolve แล้ว ไม่ใช่
    config.PROFILE_DIR เฉยๆ — เพราะ config.PROFILE_DIR ผูกกับ BOT_PROFILE ตอน import
    module (อาจไม่ตรงกับ profile จริงของพอร์ตนี้ถ้ารันสคริปต์นี้แบบ standalone)"""
    tag = portfolio_name.replace("/", "_")
    state_file = os.path.join(profile_dir, f".supervisor_lts_{tag}_state.json")
    log_file = os.path.join(profile_dir, "logs", f"lts_{tag}_supervisor.log")
    return state_file, log_file


class _Tee:
    def __init__(self, *streams):
        self.streams = streams

    def write(self, data):
        for s in self.streams:
            s.write(data)
            s.flush()

    def flush(self):
        for s in self.streams:
            s.flush()


def _install_log_tee(log_file: str):
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    log = open(log_file, "a", encoding="utf-8", buffering=1)
    sys.stdout = _Tee(sys.stdout, log)
    sys.stderr = _Tee(sys.stderr, log)


def _load_state(state_file: str, fallback_start: datetime):
    if os.path.exists(state_file):
        try:
            with open(state_file, encoding="utf-8") as f:
                d = json.load(f)
            current_start = datetime.strptime(d["current_start"], STATE_FMT)
            processed = set(tuple(x) for x in d.get("processed", []))
            print(f"📂 Resume จาก state: start={current_start.strftime(STATE_FMT)} processed={len(processed)}")
            return current_start, processed
        except Exception as e:
            print(f"⚠️ อ่าน state ไม่ได้ ({e}) — เริ่มใหม่จาก fallback")
    return fallback_start, set()


def _save_state(state_file: str, current_start: datetime, processed: set):
    # เก็บแค่ processed ล่าสุด กันไฟล์บวมไม่จำกัด (leg ที่จัดการไปนานแล้วไม่ต้องจำอีก
    # เพราะ current_start ขยับผ่านไปแล้ว ไม่มีทางเจอ fill_time_ts เก่ากว่านั้นซ้ำ)
    cutoff = current_start - timedelta(days=1)
    cutoff_ts = int(cutoff.timestamp())
    trimmed = {p for p in processed if p[1] >= cutoff_ts}
    with open(state_file, "w", encoding="utf-8") as f:
        json.dump({
            "current_start": current_start.strftime(STATE_FMT),
            "processed": [list(p) for p in trimmed],
        }, f)
    return trimmed


def _sleep_until_next_quarter():
    """Sleep จนถึงวินาทีที่ :01 ของ :00/:15/:30/:45 ถัดไป (BKK wall clock ของเครื่อง)"""
    now = datetime.now()
    minute_block = (now.minute // 15 + 1) * 15
    if minute_block >= 60:
        target = (now.replace(minute=0, second=1, microsecond=0) + timedelta(hours=1))
    else:
        target = now.replace(minute=minute_block, second=1, microsecond=0)
    wait = (target - now).total_seconds()
    while wait <= 0:
        target += timedelta(minutes=15)
        wait = (target - datetime.now()).total_seconds()
    print(f"  💤 รอจนถึง {target.strftime('%H:%M:%S')} ({wait:.0f}s)")
    time.sleep(wait)


def _is_portfolio_active_via_telegram(profile_dir: str, portfolio_name: str) -> bool:
    """อ่าน bot_state.json สดใหม่ทุกครั้ง (ไม่ cache) เพื่อเช็คว่าพี่กดปุ่ม "🤖 LTS Supervisor"
    ผ่าน Telegram (handlers/btn_demo_portfolio.py + callback_handler.py:"lts_supervisor_toggle")
    ไว้ยังไงล่าสุด — เจอ 2026-08-31: ตอนแรกลองใช้ปุ่ม DEMO_PORTFOLIO_ACTIVE เดิม (ที่คุม
    regular scan ของ main.py) ร่วมกัน แต่พี่ชี้ว่าถ้าเปิดปุ่มนั้นกลับ regular scan (มี
    hour-skip bug ที่ supervisor ตัวนี้แก้แล้ว) จะกลับมาทำงานคู่ขนานกับ supervisor พร้อมกัน
    เข้า order ซ้ำซ้อนกันได้ — แยก flag ใหม่ (config.LTS_SUPERVISOR_ACTIVE / bot_state.json
    key "lts_supervisor_active") ให้คุมเฉพาะ supervisor ตัวนี้เท่านั้น
    อ่านไฟล์ตรงๆ สดใหม่ทุกรอบ (ไม่ใช่ config module ที่ import ค้างไว้ตอน process เริ่ม)
    เพราะ supervisor รันคนละ process กับ main.py ไม่เห็นการเปลี่ยนแปลงใน memory ของอีกฝั่ง
    อ่านไม่ได้/ไฟล์เสีย = คืน False (fail-closed ปลอดภัยกว่า ไม่เทรดถ้าไม่แน่ใจ)"""
    state_file = os.path.join(profile_dir, "bot_state.json")
    try:
        with open(state_file, encoding="utf-8") as f:
            state = json.load(f)
        return bool(state.get("lts_supervisor_active", {}).get(portfolio_name, False))
    except Exception:
        return False


def _leg_key_from_comment(comment: str):
    """ดึง leg key (เช่น 'LTS_AUS3_643') จาก comment ของ order/position จริง"""
    m = re.search(r"(LTS_[A-Z0-9]+_\d+)", str(comment or ""))
    return m.group(1) if m else None


def _find_live_position(magic: int, leg_key: str, side: str, fill_dt: datetime, positions,
                         sl: float = None, tp: float = None, tol_min: int = 320, price_tol: float = 1.0):
    # เจอ 2026-09-01: tol_min เดิม 45 นาทีไม่พอสำหรับ S9x ที่เปลี่ยนไปวาง pending limit order
    # แล้วรอ broker fill เอง (รอได้นานสุด S9X_PENDING_MAX_BARS=5 แท่ง — H1 คือ 300 นาที) ถ้า
    # tol_min แคบไป พอ fill ช้ากว่านั้นจะ match live position ไม่เจอ เข้าใจผิดว่ายังไม่เคยเข้า
    # แล้ววาง pending order ซ้ำอีกอัน — ขยายเป็น 320 นาที (300 + กันชน 20) ครอบคลุมทุก TF
    #
    # เจอ 2026-09-08: tol_min=320 กว้างเกินไปสำหรับ leg ที่ยิงสัญญาณถี่ (เช่น M30
    # trend-following อย่าง LTS_AUS3_646 ที่ยิงได้ทุก 30-90 นาที) — สัญญาณคนละตัวที่เกิดห่างกัน
    # ไม่ถึง 320 นาที (แต่ entry/sl/tp ต่างกันจริง) ถูกกลืนเป็น "position เดิม" ผิดๆ ทำให้ข้าม
    # ไม่เข้า order ที่ควรเข้าจริง (ยืนยันแล้ว: leg 646 วันที่ 4/9 พลาดไป 7/10 สัญญาณที่ backtest
    # ยืนยันว่ากำไรทุกตัว) — เพิ่มเช็ค sl/tp ต้องใกล้เคียงกันด้วย (anchor_sl_tp=True ทำให้ position
    # ที่ตรงกับ backtest signal นี้จริงๆต้อง sl/tp ตรงกันแทบเป๊ะ ต่างจากสัญญาณอื่นที่ sl/tp ห่าง
    # กันหลายจุดเสมอ — ไม่ใช้แค่ entry เพราะสัญญาณ trend ต่อเนื่องบางคู่ entry ใกล้กันได้แค่ 1-3
    # จุด แต่ sl/tp ต่างกันชัดเจนกว่ามาก จึงแยกแยะได้แม่นกว่า)
    want_type = mt5.POSITION_TYPE_BUY if side == "BUY" else mt5.POSITION_TYPE_SELL
    for pos in positions:
        if pos.magic != magic or pos.type != want_type:
            continue
        if _leg_key_from_comment(pos.comment) != leg_key:
            continue
        pos_dt = datetime.fromtimestamp(pos.time)
        if abs((pos_dt - fill_dt).total_seconds()) > tol_min * 60:
            continue
        if sl is not None and abs(float(pos.sl) - float(sl)) > price_tol:
            continue
        if tp is not None and abs(float(pos.tp) - float(tp)) > price_tol:
            continue
        return pos
    return None


_TF_MINUTES = {"M1": 1, "M5": 5, "M15": 15, "M30": 30, "H1": 60, "H4": 240, "D1": 1440}


def _tf_minutes(tf_str: str) -> int:
    return _TF_MINUTES.get(tf_str, 15)


def _find_pending_order(magic: int, leg_key: str, side: str, orders):
    """หา pending limit order ที่ยังค้างอยู่ของ leg+side นี้ (ไม่เช็ค tolerance เวลา เพราะ
    ออกแบบให้มีได้สูงสุด 1 pending order ต่อ leg+side ในแต่ละช่วงเวลาอยู่แล้ว — กันซ้ำผ่าน
    dedup ของ processed/live_pos ก่อนถึงจุดนี้)"""
    want_type = mt5.ORDER_TYPE_BUY_LIMIT if side == "BUY" else mt5.ORDER_TYPE_SELL_LIMIT
    for o in orders:
        if o.magic != magic or o.type != want_type:
            continue
        if _leg_key_from_comment(o.comment) != leg_key:
            continue
        return o
    return None


def _sweep_stale_pending_orders(magic: int, orders):
    """กวาดยกเลิก pending limit order ของ S9x leg ทุกใบที่ "กำพร้า" — เจอจริง 2026-09-10:
    การเช็คหมดอายุเดิม (ในลูปหลัก ผ่าน _find_pending_order) ทำงานเฉพาะตอนมีสัญญาณของ leg+side
    เดียวกันเกิดซ้ำเท่านั้น (_find_pending_order กรองด้วย order type ตรงกับ side ปัจจุบัน) พอ
    leg กลับทิศ (เช่น BUY→SELL) order เก่าฝั่งตรงข้ามจะไม่ถูกเจอ/ไม่ถูกเช็คหมดอายุอีกเลยตลอดไป
    (ยืนยันจริง: ticket 3792454251/3792454254 ของ AUS3 leg 644/646 และ 5072565909 ของ AHR3
    leg 667 ค้างแบบนี้ — วางตอน 07:30 แล้ว leg กลับทิศเป็น SELL ตอน 08:15-08:30 โดยไม่มีการ
    ยกเลิก order BUY เดิมเลย) _place_limit_order ตั้ง GTC ไม่มี broker-side expiration เอง
    (ดู docstring) — ถ้าไม่กวาดเชิงรุก order จะค้างจนกว่าราคาจะย้อนมาแตะเอง (อาจนานมาก/ไม่มี
    วันเกิด) ที่ระดับราคา/sl/tp ที่ไม่สัมพันธ์กับตลาดปัจจุบันแล้ว — simulate 550 วัน (AUS3)
    พบว่าเฉลี่ยเป็นบวก (+52,735 จาก 587 ไม้) แต่มี tail risk ไม้เดียวขาดทุน -23,165 (ใหญ่กว่า
    ไม้อื่นมาก) จึงยกเลิกเชิงรุกแทนที่จะปล่อยพนันเอง — ใช้เกณฑ์ max_wait เดิมเป๊ะ
    (S9X_PENDING_MAX_BARS แท่งของ TF leg นั้น) เหมือนที่ per-signal loop ใช้อยู่แล้ว แค่ทำให้
    ทุก pending order ถูกเช็คทุกรอบแน่นอน ไม่ขึ้นกับว่าจะมีสัญญาณฝั่งเดิมมาซ้ำหรือเปล่า"""
    now_ts = time.time()
    for o in orders:
        if o.magic != magic:
            continue
        if o.type not in (mt5.ORDER_TYPE_BUY_LIMIT, mt5.ORDER_TYPE_SELL_LIMIT):
            continue
        leg_key = _leg_key_from_comment(o.comment)
        if leg_key is None:
            continue
        af_def = dp.AF_DEFS.get(leg_key)
        if af_def is None or not af_def.get("is_s9x"):
            continue
        tf = af_def["cfg"]["ENTRY_TF"]
        max_wait_sec = dp.S9X_PENDING_MAX_BARS * _tf_minutes(tf) * 60
        pending_age_sec = now_ts - o.time_setup
        if pending_age_sec > max_wait_sec:
            print(f"  🧹 {leg_key} ticket={o.ticket} pending limit order ค้างเกิน {max_wait_sec}s "
                  f"({pending_age_sec:.0f}s) — sweep ยกเลิก (กัน order กำพร้าจาก leg กลับทิศ)")
            dp._cancel_pending_order(o.ticket)


def _place_s9x_limit_entry(portfolio_name: str, leg_key: str, trade: dict, entry_level: float) -> bool:
    """วาง pending limit order จริงที่ broker สำหรับ S9x leg ที่ราคายังไม่ถึงเงื่อนไข entry±spread
    — แทนที่จะ poll ราคาทุก 15 นาทีแล้วค่อยยิง market order (ช้ากว่า+ราคาคลาดเคลื่อนกว่า)
    broker จะ fill ให้เองทันทีที่ราคาแตะ entry_level เป๊ะ (เจอจริง 2026-09-01: backtest เองก็
    ใช้กรอบ fill-check ~5 แท่งเหมือนกัน (ดู run_s9x_generic._resolve) — วิธีนี้เลยตรงกับที่
    backtest ตัดสิน fillable/ไม่ fillable มากกว่า poll แบบเดิมด้วย)"""
    af_def = dp.AF_DEFS.get(leg_key)
    if af_def is None:
        print(f"     ⚠️ ไม่พบ leg definition สำหรับ {leg_key} ใน AF_DEFS — ข้าม")
        return False

    magic = dp._portfolio_magic(portfolio_name)
    entry_tf = trade["tf"]
    sig = trade["signal"]
    sl = float(trade["sl"])
    tp = float(trade["tp"])

    volume, volume_meta = dp._af_order_volume(af_def, portfolio_name, tf=entry_tf, signal=sig)
    if volume_meta.get("weighted") and volume_meta.get("weight", 1.0) <= 0.0:
        print(f"     ⏭️ {leg_key} weight=0 — ข้าม")
        return False

    comment = dp._demo_comment(leg_key, entry_tf)
    result = dp._place_limit_order(sig, entry_level, sl, tp, comment, magic, volume=volume)

    if result.get("success") and result.get("ticket"):
        print(f"     📌 วาง pending limit order {leg_key} {sig} lot={volume:.2f} "
              f"entry_level={entry_level:.2f} sl={sl:.2f} tp={tp:.2f} ticket={result['ticket']}")
        return True

    reason = result.get("error") or "unknown"
    print(f"     ❌ วาง pending order {leg_key} {sig} ไม่สำเร็จ: {reason}")
    return False


def _place_entry(portfolio_name: str, leg_key: str, trade: dict) -> bool:
    """เข้า order จริง 1 ไม้ ตามผลจาก backtest (trade) ของ leg_key นี้ — ใช้ฟังก์ชัน
    เดียวกับที่ demo_portfolio._demo_scan_af_ladder ใช้ปกติ (_af_order_volume,
    _place_market_order, _demo_comment) ให้พฤติกรรมเหมือน live เดิมทุกอย่าง
    (dynamic lot / weight scaling / safety-skip ใกล้ TP)"""
    af_def = dp.AF_DEFS.get(leg_key)
    if af_def is None:
        print(f"     ⚠️ ไม่พบ leg definition สำหรับ {leg_key} ใน AF_DEFS — ข้าม")
        return False

    magic = dp._portfolio_magic(portfolio_name)
    entry_tf = trade["tf"]
    sig = trade["signal"]
    sl = float(trade["sl"])
    tp = float(trade["tp"])
    original_entry = float(trade["entry"])

    volume, volume_meta = dp._af_order_volume(af_def, portfolio_name, tf=entry_tf, signal=sig)
    if volume_meta.get("weighted") and volume_meta.get("weight", 1.0) <= 0.0:
        print(f"     ⏭️ {leg_key} weight=0 — ข้าม")
        return False

    comment = dp._demo_comment(leg_key, entry_tf)
    result = dp._place_market_order(
        sig, sl, tp, comment, magic,
        volume=volume, original_entry=original_entry, anchor_sl_tp=True,
    )

    if result.get("success") and result.get("ticket"):
        try:
            from trailing import position_sid
            position_sid[result["ticket"]] = 21
        except Exception:
            pass
        print(f"     ✅ เข้า order {leg_key} {sig} lot={volume:.2f} entry={original_entry:.2f} "
              f"sl={sl:.2f} tp={tp:.2f} ticket={result['ticket']}")
        return True

    reason = result.get("error") or ("skipped" if result.get("skipped") else "unknown")
    print(f"     ❌ เข้า order {leg_key} {sig} ไม่สำเร็จ: {reason}")
    return False


def _force_close_position(position) -> bool:
    """ปิด position จริงทันทีด้วยราคาตลาดปัจจุบัน — ใช้ตอนเจอ mismatch: backtest ยืนยัน
    แล้วว่าไม้นี้โดน TP/SL ไปแล้ว (ดู docstring ของจุดเรียกใน main()) แต่ MT5 live position
    ยังเปิดค้างอยู่ — เป็น safety net เผื่อ broker ไม่ trigger SL/TP ให้ตามที่ควร (requote/
    margin/platform hang) ไม่รอ broker ปิดเอง"""
    symbol = position.symbol
    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        print(f"     ⚠️ ปิด order ticket={position.ticket} ไม่ได้ — อ่านราคาปัจจุบันไม่ได้")
        return False
    is_buy = position.type == mt5.POSITION_TYPE_BUY
    close_type = mt5.ORDER_TYPE_SELL if is_buy else mt5.ORDER_TYPE_BUY
    price = tick.bid if is_buy else tick.ask
    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "position": position.ticket,
        "symbol": symbol,
        "volume": position.volume,
        "type": close_type,
        "price": price,
        "deviation": 50,
        "magic": position.magic,
        "comment": "BT_CLOSED_FORCE",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    result = mt5.order_send(request)
    ok = result is not None and result.retcode == mt5.TRADE_RETCODE_DONE
    if ok:
        print(f"     🔒 ปิด ticket={position.ticket} สำเร็จที่ราคา {price} (สั่งปิดเอง)")
    else:
        rc = getattr(result, "retcode", None) if result is not None else None
        cm = getattr(result, "comment", None) if result is not None else None
        print(f"     ❌ ปิด ticket={position.ticket} ไม่สำเร็จ retcode={rc} comment={cm}")
    return ok


def main():
    parser = argparse.ArgumentParser(description="LTS_AUS3/LTS_AHR3 Live Supervisor — เข้า order ตาม backtest จริง")
    parser.add_argument("--portfolio", type=str, required=True, choices=["LTS_AUS3", "LTS_AHR3"])
    parser.add_argument("--start", type=str, required=True, help="เวลาเริ่มต้น dd-MM-yyyy HH:mm (BKK)")
    parser.add_argument("--days", type=int, default=BACKTEST_DAYS_FALLBACK)
    parser.add_argument("--once", action="store_true", help="รันแค่ 1 รอบแล้วออก (สำหรับทดสอบแบบควบคุม)")
    args = parser.parse_args()

    portfolio_name = args.portfolio
    config.IN_BACKTEST = True  # run_lts_af_backtest ต้องการ flag นี้ (ดู run_backtest_sim.py)

    # resolve ว่า profile ไหนรัน portfolio นี้จริง แล้วตั้ง env ให้ mt5_initialize
    # เชื่อมบัญชีถูกต้อง (ตัวเดียวกับที่ CLI backtest ใช้ — ดู run_backtest_sim.py:main)
    rbs.setup_mt5_for_portfolio(portfolio_name)
    profile_dir = rbs.LTS_AUS_AHR_SETUP_PROFILE_DIR or config.PROFILE_DIR

    state_file, log_file = _state_paths(portfolio_name, profile_dir)
    _install_log_tee(log_file)

    fallback_start = datetime.strptime(args.start, STATE_FMT)
    current_start, processed = _load_state(state_file, fallback_start)

    if not config.mt5_initialize(mt5):
        print("❌ MT5 initialize failed")
        return
    config.resolve_mt5_symbol(mt5, "XAUUSD", set_runtime=True)

    magic = dp._portfolio_magic(portfolio_name)
    print(f"🚀 Supervisor LTS ({portfolio_name}) | magic={magic} | start={current_start.strftime(STATE_FMT)} | sync=:00/:15/:30/:45")
    print("=" * 60)

    while True:
        now = datetime.now()
        print(f"\n[{now.strftime('%H:%M:%S')}] ─── รอบใหม่ ({portfolio_name}) ───")

        # เช็คปุ่มเปิด/ปิดจาก Telegram สดใหม่ทุกรอบ (ดู docstring ของ
        # _is_portfolio_active_via_telegram) — ปิดอยู่ = ข้ามทั้งรอบ (ไม่เข้า order ใหม่ ไม่
        # force-close ด้วย ถือว่า "หยุดทั้งระบบ" ตรงตามความหมายปุ่มเดิมที่พี่คุ้นเคย)
        if not _is_portfolio_active_via_telegram(profile_dir, portfolio_name):
            print(f"  ⏸️ {portfolio_name} ปิดอยู่ (Telegram toggle) — ข้ามรอบนี้ ไม่เข้า order/force-close")
            if args.once:
                print("  🛑 --once: จบการทดสอบ 1 รอบ")
                mt5.shutdown()
                break
            mt5.shutdown()
            _sleep_until_next_quarter()
            if not config.mt5_initialize(mt5):
                print("❌ MT5 reconnect failed — ลองรอบถัดไป")
            continue

        # run_lts_af_backtest/fetch_bars_range รับ start_str รูปแบบ "%Y-%m-%d %H:%M"
        # (คนละแบบกับ STATE_FMT ที่ใช้เก็บ state เป็น "%d-%m-%Y %H:%M" ตามธรรมเนียม
        # ของ supervisor_s20_12.py) — แปลงให้ตรงตอนเรียกเท่านั้น
        start_str = current_start.strftime("%Y-%m-%d %H:%M")
        print(f"  ▶ run_lts_af_backtest(start={start_str}, cb=off, include_open=on)")
        # include_open_signals=True (เพิ่ม 2026-08-31): เข้า order ได้ทันทีที่แท่งสัญญาณปิด
        # ไม่ต้องรอผล TP/SL ยืนยันก่อน (เดิมรอผลก่อนเสมอ ทำให้เข้า order ช้ากว่าที่ควรได้สูงสุด
        # เกือบ 15 นาที — เจอจริงกับ LTS_AUS3_281/343 ที่ backtest ยืนยันแล้วตั้งแต่ 15:30 แต่
        # supervisor เพิ่งเห็นตอน 15:45) — ดู docstring ของ run_lts_af_backtest/replay84
        #
        # apply_circuit_breaker=False ตรงนี้ (ไม่เปลี่ยนจากเดิม 2026-08-31) — supervisor รัน
        # ด้วย start_str สั้นๆ ต่อรอบ (ไม่เห็นประวัติเต็มของ leg) ถ้าผ่าน _simulate_leg จะจำลอง
        # "แพ้ติดกัน" ผิดพลาด (นับจากศูนย์ทุกรอบ) อีกทั้ง supervisor ไม่ได้ใช้ pnl_usd/lot จาก
        # trade dict พวกนี้เลย (คำนวณ lot จริงแยกผ่าน _af_order_volume ตอนเข้า order) จึงไม่ต้อง
        # ผ่าน _simulate_leg เลย — เจอ 2026-09-14: CLI compare tool (run_backtest_sim.py
        # __main__) ใช้ apply_circuit_breaker=True เสมอไม่ว่าพอร์ตไหน (เพื่อให้ _simulate_leg
        # แปลง $ ให้ trades.csv ปกติ) แต่ปิด "cb skip" เฉพาะ LTS_AUS3/LTS_AHR3 ไว้ข้างในแทน (ดู
        # apply_circuit_breaker_for_portfolio ใน run_backtest_sim.py) ให้ผลลัพธ์ตรงกับที่นี่
        # (ไม่มีสัญญาณไหนถูก CB ตัดทิ้งเลยทั้งคู่) โดยไม่กระทบวิธีคำนวณ $ ของแต่ละฝั่ง
        trades = rbs.run_lts_af_backtest(
            portfolio_name, args.days, start_str, None, 1.0, apply_circuit_breaker=False,
            include_open_signals=True,
        )
        print(f"  ℹ️ run_lts_af_backtest คืน {len(trades)} trades ทั้งหมด (รวม warmup ก่อน start_str ด้วย)")

        positions = mt5.positions_get(symbol=dp._demo_symbol()) or []
        orders = mt5.orders_get(symbol=dp._demo_symbol()) or []
        _sweep_stale_pending_orders(magic, orders)
        orders = mt5.orders_get(symbol=dp._demo_symbol()) or []  # รีเฟรชหลัง sweep ยกเลิกด้านบน

        # ── Safety net: backtest ยืนยันแล้วว่าไม้นี้ปิดไปแล้ว (TP/SL) แต่ MT5 live ยังเปิดอยู่ ──
        # เจอจริง 2026-08-30: run_lts_af_backtest คืนเฉพาะ trade ที่ resolve แล้วเท่านั้น (ดู
        # sim_s84_backtest.py replay84 — "if outcome == OPEN: continue" ไม่คืน trade ที่ยังไม่โดน
        # TP/SL เลย) แปลว่าทุก trade ใน `trades` ด้านบน backtest "ยืนยันแล้ว" ว่า TP หรือ SL
        # โดนแตะจริงในอดีต — ถ้า MT5 live position ที่ตรงกับ trade นี้ (leg+side+fill time) ยัง
        # เปิดค้างอยู่ = broker ไม่ trigger SL/TP ให้ตามที่ควร (requote/margin/platform hang
        # ฯลฯ) → ปิดเองทันที ไม่รอ broker พร้อม log ชัดเจนว่าทำไมถึงปิด (ตามที่พี่ขอ 2026-08-30)
        for t in trades:
            exit_ts = t.get("exit_time_ts")
            if not exit_ts:
                continue
            exit_ts = int(exit_ts)
            if exit_ts > int(now.timestamp()):
                continue  # กันเคส exit อยู่ในอนาคต (ไม่ควรเกิดแต่กันไว้)
            fill_ts = int(t.get("fill_time_ts", 0) or 0)
            if fill_ts <= 0:
                continue
            fill_dt = datetime.fromtimestamp(fill_ts)
            leg_key = t.get("leg", "").split(" ")[0]
            side = t.get("signal")
            live_pos = _find_live_position(magic, leg_key, side, fill_dt, positions,
                                            sl=t.get("sl"), tp=t.get("tp"))
            if live_pos is None:
                continue  # ไม่มี live position ค้าง (ปิดไปแล้วจริง หรือไม่เคยเข้า) ปกติดี
            exit_dt = datetime.fromtimestamp(exit_ts)
            outcome = t.get("outcome", "?")
            print(f"  🚨 {leg_key} {side} @ {fill_dt.strftime('%H:%M')} ticket={live_pos.ticket}: "
                  f"backtest ปิดไปแล้ว ({outcome}) ตั้งแต่ {exit_dt.strftime('%d/%m %H:%M:%S')} "
                  f"@ {t.get('exit_price')}")
            print(f"     ⛔ ปิดออเดอร์นี้ทันทีเนื่องจาก backtest order นี้ปิดไปแล้วแต่ mt5 live ยังไม่ปิด")
            _force_close_position(live_pos)
        positions = mt5.positions_get(symbol=dp._demo_symbol()) or []  # รีเฟรชหลังปิดของข้างบน

        newly_processed = set()
        earliest_unhandled = None

        for t in trades:
            fill_ts = int(t.get("fill_time_ts", 0) or 0)
            if fill_ts <= 0:
                continue
            fill_dt = datetime.fromtimestamp(fill_ts)
            if fill_dt < current_start - timedelta(hours=1):
                continue  # ไม้เก่ากว่า window ที่สนใจจริงๆ (กันเศษจาก warmup)

            leg_key = t.get("leg", "").split(" ")[0]
            side = t.get("signal")
            key = (leg_key, fill_ts, side)
            if key in processed:
                continue

            live_pos = _find_live_position(magic, leg_key, side, fill_dt, positions,
                                            sl=t.get("sl"), tp=t.get("tp"))
            if live_pos is not None:
                print(f"  ✓ {leg_key} {side} @ {fill_dt.strftime('%H:%M')} มี live position อยู่แล้ว ticket={live_pos.ticket}")
                newly_processed.add(key)
                continue

            age_sec = (now - fill_dt).total_seconds()
            if age_sec > STALE_ENTRY_SEC:
                print(f"  ⏭️ {leg_key} {side} @ {fill_dt.strftime('%H:%M')} เก่าเกิน {STALE_ENTRY_SEC}s ({age_sec:.0f}s) — ข้าม ไม่เข้าสาย")
                newly_processed.add(key)
                continue

            # S9x-family (S95/S96/S97) + ยังเป็น OPEN (ไม่ resolve แล้ว): เดิมทีเช็คราคาจริงสดๆ
            # ทุกรอบ 15 นาทีผ่าน _s9x_pending_should_fill แล้วค่อยยิง market order (ช้า+ราคา
            # คลาดเคลื่อนจาก slippage ตอนรอบถัดไปค่อยเห็น) — เปลี่ยนมาวาง pending limit order
            # จริงที่ broker แทน (อนุมัติ 2026-09-01 "ลุยเลยครับ") broker fill ให้เองทันทีที่ราคา
            # แตะ entry±spread เป๊ะ ไม่ต้องรอ poll รอบถัดไป, หมดอายุตาม S9X_PENDING_MAX_BARS
            # แท่งของ TF นั้นๆ (เท่ากับกรอบที่ backtest เองใช้ตัดสิน fillable ใน run_s9x_generic
            # ._resolve — ดู feedback ที่พี่ยืนยันแล้วว่าตรงกัน)
            af_def = dp.AF_DEFS.get(leg_key)
            if af_def and af_def.get("is_s9x") and t.get("outcome") == "OPEN":
                pending = _find_pending_order(magic, leg_key, side, orders)
                if pending is not None:
                    max_wait_sec = dp.S9X_PENDING_MAX_BARS * _tf_minutes(t.get("tf")) * 60
                    pending_age_sec = now.timestamp() - pending.time_setup
                    if pending_age_sec > max_wait_sec:
                        print(f"  ⌛ {leg_key} {side} @ {fill_dt.strftime('%H:%M')} pending limit order "
                              f"ticket={pending.ticket} หมดอายุ ({pending_age_sec:.0f}s > {max_wait_sec}s) "
                              f"— ยกเลิก (ราคาไม่มาถึงตามกรอบเวลาเดียวกับที่ backtest ใช้)")
                        dp._cancel_pending_order(pending.ticket)
                        newly_processed.add(key)
                    else:
                        print(f"  ⏳ {leg_key} {side} @ {fill_dt.strftime('%H:%M')} มี pending limit order "
                              f"ticket={pending.ticket} รอราคาอยู่ ({pending_age_sec:.0f}s/{max_wait_sec}s)")
                    continue

                if not dp._s9x_pending_should_fill({"entry": t.get("entry"), "signal": side}):
                    entry = float(t.get("entry"))
                    entry_level = entry - dp.S9X_PENDING_SPREAD if side == "BUY" else entry + dp.S9X_PENDING_SPREAD
                    print(f"  📌 {leg_key} {side} @ {fill_dt.strftime('%H:%M')} (อายุ {age_sec:.0f}s) "
                          f"— S9x ราคายังไม่ถึง entry±spread กำลังวาง pending limit order @ {entry_level:.2f}...")
                    _place_s9x_limit_entry(portfolio_name, leg_key, t, entry_level)
                    continue

            print(f"  🆕 {leg_key} {side} @ {fill_dt.strftime('%H:%M')} (อายุ {age_sec:.0f}s) — ยังไม่มี live position, กำลังเข้า order...")
            entered = _place_entry(portfolio_name, leg_key, t)
            if entered:
                newly_processed.add(key)
            else:
                # เจอจริง 2026-08-28 (AUS3): order ล้มเหลวจาก margin ไม่พอ (err=10019 No money)
                # 28 ครั้งในเช้าวันเดียว — ถ้า mark processed ทันทีจะเสีย signal ไปถาวรไม่มีทาง
                # กู้คืน จึง "ไม่" ใส่ key นี้ลง processed ตรงนี้ ปล่อยให้รอบถัดไป (15 นาที) ลองใหม่
                # จนกว่าจะสำเร็จ หรือ age_sec เกิน STALE_ENTRY_SEC (สาขา stale-skip ด้านบนจะ
                # mark processed แทนตอนนั้น) — ไม่ retry ไม่จำกัด
                print(f"     🔁 จะลองใหม่รอบถัดไป (ยังไม่ mark processed)")

        processed |= newly_processed

        # หา fill_time_ts ที่ "ยังไม่จัดการ" ตัวที่เก่าสุด (ถ้ามี) — current_start ขยับผ่านมันไม่ได้
        # เจอจริง 2026-08-29: run_lts_af_backtest() คืน trade ทุกตัวในช่วง fetch เต็ม (รวม
        # ~11 วันของ extra_bars=700 warmup ก่อน start_str) ไม่ได้ตัดตาม start_str ให้เอง (ขั้นตอน
        # นั้นอยู่ใน main() ของ CLI เท่านั้น ตัว supervisor นี้เรียก run_lts_af_backtest ตรงๆ
        # ไม่ผ่าน main()) — ถ้าไม่กรอง trade เก่ากว่า current_start ออกก่อน จะได้ fill_time_ts
        # เก่ามากๆ มาปนใน unresolved_ts ทำให้ current_start ขยับไปข้างหน้าไม่ได้เลยสักครั้ง
        window_floor = current_start - timedelta(hours=1)
        unresolved_ts = [
            int(t.get("fill_time_ts", 0) or 0)
            for t in trades
            if int(t.get("fill_time_ts", 0) or 0) > 0
            and datetime.fromtimestamp(int(t["fill_time_ts"])) >= window_floor
            and (t.get("leg", "").split(" ")[0], int(t.get("fill_time_ts", 0) or 0), t.get("signal")) not in processed
        ]
        if unresolved_ts:
            next_start = datetime.fromtimestamp(min(unresolved_ts))
        else:
            next_start = now.replace(second=0, microsecond=0)

        if next_start > current_start:
            print(f"  ⏩ ขยับ --start: {current_start.strftime('%H:%M')} → {next_start.strftime('%H:%M')}")
            current_start = next_start

        processed = _save_state(state_file, current_start, processed)

        if args.once:
            print("  🛑 --once: จบการทดสอบ 1 รอบ")
            mt5.shutdown()
            break

        mt5.shutdown()
        _sleep_until_next_quarter()
        if not config.mt5_initialize(mt5):
            print("❌ MT5 reconnect failed — ลองรอบถัดไป")


if __name__ == "__main__":
    main()
