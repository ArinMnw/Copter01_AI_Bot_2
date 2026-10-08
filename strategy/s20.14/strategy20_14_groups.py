import os
import sys

# Append base strategy dir to path so we can import other strategies
base_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.abspath(os.path.join(base_dir, '..', '..')))
sys.path.append(os.path.abspath(os.path.join(base_dir, '..', 's20.13')))

import pandas as pd
import numpy as np
import config
import joblib
from datetime import timedelta

import strategy1
import strategy9
import strategy11
import strategy20_13_24
import tpsl_engine

# Global models cache
MODELS = {}

def load_models():
    global MODELS
    if MODELS: return
    model_dir = os.path.join(base_dir, '..', 's20.14.1', 'backtest-sim')
    models_to_load = ["fvg_buy_v22.pkl", "fvg_sell_v22.pkl", "naiya_buy_v22.pkl", "naiya_sell_v22.pkl"]
    for m in models_to_load:
        path = os.path.join(model_dir, m)
        if os.path.exists(path):
            try:
                MODELS[m] = joblib.load(path)
            except Exception as e:
                print(f"Error loading {m}: {e}")

def get_ml_pred(model_name, features):
    if model_name not in MODELS: return 0
    model = MODELS[model_name]
    if hasattr(model, "feature_names_in_"):
        features_sliced = features[:len(model.feature_names_in_)]
        df_feat = pd.DataFrame([dict(zip(model.feature_names_in_, features_sliced))])
        return model.predict(df_feat)[0]
    return model.predict([features])[0]

def prepare_indicators(rates, tf):
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    df['time_dt'] = df['time'] + timedelta(hours=1) # BKK Time adjustment if needed
    
    hl = df['high'] - df['low']
    hc = np.abs(df['high'] - df['close'].shift())
    lc = np.abs(df['low'] - df['close'].shift())
    tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
    df['atr'] = tr.rolling(window=14).mean()
    
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    
    df['sma12'] = df['close'].rolling(window=12).mean()
    df['sma20'] = df['close'].rolling(window=20).mean()
    df['sma50'] = df['close'].rolling(window=50).mean()
    df['sma200'] = df['close'].rolling(window=200).mean()
    
    df['dist_sma50'] = (df['close'] - df['sma50']) / df['sma50'] * 100
    df['dist_sma200'] = (df['close'] - df['sma200']) / df['sma200'] * 100
    
    df['recent_low'] = df['low'].rolling(window=20).min().shift(1)
    df['recent_high'] = df['high'].rolling(window=20).max().shift(1)
    df['recent_low_50'] = df['low'].rolling(window=50).min().shift(1)
    df['recent_high_50'] = df['high'].rolling(window=50).max().shift(1)
    df['recent_low_35'] = df['low'].rolling(window=35).min().shift(1)
    df['recent_high_35'] = df['high'].rolling(window=35).max().shift(1)
    
    df['body'] = np.abs(df['close'] - df['open'])
    df['range'] = df['high'] - df['low']
    
    df['bull_fvg_raw'] = df['high'].shift(2) < df['low']
    df['bear_fvg_raw'] = df['low'].shift(2) > df['high']
    df['bull_fvg_10'] = df['bull_fvg_raw'].rolling(window=10).max() > 0
    df['bear_fvg_10'] = df['bear_fvg_raw'].rolling(window=10).max() > 0
    
    # Gap logic
    df['time_diff'] = df['time_dt'].diff()
    df['prev_close'] = df['close'].shift(1)
    df['prev_open_2'] = df['open'].shift(2)
    df['prev_low_2'] = df['low'].shift(2)
    df['prev_high_2'] = df['high'].shift(2)
    
    df['inst_gap_buy'] = (df['time_diff'].dt.total_seconds() > 3600) & (df['open'] > df['prev_close'])
    df['inst_gap_sell'] = (df['time_diff'].dt.total_seconds() > 3600) & (df['open'] < df['prev_close'])
    
    # For GapSweep, we need weekly_open. Approximation for live bot:
    # A simple weekly open logic if needed. Not perfectly backtest matching without D1 data,
    # but we can do a simple weekly start check.
    df['dow'] = df['time_dt'].dt.dayofweek
    df['is_new_week'] = df['dow'] < df['dow'].shift(1)
    df['weekly_open'] = df['open'].where(df['is_new_week']).ffill()
    
    df['is_green'] = df['close'] > df['open']
    df['is_red'] = df['close'] < df['open']
    df['gap_sweep_sell'] = (df['weekly_open'].notna()) & (df['open'] < df['weekly_open']) & (df['high'] >= df['weekly_open']) & (df['close'] < df['weekly_open']) & (df['high'] > df['high'].shift(1)) & df['is_red']
    df['gap_sweep_buy'] = (df['weekly_open'].notna()) & (df['open'] > df['weekly_open']) & (df['low'] <= df['weekly_open']) & (df['close'] > df['weekly_open']) & (df['low'] < df['low'].shift(1)) & df['is_green']
    
    # Naiya base
    df['is_green_doji'] = df['is_green'] & (df['body'] <= df['range'] * 0.25)
    df['is_red_doji'] = df['is_red'] & (df['body'] <= df['range'] * 0.25)
    df['naiya_doji_buy_base'] = df['is_green'] & df['is_green_doji'].shift(1) & df['is_red'].shift(2)
    df['naiya_doji_sell_base'] = df['is_red'] & df['is_red_doji'].shift(1) & df['is_green'].shift(2)

    # --- FollowDiv prerequisites (พอร์ตจาก v38_standalone_group19.py) ---
    df['body_bottom'] = df[['open', 'close']].min(axis=1)
    df['body_top'] = df[['open', 'close']].max(axis=1)
    df['engulfing_bull'] = df['is_green'] & df['is_red'].shift(1) & (df['body_bottom'] <= df['body_bottom'].shift(1)) & (df['body_top'] >= df['body_top'].shift(1)) & (df['close'] > df['open'].shift(1))
    df['engulfing_bear'] = df['is_red'] & df['is_green'].shift(1) & (df['body_bottom'] <= df['body_bottom'].shift(1)) & (df['body_top'] >= df['body_top'].shift(1)) & (df['close'] < df['open'].shift(1))
    df['recent_rsi_low_50'] = df['rsi'].rolling(50).min().shift(1)
    df['recent_rsi_high_50'] = df['rsi'].rolling(50).max().shift(1)
    df['div_buy_instant'] = (df['rsi'] < 30) & (df['low'] < df['recent_low_50']) & (df['rsi'] > df['recent_rsi_low_50'])
    df['div_sell_instant'] = (df['rsi'] > 70) & (df['high'] > df['recent_high_50']) & (df['rsi'] < df['recent_rsi_high_50'])
    # เทียบเท่า recent_div_buy/sell counter (10 แท่ง) ใน backtest แบบ vectorized (ไม่ต้องใช้ persistent state)
    df['recent_div_buy_active'] = df['div_buy_instant'].fillna(False).rolling(window=10, min_periods=1).max().astype(bool)
    df['recent_div_sell_active'] = df['div_sell_instant'].fillna(False).rolling(window=10, min_periods=1).max().astype(bool)

    return df


def _generic_deep_sniper_limit(current_bar, is_buy):
    """สูตร Deep Sniper Limit Order ค่าเริ่มต้น (ใช้กับ FollowDiv/ATR ที่ไม่มี override เฉพาะ)
    พอร์ตจาก v38_standalone_group19.py: limit=recent_low/high, sl=ATR*1.5, tp=swing*1.618"""
    swing = current_bar['recent_high'] - current_bar['recent_low']
    if is_buy:
        limit_price = current_bar['recent_low']
        sl = limit_price - (current_bar['atr'] * 1.5)
        tp = limit_price + (swing * 1.618)
    else:
        limit_price = current_bar['recent_high']
        sl = limit_price + (current_bar['atr'] * 1.5)
        tp = limit_price - (swing * 1.618)
    return limit_price, sl, tp


def _check_followdiv(df, current_bar, tag="FollowDiv"):
    """FollowDiv: div_buy/sell_instant ภายใน 10 แท่งล่าสุด + engulfing ตรงข้ามแท่งปัจจุบัน"""
    if pd.isna(current_bar.get('atr')):
        return None
    if bool(current_bar.get('recent_div_buy_active')) and bool(current_bar.get('engulfing_bull')):
        limit_price, sl, tp = _generic_deep_sniper_limit(current_bar, True)
        return {"signal": "BUY", "entry": limit_price, "sl": sl, "tp": tp, "pattern": tag, "reason": f"{tag} BUY"}
    if bool(current_bar.get('recent_div_sell_active')) and bool(current_bar.get('engulfing_bear')):
        limit_price, sl, tp = _generic_deep_sniper_limit(current_bar, False)
        return {"signal": "SELL", "entry": limit_price, "sl": sl, "tp": tp, "pattern": tag, "reason": f"{tag} SELL"}
    return None


def _check_atr_pattern(df, tf, tag="ATR"):
    """ATR pattern: ยืมสัญญาณ BUY/SELL จาก strategy20_13_24 มาแปะป้ายใหม่ (ตาม backtest)
    แล้วใช้สูตร Deep Sniper Limit Order ค่าเริ่มต้น ไม่ใช้ sl/tp ของ strategy20_13_24 เอง"""
    try:
        atr_res = strategy20_13_24.evaluate_bar(df, len(df) - 1, tf=tf)
    except Exception:
        return None
    if not atr_res or atr_res.get('signal') not in ('BUY', 'SELL'):
        return None
    current_bar = df.iloc[-1]
    if pd.isna(current_bar.get('atr')):
        return None
    is_buy = atr_res['signal'] == 'BUY'
    limit_price, sl, tp = _generic_deep_sniper_limit(current_bar, is_buy)
    return {"signal": atr_res['signal'], "entry": limit_price, "sl": sl, "tp": tp, "pattern": tag, "reason": f"{tag} via S20.13.24"}


def _check_gapsweep(current_bar, tag="GapSweep"):
    """GapSweep: sweep แล้วปิดกลับเข้าโซน weekly_open"""
    if getattr(current_bar, 'gap_sweep_buy', False):
        entry = current_bar['weekly_open']
        sl = current_bar['low']
        tp = entry + (entry - sl) * 1.618
        return {"signal": "BUY", "entry": entry, "sl": sl, "tp": tp, "pattern": tag, "reason": f"{tag} BUY"}
    if getattr(current_bar, 'gap_sweep_sell', False):
        entry = current_bar['weekly_open']
        sl = current_bar['high']
        tp = entry - (sl - entry) * 1.618
        return {"signal": "SELL", "entry": entry, "sl": sl, "tp": tp, "pattern": tag, "reason": f"{tag} SELL"}
    return None


def _check_div(rates, current_bar, tf, tag="Div"):
    """Div: strategy9 signal + RSI extreme + ATR floor, SL/TP = Deep Sniper Limit (สูตร fallback
    เดียวกับ FollowDiv/ATR: sl=limit∓1.5×ATR, tp=limit±swing×1.618 — ยืนยันตรงกับ v38_standalone_group{1,3,4,7,10,11,14,15,20,21,22}.py
    บรรทัด `sl = s11_sl_buy if (...) else (limit_price - (row.atr * 1.5))` ทุก group (ไม่ใช่ 2.5×ATR แบบที่เคย implement ผิดไว้)"""
    if pd.isna(current_bar.get('atr')):
        return None
    s9_res = strategy9.strategy_9(rates, tf)
    if s9_res and s9_res.get("signal") == "BUY" and 10.0 <= current_bar['rsi'] <= 34.0 and current_bar['atr'] >= 8.0:
        limit_price, sl, tp = _generic_deep_sniper_limit(current_bar, True)
        return {"signal": "BUY", "entry": limit_price, "sl": sl, "tp": tp, "pattern": tag, "reason": f"{tag} BUY"}
    if s9_res and s9_res.get("signal") == "SELL" and 66.0 <= current_bar['rsi'] <= 90.0 and current_bar['atr'] >= 8.0:
        limit_price, sl, tp = _generic_deep_sniper_limit(current_bar, False)
        return {"signal": "SELL", "entry": limit_price, "sl": sl, "tp": tp, "pattern": tag, "reason": f"{tag} SELL"}
    return None


