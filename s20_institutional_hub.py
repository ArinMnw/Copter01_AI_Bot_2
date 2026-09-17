# -*- coding: utf-8 -*-
"""s20_institutional_hub.py
Institutional Strategy Hub for S20 Family (S20.18 through S20.304)
Provides standalone detectors for 11 unique institutional strategies
with full multi-symbol adaptation (Gold, Silver, Forex Majors).
"""

import os
import sys
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
    return enabled_syms.get(symbol, True)


# ─────────────────────────────────────────────────────────────────────────────
# 1. S20.18: Order Flow Delta & Passive Absorption
# ─────────────────────────────────────────────────────────────────────────────
def detect_s20_18(rates, tf_name="M15", symbol="XAUUSD.iux") -> dict:
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
def detect_s20_19(rates, tf_name="M15", symbol="XAUUSD.iux") -> dict:
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
def detect_s20_20(rates, tf_name="M15", symbol="XAUUSD.iux") -> dict:
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
def detect_s20_21(rates, tf_name="M15", symbol="XAUUSD.iux", silver_rates=None) -> dict:
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
def detect_s20_22(rates, tf_name="M15", symbol="XAUUSD.iux") -> dict:
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
def detect_s20_24(rates, tf_name="M15", symbol="XAUUSD.iux") -> dict:
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
def detect_s20_28(rates, tf_name="M15", symbol="XAUUSD.iux") -> dict:
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
def detect_s20_301(rates, tf_name="M15", symbol="XAUUSD.iux") -> dict:
    if not is_symbol_enabled_for_s20(symbol):
        return {"signal": "WAIT", "reason": f"S20.301 disabled for {symbol}"}
    # backtest skip M1,M5,M12 — ล้วเฉพาะ Institutional TF (M15, M30, H1, H4) ตรง line 110
    if tf_name.upper() not in ("M15", "M30", "H1", "H4"):
        return {"signal": "WAIT", "reason": f"S20.301 only evaluates on M15/M30/H1/H4 (got {tf_name})"}
    try:
        from strategy.run_master_s20_marathon_201_to_300 import compute_marathon_300_synergies, make_stages
        _, digits = get_symbol_scale_and_digits(symbol)
        df = compute_marathon_300_synergies(rates)
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
def detect_s20_302(rates, tf_name="M15", symbol="XAUUSD.iux") -> dict:
    if not is_symbol_enabled_for_s20(symbol):
        return {"signal": "WAIT", "reason": f"S20.302 disabled for {symbol}"}
    # backtest skip M1,M5,M12 — ล้วเฉพาะ Institutional TF (M15, M30, H1, H4) ตรง line 110
    if tf_name.upper() not in ("M15", "M30", "H1", "H4"):
        return {"signal": "WAIT", "reason": f"S20.302 only evaluates on M15/M30/H1/H4 (got {tf_name})"}
    try:
        from strategy.run_master_s20_marathon_201_to_300 import compute_marathon_300_synergies, make_stages
        _, digits = get_symbol_scale_and_digits(symbol)
        df = compute_marathon_300_synergies(rates)
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
def detect_s20_303(rates, tf_name="M15", symbol="XAUUSD.iux") -> dict:
    if not is_symbol_enabled_for_s20(symbol):
        return {"signal": "WAIT", "reason": f"S20.303 disabled for {symbol}"}
    # backtest skip M1,M5,M12 — ล้วเฉพาะ Institutional TF (M15, M30, H1, H4) ตรง line 110
    if tf_name.upper() not in ("M15", "M30", "H1", "H4"):
        return {"signal": "WAIT", "reason": f"S20.303 only evaluates on M15/M30/H1/H4 (got {tf_name})"}
    try:
        from strategy.run_master_s20_marathon_201_to_300 import compute_marathon_300_synergies, make_stages
        _, digits = get_symbol_scale_and_digits(symbol)
        df = compute_marathon_300_synergies(rates)
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
def detect_s20_304(rates, tf_name="M15", symbol="XAUUSD.iux") -> dict:
    if not is_symbol_enabled_for_s20(symbol):
        return {"signal": "WAIT", "reason": f"S20.304 disabled for {symbol}"}
    # backtest skip M1,M5,M12 — ล้วเฉพาะ Institutional TF (M15, M30, H1, H4) ตรง line 110
    if tf_name.upper() not in ("M15", "M30", "H1", "H4"):
        return {"signal": "WAIT", "reason": f"S20.304 only evaluates on M15/M30/H1/H4 (got {tf_name})"}
    try:
        from strategy.run_master_s20_marathon_201_to_300 import compute_marathon_300_synergies, make_stages
        _, digits = get_symbol_scale_and_digits(symbol)
        df = compute_marathon_300_synergies(rates)
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
DISPATCHER = {
    20.18: detect_s20_18,
    20.19: detect_s20_19,
    20.20: detect_s20_20,
    20.21: detect_s20_21,
    20.22: detect_s20_22,
    20.24: detect_s20_24,
    20.28: detect_s20_28,
    20.301: detect_s20_301,
    20.302: detect_s20_302,
    20.303: detect_s20_303,
    20.304: detect_s20_304,
}

def evaluate_s20_institutional(sid: float, rates, tf_name="M15", symbol="XAUUSD.iux") -> dict:
    func = DISPATCHER.get(sid)
    if not func:
        return {"signal": "WAIT", "reason": f"Unknown S20 SID: {sid}"}
    return func(rates, tf_name=tf_name, symbol=symbol)
