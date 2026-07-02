# S60 — Asian Range Sweep Reversal — research/backtest-only

วันที่เริ่ม: 2026-07-02 (Codex/Alice)
สถานะ: กำลังวิจัย — ยังไม่ wire เข้า live

## ที่มา

โจทย์คือหา Champion ตัวใหม่จาก mechanism ใหม่ ไม่ใช่ optimize leg เดิมของ Demo Portfolio

ไอเดีย S60: ใช้ high/low ของ Asian session เป็น liquidity pool ระยะสั้น แล้วเทรด reversal เมื่อช่วง
London/NY sweep เหนือ/ใต้กรอบและปิดกลับเข้ากรอบพร้อม displacement body ยืนยัน

ต่างจาก leg เดิม:
- S42 CRT ใช้ range block N แท่งล่าสุด ไม่ได้ anchor กับ session/time-of-day
- S51/S56 ใช้ prior-day/weekly extremes ไม่ใช่ Asia intraday liquidity pool
- S49/S44 ใช้ VWAP/volume profile fair value ไม่ใช่ stop-run reversal จาก session range

## Implementation

- `strategy60.py` — detect_s60()
- `sim_s60_backtest.py` — replay + fixed-lot sanity stats
- `optimize_s60.py` — grid search 648 combinations บน 150 วัน

## กติกาเริ่มต้น

- Asian range: 02:00-13:55 BKK
- Trade window: 14:00-23:00 BKK
- Entry TF: M5, market entry ที่ close ของแท่ง sweep/reject
- BUY: sweep ต่ำกว่า Asia low แล้วปิดกลับเหนือ Asia low
- SELL: sweep สูงกว่า Asia high แล้วปิดกลับใต้ Asia high
- SL: เลย sweep extreme + ATR buffer
- TP: fixed RR
- บังคับ fixed-lot sanity check เพราะอาจมีหลายไม้ต่อเดือน/วัน

## Grid plan

รันอย่างน้อย 50 combination ตาม template:

- sweep ATR: 0.10, 0.20, 0.35
- reject ATR: 0.05, 0.10, 0.20
- min range ATR: 1.0, 2.0, 3.0
- body ATR: 0.0, 0.10, 0.20
- SL ATR: 0.5, 0.8, 1.0
- RR: 0.8, 1.0, 1.2, 1.5
- confirmation: none, htf_trend

รวม 648 combination บน window 150 วันก่อน แล้วค่อย robust check 90/120/180 วันสำหรับตัวที่ดีที่สุด

## ผลรอบที่ 1 — reversal mode

Baseline 90 วัน:

- fixed-lot PF = 0.39
- fixed $/day = -4.71
- sharpe = -0.421
- max losing-day streak = 11 วัน

Quick grid 144 combinations (90 วัน) สำหรับ reversal:

- best fixed PF = 0.758
- best fixed $/day = -1.88
- best sharpe = -0.126
- best config = `reversal_sw0.1_rej0.15_mr1.0_body0.0_sl1.0_rr1.6_none`

สรุป: ฝั่ง liquidity-sweep reversal ไม่มี edge ในข้อมูลนี้

## ผลรอบที่ 2 — breakout continuation mode

เพิ่มแนวทาง edge-improvement คนละฝั่งใน S60 เดิม: หลัง Asia range แตก ให้ตาม breakout แทน fade กลับ

Quick grid รวม reversal+breakout 288 combinations (90 วัน):

- best fixed PF = 1.200
- best fixed $/day = +1.33
- best sharpe = 0.087
- trades = 69
- max losing-day streak = 5 วัน
- best config = `breakout_sw0.1_rej0.15_mr1.0_body0.15_sl0.6_rr1.2_none`

Robust check ของ best config:

| Window | Trades | fixed $/day | fixed PF | Sharpe | Max losing-day streak |
|---|---:|---:|---:|---:|---:|
| 90d | 69 | +1.33 | 1.20 | 0.087 | 5 |
| 120d | 86 | +3.21 | 1.54 | 0.189 | 5 |
| 150d | 114 | +2.43 | 1.42 | 0.148 | 7 |
| 180d | 138 | +2.53 | 1.45 | 0.159 | 7 |

Sanity-check trade ตัวอย่าง 8 ไม้แรกผ่าน:

- BUY: entry < TP และ SL < entry
- SELL: TP < entry และ SL > entry
- `diff_usd_per_001lot` ตรงกับ outcome

ตัวอย่าง:

```text
2026-05-19 17:45 SELL SL entry 4529.32 sl 4544.81 tp 4510.73 diff -15.49
2026-05-20 21:35 BUY  TP entry 4524.53 sl 4501.58 tp 4552.07 diff +27.54
2026-05-27 17:40 SELL TP entry 4463.77 sl 4478.69 tp 4445.87 diff +17.90
2026-05-28 21:45 BUY  TP entry 4469.16 sl 4451.93 tp 4489.84 diff +20.68
```

## บทสรุปชั่วคราว

S60 ไม่ใช่ Champion ตัวใหม่เดี่ยว เพราะกำไร fixed-lot ยังเล็กมากเมื่อเทียบ P13/P16 เดิม แต่ไม่ควรทิ้ง:

- reversal version = reject
- breakout version = มี edge จริงระดับเล็ก/กลาง (PF 1.42-1.54 ใน 120-180 วัน)
- candidate ที่ควรทดสอบต่อคือเพิ่มเป็น leg ใหม่ของ Demo Portfolio (`S60 AsiaBreakout`) แล้วทำ
  leave-one-in / correlation check กับ P13 เพราะกลไกเป็น time-of-day/session breakout ต่างจาก
  prior-period extreme และ volume profile เดิม

## สถานะล่าสุด

- [x] เลือกเลข strategy ถัดไป: S60
- [x] สร้าง strategy/backtest/optimizer
- [x] รัน grid search >= 50 combination (288 combinations)
- [x] ลอง edge-improvement 2 แนวทาง: reversal และ breakout
- [x] sanity-check trade ตัวอย่าง
- [x] robust window check 90/120/150/180
- [ ] leave-one-in / blend contribution กับ P13/P16
- [ ] สรุปว่าเป็น Champion candidate หรือ reject หลัง blend test
