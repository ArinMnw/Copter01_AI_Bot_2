import pandas as pd
import numpy as np
import config
from mt5_utils import now_bkk

def get_fuel_multiplier(current_tf, target_tf):
    tf_minutes = {
        "M1": 1, "M5": 5, "M15": 15, "M30": 30,
        "H1": 60, "H4": 240, "H12": 720, "D1": 1440
    }
    cur_mins = tf_minutes.get(current_tf, 60)
    tgt_mins = tf_minutes.get(target_tf, 720) # Default H12
    return np.sqrt(tgt_mins / cur_mins)

def compute_indicators_df(rates):
    df = pd.DataFrame(rates)
    df['time_dt'] = pd.to_datetime(df['time'], unit='s')
    df['hour'] = df['time_dt'].dt.hour
    
    # Calculate ATR
    high_low = df['high'] - df['low']
    high_close = np.abs(df['high'] - df['close'].shift())
    low_close = np.abs(df['low'] - df['close'].shift())
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df['atr'] = tr.rolling(window=14).mean()
    df['atr_pct'] = (df['atr'] / df['close']) * 100.0
    
    # Candle Anatomy
    df['range'] = df['high'] - df['low']
    df['body'] = np.abs(df['close'] - df['open'])
    df['body_pct'] = df['body'] / (df['range'] + 0.0001)
    
    # Wicks Anatomy (for v21/v22)
    df['upper_wick'] = df['high'] - np.maximum(df['open'], df['close'])
    df['lower_wick'] = np.minimum(df['open'], df['close']) - df['low']
    df['upper_wick_pct'] = df['upper_wick'] / (df['range'] + 0.0001)
    df['lower_wick_pct'] = df['lower_wick'] / (df['range'] + 0.0001)

    # Volume Ratio
    df['vol_ma20'] = df['tick_volume'].rolling(20).mean()
    df['vol_ratio'] = df['tick_volume'] / (df['vol_ma20'] + 1.0)
    
    # Calculate EMA 50 and 200
    df['ema_50'] = df['close'].ewm(span=50, adjust=False).mean()
    df['ema_200'] = df['close'].ewm(span=200, adjust=False).mean()
    df['dist_ema50'] = df['close'] - df['ema_50']
    df['dist_ema200'] = df['close'] - df['ema_200']
    
    # Calculate RSI 14 and RSI 7
    delta = df['close'].diff()
    gain14 = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss14 = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs14 = gain14 / loss14
    df['rsi'] = 100 - (100 / (1 + rs14))
    
    gain7 = (delta.where(delta > 0, 0)).rolling(window=7).mean()
    loss7 = (-delta.where(delta < 0, 0)).rolling(window=7).mean()
    rs7 = gain7 / loss7
    df['rsi_7'] = 100 - (100 / (1 + rs7))

    # Z-Score
    sma_20 = df['close'].rolling(20).mean()
    std_20 = df['close'].rolling(20).std()
    df['z_score'] = (df['close'] - sma_20) / std_20
    
    # ADX and DI Diff
    plus_dm = df['high'].diff()
    minus_dm = df['low'].shift() - df['low']
    plus_dm = np.where((plus_dm > minus_dm) & (plus_dm > 0), plus_dm, 0.0)
    minus_dm = np.where((minus_dm > plus_dm) & (minus_dm > 0), minus_dm, 0.0)
    tr14 = tr.rolling(14).sum()
    plus_di14 = 100 * (pd.Series(plus_dm).rolling(14).sum() / tr14)
    minus_di14 = 100 * (pd.Series(minus_dm).rolling(14).sum() / tr14)
    dx = 100 * (np.abs(plus_di14 - minus_di14) / (plus_di14 + minus_di14))
    df['adx'] = dx.rolling(14).mean()
    df['di_diff'] = plus_di14 - minus_di14
    return df

