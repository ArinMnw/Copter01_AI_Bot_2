import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import argparse
import sys
import os
import pickle
import warnings
warnings.filterwarnings('ignore')
from datetime import timedelta

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 's20.13')))

import config
import strategy1
import strategy11
import strategy9
import strategy20_13_24

def backtest_patterns_to_csv(days, compound):
    mt5.initialize(r'D:\Project\Copter01_AI_Bot_2\profiles\demo\demo-iux-2101182459\mt5\terminal64.exe')
    symbol = "XAUUSD.iux"
    info = mt5.symbol_info(symbol)
    if info is None:
        symbol = "XAUUSD"
        info = mt5.symbol_info(symbol)
        
    spread_points = info.spread if info else 15
    point = info.point if info else 0.01
    spread_price = spread_points * point
    print(f"Using Symbol: {symbol} | Spread: {spread_points} points ({spread_price})")

    tf_map = {
        "M15": mt5.TIMEFRAME_M15, "M30": mt5.TIMEFRAME_M30,
        "H1": mt5.TIMEFRAME_H1, "H12": mt5.TIMEFRAME_H12, "D1": mt5.TIMEFRAME_D1
    }
    
    target_tfs = {
        "FVG": ["M30", "H1", "H12", "D1"],
        "ATR": ["H1", "D1"],
        "Fibo": ["M15", "M30", "H1"],
        "Doji": ["M30", "H1"],
        "Div": ["H1"],
        "MA12": ["H1"],
        "Naiya": ["M30", "H1", "H12", "D1"],
        "GapSweep": ["M30", "H1"]
    }
    
    all_tfs = set()
    for tfs in target_tfs.values():
        all_tfs.update(tfs)
        
    trades_list = []
    print(f"Generating CSV backtest data for {days} days (Walk-Forward Simulator)...")
    
    model_dir = os.path.dirname(__file__)
    with open(os.path.join(model_dir, 'fvg_buy_v22.pkl'), 'rb') as f:
        fvg_buy_model = pickle.load(f)
    with open(os.path.join(model_dir, 'fvg_sell_v22.pkl'), 'rb') as f:
        fvg_sell_model = pickle.load(f)
    
    for tf_str in all_tfs:
        tf = tf_map.get(tf_str)
        if not tf: continue
        
        if tf_str.startswith('M'):
            mins = int(tf_str[1:])
        elif tf_str.startswith('H'):
            mins = int(tf_str[1:]) * 60
        elif tf_str.startswith('D'):
            mins = 24 * 60
        else:
            mins = 60
            
        limit = ((days * 24 * 60) // mins) + 150
        if limit > 500000: limit = 500000
            
        rates = mt5.copy_rates_from_pos(symbol, tf, 0, limit)
        if rates is None or len(rates) == 0: continue
        
        df = strategy20_13_24.compute_indicators_df(rates)
        df['time_dt'] = pd.to_datetime(df['time'], unit='s') + timedelta(hours=1)
        
        # Additional indicators needed for other logic

        
        df['sma12'] = df['close'].rolling(window=12).mean()
        df['sma20'] = df['close'].rolling(window=20).mean()
        df['sma50'] = df['close'].rolling(window=50).mean()
        df['sma200'] = df['close'].rolling(window=200).mean()
        
        df['recent_low'] = df['low'].rolling(window=20).min().shift(1)
        df['recent_high'] = df['high'].rolling(window=20).max().shift(1)
        df['rsi_low'] = df['rsi'].rolling(window=20).min().shift(1)
        df['rsi_high'] = df['rsi'].rolling(window=20).max().shift(1)
        
        # 50-bar lookback for Fibo
        df['recent_low_50'] = df['low'].rolling(window=50).min().shift(1)
        df['recent_high_50'] = df['high'].rolling(window=50).max().shift(1)
        
        df['body'] = np.abs(df['close'] - df['open'])
        df['range'] = df['high'] - df['low']
        
        df['bull_fvg_raw'] = df['high'].shift(2) < df['low']
        df['bear_fvg_raw'] = df['low'].shift(2) > df['high']
        # 10-bar unmitigated FVG lookback
        df['bull_fvg_10'] = df['bull_fvg_raw'].rolling(window=10).max() > 0
        df['bear_fvg_10'] = df['bear_fvg_raw'].rolling(window=10).max() > 0
        
        df['dist_sma50'] = (df['close'] - df['sma50']) / df['sma50'] * 100
        df['dist_sma200'] = (df['close'] - df['sma200']) / df['sma200'] * 100
        
        valid_idx = df[['rsi', 'atr', 'dist_sma50', 'dist_sma200']].dropna().index
        if len(valid_idx) > 0:
            df.loc[valid_idx, 'fvg_buy_ml'] = fvg_buy_model.predict(df.loc[valid_idx, ['rsi', 'atr', 'dist_sma50', 'dist_sma200']].values)
            df.loc[valid_idx, 'fvg_sell_ml'] = fvg_sell_model.predict(df.loc[valid_idx, ['rsi', 'atr', 'dist_sma50', 'dist_sma200']].values)
        else:
            df['fvg_buy_ml'] = 0
            df['fvg_sell_ml'] = 0
            
        # Naiya Doji Vectorized Setup
        df['is_green'] = df['close'] > df['open']
        df['is_red'] = df['close'] < df['open']
        df['is_green_doji'] = df['is_green'] & (df['body'] <= df['range'] * 0.35)
        df['is_red_doji'] = df['is_red'] & (df['body'] <= df['range'] * 0.35)
        
        # A Naiya Buy Base forms when current bar is Green (engulfing), prev is Green Doji (low), prev-prev is Red
        df['naiya_buy_base'] = df['is_green'] & df['is_green_doji'].shift(1) & df['is_red'].shift(2) & \
                               (df['low'].shift(1) < df['low']) & (df['low'].shift(1) < df['low'].shift(2)) & \
                               (df['close'] > df['high'].shift(1))
                               
        df['naiya_sell_base'] = df['is_red'] & df['is_red_doji'].shift(1) & df['is_green'].shift(2) & \
                                (df['high'].shift(1) > df['high']) & (df['high'].shift(1) > df['high'].shift(2)) & \
                                (df['close'] < df['low'].shift(1))
        
        # Gap Sweep Logic (Weekly Open - Unmitigated First Touch Only)
        df['time_diff'] = df['time_dt'].diff()
        weekly_open_list = []
        weekly_open_price = None
        for time_diff, open_pr in zip(df['time_diff'], df['open']):
            if pd.notna(time_diff) and time_diff.total_seconds() > 24 * 3600:
                weekly_open_price = open_pr
            weekly_open_list.append(weekly_open_price)
            
        df['weekly_open'] = weekly_open_list
        df['is_green'] = df['close'] > df['open']
        df['is_red'] = df['close'] < df['open']
        
        # GapSweep BUY: Price drops below weekly open, sweeps previous low, closes above weekly open, and is a green candle
        df['gap_sweep_buy'] = (df['weekly_open'].notna()) & (df['open'] > df['weekly_open']) & (df['low'] <= df['weekly_open']) & (df['close'] > df['weekly_open']) & (df['low'] < df['low'].shift(1)) & df['is_green']
        
        # GapSweep SELL: Price rises above weekly open, sweeps previous high, closes below weekly open, and is a red candle
        df['gap_sweep_sell'] = (df['weekly_open'].notna()) & (df['open'] < df['weekly_open']) & (df['high'] >= df['weekly_open']) & (df['close'] < df['weekly_open']) & (df['high'] > df['high'].shift(1)) & df['is_red']
        
        # FollowDiv Logic: Engulfing (Div tracking done inside loop)
        
        df['body_bottom'] = df[['open', 'close']].min(axis=1)
        df['body_top'] = df[['open', 'close']].max(axis=1)
        df['is_green'] = df['close'] > df['open']
        df['is_red'] = df['close'] < df['open']
        
        df['engulfing_bull'] = df['is_green'] & df['is_red'].shift(1) & (df['body_bottom'] <= df['body_bottom'].shift(1)) & (df['body_top'] >= df['body_top'].shift(1)) & (df['close'] > df['open'].shift(1))
        df['engulfing_bear'] = df['is_red'] & df['is_green'].shift(1) & (df['body_bottom'] <= df['body_bottom'].shift(1)) & (df['body_top'] >= df['body_top'].shift(1)) & (df['close'] < df['open'].shift(1))
        

        
        valid = df.dropna(subset=['atr', 'rsi', 'recent_low_50']).copy()
        print(f"[{tf_str}] df len: {len(df)}, valid len: {len(valid)}")
        
        list_of_dicts = valid.to_dict('records')
        strategy11.reset_state(tf_str)
        
        open_trades = []
        pending_orders = []
        pending_naiya_buy = []
        pending_naiya_sell = []
        pending_gapsweep_buy = []
        pending_gapsweep_sell = []
        valid['engulfing_bear'] = valid['engulfing_bear'].fillna(False)
        
        # Calculate instantaneous divergence (rolling 50 bars)
        valid['recent_low_50'] = valid['low'].rolling(50).min().shift(1)
        valid['recent_rsi_low_50'] = valid['rsi'].rolling(50).min().shift(1)
        valid['recent_high_50'] = valid['high'].rolling(50).max().shift(1)
        valid['recent_rsi_high_50'] = valid['rsi'].rolling(50).max().shift(1)
        
        # FollowDiv: Oversold/Overbought + Divergence + Engulfing
        valid['div_buy_instant'] = (valid['rsi'] < 30) & (valid['low'] < valid['recent_low_50']) & (valid['rsi'] > valid['recent_rsi_low_50'])
        valid['div_sell_instant'] = (valid['rsi'] > 70) & (valid['high'] > valid['recent_high_50']) & (valid['rsi'] < valid['recent_rsi_high_50'])

        recent_div_buy = 0
        recent_div_sell = 0
        
        for i, (idx, row) in enumerate(valid.iterrows()):
            if i < 50:
                continue
            
            current_rates = list_of_dicts[max(0, i-500) : i+1]
            
            # 0. Check pending limit orders
            for p in pending_orders[:]:
                p['Bars_Waited'] += 1
                if p['Bars_Waited'] > 24: # Expire after 24 bars
                    pending_orders.remove(p)
                    continue
                    
                if p['Type'] == 'BUY':
                    if row.low <= p['Limit_Price']:
                        p['Entry'] = p['Limit_Price']
                        p['Time (BKK)'] = row.time_dt.strftime('%Y-%m-%d %H:%M')
                        p['RSI'] = row.rsi
                        p['ATR'] = row.atr
                        p['dist_sma50'] = row.dist_sma50
                        p['dist_sma200'] = row.dist_sma200
                        p['body'] = row.body
                        p['range'] = row.range
                        open_trades.append(p)
                        pending_orders.remove(p)
                elif p['Type'] == 'SELL':
                    if (row.high + spread_price) >= p['Limit_Price']:
                        p['Entry'] = p['Limit_Price']
                        p['Time (BKK)'] = row.time_dt.strftime('%Y-%m-%d %H:%M')
                        p['RSI'] = row.rsi
                        p['ATR'] = row.atr
                        p['dist_sma50'] = row.dist_sma50
                        p['dist_sma200'] = row.dist_sma200
                        p['body'] = row.body
                        p['range'] = row.range
                        open_trades.append(p)
                        pending_orders.remove(p)
                        
            # -- GapSweep Trigger Logic (Enter immediately at Limit Price) --
            if row.gap_sweep_sell and tf_str in target_tfs.get("GapSweep", []):
                sl = row.weekly_open + (row.atr * 2)
                tp = row.weekly_open - (row.atr * 6)
                open_trades.append({
                    "Pattern": "GapSweep", "TF": tf_str, "Time (BKK)": row.time_dt.strftime('%Y-%m-%d %H:%M'),
                    "Type": "SELL", "Limit_Price": round(row.weekly_open, 2), "Entry": round(row.weekly_open, 2), "SL": round(sl, 2), "TP": round(tp, 2),
                    "be_trig": row.weekly_open - (row.atr * 6 * 0.4), "be_act": False,
                    "RSI": round(row.rsi, 2), "ATR": round(row.atr, 2), "Lot": compound,
                    "dist_sma50": round(row.dist_sma50, 2), "dist_sma200": round(row.dist_sma200, 2),
                    "body": round(row.body, 2), "range": round(row.range, 2),
                    "Bars_Waited": 0
                })
            
            if row.gap_sweep_buy and tf_str in target_tfs.get("GapSweep", []):
                sl = row.weekly_open - (row.atr * 2)
                tp = row.weekly_open + (row.atr * 6)
                open_trades.append({
                    "Pattern": "GapSweep", "TF": tf_str, "Time (BKK)": row.time_dt.strftime('%Y-%m-%d %H:%M'),
                    "Type": "BUY", "Limit_Price": round(row.weekly_open, 2), "Entry": round(row.weekly_open, 2), "SL": round(sl, 2), "TP": round(tp, 2),
                    "be_trig": row.weekly_open + (row.atr * 6 * 0.4), "be_act": False,
                    "RSI": round(row.rsi, 2), "ATR": round(row.atr, 2), "Lot": compound,
                    "dist_sma50": round(row.dist_sma50, 2), "dist_sma200": round(row.dist_sma200, 2),
                    "body": round(row.body, 2), "range": round(row.range, 2),
                    "Bars_Waited": 0
                })

            # 1. Update open trades (Check if SL or TP is hit)
            for t in open_trades[:]:
                if t['Type'] == 'BUY':
                    if row.low <= t['SL']:
                        t['Reason'] = 'BE' if t.get('be_act') else 'SL'
                        t['P&L'] = 0.0 if t.get('be_act') else (t['SL'] - t['Entry']) * 100 * t['Lot']
                        t['CloseTime (BKK)'] = row.time_dt.strftime('%Y-%m-%d %H:%M')
                        trades_list.append(t)
                        open_trades.remove(t)
                    elif row.high >= t['TP']:
                        t['Reason'] = 'TP'
                        t['P&L'] = (t['TP'] - t['Entry']) * 100 * t['Lot']
                        t['CloseTime (BKK)'] = row.time_dt.strftime('%Y-%m-%d %H:%M')
                        trades_list.append(t)
                        open_trades.remove(t)
                    
                    # if not t.get('be_act', False) and row.high >= t.get('be_trig', 999999):
                    #     t['be_act'] = True
                    #     t['SL'] = t['Entry']
                elif t['Type'] == 'SELL':
                    if (row.high + spread_price) >= t['SL']:
                        t['Reason'] = 'BE' if t.get('be_act') else 'SL'
                        t['P&L'] = 0.0 if t.get('be_act') else (t['Entry'] - t['SL']) * 100 * t['Lot']
                        t['CloseTime (BKK)'] = row.time_dt.strftime('%Y-%m-%d %H:%M')
                        trades_list.append(t)
                        open_trades.remove(t)
                    elif (row.low + spread_price) <= t['TP']:
                        t['Reason'] = 'TP'
                        t['P&L'] = (t['Entry'] - t['TP']) * 100 * t['Lot']
                        t['CloseTime (BKK)'] = row.time_dt.strftime('%Y-%m-%d %H:%M')
                        trades_list.append(t)
                        open_trades.remove(t)
                        
                    # if not t.get('be_act', False) and (row.low + spread_price) <= t.get('be_trig', -999999):
                    #     t['be_act'] = True
                    #     t['SL'] = t['Entry']
            # 2. Check Naiya Base Formations and Confirmations
            if tf_str == "H12" and row.time_dt.strftime("%Y-%m-%d") == "2026-07-09":
                print(f"H12 07-09 naiya_buy_base: {row.naiya_buy_base}")
                
            if tf_str in target_tfs["Naiya"]:
                if row.naiya_buy_base:
                    print(f"Naiya BUY base found on {tf_str} at {row.time_dt}")
                    doji = list_of_dicts[i-1]
                    limit_p = max(doji['open'], doji['close'])
                    sl = doji['low'] - (row.atr * 1.5)
                    tp = limit_p + (limit_p - sl) * 5.0
                    pending_orders.append({
                        'Pattern': 'Naiya', 'TF': tf_str, 'Time (BKK)': row.time_dt.strftime('%Y-%m-%d %H:%M'),
                        'Type': 'BUY', 'Limit_Price': round(limit_p, 2), 'Entry': 0.0, 'SL': round(sl, 2), 'TP': round(tp, 2),
                        'be_trig': limit_p + (limit_p - sl) * 2.0, 'be_act': False,
                        'RSI': round(row.rsi, 2), 'ATR': round(row.atr, 2), 'Lot': compound,
                        'dist_sma50': round(row.dist_sma50, 2), 'dist_sma200': round(row.dist_sma200, 2),
                        'body': round(row.body, 2), 'range': round(row.range, 2),
                        'Bars_Waited': 0
                    })
                if row.naiya_sell_base:
                    doji = list_of_dicts[i-1]
                    limit_p = min(doji['open'], doji['close'])
                    sl = doji['high'] + (row.atr * 1.5)
                    tp = limit_p - (sl - limit_p) * 5.0
                    pending_orders.append({
                        'Pattern': 'Naiya', 'TF': tf_str, 'Time (BKK)': row.time_dt.strftime('%Y-%m-%d %H:%M'),
                        'Type': 'SELL', 'Limit_Price': round(limit_p, 2), 'Entry': 0.0, 'SL': round(sl, 2), 'TP': round(tp, 2),
                        'be_trig': limit_p - (sl - limit_p) * 2.0, 'be_act': False,
                        'RSI': round(row.rsi, 2), 'ATR': round(row.atr, 2), 'Lot': compound,
                        'dist_sma50': round(row.dist_sma50, 2), 'dist_sma200': round(row.dist_sma200, 2),
                        'body': round(row.body, 2), 'range': round(row.range, 2),
                        'Bars_Waited': 0
                    })

            # 3. Check for new signals
            # 🎯 (SL/TP will be calculated dynamically using Swing & Fibo logic)
            
            # BUY LOGIC
            patterns_buy = []
            
            swing_h = row.recent_high_50
            swing_l = row.recent_low_50
            fibo_38_2 = swing_l + (swing_h - swing_l) * 0.382
            fibo_61_8 = swing_l + (swing_h - swing_l) * 0.618
            
            if tf_str in target_tfs["FVG"] and row.bull_fvg_10 and row.fvg_buy_ml == 1:
                if 15.0 <= row.rsi <= 68.0 and row.atr >= 7.0:
                    # PD Fibo Zone Check (Must be in Discount < 38.2%)
                    if row.recent_low < fibo_38_2:
                        patterns_buy.append("FVG")
            
            # S1 -> S11 Integration (Fibo 3/1)
            s1_res = strategy1.strategy_1(current_rates, tf_str)
            if s1_res and s1_res.get('signal') in ['BUY', 'SELL']:
                strategy11.record_s1_pattern(tf_str, s1_res['signal'], current_rates, current_rates[-1]['time'])
            
            s11_res = strategy11.strategy_11(current_rates, tf_str)
            if s11_res and s11_res.get('signal') == 'BUY':
                patterns_buy.append("Fibo")
                
            # S9 Integration (Div)
            s9_res = strategy9.strategy_9(current_rates, tf_str)
            if s9_res and s9_res.get('signal') == 'BUY':
                if 10.0 <= row.rsi <= 34.0 and row.atr >= 8.0:
                    patterns_buy.append("Div")
                
            if row.div_buy_instant:
                recent_div_buy = 10
            elif recent_div_buy > 0:
                recent_div_buy -= 1
                
            if recent_div_buy > 0 and row.engulfing_bull:
                patterns_buy.append("FollowDiv")
                
            # S20.13.24 Integration (ATR)
            atr_res = strategy20_13_24.evaluate_bar(df, i, tf=tf_str)
            if atr_res and atr_res.get('signal') == 'BUY':
                patterns_buy.append("ATR")
                
            if tf_str in target_tfs["Doji"] and row.range > 0 and row.body < 0.4 * row.range and (row.close - row.low) > 0.5 * row.range and row.low <= row.recent_low + row.atr*0.5 and row.rsi >= 0 and row.rsi <= 2:
                patterns_buy.append("Doji")
            if tf_str in target_tfs["MA12"] and row.low <= row.sma12 and row.close > row.sma12 and row.rsi >= 0 and row.rsi <= 18:
                patterns_buy.append("MA12")
                
            if patterns_buy:
                combined_pat = "/".join(patterns_buy)
                
                # 🎯 Deep Sniper Limit Order: ดักรอที่ก้น Swing Low เป๊ะๆ (ไม่บวกเผื่อ)
                limit_price = row.recent_low 
                sl = row.recent_low - (2.5 * row.atr) # ขยายเกราะเป็น 2.5 ATR กันสะบัด
                swing_size = row.recent_high - row.recent_low
                tp = limit_price + (swing_size * 1.618)
                be_trig = limit_price + (swing_size * 1.618 * 0.4) 

                pending_orders.append({
                    "Pattern": combined_pat, "TF": tf_str, "Time (BKK)": row.time_dt.strftime('%Y-%m-%d %H:%M'),
                    "Type": "BUY", "Limit_Price": round(limit_price, 2), "Entry": 0.0, "SL": round(sl, 2), "TP": round(tp, 2),
                    "be_trig": be_trig, "be_act": False,
                    "RSI": round(row.rsi, 2), "ATR": round(row.atr, 2), "Lot": compound,
                    "dist_sma50": round(row.dist_sma50, 2), "dist_sma200": round(row.dist_sma200, 2),
                    "body": round(row.body, 2), "range": round(row.range, 2),
                    "Bars_Waited": 0
                })

            # SELL LOGIC
            patterns_sell = []
            if tf_str in target_tfs["FVG"] and row.bear_fvg_10:
                if row.fvg_sell_ml == 1 or row.rsi < 30: # Momentum bypass
                    if 10.0 <= row.rsi <= 77.0 and row.atr >= 10.0:
                        if row.recent_high > fibo_61_8 or row.rsi < 30:
                            patterns_sell.append("FVG")
                
            if s11_res and s11_res.get('signal') == 'SELL':
                patterns_sell.append("Fibo")
            if tf_str in target_tfs["Fibo"]:
                for b in range(2, 20):
                    b_bar = df.iloc[i-b]
                    if b_bar['close'] < b_bar['open']:
                        rng = b_bar['high'] - b_bar['low']
                        if rng > 0:
                            krh3 = b_bar['low'] + rng * 5.165
                            if abs(row.high - krh3) < 2.0 and row.close < row.open:
                                patterns_sell.append("Fibo")
                                break
                
            if s9_res and s9_res.get('signal') == 'SELL':
                if 66.0 <= row.rsi <= 90.0 and row.atr >= 8.0:
                    patterns_sell.append("Div")
                
            if row.div_sell_instant:
                recent_div_sell = 10
            elif recent_div_sell > 0:
                recent_div_sell -= 1
                
            if recent_div_sell > 0 and row.engulfing_bear:
                patterns_sell.append("FollowDiv")
                
            if atr_res and atr_res.get('signal') == 'SELL':
                patterns_sell.append("ATR")

            if tf_str in target_tfs["Doji"] and row.range > 0 and row.body < 0.4 * row.range and (row.high - row.close) > 0.5 * row.range and row.high >= row.recent_high - row.atr*0.5 and row.rsi >= 74 and row.rsi <= 78 and row.close < row.sma50 and row.close < row.sma200:
                patterns_sell.append("Doji")
            if tf_str in target_tfs["MA12"] and row.high >= row.sma12 and row.close < row.sma12 and row.rsi >= 74 and row.rsi <= 76 and row.close < row.sma50:
                patterns_sell.append("MA12")
                
            if patterns_sell:
                combined_pat = "/".join(patterns_sell)
                
                # 🎯 Deep Sniper Limit Order: ดักรอที่ยอด Swing High เป๊ะๆ
                limit_price = row.recent_high 
                sl = row.recent_high + (2.5 * row.atr) # ขยายเกราะเป็น 2.5 ATR กันสะบัด
                swing_size = row.recent_high - row.recent_low
                tp = limit_price - (swing_size * 1.618)
                be_trig = limit_price - (swing_size * 1.618 * 0.4) 

                pending_orders.append({
                    "Pattern": combined_pat, "TF": tf_str, "Time (BKK)": row.time_dt.strftime('%Y-%m-%d %H:%M'),
                    "Type": "SELL", "Limit_Price": round(limit_price, 2), "Entry": 0.0, "SL": round(sl, 2), "TP": round(tp, 2),
                    "be_trig": be_trig, "be_act": False,
                    "RSI": round(row.rsi, 2), "ATR": round(row.atr, 2), "Lot": compound,
                    "dist_sma50": round(row.dist_sma50, 2), "dist_sma200": round(row.dist_sma200, 2),
                    "body": round(row.body, 2), "range": round(row.range, 2),
                    "Bars_Waited": 0
                })

        for t in open_trades:
            t['Reason'] = 'OPEN'
            t['P&L'] = 0.0
            t['CloseTime (BKK)'] = t['Time (BKK)']
            trades_list.append(t)

    mt5.shutdown()
    
    df_trades = pd.DataFrame(trades_list)
    if df_trades.empty:
        print("No trades generated.")
        return

    out_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'excel'))
    os.makedirs(out_dir, exist_ok=True)
    
    df_trades = df_trades.sort_values(by="Time (BKK)").reset_index(drop=True)
    
    # 1. Generate individual CSV files by Pattern and TF
    grouped = df_trades.groupby(['Pattern', 'TF'])
    for (pat, tf), group_df in grouped:
        group_df = group_df.copy()
        group_df['Balance'] = 10000.0 + group_df['P&L'].cumsum()
        
        safe_pat = pat.replace("/", "+")
        prefix = f"{safe_pat}_{tf}"
        cols = ["Time (BKK)", "CloseTime (BKK)", "TF", "Pattern", "Type", "RSI", "ATR", "dist_sma50", "dist_sma200", "body", "range", "Entry", "SL", "TP", "Lot", "P&L", "Balance", "Reason"]
        
        # 1. Main trades file
        group_df[cols].to_csv(os.path.join(out_dir, f"{prefix}_trades.csv"), index=False)
        
        # 2. _daily.csv
        group_df['Date'] = pd.to_datetime(group_df['CloseTime (BKK)']).dt.date
        d = group_df.groupby('Date').agg(Trades=('P&L', 'count'), Win=('Reason', lambda x: (x=='TP').sum()), Loss=('Reason', lambda x: (x=='SL').sum()), BE=('Reason', lambda x: (x=='BE').sum()), Net_PnL=('P&L', 'sum')).reset_index()
        d['Cumulative_PnL'] = d['Net_PnL'].cumsum()
        d.to_csv(os.path.join(out_dir, f"{prefix}_daily.csv"), index=False)
        
        # 3. _monthly.csv
        group_df['Month'] = pd.to_datetime(group_df['CloseTime (BKK)']).dt.to_period('M')
        m = group_df.groupby('Month').agg(Trades=('P&L', 'count'), Win=('Reason', lambda x: (x=='TP').sum()), Loss=('Reason', lambda x: (x=='SL').sum()), BE=('Reason', lambda x: (x=='BE').sum()), Net_PnL=('P&L', 'sum')).reset_index()
        m['Cumulative_PnL'] = m['Net_PnL'].cumsum()
        m.to_csv(os.path.join(out_dir, f"{prefix}_monthly.csv"), index=False)
        
        # 4. _compare.csv
        c = group_df.groupby(['Pattern', 'TF']).agg(Trades=('P&L', 'count'), Win=('Reason', lambda x: (x=='TP').sum()), Loss=('Reason', lambda x: (x=='SL').sum()), BE=('Reason', lambda x: (x=='BE').sum()), Net_PnL=('P&L', 'sum')).reset_index()
        c.to_csv(os.path.join(out_dir, f"{prefix}_compare.csv"), index=False)
        
        # 5. _mt5_real.csv
        pd.DataFrame(columns=['Time', 'Ticket', 'Type', 'Volume', 'Price', 'S / L', 'T / P', 'Profit']).to_csv(os.path.join(out_dir, f"{prefix}_mt5_real.csv"), index=False)
        
        total = len(group_df)
        wins = (group_df['Reason'] == 'TP').sum()
        losses = (group_df['Reason'] == 'SL').sum()
        be = (group_df['Reason'] == 'BE').sum()
        wr = (wins / (wins + losses) * 100) if (wins + losses) > 0 else 0
        pnl = group_df['P&L'].sum()
        print(f"Saved: {prefix} set (Trades: {total} | W: {wins} | L: {losses} | BE: {be} | WR: {wr:.1f}% | P&L: {pnl:.2f})")
        
    # 2. trades.csv (Master list)
    df_trades['Balance'] = 10000.0 + df_trades['P&L'].cumsum()
    cols = ["Time (BKK)", "CloseTime (BKK)", "TF", "Pattern", "Type", "RSI", "ATR", "dist_sma50", "dist_sma200", "body", "range", "Entry", "SL", "TP", "Lot", "P&L", "Balance", "Reason"]
    df_trades[cols].to_csv(os.path.join(out_dir, "trades.csv"), index=False)
    
    total = len(df_trades)
    wins = (df_trades['Reason'] == 'TP').sum()
    losses = (df_trades['Reason'] == 'SL').sum()
    be = (df_trades['Reason'] == 'BE').sum()
    wr = (wins / (wins + losses) * 100) if (wins + losses) > 0 else 0
    pnl = df_trades['P&L'].sum()
    print(f"Saved: trades.csv (Total Trades: {total} | W: {wins} | L: {losses} | BE: {be} | WR: {wr:.1f}% | P&L: {pnl:.2f})")
    
    # 3. daily.csv
    df_trades['Date'] = pd.to_datetime(df_trades['CloseTime (BKK)']).dt.date
    daily = df_trades.groupby('Date').agg(
        Trades=('P&L', 'count'),
        Win=('Reason', lambda x: (x == 'TP').sum()),
        Loss=('Reason', lambda x: (x == 'SL').sum()),
        BE=('Reason', lambda x: (x == 'BE').sum()),
        Net_PnL=('P&L', 'sum')
    ).reset_index()
    daily['Cumulative_PnL'] = daily['Net_PnL'].cumsum()
    daily.to_csv(os.path.join(out_dir, "daily.csv"), index=False)
    print("Saved: daily.csv")
    
    # 4. monthly.csv
    df_trades['Month'] = pd.to_datetime(df_trades['CloseTime (BKK)']).dt.to_period('M')
    monthly = df_trades.groupby('Month').agg(
        Trades=('P&L', 'count'),
        Win=('Reason', lambda x: (x == 'TP').sum()),
        Loss=('Reason', lambda x: (x == 'SL').sum()),
        BE=('Reason', lambda x: (x == 'BE').sum()),
        Net_PnL=('P&L', 'sum')
    ).reset_index()
    monthly['Cumulative_PnL'] = monthly['Net_PnL'].cumsum()
    monthly.to_csv(os.path.join(out_dir, "monthly.csv"), index=False)
    print("Saved: monthly.csv")
    
    # 5. compare.csv
    compare = df_trades.groupby(['Pattern', 'TF']).agg(
        Trades=('P&L', 'count'),
        Win=('Reason', lambda x: (x == 'TP').sum()),
        Loss=('Reason', lambda x: (x == 'SL').sum()),
        BE=('Reason', lambda x: (x == 'BE').sum()),
        Net_PnL=('P&L', 'sum')
    ).reset_index()
    compare.to_csv(os.path.join(out_dir, "compare.csv"), index=False)
    print("Saved: compare.csv")
    
    # 6. mt5_real.csv
    mt5_real = pd.DataFrame(columns=['Time', 'Ticket', 'Type', 'Volume', 'Price', 'S / L', 'T / P', 'Profit'])
    mt5_real.to_csv(os.path.join(out_dir, "mt5_real.csv"), index=False)
    print("Saved: mt5_real.csv")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=365) 
    parser.add_argument("--compound", type=float, default=2.0)
    args = parser.parse_args()
    backtest_patterns_to_csv(args.days, args.compound)
