import os, json, glob
import re
from datetime import datetime

with open("scratch/report.md", "w", encoding="utf-8") as f_out:
    # 1. Summary Table
    f_out.write("=== 1. Summary Table ===\n")
    f_out.write("sid | ตัวแม่ | วิธีผสม | สมมติฐานย่อ | TF ที่ PASS | Net รวม | PF รวม | max Jaccard | ผล\n")
    f_out.write("---|---|---|---|---|---|---|---|---\n")

    # Read mix_log for today's run
    with open("strategy/s20_gen/mix_log.md", "r", encoding="utf-8") as f:
        mix_lines = [l.strip() for l in f.readlines() if l.strip().startswith("|")]

    valid_lines = []
    for l in mix_lines:
        parts = l.split("|")
        if len(parts) >= 7:
            try:
                sid = int(parts[1].strip().split()[0])
                if sid >= 429:
                    valid_lines.append(l)
            except:
                pass

    pass_sids = []
    all_sids_processed = []

    for l in valid_lines:
        parts = l.split("|")
        sid_str = parts[1].strip().split()[0]
        sid = int(sid_str)
        a = parts[2].strip()
        b = parts[3].strip()
        method = parts[4].strip()
        result = parts[6].strip()
        
        all_sids_processed.append((sid, a, b))
        
        res_path = f"strategy/s20.{sid}/result_365d.json"
        py_path = f"strategy/s20.{sid}/strategy20_{sid}.py"
        
        net = "N/A"
        pf = "N/A"
        mj = "N/A"
        pass_tfs_str = "-"
        logic = "-"
        
        if os.path.exists(res_path):
            with open(res_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                net = str(data.get('total', {}).get('net', 'N/A'))
                pf = str(data.get('total', {}).get('pf', 'N/A'))
                un = data.get('uniqueness', {})
                mj = f"{un.get('max_jaccard', 'N/A')} ({un.get('with', 'N/A')})"
                pass_tfs = data.get('pass_tfs', [])
                if pass_tfs:
                    pass_tfs_str = ",".join(pass_tfs)
                    if sid not in pass_sids: pass_sids.append(sid)
                    
        if os.path.exists(py_path):
            with open(py_path, 'r', encoding='utf-8') as f:
                py_content = f.read()
                if '"logic":' in py_content:
                    logic_match = re.search(r'"logic":\s*"([^"]+)"', py_content)
                    if logic_match:
                        logic = logic_match.group(1)[:40] + "..."
        
        f_out.write(f"{sid} | {a} + {b} | {method} | {logic} | {pass_tfs_str} | {net} | {pf} | {mj} | {result}\n")

    f_out.write("\n=== 2. Comparison Table per TF ===\n")
    for sid, a, b in all_sids_processed:
        res_path = f"strategy/s20.{sid}/result_365d.json"
        if not os.path.exists(res_path): continue
        
        a_id = a.replace("20.", "")
        b_id = b.replace("20.", "")
        
        a_path = f"strategy/s20.{a_id}/result_365d.json"
        b_path = f"strategy/s20.{b_id}/result_365d.json"
        
        if os.path.exists(a_path) and os.path.exists(b_path):
            with open(res_path, 'r', encoding='utf-8') as f: d_mix = json.load(f)
            with open(a_path, 'r', encoding='utf-8') as f: d_a = json.load(f)
            with open(b_path, 'r', encoding='utf-8') as f: d_b = json.load(f)
            
            f_out.write(f"\n--- S20.{sid} vs A(20.{a_id}) vs B(20.{b_id}) ---\n")
            f_out.write("TF | Mix PF | A PF | B PF | Mix OOS Net | A OOS Net | B OOS Net | Mix N | A N | B N\n")
            f_out.write("---|---|---|---|---|---|---|---|---|---\n")
            tfs = d_mix.get('tf', {})
            for tf, d in tfs.items():
                if not isinstance(d, dict) or 'oos' not in d: continue
                mix_pf = d.get('pf', 0)
                a_pf = d_a.get('tf', {}).get(tf, {}).get('pf', 0) if isinstance(d_a.get('tf', {}).get(tf), dict) else 0
                b_pf = d_b.get('tf', {}).get(tf, {}).get('pf', 0) if isinstance(d_b.get('tf', {}).get(tf), dict) else 0
                
                mix_oos = d.get('oos', {}).get('net', 0)
                a_oos = d_a.get('tf', {}).get(tf, {}).get('oos', {}).get('net', 0) if isinstance(d_a.get('tf', {}).get(tf), dict) else 0
                b_oos = d_b.get('tf', {}).get(tf, {}).get('oos', {}).get('net', 0) if isinstance(d_b.get('tf', {}).get(tf), dict) else 0
                
                mix_n = d.get('n', 0)
                a_n = d_a.get('tf', {}).get(tf, {}).get('n', 0) if isinstance(d_a.get('tf', {}).get(tf), dict) else 0
                b_n = d_b.get('tf', {}).get(tf, {}).get('n', 0) if isinstance(d_b.get('tf', {}).get(tf), dict) else 0
                
                f_out.write(f"{tf} | {mix_pf} | {a_pf} | {b_pf} | {mix_oos} | {a_oos} | {b_oos} | {mix_n} | {a_n} | {b_n}\n")

    f_out.write("\n=== 3. Cumulative Stats ===\n")
    with open("strategy/s20_gen/mix_log.md", "r", encoding="utf-8") as f:
        mix_lines_all = [l.strip() for l in f.readlines() if l.strip().startswith("|")]
    total_tried = len(mix_lines_all) - 2
    if total_tried < 0: total_tried = 0

    all_res = glob.glob("strategy/s20.*/result_365d.json")
    total_pass = 0
    total_winner = 0

    for r in all_res:
        with open(r, 'r', encoding='utf-8') as f:
            try: d = json.load(f)
            except: continue
            if d.get('pass_tfs', []):
                total_pass += 1
                sid = d.get('sid', '').replace('20.', '')
                if os.path.exists(f"strategy/s20.{sid}/final_gate.txt") and os.path.exists(f"strategy/s20.{sid}/mix_check.txt"):
                    with open(f"strategy/s20.{sid}/final_gate.txt", 'r', encoding='utf-8') as fg:
                        if fg.read().startswith("WINNER"):
                            with open(f"strategy/s20.{sid}/mix_check.txt", 'r', encoding='utf-8') as mc:
                                if mc.read().startswith("MIX_OK"):
                                    total_winner += 1

    f_out.write(f"จำนวนคู่ที่ลองทั้งหมดใน mix_log: {total_tried}\n")
    f_out.write(f"มี TF PASS: {total_pass}\n")
    f_out.write(f"ผู้ชนะ (WINNER + MIX_OK): {total_winner}\n")

    f_out.write("\n=== 4. Raw stdout for PASS ===\n")
    for sid in pass_sids:
        f_out.write(f"\n--- S20.{sid} ---\n")
        out_path = f"strategy/s20.{sid}/run_one_stdout.txt"
        if os.path.exists(out_path):
            with open(out_path, 'r', encoding='utf-8') as f:
                f_out.write(f.read() + "\n")
        else:
            f_out.write("No stdout saved.\n")

    f_out.write("\n=== 5. final_gate.txt and mix_check.txt ===\n")
    for sid in pass_sids:
        fg = f"strategy/s20.{sid}/final_gate.txt"
        mc = f"strategy/s20.{sid}/mix_check.txt"
        f_out.write(f"\n--- S20.{sid} final_gate ---\n")
        if os.path.exists(fg):
            with open(fg, 'r', encoding='utf-8') as f: f_out.write(f.readline().strip() + "\n")
        f_out.write(f"--- S20.{sid} mix_check ---\n")
        if os.path.exists(mc):
            with open(mc, 'r', encoding='utf-8') as f: f_out.write(f.read().strip() + "\n")
