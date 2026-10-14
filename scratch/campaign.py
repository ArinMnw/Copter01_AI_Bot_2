import json
import os
import subprocess
import shutil
import time
import sys

def read_json(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def write_json(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=1)

def run_cmd(cmd, capture=False):
    print(f"RUNNING: {' '.join(cmd)}")
    if capture:
        # Avoid cp874 decoding errors by using bytes and decoding with errors='replace'
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        out = res.stdout.decode('utf-8', errors='replace')
        return res.returncode, out
    else:
        res = subprocess.run(cmd)
        return res.returncode, ""

pairs_to_try = [
    # 1. Elder Impulse + Quadrature Regression (Trend + Reversal Veto)
    (143, 277, "VETO", "143 provides strong trend momentum, vetoed if 277 detects a sharp mathematical curvature reversal, avoiding late entries."),
    # 2. Inside-Bar Mother-Bar + Ultimate Osc (Breakout + Momentum Confirm)
    (148, 161, "CONFIRM", "148 breakout confirmed by 161 momentum shift, ensuring we enter on a strong thrust."),
    # 3. Super Smoother + Rainbow MA (Smooth Trend + Alignment)
    (168, 242, "FILTER", "168 trades only taken when 242 Rainbow MA alignment is fully established, ensuring a mature trend."),
    # 4. Accelerator Osc + Hikkake (Momentum + False Breakout Veto)
    (210, 255, "VETO", "210 momentum entries vetoed if 255 detects a false breakout pattern (Hikkake) recently, avoiding traps."),
    # 5. FRAMA + ADX (Trend + Volatility)
    (237, 342, "CONFIRM", "237 FRAMA cross confirmed by 342 ADX volatility breakout, validating the new trend strength."),
    # 6. Quad-Reg + Bollinger Z-Score (Reversal + Volatility)
    (277, 356, "CONFIRM", "277 curvature reversal confirmed by 356 volatility expansion, ensuring sufficient energy for the reversal move."),
    # 7. Elder Impulse + Rainbow MA (Momentum + Trend Filter)
    (143, 242, "FILTER", "143 momentum trades only taken if 242 Rainbow MA indicates the higher timeframe trend is aligned."),
    # 8. Inside-Bar + FRAMA (Breakout + Trend Confirm)
    (148, 237, "CONFIRM", "148 breakout confirmed by 237 FRAMA cross, filtering out noise in choppy markets."),
    # 9. Super Smoother + ADX (Smooth Trend + Volatility Filter)
    (168, 342, "FILTER", "168 trades only taken if 342 indicates a high ADX environment, filtering out choppy sideways markets."),
    # 10. Accelerator + Quad-Reg (Momentum + Reversal Veto)
    (210, 277, "VETO", "210 momentum continuation is vetoed if 277 detects an immediate curvature reversal."),
    # 11. Hikkake + Rainbow MA (Reversal + Trend Filter)
    (255, 242, "FILTER", "255 false breakout reversal only traded if 242 Rainbow MA confirms the broader trend is aligned with the reversal."),
    # 12. Elder Impulse + Bollinger Z-Score (Momentum + Volatility Confirm)
    (143, 356, "CONFIRM", "143 momentum entry confirmed by 356 volatility expansion, ensuring sufficient energy for the move."),
    # 13. Inside-Bar + Super Smoother (Breakout + Smooth Trend Filter)
    (148, 168, "FILTER", "148 breakout trades only taken in the direction of the smooth 168 trend state."),
    # 14. Ultimate Osc + FRAMA (Momentum + Trend Filter)
    (161, 237, "FILTER", "161 momentum shift only traded if 237 FRAMA confirms the trend direction."),
    # 15. ADX + Hikkake (Volatility + False Breakout Veto)
    (342, 255, "VETO", "342 volatility breakout vetoed if 255 detects a false breakout pattern (Hikkake), avoiding fakeouts.")
]

def generate_strategy_code(sid, a, b, mix, logic):
    # Need to load parents to get sl_atr, rr, max_hold, be_r. We will use parent A's exit params.
    # To do this safely, we can just read the python file of parent A and extract META.
    import ast
    parent_a_file = f"strategy/s20.{a}/strategy20_{a}.py"
    with open(parent_a_file, 'r', encoding='utf-8') as f:
        tree = ast.parse(f.read())
    
    meta_a = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            if isinstance(node.targets[0], ast.Name) and node.targets[0].id == "META":
                meta_a = ast.literal_eval(node.value)
                break
                
    sl_atr = meta_a.get("sl_atr", 2.0)
    rr = meta_a.get("rr", 1.5)
    max_hold = meta_a.get("max_hold", 30)
    be_r = meta_a.get("be_r", 1.0)
    name_a = meta_a.get("name", f"S20.{a}")
    name_b = f"S20.{b}"
    
    # Simple name
    new_name = f"Mixed {a} x {b} {mix}"
    
    code = f'''import numpy as np
import pandas as pd
import importlib.util

def load_strategy(sid):
    path = f'strategy/s20.{{sid}}/strategy20_{{sid}}.py'
    spec = importlib.util.spec_from_file_location(f"s20_{{sid}}", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

parent_a = load_strategy("{a}")
parent_b = load_strategy("{b}")

META = {{
    "sid": "20.{sid}",
    "name": "{new_name}",
    "concept": "Hybrid Strategy",
    "logic": "{logic}",
    "parents": ["20.{a}", "20.{b}"],
    "mix": "{mix}",
    "sl_atr": {sl_atr},
    "rr": {rr},
    "max_hold": {max_hold},
    "be_r": {be_r}
}}

def generate(df, tf) -> np.ndarray:
    sig_a = parent_a.generate(df, tf)
    sig_b = parent_b.generate(df, tf)
    
    out = np.zeros(len(df), dtype=np.int8)
    
'''
    if mix == "CONFIRM":
        code += '''    # CONFIRM: เข้าเมื่อ A มีสัญญาณ และ B มีสัญญาณทิศเดียวกันใน 3 แท่งล่าสุด
    for i in range(3, len(df)):
        if sig_a[i] == 1:
            if 1 in sig_b[i-3:i+1]:
                out[i] = 1
        elif sig_a[i] == -1:
            if -1 in sig_b[i-3:i+1]:
                out[i] = -1
'''
    elif mix == "FILTER":
        code += '''    # FILTER: เข้าตาม A เฉพาะเมื่อ B ชี้ไปทิศเดียวกัน
    # หาทิศทางล่าสุดของ B
    state_b = np.zeros(len(df), dtype=np.int8)
    curr = 0
    for i in range(len(df)):
        if sig_b[i] != 0:
            curr = sig_b[i]
        state_b[i] = curr
        
    for i in range(len(df)):
        if sig_a[i] == 1 and state_b[i] == 1:
            out[i] = 1
        elif sig_a[i] == -1 and state_b[i] == -1:
            out[i] = -1
'''
    elif mix == "VETO":
        code += '''    # VETO: เข้าตาม A ยกเว้นเมื่อ B ให้สัญญาณตรงข้ามภายใน 3 แท่งที่ผ่านมา
    for i in range(3, len(df)):
        if sig_a[i] == 1:
            if -1 not in sig_b[i-3:i+1]:
                out[i] = 1
        elif sig_a[i] == -1:
            if 1 not in sig_b[i-3:i+1]:
                out[i] = -1
'''
    code += '''    return out
'''
    return code

def main():
    prog = read_json("strategy/s20_gen/progress.json")
    next_sid = prog["next"]
    
    completed = 0
    
    for (a, b, mix, logic) in pairs_to_try:
        if completed >= 15:
            break
            
        print(f"\\n{'='*50}\\nTrying {a} + {b} ({mix})\\n{'='*50}")
        
        while next_sid % 10 == 0:
            next_sid += 1
            
        # Check if pair is allowed
        ret, out = run_cmd([sys.executable, "strategy/s20_gen/mix_pair_check.py", str(a), str(b)], capture=True)
        if ret != 0:
            print(f"Skipping {a}+{b} due to mix_pair_check exit {ret}")
            continue
            
        sid = next_sid
        folder = f"strategy/s20.{sid}"
        os.makedirs(folder, exist_ok=True)
        code_path = f"{folder}/strategy20_{sid}.py"
        
        code = generate_strategy_code(sid, a, b, mix, logic)
        with open(code_path, 'w', encoding='utf-8') as f:
            f.write(code)
            
        # Run backtest
        ret, out = run_cmd([sys.executable, "strategy/s20_gen/run_one.py", str(sid)], capture=True)
        
        # Determine result for mix_log
        result_str = "UNKNOWN"
        if "DUPLICATE" in out:
            result_str = "DUPLICATE"
        elif "FAIL" in out or "FAILED_GATE" in out or "FAILED" in out:
            result_str = "FAIL"
        elif "WINNER" in out:
            result_str = "WINNER"
        elif "WEAK" in out:
            result_str = "WEAK"
        elif "PASS" in out:
            result_str = "PASS-ตกด่าน" # If it says PASS but not WINNER
            
        if "lookahead audit ok: False" in out:
            result_str = "lookahead-fail"
            
        # Write to mix_log.md
        with open("strategy/s20_gen/mix_log.md", "a", encoding="utf-8") as f:
            date_str = time.strftime("%Y-%m-%d")
            f.write(f"| {sid} | 20.{a} | 20.{b} | {mix} | {date_str} | {result_str} |\\n")
            
        print(f"Result for {sid}: {result_str}")
        
        if result_str == "DUPLICATE" or result_str == "lookahead-fail":
            # Delete and reuse sid? Prompt allows it, but to be safe we just delete and move to next sid.
            print(f"Deleting duplicate/failed {sid}...")
            shutil.rmtree(folder, ignore_errors=True)
            report_folder = f"reports/s20_{sid}"
            shutil.rmtree(report_folder, ignore_errors=True)
            # Re-use sid? The prompt says "ใช้เลขเดิมกับคู่ใหม่ได้", let's just NOT increment next_sid here.
            # So next iteration uses the same next_sid.
            pass 
        else:
            # Check progress_repair.py
            print("Running progress_repair.py --check...")
            r_ret, r_out = run_cmd([sys.executable, "strategy/s20_gen/progress_repair.py", "--check"], capture=True)
            if "หายจาก progress.json" in r_out and "(ไม่มี)" not in r_out:
                print("Missing in progress.json! Repairing...")
                run_cmd([sys.executable, "strategy/s20_gen/progress_repair.py"])
                
            # Git add
            run_cmd(["git", "add", f"strategy/s20.{sid}/"])
            
            # Increment next_sid for next pair
            next_sid += 1
            completed += 1

if __name__ == "__main__":
    main()
