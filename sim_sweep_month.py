"""
sim_sweep_month.py — Sim sweep_filter fix สำหรับทุก order เดือน Jun ที่โดน sweep unblock
ตรวจว่าหลัง fix order ไหนยังผ่าน / ไม่ผ่าน และ P/L ต่างกันเท่าไหร่
"""
import io, sys, os, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
os.chdir(os.path.dirname(os.path.abspath(__file__)))
from datetime import datetime, timezone, timedelta
import MetaTrader5 as mt5
import config

config.mt5_initialize(mt5)
UTC6 = timezone(timedelta(hours=6))
SYM  = config.SYMBOL

def bkk(ts): return datetime.fromtimestamp(int(ts), UTC6).strftime('%H:%M %d-%b')

# ── ดึง M5 และ M15 ทั้งเดือน ─────────────────────────────────────────
m5_all  = list(mt5.copy_rates_range(SYM, mt5.TIMEFRAME_M5,
    datetime(2026,6,1,0,0,tzinfo=UTC6).astimezone(timezone.utc),
    datetime(2026,6,6,0,0,tzinfo=UTC6).astimezone(timezone.utc)))
m15_all = list(mt5.copy_rates_range(SYM, mt5.TIMEFRAME_M15,
    datetime(2026,6,1,0,0,tzinfo=UTC6).astimezone(timezone.utc),
    datetime(2026,6,6,0,0,tzinfo=UTC6).astimezone(timezone.utc)))

# M1 สำหรับ sweep M1
m1_all  = list(mt5.copy_rates_range(SYM, mt5.TIMEFRAME_M1,
    datetime(2026,6,4,22,0,tzinfo=UTC6).astimezone(timezone.utc),
    datetime(2026,6,5,10,0,tzinfo=UTC6).astimezone(timezone.utc)))
mt5.shutdown()

TF_RATES = {
    'M1':  (m1_all,  60),
    'M5':  (m5_all,  300),
    'M15': (m15_all, 900),
}
TF_NEXT  = {'M1':'M5', 'M5':'M15', 'M15':'H1'}
TF_NEXT_RATES = {'M1': m5_all, 'M5': m15_all}

def get_hhll_at(tf, as_of_ts, RIGHT=5):
    rates, secs = TF_RATES[tf]
    closed = [r for r in rates if int(r['time'])+secs <= as_of_ts]
    n = len(closed)
    pivots = []
    for i in range(RIGHT, n-RIGHT):
        bar = closed[i]
        h,l,t = float(bar['high']), float(bar['low']), int(bar['time'])
        L = closed[i-RIGHT:i]; R = closed[i+1:i+RIGHT+1]
        if len(R)<RIGHT: continue
        if all(h>=float(r['high']) for r in L) and all(h>=float(r['high']) for r in R):
            pivots.append(('H',h,t))
        if all(l<=float(r['low'])  for r in L) and all(l<=float(r['low'])  for r in R):
            pivots.append(('L',l,t))
    labeled=[]; ph=pl=None
    for typ,price,ts in pivots:
        if typ=='H': lbl='HH' if ph is None or price>ph else 'LH'; ph=price
        else:        lbl='HL' if pl is None or price>pl else 'LL'; pl=price
        labeled.append((lbl,price,ts))
    lows  = [(l,p,t) for l,p,t in labeled if l in ('HL','LL')]
    highs = [(l,p,t) for l,p,t in labeled if l in ('HH','LH')]
    latest_low  = max(lows,  key=lambda x:x[2]) if lows  else None
    latest_high = max(highs, key=lambda x:x[2]) if highs else None
    return latest_low, latest_high

def htf_confirm(tf, b_ts, ref_price, is_low):
    htf_rates = TF_NEXT_RATES.get(tf, [])
    if not htf_rates: return True  # ไม่มี HTF → pass
    htf_secs = TF_RATES.get(TF_NEXT.get(tf,''), (None,900))[1]
    for idx in range(len(htf_rates)-1):
        rt = int(htf_rates[idx]['time'])
        if rt <= b_ts < rt+htf_secs:
            htfb = htf_rates[idx]; htfn = htf_rates[idx+1]
            if is_low:
                return float(htfb['low'])<ref_price and float(htfn['close'])>float(htfn['open'])
            else:
                return float(htfb['high'])>ref_price and float(htfn['close'])<float(htfn['open'])
    return False

