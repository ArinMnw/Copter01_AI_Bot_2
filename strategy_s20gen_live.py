# -*- coding: utf-8 -*-
"""strategy_s20gen_live.py — live/demo adapter สำหรับกลยุทธ์จากแคมเปญ strategy/s20_gen
(S20.140–S20.1519) ที่ผ่าน final_gate WINNER/BORDERLINE แล้ว (ดู
strategy/backtest-summary/S20_forward_demo_shortlist_62.md) แต่ยังไม่เคย forward demo เลย

ใช้คู่กับ demo_portfolio.py (ระบบ standalone แยกจาก scanner.py/active_strategies โดยสิ้นเชิง
ตาม docstring ของไฟล์นั้น) — ไม่ชนกับเลข sid ของ 48_New_God_S20 ที่ live อยู่ เพราะ
demo_portfolio.py ไม่ใช้ตัวเลข sid เป็น key ของ active_strategies แต่ใช้ string portfolio_name
ของตัวเอง (S20G_<sid>_<tf>) — sid 143/148/210 ที่ชนกับ live ในบริบทอื่นจึงไม่กระทบระบบนี้

strategy/s20.<N>/strategy20_<N>.py มีแค่ generate(df, tf) -> signal array (รูปแบบ backtest-only
ของ strategy/s20_gen/engine.py) — ไฟล์นี้ห่อให้เป็น detect-style function ที่ demo_portfolio.py
เรียกใช้ได้ โดยคำนวณ SL distance ด้วยวิธีเดียวกับ engine.py เป๊ะ (sl_dist ถ้า generate() คืนมา
ไม่งั้น sl_atr * ATR14, floor ที่ 3x spread ปัจจุบัน) เพื่อให้ sl/tp ตรงกับที่ backtest validate
ไว้มากที่สุด — max_hold (ปิดถ้าถือเกิน N แท่ง) และ be_r (เลื่อน SL ไป breakeven ที่ N×risk) ยัง
ต้อง deviate จาก backtest เล็กน้อย: max_hold ต้องมี exit-management loop แยกจัดการ (ดู
_manage_s20gen_max_hold ใน demo_portfolio.py) เพราะ engine.py จำลองแบบ bar-by-bar แต่ live
ต้องเช็คเป็นช่วงเวลาจริงแทน — ผลลัพธ์ควรใกล้เคียงกันมากแต่ไม่เป๊ะ 100%

⚠️ S20.753 ปิดไว้ (enabled=False) เพราะให้ไม้/net/PF เท่ากับ S20.751 เป๊ะ (สัญญาณเดียวกันจาก
Mix 277x242 — ต่างกันแค่ method CONFIRM vs FILTER แต่ output เหมือนกัน) เปิดทั้งคู่จะเทรดซ้อน
ไม้เดียวกัน 2 เท่าโดยไม่ได้ diversify เพิ่มเลย
"""
import os
import sys
import importlib.util

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
_S20GEN_DIR = os.path.join(HERE, "strategy", "s20_gen")
if _S20GEN_DIR not in sys.path:
    sys.path.insert(0, _S20GEN_DIR)
import ind as I  # noqa: E402  (ไลบรารี indicator เดียวกับที่ generate() ของทุกตัวใช้)

TF_SEC = {"M1": 60, "M5": 300, "M15": 900, "M30": 1800, "H1": 3600, "H4": 14400, "D1": 86400}
ATR_N = 14  # ตรงกับ M["atr_n"]=14 ของ strategy/s20_gen/engine.py (ไม่มีตัวไหนเปลี่ยนค่านี้)

_MODULE_CACHE = {}


