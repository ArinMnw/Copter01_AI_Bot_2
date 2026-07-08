import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def main():
    # Read dates from the 2-years CSV (which has ~793 trading days)
    daily_csv = ROOT / "af170_2years_daily.csv"
    dates = []
    with daily_csv.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            dates.append(row["date"])
            
    # We want 550 days
    windows = [550]
    
    out_csv = ROOT / "lts0_empty_daily.csv"
    with out_csv.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["days", "date", "total"])
        w.writeheader()
        
        for days in windows:
            # slice the last `days` dates
            slice_dates = dates[-days:]
            for d in slice_dates:
                w.writerow({"days": days, "date": d, "total": 0.0})
                
    print(f"Created {out_csv.name} with {windows} days (last date: {dates[-1]}).")

if __name__ == "__main__":
    main()
