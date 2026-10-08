# -*- coding: utf-8 -*-
"""scratch runner: mix_pair_check -> write strategy -> run_one -> log -> progress_repair --check
usage: python artifacts/scratch/mix_runner.py N A B METHOD W "name" "concept" "logic"
"""
import sys, os, subprocess, datetime

N, A, B, METHOD, W, NAME, CONCEPT, LOGIC = sys.argv[1:9]
W = int(W)
import json as _json
if N == "auto":
    N = str(_json.load(open("strategy/s20_gen/progress.json", encoding="utf-8"))["next"])
    while N.endswith("0"):
        N = str(int(N) + 1)
env = dict(os.environ, PYTHONIOENCODING="utf-8")


def run(cmd):
    p = subprocess.run(cmd, capture_output=True, env=env, encoding="utf-8", errors="replace")
    return p.returncode, (p.stdout or "") + (p.stderr or "")


import importlib.util as _iu
_sp = _iu.spec_from_file_location("pa", f"strategy/s20.{A}/strategy20_{A}.py")
_m = _iu.module_from_spec(_sp)
sys.path.insert(0, "strategy/s20_gen")
_sp.loader.exec_module(_m)
PM = _m.META
SL, RR, MH, BE = PM["sl_atr"], PM["rr"], PM["max_hold"], PM.get("be_r", 1.0)
print("exit params from A:", SL, RR, MH, BE)
rc, out = run([sys.executable, "-X", "utf8", "strategy/s20_gen/mix_pair_check.py", A, B])
print(out)
if rc != 0:
    print("PAIR_BLOCKED")
    sys.exit(1)

if METHOD == "CONFIRM":
    body = f'''    b_buy = pd.Series(sig_b == 1).rolling(window=w, min_periods=1).max().astype(bool).values
    b_sell = pd.Series(sig_b == -1).rolling(window=w, min_periods=1).max().astype(bool).values
    final_sig[(sig_a == 1) & b_buy] = 1
    final_sig[(sig_a == -1) & b_sell] = -1'''
elif METHOD == "FILTER":
    body = '''    # state ของ B = ทิศสัญญาณล่าสุดที่ยังไม่กลับทิศ (ffill แบบ causal)
    st = pd.Series(np.where(sig_b != 0, sig_b, np.nan)).ffill().fillna(0).values
    final_sig[(sig_a == 1) & (st == 1)] = 1
    final_sig[(sig_a == -1) & (st == -1)] = -1'''
elif METHOD == "VETO":
    body = '''    b_buy = pd.Series(sig_b == 1).rolling(window=w, min_periods=1).max().astype(bool).values
    b_sell = pd.Series(sig_b == -1).rolling(window=w, min_periods=1).max().astype(bool).values
    final_sig[(sig_a == 1) & ~b_sell] = 1
    final_sig[(sig_a == -1) & ~b_buy] = -1'''
else:
    print("bad method"); sys.exit(2)

code = f'''# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind
import importlib.util

spec_a = importlib.util.spec_from_file_location("s20_{A}", "strategy/s20.{A}/strategy20_{A}.py")
mod_a = importlib.util.module_from_spec(spec_a)
spec_a.loader.exec_module(mod_a)

spec_b = importlib.util.spec_from_file_location("s20_{B}", "strategy/s20.{B}/strategy20_{B}.py")
mod_b = importlib.util.module_from_spec(spec_b)
spec_b.loader.exec_module(mod_b)

META = {{
    "sid": "20.{N}",
    "name": {NAME!r},
    "concept": {CONCEPT!r},
    "logic": {LOGIC!r},
    "parents": ["20.{A}", "20.{B}"],
    "mix": "{METHOD}",
    "sl_atr": {SL},
    "rr": {RR},
    "max_hold": {MH},
    "be_r": {BE}
}}


def generate(df, tf):
    sig_a = mod_a.generate(df, tf)
    sig_b = mod_b.generate(df, tf)
    final_sig = np.zeros_like(sig_a)
    w = {W}
{body}
    return final_sig
'''
d = f"strategy/s20.{N}"
if os.path.exists(os.path.join(d, "result_365d.json")):
    print("SID already has result -> refuse"); sys.exit(3)
os.makedirs(d, exist_ok=True)
with open(f"{d}/strategy20_{N}.py", "w", encoding="utf-8", newline="\n") as f:
    f.write(code)

rc, out = run([sys.executable, "-X", "utf8", "strategy/s20_gen/run_one.py", N])
import re, shutil
lines = out.splitlines()
keep = [l for l in lines if l.startswith(" TF ") or re.match(r"^ (M1|M5|M15|M30|H1|H4|D1) ", l) or any(k in l for k in ("TOTAL", "uniqueness", "WINNER", "FAILED", "BORDERLINE", "INSUFFICIENT", "mix_check", "null p", "บันทึกแล้ว", "PASS TFs"))]
print(f"=== N={N} {A}x{B} {METHOD} rc={rc}")
print("\n".join(keep))
open(f"artifacts/scratch/run_{N}.txt", "w", encoding="utf-8").write(out)
has_res = os.path.exists(f"strategy/s20.{N}/result_365d.json")
mj = re.search(r"max Jaccard=([0-9.]+) vs (S20\.\d+)", out)
if "DUPLICATE!" in out:
    shutil.rmtree(f"strategy/s20.{N}", ignore_errors=True)
    shutil.rmtree(f"reports/s20_{N}", ignore_errors=True)
    res = f"DUPLICATE (Jaccard {mj.group(1)} กับ {mj.group(2)})" if mj else "DUPLICATE"
    print("AUTO: DUPLICATE -> folder removed, sid reusable")
elif has_res:
    pas = re.search(r"PASS TFs: (\[[^\]]*\]|-)", out)
    res = "UNIQUE"
    if pas and pas.group(1) == "-":
        res += " (NO PASS TFs)"
    else:
        gm = re.search(r"^(WINNER|FAILED_GATE|BORDERLINE_INFO_ONLY|INSUFFICIENT_DATA)[^\n]*", out, re.M)
        mx = re.search(r"mix_check: (MIX_OK|MIX_FAIL[^\n]*)", out)
        res += f", PASS {pas.group(1) if pas else ''}, gate={gm.group(0)[:60] if gm else '?'}, {mx.group(1) if mx else ''}"
else:
    res = f"ERROR rc={rc}"
subprocess.run([sys.executable, "-X", "utf8", "artifacts/scratch/log_row.py", N, A, B, METHOD, res], capture_output=True)
print("LOGGED:", res)
chk = subprocess.run([sys.executable, "-X", "utf8", "strategy/s20_gen/progress_repair.py", "--check"], capture_output=True, encoding="utf-8").stdout
print("\n".join(l for l in chk.splitlines() if "หายจาก" in l or "บนดิสก์" in l))
