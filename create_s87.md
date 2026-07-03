# S87 Attempt - D1/H12 Closed-Bar Bias Filter

สถานะ: research/backtest-only, ยังไม่ wire เข้า live bot

## Baseline

Champion ก่อนรอบนี้:

```text
S81 = P16 + S63x12.8 + S69x22.1925 + S64x13.875
```

| Metric | S81 |
|---|---:|
| Avg $/day | 339.82 |
| Min $/day | 313.60 |
| Min PF | 4.37 |
| Max streak | 3 |
| Worst day | -999.91 |
| Max lot | 0.19 |
| Max leg DD | 55.01% |
| Skipped by circuit breaker | 9727 |

## Idea

S87 ใช้ higher-timeframe closed bars เป็น directional filter ให้ S86 M15 strict:

- D1/H12 ใช้แท่งที่ปิดแล้วเท่านั้น
- case หลักที่เจอ edge: `D1_H12_TURN_follow`
- logic: D1 แดง + H12 ก่อนหน้าแดง + H12 ล่าสุดเขียว => BUY; D1 เขียว + H12 ก่อนหน้าเขียว + H12 ล่าสุดแดง => SELL
- filter raw S86 แล้วค่อย simulate ด้วย `simulate_equity_substream(raw, cfg, START_EQUITY=1000)`

## Files

- `strategy87.py`
- `sim_s87_filter_s86.py`
- `optimize_s87_overlay_s81.py`
- `s87_filter_s86_summary.csv`
- `s87_overlay_s81_search.csv`
- `s87_overlay_s81_fine.csv`

## S87 Standalone Scout Over S86

S86 raw M15 strict:

| Metric | S86 raw |
|---|---:|
| Avg $/day | 2.67 |
| Min $/day | 1.75 |
| Min PF | 1.35 |
| Fixed losing-day streak | 6 |
| Compound max loss streak | 5 |
| Max lot | 0.02 |
| Max DD | 21.76% |

Best robust filter:

```text
S87_D1_H12_TURN_follow
```

| Window | Trades | Comp $/day | PF | Comp loss streak | Fixed $/day | Fixed PF | Fixed streak | DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 90 | 12 | 0.89 | 1.68 | 3 | 0.89 | 1.682 | 3 | 5.09% |
| 120 | 17 | 1.95 | 2.67 | 3 | 1.95 | 2.666 | 3 | 4.48% |
| 150 | 23 | 1.53 | 2.23 | 3 | 1.53 | 2.227 | 3 | 4.50% |
| 180 | 25 | 0.95 | 1.70 | 3 | 0.95 | 1.701 | 3 | 6.23% |

Standalone ยังเล็กมาก แต่ streak สะอาดกว่า S86 raw และเหมาะเป็น overlay.

## New Champion Candidate

Fine search:

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

Per-window:

| Window | $/day | PF | Streak | Worst day |
|---:|---:|---:|---:|---:|
| 90 | 372.89 | 4.106 | 3 | -965.96 |
| 120 | 431.59 | 4.628 | 3 | -937.32 |
| 150 | 364.83 | 4.196 | 3 | -998.76 |
| 180 | 368.35 | 4.055 | 3 | -999.91 |

ผ่านกติกาเทียบ S81:

- Avg $/day ชนะ S81: 384.42 > 339.82
- Min $/day ชนะ S81: 364.83 > 313.60
- Max streak ยัง 3
- Worst day ยังไม่หลุด floor -1000
- ใช้ sizing/balance framework เดียวกับ P13/P16/S75/S76/S77/S81

## No-Blow Guard

| Floor | Result |
|---|---|
| -700 | fail เพราะ S81 baseline เองมี worst day -999.91 |
| -900 | fail เพราะ S81 baseline เองมี worst day -999.91 |
| -973.16 | fail เพราะ S81 baseline เองมี worst day -999.91 |
| -1000 | pass ที่ S87x33.55 |

หมายเหตุ: รอบนี้จึงเป็น champion ภายใต้ floor หลัก -1000 ตาม S81 ไม่ใช่ conservative champion ภายใต้ -973.16.

## Look-Ahead Bias Audit

- `strategy87.build_closed_series()` index HTF ด้วย `bar_open_time + timeframe_seconds`
- `strategy87.bias_at()` ใช้ `bisect_right(close_times, trade_time) - 1`
- filter ใช้ `fill_time_ts` ของ trade และเห็นเฉพาะ D1/H12 ที่ปิดก่อนหรือเท่ากับเวลา fill
- S86 raw ใช้ closed bar `j` และ fill ที่ `j + 1`
- portfolio overlay ใช้ raw trade replay แล้ว reweight daily PnL เท่านั้น
- ไม่มีการ wire เข้า `scanner.py`, `trailing.py`, `main.py`

## Verdict

พบ champion ใหม่:

```text
S82 = P16 + S63x12.8 + S69x22.1925 + S64x13.875 + S87x33.55
```

Champion ล่าสุดจึงขยับจาก S81 เป็น S82 ภายใต้ floor -1000.

ทางต่อ: ต้องหา S83 ต่อทันที เพราะยังห่างเป้าหมาย $1000/day มาก และ S87 น้ำหนักชนขอบ floor แล้ว ต้องหา overlay/generator ใหม่หรือ filter เสริมที่ไม่เพิ่ม worst-day.
