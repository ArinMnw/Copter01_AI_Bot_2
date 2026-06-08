"""check_sweep_open.py — ตรวจ sweep bar ว่า Open > ref_price ไหม"""
import io, sys, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
os.chdir(os.path.dirname(os.path.abspath(__file__)))
from datetime import datetime, timezone, timedelta
import MetaTrader5 as mt5

mt5.initialize()
UTC6 = timezone(timedelta(hours=6))
SYM  = 'XAUUSD.iux'

def show(start_h, start_m, end_h, end_m, ref, label):
    r = mt5.copy_rates_range(SYM, mt5.TIMEFRAME_M5,
        datetime(2026,6,5,start_h,start_m,tzinfo=UTC6).astimezone(timezone.utc),
        datetime(2026,6,5,end_h,  end_m,  tzinfo=UTC6).astimezone(timezone.utc))
    print(f'\nM5 {start_h:02d}:{start_m:02d}-{end_h:02d}:{end_m:02d} BKK  |  ref({label}) = {ref}')
    print(f'{"Time":>6}  {"O":>8}  {"H":>8}  {"L":>8}  {"C":>8}  C  O>ref  L<ref  Note')
    print('-'*78)
    for x in r:
        t   = datetime.fromtimestamp(x['time'], UTC6).strftime('%H:%M')
        o,h,l,c = float(x['open']),float(x['high']),float(x['low']),float(x['close'])
        col     = 'G' if c >= o else 'R'
        o_above = o > ref
        l_below = l < ref
        note = ''
        if o_above and l_below:
            note = '<< SWEEP (O>ref AND L<ref)'
        elif l_below and not o_above:
            note = '(L<ref แต่ O ต่ำกว่า ref แล้ว = ไม่ใช่ sweep)'
        print(f'{t:>6}  {o:>8.2f}  {h:>8.2f}  {l:>8.2f}  {c:>8.2f}  {col}  {str(o_above):>5}  {str(l_below):>5}  {note}')

# ตรวจ 03:45 (sweep bar จาก simulation ก่อน) - ref = HL=4476.85
show(3, 20, 4, 10, 4476.85, 'HL=4476.85@02:45')

# ตรวจ 07:15 - ref = LL=4464.10
show(6, 50, 7, 40, 4464.10, 'LL=4464.10@06:00')

mt5.shutdown()

print()
print('='*60)
print('Bug ใน sweep_filter Pattern A:')
print('  ปัจจุบัน: if bl < ref_price and nc > no')
print('  ขาด    : ไม่เช็ค bo > ref_price (open ต้องเหนือ ref)')
print('  ผล     : bar ที่เปิดใต้ ref แล้วก็ trigger ได้ (ผิด)')
print()
print('Fix ที่ถูก:')
print('  if bo > ref_price and bl < ref_price and nc > ref_price:')
print('     open เหนือ ref  + low ต่ำกว่า ref  + next close กลับเหนือ ref')
