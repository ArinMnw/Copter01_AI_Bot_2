import json
import os

results = []
for sid in range(408, 428):
    sid_str = str(sid)
    folder = f'strategy/s20.{sid_str}'
    result_file = os.path.join(folder, 'result_365d.json')
    meta_file = os.path.join(folder, f'strategy20_{sid_str}.py')
    
    if os.path.exists(result_file):
        with open(result_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            verdicts = data.get('verdicts', {})
            pass_tfs = [tf for tf, v in verdicts.items() if v == 'PASS']
            total_net = data.get('total', {}).get('Net$', 0)
            total_pf = data.get('total', {}).get('PF', 0)
            jaccard = data.get('uniqueness', {}).get('max_jaccard', 0)
            
            # Find name and concept
            name = ""
            concept = ""
            if os.path.exists(meta_file):
                with open(meta_file, 'r', encoding='utf-8') as mf:
                    content = mf.read()
                    try:
                        import ast
                        start = content.find('META = {')
                        end = content.find('}', start) + 1
                        meta_str = content[start:end].replace('META = ', '').strip()
                        meta = ast.literal_eval(meta_str)
                        name = meta.get('name', '')
                        concept = meta.get('concept', '')
                    except:
                        pass
            
            overall = "FAIL"
            if pass_tfs:
                overall = "PASS (Gate)"
            elif 'WEAK' in verdicts.values():
                overall = "WEAK"
                
            results.append({
                'sid': f'20.{sid_str}',
                'name': name,
                'concept': concept[:30] + '...' if len(concept) > 30 else concept,
                'pass_tfs': ','.join(pass_tfs) if pass_tfs else '-',
                'net': f"{total_net:.2f}",
                'pf': f"{total_pf:.3f}",
                'jaccard': jaccard,
                'result': overall
            })

with open("summary_output.md", "w", encoding="utf-8") as f:
    f.write("| sid | ชื่อ | แนวคิดย่อ | TF ที่ PASS | Net รวม | PF รวม | max Jaccard | ผล |\n")
    f.write("|---|---|---|---|---|---|---|---|\n")
    for r in results:
        f.write(f"| {r['sid']} | {r['name']} | {r['concept']} | {r['pass_tfs']} | {r['net']} | {r['pf']} | {r['jaccard']} | {r['result']} |\n")

with open('strategy/s20_gen/progress.json', 'r', encoding='utf-8') as pf:
    prog = json.load(pf)
    total_strategies = len(prog) - 1 # minus next
    pass_tfs = sum(1 for k, v in prog.items() if k != 'next' and v.get('pass_tfs', []))
    winners = 0 # none so far
    f.write(f"\n\nรวมทั้งหมด {total_strategies} กลยุทธ์, มี TF PASS = {pass_tfs}, WINNER = {winners}")

