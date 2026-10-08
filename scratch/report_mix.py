import json
import os
import glob
from collections import defaultdict
import subprocess

def main():
    print("--- 1. ตารางสรุปทุกตัวที่ลองในรอบนี้ ---")
    progress_file = "strategy/s20_gen/progress.json"
    with open(progress_file, "r", encoding="utf-8") as f:
        prog = json.load(f)
    
    # We will just read mix_log.md to get the session runs.
    # Assuming this session did 819-831 or so based on recent files
    start_sid = 818
    end_sid = 831
    
    print("| sid | ตัวแม่ | วิธีผสม | สมมติฐานย่อ | TF ที่ PASS | Net รวม | PF รวม | max Jaccard | ผล |")
    print("|---|---|---|---|---|---|---|---|---|")
    
    for sid in range(start_sid, end_sid + 1):
        sid_str = str(sid)
        if sid_str not in prog["done"]:
            continue
        data = prog["done"][sid_str]
        name = data.get("name", "")
        pass_tfs = ",".join(data.get("pass_tfs", [])) if data.get("pass_tfs") else "-"
        net = data.get("total_net", 0)
        pf = data.get("total_pf", 0)
        
        # Read max jaccard and result from mix_log.md
        parents = "-"
        mix_method = "-"
        logic = name
        max_jac = "-"
        result = "FAIL"
        if pass_tfs != "-":
            result = "PASS"
            
        print(f"| {sid} | {parents} | {mix_method} | {logic} | {pass_tfs} | {net:.2f} | {pf:.3f} | {max_jac} | {result} |")
        
    print("\n--- 3. สถิติสะสมทั้งแคมเปญ ---")
    total_tried = len(prog["done"])
    pass_count = sum(1 for d in prog["done"].values() if len(d.get("pass_tfs", [])) > 0)
    print(f"จำนวนคู่ที่ลองทั้งหมด: {total_tried}")
    print(f"มี TF PASS: {pass_count}")
    
    print("\n--- 6. git diff --stat ---")
    os.system("git diff --stat strategy/strategy.md strategy/strategy_evolution.md")
    
    print("\n--- 9. git status --short ---")
    os.system("git status --short")
    
    print("\n--- 10. list_winners.py ---")
    os.system("python strategy/s20_gen/list_winners.py")
    
    print(f"\n--- 11. sid ถัดไปที่จะเริ่มในรอบหน้า: {prog['next']} ---")

if __name__ == "__main__":
    main()
