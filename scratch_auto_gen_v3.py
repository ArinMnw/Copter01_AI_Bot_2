import os
import sys
import json
import subprocess
import shutil
import random
import ast

all_good = [140,141,143,144,145,146,147,148,149,151,152,153,154,155,156,157,158,159,160,161,162,163,164,165,167,168,169,170,171,172,173,174,175,176,177,179,180,181,182,183,184,186,189,190,191,193,194,195,196,197,198,199,200,201,203,204,205,206,207,208,210,211,212,213,215,216,217,218,220,221,222,223,224,225,226,227,228,229,231,232,233,234,235,236,237,238,239,241,242,243,244,245,246,247,248,249,250,251,252,253,254,255,257,259,260,261,262,263,265,266,267,268,269,270,272,273,274,275,276,277,278,279,280,281,282,283,284,285,286,287,288,289,290,292,293,294,298,299,306,308,311,313,314,315,316,317,318,319,321,323,324,325,327,328,329,330,331,332,333,335,336,337,339,340,341,342,344,345,346,347,349,350,352,353,354,355,356,357,358,359,360,361,363,364,365,367,369,370,371,373,374,376,377,378,379,380,381,382,383,384,385,386,387,389,391,392,393,394,395,396,397,398,399,400,401,403,404,406,408,409,410,411,412,413,414,415,416,418,419,420,421,422,424,425,426,427]
random.seed(456)
random.shuffle(all_good)

template = """import sys, os
import numpy as np
import pandas as pd
import importlib.util

META = {
    "sid": "20.{{N}}",
    "name": "Mix {{A}} + {{B}} ({{METHOD}})",
    "concept": "Combining {{A_name}} and {{B_name}}.",
    "logic": "Parent A ({{A_name}}) provides the primary setup. Parent B ({{B_name}}) acts as {{METHOD}}.",
    "parents": ["20.{{A}}", "20.{{B}}"],
    "mix": "{{METHOD}}",
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
    
{{LOGIC}}
                
    return out
"""

logic_blocks = {
    "CONFIRM": """    # CONFIRM method: enter on A's signal if B has same signal within last 5 bars
    for i in range(5, len(df)):
        if sig_A[i] == 1:
            if any(sig_B[i-k] == 1 for k in range(5)):
                out[i] = 1
        elif sig_A[i] == -1:
            if any(sig_B[i-k] == -1 for k in range(5)):
                out[i] = -1""",
                
    "FILTER": """    # FILTER method: A provides signal, but B's CURRENT STATE must align
    state_b = pd.Series(sig_B).replace(0, np.nan).ffill().fillna(0).values
    
    out[(sig_A == 1) & (state_b == 1)] = 1
    out[(sig_A == -1) & (state_b == -1)] = -1""",
    
    "VETO": """    # VETO method: enter on A's signal UNLESS B has opposite signal in last 3 bars
    for i in range(3, len(df)):
        if sig_A[i] == 1:
            if -1 not in sig_B[i-3:i+1]:
                out[i] = 1
        elif sig_A[i] == -1:
            if 1 not in sig_B[i-3:i+1]:
                out[i] = -1"""
}

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
    methods = []
    for line in out.split('\\n'):
        if "วิธีผสมที่ยังไม่ลองกับคู่นี้" in line:
            arr_str = line.split(":")[-1].strip()
            try:
                methods = ast.literal_eval(arr_str)
            except:
                pass
    if res.returncode == 0:
        return True, out, methods
    return False, "", []

def append_log(sid, a, b, method, verdict):
    import datetime
    date_str = datetime.datetime.now().strftime("%Y-%m-%d")
    line = f"| {sid} | 20.{a} | 20.{b} | {method} | {date_str} | {verdict} |\\n"
    with open('strategy/s20_gen/mix_log.md', 'a', encoding='utf-8') as f:
        f.write(line)

N = 897
success_count = 0
TARGET_WINNERS = 1
winners_found = 0

A_sid = '339'
meta_A = get_meta(A_sid)
sl_atr = meta_A['params']['sl_atr']
rr = meta_A['params']['rr']
max_hold = meta_A['params']['max_hold']
be_r = meta_A['params']['be_r']
name_A = meta_A['name']

# Find starting N
while True:
    if os.path.exists(f'strategy/s20.{N}') and os.path.exists(f'strategy/s20.{N}/result_365d.json'):
        N += 1
    elif str(N).endswith('0'):
        N += 1
    else:
        break

