#!/bin/bash
# เฝ้า log ของ batch 13-24 แล้ว append summary เข้า tf_optimization_summary.md ทันทีที่แต่ละกลุ่มเสร็จ
cd /d/Project/Copter01_AI_Bot_2
LOG="C:\Users\Copter\AppData\Local\Temp\claude\D--Project-Copter01-AI-Bot-2\16b27b43-9be4-4ba2-880a-4b73a4c722ac\tasks\b2bi3k6wo.output"
for g in 13 14 15 16 17 18 19 20 21 22 23 24; do
  until grep -q "DONE group${g} " "$LOG" 2>/dev/null; do sleep 15; done
  echo "=== group$g finished, appending summary ==="
  python scratch_append_group_summary.py "$g"
done
echo "ALL SUMMARIES 13-24 APPENDED"
