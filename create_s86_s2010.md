# S86 Champion - S20.10 M30 Fakeout_SP Overlay Above S85

สถานะ: research/backtest-only, ยังไม่ wire เข้า live bot

## Baseline

Champion ก่อนรอบนี้:

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

## Idea

S20.8 M5/M15/M30 did not produce an S86 champion above S85, so the next All-in-4S generator tested was S20.10:

- DM/SP trap
- wick purge / reversal trap
- Fakeout_SP sniper entry
- psychological price adjustment from the existing S20.10 implementation

The useful sub-leg was:

```text
S2010_M30_FSP = S20.10.Fakeout_SP on M30
```

## Files

- `optimize_s86_s2010_overlay.py`
- `s86_s2010_overlay_search.csv`
- `s86_s2010_overlay_worst_day.csv`
- `s86_s2010_m30_fsp_fine.csv`
- `s86_s2010_m30_fsp_fine_worst_day.csv`
- `s86_s2010_m30_fsp_fine_daily.csv`

## Search

Broad scout:

```text
python optimize_s86_s2010_overlay.py --windows 90,120,150,180 --tfs M1,M5,M15,M30,H1 --legs ALL,DM,SP,FSP --w 0:20:0.25 --out s86_s2010_overlay_search.csv --audit-out s86_s2010_overlay_worst_day.csv --daily-out s86_s2010_overlay_daily.csv --top 300
```

Fine search:

```text
python optimize_s86_s2010_overlay.py --windows 90,120,150,180 --tfs M30 --legs FSP --w 10.5:12.5:0.01 --out s86_s2010_m30_fsp_fine.csv --audit-out s86_s2010_m30_fsp_fine_worst_day.csv --daily-out s86_s2010_m30_fsp_fine_daily.csv --top 220
```

Raw counts for the champion leg:

| Window | S2010_M30_FSP |
|---:|---:|
| 90 | 11 |
| 120 | 27 |
| 150 | 39 |
| 180 | 43 |

## New Champion

Conservative pick:

```text
S86 = S85 + S2010_M30_FSPx11.73
```

Full formula:

```text
S86 = P16
    + S63x12.8
    + S69x22.1925
    + S64x13.875
    + S87(D1_H12_TURN_follow)x33.55
    + S88(D1_LAST_inverse_no17)x14.43
    + S89(D1_LAST_inverse_no17_risk20)x10
    + S208(Small2L2H_M1_strict_fill)x39.33
    + S2010(S20.10_Fakeout_SP_M30)x11.73
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

Per-window:

| Window | $/day | PF | Streak | Worst day |
|---:|---:|---:|---:|---:|
| 90 | 471.15 | 4.070 | 3 | -999.84 |
| 120 | 533.34 | 4.606 | 3 | -984.09 |
| 150 | 458.80 | 4.463 | 3 | -998.76 |
| 180 | 444.19 | 4.164 | 3 | -999.91 |

ผ่านกติกาเทียบ S85:

- Avg $/day ชนะ S85: 476.87 > 450.75
- Min $/day ชนะ S85: 444.19 > 419.20
- Max streak ยัง 3
- Worst day ยังไม่หลุด floor -1000
- ใช้ sizing/balance framework เดียวกับ P13/P16/S75/S76/S77/S81/S82/S83/S84/S85

## Why x11.73, Not x11.74

Fine search shows `x11.74` already breaks the floor:

| Weight | Avg $/day | Min $/day | Worst day | -999.91 guard | -1000 guard |
|---:|---:|---:|---:|---|---|
| 11.73 | 476.87 | 444.19 | -999.91 | pass | pass |
| 11.74 | 476.89 | 444.21 | -1000.20 | fail | fail |
| 11.75 | 476.91 | 444.23 | -1000.50 | fail | fail |
| 12.50 | 478.58 | 445.83 | -1022.97 | fail | fail |

S86 uses `x11.73` because it is the highest tested fine-grid weight that still respects the conservative no-blow guard.

## No-Blow Guard

| Floor | Result |
|---|---|
| -700 | fail เพราะ champion ladder ยังมี worst day ใกล้ -1000 |
| -900 | fail เพราะ champion ladder ยังมี worst day ใกล้ -1000 |
| -973.16 | fail เพราะ S86 worst day -999.91 |
| -999.91 | pass |
| -1000 | pass |

## Worst-Day Audit

`s86_s2010_m30_fsp_fine_worst_day.csv`:

| Window | Worst date | Total | S208_M1 | S2010_M30_FSP | Other total |
|---:|---|---:|---:|---:|---:|
| 90 | 2026-05-07 | -999.84 | -382.29 | 0.00 | -617.55 |
| 120 | 2026-03-09 | -984.09 | 0.00 | 0.00 | -984.09 |
| 150 | 2025-12-18 | -998.76 | 0.00 | 0.00 | -998.76 |
| 180 | 2025-10-14 | -999.91 | 0.00 | 0.00 | -999.91 |

S2010_M30_FSP improves avg/min without adding loss on the existing worst days.

## Look-Ahead Bias Audit

- `optimize_s86_s2010_overlay.py` is research/backtest-only.
- S20.10 trap detection uses completed bars plus the next bar open where the strategy explicitly checks current open for `Fakeout_SP`.
- Limit order simulation starts from that known-open bar onward.
- Same-bar ambiguity is handled conservatively:
  - before fill, if price touches the TP-side before entry, the pending order is cancelled
  - after fill, SL is checked before TP on bars that touch both
- Portfolio sizing uses `simulate_equity_substream(raw, cfg, START_EQUITY=1000)` per leg.
- Combined portfolio uses daily PnL weighted sum.
- No live bot wiring.

## Verdict

พบ champion ใหม่:

```text
S86 = S85 + S2010_M30_FSPx11.73
```

Champion ล่าสุดจึงขยับจาก S85 เป็น S86 ภายใต้ floor -1000.

ทางต่อ: ต้องหา S87 ต่อ เพราะยังห่างเป้าหมาย $1000/day มาก และ S86 ยังชน no-blow floor ใกล้ -1000 อยู่.
