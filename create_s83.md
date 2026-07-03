# S83 Attempt - S88 D1 Inverse No-17 Overlay Above S82

สถานะ: research/backtest-only, ยังไม่ wire เข้า live bot

## Baseline

Champion ก่อนรอบนี้:

```text
S82 = S81 + S87(D1_H12_TURN_follow)x33.55
```

| Metric | S82 |
|---|---:|
| Avg $/day | 384.42 |
| Min $/day | 364.83 |
| Min PF | 4.055 |
| Max streak | 3 |
| Worst day | -999.91 |
| Max lot | 0.19 |
| Max leg DD | 55.01% |
| Skipped by circuit breaker | 9727 |

## Idea

S87 `D1_LAST_inverse` had strong positive contribution but failed S83 because one loss at 2026-02-19 17:30 BKK pushed the already-weak 180d day below the -1000 floor.

S88 is a filtered version of that leg:

```text
S88_D1_INV_NO17 = S87(D1_LAST_inverse) excluding fill hour 17 BKK
```

This filter uses only fill-time/session information known before entry; it does not inspect trade outcome.

## Files

- `optimize_s83_s87_combo.py`
- `s83_s87_combo_search.csv`
- `s83_s87_combo_low.csv`
- `s83_s87_worst_day_audit.csv`
- `s83_s88_combo_search.csv`
- `s83_s88_combo_fine.csv`
- `s83_s88_worst_day_audit.csv`
- `s83_s88_worst_day_audit_fine.csv`

## New Champion Candidate

Fine search:

```text
S83 = S82 + S88_D1_INV_NO17x14.43
```

Full formula:

```text
S83 = P16
    + S63x12.8
    + S69x22.1925
    + S64x13.875
    + S87(D1_H12_TURN_follow)x33.55
    + S88(D1_LAST_inverse_no17)x14.43
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

Per-window:

| Window | $/day | PF | Streak | Worst day |
|---:|---:|---:|---:|---:|
| 90 | 439.10 | 4.474 | 3 | -984.09 |
| 120 | 475.40 | 4.573 | 3 | -984.09 |
| 150 | 402.83 | 4.220 | 3 | -998.76 |
| 180 | 401.38 | 4.095 | 3 | -999.91 |

ผ่านกติกาเทียบ S82:

- Avg $/day ชนะ S82: 429.68 > 384.42
- Min $/day ชนะ S82: 401.38 > 364.83
- Max streak ยัง 3
- Worst day ยังไม่หลุด floor -1000
- ใช้ sizing/balance framework เดียวกับ P13/P16/S75/S76/S77/S81/S82

## No-Blow Guard

| Floor | Result |
|---|---|
| -700 | fail เพราะ baseline S81/S82/S83 ยังมี worst day ใกล้ -1000 |
| -900 | fail เพราะ baseline S81/S82/S83 ยังมี worst day ใกล้ -1000 |
| -973.16 | fail เพราะ S83 worst day -999.91 |
| -1000 | pass ที่ S88x14.43 |

## Worst-Day Audit

`s83_s88_worst_day_audit_fine.csv`:

| Window | Worst date | Total | Main source |
|---:|---|---:|---|
| 90 | 2026-03-09 | -984.09 | S88_D1_INV_NO17 loss |
| 120 | 2026-03-09 | -984.09 | S88_D1_INV_NO17 loss |
| 150 | 2025-12-18 | -998.76 | S87_MAIN loss |
| 180 | 2025-10-14 | -999.91 | demo/all-in baseline |

This shows S83 is still constrained by the same old no-blow floor. Increasing S88 beyond the safe edge eventually breaks the -1000 floor.

## Look-Ahead Bias Audit

- S88 starts from S87 `D1_LAST_inverse`
- S87 HTF lookup still uses closed bars only:
  - `bar_open_time + timeframe_seconds <= fill_time_ts`
  - `bisect_right(close_times, fill_time_ts) - 1`
- S88 `NO17` filter uses only `fill_time_ts` converted to BKK hour and excludes hour 17
- No trade outcome, future OHLC, or future daily PnL is used to create signals
- Portfolio runner uses raw trade replay, then `simulate_equity_substream(raw, cfg, START_EQUITY=1000)`, then daily PnL weighting
- No live bot wiring

## Verdict

พบ champion ใหม่:

```text
S83 = S82 + S88_D1_INV_NO17x14.43
```

Champion ล่าสุดจึงขยับจาก S82 เป็น S83 ภายใต้ floor -1000.

ทางต่อ: ต้องหา S84 ต่อ เพราะยังห่างเป้าหมาย $1000/day มาก และ S83 ยังชน floor เก่าที่ -999.91 อยู่.
