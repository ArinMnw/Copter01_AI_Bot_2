# AF45 — Ambfix Ladder: Direct S86RUN cfg7171 All-RD H15

วันที่: 2026-07-04
สถานะ: research/backtest-only, ยังไม่ wire เข้า live bot
กติกา: ambfix resolution (ดู `create_af1.md` / `create_ambfix_audit.md`)
Config 7171: `S86RUN_M30_lb72_imp2.2_zt0.06_body0.08_ratio0.2_tr1_tl12_tm0.6_swing_rr_sl0.2_rr1.3`

## Baseline

```text
AF44 = AF43 + AMBFIX_DIR_S86RUNc7171_ALL_H14x125.633
```

| Metric | AF44 |
|---|---:|
| Avg $/day | 1899.5760 |
| Min $/day | 1799.3162 |
| Min PF | 8.50423 |
| Max streak | 3 |
| Worst day | -999.90966 |

## Search (sweep2 s86-cfg7171 บน AF44 base)

| Mode | Band | Hour | Best w | avg | min |
|---|---|---|---:|---:|---:|
| **direct** | **all** | **H15** | **30** | **1945.78** | **1846.68** | ✅ ผู้ชนะ (10 ไม้) |
| direct | all | H11 | 20 | 1928.97 | 1833.20 | candidate AF46 |
| direct | all | H10 | 15 | 1912.75 | 1815.21 | candidate |

## New Leg

```text
AMBFIX_DIR_S86RUNc7171_ALL_H15 — direct, ไม่กรอง RD, fill_hour == 15 BKK
```

- Raw trades: 7/8/10/10 ที่ 90/120/150/180d; ambiguity 0
- Leg stats: lot_max 0.01, DD 6.91%, skipped 0

## New Champion

```text
AF45 = AF44 + AMBFIX_DIR_S86RUNc7171_ALL_H15x31.539
```

| Metric | AF45 |
|---|---:|
| Avg $/day | 1948.1453 |
| Min $/day | 1848.1876 |
| Min PF | 8.83107 |
| Max losing-day streak | 3 |
| Worst day | -999.90946 |

| Window | $/day | PF | Streak | Worst day | Raw trades |
|---:|---:|---:|---:|---:|---:|
| 90 | 1877.6836 | 8.83107 | 3 | -999.90945 | 7 |
| 120 | 2044.8557 | 10.66577 | 3 | -999.90852 | 8 |
| 150 | 2021.8545 | 11.67689 | 3 | -999.90921 | 10 |
| 180 | 1848.1876 | 10.41386 | 3 | -999.90946 | 10 |

## Weight Threshold

`af45_ambfix_s86c7171_dir_all_h15_probe.csv`: x31.539 ผ่าน / x31.540 fail

## No-Blow Guard

-999.91 pass / -1000 pass

## Look-Ahead Bias Audit

- S86RUN detection ใช้ closed bars, fill `j+1`; filters ใช้ข้อมูล ณ ตอนเข้าไม้
- ambiguity 0; Research/backtest-only

## Verdict

```text
AF45 = AF44 + AMBFIX_DIR_S86RUNc7171_ALL_H15x31.539
```

ชนะ AF44 ทั้ง avg (1899.58 → 1948.15) และ min (1799.32 → 1848.19) — เหลือ ~$52
ถึงเป้า avg $2000