def _load_module(sid):
    if sid in _MODULE_CACHE:
        return _MODULE_CACHE[sid]
    path = os.path.join(HERE, "strategy", f"s20.{sid}", f"strategy20_{sid}.py")
    spec = importlib.util.spec_from_file_location(f"strategy20_{sid}_live", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    _MODULE_CACHE[sid] = mod
    return mod


def _rates_to_df(rates):
    names = rates.dtype.names
    df = pd.DataFrame({
        "time": rates["time"].astype(np.int64),
        "open": rates["open"].astype(float),
        "high": rates["high"].astype(float),
        "low": rates["low"].astype(float),
        "close": rates["close"].astype(float),
        "tick_volume": rates["tick_volume"].astype(float) if "tick_volume" in names else np.zeros(len(rates)),
        "spread": rates["spread"].astype(float) if "spread" in names else np.zeros(len(rates)),
    })
    df["volume"] = df["tick_volume"]
    return df


def detect_s20gen(sid, rates, tf, sl_atr, current_spread=0.0):
    """ให้ rates ที่ fetch มาแบบ copy_rates_from_pos(symbol, tf_val, 0, N) (แท่งสุดท้าย = แท่ง
    ที่กำลังวิ่ง) — ฟังก์ชันนี้ตัดแท่งนั้นทิ้งก่อนเรียก generate() เพื่อให้ตรงกับ checklist #2
    ของ engine.py (เข้าไม้ที่ open ของแท่งถัดไปหลังแท่งสัญญาณปิด — ในที่นี้คือตอนนี้เลย เพราะ
    เราสแกนทันทีที่แท่งสัญญาณปิด ราคาปัจจุบัน ≈ open ของแท่งถัดไป)"""
    if rates is None or len(rates) < 210:
        return {"signal": "WAIT", "reason": "bars not enough"}
    df = _rates_to_df(rates[:-1])  # ตัดแท่งที่ยังไม่ปิด
    mod = _load_module(sid)
    try:
        out = mod.generate(df.copy(), tf)
    except Exception as e:
        return {"signal": "WAIT", "reason": f"generate error: {type(e).__name__}: {e}"}
    if isinstance(out, dict):
        sig = np.asarray(out["sig"], dtype=np.int8)
        sl_dist_arr = out.get("sl_dist")
    else:
        sig = np.asarray(out, dtype=np.int8)
        sl_dist_arr = None
    i = len(df) - 1
    d = int(sig[i])
    if d == 0:
        return {"signal": "WAIT", "reason": "no signal"}
    a = I.atr(df, ATR_N).to_numpy()
    dist = float(sl_dist_arr[i]) if sl_dist_arr is not None else float(sl_atr) * float(a[i])
    if not np.isfinite(dist) or dist <= 0:
        return {"signal": "WAIT", "reason": "invalid atr/dist"}
    if current_spread > 0:
        dist = max(dist, 3.0 * current_spread)  # เหมือน engine.py: SL ต้องกว้างกว่า spread อย่างน้อย 3 เท่า
    return {
        "signal": "BUY" if d > 0 else "SELL",
        "dist": dist,
        "entry_bar_ts": int(df["time"].iat[i]),
    }


def leg_key(sid, tf):
    return f"S20G_{sid}_{tf}"


# sid, tf, name(ชื่อกลยุทธ์), kind(single/mix), sl_atr, rr, max_hold(แท่ง), be_r, cat(WINNER/
# BORDERLINE), enabled — ดึงจาก META จริงของแต่ละ strategy/s20.<sid>/strategy20_<sid>.py
# (ไม่ใช่ default เดียวกันทุกตัว: แคมเปญแรก 140-299 ใช้ rr/max_hold ต่างจากแคมเปญ mix ที่
# ล็อค sl_atr=1.5/rr=1.5/max_hold=24/be_r=1.0 เป็นมาตรฐานเดียวกันหมด)
S20GEN_LEGS = [
    {"sid": 194, "tf": "M5", "name": "Chande Kroll Stop Flip", "kind": "single", "sl_atr": 1.5, "rr": 2.0, "max_hold": 30, "be_r": 0.0, "cat": "WINNER", "enabled": True},
    {"sid": 143, "tf": "M5", "name": "Elder Impulse System Color Shift", "kind": "single", "sl_atr": 1.5, "rr": 2.0, "max_hold": 30, "be_r": 0.0, "cat": "WINNER", "enabled": True},
    {"sid": 242, "tf": "M5", "name": "Rainbow MA Full Alignment", "kind": "single", "sl_atr": 1.5, "rr": 2.0, "max_hold": 30, "be_r": 0.0, "cat": "WINNER", "enabled": True},
    {"sid": 194, "tf": "H1", "name": "Chande Kroll Stop Flip", "kind": "single", "sl_atr": 1.5, "rr": 2.0, "max_hold": 30, "be_r": 0.0, "cat": "WINNER", "enabled": True},
    {"sid": 685, "tf": "M5", "name": "S20.158 x S20.194 (CONFIRM w15)", "kind": "mix", "sl_atr": 1.5, "rr": 1.5, "max_hold": 24, "be_r": 1.0, "cat": "WINNER", "enabled": True},
    {"sid": 242, "tf": "M30", "name": "Rainbow MA Full Alignment", "kind": "single", "sl_atr": 1.5, "rr": 2.0, "max_hold": 30, "be_r": 0.0, "cat": "WINNER", "enabled": True},
    {"sid": 194, "tf": "M30", "name": "Chande Kroll Stop Flip", "kind": "single", "sl_atr": 1.5, "rr": 2.0, "max_hold": 30, "be_r": 0.0, "cat": "WINNER", "enabled": True},
    {"sid": 210, "tf": "M30", "name": "Bill Williams Accelerator Oscillator Two-Green", "kind": "single", "sl_atr": 1.5, "rr": 2.0, "max_hold": 24, "be_r": 0.0, "cat": "WINNER", "enabled": True},
    {"sid": 277, "tf": "M30", "name": "Quadratic-Regression Curvature Turn", "kind": "single", "sl_atr": 1.5, "rr": 2.0, "max_hold": 24, "be_r": 0.0, "cat": "WINNER", "enabled": True},
    {"sid": 255, "tf": "H4", "name": "Hikkake Inside-Bar False Breakout", "kind": "single", "sl_atr": 1.2, "rr": 2.0, "max_hold": 20, "be_r": 0.0, "cat": "WINNER", "enabled": True},
    {"sid": 168, "tf": "M30", "name": "Ehlers Super Smoother Crossover", "kind": "single", "sl_atr": 1.5, "rr": 2.0, "max_hold": 40, "be_r": 0.0, "cat": "WINNER", "enabled": True},
    {"sid": 751, "tf": "M5", "name": "S20.277 x S20.242 (CONFIRM w15)", "kind": "mix", "sl_atr": 1.5, "rr": 1.5, "max_hold": 24, "be_r": 1.0, "cat": "WINNER", "enabled": True},
    {"sid": 753, "tf": "M5", "name": "S20.277 x S20.242 (FILTER w15)", "kind": "mix", "sl_atr": 1.5, "rr": 1.5, "max_hold": 24, "be_r": 1.0, "cat": "WINNER", "enabled": False},
    {"sid": 648, "tf": "M30", "name": "S20.148 x S20.237 (CONFIRM)", "kind": "mix", "sl_atr": 1.5, "rr": 1.5, "max_hold": 24, "be_r": 1.0, "cat": "WINNER", "enabled": True},
    {"sid": 689, "tf": "H1", "name": "S20.158 x S20.242 (CONFIRM w10)", "kind": "mix", "sl_atr": 1.5, "rr": 1.5, "max_hold": 24, "be_r": 1.0, "cat": "WINNER", "enabled": True},
    {"sid": 237, "tf": "M15", "name": "Ehlers FRAMA Cross", "kind": "single", "sl_atr": 1.5, "rr": 2.0, "max_hold": 30, "be_r": 0.0, "cat": "WINNER", "enabled": True},
    {"sid": 339, "tf": "M30", "name": "Inside Bar MACD Continuation Breakout", "kind": "single", "sl_atr": 1.5, "rr": 1.5, "max_hold": 24, "be_r": 1.0, "cat": "WINNER", "enabled": True},
    {"sid": 148, "tf": "M30", "name": "Inside-Bar Mother-Bar Breakout with EMA50 Trend", "kind": "single", "sl_atr": 1.2, "rr": 2.0, "max_hold": 24, "be_r": 0.0, "cat": "WINNER", "enabled": True},
    {"sid": 637, "tf": "M30", "name": "S20.148 x S20.277 (FILTER)", "kind": "mix", "sl_atr": 1.5, "rr": 1.5, "max_hold": 24, "be_r": 1.0, "cat": "WINNER", "enabled": True},
    {"sid": 732, "tf": "H4", "name": "S20.205 x S20.143 (CONFIRM w15)", "kind": "mix", "sl_atr": 1.5, "rr": 1.5, "max_hold": 24, "be_r": 1.0, "cat": "WINNER", "enabled": True},
    {"sid": 512, "tf": "M30", "name": "MACD Divergence HalfTrend Confirm", "kind": "mix", "sl_atr": 1.5, "rr": 1.5, "max_hold": 24, "be_r": 1.0, "cat": "WINNER", "enabled": True},
    {"sid": 422, "tf": "M15", "name": "Triple MA Volatility Breakout", "kind": "single", "sl_atr": 1.5, "rr": 1.5, "max_hold": 24, "be_r": 1.0, "cat": "WINNER", "enabled": True},
    {"sid": 937, "tf": "H1", "name": "Mixed 169 x 177 FILTER", "kind": "mix", "sl_atr": 1.5, "rr": 2.0, "max_hold": 24, "be_r": 0.0, "cat": "WINNER", "enabled": True},
    {"sid": 1092, "tf": "M30", "name": "Hull Kroll x Cycle Recovery", "kind": "mix", "sl_atr": 1.5, "rr": 1.5, "max_hold": 24, "be_r": 1.0, "cat": "WINNER", "enabled": True},
    {"sid": 854, "tf": "H1", "name": "Rainbow MA x KST Confirm", "kind": "mix", "sl_atr": 1.5, "rr": 1.5, "max_hold": 24, "be_r": 1.0, "cat": "WINNER", "enabled": True},
    {"sid": 888, "tf": "M30", "name": "Mix 339 + 266 (FILTER)", "kind": "mix", "sl_atr": 1.5, "rr": 1.5, "max_hold": 24, "be_r": 1.0, "cat": "WINNER", "enabled": True},
    {"sid": 708, "tf": "M15", "name": "S20.196 x S20.143 (CONFIRM w15)", "kind": "mix", "sl_atr": 1.5, "rr": 1.5, "max_hold": 24, "be_r": 1.0, "cat": "WINNER", "enabled": True},
    {"sid": 778, "tf": "M15", "name": "Mixed 422 x 765 FILTER", "kind": "mix", "sl_atr": 1.5, "rr": 1.5, "max_hold": 24, "be_r": 1.0, "cat": "WINNER", "enabled": True},
    {"sid": 471, "tf": "M15", "name": "Mix 422 + 158 (CONFIRM)", "kind": "mix", "sl_atr": 1.5, "rr": 1.5, "max_hold": 24, "be_r": 1.0, "cat": "WINNER", "enabled": True},
    {"sid": 1118, "tf": "M30", "name": "Hull Kroll x Inside Curvature", "kind": "mix", "sl_atr": 1.5, "rr": 1.5, "max_hold": 24, "be_r": 1.0, "cat": "WINNER", "enabled": True},
    {"sid": 1185, "tf": "M5", "name": "Inside Curvature x Cycle Recovery", "kind": "mix", "sl_atr": 1.5, "rr": 1.5, "max_hold": 24, "be_r": 1.0, "cat": "WINNER", "enabled": True},
    {"sid": 1475, "tf": "M15", "name": "CMO Impulse x Random Walk Separation", "kind": "mix", "sl_atr": 1.5, "rr": 1.5, "max_hold": 24, "be_r": 1.0, "cat": "WINNER", "enabled": True},
    {"sid": 1474, "tf": "M15", "name": "CMO Impulse x Leading OBV", "kind": "mix", "sl_atr": 1.5, "rr": 1.5, "max_hold": 24, "be_r": 1.0, "cat": "WINNER", "enabled": True},
    {"sid": 161, "tf": "H1", "name": "Ultimate Oscillator Williams Buy Setup", "kind": "single", "sl_atr": 1.5, "rr": 1.5, "max_hold": 20, "be_r": 0.0, "cat": "WINNER", "enabled": True},
    {"sid": 950, "tf": "M5", "name": "Mixed 854 x 168 CONFIRM 48", "kind": "mix", "sl_atr": 1.5, "rr": 1.5, "max_hold": 24, "be_r": 1.0, "cat": "WINNER", "enabled": True},
    {"sid": 356, "tf": "M5", "name": "Bollinger Volatility Z-Score Breakout", "kind": "single", "sl_atr": 1.5, "rr": 1.5, "max_hold": 24, "be_r": 1.0, "cat": "WINNER", "enabled": True},
    {"sid": 1378, "tf": "M5", "name": "Inside Curvature x Period Open Cross", "kind": "mix", "sl_atr": 1.5, "rr": 1.5, "max_hold": 24, "be_r": 1.0, "cat": "WINNER", "enabled": True},
    {"sid": 342, "tf": "M5", "name": "ADX Low Volatility Breakout", "kind": "single", "sl_atr": 1.5, "rr": 1.5, "max_hold": 24, "be_r": 1.0, "cat": "WINNER", "enabled": True},
    {"sid": 1062, "tf": "M15", "name": "Hull Kroll x Volume MACD", "kind": "mix", "sl_atr": 1.5, "rr": 1.5, "max_hold": 24, "be_r": 1.0, "cat": "WINNER", "enabled": True},
    {"sid": 724, "tf": "M15", "name": "S20.196 x S20.406 (CONFIRM w15)", "kind": "mix", "sl_atr": 1.5, "rr": 1.5, "max_hold": 24, "be_r": 1.0, "cat": "WINNER", "enabled": True},
    {"sid": 1186, "tf": "M5", "name": "Inside Curvature x Volume MACD", "kind": "mix", "sl_atr": 1.5, "rr": 1.5, "max_hold": 24, "be_r": 1.0, "cat": "WINNER", "enabled": True},
    {"sid": 1499, "tf": "M15", "name": "CMO Histogram x Fractal Acceptance", "kind": "mix", "sl_atr": 1.5, "rr": 1.5, "max_hold": 24, "be_r": 1.0, "cat": "WINNER", "enabled": True},
    {"sid": 1244, "tf": "M5", "name": "CMO Impulse x ABC Defense", "kind": "mix", "sl_atr": 1.5, "rr": 1.5, "max_hold": 24, "be_r": 1.0, "cat": "WINNER", "enabled": True},
    {"sid": 1453, "tf": "M5", "name": "CMO Impulse x Mother Range Break", "kind": "mix", "sl_atr": 1.5, "rr": 1.5, "max_hold": 24, "be_r": 1.0, "cat": "WINNER", "enabled": True},
    {"sid": 1509, "tf": "M15", "name": "CMO Histogram x Easy Movement", "kind": "mix", "sl_atr": 1.5, "rr": 1.5, "max_hold": 24, "be_r": 1.0, "cat": "WINNER", "enabled": True},
    {"sid": 1519, "tf": "M5", "name": "CMO Histogram x Random Walk Separation", "kind": "mix", "sl_atr": 1.5, "rr": 1.5, "max_hold": 24, "be_r": 1.0, "cat": "WINNER", "enabled": True},
    {"sid": 614, "tf": "M5", "name": "S20.339 x S20.409 (CONFIRM)", "kind": "mix", "sl_atr": 1.5, "rr": 1.5, "max_hold": 24, "be_r": 1.0, "cat": "WINNER", "enabled": True},
    {"sid": 795, "tf": "H1", "name": "Mixed 194 x 237 CONFIRM", "kind": "mix", "sl_atr": 1.5, "rr": 1.5, "max_hold": 24, "be_r": 1.0, "cat": "BORDERLINE", "enabled": True},
    {"sid": 701, "tf": "H4", "name": "S20.165 x S20.143 (CONFIRM w15)", "kind": "mix", "sl_atr": 1.5, "rr": 1.5, "max_hold": 24, "be_r": 1.0, "cat": "BORDERLINE", "enabled": True},
    {"sid": 690, "tf": "M15", "name": "S20.158 x S20.153 (CONFIRM w10)", "kind": "mix", "sl_atr": 1.5, "rr": 1.5, "max_hold": 24, "be_r": 1.0, "cat": "BORDERLINE", "enabled": True},
    {"sid": 705, "tf": "M30", "name": "S20.153 x S20.210 (FILTER w5)", "kind": "mix", "sl_atr": 1.5, "rr": 1.5, "max_hold": 24, "be_r": 1.0, "cat": "BORDERLINE", "enabled": True},
    {"sid": 679, "tf": "M15", "name": "S20.153 x S20.143 (SIMULTANEOUS)", "kind": "mix", "sl_atr": 1.5, "rr": 1.5, "max_hold": 24, "be_r": 1.0, "cat": "BORDERLINE", "enabled": True},
    {"sid": 837, "tf": "H1", "name": "Chande Kroll x KST Confirm", "kind": "mix", "sl_atr": 1.5, "rr": 1.5, "max_hold": 24, "be_r": 1.0, "cat": "BORDERLINE", "enabled": True},
    {"sid": 774, "tf": "M15", "name": "Mixed 422 x 766 FILTER", "kind": "mix", "sl_atr": 1.5, "rr": 1.5, "max_hold": 24, "be_r": 1.0, "cat": "BORDERLINE", "enabled": True},
    {"sid": 935, "tf": "M30", "name": "Mixed 168 x 177 FILTER", "kind": "mix", "sl_atr": 1.5, "rr": 2.0, "max_hold": 40, "be_r": 0.0, "cat": "BORDERLINE", "enabled": True},
    {"sid": 857, "tf": "H1", "name": "Rainbow MA x Weekly Retest Confirm", "kind": "mix", "sl_atr": 1.5, "rr": 1.5, "max_hold": 24, "be_r": 1.0, "cat": "BORDERLINE", "enabled": True},
    {"sid": 1315, "tf": "M5", "name": "Inside Curvature x Chaikin Pressure", "kind": "mix", "sl_atr": 1.5, "rr": 1.5, "max_hold": 24, "be_r": 1.0, "cat": "BORDERLINE", "enabled": True},
    {"sid": 379, "tf": "M30", "name": "DMI Strong Trend Re-entry", "kind": "single", "sl_atr": 1.5, "rr": 1.5, "max_hold": 24, "be_r": 1.0, "cat": "BORDERLINE", "enabled": True},
    {"sid": 1149, "tf": "M30", "name": "Inside MACD x Exhaustion Reclaim State", "kind": "mix", "sl_atr": 1.5, "rr": 1.5, "max_hold": 24, "be_r": 1.0, "cat": "BORDERLINE", "enabled": True},
    {"sid": 1505, "tf": "M15", "name": "CMO Histogram x Confirmed Pivot Break", "kind": "mix", "sl_atr": 1.5, "rr": 1.5, "max_hold": 24, "be_r": 1.0, "cat": "BORDERLINE", "enabled": True},
    {"sid": 1253, "tf": "M15", "name": "CMO Histogram x Force Recovery", "kind": "mix", "sl_atr": 1.5, "rr": 1.5, "max_hold": 24, "be_r": 1.0, "cat": "BORDERLINE", "enabled": True},
    {"sid": 1454, "tf": "M5", "name": "CMO Impulse x NR7 Release", "kind": "mix", "sl_atr": 1.5, "rr": 1.5, "max_hold": 24, "be_r": 1.0, "cat": "BORDERLINE", "enabled": True},
    {"sid": 1265, "tf": "M15", "name": "CMO Histogram x HiLo Acceptance", "kind": "mix", "sl_atr": 1.5, "rr": 1.5, "max_hold": 24, "be_r": 1.0, "cat": "BORDERLINE", "enabled": True},
    {"sid": 1463, "tf": "M30", "name": "CMO Impulse x Hikkake Reclaim", "kind": "mix", "sl_atr": 1.5, "rr": 1.5, "max_hold": 24, "be_r": 1.0, "cat": "BORDERLINE", "enabled": True},
    {"sid": 1427, "tf": "M5", "name": "Inside Fractal x Choppiness Exit", "kind": "mix", "sl_atr": 1.5, "rr": 1.5, "max_hold": 24, "be_r": 1.0, "cat": "BORDERLINE", "enabled": True},
]

# leg_key -> leg dict (รวม idx สำหรับ magic number ที่คงที่ต่อ leg)
S20GEN_DEFS = {}
for _idx, _leg in enumerate(S20GEN_LEGS):
    _leg = dict(_leg)
    _leg["idx"] = _idx
    _leg["key"] = leg_key(_leg["sid"], _leg["tf"])
    S20GEN_DEFS[_leg["key"]] = _leg

S20GEN_ENABLED_KEYS = [k for k, v in S20GEN_DEFS.items() if v["enabled"]]
