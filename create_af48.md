# AF48 — Ambfix Ladder: Inverse S86RUN cfg7171 All-RD H17

วันที่: 2026-07-04
สถานะ: research/backtest-only, ยังไม่ wire เข้า live bot
กติกา: ambfix resolution (ดู `create_af1.md` / `create_ambfix_audit.md`)
Config 7171: `S86RUN_M30_lb72_imp2.2_zt0.06_body0.08_ratio0.2_tr1_tl12_tm0.6_swing_rr_sl0.2_rr1.3`

## Baseline

```text
AF47 = AF46 + AMBFIX_DIR_S86RUNc7171_ALL_H13x145.720
```

| Metric | AF47 |
|---|---:|
| Avg $/day | 2120.5159 |
| Min $/day | 1913.1977 |
| Min PF | 8.92719 |
| Max streak | 3 |
| Worst day | -999.90946 |

## Search (sweep2 s86-cfg7171 บน AF47 base)

| Mode | Band | Hour | Best w | avg | min |
|---|---|---|---:|---:|---:|
| **inverse** | **all** | **H17** | **35** | **2144.92** | **1947.45** | ✅ ผู้ชนะ |
| direct | all | H10 | 15 | 2133.69 | 1929.09 | candidate AF49 |
| direct | all | H20 | 5 | 2132.12 | 1925.97 | candidate (12 ไม้) |

## New Leg

```text
AMBFIX_INV_S86RUNc7171_ALL_H17 — inverse, ไม่กรอง RD, fill_hour == 17 BKK
```

- Raw trades: 5/5/5/5 ที่ 90/120/150/180d; ambiguity 0
- Leg stats: lot_max 0.01, DD 4.89%, skipped 0

## New Champion

```text
AF48 = AF47 + AMBFIX_INV_S86RUNc7171_ALL_H17x35.801
```

| Metric | AF48 |
|---|---:|
| Avg $/day | 2145.4771 |
| Min $/day | 1948.2310 |
| Min PF | 9.14430 |
| Max losing-day streak | 3 |
| Worst day | -999.90946 |

| Window | $/day | PF | Streak | Worst day | Raw trades |
|---:|---:|---:|---:|---:|---:|
| 90 | 1948.2310 | 9.14430 | 3 | -999.90945 | 5 |
| 120 | 2340.9851 | 12.25193 | 3 | -999.90852 | 5 |
| 150 | 2254.7671 | 12.94143 | 3 | -999.90921 | 5 |
| 180 | 2037.9251 | 11.38855 | 3 | -999.90946 | 5 |

## Weight Threshold

`af48_ambfix_s86c7171_inv_all_h17_probe.csv`: x35.801 ผ่าน / x35.802 fail

## No-Blow Guard

-999.91 pass / -1000 pass

## Look-Ahead Bias Audit

- S86RUN detection ใช้ closed bars, fill `j+1`; filters ใช้ข้อมูล ณ ตอนเข้าไม้
- ambiguity 0; Research/backtest-only

## Verdict

```text
AF48 = AF47 + AMBFIX_INV_S86RUNc7171_ALL_H17x35.801
```

ชนะ AF47 ทั้ง avg (2120.52 → 2145.48) และ min (1913.20 → 1948.23) — เหลือ ~$52
ถึง milestone "min ≥ $2000"
