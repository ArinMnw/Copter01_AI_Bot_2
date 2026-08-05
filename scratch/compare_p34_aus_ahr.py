import pandas as pd
import numpy as np

def simulate_phase34(portfolio_name, csv_path):
    print("="*60)
    print(f"SIMULATING PHASE 3 & 4 ON {portfolio_name}")
    print("="*60)

    try:
        df = pd.read_csv(csv_path)
    except FileNotFoundError:
        print(f"❌ Could not find {csv_path}")
        return

    original_avg = df['Net Profit'].mean()
    original_worst = df['Net Profit'].min()
    original_total = df['Net Profit'].sum()

    print(f"[ORIGINAL {portfolio_name} (Phase 3&4 OFF)]")
    print(f"   Avg Day:   {original_avg:8.2f} USD")
    print(f"   Worst Day: {original_worst:8.2f} USD")
    print(f"   Total PnL: {original_total:8.2f} USD")
    print("-" * 60)
    
    new_totals = []
    for val in df['Net Profit']:
        if val > 0:
            # Winning day: Dynamic lot sizing boosted volume by ~1.2x average
            new_val = val * 1.20
        else:
            # Losing day: Dynamic lot sizing reduced volume by ~0.8x average
            # Momentum Stall cuts the remaining loss by another 15% (x 0.85) => 0.68
            new_val = (val * 0.80) * 0.85
        
        new_totals.append(new_val)
        
    df['new_total'] = new_totals
    
    new_avg = df['new_total'].mean()
    new_worst = df['new_total'].min()
    new_total = df['new_total'].sum()

    print(f"[PHASE 3 & 4 ON SIMULATION]")
    print(f"   Avg Day:   {new_avg:8.2f} USD ({(new_avg - original_avg)/abs(original_avg)*100:+.2f}%)")
    print(f"   Worst Day: {new_worst:8.2f} USD ({(new_worst - original_worst)/abs(original_worst)*100:+.2f}%)")
    print(f"   Total PnL: {new_total:8.2f} USD ({(new_total - original_total)/abs(original_total)*100:+.2f}%)")
    print("="*60)
    print()

if __name__ == "__main__":
    simulate_phase34("LTS_AVENGERS_ULTRA_SAFE", "strategy/demo_portfolio/excel/lts/LTS_AVENGERS_ULTRA_SAFE_daily.csv")
    simulate_phase34("LTS_AVENGERS_HIGH_RISK", "strategy/demo_portfolio/excel/lts/LTS_AVENGERS_HIGH_RISK_daily.csv")
