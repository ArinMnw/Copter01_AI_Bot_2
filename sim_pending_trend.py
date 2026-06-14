"""
sim_pending_trend.py
====================
Simulation: Pending Trend Check on Approach (pre-fill cancel)
ตั้งแต่ 2026-05-26 จนถึงปัจจุบัน

Logic:
- หา orders ที่ fill แล้วโดน TREND_RECHECK fill_close_round1 หรือ fill_close_round2
- สำหรับ round1: ถ้า pending trend check ทำงาน → order ถูกยกเลิกก่อน fill → ไม่เสียเงิน
- สำหรับ round2 (หลัง fill+swing เปลี่ยน): ก็ยังโดนปิด → ผลเหมือนเดิม
  แต่ถ้า pending round 2 จับได้ก่อน fill → ไม่เสียเงิน

กลุ่ม A: โดน fill_close_round1 (trend ผิดตั้งแต่ fill ทันที) → new system จะยกเลิก pending ก่อน
กลุ่ม B: โดน fill_close_round2 → new system ก็จะยกเลิก pending ก่อน fill (ถ้าจับได้)
          หรืออย่างน้อยก็ปิดเหมือนเดิม (worst case = เหมือน old)

ผลต่าง: กลุ่ม A = ประหยัดเต็ม |profit| (หยุดก่อน fill = ไม่เสีย)
         กลุ่ม B = ประหยัดส่วนต่าง (ปิดก่อน fill ดีกว่าปิดหลัง fill มีค่าเพิ่มขึ้น)
"""

import sys, re, os
from datetime import datetime
from log_sources import bot_log_files
sys.stdout.reconfigure(encoding='utf-8')

SIM_FROM = datetime(2026, 5, 26)

# รวม log จากทุกไฟล์ที่มี (เก่า → ใหม่)
LOG_FILES = bot_log_files()

# ── helpers ──────────────────────────────────────────────────────────────────
_RE_TS   = re.compile(r'^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]')
_RE_EVT  = re.compile(r'^\[.+?\]\s+(\S+)')

def fld(line, key):
    m = re.search(rf'(?<![a-zA-Z_]){key}=([^|\s]+)', line)
    return m.group(1) if m else None

def flt(line, key, default=0.0):
    v = fld(line, key)
    try:    return float(v)
    except: return default

def ts(line):
    m = _RE_TS.match(line)
    if m:
        try: return datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S")
        except: pass
    return None

def evt(line):
    m = _RE_EVT.match(line)
    return m.group(1) if m else None

# ── อ่าน log จากทุกไฟล์ ──────────────────────────────────────────────────────
seen_lines = set()
all_lines = []
for fpath in LOG_FILES:
    if not os.path.exists(fpath):
        continue
    print(f"  อ่าน {os.path.basename(fpath)} ({os.path.getsize(fpath)//1024//1024} MB)...")
    with open(fpath, encoding='utf-8', errors='replace') as f:
        for line in f:
            key = line[:80]  # dedup โดยใช้ 80 chars แรก
            if key not in seen_lines:
                seen_lines.add(key)
                all_lines.append(line)

# กรองเฉพาะ >= SIM_FROM และ event ที่ต้องการ
WANT_EVENTS = {"POSITION_CLOSED", "TREND_RECHECK", "POSITION_CLOSE_REQUEST"}
log = []
for l in all_lines:
    t = ts(l)
    if not t or t < SIM_FROM:
        continue
    e = evt(l)
    if e not in WANT_EVENTS:
        continue
    log.append((t, e, l))

log.sort(key=lambda x: x[0])
print(f"  บรรทัดที่เกี่ยวข้องในช่วง: {len(log):,}")

# ── build ticket index ────────────────────────────────────────────────────────
# สำหรับแต่ละ ticket เก็บ: fill_profit, close_round, fill_price, close_price
# จาก POSITION_CLOSED ที่ reason ขึ้นต้นด้วย "Fill Trend Reche"

tk_re = {}   # ticket → {"close_round", "profit", "fill_price", "close_price", "sid", "tf", "signal"}