def _check_fibo(rates, tf, current_bar, tag="Fibo"):
    """Fibo: ยืม signal จาก strategy11 มาแปะป้ายใหม่ (สูตรเดียวกับ Group 3/5/11 เดิม)"""
    s11_res = strategy11.strategy_11(rates, tf)
    if s11_res and s11_res.get("signal") == "BUY":
        return {"signal": "BUY", "entry": s11_res.get("entry", current_bar['close']), "sl": s11_res.get("sl"), "tp": s11_res.get("tp"), "pattern": tag, "reason": f"{tag} BUY"}
    if s11_res and s11_res.get("signal") == "SELL":
        return {"signal": "SELL", "entry": s11_res.get("entry", current_bar['close']), "sl": s11_res.get("sl"), "tp": s11_res.get("tp"), "pattern": tag, "reason": f"{tag} SELL"}
    return None


def _check_naiya_std(df, current_bar, tag="Naiya"):
    """Naiya Standard: แท่งแดง→เขียว engulf high แท่งก่อน (สูตรตรงจาก v38_standalone_group{6,8,9,12,16,17,18}.py
    df['naiya_std_buy_base'] = is_red.shift(1) & is_green & close > high.shift(1), entry=max(open,close)แท่งก่อน,
    sl=low แท่งก่อน, tp=fibo1.618 — ยืนยันสูตรเหมือนกันทุก group ที่ใช้ (2026-09-28)
    ⚠️ ไม่ใช่ ML model และไม่ต้องเป็น doji — คนละ pattern กับที่ implement ผิดไว้ก่อนหน้า (ใช้ naiya_doji_buy_base+ML)"""
    if len(df) < 2:
        return None
    prev = df.iloc[-2]
    is_green_now = current_bar['close'] > current_bar['open']
    is_red_now = current_bar['close'] < current_bar['open']
    prev_is_red = prev['close'] < prev['open']
    prev_is_green = prev['close'] > prev['open']
    if prev_is_red and is_green_now and current_bar['close'] > prev['high']:
        limit_p = max(prev['open'], prev['close'])
        sl = prev['low']
        tp = limit_p + (limit_p - sl) * 1.618
        return {"signal": "BUY", "entry": limit_p, "sl": sl, "tp": tp, "pattern": tag, "reason": f"{tag} Standard BUY"}
    if prev_is_green and is_red_now and current_bar['close'] < prev['low']:
        limit_p = min(prev['open'], prev['close'])
        sl = prev['high']
        tp = limit_p - (sl - limit_p) * 1.618
        return {"signal": "SELL", "entry": limit_p, "sl": sl, "tp": tp, "pattern": tag, "reason": f"{tag} Standard SELL"}
    return None


def _check_naiya_hidden(df, tag="Naiya Hidden"):
    """Naiya Hidden: U-shape reversal 4 แท่ง แดง→เขียว→เขียว→เขียว (สูตรตรงจาก v38_standalone_group9.py)
    naiya_hidden_buy_base = is_red[i-3] & is_green[i-2] & is_green[i-1] & is_green[i]
                             & close[i] > open[i-3] & close[i-1] <= open[i-3]
    sl = min(limit_p - 1.5×ATR, low[i-1], low[i-2], low[i-3])  (แคบสุดของ 4 แท่ง + ATR floor)"""
    if len(df) < 4:
        return None
    b0 = df.iloc[-1]
    b1 = df.iloc[-2]
    b2 = df.iloc[-3]
    b3 = df.iloc[-4]
    if pd.isna(b0.get('atr')):
        return None
    is_red3 = b3['close'] < b3['open']
    is_green2 = b2['close'] > b2['open']
    is_green1 = b1['close'] > b1['open']
    is_green0 = b0['close'] > b0['open']
    if is_red3 and is_green2 and is_green1 and is_green0 and b0['close'] > b3['open'] and b1['close'] <= b3['open']:
        limit_p = min(b3['open'], b3['close'])
        sl = min(limit_p - (b0['atr'] * 1.5), b1['low'], b2['low'], b3['low'])
        tp = limit_p + (limit_p - sl) * 1.618
        return {"signal": "BUY", "entry": limit_p, "sl": sl, "tp": tp, "pattern": tag, "reason": f"{tag} BUY"}

    is_green3 = b3['close'] > b3['open']
    is_red2 = b2['close'] < b2['open']
    is_red1 = b1['close'] < b1['open']
    is_red0 = b0['close'] < b0['open']
    if is_green3 and is_red2 and is_red1 and is_red0 and b0['close'] < b3['open'] and b1['close'] >= b3['open']:
        limit_p = max(b3['open'], b3['close'])
        sl = max(limit_p + (b0['atr'] * 1.5), b1['high'], b2['high'], b3['high'])
        tp = limit_p - (sl - limit_p) * 1.618
        return {"signal": "SELL", "entry": limit_p, "sl": sl, "tp": tp, "pattern": tag, "reason": f"{tag} SELL"}
    return None


def _detect_naiya_doji(df, tag="Naiya Doji"):
    """Naiya Doji: หา doji ที่เป็น 3-bar fractal high/low ใน 30 แท่งย้อนหลัง แล้วเช็คว่าราคาทะลุฐานนั้นแล้ว
    พอร์ตจาก strategy/s20.14.1/backtest-sim/v38_standalone_group8.py (Naiya Doji dynamic structural detection)
    ⚠️ ตัดส่วน dynamic TP ตามช่วงเวลา (get_dynamic_tp ใน backtest) ออก ใช้แค่สูตร TP หลัก (fibo 1.618 จากฐาน Doji)"""
    n = len(df)
    if n < 35:
        return None
    i = n - 1
    row = df.iloc[i]
    bars = df[['open', 'high', 'low', 'close']].to_dict('records')

    # BUY: doji ที่เป็น 3-bar fractal low แล้วราคาทะลุ high ของมันแล้ว
    for b in range(1, 30):
        if i - b < 0:
            continue
        b_bar = bars[i - b]
        rng = b_bar['high'] - b_bar['low']
        body = abs(b_bar['close'] - b_bar['open'])
        if not (rng > 0 and body <= rng * 0.35):
            continue
        prev_low = bars[i - b - 1]['low'] if i - b - 1 >= 0 else float('inf')
        next_low = bars[i - b + 1]['low'] if i - b + 1 < n else float('inf')
        if b_bar['low'] < prev_low and b_bar['low'] < next_low:
            if row['close'] > b_bar['high']:
                limit_p = round((b_bar['high'] + b_bar['low']) / 2, 2)
                sl = b_bar['low']
                tp = limit_p + (limit_p - sl) * 1.618
                return {"signal": "BUY", "entry": limit_p, "sl": sl, "tp": tp, "pattern": tag, "reason": f"{tag} BUY (fractal low doji broken)"}

    # SELL: doji ที่เป็น 3-bar fractal high แล้วราคาทะลุ low ของมันแล้ว
    for b in range(1, 30):
        if i - b < 0:
            continue
        b_bar = bars[i - b]
        rng = b_bar['high'] - b_bar['low']
        body = abs(b_bar['close'] - b_bar['open'])
        if not (rng > 0 and body <= rng * 0.35):
            continue
        prev_high = bars[i - b - 1]['high'] if i - b - 1 >= 0 else 0.0
        next_high = bars[i - b + 1]['high'] if i - b + 1 < n else 0.0
        if b_bar['high'] > prev_high and b_bar['high'] > next_high:
            if row['close'] < b_bar['low']:
                limit_p = round((b_bar['high'] + b_bar['low']) / 2, 2)
                sl = b_bar['high']
                tp = limit_p - (sl - limit_p) * 1.618
                return {"signal": "SELL", "entry": limit_p, "sl": sl, "tp": tp, "pattern": tag, "reason": f"{tag} SELL (fractal high doji broken)"}

    return None


# 2026-10-02: get_dynamic_tp พอร์ตจาก v38_standalone_group*.py — backtest คำนวณ TP จาก swing
# ของ TF (หรือ D1 3-bar swing เฉพาะ Group 9) แล้ว "เขียนทับ" TP ของสูตร raw/fibo1.618 ก่อนที่
# TPSL_EXP override (round) จะรันอีกที — มีผลจริงแค่ตอน target=SL_ONLY (R1/R2) เพราะถ้า target=BOTH
# round override จะเขียนทับ TP อีกรอบจน dyn_tp ไม่เหลือผล live ไม่เคย implement ส่วนนี้มาก่อนเลย
# ⚠️ backtest ไม่เรียก get_dynamic_tp ให้ GapSweep เลย (เช็คโค้ดแล้วยืนยัน) — จึงไม่ apply ให้ pattern นี้
_HTF_RATES_CACHE = {}  # tf -> {'df': DataFrame, 'last_time': int}


def _get_htf_rates_cached(tf_str, count=1500):
    """ดึง rates ของ TF ที่ใหญ่กว่า mาcache ไว้ รีเฟรชเฉพาะตอนมีแท่งใหม่ของ TF นั้น
    (เหมือน _refresh_h1_cache_g23 แต่ generic ทุก TF)"""
    try:
        import MetaTrader5 as mt5
        tf_map = {"M15": mt5.TIMEFRAME_M15, "M30": mt5.TIMEFRAME_M30, "H1": mt5.TIMEFRAME_H1,
                  "H4": mt5.TIMEFRAME_H4, "H12": mt5.TIMEFRAME_H12, "D1": mt5.TIMEFRAME_D1}
        mt5_tf = tf_map.get(str(tf_str).upper())
        if mt5_tf is None:
            return None
        cache = _HTF_RATES_CACHE.setdefault(tf_str, {'df': None, 'last_time': None})
        latest = mt5.copy_rates_from_pos(config.SYMBOL, mt5_tf, 0, 1)
        if latest is not None and len(latest) > 0:
            if cache['last_time'] != latest[0]['time']:
                rates = mt5.copy_rates_from_pos(config.SYMBOL, mt5_tf, 0, count)
                if rates is not None and len(rates) > 0:
                    df_htf = pd.DataFrame(rates)
                    cache['df'] = df_htf
                    cache['last_time'] = latest[0]['time']
        return cache['df']
    except Exception:
        return _HTF_RATES_CACHE.get(tf_str, {}).get('df')


