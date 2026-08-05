import sys, csv
sys.stdout.reconfigure(encoding='utf-8')

files = [
    ("LTS_AUS", "strategy/demo_portfolio/excel/lts/LTS_AVENGERS_ULTRA_SAFE_trades.csv"),
    ("LTS_AHR", "strategy/demo_portfolio/excel/lts/LTS_AVENGERS_HIGH_RISK_trades.csv"),
]

for pf, fname in files:
    with open(fname, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        print(f"=== {pf}: no trades ===")
        continue
    cols = list(rows[0].keys())
    pnl_col  = next((c for c in cols if "P&L" in c or "pnl" in c.lower()), None)
    out_col  = next((c for c in cols if "Outcome" in c or "outcome" in c), None)
    open_col = next((c for c in cols if "Time" in c and "Close" not in c), None)
    leg_col  = next((c for c in cols if "Leg" in c), None)
    type_col = next((c for c in cols if c == "Type"), None)

    wins   = [r for r in rows if r.get(out_col, "") == "TP"]
    losses = [r for r in rows if r.get(out_col, "") == "SL"]
    others = [r for r in rows if r.get(out_col, "") not in ("TP", "SL")]
    pnls   = [float(r[pnl_col]) for r in rows]

    print(f"=== {pf} ({len(rows)} trades) ===")
    print(f"  TP={len(wins)}  SL={len(losses)}  Others={len(others)}")
    print(f"  Total PnL : {sum(pnls):+.2f} USD")
    print(f"  Win Rate  : {len(wins)/len(rows)*100:.1f}%")
    print(f"  Avg/trade : {sum(pnls)/len(rows):+.2f} USD")
    print(f"  Best      : {max(pnls):+.2f} USD")
    print(f"  Worst     : {min(pnls):+.2f} USD")
    print()

    weird_tp = [r for r in wins if float(r[pnl_col]) <= 0]
    weird_sl = [r for r in losses if float(r[pnl_col]) >= 0]
    print(f"  Weird TP(pnl<=0): {len(weird_tp)} -- {'BAD!' if weird_tp else 'OK'}")
    print(f"  Weird SL(pnl>=0): {len(weird_sl)} -- {'BAD!' if weird_sl else 'OK'}")
    print()

    # Show all trades
    print(f"  {'Open Time':<22} {'Type':<5} {'Outcome':<8} {'P&L':>10}  Leg")
    print(f"  {'-'*75}")
    for r in rows:
        t  = str(r.get(open_col, ""))[:22]
        ty = str(r.get(type_col, ""))
        oc = str(r.get(out_col, ""))
        pl = float(r[pnl_col])
        lg = str(r.get(leg_col, ""))[:35]
        print(f"  {t:<22} {ty:<5} {oc:<8} {pl:>10.2f}  {lg}")
    print()
