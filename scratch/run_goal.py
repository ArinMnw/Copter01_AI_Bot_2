import sys
import os
import json
import subprocess
import importlib.util
from datetime import datetime
import shutil

sys.stdout.reconfigure(encoding='utf-8')

progress_path = 'strategy/s20_gen/progress.json'
mix_log_path = 'strategy/s20_gen/mix_log.md'

def load_json(path):
    if not os.path.exists(path): return {}
    with open(path, 'r', encoding='utf-8') as f: return json.load(f)

import time

def save_json(path, data):
    abs_path = os.path.abspath(path)
    tmp_path = abs_path + ".tmp"
    for attempt in range(5):
        try:
            with open(tmp_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=1)
            os.replace(tmp_path, abs_path)
            return
        except OSError as e:
            if attempt == 4: raise e
            time.sleep(0.5)

def get_parent_meta(sid):
    path = f'strategy/s20.{sid}/strategy20_{sid}.py'
    if not os.path.exists(path): return {}
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    import ast
    try:
        meta_str = content.split('META = ')[1].split('\n\ndef')[0]
        return ast.literal_eval(meta_str)
    except:
        return {}

def run_subprocess(cmd):
    proc = subprocess.run(cmd, capture_output=True)
    try:
        stdout = proc.stdout.decode('utf-8', errors='replace')
    except:
        stdout = proc.stdout.decode('cp874', errors='replace')
    try:
        stderr = proc.stderr.decode('utf-8', errors='replace')
    except:
        stderr = proc.stderr.decode('cp874', errors='replace')
    proc.stdout = stdout
    proc.stderr = stderr
    return proc

def run_progress_repair():
    print("Running progress_repair.py --check:")
    proc = run_subprocess([sys.executable, 'strategy/s20_gen/progress_repair.py', '--check'])
    if proc.stdout: print(proc.stdout)
    if proc.stdout and "หายจาก progress.json" in proc.stdout:
        lines = proc.stdout.split('\n')
        for i, line in enumerate(lines):
            if "หายจาก progress.json" in line:
                if "(ไม่มี)" not in lines[i+1] if i+1 < len(lines) else True:
                    print("Anomaly detected! Running repair...")
                    run_subprocess([sys.executable, 'strategy/s20_gen/progress_repair.py'])
                    break

# Generate pairs
A_list = ['422', '339']
B_list = ['158', '169', '182', '193', '200', '206', '208', '212', '225', '228', '229', '234', '235', '250', '253']
methods = ['CONFIRM', 'FILTER', 'VETO', 'MTF']

pairs = []
for A in A_list:
    for B in B_list:
        for m in methods:
            k = 3 if m in ['CONFIRM', 'VETO'] else 0
            logic = f"Mixing {A} with {B} using {m}."
            if m == 'CONFIRM': logic += f" Confirm {A} with {B} signal within {k} bars."
            elif m == 'VETO': logic += f" Veto {A} if {B} opposite signal within {k} bars."
            elif m == 'FILTER': logic += f" Ensure {B} state aligns with {A}."
            elif m == 'MTF': logic += f" Filter {A} using {B} on higher TF."
            
            pairs.append({'A': A, 'B': B, 'method': m, 'k': k, 'logic': logic})

progress = load_json(progress_path)
N = progress.get('next', 467)

processed_count = 0
results_table = []
mix_results = {}

print(f"Starting batch mix from next={N}")