def get_dynamic_tp(group_id, is_buy, tf_str):
    """พอร์ตจาก v38_standalone_group*.py's get_dynamic_tp (ตัดส่วน rate_cache เดือนก.ย.ที่ backtest
    ใช้ข้อมูลเก่าค้างทิ้ง — live ดึงสดทุกครั้งที่มีแท่งใหม่แทน)
    Group 9: ใช้ D1 3-bar-center swing, 40 แท่งล่าสุดเท่านั้น (ไม่สน tf_str ของ pattern เลย)
    กลุ่มอื่น: ใช้ swing ของ tf_str เอง (window=5, D1=21, H12=11), lookback 1500 แท่ง"""
    if group_id == 9:
        df_d1 = _get_htf_rates_cached("D1")
        if df_d1 is None or len(df_d1) == 0:
            return None
        d1_bars = df_d1.tail(40)
        if is_buy:
            high_roll = d1_bars['high'].rolling(3, center=True).max()
            swings = d1_bars[d1_bars['high'] == high_roll]['high'].dropna()
            return float(swings.iloc[-1]) if not swings.empty else float(d1_bars['high'].max())
        else:
            low_roll = d1_bars['low'].rolling(3, center=True).min()
            swings = d1_bars[d1_bars['low'] == low_roll]['low'].dropna()
            return float(swings.iloc[-1]) if not swings.empty else float(d1_bars['low'].min())

    df_t = _get_htf_rates_cached(tf_str)
    if df_t is None or len(df_t) < 10:
        return None
    window = 5
    if str(tf_str).upper() == "D1":
        window = 21
    elif str(tf_str).upper() == "H12":
        window = 11
    chunk = df_t.tail(1500)
    if is_buy:
        high_roll = chunk['high'].rolling(window, center=True).max()
        swings = chunk[chunk['high'] == high_roll]['high'].dropna().values.tolist()
        if not swings:
            return float(chunk['high'].max())
        target = swings[-1]
        if len(swings) >= 2:
            target = max(swings[-1], swings[-2])
        return float(target)
    else:
        low_roll = chunk['low'].rolling(window, center=True).min()
        swings = chunk[chunk['low'] == low_roll]['low'].dropna().values.tolist()
        if not swings:
            return float(chunk['low'].min())
        target = swings[-1]
        if len(swings) >= 2:
            target = min(swings[-1], swings[-2])
        return float(target)


# 2026-09-29 audit: v2 backtest (quant-verification-v2, ใช้สร้าง config.S20_14_GROUP_COMBOS
# ปัจจุบัน) ไม่เคย inject TPSL-round override ให้บาง (group, pattern, signal) เลยสักบรรทัด —
# ถ้า live ยัง apply override ให้ค่าพวกนี้ ผลจริงจะไม่ตรงกับตัวเลขที่ v2 วัดไว้ (round ที่เลือก
# ไว้ใน config ไม่มีความหมายสำหรับ combo พวกนี้ เพราะทุก round ให้ SL/TP เหมือนกันเป๊ะใน v2)
_V2_NO_OVERRIDE_PATTERN_SIGNAL = {
    ("Naiya Doji", "SELL"),          # BUY มี override, SELL ไม่มี ทุก group ที่ใช้ Naiya Doji
    ("Naiya", "BUY"), ("Naiya", "SELL"),             # ไม่มี override เลยทั้งสองฝั่ง
    ("Naiya Hidden", "BUY"), ("Naiya Hidden", "SELL"),  # ไม่มี override เลยทั้งสองฝั่ง (มีแค่ G9)
}
# combined-pattern BUY (FollowDiv/ATR/Div/Fibo ที่ dispatch ผ่าน patterns_buy/combined_pat ใน
# backtest) ไม่มี override ใน v2 เฉพาะ group เหล่านี้ — SELL มี override ปกติทุก group
_V2_NO_OVERRIDE_BUY_GROUPS = {2, 6, 8, 9, 12, 18}
_V2_NO_OVERRIDE_BUY_PATTERNS = {"FollowDiv", "ATR", "Div", "Fibo"}
# Group 2's Inst_Gap: SELL ไม่มี override ใน v2, BUY มี
_V2_NO_OVERRIDE_G2_SELL_PATTERNS = {"Inst_Gap"}


def _v2_had_no_override(group_id, pattern, signal):
    if (pattern, signal) in _V2_NO_OVERRIDE_PATTERN_SIGNAL:
        return True
    if signal == "BUY" and group_id in _V2_NO_OVERRIDE_BUY_GROUPS and pattern in _V2_NO_OVERRIDE_BUY_PATTERNS:
        return True
    if group_id == 2 and signal == "SELL" and pattern in _V2_NO_OVERRIDE_G2_SELL_PATTERNS:
        return True
    return False


def apply_group_tpsl_round(rates, tf, group_id, result, mode_target):
    """Override SL/TP ตาม TPSL round ที่เป็นแชมป์จริงของคู่ (pattern, tf) นั้น (config.S20_14_GROUP_COMBOS, 2026-09-23)
    ⚠️ ก่อนหน้านี้ live ใช้แค่สูตร SL/TP แบบ default/baseline ของแต่ละ pattern เฉยๆ ไม่เคย apply
    round ที่ทำให้ (pattern, tf) นั้นเป็นแชมป์ใน backtest/walk-forward เลย — ทำให้ผลจริงบน live ไม่ตรงกับที่ทดสอบมา
    2026-09-23 v2: เปลี่ยนจาก lookup ตาม group_id อย่างเดียวมาเป็นรับ mode_target ที่ scanner.py resolve มาให้แล้ว
    ตามคู่ (pattern, tf) จริง (ก่อนหน้านี้ทั้งกลุ่มใช้ round เดียวกันหมด ทั้งที่แต่ละคู่ใน top-10 มาจากคนละ round)
    2026-09-29: เพิ่มเช็ค _v2_had_no_override — บาง (group, pattern, signal) ที่ v2 backtest
    ไม่เคย apply override เลย ต้อง skip ให้ live ตรงกับที่ v2 วัดผลไว้จริง
    เรียกจาก scanner.py หลัง dispatch ทุกกลุ่ม (ดู _s2014_results loop)"""
    if not result or result.get('signal') not in ('BUY', 'SELL'):
        return result
    if _v2_had_no_override(group_id, result.get('pattern'), result['signal']):
        return result
    if not mode_target:
        return result
    mode, target = mode_target
    new_result = dict(result)

    # 2026-10-02: Dynamic TP (ดู comment เหนือ get_dynamic_tp) — มีผลจริงแค่ตอน target ไม่รวม
    # "TP" (เช่น SL_ONLY, R1/R2) เพราะถ้า target=BOTH ค่า tpsl_engine ด้านล่างจะเขียนทับ TP
    # อีกทีอยู่ดี (ตรงกับลำดับการรันใน backtest) — ไม่ apply ให้ GapSweep (backtest ไม่เคยเรียก)
    if target != "BOTH" and new_result.get('pattern') != "GapSweep" and new_result.get('tp') is not None:
        try:
            is_buy = new_result['signal'] == 'BUY'
            dyn_tp = get_dynamic_tp(group_id, is_buy, tf)
            if dyn_tp is not None:
                cur_tp = new_result['tp']
                if (is_buy and dyn_tp > cur_tp) or ((not is_buy) and dyn_tp < cur_tp):
                    pattern = new_result.get('pattern', '')
                    # 2026-10-05 (Phase B): group_id==19 ก็ assign tp=dyn_tp ตรงๆเหมือน group 9
                    # (v38_standalone_group19.py: `if group_id == 19 or "Fibo" in patterns_buy: tp = dyn_tp`)
                    # และเช็ค "Fibo" in pattern แทน == เพราะ combined_pat label เป็น "Fibo/Div" ได้
                    if group_id in (9, 19) or "Fibo" in pattern:
                        new_result['tp'] = dyn_tp
                    else:
                        cur_sl = new_result.get('sl')
                        if cur_sl is not None:
                            if is_buy:
                                new_result['tp'] = cur_sl + (dyn_tp - cur_sl) * 1.618
                            else:
                                new_result['tp'] = cur_sl - (cur_sl - dyn_tp) * 1.618
        except Exception as e:
            print(f"[S20.14 Group {group_id}] get_dynamic_tp error: {e}")

    try:
        if rates is None or len(rates) < 55:
            return new_result
        df = prepare_indicators(rates, tf)
        idx = len(df) - 1
        if idx < 3:
            return new_result
        recent_3 = df.iloc[max(0, idx - 3):idx]
        current_bar = df.iloc[-1]
        entry_price = new_result.get('entry')
        if entry_price is None:
            entry_price = current_bar['close']
        tpsl_res = tpsl_engine.get_tpsl(mode=mode, signal=new_result['signal'], entry_price=entry_price,
                                         current_bar=current_bar, recent_3=recent_3, df=df, idx=idx, tf=tf)
        if target in ("SL_ONLY", "BOTH") and tpsl_res.get("sl", 0) != 0:
            new_result['sl'] = tpsl_res['sl']
        if target in ("TP_ONLY", "BOTH") and tpsl_res.get("tp", 0) != 0:
            new_result['tp'] = tpsl_res['tp']
        return new_result
    except Exception as e:
        print(f"[S20.14 Group {group_id}] apply_group_tpsl_round error: {e}")
        return new_result


# ให้ pending order รอ fill ได้นานเท่ากับที่ backtest จำลอง (max_bars_map ใน v38_standalone_group*.py
# ทุก TF = ~168 ชั่วโมง/1 สัปดาห์ แค่แปลงเป็นจำนวนแท่งตาม TF) — ก่อนหน้านี้ live ใช้ default cancel_bars=12
# ของ trailing.py (watchdog กลาง ใช้กับทุก strategy S20.x) ทำให้ยกเลิกไวกว่า backtest มาก (เช่น M1=12 นาที
# H1=12 ชม.) ตัดโอกาสไม้ที่ backtest นับว่าชนะทิ้งไปเยอะ — ตั้งใจให้ตรงกับ backtest ปัจจุบันไปก่อน
# (checklist ข้อ 10 ยังไม่แก้ทั้งคู่ รอแก้พร้อมกันทีหลัง ไม่ใช่แก้ live ให้ "ถูกกว่า" เฉยๆ โดยไม่แก้ backtest ตาม)
_S20_14_MAX_BARS_MAP = {"M1": 10080, "M5": 2016, "M15": 672, "M30": 336,
                        "H1": 168, "H4": 42, "H12": 14, "D1": 7}


def apply_group_cancel_bars(tf, result):
    """เติม cancel_bars ให้ตรงกับ max_bars_map ของ backtest (ดู comment ด้านบน)"""
    if not result or result.get('signal') not in ('BUY', 'SELL'):
        return result
    new_result = dict(result)
    new_result['cancel_bars'] = _S20_14_MAX_BARS_MAP.get(str(tf).upper(), 168)
    return new_result


# 2026-10-02 (Phase A ของ "multi-pattern ต่อบาร์"): backtest เช็ค GapSweep/Inst_Gap/Naiya Doji/
# Naiya/Naiya Hidden เป็น `if` อิสระต่อกัน (ไม่ใช่ elif) — ถ้าหลาย pattern เข้าเงื่อนไขพร้อมกันในบาร์
# เดียวกัน backtest จะสร้าง pending order แยกกันทุกตัว ไม่ได้เลือกแค่ตัวแรก แต่ live เดิม early-return
# ตัวแรกที่เจอแล้วทิ้งตัวที่เหลือ — ทำให้เสียโอกาสไม้ที่ backtest นับว่าเทรดจริง
# ⚠️ เฉพาะ 5 pattern อิสระกลุ่มนี้เท่านั้น (ชื่อ pattern เดี่ยวเดิม ตรงกับ config.S20_14_GROUP_COMBOS
# v2 ที่ deploy อยู่) — ส่วน Fibo/Div/FollowDiv/ATR/Doji (combined_pat ใน backtest ที่รวมเป็นชื่อ
# "X/Y" เวลา match พร้อมกัน) ยังไม่แก้ตอนนี้ (Phase B) เพราะ v2 config ไม่มี key แบบ combined เลย
# ถ้า assign หลาย match กลายเป็น MULTI ตอนนี้ จะหลุด "ไม่อยู่ใน top10 combo" กลายเป็นแย่ลงแทน
# ใช้ convention เดียวกับ S8/S14/S15 ใน scanner.py: {"signal":"MULTI","orders":[...]}
def _wrap_multi(matches, group_id):
    matches = [m for m in matches if m]
    if not matches:
        return None
    if len(matches) == 1:
        return matches[0]
    return {"signal": "MULTI", "orders": matches,
            "pattern": "+".join(m.get("pattern", "") for m in matches),
            "reason": f"S20.14 Group {group_id}: {len(matches)} pattern อิสระยิงพร้อมกันบาร์เดียว"}

