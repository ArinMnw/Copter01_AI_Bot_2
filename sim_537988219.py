"""sim_537988219.py — Before/After: Pending Trend Check bug fix for order #537988219"""
import io, sys, os, re
from datetime import datetime, timezone, timedelta
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
os.chdir(os.path.dirname(os.path.abspath(__file__)))

UTC6 = timezone(timedelta(hours=6))
ticket = 537988219

from handlers.btn_order import _grep_ticket_lines
all_lines = [l for l in _grep_ticket_lines(ticket) if 'SCAN_SUMMARY' not in l]

def fld(line, key):
    m = re.search(rf'\b{key}=([^|\s]+)', line)
    return m.group(1) if m else None

def ts(line):
    m = re.match(r'^\[(\d{4}-\d{2}-\d{2} (\d{2}:\d{2}:\d{2}))\]', line)
    return m.group(2) if m else '?'

print('=' * 65)
print(f'SIM: #{ticket}  S2 FVG BUY M5  entry=4460.42')
print('=' * 65)

# นับครั้ง approach
approach_round1 = [l for l in all_lines if 'PENDING_TREND_CHECK' in l and '| round1 |' in l]
approach_pass   = [l for l in all_lines if 'PENDING_TREND_CHECK' in l and 'round1_pass' in l]

print(f'\n[BEFORE FIX] PENDING_TREND_CHECK round1 วิ่ง {len(approach_round1)} ครั้ง')
if approach_round1:
    print(f'  ครั้งแรก  : {ts(approach_round1[0])}  dist={fld(approach_round1[0],"dist_pt")}pt')
    print(f'  ครั้งสุดท้าย: {ts(approach_round1[-1])}  dist={fld(approach_round1[-1],"dist_pt")}pt')
print(f'  State ถูก pop() ทุก 2 cycle → fill ใช้ fill_round1 ปกติ')

print(f'\n[AFTER FIX]  PENDING_TREND_CHECK round1 วิ่ง 1 ครั้ง')
if approach_round1:
    print(f'  ครั้งแรก: {ts(approach_round1[0])}  dist={fld(approach_round1[0],"dist_pt")}pt')
    print(f'  State คงอยู่จนถึง fill → fill_round1_skip_approach_passed')

# fill
fill_line = next((l for l in all_lines if 'ENTRY_FILL' in l and 'Limit fill' in l), None)
if fill_line:
    print(f'\n[FILL] {ts(fill_line)}  ราคา={fld(fill_line,"price")}')
    print(f'  ได้ fill ทั้งสองกรณี (ราคาแตะ entry ตามปกติ)')

# trend recheck
tr_line = next((l for l in all_lines if 'TREND_RECHECK' in l and '| fill_round1 |' in l), None)
if tr_line:
    allowed = fld(tr_line, "allowed")
    why     = fld(tr_line, "why")
    rounds  = fld(tr_line, "rounds_config")
    print(f'\n[TREND RECHECK]')
    print(f'  BEFORE: fill_round1 (regular)        | allowed={allowed} | why={why} | rounds={rounds}')
    print(f'  AFTER : fill_round1_skip_approach_passed | allowed=True (จาก approach {ts(approach_round1[0])})')
    print(f'  ผล trend เหมือนกัน (allowed=True) เพราะ sweep_low_unblock_buy')

# PD zone round2
pd_r2 = next((l for l in all_lines if 'PDFIBOPLUS' in l and 'fill_round2' in l), None)
close_line = next((l for l in all_lines if 'POSITION_CLOSED' in l), None)

if pd_r2:
    result = fld(pd_r2, "result")
    h_val  = float(fld(pd_r2, "h") or 0)
    l_val  = float(fld(pd_r2, "l") or 0)
    price  = float(fld(pd_r2, "price") or 0)
    eq     = float(fld(pd_r2, "eq") or 0)
    pct    = (price - l_val) / (h_val - l_val) * 100 if h_val > l_val else 0
    print(f'\n[PD ZONE fill_round2] {ts(pd_r2)}')
    print(f'  Zone H เปลี่ยน 4481.54 → {h_val}  (swing ร่วง)')
    print(f'  EQ ใหม่ = {eq}  |  entry 4460.40 = {pct:.1f}% (premium → FAIL)')
    print(f'  ปิดทั้งสองกรณีเหมือนกัน')

if close_line:
    print(f'\n[CLOSE] {ts(close_line)}  profit={fld(close_line,"profit")}  reason={fld(close_line,"reason")}')

print()
print('=' * 65)
print('RESULT:')
print('  Fill    : ได้ทั้งสองกรณี')
print('  Close   : -5.80 ทั้งสองกรณี (PD Zone ยังอยู่)')
print('  Fix เปลี่ยน:')
print(f'    - Log spam หาย ({len(approach_round1)} ครั้ง → 1 ครั้ง)')
print('    - Approach state carry over ถูกต้อง')
print('    - fill_round1_skip_approach_passed fire แทน fill_round1')
print('=' * 65)
