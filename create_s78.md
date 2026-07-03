# S78-S81 Ladder - Reweight Ceiling After S77

สถานะ: research/backtest-only, ยังไม่ wire เข้า live bot

## เป้าหมาย

ต่อยอดจาก S77 และหา champion ใหม่ไปเรื่อย ๆ จนถึง $1000/day โดยยังใช้สูตร sizing เดียวกับ P13/P16/S75/S76/S77:

```text
simulate_equity_substream(raw, cfg, START_EQUITY=1000)
-> daily_series_from_trades()
-> sum daily PnL across weighted legs
```

รอบนี้ทดสอบเฉพาะ reweight raw trades เดิมที่มีใน cache:

- P16 base
- S63
- S69
- S64

## Baseline Reproduction

| Portfolio | Avg $/day | Min $/day | Min PF | Max streak | Worst day |
|---|---:|---:|---:|---:|---:|
| S75 = P16 + S63x8 + S69x24 + S64x8 | 333.60 | 312.10 | 4.77 | 3 | -919.26 |
| S76 = P16 + S63x10 + S69x24 + S64x12 | 337.07 | 312.60 | 4.54 | 3 | -973.16 |
| S77 = P16 + S63x11.75 + S69x22.25 + S64x13.25 | 338.35 | 312.82 | 4.43 | 3 | -973.16 |

## S78

```text
S78 = P16 + S63x12.5 + S69x22.25 + S64x13.75
```

| Window | $/day | PF | Streak | Worst day |
|---|---:|---:|---:|---:|
| 90d | 342.49 | 4.79 | 3 | -958.76 |
| 120d | 365.78 | 4.63 | 3 | -931.81 |
| 150d | 313.38 | 4.38 | 3 | -931.24 |
| 180d | 336.10 | 4.38 | 3 | -994.18 |

Summary:

- Avg $/day = 339.44
- Min $/day = 313.38
- Min PF = 4.38
- Max losing-day streak = 3
- Worst day = -994.18
- Max lot = 0.19
- Max leg DD = 55.01%

## S79

```text
S79 = P16 + S63x12.625 + S69x22.25 + S64x13.875
```

Summary:

- Avg $/day = 339.63
- Min $/day = 313.46
- Min PF = 4.37
- Max losing-day streak = 3
- Worst day = -999.69

## S80

```text
S80 = P16 + S63x12.6875 + S69x22.25 + S64x13.875
```

Summary:

- Avg $/day = 339.71
- Min $/day = 313.52
- Min PF = 4.37
- Max losing-day streak = 3
- Worst day = -999.69

## S81

ตัวที่ดีที่สุดในรอบ micro-fine ก่อนชน floor -1000:

```text
S81 = P16 + S63x12.8 + S69x22.1925 + S64x13.875
```

| Window | $/day | PF | Streak | Worst day |
|---|---:|---:|---:|---:|
| 90d | 343.02 | 4.78 | 3 | -965.96 |
| 120d | 366.24 | 4.61 | 3 | -937.32 |
| 150d | 313.60 | 4.37 | 3 | -936.75 |
| 180d | 336.41 | 4.37 | 3 | -999.91 |

Summary:

- Avg $/day = 339.82
- Min $/day = 313.60
- Min PF = 4.37
- Max losing-day streak = 3
- Worst day = -999.91
- Max lot = 0.19
- Max leg DD = 55.01%

## S82 Attempt

ต่อจาก S81 ได้กวาด ridge เพิ่ม:

```text
S63 12.75 -> 14.00 step 0.025
S69 21.00 -> 22.25 step 0.025
S64 13.50 -> 14.10 step 0.05
floor = -1000
max losing-day streak <= 3
```

ผล: ไม่พบ candidate ที่ชนะ S81

Top valid candidate ในรอบ S82 ได้เพียง:

```text
P16 + S63x12.775 + S69x22.2 + S64x13.85
```

- Avg $/day = 339.79
- Min $/day = 313.59
- Worst day = -999.44

จึงถือว่า reweight space ของ S63/S69/S64 ภายใต้ floor -1000 ชนเพดานแถว S81 แล้ว

## Comparison

| Metric | S77 | S78 | S79 | S80 | S81 |
|---|---:|---:|---:|---:|---:|
| Avg $/day | 338.35 | 339.44 | 339.63 | 339.71 | 339.82 |
| Min $/day | 312.82 | 313.38 | 313.46 | 313.52 | 313.60 |
| Min PF | 4.43 | 4.38 | 4.37 | 4.37 | 4.37 |
| Max streak | 3 | 3 | 3 | 3 | 3 |
| Worst day | -973.16 | -994.18 | -999.69 | -999.69 | -999.91 |

## Look-Ahead Bias Audit

ตรวจระดับ framework แล้ว:

- ใช้ raw trades/cache เดียวกับ S75/S76/S77
- ใช้ sizing helper เดียวกันทุก leg
- Search runner ไม่สร้าง signal ใหม่จาก future OHLC; ทำเฉพาะ reweight daily PnL ของ raw trades ที่ simulate ไว้แล้ว
- P16/S63/S64/S69 ยังอยู่ภายใต้ข้อจำกัด audit เดิมจาก S77

ข้อจำกัด:

- ยังไม่ได้ forensic audit รายไฟล์ของทุก P16 leg ทีละบรรทัด
- ยังไม่ได้สร้าง raw-trade generator ใหม่จาก PDF อออิน4s
- ยังไม่ใช่ live execution simulation

## Verdict

S81 คือ champion ล่าสุดใน reweight space เดิม:

- ชนะ S77/S78/S79/S80 ใน avg $/day และ min $/day
- max losing-day streak ยังเท่า 3
- worst day ชิด no-blow floor -1000 มากแล้ว
- ยังไกลจากเป้าหมาย $1000/day มาก

เพื่อไปต่อสู่ $1000/day ต้องเพิ่ม raw-trade overlay/generator ใหม่จากเทคนิค PDF อออิน4s หรือ source ใหม่ ไม่ใช่แค่เพิ่มน้ำหนัก S63/S64/S69

## Next Generator Direction

จาก `allin4s_pdf_reading_notes.md` direction ที่ควรแตกต่อ:

- S65 Fake Reversal Trap: โครงสร้างหลอกกลับตัว 2L/2H หรือ fake move ที่ fail แล้วเข้าในทิศ H-L เดิม
- S66 FVG Ladder Follow Trend: เทรนด์ที่มี FVG หลายชั้น, latest FVG fail แล้วรอ base/lower FVG รับแรงก่อนกลับเข้า trend

สองตัวนี้ควรสร้าง raw trade generator ใหม่แล้วนำเข้า cache/portfolio search แทนการ reweight S63/S64/S69 เพิ่ม เพราะ S81 ชน floor -1000 แล้ว

## Files

- `optimize_s78_ladder_search.py`
- `s78_ladder_search.csv`
- `s78_ladder_search_wide.csv`
- `s79_ladder_search.csv`
- `s80_ladder_search.csv`
- `s81_ladder_search.csv`
- `s82_ladder_search.csv`
- `create_s78.md`
