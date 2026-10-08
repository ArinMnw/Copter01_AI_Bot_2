import sys
import json
import os
import subprocess
import shutil
from datetime import datetime

A_list = [339, 422]
B_list = [194, 143, 242, 168, 277, 255, 210, 237, 148, 161, 379, 342, 356]
methods = ['CONFIRM', 'FILTER', 'VETO']
log_file = 'strategy/s20_gen/mix_log.md'
prog_file = 'strategy/s20_gen/progress.json'
mix_check_script = 'scratch/mix_check_one.py'

# Get next N
with open(prog_file, 'r', encoding='utf-8') as f:
    prog = json.load(f)
N = prog['next']

with open(log_file, 'r', encoding='utf-8') as f:
    log_content = f.read()

# Logic mapping
logic_map = {
    'CONFIRM': "A ให้ทิศของเทรนด์ใหญ่, B ให้จังหวะเข้าซ้อนยืนยันภายใน 5 แท่ง เพื่อกรอง false breakout",
    'FILTER': "A ให้ทิศของเทรนด์ใหญ่, เข้าเมื่อสถานะของ B อยู่ในทิศเดียวกัน (B เป็นตัวกรอง regime)",
    'VETO': "A ให้สัญญาณหลัก, แต่ยกเว้น (Veto) ถ้า B เพิ่งให้สัญญาณทิศตรงข้ามใน 3 แท่งที่ผ่านมา (ป้องกันการสวนโมเมนตัมย่อย)"
}

generated = 0
for A in A_list:
    for B in B_list:
        if A == B: continue
        res = subprocess.run([sys.executable, 'strategy/s20_gen/mix_pair_check.py', f"20.{A}", f"20.{B}"], capture_output=True)
        if res.returncode != 0: continue
        
        for mix in methods:
            if generated >= 15: break
            if f"| {A} | {B} | {mix} |" in log_content: continue
            
            logic = logic_map[mix]
            
            code = f"""# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind
import importlib.util

META = {{
    "sid": "20.{N}",
    "name": "Mix {A} + {B} ({mix})",
    "concept": "Mix Strategy",
    "logic": "{logic}",
    "parents": ["20.{A}", "20.{B}"],
    "mix": "{mix}",
    "sl_atr": 1.5,
    "rr": 1.5,
    "max_hold": 24,
    "be_r": 1.0
}}

def generate(df, tf):
    def load_mod(name, path):
        spec = importlib.util.spec_from_file_location(name, path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    mod_A = load_mod("parent_A", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", f"s20.{A}", f"strategy20_{A}.py"))
    mod_B = load_mod("parent_B", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", f"s20.{B}", f"strategy20_{B}.py"))
    sig_A = mod_A.generate(df, tf)
    sig_B = mod_B.generate(df, tf)
"""
            if mix == "CONFIRM":
                code += """
    sig_B_bull = pd.Series(sig_B == 1).rolling(5).max() == 1
    sig_B_bear = pd.Series(sig_B == -1).rolling(5).max() == 1
    buy = (sig_A == 1) & sig_B_bull
    sell = (sig_A == -1) & sig_B_bear
"""
            elif mix == "FILTER":
                code += """
    state_B = pd.Series(sig_B).replace(0, np.nan).ffill().fillna(0)
    buy = (sig_A == 1) & (state_B == 1)
    sell = (sig_A == -1) & (state_B == -1)
"""
            elif mix == "VETO":
                code += """
    sig_B_bear_recent = pd.Series(sig_B == -1).rolling(3).max() == 1
    sig_B_bull_recent = pd.Series(sig_B == 1).rolling(3).max() == 1
    buy = (sig_A == 1) & ~sig_B_bear_recent
    sell = (sig_A == -1) & ~sig_B_bull_recent
"""
            code += """
    return ind.sig_from(buy, sell)
"""
            
            os.makedirs(f"strategy/s20.{N}", exist_ok=True)
            with open(f"strategy/s20.{N}/strategy20_{N}.py", "w", encoding="utf-8") as f:
                f.write(code)
            
            print(f"Running N={N}, A={A}, B={B}, MIX={mix}")
            res_run = subprocess.run([sys.executable, "strategy/s20_gen/run_one.py", str(N)], capture_output=True)
            
            today = datetime.now().strftime("%Y-%m-%d")
            out_str = res_run.stdout.decode('utf-8', errors='replace') + res_run.stderr.decode('utf-8', errors='replace')
            
            if "DUPLICATE" in out_str:
                verdict = "DUPLICATE"
                max_jac = "0"
                for line in out_str.split("\\n"):
                    if "DUPLICATE (Max Jaccard" in line:
                        try:
                            max_jac = line.split("Jaccard ")[1].replace(")", "").strip()
                        except:
                            pass
                        verdict = f"DUPLICATE (Max Jaccard {max_jac})"
                
                with open(log_file, "a", encoding="utf-8") as f:
                    f.write(f"| {N} | 20.{A} | 20.{B} | {mix} | {today} | {verdict} |\\n")
                print(f"  Result: {verdict}")
                shutil.rmtree(f"strategy/s20.{N}", ignore_errors=True)
                shutil.rmtree(f"reports/s20_{N}", ignore_errors=True)
                continue
            elif "lookahead" in out_str.lower() and "fail" in out_str.lower():
                verdict = "FAIL (lookahead)"
                with open(log_file, "a", encoding="utf-8") as f:
                    f.write(f"| {N} | 20.{A} | 20.{B} | {mix} | {today} | {verdict} |\\n")
                shutil.rmtree(f"strategy/s20.{N}", ignore_errors=True)
                shutil.rmtree(f"reports/s20_{N}", ignore_errors=True)
                continue
            
            # Not DUPLICATE
            verdict_overall = "FAIL"
            if os.path.exists(f"strategy/s20.{N}/result_365d.json"):
                with open(f"strategy/s20.{N}/result_365d.json", "r", encoding="utf-8") as f:
                    res_json = json.load(f)
                pass_tfs = [tf for tf, d in res_json.get("tfs", {}).items() if d.get("verdict") == "PASS"]
                weak_tfs = [tf for tf, d in res_json.get("tfs", {}).items() if d.get("verdict") == "WEAK"]
                if pass_tfs:
                    verdict_overall = f"PASS ({','.join(pass_tfs)})"
                elif weak_tfs:
                    verdict_overall = f"WEAK"
            else:
                print("Error: result_365d.json not generated.")
                print(out_str)
                # Break to avoid infinite loop of failures
                break
            
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(f"| {N} | 20.{A} | 20.{B} | {mix} | {today} | {verdict_overall} |\\n")
            print(f"  Result: {verdict_overall}")
            
            # run repair
            res_rep = subprocess.run([sys.executable, "strategy/s20_gen/progress_repair.py", "--check"], capture_output=True, text=True, errors='replace')
            if "(ไม่มี)" not in res_rep.stdout.split("หายจาก progress.json")[1]:
                print("Repairing progress...")
                subprocess.run([sys.executable, "strategy/s20_gen/progress_repair.py"], capture_output=True)
            
            # if PASS run final gate
            if "PASS" in verdict_overall:
                print(f"  Running final_gate for N={N}")
                subprocess.run([sys.executable, "strategy/s20_gen/final_gate.py", str(N)])
                subprocess.run([sys.executable, "scratch/mix_check_one.py", str(N)])
            
            generated += 1
            N += 1

print(f"Done. Generated {generated} strategies.")
