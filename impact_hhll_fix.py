"""
Impact analysis: HHLL race-condition fix
ตรวจว่า order ไหนบ้าง (ตั้งแต่ 2026-05-24) ที่จะถูก block
ถ้า fix นี้ apply อยู่แล้ว
"""
import sys, re, os
sys.stdout.reconfigure(encoding='utf-8')
os.chdir(os.path.dirname(os.path.abspath(__file__)))

LOG_PATH = 'logs/bot.log'
SINCE_DT = '2026-05-24'

print("Loading log file...")
lines = open(LOG_PATH, encoding='utf-8-sig').readlines()
print(f"Total lines: {len(lines)}")

# ──────────────────────────────────────────────────────────────
# STEP 1: Build per-TF HHLL+Trend timeline from SCAN_SUMMARY
# Format: { line_idx: {'ts': str, 'tf_data': {tf: {'trend': str, 'last_label': str}}} }
# ──────────────────────────────────────────────────────────────
print("\nStep 1: Building HHLL+Trend timeline from SCAN_SUMMARY Scan Swing sections...")

# TF section separator pattern: ┌─ <emoji> M1 / M5 / etc.
# Pattern for a TF block within Scan Swing:
# ┌─ 🟨 M1 | │ 🧭 Trend:⚪ SIDEWAY | ... | │ 🏷️ HHLL: HH ▸ HL ... |
re_tf_block = re.compile(
    r'┌─\s*\S+\s+(\w+)\s*\|'           # group 1: TF name (M1, M5, etc.)
    r'(?=.*?🧭\s*Trend:(?:⚪|🟢|🔴)\s*(\w+[^|]*))'  # group 2: trend word
)

# For each TF block: extract HHLL last_label (first item in "HHLL: X ▸ Y ▸ ...")
re_hhll = re.compile(r'🏷️\s*HHLL:\s*([A-Z]+)')  # group 1: last_label (first element)
re_trend = re.compile(r'🧭\s*Trend:[^\s]+\s*(\w+)')  # group 1: trend word (SIDEWAY/Bull/Bear)

# Parse timestamp from log line
re_ts = re.compile(r'^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]')

# Build timeline: list of (line_idx, ts_str, {tf: {trend, last_label}})
timeline = []

for i, line in enumerate(lines):
    if 'SCAN_SUMMARY' not in line or 'Scan Swing' not in line:
        continue
    ts_m = re_ts.match(line)
    if not ts_m:
        continue
    ts = ts_m.group(1)
    if ts < SINCE_DT + ' ':
        continue  # skip before May 24

    # Find Scan Swing part
    sw_idx = line.find('Scan Swing')
    if sw_idx < 0:
        continue
    sw_part = line[sw_idx:]

    # Split by TF sections: ┌─ ... ┌─ ...
    tf_sections = re.split(r'(?=┌─)', sw_part)

    tf_data = {}
    for sec in tf_sections:
        if not sec.strip():
            continue
        # Get TF name
        tf_m = re.match(r'┌─\s*\S+\s+(\w+)', sec)
        if not tf_m:
            continue
        tf = tf_m.group(1)

        # Get trend
        trend_m = re_trend.search(sec)
        if not trend_m:
            continue
        trend_raw = trend_m.group(1).strip()
        # Normalize: Bull → BULL, Bear → BEAR, SIDEWAY → SIDEWAY
        trend = 'SIDEWAY' if 'SIDEWAY' in trend_raw else (
                'BULL' if 'ull' in trend_raw else (
                'BEAR' if 'ear' in trend_raw else trend_raw))

        # Get HHLL last_label (first element = newest)
        hhll_m = re_hhll.search(sec)
        last_label = hhll_m.group(1) if hhll_m else ''

        tf_data[tf] = {'trend': trend, 'last_label': last_label}

    if tf_data:
        timeline.append((i, ts, tf_data))

print(f"Built {len(timeline)} scan snapshots with Scan Swing data")
if timeline:
    print(f"First: {timeline[0][1]}, Last: {timeline[-1][1]}")
    # Show sample
    for _i, _ts, _d in timeline[:2]:
        print(f"  {_ts}: {_d}")

# ──────────────────────────────────────────────────────────────
# STEP 2: Collect ENTRY_FILL since May 24
# ──────────────────────────────────────────────────────────────
print("\nStep 2: Collecting ENTRY_FILL records since May 24...")

re_fill = re.compile(
    r'ENTRY_FILL.*?ticket=(\d+).*?side=(\w+).*?tf=(\S+).*?price=([\d.]+).*?pnl=([-\d.]+)',
    re.DOTALL
)

