import pandas as pd

df = pd.read_csv('reports/s20_all/S20_ALL_compare.csv')
print(f"Total Matched: {len(df)}")
for i, r in df.iterrows():
    leg = str(r['SIM_Leg'])
    typ = str(r['SIM_Type'])
    bt_e = float(r['SIM_Entry'])
    mt_e = float(r['MT5_Entry'])
    bt_sl = float(r['SIM_SL'])
    mt_sl = float(r['MT5_SL'])
    bt_p = float(r['SIM_P&L'])
    mt_p = float(r['MT5_P&L'])
    t_open = str(r['MT5_Open_Time'])
    t_close = str(r['MT5_Close_Time'])
    comm = str(r['MT5_Comment'])
    print(f"{t_open} -> {t_close} | {leg:18s} | {typ} | Entry: {bt_e:.4f} vs {mt_e:.4f} | SL: {bt_sl:.4f} vs {mt_sl:.4f} | PnL: ${bt_p:+5.2f} vs ${mt_p:+5.2f} | {comm}")
