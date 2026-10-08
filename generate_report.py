import json
import os
import glob
import re

SIDS_RUN = [766, 767, 768, 769]
# We also had some DUPLICATE or lookahead-fail? No, the log says "Success/Pass/Weak/Fail (Keep)" for all of them. So no DUPLICATEs were discarded.

print("--- 1. ตารางสรุปทุกตัวที่ลองในรอบนี้ ---")
print("| sid | ตัวแม่ | วิธีผสม | สมมติฐานย่อ | TF ที่ PASS | Net รวม | PF รวม | max Jaccard | ผล |")
print("|---|---|---|---|---|---|---|---|---|")

for n in SIDS_RUN:
    p = f"strategy/s20.{n}/result_365d.json"
    if not os.path.exists(p):
        print(f"| {n} | ERROR | FILE NOT FOUND | | | | | | |")
        continue
    with open(p, "r", encoding="utf-8") as f:
        res = json.load(f)
    
    name = res.get('name', '')
    import re
    m = re.search(r'S20\.(\d+)[ x]+S20\.(\d+)', name)
    a_id = m.group(1) if m else ""
    b_id = m.group(2) if m else ""
    parents_str = f"{a_id} + {b_id}" if a_id else "-"
    mix_m = res.get('concept', '')
    logic = name
    if len(logic) > 30: logic = logic[:30] + "..."
    
    pass_tfs = ",".join(res.get('pass_tfs', [])) or "-"
    net = f"{res.get('total', {}).get('net', 0):.2f}"
    pf = f"{res.get('total', {}).get('pf', 0):.3f}"
    
    # get max Jaccard
    jaccards = []
    for tf, tf_data in res.get('tf', {}).items():
        if tf_data and 'max_jaccard' in tf_data:
            jaccards.append(tf_data['max_jaccard'])
    max_j = res.get('uniqueness', {}).get('max_jaccard', 0)
    
    verdict = res.get('verdict', 'FAIL')
    if pass_tfs != "-":
        verdict = "PASS"
    print(f"| S20.{n} | {parents_str} | {mix_m} | {logic} | {pass_tfs} | {net} | {pf} | {max_j:.3f} | {verdict} |")


print("\n--- 2. ตารางเทียบตัวผสมกับตัวแม่ ต่อ TF (PF / OOS net / จำนวนไม้) ---")
print("| sid (Mix) | TF | Mix PF | Mix OOS Net | Mix Trades | A PF | A OOS Net | A Trades | B PF | B OOS Net | B Trades |")
print("|---|---|---|---|---|---|---|---|---|---|---|")

for n in SIDS_RUN:
    p = f"strategy/s20.{n}/result_365d.json"
    if not os.path.exists(p): continue
    with open(p, "r", encoding="utf-8") as f:
        res = json.load(f)
    
    name = res.get('name', '')
    import re
    m = re.search(r'S20\.(\d+)[ x]+S20\.(\d+)', name)
    a_id = m.group(1) if m else ""
    b_id = m.group(2) if m else ""
    
    a_p = f"strategy/s20.{a_id}/result_365d.json" if a_id else ""
    b_p = f"strategy/s20.{b_id}/result_365d.json" if b_id else ""
    
    res_a, res_b = {}, {}
    if a_p and os.path.exists(a_p):
        with open(a_p, "r", encoding="utf-8") as fa: res_a = json.load(fa).get('tf', {})
    if b_p and os.path.exists(b_p):
        with open(b_p, "r", encoding="utf-8") as fb: res_b = json.load(fb).get('tf', {})
        
    for tf in res.get('pass_tfs', []):
        mix_d = res.get('tf', {}).get(tf, {})
        m_pf = mix_d.get('pf', 0)
        m_net = mix_d.get('oos', {}).get('net', 0)
        m_tr = mix_d.get('n', 0)
        
        a_d = res_a.get(tf, {})
        a_pf = a_d.get('pf', 0)
        a_net = a_d.get('oos', {}).get('net', 0)
        a_tr = a_d.get('n', 0)
        
        b_d = res_b.get(tf, {})
        b_pf = b_d.get('pf', 0)
        b_net = b_d.get('oos', {}).get('net', 0)
        b_tr = b_d.get('n', 0)
        
        print(f"| S20.{n} | {tf} | {m_pf:.3f} | {m_net:.2f} | {m_tr} | {a_pf:.3f} | {a_net:.2f} | {a_tr} | {b_pf:.3f} | {b_net:.2f} | {b_tr} |")


print("\n--- 3. สถิติสะสมทั้งแคมเปญ ---")
with open('strategy/s20_gen/progress.json', 'r', encoding="utf-8") as f:
    prog = json.load(f)
    
total_tries = len(prog) - 1 # 'next' is not a strategy
pass_count = sum(1 for v in prog.values() if isinstance(v, dict) and len(v.get('pass_tfs', [])) > 0)

with open('strategy/s20_gen/list_winners.py', 'r', encoding="utf-8") as f:
    # Just run it later or count from it
    pass
    
print(f"จำนวนคู่ที่ลองทั้งหมด: {total_tries}")
print(f"มี TF PASS: {pass_count}")
