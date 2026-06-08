"""debug_sweep.py — ตรวจ HHLL simulation vs จริง และ sweep candidates"""
import io, sys, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
os.chdir(os.path.dirname(os.path.abspath(__file__)))
from datetime import datetime, timezone, timedelta
import MetaTrader5 as mt5

mt5.initialize()
UTC6 = timezone(timedelta(hours=6))
SYM  = 'XAUUSD.iux'

def bkk(ts): return datetime.fromtimestamp(int(ts), UTC6).strftime('%H:%M %d-%b')

m5 = list(mt5.copy_rates_range(SYM, mt5.TIMEFRAME_M5,
    datetime(2026,6,4,20,0,tzinfo=UTC6).astimezone(timezone.utc),
    datetime(2026,6,5,8,30,tzinfo=UTC6).astimezone(timezone.utc)))
m15 = list(mt5.copy_rates_range(SYM, mt5.TIMEFRAME_M15,
    datetime(2026,6,4,18,0,tzinfo=UTC6).astimezone(timezone.utc),
    datetime(2026,6,5,8,30,tzinfo=UTC6).astimezone(timezone.utc)))
mt5.shutdown()

# ── HHLL calculation ณ 07:40 BKK ─────────────────────────────────────
as_of_ts = int(datetime(2026,6,5,7,40,tzinfo=UTC6).timestamp())
RIGHT = 5
closed = [r for r in m5 if int(r['time'])+300 <= as_of_ts]
n = len(closed)

pivots = []
for i in range(RIGHT, n-RIGHT):
    bar = closed[i]
    h, l, t = float(bar['high']), float(bar['low']), int(bar['time'])
    left  = closed[i-RIGHT:i]
    right = closed[i+1:i+RIGHT+1]
    if len(right) < RIGHT: continue
    if all(h >= float(r['high']) for r in left) and all(h >= float(r['high']) for r in right):
        pivots.append(('H', h, t))
    if all(l <= float(r['low'])  for r in left) and all(l <= float(r['low'])  for r in right):
        pivots.append(('L', l, t))

labeled = []; prev_h = prev_l = None
for typ, price, ts in pivots:
    if typ == 'H':
        lbl = 'HH' if prev_h is None or price > prev_h else 'LH'; prev_h = price
    else:
        lbl = 'HL' if prev_l is None or price > prev_l else 'LL'; prev_l = price
    labeled.append((lbl, price, ts))

print('HHLL pivots M5 ณ 07:40 BKK (ล่าสุด 15 จุด):')
for lbl,p,t in labeled[-15:]:
    print(f'  {lbl}  {p:.2f}  @ {bkk(t)}')

low_sw  = [(l,p,t) for l,p,t in labeled if l in ('HL','LL')]
high_sw = [(l,p,t) for l,p,t in labeled if l in ('HH','LH')]
latest_low  = max(low_sw,  key=lambda x: x[2]) if low_sw  else None
latest_high = max(high_sw, key=lambda x: x[2]) if high_sw else None

print(f'\nLatest LOW swing : {latest_low}')
print(f'Latest HIGH swing: {latest_high}')

# ── ตรวจ sweep candidates รอบ HL=4476.85 ─────────────────────────────
print('\n\nSweep candidates สำหรับ HL=4476.85 @ 02:45:')
HL_PRICE = 4476.85
HL_TIME  = int(datetime(2026,6,5,2,45,tzinfo=UTC6).timestamp())
bars_after = [r for r in closed if int(r['time']) > HL_TIME]

print(f'{"Time":>6}  {"O":>8}  {"L":>8}  O>ref  L<ref  NxtG  Note')
print('-'*70)
for i in range(len(bars_after)-1):
    b   = bars_after[i]
    nxt = bars_after[i+1]
    bo, bl = float(b['open']), float(b['low'])
    no, nc = float(nxt['open']), float(nxt['close'])
    t = bkk(int(b['time']))
    o_ok = bo > HL_PRICE
    l_ok = bl < HL_PRICE
    g_ok = nc > no

    if o_ok or l_ok:
        # HTF check
        b_ts = int(b['time'])
        htf_ok = False
        for idx in range(len(m15)-1):
            rt = int(m15[idx]['time'])
            if rt <= b_ts < rt+900:
                htf_ok = (float(m15[idx]['low']) < HL_PRICE and
                          float(m15[idx+1]['close']) > float(m15[idx+1]['open']))
                break
        note = ''
        if o_ok and l_ok:
            note = f'SWEEP CAND htf={htf_ok}'
            if o_ok and l_ok and g_ok and htf_ok:
                note = '*** TRIGGER ***'
        print(f'{t:>6}  {bo:>8.2f}  {bl:>8.2f}  {str(o_ok):>5}  {str(l_ok):>5}  {str(g_ok):>5}  {note}')
    if t > '06:00': break  # หยุดหลัง 06:00
