import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def _read_csv(path):
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))

def main():
    components_file = ROOT / "strategy" / "af" / "excel" / "af_ladder_components.csv"
    if not components_file.exists():
        print("Run export_af_ladder_composition.py first.")
        return

    components = _read_csv(components_file)
    
    # Load daily PnL for 180 days for all components
    daily_data = {} # comp_no -> dict of date -> total_pnl
    all_dates = set()
    
    for comp in components:
        comp_no = int(comp["component_no"])
        file_path = ROOT / comp["daily_file"]
        rows = _read_csv(file_path)
        data = {}
        for r in rows:
            if int(r["days"]) == 180:
                d = r["date"]
                data[d] = float(r["total"])
                all_dates.add(d)
        daily_data[comp_no] = data

    sorted_dates = sorted(list(all_dates))
    
    if len(sorted_dates) > 180:
        sorted_dates = sorted_dates[-180:]
        
    is_dates = sorted_dates[:120]
    oos_dates = sorted_dates[120:]
    
    print(f"IS period: {is_dates[0]} to {is_dates[-1]} ({len(is_dates)} days)")
    print(f"OOS period: {oos_dates[0]} to {oos_dates[-1]} ({len(oos_dates)} days)")

    # Calculate leg contributions
    leg_stats = []
    prev_daily = daily_data[0] # Base S88
    
    def calc_metrics(dates, data_dict):
        vals = [data_dict.get(d, 0.0) for d in dates]
        return sum(vals), sum(vals)/len(dates) if dates else 0, min(vals) if dates else 0
    
    # Portfolio tracking
    is_port = [0.0] * len(is_dates)
    oos_port = [0.0] * len(oos_dates)
    
    # Add base to portfolio
    for i, d in enumerate(is_dates):
        is_port[i] += daily_data[0].get(d, 0.0)
    for i, d in enumerate(oos_dates):
        oos_port[i] += daily_data[0].get(d, 0.0)

    for comp in components:
        comp_no = int(comp["component_no"])
        name = comp["component_name"]
        
        if comp_no == 0:
            is_sum, is_avg, is_min = calc_metrics(is_dates, daily_data[0])
            oos_sum, oos_avg, oos_min = calc_metrics(oos_dates, daily_data[0])
            leg_stats.append({
                "leg_no": comp_no, "name": name,
                "is_sum": is_sum, "is_avg": is_avg, "is_min": is_min,
                "oos_sum": oos_sum, "oos_avg": oos_avg, "oos_min": oos_min
            })
            continue

        cur_daily = daily_data[comp_no]
        leg_contrib = {}
        for d in sorted_dates:
            leg_contrib[d] = cur_daily.get(d, 0.0) - prev_daily.get(d, 0.0)
            
        is_sum, is_avg, is_min = calc_metrics(is_dates, leg_contrib)
        oos_sum, oos_avg, oos_min = calc_metrics(oos_dates, leg_contrib)
        
        leg_stats.append({
            "leg_no": comp_no, "name": name,
            "is_sum": is_sum, "is_avg": is_avg, "is_min": is_min,
            "oos_sum": oos_sum, "oos_avg": oos_avg, "oos_min": oos_min
        })
        
        # Add to portfolio
        for i, d in enumerate(is_dates):
            is_port[i] += leg_contrib.get(d, 0.0)
        for i, d in enumerate(oos_dates):
            oos_port[i] += leg_contrib.get(d, 0.0)
            
        prev_daily = cur_daily

    # Report Portfolio
    def calc_port_metrics(vals):
        if not vals: return 0,0,0
        return sum(vals)/len(vals), min(vals), min(vals) # simplistic, real streak/worst day need numpy
        
    is_avg, is_min, _ = calc_port_metrics(is_port)
    oos_avg, oos_min, _ = calc_port_metrics(oos_port)
    
    print("\nPortfolio Metrics:")
    print(f"IS (120d) : avg $/day = {is_avg:.2f}, min $/day = {min(is_port):.2f}, worst day = {min(is_port):.2f}")
    print(f"OOS (60d) : avg $/day = {oos_avg:.2f}, min $/day = {min(oos_port):.2f}, worst day = {min(oos_port):.2f}")
    
    # Save leg stats
    out_path = ROOT / "af51_walkforward_legs.csv"
    with out_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["leg_no", "name", "is_sum", "is_avg", "is_min", "oos_sum", "oos_avg", "oos_min"])
        w.writeheader()
        w.writerows(leg_stats)
    print(f"\nSaved leg stats to {out_path.name}")
    
    # Count survivors
    oos_positive = sum(1 for s in leg_stats if s["leg_no"] > 0 and s["oos_sum"] > 0)
    oos_negative = sum(1 for s in leg_stats if s["leg_no"] > 0 and s["oos_sum"] <= 0)
    print(f"\nOOS Survival: {oos_positive} legs positive, {oos_negative} legs negative/zero")

if __name__ == "__main__":
    main()
