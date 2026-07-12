import pandas as pd
import numpy as np
import MetaTrader5 as mt5
import sys
import os

sys.path.append(os.path.abspath(r'd:\Project\Copter01_AI_Bot_2'))
import config

def get_h1_ema():
    if not config.mt5_initialize(mt5):
        print("MT5 init failed")
        return None
    
    # fetch H1 bars for 60 days
    rates = mt5.copy_rates_from_pos(config.SYMBOL, mt5.TIMEFRAME_H1, 0, 24 * 60)
    mt5.shutdown()
    
    if rates is None: return None
    
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    # MT5 server time is used
    df['ema50'] = df['close'].ewm(span=50, adjust=False).mean()
    
    # shift EMA by 1 to prevent lookahead bias (we only know closed H1 candle ema)
    df['ema50'] = df['ema50'].shift(1)
    
    return df[['time', 'ema50', 'close']]

def main():
    try:
        df = pd.read_csv(r"C:\Users\Copter\.gemini\antigravity-ide\brain\46b76b60-dc83-4319-86c1-8cec2d62a6ff\scratch\s96_trades.csv")
    except:
        print("Cannot load CSV")
        return
        
    df['time'] = pd.to_datetime(df['time'])
    
    h1_df = get_h1_ema()
    if h1_df is None: return
    
    # Floor M5 time to H1 to join
    df['h1_time'] = df['time'].dt.floor('h') # 'H' is deprecated, use 'h'
    
    # Merge
    merged = pd.merge(df, h1_df, left_on='h1_time', right_on='time', how='left', suffixes=('', '_h1'))
    
    # Now we have ema50 (which is the previous H1 closed EMA50) and close (previous H1 close)
    # We can filter:
    # BUY only if H1 Close > H1 EMA50
    # SELL only if H1 Close < H1 EMA50
    
    # Because h1_df has shifted EMA and close? Wait, I didn't shift 'close'. 
    # Let's just use ema50 directly. 
    # If the trend is up, ema50 < price. But we don't have the H1 close at the moment of the trade.
    
    # We can just check the raw trades
    print("Original trades: ", len(merged))
    print("Original Net: $", merged['profit'].sum())
    print("Original WR: ", len(merged[merged['outcome'] == 'TP']) / len(merged) * 100)
    
    # Filter HTF Trend
    # For BUY: we want the H1 trend to be bullish (which implies we are trading in direction of HTF)
    # Actually wait. If H1 is bullish, price is dropping to M5 PoC, so it's a pullback on M5 but aligns with H1!
    def check_htf(row):
        if pd.isna(row['ema50']): return True # keep if unknown
        # Since I shifted ema50 in get_h1_ema, row['ema50'] is the EMA50 of the PREVIOUS closed H1 candle.
        # But we need the close of the PREVIOUS H1 candle to compare.
        # Let's approximate: if current entry price is > h1_ema50, HTF trend is UP.
        is_bullish = row['entry'] > row['ema50']
        
        if row['dir'] == 'BUY' and is_bullish:
            return True
        if row['dir'] == 'SELL' and not is_bullish:
            return True
        return False
        
    merged['htf_ok'] = merged.apply(check_htf, axis=1)
    
    df_htf = merged[merged['htf_ok'] == True]
    
    print("\nAfter HTF Filter (Entry price relative to H1 EMA50):")
    print("Trades: ", len(df_htf))
    print("Net: $", df_htf['profit'].sum())
    print("WR: ", len(df_htf[df_htf['outcome'] == 'TP']) / len(df_htf) * 100)
    
if __name__ == "__main__":
    main()
