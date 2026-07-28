import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

def run_fast_inspect():
    path = r'd:\Project\Copter01_AI_Bot_2\profiles\demo\demo-iux-2101114448\mt5\terminal64.exe'
    if not mt5.initialize(path=path):
        print("MT5 initialize failed")
        return
        
    end = datetime.now()
    start = end - timedelta(days=370)
    rates = mt5.copy_rates_range("XAUUSD.iux", mt5.TIMEFRAME_H1, start, end)
    mt5.shutdown()
    
    if rates is None or len(rates) == 0:
        print("Failed to get rates")
        return

    df = pd.DataFrame(rates)
    df['dt_bkk'] = pd.to_datetime(df['time'], unit='s') + timedelta(hours=7)
    df['dt_str'] = df['dt_bkk'].dt.strftime('%Y-%m-%d %H:%M')
    
    # ATR
    high_low = df['high'] - df['low']
    high_close = np.abs(df['high'] - df['close'].shift())
    low_close = np.abs(df['low'] - df['close'].shift())
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df['atr'] = tr.rolling(14).mean()
    df['atr_pct'] = (df['atr'] / df['close']) * 100.0
    
    # Candle
    df['range'] = df['high'] - df['low']
    df['body'] = np.abs(df['close'] - df['open'])
    df['body_pct'] = df['body'] / (df['range'] + 0.0001)

    # Vol Ratio
    df['vol_ma20'] = df['tick_volume'].rolling(20).mean()
    df['vol_ratio'] = df['tick_volume'] / (df['vol_ma20'] + 1.0)
    
    # EMA
    df['ema_50'] = df['close'].ewm(span=50, adjust=False).mean()
    df['ema_200'] = df['close'].ewm(span=200, adjust=False).mean()
    df['dist_ema50'] = df['close'] - df['ema_50']
    df['dist_ema200'] = df['close'] - df['ema_200']
    
    # RSI
    delta = df['close'].diff()
    gain14 = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss14 = (-delta.where(delta < 0, 0)).rolling(14).mean()
    df['rsi'] = 100 - (100 / (1 + (gain14/loss14)))
    
    gain7 = (delta.where(delta > 0, 0)).rolling(7).mean()
    loss7 = (-delta.where(delta < 0, 0)).rolling(7).mean()
    df['rsi_7'] = 100 - (100 / (1 + (gain7/loss7)))

    # Z-Score
    sma_20 = df['close'].rolling(20).mean()
    std_20 = df['close'].rolling(20).std()
    df['z_score'] = (df['close'] - sma_20) / (std_20 + 0.0001)
    
    # ADX & DI
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
    df['hour'] = df['dt_bkk'].dt.hour
    df['dayofweek'] = df['dt_bkk'].dt.dayofweek

    trades = pd.read_csv(r'd:\Project\Copter01_AI_Bot_2\s20_13_19_trades.csv')
    
    # Merge trades with features
    merged = pd.merge(trades, df, left_on='Time (BKK)', right_on='dt_str', how='inner')
    print("Merged rows:", len(merged))
    
    for side in ['BUY', 'SELL']:
        print(f"\n==================== {side} TRADES ====================")
        sub = merged[merged['Type'] == side]
        for res in ['TP', 'SL']:
            res_df = sub[sub['Reason'] == res]
            print(f"\n--- {side} {res} (Count: {len(res_df)}) ---")
            if len(res_df) == 0: continue
            cols = ['rsi', 'rsi_7', 'adx', 'di_diff', 'z_score', 'atr_pct', 'body_pct', 'vol_ratio', 'dist_ema50', 'hour']
            print(res_df[cols].describe().T[['mean', 'min', '50%', 'max']])
            
    merged.to_csv('trades_365d_fast_features.csv', index=False)
    print("\nSaved trades_365d_fast_features.csv!")

if __name__ == '__main__':
    run_fast_inspect()
