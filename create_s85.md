# S85 Attempt - Significant Level Rejection

สถานะ: research/backtest-only, ยังไม่ wire เข้า live bot

## Baseline

Champion ล่าสุดยังเป็น:

```text
S81 = P16 + S63x12.8 + S69x22.1925 + S64x13.875
```

| Metric | S81 |
|---|---:|
| Avg $/day | 339.82 |
| Min $/day | 313.60 |
| Min PF | 4.37 |
| Max streak | 3 |
| Worst day | -999.91 |

## Candidate

```text
S85 = All-in-4S Significant Level Rejection
```

ที่มาจาก notes/PDF:

- key levels มาจาก old H/L breaks
- first rejection wick
- old support/resistance
- doji/significant candle
- psychological/context levels

## Implementation

ไฟล์:

- `strategy85.py`
- `sim_s85_backtest.py`
- `optimize_s85_significant_level.py`

หลักการ:

1. หา level จาก pivot high/low และ doji high/low
2. level ต้องมีอายุอย่างน้อย `MIN_LEVEL_AGE`
3. ราคา revisit/touch level
4. แท่งปิด reject ออกจาก level พร้อม wick ชัด
5. ถ้าเปิด trend filter ต้องมี momentum เข้า level ก่อน reject
6. fill ที่แท่งถัดไปเท่านั้น
7. exact sizing ใช้ `simulate_equity_substream(raw, cfg, START_EQUITY=1000)`

## Performance Note

ตอนแรก optimizer ช้าเพราะคำนวณ pivot/doji level ซ้ำทุกแท่งทุก config จึงเพิ่ม `_PRE_LEVELS` cache ใน `sim_s85_backtest.py`.

Look-ahead guard ของ cache:

- precompute ทั้งชุดได้ แต่ตอน detect ใช้เฉพาะ `idx <= j - MIN_LEVEL_AGE`
- `MIN_LEVEL_AGE` มากกว่า `PIVOT_RIGHT` ดังนั้น pivot ถูก confirm แล้วก่อนนำมาใช้

## 90d Manual Scout

ไฟล์ summary:

```text
s85_backtest_summary.csv
```

ผลที่สำคัญ:

| Label | Signals | Comp $/day | PF | Fixed $/day | Fixed PF | Max streak |
|---|---:|---:|---:|---:|---:|---:|
| s85_default_90 | 405 | 0.21 | 1.02 | -0.21 | 0.99 | 8 |
| s85_strict_a_90 | 172 | 0.68 | 1.18 | 0.43 | 1.06 | 5 |
| s85_strict_b_90 | 105 | -1.72 | 0.45 | -1.65 | 0.73 | 5 |
| s85_doji_strict_90 | 145 | 0.73 | 1.23 | 0.94 | 1.15 | 4 |
| s85_strict_c_90 | 82 | -0.50 | 0.67 | -2.32 | 0.51 | 5 |
| s85_strict_d_90 | 225 | -1.12 | 0.76 | -0.67 | 0.92 | 6 |
| s85_m15_strict_90 | 81 | 0.61 | 1.23 | -0.67 | 0.89 | 8 |

## Verdict

S85 ยังไม่ผ่าน champion:

- best 90d มี edge เล็ก แต่ max streak ต่ำสุดที่ยังเป็นบวกคือ 4
- ยังไม่ผ่าน guard `max losing-day streak <= 3`
- avg $/day เล็กมากเมื่อเทียบกับ S81
- ยังไม่ควรนำไป overlay กับ S81

Champion ล่าสุดยังเป็น S81.

## Look-Ahead Bias Audit

- `strategy85._detect_closed()` ใช้ closed bar index `j`
- `sim_s85_backtest.replay85()` fill ที่ `j + 1`
- TP/SL exit ใช้ข้อมูลหลัง fill เท่านั้น
- `_PRE_LEVELS` cache filter ด้วย `idx <= j - MIN_LEVEL_AGE`
- ไม่ wire เข้า live bot

## Next Direction

ทางต่อควรทำ S86 จาก Fibo 50-60 / RUN decision หรือ HTF D1/H12 future-read filter เพราะ S85 significant-level rejection ยังมี edge จางและ streak สูง.