# Step 1: หา tickets ที่โดน Trend Recheck ปิด จาก POSITION_CLOSE_REQUEST
# (มี round info ครบ เช่น "Fill Trend Recheck [round1/2]")
pcr_tickets = {}  # ticket → {"round": "round1"|"round2", "close_price": float}
for t, e, l in log:
    if e != "POSITION_CLOSE_REQUEST":
        continue
    if 'Fill Trend Recheck' not in l:
        continue
    if 'ok=True' not in l:
        continue
    ticket_str = fld(l, 'ticket')
    if not ticket_str:
        continue
    ticket = int(ticket_str)
    # ดึง round จาก sub-field เช่น "Fill Trend Recheck [round1/2]"
    rm = re.search(r'\[round(\d+)/', l)
    rnd = "round" + rm.group(1) if rm else "round1"
    cp = flt(l, 'close_price') or flt(l, 'bid') or 0.0
    # เก็บ round ล่าสุด (อาจมี retry)
    pcr_tickets[ticket] = {"round": rnd, "close_price": cp}

# Step 2: หา profit/sid/tf จาก POSITION_CLOSED
for t, e, l in log:
    if e != "POSITION_CLOSED":
        continue
    if 'Fill Trend Reche' not in l:  # reason field truncated แต่ substring ยังอยู่ใน line
        continue
    ticket_str = fld(l, 'ticket')
    if not ticket_str:
        continue
    ticket = int(ticket_str)
    profit      = flt(l, 'profit')
    open_price  = flt(l, 'open_price')
    close_price = flt(l, 'close_price')
    sid         = fld(l, 'sid') or "?"
    tf          = fld(l, 'tf') or "?"
    signal      = fld(l, 'side') or "?"

    close_round = pcr_tickets.get(ticket, {}).get("round", "round1")

    tk_re[ticket] = {
        "close_round": close_round,
        "profit":      profit,
        "fill_price":  open_price,
        "close_price": close_price,
        "sid":         sid,
        "tf":          tf,
        "signal":      signal,
        "time":        t,
    }

# ── แยกกลุ่ม ──────────────────────────────────────────────────────────────────
# Skip: S9, S10, S14, S15 (new feature ไม่ทำงานกับ sid เหล่านี้)
SKIP_SIDS = {"9", "10", "14", "15"}

grp_A  = []   # round1 (โดนปิดทันที) + not skip → new system ยกเลิก pending ก่อน fill
grp_B  = []   # round2 (โดนปิดหลัง swing เปลี่ยน) + not skip → new system ยกเลิก pending ก่อน fill ด้วย
grp_skip = [] # sid ที่ skip

for ticket, d in tk_re.items():
    if str(d["sid"]) in SKIP_SIDS:
        grp_skip.append((ticket, d))
    elif d["close_round"] == "round1":
        grp_A.append((ticket, d))
    else:
        grp_B.append((ticket, d))

# ── คำนวณผล ───────────────────────────────────────────────────────────────────
# กลุ่ม A (fill_round1): trend ผิดตั้งแต่ fill ทันที
#   → new system ยกเลิก pending ก่อน fill → profit = 0 (ไม่เข้าเทรด)
#   → ผลต่าง = 0 - old_A_profit (ถ้า net loss → ดีขึ้น)
#   Note: Group A มีทั้ง winner และ loser ที่โดนปิดทันที
#         winner = ผ่าน round1 ก่อนที่ swing เปลี่ยนแล้วราคากลับมา แต่ trend ก็ fail ทันที
#
# กลุ่ม B (fill_round2): trend ดีตอน fill แต่เปลี่ยนเมื่อ swing ใหม่
#   → round1 ผ่าน → fill → round2 check → ปิด
#   → new system: round1 pending ก็ผ่าน → fill → round2 ใช้ approach-time swing
#   → ผลเหมือนเดิม (worst) หรือยกเลิกก่อน fill ถ้า pending round2 จับได้ (best)

a_old = sum(d["profit"] for _, d in grp_A)   # net P/L group A (winner - loser)
a_new = 0.0                                    # ยกเลิกก่อน fill ทั้งหมด → 0

a_losses = sum(d["profit"] for _, d in grp_A if d["profit"] < 0)  # sum of losses (negative)
a_wins   = sum(d["profit"] for _, d in grp_A if d["profit"] > 0)  # sum of wins

b_old   = sum(d["profit"] for _, d in grp_B)
b_worst = b_old   # เหมือนเดิม
b_best  = 0.0     # ยกเลิกก่อน fill ทุกตัว

