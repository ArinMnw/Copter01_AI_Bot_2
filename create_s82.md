# S82 Attempt - S66 FVG Ladder Overlay Above S81

สถานะ: research/backtest-only, ยังไม่ wire เข้า live bot

## เป้าหมาย

หลังจาก reweight S63/S64/S69 ชนเพดานที่ S81 แล้ว รอบนี้ทดสอบ raw-trade overlay ใหม่จาก PDF อออิน4s:

```text
S66 = FVG Ladder Follow Trend
```

ยังใช้สูตร sizing เดียวกับ P13/P16/S75/S76/S77/S81:

```text
simulate_equity_substream(raw, cfg, START_EQUITY=1000)
-> daily_series_from_trades()
-> sum daily PnL across weighted legs
```

## Baseline

Champion ล่าสุดก่อนทดสอบ S66:

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

## S66 Config Tested

Runner: `optimize_s82_with_s66.py`

S66 config:

```text
ENTRY_TF = M5
LOOKBACK = 80
FVG_MIN_ATR = 0.04
MIN_FVG_COUNT = 3
ZONE_SELECT = base
TOUCH_TOL_ATR = 0.10
MIN_BODY_ATR = 0.18
MIN_BODY_RATIO = 0.35
CLOSE_BEYOND_ZONE = True
REQUIRE_LATEST_FAIL = False
SL_ATR_MULT = 0.35
TP_RR = 1.60
```

## S66 Standalone Result

ทดสอบ 90/120/150/180 วัน:

| Metric | S66 only |
|---|---:|
| Avg $/day | -0.44 |
| Min $/day | -1.85 |
| Min PF | 0.80 |
| Max streak | 8 |
| Worst day | -75.14 |

S66 standalone ไม่ผ่าน sizing จริง แม้ fixed-lot บางรอบเคยดูเป็นบวก

## Portfolio Search

Search:

```text
S81 + S66x0..80
floor = -1000
max streak <= 3
```

Top result ที่ผ่านจริงคือ `S66x0` หรือ S81 เดิม:

| Candidate | Avg $/day | Min $/day | Min PF | Max streak | Worst day |
|---|---:|---:|---:|---:|---:|
| S81 + S66x0 | 339.82 | 313.60 | 4.37 | 3 | -999.91 |
| S81 + S66x1 | 339.38 | 312.62 | 4.35 | 4 | -1054.57 |
| S81 + S66x2 | 338.94 | 311.65 | 4.31 | 4 | -1109.23 |

ผล: S66 เพิ่มเข้าพอร์ตแล้วทำให้ทั้ง min $/day, streak, worst day แย่ลง และทะลุ no-blow floor -1000 ตั้งแต่ weight 1

## Look-Ahead Bias Audit

ตรวจระดับ framework:

- S66 detect จาก closed bars เท่านั้น
- `sim_s66_backtest.py` fill ที่ bar ถัดไป (`fill_idx = j + 1`)
- Portfolio runner ใช้ `simulate_equity_substream()` เหมือน S75-S81
- `optimize_s82_with_s66.py` ไม่สร้าง signal จาก future OHLC; ใช้ raw trade replay แล้วค่อย reweight daily PnL

ข้อจำกัด:

- ยังไม่ได้ forensic audit รายบรรทัดของ S66 ทุก branch
- ยังไม่ได้ optimize S66 หลาย config ด้วย portfolio-level objective

## Verdict

S82 ไม่ผ่าน:

- ไม่มี candidate ที่ชนะ S81
- S66 standalone เป็นลบเมื่อใช้ sizing จริง
- เพิ่ม S66 แล้วพอร์ตแย่ลงและทะลุ floor -1000

Champion ล่าสุดยังเป็น S81

ทางต่อ:

- ปรับ performance optimizer ของ S65 Fake Reversal Trap แล้วค้นหา config ที่มี edge จริง
- หรือสร้าง generator ใหม่จาก PDF technique อื่น ไม่ใช่ใช้ S66 config นี้ต่อ

## S65 Follow-up Audit

หลัง S66 ไม่ผ่าน ได้ปรับ `optimize_s65_fake_trap.py` ให้มี `micro` preset และ `scout` mode:

```text
fixed/raw scout -> exact sizing validation เฉพาะ top candidates
```

ไฟล์ผล:

- `s65_fake_trap_micro_scout_90.csv`
- `s65_fake_trap_micro_scout_4w.csv`
- `optimize_s82_with_s65.py`
- `s82_with_s65_search.csv`
- `s82_with_s65_fine_low.csv`

Best S65 standalone จาก 90/120/150/180:

| Metric | S65 best |
|---|---:|
| Avg $/day | 2.51 |
| Min $/day | 1.76 |
| Min PF | 1.21 |
| Max streak | 6 |
| Worst day | -113.52 |

Best S65 config:

```text
ENTRY_TF = M5
LEG_LOOKBACK = 18
PULLBACK_BARS = 4
LEG_MIN_ATR = 1.3
PULLBACK_MIN_ATR = 0.15
FAIL_TOL_ATR = 0.05
CONFIRM_BODY_ATR = 0.10
SL_ATR_MULT = 0.45
TP_RR = 1.50
FLIP_SIGNAL = False
```

Portfolio overlay:

| Candidate | Avg $/day | Min $/day | Min PF | Max streak | Worst day | Verdict |
|---|---:|---:|---:|---:|---:|---|
| S81 + S65x0 | 339.82 | 313.60 | 4.37 | 3 | -999.91 | baseline |
| S81 + S65x0.05 | 339.94 | 313.71 | 4.37 | 4 | -999.69 | fail streak |
| S81 + S65x0.5 | 341.07 | 314.72 | 4.36 | 4 | -999.69 | fail streak |
| S81 + S65x4 | 349.86 | 322.56 | 4.27 | 4 | -999.69 | fail streak |
| S81 + S65x30 | 415.17 | 380.81 | 2.67 | 5 | -1944.08 | fail floor/streak |

ผล: S65 มี positive edge เล็กน้อยและดัน avg/min ได้ แต่เพิ่ม weight แค่ `x0.05` ก็ทำให้ max losing-day streak จาก 3 เป็น 4 ใน 90d จึงยังไม่ผ่านกติกา champion.

S65 look-ahead audit:

- detect จาก closed bar index `j`
- fill ที่ bar ถัดไป `fill_idx = j + 1`
- TP/SL simulation ใช้ข้อมูลหลัง fill เพื่อ exit เท่านั้น
- portfolio overlay ใช้ `simulate_equity_substream()` เดียวกับ S75-S81

## Files

- `optimize_s82_with_s66.py`
- `optimize_s82_with_s65.py`
- `optimize_s65_fake_trap.py`
- `s82_with_s66_search.csv`
- `s82_with_s65_search.csv`
- `s82_with_s65_fine_low.csv`
- `create_s82.md`
