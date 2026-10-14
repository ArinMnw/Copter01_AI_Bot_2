import json
import os

sids = [881, 882, 883, 884, 885, 886, 887, 888, 889, 891, 892, 893, 894, 895, 896]
print("## 1. ตารางสรุปทุกตัวที่ลองในรอบนี้")
print("| sid | ตัวแม่ | วิธีผสม | สมมติฐานย่อ | TF ที่ PASS | Net รวม | PF รวม | max Jaccard | ผล |")
print("|---|---|---|---|---|---|---|---|---|")

for sid in sids:
    try:
        with open(f"strategy/s20.{sid}/result_365d.json", encoding="utf-8") as f:
            data = json.load(f)
        parents = data.get("parents", [])
        mix = data.get("mix", "CONFIRM")
        logic = data.get("logic", "Parent A setup, B confirms")
        pass_tfs = ", ".join(data.get("pass_tfs", [])) if data.get("pass_tfs") else "-"
        total = data.get("total", {})
        net = total.get("net", 0)
        pf = total.get("pf", 0)
        uniqueness = data.get("uniqueness", {})
        max_jaccard = uniqueness.get("max_jaccard", 0)
        verdict = "FAIL" if not data.get("pass_tfs") else "PASS"
        parent_str = " + ".join([p.replace("20.", "") for p in parents])
        
        print(f"| {sid} | {parent_str} | {mix} | {logic[:30]}... | {pass_tfs} | {net:.2f} | {pf:.2f} | {max_jaccard:.3f} | {verdict} |")
    except Exception as e:
        print(f"| {sid} | Error reading JSON: {e} |")

print("\n## 2. ตารางเทียบตัวผสมกับตัวแม่ ต่อ TF (เฉพาะ PASS/WEAK ของตัวผสม)")
print("| sid | TF | Parent A (Net/PF/N) | Parent B (Net/PF/N) | Mix (Net/PF/N) |")
print("|---|---|---|---|---|")

for sid in sids:
    try:
        with open(f"strategy/s20.{sid}/result_365d.json", encoding="utf-8") as f:
            data = json.load(f)
        parents = data.get("parents", [])
        if not parents: continue
        pA = parents[0].replace("20.", "")
        pB = parents[1].replace("20.", "")
        
        with open(f"strategy/s20.{pA}/result_365d.json", encoding="utf-8") as fA:
            dataA = json.load(fA)
        with open(f"strategy/s20.{pB}/result_365d.json", encoding="utf-8") as fB:
            dataB = json.load(fB)
            
        for tf, d in data.get("tf", {}).items():
            if d.get("verdict") in ["PASS", "WEAK"]:
                dA = dataA.get("tf", {}).get(tf, {})
                dB = dataB.get("tf", {}).get(tf, {})
                
                netM = d.get("oos", {}).get("net", 0)
                pfM = d.get("pf", 0)
                nM = d.get("n", 0)
                
                netA = dA.get("oos", {}).get("net", 0) if dA else 0
                pfA = dA.get("pf", 0) if dA else 0
                nA = dA.get("n", 0) if dA else 0
                
                netB = dB.get("oos", {}).get("net", 0) if dB else 0
                pfB = dB.get("pf", 0) if dB else 0
                nB = dB.get("n", 0) if dB else 0
                
                print(f"| {sid} | {tf} | {netA:.2f} / {pfA:.2f} / {nA} | {netB:.2f} / {pfB:.2f} / {nB} | {netM:.2f} / {pfM:.2f} / {nM} |")
    except Exception as e:
        pass

print("\n## 3. สถิติสะสมทั้งแคมเปญ")
try:
    with open("strategy/s20_gen/progress.json", encoding="utf-8") as f:
        prog = json.load(f)
        entries = len(prog.get("entries", {}))
        print(f"- จำนวนคู่ที่ลองทั้งหมด (sid ใน progress.json): {entries}")
except Exception as e:
    pass

winners = 0
with open("strategy/s20_gen/mix_log.md", encoding="utf-8") as f:
    for line in f:
        if "WINNER" in line:
            winners += 1
print(f"- ผู้ชนะจาก mix_log.md: {winners}")

