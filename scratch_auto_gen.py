import os
import sys
import json
import subprocess
import shutil
import random

all_good = [140,141,143,144,145,146,147,148,149,151,152,153,154,155,156,157,158,159,160,161,162,163,164,165,167,168,169,170,171,172,173,174,175,176,177,179,180,181,182,183,184,186,189,190,191,193,194,195,196,197,198,199,200,201,203,204,205,206,207,208,210,211,212,213,215,216,217,218,220,221,222,223,224,225,226,227,228,229,231,232,233,234,235,236,237,238,239,241,242,243,244,245,246,247,248,249,250,251,252,253,254,255,257,259,260,261,262,263,265,266,267,268,269,270,272,273,274,275,276,277,278,279,280,281,282,283,284,285,286,287,288,289,290,292,293,294,298,299,306,308,311,313,314,315,316,317,318,319,321,323,324,325,327,328,329,330,331,332,333,335,336,337,339,340,341,342,344,345,346,347,349,350,352,353,354,355,356,357,358,359,360,361,363,364,365,367,369,370,371,373,374,376,377,378,379,380,381,382,383,384,385,386,387,389,391,392,393,394,395,396,397,398,399,400,401,403,404,406,408,409,410,411,412,413,414,415,416,418,419,420,421,422,424,425,426,427]
random.seed(123)
random.shuffle(all_good)

template = """import sys, os
import numpy as np
import pandas as pd
import importlib.util

META = {
    "sid": "20.{{N}}",
    "name": "Mix {{A}} + {{B}} (CONFIRM)",
    "concept": "Combining {{A_name}} and {{B_name}}.",
    "logic": "Parent A ({{A_name}}) provides the primary setup. Parent B ({{B_name}}) acts as confirmation within 5 bars.",
    "parents": ["20.{{A}}", "20.{{B}}"],
    "mix": "CONFIRM",
    "sl_atr": {{sl_atr}},
    "rr": {{rr}},
    "max_hold": {{max_hold}},
    "be_r": {{be_r}}
}

def generate(df, tf):
    def load_mod(name, path):
        spec = importlib.util.spec_from_file_location(name, path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    mod_A = load_mod("mod_A", os.path.join(os.path.dirname(os.path.abspath(__file__)), f"../s20.{{A}}/strategy20_{{A}}.py"))
    mod_B = load_mod("mod_B", os.path.join(os.path.dirname(os.path.abspath(__file__)), f"../s20.{{B}}/strategy20_{{B}}.py"))

    sig_A = mod_A.generate(df, tf)
    sig_B = mod_B.generate(df, tf)
    
    out = np.zeros(len(df), dtype=np.int8)
    
    # CONFIRM method: enter on A's signal if B has same signal within last 5 bars
    for i in range(5, len(df)):
        if sig_A[i] == 1:
            if any(sig_B[i-k] == 1 for k in range(5)):
                out[i] = 1
        elif sig_A[i] == -1:
            if any(sig_B[i-k] == -1 for k in range(5)):
                out[i] = -1
                
    return out
"""

def get_meta(sid):
    try:
        with open(f'strategy/s20.{sid}/result_365d.json', encoding='utf-8') as f:
            data = json.load(f)
            return data
    except Exception as e:
        return None

def check_pair(a, b):
    res = subprocess.run([sys.executable, 'strategy/s20_gen/mix_pair_check.py', a, b], capture_output=True)
    out = res.stdout.decode('utf-8', errors='replace')
    if res.returncode == 0:
        return True, out
    return False, ""

def append_log(sid, a, b, method, verdict):
    import datetime
    date_str = datetime.datetime.now().strftime("%Y-%m-%d")
    line = f"| {sid} | 20.{a} | 20.{b} | {method} | {date_str} | {verdict} |\n"
    with open('strategy/s20_gen/mix_log.md', 'a', encoding='utf-8') as f:
        f.write(line)

N = 881
success_count = 0
TARGET = 15

A_sid = '339'
meta_A = get_meta(A_sid)
sl_atr = meta_A['params']['sl_atr']
rr = meta_A['params']['rr']
max_hold = meta_A['params']['max_hold']
be_r = meta_A['params']['be_r']
name_A = meta_A['name']

