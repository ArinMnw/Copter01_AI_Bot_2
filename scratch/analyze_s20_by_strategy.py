import pandas as pd
import numpy as np

df = pd.read_csv('reports/s20_all/S20_ALL_trades.csv')
df['sid'] = df['Leg'].apply(lambda x: x.split('_')[0] + '.' + x.split('_')[1] if '_' in str(x) else str(x))

for sid, g in df.groupby('sid'):
    trades = len(g)
    wins_df = g[g['Outcome'] == 'TP']
    loss_df = g[g['Outcome'] == 'SL']
    wins_cnt = len(wins_df)
    loss_cnt = len(loss_df)
    wr = round(wins_cnt / trades * 100, 1) if trades > 0 else 0.0
    pnl = round(g['P&L'].sum(), 2)
    win_val = wins_df['P&L'].sum()
    loss_val = abs(loss_df['P&L'].sum())
    pf = round(win_val / loss_val, 2) if loss_val > 0 else 99.9
    cum = g['P&L'].cumsum()
    peak = cum.cummax()
    max_dd = round((peak - cum).max(), 2)
    print(f"{sid:7s} | Trades: {trades:5d} | Wins: {wins_cnt:5d} | Losses: {loss_cnt:5d} | Win Rate: {wr:5.1f}% | Net P&L: ${pnl:10.2f} | PF: {pf:5.2f} | Max DD: ${max_dd:6.2f}")
