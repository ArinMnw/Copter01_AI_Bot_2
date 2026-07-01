"""show_m5_sweep2.py — ดูแท่ง M5 ครบช่วง และ simulate sweep detection จริง"""
import io, sys, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime, timezone, timedelta
import MetaTrader5 as mt5
import config

config.mt5_initialize(mt5)
UTC6 = timezone(timedelta(hours=6))

# ดึง M5 ช่วงกว้างขึ้น 05:00-08:00 BKK
start = datetime(2026,6,5,5,0, tzinfo=UTC6).astimezone(timezone.utc)
end   = datetime(2026,6,5,8,0, tzinfo=UTC6).astimezone(timezone.utc)
rates = mt5.copy_rates_range(config.SYMBOL, mt5.TIMEFRAME_M5, start, end)
mt5.shutdown()

LL_PRICE = 4464.10   # LL pivot ที่ confirmed ใน HHLL
LL_TIME  = "06:00"

print(f'M5  {config.SYMBOL}  05:00-08:00 BKK  |  LL pivot = {LL_PRICE} @ {LL_TIME}')
print(f'{"Time":>6}  {"O":>8}  {"H":>8}  {"L":>8}  {"C":>8}  C  Sweep check')
print('-' * 75)

ll_found = False
sweep_bar = None
sweep_nxt = None

for i, r in enumerate(rates):
    t  = datetime.fromtimestamp(r['time'], UTC6).strftime('%H:%M')
    o, h, l, c = float(r['open']), float(r['high']), float(r['low']), float(r['close'])
    color = 'G' if c >= o else 'R'

    note = ''
    if t == LL_TIME:
        note = f'◀ LL pivot = {LL_PRICE} (HHLL confirmed ~06:25)'
        ll_found = True
    elif ll_found and sweep_bar is None:
        # Pattern A: low < LL_PRICE → check next
        if l < LL_PRICE:
            note = f'*** LOW < LL ({l:.2f} < {LL_PRICE}) = SWEEP CANDIDATE ***'
            sweep_bar = (t, l, color, i)
        # ถ้าเจอ sweep bar แล้ว check next
    elif sweep_bar is not None and sweep_nxt is None:
        idx = sweep_bar[3]
        if i == idx + 1:
            if color == 'G':
                note = f'*** SWEEP_LOW TRIGGERED (bar ถัดจาก sweep ปิดเขียว) ***'
                sweep_nxt = (t, o, c, color)
            else:
                note = f'(ถัดจาก sweep แต่ปิดแดง → Pattern A ยังไม่ trigger)'
                sweep_bar = None  # reset ต้องหาใหม่

    print(f'{t:>6}  {o:>8.2f}  {h:>8.2f}  {l:>8.2f}  {c:>8.2f}  {color}  {note}')

print()
if sweep_bar and sweep_nxt:
    print(f'SWING LOW bar : M5 {LL_TIME} BKK  L={LL_PRICE}  (HHLL LL pivot)')
    print(f'SWEEP bar     : M5 {sweep_bar[0]} BKK  L={sweep_bar[1]:.2f} < LL={LL_PRICE}  [{sweep_bar[2]}]')
    print(f'Confirm bar   : M5 {sweep_nxt[0]} BKK  O={sweep_nxt[1]:.2f} C={sweep_nxt[2]:.2f}  [{sweep_nxt[3]}] ← ปิดเขียว')
    print(f'→ SWEEP_LOW active หลัง M5 {sweep_nxt[0]} BKK')
elif sweep_bar and not sweep_nxt:
    print(f'พบ sweep bar ที่ {sweep_bar[0]} แต่ bar ถัดไปปิดแดง → ยังไม่ trigger')
else:
    print(f'ไม่พบ bar ที่ low < {LL_PRICE} → อาจใช้ LL pivot อื่น หรือ Pattern B')
