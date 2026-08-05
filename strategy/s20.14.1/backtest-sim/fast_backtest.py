import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import argparse
from datetime import datetime, timedelta
import sys
import os

# Add config path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import config

def fast_backtest(days, tf_list, compound):
    mt5.initialize()
    symbol = "XAUUSD.iux"
    tf_map = {
        "M1": mt5.TIMEFRAME_M1, "M5": mt5.TIMEFRAME_M5, "M15": mt5.TIMEFRAME_M15,
        "M30": mt5.TIMEFRAME_M30, "H1": mt5.TIMEFRAME_H1, "H4": mt5.TIMEFRAME_H4,
        "H12": mt5.TIMEFRAME_H12, "D1": mt5.TIMEFRAME_D1
    }
    
    if tf_list == ["all"]:
        tf_list = ["M1", "M5", "M15", "M30", "H1", "H4", "H12", "D1"]
        
    print(f"\n--- FAST Backtest S20.14 | Days: {days} | Compound: {compound} ---")
    print(f"{'Timeframe':<10} | {'Trades':<8} | {'Win':<6} | {'Loss':<6} | {'Win Rate %':<12} | {'Net P&L ($)':<12} | Patterns")
    print("-" * 110)
    
    total_trades = 0
    total_win = 0
    total_loss = 0
    total_pnl = 0.0
    global_patterns = {}
    
    for tf_str in tf_list:
        tf = tf_map.get(tf_str)
        if not tf: continue
        
        limit = days * 24 * 60 // (int(tf_str[1:]) if tf_str[1:].isdigit() else 60)
        # Hard cap at 500,000 bars if limit is too large to prevent MT5 hanging
        if limit > 500000:
            limit = 500000
            
        rates = mt5.copy_rates_from_pos(symbol, tf, 0, limit)
        if rates is None or len(rates) == 0:
            print(f"{tf_str:<10} | No Data")
            continue
            
        df = pd.DataFrame(rates)
        
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        df['atr'] = tr.rolling(window=14).mean()
        
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        
        df['recent_low'] = df['low'].rolling(window=13).min().shift(2)
        df['recent_high'] = df['high'].rolling(window=13).max().shift(2)
        df['rsi_low'] = df['rsi'].rolling(window=13).min().shift(2)
        df['rsi_high'] = df['rsi'].rolling(window=13).max().shift(2)
        
        df['is_bullish_div'] = (df['low'] < df['recent_low']) & (df['rsi'] > df['rsi_low'])
        df['is_bearish_div'] = (df['high'] > df['recent_high']) & (df['rsi'] < df['rsi_high'])
        
        active_mode = getattr(config, "S20_14_ACTIVE_MODE", 2.0)
        
        trades = 0
        win = 0
        loss_cnt = 0
        pnl = 0.0
        pat_counts = {}
        
        df['next_low'] = df['low'].shift(-1)
        df['next_high'] = df['high'].shift(-1)
        
        valid = df.dropna(subset=['atr', 'rsi', 'recent_low', 'next_low']).copy()
        
        for row in valid.itertuples():
            if row.is_bearish_div:
                sl = row.high + config.SL_BUFFER(row.atr)
                tp = row.close - (row.atr * active_mode)
                trades += 1
                pat = "BearDiv"
                pat_counts[pat] = pat_counts.get(pat, 0) + 1
                global_patterns[pat] = global_patterns.get(pat, 0) + 1
                
                if row.next_high >= sl:
                    loss_cnt += 1
                    pnl -= 50 * compound
                elif row.next_low <= tp:
                    win += 1
                    pnl += 100 * compound
                    
            elif row.is_bullish_div:
                sl = row.low - config.SL_BUFFER(row.atr)
                tp = row.close + (row.atr * active_mode)
                trades += 1
                pat = "BullDiv"
                pat_counts[pat] = pat_counts.get(pat, 0) + 1
                global_patterns[pat] = global_patterns.get(pat, 0) + 1
                
                if row.next_low <= sl:
                    loss_cnt += 1
                    pnl -= 50 * compound
                elif row.next_high >= tp:
                    win += 1
                    pnl += 100 * compound
                    
        win_rate = (win / trades * 100) if trades > 0 else 0
        total_trades += trades
        total_win += win
        total_loss += loss_cnt
        total_pnl += pnl
        
        pat_str = " | ".join([f"{k}: {v}" for k, v in pat_counts.items()])
        print(f"{tf_str:<10} | {trades:<8} | {win:<6} | {loss_cnt:<6} | {win_rate:<12.2f} | {pnl:,.2f} | {pat_str}")
        
    tot_win_rate = (total_win / total_trades * 100) if total_trades > 0 else 0
    tot_pat_str = " | ".join([f"{k}: {v}" for k, v in global_patterns.items()])
    print("-" * 110)
    print(f"{'Total':<10} | {total_trades:<8} | {total_win:<6} | {total_loss:<6} | {tot_win_rate:<12.2f} | {total_pnl:,.2f} | {tot_pat_str}")
    mt5.shutdown()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--tf", nargs="+", default=["all"])
    parser.add_argument("--compound", type=float, default=1.0)
    args = parser.parse_args()
    fast_backtest(args.days, args.tf, args.compound)
