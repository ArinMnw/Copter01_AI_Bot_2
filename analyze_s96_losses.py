import pandas as pd
import numpy as np
import MetaTrader5 as mt5
import sys
import os

sys.path.append(os.path.abspath(r'd:\Project\Copter01_AI_Bot_2'))
import config
from sim_s30_backtest import fetch_bars

def main():
    try:
        df = pd.read_csv(r"d:\Project\Copter01_AI_Bot_2\s96_trades.csv")
    except:
        print("Cannot load CSV")
        return
        
    df['time'] = pd.to_datetime(df['time'])
    
    if not config.mt5_initialize(mt5):
        print("MT5 init failed")
        return
        
    rates = fetch_bars(config.SYMBOL, "M5", 35, extra_bars=500)
    mt5.shutdown()
    
    if len(rates) == 0: return
    
    m5_df = pd.DataFrame(rates)
    m5_df['time'] = pd.to_datetime(m5_df['time'], unit='s')
    
    # Calculate indicators on M5
    # RSI 14
    delta = m5_df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    m5_df['rsi'] = 100 - (100 / (1 + rs))
    
    # ADX 14
    high_diff = m5_df['high'].diff()
    low_diff = m5_df['low'].diff()
    m5_df['+dm'] = np.where((high_diff > low_diff) & (high_diff > 0), high_diff, 0.0)
    m5_df['-dm'] = np.where((low_diff > high_diff) & (low_diff > 0), low_diff, 0.0)
    tr1 = m5_df['high'] - m5_df['low']
    tr2 = (m5_df['high'] - m5_df['close'].shift(1)).abs()
    tr3 = (m5_df['low'] - m5_df['close'].shift(1)).abs()
    m5_df['tr'] = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = m5_df['tr'].rolling(14).mean()
    plus_di = 100 * (m5_df['+dm'].rolling(14).mean() / atr)
    minus_di = 100 * (m5_df['-dm'].rolling(14).mean() / atr)
    dx = (abs(plus_di - minus_di) / (plus_di + minus_di)) * 100
    m5_df['adx'] = dx.rolling(14).mean()
    
    # Merge indicators to trades
    df['time_floor'] = df['time'].dt.floor('5min')
    merged = pd.merge(df, m5_df[['time', 'rsi', 'adx']], left_on='time_floor', right_on='time', how='left')
    
    wins = merged[merged['outcome'] == 'TP']
    losses = merged[merged['outcome'] == 'SL']
    
    print("--- WINNING TRADES ---")
    print(wins[['rsi', 'adx']].describe())
    
    print("\n--- LOSING TRADES ---")
    print(losses[['rsi', 'adx']].describe())
    
    # Check WR by RSI bins
    print("\n--- WR by RSI (BUY) ---")
    buys = merged[merged['dir'] == 'BUY']
    for i in range(20, 80, 10):
        subset = buys[(buys['rsi'] >= i) & (buys['rsi'] < i+10)]
        if len(subset) > 0:
            wr = len(subset[subset['outcome']=='TP'])/len(subset)*100
            print(f"RSI {i}-{i+10}: WR {wr:.1f}% ({len(subset)} trades)")

    print("\n--- WR by RSI (SELL) ---")
    sells = merged[merged['dir'] == 'SELL']
    for i in range(20, 80, 10):
        subset = sells[(sells['rsi'] >= i) & (sells['rsi'] < i+10)]
        if len(subset) > 0:
            wr = len(subset[subset['outcome']=='TP'])/len(subset)*100
            print(f"RSI {i}-{i+10}: WR {wr:.1f}% ({len(subset)} trades)")
            
    # Check WR by ADX bins
    print("\n--- WR by ADX ---")
    for i in range(10, 60, 10):
        subset = merged[(merged['adx'] >= i) & (merged['adx'] < i+10)]
        if len(subset) > 0:
            wr = len(subset[subset['outcome']=='TP'])/len(subset)*100
            print(f"ADX {i}-{i+10}: WR {wr:.1f}% ({len(subset)} trades)")

if __name__ == "__main__":
    main()
