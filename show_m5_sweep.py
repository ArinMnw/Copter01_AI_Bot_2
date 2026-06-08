"""show_m5_sweep.py — แสดงแท่ง M5 ช่วง sweep low detection"""
import io, sys, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime, timezone, timedelta
import MetaTrader5 as mt5

mt5.initialize()
UTC6 = timezone(timedelta(hours=6))

# M5 ช่วง 05:20-06:40 BKK เพื่อดู swing low + sweep bar
start = datetime(2026,6,5,5,20, tzinfo=UTC6).astimezone(timezone.utc)
end   = datetime(2026,6,5,6,40, tzinfo=UTC6).astimezone(timezone.utc)

rates = mt5.copy_rates_range('XAUUSD.iux', mt5.TIMEFRAME_M5, start, end)
mt5.shutdown()

if rates is None or len(rates) == 0:
    print('ไม่ได้ข้อมูล MT5')
    sys.exit(1)

LL_PRICE = 4464.10   # LL pivot ที่เห็นใน HHLL

print(f'M5  XAUUSD.iux  |  05:20-06:40 BKK  |  LL pivot = {LL_PRICE}')
print(f'{"Time":>6}  {"Open":>8}  {"High":>8}  {"Low":>8}  {"Close":>8}  C  Note')
print('-' * 65)

ll_bar_idx  = None
sweep_bar_idx = None

for i, r in enumerate(rates):
    t  = datetime.fromtimestamp(r['time'], UTC6).strftime('%H:%M')
    o, h, l, c = float(r['open']), float(r['high']), float(r['low']), float(r['close'])
    color = 'G' if c >= o else 'R'

    note = ''
    # หา bar ที่มี Low ต่ำสุด (LL pivot)
    if abs(l - LL_PRICE) < 0.02:
        note = '◀ SWING LOW (LL pivot = 4464.10)'
        ll_bar_idx = i
    # หา sweep bar = แท่งแรกหลัง LL ที่ปิดเขียว
    elif ll_bar_idx is not None and i > ll_bar_idx and color == 'G' and sweep_bar_idx is None:
        note = '◀ SWEEP BAR (แรกหลัง LL ปิดเขียว → SWEEP_LOW active)'
        sweep_bar_idx = i

    print(f'{t:>6}  {o:>8.2f}  {h:>8.2f}  {l:>8.2f}  {c:>8.2f}  {color}  {note}')

print()
if ll_bar_idx is not None:
    r = rates[ll_bar_idx]
    t = datetime.fromtimestamp(r['time'], UTC6).strftime('%H:%M')
    print(f'Swing LOW bar : M5 {t} BKK  L={float(r["low"]):.2f}')
if sweep_bar_idx is not None:
    r = rates[sweep_bar_idx]
    t = datetime.fromtimestamp(r['time'], UTC6).strftime('%H:%M')
    print(f'Sweep bar     : M5 {t} BKK  O={float(r["open"]):.2f} C={float(r["close"]):.2f} (เขียว)')
    print(f'→ SWEEP_LOW state active ตั้งแต่ {t} BKK')
