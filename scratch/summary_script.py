import json, os

print('| sid | ตัวแม่ | วิธีผสม | สมมติฐานย่อ | TF ที่ PASS | Net รวม | PF รวม | max Jaccard | ผล |')
print('|---|---|---|---|---|---|---|---|---|')
for sid in range(905, 920):
    path = f'reports/s20_{sid}/result_365d.json'
    if not os.path.exists(path):
        continue
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    meta = data.get('meta', {})
    stats = data.get('total_stats', {})
    parents = ','.join(meta.get('parents', []))
    mix = meta.get('mix', '')
    logic = meta.get('concept', '')
    pass_tfs = ','.join(data.get('pass_tfs', [])) or '-'
    net = f"{stats.get('net_profit', 0):.2f}"
    pf = f"{stats.get('pf', 0):.3f}"
    jaccard = data.get('uniqueness', {}).get('max_jaccard', 0)
    verdict = meta.get('final_verdict', 'UNIQUE')
    print(f'| {sid} | {parents} | {mix} | {logic} | {pass_tfs} | {net} | {pf} | {jaccard} | {verdict} |')
