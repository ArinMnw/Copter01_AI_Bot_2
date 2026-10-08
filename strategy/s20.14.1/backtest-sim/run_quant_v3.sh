#!/bin/bash
# รัน 24 กลุ่ม (1-24, ไม่รวม group23 variant พิเศษ) x 4 round เต็มปี 365 วัน
# ด้วยโค้ดที่แก้ checklist ข้อ 10+13 แล้ว (TF-proportional expiry + pending cap)
set -uo pipefail
cd /d/Project/Copter01_AI_Bot_2/strategy/s20.14.1/backtest-sim
BASE="../backtest-summary/quant-verification-v3"
declare -A MODE=( [1]="S20.14.23" [2]="S20.13.23" [3]="S20.14.23" [4]="S20.13.23" )
declare -A TARGET=( [1]="SL_ONLY" [2]="SL_ONLY" [3]="BOTH" [4]="BOTH" )
ALL_GROUPS="1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24"
for r in 1 2 3 4; do
  for g in $ALL_GROUPS; do
    LOG="$BASE/round_$r/raw_logs/group${g}.log"
    echo "=== START round$r group$g mode=${MODE[$r]} target=${TARGET[$r]} $(date) ==="
    TPSL_EXP_MODE="${MODE[$r]}" TPSL_EXP_TARGET="${TARGET[$r]}" PYTHONIOENCODING=utf-8 \
      python -u v38_standalone_group${g}.py --day 365 > "$LOG" 2>&1
    echo "=== DONE round$r group$g exit=$? $(date) ==="
  done
  # group23 variants (mtf/mtf_limit/mtf_live) — เหมือน v2 เดิม รันแยกครั้งเดียวไม่ผูก round (ไม่มี TPSL override)
done
# group23 variants (mtf/mtf_limit/mtf_live) รันแยกไปแล้วในรอบก่อนหน้า (task brjlvim4d ที่ยังทำงานถูกต้อง
# แม้ ALL_GROUPS หลักจะพังเพราะบั๊กชื่อตัวแปรชนกับ bash builtin) ไม่ต้องรันซ้ำที่นี่
echo "ALL QUANT-V3 RUNS DONE $(date)"
