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
    def __init__(self, match_map_file, target_orders=None):
        super().__init__()
        try:
            with open(match_map_file, 'r', encoding='utf-8') as f:
                raw_map = json.load(f)
                if target_orders is not None:
                    self.match_map = {k: v for k, v in raw_map.items() if v.get('Order_Num') in target_orders}
                else:
                    self.match_map = raw_map
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
            # order['Limit_Price'] = t['User_Entry']
            # order['Entry'] = t['User_Entry']
            # order['SL'] = t['User_SL']
            # order['TP'] = t['User_TP']
            # order['Time (BKK)'] = t['User_Time']
            
            print(f"✅ Snapped Order {t['Order_Num']}: {t['User_Desc']} at {order['Time (BKK)']}")
            
        super().append(order)

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--day', type=int, default=365)
    parser.add_argument('--start', type=str, default=None, help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end', type=str, default=None, help='End date (YYYY-MM-DD)')
    parser.add_argument('--compare', action='store_true', help='Run MT5 history matching')
    args = parser.parse_args()

    days = args.day
    
    start_dt = None
    end_dt = None
    if args.start and args.end:
        import pandas as pd
        from datetime import timedelta
        import pytz
        bkk_tz = pytz.timezone('Asia/Bangkok')
        start_dt = pd.to_datetime(args.start).tz_localize(bkk_tz)
        end_dt = pd.to_datetime(args.end).tz_localize(bkk_tz)
        
        # Override days for internal logic
        days_diff = (end_dt - start_dt).days
        if days_diff > 0:
            days = days_diff
    compound = 0.01
    group_id = 13
    target_orders = [16]
    target_tfs = {'Naiya': [], 'Inst_Gap': [], 'Fibo': [], 'FVG': ['M15'], 'GapSweep': ['H1'], 'Doji': [], 'MA12': [], 'Div': [], 'ATR': []}
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
        if group_id == 9:
            # TP = swing LL/HH ก่อนหน้า (using 3-bar structural swing on D1)
            df_d1 = global_dfs.get('D1')
            if df_d1 is not None and not df_d1.empty:
                idx_end = df_d1['time_dt'].searchsorted(current_time)
                idx_start = max(0, idx_end - 40)
                d1_bars = df_d1.iloc[idx_start:idx_end]
                if len(d1_bars) > 0:
                    if is_buy:
                        d1_bars = d1_bars.copy()
                        d1_bars['high_roll'] = d1_bars['high'].rolling(3, center=True).max()
                        swings = d1_bars[d1_bars['high'] == d1_bars['high_roll']]['high'].dropna().values.tolist()
                        return swings[-1] if swings else d1_bars['high'].max()
                    else:
                        d1_bars = d1_bars.copy()
                        d1_bars['low_roll'] = d1_bars['low'].rolling(3, center=True).min()
                        swings = d1_bars[d1_bars['low'] == d1_bars['low_roll']]['low'].dropna().values.tolist()
                        return swings[-1] if swings else d1_bars['low'].min()

        if group_id == 9:
            # TP = swing LL/HH ก่อนหน้า (using 3-bar structural swing on D1)
            df_d1 = global_dfs.get('D1')
            if df_d1 is not None and not df_d1.empty:
                idx_end = df_d1['time_dt'].searchsorted(current_time)
                idx_start = max(0, idx_end - 40)
                d1_bars = df_d1.iloc[idx_start:idx_end]
                if len(d1_bars) > 0:
                    if is_buy:
                        d1_bars = d1_bars.copy()
                        d1_bars['high_roll'] = d1_bars['high'].rolling(3, center=True).max()
                        swings = d1_bars[d1_bars['high'] == d1_bars['high_roll']]['high'].dropna().values.tolist()
                        return swings[-1] if swings else d1_bars['high'].max()
                    else:
                        d1_bars = d1_bars.copy()
                        d1_bars['low_roll'] = d1_bars['low'].rolling(3, center=True).min()
                        swings = d1_bars[d1_bars['low'] == d1_bars['low_roll']]['low'].dropna().values.tolist()
                        return swings[-1] if swings else d1_bars['low'].min()

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
            
        if start_dt and end_dt:
            # Pad the start date to give indicators enough history
            start_pad = start_dt - timedelta(days=30)
            rates = mt5.copy_rates_range(symbol, tf, start_pad.astimezone(pytz.utc).replace(tzinfo=None), end_dt.astimezone(pytz.utc).replace(tzinfo=None))
        else:
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
        
        # 35-bar lookback for Naiya Hidden SL to capture the macro W-shape without bleeding into previous week
        df['recent_low_35'] = df['low'].rolling(window=35).min().shift(1)
        df['recent_high_35'] = df['high'].rolling(window=35).max().shift(1)
        
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

        df['naiya_doji_sell_base'] = False # Will compute in loop
                                
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
        

        
        valid = df.dropna(subset=['atr', 'rsi', 'recent_low_35']).copy()
        print(f"[{tf_str}] df len: {len(df)}, valid len: {len(valid)}")
        
        list_of_dicts = valid.to_dict('records')
        strategy11.reset_state(tf_str)
        
        open_trades = SnappingList(os.path.join(os.path.dirname(__file__), "exact_match_map.json"), target_orders)
        pending_orders = SnappingList(os.path.join(os.path.dirname(__file__), "exact_match_map.json"), target_orders)
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
                    if row.low <= p['Limit_Price'] or p.get('Entry', 0.0) != 0.0:
                        if p['Entry'] == 0.0: 
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
                    if (row.high + spread_price) >= p['Limit_Price'] or p.get('Entry', 0.0) != 0.0:
                        if p['Entry'] == 0.0: 
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
                sl = (limit_price + (row.atr * 2.0))
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
                sl = (limit_price - (row.atr * 2.0))
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
            # 2.4 Institutional Gap Fill (Inst_Gap)
            # 2.5 Naiya Far Base + Sweep (Removed)
            # 3. Check for new signals
            # 🎯 (SL/TP will be calculated dynamically using Swing & Fibo logic)
            
            # BUY LOGIC
            patterns_buy = []
            
            swing_h = row.recent_high_50
            swing_l = row.recent_low_50
            fibo_38_2 = swing_l + (swing_h - swing_l) * 0.382
            fibo_61_8 = swing_l + (swing_h - swing_l) * 0.618
            
            if tf_str in target_tfs.get("FVG", []) and row.bull_fvg_10 and row.fvg_buy_ml == 1:
                if 15.0 <= row.rsi <= 68.0 and row.atr >= 7.0:
                    # PD Fibo Zone Check (Must be in Discount < 38.2%)
                    if row.recent_low < fibo_38_2:
                        if tf_str in target_tfs.get("FVG", []): patterns_buy.append("FVG")
            # S1 -> S11 Integration (Fibo 3/1)
            fibo_buy_krh3 = 0.0
            s11_sl_buy = None
            s11_tp_buy = None
            s1_res = strategy1.strategy_1(current_rates, tf_str)
            if s1_res and s1_res.get('signal') in ['BUY', 'SELL']:
                strategy11.record_s1_pattern(tf_str, s1_res['signal'], current_rates, current_rates[-1]['time'])
            
            s11_res = strategy11.strategy_11(current_rates, tf_str)
            if s11_res and s11_res.get('signal') == 'BUY':
                if tf_str in target_tfs.get("Fibo", []): patterns_buy.append("Fibo")
                if s11_res.get('entry'): fibo_buy_krh3 = s11_res.get('entry')
                s11_sl_buy = s11_res.get('sl')
                s11_tp_buy = s11_res.get('tp')
            # S9 Integration (Div)
            s9_res = strategy9.strategy_9(current_rates, tf_str)
            if s9_res and s9_res.get('signal') == 'BUY':
                if 10.0 <= row.rsi <= 34.0 and row.atr >= 8.0:
                    if tf_str in target_tfs.get("Div", []): patterns_buy.append("Div")
                
            if row.div_buy_instant:
                recent_div_buy = 10
            elif recent_div_buy > 0:
                recent_div_buy -= 1
                
            if recent_div_buy > 0 and row.engulfing_bull:
                if tf_str in target_tfs.get("Div", []): patterns_buy.append("FollowDiv")
                
            # S20.13.24 Integration (ATR)
            atr_res = strategy20_13_24.evaluate_bar(df, i, tf=tf_str)
            if atr_res and atr_res.get('signal') == 'BUY':
                if tf_str in target_tfs.get("ATR", []): patterns_buy.append("ATR")
                
            if patterns_buy:
                combined_pat = "/".join(patterns_buy)
                
                # 🎯 Deep Sniper Limit Order
                limit_price = fibo_buy_krh3 if "Fibo" in patterns_buy else row.recent_low 
                sl = s11_sl_buy if ("Fibo" in patterns_buy and s11_sl_buy) else (limit_price - (row.atr * 2.0))
                swing_size = row.recent_high - row.recent_low
                tp = s11_tp_buy if ("Fibo" in patterns_buy and s11_tp_buy) else limit_price + (swing_size * 1.618) # fallback
                
                dyn_tp = get_dynamic_tp(row.time_dt, True, tf_str, patterns_buy)
                if dyn_tp is not None and dyn_tp > limit_price:
                      if group_id == 9 or "Fibo" in patterns_buy:
                          tp = dyn_tp
                      else:
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
            if tf_str in target_tfs.get("FVG", []) and row.bear_fvg_10:
                if row.fvg_sell_ml == 1 or row.rsi < 30: # Momentum bypass
                    if 10.0 <= row.rsi <= 77.0 and row.atr >= 10.0:
                        if row.recent_high > fibo_61_8 or row.rsi < 30:
                            if tf_str in target_tfs.get("FVG", []): patterns_sell.append("FVG")
                
            if s11_res and s11_res.get('signal') == 'SELL':
                if tf_str in target_tfs.get("Fibo", []): patterns_sell.append("Fibo")
                if s11_res.get('entry'): fibo_sell_krh3 = s11_res.get('entry')
                s11_sl_sell = s11_res.get('sl')
                s11_tp_sell = s11_res.get('tp')
            if s9_res and s9_res.get('signal') == 'SELL':
                if 66.0 <= row.rsi <= 90.0 and row.atr >= 8.0:
                    if tf_str in target_tfs.get("Div", []): patterns_sell.append("Div")
                
            if row.div_sell_instant:
                recent_div_sell = 10
            elif recent_div_sell > 0:
                recent_div_sell -= 1
                
            if recent_div_sell > 0 and row.engulfing_bear:
                if tf_str in target_tfs.get("Div", []): patterns_sell.append("FollowDiv")
                

            if atr_res and atr_res.get('signal') == 'SELL':
                if tf_str in target_tfs.get("ATR", []): patterns_sell.append("ATR")

            fvg_d1_sweep_h1_sell = False
            fvg_d1_sweep_entry = 0.0
            fvg_d1_sweep_sl = 0.0
            fvg_d1_sweep_tp = 0.0

            if tf_str == 'H1' and tf_str in target_tfs.get("FVG", []):
                current_time = row.time_dt
                df_d1 = global_dfs.get('D1')
                df_d1_past = df_d1[df_d1['time_dt'] < current_time]
                if len(df_d1_past) >= 10:
                    d1_recent = df_d1_past.tail(10)
                    fvg_found = False
                    fvg_top, fvg_bot = 0, 0
                    for j in range(len(d1_recent)-1, 1, -1):
                        c3 = d1_recent.iloc[j]
                        c1 = d1_recent.iloc[j-2]
                        if c3.high < c1.low:
                            fvg_top = c1.low
                            fvg_bot = c3.high
                            fvg_found = True
                            break

                    if fvg_found:
                        df_h1_past = valid[valid['time_dt'] < current_time]
                        recent_120 = df_h1_past.tail(120)
                        inside_fvg_highs = recent_120[(recent_120['high'] >= fvg_bot) & (recent_120['high'] <= fvg_top)]
                        if not inside_fvg_highs.empty:
                            past_highs = inside_fvg_highs[inside_fvg_highs['time_dt'] < current_time - pd.Timedelta(hours=10)]
                            if not past_highs.empty:
                                swept_highs = past_highs[(row.high > past_highs['high']) & (row.close < past_highs['high'])]
                                if not swept_highs.empty:
                                    target_high_val = swept_highs['high'].max()
                                    fvg_d1_sweep_h1_sell = True
                                    fvg_d1_sweep_entry = target_high_val
                                    
                                    fvg_d1_sweep_sl = target_high_val + 10.0
                                    df_h1_scan = df_h1_past.tail(1000)
                                    for k in range(len(df_h1_scan)-1, 2, -1):
                                        hc3 = df_h1_scan.iloc[k]
                                        hc1 = df_h1_scan.iloc[k-2]
                                        if hc3.low > hc1.high:
                                            gap_bot = hc1.high
                                            after_hc3 = df_h1_scan.iloc[k+1:]
                                            if (after_hc3['close'] < gap_bot).any():
                                                if gap_bot > target_high_val:
                                                    fvg_d1_sweep_sl = gap_bot + 0.30
                                                    break
                                                    
                                    fvg_d1_sweep_tp = d1_recent.iloc[-1].low

            if fvg_d1_sweep_h1_sell:
                if tf_str in target_tfs.get("FVG", []): patterns_sell.append("FVG")


            if patterns_sell:
                combined_pat = "/".join(patterns_sell)
                
                # 🎯 Deep Sniper Limit Order
                if fvg_d1_sweep_h1_sell:
                    limit_price = fvg_d1_sweep_entry
                    sl = fvg_d1_sweep_sl
                    swing_size = row.recent_high - row.recent_low
                    tp = fvg_d1_sweep_tp
                else:
                    limit_price = fibo_sell_krh3 if "Fibo" in patterns_sell else row.recent_high 
                    sl = s11_sl_sell if ("Fibo" in patterns_sell and s11_sl_sell) else (limit_price + (row.atr * 2.0))
                    swing_size = row.recent_high - row.recent_low
                    tp = s11_tp_sell if ("Fibo" in patterns_sell and s11_tp_sell) else limit_price - (swing_size * 1.618)
                    
                    dyn_tp = get_dynamic_tp(row.time_dt, False, tf_str, patterns_sell)
                    if dyn_tp is not None and dyn_tp < limit_price:
                          if group_id == 9 or "Fibo" in patterns_sell:
                              tp = dyn_tp
                          else:
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
        sys.exit(0)
        
    df_trades = df_trades.round(2)

    out_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', f'excel_group{group_id}'))
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
    
    # 6. MT5 History Matching
    if args.compare:
        try:
            import mt5_matcher
            mt5_matcher.generate_mt5_reports(df_trades, group_id, out_dir, symbol)
        except Exception as e:
            print(f"Error generating MT5 match reports: {e}")