def evaluate_bar(df, idx, tf="H1"):
    if idx < 20 or idx >= len(df):
        return {"signal": "WAIT", "reason": "Not enough data"}

    current_bar = df.iloc[idx]
    prev_bar = df.iloc[idx - 1]
    
    if pd.isna(current_bar['atr']) or pd.isna(current_bar['rsi']) or pd.isna(current_bar['ema_200']):
        return {"signal": "WAIT", "reason": "Indicators not ready"}

    lookback_bars = df.iloc[idx - 14 : idx - 3]
    local_low = lookback_bars['low'].min()
    local_high = lookback_bars['high'].max()
    active_mode = getattr(config, "S20_13_ACTIVE_MODE", 2.6)
    target_tf_buy = getattr(config, "S20_13_TARGET_TF_BUY", "H12")
    target_tf_sell = getattr(config, "S20_13_TARGET_TF_SELL", "D1")
    current_time = current_bar['time_dt']
    hour = current_time.hour
    is_ny_pre_open = (hour == 12 or hour == 13)
    is_sydney_open = (hour == 23 or hour == 0)
    is_tokyo_buy = (hour == 2)
    is_late_ny_buy = (hour == 19)
    is_midnight_buy = (hour == 17)
    is_london_open = (hour == 8)
    is_london_fake = (hour == 9)
    
    # Base Filter 20.13.3 (Engulfing Range ATR)
    cur_range = current_bar['high'] - current_bar['low']
    is_strong_range = cur_range >= (0.8 * current_bar['atr'])

    # -------------------------------------------------------------
    # BUY PA CONFIRMATION (CHoCH / Engulfing)
    # -------------------------------------------------------------
    recent_3 = df.iloc[idx - 3 : idx]
    sweep_buy = recent_3['low'].min() < local_low
    engulf_buy = current_bar['close'] > prev_bar['high']
    
    instant_sweep_buy = current_bar['low'] < local_low and current_bar['close'] > prev_bar['high']
    
    if (sweep_buy and engulf_buy) or instant_sweep_buy:
        if not is_strong_range:
            return {"signal": "WAIT", "reason": "Engulfing Range < 0.8 ATR"}
        if is_ny_pre_open:
            return {"signal": "WAIT", "reason": "NY Pre-Open Trap"}
        if is_sydney_open:
            return {"signal": "WAIT", "reason": "Sydney Open Trap"}
        if is_tokyo_buy:
            return {"signal": "WAIT", "reason": "Tokyo Open Trap (BUY)"}
        if is_late_ny_buy:
            return {"signal": "WAIT", "reason": "Late NY Trap (BUY)"}
        if is_midnight_buy:
            return {"signal": "WAIT", "reason": "Midnight Trap (BUY)"}
        if is_london_open:
            return {"signal": "WAIT", "reason": "London Open Trap"}
        if is_london_fake:
            return {"signal": "WAIT", "reason": "London Fakeout Trap"}
            
        if current_bar['rsi'] < 35:
            return {"signal": "WAIT", "reason": f"RSI too low ({current_bar['rsi']:.1f})"}
            
        entry_price = current_bar['close']
        sweep_bottom = min(recent_3['low'].min(), current_bar['low'])
        if current_bar['z_score'] > 0.0 and current_bar['adx'] > 30.0:
            return {"signal": "WAIT", "reason": f"BUY Trend/Z Block (Z={current_bar['z_score']:.2f}, ADX={current_bar['adx']:.1f})"}
            
        # v18 Deep Feature BUY Filters
        if current_bar['adx'] > 52.0:
            return {"signal": "WAIT", "reason": f"BUY Trend Exhaustion Block (ADX={current_bar['adx']:.1f} > 52.0)"}
        if current_bar['atr_pct'] <= 0.41 and current_bar['adx'] < 50.0:
            return {"signal": "WAIT", "reason": f"BUY Low Volatility Drift Block (ATR%={current_bar['atr_pct']:.2f}%, ADX={current_bar['adx']:.1f})"}

        # v20 Evolution BUY Filters
        if current_bar['vol_ratio'] < 0.55:
            return {"signal": "WAIT", "reason": f"BUY Extreme Low Volume Breakout Block (VolRatio={current_bar['vol_ratio']:.2f})"}

        # v21 Evolution BUY Filters
        if current_bar['rsi'] > 40.0 and current_bar['dist_ema50'] < -20.0:
            return {"signal": "WAIT", "reason": f"BUY Mid-RSI Falling Knife Below EMA50 Block (RSI={current_bar['rsi']:.1f}, DistEMA50={current_bar['dist_ema50']:.1f})"}

        # v22 Evolution BUY Filters (Zero-Loss 100% WR Target)
        if current_bar['rsi'] < 48.0 and current_bar['di_diff'] > 0.0:
            return {"signal": "WAIT", "reason": f"BUY Bull Trap Exhaustion Divergence Block (RSI={current_bar['rsi']:.1f}, DI_Diff={current_bar['di_diff']:.1f})"}

        sl = sweep_bottom - config.SL_BUFFER(current_bar['atr'])
        fuel_multiplier = get_fuel_multiplier(tf, target_tf_buy)
        fuel = current_bar['atr'] * active_mode * fuel_multiplier
        tp = sweep_bottom + fuel
        return {
            "signal": "BUY",
            "entry": entry_price,
            "sl": sl,
            "tp": tp,
            "pattern": "S20.13.22 PA Confirmed BUY",
            "reason": f"Sweep {local_low:.2f} | No Trend | TP {tp:.2f}"
        }
        
    # -------------------------------------------------------------
    # SELL PA CONFIRMATION (CHoCH / Engulfing)
    # -------------------------------------------------------------
    sweep_sell = recent_3['high'].max() > local_high
    engulf_sell = current_bar['close'] < prev_bar['low']
    
    instant_sweep_sell = current_bar['high'] > local_high and current_bar['close'] < prev_bar['low']
    
    if (sweep_sell and engulf_sell) or instant_sweep_sell:
        if not is_strong_range:
            return {"signal": "WAIT", "reason": "Engulfing Range < 0.8 ATR"}
        if is_ny_pre_open:
            return {"signal": "WAIT", "reason": "NY Pre-Open Trap"}
        if is_sydney_open:
            return {"signal": "WAIT", "reason": "Sydney Open Trap"}
        if is_london_open:
            return {"signal": "WAIT", "reason": "London Open Trap"}
        if is_london_fake:
            return {"signal": "WAIT", "reason": "London Fakeout Trap"}
            
        if current_bar['rsi'] > 60:
            return {"signal": "WAIT", "reason": f"RSI too high ({current_bar['rsi']:.1f})"}
            
        entry_price = current_bar['close']
        sweep_top = max(recent_3['high'].max(), current_bar['high'])
        if (current_bar['z_score'] < 0.0 and current_bar['adx'] > 50.0) or (current_bar['close'] - current_bar['ema_50'] > 100.0):
            return {"signal": "WAIT", "reason": f"SELL Trend/Z Block (Z={current_bar['z_score']:.2f}, ADX={current_bar['adx']:.1f})"}

        # v18 Deep Feature SELL Filters
        if current_bar['rsi_7'] > 50.5 and 0.35 <= current_bar['body_pct'] <= 0.615:
            return {"signal": "WAIT", "reason": f"SELL Momentum Conflict Block (RSI7={current_bar['rsi_7']:.1f}, Body%={current_bar['body_pct']:.2f})"}
        if current_bar['rsi_7'] > 50.5 and 0.35 <= current_bar['body_pct'] <= 0.65 and current_bar['di_diff'] < 4.0:
            return {"signal": "WAIT", "reason": f"SELL Weak Directional Block (RSI7={current_bar['rsi_7']:.1f}, DI_Diff={current_bar['di_diff']:.1f})"}
        if current_bar['vol_ratio'] < 0.88 and current_bar['di_diff'] > 1.0:
            return {"signal": "WAIT", "reason": f"SELL Low Volume Trap Block (VolRatio={current_bar['vol_ratio']:.2f}, DI_Diff={current_bar['di_diff']:.1f})"}

        # v19 Evolution SELL Filters
        if current_bar['body_pct'] < 0.145:
            return {"signal": "WAIT", "reason": f"SELL Extreme Doji Block (Body%={current_bar['body_pct']:.2f})"}
        if current_bar['rsi'] < 37.0 and current_bar['z_score'] > -1.80:
            return {"signal": "WAIT", "reason": f"SELL Oversold Trap Block (RSI={current_bar['rsi']:.1f}, Z={current_bar['z_score']:.2f})"}
        if current_bar['adx'] < 17.5 and current_bar['vol_ratio'] < 0.90:
            return {"signal": "WAIT", "reason": f"SELL Low Volume Chop Block (ADX={current_bar['adx']:.1f}, VolRatio={current_bar['vol_ratio']:.2f})"}
        if current_bar['rsi'] > 58.5 and current_bar['rsi_7'] < 41.5:
            return {"signal": "WAIT", "reason": f"SELL RSI Divergence Trap Block (RSI={current_bar['rsi']:.1f}, RSI7={current_bar['rsi_7']:.1f})"}

        # v20 Evolution SELL Filters
        if current_bar['rsi_7'] < 41.5 and current_bar['di_diff'] > 0.5:
            return {"signal": "WAIT", "reason": f"SELL Short-Term Oversold Bullish DI Block (RSI7={current_bar['rsi_7']:.1f}, DI_Diff={current_bar['di_diff']:.1f})"}
        if current_bar['adx'] < 20.2 and (current_bar['close'] - current_bar['ema_50']) > -12.0:
            return {"signal": "WAIT", "reason": f"SELL Low ADX Above EMA50 Block (ADX={current_bar['adx']:.1f}, DistEMA50={(current_bar['close'] - current_bar['ema_50']):.1f})"}
        if current_bar['vol_ratio'] < 1.90 and current_bar['rsi'] < 39.0:
            return {"signal": "WAIT", "reason": f"SELL Low Volume Oversold Trap Block (VolRatio={current_bar['vol_ratio']:.2f}, RSI={current_bar['rsi']:.1f})"}
        if current_bar['z_score'] > 0.20 and current_bar['atr_pct'] < 0.31:
            return {"signal": "WAIT", "reason": f"SELL Low Volatility Upper BB Block (Z={current_bar['z_score']:.2f}, ATR%={current_bar['atr_pct']:.2f}%)"}
        if current_bar['rsi'] > 53.0 and current_bar['rsi_7'] < 37.0:
            return {"signal": "WAIT", "reason": f"SELL RSI Momentum Divergence Block (RSI={current_bar['rsi']:.1f}, RSI7={current_bar['rsi_7']:.1f})"}

        # v21 Evolution SELL Filters
        if current_bar['dist_ema50'] > 20.0 and current_bar['upper_wick_pct'] > 0.15:
            return {"signal": "WAIT", "reason": f"SELL Upper Wick Exhaustion Above EMA50 Block (DistEMA50={current_bar['dist_ema50']:.1f}, uWick%={current_bar['upper_wick_pct']:.2f})"}
        if hour == 10:
            return {"signal": "WAIT", "reason": f"SELL Tokyo Mid-Session Liquidity Trap Block (Hour=10)"}
        if current_bar['adx'] > 20.0 and current_bar['vol_ratio'] > 2.50:
            return {"signal": "WAIT", "reason": f"SELL Volumetric Climax Absorption Block (ADX={current_bar['adx']:.1f}, VolRatio={current_bar['vol_ratio']:.2f})"}
        if current_bar['adx'] < 25.0 and current_bar['lower_wick_pct'] > 0.40:
            return {"signal": "WAIT", "reason": f"SELL Weak Trend High Rejection Tail Block (ADX={current_bar['adx']:.1f}, lWick%={current_bar['lower_wick_pct']:.2f})"}
        if current_bar['di_diff'] < 0.0 and current_bar['dist_ema50'] > 20.0:
            return {"signal": "WAIT", "reason": f"SELL Bearish DI Pullback Above EMA50 Block (DI_Diff={current_bar['di_diff']:.1f}, DistEMA50={current_bar['dist_ema50']:.1f})"}

        # v22 Evolution SELL Filters (Zero-Loss 100% WR Target)
        if current_bar['dist_ema50'] < 10.0 and current_bar['dist_ema200'] > 50.0:
            return {"signal": "WAIT", "reason": f"SELL EMA50 Bull Market Support Trap Block (DistEMA50={current_bar['dist_ema50']:.1f}, DistEMA200={current_bar['dist_ema200']:.1f})"}
        if current_bar['rsi'] > 55.0 and current_bar['di_diff'] < -3.0:
            return {"signal": "WAIT", "reason": f"SELL Bullish RSI vs Bearish DI Conflict Block (RSI={current_bar['rsi']:.1f}, DI_Diff={current_bar['di_diff']:.1f})"}
        if current_bar['rsi'] > 58.0 and current_bar['di_diff'] > 10.0:
            return {"signal": "WAIT", "reason": f"SELL Strong Bullish Momentum & Direction Block (RSI={current_bar['rsi']:.1f}, DI_Diff={current_bar['di_diff']:.1f})"}
        if current_bar['rsi'] < 50.0 and current_bar['dist_ema200'] > 80.0:
            return {"signal": "WAIT", "reason": f"SELL Deep Pullback in Extended Super-Trend Block (RSI={current_bar['rsi']:.1f}, DistEMA200={current_bar['dist_ema200']:.1f})"}
        if current_bar['z_score'] < -1.50 and current_bar['upper_wick_pct'] > 0.30:
            return {"signal": "WAIT", "reason": f"SELL Lower BB Whipsaw Rejection Block (Z={current_bar['z_score']:.2f}, uWick%={current_bar['upper_wick_pct']:.2f})"}

        sl = sweep_top + config.SL_BUFFER(current_bar['atr'])
        fuel_multiplier = get_fuel_multiplier(tf, target_tf_sell)
        fuel = current_bar['atr'] * active_mode * fuel_multiplier
        tp = sweep_top - fuel
        return {
            "signal": "SELL",
            "entry": entry_price,
            "sl": sl,
            "tp": tp,
            "pattern": "S20.13.22 PA Confirmed SELL",
            "reason": f"Sweep {local_high:.2f} | No Trend | TP {tp:.2f}"
        }

    return {"signal": "WAIT", "reason": "No Setup"}

def strategy_20_13_22(rates, tf="H1"):
    if rates is None or len(rates) < 20:
        return {"signal": "WAIT", "reason": "Not enough data"}
    df = compute_indicators_df(rates)
    return evaluate_bar(df, len(df) - 1, tf=tf)
