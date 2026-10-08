#!/bin/bash
set -uo pipefail
cd /d/Project/Copter01_AI_Bot_2
OUT_DIR="strategy/s20.14.1/backtest-summary/quant-verification-v2/raw_logs"
mkdir -p "$OUT_DIR"
for v in mtf mtf_limit mtf_live; do
  echo "=== START group23_$v $(date) ==="
  python "strategy/s20.14.1/backtest-sim/v38_standalone_group23_${v}.py" --day 365 > "$OUT_DIR/group23_${v}.log" 2>&1
  echo "=== DONE group23_$v $(date) exit=$? ==="
done
echo "ALL G23 VARIANTS DONE $(date)"
