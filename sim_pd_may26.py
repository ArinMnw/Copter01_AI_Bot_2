"""
sim_pd_may26.py — Sim PD Zone Fix ตั้งแต่ 2026-05-26 เป็นต้นไป
เปรียบเทียบ Old P/L vs New P/L (multi-TF skip_no_data → check จริง)
"""
import glob, re, os, sys, csv
from datetime import datetime, timedelta
from collections import defaultdict
import MetaTrader5 as mt5
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import config
from config import SYMBOL

DATE_FROM = datetime(2026, 5, 26, 0, 0, 0)

mt5.initialize()

TF_ORDER = ["M1","M5","M15","M30","H1","H4","H12","D1","W1","MN1"]
TF_MAP_MT5 = {
    "M1":  mt5.TIMEFRAME_M1,  "M5":  mt5.TIMEFRAME_M5,
    "M15": mt5.TIMEFRAME_M15, "M30": mt5.TIMEFRAME_M30,
    "H1":  mt5.TIMEFRAME_H1,  "H4":  mt5.TIMEFRAME_H4,
    "H12": mt5.TIMEFRAME_H12, "D1":  mt5.TIMEFRAME_D1,
}
SPREAD_EST = 0.20
BKK_OFFSET = 1

def smallest_tf(tf_str):
    if not any(s in str(tf_str) for s in ["_", "+", ","]):
        return tf_str
    parts = re.findall(r'[A-Z]\d+', str(tf_str))
    if not parts:
        return tf_str
    return min(parts, key=lambda t: TF_ORDER.index(t) if t in TF_ORDER else 99)

def is_multitf(tf_str):
    return any(s in str(tf_str) for s in ["_", "+", ",", "["])

def log_files():
    from log_sources import bot_log_files
    return bot_log_files()

def fld(line, key):
    m = re.search(rf'{key}=([^|\s]+)', line)
    return m.group(1).strip() if m else None

# ── 1. เก็บ skip_no_data tickets ────────────────────────────────
skip_tickets = set()
for path in log_files():
    try:
        for line in open(path, encoding='utf-8', errors='replace'):
            if 'fill_round1_skip_no_data' in line:
                tk = fld(line, 'ticket')
                if tk: skip_tickets.add(tk)
    except: pass
print(f"skip_no_data tickets (all time): {len(skip_tickets)}")

# ── 2. ดึง fill info ─────────────────────────────────────────────
fills  = {}
closes = {}
seen_close = set()

for path in log_files():
    try:
        for line in open(path, encoding='utf-8', errors='replace'):
            m = re.match(r'^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]\s+(\S+)', line)
            if not m: continue
            ts_str, kind = m.group(1), m.group(2)
            tk = fld(line, 'ticket')
            if not tk: continue

            if kind == 'ENTRY_FILL' and tk in skip_tickets:
                try:
                    ts_dt = datetime.strptime(ts_str, '%Y-%m-%d %H:%M:%S')
                except: continue
                if ts_dt < DATE_FROM: continue  # filter date
                raw_tf = fld(line, 'tf') or ''
                fills[tk] = {
                    'fill_ts':    ts_str,
                    'fill_ts_dt': ts_dt,
                    'fill_price': float(fld(line, 'price') or 0),
                    'raw_tf':     raw_tf,
                    'tf':         smallest_tf(raw_tf),
                    'side':       fld(line, 'side') or fld(line, 'signal') or '',
                    'sid':        fld(line, 'sid') or '',
                    'is_multitf': is_multitf(raw_tf),
                }
            elif kind == 'POSITION_CLOSED' and tk not in seen_close and 'XAUUSD' in line:
                seen_close.add(tk)
                closes[tk] = {
                    'profit':    float(fld(line, 'profit') or 0),
                    'close_ts':  ts_str,
                }
    except: pass

in_range = {tk: fi for tk, fi in fills.items()}
print(f"Fills from {DATE_FROM.date()}: {len(in_range)} | มี POSITION_CLOSED: {sum(1 for tk in in_range if tk in closes)}")

# ── 3. Fetch HHLL + check PD Zone ────────────────────────────────
results = []

