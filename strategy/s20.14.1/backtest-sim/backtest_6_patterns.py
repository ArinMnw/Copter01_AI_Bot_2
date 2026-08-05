import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import argparse
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))
import config

def backtest_patterns(days_list, compound):
    mt5.initialize()
    symbol = "XAUUSD.iux"
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
        "MA12": ["H1"]
    }
    
    all_tfs = set()
    for tfs in target_tfs.values():
        all_tfs.update(tfs)
        
    print("Pattern | TF | Days | Trades | Win | Loss | Net P&L")
    print("-" * 65)
    
    for tf_str in all_tfs:
        tf = tf_map.get(tf_str)
        if not tf: continue
        
        limit = max(days_list) * 24 * 60 // (int(tf_str[1:]) if tf_str[1:].isdigit() else 60)
        if limit > 500000: limit = 500000
            
        rates = mt5.copy_rates_from_pos(symbol, tf, 0, limit)
        if rates is None or len(rates) == 0: continue
        
        df = pd.DataFrame(rates)
        df['time_dt'] = pd.to_datetime(df['time'], unit='s')
        
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
        
        df['recent_low'] = df['low'].rolling(window=20).min().shift(1)
        df['recent_high'] = df['high'].rolling(window=20).max().shift(1)
        df['rsi_low'] = df['rsi'].rolling(window=20).min().shift(1)
        
        df['body'] = np.abs(df['close'] - df['open'])
        df['range'] = df['high'] - df['low']
        
        df['bull_fvg'] = df['high'].shift(2) < df['low']
        
        df['next_low'] = df['low'].shift(-1)
        df['next_high'] = df['high'].shift(-1)
        
        valid = df.dropna(subset=['atr', 'rsi', 'next_low']).copy()
        
        for days in days_list:
            cutoff = pd.Timestamp.now() - pd.Timedelta(days=days)
            sub_valid = valid[valid['time_dt'] >= cutoff]
            
            results = {
                "FVG": {"trades":0, "win":0, "loss":0, "pnl":0.0},
                "ATR": {"trades":0, "win":0, "loss":0, "pnl":0.0},
                "Fibo": {"trades":0, "win":0, "loss":0, "pnl":0.0},
                "Doji": {"trades":0, "win":0, "loss":0, "pnl":0.0},
                "Div": {"trades":0, "win":0, "loss":0, "pnl":0.0},
                "MA12": {"trades":0, "win":0, "loss":0, "pnl":0.0},
            }
            
            for row in sub_valid.itertuples():
                sl_dist = config.SL_BUFFER(row.atr)
                tp_dist = row.atr * 2.0
                
                # 1. FVG
                if tf_str in target_tfs["FVG"]:
                    if row.bull_fvg:
                        results["FVG"]["trades"] += 1
                        if row.next_low <= row.low - sl_dist:
                            results["FVG"]["loss"] += 1; results["FVG"]["pnl"] -= 50*compound
                        elif row.next_high >= row.close + tp_dist:
                            results["FVG"]["win"] += 1; results["FVG"]["pnl"] += 100*compound
                            
                # 2. ATR
                if tf_str in target_tfs["ATR"]:
                    if row.close < row.sma20 - 2.5 * row.atr:
                        results["ATR"]["trades"] += 1
                        if row.next_low <= row.low - sl_dist:
                            results["ATR"]["loss"] += 1; results["ATR"]["pnl"] -= 50*compound
                        elif row.next_high >= row.close + tp_dist:
                            results["ATR"]["win"] += 1; results["ATR"]["pnl"] += 100*compound
                            
                # 3. Fibo
                if tf_str in target_tfs["Fibo"]:
                    fibo_level = row.recent_high - (row.recent_high - row.recent_low) * 0.5
                    if row.low <= fibo_level and row.close > fibo_level:
                        results["Fibo"]["trades"] += 1
                        if row.next_low <= row.low - sl_dist:
                            results["Fibo"]["loss"] += 1; results["Fibo"]["pnl"] -= 50*compound
                        elif row.next_high >= row.close + tp_dist:
                            results["Fibo"]["win"] += 1; results["Fibo"]["pnl"] += 100*compound
                            
                # 4. Doji
                if tf_str in target_tfs["Doji"]:
                    if row.range > 0 and row.body < 0.25 * row.range and (row.close - row.low) > 0.6 * row.range and row.low <= row.recent_low + row.atr*0.1:
                        results["Doji"]["trades"] += 1
                        if row.next_low <= row.low - sl_dist:
                            results["Doji"]["loss"] += 1; results["Doji"]["pnl"] -= 50*compound
                        elif row.next_high >= row.close + tp_dist:
                            results["Doji"]["win"] += 1; results["Doji"]["pnl"] += 100*compound
                            
                # 5. Div
                if tf_str in target_tfs["Div"]:
                    if row.low < row.recent_low and row.rsi > row.rsi_low:
                        results["Div"]["trades"] += 1
                        if row.next_low <= row.low - sl_dist:
                            results["Div"]["loss"] += 1; results["Div"]["pnl"] -= 50*compound
                        elif row.next_high >= row.close + tp_dist:
                            results["Div"]["win"] += 1; results["Div"]["pnl"] += 100*compound
                            
                # 6. MA12
                if tf_str in target_tfs["MA12"]:
                    if row.low <= row.sma12 and row.close > row.sma12:
                        results["MA12"]["trades"] += 1
                        if row.next_low <= row.low - sl_dist:
                            results["MA12"]["loss"] += 1; results["MA12"]["pnl"] -= 50*compound
                        elif row.next_high >= row.close + tp_dist:
                            results["MA12"]["win"] += 1; results["MA12"]["pnl"] += 100*compound
                            
            for pat, val in results.items():
                if tf_str in target_tfs[pat]:
                    print(f"{pat:<10} | {tf_str:<5} | {days:<4} | {val['trades']:<8} | {val['win']:<6} | {val['loss']:<6} | {val['pnl']:,.2f}")
                    
    mt5.shutdown()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, nargs="+", default=[30, 60, 90, 120, 150, 365, 700])
    parser.add_argument("--compound", type=float, default=2.0)
    args = parser.parse_args()
    backtest_patterns(args.days, args.compound)
