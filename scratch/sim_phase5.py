"""
Phase 5: Max Single-Trade Loss Cap Simulation
============================================
แนวคิด: ถ้าไม้ไหนขาดทุน (SL) เกิน threshold ที่กำหนด
→ จำลองว่าระบบตัดออกที่ threshold นั้นแทน (เสียน้อยกว่า)

ทดสอบ threshold หลายค่า: -200, -500, -1000, -2000, -5000 USD (AUS)
                          -2000, -5000, -10000, -20000 USD (AHR)
"""
import csv
import sys

sys.stdout.reconfigure(encoding="utf-8")


def load_trades(fname):
    with open(fname, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    cols = list(rows[0].keys()) if rows else []
    pnl_col = next((c for c in cols if "P&L" in c or "pnl" in c.lower()), None)
    out_col = next((c for c in cols if "Outcome" in c), None)
    return rows, pnl_col, out_col


def simulate_phase5(rows, pnl_col, out_col, threshold):
    """
    threshold = negative USD, e.g. -1000
    ถ้า SL แล้ว pnl < threshold → เปลี่ยนเป็น threshold (ตัดก่อน)
    """
    new_pnls = []
    capped = 0
    for r in rows:
        pnl = float(r[pnl_col])
        outcome = r.get(out_col, "")
        if outcome == "SL" and pnl < threshold:
            new_pnls.append(threshold)
            capped += 1
        else:
            new_pnls.append(pnl)
    return new_pnls, capped


def stats(pnls):
    total = sum(pnls)
    avg   = total / len(pnls) if pnls else 0
    worst = min(pnls) if pnls else 0
    wins  = sum(1 for p in pnls if p > 0)
    wr    = wins / len(pnls) * 100 if pnls else 0
    return total, avg, worst, wr


portfolios = [
    (
        "LTS_AUS",
        "strategy/demo_portfolio/excel/lts/LTS_AVENGERS_ULTRA_SAFE_trades.csv",
        [-200, -500, -1000, -2000, -5000],
    ),
    (
        "LTS_AHR",
        "strategy/demo_portfolio/excel/lts/LTS_AVENGERS_HIGH_RISK_trades.csv",
        [-2000, -5000, -10000, -20000, -50000],
    ),
]

for pf, fname, thresholds in portfolios:
    try:
        rows, pnl_col, out_col = load_trades(fname)
    except FileNotFoundError:
        print(f"[{pf}] file not found: {fname}")
        continue

    orig_pnls = [float(r[pnl_col]) for r in rows]
    losses = [p for p in orig_pnls if p < 0]
    wins_pnl = [p for p in orig_pnls if p > 0]
    sl_rows = [r for r in rows if r.get(out_col, "") == "SL"]

    print(f"{'='*65}")
    print(f"  {pf}  ({len(rows)} trades)")
    print(f"{'='*65}")
    print(f"  SL trades      : {len(sl_rows)}")
    if losses:
        print(f"  Loss distribution:")
        print(f"    Worst SL     : {min(losses):+.2f} USD")
        print(f"    Avg SL       : {sum(losses)/len(losses):+.2f} USD")
        loss_buckets = {}
        for p in [float(r[pnl_col]) for r in sl_rows]:
            if p >= -500:   bucket = "0 to -500"
            elif p >= -1000: bucket = "-500 to -1000"
            elif p >= -2000: bucket = "-1000 to -2000"
            elif p >= -5000: bucket = "-2000 to -5000"
            elif p >= -10000: bucket = "-5000 to -10000"
            elif p >= -20000: bucket = "-10000 to -20000"
            else:            bucket = "< -20000"
            loss_buckets[bucket] = loss_buckets.get(bucket, 0) + 1
        for b in sorted(loss_buckets):
            print(f"    {b:<25}: {loss_buckets[b]} trades")
    print()

    # Baseline (no Phase 5)
    tot0, avg0, worst0, wr0 = stats(orig_pnls)
    print(f"  [BASELINE — Phase 5 OFF]")
    print(f"    Total PnL  : {tot0:+,.2f} USD")
    print(f"    Avg/trade  : {avg0:+.2f} USD")
    print(f"    Worst SL   : {worst0:+.2f} USD")
    print(f"    Win Rate   : {wr0:.1f}%")
    print()

    print(f"  [PHASE 5 SIMULATION — various thresholds]")
    print(f"  {'Threshold':>12}  {'Total PnL':>14}  {'vs Baseline':>12}  {'Worst SL':>12}  {'Capped':>7}")
    print(f"  {'-'*65}")
    for th in thresholds:
        new_pnls, capped = simulate_phase5(rows, pnl_col, out_col, th)
        tot, avg, worst, wr = stats(new_pnls)
        diff = tot - tot0
        diff_pct = diff / abs(tot0) * 100 if tot0 else 0
        print(f"  {th:>12,.0f}  {tot:>14,.2f}  {diff:>+12,.2f} ({diff_pct:+.1f}%)  {worst:>12,.2f}  {capped:>7} trades")
    print()
    print()
