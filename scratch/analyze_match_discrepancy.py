import pandas as pd

df_real = pd.read_csv('reports/s20_301/S20_301_mt5_real.csv')
df_bt_no = pd.read_csv('reports/s20_301/S20_301_backtest_not_match.csv')
df_comp = pd.read_csv('reports/s20_301/S20_301_compare.csv')

print('=== Backtest not match rows ===')
for idx, r in df_bt_no.iterrows():
    st = r['SIM_Open_Time']
    tf = r['SIM_TF']
    typ = r['SIM_Type']
    ep = r['SIM_Entry']
    print(f'#{idx}: {st} {tf} {typ} @ {ep}')
    matches = df_real[(df_real['TF'] == tf) & (df_real['Type'] == typ) & (abs(df_real['Entry'] - ep) < 1.0)]
    if len(matches) > 0:
        print('   Found in MT5 Real:')
        for _, m in matches.iterrows():
            m_time = m['Time (BKK)']
            m_entry = m['Entry']
            already = df_comp[df_comp['MT5_Open_Time'] == m_time]
            if len(already) > 0:
                sim_time = already['SIM_Open_Time'].values[0]
                sim_entry = already['SIM_Entry'].values[0]
                print(f'      MT5: {m_time} @ {m_entry} -> Already matched to SIM {sim_time} @ {sim_entry}')
            else:
                print(f'      MT5: {m_time} @ {m_entry} -> UNMATCHED in MT5!')
    else:
        print('   No real trades within 1.0 USD')
