# S87 Attempt - S20.10 Remaining Legs Above S86

สถานะ: research/backtest-only, ยังไม่ wire เข้า live bot

## Baseline

Champion ล่าสุด:

```text
S86 = S85 + S2010_M30_FSPx11.73
```

| Metric | S86 |
|---|---:|
| Avg $/day | 476.87 |
| Min $/day | 444.19 |
| Min PF | 4.07 |
| Max streak | 3 |
| Worst day | -999.91 |
| Max lot | 0.19 |
| Max leg DD | 55.01% |
| Skipped by circuit breaker | 9839 |

## Search 1: Other TFs

Runner:

```text
python optimize_s86_s2010_overlay.py --windows 90,120,150,180 --tfs M1,M5,M15,H1 --legs ALL,DM,SP,FSP --base-s2010-m30-fsp 11.73 --w 0:20:0.25 --out s87_from_s86_s2010_other_tf.csv --audit-out s87_from_s86_s2010_other_tf_worst_day.csv --daily-out s87_from_s86_s2010_other_tf_daily.csv --top 300
```

Tested:

- `S2010_M1_ALL/DM/SP/FSP`
- `S2010_M5_ALL/DM/SP/FSP`
- `S2010_M15_ALL/DM/SP/FSP`
- `S2010_H1_ALL/DM/SP/FSP`

Result: no S87 champion found. Top valid rows are all weight 0, which means S86 unchanged.

## Search 2: M30 Non-FSP Legs

Runner:

```text
python optimize_s86_s2010_overlay.py --windows 90,120,150,180 --tfs M30 --legs ALL,DM,SP --base-s2010-m30-fsp 11.73 --w 0:20:0.25 --out s87_from_s86_s2010_m30_other.csv --audit-out s87_from_s86_s2010_m30_other_worst_day.csv --daily-out s87_from_s86_s2010_m30_other_daily.csv --top 180
```

Tested:

- `S2010_M30_ALL`
- `S2010_M30_DM`
- `S2010_M30_SP`

Raw counts:

| Window | M30_ALL | M30_DM | M30_SP |
|---:|---:|---:|---:|
| 90 | 72 | 20 | 31 |
| 120 | 77 | 28 | 32 |
| 150 | 117 | 28 | 40 |
| 180 | 126 | 31 | 42 |

Result: no S87 champion found.

Top valid rows are weight 0. Positive weights degrade avg/min or break streak/floor:

| Candidate | Avg $/day | Min $/day | Min PF | Streak | Worst day | Verdict |
|---|---:|---:|---:|---:|---:|---|
| S86 + S2010_M30_SPx0.25 | 476.02 | 443.35 | 4.07 | 3 | -999.91 | loses avg/min |
| S86 + S2010_M30_ALLx0.25 | 476.51 | 443.92 | 4.07 | 7 | -999.90 | streak fail |
| S86 + S2010_M30_DMx0.25 | 476.39 | 443.70 | 4.07 | 4 | -999.91 | streak fail |
| S86 + S2010_M30_ALLx1.00 | 475.45 | 443.10 | 4.06 | 7 | -1009.54 | floor/streak fail |

## Look-Ahead Bias Audit

- Reused `optimize_s86_s2010_overlay.py`.
- Baseline fetch bug was fixed before the valid S87 runs:
  - when `--base-s2010-m30-fsp` is set and `M30` is not in `--tfs`, runner now still fetches M30 raw data so S86 baseline is actually present.
- S20.10 replay remains conservative limit replay from known closed/current-open information.
- Portfolio sizing remains `simulate_equity_substream(raw, cfg, START_EQUITY=1000)` per leg.
- No live bot wiring.

## Verdict

ยังไม่พบ S87 champion จาก S20.10 remaining legs ต่อจาก S86.

S20.10 family ที่ใช้ได้ตอนนี้มีเพียง:

```text
S86 = S85 + S2010_M30_FSPx11.73
```

ทางต่อ: ต้องเปลี่ยน search space เป็น generator/filter ใหม่ เช่น weak-day hedge, clear-candle filter, significant-level/old H-L break, หรือ FVG/DM/SP confluence จาก PDF อออิน4s แทนการเพิ่ม S20.10 family เดิม.
