# S85 Champion - S20.8 M1 Strict-Fill Overlay Above S84

สถานะ: research/backtest-only, ยังไม่ wire เข้า live bot

## Baseline

Champion ก่อนรอบนี้:

```text
S84 = S82 + S88_D1_INV_NO17x14.43 + S89_D1_INV_NO17_RISK20x10
```

| Metric | S84 |
|---|---:|
| Avg $/day | 441.94 |
| Min $/day | 413.02 |
| Min PF | 4.20 |
| Max streak | 3 |
| Worst day | -999.91 |
| Max lot | 0.19 |
| Max leg DD | 55.01% |
| Skipped by circuit breaker | 9779 |

## Idea

Existing S87/S88/S89 overlay space above S84 was exhausted: only weight 0 passed the no-blow/streak guard.

The next raw generator tested was S20.8 Small 2L/2H Wick Rejection from the All-in-4S notes:

- liquidity sweep of recent M1 lows/highs
- wick rejection / exhaustion
- macro premium/discount context
- Bollinger pierce + RSI filter

Important correction vs the old S20.8 scout:

```text
detect from closed bar j
fill at next bar j+1 open
```

The older S20.8 scout filled at the signal bar close, which is too optimistic for portfolio champion research.

## Files

- `optimize_s85_s208_overlay.py`
- `s85_s208_overlay_m1.csv`
- `s85_s208_overlay_m1_worst_day.csv`
- `s85_s208_overlay_m1_wide.csv`
- `s85_s208_overlay_m1_wide_worst_day.csv`
- `s85_s208_overlay_m1_fine.csv`
- `s85_s208_overlay_m1_fine_worst_day.csv`
- `s85_s208_overlay_m5_m15_m30.csv`
- `s85_s208_overlay_m5_m15_m30_worst_day.csv`

## Search

Scout M5/M15/M30:

```text
python optimize_s85_s208_overlay.py --windows 90,120,150,180 --tfs M5,M15,M30 --w 0:20:0.25 --out s85_s208_overlay_m5_m15_m30.csv --audit-out s85_s208_overlay_m5_m15_m30_worst_day.csv --daily-out s85_s208_overlay_m5_m15_m30_daily.csv --top 300
```

Result: M5/M15/M30 did not improve S84. M30 degraded avg/min; M5/M15 did not appear as valid top improvements.

M1 scout:

```text
python optimize_s85_s208_overlay.py --windows 90,120,150,180 --tfs M1 --w 0:10:0.1 --out s85_s208_overlay_m1.csv --audit-out s85_s208_overlay_m1_worst_day.csv --daily-out s85_s208_overlay_m1_daily.csv --top 200
```

M1 wide:

```text
python optimize_s85_s208_overlay.py --windows 90,120,150,180 --tfs M1 --w 10:50:0.5 --out s85_s208_overlay_m1_wide.csv --audit-out s85_s208_overlay_m1_wide_worst_day.csv --daily-out s85_s208_overlay_m1_wide_daily.csv --top 250
```

M1 fine:

```text
python optimize_s85_s208_overlay.py --windows 90,120,150,180 --tfs M1 --w 38.5:39.4:0.01 --out s85_s208_overlay_m1_fine.csv --audit-out s85_s208_overlay_m1_fine_worst_day.csv --daily-out s85_s208_overlay_m1_fine_daily.csv --top 120
```

## New Champion

Conservative pick:

```text
S85 = S84 + S208_M1x39.33
```

Full formula:

```text
S85 = P16
    + S63x12.8
    + S69x22.1925
    + S64x13.875
    + S87(D1_H12_TURN_follow)x33.55
    + S88(D1_LAST_inverse_no17)x14.43
    + S89(D1_LAST_inverse_no17_risk20)x10
    + S208(Small2L2H_M1_strict_fill)x39.33
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

Per-window:

| Window | $/day | PF | Streak | Worst day |
|---:|---:|---:|---:|---:|
| 90 | 463.87 | 4.437 | 3 | -999.84 |
| 120 | 497.80 | 4.617 | 3 | -984.09 |
| 150 | 422.13 | 4.256 | 3 | -998.76 |
| 180 | 419.20 | 4.171 | 3 | -999.91 |

ผ่านกติกาเทียบ S84:

- Avg $/day ชนะ S84: 450.75 > 441.94
- Min $/day ชนะ S84: 419.20 > 413.02
- Max streak ยัง 3
- Worst day ยังไม่หลุด floor -1000
- ใช้ sizing/balance framework เดียวกับ P13/P16/S75/S76/S77/S81/S82/S83/S84

## Why x39.33, Not x39.34

`S208_M1x39.34` has slightly higher rounded avg/min but fails the stricter `-999.91` guard:

| Weight | Worst day | -999.91 guard | -1000 guard |
|---:|---:|---|---|
| 39.33 | -999.91 | pass | pass |
| 39.34 | -999.94 | fail | pass |

S85 uses `x39.33` to keep the same conservative no-blow edge as S84.

## No-Blow Guard

| Floor | Result |
|---|---|
| -700 | fail เพราะ champion ladder ยังมี worst day ใกล้ -1000 |
| -900 | fail เพราะ champion ladder ยังมี worst day ใกล้ -1000 |
| -973.16 | fail เพราะ S85 worst day -999.91 |
| -999.91 | pass |
| -1000 | pass |

## Worst-Day Audit

`s85_s208_overlay_m1_fine_worst_day.csv`:

| Window | Worst date | Total | Main source |
|---:|---|---:|---|
| 90 | 2026-05-07 | -999.84 | S87/S88 plus S208 impact |
| 120 | 2026-03-09 | -984.09 | S88_D1_INV_NO17 loss |
| 150 | 2025-12-18 | -998.76 | S87_MAIN loss |
| 180 | 2025-10-14 | -999.91 | demo/all-in baseline |

S208_M1 improves avg/min but creates a new 90d near-floor weak day, so further S208_M1 scaling is unsafe.

## Look-Ahead Bias Audit

- `optimize_s85_s208_overlay.py` is research/backtest-only.
- S20.8 detector sees only bars through closed bar `j`.
- Fill is forced to next bar `j+1` open, not signal close.
- Exit simulation begins from the fill bar after the next-open fill.
- S20.8 inputs are known at signal time:
  - recent 15-bar liquidity sweep
  - wick/body ratios
  - SMA/Bollinger/RSI from closed bars
  - macro premium/discount from visible lookback bars
- Portfolio runner uses raw trade replay, then `simulate_equity_substream(raw, cfg, START_EQUITY=1000)` per leg.
- Combined portfolio uses daily PnL weighted sum.
- No live bot wiring.

## Verdict

พบ champion ใหม่:

```text
S85 = S84 + S208_M1x39.33
```

Champion ล่าสุดจึงขยับจาก S84 เป็น S85 ภายใต้ floor -1000.

ทางต่อ: ต้องหา S86 ต่อ เพราะยังห่างเป้าหมาย $1000/day มาก และ S85 ยังชน no-blow floor ใกล้ -1000 อยู่.
