"""
sim_pd_multitf.py — Sim แก้ Bug PD_ZONE_CHECK skip_no_data สำหรับ multi-TF orders

ก่อนหน้า: order เช่น [M15_M30] → _gshl("[M15_M30]") ไม่มีข้อมูล → skip ตลอด
หลังแก้:  เลือก TF เล็กสุด (M15) → _gshl("M15") ทำงานได้ → check จริง

Logic sim:
  1. หา ticket ที่มี fill_round1_skip_no_data
  2. ดึง fill price, fill time, TF, side จาก ENTRY_FILL log
  3. ดึง POSITION_CLOSED profit
  4. Fetch HHLL จาก MT5 ที่ fill_time ด้วย TF เล็กสุด
  5. ตรวจ PD Zone: BUY ต้องอยู่ใน discount (price < EQ), SELL ใน premium (price > EQ)
  6. ถ้า FAIL → order จะถูกปิด ~fill_price (loss ≈ spread ~0.20)
  7. คำนวณ diff (จริง vs sim)
"""
import glob, re, os, sys
from datetime import datetime, timedelta
from collections import defaultdict
import MetaTrader5 as mt5
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import config
from config import SYMBOL

mt5.initialize()

TF_ORDER   = ["M1","M5","M15","M30","H1","H4","H12","D1","W1","MN1"]
TF_MAP_MT5 = {
    "M1":  mt5.TIMEFRAME_M1,  "M5":  mt5.TIMEFRAME_M5,
    "M15": mt5.TIMEFRAME_M15, "M30": mt5.TIMEFRAME_M30,
    "H1":  mt5.TIMEFRAME_H1,  "H4":  mt5.TIMEFRAME_H4,
    "H12": mt5.TIMEFRAME_H12, "D1":  mt5.TIMEFRAME_D1,
}
BKK_OFFSET = 1  # fetch +1h ตาม timezone rule

def smallest_tf(tf_str):
    """เลือก TF เล็กสุดจาก multi-TF string เช่น [M15_M30] → M15"""
    if not any(s in str(tf_str) for s in ["_", "+", ","]):
        return tf_str
    parts = re.findall(r'[A-Z]\d+', str(tf_str))
    if not parts:
        return tf_str
    return min(parts, key=lambda t: TF_ORDER.index(t) if t in TF_ORDER else 99)

def log_files():
    from log_sources import bot_log_files
    return bot_log_files()

def fld(line, key):
    m = re.search(rf'{key}=([^|\s]+)', line)
    return m.group(1).strip() if m else None

# ── 1. เก็บ tickets ที่มี skip_no_data ─────────────────────────
skip_tickets = set()
for path in log_files():
    try:
        for line in open(path, encoding='utf-8', errors='replace'):
            if 'fill_round1_skip_no_data' in line:
                tk = fld(line, 'ticket')
                if tk: skip_tickets.add(tk)
    except: pass

print(f"Tickets ที่มี skip_no_data: {len(skip_tickets)}")

# ── 2. ดึง fill info + close info ──────────────────────────────
fills   = {}  # ticket -> {fill_ts, fill_price, tf, side, raw_tf}
closes  = {}  # ticket -> {profit, close_price, close_ts}
seen_close = set()

for path in log_files():
    try:
        for line in open(path, encoding='utf-8', errors='replace'):
            m = re.match(r'^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]\s+(\S+)', line)
            if not m: continue
            ts, kind = m.group(1), m.group(2)
            tk = fld(line, 'ticket')
            if not tk or tk not in skip_tickets: continue

            if kind == 'ENTRY_FILL':
                raw_tf = fld(line, 'tf') or ''
                fills[tk] = {
                    'fill_ts':    ts,
                    'fill_price': float(fld(line, 'price') or 0),
                    'raw_tf':     raw_tf,
                    'tf':         smallest_tf(raw_tf),
                    'side':       fld(line, 'side') or fld(line, 'signal') or '',
                    'sid':        fld(line, 'sid') or '',
                }
            elif kind == 'POSITION_CLOSED' and tk not in seen_close and 'XAUUSD' in line:
                seen_close.add(tk)
                closes[tk] = {
                    'profit':      float(fld(line, 'profit') or 0),
                    'close_price': float(fld(line, 'close_price') or 0),
                    'close_ts':    ts,
                }
    except: pass

print(f"มี ENTRY_FILL: {len(fills)} | มี POSITION_CLOSED: {len(closes)}")

# ── 3. Fetch HHLL ณ fill_time + check PD Zone ──────────────────
SPREAD_EST = 0.20  # ค่า spread โดยประมาณ (USD, 0.04 lot)
LOT_VALUE  = 0.4   # 1 pt = $0.40 (XAUUSD 0.04 lot)

results = []

