"""
sim_sweep_fixed.py — Sim sweep detection หลัง fix (bo > ref_price required)
ตรวจว่า SWEEP_LOW M5 ยังอยู่ไหมตอน order #537988219 create/approach/fill
"""
import io, sys, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
os.chdir(os.path.dirname(os.path.abspath(__file__)))
from datetime import datetime, timezone, timedelta
import MetaTrader5 as mt5

mt5.initialize()
UTC6 = timezone(timedelta(hours=6))
SYM  = 'XAUUSD.iux'

def bkk(ts): return datetime.fromtimestamp(int(ts), UTC6).strftime('%H:%M')

# ── ดึงข้อมูล ─────────────────────────────────────────────────────────
m5 = list(mt5.copy_rates_range(SYM, mt5.TIMEFRAME_M5,
    datetime(2026,6,4,18,0,tzinfo=UTC6).astimezone(timezone.utc),
    datetime(2026,6,5,8,30,tzinfo=UTC6).astimezone(timezone.utc)))
m15 = list(mt5.copy_rates_range(SYM, mt5.TIMEFRAME_M15,
    datetime(2026,6,4,16,0,tzinfo=UTC6).astimezone(timezone.utc),
    datetime(2026,6,5,8,30,tzinfo=UTC6).astimezone(timezone.utc)))
mt5.shutdown()

def htf_confirm_low(b_ts, ref_price):
    for idx in range(len(m15)-1):
        rt = int(m15[idx]['time'])
        if rt <= b_ts < rt + 900:
            m15b = m15[idx]; m15n = m15[idx+1]
            return (float(m15b['low']) < ref_price and
                    float(m15n['close']) > float(m15n['open']))
    return False

def find_hhll_at(as_of_ts):
    """คำนวณ HHLL pivots ที่ confirmed ณ as_of_ts (RIGHT=5 bars)"""
    RIGHT = 5
    closed = [r for r in m5 if int(r['time'])+300 <= as_of_ts]
    n = len(closed)
    pivots = []
    for i in range(RIGHT, n - RIGHT):
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

    low_sw  = [(l,p,t) for l,p,t in labeled if l in ('HL','LL')]
    high_sw = [(l,p,t) for l,p,t in labeled if l in ('HH','LH')]
    latest_low  = max(low_sw,  key=lambda x: x[2]) if low_sw  else None
    latest_high = max(high_sw, key=lambda x: x[2]) if high_sw else None
    return latest_low, latest_high

def check_sweep_low_fixed(as_of_ts):
    """
    SWEEP_LOW (FIXED): bo > ref_price AND bl < ref_price AND next GREEN + M15 confirm
    """
    latest_low, _ = find_hhll_at(as_of_ts)
    if not latest_low: return None
    ref_lbl, ref_price, ref_time = latest_low

    closed = [r for r in m5 if int(r['time'])+300 <= as_of_ts]
    bars_after = [r for r in closed if int(r['time']) > ref_time]

    for i in range(len(bars_after)-1):
        b   = bars_after[i]
        nxt = bars_after[i+1]
        bo, bl = float(b['open']),   float(b['low'])
        no, nc = float(nxt['open']), float(nxt['close'])
        b_ts   = int(b['time'])

        # Pattern A FIXED: open ต้องเหนือ ref ก่อน
        if bo > ref_price and bl < ref_price and nc > no:
            if htf_confirm_low(b_ts, ref_price):
                return {
                    'ref':     f'{ref_lbl}={ref_price:.2f} @ {bkk(ref_time)}',
                    'sweep':   f'M5 {bkk(b_ts)} O={bo:.2f} L={bl:.2f}',
                    'confirm': f'M5 {bkk(int(nxt["time"]))} C={nc:.2f}',
                }
    return None

# ── Scan หา first trigger ─────────────────────────────────────────────
print('='*68)
print('SIM #537988219 — SWEEP_LOW M5 หลัง fix (bo > ref required)')
print('='*68)
print(f'\nScan M5 02:00-08:00 BKK...\n')

first_trigger = None
scan_times = [r for r in m5 if '2026-06-05' in
              datetime.fromtimestamp(int(r['time']),UTC6).strftime('%Y-%m-%d')]

for r in scan_times:
    ts = int(r['time']) + 300
    t  = bkk(int(r['time']))
    if t < '02:00': continue
    if t > '08:00': break

    res = check_sweep_low_fixed(ts)
    if res and first_trigger is None:
        first_trigger = (t, res)
        print(f'SWEEP_LOW first triggered หลัง M5 {t} BKK')
        print(f'  Ref    : {res["ref"]}')
        print(f'  Sweep  : {res["sweep"]}  ← O > ref, L < ref ✅')
        print(f'  Confirm: {res["confirm"]}')

if first_trigger is None:
    print('ไม่พบ SWEEP_LOW ที่ถูกต้องเลย (ด้วย logic ที่ fix แล้ว)')

# ── ตรวจ key checkpoints ─────────────────────────────────────────────
print()
KEY = {
    'ORDER_CREATED (07:40)':   datetime(2026,6,5,7,40, tzinfo=UTC6),
    'Approach #1  (07:49)':    datetime(2026,6,5,7,49, tzinfo=UTC6),
    'Approach last(07:59)':    datetime(2026,6,5,7,59, tzinfo=UTC6),
    'FILL         (07:59:23)': datetime(2026,6,5,7,59,30, tzinfo=UTC6),
}
print(f'{"Event":<28} {"SWEEP_LOW (fixed)":>18}  Detail')
print('-'*68)
for label, dt in KEY.items():
    ts  = int(dt.timestamp())
    res = check_sweep_low_fixed(ts)
    # Persistence: ถ้า trigger แล้ว ยังอยู่ถ้า trend ไม่เปลี่ยน
    persisted = (first_trigger is not None and
                 ts >= int(datetime.strptime('2026-06-05 '+first_trigger[0],
                           '%Y-%m-%d %H:%M').replace(tzinfo=UTC6).timestamp()))
    status = 'ACTIVE ✅' if (res or persisted) else 'NOT active ❌'
    detail = res['sweep'] if res else (f'persist จาก {first_trigger[0]}' if persisted else '')
    print(f'{label:<28} {status:>18}  {detail}')

# ── ผลสรุป ────────────────────────────────────────────────────────────
print()
print('='*68)
if first_trigger:
    ft = first_trigger[0]
    order_ts = int(datetime(2026,6,5,7,40,tzinfo=UTC6).timestamp())
    trigger_ts = int(datetime.strptime('2026-06-05 '+ft,'%Y-%m-%d %H:%M').replace(tzinfo=UTC6).timestamp()) + 300
    if trigger_ts <= order_ts:
        print(f'SWEEP_LOW active ก่อน order create ({ft} < 07:40)')
        print('→ Approach check: sweep_low_unblock_buy → PASS')
        print('→ ORDER FILLS @ 07:59  P/L = -5.80')
    else:
        print(f'SWEEP_LOW triggered {ft} > 07:40 (หลัง order create)')
        print('→ Approach check ตอน order create: ไม่มี sweep → trend_allows_signal check ปกติ')
        print('→ M5 bear_strong + BUY → BLOCK → order ถูก cancel ก่อน fill')
else:
    print('ไม่มี SWEEP_LOW เลย')
    print('→ trend_allows_signal(M5, BUY) = False (bear_strong)')
    print('→ ORDER ไม่ได้ถูกสร้าง หรือถูก cancel ก่อน fill')
print('='*68)