for tk in sorted(in_range, key=lambda x: in_range[x]['fill_ts']):
    fi = in_range[tk]
    cl = closes.get(tk)
    if not cl:
        continue  # ยังเปิดอยู่

    tf_single = fi['tf']
    if tf_single not in TF_MAP_MT5:
        results.append({'tk': tk, 'fi': fi, 'cl': cl, 'pd_result': 'NO_DATA', 'diff': 0.0,
                        'eq': 0, 'actual_pl': cl['profit'], 'sim_pl': cl['profit']})
        continue

    fill_dt = fi['fill_ts_dt'] + timedelta(hours=BKK_OFFSET)
    rates = mt5.copy_rates_from(SYMBOL, TF_MAP_MT5[tf_single], fill_dt, 50)
    if rates is None or len(rates) < 10:
        results.append({'tk': tk, 'fi': fi, 'cl': cl, 'pd_result': 'NO_DATA', 'diff': 0.0,
                        'eq': 0, 'actual_pl': cl['profit'], 'sim_pl': cl['profit']})
        continue

    swing_h = max(float(r['high']) for r in rates[-30:])
    swing_l = min(float(r['low'])  for r in rates[-30:])
    eq       = (swing_h + swing_l) / 2.0
    fill_p   = fi['fill_price']
    side     = fi['side']

    if side == 'BUY':
        pd_pass = fill_p < eq
    elif side == 'SELL':
        pd_pass = fill_p > eq
    else:
        pd_pass = True

    actual_pl = cl['profit']
    sim_pl    = -SPREAD_EST if not pd_pass else actual_pl
    diff      = sim_pl - actual_pl

    results.append({
        'tk': tk, 'fi': fi, 'cl': cl,
        'pd_result': 'PASS' if pd_pass else 'FAIL',
        'eq': round(eq, 2),
        'actual_pl': actual_pl, 'sim_pl': sim_pl, 'diff': diff,
    })

# ── 4. Summary ───────────────────────────────────────────────────
print()
print("=" * 75)
print(f"  Sim: PD Zone Fix — orders ตั้งแต่ {DATE_FROM.date()}")
print("=" * 75)

n_pass   = sum(1 for r in results if r['pd_result'] == 'PASS')
n_fail   = sum(1 for r in results if r['pd_result'] == 'FAIL')
n_nodata = sum(1 for r in results if r['pd_result'] == 'NO_DATA')
old_total  = sum(r['actual_pl'] for r in results)
new_total  = sum(r['sim_pl']    for r in results)
total_diff = sum(r['diff']       for r in results)

print(f"  Orders analyzed:  {len(results)}")
print(f"  PD PASS:          {n_pass}")
print(f"  PD FAIL:          {n_fail}")
print(f"  NO DATA:          {n_nodata}")
print(f"\n  Old P/L รวม:  {old_total:+.2f} USD")
print(f"  New P/L รวม:  {new_total:+.2f} USD")
print(f"  DIFF:         {total_diff:+.2f} USD  {'✅ ดีขึ้น' if total_diff > 0 else '❌ แย่ลง'}")

print()
print("  By Strategy:")
by_sid = defaultdict(lambda: [0, 0, 0.0, 0.0, 0.0])
for r in results:
    sid = r['fi']['sid'] or '?'
    by_sid[sid][0] += 1
    by_sid[sid][1] += (1 if r['pd_result'] == 'FAIL' else 0)
    by_sid[sid][2] += r['actual_pl']
    by_sid[sid][3] += r['sim_pl']
    by_sid[sid][4] += r['diff']
for sid, (cnt, fail, old, new, diff) in sorted(by_sid.items(), key=lambda x: -abs(x[1][4])):
    print(f"    S{sid:2}: {cnt:4} orders | fail={fail:3} | old={old:+8.2f} | new={new:+8.2f} | diff={diff:+7.2f}")

mt5.shutdown()

# ── 5. Save CSV ──────────────────────────────────────────────────
os.makedirs('excel_reports', exist_ok=True)
out_csv = 'excel_reports/sim_pd_may26.csv'
with open(out_csv, 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.writer(f)
    w.writerow(['ticket','fill_ts','side','raw_tf','tf_used','sid','is_multitf',
                'fill_price','eq','pd_result','actual_pl','sim_pl','diff','close_ts'])
    for r in results:
        fi, cl = r['fi'], r['cl']
        w.writerow([r['tk'], fi['fill_ts'], fi['side'], fi['raw_tf'], fi['tf'],
                    fi['sid'], fi['is_multitf'], fi['fill_price'],
                    r.get('eq',''), r['pd_result'],
                    r['actual_pl'], r['sim_pl'], r['diff'], cl['close_ts']])
print(f"\n  บันทึก -> {out_csv}")
