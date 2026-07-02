# S63 - All-in-4S DMxSP/FVG Reclaim

วันที่เริ่มวิจัย: 2026-07-02
สถานะ: research/backtest-only, ยังไม่ wire เข้า live bot

## แหล่งที่มา

แตกต่อจาก S62 หลัง close-cover reversal เดี่ยว ๆ ไม่ robust

อ้างอิงเอกสาร All-in-4S:

- หน้า DMxSP 83-90: มี SP zone หรือช่วงพักราคา แล้วราคาออกจากโซนแรง
- หน้า FVG 144-146: H1/H2, swing และ FVG ใช้เป็นนัยยะสำคัญประกอบการอ่านอนาคต

## นิยาม S63 v1

กฎที่แปลงเป็น code:

- หา SP box จากช่วงพักราคา `SP_LOOKBACK` แท่งก่อนหน้า
- box ต้องแคบกว่า `SP_MAX_ATR`
- BUY: มี sweep ใต้ box หรือ breakout แล้วแท่งเขียวปิดเหนือ box
- SELL: มี sweep เหนือ box หรือ breakout แล้วแท่งแดงปิดใต้ box
- optional FVG: ใช้ gap ระหว่างแท่งปัจจุบันกับแท่ง `j-2`
- body ของแท่ง displacement ต้องใหญ่พอ แต่ไม่เกิน max risk
- เข้า market ที่ close, SL หลัง zone/sweep + ATR buffer, TP fixed RR

## ไฟล์

- `strategy63.py`
- `sim_s63_backtest.py`
- `optimize_s63.py`
- `s63_backtest_summary.csv`
- `s63_optimize_summary.csv`

## Exhaustion Checklist

- [x] grid search >= 50 combinations
- [x] ลอง edge-improvement อย่างน้อย 2 แนวทาง
- [x] print ตัวอย่าง trade 5-10 ไม้และตรวจ logic
- [ ] คำนวณ expectancy ที่ต้องการเทียบกับผลจริง
- [ ] สรุปผลสุดท้ายก่อนแตก S64

## ผลรอบแรก

Baseline ที่บังคับ `sweep_reclaim + FVG` ไม่มี trade ใน 90 วัน จึง strict เกินไป

Quick grid 128 combinations:

- เมื่อเปิด/ปิด FVG และลอง breakout/either พบว่า edge อยู่ที่ M5 SP breakout แบบไม่บังคับ FVG
- Best usable 90 วัน:
  - `M5_breakout_lb8_sp1.4_fvg0_fm0.0_mb0.35_br0.4_sl0.35_rr1.2`
  - 42 trades
  - fixed-lot +$3.16/day
  - fixed PF 2.12
  - sharpe-like 0.338
  - max losing-day streak 3 วัน

Robust check:

| Candidate | 120d | 150d | 180d | สรุป |
|---|---:|---:|---:|---|
| A: M5 SP breakout, SL 0.35 ATR, RR 1.2 | PF 1.74, +$2.24/d | PF 1.75, +$2.05/d | PF 1.63, +$1.85/d | candidate leg |
| B: M5 SP breakout, SL 0.60 ATR, RR 0.9 | PF 1.64, +$1.84/d | PF 1.60, +$1.60/d | PF 1.43, +$1.26/d | safer but lower yield |

Sample trade sanity check:

- ตัวอย่าง 90 วันของ candidate A ได้ 42 trades, fixed PF 2.12
- entry/SL/TP ดูถูกฝั่ง: SELL ปิดออกจาก SP zone ลง, BUY ปิดออกจาก SP zone ขึ้น
- หลายไม้มี `sweep=1` แม้ config ไม่บังคับ FVG แปลว่า detector ยังจับ failure/reclaim ของ zone ได้จริง

## สรุปชั่วคราว

S63 ดีกว่า S62 ชัดเจนและเป็น candidate leg ที่น่าเก็บ:

- fixed PF 1.63-1.75 บน 120-180 วัน
- losing-day streak 3 วัน
- แต่กำไร fixed-lot ยังแค่ +$1.85/day ที่ 180 วัน ยังไม่ใช่ champion เดี่ยว

แนวทางถัดไป:

- ใช้ S63 เป็น leg/decorrelation candidate
- แตก S64 เป็น family "fibo-to-defect/engulf target" จากหน้า fibo 156-163 หรือเพิ่ม HTF/session filter ให้ S63 ถ้าต้องการจูนต่อ
