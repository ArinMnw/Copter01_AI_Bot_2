import json, os

out = []
out.append('## 2. เปรียบเทียบกับตัวแม่ (เฉพาะคู่ที่มีผลรัน)\n')
out.append('| sid | TF | Mix PF | Mix Net | Mix n | Parent PF | Parent Net | Parent n |\n')
out.append('|---|---|---|---|---|---|---|---|\n')

with open('strategy/s20_gen/progress.json', 'r', encoding='utf-8') as f:
    prog = json.load(f)

for sid in range(905, 920):
    path = f'reports/s20_{sid}/result_365d.json'
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        meta = data.get('meta', {})
        parents = meta.get('parents', [])
        if not parents: continue
        
        parent_sid_str = parents[0]
        # find parent in progress.json
        p_entry = None
        for entry in prog:
            if entry.get('sid') == parent_sid_str:
                p_entry = entry
                break
                
        if p_entry:
            for tf in ['M1', 'M5', 'M15', 'M30', 'H1', 'H4', 'D1']:
                tf_mix = data.get('tf_stats', {}).get(tf, {})
                
                # Check if parent passed this TF
                p_pass_tfs = p_entry.get('pass_tfs', [])
                if tf not in p_pass_tfs:
                    continue
                    
                p_pf = 0
                p_net = 0
                p_n = 0
                # Usually we just show for the mix since we might not have full stats for parent in progress.json
                # Let's extract parent's PF from progress if available. (progress doesn't have per-TF stats).
                # If we don't have per-TF parent stats, we just output `-`
                
                if tf_mix:
                    m_pf = tf_mix.get('pf', 0)
                    m_net = tf_mix.get('net_profit', 0)
                    m_n = tf_mix.get('total_trades', 0)
                    out.append(f'| {sid} | {tf} | {m_pf:.3f} | {m_net:.2f} | {m_n} | - | - | - |\n')

with open('scratch/report_out_2.md', 'w', encoding='utf-8') as f:
    f.writelines(out)

# Part 3: Cumulative stats
mixed_total = 0
pass_total = 0
winner_total = 0

for entry in prog:
    sid_str = entry.get('sid', '')
    if '.' in sid_str:
        num = int(sid_str.split('.')[1])
        if num >= 429: # Roughly when mix campaign started
            if 'parents' in entry and entry['parents']:
                mixed_total += 1
                if entry.get('pass_tfs'):
                    pass_total += 1
                if entry.get('final_verdict', '').startswith('WINNER'):
                    winner_total += 1

out_stats = []
out_stats.append('## 3. สถิติสะสมทั้งแคมเปญ\n')
out_stats.append(f'- จำนวนคู่ผสมที่ลองทั้งหมด (บันทึกแล้ว): {mixed_total}\n')
out_stats.append(f'- จำนวนที่มี TF PASS: {pass_total}\n')
out_stats.append(f'- จำนวนผู้ชนะ (WINNER): {winner_total}\n')

with open('scratch/report_out_3.md', 'w', encoding='utf-8') as f:
    f.writelines(out_stats)
