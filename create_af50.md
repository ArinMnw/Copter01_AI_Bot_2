# AF50 — Ambfix Ladder: Direct S86RUN cfg7171 All-RD H20

วันที่: 2026-07-04
สถานะ: research/backtest-only, ยังไม่ wire เข้า live bot
กติกา: ambfix resolution (ดู `create_af1.md` / `create_ambfix_audit.md`)
Config 7171: `S86RUN_M30_lb72_imp2.2_zt0.06_body0.08_ratio0.2_tr1_tl12_tm0.6_swing_rr_sl0.2_rr1.3`

## Baseline

```text
AF49 = AF48 + AMBFIX_DIR_S86RUNc7171_ALL_H10x17.894
```

| Metric | AF49 |
|---|---:|
| Avg $/day | 2161.1970 |
| Min $/day | 1967.1907 |
| Min PF | 9.22356 |
| Max streak | 3 |
| Worst day | -999.90946 |

## New Leg

```text
AMBFIX_DIR_S86RUNc7171_ALL_H20 — direct, ไม่กรอง RD, fill_hour == 20 BKK
```

- Raw trades: 9/12/12/12 ที่ 90/120/150/180d; ambiguity 0
- Leg stats: lot_max 0.01, DD 6.35%, skipped 0

## New Champion

```text
AF50 = AF49 + AMBFIX_DIR_S86RUNc7171_ALL_H20x7.112
```

| Metric | AF50 |
|---|---:|
| Avg $/day | 2177.7001 |
| Min $/day | 1985.3618 |
| Min PF | 9.20016 |
| Max losing-day streak | 3 |
| Worst day | -999.90946 |

| Window | $/day | PF | Streak | Worst day | Raw trades |
|---:|---:|---:|---:|---:|---:|
| 90 | 1985.3618 | 9.20016 | 3 | -999.90945 | 9 |
| 120 | 2374.5999 | 12.14828 | 3 | -999.90852 | 12 |
| 150 | 2281.6590 | 12.77167 | 3 | -999.90921 | 12 |
| 180 | 2069.1795 | 11.30905 | 3 | -999.90946 | 12 |

## Weight Threshold

`af50_ambfix_s86c7171_dir_all_h20_probe.csv`: x7.112 ผ่าน / x7.113 fail

## No-Blow Guard

-999.91 pass / -1000 pass

## Look-Ahead Bias Audit

- S86RUN detection ใช้ closed bars, fill `j+1`; filters ใช้ข้อมูล ณ ตอนเข้าไม้
- ambiguity 0; Research/backtest-only

## Verdict

```text
AF50 = AF49 + AMBFIX_DIR_S86RUNc7171_ALL_H20x7.112
```

ชนะ AF49 ทั้ง avg (2161.20 → 2177.70) และ min (1967.19 → 1985.36) — เหลือ ~$15
ถึง milestone "min ≥ $2000"
