"""
sim_sweep_replay.py — Replay SWEEP_LOW detection M5 ด้วย reference ที่ถูกต้อง
Reference = HL หรือ LL ที่ใหม่กว่า (ตาม _get_latest_low_swing)
"""
import io, sys, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime, timezone, timedelta
import MetaTrader5 as mt5
import config

config.mt5_initialize(mt5)
UTC6 = timezone(timedelta(hours=6))
SYM  = config.SYMBOL

def bkk(ts):
    return datetime.fromtimestamp(int(ts), UTC6).strftime('%H:%M')

# ── ดึงข้อมูล M5 และ M15 ─────────────────────────────────────────────
m5_rates = mt5.copy_rates_range(SYM, mt5.TIMEFRAME_M5,
    datetime(2026,6,4,18,0,tzinfo=UTC6).astimezone(timezone.utc),
    datetime(2026,6,5,8,30,tzinfo=UTC6).astimezone(timezone.utc))

m15_rates = mt5.copy_rates_range(SYM, mt5.TIMEFRAME_M15,
    datetime(2026,6,4,16,0,tzinfo=UTC6).astimezone(timezone.utc),
    datetime(2026,6,5,8,30,tzinfo=UTC6).astimezone(timezone.utc))
mt5.shutdown()

m5  = list(m5_rates)
m15 = list(m15_rates)

def htf_confirm_low(b_ts, ref_price):
    """M15 bar คลุม b_ts มี low < ref_price AND M15 ถัดไปปิดเขียว"""
    for idx in range(len(m15)-1):
        rt = int(m15[idx]['time'])
        if rt <= b_ts < rt + 900:
            m15b = m15[idx]
            m15n = m15[idx+1]
            return (float(m15b['low']) < ref_price and
                    float(m15n['close']) > float(m15n['open']))
    return False

def find_hhll_at(as_of_ts):
    """
    คำนวณ HHLL pivots ที่ confirmed ณ เวลา as_of_ts
    Pivot HIGH = แท่ง M5 ที่ H สูงกว่า 5 แท่งซ้ายและ 5 แท่งขวา (HHLL_RIGHT=5)
    Pivot LOW  = แท่ง M5 ที่ L ต่ำกว่า 5 แท่งซ้ายและ 5 แท่งขวา
    ใช้เฉพาะแท่งที่ปิดก่อน as_of_ts และมีแท่งขวาครบ 5 แท่งปิดแล้ว
    """
    RIGHT = 5
    closed = [r for r in m5 if int(r['time'])+300 <= as_of_ts]
    n = len(closed)
    pivots = []
    for i in range(RIGHT, n - RIGHT):
        bar = closed[i]
        h = float(bar['high'])
        l = float(bar['low'])
        t = int(bar['time'])
        left  = closed[i-RIGHT:i]
        right = closed[i+1:i+RIGHT+1]
        if len(right) < RIGHT:
            continue
        # Pivot HIGH
        if all(h >= float(r['high']) for r in left) and all(h >= float(r['high']) for r in right):
            pivots.append(('H', h, t))
        # Pivot LOW
        if all(l <= float(r['low']) for r in left) and all(l <= float(r['low']) for r in right):
            pivots.append(('L', l, t))

    # HHLL logic: label each pivot
    labeled = []
    prev_h = prev_l = None
    for typ, price, ts in pivots:
        if typ == 'H':
            if prev_h is None:
                lbl = 'HH'
            else:
                lbl = 'HH' if price > prev_h else 'LH'
            prev_h = price
        else:
            if prev_l is None:
                lbl = 'HL'
            else:
                lbl = 'LL' if price < prev_l else 'HL'
            prev_l = price
        labeled.append((lbl, price, ts))

    # หา latest low swing (HL หรือ LL ที่ใหม่กว่า)
    low_swings  = [(lbl,p,t) for lbl,p,t in labeled if lbl in ('HL','LL')]
    high_swings = [(lbl,p,t) for lbl,p,t in labeled if lbl in ('HH','LH')]
    latest_low  = max(low_swings,  key=lambda x: x[2]) if low_swings  else None
    latest_high = max(high_swings, key=lambda x: x[2]) if high_swings else None
    return latest_low, latest_high, labeled

def check_sweep_low_correct(as_of_ts):
    """
    ตรวจ SWEEP_LOW ณ เวลา as_of_ts โดยใช้ reference ที่ถูกต้อง:
    - latest_low_swing (HL หรือ LL ที่ใหม่กว่า)
    - bars_after = M5 bars ที่ปิดหลัง ref_time และก่อน as_of_ts
    - Pattern A: bar.low < ref_price AND next bar ปิดเขียว + M15 confirm
    """
    latest_low, _, _ = find_hhll_at(as_of_ts)
    if not latest_low:
        return None

    ref_lbl, ref_price, ref_time = latest_low
    closed = [r for r in m5 if int(r['time'])+300 <= as_of_ts]
    bars_after = [r for r in closed if int(r['time']) > ref_time]

    for i in range(len(bars_after)-1):
        b   = bars_after[i]
        nxt = bars_after[i+1]
        bl  = float(b['low'])
        bo = float(b['open'])
        nc, no = float(nxt['close']), float(nxt['open'])
        b_ts = int(b['time'])

        if bo > ref_price and bl < ref_price and nc > no:
            if htf_confirm_low(b_ts, ref_price):
                return {
                    'ref': f'{ref_lbl}={ref_price:.2f} @ {bkk(ref_time)}',
                    'sweep': f'M5 {bkk(b_ts)} L={bl:.2f}',
                    'confirm': f'M5 {bkk(int(nxt["time"]))} C={nc:.2f}',
                }
    return None

# ── Scan ทุก M5 bar ตั้งแต่ 05:00 หา sweep trigger ─────────────────
print('='*70)
print('Replay SWEEP_LOW M5 — ใช้ HL/LL ที่ใหม่กว่าเป็น reference')
print('='*70)
print(f'\n{"Time":>6}  {"Ref swing":>22}  {"Sweep result"}')
print('-'*70)

first_trigger = None
for r in m5:
    ts = int(r['time']) + 300  # หลังแท่งนี้ปิด
    t = bkk(int(r['time']))
    if t < '05:00' or t > '08:00':
        continue

    latest_low, _, labeled = find_hhll_at(ts)
    ref_str = f"{latest_low[0]}={latest_low[1]:.2f}@{bkk(latest_low[2])}" if latest_low else '-'

    result = check_sweep_low_correct(ts)
    if result:
        if first_trigger is None:
            first_trigger = (t, result)
            print(f'{t:>6}  {ref_str:>22}  *** SWEEP_LOW TRIGGERED ***')
            print(f'       Ref  : {result["ref"]}')
            print(f'       Sweep: {result["sweep"]}')
            print(f'       Confirm:{result["confirm"]}')
        else:
            print(f'{t:>6}  {ref_str:>22}  (still active from {first_trigger[0]})')
    else:
        print(f'{t:>6}  {ref_str:>22}  -')

print()
if first_trigger:
    print(f'→ SWEEP_LOW first triggered after M5 {first_trigger[0]} BKK')
