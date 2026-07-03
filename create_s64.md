# S64 - All-in-4S KRH Fibo Expansion Hold

วันที่เริ่มวิจัย: 2026-07-02
สถานะ: research/backtest-only, ยังไม่ wire เข้า live bot

## แหล่งที่มา

แตกต่อจาก S63 ตาม family อออิน4s ส่วนฟิโบ หน้า 156-163

แนวคิดจากเอกสาร:

- ต้องหา swing/seed หลักก่อน
- เป้าหมายของฟิโบคือจุดตำหนิหรือกลืนกิน
- ใช้ level เฉพาะ เช่น 1.617, 3.097, 5.165, 7.044
- หน้า 159-161 เน้นการตัดสินใจว่า level 2 หลุดหรือไม่หลุด

## นิยาม S64 v1

- หา seed จากคู่แท่ง engulf/defect ที่ body ไม่เล็กและไม่ใหญ่เกิน ATR
- ใช้ high/low ของคู่แท่งเป็นฐาน fibo expansion
- BUY seed: project level ขึ้นจาก low ของ seed
- SELL seed: project level ลงจาก high ของ seed
- เข้าเมื่อราคา hold หรือ break level เป้าหมาย เช่น 1.617 หรือ 3.097
- TP ใช้ KRH level ถัดไป หรือ RR fixed
- SL ใช้ level ก่อนหน้า + ATR buffer

## ไฟล์

- `strategy64.py`
- `sim_s64_backtest.py`
- `optimize_s64.py`
- `s64_backtest_summary.csv`
- `s64_optimize_summary.csv`

## Exhaustion Checklist

- [x] grid search >= 50 combinations
- [x] ลอง edge-improvement อย่างน้อย 2 แนวทาง
- [x] print ตัวอย่าง trade 5-10 ไม้และตรวจ logic
- [ ] คำนวณ expectancy ที่ต้องการเทียบกับผลจริง
- [ ] สรุปผลสุดท้ายก่อนแตก S65

## ผลรอบแรก

Baseline 90 วัน:

- 136 trades
- fixed-lot +$2.26/day
- fixed PF 1.22
- sharpe-like 0.133
- max losing-day streak 9 วัน
- ปัญหา: TP แบบ KRH บางไม้ใกล้ entry เกินไป และมีสัญญาณซ้ำ seed เดิม

Quick grid 96 combinations:

- Best 90 วันก่อนแก้ one-shot:
  - `M15_break_slb36_lv3.097_tg5.165_smn0.25_mb0.12_sll1.617_sl0.25_krh_rr1.2`
  - 42 trades, fixed PF 1.67, +$3.18/day, streak 2
- High-frequency candidate:
  - `M15_break_slb36_lv1.617_tg3.097_smn0.25_mb0.12_sll0.0_sl0.25_krh_rr1.2`
  - 251 trades, fixed PF 1.35, +$10.05/day, streak 5

Bug/logic fix:

- พบว่า seed เดิมยิงซ้ำหลายไม้หลัง break level
- แก้ `sim_s64_backtest.py` ให้ one-shot ต่อ `(seed_idx, side, level, mode)`

Robust หลัง one-shot:

| Candidate | 90d | 120d | 150d | 180d | สรุป |
|---|---:|---:|---:|---:|---|
| A: M15 KRH2 break -> KRH3 | PF 1.49, +$2.33/d | PF 1.55, +$2.58/d | PF 1.35, +$1.53/d | PF 1.45, +$1.77/d | candidate รอง |

## สรุปชั่วคราว

S64 มี edge พอใช้แต่ต่ำกว่า S63:

- robust fixed PF ประมาณ 1.35-1.55
- losing-day streak 2-4 วัน
- ยังไม่ใช่ champion เดี่ยว
- จุดอ่อนคือ risk/target จาก KRH level บางช่วงไม่สมดุล และ compounding PF แกว่ง

แนวทางถัดไป:

- เก็บเป็น candidate leg รอง
- ถ้าจะเดินต่อ ให้แตก S65 เป็น psychological level + defect/close-cover หรือปรับ S64 เพิ่ม HTF trend/session filter