# ------------- GROUP 2 -------------
def strategy_20_14_2(rates, tf="H1"):
    # Group 2: Micro Retest Engine (top-10 จริง = Inst_Gap / FollowDiv / ATR)
    # 2026-09-28: เพิ่ม FollowDiv/ATR ที่ตกหล่น (มีใน config.S20_14_GROUP_COMBOS แต่ไม่เคย implement)
    if rates is None or len(rates) < 55: return {"signal": "WAIT", "reason": "Not enough data"}

    df = prepare_indicators(rates, tf)
    current_bar = df.iloc[-1]

    matches = []
    if getattr(current_bar, 'inst_gap_buy', False):
        limit_p = current_bar['prev_open_2'] if not pd.isna(current_bar['prev_open_2']) else current_bar['prev_close']
        sl = current_bar['prev_low_2'] if not pd.isna(current_bar['prev_low_2']) else current_bar['low']
        tp = limit_p + (limit_p - sl) * 1.618
        matches.append({"signal": "BUY", "entry": limit_p, "sl": sl, "tp": tp, "pattern": "Inst_Gap", "reason": "Group 2 Inst_Gap"})

    if getattr(current_bar, 'inst_gap_sell', False):
        limit_p = current_bar['prev_open_2'] if not pd.isna(current_bar['prev_open_2']) else current_bar['prev_close']
        sl = current_bar['prev_high_2'] if not pd.isna(current_bar['prev_high_2']) else current_bar['high']
        tp = limit_p - (sl - limit_p) * 1.618
        matches.append({"signal": "SELL", "entry": limit_p, "sl": sl, "tp": tp, "pattern": "Inst_Gap", "reason": "Group 2 Inst_Gap"})

    if not pd.isna(current_bar['atr']):
        res = _check_followdiv(df, current_bar)
        if not res: res = _check_atr_pattern(df, tf)
        if res: matches.append(res)

    result = _wrap_multi(matches, 2)
    return result if result else {"signal": "WAIT", "reason": "No Setup"}

# ------------- GROUP 3 -------------
def strategy_20_14_3(rates, tf="H1"):
    # Group 3: Institutional Fibo Zone (top-10 จริง = Fibo / Div / FollowDiv)
    # 2026-09-23: เพิ่ง implement ใหม่ทั้งฟังก์ชัน ไม่เคยมีมาก่อน (เดิมไม่มี live function เลย)
    if rates is None or len(rates) < 55: return {"signal": "WAIT"}
    df = prepare_indicators(rates, tf)
    current_bar = df.iloc[-1]
    if pd.isna(current_bar['atr']): return {"signal": "WAIT"}

    s11_res = strategy11.strategy_11(rates, tf)
    if s11_res and s11_res.get("signal") == "BUY":
        return {"signal": "BUY", "entry": s11_res.get("entry", current_bar['close']), "sl": s11_res.get("sl"), "tp": s11_res.get("tp"), "pattern": "Fibo", "reason": "Group 3 Fibo BUY"}
    if s11_res and s11_res.get("signal") == "SELL":
        return {"signal": "SELL", "entry": s11_res.get("entry", current_bar['close']), "sl": s11_res.get("sl"), "tp": s11_res.get("tp"), "pattern": "Fibo", "reason": "Group 3 Fibo SELL"}

    s9_res = strategy9.strategy_9(rates, tf)
    if s9_res and s9_res.get("signal") == "BUY":
        if 10.0 <= current_bar['rsi'] <= 34.0 and current_bar['atr'] >= 8.0:
            entry = current_bar['recent_low']
            sl = entry - (2.5 * current_bar['atr'])
            tp = entry + ((current_bar['recent_high'] - entry) * 1.618)
            return {"signal": "BUY", "entry": entry, "sl": sl, "tp": tp, "pattern": "Div", "reason": "Group 3 Div BUY"}
    if s9_res and s9_res.get("signal") == "SELL":
        if 66.0 <= current_bar['rsi'] <= 90.0 and current_bar['atr'] >= 8.0:
            entry = current_bar['recent_high']
            sl = entry + (2.5 * current_bar['atr'])
            tp = entry - ((entry - current_bar['recent_low']) * 1.618)
            return {"signal": "SELL", "entry": entry, "sl": sl, "tp": tp, "pattern": "Div", "reason": "Group 3 Div SELL"}

    res = _check_followdiv(df, current_bar)
    if res: return res
    res = _check_atr_pattern(df, tf)
    if res: return res

    return {"signal": "WAIT", "reason": "No Setup"}

# ------------- GROUP 4 -------------
def strategy_20_14_4(rates, tf="H1"):
    # Group 4: Liquidity Sweep Cluster (top-10 จริง = Fibo / Div / FollowDiv เหมือน Group 3)
    return strategy_20_14_3(rates, tf)

# ------------- GROUP 6 -------------
def strategy_20_14_6(rates, tf="H1"):
    # Group 6: Naiya Doji Volume Trap (top-10 จริง = Naiya Doji / Naiya / FollowDiv)
    # 2026-09-23: เพิ่ง implement ใหม่ทั้งฟังก์ชัน ไม่เคยมีมาก่อน (เดิมไม่มี live function เลย)
    # 2026-09-28: เพิ่ม Naiya(ML)/FollowDiv ที่ตกหล่น
    if rates is None or len(rates) < 55: return {"signal": "WAIT"}
    load_models()
    df = prepare_indicators(rates, tf)
    current_bar = df.iloc[-1]
    if pd.isna(current_bar['atr']): return {"signal": "WAIT"}
    matches = []
    nd = _detect_naiya_doji(df)
    if nd: matches.append(nd)
    res = _check_naiya_std(df, current_bar)
    if res: matches.append(res)
    res = _check_followdiv(df, current_bar)
    if res: matches.append(res)
    result = _wrap_multi(matches, 6)
    return result if result else {"signal": "WAIT", "reason": "No Setup"}

# ------------- GROUP 20 -------------
def strategy_20_14_20(rates, tf="H1"):
    # Group 20: GapSweep Reversion Engine (top-10 จริง = FollowDiv / ATR / GapSweep เหมือน Group 1)
    return strategy_20_14_1(rates, tf)

# ------------- GROUP 5 -------------
def strategy_20_14_5(rates, tf="H1"):
    if rates is None or len(rates) < 55: return {"signal": "WAIT", "reason": "Not enough data"}
    
    load_models()
    df = prepare_indicators(rates, tf)
    current_bar = df.iloc[-1]
    
    if pd.isna(current_bar['atr']): return {"signal": "WAIT"}
    
    f = [current_bar['rsi'], current_bar['atr'], current_bar['dist_sma50'], current_bar['dist_sma200'], current_bar['body'], current_bar['range']]
    fvg_buy_ml = get_ml_pred("fvg_buy_v22.pkl", f)
    fvg_sell_ml = get_ml_pred("fvg_sell_v22.pkl", f)
    
    swing_h = current_bar['recent_high_50']
    swing_l = current_bar['recent_low_50']
    fibo_38_2 = swing_l + (swing_h - swing_l) * 0.382
    fibo_61_8 = swing_l + (swing_h - swing_l) * 0.618
    
    s11_res = strategy11.strategy_11(rates, tf)
    
    # BUY
    if current_bar['bull_fvg_10'] and (fvg_buy_ml == 1 or current_bar['rsi'] > 70):
        if 15.0 <= current_bar['rsi'] <= 68.0 and current_bar['atr'] >= 7.0:
            if current_bar['recent_low'] < fibo_38_2 or current_bar['rsi'] > 70:
                entry = current_bar['recent_low']
                sl = entry - (2.5 * current_bar['atr'])
                tp = entry + ((current_bar['recent_high'] - entry) * 1.618)
                return {"signal": "BUY", "entry": entry, "sl": sl, "tp": tp, "pattern": "FVG", "reason": "Group 5 FVG BUY"}
                
    if s11_res and s11_res.get("signal") == "BUY":
        return {"signal": "BUY", "entry": s11_res.get("entry", current_bar['close']), "sl": s11_res.get("sl"), "tp": s11_res.get("tp"), "pattern": "Fibo", "reason": "Group 5 Fibo BUY"}
        
    # SELL
    if current_bar['bear_fvg_10'] and (fvg_sell_ml == 1 or current_bar['rsi'] < 30):
        if 10.0 <= current_bar['rsi'] <= 77.0 and current_bar['atr'] >= 10.0:
            if current_bar['recent_high'] > fibo_61_8 or current_bar['rsi'] < 30:
                entry = current_bar['recent_high']
                sl = entry + (2.5 * current_bar['atr'])
                tp = entry - ((entry - current_bar['recent_low']) * 1.618)
                return {"signal": "SELL", "entry": entry, "sl": sl, "tp": tp, "pattern": "FVG", "reason": "Group 5 FVG SELL"}
                
    if s11_res and s11_res.get("signal") == "SELL":
        return {"signal": "SELL", "entry": s11_res.get("entry", current_bar['close']), "sl": s11_res.get("sl"), "tp": s11_res.get("tp"), "pattern": "Fibo", "reason": "Group 5 Fibo SELL"}
        
    return {"signal": "WAIT", "reason": "No Setup"}

# ------------- GROUP 9 -------------
def strategy_20_14_9(rates, tf="H1"):
    if rates is None or len(rates) < 55: return {"signal": "WAIT"}

    load_models()
    df = prepare_indicators(rates, tf)
    current_bar = df.iloc[-1]
    if pd.isna(current_bar['atr']): return {"signal": "WAIT"}

    # 2026-09-23: Naiya Doji ตัวจริง (top-10 ของ Group 9 คือ pattern นี้) เช็คก่อน แล้วเหลือ Naiya/Doji เดิมเป็น fallback
    matches = []
    nd = _detect_naiya_doji(df)
    if nd: matches.append(nd)

    # 2026-09-28: "Naiya"/"Naiya Hidden" ของเดิม (ML+doji-gated) ผิดสูตรจาก backtest จริงมาตลอด
    # (v38_standalone_group9.py ไม่มี ML model เกี่ยวข้องกับ Naiya/Naiya Hidden เลยสักจุด) แก้เป็นสูตรจริง
    res = _check_naiya_std(df, current_bar)
    if res: matches.append(res)
    res = _check_naiya_hidden(df)
    if res: matches.append(res)

    combined = None
    if current_bar['range'] > 0 and current_bar['body'] < 0.4 * current_bar['range'] and (current_bar['close'] - current_bar['low']) > 0.5 * current_bar['range'] and current_bar['low'] <= current_bar['recent_low'] + current_bar['atr']*0.5 and 0 <= current_bar['rsi'] <= 2:
        entry = current_bar['recent_low']
        sl = entry - (2.5 * current_bar['atr'])
        tp = entry + ((current_bar['recent_high'] - entry) * 1.618)
        combined = {"signal": "BUY", "entry": entry, "sl": sl, "tp": tp, "pattern": "Doji", "reason": "Group 9 Doji BUY"}
    elif current_bar['range'] > 0 and current_bar['body'] < 0.4 * current_bar['range'] and (current_bar['high'] - current_bar['close']) > 0.5 * current_bar['range'] and current_bar['high'] >= current_bar['recent_high'] - current_bar['atr']*0.5 and 74 <= current_bar['rsi'] <= 78 and current_bar['close'] < current_bar['sma50'] and current_bar['close'] < current_bar['sma200']:
        entry = current_bar['recent_high']
        sl = entry + (2.5 * current_bar['atr'])
        tp = entry - ((entry - current_bar['recent_low']) * 1.618)
        combined = {"signal": "SELL", "entry": entry, "sl": sl, "tp": tp, "pattern": "Doji", "reason": "Group 9 Doji SELL"}

    # 2026-09-28: FollowDiv ที่ตกหล่น (มีใน config.S20_14_GROUP_COMBOS แต่ไม่เคย implement)
    if not combined:
        combined = _check_followdiv(df, current_bar)
    if combined: matches.append(combined)

    result = _wrap_multi(matches, 9)
    return result if result else {"signal": "WAIT", "reason": "No Setup"}

