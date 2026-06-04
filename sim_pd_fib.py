"""
sim_pd_fib.py — เปรียบเทียบ PD Zone: EQ (เก่า, 50%) vs Fib 38.2/61.8 (ใหม่)
อ่านจาก PD_ZONE_CHECK | fill_check ตั้งแต่ 2026-05-26
"""
import re, os, sys
from datetime import datetime
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

DATE_FROM = datetime(2026, 5, 26, 0, 0, 0)

# ──────────────────────────────────────────────
def log_files():
    log_dir = 'logs'
    candidates = [
        'old_logs/bot-2026-05.log',
        'old_logs/bot-2026-06.log',
        'bot.log',
    ]
    return [os.path.join(log_dir, n) for n in candidates if os.path.exists(os.path.join(log_dir, n))]

def fld(line, key):
    m = re.search(rf'(?<![a-zA-Z_]){key}=([^|\s]+)', line)
    return m.group(1).strip() if m else None

# ──────────────────────────────────────────────
# Zone logic
def old_in_zone(price, signal, h, l):
    if h <= l: return True
    eq = (h + l) / 2.0
    if signal == "BUY":  return price < eq
    if signal == "SELL": return price > eq
    return True

def new_in_zone(price, signal, h, l):
    if h <= l: return True
    r = h - l
    fib_382 = l + r * 0.382
    fib_618 = l + r * 0.618
    if signal == "BUY":  return price < fib_382
    if signal == "SELL": return price > fib_618
    return True

# ──────────────────────────────────────────────
# 1. เก็บ fill_check entries
checks = {}   # ticket → {ts, signal, price, h, l, old_result, new_result, sid}
for path in log_files():
    for line in open(path, encoding='utf-8', errors='replace'):
        if ('PD_ZONE_CHECK' not in line and 'PDFIBOPLUS' not in line) or 'fill_check' not in line:
            continue
        m = re.match(r'^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]', line)
        if not m: continue
        ts = datetime.strptime(m.group(1), '%Y-%m-%d %H:%M:%S')
        if ts < DATE_FROM: continue
        tk  = fld(line, 'ticket')
        sig = fld(line, 'signal')
        pr  = fld(line, 'price')
        h_  = fld(line, 'h')
        l_  = fld(line, 'l')
        sid = fld(line, 'sid') or '0'
        if not all([tk, sig, pr, h_, l_]): continue
        pr, h_, l_ = float(pr), float(h_), float(l_)
        checks[tk] = {
            'ts': ts, 'signal': sig, 'price': pr, 'h': h_, 'l': l_,
            'sid': int(sid),
            'old': old_in_zone(pr, sig, h_, l_),
            'new': new_in_zone(pr, sig, h_, l_),
        }

# ──────────────────────────────────────────────
# 2. เก็บ P/L จาก POSITION_CLOSED
profits = {}   # ticket → profit
for path in log_files():
    for line in open(path, encoding='utf-8', errors='replace'):
        if 'POSITION_CLOSED' not in line: continue
        tk  = fld(line, 'ticket')
        pnl = fld(line, 'profit')
        if tk and pnl:
            try: profits[tk] = float(pnl)
            except: pass

# ──────────────────────────────────────────────
# 3. วิเคราะห์
rows_same   = []   # old == new (ไม่ต่าง)
rows_diff   = []   # old != new

for tk, c in checks.items():
    pnl = profits.get(tk)
    row = {**c, 'ticket': tk, 'pnl': pnl}
    if c['old'] == c['new']:
        rows_same.append(row)
    else:
        rows_diff.append(row)

# ──────────────────────────────────────────────
# 4. แสดงผล
print(f"\n{'='*65}")
print(f"  sim_pd_fib — EQ vs Fib 38.2/61.8  (ตั้งแต่ {DATE_FROM.date()})")
print(f"{'='*65}")
print(f"  Total fill_check entries : {len(checks)}")
print(f"  ผลเหมือนกัน (old==new)  : {len(rows_same)}")
print(f"  ผลต่างกัน   (old!=new)  : {len(rows_diff)}")

# สรุป rows_diff
old_pass_new_fail = [r for r in rows_diff if r['old'] and not r['new']]   # เก่าผ่าน ใหม่ไม่ผ่าน
old_fail_new_pass = [r for r in rows_diff if not r['old'] and r['new']]   # เก่าไม่ผ่าน ใหม่ผ่าน

def pnl_sum(rows):
    return sum(r['pnl'] for r in rows if r['pnl'] is not None)

def pnl_str(v):
    return f"{v:+.2f}" if v else "N/A"

print(f"\n{'─'*65}")
print(f"  [A] เก่า PASS → ใหม่ FAIL  (ใหม่จะปิด/ยกเลิก order)")
print(f"      จำนวน: {len(old_pass_new_fail)}")

