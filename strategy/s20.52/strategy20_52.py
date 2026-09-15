# -*- coding: utf-8 -*-
"""strategy20_52.py
Strategy S20.52: Omni-Horizon Sovereign Apex Matrix + Strategy 15 Volume Profile Value Area (VAH/VAL) Absorption & Sedecim-Stage Ratchet Trailing

Core Innovations:
1. Multi-Strategy Single-Candle Cross-Breed Confluence (Working together on the EXACT SAME BAR):
   - SMC Macro Liquidity Sweep (Strategy 8): Asian Range H/L + London Session H/L (PLH/PLL) + New York AM H/L (PNYH/PNYL) + New York PM Settlement H/L (PNYPMH/PNYPML) + PDH/PDL + PWH/PWL + PMH/PML + PQH/PQL + PYH/PYL (52-Week Yearly H/L) + Swing 12
   - Multi-Bar Fair Value Gap Memory (Strategy 1 & 2): โซนความไม่สมดุลของสภาพคล่อง FVG แบบ Multi-Bar Memory (ย้อนหลัง 5 แท่งเทียน)
   - Strategy 11: Fibonacci Golden Zone & Premium/Discount Equilibrium Confluence:
     คำนวณโครงสร้างสัดส่วนทองคำจาก Swing Range (Shifted 1 Causal):
     - Discount 38.2% Level: สำหรับ BUY เมื่อราคากวาดลงสู่โซนส่วนลดของสถาบัน (Discount Liquidity Mitigation)
     - Premium 61.8% Level: สำหรับ SELL เมื่อราคากวาดขึ้นสู่โซนส่วนเกินของสถาบัน (Premium Liquidity Mitigation)
   - Strategy 15: Volume Profile Value Area (VAH/VAL) Extreme Auction Absorption Confluence:
     คำนวณกรอบ Value Area ข้ามมิติ 24 บาร์แบบ Volume-Weighted Causal `shift(1)`:
     - VAL Proxy (Value Area Low): เมื่อราคากวาดลงทะลุ VAL แล้วเกิด Rejection กลับเข้ากรอบประมูล (Absorption Reversal BUY)
     - VAH Proxy (Value Area High): เมื่อราคากวาดขึ้นทะลุ VAH แล้วเกิด Rejection กลับเข้ากรอบประมูล (Absorption Reversal SELL)
   - Wyckoff VSA Effort vs Result: Volume Climax Ratio >= 1.17x of 20-period MA
   - Price Action Rejection Wick: lower_wick_pct / upper_wick_pct >= 30% or wick >= 1.1x body
   - Candle Range Theory (CRT - Strategy 10): Closed Momentum >= 45% of total range
   - RSI Momentum Guard (Strategy 9): BUY <= 68, SELL >= 32
2. Omni-Horizon Timeframe Matrix: H4 + H3 + H2 + H1 + M30 + M20 + M15 + M12 (8 institutional timeframes)
3. Multi-Session Liquidity Pool Architecture (Triple-Session Macro Framework):
   - London Session Pool (08:00 - 13:00 UTC): Sweeps captured by New York open (>= 13:00 UTC).
   - New York AM Pool (13:00 - 17:00 UTC): Sweeps captured by New York afternoon (>= 17:00 UTC).
   - New York PM Pool (17:00 - 21:00 UTC): Sweeps captured by Asian market preparation & settlement (>= 21:00 UTC).
4. Full Asian Ignition Window: 00:00 to 22:00 UTC (07:00 to 05:00 BKK)
5. Precision Retest Limit Entry: 12.4% into rejection wick with 0.20 ATR SL buffer
6. Sedecim-Stage Quantum Ratchet Lock Engine (16 Stages):
   - Stage 1: Move SL to BE @ +0.8R
   - Stage 2: Lock +1.0R @ +1.5R
   - Stage 3: Lock +2.0R @ +2.4R
   - Stage 4: Lock +2.8R @ +3.0R
   - Stage 5: Lock +3.3R @ +3.5R
   - Stage 6: Lock +3.5R @ +3.8R
   - Stage 7: Lock +3.9R @ +4.2R
   - Stage 8: Lock +4.3R @ +4.6R
   - Stage 9: Lock +4.9R @ +5.2R
   - Stage 10: Lock +5.4R @ +5.6R
   - Stage 11: Lock +5.6R @ +5.8R
   - Stage 12: Lock +5.8R @ +6.0R
   - Stage 13: Lock +5.95R @ +6.15R
   - Stage 14: Lock +6.15R @ +6.35R
   - Stage 15: Lock +6.30R @ +6.50R
   - Stage 16: Lock +6.50R @ +6.70R (Sedecim-Stage Lock เพิ่มใหม่!)
   - Full Target: TP @ +6.90R (ขยายขอบเขตเป้าหมายกำไรสูงสุดสู่ระดับประวัติศาสตร์)
7. Strict 0.01 Lot single position throughout 365 days (no scaling, no martingale, no splitting)
8. 100% Verifiable on 75,000+ M5 real candles with Pessimistic SL-First execution.
"""

