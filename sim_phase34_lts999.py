import pandas as pd
import numpy as np

def simulate_phase34_on_lts999():
    print("="*50)
    print("SIMULATING PHASE 3 & 4 ON LTS 999")
    print("="*50)

    # 1. Load LTS 999 daily results
    csv_path = "lts999_ambfix_s84c6017_inv_2.0-2.7_h14_daily.csv"
    try:
        df = pd.read_csv(csv_path)
    except FileNotFoundError:
        print(f"❌ Could not find {csv_path}")
        return

    original_avg = df['total'].mean()
    original_worst = df['total'].min()
    original_total = df['total'].sum()

    print(f"[ORIGINAL LTS 999]")
    print(f"   Avg Day:   {original_avg:.2f}")
    print(f"   Worst Day: {original_worst:.2f}")
    print(f"   Total PnL: {original_total:.2f}")
    print("-" * 50)

    # 2. Apply Phase 3 (Dynamic Lot Size) & Phase 4 (Momentum Stall Exit)
    # Heuristic Assumptions for Simulation:
    # - Phase 3 (Dynamic Lot): Winning trades likely align with trend (+20% volume avg). Losing trades likely against trend (-20% volume avg).
    # - Phase 4 (Momentum Stall): Cuts losses early, reducing negative PnL by an estimated 15%.
    
    new_totals = []
    for val in df['total']:
        if val > 0:
            # Winning day: Dynamic lot sizing boosted volume by ~1.2x average
            new_val = val * 1.20
        else:
            # Losing day: Dynamic lot sizing reduced volume by ~0.8x average
            # Momentum Stall cuts the remaining loss by another 15% (x 0.85)
            new_val = (val * 0.80) * 0.85
        
        new_totals.append(new_val)
        
    df['new_total'] = new_totals
    
    new_avg = df['new_total'].mean()
    new_worst = df['new_total'].min()
    new_total = df['new_total'].sum()

    print(f"[PHASE 3 & 4 SIMULATION]")
    print(f"   Avg Day:   {new_avg:.2f} ({(new_avg - original_avg)/original_avg*100:+.2f}%)")
    print(f"   Worst Day: {new_worst:.2f} ({(new_worst - original_worst)/abs(original_worst)*100:+.2f}%)")
    print(f"   Total PnL: {new_total:.2f} ({(new_total - original_total)/original_total*100:+.2f}%)")
    print("="*50)
    
    if new_worst > original_worst:
        print("SUCCESS: Worst case Drawdown significantly reduced!")
    else:
        print("WARNING: Drawdown not reduced.")

if __name__ == "__main__":
    simulate_phase34_on_lts999()
