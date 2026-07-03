# S83 Attempt - S67 Clear Candle Scout Above S81

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
S67 = All-in-4S Clear Candle
```

แนวคิดจาก PDF:

- clear candle คือแท่งที่ถูกดันแรงไปทางหนึ่งแล้วถูกดึงกลับมาปิดอีกฝั่ง
- ต้องมี rejection wick ชัด
- close ต้อง cover context ของแท่งก่อนหน้า
- แยก test เป็น reversal/continuation

## Runner

เพิ่ม optimizer:

```text
optimize_s67_clear_candle.py
```

โหมด:

```text
fixed/raw scout -> exact sizing validation เฉพาะ top candidates
```

ยังใช้ sizing เดียวกับ champion เดิม:

```text
simulate_equity_substream(raw, cfg, START_EQUITY=1000)
```

## 90d Scout

ไฟล์ผล:

```text
s67_clear_candle_micro_scout_90.csv
```

Best 90d:

| Metric | Best S67 90d |
|---|---:|
| Avg $/day | 1.44 |
| Min PF | 1.71 |
| Max streak | 3 |
| Worst day | -23.58 |
| Trades | 72 |

Config:

```text
ENTRY_TF = M5
MODE = continuation
CLOSE_COVER = body
MIN_BODY_ATR = 0.12
MIN_RANGE_ATR = 0.90
WICK_BODY_MULT = 1.20
WICK_RANGE_MIN = 0.35
TREND_LOOKBACK = 14
TREND_MIN_ATR = 1.0
SL_ATR_MULT = 0.35
TP_RR = 1.0
```

## 90/120/150/180 Scout

ไฟล์ผล:

```text
s67_clear_candle_micro_scout_4w.csv
```

Best by avg across 4 windows:

| Metric | S67 best 4w |
|---|---:|
| Avg $/day | 2.00 |
| Min $/day | 0.76 |
| Min PF | 1.30 |
| Max streak | 7 |
| Worst day | -45.19 |
| Min trades | 88 |

Best near-pass candidate:

| Metric | S67 near-pass |
|---|---:|
| Avg $/day | 1.53 |
| Min $/day | 0.77 |
| Min PF | 1.43 |
| Max streak | 4 |
| Worst day | -36.36 |
| Min trades | 43 |

## Verdict

S83 ยังไม่ผ่าน champion:

- 90d มี candidate ที่ดูดีและ streak 3
- แต่พอขยายเป็น 90/120/150/180 แล้ว max losing-day streak เพิ่มเป็น 4-7
- standalone edge เล็กเกินไปเมื่อเทียบกับ S81
- ยังไม่ควรเอาไปเพิ่ม S81 เป็น champion leg จนกว่าจะมี filter ลด streak

Champion ล่าสุดยังเป็น S81.

## Look-Ahead Bias Audit

- `strategy67._detect_closed()` ตรวจจาก closed bar index `j`
- `sim_s67_backtest.replay67()` fill ที่ `j + 1`
- TP/SL ใช้ bar หลัง fill สำหรับ exit เท่านั้น
- optimizer ใช้ exact sizing เดิมหลัง fixed/raw scout
- ยังไม่ wire เข้า live bot

## Files

- `strategy67.py`
- `sim_s67_backtest.py`
- `optimize_s67_clear_candle.py`
- `s67_clear_candle_micro_scout_90.csv`
- `s67_clear_candle_micro_scout_4w.csv`
- `create_s83.md`
