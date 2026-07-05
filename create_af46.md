# AF46 — Ambfix Ladder: Direct S86RUN cfg7171 All-RD H11

วันที่: 2026-07-04
สถานะ: research/backtest-only, ยังไม่ wire เข้า live bot
กติกา: ambfix resolution (ดู `create_af1.md` / `create_ambfix_audit.md`)
Config 7171: `S86RUN_M30_lb72_imp2.2_zt0.06_body0.08_ratio0.2_tr1_tl12_tm0.6_swing_rr_sl0.2_rr1.3`

## Baseline

```text
AF45 = AF44 + AMBFIX_DIR_S86RUNc7171_ALL_H15x31.539
```

| Metric | AF45 |
|---|---:|
| Avg $/day | 1948.1453 |
| Min $/day | 1848.1876 |
| Min PF | 8.83107 |
| Max streak | 3 |
| Worst day | -999.90946 |

## New Leg

```text
AMBFIX_DIR_S86RUNc7171_ALL_H11 — direct, ไม่กรอง RD, fill_hour == 11 BKK
```

- Raw trades: 6/6/7/8 ที่ 90/120/150/180d; ambiguity 0
- Leg stats: lot_max 0.01, DD 5.82%, skipped 0

## New Champion

```text
AF46 = AF45 + AMBFIX_DIR_S86RUNc7171_ALL_H11x23.755
```

| Metric | AF46 |
|---|---:|
| Avg $/day | 1983.0592 |
| Min $/day | 1867.0543 |
| Min PF | 9.38609 |
| Max losing-day streak | 3 |
| Worst day | -999.90946 |

| Window | $/day | PF | Streak | Worst day | Raw trades |
|---:|---:|---:|---:|---:|---:|
| 90 | 1930.7813 | 9.38609 | 3 | -999.90945 | 6 |
| 120 | 2084.6790 | 11.17683 | 3 | -999.90852 | 6 |
| 150 | 2049.7223 | 11.95368 | 3 | -999.90921 | 7 |
| 180 | 1867.0543 | 10.46097 | 3 | -999.90946 | 8 |

## Weight Threshold

`af46_ambfix_s86c7171_dir_all_h11_probe.csv`: x23.755 ผ่าน / x23.756 fail

## No-Blow Guard

-999.91 pass / -1000 pass

## Look-Ahead Bias Audit

- S86RUN detection ใช้ closed bars, fill `j+1`; filters ใช้ข้อมูล ณ ตอนเข้าไม้
- ambiguity 0; Research/backtest-only

## Verdict

```text
AF46 = AF45 + AMBFIX_DIR_S86RUNc7171_ALL_H11x23.755
```

ชนะ AF45 ทั้ง avg (1948.15 → 1983.06) และ min (1848.19 → 1867.05) — เหลือ ~$17
ถึงเป้า avg $2000