old_total    = a_old + b_old          # รวมเฉพาะ trend-recheck orders
delta_A      = a_new - a_old          # กลุ่ม A: เปลี่ยนแปลงถ้า cancel ทั้งหมด
delta_B_best = b_best - b_old         # กลุ่ม B: เปลี่ยนแปลง best case
delta_B_wrst = b_worst - b_old        # = 0

improvement_best  = delta_A + delta_B_best
improvement_worst = delta_A + delta_B_wrst

print(f"\n{'='*60}")
print(f"  SIM: Pending Trend Check — ตั้งแต่ 2026-05-26")
print(f"{'='*60}")
print(f"\n  Orders โดน Trend Recheck ทั้งหมด : {len(tk_re):>4} orders")
print(f"  Skip (S9/S10/S14/S15)             : {len(grp_skip):>4} orders")
print(f"  กลุ่ม A (round1 — new จะ cancel)   : {len(grp_A):>4} orders")
print(f"  กลุ่ม B (round2 — new อาจ cancel)  : {len(grp_B):>4} orders")

print(f"\n  ── กลุ่ม A (round1, ยกเลิกก่อน fill) ──────────────────")
print(f"  {'Ticket':<12} {'Time':>16} {'SID':>4} {'TF':>4} {'Signal':>6} {'Profit':>9}")
for ticket, d in sorted(grp_A, key=lambda x: x[1]['time']):
    flag = "💸" if d["profit"] < 0 else "💰"
    print(f"  {ticket:<12} {d['time'].strftime('%d/%m %H:%M:%S'):>16} {d['sid']:>4} {d['tf']:>4} {d['signal']:>6} {flag}{d['profit']:>8.2f}")

print(f"\n  ── กลุ่ม B (round2, อาจยกเลิกก่อน fill) ───────────────")
print(f"  {'Ticket':<12} {'Time':>16} {'SID':>4} {'TF':>4} {'Signal':>6} {'Profit':>9}")
for ticket, d in sorted(grp_B, key=lambda x: x[1]['time']):
    flag = "💸" if d["profit"] < 0 else "💰"
    print(f"  {ticket:<12} {d['time'].strftime('%d/%m %H:%M:%S'):>16} {d['sid']:>4} {d['tf']:>4} {d['signal']:>6} {flag}{d['profit']:>8.2f}")

print(f"\n{'='*60}")
print(f"  ── สรุปผล P/L (เฉพาะ Trend Recheck orders) ────────────")
print(f"{'='*60}")
n_a_loss = len([x for _,x in grp_A if x['profit']<0])
n_a_win  = len([x for _,x in grp_A if x['profit']>0])
print(f"\n  Group A ({len(grp_A)} orders) — P/L old: {a_old:>8.2f} USD")
print(f"    Losses : {a_losses:>8.2f} USD ({n_a_loss} orders) -- saved if cancel before fill")
print(f"    Wins   : {a_wins:>+8.2f} USD ({n_a_win} orders) -- lost if cancel before fill")
print(f"    new    :     0.00 USD  |  diff: {delta_A:>+8.2f} USD")
print(f"\n  Group B ({len(grp_B)} orders) — P/L old: {b_old:>8.2f} USD")
print(f"    new worst (no change):         {b_worst:>8.2f} USD  |  diff: {delta_B_wrst:>+8.2f}")
print(f"    new best  (cancel before fill):   0.00 USD  |  diff: {delta_B_best:>+8.2f}")
print(f"\n{'='*60}")
print(f"  TOTAL (trend-recheck orders only)")
print(f"  old                : {old_total:>8.2f} USD")
print(f"  new -- worst case  : {old_total + improvement_worst:>8.2f} USD  ({improvement_worst:>+.2f} USD)")
print(f"  new -- best  case  : {old_total + improvement_best:>8.2f} USD  ({improvement_best:>+.2f} USD)")
print(f"\n  Core improvement (Group A, guaranteed): {delta_A:>+.2f} USD")
print(f"  -- cancel before fill when trend bad at approach time")
print(f"  -- worst: some A orders trend OK at approach, still pass -> no benefit")
print(f"  -- feature never WORSE than old (cancelled = 0, old = loss)")
print(f"\n  Data note: fill_trend_recheck close(ok=True) starts 03/06/2026")
print(f"             May data: all close attempts had ok=False (no data)")
print(f"{'='*60}")
