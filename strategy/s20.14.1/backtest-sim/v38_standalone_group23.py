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
    parser.add_argument('--compare-profile', type=str, default=None, help='MT5 profile directory name to use')
    args = parser.parse_args()

    days = args.day
    
    start_dt = None
    end_dt = None
    if args.start:
        import pandas as pd
        from datetime import timedelta
        import pytz
        bkk_tz = pytz.timezone('Asia/Bangkok')
        start_dt = pd.to_datetime(args.start).tz_localize(bkk_tz)
        # ใส่ --start เดี่ยวๆ ไม่ใส่ --end ได้ — default end = ตอนนี้ (BKK)
        # เดิมต้องใส่คู่กันเสมอ (if args.start and args.end) ไม่งั้น start_dt/
        # end_dt ค้างเป็น None ทั้งคู่แล้ว fallback ไปใช้ days=365 จาก 'now'
        # เหมือนกันหมดไม่ว่า --start จะใส่ปีอะไร (เจอบั๊กจริง 2026-09-17)
        end_dt = pd.to_datetime(args.end).tz_localize(bkk_tz) if args.end else pd.Timestamp.now(tz=bkk_tz)
        
        # Override days for internal logic
        days_diff = (end_dt - start_dt).days
        if days_diff > 0:
            days = days_diff
    compound = 0.01
    group_id = 23
    target_orders = [31]
    target_tfs = {"Naiya": [], "Inst_Gap": [], "Fibo": [], "FVG": [], "Naiya": ["H1"], "Doji": [], "MA12": [], "Div": [], "ATR": []}
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
        
        # Naiya BUY: Price drops below weekly open, sweeps previous low, closes above weekly open, and is a green candle
        df['gap_sweep_buy'] = (df['weekly_open'].notna()) & (df['open'] > df['weekly_open']) & (df['low'] <= df['weekly_open']) & (df['close'] > df['weekly_open']) & (df['low'] < df['low'].shift(1)) & df['is_green']
        
        # Naiya SELL: Price rises above weekly open, sweeps previous high, closes below weekly open, and is a red candle
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
        recent_div_buy = 0
        recent_div_sell = 0
        
        # S1 Zone Wick Sweep State Machine (Group 22 Order 30)
        # 0: Looking for S1 SELL
        # 1: Looking for LL (Wait for price to drop and bounce to create a Support)
        # 2: Wait for BOS (Close < Support)
        # 3: Wait for Wick Sweep in S1 Zone
        s1_sweep_state = 0
        s1_sweep_zone_high = 0
        s1_sweep_zone_low = 0
        s1_sweep_support = 0
        s1_sweep_tp = 0
        s1_sweep_ll = 0
        s1_sweep_hl = 0
        s1_sweep_ll_idx = 0
    open_trade = None
    for i, (idx, row) in enumerate(valid.iterrows()):
        
        if open_trade is not None:
            if row.low <= open_trade['SL']:
                open_trade['CloseTime (BKK)'] = row.time_dt.strftime('%Y-%m-%d %H:%M')
                open_trade['Close'] = open_trade['SL']
                open_trade['P&L'] = (open_trade['Close'] - open_trade['Entry']) * 100 * open_trade['Lot'] if open_trade['Type'] == 'BUY' else (open_trade['Entry'] - open_trade['Close']) * 100 * open_trade['Lot']
                open_trade['Balance'] = 0.0
                open_trade['Reason'] = 'SL'
                trades_list.append(open_trade)
                open_trade = None
            elif (open_trade['Type'] == 'BUY' and row.high >= open_trade['TP']) or (open_trade['Type'] == 'SELL' and row.low <= open_trade['TP']):
                open_trade['CloseTime (BKK)'] = row.time_dt.strftime('%Y-%m-%d %H:%M')
                open_trade['Close'] = open_trade['TP']
                open_trade['P&L'] = (open_trade['Close'] - open_trade['Entry']) * 100 * open_trade['Lot'] if open_trade['Type'] == 'BUY' else (open_trade['Entry'] - open_trade['Close']) * 100 * open_trade['Lot']
                open_trade['Balance'] = 0.0
                open_trade['Reason'] = 'TP'
                trades_list.append(open_trade)
                open_trade = None
            continue

        # Setup: Red Liquidity Sweep Low followed by a Respect Low (Higher Low)
        recent_h1 = valid.loc[:idx].iloc[-150:].copy()
        if len(recent_h1) < 15:
            continue
            
        recent_h1['low_roll'] = recent_h1['low'].rolling(3, center=True).min()
        recent_swings = recent_h1[recent_h1['low'] == recent_h1['low_roll']]
        
        if len(recent_swings) >= 2:
            for s in range(len(recent_swings)-1):
                liq_low = recent_swings.iloc[s]
                res_low = recent_swings.iloc[s+1]
                
                # Check if res_low is higher than liq_low
                if res_low['low'] > liq_low['low']:
                    liq_idx = recent_h1.index.get_loc(liq_low.name)
                    res_idx = recent_h1.index.get_loc(res_low.name)
                    
                    if liq_idx > 0 and res_idx > liq_idx:
                        prev_c = recent_h1.iloc[liq_idx-1]
                        
                        # Liq low condition: sweeps the previous candle's low, and previous was RED
                        if liq_low['low'] < prev_c['low'] and prev_c['close'] < prev_c['open']:
                            # The setup is confirmed. If price touches the res_low price, trigger!
                            if row.low <= res_low['low'] and row.high >= res_low['low']:
                                
                                if (row.time_dt - res_low['time_dt']).total_seconds() < 86400 * 14: # valid for 14 days
                                
                                    print(f"???? BUY TRIGGERED at {row.time_dt}")
                                    
                                    # Dynamic TP: Nearest Respect High before trigger
                                    tp_price = row.high + 10
                                    recent_h1['high_roll'] = recent_h1['high'].rolling(3, center=True).max()
                                    highs = recent_h1[recent_h1['high'] == recent_h1['high_roll']]
                                    
                                    respect_highs = []
                                    for h_idx in highs.index:
                                        loc = recent_h1.index.get_loc(h_idx)
                                        if loc > 0:
                                            h2 = recent_h1.iloc[loc]
                                            prev_highs = recent_h1.iloc[:loc]
                                            prev_highs = prev_highs[prev_highs['high'] == prev_highs['high_roll']]
                                            if not prev_highs.empty:
                                                h1 = prev_highs.iloc[-1]
                                                if h2['high'] < h1['high']: # Lower high
                                                    loc1 = recent_h1.index.get_loc(h1.name)
                                                    if loc1 > 0:
                                                        h1_prev = recent_h1.iloc[loc1-1]
                                                        # Red sweep high
                                                        if h1['close'] < h1['open'] and h1['high'] > h1_prev['high']:
                                                            respect_highs.append(h2['high'])
                                                            
                                    if respect_highs:
                                        tp_price = respect_highs[-1]
                                        
                                    open_trade = {
                                        'Time (BKK)': row.time_dt.strftime('%Y-%m-%d %H:%M'),
                                        'TF': 'H1',
                                        'Pattern': 'Naiya',
                                        'Type': 'BUY',
                                        'Entry': res_low['low'],
                                        'SL': liq_low['low'],
                                        'TP': tp_price,
                                        'Lot': compound,
                                        'RSI': round(row.rsi, 2),
                                        'ATR': round(row.atr, 2),
                                        'dist_sma50': round(row.dist_sma50, 2),
                                        'dist_sma200': round(row.dist_sma200, 2),
                                        'body': abs(row.open - row.close),
                                        'range': row.high - row.low
                                    }
                                    break
            if open_trade is not None:
                pass # Already broke out, will continue to next row
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
        d.round(2).to_csv(os.path.join(out_dir, f"{prefix}_daily.csv"), index=False)
        
        # 3. _monthly.csv
        group_df['Month'] = pd.to_datetime(group_df['CloseTime (BKK)']).dt.to_period('M')
        m = group_df.groupby('Month').agg(Trades=('P&L', 'count'), Win=('Reason', lambda x: (x=='TP').sum()), Loss=('Reason', lambda x: (x=='SL').sum()), BE=('Reason', lambda x: (x=='BE').sum()), Net_PnL=('P&L', 'sum')).reset_index()
        m['Cumulative_PnL'] = m['Net_PnL'].cumsum()
        m.round(2).to_csv(os.path.join(out_dir, f"{prefix}_monthly.csv"), index=False)
        
        # 4. _compare.csv
        c = group_df.groupby(['Pattern', 'TF']).agg(Trades=('P&L', 'count'), Win=('Reason', lambda x: (x=='TP').sum()), Loss=('Reason', lambda x: (x=='SL').sum()), BE=('Reason', lambda x: (x=='BE').sum()), Net_PnL=('P&L', 'sum')).reset_index()
        c.round(2).to_csv(os.path.join(out_dir, f"{prefix}_compare.csv"), index=False)
        
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
    daily.round(2).to_csv(os.path.join(out_dir, "daily.csv"), index=False)
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
    monthly.round(2).to_csv(os.path.join(out_dir, "monthly.csv"), index=False)
    print("Saved: monthly.csv")
    
    # 5. compare.csv
    compare = df_trades.groupby(['Pattern', 'TF']).agg(
        Trades=('P&L', 'count'),
        Win=('Reason', lambda x: (x == 'TP').sum()),
        Loss=('Reason', lambda x: (x == 'SL').sum()),
        BE=('Reason', lambda x: (x == 'BE').sum()),
        Net_PnL=('P&L', 'sum')
    ).reset_index()
    compare.round(2).to_csv(os.path.join(out_dir, "compare.csv"), index=False)
    print("Saved: compare.csv")
    
    # 6. MT5 History Matching
    if args.compare:
        try:
            import mt5_matcher
            mt5_matcher.generate_mt5_reports(df_trades, group_id, out_dir, symbol, profile=args.compare_profile)
        except Exception as e:
            print(f"Error generating MT5 match reports: {e}")

