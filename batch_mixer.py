import os
import json
import shutil
import subprocess
import datetime
import importlib
import sys

def run_cmd(cmd):
    print(f"Running: {cmd}")
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    res = subprocess.run(cmd, shell=True, capture_output=True, env=env)
    res.stdout = res.stdout.decode('utf-8', 'ignore') if res.stdout else ""
    res.stderr = res.stderr.decode('utf-8', 'ignore') if res.stderr else ""
    return res

tasks = [
    (194, 242, 'FILTER', '194 (Chande Kroll) as trend direction, filter by 242 (Rainbow MA) to ensure strong momentum'),
    (194, 168, 'CONFIRM', '194 (Chande Kroll) combined with 168 (Ehlers Super Smoother) for confirmation within 5 bars'),
    (194, 356, 'FILTER', '194 trend filtered by 356 (Bollinger Volatility Breakout) state'),
    (242, 356, 'CONFIRM', '242 (Rainbow MA) confirmed by 356 (Bollinger Z-Score) volatility expansion'),
    (242, 168, 'VETO', '242 entered, vetoed if 168 gives opposite signal recently'),
    (143, 342, 'FILTER', '143 (Elder Impulse) filtered by 342 (ADX Low Volatility Breakout) state'),
    (143, 168, 'CONFIRM', '143 (Elder) confirmed by 168 (Ehlers) within 3 bars'),
    (148, 255, 'CONFIRM', '148 (Inside Bar) confirmed by 255 (Hikkake Inside Bar False Breakout)'),
    (148, 194, 'FILTER', '148 filtered by 194 trend'),
    (161, 242, 'FILTER', '161 (Ultimate Osc) filtered by 242 (Rainbow MA) trend'),
    (168, 210, 'CONFIRM', '168 (Ehlers) confirmed by 210 (Bill Williams AC)'),
    (168, 356, 'FILTER', '168 (Ehlers) filtered by 356 (Bollinger Breakout)'),
    (277, 242, 'FILTER', '277 (Quadratic Reg) filtered by 242 (Rainbow MA)'),
    (277, 194, 'FILTER', '277 filtered by 194 (Chande Kroll)'),
    (342, 168, 'CONFIRM', '342 (ADX Breakout) confirmed by 168 (Ehlers)'),
    (356, 143, 'FILTER', '356 (Bollinger Z-Score) filtered by 143 (Elder Impulse)'),
    (356, 161, 'CONFIRM', '356 confirmed by 161 (Ultimate Osc)'),
    (143, 242, 'FILTER', '143 filtered by 242'),
    (242, 194, 'CONFIRM', '242 confirmed by 194'),
    (194, 143, 'VETO', '194 vetoed by 143')
]

# Read current next
with open('strategy/s20_gen/progress.json', 'r', encoding='utf-8') as f:
    prog = json.load(f)
N = prog['next']

success_count = 0
task_idx = 0
log_f = open('batch_output.txt', 'w', encoding='utf-8')

