import csv
rows = [r for r in csv.DictReader(open("s30_backtest_summary.csv", encoding="utf-8"))
        if r["label"].startswith("widesl_risk")]
print(f"{'risk%':>6} {'lot(min-max)':>14} {'DD%':>7} {'$/day':>8} {'$/month':>9} {'final_eq':>9} {'PF':>5}")
for r in rows:
    lot = f"{r['lot_min']}-{r['lot_max']}"
    print(f"{r['risk_pct']:>6} {lot:>14} {r['max_dd_pct']:>7} {r['avg_per_day_span']:>8} "
          f"{float(r['avg_per_day_span'])*30:>9.1f} {r['final_equity']:>9} {r['profit_factor']:>5}")
