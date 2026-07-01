"""
sim_sweep_order.py — Simulate sweep state + order fill for #537988219
ตรวจสอบ sweep_low M5 ที่จุดต่างๆ และ outcome ของ order
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
LL_PRICE  = 4464.10   # LL pivot M5 06:00
LL_TIME   = datetime(2026,6,5,6,0, tzinfo=UTC6)
LL_TS     = int(LL_TIME.timestamp())

def bkk(ts):
    return datetime.fromtimestamp(ts, UTC6).strftime('%H:%M')

def get_m5(start_bkk, n=100):
    s = start_bkk.astimezone(timezone.utc)
    return mt5.copy_rates_from(SYM, mt5.TIMEFRAME_M5, s, n)

def get_m15(start_bkk, n=50):
    s = start_bkk.astimezone(timezone.utc)
    return mt5.copy_rates_from(SYM, mt5.TIMEFRAME_M15, s, n)

# ── ดึง M5 และ M15 ช่วงกว้าง ─────────────────────────────────────────
m5  = mt5.copy_rates_range(SYM, mt5.TIMEFRAME_M5,
        datetime(2026,6,5,5,0,tzinfo=UTC6).astimezone(timezone.utc),
        datetime(2026,6,5,8,30,tzinfo=UTC6).astimezone(timezone.utc))
m15 = mt5.copy_rates_range(SYM, mt5.TIMEFRAME_M15,
        datetime(2026,6,5,4,0,tzinfo=UTC6).astimezone(timezone.utc),
        datetime(2026,6,5,8,30,tzinfo=UTC6).astimezone(timezone.utc))
mt5.shutdown()

def check_sweep_low_at(check_ts: int) -> dict:
    """
    Replay: ณ เวลา check_ts มี SWEEP_LOW M5 ไหม?
    ใช้เฉพาะแท่งที่ปิดก่อน check_ts (simulate real-time)
    Pattern A: M5 bar b: low < LL_PRICE, bar b+1: close > open
    HTF (M15) confirm: M15 bar ที่คลุม b: low < LL_PRICE, M15 next ปิดเขียว
    """
    # bars_after = M5 ที่ปิดหลัง LL_TS และก่อน check_ts
    bars_after = [r for r in m5
                  if int(r['time']) > LL_TS and int(r['time']) + 300 <= check_ts]

    for i in range(len(bars_after) - 1):
        b   = bars_after[i]
        nxt = bars_after[i+1]
        bl  = float(b['low'])
        nc, no = float(nxt['close']), float(nxt['open'])

        # Pattern A: low < ref AND next ปิดเขียว
        if bl < LL_PRICE and nc > no:
            # HTF M15 confirm: M15 bar ที่คลุม b.time มี low < LL_PRICE AND M15 next ปิดเขียว
            b_ts   = int(b['time'])
            m15_cover = next((r for r in m15 if int(r['time']) <= b_ts < int(r['time'])+900), None)
            if m15_cover is None:
                continue
            m15_idx = list(m15).index(m15_cover)
            if m15_idx + 1 >= len(m15):
                continue
            m15_nxt = m15[m15_idx + 1]
            htf_ok = (float(m15_cover['low']) < LL_PRICE and
                      float(m15_nxt['close']) > float(m15_nxt['open']))
            if htf_ok:
                return {
                    'active': True,
                    'sweep_bar': f"M5 {bkk(b_ts)} L={bl:.2f}",
                    'confirm_bar': f"M5 {bkk(int(nxt['time']))} C={nc:.2f}",
                    'htf_sweep': f"M15 {bkk(int(m15_cover['time']))} L={float(m15_cover['low']):.2f}",
                    'htf_confirm': f"M15 {bkk(int(m15_nxt['time']))} C={float(m15_nxt['close']):.2f}",
                }
    return {'active': False}

# ── Key timestamps ────────────────────────────────────────────────────
KEY_TIMES = {
    'ORDER_CREATED (07:40)':    datetime(2026,6,5,7,40, tzinfo=UTC6),
    'Approach #1  (07:49)':     datetime(2026,6,5,7,49, tzinfo=UTC6),
    'Approach last(07:59)':     datetime(2026,6,5,7,59, tzinfo=UTC6),
    'FILL         (07:59:23)':  datetime(2026,6,5,7,59,30, tzinfo=UTC6),
}

print('='*65)
print('SIM: SWEEP_LOW M5 state replay — #537988219')
print(f'LL pivot: M5 06:00 BKK  L={LL_PRICE}')
print('='*65)

# หา sweep trigger time จริง
for r in m5:
    ts = int(r['time'])
    if ts + 300 > int(datetime(2026,6,5,6,45,tzinfo=UTC6).timestamp()):
        res = check_sweep_low_at(ts + 300)
        if res['active']:
            print(f'\nSWEEP_LOW first active after: M5 {bkk(ts)} closes')
            print(f"  Sweep bar  : {res['sweep_bar']}")
            print(f"  Confirm bar: {res['confirm_bar']}")
            print(f"  M15 sweep  : {res['htf_sweep']}")
            print(f"  M15 confirm: {res['htf_confirm']}")
            SWEEP_ACTIVE_FROM = ts + 300
            break

print()
print(f'{"Event":<28} {"SWEEP_LOW":>10}  Detail')
print('-'*65)

for label, dt in KEY_TIMES.items():
    ts = int(dt.timestamp())
    res = check_sweep_low_at(ts)
    status = 'ACTIVE ✅' if res['active'] else 'NOT active ❌'
    detail = res.get('sweep_bar','') if res['active'] else ''
    print(f'{label:<28} {status:>10}  {detail}')

# ── Outcome ───────────────────────────────────────────────────────────
print()
print('='*65)
print('OUTCOME (ไม่เปลี่ยนทั้ง before/after fix):')
print('  Approach check : sweep_low_unblock_buy → PASS (ทุก check)')
print('  Fill @ 07:59   : 4460.40')
print('  PD Zone R2     : FAIL (Swing H ร่วง 4481→4466 → 59.6% premium)')
print('  Close @ 08:00  : 4458.95  P/L = -5.80')
print('='*65)
