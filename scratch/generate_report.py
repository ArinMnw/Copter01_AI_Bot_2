import json
import os
import glob
from pathlib import Path

# SIDs processed in this session
sids_kept = [942, 943, 944, 945, 946]
# Note: 942 (first attempt, 339+338) and 945 (first attempt, 339+258) were DUPLICATE and deleted.

def get_strategy_info(sid):
    path = f"strategy/s20.{sid}/result_365d.json"
    if not os.path.exists(path):
        return None
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

print("### 1. ตารางสรุปผลกลยุทธ์ที่เก็บไว้ในรอบนี้")
print("| sid | ตัวแม่ | วิธีผสม | สมมติฐานย่อ | TF ที่ PASS | Net รวม | PF รวม | max Jaccard | ผล |")
print("|---|---|---|---|---|---|---|---|---|")

for sid in sids_kept:
    res = get_strategy_info(sid)
    if not res:
        continue
        
    meta = res.get('meta', {})
    parents = meta.get('parents', ['?', '?'])
    parent_str = f"{parents[0].replace('20.', '')}+{parents[1].replace('20.', '')}"
    mix = meta.get('mix', '?')
    logic = meta.get('logic', '?')
    pass_tfs = res.get('pass_tfs', [])
    pass_str = ",".join(pass_tfs) if pass_tfs else "-"
    
    # Calculate overall net and PF across all tested TFs
    total_net = 0
    total_gross_profit = 0
    total_gross_loss = 0
    
    tf_results = res.get('tf_results', {})
    max_jaccard = 0.0
    for tf, tf_data in tf_results.items():
        if tf_data.get('metrics'):
            total_net += tf_data['metrics'].get('net_profit', 0)
            total_gross_profit += tf_data['metrics'].get('gross_profit', 0)
            total_gross_loss += tf_data['metrics'].get('gross_loss', 0)
        if tf_data.get('jaccard_similarity'):
            if tf_data['jaccard_similarity'] > max_jaccard:
                max_jaccard = tf_data['jaccard_similarity']
                
    pf_overall = (total_gross_profit / total_gross_loss) if total_gross_loss > 0 else 0
    
    verdict = res.get('verdict', 'FAIL')
    if verdict == 'PASS' and pass_tfs:
        verdict = f"PASS({','.join(pass_tfs)})"
        
    print(f"| {sid} | {parent_str} | {mix} | {logic[:30]}... | {pass_str} | {total_net:.2f} | {pf_overall:.2f} | {max_jaccard:.3f} | {verdict} |")

print("\n*หมายเหตุ: sid 942 (339+338 CONFIRM) และ 945 (339+258 CONFIRM) พบผล DUPLICATE จึงลบทิ้งและใช้เลขซ้ำกับคู่ใหม่ตามกฎแล้ว*")

print("\n### 2. ตารางเทียบตัวผสมกับตัวแม่ (เฉพาะคู่ที่เก็บไว้)")
for sid in sids_kept:
    res = get_strategy_info(sid)
    if not res:
        continue
    meta = res.get('meta', {})
    parents = meta.get('parents', [])
    if len(parents) < 1:
        continue
    parent_a = parents[0].replace('20.', '')
    
    parent_res = get_strategy_info(parent_a)
    if not parent_res:
        continue
        
    print(f"\n**เทียบ S20.{sid} (ผสม) กับ S20.{parent_a} (แม่หลัก)**")
    print("| TF | ฝั่ง | PF | OOS Net | ไม้ |")
    print("|---|---|---|---|---|")
    
    tf_results = res.get('tf_results', {})
    p_tf_results = parent_res.get('tf_results', {})
    
    for tf in ["M15", "M30", "H1", "H4", "D1"]:
        if tf in tf_results and tf in p_tf_results:
            m_mix = tf_results[tf].get('metrics', {})
            m_p = p_tf_results[tf].get('metrics', {})
            if m_mix and m_p:
                print(f"| {tf} | S20.{sid} | {m_mix.get('profit_factor',0):.2f} | {m_mix.get('oos_net_profit',0):.2f} | {m_mix.get('total_trades',0)} |")
                print(f"| {tf} | S20.{parent_a} | {m_p.get('profit_factor',0):.2f} | {m_p.get('oos_net_profit',0):.2f} | {m_p.get('total_trades',0)} |")

print("\n### 3. สถิติสะสมทั้งแคมเปญ")
with open('strategy/s20_gen/progress.json', 'r', encoding='utf-8') as f:
    prog = json.load(f)

total_entries = len(prog.get('entries', {}))
pass_count = sum(1 for e in prog.get('entries', {}).values() if e.get('verdict') == 'PASS')
print(f"- จำนวนคู่ที่ลองทั้งหมด (ใน progress.json): {total_entries}")
print(f"- จำนวนที่มี TF PASS: {pass_count}")

# Check winners
winner_count = 0
for d in glob.glob("strategy/s20.*/final_gate.txt"):
    with open(d, 'r', encoding='utf-8') as f:
        first_line = f.readline().strip()
        if first_line.startswith("WINNER"):
            # Ensure it also has MIX_OK
            mix_check = d.replace("final_gate.txt", "mix_check.txt")
            if os.path.exists(mix_check):
                with open(mix_check, 'r', encoding='utf-8') as f2:
                    if f2.readline().strip().startswith("MIX_OK"):
                        winner_count += 1

print(f"- ผู้ชนะ (WINNER + MIX_OK): {winner_count}")
