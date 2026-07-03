# S84 Follow-up - S83 Plus Existing S87/S88 Variants

สถานะ: research/backtest-only, ยังไม่ wire เข้า live bot

## Baseline

Champion ล่าสุด:

```text
S83 = S82 + S88_D1_INV_NO17x14.43
```

| Metric | S83 |
|---|---:|
| Avg $/day | 429.68 |
| Min $/day | 401.38 |
| Min PF | 4.095 |
| Max streak | 3 |
| Worst day | -999.91 |
| Max lot | 0.19 |
| Max leg DD | 55.01% |
| Skipped by circuit breaker | 9754 |

## Search

Runner:

```text
python optimize_s83_s87_combo.py --base S83 --windows 90,120,150,180 --wadd 0:10:0.1 --out s84_from_s83_s88_combo_search.csv --audit-out s84_from_s83_worst_day_audit.csv
```

Tested adding existing S87/S88 variants above S83:

- `S87_D1_LAST_INV`
- `S87_D1_REV`
- `S87_H12_TURN`
- `S88_D1_INV_RISK10`
- `S88_D1_INV_RATR12`

## Result

No S84 champion found in this search space.

Top high-profit candidate failed no-blow:

| Candidate | Avg $/day | Min $/day | Min PF | Streak | Worst day | Verdict |
|---|---:|---:|---:|---:|---:|---|
| S83 + S87_D1_LAST_INVx10 | 463.08 | 426.32 | 3.99 | 3 | -1473.54 | fail floor |

CSV check:

```text
beats = 0
valid under floor/streak = 0
```

## Worst-Day Audit

`s84_from_s83_worst_day_audit.csv` shows S83 already has a new weak day:

| Window | Worst date | Total | Main source |
|---:|---|---:|---|
| 90 | 2026-03-09 | -984.09 | S88_D1_INV_NO17 loss |
| 120 | 2026-03-09 | -984.09 | S88_D1_INV_NO17 loss |
| 150 | 2025-12-18 | -998.76 | S87_MAIN loss |
| 180 | 2025-10-14 | -999.91 | demo/all-in baseline |

Adding `S87_D1_LAST_INV` also loses on 2026-03-09, so it breaks the -1000 floor immediately when scaled.

## Verdict

Existing S87/S88 variant space above S83 is exhausted for this first S84 attempt. The next S84 direction should be a new raw generator/filter that specifically avoids adding loss on:

- 2026-03-09
- 2025-12-18
- 2025-10-14

while still improving avg $/day and min $/day over S83.

## Look-Ahead Bias Audit

- This search reused only closed-bar S87/S88 raw trades.
- S88 filters use known-at-entry features only: fill hour, risk distance, riskATR from the signal.
- Portfolio combination uses `simulate_equity_substream(raw, cfg, START_EQUITY=1000)` per leg and daily PnL weighting.
- No live bot wiring.