def sweep_valid_fixed(tf, signal, create_ts):
    """ตรวจว่า sweep unblock ยังผ่านไหมด้วย logic ที่ fix แล้ว"""
    rates, secs = TF_RATES.get(tf, (m5_all,300))
    latest_low, latest_high = get_hhll_at(tf, create_ts)

    if signal == 'BUY':  # sweep_low_unblock_buy → ต้องมี valid sweep low
        if not latest_low: return False, 'no LL/HL pivot'
        ref_lbl, ref_price, ref_time = latest_low
        closed = [r for r in rates if int(r['time'])+secs <= create_ts]
        bars_after = [r for r in closed if int(r['time']) > ref_time]
        for i in range(len(bars_after)-1):
            b=bars_after[i]; nxt=bars_after[i+1]
            bo,bl=float(b['open']),float(b['low'])
            no,nc=float(nxt['open']),float(nxt['close'])
            b_ts=int(b['time'])
            if bo>ref_price and bl<ref_price and nc>no:
                if htf_confirm(tf, b_ts, ref_price, True):
                    return True, f'{ref_lbl}={ref_price:.2f} sweep {bkk(b_ts)}'
        return False, f'no valid sweep of {ref_lbl}={ref_price:.2f}'

    else:  # sweep_high_unblock_sell → ต้องมี valid sweep high
        if not latest_high: return False, 'no HH/LH pivot'
        ref_lbl, ref_price, ref_time = latest_high
        closed = [r for r in rates if int(r['time'])+secs <= create_ts]
        bars_after = [r for r in closed if int(r['time']) > ref_time]
        for i in range(len(bars_after)-1):
            b=bars_after[i]; nxt=bars_after[i+1]
            bo,bh=float(b['open']),float(b['high'])
            no,nc=float(nxt['open']),float(nxt['close'])
            b_ts=int(b['time'])
            if bo<ref_price and bh>ref_price and nc<no:
                if htf_confirm(tf, b_ts, ref_price, False):
                    return True, f'{ref_lbl}={ref_price:.2f} sweep {bkk(b_ts)}'
        return False, f'no valid sweep of {ref_lbl}={ref_price:.2f}'

# ── Orders ────────────────────────────────────────────────────────────
orders = [
    # ticket, tf, signal, why, create_bkk, status, profit_before
    ('537988219','M5','BUY','sweep_low','2026-06-05 07:40', 'CLOSED', -5.80),
    ('537986275','M5','BUY','sweep_low','2026-06-05 07:35', 'CLOSED', -5.67),
    ('537959048','M1','SELL','sweep_high','2026-06-05 05:30','CLOSED',  2.24),
    ('537959508','M1','SELL','sweep_high','2026-06-05 05:35','CANCELED', 0.00),
    ('537958101','M1','BUY','sweep_low', '2026-06-05 05:23','CANCELED', 0.00),
    ('538059433','M5','BUY','sweep_low','2026-06-05 09:50', 'PENDING',  0.00),
    ('538059434','M5','BUY','sweep_low','2026-06-05 09:50', 'PENDING',  0.00),
]

print('='*80)
print('SIM: sweep_filter fix — Jun 2026 orders ที่โดน sweep unblock')
print('='*80)
print(f'\n{"Ticket":>10}  {"TF":>3}  {"Sig":>4}  {"Sweep":>10}  {"Status":>8}  {"P/L ก่อน":>9}  {"Fix?":>12}  {"P/L หลัง":>9}')
print('-'*85)

total_before = 0.0
total_after  = 0.0

for tk, tf, sig, why, create_str, status, pnl_before in orders:
    create_ts = int(datetime.strptime(create_str,'%Y-%m-%d %H:%M').replace(tzinfo=UTC6).timestamp())
    valid, reason = sweep_valid_fixed(tf, sig, create_ts)

    if status == 'CLOSED':
        pnl_after = pnl_before if valid else 0.0
        fix_label = 'ผ่าน ✅' if valid else 'BLOCK ❌'
    elif status == 'CANCELED':
        pnl_after = 0.0
        fix_label = 'BLOCK ❌' if not valid else 'ผ่าน ✅'
    else:  # PENDING
        pnl_after = 0.0 if not valid else pnl_before
        fix_label = 'BLOCK ❌' if not valid else 'ผ่าน ✅'

    total_before += pnl_before
    total_after  += pnl_after
    print(f'{tk:>10}  {tf:>3}  {sig:>4}  {why:>10}  {status:>8}  {pnl_before:>+9.2f}  {fix_label:>12}  {pnl_after:>+9.2f}')
    print(f'{"":>10}  Reason: {reason}')

print('-'*85)
print(f'{"TOTAL":>10}  {"":>3}  {"":>4}  {"":>10}  {"":>8}  {total_before:>+9.2f}  {"":>12}  {total_after:>+9.2f}')
print()
print(f'P/L ก่อน fix : {total_before:+.2f}')
print(f'P/L หลัง fix  : {total_after:+.2f}')
print(f'ผลต่าง        : {total_after-total_before:+.2f}')
print('='*80)
