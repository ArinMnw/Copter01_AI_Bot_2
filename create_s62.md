# S62 - All-in-4S First-Wave Close-Cover Reversal

วันที่เริ่มวิจัย: 2026-07-02
สถานะ: research/backtest-only, ยังไม่ wire เข้า live bot

## แหล่งที่มา

ใช้เอกสาร local ใน `C:\Users\Copter\Downloads\อออิน4s` โดยเฉพาะไฟล์ `วิชาอออิน4S upgrade .pdf`
และหน้าที่ render ไว้ใน `tmp/pdfs/allin4s/`

ข้อสังเกตที่แปลงเป็น logic ได้:

- หน้ากลับตัว 14-17: ใช้สัญญาณกลับตัวฝั่ง B/S ที่เกิดใกล้ H/L และเส้นนัยยะสำคัญ เน้นคลื่นลูกแรก
- หน้าตำหนิ 23-29: แรงที่ดีต้องปิดคลุมเนื้อ-ไส้ ถ้าปิดคลุมแค่บางส่วนคุณภาพต่ำกว่า
- หน้าฟิโบ 156-158: ต้องหา swing หลัก และเป้าหมายคือจุดตำหนิ/กลืนกิน โดยแท่งต้องไม่ใหญ่เกินไป
- หน้า DMxSP/FVG 83-90 และ 144-146: โซนพักราคา, FVG, SP และ H1/H2 เป็น context สำคัญ ไม่ควรดูแท่งเดียวโดด ๆ

## นิยาม S62 v1

ชื่อทำงาน: All-in-4S First-Wave Close-Cover Reversal

กฎหลัก:

- เทรดเฉพาะหลังเกิด short-term trend ไปด้านหนึ่งก่อน
- BUY: ราคาอยู่ในบริบทลง แล้วแท่งเขียวปิดคลุมแท่งก่อนหน้า
- SELL: ราคาอยู่ในบริบทขึ้น แล้วแท่งแดงปิดคลุมแท่งก่อนหน้า
- ต้องอยู่ใกล้ level: sweep high/low ล่าสุด, ใกล้ high/low สำคัญ, หรือใกล้เลขกลม
- กันคลื่นซ้ำด้วย `FIRST_WAVE_BARS`
- body ของแท่งสัญญาณต้องมีนัยยะ แต่ไม่ใหญ่เกิน ATR
- เข้า market ที่ close ของแท่งสัญญาณ, SL หลัง wick + ATR buffer, TP เป็น RR fixed

## ไฟล์

- `strategy62.py` - detector สำหรับ research
- `sim_s62_backtest.py` - backtest ราย config
- `optimize_s62.py` - grid search
- `s62_backtest_summary.csv` - log ผล backtest ราย config
- `s62_optimize_summary.csv` - log ผล grid search

## Exhaustion Checklist

- [x] grid search >= 50 combinations
- [x] ลอง edge-improvement อย่างน้อย 2 แนวทาง
- [x] print ตัวอย่าง trade 5-10 ไม้และตรวจ logic
- [ ] คำนวณ expectancy ที่ต้องการเทียบกับผลจริง
- [x] สรุปผลสุดท้ายก่อนแตก S63/S64

## ผลรอบแรก

Baseline 90 วัน:

- 225 trades
- fixed-lot +$1.94/day
- fixed PF 1.11
- sharpe-like 0.074
- max losing-day streak 7 วัน

Quick grid 384 combinations:

- ตัว strict ที่ดีที่สุดใน 90 วัน: `M15_sweep_wick_tr8_pv8_lv60_mb0.1_xb1.8_br0.3_fw12_sl0.35_rr0.9`
- 90 วัน: 10 trades, fixed PF 2.53, +$0.74/day, sharpe-like 0.577
- ปัญหา: จำนวนไม้ต่ำมาก และมีความเสี่ยง overfit

Robust check:

| Candidate | 120d | 150d | 180d | สรุป |
|---|---:|---:|---:|---|
| A: M15 sweep wick | PF 1.07, +$0.06/d | PF 1.07, +$0.05/d | PF 0.69, -$0.39/d | ไม่ robust |
| B: M15 sweep body | PF 1.32, +$0.47/d | PF 1.27, +$0.36/d | PF 0.93, -$0.12/d | ดีช่วงกลางแต่พัง 180d |
| C: M5 frequency | PF 0.99, -$0.28/d | PF 1.01, +$0.20/d | PF 0.96, -$0.66/d | ไม่มี edge จริง |

## บทสรุป S62 v1

Close-cover reversal แบบเดี่ยว ๆ ยังไม่ใช่ champion:

- สัญญาณ strict ให้ PF สูงแต่ sample น้อยและไม่ทน window ยาว
- สัญญาณกว้างให้จำนวนไม้พอ แต่ fixed-lot PF กลับมาใกล้ 1.0
- แนวคิดนี้อาจใช้เป็น confirmation ประกอบ strategy อื่นได้ แต่ไม่ควรเป็น standalone leg ตอนนี้

ต่อไปแตกเป็น S63: DMxSP/FVG reclaim ซึ่งเป็น family คนละชุดจากเอกสารอออิน4s