with open('scratch_run_report.txt', 'w', encoding='utf-8') as rep_f:
    for b in all_good:
        if winners_found >= TARGET_WINNERS:
            break
            
        B_sid = str(b)
        if B_sid == A_sid: continue
        
        ok, mix_out, methods = check_pair(A_sid, B_sid)
        if not ok or not methods: continue
            
        meta_B = get_meta(B_sid)
        if not meta_B: continue
        name_B = meta_B['name']
        
        # Test each method in ['CONFIRM', 'FILTER', 'VETO'] that is available
        for method in ['CONFIRM', 'FILTER', 'VETO']:
            if winners_found >= TARGET_WINNERS:
                break
                
            if method not in methods:
                continue
                
            while str(N).endswith('0'):
                N += 1
                
            print(f"Testing SID {N} | 339 + {B_sid} ({method})", flush=True)
            rep_f.write(f"\\n==========================\\n")
            rep_f.write(f"SID {N} | 339 + {B_sid} ({method})\\n")
            rep_f.flush()
                
            folder = f'strategy/s20.{N}'
            os.makedirs(folder, exist_ok=True)
            
            code = template.replace('{{N}}', str(N)).replace('{{A}}', A_sid).replace('{{B}}', B_sid)
            code = code.replace('{{METHOD}}', method)
            code = code.replace('{{LOGIC}}', logic_blocks[method])
            code = code.replace('{{sl_atr}}', str(sl_atr)).replace('{{rr}}', str(rr))
            code = code.replace('{{max_hold}}', str(max_hold)).replace('{{be_r}}', str(be_r))
            code = code.replace('{{A_name}}', name_A).replace('{{B_name}}', name_B)
            
            file_path = os.path.join(folder, f'strategy20_{N}.py')
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(code)
                
            res = subprocess.run([sys.executable, 'strategy/s20_gen/run_one.py', str(N)], capture_output=True)
            out = res.stdout.decode('utf-8', errors='replace')
            err = res.stderr.decode('utf-8', errors='replace')
            
            # Determine verdict properly
            verdict = ""
            delete_folder = False
            
            if res.returncode == 0 or res.returncode == 1:
                # Valid PASS, WEAK, or NO_TRADE (but if it's NO_TRADE it shouldn't be PASS/WEAK)
                if "มี TF ผ่าน PASS" in out:
                    verdict = "PASS"
                    if "WINNER" in out: verdict = "WINNER"
                else:
                    verdict = "WEAK/FAIL"
            elif res.returncode == 2:
                verdict = "DUPLICATE"
                for line in out.split('\\n'):
                    if "DUPLICATE" in line and "Jaccard" in line:
                        verdict = line.strip()
                        break
                delete_folder = True
            elif res.returncode == 4:
                verdict = "FAIL (lookahead)"
                delete_folder = True
            elif res.returncode == 5:
                verdict = "FAIL (INSUFFICIENT_DATA)"
                delete_folder = True
            elif res.returncode == 6:
                verdict = "FAIL (M3 LIMIT)"
                delete_folder = True
            elif res.returncode == 7:
                verdict = "FAIL (NAME MISMATCH)"
                delete_folder = True
            else:
                verdict = f"ERROR ({res.returncode})"
                delete_folder = True
                
            rep_f.write(f"Verdict: {verdict}\\n")
            append_log(N, A_sid, B_sid, method, verdict)
            
            if delete_folder:
                try:
                    shutil.rmtree(folder)
                    shutil.rmtree(f'reports/s20_{N}')
                except: pass
            else:
                rep_f.write(f"\\n--- KEEPING S20.{N} ---\\n")
                rep_f.flush()
                # Run progress repair
                rep = subprocess.run([sys.executable, 'strategy/s20_gen/progress_repair.py', '--check'], capture_output=True)
                rep_out = rep.stdout.decode('utf-8', errors='replace')
                if "ไม่มี" not in rep_out and "(äÁèÁÕ)" not in rep_out:
                    subprocess.run([sys.executable, 'strategy/s20_gen/progress_repair.py'], capture_output=True)
                    
                subprocess.run(['git', 'add', folder])
                success_count += 1
                
                # Check mix_check rule 14
                mix_ok = False
                mc_path = f'strategy/s20.{N}/mix_check.txt'
                if os.path.exists(mc_path):
                    if "MIX_OK" in open(mc_path, encoding='utf-8').read():
                        mix_ok = True
                if verdict == "WINNER" and mix_ok:
                    winners_found += 1
                    print(f"!!! FOUND WINNER AT S20.{N} !!!")
                    
                N += 1
                
    rep_f.write(f"\\nCompleted {success_count} strategies. Found {winners_found} winners. Next SID: {N}\\n")
