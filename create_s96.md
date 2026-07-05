# S96 Champion - Inverse S84 RD 1.3-2.0 Midday Overlay

สถานะ: research/backtest-only, ยังไม่ wire เข้า live bot

## Baseline

Champion ล่าสุดก่อนหน้า:

```text
S95 = S94 + INV_S84_M15_OLDWICK_FOLLOW_RD1.3_2.0x5.403
```

| Metric | S95 |
|---|---:|
| Avg $/day | 619.5492 |
| Min $/day | 599.7833 |
| Min PF | 5.32770 |
| Max losing-day streak | 3 |
| Worst day | -999.90644 |
| Max lot | 0.19 |
| Max leg DD | 55.01% |
| Skipped by circuit breaker | 10391 |

## New Leg

Winning overlay:

```text
INV_S84_M15_lb48_rw0.25_wb0.8_eat0.06_fail0.03_op1_mb0.06_mr0.35_rr_follow_sl0.2_rr0.9_Frdmin1.3_rd2_hfrom10_hbefore13
```

Meaning:

- Base generator: S84 old-wick follow
- Mode: inverse raw
- TF: M15
- Lookback: 48
- Old wick min: 0.25 ATR
- Wick/body min: 0.8
- Eat tolerance: 0.06 ATR
- Close-fail threshold: 0.03 ATR
- Require opposite close: on
- Min body: 0.06 ATR
- Min range: 0.35 ATR
- Target mode: RR
- SL buffer: 0.2 ATR
- RR: 0.9
- Post-filter: `1.3 <= risk_distance <= 2.0`
- Time filter: `10 <= fill_hour < 13` BKK

## New Champion

```text
S96 = S95 + INV_S84_M15_OLDWICK_FOLLOW_RD1.3_2.0_H10_13x6.628
```

| Metric | S96 |
|---|---:|
| Avg $/day | 622.0345 |
| Min $/day | 602.8985 |
| Min PF | 5.38154 |
| Max losing-day streak | 3 |
| Worst day | -999.90826 |
| Max lot | 0.19 |
| Max leg DD | 55.01% |
| Skipped by circuit breaker | 10391 |

Per-window exact from `s96_s84_inv_rdmin13_rd20_h10_13_daily.csv`:

| Window | $/day | PF | Streak | Worst day | Raw trades |
|---:|---:|---:|---:|---:|---:|
| 90 | 602.8985 | 5.38154 | 3 | -978.3384 | 18 |
| 120 | 659.4686 | 5.87678 | 3 | -976.22864 | 21 |
| 150 | 622.2400 | 5.75263 | 3 | -986.25864 | 29 |
| 180 | 603.5307 | 5.40208 | 3 | -999.90826 | 36 |

## Weight Threshold

`s96_s84_inv_rdmin13_rd20_h10_13_target28_ultrafine.csv`:

| Weight | Result |
|---:|---|
| 6.628 | highest 0.001-step weight that passes `-999.91` |
| 6.629 | fails `-999.91` |
| 6.646 | passes only `-1000`, fails `-999.91` |

## No-Blow Guard

| Floor | Result |
|---|---|
| -700 | fail because the champion ladder already has near -1000 days |
| -900 | fail because the champion ladder already has near -1000 days |
| -973.16 | fail because the champion ladder already has near -1000 days |
| -999.91 | pass |
| -1000 | pass |

## Evidence

- `optimize_s88_allin4s_fast.py`
- `s96_s84_inv_rdmin13_rd20_h10_13_target28_probe.csv`
- `s96_s84_inv_rdmin13_rd20_h10_13_target28_ultrafine.csv`
- `s96_s84_inv_rdmin13_rd20_h10_13_target28_ultrafine_worst_day.csv`
- `s96_s84_inv_rdmin13_rd20_h10_13_daily.csv`

## Look-Ahead Bias Audit

- Research/backtest-only; no live bot wiring.
- S96 uses `s95_s84_inv_rdmin13_rd20_daily.csv` as the base, so it is compared
  against the current champion S95.
- The new leg still uses `simulate_equity_substream(raw, cfg, START_EQUITY=1000)`
  for per-leg sizing.
- S84 detection uses closed bar `j`.
- Fill is simulated from `j+1` via the existing `sim_s84_backtest.run_single`
  replay.
- Inverse mode swaps signal/TP/SL on the same raw event and negates
  `diff_usd_per_001lot`.
- `risk_distance` is entry/SL distance known at signal construction time.
- `10 <= fill_hour < 13` uses the simulated fill timestamp available at entry,
  not any post-entry outcome.
- No future candle, same-bar close fill, or result filter is used.

## Verdict

Found new champion:

```text
S96 = S95 + INV_S84_M15_OLDWICK_FOLLOW_RD1.3_2.0_H10_13x6.628
```

This improves both avg $/day and min $/day while keeping max losing-day streak
at 3 and passing the `-999.91` / `-1000` floors. Continue with S97 search using
S96 as the new baseline.