# Clean mix_log.md again if needed
lines = open('strategy/s20_gen/mix_log.md', encoding='utf-8').readlines()
with open('strategy/s20_gen/mix_log.md', 'w', encoding='utf-8') as f:
    for line in lines:
        if "ERROR (1)" in line and any(f"| {i} |" in line for i in range(881, 950)):
            continue
        f.write(line)

# Check if N has been advanced by previous run before failure
while True:
    if os.path.exists(f'strategy/s20.{N}') and os.path.exists(f'strategy/s20.{N}/result_365d.json'):
        N += 1
    elif str(N).endswith('0'):
        N += 1
    else:
        break

with open('scratch_run_report.txt', 'w', encoding='utf-8') as rep_f:
    for b in all_good:
        if success_count >= TARGET:
            break
            
        B_sid = str(b)
        if B_sid == A_sid: continue
        
        ok, mix_out = check_pair(A_sid, B_sid)
        if not ok: continue
            
        meta_B = get_meta(B_sid)
        if not meta_B: continue
        name_B = meta_B['name']
        
        while str(N).endswith('0'):
            N += 1
            
        rep_f.write(f"\\n==========================\\n")
        rep_f.write(f"SID {N} | 339 + {B_sid}\\n")
        rep_f.write(mix_out + "\\n")
            
        folder = f'strategy/s20.{N}'
        os.makedirs(folder, exist_ok=True)
        code = template.replace('{{N}}', str(N)).replace('{{A}}', A_sid).replace('{{B}}', B_sid)
        code = code.replace('{{sl_atr}}', str(sl_atr)).replace('{{rr}}', str(rr))
        code = code.replace('{{max_hold}}', str(max_hold)).replace('{{be_r}}', str(be_r))
        code = code.replace('{{A_name}}', name_A).replace('{{B_name}}', name_B)
        
        file_path = os.path.join(folder, f'strategy20_{N}.py')
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(code)
            
        res = subprocess.run([sys.executable, 'strategy/s20_gen/run_one.py', str(N)], capture_output=True)
        out = res.stdout.decode('utf-8', errors='replace')
        err = res.stderr.decode('utf-8', errors='replace')
        
        verdict = "FAIL"
        if res.returncode == 6:
            verdict = "FAIL (M3 LIMIT)"
        elif res.returncode == 7:
            verdict = "FAIL (NAME MISMATCH)"
        elif res.returncode != 0:
            verdict = f"ERROR ({res.returncode})"
            rep_f.write(f"\\n--- RUN_ONE.PY ERROR OUTPUT FOR {N} ---\\n")
            rep_f.write(out + "\\n" + err + "\\n")
        elif "DUPLICATE" in out or "Jaccard" in out:
            verdict = "DUPLICATE"
            for line in out.split('\\n'):
                if "DUPLICATE" in line and "Jaccard" in line:
                    verdict = line.strip()
                    break
        elif "lookahead ไม่ผ่าน" in out:
            verdict = "FAIL (lookahead)"
        else:
            if "มี TF ผ่าน PASS -> รันด่านสุดท้ายอัตโนมัติ" in out:
                verdict = "PASS"
                if "WINNER" in out:
                    verdict = "WINNER"
                rep_f.write(f"\\n--- RUN_ONE.PY OUTPUT FOR {N} (PASS) ---\\n")
                rep_f.write(out + "\\n")
            else:
                verdict = "WEAK/FAIL"
                
        append_log(N, A_sid, B_sid, "CONFIRM", verdict)
        rep_f.write(f"Verdict: {verdict}\\n")
        
        if "DUPLICATE" in verdict or "lookahead" in verdict or "ERROR" in verdict or res.returncode in [6, 7]:
            try:
                shutil.rmtree(folder)
                shutil.rmtree(f'reports/s20_{N}')
            except: pass
        else:
            rep = subprocess.run([sys.executable, 'strategy/s20_gen/progress_repair.py', '--check'], capture_output=True)
            rep_out = rep.stdout.decode('utf-8', errors='replace')
            rep_f.write(f"\\n--- PROGRESS REPAIR ---\\n{rep_out}\\n")
            if "ไม่มี" not in rep_out and "(äÁèÁÕ)" not in rep_out:
                subprocess.run([sys.executable, 'strategy/s20_gen/progress_repair.py'], capture_output=True)
                
            subprocess.run(['git', 'add', folder])
            success_count += 1
            N += 1
            
    rep_f.write(f"\\nCompleted {success_count} strategies. Next SID: {N}\\n")