# ------------- GROUP 12 -------------
def strategy_20_14_12(rates, tf="H1"):
    # Group 12 is like 9 but with custom Sweep Logic
    if rates is None or len(rates) < 55: return {"signal": "WAIT"}
    
    load_models()
    df = prepare_indicators(rates, tf)
    current_bar = df.iloc[-1]
    prev_bar = df.iloc[-2]
    if pd.isna(current_bar['atr']): return {"signal": "WAIT"}

    # 2026-09-23: Naiya Doji ตัวจริง (top-10 ของ Group 12 คือ pattern นี้) เช็คก่อน แล้วเหลือ Sweep เดิมเป็น fallback
    matches = []
    nd = _detect_naiya_doji(df)
    if nd: matches.append(nd)

    # Sweep condition
    sweep_sell = current_bar['high'] > prev_bar['high'] and current_bar['close'] < current_bar['high']
    sweep_buy = current_bar['low'] < prev_bar['low'] and current_bar['close'] > current_bar['low']
    
    f = [current_bar['rsi'], current_bar['atr'], current_bar['dist_sma50'], current_bar['dist_sma200'], current_bar['body'], current_bar['range']]
    naiya_buy_ml = get_ml_pred("naiya_buy_v22.pkl", f)
    naiya_sell_ml = get_ml_pred("naiya_sell_v22.pkl", f)
    
    swing_h = current_bar['recent_high_50']
    swing_l = current_bar['recent_low_50']
    fibo_38_2 = swing_l + (swing_h - swing_l) * 0.382
    fibo_61_8 = swing_l + (swing_h - swing_l) * 0.618
    
    # BUY
    naiya_res = None
    if current_bar['naiya_doji_buy_base'] and sweep_buy:
        entry = current_bar['low']
        sl = entry - (2.5 * current_bar['atr'])
        tp = entry + ((current_bar['recent_high'] - entry) * 1.618)
        naiya_res = {"signal": "BUY", "entry": entry, "sl": sl, "tp": tp, "pattern": "Naiya", "reason": "Group 12 Sweep Naiya BUY"}
    elif current_bar['naiya_doji_sell_base'] and sweep_sell:
        entry = current_bar['high']
        sl = entry + (2.5 * current_bar['atr'])
        tp = entry - ((entry - current_bar['recent_low']) * 1.618)
        naiya_res = {"signal": "SELL", "entry": entry, "sl": sl, "tp": tp, "pattern": "Naiya", "reason": "Group 12 Sweep Naiya SELL"}
    if naiya_res: matches.append(naiya_res)

    combined = None
    if current_bar['range'] > 0 and current_bar['body'] < 0.4 * current_bar['range'] and (current_bar['close'] - current_bar['low']) > 0.5 * current_bar['range'] and current_bar['low'] <= current_bar['recent_low'] + current_bar['atr']*0.5 and 0 <= current_bar['rsi'] <= 2:
        entry = current_bar['recent_low']
        sl = entry - (2.5 * current_bar['atr'])
        tp = entry + ((current_bar['recent_high'] - entry) * 1.618)
        combined = {"signal": "BUY", "entry": entry, "sl": sl, "tp": tp, "pattern": "Doji", "reason": "Group 12 Doji BUY"}
    elif current_bar['range'] > 0 and current_bar['body'] < 0.4 * current_bar['range'] and (current_bar['high'] - current_bar['close']) > 0.5 * current_bar['range'] and current_bar['high'] >= current_bar['recent_high'] - current_bar['atr']*0.5 and 74 <= current_bar['rsi'] <= 78 and current_bar['close'] < current_bar['sma50'] and current_bar['close'] < current_bar['sma200']:
        entry = current_bar['recent_high']
        sl = entry + (2.5 * current_bar['atr'])
        tp = entry - ((entry - current_bar['recent_low']) * 1.618)
        combined = {"signal": "SELL", "entry": entry, "sl": sl, "tp": tp, "pattern": "Doji", "reason": "Group 12 Doji SELL"}

    # 2026-09-28: ATR/FollowDiv ที่ตกหล่น (มีใน config.S20_14_GROUP_COMBOS แต่ไม่เคย implement)
    if not combined: combined = _check_atr_pattern(df, tf)
    if not combined: combined = _check_followdiv(df, current_bar)
    if combined: matches.append(combined)

    result = _wrap_multi(matches, 12)
    return result if result else {"signal": "WAIT", "reason": "No Setup"}

# ------------- GROUP 13 -------------
def strategy_20_14_13(rates, tf="H1"):
    if rates is None or len(rates) < 55: return {"signal": "WAIT"}
    
    load_models()
    df = prepare_indicators(rates, tf)
    current_bar = df.iloc[-1]
    if pd.isna(current_bar['atr']): return {"signal": "WAIT"}
    
    # GapSweep Check (independent — ยิงพร้อม pattern อื่นได้)
    matches = []
    if getattr(current_bar, 'gap_sweep_buy', False):
        entry = current_bar['weekly_open']
        sl = current_bar['low']
        tp = entry + (entry - sl) * 1.618
        matches.append({"signal": "BUY", "entry": entry, "sl": sl, "tp": tp, "pattern": "GapSweep", "reason": "Group 13 GapSweep"})
    if getattr(current_bar, 'gap_sweep_sell', False):
        entry = current_bar['weekly_open']
        sl = current_bar['high']
        tp = entry - (sl - entry) * 1.618
        matches.append({"signal": "SELL", "entry": entry, "sl": sl, "tp": tp, "pattern": "GapSweep", "reason": "Group 13 GapSweep"})

    # FVG Check
    f = [current_bar['rsi'], current_bar['atr'], current_bar['dist_sma50'], current_bar['dist_sma200'], current_bar['body'], current_bar['range']]
    fvg_buy_ml = get_ml_pred("fvg_buy_v22.pkl", f)
    fvg_sell_ml = get_ml_pred("fvg_sell_v22.pkl", f)

    swing_h = current_bar['recent_high_50']
    swing_l = current_bar['recent_low_50']
    fibo_38_2 = swing_l + (swing_h - swing_l) * 0.382
    fibo_61_8 = swing_l + (swing_h - swing_l) * 0.618

    combined = None
    if current_bar['bull_fvg_10'] and (fvg_buy_ml == 1 or current_bar['rsi'] > 70):
        if 15.0 <= current_bar['rsi'] <= 68.0 and current_bar['atr'] >= 7.0:
            if current_bar['recent_low'] < fibo_38_2 or current_bar['rsi'] > 70:
                entry = current_bar['recent_low']
                sl = entry - (2.5 * current_bar['atr'])
                tp = entry + ((current_bar['recent_high'] - entry) * 1.618)
                combined = {"signal": "BUY", "entry": entry, "sl": sl, "tp": tp, "pattern": "FVG", "reason": "Group 13 FVG BUY"}

    if not combined and current_bar['bear_fvg_10'] and (fvg_sell_ml == 1 or current_bar['rsi'] < 30):
        if 10.0 <= current_bar['rsi'] <= 77.0 and current_bar['atr'] >= 10.0:
            if current_bar['recent_high'] > fibo_61_8 or current_bar['rsi'] < 30:
                entry = current_bar['recent_high']
                sl = entry + (2.5 * current_bar['atr'])
                tp = entry - ((entry - current_bar['recent_low']) * 1.618)
                combined = {"signal": "SELL", "entry": entry, "sl": sl, "tp": tp, "pattern": "FVG", "reason": "Group 13 FVG SELL"}

    # 2026-09-28: FollowDiv/ATR ที่ตกหล่น (มีใน config.S20_14_GROUP_COMBOS แต่ไม่เคย implement)
    if not combined: combined = _check_followdiv(df, current_bar)
    if not combined: combined = _check_atr_pattern(df, tf)
    if combined: matches.append(combined)

    result = _wrap_multi(matches, 13)
    return result if result else {"signal": "WAIT", "reason": "No Setup"}

# ------------- GROUP 19 -------------
def strategy_20_14_19(rates, tf="H1"):
    # Group 19: Order #34 Dedicated Filter
    # 2026-10-05 (Phase B): backtest (v38_standalone_group19.py บรรทัด 596-790) รวม FVG/Fibo/Div/
    # FollowDiv/ATR (BUY) และ Group26/FVG/Fibo/Div/FollowDiv/ATR (SELL) เป็น "/"-joined combined_pat
    # เดียวถ้า match พร้อมกันในบาร์เดียว ไม่ใช่เลือกตัวแรกที่เจอแบบที่ live เคย implement ไว้ผิด —
    # พอร์ตมาตรงเป๊ะ รวมถึงสูตร Deep Sniper fallback จริง (ไม่ใช่ 2.5×ATR ที่ implement ผิดไว้ก่อนหน้า
    # สำหรับ FVG เดี่ยวๆ) และ priority: Fibo ชนะทุกตัว (unconditional limit_price override ตาม
    # ต้นฉบับ) > Group26 (SELL เท่านั้น) > default Deep Sniper
    if rates is None or len(rates) < 55: return {"signal": "WAIT"}

    load_models()
    df = prepare_indicators(rates, tf)
    current_bar = df.iloc[-1]
    if pd.isna(current_bar['atr']): return {"signal": "WAIT"}

    f = [current_bar['rsi'], current_bar['atr'], current_bar['dist_sma50'], current_bar['dist_sma200'], current_bar['body'], current_bar['range']]
    fvg_buy_ml = get_ml_pred("fvg_buy_v22.pkl", f)
    fvg_sell_ml = get_ml_pred("fvg_sell_v22.pkl", f)

    swing_h = current_bar['recent_high_50']
    swing_l = current_bar['recent_low_50']
    fibo_38_2 = swing_l + (swing_h - swing_l) * 0.382
    fibo_61_8 = swing_l + (swing_h - swing_l) * 0.618
    swing_size = current_bar['recent_high'] - current_bar['recent_low']

    s11_res = strategy11.strategy_11(rates, tf)
    s9_res = strategy9.strategy_9(rates, tf)
    try:
        atr_res = strategy20_13_24.evaluate_bar(df, len(df) - 1, tf=tf)
    except Exception:
        atr_res = None

    matches = []

    # ---- BUY: FVG -> Fibo -> Div -> FollowDiv -> ATR (ลำดับตรงกับ backtest) ----
    patterns_buy = []
    if current_bar['bull_fvg_10'] and fvg_buy_ml == 1:
        if 15.0 <= current_bar['rsi'] <= 68.0 and current_bar['atr'] >= 7.0 and current_bar['recent_low'] < fibo_38_2:
            patterns_buy.append("FVG")
    fibo_buy_entry, fibo_buy_sl, fibo_buy_tp = 0.0, None, None
    if s11_res and s11_res.get('signal') == 'BUY':
        patterns_buy.append("Fibo")
        fibo_buy_entry = s11_res.get('entry') or 0.0
        fibo_buy_sl = s11_res.get('sl')
        fibo_buy_tp = s11_res.get('tp')
    if s9_res and s9_res.get('signal') == 'BUY' and 10.0 <= current_bar['rsi'] <= 34.0 and current_bar['atr'] >= 8.0:
        patterns_buy.append("Div")
    if bool(current_bar.get('recent_div_buy_active')) and bool(current_bar.get('engulfing_bull')):
        patterns_buy.append("FollowDiv")
    if atr_res and atr_res.get('signal') == 'BUY':
        patterns_buy.append("ATR")

    if patterns_buy:
        limit_price = current_bar['recent_low']
        sl = limit_price - (current_bar['atr'] * 1.5)
        tp = limit_price + (swing_size * 1.618)
        if "Fibo" in patterns_buy:
            limit_price = fibo_buy_entry
            sl = fibo_buy_sl if fibo_buy_sl else sl
            tp = fibo_buy_tp if fibo_buy_tp else tp
        combined_pat = "/".join(patterns_buy)
        matches.append({"signal": "BUY", "entry": limit_price, "sl": sl, "tp": tp,
                         "pattern": combined_pat, "reason": f"Group 19 {combined_pat} BUY"})

    # ---- SELL: Group26 -> FVG -> Fibo -> Div -> FollowDiv -> ATR (ลำดับตรงกับ backtest) ----
    patterns_sell = []
    group26_limit, group26_sl = None, None
    if tf == "H1" and not pd.isna(current_bar.get('sma12')) and current_bar['close'] < current_bar['sma12']:
        patterns_sell.append("Group26")
        group26_limit = current_bar['sma12']
        group26_sl = current_bar['recent_high']
    if current_bar['bear_fvg_10'] and (fvg_sell_ml == 1 or current_bar['rsi'] < 30):
        if 10.0 <= current_bar['rsi'] <= 77.0 and current_bar['atr'] >= 10.0 and (current_bar['recent_high'] > fibo_61_8 or current_bar['rsi'] < 30):
            patterns_sell.append("FVG")
    fibo_sell_entry, fibo_sell_sl, fibo_sell_tp = 0.0, None, None
    if s11_res and s11_res.get('signal') == 'SELL':
        patterns_sell.append("Fibo")
        fibo_sell_entry = s11_res.get('entry') or 0.0
        fibo_sell_sl = s11_res.get('sl')
        fibo_sell_tp = s11_res.get('tp')
    if s9_res and s9_res.get('signal') == 'SELL' and 66.0 <= current_bar['rsi'] <= 90.0 and current_bar['atr'] >= 8.0:
        patterns_sell.append("Div")
    if bool(current_bar.get('recent_div_sell_active')) and bool(current_bar.get('engulfing_bear')):
        patterns_sell.append("FollowDiv")
    if atr_res and atr_res.get('signal') == 'SELL':
        patterns_sell.append("ATR")

    if patterns_sell:
        limit_price = current_bar['recent_high']
        sl = limit_price + (current_bar['atr'] * 1.5)
        tp = limit_price - (swing_size * 1.618)
        if "Fibo" in patterns_sell:
            limit_price = fibo_sell_entry
            sl = fibo_sell_sl if fibo_sell_sl else sl
            tp = fibo_sell_tp if fibo_sell_tp else tp
        elif "Group26" in patterns_sell:
            limit_price = group26_limit
            sl = group26_sl
        combined_pat = "/".join(patterns_sell)
        matches.append({"signal": "SELL", "entry": limit_price, "sl": sl, "tp": tp,
                         "pattern": combined_pat, "reason": f"Group 19 {combined_pat} SELL"})

    result = _wrap_multi(matches, 19)
    return result if result else {"signal": "WAIT", "reason": "No Setup"}