fills = {}  # ticket → {ts, side, tf, price, pnl_close, close_ts}
for i, line in enumerate(lines):
    if 'ENTRY_FILL' not in line:
        continue
    ts_m = re_ts.match(line)
    if not ts_m:
        continue
    ts = ts_m.group(1)
    if ts < SINCE_DT + ' ':
        continue

    # Extract fields
    ticket_m = re.search(r'ticket=(\d+)', line)
    side_m = re.search(r'side=(\w+)', line)
    tf_m = re.search(r'\btf=(\S+)', line)
    price_m = re.search(r'price=([\d.]+)', line)
    if not (ticket_m and side_m and tf_m and price_m):
        continue

    ticket = ticket_m.group(1)
    tf_raw = tf_m.group(1)
    # Normalize TF (handle [H1_M1] style)
    # For TREND_RECHECK, the tf field in fill_round1 matches the order's tf
    # Just use as-is for matching
    tf = tf_raw.rstrip('|').strip()

    fills[ticket] = {
        'ts': ts,
        'line_idx': i,
        'side': side_m.group(1),
        'tf': tf,
        'entry_price': float(price_m.group(1)),
        'pnl': None,
        'close_ts': None,
    }

print(f"Found {len(fills)} fills since May 24")

# ──────────────────────────────────────────────────────────────
# STEP 3: Find TREND_RECHECK fill_round1 for each fill
# ──────────────────────────────────────────────────────────────
print("\nStep 3: Finding TREND_RECHECK fill_round1 entries...")

re_tr = re.compile(
    r'TREND_RECHECK.*?fill_round1.*?ticket=(\d+).*?tf=(\S+).*?signal=(\w+).*?allowed=(\w+).*?why=(\S+)'
)

fill_round1 = {}  # ticket → {tf, signal, allowed, why, ts, line_idx}
for i, line in enumerate(lines):
    if 'TREND_RECHECK' not in line or 'fill_round1' not in line:
        continue
    ts_m = re_ts.match(line)
    if not ts_m:
        continue
    ts = ts_m.group(1)
    if ts < SINCE_DT + ' ':
        continue

    ticket_m = re.search(r'ticket=(\d+)', line)
    tf_m = re.search(r'\btf=(\S+)', line)
    signal_m = re.search(r'signal=(\w+)', line)
    allowed_m = re.search(r'allowed=(\w+)', line)
    why_m = re.search(r'why=(\S+)', line)

    if not (ticket_m and signal_m and allowed_m and why_m):
        continue

    ticket = ticket_m.group(1)
    tf = tf_m.group(1).rstrip('|').strip() if tf_m else ''
    fill_round1[ticket] = {
        'ts': ts,
        'line_idx': i,
        'tf': tf,
        'signal': signal_m.group(1),
        'allowed': allowed_m.group(1) == 'True',
        'why': why_m.group(1).rstrip('|').strip(),
    }

print(f"Found {len(fill_round1)} fill_round1 TREND_RECHECK entries")

# ──────────────────────────────────────────────────────────────
# STEP 4: Collect POSITION_CLOSED P&L for each ticket
# ──────────────────────────────────────────────────────────────
print("\nStep 4: Collecting POSITION_CLOSED P&L...")

closed_pnl = {}  # ticket → {pnl, close_ts, close_type}
for i, line in enumerate(lines):
    if 'POSITION_CLOSED' not in line:
        continue
    ts_m = re_ts.match(line)
    if not ts_m:
        continue
    ts = ts_m.group(1)
    if ts < SINCE_DT + ' ':
        continue

    ticket_m = re.search(r'ticket=(\d+)', line)
    pnl_m = re.search(r'profit=([-\d.]+)', line)
    if not (ticket_m and pnl_m):
        continue

    ticket = ticket_m.group(1)
    # close_type from log
    close_type = 'Bot'
    if '🎯' in line or 'TP Hit' in line:
        close_type = 'TP'
    elif '🛑' in line or 'SL Hit' in line:
        close_type = 'SL'

    closed_pnl[ticket] = {
        'pnl': float(pnl_m.group(1)),
        'close_ts': ts,
        'close_type': close_type,
    }

print(f"Found {len(closed_pnl)} closed positions since May 24")

# ──────────────────────────────────────────────────────────────
# STEP 5: Find closest prior scan snapshot for each fill
# ──────────────────────────────────────────────────────────────
print("\nStep 5: Matching fills to scan snapshots...")

def get_scan_state(fill_line_idx, tf_name):
    """Find the closest prior scan snapshot that has data for tf_name."""
    # Binary search: find largest idx in timeline where line_idx <= fill_line_idx
    lo, hi = 0, len(timeline) - 1
    best = None
    while lo <= hi:
        mid = (lo + hi) // 2
        if timeline[mid][0] <= fill_line_idx:
            best = mid
            lo = mid + 1
        else:
            hi = mid - 1

    if best is None:
        return None

    # Search backwards for TF data (sometimes scan for a specific TF comes slightly before fill)
    for j in range(best, max(best - 20, -1), -1):
        if tf_name in timeline[j][2]:
            return timeline[j][2][tf_name]
    return None

# ──────────────────────────────────────────────────────────────
# STEP 6: Identify impacted orders
# ──────────────────────────────────────────────────────────────
print("\nStep 6: Identifying impacted orders (would-be-blocked by HHLL fix)...")

impacted = []    # orders that would have been blocked
all_sideway = [] # all SIDEWAY orders with why=-

