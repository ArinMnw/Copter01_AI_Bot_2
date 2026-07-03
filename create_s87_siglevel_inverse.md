# S87 Micro Champion - Inverse Significant Level M30 Above S86

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

## Idea

S20.10 remaining legs did not improve S86, so the next tested search space was Significant Level Rejection from All-in-4S:

- old H/L breaks
- pivot high/low levels
- first rejection wick / significant candle
- doji or important candle levels

The direct significant-level leg was consistently negative against S86 in the sampled configs, so an inverse replay was tested:

```text
S87 = inverse of S85SIG_M30 significant-level rejection
```

This is interpreted as: when the significant-level rejection setup fires, test the opposite side using symmetric TP/SL replay.

## Files

- `optimize_s87_siglevel_fast.py`
- `s87_siglevel_fast_one.csv`
- `s87_siglevel_fast_sample_m15.csv`
- `s87_siglevel_fast_sample_m30.csv`
- `s87_siglevel_fast_sample_m5_tr0.csv`
- `s87_siglevel_fast_sample_m15_tr0.csv`
- `s87_siglevel_fast_sample_m30_tr0.csv`
- `s87_siglevel_inv_sample_m5.csv`
- `s87_siglevel_inv_sample_m15.csv`
- `s87_siglevel_inv_sample_m30.csv`
- `s87_siglevel_inv_m15_fine.csv`
- `s87_siglevel_inv_m30_fine.csv`
- `s87_siglevel_inv_m30_ultrafine.csv`
- `s87_siglevel_inv_m30_ultrafine_worst_day.csv`

## Candidate

Config:

```text
S85SIG_M30_lb72_age8_t0.08_a0.04_w0.18_wb0.8_dj0_pv1_tr1_tl12_tm0.8_sl0.25_rr1
```

Meaning:

- TF: M30
- lookback: 72
- level age: 8
- touch tolerance: 0.08 ATR
- close away: 0.04 ATR
- rejection wick: 0.18 ATR
- wick/body: 0.8
- doji levels: off
- pivot levels: on
- trend-into-level: on
- trend lookback: 12
- trend min: 0.8 ATR
- SL: 0.25 ATR
- RR: 1.0
- mode: inverse raw

Raw counts:

| Window | Trades |
|---:|---:|
| 90 | 99 |
| 120 | 119 |
| 150 | 151 |
| 180 | 165 |

## New Micro Champion

Conservative pick:

```text
S87 = S86 + inverse(S85SIG_M30)x0.007
```

Rounded metrics:

| Metric | S87 |
|---|---:|
| Avg $/day | 476.87 |
| Min $/day | 444.19 |
| Min PF | 4.07 |
| Max streak | 3 |
| Worst day | -999.91 |
| Max lot | 0.19 |
| Max leg DD | 55.01% |
| Skipped by circuit breaker | 9909 |

Important note:

- The runner marks `beats_s86=True` for `x0.007` using unrounded values.
- The edge is extremely small, so `avg_day` and `min_day` still display the same after 2-decimal rounding.
- This is a valid micro-step under the exact comparator, but it is not a meaningful jump toward $1000/day.

Per-window rounded:

| Window | $/day | PF | Streak | Worst day |
|---:|---:|---:|---:|---:|
| 90 | 471.15 | 4.07 | 3 | -999.90 |
| 120 | 533.35 | 4.61 | 3 | -984.30 |
| 150 | 458.80 | 4.46 | 3 | -998.76 |
| 180 | 444.19 | 4.16 | 3 | -999.91 |

## Why x0.007, Not x0.008

`s87_siglevel_inv_m30_ultrafine.csv`:

| Weight | beats S86 | Worst day | -999.91 guard | -1000 guard |
|---:|---|---:|---|---|
| 0.007 | True | -999.91 | pass | pass |
| 0.008 | True | -999.91 rounded | fail | pass |
| 0.009 | True | -999.92 | fail | pass |
| 0.010 | True | -999.95 | fail | pass |

`x0.007` is the highest tested ultra-fine weight that keeps the stricter `-999.91` guard.

## No-Blow Guard

| Floor | Result |
|---|---|
| -700 | fail because the champion ladder already has near -1000 days |
| -900 | fail because the champion ladder already has near -1000 days |
| -973.16 | fail because S87 worst day is near -999.91 |
| -999.91 | pass |
| -1000 | pass |

## Worst-Day Audit

`s87_siglevel_inv_m30_ultrafine_worst_day.csv`:

| Window | Worst date | Total | Base | Siglevel contribution |
|---:|---|---:|---:|---:|
| 90 | 2026-05-07 | -999.90 | -999.84 | small negative |
| 120 | 2026-03-09 | -984.30 | -984.09 | small negative |
| 150 | 2025-12-18 | -998.76 | -998.76 | 0.00 |
| 180 | 2025-10-14 | -999.91 | -999.91 | 0.00 |

The inverse significant-level leg barely changes the weak-day profile, which is why the safe weight is tiny.

## Look-Ahead Bias Audit

- `optimize_s87_siglevel_fast.py` is research/backtest-only.
- Base S86 daily PnL is loaded from the verified S86 daily CSV instead of rebuilding the full portfolio.
- The new leg still uses `simulate_equity_substream(raw, cfg, START_EQUITY=1000)` for per-leg sizing.
- Significant-level detection uses completed bar `j`.
- Fill is the next bar open from `sim_s85_backtest.replay85`.
- Inverse mode swaps signal/TP/SL on the same raw event and negates the point outcome; no future filter is added.
- No live bot wiring.

## Verdict

Found a micro champion:

```text
S87 = S86 + inverse(S85SIG_M30)x0.007
```

However, the improvement is too small to materially help the $1000/day target. The practical next step should continue with a stronger new generator/filter, not more scaling of this leg.
