import os, json, re

def get_report():
    print("## 1. ตารางสรุปทุกตัวที่ลองในรอบนี้ (รวม FAIL และ DUPLICATE)")
    print("| sid | ตัวแม่ | วิธีผสม | สมมติฐานย่อ | TF ที่ PASS | Net รวม | PF รวม | max Jaccard | ผล |")
    print("|---|---|---|---|---|---|---|---|---|")
    
    success_count = 0
    total_net = 0
    
    for sid in range(881, 897):
        path = f'strategy/s20.{sid}/result_365d.json'
        if os.path.exists(path):
            with open(path, encoding='utf-8') as f:
                res = json.load(f)
            
            name = res.get('name', '')
            m = re.match(r'Mix\s+(\d+)\s*\+\s*(\d+)\s*\((.*?)\)', name)
            if m:
                p_a, p_b, mix = m.groups()
                parents = f"[{p_a}, {p_b}]"
            else:
                parents = "[]"
                mix = ""
                
            logic = res.get('concept', '')
            pass_tfs = res.get('pass_tfs', [])
            pass_tf_str = ", ".join(pass_tfs) if pass_tfs else "-"
            
            total = res.get('total', {})
            net = total.get('net', 0)
            pf = total.get('pf', 0)
            
            uniq = res.get('uniqueness', {})
            jaccard = uniq.get('max_jaccard', 0)
            
            verdict = "FAIL"
            if pass_tfs:
                # Check mix_check.txt first (rule 14)
                mix_ok = False
                mc_path = f'strategy/s20.{sid}/mix_check.txt'
                if os.path.exists(mc_path):
                    mc = open(mc_path, encoding='utf-8').read()
                    if "MIX_OK" in mc:
                        mix_ok = True
                
                win = False
                fg_path = f'strategy/s20.{sid}/final_gate.txt'
                if os.path.exists(fg_path):
                    fg = open(fg_path, encoding='utf-8').read()
                    if "WINNER" in fg:
                        win = True
                        
                if win and mix_ok:
                    verdict = "WINNER"
                    success_count += 1
                elif pass_tfs:
                    verdict = "PASS"
            
            logic_trunc = logic[:40].replace('\n', ' ')
            print(f"| {sid} | {parents} | {mix} | {logic_trunc}... | {pass_tf_str} | {net:.2f} | {pf:.2f} | {jaccard:.3f} | {verdict} |")
        else:
            print(f"| {sid} | - | - | (DUPLICATE / ERROR) | - | - | - | - | FAIL |")
            
    print("\n## 2. ตารางเทียบตัวผสมกับตัวแม่ ต่อ TF (เฉพาะตัว PASS)")
    print("| sid | TF | Parent A (Net/PF/N) | Parent B (Net/PF/N) | Mix (Net/PF/N) |")
    print("|---|---|---|---|---|")
    
    for sid in range(881, 897):
        path = f'strategy/s20.{sid}/result_365d.json'
        if not os.path.exists(path): continue
        
        with open(path, encoding='utf-8') as f:
            mix_res = json.load(f)
            
        pass_tfs = mix_res.get('pass_tfs', [])
        if not pass_tfs: continue
        
        name = mix_res.get('name', '')
        m = re.match(r'Mix\s+(\d+)\s*\+\s*(\d+)', name)
        if m:
            p_a, p_b = m.groups()
            try:
                with open(f'strategy/s20.{p_a}/result_365d.json', encoding='utf-8') as f:
                    res_a = json.load(f)
                with open(f'strategy/s20.{p_b}/result_365d.json', encoding='utf-8') as f:
                    res_b = json.load(f)
                    
                for tf in pass_tfs:
                    row_mix = mix_res['tf'].get(tf, {})
                    row_a = res_a['tf'].get(tf, {})
                    row_b = res_b['tf'].get(tf, {})
                    
                    s_mix = f"{row_mix.get('net', 0):.2f}/{row_mix.get('pf', 0):.2f}/{row_mix.get('n', 0)}"
                    s_a = f"{row_a.get('net', 0):.2f}/{row_a.get('pf', 0):.2f}/{row_a.get('n', 0)}"
                    s_b = f"{row_b.get('net', 0):.2f}/{row_b.get('pf', 0):.2f}/{row_b.get('n', 0)}"
                    
                    print(f"| {sid} | {tf} | {s_a} | {s_b} | {s_mix} |")
            except Exception as e:
                print(f"| {sid} | ERROR | {str(e)} |")
                
    print("\n## 3. สถิติสะสมทั้งแคมเปญ")
    lines = open('strategy/s20_gen/mix_log.md', encoding='utf-8').readlines()
    total = len([l for l in lines if '|' in l and '20.' in l])
    print(f"จำนวนคู่ที่ลองทั้งหมด: {total} (อิงจาก mix_log.md)")
    print(f"รอบนี้ผ่าน (PASS/WINNER): {success_count} จาก 15 ตัว (sid 881-896)")

if __name__ == "__main__":
    get_report()
