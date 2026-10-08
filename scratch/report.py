import os
import json
import re

start_sid = 787
end_sid = 805

print("### 1. ตารางสรุปรอบนี้ (อ่านจาก mix_log.md)")
lines = open("strategy/s20_gen/mix_log.md", encoding="utf-8").readlines()
print("| sid | ตัวแม่ | วิธีผสม | วันที่ | ผล |")
print("|---|---|---|---|---|")
for line in lines:
    m = re.match(r'\|\s*(\d+)\s*\|', line)
    if m:
        sid = int(m.group(1))
        if start_sid <= sid <= end_sid:
            print(line.strip())

print("\n### 2. ตารางเทียบตัวผสมกับตัวแม่ ต่อ TF (เฉพาะตัวที่มี PASS TF)")
for sid in range(start_sid, end_sid + 1):
    res_path = f"strategy/s20.{sid}/result_365d.json"
    if os.path.exists(res_path):
        data = json.load(open(res_path, encoding="utf-8"))
        pass_tfs = data.get("pass_tfs", [])
        if not pass_tfs: continue
        parents = data.get("meta", {}).get("parents", [])
        print(f"\nS20.{sid} PASS TFs: {pass_tfs}")
        for tf in pass_tfs:
            tf_data = data.get("tfs", {}).get(tf, {})
            print(f"  {tf}: Mix = PF {tf_data.get('pf',0):.2f}, OOS net {tf_data.get('oos_net',0):.2f}, n {tf_data.get('n',0)}")
            if parents:
                pA = parents[0]
                pA_file = f"strategy/s20.{pA.split('.')[-1]}/result_365d.json"
                if os.path.exists(pA_file):
                    pA_data = json.load(open(pA_file, encoding="utf-8"))
                    pA_tf = pA_data.get("tfs", {}).get(tf, {})
                    print(f"       Parent A ({pA}) = PF {pA_tf.get('pf',0):.2f}, OOS net {pA_tf.get('oos_net',0):.2f}, n {pA_tf.get('n',0)}")

print("\n### 3. สถิติสะสมทั้งแคมเปญ")
total_tried = len([line for line in lines if re.match(r'\|\s*\d+\s*\|', line)])
total_pass = len([line for line in lines if "PASS" in line or "WINNER" in line])
total_winners = len([line for line in lines if "WINNER" in line])
print(f"- จำนวนคู่ที่ลองทั้งหมด: {total_tried}")
print(f"- มี TF PASS: {total_pass}")
print(f"- ผู้ชนะ: {total_winners}")

