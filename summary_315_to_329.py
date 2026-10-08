import json, os

start_sid = 315
end_sid = 329

print("| SID | ชื่อ (Name) | แนวคิดย่อ (Concept) | TF ที่ PASS | Net รวม | PF รวม | Max Jaccard | ผลลัพธ์ |")
print("|---|---|---|---|---|---|---|---|")

for i in range(start_sid, end_sid + 1):
    sid = f"20.{i}"
    res_path = f"strategy/s20.{i}/result_365d.json"
    gate_path = f"strategy/s20.{i}/final_gate.txt"
    strat_path = f"strategy/s20.{i}/strategy20_{i}.py"
    
    if not os.path.exists(res_path):
        continue
        
    with open(res_path, 'r', encoding='utf-8') as f:
        res = json.load(f)
        
    name = res.get("name", "-")
    
    # Extract concept from strategy file
    concept = "-"
    if os.path.exists(strat_path):
        with open(strat_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            for line in lines:
                if "'concept':" in line or '"concept":' in line:
                    concept_part = line.split("concept")[-1]
                    if ":" in concept_part:
                        concept_val = concept_part.split(":", 1)[1].strip()
                        if concept_val.endswith(","):
                            concept_val = concept_val[:-1]
                        concept = concept_val.strip("'\" ")
                        break
                    
    pass_tfs = res.get("pass_tfs", [])
    pass_tfs_str = ", ".join(pass_tfs) if pass_tfs else "-"
    
    net = res.get("total", {}).get("net", 0)
    pf = res.get("total", {}).get("pf", 0)
    
    jaccard = res.get("uniqueness", {}).get("max_jaccard", "-")
    
    # Determine result
    result = "-"
    if pass_tfs:
        if os.path.exists(gate_path):
            with open(gate_path, 'r', encoding='utf-8') as f:
                gate_result = f.readline().strip()
                result = gate_result
        else:
            result = "FAILED_GATE: ไม่ผ่านด่านสุดท้าย"
    else:
        # check if it has WEAK
        has_weak = False
        if "tf_res" in res:
            for tf, data in res["tf_res"].items():
                if data.get("verdict") == "WEAK":
                    has_weak = True
                    break
        result = "WEAK" if has_weak else "FAIL"
        
    print(f"| {sid} | {name} | {concept[:30]}... | {pass_tfs_str} | {net:.2f} | {pf:.3f} | {jaccard} | {result} |")
