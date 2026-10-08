import json
import os
import glob
import re

ROOT = "strategy"
DONE = json.load(open("strategy/s20_gen/progress.json", encoding="utf-8")).get("done", {})

# 1. ตารางสรุปทุกตัวที่ลองในรอบนี้
print("### 1. ตารางสรุปทุกตัวที่ลองในรอบนี้")
print("| sid | ตัวแม่ | วิธีผสม | สมมติฐานย่อ | TF ที่ PASS | Net รวม | PF รวม | max Jaccard | ผล |")
print("|-----|--------|--------|-------------|-------------|---------|--------|-------------|----|")

# Read mix_log.md for all attempts today
mix_log = []
with open("strategy/s20_gen/mix_log.md", encoding="utf-8") as f:
    for line in f:
        if "| 615 |" in line or "| 616 |" in line or "| 617 |" in line:
            mix_log.append(line.strip())

for line in mix_log:
    parts = [p.strip() for p in line.split("|")]
    if len(parts) >= 7:
        sid = parts[1]
        a = parts[2]
        b = parts[3]
        mix = parts[4]
        res = parts[6]
        
        # get from result if exists
        rf = f"strategy/s20.{sid}/result_365d.json"
        tf_pass = "-"
        net = "-"
        pf = "-"
        jac = "-"
        logic = "-"
        
        if os.path.exists(rf):
            d = json.load(open(rf, encoding="utf-8"))
            tf_pass = ",".join(d.get("pass_tfs", [])) or "-"
            net = f'{d.get("total", {}).get("net", 0):.2f}'
            pf = f'{d.get("total", {}).get("pf", 0):.3f}'
            logic = d.get("logic", "-")[:40] + "..."
            jac = f'{d.get("jaccard_max", 0):.3f}'
            if not res: 
                res = "PASS" if tf_pass != "-" else "FAIL/WEAK"
        
        print(f"| {sid} | {a} x {b} | {mix} | {logic} | {tf_pass} | {net} | {pf} | {jac} | {res} |")

# 2. ตารางเทียบตัวผสมกับตัวแม่
print("\n### 2. ตารางเทียบตัวผสมกับตัวแม่ ต่อ TF (PF / OOS net / จำนวนไม้)")
print("| sid (TF) | ตัวผสม PF | ตัวผสม OOS Net | ตัวผสม ไม้ | ตัวแม่ A PF | ตัวแม่ A OOS Net | ตัวแม่ A ไม้ |")
print("|----------|-----------|----------------|------------|-------------|------------------|--------------|")
for sid in ["616", "617"]:
    rf = f"strategy/s20.{sid}/result_365d.json"
    if os.path.exists(rf):
        d = json.load(open(rf, encoding="utf-8"))
        parents = d.get("parents", [])
        if not parents: continue
        parent_a = parents[0].replace("20.", "")
        prf = f"strategy/s20.{parent_a}/result_365d.json"
        pd_data = {}
        if os.path.exists(prf):
            pd_data = json.load(open(prf, encoding="utf-8"))
        
        for tf, tdata in d.get("tfs", {}).items():
            if tdata.get("verdict") == "PASS":
                mix_pf = tdata.get("pf", 0)
                mix_oos = tdata.get("oos_net", 0)
                mix_n = tdata.get("n", 0)
                
                p_pf = pd_data.get("tfs", {}).get(tf, {}).get("pf", 0)
                p_oos = pd_data.get("tfs", {}).get(tf, {}).get("oos_net", 0)
                p_n = pd_data.get("tfs", {}).get(tf, {}).get("n", 0)
                
                print(f"| {sid} ({tf}) | {mix_pf:.3f} | {mix_oos:.2f} | {mix_n} | {p_pf:.3f} | {p_oos:.2f} | {p_n} |")

# 3. สถิติสะสมทั้งแคมเปญ
print("\n### 3. สถิติสะสมทั้งแคมเปญ")
total_tried = len(DONE)
total_pass = sum(1 for v in DONE.values() if len(v.get("pass_tfs", [])) > 0)
print(f"- จำนวนคู่ที่ลองทั้งหมด (รวมเดี่ยวและผสมที่สำเร็จ): {total_tried}")
print(f"- มี TF PASS: {total_pass}")
