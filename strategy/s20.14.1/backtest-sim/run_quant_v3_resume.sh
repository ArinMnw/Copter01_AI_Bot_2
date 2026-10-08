#!/bin/bash
# resume: ข้าม group ที่มี log สมบูรณ์อยู่แล้ว (จบด้วย "Saved: compare.csv")
set -uo pipefail
cd /d/Project/Copter01_AI_Bot_2/strategy/s20.14.1/backtest-sim
BASE="../backtest-summary/quant-verification-v3"
declare -A MODE=( [1]="S20.14.23" [2]="S20.13.23" [3]="S20.14.23" [4]="S20.13.23" )
declare -A TARGET=( [1]="SL_ONLY" [2]="SL_ONLY" [3]="BOTH" [4]="BOTH" )
ALL_GROUPS="1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24"
for r in 1 2 3 4; do
  for g in $ALL_GROUPS; do
    LOG="$BASE/round_$r/raw_logs/group${g}.log"
    if [ -f "$LOG" ] && tail -3 "$LOG" | grep -q "Saved: compare.csv"; then
      echo "=== SKIP round$r group$g (already done) ==="
      continue
    fi
    echo "=== START round$r group$g mode=${MODE[$r]} target=${TARGET[$r]} $(date) ==="
    TPSL_EXP_MODE="${MODE[$r]}" TPSL_EXP_TARGET="${TARGET[$r]}" PYTHONIOENCODING=utf-8 \
      python -u v38_standalone_group${g}.py --day 365 > "$LOG" 2>&1
    echo "=== DONE round$r group$g exit=$? $(date) ==="
  done
done
echo "ALL QUANT-V3 RUNS DONE $(date)"