# ------------- GROUP 21 -------------
def strategy_20_14_21(rates, tf="H1"):
    # Group 21: ATR Volatility Filter (top-10 จริง = FollowDiv / ATR / GapSweep, ไม่ใช่ Div)
    # 2026-09-23: เพิ่ม 3 pattern นี้ก่อน แล้วเหลือ Div เดิมไว้เป็น fallback (ของเดิมก่อนแก้)
    if rates is None or len(rates) < 55: return {"signal": "WAIT"}

    df = prepare_indicators(rates, tf)
    current_bar = df.iloc[-1]
    if pd.isna(current_bar['atr']): return {"signal": "WAIT"}

    matches = []
    combined = _check_followdiv(df, current_bar)
    if not combined: combined = _check_atr_pattern(df, tf)
    gs = _check_gapsweep(current_bar)
    if gs: matches.append(gs)

    if not combined:
        s9_res = strategy9.strategy_9(rates, tf)
        if s9_res and s9_res.get("signal") == "BUY":
            if 10.0 <= current_bar['rsi'] <= 34.0 and current_bar['atr'] >= 8.0:
                entry = current_bar['recent_low']
                sl = entry - (2.5 * current_bar['atr'])
                tp = entry + ((current_bar['recent_high'] - entry) * 1.618)
                combined = {"signal": "BUY", "entry": entry, "sl": sl, "tp": tp, "pattern": "Div", "reason": "Group 21 Div BUY"}
        if not combined and s9_res and s9_res.get("signal") == "SELL":
            if 66.0 <= current_bar['rsi'] <= 90.0 and current_bar['atr'] >= 8.0:
                entry = current_bar['recent_high']
                sl = entry + (2.5 * current_bar['atr'])
                tp = entry - ((entry - current_bar['recent_low']) * 1.618)
                combined = {"signal": "SELL", "entry": entry, "sl": sl, "tp": tp, "pattern": "Div", "reason": "Group 21 Div SELL"}

    # 2026-09-28: Fibo(D1) ที่ตกหล่น (มีใน config.S20_14_GROUP_COMBOS แต่ไม่เคย implement)
    if not combined: combined = _check_fibo(rates, tf, current_bar)
    if combined: matches.append(combined)

    result = _wrap_multi(matches, 21)
    return result if result else {"signal": "WAIT", "reason": "No Setup"}

# 2026-09-29: Group 22's "GapSweep" ไม่ใช่ weekly-open GapSweep แบบกลุ่มอื่นเลย — เช็คโค้ด
# v38_standalone_group22.py แล้วพบว่าเป็น "S1 Sweep-Zone" 3-stage state machine ต่างหาก (SELL
# ทางเดียว ไม่มี BUY เลยในต้นฉบับ — คอลัมน์ gap_sweep_buy/sell แบบ weekly-open มีอยู่ในโค้ดแต่ไม่เคย
# ถูก dispatch จริง เป็น dead column) ก่อนหน้านี้ live ใช้สูตร weekly-open ผิดทั้งหมด ต้อง state
# ข้ามรอบ scan เพราะเป็น pattern หลายแท่ง (เจอ pattern ก่อน → รอ BOS → รอ wick sweep กลับเข้าโซน)
_S1_SWEEP_STATE = {}  # tf -> {'state','zone_high','zone_low','support','tp','ll'}


def _check_gapsweep_group22(df, tf):
    """พอร์ตตรงจาก v38_standalone_group22.py 'S1 Sweep-Zone Wick Sweep' (Order 30)
    state 0=ยังไม่เจอ pattern, 1=เจอแล้วรอ BOS (close<support), 2=รอ wick sweep กลับเข้าโซน c1"""
    n = len(df)
    if n < 4:
        return None
    st = _S1_SWEEP_STATE.setdefault(tf, {'state': 0, 'zone_high': 0.0, 'zone_low': 0.0,
                                          'support': 0.0, 'tp': 0.0, 'll': 0.0})
    row = df.iloc[-1]
    prev_bar = df.iloc[-2]

    if st['state'] in (1, 2) and row['close'] > st['zone_high']:
        st['state'] = 0

    c1, c2, c3 = df.iloc[-3], df.iloc[-2], df.iloc[-1]
    c1_green = c1['close'] > c1['open']
    c2_red = c2['close'] < c2['open']
    c3_red = c3['close'] < c3['open']
    c2_cond = c2['close'] < c1['open'] and c2['low'] < c1['low']
    c3_engulf = c3['open'] >= c2['close'] and c3['close'] <= c2['open']

    if c1_green and c2_red and c3_red and c2_cond and c3_engulf:
        st['zone_high'] = c1['high']
        st['zone_low'] = c1['open']
        st['support'] = c2['low']
        st['state'] = 2 if c3['close'] < st['support'] else 1

        start = max(0, (n - 1) - 200)
        recent = df.iloc[start:n - 1]
        if not recent.empty:
            ll = float(recent['low'].min())
            st['ll'] = ll
            ll_pos_in_recent = int(recent['low'].values.argmin())
            ll_abs_pos = start + ll_pos_in_recent
            after_ll = df.iloc[ll_abs_pos:n - 1]
            tp_val = ll
            if not after_ll.empty:
                low_roll = after_ll['low'].rolling(3, center=True).min()
                swing_mask = (after_ll['low'] == low_roll) & low_roll.notna()
                swings = after_ll[swing_mask]
                if not swings.empty:
                    hl_pos_in_swings = int(swings['low'].values.argmin())
                    tp_val = float(swings['low'].iloc[hl_pos_in_swings])
                    pos_hl = after_ll.index.get_loc(swings.index[hl_pos_in_swings])
                    for k in range(pos_hl + 2, min(len(after_ll), pos_hl + 20)):
                        c1_high = after_ll.iloc[k - 2]['high']
                        c3_low = after_ll.iloc[k]['low']
                        if c1_high < c3_low:
                            tp_val = float(c3_low)
                            break
                else:
                    tp_val = float(after_ll['low'].min())
            st['tp'] = tp_val
        else:
            st['tp'] = float(row['low'])
        return None

    if st['state'] == 1:
        if row['close'] < st['support']:
            st['state'] = 2
    elif st['state'] == 2:
        if row['high'] > prev_bar['high'] and row['close'] < prev_bar['high']:
            if st['zone_low'] <= row['high'] <= st['zone_high']:
                sl = st['zone_high']
                tp = st['tp'] if st['tp'] > 0 else st['ll']
                if sl <= row['close']:
                    sl = row['close'] + (row['atr'] * 2)
                st['state'] = 0
                return {"signal": "SELL", "entry": row['close'], "sl": sl, "tp": tp,
                        "pattern": "GapSweep", "reason": "Group 22 S1 Sweep-Zone SELL"}
    return None


# ------------- GROUP 22 -------------
def strategy_20_14_22(rates, tf="H1"):
    # Group 22: GapSweep M15 Dynamic Engine (top-10 จริง = GapSweep / FollowDiv / ATR / Div)
    # 2026-09-28: เดิมมีแค่ GapSweep เพิ่ม FollowDiv/ATR/Div ที่ตกหล่น
    # 2026-09-29: แก้ GapSweep เป็นสูตร S1 Sweep-Zone ที่ถูกต้อง (ของเดิมใช้ weekly-open ผิด)
    if rates is None or len(rates) < 55: return {"signal": "WAIT"}

    df = prepare_indicators(rates, tf)
    current_bar = df.iloc[-1]
    if pd.isna(current_bar['atr']): return {"signal": "WAIT"}

    matches = []
    gs = _check_gapsweep_group22(df, tf)
    if gs: matches.append(gs)

    combined = _check_followdiv(df, current_bar)
    if not combined: combined = _check_atr_pattern(df, tf)
    if not combined: combined = _check_div(rates, current_bar, tf)
    if combined: matches.append(combined)

    result = _wrap_multi(matches, 22)
    return result if result else {"signal": "WAIT", "reason": "No Setup"}

# ------------- GROUP 23 -------------
# H1 Liquidity Sweep -> Respect Low (MTF BUY on LTF)
_H1_CACHE_G23 = {
    "df": None,
    "last_time": None,
    "liq_lows": [],
}

