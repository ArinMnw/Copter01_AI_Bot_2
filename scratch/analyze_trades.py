import pandas as pd
import numpy as np
import MetaTrader5 as mt5
from datetime import datetime

df = pd.read_csv('d:/Project/Copter01_AI_Bot_2/strategy/s20.13/excel/s20_13_sim_trades.csv')
print("Total trades loaded:", len(df))

# Let's extract Hour from Time (BKK)
df['Time (BKK)'] = pd.to_datetime(df['Time (BKK)'])
df['Hour'] = df['Time (BKK)'].dt.hour

# We can quickly analyze Win vs Loss by Hour
print("\n--- Trades by Hour ---")
print(pd.crosstab(df['Hour'], df['Reason']))

# Now let's run a quick MT5 data pull to get EMA and RSI for these trades
if mt5.initialize():
    rates = mt5.copy_rates_from_pos("XAUUSD.iux", mt5.TIMEFRAME_H1, 0, 1000)
    mt5_df = pd.DataFrame(rates)
    mt5_df['time'] = pd.to_datetime(mt5_df['time'], unit='s') # Server time
    
    # Calculate EMA 50 and 200
    mt5_df['EMA_50'] = mt5_df['close'].ewm(span=50, adjust=False).mean()
    mt5_df['EMA_200'] = mt5_df['close'].ewm(span=200, adjust=False).mean()
    
    # Calculate RSI
    delta = mt5_df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    mt5_df['RSI'] = 100 - (100 / (1 + rs))
    
    # Merge based on time
    # Time in CSV is BKK. BKK = Server Time + 7 hours (approx, depending on DST).
    # In the backtester: dt_str = datetime.fromtimestamp(rates[i-1]['time'])
    # In Windows, fromtimestamp treats the unix timestamp as local time.
    # So if Server time is X, fromtimestamp(X) produces X + 7 hours.
    # So Server Time = BKK Time - 7 hours.
    
    df['Server_Time'] = df['Time (BKK)'] - pd.Timedelta(hours=7)
    
    merged = pd.merge(df, mt5_df, left_on='Server_Time', right_on='time', how='left')
    
    # Check Trend Alignment
    # Uptrend = Close > EMA 50 > EMA 200
    merged['Trend'] = 'SIDEWAY'
    merged.loc[(merged['close'] > merged['EMA_50']) & (merged['EMA_50'] > merged['EMA_200']), 'Trend'] = 'UP'
    merged.loc[(merged['close'] < merged['EMA_50']) & (merged['EMA_50'] < merged['EMA_200']), 'Trend'] = 'DOWN'
    
    merged['With_Trend'] = False
    merged.loc[(merged['Type'] == 'BUY') & (merged['Trend'] == 'UP'), 'With_Trend'] = True
    merged.loc[(merged['Type'] == 'SELL') & (merged['Trend'] == 'DOWN'), 'With_Trend'] = True
    merged.loc[(merged['Type'] == 'SELL') & (merged['Trend'] == 'UP'), 'Counter_Trend'] = True
    
    print("\n--- Trend Context vs Outcome ---")
    print(pd.crosstab(merged['Trend'], merged['Reason']))
    
    print("\n--- With Trend vs Counter Trend ---")
    print(pd.crosstab(merged['With_Trend'], merged['Reason']))
    
    print("\n--- Average RSI at Entry ---")
    print(merged.groupby(['Type', 'Reason'])['RSI'].mean())
    
    mt5.shutdown()
