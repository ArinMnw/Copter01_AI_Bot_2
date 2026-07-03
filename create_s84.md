# S84 Champion - S88/S89 Risk20 Rebalanced Overlay

สถานะ: research/backtest-only, ยังไม่ wire เข้า live bot

## Baseline

Champion ก่อนรอบนี้:

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

## Idea

S83 ยังติด no-blow floor ใกล้ -1000 โดยเฉพาะ weak day:

- 2026-03-09: S88 loss
- 2025-12-18: S87_MAIN loss
- 2025-10-14: baseline/demo all-in loss

แทนที่จะเพิ่ม S88 ตรง ๆ จึง rebalance ด้วย S89 ซึ่งเป็น safer subset ของ S88:

```text
S89_D1_INV_NO17_RISK20 = S87(D1_LAST_inverse)
    + exclude fill hour 17 BKK
    + risk_distance <= 20
```

filter นี้ใช้เฉพาะข้อมูลที่รู้ ณ เวลา entry:

- fill hour จาก `fill_time_ts`
- `risk_distance` จาก entry/SL ของ signal

## Files

- `optimize_s84_s89_mix.py`
- `s84_s89_mix_risk20.csv`
- `s84_s89_mix_risk20_worst_day.csv`
- `s84_s89_mix_risk20_daily.csv`
- `s84_s89_mix_risk20_fine.csv`
- `s84_s89_mix_risk20_fine_worst_day.csv`
- `s84_s89_mix_risk20_fine_daily.csv`
- `s84_s89_mix_ratr18.csv`
- `s84_s89_mix_ratr18_worst_day.csv`
- `s84_s89_mix_ratr20.csv`
- `s84_s89_mix_ratr20_worst_day.csv`

## Search

Coarse:

```text
python optimize_s84_s89_mix.py --base S82 --leg-a S88_D1_INV_NO17 --leg-b S89_D1_INV_NO17_RISK20 --wa 6:14.5:0.25 --wb 0:50:0.25 --out s84_s89_mix_risk20.csv --audit-out s84_s89_mix_risk20_worst_day.csv --daily-out s84_s89_mix_risk20_daily.csv
```

Fine:

```text
python optimize_s84_s89_mix.py --base S82 --leg-a S88_D1_INV_NO17 --leg-b S89_D1_INV_NO17_RISK20 --wa 13.5:14.45:0.01 --wb 8:12:0.01 --out s84_s89_mix_risk20_fine.csv --audit-out s84_s89_mix_risk20_fine_worst_day.csv --daily-out s84_s89_mix_risk20_fine_daily.csv --top 300
```

Checked alternatives:

```text
S89_D1_INV_NO17_RATR18
S89_D1_INV_NO17_RATR20
```

RATR18 did not beat S83 on min $/day. RATR20 beat S83 but underperformed RISK20.

## New Champion

```text
S84 = S82 + S88_D1_INV_NO17x14.43 + S89_D1_INV_NO17_RISK20x10
```

Full formula:

```text
S84 = P16
    + S63x12.8
    + S69x22.1925
    + S64x13.875
    + S87(D1_H12_TURN_follow)x33.55
    + S88(D1_LAST_inverse_no17)x14.43
    + S89(D1_LAST_inverse_no17_risk20)x10
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
| Skipped by circuit breaker | 9764 |

Per-window:

| Window | $/day | PF | Streak | Worst day |
|---:|---:|---:|---:|---:|
| 90 | 451.51 | 4.49 | 3 | -984.09 |
| 120 | 488.53 | 4.68 | 3 | -984.09 |
| 150 | 414.71 | 4.30 | 3 | -998.76 |
| 180 | 413.02 | 4.20 | 3 | -999.91 |

ผ่านกติกาเทียบ S83:

- Avg $/day ชนะ S83: 441.94 > 429.68
- Min $/day ชนะ S83: 413.02 > 401.38
- Max streak ยัง 3
- Worst day ยังไม่หลุด floor -1000
- ใช้ sizing/balance framework เดียวกับ P13/P16/S75/S76/S77/S81/S82/S83

## No-Blow Guard

| Floor | Result |
|---|---|
| -700 | fail เพราะ baseline/champion ladder ยังมี worst day ใกล้ -1000 |
| -900 | fail เพราะ baseline/champion ladder ยังมี worst day ใกล้ -1000 |
| -973.16 | fail เพราะ S84 worst day -999.91 |
| -999.91 | pass |
| -1000 | pass |

## Worst-Day Audit

`s84_s89_mix_risk20_fine_worst_day.csv`:

| Window | Worst date | Total | Main source |
|---:|---|---:|---|
| 90 | 2026-03-09 | -984.09 | S88_D1_INV_NO17 loss |
| 120 | 2026-03-09 | -984.09 | S88_D1_INV_NO17 loss |
| 150 | 2025-12-18 | -998.76 | S87_MAIN loss |
| 180 | 2025-10-14 | -999.91 | demo/all-in baseline |

S84 ยังถูกจำกัดด้วย no-blow floor เดิม การเพิ่ม S88/S89 ต่อแบบตรง ๆ จะมีโอกาสชน -1000 เร็วมาก

## Look-Ahead Bias Audit

- S84 reuse S87/S88 framework ที่ใช้ HTF closed bars เท่านั้น:
  - `bar_open_time + timeframe_seconds <= fill_time_ts`
  - `bisect_right(close_times, fill_time_ts) - 1`
- S89 filter ใช้เฉพาะ known-at-entry:
  - BKK fill hour จาก `fill_time_ts`
  - `risk_distance` จาก signal entry/SL
- ไม่มีการใช้ผลลัพธ์ trade, future OHLC, future daily PnL หรือ hardcode วันที่
- Portfolio runner ใช้ raw trade replay แล้วค่อย `simulate_equity_substream(raw, cfg, START_EQUITY=1000)` ต่อ leg
- รวม portfolio ด้วย daily PnL weighted sum เหมือน P13/P16/S75/S76/S77/S81/S82/S83
- No live bot wiring

## Verdict

พบ champion ใหม่:

```text
S84 = S82 + S88_D1_INV_NO17x14.43 + S89_D1_INV_NO17_RISK20x10
```

Champion ล่าสุดจึงขยับจาก S83 เป็น S84 ภายใต้ floor -1000

ทางต่อ: ต้องหา S85 ต่อ เพราะยังห่างเป้าหมาย $1000/day มาก และ S84 ยังชน floor เก่าที่ -999.91 อยู่
