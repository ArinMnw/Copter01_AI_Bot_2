import json
import os
import glob
import re

LOG_FILE = r"C:\Users\Copter\.gemini\antigravity-ide\brain\571aeb5c-a50d-457d-bb03-c234719edfba\.system_generated\tasks\task-111.log"

def get_strategy_meta(sid):
    path = f"strategy/s20.{sid}/strategy20_{sid}.py"
    if not os.path.exists(path):
        return None
    import ast
    with open(path, 'r', encoding='utf-8') as f:
        tree = ast.parse(f.read())
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            if isinstance(node.targets[0], ast.Name) and node.targets[0].id == "META":
                return ast.literal_eval(node.value)
    return None

def main():
    print("="*80)
    print("REPORT GENERATOR")
    print("="*80)

    try:
        with open(LOG_FILE, 'r', encoding='utf-8', errors='replace') as f:
            log_content = f.read()
    except Exception as e:
        print(f"Could not read task log: {e}")
        return

    # Extract all attempted SIDs and their results from the log
    attempts = []
    # Log pattern: 
    # ==================================================
    # Trying 143 + 277 (VETO)
    # ==================================================
    # ...
    # Result for 872: FAIL
    
    current_pair = None
    for line in log_content.split('\n'):
        m_pair = re.search(r'Trying (\d+) \+ (\d+) \(([A-Z]+)\)', line)
        if m_pair:
            current_pair = (m_pair.group(1), m_pair.group(2), m_pair.group(3))
        
        m_res = re.search(r'Result for (\d+): (.*)', line)
        if m_res and current_pair:
            sid = m_res.group(1)
            result = m_res.group(2).strip()
            attempts.append({
                "sid": sid,
                "a": current_pair[0],
                "b": current_pair[1],
                "mix": current_pair[2],
                "result": result
            })
            current_pair = None
            
    print("\n1. ตารางสรุปทุกตัวที่ลองในรอบนี้ (รวม FAIL และตัวที่ DUPLICATE):")
    print("-" * 120)
    print(f"{'SID':<5} | {'Parents':<15} | {'Mix':<8} | {'TF PASS':<15} | {'Net รวม':<10} | {'PF รวม':<8} | {'Max Jaccard':<12} | {'Result':<15} | {'Logic Summary'}")
    print("-" * 120)

    pass_sids = []

    for att in attempts:
        sid = att['sid']
        result = att['result']
        
        meta = get_strategy_meta(sid)
        logic = meta['logic'] if meta else "N/A"
        
        # Default values if deleted or missing
        tf_pass = "-"
        net = "-"
        pf = "-"
        max_jac = "-"
        
        # Search for Jaccard in log block for this SID (very rough heuristic)
        # We can extract max Jaccard from the log using regex over the whole file
        jac_matches = re.findall(rf'Jaccard: (0\.\d+)', log_content)
        # Actually it's better to look in result_365d.json if it exists
        res_file = f"reports/s20_{sid}/result_365d.json"
        if os.path.exists(res_file):
            with open(res_file, 'r', encoding='utf-8') as f:
                res_data = json.load(f)
                tf_pass = ",".join(res_data.get("pass_tfs", []))
                net = f"{res_data.get('total_net', 0):.2f}"
                pf = f"{res_data.get('total_pf', 0):.3f}"
                max_jac = f"{res_data.get('max_jaccard', 0):.3f}"
                if tf_pass:
                    pass_sids.append((sid, att['a'], att['b']))
        else:
            # Maybe it was DUPLICATE and deleted, try to find Jaccard in the log
            # The run_one.py prints something like "Max Jaccard: 0.850"
            pass
            
        # Truncate logic
        logic_trunc = logic[:40] + "..." if len(logic) > 40 else logic
            
        print(f"{sid:<5} | {att['a']}+{att['b']:<11} | {att['mix']:<8} | {tf_pass:<15} | {net:<10} | {pf:<8} | {max_jac:<12} | {result:<15} | {logic_trunc}")

    print("\n2. ตารางเทียบตัวผสมกับตัวแม่ ต่อ TF (PF / OOS net / จำนวนไม้) เฉพาะตัวที่มี TF PASS")
    print("-" * 120)
    for sid, a, b in pass_sids:
        print(f"\n--- เทียบ S20.{sid} vs S20.{a} vs S20.{b} ---")
        try:
            res_mix = json.load(open(f"reports/s20_{sid}/result_365d.json", 'r', encoding='utf-8'))
            res_a = json.load(open(f"reports/s20_{a}/result_365d.json", 'r', encoding='utf-8'))
            res_b = json.load(open(f"reports/s20_{b}/result_365d.json", 'r', encoding='utf-8'))
            
            for tf in res_mix.get("pass_tfs", []):
                if tf not in res_mix: continue
                m = res_mix[tf]
                ma = res_a.get(tf, {})
                mb = res_b.get(tf, {})
                
                print(f"TF: {tf}")
                print(f"  Mix ({sid}): PF={m.get('pf',0):.2f}, OOS Net={m.get('oos_net',0):.2f}, Trades={m.get('trades_total',0)}")
                print(f"  P_A ({a}): PF={ma.get('pf',0):.2f}, OOS Net={ma.get('oos_net',0):.2f}, Trades={ma.get('trades_total',0)}")
                print(f"  P_B ({b}): PF={mb.get('pf',0):.2f}, OOS Net={mb.get('oos_net',0):.2f}, Trades={mb.get('trades_total',0)}")
        except Exception as e:
            print(f"Error loading stats for {sid}: {e}")

    print("\n3. สถิติสะสมทั้งแคมเปญ (อ่านจาก strategy.md / mix_log.md)")
    # Just rough count from mix_log.md
    if os.path.exists("strategy/s20_gen/mix_log.md"):
        with open("strategy/s20_gen/mix_log.md", 'r', encoding='utf-8') as f:
            lines = f.readlines()
        total_tried = len([l for l in lines if '|' in l])
        pass_count = len([l for l in lines if 'PASS' in l or 'WINNER' in l])
        winner_count = len([l for l in lines if 'WINNER' in l])
        print(f"จำนวนคู่ที่ลองทั้งหมด: {total_tried}")
        print(f"มี TF PASS: {pass_count}")
        print(f"ผู้ชนะ: {winner_count}")
        
if __name__ == "__main__":
    main()