for ticket, tr in fill_round1.items():
    if not tr['allowed']:
        continue  # already blocked - not impacted by this bug
    if tr['why'] != '-':
        continue  # has a specific reason - not the race condition path

    fill = fills.get(ticket)
    if not fill:
        continue  # no ENTRY_FILL found (might be outside date range)

    # Get scan state at fill time for the order's TF
    tf = tr['tf']
    # Handle compound TF like [H1_M1] - use the actual strategy tf from fill
    if tf.startswith('['):
        # Use the tf from ENTRY_FILL instead
        tf = fill['tf']
    # Remove brackets if still present
    tf = tf.strip('[]')

    state = get_scan_state(fill['line_idx'], tf)
    if not state:
        continue

    trend = state.get('trend', '')
    last_label = state.get('last_label', '')
    signal = tr['signal']

    if trend != 'SIDEWAY':
        continue

    all_sideway.append({
        'ticket': ticket,
        'ts': fill['ts'],
        'tf': tf,
        'side': fill['side'],
        'signal': signal,
        'trend': trend,
        'last_label': last_label,
        'would_block': False,
    })

    # Would HHLL fix block this?
    would_block = False
    if last_label in ('HH', 'HL') and signal == 'SELL':
        would_block = True
    elif last_label in ('LH', 'LL') and signal == 'BUY':
        would_block = True

    if would_block:
        cl = closed_pnl.get(ticket, {})
        pnl = cl.get('pnl', None)
        all_sideway[-1]['would_block'] = True
        impacted.append({
            'ticket': ticket,
            'ts': fill['ts'],
            'tf': tf,
            'side': fill['side'],
            'signal': signal,
            'last_label': last_label,
            'pnl': pnl,
            'close_type': cl.get('close_type', '?'),
            'close_ts': cl.get('close_ts', ''),
        })

print(f"\nSIDEWAY orders (allowed, why=-): {len(all_sideway)}")
print(f"Would-be-blocked by HHLL fix:    {len(impacted)}")

# ──────────────────────────────────────────────────────────────
# STEP 7: Summary
# ──────────────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("IMPACT SUMMARY")
print("=" * 70)

pnl_known = [o for o in impacted if o['pnl'] is not None]
pnl_unknown = [o for o in impacted if o['pnl'] is None]
total_pnl = sum(o['pnl'] for o in pnl_known)
tp_count = sum(1 for o in pnl_known if o['close_type'] == 'TP')
sl_count = sum(1 for o in pnl_known if o['close_type'] == 'SL')
bot_count = sum(1 for o in pnl_known if o['close_type'] == 'Bot')

print(f"\nTotal impacted orders: {len(impacted)}")
print(f"  With known P&L: {len(pnl_known)}  (TP={tp_count}, SL={sl_count}, Bot={bot_count})")
print(f"  Without close data: {len(pnl_unknown)}")
print(f"\nTotal P&L of impacted orders: {total_pnl:.2f} USD")
print(f"  (If positive → the fix would have SAVED this loss)")
print(f"  (If negative → the fix would have MISSED these gains)")

# Detail by signal
sells = [o for o in impacted if o['signal'] == 'SELL']
buys = [o for o in impacted if o['signal'] == 'BUY']
print(f"\nBy direction: SELL={len(sells)}, BUY={len(buys)}")

# Breakdown by last_label
from collections import Counter
lbl_counter = Counter(o['last_label'] for o in impacted)
print(f"By HHLL last_label: {dict(lbl_counter)}")

# Breakdown by TF
tf_counter = Counter(o['tf'] for o in impacted)
print(f"By TF: {dict(tf_counter)}")

# Detail table
print("\n" + "-" * 80)
print(f"{'Ticket':<12} {'Timestamp':<20} {'TF':<8} {'Signal':<6} {'HHLL':<4} {'P&L':>8} {'Close':<6}")
print("-" * 80)
for o in sorted(impacted, key=lambda x: x['ts']):
    pnl_s = f"{o['pnl']:.2f}" if o['pnl'] is not None else "?"
    print(f"{o['ticket']:<12} {o['ts']:<20} {o['tf']:<8} {o['signal']:<6} {o['last_label']:<4} {pnl_s:>8} {o['close_type']:<6}")

# SIDEWAY stats (including non-blocked)
print("\n" + "=" * 70)
print("ALL SIDEWAY why=- ORDERS (context)")
print("=" * 70)
no_hhll = [o for o in all_sideway if not o['last_label']]
with_hhll_ok = [o for o in all_sideway if o['last_label'] and not o['would_block']]
with_hhll_block = [o for o in all_sideway if o['would_block']]
print(f"Total SIDEWAY why=- fills: {len(all_sideway)}")
print(f"  No HHLL data in scan:    {len(no_hhll)}  (scan snapshot missing last_label)")
print(f"  HHLL allows signal:      {len(with_hhll_ok)}  (correctly allowed - fix wouldn't change)")
print(f"  HHLL would block:        {len(with_hhll_block)}  (← affected by this bug)")

print("\nDone.")
