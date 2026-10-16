# -*- coding: utf-8 -*-
"""strategy_indi1_live.py — live adapter ของกลยุทธ์ Indi1 (3 เส้น H1 + จังหวะ M5)

ที่มา: Pine "Geno Smart signal V2.3" -> mq5_strategy/indi1/{GenoSmartSignal.mq5,Indi1_EA.mq5,
Indi1_strategy.py} (ตรรกะสัญญาณใช้ฟังก์ชันเดียวกับ backtest โดย import Indi1_strategy ตรงๆ
ไม่ copy โค้ด เพื่อให้ live/backtest ไม่แยกทางกัน)

ใช้คู่กับ demo_portfolio.py (ระบบ standalone แยกจาก scanner.py) เหมือน strategy_s20gen_live.py

กฎ (Buy; Sell สลับด้านเป็นแดง):
  กฎ 1 แท่ง (INDI1_CONFIRM_BARS=1, ค่าปัจจุบัน — เปลี่ยนจากกฎ 2 แท่งเดิมเมื่อ 2026-10-15 ตามพี่):
  1) H1: แท่งที่ปิดแล้วล่าสุด Trend Line BB + Trend Line MA + Line 2 (Kernel) เขียวพร้อมกัน
  2) M5: แท่งที่เพิ่งปิดเพิ่งครบ 3 เส้นพร้อมกัน (แท่งก่อนหน้ายังไม่ครบ) หรือเกิด Smart Buy -> เข้า market ทันที
  กฎ 2 แท่งเดิม (INDI1_CONFIRM_BARS=2): H1 2 แท่งติดกัน, M5 trigger ที่ T แล้วรอ T+1 ปิดยืนยันก่อนเข้า
  SL = swing ZigZag ล่าสุดของ M5 -/+ buffer, TP = RR x ระยะ SL, lot จาก Risk % ของ balance
  Fibo breakeven: แท่ง M5 ปิดเลย 50% ของ entry->TP -> SL ไป entry +/- 50 จุด (ดู
  _manage_indi1_positions ใน demo_portfolio.py)

⚠️ ผล backtest 24 เดือน (XAUUSD, spread 0.20, ทุน 10,000): ไม่จำกัดไม้ต่อสัญญาณ H1 + Risk 0.33%
   ได้ +57.6% PF 1.14 DD 15.9% แต่ edge บาง ฝั่ง Buy ไม่นิ่ง และ backtest ไม่ได้จำลอง margin/
   จำนวนไม้ซ้อนสูงสุด — ดู INDI1_MAX_OPEN_POSITIONS ใน config.py (เพดานฉุกเฉินกันซ้อนไม้บาน
   เหมือนเหตุการณ์ 3587 เมื่อ 2026-08-18)
"""
import importlib.util
import os

HERE = os.path.dirname(os.path.abspath(__file__))
_CORE_PATH = os.path.join(HERE, "mq5_strategy", "indi1", "Indi1_strategy.py")

INDI1_KEY = "INDI1"
INDI1_LEG = "INDI1_M5"       # ขึ้นต้น "INDI1_" เพื่อให้ _fetch_leg_pnl/get_status_text จับคู่ได้
INDI1_LTF = "M5"
INDI1_HTF = "H1"
LTF_BARS = 2500              # warm-up ให้ EMA/ATR/Kernel/ZigZag converge (backtest ใช้ ~45 วัน)
HTF_BARS = 700

_core = None


def _load_core():
    global _core
    if _core is None:
        spec = importlib.util.spec_from_file_location("indi1_strategy_core", _CORE_PATH)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _core = mod
    return _core


def core_cfg(rr=None, sl_buffer_ticks=None, tick_size=None, point=None, confirm_bars=None):
    core = _load_core()
    cfg = dict(core.DEFAULT_CFG)
    if rr is not None:
        cfg["RR"] = float(rr)
    if sl_buffer_ticks is not None:
        cfg["SL_BUFFER_TICKS"] = int(sl_buffer_ticks)
    if tick_size:
        cfg["TICK_SIZE"] = float(tick_size)
    if point:
        cfg["POINT"] = float(point)
    if confirm_bars is not None:
        cfg["CONFIRM_BARS"] = int(confirm_bars)
    return cfg


def detect_indi1(m5_rates, h1_rates, cfg, allow_buy=True, allow_sell=True):
    """m5_rates/h1_rates = copy_rates_from_pos(symbol, tf, 0, N) (แท่งสุดท้ายคือแท่งที่กำลังวิ่ง ->
    ตัดทิ้ง) คืน dict:
      signal: BUY/SELL/WAIT, swing (ราคา swing สำหรับคำนวณ SL), entry_bar_ts (เวลาเปิดของแท่ง M5
      ที่เพิ่งปิด = แท่ง T+1), episode_start_ts (เวลาที่สัญญาณ H1 รอบปัจจุบันเริ่มมีผล)"""
    core = _load_core()
    if m5_rates is None or h1_rates is None or len(m5_rates) < 600 or len(h1_rates) < 200:
        return {"signal": "WAIT", "reason": "bars not enough"}
    m5 = list(m5_rates[:-1])
    h1 = list(h1_rates[:-1])
    try:
        ltf = core.compute_signals(m5, cfg)
        htf = core.compute_signals(h1, cfg)
    except Exception as e:
        return {"signal": "WAIT", "reason": f"compute error: {type(e).__name__}: {e}"}

    i = len(m5) - 1
    j = len(h1) - 1
    if j < 1:
        return {"signal": "WAIT", "reason": "no htf"}

    for buy in (True, False):
        if buy and not allow_buy:
            continue
        if not buy and not allow_sell:
            continue
        need = int(cfg.get("CONFIRM_BARS", 1))
        if not core.htf_ok(htf, j, buy, need):
            continue
        if not core.entry_signal(ltf, True, i, buy, need):
            continue
        # หาจุดเริ่มของสัญญาณ H1 รอบนี้ (ถอยหลังจนกว่าสัญญาณ HTF จะไม่ผ่าน)
        js = j
        while js - 1 >= 1 and core.htf_ok(htf, js - 1, buy, need) and (j - js) < 500:
            js -= 1
        episode_start_ts = int(h1[js]["time"]) + int(cfg["HTF_SECONDS"])
        swing = ltf["swing_low" if buy else "swing_high"][i]
        if swing != swing:  # NaN
            return {"signal": "WAIT", "reason": "no swing"}
        return {
            "signal": "BUY" if buy else "SELL",
            "swing": float(swing),
            "entry_bar_ts": int(m5[i]["time"]),
            "episode_start_ts": episode_start_ts,
        }
    return {"signal": "WAIT", "reason": "no signal"}