if old_pass_new_fail:
    with_pnl  = [r for r in old_pass_new_fail if r['pnl'] is not None]
    no_pnl    = [r for r in old_pass_new_fail if r['pnl'] is None]
    pnl_total = pnl_sum(with_pnl)
    wins   = [r for r in with_pnl if r['pnl'] > 0]
    losses = [r for r in with_pnl if r['pnl'] < 0]
    print(f"      มี P/L: {len(with_pnl)} | ไม่มี P/L: {len(no_pnl)}")
    print(f"      กำไร: {len(wins)} รายการ | ขาดทุน: {len(losses)} รายการ")
    print(f"      รวม P/L (ที่เก่าเปิด): {pnl_str(pnl_total)} USD")
    print(f"      ถ้าใหม่ block → หลีกเลี่ยงได้: {pnl_str(-pnl_total)} USD")
    print()
    for r in sorted(old_pass_new_fail, key=lambda x: x['ts']):
        fib382 = round(r['l'] + (r['h']-r['l'])*0.382, 2)
        fib618 = round(r['l'] + (r['h']-r['l'])*0.618, 2)
        eq     = round((r['h']+r['l'])/2, 2)
        pnl_s  = f"{r['pnl']:+.2f}" if r['pnl'] is not None else "open"
        print(f"    #{r['ticket']}  {r['ts'].strftime('%m-%d %H:%M')}  "
              f"{r['signal']:4s}  entry={r['price']:.2f}  "
              f"38.2%={fib382}  EQ={eq}  61.8%={fib618}  "
              f"P/L={pnl_s}")

print(f"\n{'─'*65}")
print(f"  [B] เก่า FAIL → ใหม่ PASS  (เก่าปิด/ยกเลิก แต่ใหม่เปิดไว้)")
print(f"      จำนวน: {len(old_fail_new_pass)}")

if old_fail_new_pass:
    with_pnl  = [r for r in old_fail_new_pass if r['pnl'] is not None]
    no_pnl    = [r for r in old_fail_new_pass if r['pnl'] is None]
    pnl_total = pnl_sum(with_pnl)
    wins   = [r for r in with_pnl if r['pnl'] > 0]
    losses = [r for r in with_pnl if r['pnl'] < 0]
    print(f"      มี P/L: {len(with_pnl)} | ไม่มี P/L: {len(no_pnl)}")
    print(f"      กำไร: {len(wins)} รายการ | ขาดทุน: {len(losses)} รายการ")
    print(f"      รวม P/L (ถ้าใหม่เปิดไว้): {pnl_str(pnl_total)} USD")
    print()
    for r in sorted(old_fail_new_pass, key=lambda x: x['ts']):
        fib382 = round(r['l'] + (r['h']-r['l'])*0.382, 2)
        fib618 = round(r['l'] + (r['h']-r['l'])*0.618, 2)
        eq     = round((r['h']+r['l'])/2, 2)
        pnl_s  = f"{r['pnl']:+.2f}" if r['pnl'] is not None else "open"
        print(f"    #{r['ticket']}  {r['ts'].strftime('%m-%d %H:%M')}  "
              f"{r['signal']:4s}  entry={r['price']:.2f}  "
              f"38.2%={fib382}  EQ={eq}  61.8%={fib618}  "
              f"P/L={pnl_s}")

# ──────────────────────────────────────────────
# 5. สรุปรวม impact
print(f"\n{'='*65}")
print(f"  สรุป Impact เมื่อเปลี่ยนจาก EQ → Fib")
print(f"{'='*65}")

# [A] ใหม่จะ block orders ที่เก่าเปิด → ผลคือ ไม่มี P/L เหล่านั้น
a_pnl = pnl_sum([r for r in old_pass_new_fail if r['pnl'] is not None])
# [B] ใหม่จะเปิด orders ที่เก่า block → ผลคือ มี P/L เพิ่ม
b_pnl = pnl_sum([r for r in old_fail_new_pass if r['pnl'] is not None])

net = b_pnl - a_pnl   # P/L ของ new ที่ต่างจาก old
print(f"  [A] block orders ที่เก่าผ่าน (หลีกเลี่ยง P/L รวม): {pnl_str(-a_pnl)} USD")
print(f"  [B] เปิด orders ที่เก่า block (P/L เพิ่ม):           {pnl_str(b_pnl)} USD")
print(f"  Net impact (new vs old):                              {pnl_str(net)} USD")
print()

if net > 0:
    print("  ✅ Fib logic ดีกว่า EQ ในช่วงนี้")
elif net < 0:
    print("  ❌ EQ logic ดีกว่า Fib ในช่วงนี้")
else:
    print("  ⚖️ ผลเท่ากัน")
print(f"{'='*65}\n")
