import os
import sys
import subprocess
import pandas as pd
import datetime

groups = [1, 2, 5, 7, 8, 10, 11, 12, 13, 15, 17, 18, 22, 23, 24]
python_exe = sys.executable
start_time = '2026-09-17 10:36'
profile = 'demo-exness-434238722'

print(f'Starting Compare run for {len(groups)} groups from {start_time} against {profile}...\n')

results = []
for g in groups:
    if g == 23:
        script = 'strategy/s20.14.1/backtest-sim/v38_standalone_group23_mtf_limit.py'
        out_dir = f'strategy/s20.14.1/excel_group{g}_limit'
    else:
        script = f'strategy/s20.14.1/backtest-sim/v38_standalone_group{g}.py'
        out_dir = f'strategy/s20.14.1/excel_group{g}'
    
    if os.path.exists(script):
        time_str = datetime.datetime.now().strftime('%H:%M:%S')
        print(f'=== [{time_str}] Group {g} ===')
        for f in ['match_order.csv', 'backtest_not_match.csv', 'mt5_not_match.csv']:
            path = os.path.join(out_dir, f)
            if os.path.exists(path):
                try: os.remove(path)
                except: pass
                
        cmd = [python_exe, script, '--start', start_time, '--compare']
        subprocess.run(cmd, capture_output=False)

        match_file = os.path.join(out_dir, 'match_order.csv')
        bt_unmatch = os.path.join(out_dir, 'backtest_not_match.csv')
        mt5_unmatch = os.path.join(out_dir, 'mt5_not_match.csv')
        
        m_cnt = len(pd.read_csv(match_file)) if os.path.exists(match_file) else 0
        bt_cnt = len(pd.read_csv(bt_unmatch)) if os.path.exists(bt_unmatch) else 0
        mt5_cnt = len(pd.read_csv(mt5_unmatch)) if os.path.exists(mt5_unmatch) else 0
            
        results.append({'Group': g, 'Matched': m_cnt, 'BT_Unmatched': bt_cnt, 'MT5_Unmatched': mt5_cnt})

if results:
    print('\n=== MATCHING RESULTS ===')
    print(pd.DataFrame(results).to_string(index=False))