for tk in sorted(fills, key=lambda x: fills[x]['fill_ts']):
    fi = fills[tk]
    cl = closes.get(tk)
    if not cl:
        continue  # ยังเปิดอยู่ — ข้าม

    tf_single = fi['tf']
    if tf_single not in TF_MAP_MT5:
        continue

    fill_dt = datetime.strptime(fi['fill_ts'], '%Y-%m-%d %H:%M:%S') + timedelta(hours=BKK_OFFSET)

    # fetch rates ย้อนหลัง 50 แท่ง จาก fill_time
    rates = mt5.copy_rates_from(SYMBOL, TF_MAP_MT5[tf_single], fill_dt, 50)
    if rates is None or len(rates) < 10:
        results.append({'tk': tk, 'fi': fi, 'cl': cl, 'pd_result': 'NO_DATA', 'diff': 0.0})
        continue

    # HHLL แบบง่าย: swing_high = max(high[-30:]), swing_low = min(low[-30:])
    swing_h = max(float(r['high']) for r in rates[-30:])
    swing_l = min(float(r['low'])  for r in rates[-30:])
    eq       = (swing_h + swing_l) / 2.0
    fill_p   = fi['fill_price']
    side     = fi['side']

    # PD Zone check: BUY ควรอยู่ใน discount (fill_p < eq), SELL ใน premium (fill_p > eq)
    if side == 'BUY':
        pd_pass = fill_p < eq
    elif side == 'SELL':
        pd_pass = fill_p > eq
    else:
        pd_pass = True

    actual_pl  = cl['profit']
    # ถ้า FAIL → close ทันทีที่ fill → loss = spread
    sim_pl     = -SPREAD_EST if not pd_pass else actual_pl
    diff       = sim_pl - actual_pl  # + = ดีขึ้น, - = แย่ลง

    results.append({
        'tk': tk, 'fi': fi, 'cl': cl,
        'pd_result': 'PASS' if pd_pass else 'FAIL',
        'eq': round(eq, 2), 'swing_h': round(swing_h, 2), 'swing_l': round(swing_l, 2),
        'actual_pl': actual_pl, 'sim_pl': sim_pl, 'diff': diff,
    })

# ── 4. Summary ──────────────────────────────────────────────────
print()
print("=" * 75)
print("  Sim: PD Zone fix สำหรับ multi-TF orders (skip_no_data → check จริง)")
print("=" * 75)

n_pass    = sum(1 for r in results if r['pd_result'] == 'PASS')
n_fail    = sum(1 for r in results if r['pd_result'] == 'FAIL')
n_nodata  = sum(1 for r in results if r['pd_result'] == 'NO_DATA')
total_diff = sum(r['diff'] for r in results)

print(f"  Orders checked: {len(results)}")
print(f"  PD PASS (entry ถูก zone → ไม่เปลี่ยน):  {n_pass}")
print(f"  PD FAIL (entry ผิด zone → ปิดทันที):    {n_fail}")
print(f"  ไม่มีข้อมูล MT5:                          {n_nodata}")
print(f"\n  DIFF รวม: {total_diff:+.2f} USD  {'(ดีขึ้น)' if total_diff > 0 else '(แย่ลง)'}")
print()

# by sid
by_sid = defaultdict(lambda: [0, 0, 0.0])
for r in results:
    sid = r['fi']['sid'] or '?'
    by_sid[sid][0] += 1
    by_sid[sid][1] += (1 if r['pd_result'] == 'FAIL' else 0)
    by_sid[sid][2] += r['diff']
print("  By Strategy:")
for sid, (cnt, fail, diff) in sorted(by_sid.items(), key=lambda x: x[1][2]):
    print(f"    S{sid}: {cnt:3} orders | fail={fail:3} | diff={diff:+8.2f}")
print()

# Top failing orders
fails = [r for r in results if r['pd_result'] == 'FAIL']
if fails:
    print(f"  Top orders ที่ PD FAIL (entry ผิด zone) — ดีขึ้นสุด:")
    for r in sorted(fails, key=lambda x: -x['diff'])[:15]:
        fi, cl = r['fi'], r['cl']
        print(f"    {fi['fill_ts']} | {fi['side']:4} {fi['tf']:4} S{fi['sid']:2} | "
              f"fill={fi['fill_price']} EQ={r['eq']} | "
              f"actual={cl['profit']:+7.2f} sim={r['sim_pl']:+5.2f} diff={r['diff']:+7.2f}")

mt5.shutdown()

# ── 5. Save CSV ─────────────────────────────────────────────────
import csv
out = 'excel_reports/sim_pd_multitf.csv'
with open(out, 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.writer(f)
    w.writerow(['ticket','fill_ts','side','raw_tf','tf_used','sid','fill_price',
                'eq','swing_h','swing_l','pd_result',
                'actual_pl','sim_pl','diff','close_ts'])
    for r in results:
        fi, cl = r['fi'], r['cl']
        w.writerow([r['tk'], fi['fill_ts'], fi['side'], fi['raw_tf'], fi['tf'],
                    fi['sid'], fi['fill_price'],
                    r.get('eq',''), r.get('swing_h',''), r.get('swing_l',''),
                    r['pd_result'],
                    r['actual_pl'], r['sim_pl'], r['diff'], cl['close_ts']])
print(f"\n  บันทึก -> {out}")
