#!/bin/bash
# รัน 24 กลุ่ม (365 วัน) หลังแก้บั๊ก magic-fill/SL-slippage/compare-symbol เรียงทีละกลุ่ม
# (รันพร้อมกันเสี่ยง MT5 terminal เดียวกันชนกัน) บันทึก log แยกไฟล์ต่อกลุ่มไว้ให้ parse ทีหลัง
set -uo pipefail
cd /d/Project/Copter01_AI_Bot_2
OUT_DIR="strategy/s20.14.1/backtest-summary/quant-verification-v2/raw_logs"
mkdir -p "$OUT_DIR"
for g in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24; do
  echo "=== START group$g $(date) ==="
  python "strategy/s20.14.1/backtest-sim/v38_standalone_group${g}.py" --day 365 > "$OUT_DIR/group${g}.log" 2>&1
  echo "=== DONE group$g $(date) exit=$? ==="
done
echo "ALL 24 GROUPS DONE $(date)"
