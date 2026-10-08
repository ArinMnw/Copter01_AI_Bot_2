#!/bin/bash
set -uo pipefail
cd /d/Project/Copter01_AI_Bot_2/strategy/s20.14.1/backtest-sim
OUT=../backtest-summary/checklist10-test
declare -A MODE=( [1]="S20.13.23" [3]="S20.13.23" [4]="S20.13.23" [13]="S20.13.23" [22]="S20.13.23" )
declare -A TARGET=( [1]="BOTH" [3]="BOTH" [4]="SL_ONLY" [13]="BOTH" [22]="SL_ONLY" )
for g in 1 3 4 13 22; do
  echo "=== START group$g OLD-map $(date) ==="
  TPSL_EXP_MODE="${MODE[$g]}" TPSL_EXP_TARGET="${TARGET[$g]}" _CHECKLIST10_USE_OLD_MAP=1 PYTHONIOENCODING=utf-8 \
    python -u v38_standalone_group${g}.py --start 2025-09-23 --end 2026-09-23 > "$OUT/group${g}_oldmap.log" 2>&1
  echo "=== DONE group$g OLD-map exit=$? $(date) ==="
  echo "=== START group$g NEW-map $(date) ==="
  TPSL_EXP_MODE="${MODE[$g]}" TPSL_EXP_TARGET="${TARGET[$g]}" PYTHONIOENCODING=utf-8 \
    python -u v38_standalone_group${g}.py --start 2025-09-23 --end 2026-09-23 > "$OUT/group${g}_newmap.log" 2>&1
  echo "=== DONE group$g NEW-map exit=$? $(date) ==="
done
echo "ALL CHECKLIST10 AB TESTS DONE"
