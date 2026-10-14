import json, os, re

out = []
out.append('## 1. ตารางสรุป (sid 905-919)\n')
out.append('| sid | ตัวแม่ | วิธีผสม | สมมติฐานย่อ | TF ที่ PASS | Net รวม | PF รวม | max Jaccard | ผล |\n')
out.append('|---|---|---|---|---|---|---|---|---|\n')
# We need to read from mix_log.md for DUPLICATES
with open('strategy/s20_gen/mix_log.md', 'r', encoding='utf-8') as f:
    log_lines = f.readlines()

log_data = {}
for line in log_lines:
    parts = [p.strip() for p in line.split('|')]
    if len(parts) > 6 and parts[1].isdigit():
        sid = int(parts[1])
        if 905 <= sid <= 919:
            log_data.setdefault(sid, []).append({
                'parents': f'{parts[2]} x {parts[3]}',
                'mix': parts[4],
                'result': parts[6]
            })

for sid in range(905, 920):
    path = f'reports/s20_{sid}/result_365d.json'
    if os.path.exists(path):
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
        if verdict == 'UNIQUE':
            if pass_tfs == '-':
                verdict = 'UNIQUE (NO PASS TFs)'
            else:
                verdict = 'UNIQUE (PASS)'
        out.append(f'| {sid} | {parents} | {mix} | {logic} | {pass_tfs} | {net} | {pf} | {jaccard} | {verdict} |\n')
    else:
        # Fallback to mix_log.md
        if sid in log_data:
            for entry in log_data[sid]:
                out.append(f'| {sid} | {entry["parents"]} | {entry["mix"]} | - | - | - | - | - | {entry["result"]} |\n')

out.append('\n## 2. เปรียบเทียบกับตัวแม่ (เฉพาะคู่ที่มีผลรัน)\n')
out.append('| sid | TF | Mix PF | Mix Net | Mix n | Parent PF | Parent Net | Parent n |\n')
out.append('|---|---|---|---|---|---|---|---|\n')
for sid in range(905, 920):
    path = f'reports/s20_{sid}/result_365d.json'
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        meta = data.get('meta', {})
        parents = meta.get('parents', [])
        if not parents: continue
        parent_sid = parents[0].split('.')[1]
        p_path = f'reports/s20_{parent_sid}/result_365d.json'
        if os.path.exists(p_path):
            with open(p_path, 'r', encoding='utf-8') as pf:
                p_data = json.load(pf)
            for tf in ['M1', 'M5', 'M15', 'M30', 'H1', 'H4', 'D1']:
                tf_mix = data.get('tf_stats', {}).get(tf, {})
                tf_p = p_data.get('tf_stats', {}).get(tf, {})
                if tf_mix and tf_p:
                    m_pf = tf_mix.get('pf', 0)
                    m_net = tf_mix.get('net_profit', 0)
                    m_n = tf_mix.get('total_trades', 0)
                    p_pf = tf_p.get('pf', 0)
                    p_net = tf_p.get('net_profit', 0)
                    p_n = tf_p.get('total_trades', 0)
                    if m_n > 0 or p_n > 0:
                        out.append(f'| {sid} | {tf} | {m_pf:.3f} | {m_net:.2f} | {m_n} | {p_pf:.3f} | {p_net:.2f} | {p_n} |\n')

with open('scratch/report_out.md', 'w', encoding='utf-8') as f:
    f.writelines(out)
print('Report generated in scratch/report_out.md')
