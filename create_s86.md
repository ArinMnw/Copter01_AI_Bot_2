# S86 Attempt - Fibo 50-60 RUN Decision

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
S86 = All-in-4S Fibo 50-60 RUN Decision
```

ที่มาจาก notes/PDF:

- Fibo 50-60 เป็น decision area ก่อน RUN
- ถ้าราคาทดสอบ 50 แล้วไม่ break structure อาจ RUN ต่อ
- ถ้า break 50 structure อาจกลับไป old low/high
- KRH/RUN ควรเป็น structured target/validation ไม่ใช่ blind entry

## Implementation

ไฟล์:

- `strategy86.py`
- `sim_s86_backtest.py`

หลักการ:

1. หา impulse ล่าสุดจาก pivot low/high
2. impulse ต้องใหญ่กว่า `IMPULSE_MIN_ATR`
3. รอราคา pullback เข้า zone 50-60
4. รอแท่งปิด reclaim level 50 พร้อม body/range confirmation
5. fill ที่แท่งถัดไป
6. TP ใช้ old high/low หรือ RR
7. SL ใช้ swing/zone + ATR buffer
8. exact sizing ใช้ `simulate_equity_substream(raw, cfg, START_EQUITY=1000)`

## 90d Manual Scout

ไฟล์ summary:

```text
s86_backtest_summary.csv
```

| Label | TF | Signals | Comp $/day | PF | Fixed $/day | Fixed PF | Max streak |
|---|---|---:|---:|---:|---:|---:|---:|
| s86_default_90 | M5 | 306 | -1.12 | 0.92 | -0.85 | 0.95 | 5 |
| s86_rr_zone_90 | M5 | 412 | 3.11 | 1.28 | 2.10 | 1.09 | 7 |
| s86_m15_90 | M15 | 140 | 0.59 | 1.10 | 3.32 | 1.27 | 5 |
| s86_strict_a_90 | M5 | 188 | 1.01 | 1.17 | -0.21 | 0.98 | 9 |
| s86_strict_b_90 | M5 | 258 | 1.36 | 1.17 | -0.70 | 0.96 | 14 |
| s86_m15_strict_90 | M15 | 81 | 4.72 | 1.91 | 3.32 | 1.39 | 6 |

## M15 Strict 4-Window Scout

Config:

```text
ENTRY_TF = M15
LOOKBACK = 96
IMPULSE_MIN_ATR = 2.6
ZONE_TOL_ATR = 0.08
CONFIRM_BODY_ATR = 0.14
CONFIRM_BODY_RATIO = 0.35
REQUIRE_TREND = True
TREND_LOOKBACK = 16
TREND_MIN_ATR = 1.0
SL_MODE = zone
SL_ATR_MULT = 0.20
TP_MODE = rr
TP_RR = 1.5
```

| Window | Signals | Comp $/day | PF | Fixed $/day | Fixed PF | Max streak |
|---:|---:|---:|---:|---:|---:|---:|
| 90 | 81 | 4.72 | 1.91 | 3.32 | 1.39 | 6 |
| 120 | 114 | 1.86 | 1.35 | 4.77 | 1.50 | 6 |
| 150 | 145 | 2.44 | 1.51 | 4.88 | 1.57 | 6 |
| 180 | 173 | 1.75 | 1.39 | 3.56 | 1.41 | 6 |

## Verdict

S86 ยังไม่ผ่าน champion:

- มี positive edge ต่อเนื่องใน M15 strict
- แต่ max losing-day streak = 6 ทุก window
- comp $/day เล็กมากเมื่อเทียบกับ S81
- ยังไม่ควรนำไป overlay กับ S81 เพราะจะเสี่ยงเพิ่ม streak เหมือน S65/S67

Champion ล่าสุดยังเป็น S81.

## Look-Ahead Bias Audit

- `strategy86._detect_closed()` ใช้ closed bar index `j`
- pivot impulse ใช้ pivot ที่จบก่อน `j - 2`
- `sim_s86_backtest.replay86()` fill ที่ `j + 1`
- TP/SL exit ใช้ข้อมูลหลัง fill เท่านั้น
- ไม่ wire เข้า live bot

## Next Direction

S86 มี edge แต่ streak สูง ควรใช้เป็น filter/validator มากกว่า standalone leg หรือแตก S87 เป็น HTF D1/H12 future-read filter เพื่อคัดเฉพาะวัน/ทิศทางที่ควรเล่น.