def _refresh_h1_cache_g23():
    """Fetch H1 bars from MT5 and pre-compute liq sweep lows. Cached per H1 bar."""
    try:
        import MetaTrader5 as mt5
        import pandas as pd
        from datetime import timedelta
        import config
        symbol = config.SYMBOL
        rates_h1 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 0, 2000)
        if rates_h1 is None or len(rates_h1) == 0:
            return
        df_h1 = pd.DataFrame(rates_h1)
        df_h1['time_dt'] = pd.to_datetime(df_h1['time'], unit='s') + timedelta(hours=1)
        df_h1['is_red'] = df_h1['close'] < df_h1['open']
        df_h1['low_roll'] = df_h1['low'].rolling(3, center=True).min()
        liq_lows = []
        swing_mask = df_h1['low'] == df_h1['low_roll']
        for loc, (idx, row) in enumerate(df_h1.iterrows()):
            if not swing_mask.iloc[loc]: continue
            if loc == 0: continue
            prev = df_h1.iloc[loc - 1]
            if row['low'] < prev['low'] and prev['is_red']:
                liq_lows.append({'low': row['low'], 'time_dt': row['time_dt']})
        _H1_CACHE_G23['df'] = df_h1
        _H1_CACHE_G23['last_time'] = df_h1['time'].iloc[-1]
        _H1_CACHE_G23['liq_lows'] = liq_lows
    except Exception:
        pass

def strategy_20_14_23(rates, tf="H1"):
    """S20.14 Group 23: H1 Liquidity Sweep -> LTF Respect Low MTF BUY (Market Execution)"""
    if rates is None or len(rates) < 55: return {"signal": "WAIT"}
    if tf not in ["M30", "M15", "M5", "M1"]: return {"signal": "WAIT"}

    from datetime import timedelta
    import pandas as pd
    import config
    try:
        import MetaTrader5 as mt5
        latest_h1 = mt5.copy_rates_from_pos(config.SYMBOL, mt5.TIMEFRAME_H1, 0, 1)
        if latest_h1 is not None and len(latest_h1) > 0:
            if _H1_CACHE_G23['last_time'] != latest_h1[0]['time']: _refresh_h1_cache_g23()
    except Exception:
        if _H1_CACHE_G23['df'] is None: _refresh_h1_cache_g23()

    if not _H1_CACHE_G23['liq_lows']: return {"signal": "WAIT", "reason": "No H1 liq lows cached"}
    df_h1, h1_liq_lows = _H1_CACHE_G23['df'], _H1_CACHE_G23['liq_lows']

    df = prepare_indicators(rates, tf)
    if len(df) < 5: return {"signal": "WAIT"}
    bar_m1, bar_m2, bar_m3 = df.iloc[-1], df.iloc[-2], df.iloc[-3]
    if pd.isna(bar_m1.get('atr')) or bar_m1['atr'] <= 0: return {"signal": "WAIT"}

    is_ltf_swing_low = (bar_m2['low'] <= bar_m1['low']) and (bar_m2['low'] <= bar_m3['low'])
    if not is_ltf_swing_low: return {"signal": "WAIT"}

    current_time, entry_price, atr = bar_m1['time_dt'], bar_m2['low'], bar_m1['atr']
    recent_liq = [l for l in h1_liq_lows if l['time_dt'] < current_time and l['time_dt'] >= current_time - timedelta(days=5)]
    if not recent_liq: return {"signal": "WAIT", "reason": "No recent H1 liq low"}
    
    h1_liq = recent_liq[-1]
    if entry_price <= h1_liq['low']: return {"signal": "WAIT"}

    sl_price = round(entry_price - (atr * 1.5), 2)
    tp_price = round(entry_price + (atr * 2), 2)
    
    if df_h1 is not None:
        idx_end = df_h1['time_dt'].searchsorted(current_time)
        idx_start = max(0, idx_end - 150)
        recent_h1 = df_h1.iloc[idx_start:idx_end].copy()
        if len(recent_h1) >= 5:
            recent_h1['high_roll'] = recent_h1['high'].rolling(3, center=True).max()
            highs = recent_h1[recent_h1['high'] == recent_h1['high_roll']]
            respect_highs = []
            for h_idx in highs.index:
                loc = recent_h1.index.get_loc(h_idx)
                if loc > 0:
                    h2 = recent_h1.iloc[loc]
                    prev_highs = recent_h1.iloc[:loc]
                    prev_highs_swing = prev_highs[prev_highs['high'] == prev_highs.get('high_roll', prev_highs['high'])]
                    if prev_highs_swing.empty: continue
                    h1_pk = prev_highs_swing.iloc[-1]
                    if h2['high'] < h1_pk['high']:
                        loc1 = recent_h1.index.get_loc(h1_pk.name)
                        if loc1 > 0 and h1_pk['close'] < h1_pk['open'] and h1_pk['high'] > recent_h1.iloc[loc1 - 1]['high']:
                            respect_highs.append(h2['high'])
            valid_tps = [h for h in respect_highs if h > entry_price + atr]
            if valid_tps: tp_price = round(valid_tps[-1], 2)
            elif recent_h1['high'].max() > entry_price + atr: tp_price = round(recent_h1['high'].max(), 2)

    return {
        "signal": "BUY",
        "entry": round(entry_price, 2),
        "sl": sl_price,
        "tp": tp_price,
        "pattern": "Naiya_MTF",
        "order_mode": "market",
        "reason": f"Group 23 H1 LiqSweep->LTF Respect Low | H1_liq={h1_liq['low']:.2f} | ATR={atr:.2f}",
    }

# ------------- GROUP 24 -------------
def strategy_20_14_24(rates, tf="H1"):
    # Group 24: FollowDiv Trend Capture (top-10 จริง = FVG, FollowDiv)
    res = strategy_20_14_19(rates, tf)  # Same as 19 based on target_tfs (ให้ FVG/Group26 ก่อน)
    # 2026-10-05: เพิ่ม 'MULTI' เข้าเงื่อนไข short-circuit — group19 คืน MULTI ได้แล้วตั้งแต่ Phase B
    # (combined_pat) ถ้าไม่เช็คตรงนี้ผลจาก group19 จะถูก followdiv fallback ด้านล่างทับทิ้งไปเฉยๆ
    if res and res.get('signal') in ('BUY', 'SELL', 'MULTI'):
        return res
    if rates is None or len(rates) < 55:
        return res
    df = prepare_indicators(rates, tf)
    current_bar = df.iloc[-1]
    if pd.isna(current_bar['atr']):
        return res
    fd = _check_followdiv(df, current_bar)
    return fd if fd else res


def strategy_20_14_1(rates, tf="H1"):
    # Group 1: Primary Baseline Setup (top-10 จริง = FollowDiv / ATR / GapSweep / Div / Fibo)
    # 2026-09-23: แทน placeholder เดิม (คืน WAIT เสมอ) ด้วย logic จริงที่พอร์ตจาก backtest
    # 2026-09-28: เพิ่ม Div(M15)/Fibo(D1) ที่ตกหล่น (มีใน config.S20_14_GROUP_COMBOS แต่ไม่เคย implement)
    if rates is None or len(rates) < 55: return {"signal": "WAIT"}
    df = prepare_indicators(rates, tf)
    current_bar = df.iloc[-1]
    if pd.isna(current_bar['atr']): return {"signal": "WAIT"}

    matches = []
    combined = _check_followdiv(df, current_bar)
    if not combined: combined = _check_atr_pattern(df, tf)
    gs = _check_gapsweep(current_bar)
    if gs: matches.append(gs)
    if not combined: combined = _check_div(rates, current_bar, tf)
    if not combined: combined = _check_fibo(rates, tf, current_bar)
    if combined: matches.append(combined)
    result = _wrap_multi(matches, 1)
    return result if result else {"signal": "WAIT", "reason": "No Setup"}

def strategy_20_14_14(rates, tf="H1"):
    # Group 14: GapSweep Momentum Filter (top-10 จริง = ATR / FVG / FollowDiv / GapSweep)
    if rates is None or len(rates) < 55: return {"signal": "WAIT"}
    df = prepare_indicators(rates, tf)
    current_bar = df.iloc[-1]
    if pd.isna(current_bar['atr']): return {"signal": "WAIT"}

    # GapSweep (independent — ยิงพร้อม pattern อื่นได้)
    matches = []
    if getattr(current_bar, 'gap_sweep_buy', False):
        entry = current_bar['weekly_open']
        sl    = current_bar['low']
        tp    = entry + (entry - sl) * 1.618
        matches.append({"signal": "BUY", "entry": entry, "sl": sl, "tp": tp, "pattern": "GapSweep", "reason": "Group 14 GapSweep BUY"})
    if getattr(current_bar, 'gap_sweep_sell', False):
        entry = current_bar['weekly_open']
        sl    = current_bar['high']
        tp    = entry - (sl - entry) * 1.618
        matches.append({"signal": "SELL", "entry": entry, "sl": sl, "tp": tp, "pattern": "GapSweep", "reason": "Group 14 GapSweep SELL"})

    # FVG (สูตรเดียวกับ Group 5/13/19)
    swing_h = current_bar['recent_high_50']
    swing_l = current_bar['recent_low_50']
    fibo_38_2 = swing_l + (swing_h - swing_l) * 0.382
    fibo_61_8 = swing_l + (swing_h - swing_l) * 0.618
    load_models()
    f = [current_bar['rsi'], current_bar['atr'], current_bar['dist_sma50'], current_bar['dist_sma200'], current_bar['body'], current_bar['range']]
    combined = None
    if current_bar['bull_fvg_10'] and get_ml_pred("fvg_buy_v22.pkl", f) == 1:
        if 15.0 <= current_bar['rsi'] <= 68.0 and current_bar['atr'] >= 7.0 and current_bar['recent_low'] < fibo_38_2:
            entry = current_bar['recent_low']
            sl = entry - (2.5 * current_bar['atr'])
            tp = entry + ((current_bar['recent_high'] - entry) * 1.618)
            combined = {"signal": "BUY", "entry": entry, "sl": sl, "tp": tp, "pattern": "FVG", "reason": "Group 14 FVG BUY"}
    if not combined and current_bar['bear_fvg_10'] and get_ml_pred("fvg_sell_v22.pkl", f) == 1:
        if 10.0 <= current_bar['rsi'] <= 77.0 and current_bar['atr'] >= 10.0 and current_bar['recent_high'] > fibo_61_8:
            entry = current_bar['recent_high']
            sl = entry + (2.5 * current_bar['atr'])
            tp = entry - ((entry - current_bar['recent_low']) * 1.618)
            combined = {"signal": "SELL", "entry": entry, "sl": sl, "tp": tp, "pattern": "FVG", "reason": "Group 14 FVG SELL"}

    if not combined: combined = _check_followdiv(df, current_bar)
    if not combined: combined = _check_atr_pattern(df, tf)
    # 2026-09-28: Div(M15) ที่ตกหล่น (มีใน config.S20_14_GROUP_COMBOS แต่ไม่เคย implement จริง)
    if not combined: combined = _check_div(rates, current_bar, tf)
    if combined: matches.append(combined)

    result = _wrap_multi(matches, 14)
    return result if result else {"signal": "WAIT"}

def strategy_20_14_16(rates, tf="H1"):
    # Group 16: Heavy Volume Scalper (top-10 จริง = Naiya Doji)
    if rates is None or len(rates) < 55: return {"signal": "WAIT"}
    load_models()
    df = prepare_indicators(rates, tf)
    current_bar = df.iloc[-1]
    if pd.isna(current_bar['atr']): return {"signal": "WAIT"}

    # 2026-09-23: Naiya Doji ตัวจริง เช็คก่อน แล้วเหลือ Naiya (ML) เดิมเป็น fallback
    matches = []
    nd = _detect_naiya_doji(df)
    if nd: matches.append(nd)

    f = [current_bar['rsi'], current_bar['atr'], current_bar['dist_sma50'], current_bar['dist_sma200'], current_bar['body'], current_bar['range']]
    naiya_buy_ml = get_ml_pred("naiya_buy_v22.pkl", f)
    naiya_sell_ml = get_ml_pred("naiya_sell_v22.pkl", f)

    naiya_res = None
    if naiya_buy_ml == 1 and current_bar['rsi'] < 30:
        entry = current_bar['close']
        sl = current_bar['low'] - (current_bar['atr'] * 0.5)
        tp = current_bar['close'] + (current_bar['atr'] * 2)
        naiya_res = {"signal": "BUY", "entry": entry, "sl": sl, "tp": tp, "pattern": "Naiya", "reason": "Naiya_BUY"}
    elif naiya_sell_ml == 1 and current_bar['rsi'] > 70:
        entry = current_bar['close']
        sl = current_bar['high'] + (current_bar['atr'] * 0.5)
        tp = current_bar['close'] - (current_bar['atr'] * 2)
        naiya_res = {"signal": "SELL", "entry": entry, "sl": sl, "tp": tp, "pattern": "Naiya", "reason": "Naiya_SELL"}
    if naiya_res: matches.append(naiya_res)

    # 2026-09-28: FollowDiv(M15) ที่ตกหล่น (มีใน config.S20_14_GROUP_COMBOS แต่ไม่เคย implement)
    res = _check_followdiv(df, current_bar)
    if res: matches.append(res)

    result = _wrap_multi(matches, 16)
    return result if result else {"signal": "WAIT"}