for p in pairs:
    if processed_count >= 12:
        break
        
    if str(N).endswith('0'):
        N += 1
        progress['next'] = N
        save_json(progress_path, progress)

    # Check mix_pair_check.py
    proc_chk = run_subprocess([sys.executable, 'strategy/s20_gen/mix_pair_check.py', p['A'], p['B']])
    if proc_chk.returncode != 0:
        continue
        
    # Check mix_log.md memory to avoid duplicates that may have slipped
    if os.path.exists(mix_log_path):
        with open(mix_log_path, 'r', encoding='utf-8') as f:
            mlog = f.read()
        if f"| {p['A']} | {p['B']} | {p['method']}" in mlog or f"| 20.{p['A']} | 20.{p['B']} | {p['method']}" in mlog:
            continue
            
    print(f"\n--- Processing S20.{N} ---")
    print(proc_chk.stdout.strip())
    
    meta_A = get_parent_meta(p['A'])
    if not meta_A: continue
    
    strategy_code = f'''import numpy as np
import pandas as pd
import importlib.util

META = {{
    "sid": "20.{N}",
    "name": "Mix {p['A']} + {p['B']} ({p['method']})",
    "concept": "Mixed Strategy: {p['A']} and {p['B']}",
    "logic": "{p['logic']}",
    "parents": ["20.{p['A']}", "20.{p['B']}"],
    "mix": "{p['method']}",
    "sl_atr": {meta_A.get('sl_atr', 2.0)},
    "rr": {meta_A.get('rr', 1.5)},
    "max_hold": {meta_A.get('max_hold', 24)},
    "be_r": {meta_A.get('be_r', 1.0)}
}}

def load_strategy(sid):
    path = f'strategy/s20.{{sid}}/strategy20_{{sid}}.py'
    spec = importlib.util.spec_from_file_location(f"s20_{{sid}}", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

mod_a = load_strategy("{p['A']}")
mod_b = load_strategy("{p['B']}")

def generate(df, tf):
    sig_a = mod_a.generate(df, tf)
'''
    if p['method'] == 'CONFIRM':
        strategy_code += f'''    sig_b = mod_b.generate(df, tf)
    out = np.zeros(len(df), dtype=np.int8)
    sig_b_s = pd.Series(sig_b)
    b_long_recent = sig_b_s.rolling(window={p['k']+1}, min_periods=1).max() == 1
    b_short_recent = sig_b_s.rolling(window={p['k']+1}, min_periods=1).min() == -1
    out[(sig_a == 1) & b_long_recent] = 1
    out[(sig_a == -1) & b_short_recent] = -1
    return out
'''
    elif p['method'] == 'FILTER':
        strategy_code += f'''    sig_b = mod_b.generate(df, tf)
    out = np.zeros(len(df), dtype=np.int8)
    state_b = pd.Series(sig_b).replace(0, np.nan).ffill().fillna(0)
    out[(sig_a == 1) & (state_b == 1)] = 1
    out[(sig_a == -1) & (state_b == -1)] = -1
    return out
'''
    elif p['method'] == 'VETO':
        strategy_code += f'''    sig_b = mod_b.generate(df, tf)
    out = np.zeros(len(df), dtype=np.int8)
    sig_b_s = pd.Series(sig_b)
    b_long_recent = sig_b_s.rolling(window={p['k']+1}, min_periods=1).max() == 1
    b_short_recent = sig_b_s.rolling(window={p['k']+1}, min_periods=1).min() == -1
    out[(sig_a == 1) & ~b_short_recent] = 1
    out[(sig_a == -1) & ~b_long_recent] = -1
    return out
'''
    elif p['method'] == 'MTF':
        strategy_code += f'''    import sys
    sys.path.append('.')
    import data
    tf_mapping = {{'M1': 'M5', 'M5': 'M15', 'M15': 'H1', 'M30': 'H4', 'H1': 'D1', 'H4': 'D1', 'D1': 'D1'}}
    tf_big = tf_mapping.get(tf, 'D1')
    tf_sec = {{'M1': 60, 'M5': 300, 'M15': 900, 'M30': 1800, 'H1': 3600, 'H4': 14400, 'D1': 86400}}
    
    if tf_big == tf: return mod_a.generate(df, tf)
        
    df_big = pd.DataFrame(data.load_bars(tf_big))
    current_time_max = df['time'].iloc[-1] + tf_sec[tf]
    df_big = df_big[(df_big['time'] + tf_sec[tf_big]) <= current_time_max].copy()
    
    if len(df_big) == 0: return np.zeros(len(df), dtype=np.int8)
        
    sig_b_big = mod_b.generate(df_big, tf_big)
    state_b_big = pd.Series(sig_b_big, index=df_big['time']).replace(0, np.nan).ffill().fillna(0)
    
    close_times = df_big['time'] + tf_sec[tf_big]
    state_b_big.index = close_times
    state_aligned = state_b_big.reindex(df['time'].values, method='ffill').fillna(0)
    
    out = np.zeros(len(df), dtype=np.int8)
    out[(sig_a == 1) & (state_aligned.values == 1)] = 1
    out[(sig_a == -1) & (state_aligned.values == -1)] = -1
    return out
'''
    os.makedirs(f'strategy/s20.{N}', exist_ok=True)
    with open(f'strategy/s20.{N}/strategy20_{N}.py', 'w', encoding='utf-8') as f:
        f.write(strategy_code)
        
    print(f"Running run_one.py for {N}")
    proc = run_subprocess([sys.executable, 'strategy/s20_gen/run_one.py', str(N)])
    
    res_path = f'strategy/s20.{N}/result_365d.json'
    res_data = load_json(res_path)
    
    verdict_str = "FAIL"
    is_duplicate = "DUPLICATE" in proc.stdout
    pass_tfs = []
    total_net = 0.0
    total_pf = 0.0
    max_jaccard = 0.0
    
    if "Max Jaccard:" in proc.stdout:
        try:
            # Extract Max Jaccard from stdout
            lines = proc.stdout.split('\n')
            for line in lines:
                if "Max Jaccard:" in line:
                    max_jaccard = float(line.split('Max Jaccard:')[1].split()[0])
                    break
        except: pass
        
    if is_duplicate:
        verdict_str = f"DUPLICATE (Max Jaccard {max_jaccard})"
    elif not res_data:
        verdict_str = "FAIL (No result)"
    elif not res_data.get('lookahead_ok', True):
        verdict_str = "FAIL (Lookahead)"
    else:
        tfs = res_data.get('tf', {})
        pass_tfs = [tf for tf, d in tfs.items() if isinstance(d, dict) and d.get('verdict') == 'PASS']
        weak_tfs = [tf for tf, d in tfs.items() if isinstance(d, dict) and d.get('verdict') == 'WEAK']
        if pass_tfs: verdict_str = f"PASS ({','.join(pass_tfs)})"
        elif weak_tfs: verdict_str = "WEAK"
        
        # Calculate net and pf
        for tf, d in tfs.items():
            if isinstance(d, dict) and 'oos' in d:
                total_net += d['oos']['net']
        total_pf = res_data.get('total_pf', 0.0)

    # Append to mix log
    date_str = datetime.now().strftime('%Y-%m-%d')
    with open(mix_log_path, 'a', encoding='utf-8') as f:
        f.write(f"| {N} | 20.{p['A']} | 20.{p['B']} | {p['method']} | {date_str} | {verdict_str} |\n")
        
    # Table record
    results_table.append(f"| S20.{N} | 20.{p['A']} | 20.{p['B']} | {p['method']} | {','.join(pass_tfs) if pass_tfs else '-'} | {total_net:.2f} | {total_pf:.2f} | {max_jaccard:.3f} | {verdict_str} |")
    
    # Process Repair Check
    if not is_duplicate and verdict_str != "FAIL (Lookahead)" and verdict_str != "FAIL (No result)":
        run_progress_repair()

    # Final Gate
    if pass_tfs:
        print(f"Running final_gate for {N}")
        fg_proc = run_subprocess([sys.executable, 'strategy/s20_gen/final_gate.py', str(N)])
        print(fg_proc.stdout)
        
        # Mix Check
        res_a = load_json(f'strategy/s20.{p["A"]}/result_365d.json')
        mix_check = "MIX_OK\n"
        for p_tf in pass_tfs:
            mix_pf = tfs[p_tf]['pf']
            mix_oos = tfs[p_tf]['oos']['net']
            mix_n = tfs[p_tf]['n']
            a_pf = res_a['tf'][p_tf]['pf']
            a_oos = res_a['tf'][p_tf]['oos']['net']
            
            if mix_n < 50: mix_check = f"MIX_FAIL: b (n={mix_n} < 50 in {p_tf})\n"
            elif mix_pf < a_pf + 0.10: mix_check = f"MIX_FAIL: a (PF {mix_pf} not > {a_pf}+0.10 in {p_tf})\n"
            elif mix_oos < a_oos: mix_check = f"MIX_FAIL: a (OOS {mix_oos} worse than A {a_oos} in {p_tf})\n"
            mix_check += f"{p_tf}: PF {mix_pf} vs A {a_pf} | OOS {mix_oos} vs A {a_oos} | N {mix_n}\n"
            
            mix_results[N] = {'tf': p_tf, 'mix_pf': mix_pf, 'a_pf': a_pf, 'mix_oos': mix_oos, 'a_oos': a_oos, 'mix_n': mix_n}
            
        with open(f'strategy/s20.{N}/mix_check.txt', 'w', encoding='utf-8') as f:
            f.write(mix_check)
            
        print("mix_check.txt:")
        print(mix_check)
        
    if is_duplicate or verdict_str.startswith("FAIL"):
        shutil.rmtree(f'strategy/s20.{N}', ignore_errors=True)
        shutil.rmtree(f'reports/s20_{N}', ignore_errors=True)
    else:
        # Check winner
        fg_path = f'strategy/s20.{N}/final_gate.txt'
        mc_path = f'strategy/s20.{N}/mix_check.txt'
        is_winner = False
        if os.path.exists(fg_path) and os.path.exists(mc_path):
            with open(fg_path, 'r', encoding='utf-8') as f: fg = f.read()
            with open(mc_path, 'r', encoding='utf-8') as f: mc = f.read()
            if fg.startswith('WINNER') and mc.startswith('MIX_OK'):
                is_winner = True
        
        if not is_winner:
            shutil.rmtree(f'reports/s20_{N}', ignore_errors=True)
            
    progress = load_json(progress_path)
    N = int(N) + 1
    progress['next'] = N
    save_json(os.path.abspath(progress_path), progress)
    processed_count += 1
    print(f"Finished. Moving to next: {N}")

print("\n\n=== 1. SUMMARY TABLE ===")
print("| sid | Parent A | Parent B | Method | Pass TFs | Total Net | Total PF | Max Jaccard | Verdict |")
print("|---|---|---|---|---|---|---|---|---|")
for r in results_table: print(r)

print("\n=== 2. COMPARISON TABLE ===")
print("| sid | TF | Mix PF | A PF | Mix OOS | A OOS | Mix N |")
print("|---|---|---|---|---|---|---|")
for sid, d in mix_results.items():
    print(f"| {sid} | {d['tf']} | {d['mix_pf']} | {d['a_pf']} | {d['mix_oos']} | {d['a_oos']} | {d['mix_n']} |")