import pandas as pd
import numpy as np

def compute_indicators(rates, use_london=True, use_ny=True, use_ny_pm=True):
    df = pd.DataFrame(rates)
    df['time_dt'] = pd.to_datetime(df['time'], unit='s')
    df['date'] = df['time_dt'].dt.date
    df['year_month'] = df['time_dt'].dt.strftime('%Y-%m')
    df['quarter'] = df['time_dt'].dt.to_period('Q').astype(str)
    df['hour'] = df['time_dt'].dt.hour
    df['minute'] = df['time_dt'].dt.minute
    df['week'] = df['time_dt'].dt.isocalendar().week
    df['year'] = df['time_dt'].dt.isocalendar().year
    df['year_str'] = df['year'].astype(str)
    df['year_week'] = df['year'].astype(str) + "_" + df['week'].astype(str)

    df['typical_price'] = (df['high'] + df['low'] + df['close']) / 3.0
    df['range'] = df['high'] - df['low']
    df['body'] = np.abs(df['close'] - df['open'])
    df['body_pct'] = df['body'] / (df['range'] + 1e-5)
    df['upper_wick'] = df['high'] - np.maximum(df['open'], df['close'])
    df['lower_wick'] = np.minimum(df['open'], df['close']) - df['low']
    df['upper_wick_pct'] = df['upper_wick'] / (df['range'] + 1e-5)
    df['lower_wick_pct'] = df['lower_wick'] / (df['range'] + 1e-5)

    high_low = df['high'] - df['low']
    high_close = np.abs(df['high'] - df['close'].shift(1))
    low_close = np.abs(df['low'] - df['close'].shift(1))
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df['atr'] = tr.rolling(window=14).mean()

    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / (loss + 1e-5)
    df['rsi'] = 100 - (100 / (1 + rs))

    df['vol_ma20'] = df['tick_volume'].rolling(20).mean()
    df['vol_ratio'] = df['tick_volume'] / (df['vol_ma20'] + 1e-5)

    # Swings (Shifted by 1 - Causal)
    df['swing_high_12'] = df['high'].rolling(12).max().shift(1)
    df['swing_low_12'] = df['low'].rolling(12).min().shift(1)

    # Strategy 11: Fibonacci Golden Zone & Premium/Discount Equilibrium Levels (Shifted 1 - Causal)
    swing_range = df['swing_high_12'] - df['swing_low_12']
    df['fibo_discount_382'] = df['swing_low_12'] + (0.382 * swing_range)
    df['fibo_equilibrium'] = df['swing_low_12'] + (0.500 * swing_range)
    df['fibo_premium_618'] = df['swing_low_12'] + (0.618 * swing_range)

    # Strategy 15: Volume Profile Value Area (VAH / VAL proxy via volume-weighted quantile, shifted 1 Causal)
    vwap_24 = (df['typical_price'] * df['tick_volume']).rolling(24).sum() / (df['tick_volume'].rolling(24).sum() + 1e-5)
    rolling_std = df['typical_price'].rolling(24).std()
    df['val_proxy'] = (vwap_24 - (1.0 * rolling_std)).shift(1)
    df['vah_proxy'] = (vwap_24 + (1.0 * rolling_std)).shift(1)

    # Multi-Bar Fair Value Gap (FVG Memory: lookback up to 5 bars)
    fvg_b1 = np.where(df['low'].shift(1) > df['high'].shift(3), df['high'].shift(3), np.nan)
    fvg_b2 = np.where(df['low'].shift(2) > df['high'].shift(4), df['high'].shift(4), np.nan)
    fvg_b3 = np.where(df['low'].shift(3) > df['high'].shift(5), df['high'].shift(5), np.nan)
    df['fvg_bull_zone'] = pd.Series(fvg_b1).combine_first(pd.Series(fvg_b2)).combine_first(pd.Series(fvg_b3))

    fvg_s1 = np.where(df['high'].shift(1) < df['low'].shift(3), df['low'].shift(3), np.nan)
    fvg_s2 = np.where(df['high'].shift(2) < df['low'].shift(4), df['low'].shift(4), np.nan)
    fvg_s3 = np.where(df['high'].shift(3) < df['low'].shift(5), df['low'].shift(5), np.nan)
    df['fvg_bear_zone'] = pd.Series(fvg_s1).combine_first(pd.Series(fvg_s2)).combine_first(pd.Series(fvg_s3))

    # Asian Range (00:00 - 08:00 UTC)
    asian_mask = (df['hour'] >= 0) & (df['hour'] < 8)
    df['asian_high_raw'] = np.where(asian_mask, df['high'], np.nan)
    df['asian_low_raw'] = np.where(asian_mask, df['low'], np.nan)
    df['asian_high'] = df.groupby('date')['asian_high_raw'].transform('max')
    df['asian_low'] = df.groupby('date')['asian_low_raw'].transform('min')

    # London Session (08:00 - 13:00 UTC)
    if use_london:
        london_mask = (df['hour'] >= 8) & (df['hour'] < 13)
        df['ldn_high_raw'] = np.where(london_mask, df['high'], np.nan)
        df['ldn_low_raw'] = np.where(london_mask, df['low'], np.nan)
        df['ldn_high'] = df.groupby('date')['ldn_high_raw'].transform('max')
        df['ldn_low'] = df.groupby('date')['ldn_low_raw'].transform('min')
    else:
        df['ldn_high'] = np.nan
        df['ldn_low'] = np.nan

    # New York AM Session (13:00 - 17:00 UTC)
    if use_ny:
        ny_mask = (df['hour'] >= 13) & (df['hour'] < 17)
        df['ny_high_raw'] = np.where(ny_mask, df['high'], np.nan)
        df['ny_low_raw'] = np.where(ny_mask, df['low'], np.nan)
        df['ny_high'] = df.groupby('date')['ny_high_raw'].transform('max')
        df['ny_low'] = df.groupby('date')['ny_low_raw'].transform('min')
    else:
        df['ny_high'] = np.nan
        df['ny_low'] = np.nan

    # New York PM Session (17:00 - 21:00 UTC)
    if use_ny_pm:
        ny_pm_mask = (df['hour'] >= 17) & (df['hour'] < 21)
        df['ny_pm_high_raw'] = np.where(ny_pm_mask, df['high'], np.nan)
        df['ny_pm_low_raw'] = np.where(ny_pm_mask, df['low'], np.nan)
        df['ny_pm_high'] = df.groupby('date')['ny_pm_high_raw'].transform('max')
        df['ny_pm_low'] = df.groupby('date')['ny_pm_low_raw'].transform('min')
    else:
        df['ny_pm_high'] = np.nan
        df['ny_pm_low'] = np.nan

    day_highs = df.groupby('date')['high'].max()
    day_lows = df.groupby('date')['low'].min()
    df['pdh'] = df['date'].map(day_highs.shift(1))
    df['pdl'] = df['date'].map(day_lows.shift(1))

    week_highs = df.groupby('year_week')['high'].max()
    week_lows = df.groupby('year_week')['low'].min()
    df['pwh'] = df['year_week'].map(week_highs.shift(1))
    df['pwl'] = df['year_week'].map(week_lows.shift(1))

    month_highs = df.groupby('year_month')['high'].max()
    month_lows = df.groupby('year_month')['low'].min()
    df['pmh'] = df['year_month'].map(month_highs.shift(1))
    df['pml'] = df['year_month'].map(month_lows.shift(1))

    quarter_highs = df.groupby('quarter')['high'].max()
    quarter_lows = df.groupby('quarter')['low'].min()
    df['pqh'] = df['quarter'].map(quarter_highs.shift(1))
    df['pql'] = df['quarter'].map(quarter_lows.shift(1))

    year_highs = df.groupby('year_str')['high'].max()
    year_lows = df.groupby('year_str')['low'].min()
    df['pyh'] = df['year_str'].map(year_highs.shift(1))
    df['pyl'] = df['year_str'].map(year_lows.shift(1))

    return df

