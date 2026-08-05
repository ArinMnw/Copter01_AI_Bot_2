import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import argparse
import sys
import os
from datetime import timedelta

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))
import config

def backtest_patterns_to_csv(days, compound):
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
        
    trades_list = []
    print(f"Generating CSV backtest data for {days} days (Walk-Forward Simulator)...")
    
    for tf_str in all_tfs:
        tf = tf_map.get(tf_str)
        if not tf: continue
        
        limit = days * 24 * 60 // (int(tf_str[1:]) if tf_str[1:].isdigit() else 60)
        if limit > 500000: limit = 500000
            
        rates = mt5.copy_rates_from_pos(symbol, tf, 0, limit)
        if rates is None or len(rates) == 0: continue
        
        df = pd.DataFrame(rates)
        df['time_dt'] = pd.to_datetime(df['time'], unit='s') + timedelta(hours=1)
        
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
        
        valid = df.dropna(subset=['atr', 'rsi', 'recent_low_50']).copy()
        
        open_trades = []
        for row in valid.itertuples():
            # 1. Update open trades (Check if SL or TP is hit)
            for t in open_trades[:]:
                if t['Type'] == 'BUY':
                    if row.low <= t['SL']:
                        t['Reason'] = 'BE' if t.get('be_act') else 'SL'
                        t['P&L'] = 0.0 if t.get('be_act') else -50 * t['Lot']
                        t['CloseTime (BKK)'] = row.time_dt.strftime('%Y-%m-%d %H:%M')
                        trades_list.append(t)
                        open_trades.remove(t)
                    elif row.high >= t['TP']:
                        t['Reason'] = 'TP'
                        t['P&L'] = 100 * t['Lot']
                        t['CloseTime (BKK)'] = row.time_dt.strftime('%Y-%m-%d %H:%M')
                        trades_list.append(t)
                        open_trades.remove(t)
                    
                    if not t.get('be_act', False) and row.high >= t.get('be_trig', 999999):
                        t['be_act'] = True
                        t['SL'] = t['Entry']
                elif t['Type'] == 'SELL':
                    if row.high >= t['SL']:
                        t['Reason'] = 'BE' if t.get('be_act') else 'SL'
                        t['P&L'] = 0.0 if t.get('be_act') else -50 * t['Lot']
                        t['CloseTime (BKK)'] = row.time_dt.strftime('%Y-%m-%d %H:%M')
                        trades_list.append(t)
                        open_trades.remove(t)
                    elif row.low <= t['TP']:
                        t['Reason'] = 'TP'
                        t['P&L'] = 100 * t['Lot']
                        t['CloseTime (BKK)'] = row.time_dt.strftime('%Y-%m-%d %H:%M')
                        trades_list.append(t)
                        open_trades.remove(t)
                        
                    if not t.get('be_act', False) and row.low <= t.get('be_trig', -999999):
                        t['be_act'] = True
                        t['SL'] = t['Entry']
            
            # 2. Check for new signals
            sl_dist = row.atr * 3.0
            tp_dist = row.atr * 1.2
            
            # BUY LOGIC
            patterns_buy = []
            if tf_str in target_tfs["FVG"] and row.bull_fvg_10:
                patterns_buy.append("FVG")
            if tf_str in target_tfs["ATR"] and row.close < row.sma20 - 2.0 * row.atr and row.rsi < 30:
                patterns_buy.append("ATR")
            fibo_38_b = row.recent_high_50 - (row.recent_high_50 - row.recent_low_50) * 0.382
            fibo_61_b = row.recent_high_50 - (row.recent_high_50 - row.recent_low_50) * 0.618
            if tf_str in target_tfs["Fibo"] and row.close <= fibo_38_b and row.close >= fibo_61_b and row.rsi < 40:
                patterns_buy.append("Fibo")
            if tf_str in target_tfs["Doji"] and row.range > 0 and row.body < 0.4 * row.range and (row.close - row.low) > 0.5 * row.range and row.low <= row.recent_low + row.atr*0.5 and row.rsi < 35:
                patterns_buy.append("Doji")
            if tf_str in target_tfs["Div"] and row.low < row.recent_low and row.rsi > row.rsi_low and row.sma50 > row.sma200:
                patterns_buy.append("Div")
            if tf_str in target_tfs["MA12"] and row.low <= row.sma12 and row.close > row.sma12 and row.rsi < 35:
                patterns_buy.append("MA12")
                
            for pat in patterns_buy:
                sl = row.low - sl_dist
                tp = row.close + tp_dist
                be_trig = row.close + (tp_dist * 0.4)
                open_trades.append({
                    "Pattern": pat, "TF": tf_str, "Time (BKK)": row.time_dt.strftime('%Y-%m-%d %H:%M'),
                    "Type": "BUY", "Entry": round(row.close, 2), "SL": round(sl, 2), "TP": round(tp, 2),
                    "be_trig": be_trig, "be_act": False,
                    "RSI": round(row.rsi, 2), "ATR": round(row.atr, 2), "Lot": compound
                })

            # SELL LOGIC
            patterns_sell = []
            if tf_str in target_tfs["FVG"] and row.bear_fvg_10:
                patterns_sell.append("FVG")
            if tf_str in target_tfs["ATR"] and row.close > row.sma20 + 2.0 * row.atr and row.rsi > 70:
                patterns_sell.append("ATR")
            fibo_38_s = row.recent_low_50 + (row.recent_high_50 - row.recent_low_50) * 0.382
            fibo_61_s = row.recent_low_50 + (row.recent_high_50 - row.recent_low_50) * 0.618
            if tf_str in target_tfs["Fibo"] and row.close >= fibo_38_s and row.close <= fibo_61_s and row.rsi > 50:
                patterns_sell.append("Fibo")
            if tf_str in target_tfs["Doji"] and row.range > 0 and row.body < 0.4 * row.range and (row.high - row.close) > 0.5 * row.range and row.high >= row.recent_high - row.atr*0.5 and row.rsi > 70:
                patterns_sell.append("Doji")
            if tf_str in target_tfs["Div"] and row.high > row.recent_high and row.rsi < row.rsi_high and row.sma50 < row.sma200:
                patterns_sell.append("Div")
            if tf_str in target_tfs["MA12"] and row.high >= row.sma12 and row.close < row.sma12 and row.rsi > 70:
                patterns_sell.append("MA12")
                
            for pat in patterns_sell:
                sl = row.high + sl_dist
                tp = row.close - tp_dist
                be_trig = row.close - (tp_dist * 0.4)
                open_trades.append({
                    "Pattern": pat, "TF": tf_str, "Time (BKK)": row.time_dt.strftime('%Y-%m-%d %H:%M'),
                    "Type": "SELL", "Entry": round(row.close, 2), "SL": round(sl, 2), "TP": round(tp, 2),
                    "be_trig": be_trig, "be_act": False,
                    "RSI": round(row.rsi, 2), "ATR": round(row.atr, 2), "Lot": compound
                })

    mt5.shutdown()
    
    df_trades = pd.DataFrame(trades_list)
    if df_trades.empty:
        print("No trades generated.")
        return

    out_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'excel'))
    os.makedirs(out_dir, exist_ok=True)
    
    df_trades = df_trades.sort_values(by="Time (BKK)").reset_index(drop=True)
    
    # 1. Generate individual CSV files by Pattern and TF
    grouped = df_trades.groupby(['Pattern', 'TF'])
    for (pat, tf), group_df in grouped:
        group_df = group_df.copy()
        group_df['Balance'] = 10000.0 + group_df['P&L'].cumsum()
        
        prefix = f"{pat}_{tf}"
        cols = ["Time (BKK)", "CloseTime (BKK)", "TF", "Pattern", "Type", "RSI", "ATR", "Entry", "SL", "TP", "Lot", "P&L", "Balance", "Reason"]
        
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
    cols = ["Time (BKK)", "CloseTime (BKK)", "TF", "Pattern", "Type", "RSI", "ATR", "Entry", "SL", "TP", "Lot", "P&L", "Balance", "Reason"]
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
