#!/bin/bash
# v4: หลังแก้บั๊ก backtest 3 จุด (2026-09-28) ใน 7 groups ที่มี Naiya (6,8,9,12,16,17,18):
#   1. Naiya Doji re-fire ทุกแท่งจนกว่า doji จะถูก invalidate (ไม่มี "already triggered" guard)
#   2. TPSL override อ่าน entry ผิด (locals()-sniffing ได้ limit_price ค้างจากบล็อกอื่น ไม่ใช่ limit_p)
#   3. TPSL override ขาดไปทั้งหมดใน Naiya/Naiya Hidden/Naiya Doji SELL + ไม่สมมาตรใน combined BUY
#   (Group 16/17 มีบั๊กเสริม: Naiya Doji BUY เรียก signal="SELL" ผิดทิศ)
# resume: ข้าม group ที่มี log สมบูรณ์อยู่แล้ว (จบด้วย "Saved: compare.csv")
set -uo pipefail
cd /d/Project/Copter01_AI_Bot_2/strategy/s20.14.1/backtest-sim
BASE="../backtest-summary/quant-verification-v4"
declare -A MODE=( [1]="S20.14.23" [2]="S20.13.23" [3]="S20.14.23" [4]="S20.13.23" )
declare -A TARGET=( [1]="SL_ONLY" [2]="SL_ONLY" [3]="BOTH" [4]="BOTH" )
ALL_GROUPS="1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24"
for r in 1 2 3 4; do
  for g in $ALL_GROUPS; do
    LOG="$BASE/round_$r/raw_logs/group${g}.log"
    mkdir -p "$BASE/round_$r/raw_logs"
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
echo "ALL QUANT-V4 RUNS DONE $(date)"