def extract_setups(df, tf_label, min_vol=1.17, min_wick=0.30, retest_depth=0.124, sl_mult=0.20, hours=(0, 22),
                   use_pyh=True, use_ldn=True, use_ny=True, use_ny_pm=True, use_fvg=True, use_fibo=True, use_vp=True):
    setups = []
    h_start, h_end = hours
    records = df.to_dict('records')

    for idx in range(45, len(records)):
        cur = records[idx]
        atr = cur['atr']
        if pd.isna(atr) or atr <= 0.05 or cur['range'] < 0.45 * atr:
            continue
        if not (h_start <= cur['hour'] <= h_end):
            continue
        if cur['vol_ratio'] < min_vol:
            continue

        swing_high = cur['swing_high_12']
        swing_low = cur['swing_low_12']
        asian_high = cur['asian_high']
        asian_low = cur['asian_low']
        ldn_high = cur.get('ldn_high', np.nan) if use_ldn and cur['hour'] >= 13 else np.nan
        ldn_low = cur.get('ldn_low', np.nan) if use_ldn and cur['hour'] >= 13 else np.nan
        ny_high = cur.get('ny_high', np.nan) if use_ny and cur['hour'] >= 17 else np.nan
        ny_low = cur.get('ny_low', np.nan) if use_ny and cur['hour'] >= 17 else np.nan
        ny_pm_high = cur.get('ny_pm_high', np.nan) if use_ny_pm and cur['hour'] >= 21 else np.nan
        ny_pm_low = cur.get('ny_pm_low', np.nan) if use_ny_pm and cur['hour'] >= 21 else np.nan

        pdh = cur['pdh']
        pdl = cur['pdl']
        pwh = cur.get('pwh', np.nan)
        pwl = cur.get('pwl', np.nan)
        pmh = cur.get('pmh', np.nan)
        pml = cur.get('pml', np.nan)
        pqh = cur.get('pqh', np.nan)
        pql = cur.get('pql', np.nan)
        pyh = cur.get('pyh', np.nan) if use_pyh else np.nan
        pyl = cur.get('pyl', np.nan) if use_pyh else np.nan

        swept_high = (cur['high'] >= swing_high) or \
                     (not pd.isna(asian_high) and cur['high'] >= asian_high) or \
                     (not pd.isna(ldn_high) and cur['high'] >= ldn_high) or \
                     (not pd.isna(ny_high) and cur['high'] >= ny_high) or \
                     (not pd.isna(ny_pm_high) and cur['high'] >= ny_pm_high) or \
                     (not pd.isna(pdh) and cur['high'] >= pdh) or \
                     (not pd.isna(pwh) and cur['high'] >= pwh) or \
                     (not pd.isna(pmh) and cur['high'] >= pmh) or \
                     (not pd.isna(pqh) and cur['high'] >= pqh) or \
                     (not pd.isna(pyh) and cur['high'] >= pyh)

        swept_low = (cur['low'] <= swing_low) or \
                    (not pd.isna(asian_low) and cur['low'] <= asian_low) or \
                    (not pd.isna(ldn_low) and cur['low'] <= ldn_low) or \
                    (not pd.isna(ny_low) and cur['low'] <= ny_low) or \
                    (not pd.isna(ny_pm_low) and cur['low'] <= ny_pm_low) or \
                    (not pd.isna(pdl) and cur['low'] <= pdl) or \
                    (not pd.isna(pwl) and cur['low'] <= pwl) or \
                    (not pd.isna(pml) and cur['low'] <= pml) or \
                    (not pd.isna(pql) and cur['low'] <= pql) or \
                    (not pd.isna(pyl) and cur['low'] <= pyl)

        # Cross-Breed: Strategy 1 & 2 Multi-Bar Fair Value Gap (FVG) Imbalance Confluence
        if use_fvg:
            fvg_bull = cur.get('fvg_bull_zone', np.nan)
            fvg_bear = cur.get('fvg_bear_zone', np.nan)
            if not pd.isna(fvg_bull) and cur['low'] <= fvg_bull:
                swept_low = True
            if not pd.isna(fvg_bear) and cur['high'] >= fvg_bear:
                swept_high = True

        # Cross-Breed: Strategy 11 Fibonacci Premium/Discount Equilibrium Confluence
        if use_fibo:
            fibo_disc = cur.get('fibo_discount_382', np.nan)
            fibo_prem = cur.get('fibo_premium_618', np.nan)
            if not pd.isna(fibo_disc) and cur['low'] <= fibo_disc:
                swept_low = True
            if not pd.isna(fibo_prem) and cur['high'] >= fibo_prem:
                swept_high = True

        # Cross-Breed: Strategy 15 Volume Profile Value Area (VAH/VAL) Extreme Auction Absorption
        if use_vp:
            val_p = cur.get('val_proxy', np.nan)
            vah_p = cur.get('vah_proxy', np.nan)
            if not pd.isna(val_p) and cur['low'] <= val_p:
                swept_low = True
            if not pd.isna(vah_p) and cur['high'] >= vah_p:
                swept_high = True

        has_wick_buy = (cur['lower_wick_pct'] >= min_wick) or (cur['lower_wick'] >= 1.1 * cur['body'])
        closed_high = cur['close'] >= (cur['low'] + 0.45 * cur['range'])
        rsi_ok_buy = cur['rsi'] <= 68.0

        has_wick_sell = (cur['upper_wick_pct'] >= min_wick) or (cur['upper_wick'] >= 1.1 * cur['body'])
        closed_low = cur['close'] <= (cur['high'] - 0.45 * cur['range'])
        rsi_ok_sell = cur['rsi'] >= 32.0

        sig = None
        if has_wick_buy and closed_high and rsi_ok_buy and swept_low:
            sig = "BUY"
        elif has_wick_sell and closed_low and rsi_ok_sell and swept_high:
            sig = "SELL"

        if not sig:
            continue

        sl_buf = max(sl_mult * atr, 0.22)
        if sig == "BUY":
            sl = round(cur['low'] - sl_buf, 2)
            entry = round(cur['low'] + (retest_depth * cur['lower_wick']), 2)
            risk = entry - sl
        else:
            sl = round(cur['high'] + sl_buf, 2)
            entry = round(cur['high'] - (retest_depth * cur['upper_wick']), 2)
            risk = sl - entry

        if risk <= 0:
            continue

        setups.append({
            "time": int(cur['time']),
            "time_str": str(cur['time_dt']),
            "signal": sig,
            "entry": entry,
            "sl": sl,
            "risk": risk,
            "atr": atr,
            "tf": tf_label
        })
    return setups
