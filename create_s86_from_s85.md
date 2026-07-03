# S86 Attempt - S20.8 M5/M15/M30 Above S85

สถานะ: research/backtest-only, ยังไม่ wire เข้า live bot

## Baseline

Champion ล่าสุด:

```text
S85 = S84 + S208_M1x39.33
```

| Metric | S85 |
|---|---:|
| Avg $/day | 450.75 |
| Min $/day | 419.20 |
| Min PF | 4.171 |
| Max streak | 3 |
| Worst day | -999.91 |
| Max lot | 0.19 |
| Max leg DD | 55.01% |
| Skipped by circuit breaker | 9809 |

## Search

Runner:

```text
python optimize_s85_s208_overlay.py --windows 90,120,150,180 --tfs M5,M15,M30 --base-s208-m1 39.33 --w 0:20:0.25 --out s86_from_s85_s208_m5_m15_m30.csv --audit-out s86_from_s85_s208_m5_m15_m30_worst_day.csv --daily-out s86_from_s85_s208_m5_m15_m30_daily.csv --top 300
```

Tested S20.8 strict-fill overlays above S85:

- `S208_M5`
- `S208_M15`
- `S208_M30`

Raw counts:

| Window | S208_M5 | S208_M15 | S208_M30 |
|---:|---:|---:|---:|
| 90 | 14 | 8 | 1 |
| 120 | 22 | 10 | 1 |
| 150 | 27 | 17 | 2 |
| 180 | 24 | 20 | 3 |

## Result

No S86 champion found from S20.8 M5/M15/M30 above S85.

CSV audit:

```text
unique candidates = 243
valid floor/streak = 83
beats current baseline = 0
```

Top valid rows are weight 0, which means S85 unchanged. Adding M30 starts reducing avg/min immediately. M5/M15 do not produce a valid improvement over S85 in the written top set.

Top valid rows:

| Candidate | Avg $/day | Min $/day | Min PF | Streak | Worst day |
|---|---:|---:|---:|---:|---:|
| S85 + S208_M5x0 | 450.75 | 419.20 | 4.171 | 3 | -999.91 |
| S85 + S208_M15x0 | 450.75 | 419.20 | 4.171 | 3 | -999.91 |
| S85 + S208_M30x0 | 450.75 | 419.20 | 4.171 | 3 | -999.91 |
| S85 + S208_M30x0.25 | 450.69 | 419.13 | 4.170 | 3 | -999.91 |

## No-Blow Guard

For this S86 search:

| Floor | Result |
|---|---|
| -700 | fail |
| -900 | fail |
| -973.16 | fail |
| -999.91 | only S85 / non-improving rows pass |
| -1000 | only S85 / non-improving rows pass |

## Look-Ahead Bias Audit

- Reused `optimize_s85_s208_overlay.py`, which is research/backtest-only.
- S20.8 detector sees only bars through closed bar `j`.
- Fill is forced to next bar `j+1` open.
- Exit simulation begins from the fill bar.
- Portfolio sizing uses `simulate_equity_substream(raw, cfg, START_EQUITY=1000)` per leg.
- No live bot wiring.

## Verdict

ยังไม่พบ S86 champion จาก S20.8 M5/M15/M30 ต่อจาก S85.

ทางต่อ: S20.8 family เหลือเพดาน M1 แล้ว และ TF อื่นไม่ช่วย ดังนั้นควรกลับไปสร้าง raw generator/filter ใหม่จาก PDF อออิน4s หรือสร้าง weak-day hedge/filter ที่ไม่เพิ่ม loss ใน:

- 2026-05-07
- 2026-03-09
- 2025-12-18
- 2025-10-14
