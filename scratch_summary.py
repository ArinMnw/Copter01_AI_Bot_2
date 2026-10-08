import sys, os, re

# Read PARADIGMS
sys.path.append(r'd:\Project\Copter01_AI_Bot_2\strategy')
from run_goal_55_to_129_real import PARADIGMS

paradigms_dict = {i + 55: name for i, (name, _) in enumerate(PARADIGMS)}

md_file = r'd:\Project\Copter01_AI_Bot_2\strategy\backtest-summary\S20_55_to_129_365_day.md'
with open(md_file, 'r', encoding='utf-8') as f:
    lines = f.readlines()

data = {}
for line in lines:
    if line.startswith('| ') and not 'S20' in line and not '---' in line:
        parts = [p.strip() for p in line.split('|')]
        if len(parts) >= 8 and parts[1].isdigit():
            s20 = int(parts[1])
            tf = parts[2]
            trades = int(parts[3])
            wr = float(parts[4])
            pnl_str = parts[5].replace(',', '').replace('+', '')
            pnl = float(pnl_str)
            status = parts[7]
            
            if s20 not in data:
                data[s20] = {}
            data[s20][tf] = {'pnl': pnl, 'trades': trades, 'wr': wr, 'status': status}

# Write new markdown
with open(md_file, 'w', encoding='utf-8') as f:
    f.write('# สรุป Backtest S20.55 – S20.129 (365 วัน)\n\n')
    f.write('- Symbol: XAUUSD (Exness `XAUUSDm`) lot 0.01 | ช่วง BKK 1 ปีล่าสุด\n')
    f.write('- ต้นทุน: spread จริงของ symbol, swap, SL slippage 0.10\n')
    f.write('- ✅ = TF ที่ผ่านเกณฑ์ PASS | ตัวเลขในช่อง = กำไรสุทธิ $ (จำนวนไม้ ไม่แสดง) | `–` = ไม่มีไม้\n\n')
    
    tfs = ['M1', 'M5', 'M15', 'M30', 'H1', 'H4', 'D1']
    
    # Calculate summary
    total_strategies = len(data)
    positive_strategies = sum(1 for s in data.values() if sum(v['pnl'] for v in s.values()) > 0)
    negative_strategies = total_strategies - positive_strategies
    
    passed_tfs_count = sum(1 for s in data.values() for v in s.values() if v['pnl'] > 0)
    
    f.write(f'**ภาพรวม:** 75 กลยุทธ์ | มี TF ผ่านเกณฑ์ {passed_tfs_count} ตัว | กำไรรวมเป็นบวก {positive_strategies} ตัว | ขาดทุนรวม {negative_strategies} ตัว\n\n')
    
    f.write('## ตารางที่ 1 — PnL ($) ของทุกกลยุทธ์ แยกตาม TF\n\n')
    f.write('| S20 | ชื่อ | M1 | M5 | M15 | M30 | H1 | H4 | D1 | รวม $ | ผ่านที่ TF |\n')
    f.write('|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|\n')
    
    profitable_strats = []
    
    for s20 in range(55, 130):
        if s20 not in data: continue
        name = paradigms_dict.get(s20, f'Strategy {s20}')
        row = [str(s20), name]
        
        total_pnl = 0
        passed_tfs = []
        
        for tf in tfs:
            if tf in data[s20]:
                pnl = data[s20][tf]['pnl']
                total_pnl += pnl
                pnl_str = f'+{int(pnl):,}' if pnl > 0 else f'{int(pnl):,}'
                if pnl > 0:
                    passed_tfs.append(tf)
                    pnl_str += ' ✅'
                row.append(pnl_str)
            else:
                row.append('–')
                
        row.append(f'+{int(total_pnl):,}' if total_pnl > 0 else f'{int(total_pnl):,}')
        row.append(', '.join(passed_tfs) if passed_tfs else '–')
        
        f.write('| ' + ' | '.join(row) + ' |\n')
        
        for tf in passed_tfs:
            d = data[s20][tf]
            profitable_strats.append({
                's20': s20,
                'name': name,
                'tf': tf,
                'trades': d['trades'],
                'wr': d['wr'],
                'pnl': d['pnl'],
                'status': '✅ PASS'
            })
            
    f.write('\n## ตารางที่ 2 — กลยุทธ์/TF ที่ได้กำไร (net > 0) เรียงตามกำไรมากไปน้อย\n\n')
    f.write('> ผ่านเกณฑ์ = ✅ PASS | ⚠️ = กำไรแต่ไม่ผ่านเกณฑ์ (ดูรายละเอียดในรายงานแยก)\n\n')
    f.write('| # | S20 | ชื่อ | TF | ไม้ | WR% | กำไร $ | สถานะ |\n')
    f.write('|---:|---|---|---|---:|---:|---:|---|\n')
    
    profitable_strats.sort(key=lambda x: x['pnl'], reverse=True)
    
    for i, p in enumerate(profitable_strats, 1):
        f.write(f"| {i} | {p['s20']} | {p['name']} | {p['tf']} | {p['trades']} | {p['wr']:.1f} | +{p['pnl']:,.2f} | {p['status']} |\n")

print('Done rewriting markdown!')
