# AF49 — Ambfix Ladder: Direct S86RUN cfg7171 All-RD H10

วันที่: 2026-07-04
สถานะ: research/backtest-only, ยังไม่ wire เข้า live bot
กติกา: ambfix resolution (ดู `create_af1.md` / `create_ambfix_audit.md`)
Config 7171: `S86RUN_M30_lb72_imp2.2_zt0.06_body0.08_ratio0.2_tr1_tl12_tm0.6_swing_rr_sl0.2_rr1.3`

## Baseline

```text
AF48 = AF47 + AMBFIX_INV_S86RUNc7171_ALL_H17x35.801
```

| Metric | AF48 |
|---|---:|
| Avg $/day | 2145.4771 |
| Min $/day | 1948.2310 |
| Min PF | 9.14430 |
| Max streak | 3 |
| Worst day | -999.90946 |

## New Leg

```text
AMBFIX_DIR_S86RUNc7171_ALL_H10 — direct, ไม่กรอง RD, fill_hour == 10 BKK
```

- Raw trades: 4/4/4/6 ที่ 90/120/150/180d; ambiguity 0
- Leg stats: lot_max 0.01, DD 4.96%, skipped 0

## New Champion

```text
AF49 = AF48 + AMBFIX_DIR_S86RUNc7171_ALL_H10x17.894
```

| Metric | AF49 |
|---|---:|
| Avg $/day | 2161.1970 |
| Min $/day | 1967.1907 |
| Min PF | 9.22356 |
| Max losing-day streak | 3 |
| Worst day | -999.90946 |

| Window | $/day | PF | Streak | Worst day | Raw trades |
|---:|---:|---:|---:|---:|---:|
| 90 | 1967.1907 | 9.22356 | 3 | -999.90945 | 4 |
| 120 | 2355.2049 | 12.06465 | 3 | -999.90852 | 4 |
| 150 | 2266.1430 | 12.74310 | 3 | -999.90921 | 4 |
| 180 | 2056.2495 | 11.25591 | 3 | -999.90946 | 6 |

## Weight Threshold

`af49_ambfix_s86c7171_dir_all_h10_probe.csv`: x17.894 ผ่าน / x17.895 fail

## No-Blow Guard

-999.91 pass / -1000 pass

## Look-Ahead Bias Audit

- S86RUN detection ใช้ closed bars, fill `j+1`; filters ใช้ข้อมูล ณ ตอนเข้าไม้
- ambiguity 0; Research/backtest-only

## Verdict

```text
AF49 = AF48 + AMBFIX_DIR_S86RUNc7171_ALL_H10x17.894
```

ชนะ AF48 ทั้ง avg (2145.48 → 2161.20) และ min (1948.23 → 1967.19) — เหลือ ~$33
ถึง milestone "min ≥ $2000"
