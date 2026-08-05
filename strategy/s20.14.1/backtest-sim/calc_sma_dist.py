import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime, timedelta

mt5.initialize()
symbol = 'XAUUSD.iux'
if not mt5.symbol_info(symbol): symbol = 'XAUUSD'

df_matches = pd.read_csv('matched_trades.csv')
for index, row in df_matches.iterrows():
    tf_str = row['TF']
    tf_map = {'M15': mt5.TIMEFRAME_M15, 'M30': mt5.TIMEFRAME_M30, 'H1': mt5.TIMEFRAME_H1, 'H12': mt5.TIMEFRAME_H12, 'D1': mt5.TIMEFRAME_D1}
    tf = tf_map.get(tf_str)
    
    dt_bkk = datetime.strptime(row['Time (BKK)'], '%Y-%m-%d %H:%M')
    dt_mt5 = dt_bkk - timedelta(hours=1)
    
    rates = mt5.copy_rates_from(symbol, tf, dt_mt5, 300)
    if rates is None or len(rates) == 0: continue
    
    rdf = pd.DataFrame(rates)
    rdf['time'] = pd.to_datetime(rdf['time'], unit='s')
    rdf['sma50'] = rdf['close'].rolling(50).mean()
    rdf['sma200'] = rdf['close'].rolling(200).mean()
    
    target = rdf.iloc[-1]
    
    print(f"{row['Type']} {tf_str} {dt_bkk}: dist_sma50={((target['close'] - target['sma50'])/target['sma50']*100):.2f}% dist_sma200={((target['close'] - target['sma200'])/target['sma200']*100):.2f}%")
mt5.shutdown()