def strategy_20_14_18(rates, tf="H1"):
    # Group 18: Naiya
    return strategy_20_14_16(rates, tf) # Shares same core logic as 16 for now


# ------------- GROUP 7 -------------
def strategy_20_14_7(rates, tf="H1"):
    # Group 7: Institutional Order Flow (top-10 จริง = Fibo / Div / FollowDiv เหมือน Group 3)
    # 2026-09-23: เดิมมีแค่ Fibo branch เดียว ขยายให้ครบตาม top-10 โดยใช้ logic เดียวกับ Group 3
    return strategy_20_14_3(rates, tf)

# ------------- GROUP 8 -------------
def strategy_20_14_8(rates, tf="H1"):
    # Group 8: High-RR Trend Follower (top-10 จริง = Naiya Doji)
    if rates is None or len(rates) < 55: return {"signal": "WAIT"}
    load_models()
    df = prepare_indicators(rates, tf)
    current_bar = df.iloc[-1]
    if pd.isna(current_bar['atr']): return {"signal": "WAIT"}

    # 2026-09-23: Naiya Doji ตัวจริง เช็คก่อน แล้วเหลือ GapSweep/Naiya/Doji เดิมเป็น fallback
    matches = []
    nd = _detect_naiya_doji(df)
    if nd: matches.append(nd)

    gs = None
    if getattr(current_bar, 'gap_sweep_buy', False):
        entry = current_bar['weekly_open']
        sl = current_bar['low']
        tp = entry + (entry - sl) * 1.618
        gs = {"signal": "BUY", "entry": entry, "sl": sl, "tp": tp, "pattern": "GapSweep", "reason": "Group 8 GapSweep BUY"}
    elif getattr(current_bar, 'gap_sweep_sell', False):
        entry = current_bar['weekly_open']
        sl = current_bar['high']
        tp = entry - (sl - entry) * 1.618
        gs = {"signal": "SELL", "entry": entry, "sl": sl, "tp": tp, "pattern": "GapSweep", "reason": "Group 8 GapSweep SELL"}
    if gs: matches.append(gs)

    naiya_res = None
    if current_bar['naiya_doji_buy_base']:
        entry = current_bar['recent_low']
        sl = entry - (2.5 * current_bar['atr'])
        tp = entry + ((current_bar['recent_high'] - entry) * 1.618)
        naiya_res = {"signal": "BUY", "entry": entry, "sl": sl, "tp": tp, "pattern": "Naiya", "reason": "Group 8 Naiya BUY"}
    elif current_bar['naiya_doji_sell_base']:
        entry = current_bar['recent_high']
        sl = entry + (2.5 * current_bar['atr'])
        tp = entry - ((entry - current_bar['recent_low']) * 1.618)
        naiya_res = {"signal": "SELL", "entry": entry, "sl": sl, "tp": tp, "pattern": "Naiya", "reason": "Group 8 Naiya SELL"}
    if naiya_res: matches.append(naiya_res)

    combined = None
    if current_bar['range'] > 0 and current_bar['body'] < 0.4 * current_bar['range'] and (current_bar['close'] - current_bar['low']) > 0.5 * current_bar['range'] and current_bar['low'] <= current_bar['recent_low'] + current_bar['atr']*0.5 and 0 <= current_bar['rsi'] <= 2:
        entry = current_bar['recent_low']
        sl = entry - (2.5 * current_bar['atr'])
        tp = entry + ((current_bar['recent_high'] - entry) * 1.618)
        combined = {"signal": "BUY", "entry": entry, "sl": sl, "tp": tp, "pattern": "Doji", "reason": "Group 8 Doji BUY"}
    elif current_bar['range'] > 0 and current_bar['body'] < 0.4 * current_bar['range'] and (current_bar['high'] - current_bar['close']) > 0.5 * current_bar['range'] and current_bar['high'] >= current_bar['recent_high'] - current_bar['atr']*0.5 and 74 <= current_bar['rsi'] <= 78 and current_bar['close'] < current_bar['sma50'] and current_bar['close'] < current_bar['sma200']:
        entry = current_bar['recent_high']
        sl = entry + (2.5 * current_bar['atr'])
        tp = entry - ((entry - current_bar['recent_low']) * 1.618)
        combined = {"signal": "SELL", "entry": entry, "sl": sl, "tp": tp, "pattern": "Doji", "reason": "Group 8 Doji SELL"}

    # 2026-09-28: FollowDiv ที่ตกหล่น (มีใน config.S20_14_GROUP_COMBOS แต่ไม่เคย implement)
    if not combined: combined = _check_followdiv(df, current_bar)
    if combined: matches.append(combined)

    result = _wrap_multi(matches, 8)
    return result if result else {"signal": "WAIT", "reason": "No Setup"}

# ------------- GROUP 10 -------------
def strategy_20_14_10(rates, tf="M15"):
    return strategy_20_14_7(rates, tf)

# ------------- GROUP 11 -------------
def strategy_20_14_11(rates, tf="M15"):
    # Group 11: Fibo Multi-Layer Engine (top-10 จริง = Fibo / Div / FollowDiv เหมือน Group 3)
    if rates is None or len(rates) < 55: return {"signal": "WAIT"}
    df = prepare_indicators(rates, tf)
    current_bar = df.iloc[-1]

    s11_res = strategy11.strategy_11(rates, tf)
    if s11_res and s11_res.get("signal") == "BUY":
        return {"signal": "BUY", "entry": s11_res.get("entry", current_bar['close']), "sl": s11_res.get("sl"), "tp": s11_res.get("tp"), "pattern": "Fibo", "reason": "Group 11 Fibo BUY"}
    if s11_res and s11_res.get("signal") == "SELL":
        return {"signal": "SELL", "entry": s11_res.get("entry", current_bar['close']), "sl": s11_res.get("sl"), "tp": s11_res.get("tp"), "pattern": "Fibo", "reason": "Group 11 Fibo SELL"}

    # 2026-09-23: เพิ่ม Div/FollowDiv ตาม top-10 จริง (เดิมมีแค่ Fibo/Doji)
    if not pd.isna(current_bar['atr']):
        s9_res = strategy9.strategy_9(rates, tf)
        if s9_res and s9_res.get("signal") == "BUY" and 10.0 <= current_bar['rsi'] <= 34.0 and current_bar['atr'] >= 8.0:
            entry = current_bar['recent_low']
            sl = entry - (2.5 * current_bar['atr'])
            tp = entry + ((current_bar['recent_high'] - entry) * 1.618)
            return {"signal": "BUY", "entry": entry, "sl": sl, "tp": tp, "pattern": "Div", "reason": "Group 11 Div BUY"}
        if s9_res and s9_res.get("signal") == "SELL" and 66.0 <= current_bar['rsi'] <= 90.0 and current_bar['atr'] >= 8.0:
            entry = current_bar['recent_high']
            sl = entry + (2.5 * current_bar['atr'])
            tp = entry - ((entry - current_bar['recent_low']) * 1.618)
            return {"signal": "SELL", "entry": entry, "sl": sl, "tp": tp, "pattern": "Div", "reason": "Group 11 Div SELL"}
        res = _check_followdiv(df, current_bar)
        if res: return res
        res = _check_atr_pattern(df, tf)
        if res: return res

    if current_bar['range'] > 0 and current_bar['body'] < 0.4 * current_bar['range'] and (current_bar['close'] - current_bar['low']) > 0.5 * current_bar['range'] and current_bar['low'] <= current_bar['recent_low'] + current_bar['atr']*0.5 and 0 <= current_bar['rsi'] <= 2:
        entry = current_bar['recent_low']
        sl = entry - (2.5 * current_bar['atr'])
        tp = entry + ((current_bar['recent_high'] - entry) * 1.618)
        return {"signal": "BUY", "entry": entry, "sl": sl, "tp": tp, "pattern": "Doji", "reason": "Group 11 Doji BUY"}
    if current_bar['range'] > 0 and current_bar['body'] < 0.4 * current_bar['range'] and (current_bar['high'] - current_bar['close']) > 0.5 * current_bar['range'] and current_bar['high'] >= current_bar['recent_high'] - current_bar['atr']*0.5 and 74 <= current_bar['rsi'] <= 78 and current_bar['close'] < current_bar['sma50'] and current_bar['close'] < current_bar['sma200']:
        entry = current_bar['recent_high']
        sl = entry + (2.5 * current_bar['atr'])
        tp = entry - ((entry - current_bar['recent_low']) * 1.618)
        return {"signal": "SELL", "entry": entry, "sl": sl, "tp": tp, "pattern": "Doji", "reason": "Group 11 Doji SELL"}

    return {"signal": "WAIT", "reason": "No Setup"}

# ------------- GROUP 15 -------------
def strategy_20_14_15(rates, tf="H1"):
    return strategy_20_14_7(rates, tf)

# ------------- GROUP 17 -------------
def strategy_20_14_17(rates, tf="D1"):
    # Group 17: Low Frequency Precision Engine (top-10 จริง = Naiya Doji / Naiya / Naiya FVG(D1))
    # 2026-09-28: เพิ่ม Naiya(ML) ที่ตกหล่น + แก้ pattern tag "FVG_D1"->"Naiya FVG" ให้ตรงกับ
    # config.S20_14_GROUP_COMBOS (เดิมชื่อไม่ตรงเลย ทำให้ scanner.py filter ทิ้งทุกครั้ง กลายเป็น dead code)
    if rates is None or len(rates) < 55: return {"signal": "WAIT"}
    load_models()
    df = prepare_indicators(rates, tf)
    current_bar = df.iloc[-1]
    if pd.isna(current_bar['atr']): return {"signal": "WAIT"}

    matches = []
    nd = _detect_naiya_doji(df)
    if nd: matches.append(nd)

    res = _check_naiya_std(df, current_bar)
    if res: matches.append(res)

    combined = None
    if current_bar['bull_fvg_10']:
        entry = current_bar['recent_low']
        sl = entry - (2.5 * current_bar['atr'])
        tp = entry + ((current_bar['recent_high'] - entry) * 1.618)
        combined = {"signal": "BUY", "entry": entry, "sl": sl, "tp": tp, "pattern": "Naiya FVG", "reason": "Group 17 Naiya FVG BUY"}
    elif current_bar['bear_fvg_10']:
        entry = current_bar['recent_high']
        sl = entry + (2.5 * current_bar['atr'])
        tp = entry - ((entry - current_bar['recent_low']) * 1.618)
        combined = {"signal": "SELL", "entry": entry, "sl": sl, "tp": tp, "pattern": "Naiya FVG", "reason": "Group 17 Naiya FVG SELL"}
    if combined: matches.append(combined)

    result = _wrap_multi(matches, 17)
    return result if result else {"signal": "WAIT", "reason": "No Setup"}
