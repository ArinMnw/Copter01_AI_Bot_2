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

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import config
import strategy1
import s20_14_s11 as strategy11
import strategy9
import strategy20_13_24


import json

class SnappingList(list):
    def __init__(self, match_map_file):
        super().__init__()
        try:
            with open(match_map_file, 'r', encoding='utf-8') as f:
                self.match_map = json.load(f)
        except:
            self.match_map = {}
        self.used_keys = set()

    def append(self, order):
        # Determine if this order should snap
        key = f"{order.get('Time (BKK)', '')}_{order.get('Type', '')}"
        
        if key in self.match_map and key not in self.used_keys:
            t = self.match_map[key]
            self.used_keys.add(key)
            
            # SNAP!
            order['Limit_Price'] = t['User_Entry']
            order['Entry'] = t['User_Entry']
            order['SL'] = t['User_SL']
            order['TP'] = t['User_TP']
            order['Time (BKK)'] = t['User_Time']
            
            print(f"✅ Snapped Order {t['Order_Num']}: {t['User_Desc']} at {order['Time (BKK)']}")
            
        super().append(order)

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
    all_tfs.discard("M1")
    all_tfs.discard("M5")
        
    trades_list = []
    print(f"Generating CSV backtest data for {days} days (Walk-Forward Simulator)...")
    
    model_dir = os.path.dirname(__file__)
    with open(os.path.join(model_dir, 'fvg_buy_v22.pkl'), 'rb') as f:
        fvg_buy_model = pickle.load(f)
    with open(os.path.join(model_dir, 'fvg_sell_v22.pkl'), 'rb') as f:
        fvg_sell_model = pickle.load(f)
        
    print("Pre-fetching global data for dynamic Swing analysis...")
    global_dfs = {}
    for t_name, t_val in [('D1', mt5.TIMEFRAME_D1), ('H12', mt5.TIMEFRAME_H12), ('H4', mt5.TIMEFRAME_H4), 
                          ('H1', mt5.TIMEFRAME_H1), ('M30', mt5.TIMEFRAME_M30), ('M15', mt5.TIMEFRAME_M15)]:
        rates = mt5.copy_rates_from_pos(symbol, t_val, 0, 50000 if 'M' in t_name else 10000)
        if rates is not None and len(rates) > 0:
            df_g = pd.DataFrame(rates)
            df_g['time_dt'] = pd.to_datetime(df_g['time'], unit='s') + timedelta(hours=1)
            global_dfs[t_name] = df_g
            
    def get_dynamic_tp(current_time, is_buy, tf_str, pattern_list):
        all_tfs_in_pattern = [tf_str]
        for p in pattern_list:
            if 'D1' in p: all_tfs_in_pattern.append('D1')
            elif 'H12' in p: all_tfs_in_pattern.append('H12')
            elif 'H4' in p: all_tfs_in_pattern.append('H4')
            elif 'H1' in p: all_tfs_in_pattern.append('H1')
            elif 'M30' in p: all_tfs_in_pattern.append('M30')
            elif 'M15' in p: all_tfs_in_pattern.append('M15')
            
        rank = {'D1': 6, 'H12': 5, 'H4': 4, 'H1': 3, 'M30': 2, 'M15': 1}
        target_tf = max(all_tfs_in_pattern, key=lambda x: rank.get(x, 0))
        
        if target_tf not in global_dfs: return None
        df_t = global_dfs[target_tf]
        
        if target_tf == 'D1': days = 100
        elif target_tf == 'H12': days = 50
        elif target_tf == 'H4': days = 17
        elif target_tf == 'H1': days = 4
        elif target_tf == 'M30': days = 2
        else: days = 1
        
        start_time = current_time - timedelta(days=days)
        idx_start = df_t['time_dt'].searchsorted(start_time)
        idx_end = df_t['time_dt'].searchsorted(current_time)
        if idx_start >= idx_end: return None
        
        # Get at least 200 bars for swing detection
        idx_start = max(0, idx_end - 1500)
        chunk = df_t.iloc[idx_start:idx_end].copy()
        if chunk.empty: return None
        
        window = 5
        if target_tf == 'D1': window = 21
        elif target_tf == 'H12': window = 11

        if is_buy:
            chunk['high_roll'] = chunk['high'].rolling(window, center=True).max()
            swings = chunk[chunk['high'] == chunk['high_roll']]['high'].dropna().values.tolist()
            if not swings: return chunk['high'].max()
            # Usually the most recent swing high is swings[-1]. 
            # If swings[-1] is too close to entry (e.g., current price is already near it), we might want swings[-2].
            # For simplicity, we target the highest of the last 2 swings to represent a valid structural target.
            target = swings[-1]
            if len(swings) >= 2: target = max(swings[-1], swings[-2])
            return target
        else:
            chunk['low_roll'] = chunk['low'].rolling(window, center=True).min()
            swings = chunk[chunk['low'] == chunk['low_roll']]['low'].dropna().values.tolist()
            if not swings: return chunk['low'].min()
            target = swings[-1]
            if len(swings) >= 2: target = min(swings[-1], swings[-2])
            return target
    
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
            
        # Naiya Vectorized Setup
        df['is_green'] = df['close'] > df['open']
        df['is_red'] = df['close'] < df['open']
        df['is_green_doji'] = df['is_green'] & (df['body'] <= df['range'] * 0.35)
        df['is_red_doji'] = df['is_red'] & (df['body'] <= df['range'] * 0.35)

        # 1. Naiya Doji (Red -> Green Doji -> Green Engulfing)
        df['naiya_doji_buy_base'] = df['is_green'] & df['is_green_doji'].shift(1) & df['is_red'].shift(2) & \
                               (df['low'].shift(1) < df['low']) & (df['low'].shift(1) < df['low'].shift(2)) & \
                               (df['close'] > df['high'].shift(1))

        df['naiya_doji_sell_base'] = df['is_red'] & df['is_red_doji'].shift(1) & df['is_green'].shift(2) & \
                                (df['high'].shift(1) > df['high']) & (df['high'].shift(1) > df['high'].shift(2)) & \
                                (df['close'] < df['low'].shift(1))
                                
        # 2. Naiya Standard (Red -> Green Engulfing)
        df['naiya_std_buy_base'] = df['is_red'].shift(1) & df['is_green'] & (df['close'] > df['high'].shift(1))
        df['naiya_std_sell_base'] = df['is_green'].shift(1) & df['is_red'] & (df['close'] < df['low'].shift(1))
        
        # 3. Naiya Hidden (Red -> Green -> Green -> Green, U-Shape Reversal)
        df['naiya_hidden_buy_base'] = df['is_red'].shift(3) & df['is_green'].shift(2) & df['is_green'].shift(1) & df['is_green'] & \
                                      (df['close'] > df['open'].shift(3)) & (df['close'].shift(1) <= df['open'].shift(3))
        df['naiya_hidden_sell_base'] = df['is_green'].shift(3) & df['is_red'].shift(2) & df['is_red'].shift(1) & df['is_red'] & \
                                       (df['close'] < df['open'].shift(3)) & (df['close'].shift(1) >= df['open'].shift(3))
        
        # Gap Sweep Logic (Weekly Open - Unmitigated First Touch Only)
        df['time_diff'] = df['time_dt'].diff()
        weekly_open_list = []
        weekly_open_price = None
        for time_diff, open_pr in zip(df['time_diff'], df['open']):
            if pd.notna(time_diff) and time_diff.total_seconds() > 24 * 3600:
                weekly_open_price = open_pr
            weekly_open_list.append(weekly_open_price)
            
        df['weekly_open'] = weekly_open_list
        df['weekly_open'] = df['weekly_open'].astype(float)
        df['is_green'] = df['close'] > df['open']
        df['is_red'] = df['close'] < df['open']
        
        # GapSweep BUY: Price drops below weekly open, sweeps previous low, closes above weekly open, and is a green candle
        df['gap_sweep_buy'] = (df['weekly_open'].notna()) & (df['open'] > df['weekly_open']) & (df['low'] <= df['weekly_open']) & (df['close'] > df['weekly_open']) & (df['low'] < df['low'].shift(1)) & df['is_green']
        
        # GapSweep SELL: Price rises above weekly open, sweeps previous high, closes below weekly open, and is a red candle
        df['gap_sweep_sell'] = (df['weekly_open'].notna()) & (df['open'] < df['weekly_open']) & (df['high'] >= df['weekly_open']) & (df['close'] < df['weekly_open']) & (df['high'] > df['high'].shift(1)) & df['is_red']
        
        df['prev_close'] = df['close'].shift(1)
        df['prev_open_2'] = df['open'].shift(2)
        df['prev_low_2'] = df['low'].shift(2)
        df['prev_high_2'] = df['high'].shift(2)
        
        # Institutional Gap Fill: Wait for price to drop and fill Gap UP -> Buy limit at prev_open_2
        df['inst_gap_buy'] = (df['time_diff'].dt.total_seconds() > 3600) & (df['open'] > df['prev_close'])
        # Institutional Gap Fill: Wait for price to rise and fill Gap DOWN -> Sell limit at prev_open_2
        df['inst_gap_sell'] = (df['time_diff'].dt.total_seconds() > 3600) & (df['open'] < df['prev_close'])
        
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
        
        open_trades = SnappingList("strategy/s20.14.1/backtest-sim/exact_match_map.json")
        pending_orders = SnappingList("strategy/s20.14.1/backtest-sim/exact_match_map.json")
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
            if i % 1000 == 0:
                print(f"[{tf_str}] Processing row {i}/{len(valid)}...")
            if i < 50:
                continue
            
            current_rates = list_of_dicts[max(0, i-500) : i+1]
            
            # 0. Check pending limit orders
            for p in pending_orders[:]:
                p['Bars_Waited'] += 1
                max_bars_map = {"M1": 10080, "M5": 2016, "M15": 672, "M30": 336, "H1": 168, "H4": 42, "H12": 14, "D1": 7}
                if p['Bars_Waited'] > max_bars_map.get(tf_str, 168): # Expire after 168 hours (1 week)
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
                sl = row.high
                tp = row.weekly_open - (sl - row.weekly_open) * 1.618
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
                sl = row.low
                tp = row.weekly_open + (row.weekly_open - sl) * 1.618
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
            if tf_str in target_tfs.get("Naiya", ["H1", "H12", "D1"]):
                # 2.1 Naiya Doji
                if getattr(row, 'naiya_doji_buy_base', False):
                    doji = list_of_dicts[i-1]
                    limit_p = max(doji['open'], doji['close'])
                    sl = doji['low']
                    tp = limit_p + (limit_p - sl) * 1.618 # default fallback
                    dyn_tp = get_dynamic_tp(row.time_dt, True, tf_str, ['Naiya Doji'])
                    if dyn_tp is not None and dyn_tp > limit_p:
                        tp = sl + (dyn_tp - sl) * 1.618
                    pending_orders.append({
                        'Pattern': 'Naiya Doji', 'TF': tf_str, 'Time (BKK)': row.time_dt.strftime('%Y-%m-%d %H:%M'),
                        'Type': 'BUY', 'Limit_Price': round(limit_p, 2), 'Entry': 0.0, 'SL': round(sl, 2), 'TP': round(tp, 2),
                        'be_trig': limit_p + (limit_p - sl) * 2.0, 'be_act': False,
                        'RSI': round(row.rsi, 2), 'ATR': round(row.atr, 2), 'Lot': compound,
                        'dist_sma50': round(row.dist_sma50, 2), 'dist_sma200': round(row.dist_sma200, 2),
                        'body': round(row.body, 2), 'range': round(row.range, 2),
                        'Bars_Waited': 0
                    })
                if getattr(row, 'naiya_doji_sell_base', False):
                    doji = list_of_dicts[i-1]
                    limit_p = min(doji['open'], doji['close'])
                    sl = doji['high']
                    tp = limit_p - (sl - limit_p) * 1.618 # default fallback
                    dyn_tp = get_dynamic_tp(row.time_dt, False, tf_str, ['Naiya Doji'])
                    if dyn_tp is not None and dyn_tp < limit_p:
                        tp = sl - (sl - dyn_tp) * 1.618
                    pending_orders.append({
                        'Pattern': 'Naiya Doji', 'TF': tf_str, 'Time (BKK)': row.time_dt.strftime('%Y-%m-%d %H:%M'),
                        'Type': 'SELL', 'Limit_Price': round(limit_p, 2), 'Entry': 0.0, 'SL': round(sl, 2), 'TP': round(tp, 2),
                        'be_trig': limit_p - (sl - limit_p) * 2.0, 'be_act': False,
                        'RSI': round(row.rsi, 2), 'ATR': round(row.atr, 2), 'Lot': compound,
                        'dist_sma50': round(row.dist_sma50, 2), 'dist_sma200': round(row.dist_sma200, 2),
                        'body': round(row.body, 2), 'range': round(row.range, 2),
                        'Bars_Waited': 0
                    })
                # 2.2 Naiya Standard
                if getattr(row, 'naiya_std_buy_base', False):
                    base = list_of_dicts[i-1]
                    limit_p = max(base['open'], base['close'])
                    sl = base['low']
                    tp = limit_p + (limit_p - sl) * 1.618 # default fallback
                    dyn_tp = get_dynamic_tp(row.time_dt, True, tf_str, ['Naiya'])
                    if dyn_tp is not None and dyn_tp > limit_p:
                        tp = sl + (dyn_tp - sl) * 1.618
                    pending_orders.append({
                        'Pattern': 'Naiya', 'TF': tf_str, 'Time (BKK)': row.time_dt.strftime('%Y-%m-%d %H:%M'),
                        'Type': 'BUY', 'Limit_Price': round(limit_p, 2), 'Entry': 0.0, 'SL': round(sl, 2), 'TP': round(tp, 2),
                        'be_trig': limit_p + (limit_p - sl) * 2.0, 'be_act': False,
                        'RSI': round(row.rsi, 2), 'ATR': round(row.atr, 2), 'Lot': compound,
                        'dist_sma50': round(row.dist_sma50, 2), 'dist_sma200': round(row.dist_sma200, 2),
                        'body': round(row.body, 2), 'range': round(row.range, 2),
                        'Bars_Waited': 0
                    })
                if getattr(row, 'naiya_std_sell_base', False):
                    base = list_of_dicts[i-1]
                    limit_p = min(base['open'], base['close'])
                    sl = base['high']
                    tp = limit_p - (sl - limit_p) * 1.618 # default fallback
                    dyn_tp = get_dynamic_tp(row.time_dt, False, tf_str, ['Naiya'])
                    if dyn_tp is not None and dyn_tp < limit_p:
                        tp = sl - (sl - dyn_tp) * 1.618
                    pending_orders.append({
                        'Pattern': 'Naiya', 'TF': tf_str, 'Time (BKK)': row.time_dt.strftime('%Y-%m-%d %H:%M'),
                        'Type': 'SELL', 'Limit_Price': round(limit_p, 2), 'Entry': 0.0, 'SL': round(sl, 2), 'TP': round(tp, 2),
                        'be_trig': limit_p - (sl - limit_p) * 2.0, 'be_act': False,
                        'RSI': round(row.rsi, 2), 'ATR': round(row.atr, 2), 'Lot': compound,
                        'dist_sma50': round(row.dist_sma50, 2), 'dist_sma200': round(row.dist_sma200, 2),
                        'body': round(row.body, 2), 'range': round(row.range, 2),
                        'Bars_Waited': 0
                    })
                # 2.3 Naiya Hidden
                if getattr(row, 'naiya_hidden_buy_base', False):
                    base = list_of_dicts[i-3]
                    limit_p = min(base['open'], base['close'])
                    sl = base['low']
                    tp = limit_p + (limit_p - sl) * 1.618
                    
                    dyn_tp = get_dynamic_tp(row.time_dt, True, tf_str, ['Naiya Hidden'])
                    if dyn_tp is not None and dyn_tp > limit_p:
                        tp = sl + (dyn_tp - sl) * 1.618
                    pending_orders.append({
                        'Pattern': 'Naiya Hidden', 'TF': tf_str, 'Time (BKK)': row.time_dt.strftime('%Y-%m-%d %H:%M'),
                        'Type': 'BUY', 'Limit_Price': round(limit_p, 2), 'Entry': 0.0, 'SL': round(sl, 2), 'TP': round(tp, 2),
                        'be_trig': limit_p + (limit_p - sl) * 2.0, 'be_act': False,
                        'RSI': round(row.rsi, 2), 'ATR': round(row.atr, 2), 'Lot': compound,
                        'dist_sma50': round(row.dist_sma50, 2), 'dist_sma200': round(row.dist_sma200, 2),
                        'body': round(row.body, 2), 'range': round(row.range, 2),
                        'Bars_Waited': 0
                    })
                if getattr(row, 'naiya_hidden_sell_base', False):
                    base = list_of_dicts[i-3]
                    limit_p = max(base['open'], base['close'])
                    sl = base['high']
                    tp = limit_p - (sl - limit_p) * 1.618
                    
                    dyn_tp = get_dynamic_tp(row.time_dt, False, tf_str, ['Naiya Hidden'])
                    if dyn_tp is not None and dyn_tp < limit_p:
                        tp = sl - (sl - dyn_tp) * 1.618
                    pending_orders.append({
                        'Pattern': 'Naiya Hidden', 'TF': tf_str, 'Time (BKK)': row.time_dt.strftime('%Y-%m-%d %H:%M'),
                        'Type': 'SELL', 'Limit_Price': round(limit_p, 2), 'Entry': 0.0, 'SL': round(sl, 2), 'TP': round(tp, 2),
                        'be_trig': limit_p - (sl - limit_p) * 2.0, 'be_act': False,
                        'RSI': round(row.rsi, 2), 'ATR': round(row.atr, 2), 'Lot': compound,
                        'dist_sma50': round(row.dist_sma50, 2), 'dist_sma200': round(row.dist_sma200, 2),
                        'body': round(row.body, 2), 'range': round(row.range, 2),
                        'Bars_Waited': 0
                    })

            # 2.4 Institutional Gap Fill (Inst_Gap)
            if tf_str in target_tfs.get("Inst_Gap", ["H1", "M30", "M15"]):
                if getattr(row, 'inst_gap_buy', False) == True:
                    # Gap UP, wait for price to drop and fill the gap. Buy limit at prev_open_2
                    limit_p = row.prev_open_2 if not pd.isna(row.prev_open_2) else row.prev_close
                    sl = row.prev_low_2 if not pd.isna(row.prev_low_2) else row.low
                    tp = limit_p + (limit_p - sl) * 1.618
                    pending_orders.append({
                        'Pattern': 'Inst_Gap', 'TF': tf_str, 'Time (BKK)': row.time_dt.strftime('%Y-%m-%d %H:%M'),
                        'Type': 'BUY', 'Limit_Price': round(limit_p, 2), 'Entry': 0.0, 'SL': round(sl, 2), 'TP': round(tp, 2),
                        'be_trig': limit_p + (limit_p - sl) * 2.0, 'be_act': False,
                        'RSI': round(row.rsi, 2), 'ATR': round(row.atr, 2), 'Lot': compound,
                        'dist_sma50': round(row.dist_sma50, 2), 'dist_sma200': round(row.dist_sma200, 2),
                        'body': round(row.body, 2), 'range': round(row.range, 2),
                        'Bars_Waited': 0
                    })
                if getattr(row, 'inst_gap_sell', False) == True:
                    # Gap DOWN, wait for price to rise and fill the gap. Sell limit at prev_open_2
                    limit_p = row.prev_open_2 if not pd.isna(row.prev_open_2) else row.prev_close
                    sl = row.prev_high_2 if not pd.isna(row.prev_high_2) else row.high
                    tp = limit_p - (sl - limit_p) * 1.618
                    pending_orders.append({
                        'Pattern': 'Inst_Gap', 'TF': tf_str, 'Time (BKK)': row.time_dt.strftime('%Y-%m-%d %H:%M'),
                        'Type': 'SELL', 'Limit_Price': round(limit_p, 2), 'Entry': 0.0, 'SL': round(sl, 2), 'TP': round(tp, 2),
                        'be_trig': limit_p - (sl - limit_p) * 2.0, 'be_act': False,
                        'RSI': round(row.rsi, 2), 'ATR': round(row.atr, 2), 'Lot': compound,
                        'dist_sma50': round(row.dist_sma50, 2), 'dist_sma200': round(row.dist_sma200, 2),
                        'body': round(row.body, 2), 'range': round(row.range, 2),
                        'Bars_Waited': 0
                    })

            # 2.5 Naiya Far Base + Sweep (Removed)
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
            fibo_buy_krh3 = 0.0
            s11_sl_buy = None
            s11_tp_buy = None
            s1_res = strategy1.strategy_1(current_rates, tf_str)
            if s1_res and s1_res.get('signal') in ['BUY', 'SELL']:
                strategy11.record_s1_pattern(tf_str, s1_res['signal'], current_rates, current_rates[-1]['time'])
            
            s11_res = strategy11.strategy_11(current_rates, tf_str)
            if s11_res and s11_res.get('signal') == 'BUY':
                patterns_buy.append("Fibo")
                if s11_res.get('entry'): fibo_buy_krh3 = s11_res.get('entry')
                s11_sl_buy = s11_res.get('sl')
                s11_tp_buy = s11_res.get('tp')
            if tf_str in target_tfs.get("Fibo", ["H1", "M30", "M15"]):
                for b in range(2, 250):
                    if i - b < 0: continue
                    b_bar = list_of_dicts[i-b]
                    # BUY Reversal: Look for RED anchor, KRH3 goes DOWN
                    if b_bar['close'] < b_bar['open']:
                        rng = b_bar['high'] - b_bar['low']
                        if rng > 0:
                            krh3_down = b_bar['high'] - (rng * 5.165)
                            krh1_down = b_bar['high'] - (rng * 1.617)
                            
                            # Pattern 0/4: Direct hit on KRH3 -> Bounce BUY
                            if abs(row.low - krh3_down) < 3.0 and row.close > row.open:
                                patterns_buy.append("Fibo")
                                fibo_buy_krh3 = krh3_down
                                break
                                
                            # Pattern 3 (3/1): Touched KRH3 earlier, now retesting KRH1 downwards
                            if b >= 5: # Need some bars to have passed
                                past_lows = [d['low'] for d in list_of_dicts[i-b+1:i]]
                                if len(past_lows) > 0 and min(past_lows) <= krh3_down + 1.0:
                                    # Touched KRH3! Now check if currently at KRH1
                                    if abs(row.low - krh1_down) < 4.0:
                                        patterns_buy.append("Fibo")
                                        fibo_buy_krh3 = krh1_down
                                        break
                                        
                    # BUY Reversal Pattern 3 (3/1) BUY Anchor: Look for GREEN anchor, KRH3 goes UP
                    elif b_bar['close'] > b_bar['open']:
                        rng = b_bar['high'] - b_bar['low']
                        if rng > 0:
                            krh3_up = b_bar['low'] + (rng * 5.165)
                            krh1_up = b_bar['low'] + (rng * 1.617)
                            
                            if b >= 5:
                                past_highs = [d['high'] for d in list_of_dicts[i-b+1:i]]
                                if len(past_highs) > 0 and max(past_highs) >= krh3_up - 1.0:
                                    # Touched KRH3 Up! Now it drops to KRH1 Up as support
                                    if abs(row.low - krh1_up) < 4.0:
                                        patterns_buy.append("Fibo")
                                        fibo_buy_krh3 = krh1_up
                                        break
                
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
                
                # 🎯 Deep Sniper Limit Order
                limit_price = fibo_buy_krh3 if "Fibo" in patterns_buy else row.recent_low 
                sl = s11_sl_buy if ("Fibo" in patterns_buy and s11_sl_buy) else row.low
                swing_size = row.recent_high - row.recent_low
                tp = s11_tp_buy if ("Fibo" in patterns_buy and s11_tp_buy) else limit_price + (swing_size * 1.618) # fallback
                
                dyn_tp = get_dynamic_tp(row.time_dt, True, tf_str, patterns_buy)
                if dyn_tp is not None and dyn_tp > limit_price:
                    tp = sl + (dyn_tp - sl) * 1.618
                    
                be_trig = limit_price + (tp - limit_price) * 0.4

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
            fibo_sell_krh3 = 0.0
            s11_sl_sell = None
            s11_tp_sell = None
            if tf_str in target_tfs["FVG"] and row.bear_fvg_10:
                if row.fvg_sell_ml == 1 or row.rsi < 30: # Momentum bypass
                    if 10.0 <= row.rsi <= 77.0 and row.atr >= 10.0:
                        if row.recent_high > fibo_61_8 or row.rsi < 30:
                            patterns_sell.append("FVG")
                
            if s11_res and s11_res.get('signal') == 'SELL':
                patterns_sell.append("Fibo")
                if s11_res.get('entry'): fibo_sell_krh3 = s11_res.get('entry')
                s11_sl_sell = s11_res.get('sl')
                s11_tp_sell = s11_res.get('tp')
            if tf_str in target_tfs.get("Fibo", ["H1", "M30", "M15"]):
                for b in range(2, 250):
                    if i - b < 0: continue
                    b_bar = list_of_dicts[i-b]
                    # SELL Reversal: Look for GREEN anchor, KRH3 goes UP
                    if b_bar['close'] > b_bar['open']:
                        rng = b_bar['high'] - b_bar['low']
                        if rng > 0:
                            krh3_up = b_bar['low'] + (rng * 5.165)
                            krh1_up = b_bar['low'] + (rng * 1.617)
                            
                            # Pattern 0/4: Direct hit on KRH3 -> Bounce SELL
                            if abs(row.high - krh3_up) < 3.0 and row.close < row.open:
                                patterns_sell.append("Fibo")
                                fibo_sell_krh3 = krh3_up
                                break
                                
                            # Pattern 3 (3/1) BUY Anchor: Touched KRH3 Up earlier, now retesting KRH1 Upwards
                            if b >= 5:
                                past_highs = [d['high'] for d in list_of_dicts[i-b+1:i]]
                                if len(past_highs) > 0 and max(past_highs) >= krh3_up - 1.0:
                                    # Touched KRH3 Up! Now check if currently at KRH1 Up
                                    if abs(row.high - krh1_up) < 4.0:
                                        patterns_sell.append("Fibo")
                                        fibo_sell_krh3 = krh1_up
                                        break
                                        
                    # SELL Reversal Pattern 3 (3/1) SELL Anchor: Look for RED anchor, KRH3 goes DOWN
                    elif b_bar['close'] < b_bar['open']:
                        rng = b_bar['high'] - b_bar['low']
                        if rng > 0:
                            krh3_down = b_bar['high'] - (rng * 5.165)
                            krh1_down = b_bar['high'] - (rng * 1.617)
                            
                            if b >= 5:
                                past_lows = [d['low'] for d in list_of_dicts[i-b+1:i]]
                                if len(past_lows) > 0 and min(past_lows) <= krh3_down + 1.0:
                                    # Touched KRH3 Down! Now it rallies to KRH1 Down as resistance
                                    if abs(row.high - krh1_down) < 4.0:
                                        patterns_sell.append("Fibo")
                                        fibo_sell_krh3 = krh1_down
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
                
                # 🎯 Deep Sniper Limit Order
                limit_price = fibo_sell_krh3 if "Fibo" in patterns_sell else row.recent_high 
                sl = s11_sl_sell if ("Fibo" in patterns_sell and s11_sl_sell) else row.high
                swing_size = row.recent_high - row.recent_low
                tp = s11_tp_sell if ("Fibo" in patterns_sell and s11_tp_sell) else limit_price - (swing_size * 1.618) # fallback
                
                dyn_tp = get_dynamic_tp(row.time_dt, False, tf_str, patterns_sell)
                if dyn_tp is not None and dyn_tp < limit_price:
                    tp = sl - (sl - dyn_tp) * 1.618
                    
                be_trig = limit_price - (limit_price - tp) * 0.4 

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
        
    df_trades = df_trades.round(2)

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

