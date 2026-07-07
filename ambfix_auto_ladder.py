import argparse
import csv
import subprocess
import os
import re
import sys

CONFIG_POOL = [
    ("s84", 28),
    ("s84", 889),
    ("s84", 3057),
    ("s84", 4369),
    ("s84", 5505),
    ("s84", 6017),
    ("s86", 7171),
    ("s86", 7187),
    ("s86", 4227),
    ("s86", 6275),
    ("s86", 11)
]

def parse_raw_counts(rc_str):
    parts = rc_str.split(";")
    counts = {}
    for p in parts:
        days, count = p.split("d:")
        counts[int(days)] = int(count)
    return counts

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--start-idx", type=int, required=True)
    ap.add_argument("--target", type=float, default=10000.0)
    ap.add_argument("--keep-all", action="store_true")
    args = ap.parse_args()

    base_csv = args.base
    curr_idx = args.start_idx
    pool_idx = 0
    
    log_file = "auto_ladder_log.md"
    if not os.path.exists(log_file):
        with open(log_file, "w", encoding="utf-8") as f:
            f.write("# Auto Ladder Log\n\n")

    current_avg = 0.0

    while current_avg < args.target:
        fam, cfg_idx = CONFIG_POOL[pool_idx % len(CONFIG_POOL)]
        pool_idx += 1
        
        print(f"\n[{curr_idx}] Sweeping {fam}c{cfg_idx} on {base_csv}...")
        
        # Run sweep
        sweep_cmd = [sys.executable, "ambfix_sweep2.py", "--base", base_csv, "--family", fam, "--cfg-idx", str(cfg_idx), "--w-step", "10.0"]
        res = subprocess.run(sweep_cmd, capture_output=True, text=True)
        if res.returncode != 0:
            print(f"Sweep failed:\n{res.stderr}")
            break
            
        # Read sweep results
        candidates = []
        with open("ambfix_sweep_results.csv", "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                counts = parse_raw_counts(row["raw_counts"])
                # Require >= 5 trades at 180d
                if counts.get(180, 0) >= 5:
                    candidates.append(row)
                    
        if not candidates:
            print(f"No valid candidates with >=5 trades for {fam}c{cfg_idx}. Moving to next.")
            continue
            
        # Find best candidate (highest avg that doesn't hit cap)
        best = None
        for cand in candidates:
            if float(cand["weight"]) < 600.0:
                if best is None or float(cand["avg"]) > float(best["avg"]):
                    best = cand
                    
        if not best:
            # If all hit cap, take the one with highest avg
            best = max(candidates, key=lambda x: float(x["avg"]))
            
        label = best["label"]
        weight = float(best["weight"])
        print(f"[{curr_idx}] Selected {label} at ~W={weight}")
        
        # Parse label: e.g. INVERSE_S84c28_RD1.3-2.0_H18
        m = re.match(r"(DIRECT|INVERSE)_S(\d+)c(\d+)_RD([a-zA-Z0-9.\-]+)_H(\d+)", label)
        if not m:
            print(f"Failed to parse label {label}")
            break
            
        mode = m.group(1).lower()
        band = m.group(4)
        hour = m.group(5)
        
        w_lo = max(1.0, weight - 40.0)
        w_hi = weight + 40.0
        if weight >= 600.0:
            # Cap hit, expand search
            w_hi = 1200.0
            
        out_prefix = f"af{curr_idx}_ambfix_{fam}c{cfg_idx}_{mode[:3]}_{band}_h{hour}"
        
        print(f"[{curr_idx}] Building {out_prefix}...")
        build_cmd = [
            sys.executable, "ambfix_build2.py", 
            "--base", base_csv, 
            "--family", fam, 
            "--cfg-idx", str(cfg_idx), 
            "--mode", mode, 
            "--rd-band", band, 
            "--h", hour, 
            "--w-lo", str(w_lo), 
            "--w-hi", str(w_hi),
            "--out-prefix", out_prefix
        ]
        
        bres = subprocess.run(build_cmd, capture_output=True, text=True)
        if bres.returncode != 0:
            print(f"Build failed:\n{bres.stderr}")
            # try next config
            continue
            
        # Parse output for final stats
        # Best weight: 361.049 | avg: 3051.09 | min: 2800.00 | worst: -1000.00
        m2 = re.search(r"Best weight: ([0-9.]+) \| avg: ([0-9.]+) \| min: ([0-9.]+) \| worst: ([0-9.\-]+)", bres.stdout)
        if not m2:
            print(f"Failed to parse build output:\n{bres.stdout}")
            break
            
        final_w = float(m2.group(1))
        current_avg = float(m2.group(2))
        final_min = float(m2.group(3))
        
        print(f"[{curr_idx}] Built successfully! AF{curr_idx} avg = {current_avg:.2f}")
        
        # Log to file
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"- AF{curr_idx} = AF{curr_idx-1} + {label}x{final_w:.3f} -> avg: {current_avg:.2f}, min: {final_min:.2f}\n")
            
        # Cleanup old base if requested
        if not args.keep_all and (curr_idx - 1) % 10 != 0 and (curr_idx - 1) != args.start_idx - 1:
            try:
                if os.path.exists(base_csv):
                    os.remove(base_csv)
                old_probe = base_csv.replace("_daily.csv", "_probe.csv")
                if os.path.exists(old_probe):
                    os.remove(old_probe)
            except PermissionError as e:
                print(f"Skipping cleanup due to PermissionError: {e}")
                
        base_csv = f"{out_prefix}_daily.csv"
        curr_idx += 1

if __name__ == "__main__":
    main()