while success_count < 15 and task_idx < len(tasks):
    A, B, mix, logic = tasks[task_idx]
    
    # Check if N ends with 0
    if str(N).endswith('0'):
        print(f"Skip N={N} (ends with 0)")
        N += 1
        continue
        
    print(f"\n--- TRYING N={N} with {A} + {B} ({mix}) ---")
    log_f.write(f"\n--- TRYING N={N} with {A} + {B} ({mix}) ---\n")
    
    # Check pair validity
    check_res = run_cmd(f"python strategy/s20_gen/mix_pair_check.py {A} {B}")
    log_f.write(f"mix_pair_check:\n{check_res.stdout}\n")
    if check_res.returncode == 1:
        print("Pair invalid, trying next pair")
        task_idx += 1
        continue
        
    # Generate code
    sys.path.insert(0, os.path.abspath('.'))
    try:
        spec_a = importlib.util.spec_from_file_location(f"s20_{A}", f"strategy/s20.{A}/strategy20_{A}.py")
        mod_a = importlib.util.module_from_spec(spec_a)
        spec_a.loader.exec_module(mod_a)
        
        sl = mod_a.META.get('sl_atr', 2.0)
        rr = mod_a.META.get('rr', 1.5)
        mh = mod_a.META.get('max_hold', 100)
        be = mod_a.META.get('be_r', 0.0)
    except Exception as e:
        print(f"Error loading parent: {e}")
        task_idx += 1
        continue
        
    code = f"""import sys, os
sys.path.insert(0, os.path.abspath('.'))
import numpy as np
import pandas as pd
from strategy.s20_gen.ind import *
import importlib.util

spec_a = importlib.util.spec_from_file_location("s20_{A}", "strategy/s20.{A}/strategy20_{A}.py")
parent_A = importlib.util.module_from_spec(spec_a)
spec_a.loader.exec_module(parent_A)

spec_b = importlib.util.spec_from_file_location("s20_{B}", "strategy/s20.{B}/strategy20_{B}.py")
parent_B = importlib.util.module_from_spec(spec_b)
spec_b.loader.exec_module(parent_B)

META = {{
    "sid": "20.{N}",
    "name": "S20.{A} x S20.{B} ({mix})",
    "concept": "{mix}",
    "logic": "{logic}",
    "sl_atr": {sl},
    "rr": {rr},
    "max_hold": {mh},
    "be_r": {be},
    "parents": ["20.{A}", "20.{B}"],
    "mix": "{mix}"
}}

def generate(df: pd.DataFrame, tf: str) -> np.ndarray:
    out_A = parent_A.generate(df, tf)
    sig_A = out_A[0] if isinstance(out_A, tuple) else out_A
    out_B = parent_B.generate(df, tf)
    sig_B = out_B[0] if isinstance(out_B, tuple) else out_B
    out = np.zeros(len(df), dtype=np.int8)
    
"""
    if mix == 'CONFIRM':
        code += f"""    s_b_buy = pd.Series(sig_B == 1).rolling(5, min_periods=1).max().astype(bool).values
    s_b_sell = pd.Series(sig_B == -1).rolling(5, min_periods=1).max().astype(bool).values
    out = np.where((sig_A == 1) & s_b_buy, 1, np.where((sig_A == -1) & s_b_sell, -1, 0))
    return out
"""
    elif mix == 'FILTER':
        code += f"""    s_b = pd.Series(sig_B).replace(0, np.nan).ffill().fillna(0).values
    out = np.where((sig_A == 1) & (s_b == 1), 1, np.where((sig_A == -1) & (s_b == -1), -1, 0))
    return out
"""
    elif mix == 'VETO':
        code += f"""    s_b_sell = pd.Series(sig_B == -1).rolling(5, min_periods=1).max().astype(bool).values
    s_b_buy = pd.Series(sig_B == 1).rolling(5, min_periods=1).max().astype(bool).values
    out = np.where((sig_A == 1) & ~s_b_sell, 1, np.where((sig_A == -1) & ~s_b_buy, -1, 0))
    return out
"""
    
    os.makedirs(f"strategy/s20.{N}", exist_ok=True)
    with open(f"strategy/s20.{N}/strategy20_{N}.py", "w", encoding="utf-8") as f:
        f.write(code)
        
    # Run backtest
    run_res = run_cmd(f"python strategy/s20_gen/run_one.py {N}")
    out = run_res.stdout + "\n" + run_res.stderr
    log_f.write(f"run_one:\n{out}\n")
    
    is_dup = "DUPLICATE" in out
    is_lookahead = "lookahead fail" in out
    is_code6 = run_res.returncode == 6
    is_crash = run_res.returncode != 0 and not is_code6
    
    if is_dup or is_lookahead or is_code6 or is_crash:
        print(f"Failed (DUP/LOOKAHEAD/CODE6/CRASH). Return code: {run_res.returncode}")
        shutil.rmtree(f"strategy/s20.{N}", ignore_errors=True)
        shutil.rmtree(f"reports/s20_{N}", ignore_errors=True)
        if not is_code6:
            # write mix log for DUP
            with open("strategy/s20_gen/mix_log.md", "a", encoding="utf-8") as f:
                date_str = datetime.datetime.now().strftime("%Y-%m-%d")
                f.write(f"| {N} | 20.{A} | 20.{B} | {mix} | {date_str} | DUPLICATE/FAIL |\n")
        # Try next pair, keep same N
        task_idx += 1
    else:
        print(f"Success/Pass/Weak/Fail (Keep). N={N} consumed.")
        # Write mix log
        with open("strategy/s20_gen/mix_log.md", "a", encoding="utf-8") as f:
            date_str = datetime.datetime.now().strftime("%Y-%m-%d")
            res_str = "PASS" if "WINNER" in out or "MIX_OK" in out else "WEAK/FAIL" # approx
            if "FAIL" in out and not "MIX_FAIL" in out: res_str = "FAIL"
            f.write(f"| {N} | 20.{A} | 20.{B} | {mix} | {date_str} | KEEP (see logs) |\n")
        
        # Repair progress
        rep_res = run_cmd("python strategy/s20_gen/progress_repair.py --check")
        log_f.write(f"repair_check:\n{rep_res.stdout}\n")
        if "(ไม่มี)" not in rep_res.stdout:
            print("Repair needed!")
            rep_do = run_cmd("python strategy/s20_gen/progress_repair.py")
            log_f.write(f"repair_do:\n{rep_do.stdout}\n")
            
        N += 1
        success_count += 1
        task_idx += 1
        
    log_f.flush()

log_f.close()
print("Batch finished")
