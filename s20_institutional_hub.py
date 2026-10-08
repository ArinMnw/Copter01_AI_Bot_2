# -*- coding: utf-8 -*-
"""s20_institutional_hub.py
Institutional Strategy Hub for S20 Family (S20.18 through S20.304)
Provides standalone detectors for 11 unique institutional strategies
with full multi-symbol adaptation (Gold, Silver, Forex Majors).
"""

import os
import sys
import inspect
import importlib.util
import numpy as np
import pandas as pd
from datetime import datetime, timezone

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

import config

# Module cache for dynamic loading of s20.* directories
_MODULE_CACHE = {}

def _get_module(folder_name: str, file_name: str):
    key = f"{folder_name}/{file_name}"
    if key in _MODULE_CACHE:
        return _MODULE_CACHE[key]
    path = os.path.join(ROOT_DIR, "strategy", folder_name, f"{file_name}.py")
    if not os.path.exists(path):
        return None
    try:
        spec = importlib.util.spec_from_file_location(f"mod_{folder_name}", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _MODULE_CACHE[key] = mod
        return mod
    except Exception as e:
        print(f"[S20 HUB] Error loading {key}: {e}")
        return None

_MARATHON_CACHE = {"key": None, "df": None}


def _marathon_df(rates, compute_fn):
    """S20.301-304 คำนวณ marathon df จาก rates ชุดเดียวกันติดกัน 4 ครั้ง — คำนวณครั้งเดียวแล้วใช้ร่วม (single-slot)"""
    key = (len(rates), int(rates[0]["time"]), int(rates[-1]["time"]), float(rates[-1]["close"]), float(rates[-1]["high"]), float(rates[-1]["low"]))
    if _MARATHON_CACHE["key"] == key and _MARATHON_CACHE["df"] is not None:
        return _MARATHON_CACHE["df"]
    df = compute_fn(rates)
    _MARATHON_CACHE["key"] = key
    _MARATHON_CACHE["df"] = df
    return df


def get_symbol_scale_and_digits(symbol: str):
    """Returns (scale_factor, digits) for scaling rates to pass ATR thresholds."""
    sym = symbol.upper()
    if "JPY" in sym or "XAG" in sym:
        return 1.0, 3
    elif any(fx in sym for fx in ("EUR", "GBP", "AUD", "NZD", "CAD", "CHF")):
        return 1000.0, 5
    else:
        return 1.0, 2

def is_symbol_enabled_for_s20(symbol: str) -> bool:
    """Checks if the symbol is enabled in config switchboard."""
    enabled_syms = getattr(config, "S20_SYMBOLS", getattr(config, "S20_304_SYMBOLS", {}))
    root = config._symbol_root(symbol)
    return enabled_syms.get(root, enabled_syms.get(symbol, True))


# ─────────────────────────────────────────────────────────────────────────────
# 1. S20.18: Order Flow Delta & Passive Absorption
# ─────────────────────────────────────────────────────────────────────────────
def detect_s20_18(rates, tf_name="M15", symbol="XAUUSD") -> dict:
    if not is_symbol_enabled_for_s20(symbol):
        return {"signal": "WAIT", "reason": f"S20.18 disabled for {symbol}"}
    if tf_name != "M15":
        # backtest (extract_setups_for_strategy) ทดสอบเฉพาะ M15 เท่านั้น — ให้ live ตรงกัน
        # ตามที่พี่ยืนยันว่าอยากให้ live ตรงกับ backtest 2026-09
        return {"signal": "WAIT", "reason": "S20.18 only evaluates on M15"}
    mod = _get_module("s20.18", "strategy20_18")
    if not mod or len(rates) < 30:
        return {"signal": "WAIT", "reason": "S20.18 module not ready or rates too short"}
    try:
        scale, digits = get_symbol_scale_and_digits(symbol)
        r_eval = rates
        if scale != 1.0:
            r_eval = rates.copy()
            for col in ('open', 'high', 'low', 'close'):
                r_eval[col] = rates[col] * scale
        df = mod.compute_indicators_df(r_eval)
        idx = len(df) - 1
        res = mod.evaluate_bar(df, idx, tf=tf_name, entry_mode="RETEST", rr_ratio=1.8)
        if res.get("signal") in ("BUY", "SELL"):
            res["sid"] = 20.18
            res["cancel_bars"] = 5  # ตาม backtest (future_rates[:5]): รอย้อน retest ไม่เกิน 5 แท่ง M15 (75 นาที)
            clean_sym = symbol.split('.')[0]
            res["pattern"] = f"S20.18_Absorption_{clean_sym}"
            if scale != 1.0:
                res["entry"] = round(res["entry"] / scale, digits)
                res["sl"] = round(res["sl"] / scale, digits)
                res["tp"] = round(res["tp"] / scale, digits)
                res["risk"] = round(res["risk"] / scale, digits)
            else:
                res["entry"] = round(res["entry"], digits)
                res["sl"] = round(res["sl"], digits)
                res["tp"] = round(res["tp"], digits)
                res["risk"] = round(res["risk"], digits)
        return res
    except Exception as e:
        return {"signal": "WAIT", "reason": f"S20.18 error: {e}"}


# ─────────────────────────────────────────────────────────────────────────────
# 2. S20.19: Micro-Liquidity Pinbar Scalper
# ─────────────────────────────────────────────────────────────────────────────
def detect_s20_19(rates, tf_name="M15", symbol="XAUUSD") -> dict:
    if not is_symbol_enabled_for_s20(symbol):
        return {"signal": "WAIT", "reason": f"S20.19 disabled for {symbol}"}
    if tf_name != "M15":
        # backtest ยืนยัน M15 หลังปรับ (Turnaround: -$19 → +$4,692) — ให้ live ตรงกัน 2026-09
        return {"signal": "WAIT", "reason": "S20.19 only evaluates on M15"}
    mod = _get_module("s20.19", "strategy20_19")
    if not mod or len(rates) < 30:
        return {"signal": "WAIT", "reason": "S20.19 module not ready or rates too short"}
    try:
        scale, digits = get_symbol_scale_and_digits(symbol)
        r_eval = rates
        if scale != 1.0:
            r_eval = rates.copy()
            for col in ('open', 'high', 'low', 'close'):
                r_eval[col] = rates[col] * scale
        df = mod.compute_indicators_df(r_eval)
        idx = len(df) - 1
        res = mod.evaluate_bar(df, idx, tf=tf_name, entry_mode="RETEST", rr_ratio=1.8)
        if res.get("signal") in ("BUY", "SELL"):
            res["sid"] = 20.19
            clean_sym = symbol.split('.')[0]
            res["pattern"] = f"S20.19_Pinbar_{clean_sym}"
            if scale != 1.0:
                res["entry"] = round(res["entry"] / scale, digits)
                res["sl"] = round(res["sl"] / scale, digits)
                res["tp"] = round(res["tp"] / scale, digits)
                res["risk"] = round(res["risk"] / scale, digits)
            else:
                res["entry"] = round(res["entry"], digits)
                res["sl"] = round(res["sl"], digits)
                res["tp"] = round(res["tp"], digits)
                res["risk"] = round(res["risk"], digits)
        return res
    except Exception as e:
        return {"signal": "WAIT", "reason": f"S20.19 error: {e}"}


# ─────────────────────────────────────────────────────────────────────────────
# 3. S20.20: Asian Judas Swing Reversal
# ─────────────────────────────────────────────────────────────────────────────
def detect_s20_20(rates, tf_name="M15", symbol="XAUUSD") -> dict:
    if not is_symbol_enabled_for_s20(symbol):
        return {"signal": "WAIT", "reason": f"S20.20 disabled for {symbol}"}
    if tf_name != "M15":
        return {"signal": "WAIT", "reason": "S20.20 only evaluates on M15"}
    mod = _get_module("s20.20", "strategy20_20")
    if not mod or len(rates) < 30:
        return {"signal": "WAIT", "reason": "S20.20 module not ready"}
    try:
        scale, digits = get_symbol_scale_and_digits(symbol)
        r_eval = rates
        if scale != 1.0:
            r_eval = rates.copy()
            for col in ('open', 'high', 'low', 'close'):
                r_eval[col] = rates[col] * scale
        df = mod.compute_indicators_df(r_eval)
        idx = len(df) - 1
        res = mod.evaluate_asian_mean_reversion(df, idx, tf=tf_name)
        if not res or res.get("signal") == "WAIT":
            res = mod.evaluate_asymmetric_rr(df, idx, tf=tf_name)
        if res and res.get("signal") in ("BUY", "SELL"):
            res["sid"] = 20.20
            clean_sym = symbol.split('.')[0]
            res["pattern"] = f"S20.20_Judas_{clean_sym}"
            if scale != 1.0:
                res["entry"] = round(res["entry"] / scale, digits)
                res["sl"] = round(res["sl"] / scale, digits)
                res["tp"] = round(res["tp"] / scale, digits)
                res["risk"] = round(res["risk"] / scale, digits)
            else:
                res["entry"] = round(res["entry"], digits)
                res["sl"] = round(res["sl"], digits)
                res["tp"] = round(res["tp"], digits)
                res["risk"] = round(res["risk"], digits)
        return res if res else {"signal": "WAIT", "reason": "No setup"}
    except Exception as e:
        return {"signal": "WAIT", "reason": f"S20.20 error: {e}"}


# ─────────────────────────────────────────────────────────────────────────────
# 4. S20.21: Intermarket SMT Divergence
# ─────────────────────────────────────────────────────────────────────────────
def detect_s20_21(rates, tf_name="M15", symbol="XAUUSD", silver_rates=None) -> dict:
    if not is_symbol_enabled_for_s20(symbol):
        return {"signal": "WAIT", "reason": f"S20.21 disabled for {symbol}"}
    if tf_name != "M15":
        return {"signal": "WAIT", "reason": "S20.21 only evaluates on M15"}
    mod = _get_module("s20.21", "strategy20_21")
    if not mod or len(rates) < 30:
        return {"signal": "WAIT", "reason": "S20.21 module not ready"}
    try:
        scale, digits = get_symbol_scale_and_digits(symbol)
        r_eval = rates
        if scale != 1.0:
            r_eval = rates.copy()
            for col in ('open', 'high', 'low', 'close'):
                r_eval[col] = rates[col] * scale
        df = mod.compute_indicators_df(r_eval)
        idx = len(df) - 1
        silver_df = mod.compute_indicators_df(silver_rates) if silver_rates is not None and len(silver_rates) >= 30 else None
        
        res = mod.evaluate_smt_divergence(df, idx, silver_df=silver_df, tf=tf_name)
        if not res or res.get("signal") == "WAIT":
            res = mod.evaluate_breaker_block(df, idx, tf=tf_name)
        if not res or res.get("signal") == "WAIT":
            res = mod.evaluate_judas_swing(df, idx, tf=tf_name)
        if res and res.get("signal") in ("BUY", "SELL"):
            res["sid"] = 20.21
            clean_sym = symbol.split('.')[0]
            res["pattern"] = f"S20.21_SMT_{clean_sym}"
            if scale != 1.0:
                res["entry"] = round(res["entry"] / scale, digits)
                res["sl"] = round(res["sl"] / scale, digits)
                res["tp"] = round(res["tp"] / scale, digits)
                res["risk"] = round(res["risk"] / scale, digits)
            else:
                res["entry"] = round(res["entry"], digits)
                res["sl"] = round(res["sl"], digits)
                res["tp"] = round(res["tp"], digits)
                res["risk"] = round(res["risk"], digits)
        return res if res else {"signal": "WAIT", "reason": "No setup"}
    except Exception as e:
        return {"signal": "WAIT", "reason": f"S20.21 error: {e}"}


# ─────────────────────────────────────────────────────────────────────────────
# 5. S20.22: Session Anchored VWAP Reversion
# ─────────────────────────────────────────────────────────────────────────────
def detect_s20_22(rates, tf_name="M15", symbol="XAUUSD") -> dict:
    if not is_symbol_enabled_for_s20(symbol):
        return {"signal": "WAIT", "reason": f"S20.22 disabled for {symbol}"}
    if tf_name != "M15":
        return {"signal": "WAIT", "reason": "S20.22 only evaluates on M15"}
    mod = _get_module("s20.22", "strategy20_22")
    if not mod or len(rates) < 30:
        return {"signal": "WAIT", "reason": "S20.22 module not ready"}
    try:
        scale, digits = get_symbol_scale_and_digits(symbol)
        r_eval = rates
        if scale != 1.0:
            r_eval = rates.copy()
            for col in ('open', 'high', 'low', 'close'):
                r_eval[col] = rates[col] * scale
        df = mod.compute_indicators_df(r_eval)
        idx = len(df) - 1
        res = mod.evaluate_vwap_reversion(df, idx, tf=tf_name)
        if not res or res.get("signal") == "WAIT":
            res = mod.evaluate_asian_expansion(df, idx, tf=tf_name)
        if not res or res.get("signal") == "WAIT":
            res = mod.evaluate_institutional_orb(df, idx, tf=tf_name)
        if res and res.get("signal") in ("BUY", "SELL"):
            res["sid"] = 20.22
            clean_sym = symbol.split('.')[0]
            res["pattern"] = f"S20.22_VWAP_{clean_sym}"
            if scale != 1.0:
                res["entry"] = round(res["entry"] / scale, digits)
                res["sl"] = round(res["sl"] / scale, digits)
                res["tp"] = round(res["tp"] / scale, digits)
                res["risk"] = round(res["risk"] / scale, digits)
            else:
                res["entry"] = round(res["entry"], digits)
                res["sl"] = round(res["sl"], digits)
                res["tp"] = round(res["tp"], digits)
                res["risk"] = round(res["risk"], digits)
        return res if res else {"signal": "WAIT", "reason": "No setup"}
    except Exception as e:
        return {"signal": "WAIT", "reason": f"S20.22 error: {e}"}


# ─────────────────────────────────────────────────────────────────────────────
# 6. S20.24: Wyckoff Stopping Volume & London Fix
# ─────────────────────────────────────────────────────────────────────────────
def detect_s20_24(rates, tf_name="M15", symbol="XAUUSD") -> dict:
    if not is_symbol_enabled_for_s20(symbol):
        return {"signal": "WAIT", "reason": f"S20.24 disabled for {symbol}"}
    if tf_name != "M15":
        return {"signal": "WAIT", "reason": "S20.24 only evaluates on M15"}
    mod = _get_module("s20.24", "strategy20_24")
    if not mod or len(rates) < 30:
        return {"signal": "WAIT", "reason": "S20.24 module not ready"}
    try:
        scale, digits = get_symbol_scale_and_digits(symbol)
        r_eval = rates
        if scale != 1.0:
            r_eval = rates.copy()
            for col in ('open', 'high', 'low', 'close'):
                r_eval[col] = rates[col] * scale
        df = mod.compute_indicators_df(r_eval)
        idx = len(df) - 1
        res = mod.evaluate_wyckoff_vsa(df, idx, tf=tf_name)
        if not res or res.get("signal") == "WAIT":
            res = mod.evaluate_london_close_reversal(df, idx, tf=tf_name)
        if res and res.get("signal") in ("BUY", "SELL"):
            res["sid"] = 20.24
            clean_sym = symbol.split('.')[0]
            res["pattern"] = f"S20.24_Wyckoff_{clean_sym}"
            if scale != 1.0:
                res["entry"] = round(res["entry"] / scale, digits)
                res["sl"] = round(res["sl"] / scale, digits)
                res["tp"] = round(res["tp"] / scale, digits)
                res["risk"] = round(res["risk"] / scale, digits)
            else:
                res["entry"] = round(res["entry"], digits)
                res["sl"] = round(res["sl"], digits)
                res["tp"] = round(res["tp"], digits)
                res["risk"] = round(res["risk"], digits)
        return res if res else {"signal": "WAIT", "reason": "No setup"}
    except Exception as e:
        return {"signal": "WAIT", "reason": f"S20.24 error: {e}"}


# ─────────────────────────────────────────────────────────────────────────────
# 7. S20.28: Macro Session Pool Sweeps
# ─────────────────────────────────────────────────────────────────────────────
def detect_s20_28(rates, tf_name="M15", symbol="XAUUSD") -> dict:
    if not is_symbol_enabled_for_s20(symbol):
        return {"signal": "WAIT", "reason": f"S20.28 disabled for {symbol}"}
    if tf_name != "M15":
        return {"signal": "WAIT", "reason": "S20.28 only evaluates on M15"}
    mod = _get_module("s20.28", "strategy20_28")
    if not mod or len(rates) < 30:
        return {"signal": "WAIT", "reason": "S20.28 module not ready"}
    try:
        scale, digits = get_symbol_scale_and_digits(symbol)
        r_eval = rates
        if scale != 1.0:
            r_eval = rates.copy()
            for col in ('open', 'high', 'low', 'close'):
                r_eval[col] = rates[col] * scale
        df = mod.compute_indicators_df(r_eval)
        idx = len(df) - 1
        res = mod.evaluate_s20_28_bar(df, idx, tf=tf_name)
        if res and "tp" not in res and "tp_scalp" in res:
            res["tp"] = res["tp_scalp"]
        if res and res.get("signal") in ("BUY", "SELL"):
            res["sid"] = 20.28
            clean_sym = symbol.split('.')[0]
            res["pattern"] = f"S20.28_SessionPool_{clean_sym}"
            if scale != 1.0:
                res["entry"] = round(res["entry"] / scale, digits)
                res["sl"] = round(res["sl"] / scale, digits)
                res["tp"] = round(res["tp"] / scale, digits)
                res["risk"] = round(res["risk"] / scale, digits)
            else:
                res["entry"] = round(res["entry"], digits)
                res["sl"] = round(res["sl"], digits)
                res["tp"] = round(res["tp"], digits)
                res["risk"] = round(res["risk"], digits)
        # evaluate_s20_28_bar() คืน None ตรงๆ (ไม่ใช่ dict) ในเคส early-exit
        # ปกติหลายจุด (นอก killzone, ATR ต่ำ, vol_ratio ไม่ถึงเกณฑ์ ฯลฯ) — ต้อง
        # normalize เป็น WAIT dict ก่อนส่งกลับ ไม่งั้น scanner.py's
        # `_r.get("signal")` จะ crash ด้วย AttributeError ทุกครั้งที่ไม่มี setup
        # (เจอจริง 2026-09-16 — spam error.log ทุก ~5-10s บนหลาย profile)
        if res is None:
            return {"signal": "WAIT", "reason": "S20.28 no setup"}
        return res
    except Exception as e:
        return {"signal": "WAIT", "reason": f"S20.28 error: {e}"}


# ─────────────────────────────────────────────────────────────────────────────
# PILOT: S20.40 (Group 1 — M5 SL-First Verified Engine, Octa-Stage Ratchet)
# ─────────────────────────────────────────────────────────────────────────────
S20_40_STAGES = [(1.5, 1.0), (2.4, 2.0), (3.0, 2.8), (3.5, 3.3), (3.8, 3.5), (4.2, 3.9), (4.6, 4.3)]
S20_40_TP_R = 5.0

def detect_s20_40(rates, tf_name="M15", symbol="XAUUSD") -> dict:
    if not is_symbol_enabled_for_s20(symbol):
        return {"signal": "WAIT", "reason": f"S20.40 disabled for {symbol}"}
    if tf_name.upper() not in ("H4", "H2", "H1", "M30", "M15"):
        return {"signal": "WAIT", "reason": f"S20.40 only evaluates H4/H2/H1/M30/M15 (got {tf_name})"}
    mod = _get_module("s20.40", "strategy20_40")
    if not mod or len(rates) < 60:
        return {"signal": "WAIT", "reason": "S20.40 module not ready or rates too short"}
    try:
        scale, digits = get_symbol_scale_and_digits(symbol)
        r_eval = rates
        if scale != 1.0:
            r_eval = rates.copy()
            for col in ('open', 'high', 'low', 'close'):
                r_eval[col] = rates[col] * scale
        df = mod.compute_indicators(r_eval)
        setups = mod.extract_setups(df, tf_name, min_vol=1.20, retest_depth=0.130, sl_mult=0.20, hours=(3, 22), use_pqh=True)
        last_bar_time = int(rates[-1]['time'])
        matches = [s for s in setups if s['time'] == last_bar_time]
        if not matches:
            return {"signal": "WAIT", "reason": "S20.40 no setup on latest closed bar"}
        s = matches[0]
        sig = s["signal"]
        entry, sl, risk = s["entry"], s["sl"], s["risk"]
        tp = entry + (S20_40_TP_R * risk) if sig == "BUY" else entry - (S20_40_TP_R * risk)
        res = {
            "signal": sig, "entry": entry, "sl": sl, "tp": tp, "risk": risk,
            "stages": S20_40_STAGES, "be_r": 0.8, "order_mode": "limit", "cancel_bars": 5,
            "sid": 20.40,
        }
        clean_sym = symbol.split('.')[0]
        res["pattern"] = f"S20.40_Pilot_{clean_sym}"
        if scale != 1.0:
            res["entry"] = round(res["entry"] / scale, digits)
            res["sl"] = round(res["sl"] / scale, digits)
            res["tp"] = round(res["tp"] / scale, digits)
            res["risk"] = round(res["risk"] / scale, digits)
        else:
            res["entry"] = round(res["entry"], digits)
            res["sl"] = round(res["sl"], digits)
            res["tp"] = round(res["tp"], digits)
            res["risk"] = round(res["risk"], digits)
        return res
    except Exception as e:
        return {"signal": "WAIT", "reason": f"S20.40 error: {e}"}


# ─────────────────────────────────────────────────────────────────────────────
# PILOT: S20.30 (Group 2 — Scalp+Runner Dual-Exit, combo_baseline_sweep)
# ─────────────────────────────────────────────────────────────────────────────
def detect_s20_30(rates, tf_name="M15", symbol="XAUUSD") -> dict:
    if not is_symbol_enabled_for_s20(symbol):
        return {"signal": "WAIT", "reason": f"S20.30 disabled for {symbol}"}
    if tf_name.upper() != "M5":
        return {"signal": "WAIT", "reason": f"S20.30 only evaluates M5 (got {tf_name})"}
    mod = _get_module("s20.30", "strategy20_30")
    if not mod or len(rates) < 60:
        return {"signal": "WAIT", "reason": "S20.30 module not ready or rates too short"}
    try:
        scale, digits = get_symbol_scale_and_digits(symbol)
        r_eval = rates
        if scale != 1.0:
            r_eval = rates.copy()
            for col in ('open', 'high', 'low', 'close'):
                r_eval[col] = rates[col] * scale
        df = mod.compute_indicators_df(r_eval)
        idx = len(r_eval) - 1
        res = mod.evaluate_s20_30_bar(df, idx, combo="combo_baseline_sweep")
        if res is None:
            return {"signal": "WAIT", "reason": "S20.30 no setup on latest closed bar"}
        if res.get("signal") in ("BUY", "SELL"):
            sig, entry, risk = res["signal"], res["entry"], res["risk"]
            tp2 = entry + (4.0 * risk) if sig == "BUY" else entry - (4.0 * risk)
            res["tp"] = tp2
            res["stages"] = [(1.8, 0.8)]
            res["order_mode"] = "limit"
            res["cancel_bars"] = 5
            res["sid"] = 20.30
            clean_sym = symbol.split('.')[0]
            res["pattern"] = f"S20.30_Pilot_{clean_sym}"
            if scale != 1.0:
                res["entry"] = round(res["entry"] / scale, digits)
                res["sl"] = round(res["sl"] / scale, digits)
                res["tp"] = round(res["tp"] / scale, digits)
                res["risk"] = round(res["risk"] / scale, digits)
            else:
                res["entry"] = round(res["entry"], digits)
                res["sl"] = round(res["sl"], digits)
                res["tp"] = round(res["tp"], digits)
                res["risk"] = round(res["risk"], digits)
        return res
    except Exception as e:
        return {"signal": "WAIT", "reason": f"S20.30 error: {e}"}


# ─────────────────────────────────────────────────────────────────────────────
# Common SMC Synergy Engine for S20.301, S20.302, S20.303, S20.304
# ─────────────────────────────────────────────────────────────────────────────
def _evaluate_smc_candle(cur, digits=2, is_overlap=False, tp_r=13.43, stages=None, symbol=None, tf_name="M5"):
    # min_atr/min_buf ตาม symbol จริง (แทนค่าคงที่เดิมที่ไม่กรองอะไรเลยสำหรับ Gold) —
    # ให้ตรงกับ backtest (strategy/s20.304/run_s20_304_m5_verified.py::extract_setups_for_symbol)
    # ตามที่พี่ยืนยันว่าอยากให้ live ตรงกับ backtest 2026-09
    sym_upper = (symbol or "").upper()
    if "XAU" in sym_upper:
        min_atr, min_buf = 0.05, 0.22
    elif "XAG" in sym_upper:
        min_atr, min_buf = 0.001, 0.015
    elif sym_upper:
        point = 10 ** (-digits)
        min_atr, min_buf = 2.0 * point, 2.0 * point
    else:
        # ไม่มี symbol ส่งมา (backward-compat) — ใช้สูตรเดิมตาม digits
        min_atr = 0.00005
        min_buf = 0.22 if digits <= 2 else (0.00020 if digits >= 5 else 0.015)

    if pd.isna(cur['atr']) or cur['atr'] <= min_atr or cur['range'] < 0.40 * cur['atr'] or cur['vol_ratio'] < 1.20:
        return {"signal": "WAIT", "reason": "Filters not met"}

    swept_low = (cur['low'] <= cur.get('swing_low_12', cur['low'])) or \
                (cur['low'] <= cur.get('asian_low', cur['low'])) or \
                (not pd.isna(cur.get('fvg_bull_zone')) and cur['low'] <= cur['fvg_bull_zone']) or \
                (not pd.isna(cur.get('fibo_discount_382')) and cur['low'] <= cur['fibo_discount_382']) or \
                (not pd.isna(cur.get('val_proxy')) and cur['low'] <= cur['val_proxy']) or \
                (not pd.isna(cur.get('pdl')) and cur['low'] <= cur['pdl']) or \
                cur.get('swept_htf_low', False) or cur.get('is_spring', False)

    swept_high = (cur['high'] >= cur.get('swing_high_12', cur['high'])) or \
                 (cur['high'] >= cur.get('asian_high', cur['high'])) or \
                 (not pd.isna(cur.get('fvg_bear_zone')) and cur['high'] >= cur['fvg_bear_zone']) or \
                 (not pd.isna(cur.get('fibo_premium_618')) and cur['high'] >= cur['fibo_premium_618']) or \
                 (not pd.isna(cur.get('vah_proxy')) and cur['high'] >= cur['vah_proxy']) or \
                 (not pd.isna(cur.get('pdh')) and cur['high'] >= cur['pdh']) or \
                 cur.get('swept_htf_high', False) or cur.get('is_utad', False)

    bull_ob = cur.get('bull_ob_zone', np.nan)
    bear_ob = cur.get('bear_ob_zone', np.nan)
    ob_mitigated_bull = (not pd.isna(bull_ob) and cur['low'] <= bull_ob)
    ob_mitigated_bear = (not pd.isna(bear_ob) and cur['high'] >= bear_ob)

    bpr_tap_bull = (cur.get('has_bpr', False) and cur['low'] <= cur.get('bpr_high', 0) and cur['high'] >= cur.get('bpr_low', 0))
    bpr_tap_bear = (cur.get('has_bpr', False) and cur['high'] >= cur.get('bpr_low', 0) and cur['low'] <= cur.get('bpr_high', 0))

    is_abs_buy = cur.get('is_absorption_buy', False)
    is_abs_sell = cur.get('is_absorption_sell', False)
    ifvg_buy = cur.get('ifvg_tap_buy', False)
    ifvg_sell = cur.get('ifvg_tap_sell', False)

    bb_buy = (not pd.isna(cur.get('breaker_bull_zone')) and cur['low'] <= cur['breaker_bull_zone'])
    bb_sell = (not pd.isna(cur.get('breaker_bear_zone')) and cur['high'] >= cur['breaker_bear_zone'])

    has_wick_buy = (cur['lower_wick_pct'] >= 0.35) or (cur['lower_wick'] >= 1.0 * cur['body'])
    has_wick_sell = (cur['upper_wick_pct'] >= 0.35) or (cur['upper_wick'] >= 1.0 * cur['body'])

    closed_high = cur['close'] >= (cur['low'] + 0.45 * cur['range'])
    closed_low = cur['close'] <= (cur['high'] - 0.45 * cur['range'])
    is_comp = cur.get('compression_ratio', 1.0) <= 0.70

    sig = "BUY" if ((swept_low or ob_mitigated_bull or bpr_tap_bull or is_abs_buy or ifvg_buy or bb_buy) and has_wick_buy and closed_high) else \
          ("SELL" if ((swept_high or ob_mitigated_bear or bpr_tap_bear or is_abs_sell or ifvg_sell or bb_sell) and has_wick_sell and closed_low) else None)

    if not sig:
        return {"signal": "WAIT", "reason": "No SMC signal"}

    is_hc = (ob_mitigated_bull if sig == "BUY" else ob_mitigated_bear) or \
            (bpr_tap_bull if sig == "BUY" else bpr_tap_bear) or \
            (is_abs_buy if sig == "BUY" else is_abs_sell) or \
            (ifvg_buy if sig == "BUY" else ifvg_sell) or \
            (bb_buy if sig == "BUY" else bb_sell)

    # sl_mult=0.30, active_depth=0.35 ตรงกับ backtest verified (run_s20_304_m5_verified.py line 153-155)
    # XAU min_buf=0.40 (ตรง backtest line 154: max(min_sl_buf, 0.40 if "XAU" in sym_upper))
    sl_mult = 0.30
    _min_buf_floor = 0.40 if (symbol and "XAU" in (symbol or "").upper()) else min_buf
    sl_buf = max(sl_mult * cur['atr'], max(min_buf, _min_buf_floor))
    active_depth = 0.35

    entry = round(cur['low'] + (active_depth * cur['lower_wick']), digits) if sig == "BUY" else round(cur['high'] - (active_depth * cur['upper_wick']), digits)
    sl = round(cur['low'] - sl_buf, digits) if sig == "BUY" else round(cur['high'] + sl_buf, digits)
    risk = entry - sl if sig == "BUY" else sl - entry

    _min_risk = 30 * (10 ** -digits)  # 30 pips equivalent: XAU(d=2)=0.30, JPY(d=3)=0.030, EUR(d=5)=0.0003
    if risk <= 0 or risk < _min_risk:
        return {"signal": "WAIT", "reason": f"Risk {risk:.4f} < {_min_risk:.5f} (30-pip min risk filter)"}

    # cancel_bars unit = bars ของ TF ออเดอร์นั้น (trailing.py ใช้ check_tf = order TF นับ elapsed)
    # สูตร: backtest max_wait = max(12, tf_secs/300) M5-bars = max(60min, tf_secs/5 min)
    #        live unit = TF-bars → max_wait_sec / tf_secs = max(3600, tf_secs) / tf_secs
    #        ย่อ: max(1, 3600 // tf_secs) — ตรงกับ backtest (M15=4, M30=2, H1=1, H4=1 bar)
    _tf_sec_map = {
        "M1": 60, "M5": 300, "M15": 900, "M30": 1800,
        "H1": 3600, "H2": 7200, "H3": 10800, "H4": 14400, "D1": 86400
    }
    _tf_secs = _tf_sec_map.get(str(tf_name).upper(), 300)
    cancel_bars = max(1, 3600 // _tf_secs)

    tp = round(entry + (tp_r * risk), digits) if sig == "BUY" else round(entry - (tp_r * risk), digits)
    return {
        "signal": sig,
        "entry": entry,
        "sl": sl,
        "tp": tp,
        "risk": risk,
        "order_mode": "limit",
        "stages": stages,
        "cancel_bars": cancel_bars,
    }


# ─────────────────────────────────────────────────────────────────────────────
# 8. S20.301: Structural Trend HTF Extension & Sniper
# ─────────────────────────────────────────────────────────────────────────────
def detect_s20_301(rates, tf_name="M15", symbol="XAUUSD") -> dict:
    if not is_symbol_enabled_for_s20(symbol):
        return {"signal": "WAIT", "reason": f"S20.301 disabled for {symbol}"}
    # backtest skip M1,M5,M12 — ล้วเฉพาะ Institutional TF (M15, M30, H1, H4) ตรง line 110
    if tf_name.upper() not in ("M15", "M30", "H1", "H4"):
        return {"signal": "WAIT", "reason": f"S20.301 only evaluates on M15/M30/H1/H4 (got {tf_name})"}
    try:
        from strategy.run_master_s20_marathon_201_to_300 import compute_marathon_300_synergies, make_stages
        _, digits = get_symbol_scale_and_digits(symbol)
        df = _marathon_df(rates, compute_marathon_300_synergies)
        cur = df.iloc[-1]
        stages = make_stages(55)
        res = _evaluate_smc_candle(cur, digits=digits, is_overlap=cur.get('is_ldn_ny_overlap', False), tp_r=13.43, stages=stages, symbol=symbol, tf_name=tf_name)
        if res.get("signal") in ("BUY", "SELL"):
            res["sid"] = 20.301
            clean_sym = symbol.split('.')[0]
            res["pattern"] = f"S20.301_TrendSniper_{clean_sym}"
        return res
    except Exception as e:
        return {"signal": "WAIT", "reason": f"S20.301 error: {e}"}


# ─────────────────────────────────────────────────────────────────────────────
# 9. S20.302: Non-Conflicting Multi-Session Architecture
# ─────────────────────────────────────────────────────────────────────────────
def detect_s20_302(rates, tf_name="M15", symbol="XAUUSD") -> dict:
    if not is_symbol_enabled_for_s20(symbol):
        return {"signal": "WAIT", "reason": f"S20.302 disabled for {symbol}"}
    # backtest skip M1,M5,M12 — ล้วเฉพาะ Institutional TF (M15, M30, H1, H4) ตรง line 110
    if tf_name.upper() not in ("M15", "M30", "H1", "H4"):
        return {"signal": "WAIT", "reason": f"S20.302 only evaluates on M15/M30/H1/H4 (got {tf_name})"}
    try:
        from strategy.run_master_s20_marathon_201_to_300 import compute_marathon_300_synergies, make_stages
        _, digits = get_symbol_scale_and_digits(symbol)
        df = _marathon_df(rates, compute_marathon_300_synergies)
        cur = df.iloc[-1]
        stages = make_stages(55)
        res = _evaluate_smc_candle(cur, digits=digits, is_overlap=cur.get('is_ldn_ny_overlap', False), tp_r=13.43, stages=stages, symbol=symbol, tf_name=tf_name)
        if res.get("signal") in ("BUY", "SELL"):
            res["sid"] = 20.302
            clean_sym = symbol.split('.')[0]
            res["pattern"] = f"S20.302_MultiSession_{clean_sym}"
        return res
    except Exception as e:
        return {"signal": "WAIT", "reason": f"S20.302 error: {e}"}


# ─────────────────────────────────────────────────────────────────────────────
# 10. S20.303: Dynamic Volatility-Scaled Engine (Gold Solo Zenith)
# ─────────────────────────────────────────────────────────────────────────────
def detect_s20_303(rates, tf_name="M15", symbol="XAUUSD") -> dict:
    if not is_symbol_enabled_for_s20(symbol):
        return {"signal": "WAIT", "reason": f"S20.303 disabled for {symbol}"}
    # backtest skip M1,M5,M12 — ล้วเฉพาะ Institutional TF (M15, M30, H1, H4) ตรง line 110
    if tf_name.upper() not in ("M15", "M30", "H1", "H4"):
        return {"signal": "WAIT", "reason": f"S20.303 only evaluates on M15/M30/H1/H4 (got {tf_name})"}
    try:
        from strategy.run_master_s20_marathon_201_to_300 import compute_marathon_300_synergies, make_stages
        _, digits = get_symbol_scale_and_digits(symbol)
        df = _marathon_df(rates, compute_marathon_300_synergies)
        cur = df.iloc[-1]
        stages = make_stages(56)
        # tp_r=13.43 ตรง backtest (run_s20_304_m5_verified.py line 593: tp_r=13.43 สำหรับทุกกลยุทธ์)
        res = _evaluate_smc_candle(cur, digits=digits, is_overlap=cur.get('is_ldn_ny_overlap', False), tp_r=13.43, stages=stages, symbol=symbol, tf_name=tf_name)
        if res.get("signal") in ("BUY", "SELL"):
            res["sid"] = 20.303
            clean_sym = symbol.split('.')[0]
            res["pattern"] = f"S20.303_VolScaled_{clean_sym}"
        return res
    except Exception as e:
        return {"signal": "WAIT", "reason": f"S20.303 error: {e}"}


# ─────────────────────────────────────────────────────────────────────────────
# 11. S20.304: The Sovereign Dual-Asset Citadel Matrix (Cross-Asset Zenith)
# ─────────────────────────────────────────────────────────────────────────────
def detect_s20_304(rates, tf_name="M15", symbol="XAUUSD") -> dict:
    if not is_symbol_enabled_for_s20(symbol):
        return {"signal": "WAIT", "reason": f"S20.304 disabled for {symbol}"}
    # backtest skip M1,M5,M12 — ล้วเฉพาะ Institutional TF (M15, M30, H1, H4) ตรง line 110
    if tf_name.upper() not in ("M15", "M30", "H1", "H4"):
        return {"signal": "WAIT", "reason": f"S20.304 only evaluates on M15/M30/H1/H4 (got {tf_name})"}
    try:
        from strategy.run_master_s20_marathon_201_to_300 import compute_marathon_300_synergies, make_stages
        _, digits = get_symbol_scale_and_digits(symbol)
        df = _marathon_df(rates, compute_marathon_300_synergies)
        cur = df.iloc[-1]
        stages = make_stages(55)
        res = _evaluate_smc_candle(cur, digits=digits, is_overlap=cur.get('is_ldn_ny_overlap', False), tp_r=13.43, stages=stages, symbol=symbol, tf_name=tf_name)
        if res.get("signal") in ("BUY", "SELL"):
            res["sid"] = 20.304
            clean_sym = symbol.split('.')[0]
            res["pattern"] = f"S20.304_{clean_sym}"
        return res
    except Exception as e:
        return {"signal": "WAIT", "reason": f"S20.304 error: {e}"}


# ─────────────────────────────────────────────────────────────────────────────
# Dispatcher
# ─────────────────────────────────────────────────────────────────────────────
S20_131_STAGES = [(1.5, 1.0), (2.4, 2.0), (3.0, 2.8), (3.5, 3.3), (3.8, 3.5), (4.2, 3.9), (4.6, 4.3), (5.2, 4.9), (5.5, 5.2), (5.6, 5.4), (5.8, 5.6), (6.0, 5.8), (6.15, 5.95), (6.35, 6.15), (6.5, 6.3), (6.7, 6.5), (6.85, 6.65), (7.0, 6.8), (7.15, 6.95), (7.3, 7.1), (7.45, 7.25), (7.6, 7.4), (7.75, 7.55), (7.9, 7.7), (8.05, 7.85), (8.2, 8.0), (8.35, 8.15), (8.5, 8.3), (8.65, 8.45), (8.8, 8.6), (8.95, 8.75), (9.1, 8.9), (9.25, 9.05), (9.4, 9.2), (9.55, 9.35)]

S20_132_STAGES = [(1.5, 1.0), (2.4, 2.0), (3.0, 2.8), (3.5, 3.3), (3.8, 3.5), (4.2, 3.9), (4.6, 4.3), (5.2, 4.9), (5.5, 5.2), (5.6, 5.4), (5.8, 5.6), (6.0, 5.8), (6.15, 5.95), (6.35, 6.15), (6.5, 6.3), (6.7, 6.5), (6.85, 6.65), (7.0, 6.8), (7.15, 6.95), (7.3, 7.1), (7.45, 7.25), (7.6, 7.4), (7.75, 7.55), (7.9, 7.7), (8.05, 7.85), (8.2, 8.0), (8.35, 8.15), (8.5, 8.3), (8.65, 8.45), (8.8, 8.6), (8.95, 8.75), (9.1, 8.9), (9.25, 9.05), (9.4, 9.2), (9.55, 9.35)]

S20_133_STAGES = [(1.5, 1.0), (2.4, 2.0), (3.0, 2.8), (3.5, 3.3), (3.8, 3.5), (4.2, 3.9), (4.6, 4.3), (5.2, 4.9), (5.5, 5.2), (5.6, 5.4), (5.8, 5.6), (6.0, 5.8), (6.15, 5.95), (6.35, 6.15), (6.5, 6.3), (6.7, 6.5), (6.85, 6.65), (7.0, 6.8), (7.15, 6.95), (7.3, 7.1), (7.45, 7.25), (7.6, 7.4), (7.75, 7.55), (7.9, 7.7), (8.05, 7.85), (8.2, 8.0), (8.35, 8.15), (8.5, 8.3), (8.65, 8.45), (8.8, 8.6), (8.95, 8.75), (9.1, 8.9), (9.25, 9.05), (9.4, 9.2), (9.55, 9.35), (9.7, 9.5), (9.85, 9.65)]

S20_134_STAGES = [(1.5, 1.0), (2.4, 2.0), (3.0, 2.8), (3.5, 3.3), (3.8, 3.5), (4.2, 3.9), (4.6, 4.3), (5.2, 4.9), (5.5, 5.2), (5.6, 5.4), (5.8, 5.6), (6.0, 5.8), (6.15, 5.95), (6.35, 6.15), (6.5, 6.3), (6.7, 6.5), (6.85, 6.65), (7.0, 6.8), (7.15, 6.95), (7.3, 7.1), (7.45, 7.25), (7.6, 7.4), (7.75, 7.55), (7.9, 7.7), (8.05, 7.85), (8.2, 8.0), (8.35, 8.15), (8.5, 8.3), (8.65, 8.45), (8.8, 8.6), (8.95, 8.75), (9.1, 8.9), (9.25, 9.05), (9.4, 9.2), (9.55, 9.35), (9.7, 9.5), (9.85, 9.65), (10.0, 9.8)]

S20_135_STAGES = [(1.5, 1.0), (2.4, 2.0), (3.0, 2.8), (3.5, 3.3), (3.8, 3.5), (4.2, 3.9), (4.6, 4.3), (5.2, 4.9), (5.5, 5.2), (5.6, 5.4), (5.8, 5.6), (6.0, 5.8), (6.15, 5.95), (6.35, 6.15), (6.5, 6.3), (6.7, 6.5), (6.85, 6.65), (7.0, 6.8), (7.15, 6.95), (7.3, 7.1), (7.45, 7.25), (7.6, 7.4), (7.75, 7.55), (7.9, 7.7), (8.05, 7.85), (8.2, 8.0), (8.35, 8.15), (8.5, 8.3), (8.65, 8.45), (8.8, 8.6), (8.95, 8.75), (9.1, 8.9), (9.25, 9.05), (9.4, 9.2), (9.55, 9.35), (9.7, 9.5), (9.85, 9.65), (10.0, 9.8)]

S20_136_STAGES = [(1.5, 1.0), (2.4, 2.0), (3.0, 2.8), (3.5, 3.3), (3.8, 3.5), (4.2, 3.9), (4.6, 4.3), (5.2, 4.9), (5.5, 5.2), (5.6, 5.4), (5.8, 5.6), (6.0, 5.8), (6.15, 5.95), (6.35, 6.15), (6.5, 6.3), (6.7, 6.5), (6.85, 6.65), (7.0, 6.8), (7.15, 6.95), (7.3, 7.1), (7.45, 7.25), (7.6, 7.4), (7.75, 7.55), (7.9, 7.7), (8.05, 7.85), (8.2, 8.0), (8.35, 8.15), (8.5, 8.3), (8.65, 8.45), (8.8, 8.6), (8.95, 8.75), (9.1, 8.9), (9.25, 9.05), (9.4, 9.2), (9.55, 9.35), (9.7, 9.5), (9.85, 9.65), (10.0, 9.8), (10.15, 9.95), (10.3, 10.1), (10.45, 10.25), (10.6, 10.4)]

S20_137_STAGES = [(1.5, 1.0), (2.4, 2.0), (3.0, 2.8), (3.5, 3.3), (3.8, 3.5), (4.2, 3.9), (4.6, 4.3), (5.2, 4.9), (5.5, 5.2), (5.6, 5.4), (5.8, 5.6), (6.0, 5.8), (6.15, 5.95), (6.35, 6.15), (6.5, 6.3), (6.7, 6.5), (6.85, 6.65), (7.0, 6.8), (7.15, 6.95), (7.3, 7.1), (7.45, 7.25), (7.6, 7.4), (7.75, 7.55), (7.9, 7.7), (8.05, 7.85), (8.2, 8.0), (8.35, 8.15), (8.5, 8.3), (8.65, 8.45), (8.8, 8.6), (8.95, 8.75), (9.1, 8.9), (9.25, 9.05), (9.4, 9.2), (9.55, 9.35), (9.7, 9.5), (9.85, 9.65), (10.0, 9.8), (10.15, 9.95), (10.3, 10.1), (10.45, 10.25), (10.6, 10.4), (10.75, 10.55)]

S20_138_STAGES = [(1.5, 1.0), (2.4, 2.0), (3.0, 2.8), (3.5, 3.3), (3.8, 3.5), (4.2, 3.9), (4.6, 4.3), (5.2, 4.9), (5.5, 5.2), (5.6, 5.4), (5.8, 5.6), (6.0, 5.8), (6.15, 5.95), (6.35, 6.15), (6.5, 6.3), (6.7, 6.5), (6.85, 6.65), (7.0, 6.8), (7.15, 6.95), (7.3, 7.1), (7.45, 7.25), (7.6, 7.4), (7.75, 7.55), (7.9, 7.7), (8.05, 7.85), (8.2, 8.0), (8.35, 8.15), (8.5, 8.3), (8.65, 8.45), (8.8, 8.6), (8.95, 8.75), (9.1, 8.9), (9.25, 9.05), (9.4, 9.2), (9.55, 9.35), (9.7, 9.5), (9.85, 9.65), (10.0, 9.8), (10.15, 9.95), (10.3, 10.1), (10.45, 10.25), (10.6, 10.4), (10.75, 10.55), (10.9, 10.7), (11.05, 10.85), (11.2, 11.0)]

S20_139_STAGES = [(1.5, 1.0), (2.4, 2.0), (3.0, 2.8), (3.5, 3.3), (3.8, 3.5), (4.2, 3.9), (4.6, 4.3), (5.2, 4.9), (5.5, 5.2), (5.6, 5.4), (5.8, 5.6), (6.0, 5.8), (6.15, 5.95), (6.35, 6.15), (6.5, 6.3), (6.7, 6.5), (6.85, 6.65), (7.0, 6.8), (7.15, 6.95), (7.3, 7.1), (7.45, 7.25), (7.6, 7.4), (7.75, 7.55), (7.9, 7.7), (8.05, 7.85), (8.2, 8.0), (8.35, 8.15), (8.5, 8.3), (8.65, 8.45), (8.8, 8.6), (8.95, 8.75), (9.1, 8.9), (9.25, 9.05), (9.4, 9.2), (9.55, 9.35), (9.7, 9.5), (9.85, 9.65), (10.0, 9.8), (10.15, 9.95), (10.3, 10.1), (10.45, 10.25), (10.6, 10.4), (10.75, 10.55), (10.9, 10.7), (11.05, 10.85), (11.2, 11.0), (11.35, 11.15), (11.5, 11.3), (11.65, 11.45), (11.8, 11.6), (11.95, 11.75)]

S20_300_STAGES = [(1.5, 1.0), (2.4, 2.0), (3.0, 2.8), (3.5, 3.3), (3.8, 3.5), (4.2, 3.9), (4.6, 4.3), (5.2, 4.9), (5.5, 5.2), (5.6, 5.4), (5.8, 5.6), (6.0, 5.8), (6.15, 5.95), (6.35, 6.15), (6.5, 6.3), (6.7, 6.5), (6.85, 6.65), (7.0, 6.8), (7.15, 6.95), (7.3, 7.1), (7.45, 7.25), (7.6, 7.4), (7.75, 7.55), (7.9, 7.7), (8.05, 7.85), (8.2, 8.0), (8.35, 8.15), (8.5, 8.3), (8.65, 8.45), (8.8, 8.6), (8.95, 8.75), (9.1, 8.9), (9.25, 9.05), (9.4, 9.2), (9.55, 9.35), (9.7, 9.5), (9.85, 9.65), (10.0, 9.8), (10.15, 9.95), (10.3, 10.1), (10.45, 10.25), (10.6, 10.4), (10.75, 10.55), (10.9, 10.7), (11.05, 10.85), (11.2, 11.0), (11.35, 11.15), (11.5, 11.3), (11.65, 11.45), (11.8, 11.6), (11.95, 11.75), (12.1, 11.9), (12.25, 12.05), (12.4, 12.2), (12.55, 12.35)]


def _bar_logic_s20_131(cur, tf):
    if pd.isna(cur['atr']) or cur['atr'] <= 0.05 or cur['range'] < 0.45 * cur['atr'] or cur['vol_ratio'] < 1.11:
        return None
    swept_low = (cur['low'] <= cur['swing_low_12']) or (cur['low'] <= cur['asian_low']) or                         (not pd.isna(cur.get('fvg_bull_zone')) and cur['low'] <= cur['fvg_bull_zone']) or                         (not pd.isna(cur.get('fibo_discount_382')) and cur['low'] <= cur['fibo_discount_382']) or                         (not pd.isna(cur.get('val_proxy')) and cur['low'] <= cur['val_proxy']) or                         (not pd.isna(cur.get('pdl')) and cur['low'] <= cur['pdl'])

    swept_high = (cur['high'] >= cur['swing_high_12']) or (cur['high'] >= cur['asian_high']) or                          (not pd.isna(cur.get('fvg_bear_zone')) and cur['high'] >= cur['fvg_bear_zone']) or                          (not pd.isna(cur.get('fibo_premium_618')) and cur['high'] >= cur['fibo_premium_618']) or                          (not pd.isna(cur.get('vah_proxy')) and cur['high'] >= cur['vah_proxy']) or                          (not pd.isna(cur.get('pdh')) and cur['high'] >= cur['pdh'])

    has_wick_buy = (cur['lower_wick_pct'] >= 0.14) or (cur['lower_wick'] >= 1.1 * cur['body'])
    has_wick_sell = (cur['upper_wick_pct'] >= 0.14) or (cur['upper_wick'] >= 1.1 * cur['body'])
    closed_high = cur['close'] >= (cur['low'] + 0.45 * cur['range'])
    closed_low = cur['close'] <= (cur['high'] - 0.45 * cur['range'])

    is_comp = cur['compression_ratio'] <= 0.70
    sig = "BUY" if (swept_low and has_wick_buy and closed_high) else ("SELL" if (swept_high and has_wick_sell and closed_low) else None)
    if sig:
        sl_mult = 0.190 if is_comp else 0.198
        sl_buf = max(sl_mult * cur['atr'], 0.22)
        active_depth = 0.124 if is_comp else 0.125
        entry = round(cur['low'] + (active_depth * cur['lower_wick']), 2) if sig == "BUY" else round(cur['high'] - (active_depth * cur['upper_wick']), 2)
        sl = round(cur['low'] - sl_buf, 2) if sig == "BUY" else round(cur['high'] + sl_buf, 2)
        risk = entry - sl if sig == "BUY" else sl - entry
        if risk > 0:
            return {"time": int(cur['time']), "signal": sig, "entry": entry, "sl": sl, "risk": risk, "atr": cur['atr'], "tf": tf}
    return None


def _bar_logic_s20_132(cur, tf):
    if pd.isna(cur['atr']) or cur['atr'] <= 0.05 or cur['range'] < 0.45 * cur['atr'] or cur['vol_ratio'] < 1.11:
        return None
    swept_low = (cur['low'] <= cur['swing_low_12']) or (cur['low'] <= cur['asian_low']) or                         (not pd.isna(cur.get('fvg_bull_zone')) and cur['low'] <= cur['fvg_bull_zone']) or                         (not pd.isna(cur.get('fibo_discount_382')) and cur['low'] <= cur['fibo_discount_382']) or                         (not pd.isna(cur.get('val_proxy')) and cur['low'] <= cur['val_proxy']) or                         (not pd.isna(cur.get('pdl')) and cur['low'] <= cur['pdl'])

    swept_high = (cur['high'] >= cur['swing_high_12']) or (cur['high'] >= cur['asian_high']) or                          (not pd.isna(cur.get('fvg_bear_zone')) and cur['high'] >= cur['fvg_bear_zone']) or                          (not pd.isna(cur.get('fibo_premium_618')) and cur['high'] >= cur['fibo_premium_618']) or                          (not pd.isna(cur.get('vah_proxy')) and cur['high'] >= cur['vah_proxy']) or                          (not pd.isna(cur.get('pdh')) and cur['high'] >= cur['pdh'])

    bull_ob = cur['bull_ob_zone']
    bear_ob = cur['bear_ob_zone']
    ob_mitigated_bull = (not pd.isna(bull_ob) and cur['low'] <= bull_ob)
    ob_mitigated_bear = (not pd.isna(bear_ob) and cur['high'] >= bear_ob)

    has_wick_buy = (cur['lower_wick_pct'] >= 0.14) or (cur['lower_wick'] >= 1.1 * cur['body'])
    has_wick_sell = (cur['upper_wick_pct'] >= 0.14) or (cur['upper_wick'] >= 1.1 * cur['body'])
    closed_high = cur['close'] >= (cur['low'] + 0.45 * cur['range'])
    closed_low = cur['close'] <= (cur['high'] - 0.45 * cur['range'])

    sig = "BUY" if ((swept_low or ob_mitigated_bull) and has_wick_buy and closed_high) else                   ("SELL" if ((swept_high or ob_mitigated_bear) and has_wick_sell and closed_low) else None)
    if sig:
        sl_mult = 0.188 if (ob_mitigated_bull if sig == "BUY" else ob_mitigated_bear) else 0.195
        sl_buf = max(sl_mult * cur['atr'], 0.22)
        active_depth = 0.123 if (ob_mitigated_bull if sig == "BUY" else ob_mitigated_bear) else 0.125
        entry = round(cur['low'] + (active_depth * cur['lower_wick']), 2) if sig == "BUY" else round(cur['high'] - (active_depth * cur['upper_wick']), 2)
        sl = round(cur['low'] - sl_buf, 2) if sig == "BUY" else round(cur['high'] + sl_buf, 2)
        risk = entry - sl if sig == "BUY" else sl - entry
        if risk > 0:
            return {"time": int(cur['time']), "signal": sig, "entry": entry, "sl": sl, "risk": risk, "atr": cur['atr'], "tf": tf}
    return None


def _bar_logic_s20_133(cur, tf):
    if pd.isna(cur['atr']) or cur['atr'] <= 0.05 or cur['range'] < 0.45 * cur['atr'] or cur['vol_ratio'] < 1.11:
        return None
    swept_low = (cur['low'] <= cur['swing_low_12']) or (cur['low'] <= cur['asian_low']) or                         (not pd.isna(cur.get('fvg_bull_zone')) and cur['low'] <= cur['fvg_bull_zone']) or                         (not pd.isna(cur.get('fibo_discount_382')) and cur['low'] <= cur['fibo_discount_382']) or                         (not pd.isna(cur.get('val_proxy')) and cur['low'] <= cur['val_proxy']) or                         (not pd.isna(cur.get('pdl')) and cur['low'] <= cur['pdl'])

    swept_high = (cur['high'] >= cur['swing_high_12']) or (cur['high'] >= cur['asian_high']) or                          (not pd.isna(cur.get('fvg_bear_zone')) and cur['high'] >= cur['fvg_bear_zone']) or                          (not pd.isna(cur.get('fibo_premium_618')) and cur['high'] >= cur['fibo_premium_618']) or                          (not pd.isna(cur.get('vah_proxy')) and cur['high'] >= cur['vah_proxy']) or                          (not pd.isna(cur.get('pdh')) and cur['high'] >= cur['pdh'])

    bull_ob = cur['bull_ob_zone']
    bear_ob = cur['bear_ob_zone']
    ob_mitigated_bull = (not pd.isna(bull_ob) and cur['low'] <= bull_ob)
    ob_mitigated_bear = (not pd.isna(bear_ob) and cur['high'] >= bear_ob)

    is_comp = cur['compression_ratio'] <= 0.70

    has_wick_buy = (cur['lower_wick_pct'] >= 0.14) or (cur['lower_wick'] >= 1.1 * cur['body'])
    has_wick_sell = (cur['upper_wick_pct'] >= 0.14) or (cur['upper_wick'] >= 1.1 * cur['body'])
    closed_high = cur['close'] >= (cur['low'] + 0.45 * cur['range'])
    closed_low = cur['close'] <= (cur['high'] - 0.45 * cur['range'])

    sig = "BUY" if ((swept_low or ob_mitigated_bull) and has_wick_buy and closed_high) else                   ("SELL" if ((swept_high or ob_mitigated_bear) and has_wick_sell and closed_low) else None)
    if sig:
        is_high_conviction = (ob_mitigated_bull if sig == "BUY" else ob_mitigated_bear)
        sl_mult = 0.186 if is_high_conviction else (0.190 if is_comp else 0.195)
        sl_buf = max(sl_mult * cur['atr'], 0.22)
        active_depth = 0.122 if is_high_conviction else (0.124 if is_comp else 0.125)
        entry = round(cur['low'] + (active_depth * cur['lower_wick']), 2) if sig == "BUY" else round(cur['high'] - (active_depth * cur['upper_wick']), 2)
        sl = round(cur['low'] - sl_buf, 2) if sig == "BUY" else round(cur['high'] + sl_buf, 2)
        risk = entry - sl if sig == "BUY" else sl - entry
        if risk > 0:
            return {"time": int(cur['time']), "signal": sig, "entry": entry, "sl": sl, "risk": risk, "atr": cur['atr'], "tf": tf}
    return None


def _bar_logic_s20_134(cur, tf):
    if pd.isna(cur['atr']) or cur['atr'] <= 0.05 or cur['range'] < 0.45 * cur['atr'] or cur['vol_ratio'] < 1.11:
        return None
    swept_low = (cur['low'] <= cur['swing_low_12']) or (cur['low'] <= cur['asian_low']) or                         (not pd.isna(cur.get('fvg_bull_zone')) and cur['low'] <= cur['fvg_bull_zone']) or                         (not pd.isna(cur.get('fibo_discount_382')) and cur['low'] <= cur['fibo_discount_382']) or                         (not pd.isna(cur.get('val_proxy')) and cur['low'] <= cur['val_proxy']) or                         (not pd.isna(cur.get('pdl')) and cur['low'] <= cur['pdl'])

    swept_high = (cur['high'] >= cur['swing_high_12']) or (cur['high'] >= cur['asian_high']) or                          (not pd.isna(cur.get('fvg_bear_zone')) and cur['high'] >= cur['fvg_bear_zone']) or                          (not pd.isna(cur.get('fibo_premium_618')) and cur['high'] >= cur['fibo_premium_618']) or                          (not pd.isna(cur.get('vah_proxy')) and cur['high'] >= cur['vah_proxy']) or                          (not pd.isna(cur.get('pdh')) and cur['high'] >= cur['pdh'])

    bull_ob = cur['bull_ob_zone']
    bear_ob = cur['bear_ob_zone']
    ob_mitigated_bull = (not pd.isna(bull_ob) and cur['low'] <= bull_ob)
    ob_mitigated_bear = (not pd.isna(bear_ob) and cur['high'] >= bear_ob)

    bpr_tap_bull = (cur['has_bpr'] and cur['low'] <= cur['bpr_high'] and cur['high'] >= cur['bpr_low'])
    bpr_tap_bear = (cur['has_bpr'] and cur['high'] >= cur['bpr_low'] and cur['low'] <= cur['bpr_high'])

    has_wick_buy = (cur['lower_wick_pct'] >= 0.14) or (cur['lower_wick'] >= 1.1 * cur['body'])
    has_wick_sell = (cur['upper_wick_pct'] >= 0.14) or (cur['upper_wick'] >= 1.1 * cur['body'])
    closed_high = cur['close'] >= (cur['low'] + 0.45 * cur['range'])
    closed_low = cur['close'] <= (cur['high'] - 0.45 * cur['range'])

    is_comp = cur['compression_ratio'] <= 0.70

    sig = "BUY" if ((swept_low or ob_mitigated_bull or bpr_tap_bull) and has_wick_buy and closed_high) else                   ("SELL" if ((swept_high or ob_mitigated_bear or bpr_tap_bear) and has_wick_sell and closed_low) else None)

    if sig:
        is_hc = (ob_mitigated_bull if sig == "BUY" else ob_mitigated_bear) or (bpr_tap_bull if sig == "BUY" else bpr_tap_bear)
        sl_mult = 0.188 if is_hc else (0.190 if is_comp else 0.195)
        sl_buf = max(sl_mult * cur['atr'], 0.22)
        active_depth = 0.122 if is_hc else (0.124 if is_comp else 0.125)
        entry = round(cur['low'] + (active_depth * cur['lower_wick']), 2) if sig == "BUY" else round(cur['high'] - (active_depth * cur['upper_wick']), 2)
        sl = round(cur['low'] - sl_buf, 2) if sig == "BUY" else round(cur['high'] + sl_buf, 2)
        risk = entry - sl if sig == "BUY" else sl - entry
        if risk > 0:
            return {"time": int(cur['time']), "signal": sig, "entry": entry, "sl": sl, "risk": risk, "atr": cur['atr'], "tf": tf}
    return None


def _bar_logic_s20_135(cur, tf):
    if pd.isna(cur['atr']) or cur['atr'] <= 0.05 or cur['range'] < 0.45 * cur['atr'] or cur['vol_ratio'] < 1.11:
        return None

    swept_low = (cur['low'] <= cur['swing_low_12']) or (cur['low'] <= cur['asian_low']) or                         (not pd.isna(cur.get('fvg_bull_zone')) and cur['low'] <= cur['fvg_bull_zone']) or                         (not pd.isna(cur.get('fibo_discount_382')) and cur['low'] <= cur['fibo_discount_382']) or                         (not pd.isna(cur.get('val_proxy')) and cur['low'] <= cur['val_proxy']) or                         (not pd.isna(cur.get('pdl')) and cur['low'] <= cur['pdl'])

    swept_high = (cur['high'] >= cur['swing_high_12']) or (cur['high'] >= cur['asian_high']) or                          (not pd.isna(cur.get('fvg_bear_zone')) and cur['high'] >= cur['fvg_bear_zone']) or                          (not pd.isna(cur.get('fibo_premium_618')) and cur['high'] >= cur['fibo_premium_618']) or                          (not pd.isna(cur.get('vah_proxy')) and cur['high'] >= cur['vah_proxy']) or                          (not pd.isna(cur.get('pdh')) and cur['high'] >= cur['pdh'])

    bull_ob = cur['bull_ob_zone']
    bear_ob = cur['bear_ob_zone']
    ob_mitigated_bull = (not pd.isna(bull_ob) and cur['low'] <= bull_ob)
    ob_mitigated_bear = (not pd.isna(bear_ob) and cur['high'] >= bear_ob)

    bpr_tap_bull = (cur['has_bpr'] and cur['low'] <= cur['bpr_high'] and cur['high'] >= cur['bpr_low'])
    bpr_tap_bear = (cur['has_bpr'] and cur['high'] >= cur['bpr_low'] and cur['low'] <= cur['bpr_high'])

    is_abs_buy = cur['is_absorption_buy']
    is_abs_sell = cur['is_absorption_sell']

    has_wick_buy = (cur['lower_wick_pct'] >= 0.14) or (cur['lower_wick'] >= 1.1 * cur['body'])
    has_wick_sell = (cur['upper_wick_pct'] >= 0.14) or (cur['upper_wick'] >= 1.1 * cur['body'])
    closed_high = cur['close'] >= (cur['low'] + 0.45 * cur['range'])
    closed_low = cur['close'] <= (cur['high'] - 0.45 * cur['range'])

    is_comp = cur['compression_ratio'] <= 0.70

    sig = "BUY" if ((swept_low or ob_mitigated_bull or bpr_tap_bull or is_abs_buy) and has_wick_buy and closed_high) else                   ("SELL" if ((swept_high or ob_mitigated_bear or bpr_tap_bear or is_abs_sell) and has_wick_sell and closed_low) else None)

    if sig:
        is_hc = (ob_mitigated_bull if sig == "BUY" else ob_mitigated_bear) or                         (bpr_tap_bull if sig == "BUY" else bpr_tap_bear) or                         (is_abs_buy if sig == "BUY" else is_abs_sell)
        sl_mult = 0.188 if is_hc else (0.190 if is_comp else 0.195)
        sl_buf = max(sl_mult * cur['atr'], 0.22)
        active_depth = 0.121 if is_hc else (0.124 if is_comp else 0.125)
        entry = round(cur['low'] + (active_depth * cur['lower_wick']), 2) if sig == "BUY" else round(cur['high'] - (active_depth * cur['upper_wick']), 2)
        sl = round(cur['low'] - sl_buf, 2) if sig == "BUY" else round(cur['high'] + sl_buf, 2)
        risk = entry - sl if sig == "BUY" else sl - entry
        if risk > 0:
            return {"time": int(cur['time']), "signal": sig, "entry": entry, "sl": sl, "risk": risk, "atr": cur['atr'], "tf": tf}
    return None


def _bar_logic_s20_136(cur, tf):
    if pd.isna(cur['atr']) or cur['atr'] <= 0.05 or cur['range'] < 0.45 * cur['atr'] or cur['vol_ratio'] < 1.11:
        return None

    swept_low = (cur['low'] <= cur['swing_low_12']) or (cur['low'] <= cur['asian_low']) or                         (not pd.isna(cur.get('fvg_bull_zone')) and cur['low'] <= cur['fvg_bull_zone']) or                         (not pd.isna(cur.get('fibo_discount_382')) and cur['low'] <= cur['fibo_discount_382']) or                         (not pd.isna(cur.get('val_proxy')) and cur['low'] <= cur['val_proxy']) or                         (not pd.isna(cur.get('pdl')) and cur['low'] <= cur['pdl'])

    swept_high = (cur['high'] >= cur['swing_high_12']) or (cur['high'] >= cur['asian_high']) or                          (not pd.isna(cur.get('fvg_bear_zone')) and cur['high'] >= cur['fvg_bear_zone']) or                          (not pd.isna(cur.get('fibo_premium_618')) and cur['high'] >= cur['fibo_premium_618']) or                          (not pd.isna(cur.get('vah_proxy')) and cur['high'] >= cur['vah_proxy']) or                          (not pd.isna(cur.get('pdh')) and cur['high'] >= cur['pdh'])

    bull_ob = cur['bull_ob_zone']
    bear_ob = cur['bear_ob_zone']
    ob_mitigated_bull = (not pd.isna(bull_ob) and cur['low'] <= bull_ob)
    ob_mitigated_bear = (not pd.isna(bear_ob) and cur['high'] >= bear_ob)

    bpr_tap_bull = (cur['has_bpr'] and cur['low'] <= cur['bpr_high'] and cur['high'] >= cur['bpr_low'])
    bpr_tap_bear = (cur['has_bpr'] and cur['high'] >= cur['bpr_low'] and cur['low'] <= cur['bpr_high'])

    is_abs_buy = cur['is_absorption_buy']
    is_abs_sell = cur['is_absorption_sell']

    has_wick_buy = (cur['lower_wick_pct'] >= 0.14) or (cur['lower_wick'] >= 1.1 * cur['body'])
    has_wick_sell = (cur['upper_wick_pct'] >= 0.14) or (cur['upper_wick'] >= 1.1 * cur['body'])
    closed_high = cur['close'] >= (cur['low'] + 0.45 * cur['range'])
    closed_low = cur['close'] <= (cur['high'] - 0.45 * cur['range'])

    is_comp = cur['compression_ratio'] <= 0.70

    sig = "BUY" if ((swept_low or ob_mitigated_bull or bpr_tap_bull or is_abs_buy) and has_wick_buy and closed_high) else                   ("SELL" if ((swept_high or ob_mitigated_bear or bpr_tap_bear or is_abs_sell) and has_wick_sell and closed_low) else None)

    if sig:
        is_hc = (ob_mitigated_bull if sig == "BUY" else ob_mitigated_bear) or                         (bpr_tap_bull if sig == "BUY" else bpr_tap_bear) or                         (is_abs_buy if sig == "BUY" else is_abs_sell)
        sl_mult = 0.188 if is_hc else (0.190 if is_comp else 0.195)
        sl_buf = max(sl_mult * cur['atr'], 0.22)
        active_depth = 0.121 if is_hc else (0.124 if is_comp else 0.125)
        entry = round(cur['low'] + (active_depth * cur['lower_wick']), 2) if sig == "BUY" else round(cur['high'] - (active_depth * cur['upper_wick']), 2)
        sl = round(cur['low'] - sl_buf, 2) if sig == "BUY" else round(cur['high'] + sl_buf, 2)
        risk = entry - sl if sig == "BUY" else sl - entry
        if risk > 0:
            return {"time": int(cur['time']), "signal": sig, "entry": entry, "sl": sl, "risk": risk, "atr": cur['atr'], "tf": tf}
    return None


def _bar_logic_s20_137(cur, tf):
    if pd.isna(cur['atr']) or cur['atr'] <= 0.05 or cur['range'] < 0.45 * cur['atr'] or cur['vol_ratio'] < 1.11:
        return None

    swept_low = (cur['low'] <= cur['swing_low_12']) or (cur['low'] <= cur['asian_low']) or                         (not pd.isna(cur.get('fvg_bull_zone')) and cur['low'] <= cur['fvg_bull_zone']) or                         (not pd.isna(cur.get('fibo_discount_382')) and cur['low'] <= cur['fibo_discount_382']) or                         (not pd.isna(cur.get('val_proxy')) and cur['low'] <= cur['val_proxy']) or                         (not pd.isna(cur.get('pdl')) and cur['low'] <= cur['pdl'])

    swept_high = (cur['high'] >= cur['swing_high_12']) or (cur['high'] >= cur['asian_high']) or                          (not pd.isna(cur.get('fvg_bear_zone')) and cur['high'] >= cur['fvg_bear_zone']) or                          (not pd.isna(cur.get('fibo_premium_618')) and cur['high'] >= cur['fibo_premium_618']) or                          (not pd.isna(cur.get('vah_proxy')) and cur['high'] >= cur['vah_proxy']) or                          (not pd.isna(cur.get('pdh')) and cur['high'] >= cur['pdh'])

    bull_ob = cur['bull_ob_zone']
    bear_ob = cur['bear_ob_zone']
    ob_mitigated_bull = (not pd.isna(bull_ob) and cur['low'] <= bull_ob)
    ob_mitigated_bear = (not pd.isna(bear_ob) and cur['high'] >= bear_ob)

    bpr_tap_bull = (cur['has_bpr'] and cur['low'] <= cur['bpr_high'] and cur['high'] >= cur['bpr_low'])
    bpr_tap_bear = (cur['has_bpr'] and cur['high'] >= cur['bpr_low'] and cur['low'] <= cur['bpr_high'])

    is_abs_buy = cur['is_absorption_buy']
    is_abs_sell = cur['is_absorption_sell']

    ifvg_buy = cur['ifvg_tap_buy']
    ifvg_sell = cur['ifvg_tap_sell']

    has_wick_buy = (cur['lower_wick_pct'] >= 0.14) or (cur['lower_wick'] >= 1.1 * cur['body'])
    has_wick_sell = (cur['upper_wick_pct'] >= 0.14) or (cur['upper_wick'] >= 1.1 * cur['body'])
    closed_high = cur['close'] >= (cur['low'] + 0.45 * cur['range'])
    closed_low = cur['close'] <= (cur['high'] - 0.45 * cur['range'])

    is_comp = cur['compression_ratio'] <= 0.70

    sig = "BUY" if ((swept_low or ob_mitigated_bull or bpr_tap_bull or is_abs_buy or ifvg_buy) and has_wick_buy and closed_high) else                   ("SELL" if ((swept_high or ob_mitigated_bear or bpr_tap_bear or is_abs_sell or ifvg_sell) and has_wick_sell and closed_low) else None)

    if sig:
        is_hc = (ob_mitigated_bull if sig == "BUY" else ob_mitigated_bear) or                         (bpr_tap_bull if sig == "BUY" else bpr_tap_bear) or                         (is_abs_buy if sig == "BUY" else is_abs_sell) or                         (ifvg_buy if sig == "BUY" else ifvg_sell)
        sl_mult = 0.188 if is_hc else (0.190 if is_comp else 0.195)
        sl_buf = max(sl_mult * cur['atr'], 0.22)
        active_depth = 0.121 if is_hc else (0.124 if is_comp else 0.125)
        entry = round(cur['low'] + (active_depth * cur['lower_wick']), 2) if sig == "BUY" else round(cur['high'] - (active_depth * cur['upper_wick']), 2)
        sl = round(cur['low'] - sl_buf, 2) if sig == "BUY" else round(cur['high'] + sl_buf, 2)
        risk = entry - sl if sig == "BUY" else sl - entry
        if risk > 0:
            return {"time": int(cur['time']), "signal": sig, "entry": entry, "sl": sl, "risk": risk, "atr": cur['atr'], "tf": tf}
    return None


def _bar_logic_s20_138(cur, tf):
    if pd.isna(cur['atr']) or cur['atr'] <= 0.05 or cur['range'] < 0.45 * cur['atr'] or cur['vol_ratio'] < 1.11:
        return None

    swept_low = (cur['low'] <= cur['swing_low_12']) or (cur['low'] <= cur['asian_low']) or                         (not pd.isna(cur.get('fvg_bull_zone')) and cur['low'] <= cur['fvg_bull_zone']) or                         (not pd.isna(cur.get('fibo_discount_382')) and cur['low'] <= cur['fibo_discount_382']) or                         (not pd.isna(cur.get('val_proxy')) and cur['low'] <= cur['val_proxy']) or                         (not pd.isna(cur.get('pdl')) and cur['low'] <= cur['pdl'])

    swept_high = (cur['high'] >= cur['swing_high_12']) or (cur['high'] >= cur['asian_high']) or                          (not pd.isna(cur.get('fvg_bear_zone')) and cur['high'] >= cur['fvg_bear_zone']) or                          (not pd.isna(cur.get('fibo_premium_618')) and cur['high'] >= cur['fibo_premium_618']) or                          (not pd.isna(cur.get('vah_proxy')) and cur['high'] >= cur['vah_proxy']) or                          (not pd.isna(cur.get('pdh')) and cur['high'] >= cur['pdh'])

    bull_ob = cur['bull_ob_zone']
    bear_ob = cur['bear_ob_zone']
    ob_mitigated_bull = (not pd.isna(bull_ob) and cur['low'] <= bull_ob)
    ob_mitigated_bear = (not pd.isna(bear_ob) and cur['high'] >= bear_ob)

    bpr_tap_bull = (cur['has_bpr'] and cur['low'] <= cur['bpr_high'] and cur['high'] >= cur['bpr_low'])
    bpr_tap_bear = (cur['has_bpr'] and cur['high'] >= cur['bpr_low'] and cur['low'] <= cur['bpr_high'])

    is_abs_buy = cur['is_absorption_buy']
    is_abs_sell = cur['is_absorption_sell']

    ifvg_buy = cur['ifvg_tap_buy']
    ifvg_sell = cur['ifvg_tap_sell']

    has_wick_buy = (cur['lower_wick_pct'] >= 0.14) or (cur['lower_wick'] >= 1.1 * cur['body'])
    has_wick_sell = (cur['upper_wick_pct'] >= 0.14) or (cur['upper_wick'] >= 1.1 * cur['body'])
    closed_high = cur['close'] >= (cur['low'] + 0.45 * cur['range'])
    closed_low = cur['close'] <= (cur['high'] - 0.45 * cur['range'])

    is_comp = cur['compression_ratio'] <= 0.70

    sig = "BUY" if ((swept_low or ob_mitigated_bull or bpr_tap_bull or is_abs_buy or ifvg_buy) and has_wick_buy and closed_high) else                   ("SELL" if ((swept_high or ob_mitigated_bear or bpr_tap_bear or is_abs_sell or ifvg_sell) and has_wick_sell and closed_low) else None)

    if sig:
        is_hc = (ob_mitigated_bull if sig == "BUY" else ob_mitigated_bear) or                         (bpr_tap_bull if sig == "BUY" else bpr_tap_bear) or                         (is_abs_buy if sig == "BUY" else is_abs_sell) or                         (ifvg_buy if sig == "BUY" else ifvg_sell)
        sl_mult = 0.188 if is_hc else (0.190 if is_comp else 0.195)
        sl_buf = max(sl_mult * cur['atr'], 0.22)
        active_depth = 0.121 if is_hc else (0.124 if is_comp else 0.125)
        entry = round(cur['low'] + (active_depth * cur['lower_wick']), 2) if sig == "BUY" else round(cur['high'] - (active_depth * cur['upper_wick']), 2)
        sl = round(cur['low'] - sl_buf, 2) if sig == "BUY" else round(cur['high'] + sl_buf, 2)
        risk = entry - sl if sig == "BUY" else sl - entry
        if risk > 0:
            return {"time": int(cur['time']), "signal": sig, "entry": entry, "sl": sl, "risk": risk, "atr": cur['atr'], "tf": tf}
    return None


def _bar_logic_s20_139(cur, tf):
    if pd.isna(cur['atr']) or cur['atr'] <= 0.05 or cur['range'] < 0.45 * cur['atr'] or cur['vol_ratio'] < 1.11:
        return None

    swept_low = (cur['low'] <= cur['swing_low_12']) or (cur['low'] <= cur['asian_low']) or                         (not pd.isna(cur.get('fvg_bull_zone')) and cur['low'] <= cur['fvg_bull_zone']) or                         (not pd.isna(cur.get('fibo_discount_382')) and cur['low'] <= cur['fibo_discount_382']) or                         (not pd.isna(cur.get('val_proxy')) and cur['low'] <= cur['val_proxy']) or                         (not pd.isna(cur.get('pdl')) and cur['low'] <= cur['pdl'])

    swept_high = (cur['high'] >= cur['swing_high_12']) or (cur['high'] >= cur['asian_high']) or                          (not pd.isna(cur.get('fvg_bear_zone')) and cur['high'] >= cur['fvg_bear_zone']) or                          (not pd.isna(cur.get('fibo_premium_618')) and cur['high'] >= cur['fibo_premium_618']) or                          (not pd.isna(cur.get('vah_proxy')) and cur['high'] >= cur['vah_proxy']) or                          (not pd.isna(cur.get('pdh')) and cur['high'] >= cur['pdh'])

    bull_ob = cur['bull_ob_zone']
    bear_ob = cur['bear_ob_zone']
    ob_mitigated_bull = (not pd.isna(bull_ob) and cur['low'] <= bull_ob)
    ob_mitigated_bear = (not pd.isna(bear_ob) and cur['high'] >= bear_ob)

    bpr_tap_bull = (cur['has_bpr'] and cur['low'] <= cur['bpr_high'] and cur['high'] >= cur['bpr_low'])
    bpr_tap_bear = (cur['has_bpr'] and cur['high'] >= cur['bpr_low'] and cur['low'] <= cur['bpr_high'])

    is_abs_buy = cur['is_absorption_buy']
    is_abs_sell = cur['is_absorption_sell']

    ifvg_buy = cur['ifvg_tap_buy']
    ifvg_sell = cur['ifvg_tap_sell']

    has_wick_buy = (cur['lower_wick_pct'] >= 0.14) or (cur['lower_wick'] >= 1.1 * cur['body'])
    has_wick_sell = (cur['upper_wick_pct'] >= 0.14) or (cur['upper_wick'] >= 1.1 * cur['body'])
    closed_high = cur['close'] >= (cur['low'] + 0.45 * cur['range'])
    closed_low = cur['close'] <= (cur['high'] - 0.45 * cur['range'])

    is_comp = cur['compression_ratio'] <= 0.70

    sig = "BUY" if ((swept_low or ob_mitigated_bull or bpr_tap_bull or is_abs_buy or ifvg_buy) and has_wick_buy and closed_high) else                   ("SELL" if ((swept_high or ob_mitigated_bear or bpr_tap_bear or is_abs_sell or ifvg_sell) and has_wick_sell and closed_low) else None)

    if sig:
        is_hc = (ob_mitigated_bull if sig == "BUY" else ob_mitigated_bear) or                         (bpr_tap_bull if sig == "BUY" else bpr_tap_bear) or                         (is_abs_buy if sig == "BUY" else is_abs_sell) or                         (ifvg_buy if sig == "BUY" else ifvg_sell)
        sl_mult = 0.188 if is_hc else (0.190 if is_comp else 0.195)
        sl_buf = max(sl_mult * cur['atr'], 0.22)
        active_depth = 0.121 if is_hc else (0.124 if is_comp else 0.125)
        entry = round(cur['low'] + (active_depth * cur['lower_wick']), 2) if sig == "BUY" else round(cur['high'] - (active_depth * cur['upper_wick']), 2)
        sl = round(cur['low'] - sl_buf, 2) if sig == "BUY" else round(cur['high'] + sl_buf, 2)
        risk = entry - sl if sig == "BUY" else sl - entry
        if risk > 0:
            return {"time": int(cur['time']), "signal": sig, "entry": entry, "sl": sl, "risk": risk, "atr": cur['atr'], "tf": tf}
    return None


def _bar_logic_s20_300(cur, tf):
    if pd.isna(cur['atr']) or cur['atr'] <= 0.05 or cur['range'] < 0.45 * cur['atr'] or cur['vol_ratio'] < 1.11:
        return None

    swept_low = (cur['low'] <= cur['swing_low_12']) or (cur['low'] <= cur['asian_low']) or \
                (not pd.isna(cur.get('fvg_bull_zone')) and cur['low'] <= cur['fvg_bull_zone']) or \
                (not pd.isna(cur.get('fibo_discount_382')) and cur['low'] <= cur['fibo_discount_382']) or \
                (not pd.isna(cur.get('val_proxy')) and cur['low'] <= cur['val_proxy']) or \
                (not pd.isna(cur.get('pdl')) and cur['low'] <= cur['pdl']) or \
                cur['swept_htf_low'] or cur['is_spring']

    swept_high = (cur['high'] >= cur['swing_high_12']) or (cur['high'] >= cur['asian_high']) or \
                 (not pd.isna(cur.get('fvg_bear_zone')) and cur['high'] >= cur['fvg_bear_zone']) or \
                 (not pd.isna(cur.get('fibo_premium_618')) and cur['high'] >= cur['fibo_premium_618']) or \
                 (not pd.isna(cur.get('vah_proxy')) and cur['high'] >= cur['vah_proxy']) or \
                 (not pd.isna(cur.get('pdh')) and cur['high'] >= cur['pdh']) or \
                 cur['swept_htf_high'] or cur['is_utad']

    bull_ob = cur['bull_ob_zone']
    bear_ob = cur['bear_ob_zone']
    ob_mitigated_bull = (not pd.isna(bull_ob) and cur['low'] <= bull_ob)
    ob_mitigated_bear = (not pd.isna(bear_ob) and cur['high'] >= bear_ob)

    bpr_tap_bull = (cur['has_bpr'] and cur['low'] <= cur['bpr_high'] and cur['high'] >= cur['bpr_low'])
    bpr_tap_bear = (cur['has_bpr'] and cur['high'] >= cur['bpr_low'] and cur['low'] <= cur['bpr_high'])

    is_abs_buy = cur['is_absorption_buy']
    is_abs_sell = cur['is_absorption_sell']

    ifvg_buy = cur['ifvg_tap_buy']
    ifvg_sell = cur['ifvg_tap_sell']

    bb_buy = (not pd.isna(cur.get('breaker_bull_zone')) and cur['low'] <= cur['breaker_bull_zone'])
    bb_sell = (not pd.isna(cur.get('breaker_bear_zone')) and cur['high'] >= cur['breaker_bear_zone'])

    is_overlap = cur['is_ldn_ny_overlap']

    has_wick_buy = (cur['lower_wick_pct'] >= 0.14) or (cur['lower_wick'] >= 1.1 * cur['body'])
    has_wick_sell = (cur['upper_wick_pct'] >= 0.14) or (cur['upper_wick'] >= 1.1 * cur['body'])
    closed_high = cur['close'] >= (cur['low'] + 0.45 * cur['range'])
    closed_low = cur['close'] <= (cur['high'] - 0.45 * cur['range'])

    is_comp = cur['compression_ratio'] <= 0.70

    sig = "BUY" if ((swept_low or ob_mitigated_bull or bpr_tap_bull or is_abs_buy or ifvg_buy or bb_buy) and has_wick_buy and closed_high) else \
          ("SELL" if ((swept_high or ob_mitigated_bear or bpr_tap_bear or is_abs_sell or ifvg_sell or bb_sell) and has_wick_sell and closed_low) else None)

    if sig:
        is_hc = (ob_mitigated_bull if sig == "BUY" else ob_mitigated_bear) or \
                (bpr_tap_bull if sig == "BUY" else bpr_tap_bear) or \
                (is_abs_buy if sig == "BUY" else is_abs_sell) or \
                (ifvg_buy if sig == "BUY" else ifvg_sell) or \
                (bb_buy if sig == "BUY" else bb_sell)

        sl_mult = (0.188 - 0.002 if is_overlap else 0.188) if is_hc else (0.190 if is_comp else 0.195)
        sl_buf = max(sl_mult * cur['atr'], 0.22)
        active_depth = 0.121 if is_hc else (0.124 if is_comp else 0.125)
        entry = round(cur['low'] + (active_depth * cur['lower_wick']), 2) if sig == "BUY" else round(cur['high'] - (active_depth * cur['upper_wick']), 2)
        sl = round(cur['low'] - sl_buf, 2) if sig == "BUY" else round(cur['high'] + sl_buf, 2)
        risk = entry - sl if sig == "BUY" else sl - entry
        if risk > 0:
            return {"time": int(cur['time']), "signal": sig, "entry": entry, "sl": sl, "risk": risk, "atr": cur['atr'], "tf": tf}
    return None


# ═══════════════════════════════════════════════════════════════════════════
# GROUP 1 EXPANSION (2026-09-24): S20.31-53, 130-139, 300 (pilot -> full)
# ═══════════════════════════════════════════════════════════════════════════

def _make_extract_family_detector(sid, folder, modfile, tfs, min_vol, min_wick, retest_depth,
                                   sl_mult, hours, use_flags, tp_r, stages, pattern_name):
    def detector(rates, tf_name="M15", symbol="XAUUSD"):
        if not is_symbol_enabled_for_s20(symbol):
            return {"signal": "WAIT", "reason": f"{pattern_name} disabled for {symbol}"}
        if tf_name.upper() not in tfs:
            return {"signal": "WAIT", "reason": f"{pattern_name} only evaluates {'/'.join(tfs)} (got {tf_name})"}
        mod = _get_module(folder, modfile)
        if not mod or len(rates) < 60:
            return {"signal": "WAIT", "reason": f"{pattern_name} module not ready"}
        try:
            scale, digits = get_symbol_scale_and_digits(symbol)
            r_eval = rates
            if scale != 1.0:
                r_eval = rates.copy()
                for col in ('open', 'high', 'low', 'close'):
                    r_eval[col] = rates[col] * scale
            df = mod.compute_indicators(r_eval)
            kwargs = dict(min_vol=min_vol, retest_depth=retest_depth, hours=tuple(hours))
            if sl_mult is not None and "sl_mult" in inspect.signature(mod.extract_setups).parameters:
                kwargs["sl_mult"] = sl_mult
            if min_wick is not None:
                kwargs["min_wick"] = min_wick
            kwargs.update(use_flags)
            setups = mod.extract_setups(df, tf_name, **kwargs)
            last_bar_time = int(rates[-1]["time"])
            matches = [s for s in setups if s["time"] == last_bar_time]
            if not matches:
                return {"signal": "WAIT", "reason": f"{pattern_name} no setup on latest closed bar"}
            s = matches[0]
            sig, entry, sl, risk = s["signal"], s["entry"], s["sl"], s["risk"]
            tp = entry + (tp_r * risk) if sig == "BUY" else entry - (tp_r * risk)
            res = {"signal": sig, "entry": entry, "sl": sl, "tp": tp, "risk": risk,
                   "stages": stages, "be_r": 0.8, "order_mode": "limit", "cancel_bars": 5, "sid": sid}
            clean_sym = symbol.split(".")[0]
            res["pattern"] = f"{pattern_name}_{clean_sym}"
            if scale != 1.0:
                for k in ("entry", "sl", "tp", "risk"):
                    res[k] = round(res[k] / scale, digits)
            else:
                for k in ("entry", "sl", "tp", "risk"):
                    res[k] = round(res[k], digits)
            return res
        except Exception as e:
            return {"signal": "WAIT", "reason": f"{pattern_name} error: {e}"}
    detector.ratchet = (stages, 0.8)
    return detector

detect_s20_37 = _make_extract_family_detector(
    sid=20.37, folder="s20.37", modfile="strategy20_37",
    tfs=('H4', 'H1', 'M30', 'M15'), min_vol=1.2, min_wick=None,
    retest_depth=0.15, sl_mult=0.2, hours=(7, 21),
    use_flags={}, tp_r=4.0, stages=[[1.5, 1.0], [2.4, 2.0], [3.0, 2.8], [3.5, 3.3]],
    pattern_name="S20.37")

detect_s20_38 = _make_extract_family_detector(
    sid=20.38, folder="s20.38", modfile="strategy20_38",
    tfs=('H4', 'H1', 'M30', 'M15'), min_vol=1.2, min_wick=None,
    retest_depth=0.13, sl_mult=0.2, hours=(6, 22),
    use_flags={'use_pmh': True}, tp_r=4.2, stages=[[1.5, 1.0], [2.4, 2.0], [3.0, 2.8], [3.5, 3.3], [3.8, 3.5]],
    pattern_name="S20.38")

detect_s20_39 = _make_extract_family_detector(
    sid=20.39, folder="s20.39", modfile="strategy20_39",
    tfs=('H4', 'H1', 'M30', 'M15'), min_vol=1.2, min_wick=None,
    retest_depth=0.13, sl_mult=0.2, hours=(4, 22),
    use_flags={'use_pqh': True}, tp_r=4.6, stages=[[1.5, 1.0], [2.4, 2.0], [3.0, 2.8], [3.5, 3.3], [3.8, 3.5], [4.2, 3.9]],
    pattern_name="S20.39")

detect_s20_41 = _make_extract_family_detector(
    sid=20.41, folder="s20.41", modfile="strategy20_41",
    tfs=('H4', 'H3', 'H2', 'H1', 'M30', 'M15'), min_vol=1.2, min_wick=None,
    retest_depth=0.13, sl_mult=0.2, hours=(2, 22),
    use_flags={'use_pyh': True}, tp_r=5.0, stages=[[1.5, 1.0], [2.4, 2.0], [3.0, 2.8], [3.5, 3.3], [3.8, 3.5], [4.2, 3.9], [4.6, 4.3]],
    pattern_name="S20.41")

detect_s20_42 = _make_extract_family_detector(
    sid=20.42, folder="s20.42", modfile="strategy20_42",
    tfs=('H4', 'H3', 'H2', 'H1', 'M30', 'M20', 'M15'), min_vol=1.2, min_wick=None,
    retest_depth=0.128, sl_mult=0.2, hours=(1, 22),
    use_flags={'use_pyh': True}, tp_r=5.6, stages=[[1.5, 1.0], [2.4, 2.0], [3.0, 2.8], [3.5, 3.3], [3.8, 3.5], [4.2, 3.9], [4.6, 4.3], [5.2, 4.9]],
    pattern_name="S20.42")

detect_s20_43 = _make_extract_family_detector(
    sid=20.43, folder="s20.43", modfile="strategy20_43",
    tfs=('H4', 'H3', 'H2', 'H1', 'M30', 'M20', 'M15', 'M12'), min_vol=1.2, min_wick=None,
    retest_depth=0.122, sl_mult=0.2, hours=(1, 22),
    use_flags={'use_pyh': True}, tp_r=5.8, stages=[[1.5, 1.0], [2.4, 2.0], [3.0, 2.8], [3.5, 3.3], [3.8, 3.5], [4.2, 3.9], [4.6, 4.3], [5.2, 4.9], [5.5, 5.2]],
    pattern_name="S20.43")

detect_s20_44 = _make_extract_family_detector(
    sid=20.44, folder="s20.44", modfile="strategy20_44",
    tfs=('H4', 'H3', 'H2', 'H1', 'M30', 'M20', 'M15', 'M12'), min_vol=1.2, min_wick=None,
    retest_depth=0.121, sl_mult=0.2, hours=(1, 22),
    use_flags={'use_pyh': True, 'use_ldn': True}, tp_r=5.8, stages=[[1.5, 1.0], [2.4, 2.0], [3.0, 2.8], [3.5, 3.3], [3.8, 3.5], [4.2, 3.9], [4.6, 4.3], [5.2, 4.9], [5.5, 5.2]],
    pattern_name="S20.44")

detect_s20_45 = _make_extract_family_detector(
    sid=20.45, folder="s20.45", modfile="strategy20_45",
    tfs=('H4', 'H3', 'H2', 'H1', 'M30', 'M20', 'M15', 'M12'), min_vol=1.2, min_wick=None,
    retest_depth=0.121, sl_mult=0.2, hours=(0, 22),
    use_flags={'use_pyh': True, 'use_ldn': True, 'use_ny': True}, tp_r=5.85, stages=[[1.5, 1.0], [2.4, 2.0], [3.0, 2.8], [3.5, 3.3], [3.8, 3.5], [4.2, 3.9], [4.6, 4.3], [5.2, 4.9], [5.5, 5.2], [5.6, 5.3]],
    pattern_name="S20.45")

detect_s20_46 = _make_extract_family_detector(
    sid=20.46, folder="s20.46", modfile="strategy20_46",
    tfs=('H4', 'H3', 'H2', 'H1', 'M30', 'M20', 'M15', 'M12'), min_vol=1.18, min_wick=0.36,
    retest_depth=0.121, sl_mult=0.2, hours=(0, 22),
    use_flags={'use_pyh': True, 'use_ldn': True, 'use_ny': True}, tp_r=5.9, stages=[[1.5, 1.0], [2.4, 2.0], [3.0, 2.8], [3.5, 3.3], [3.8, 3.5], [4.2, 3.9], [4.6, 4.3], [5.2, 4.9], [5.5, 5.2], [5.6, 5.4]],
    pattern_name="S20.46")

detect_s20_47 = _make_extract_family_detector(
    sid=20.47, folder="s20.47", modfile="strategy20_47",
    tfs=('H4', 'H3', 'H2', 'H1', 'M30', 'M20', 'M15', 'M12'), min_vol=1.17, min_wick=0.34,
    retest_depth=0.122, sl_mult=0.2, hours=(0, 22),
    use_flags={'use_pyh': True, 'use_ldn': True, 'use_ny': True}, tp_r=6.05, stages=[[1.5, 1.0], [2.4, 2.0], [3.0, 2.8], [3.5, 3.3], [3.8, 3.5], [4.2, 3.9], [4.6, 4.3], [5.2, 4.9], [5.5, 5.2], [5.6, 5.4], [5.8, 5.6]],
    pattern_name="S20.47")

detect_s20_48 = _make_extract_family_detector(
    sid=20.48, folder="s20.48", modfile="strategy20_48",
    tfs=('H4', 'H3', 'H2', 'H1', 'M30', 'M20', 'M15', 'M12'), min_vol=1.17, min_wick=0.34,
    retest_depth=0.122, sl_mult=0.2, hours=(0, 22),
    use_flags={'use_pyh': True, 'use_ldn': True, 'use_ny': True, 'use_fvg': True}, tp_r=6.35, stages=[[1.5, 1.0], [2.4, 2.0], [3.0, 2.8], [3.5, 3.3], [3.8, 3.5], [4.2, 3.9], [4.6, 4.3], [5.2, 4.9], [5.5, 5.2], [5.6, 5.4], [5.8, 5.6], [6.0, 5.8]],
    pattern_name="S20.48")

detect_s20_49 = _make_extract_family_detector(
    sid=20.49, folder="s20.49", modfile="strategy20_49",
    tfs=('H4', 'H3', 'H2', 'H1', 'M30', 'M20', 'M15', 'M12'), min_vol=1.17, min_wick=0.34,
    retest_depth=0.122, sl_mult=0.2, hours=(0, 22),
    use_flags={'use_pyh': True, 'use_ldn': True, 'use_ny': True, 'use_fvg': True}, tp_r=6.7, stages=[[1.5, 1.0], [2.4, 2.0], [3.0, 2.8], [3.5, 3.3], [3.8, 3.5], [4.2, 3.9], [4.6, 4.3], [5.2, 4.9], [5.5, 5.2], [5.6, 5.4], [5.8, 5.6], [6.0, 5.8], [6.15, 5.95]],
    pattern_name="S20.49")

detect_s20_50 = _make_extract_family_detector(
    sid=20.505, folder="s20.50", modfile="strategy20_50",
    tfs=('H4', 'H3', 'H2', 'H1', 'M30', 'M20', 'M15', 'M12'), min_vol=1.17, min_wick=0.33,
    retest_depth=0.124, sl_mult=0.2, hours=(0, 22),
    use_flags={'use_pyh': True, 'use_ldn': True, 'use_ny': True, 'use_ny_pm': True, 'use_fvg': True}, tp_r=6.65, stages=[[1.5, 1.0], [2.4, 2.0], [3.0, 2.8], [3.5, 3.3], [3.8, 3.5], [4.2, 3.9], [4.6, 4.3], [5.2, 4.9], [5.5, 5.2], [5.6, 5.4], [5.8, 5.6], [6.0, 5.8], [6.15, 5.95], [6.35, 6.15]],
    pattern_name="S20.50")

detect_s20_51 = _make_extract_family_detector(
    sid=20.51, folder="s20.51", modfile="strategy20_51",
    tfs=('H4', 'H3', 'H2', 'H1', 'M30', 'M20', 'M15', 'M12'), min_vol=1.17, min_wick=0.32,
    retest_depth=0.124, sl_mult=0.2, hours=(0, 22),
    use_flags={'use_pyh': True, 'use_ldn': True, 'use_ny': True, 'use_ny_pm': True, 'use_fvg': True}, tp_r=6.75, stages=[[1.5, 1.0], [2.4, 2.0], [3.0, 2.8], [3.5, 3.3], [3.8, 3.5], [4.2, 3.9], [4.6, 4.3], [5.2, 4.9], [5.5, 5.2], [5.6, 5.4], [5.8, 5.6], [6.0, 5.8], [6.15, 5.95], [6.35, 6.15], [6.5, 6.3]],
    pattern_name="S20.51")

detect_s20_52 = _make_extract_family_detector(
    sid=20.52, folder="s20.52", modfile="strategy20_52",
    tfs=('H4', 'H3', 'H2', 'H1', 'M30', 'M20', 'M15', 'M12'), min_vol=1.17, min_wick=0.3,
    retest_depth=0.124, sl_mult=0.2, hours=(0, 22),
    use_flags={'use_pyh': True, 'use_ldn': True, 'use_ny': True, 'use_ny_pm': True, 'use_fvg': True}, tp_r=6.9, stages=[[1.5, 1.0], [2.4, 2.0], [3.0, 2.8], [3.5, 3.3], [3.8, 3.5], [4.2, 3.9], [4.6, 4.3], [5.2, 4.9], [5.5, 5.2], [5.6, 5.4], [5.8, 5.6], [6.0, 5.8], [6.15, 5.95], [6.35, 6.15], [6.5, 6.3], [6.7, 6.5]],
    pattern_name="S20.52")


# ---- Family C: evaluate_setup(df, idx, ...) style (31, 32, 33) ----

def _make_evalidx_family_detector(sid, folder, modfile, tfs, extra_kwargs, tp_r, stages, be_r, pattern_name):
    def detector(rates, tf_name="M15", symbol="XAUUSD"):
        if not is_symbol_enabled_for_s20(symbol):
            return {"signal": "WAIT", "reason": f"{pattern_name} disabled for {symbol}"}
        if tf_name.upper() not in tfs:
            return {"signal": "WAIT", "reason": f"{pattern_name} only evaluates {'/'.join(tfs)} (got {tf_name})"}
        mod = _get_module(folder, modfile)
        if not mod or len(rates) < 60:
            return {"signal": "WAIT", "reason": f"{pattern_name} module not ready"}
        try:
            scale, digits = get_symbol_scale_and_digits(symbol)
            r_eval = rates
            if scale != 1.0:
                r_eval = rates.copy()
                for col in ('open', 'high', 'low', 'close'):
                    r_eval[col] = rates[col] * scale
            df = mod.compute_indicators_df(r_eval)
            idx = len(df) - 1
            kw = dict(extra_kwargs)
            if "tf_label" in kw:
                kw["tf_label"] = tf_name
            res = mod.evaluate_setup(df, idx, **kw)
            if not res or res.get("signal") not in ("BUY", "SELL"):
                return {"signal": "WAIT", "reason": f"{pattern_name} no setup on latest closed bar"}
            sig, entry, sl, risk = res["signal"], res["entry"], res["sl"], res["risk"]
            tp = entry + (tp_r * risk) if sig == "BUY" else entry - (tp_r * risk)
            out = {"signal": sig, "entry": entry, "sl": sl, "tp": tp, "risk": risk,
                   "stages": stages, "be_r": 0.8, "order_mode": "limit", "cancel_bars": 5, "sid": sid}
            clean_sym = symbol.split(".")[0]
            out["pattern"] = f"{pattern_name}_{clean_sym}"
            if scale != 1.0:
                for k in ("entry", "sl", "tp", "risk"):
                    out[k] = round(out[k] / scale, digits)
            else:
                for k in ("entry", "sl", "tp", "risk"):
                    out[k] = round(out[k], digits)
            return out
        except Exception as e:
            return {"signal": "WAIT", "reason": f"{pattern_name} error: {e}"}
    detector.ratchet = (stages, 0.8)
    return detector

detect_s20_31 = _make_evalidx_family_detector(
    sid=20.31, folder="s20.31", modfile="strategy20_31",
    tfs=("M30",), extra_kwargs={"synergy_mode": "sweep_only"}, tp_r=1.8, stages=[], be_r=0.8,
    pattern_name="S20.31")

detect_s20_32 = _make_evalidx_family_detector(
    sid=20.32, folder="s20.32", modfile="strategy20_32",
    tfs=("M30", "M15"), extra_kwargs={"tf_label": "M30"}, tp_r=2.5, stages=[(1.6, 1.0)], be_r=0.8,
    pattern_name="S20.32")

detect_s20_33 = _make_evalidx_family_detector(
    sid=20.33, folder="s20.33", modfile="strategy20_33",
    tfs=("H1", "M30", "M15"), extra_kwargs={"tf_label": "M30", "retest_depth": 0.300}, tp_r=2.8,
    stages=[(1.5, 1.0), (2.2, 1.8)], be_r=0.8,
    pattern_name="S20.33")


# ---- Family D: evaluate_setup(cur, ...) per-record style (34, 35, 36) ----

def _make_evalcur_family_detector(sid, folder, modfile, tfs, extra_kwargs, tp_r, stages, pattern_name):
    def detector(rates, tf_name="M15", symbol="XAUUSD"):
        if not is_symbol_enabled_for_s20(symbol):
            return {"signal": "WAIT", "reason": f"{pattern_name} disabled for {symbol}"}
        if tf_name.upper() not in tfs:
            return {"signal": "WAIT", "reason": f"{pattern_name} only evaluates {'/'.join(tfs)} (got {tf_name})"}
        mod = _get_module(folder, modfile)
        if not mod or len(rates) < 60:
            return {"signal": "WAIT", "reason": f"{pattern_name} module not ready"}
        try:
            scale, digits = get_symbol_scale_and_digits(symbol)
            r_eval = rates
            if scale != 1.0:
                r_eval = rates.copy()
                for col in ('open', 'high', 'low', 'close'):
                    r_eval[col] = rates[col] * scale
            df = mod.compute_indicators_df(r_eval)
            cur = df.to_dict('records')[-1]
            kw = dict(extra_kwargs)
            kw["tf_label"] = tf_name
            res = mod.evaluate_setup(cur, **kw)
            if not res or res.get("signal") not in ("BUY", "SELL"):
                return {"signal": "WAIT", "reason": f"{pattern_name} no setup on latest closed bar"}
            sig, entry, sl, risk = res["signal"], res["entry"], res["sl"], res["risk"]
            tp = entry + (tp_r * risk) if sig == "BUY" else entry - (tp_r * risk)
            out = {"signal": sig, "entry": entry, "sl": sl, "tp": tp, "risk": risk,
                   "stages": stages, "be_r": 0.8, "order_mode": "limit", "cancel_bars": 5, "sid": sid}
            clean_sym = symbol.split(".")[0]
            out["pattern"] = f"{pattern_name}_{clean_sym}"
            if scale != 1.0:
                for k in ("entry", "sl", "tp", "risk"):
                    out[k] = round(out[k] / scale, digits)
            else:
                for k in ("entry", "sl", "tp", "risk"):
                    out[k] = round(out[k], digits)
            return out
        except Exception as e:
            return {"signal": "WAIT", "reason": f"{pattern_name} error: {e}"}
    detector.ratchet = (stages, 0.8)
    return detector

detect_s20_34 = _make_evalcur_family_detector(
    sid=20.34, folder="s20.34", modfile="strategy20_34",
    tfs=("H1", "M30", "M15"), extra_kwargs={}, tp_r=2.6, stages=[(1.5, 1.0), (2.2, 1.8)],
    pattern_name="S20.34")

detect_s20_35 = _make_evalcur_family_detector(
    sid=20.35, folder="s20.35", modfile="strategy20_35",
    tfs=("H4", "H1", "M30", "M15"), extra_kwargs={}, tp_r=2.8, stages=[(1.5, 1.0), (2.2, 1.8)],
    pattern_name="S20.35")

detect_s20_36 = _make_evalcur_family_detector(
    sid=20.36, folder="s20.36", modfile="strategy20_36",
    tfs=("H4", "H1", "M30", "M15"), extra_kwargs={}, tp_r=3.5,
    stages=[(1.5, 1.0), (2.4, 2.0), (3.0, 2.8)],
    pattern_name="S20.36")


# ---- Family E: shared goal_s20_53_to_100 engine, base (53, 130) ----

def _make_goal_engine_detector(sid, tfs, min_vol, min_wick, retest_depth, hours, use_flags, tp_r, stages, pattern_name):
    def detector(rates, tf_name="M15", symbol="XAUUSD"):
        if not is_symbol_enabled_for_s20(symbol):
            return {"signal": "WAIT", "reason": f"{pattern_name} disabled for {symbol}"}
        if tf_name.upper() not in tfs:
            return {"signal": "WAIT", "reason": f"{pattern_name} only evaluates {'/'.join(tfs)} (got {tf_name})"}
        try:
            from strategy.goal_s20_53_to_100 import compute_indicators, extract_setups
        except Exception as e:
            return {"signal": "WAIT", "reason": f"{pattern_name} import error: {e}"}
        if len(rates) < 60:
            return {"signal": "WAIT", "reason": f"{pattern_name} rates too short"}
        try:
            scale, digits = get_symbol_scale_and_digits(symbol)
            r_eval = rates
            if scale != 1.0:
                r_eval = rates.copy()
                for col in ('open', 'high', 'low', 'close'):
                    r_eval[col] = rates[col] * scale
            df = compute_indicators(r_eval, True, True, True, fvg_depth=5)
            kwargs = dict(min_vol=min_vol, min_wick=min_wick, retest_depth=retest_depth, hours=tuple(hours))
            kwargs.update(use_flags)
            setups = extract_setups(df, tf_name, **kwargs)
            last_bar_time = int(rates[-1]["time"])
            matches = [s for s in setups if s["time"] == last_bar_time]
            if not matches:
                return {"signal": "WAIT", "reason": f"{pattern_name} no setup on latest closed bar"}
            s = matches[0]
            sig, entry, sl, risk = s["signal"], s["entry"], s["sl"], s["risk"]
            tp = entry + (tp_r * risk) if sig == "BUY" else entry - (tp_r * risk)
            res = {"signal": sig, "entry": entry, "sl": sl, "tp": tp, "risk": risk,
                   "stages": stages, "be_r": 0.8, "order_mode": "limit", "cancel_bars": 5, "sid": sid}
            clean_sym = symbol.split(".")[0]
            res["pattern"] = f"{pattern_name}_{clean_sym}"
            if scale != 1.0:
                for k in ("entry", "sl", "tp", "risk"):
                    res[k] = round(res[k] / scale, digits)
            else:
                for k in ("entry", "sl", "tp", "risk"):
                    res[k] = round(res[k], digits)
            return res
        except Exception as e:
            return {"signal": "WAIT", "reason": f"{pattern_name} error: {e}"}
    detector.ratchet = (stages, 0.8)
    return detector

detect_s20_53 = _make_goal_engine_detector(
    sid=20.53, tfs=('H4', 'H3', 'H2', 'H1', 'M30', 'M20', 'M15', 'M12'), min_vol=1.17, min_wick=0.295, retest_depth=0.124,
    hours=(0, 22), use_flags={'use_pyh': True, 'use_ldn': True, 'use_ny': True, 'use_ny_pm': True, 'use_fvg': True, 'use_fibo': True, 'use_vp': True}, tp_r=6.98, stages=[(1.5, 1.0), (2.4, 2.0), (3.0, 2.8), (3.5, 3.3), (3.8, 3.5), (4.2, 3.9), (4.6, 4.3), (5.2, 4.9), (5.5, 5.2), (5.6, 5.4), (5.8, 5.6), (6.0, 5.8), (6.15, 5.95), (6.35, 6.15), (6.5, 6.3), (6.7, 6.5), (6.85, 6.65)],
    pattern_name="S20.53")

detect_s20_130 = _make_goal_engine_detector(
    sid=20.1305, tfs=('H4', 'H3', 'H2', 'H1', 'M30', 'M20', 'M15', 'M12'), min_vol=1.17, min_wick=0.14, retest_depth=0.125,
    hours=(0, 22), use_flags={'use_pyh': True, 'use_ldn': True, 'use_ny': True, 'use_ny_pm': True, 'use_fvg': True, 'use_fibo': True, 'use_vp': True}, tp_r=11.36, stages=[(1.5, 1.0), (2.4, 2.0), (3.0, 2.8), (3.5, 3.3), (3.8, 3.5), (4.2, 3.9), (4.6, 4.3), (5.2, 4.9), (5.5, 5.2), (5.6, 5.4), (5.8, 5.6), (6.0, 5.8), (6.15, 5.95), (6.35, 6.15), (6.5, 6.3), (6.7, 6.5), (6.85, 6.65), (7.0, 6.8), (7.15, 6.95), (7.3, 7.1), (7.45, 7.25), (7.6, 7.4), (7.75, 7.55), (7.9, 7.7), (8.05, 7.85), (8.2, 8.0), (8.35, 8.15), (8.5, 8.3), (8.65, 8.45), (8.8, 8.6), (8.95, 8.75), (9.1, 8.9), (9.25, 9.05), (9.4, 9.2), (9.55, 9.35)],
    pattern_name="S20.130")


# ---- Family F: embedded SMC-progressive confluence, per-bar logic (131-139, 300) ----

def _make_bar_logic_detector(sid, compute_module, compute_func, bar_logic_fn, tp_r, stages, pattern_name):
    def detector(rates, tf_name="M15", symbol="XAUUSD"):
        if not is_symbol_enabled_for_s20(symbol):
            return {"signal": "WAIT", "reason": f"{pattern_name} disabled for {symbol}"}
        if tf_name.upper() not in ("M15", "M30", "H1", "H4"):
            return {"signal": "WAIT", "reason": f"{pattern_name} only evaluates M15/M30/H1/H4 (got {tf_name})"}
        if len(rates) < 60:
            return {"signal": "WAIT", "reason": f"{pattern_name} rates too short"}
        try:
            import importlib, sys as _sys, os as _os
            _strat_dir = _os.path.join(ROOT_DIR, "strategy")
            if _strat_dir not in _sys.path:
                _sys.path.append(_strat_dir)
            mod = importlib.import_module(compute_module)
            compute_fn = getattr(mod, compute_func)
            _, digits = get_symbol_scale_and_digits(symbol)
            df = _marathon_df(rates, compute_fn) if "201_to_300" in compute_module else compute_fn(rates)
            cur = df.to_dict("records")[-1]
            setup = bar_logic_fn(cur, tf_name)
            if not setup:
                return {"signal": "WAIT", "reason": f"{pattern_name} no setup on latest closed bar"}
            sig, entry, sl, risk = setup["signal"], setup["entry"], setup["sl"], setup["risk"]
            tp = round(entry + (tp_r * risk), digits) if sig == "BUY" else round(entry - (tp_r * risk), digits)
            res = {"signal": sig, "entry": round(entry, digits), "sl": round(sl, digits), "tp": tp,
                   "risk": round(risk, digits), "stages": stages, "be_r": 0.8, "order_mode": "limit",
                   "cancel_bars": 5, "sid": sid}
            clean_sym = symbol.split(".")[0]
            res["pattern"] = f"{pattern_name}_{clean_sym}"
            return res
        except Exception as e:
            return {"signal": "WAIT", "reason": f"{pattern_name} error: {e}"}
    detector.ratchet = (stages, 0.8)
    return detector

detect_s20_131 = _make_bar_logic_detector(
    sid=20.131, compute_module="tune_master_fusion_131_to_133", compute_func="compute_all_synergies",
    bar_logic_fn=_bar_logic_s20_131, tp_r=11.4, stages=S20_131_STAGES,
    pattern_name="S20.131")

detect_s20_132 = _make_bar_logic_detector(
    sid=20.132, compute_module="tune_master_fusion_131_to_133", compute_func="compute_all_synergies",
    bar_logic_fn=_bar_logic_s20_132, tp_r=11.38, stages=S20_132_STAGES,
    pattern_name="S20.132")

detect_s20_133 = _make_bar_logic_detector(
    sid=20.133, compute_module="tune_master_fusion_131_to_133", compute_func="compute_all_synergies",
    bar_logic_fn=_bar_logic_s20_133, tp_r=11.45, stages=S20_133_STAGES,
    pattern_name="S20.133")

detect_s20_134 = _make_bar_logic_detector(
    sid=20.134, compute_module="tune_master_fusion_134_to_136", compute_func="compute_extended_synergies",
    bar_logic_fn=_bar_logic_s20_134, tp_r=11.55, stages=S20_134_STAGES,
    pattern_name="S20.134")

detect_s20_135 = _make_bar_logic_detector(
    sid=20.135, compute_module="tune_master_fusion_134_to_136", compute_func="compute_extended_synergies",
    bar_logic_fn=_bar_logic_s20_135, tp_r=11.6, stages=S20_135_STAGES,
    pattern_name="S20.135")

detect_s20_136 = _make_bar_logic_detector(
    sid=20.136, compute_module="tune_master_fusion_134_to_136", compute_func="compute_extended_synergies",
    bar_logic_fn=_bar_logic_s20_136, tp_r=11.9, stages=S20_136_STAGES,
    pattern_name="S20.136")

detect_s20_137 = _make_bar_logic_detector(
    sid=20.137, compute_module="tune_master_fusion_137_to_139", compute_func="compute_omni_synergies",
    bar_logic_fn=_bar_logic_s20_137, tp_r=11.95, stages=S20_137_STAGES,
    pattern_name="S20.137")

detect_s20_138 = _make_bar_logic_detector(
    sid=20.138, compute_module="tune_master_fusion_137_to_139", compute_func="compute_omni_synergies",
    bar_logic_fn=_bar_logic_s20_138, tp_r=12.15, stages=S20_138_STAGES,
    pattern_name="S20.138")

detect_s20_139 = _make_bar_logic_detector(
    sid=20.139, compute_module="tune_master_fusion_137_to_139", compute_func="compute_omni_synergies",
    bar_logic_fn=_bar_logic_s20_139, tp_r=12.5, stages=S20_139_STAGES,
    pattern_name="S20.139")

detect_s20_300 = _make_bar_logic_detector(
    sid=20.3005, compute_module="run_master_s20_marathon_201_to_300", compute_func="compute_marathon_300_synergies",
    bar_logic_fn=_bar_logic_s20_300, tp_r=13.43, stages=S20_300_STAGES,
    pattern_name="S20.300")


# ---- S20.300 v2: โซน TF ใหญ่ (จากแท่งปิดแล้วก่อนหน้า) + ยืนยันสัญญาณด้วยแท่ง M5 จริง ----
# แก้บั๊ก fill-ก่อนแท่งปิดของ S20.300 เดิม (sid 20.3005 ด้านบน) — ดู strategy/s20.300/v2_zone_ltf_trigger.py
# สำหรับหลักการ และ strategy/backtest-summary/s20_300_v2_*.md สำหรับผล walk-forward/rolling/sensitivity
# ที่ผ่านครบ (2026-10-03) ทำงานเฉพาะ tf_name == M5 เพราะดีไซน์นี้ยืนยันที่ระดับ M5 เสมอ ไม่ขึ้นกับ TF
# ที่ scanner.py วนมาเรียก — ดึงโซนของ TF ใหญ่ (H4,H3,H2,H1,M30,M20,M15,M12) สดๆ ผ่าน MT5 เองภายในฟังก์ชัน
# เพราะ scanner.py ไม่ได้ส่ง rates ของ TF อื่นมาให้ (ไม่เหมือน silver_rates ของ S20.21)
def detect_s20_300_v2(rates, tf_name="M15", symbol="XAUUSD") -> dict:
    if not is_symbol_enabled_for_s20(symbol):
        return {"signal": "WAIT", "reason": f"S20.300v2 disabled for {symbol}"}
    if "XAU" not in symbol.upper():
        return {"signal": "WAIT", "reason": "S20.300v2 เทสต์แค่ XAUUSD ยังไม่ validate สินทรัพย์อื่น"}
    if tf_name.upper() != "M5":
        return {"signal": "WAIT", "reason": "S20.300v2 only evaluates on M5 (โซนอ่านจาก H4-M12 ภายในฟังก์ชันเอง)"}
    if len(rates) < 60:
        return {"signal": "WAIT", "reason": "S20.300v2 M5 rates too short"}
    try:
        import MetaTrader5 as mt5
    except Exception as e:
        return {"signal": "WAIT", "reason": f"S20.300v2 MT5 import error: {e}"}
    mod = _get_module("s20.300", "v2_zone_ltf_trigger")
    if not mod:
        return {"signal": "WAIT", "reason": "S20.300v2 module not ready"}
    try:
        _, digits = get_symbol_scale_and_digits(symbol)
        rates_zone = {}
        for tf in mod.ZONE_TFS:
            tf_const = getattr(mt5, f"TIMEFRAME_{tf}", None)
            r = mt5.copy_rates_from_pos(symbol, tf_const, 0, 300) if tf_const is not None else None
            if r is None or len(r) < 60:
                return {"signal": "WAIT", "reason": f"S20.300v2 {tf} rates not ready"}
            rates_zone[tf] = r
        _, merged_per_tf = mod.build_merged_zones(rates_zone, rates)
        setups = mod.generate_setups(merged_per_tf, mod.DEFAULT_CFG, zone_tfs=mod.ZONE_TFS)
        last_bar_time = int(rates[-1]["time"])
        matches = [s for s in setups if s["time"] == last_bar_time]
        if not matches:
            return {"signal": "WAIT", "reason": "S20.300v2 no setup on latest closed M5 bar"}
        s = matches[0]
        sig, entry, sl, risk = s["signal"], s["entry"], s["sl"], s["risk"]
        tp_r = mod.DEFAULT_CFG["tp_r"]
        tp = entry + (tp_r * risk) if sig == "BUY" else entry - (tp_r * risk)
        res = {
            "signal": sig, "entry": round(entry, digits), "sl": round(sl, digits), "tp": round(tp, digits),
            "risk": round(risk, digits), "stages": mod.DEFAULT_CFG["stages"], "be_r": 0.8,
            "order_mode": "limit", "cancel_bars": 24, "sid": 20.3006,
        }
        clean_sym = symbol.split(".")[0]
        res["pattern"] = f"S20.300v2_{clean_sym}"
        return res
    except Exception as e:
        return {"signal": "WAIT", "reason": f"S20.300v2 error: {e}"}
detect_s20_300_v2.ratchet = (S20_300_STAGES, 0.8)


# ---- Family G: Group 2 scalp+runner style, using each strategy's own tp_scalp/tp_runner (23,25,26,27,29) ----
def _make_scalprunner_family_detector(sid, folder, modfile, func_name, tf, extra_kwargs, pattern_name):
    def detector(rates, tf_name="M15", symbol="XAUUSD"):
        if not is_symbol_enabled_for_s20(symbol):
            return {"signal": "WAIT", "reason": f"{pattern_name} disabled for {symbol}"}
        if tf_name.upper() != tf:
            return {"signal": "WAIT", "reason": f"{pattern_name} only evaluates {tf} (got {tf_name})"}
        mod = _get_module(folder, modfile)
        if not mod or len(rates) < 60:
            return {"signal": "WAIT", "reason": f"{pattern_name} module not ready"}
        try:
            scale, digits = get_symbol_scale_and_digits(symbol)
            r_eval = rates
            if scale != 1.0:
                r_eval = rates.copy()
                for col in ('open', 'high', 'low', 'close'):
                    r_eval[col] = rates[col] * scale
            df = mod.compute_indicators_df(r_eval)
            idx = len(df) - 1
            fn = getattr(mod, func_name)
            res = fn(df, idx, tf=tf_name, **extra_kwargs)
            if not res or res.get("signal") not in ("BUY", "SELL"):
                return {"signal": "WAIT", "reason": f"{pattern_name} no setup on latest closed bar"}
            sig, entry, sl, risk = res["signal"], res["entry"], res["sl"], res["risk"]
            tp = res.get("tp_runner", res.get("tp"))
            out = {"signal": sig, "entry": entry, "sl": sl, "tp": tp, "risk": risk,
                   "stages": [(1.8, 0.8)], "order_mode": "limit", "cancel_bars": 5, "sid": sid}
            clean_sym = symbol.split(".")[0]
            out["pattern"] = f"{pattern_name}_{clean_sym}"
            if scale != 1.0:
                for k in ("entry", "sl", "tp", "risk"):
                    out[k] = round(out[k] / scale, digits)
            else:
                for k in ("entry", "sl", "tp", "risk"):
                    out[k] = round(out[k], digits)
            return out
        except Exception as e:
            return {"signal": "WAIT", "reason": f"{pattern_name} error: {e}"}
    return detector

detect_s20_23_pilot = _make_scalprunner_family_detector(
    sid=20.23, folder="s20.23", modfile="strategy20_23", func_name="evaluate_hybrid_setup",
    tf="M30", extra_kwargs={}, pattern_name="S20.23")

detect_s20_25_pilot = _make_scalprunner_family_detector(
    sid=20.25, folder="s20.25", modfile="strategy20_25", func_name="evaluate_confluence_bar",
    tf="M30", extra_kwargs={}, pattern_name="S20.25")

detect_s20_26_pilot = _make_scalprunner_family_detector(
    sid=20.26, folder="s20.26", modfile="strategy20_26", func_name="evaluate_s20_26_bar",
    tf="M30", extra_kwargs={"mode": "session_pool"}, pattern_name="S20.26")

detect_s20_27_pilot = _make_scalprunner_family_detector(
    sid=20.27, folder="s20.27", modfile="strategy20_27", func_name="evaluate_s20_27_bar",
    tf="M30", extra_kwargs={"mode": "nexus_htf"}, pattern_name="S20.27")

detect_s20_29_pilot = _make_scalprunner_family_detector(
    sid=20.29, folder="s20.29", modfile="strategy20_29", func_name="evaluate_s20_29_bar",
    tf="M30", extra_kwargs={}, pattern_name="S20.29")



detect_s20_40.ratchet = (S20_40_STAGES, 0.8)

DISPATCHER = {
    20.18: detect_s20_18,
    20.19: detect_s20_19,
    20.20: detect_s20_20,
    20.21: detect_s20_21,
    20.22: detect_s20_22,
    20.24: detect_s20_24,
    20.28: detect_s20_28,
    20.40: detect_s20_40,
    20.30: detect_s20_30,
    20.31: detect_s20_31,
    20.32: detect_s20_32,
    20.33: detect_s20_33,
    20.34: detect_s20_34,
    20.35: detect_s20_35,
    20.36: detect_s20_36,
    20.37: detect_s20_37,
    20.38: detect_s20_38,
    20.39: detect_s20_39,
    20.41: detect_s20_41,
    20.42: detect_s20_42,
    20.43: detect_s20_43,
    20.44: detect_s20_44,
    20.45: detect_s20_45,
    20.46: detect_s20_46,
    20.47: detect_s20_47,
    20.48: detect_s20_48,
    20.49: detect_s20_49,
    20.505: detect_s20_50,
    20.51: detect_s20_51,
    20.52: detect_s20_52,
    20.53: detect_s20_53,
    20.1305: detect_s20_130,
    20.131: detect_s20_131,
    20.132: detect_s20_132,
    20.133: detect_s20_133,
    20.134: detect_s20_134,
    20.135: detect_s20_135,
    20.136: detect_s20_136,
    20.137: detect_s20_137,
    20.138: detect_s20_138,
    20.139: detect_s20_139,
    20.3005: detect_s20_300,
    20.3006: detect_s20_300_v2,
    20.23: detect_s20_23_pilot,
    20.25: detect_s20_25_pilot,
    20.26: detect_s20_26_pilot,
    20.27: detect_s20_27_pilot,
    20.29: detect_s20_29_pilot,
    20.301: detect_s20_301,
    20.302: detect_s20_302,
    20.303: detect_s20_303,
    20.304: detect_s20_304,
}

def evaluate_s20_institutional(sid: float, rates, tf_name="M15", symbol="XAUUSD") -> dict:
    func = DISPATCHER.get(sid)
    if not func:
        return {"signal": "WAIT", "reason": f"Unknown S20 SID: {sid}"}
    return func(rates, tf_name=tf_name, symbol=symbol)
