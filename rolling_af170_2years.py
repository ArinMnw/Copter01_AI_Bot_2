import csv
import subprocess
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent

import sys

def main():
    print("Running export_af_ladder_sim_orders.py for AF170 over 730 days...")
    cmd = [
        sys.executable,
        str(ROOT / "strategy" / "af" / "export_af_ladder_sim_orders.py"),
        "--targets", "170",
        "--days", "730"
    ]
    
    # Run in background via subprocess
    result = subprocess.run(cmd, capture_output=True, text=True)
    print(result.stdout)
    if result.returncode != 0:
        print("Error running export script:")
        print(result.stderr)
        return

    # Now parse the daily CSV to get portfolio metrics
    daily_csv = ROOT / "strategy" / "af" / "excel" / "af_ladder_sim_daily.csv"
    if not daily_csv.exists():
        print(f"Error: {daily_csv} not found.")
        return
        
    portfolio_daily = defaultdict(float)
    with daily_csv.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["target_af"] == "AF170" and int(row["window_days"]) == 730:
                date = row["date"]
                portfolio_daily[date] += float(row["pnl_weighted_full"])
                
    dates = sorted(portfolio_daily.keys())
    if not dates:
        print("No daily data found for AF170 over 730 days.")
        return
        
    vals = [portfolio_daily[d] for d in dates]
    
    avg_day = sum(vals) / len(vals)
    min_day = min(vals)
    worst_day = min(vals)
    
    # Calculate streak
    streak = 0
    max_streak = 0
    for v in vals:
        if v <= 0:
            streak += 1
            max_streak = max(max_streak, streak)
        else:
            streak = 0
            
    print("\n" + "="*50)
    print("AF170 2-YEAR (730 DAYS) ROLLING WALK-FORWARD RESULTS")
    print("="*50)
    print(f"Period: {dates[0]} to {dates[-1]} ({len(dates)} days)")
    print(f"Average PnL/day: ${avg_day:.2f}")
    print(f"Minimum PnL/day: ${min_day:.2f}")
    print(f"Worst Day:       ${worst_day:.2f}")
    print(f"Max Losing Streak: {max_streak} days")
    print("="*50)
    
    # Output to af170_2years_daily.csv
    out_csv = ROOT / "af170_2years_daily.csv"
    with out_csv.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["date", "portfolio_pnl"])
        w.writeheader()
        for d in dates:
            w.writerow({"date": d, "portfolio_pnl": round(portfolio_daily[d], 2)})
            
    print(f"Saved daily breakdown to {out_csv.name}")

if __name__ == "__main__":
    main()
