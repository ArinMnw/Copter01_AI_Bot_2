import os, sys, subprocess, json, shutil

env = os.environ.copy()
env["PYTHONIOENCODING"] = "utf-8"

pairs_to_try = [
    ("339", "766"), ("422", "766"),
    ("339", "765"), ("422", "765"),
    ("339", "762"), ("422", "762"),
    ("339", "761"), ("422", "761"),
    ("339", "759"), ("422", "759"),
    ("339", "758"), ("422", "758"),
    ("339", "757"), ("422", "757"),
    ("339", "756"), ("422", "756"),
    ("339", "754"), ("422", "754"),
    ("339", "753"), ("422", "753"),
]
methods = ["CONFIRM", "FILTER", "VETO"]
target_count = 15
success_count = 0

current_N = 771
mix_log_file = "strategy/s20_gen/mix_log.md"

def append_mix_log(n, a, b, method, res):
    with open(mix_log_file, "a", encoding="utf-8") as f:
        f.write(f"| {n} | 20.{a} | 20.{b} | {method} | 2026-10-07 | {res} |\n")

pass_outputs = []

for (a, b) in pairs_to_try:
    for method in methods:
        if success_count >= target_count:
            break
            
        # 1. Pre-check mix pair
        res = subprocess.run(["python", "strategy/s20_gen/mix_pair_check.py", a, b], capture_output=True, env=env, text=True, encoding="utf-8")
        if res.returncode != 0:
            print(f"Skipping {a}+{b} (exhausted mix_pair_check)")
            continue
            
        while str(current_N).endswith("0"):
            current_N += 1
            
        N_str = str(current_N)
        print(f"\n=======================================================")
        print(f"--- Running S20.{N_str}: {a} + {b} ({method}) ---")
        
        # 2. Generate code
        os.makedirs(f"strategy/s20.{N_str}", exist_ok=True)
        code = f"""# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import ind
import importlib.util

def load_parent(sid):
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", f"s20.{{sid}}", f"strategy20_{{sid}}.py")
    spec = importlib.util.spec_from_file_location(f"strategy20_{{sid}}", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

parent_a = load_parent("{a}")
parent_b = load_parent("{b}")

META = {{
    "sid": "20.{N_str}",
    "name": "Mixed {a} x {b} {method}",
    "concept": "{method} mix of 20.{a} and 20.{b}",
    "logic": "{a} provides the primary setup, {b} acts as {method} to improve timing.",
    "parents": ["20.{a}", "20.{b}"],
    "mix": "{method}",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}}

def generate(df, tf):
    sig_a = parent_a.generate(df, tf)
    sig_b = parent_b.generate(df, tf)
"""
        if method == "CONFIRM":
            code += """
    import pandas as pd
    buy_a = (sig_a == 1)
    sell_a = (sig_a == -1)
    
    b_buy_recent = pd.Series(sig_b == 1).rolling(4, min_periods=1).max() > 0
    b_sell_recent = pd.Series(sig_b == -1).rolling(4, min_periods=1).max() > 0
    
    buy_sig = buy_a & b_buy_recent
    sell_sig = sell_a & b_sell_recent
    return ind.sig_from(buy_sig, sell_sig)
"""
        elif method == "FILTER":
            code += """
    import pandas as pd
    buy_a = (sig_a == 1)
    sell_a = (sig_a == -1)
    
    b_state = pd.Series(sig_b).replace(0, np.nan).ffill().fillna(0)
    
    buy_sig = buy_a & (b_state == 1)
    sell_sig = sell_a & (b_state == -1)
    return ind.sig_from(buy_sig, sell_sig)
"""
        elif method == "VETO":
            code += """
    import pandas as pd
    buy_a = (sig_a == 1)
    sell_a = (sig_a == -1)
    
    b_buy_recent = pd.Series(sig_b == 1).rolling(4, min_periods=1).max() > 0
    b_sell_recent = pd.Series(sig_b == -1).rolling(4, min_periods=1).max() > 0
    
    buy_sig = buy_a & ~b_sell_recent
    sell_sig = sell_a & ~b_buy_recent
    return ind.sig_from(buy_sig, sell_sig)
"""
        with open(f"strategy/s20.{N_str}/strategy20_{N_str}.py", "w", encoding="utf-8") as f:
            f.write(code)
            
        # 3. Run one
        res_run = subprocess.run(["python", "strategy/s20_gen/run_one.py", N_str], capture_output=True, env=env, text=True, encoding="utf-8")
        out = res_run.stdout + "\n" + res_run.stderr
        
        is_duplicate = "DUPLICATE" in out or "Jaccard > 0.5" in out
        is_lookahead = "lookahead" in out.lower()
        
        if is_duplicate or is_lookahead or res_run.returncode == 6 or res_run.returncode == 7:
            result_str = "DUPLICATE" if is_duplicate else ("lookahead-fail" if is_lookahead else f"FAIL (exit {res_run.returncode})")
            append_mix_log(N_str, a, b, method, result_str)
            print(f"[{result_str}] Cleaning up S20.{N_str}")
            shutil.rmtree(f"strategy/s20.{N_str}", ignore_errors=True)
            shutil.rmtree(f"reports/s20_{N_str}", ignore_errors=True)
            if res_run.returncode in [6, 7]:
                current_N += 1
            success_count += 1
        else:
            verdict = "FAIL"
            if "WINNER" in out: verdict = "WINNER"
            elif "PASS" in out: verdict = "PASS"
            elif "WEAK" in out: verdict = "WEAK"
            append_mix_log(N_str, a, b, method, verdict)
            
            print(f"[{verdict}] Running progress_repair...")
            if verdict in ["PASS", "WINNER"]:
                pass_outputs.append((N_str, a, b, method, out))
                
            repair_out = subprocess.run(["python", "strategy/s20_gen/progress_repair.py", "--check"], capture_output=True, env=env, text=True, encoding="utf-8")
            print(repair_out.stdout)
            if "(ไม่มี)" not in repair_out.stdout:
                print("Repairing progress...")
                subprocess.run(["python", "strategy/s20_gen/progress_repair.py"], text=True, encoding="utf-8")
            
            subprocess.run(["git", "add", f"strategy/s20.{N_str}/"])
            current_N += 1
            success_count += 1

print("\n--- DONE ---")
with open("scratch/pass_outputs.txt", "w", encoding="utf-8") as f:
    for p in pass_outputs:
        f.write(f"\n================ S20.{p[0]} ({p[1]}+{p[2]} {p[3]}) ================\n")
        f.write(p[4])
