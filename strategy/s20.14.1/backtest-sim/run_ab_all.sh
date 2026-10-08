#!/bin/bash
set -uo pipefail
cd /d/Project/Copter01_AI_Bot_2/strategy/s20.14.1/backtest-sim
OUT=../backtest-summary/checklist13-test/ab_logs
declare -A MODE=( [3]="S20.13.23" [4]="S20.13.23" [13]="S20.13.23" [22]="S20.13.23" )
declare -A TARGET=( [3]="BOTH" [4]="SL_ONLY" [13]="BOTH" [22]="SL_ONLY" )
for g in 3 4 13 22; do
  for cond in nocap cap; do
    if [ "$cond" = "nocap" ]; then CAP=999999999; else CAP=1024; fi
    echo "=== START group$g $cond (cap=$CAP) $(date) ==="
    TPSL_EXP_MODE="${MODE[$g]}" TPSL_EXP_TARGET="${TARGET[$g]}" _CHECKLIST13_CAP_OVERRIDE=$CAP PYTHONIOENCODING=utf-8 \
      python -u v38_standalone_group${g}.py --start 2025-09-23 --end 2026-09-23 > "$OUT/group${g}_${cond}.log" 2>&1
    echo "=== DONE group$g $cond exit=$? $(date) ==="
  done
done
echo "ALL AB TESTS DONE"
