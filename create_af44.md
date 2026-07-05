# AF44 — Ambfix Ladder: Direct S86RUN cfg7171 All-RD H14

วันที่: 2026-07-04
สถานะ: research/backtest-only, ยังไม่ wire เข้า live bot
กติกา: ambfix resolution (ดู `create_af1.md` / `create_ambfix_audit.md`)
Config 7171: `S86RUN_M30_lb72_imp2.2_zt0.06_body0.08_ratio0.2_tr1_tl12_tm0.6_swing_rr_sl0.2_rr1.3`

## Baseline

```text
AF43 = AF42 + AMBFIX_DIR_S86RUNc7171_ALL_H22x124.801
```

| Metric | AF43 |
|---|---:|
| Avg $/day | 1846.1137 |
| Min $/day | 1768.8165 |
| Min PF | 8.77701 |
| Max streak | 3 |
| Worst day | -999.90966 |

## Search (sweep2 s86-cfg7171 บน AF43 base)

| Mode | Band | Hour | Best w | avg | min | หมายเหตุ |
|---|---|---|---:|---:|---:|---|
| direct | all | H13 | 140 | 1978.17 | 1769.04 | ❌ ปฏิเสธ — ที่ threshold เต็ม (x145.72) fail beats (min ตกใต้ base), ที่ w140 margin min เหลือ +$0.2 บนแค่ 3 ไม้ = เปราะเกิน |
| **direct** | **all** | **H14** | **125** | **1899.31** | **1799.25** | ✅ ผู้ชนะ (6 ไม้ margin ชัด) |
| direct | all | H15 | 30 | 1892.31 | 1798.19 | candidate AF45 (10 ไม้) |

## New Leg

```text
AMBFIX_DIR_S86RUNc7171_ALL_H14 — direct, ไม่กรอง RD, fill_hour == 14 BKK
```

- Raw trades: 4/5/6/6 ที่ 90/120/150/180d; ambiguity 0
- Leg stats: lot_max 0.01, DD 4.87%, skipped 0

## New Champion

```text
AF44 = AF43 + AMBFIX_DIR_S86RUNc7171_ALL_H14x125.633
```

| Metric | AF44 |
|---|---:|
| Avg $/day | 1899.5760 |
| Min $/day | 1799.3162 |
| Min PF | 8.50423 |
| Max losing-day streak | 3 |
| Worst day | -999.90966 |

| Window | $/day | PF | Streak | Worst day | Raw trades |
|---:|---:|---:|---:|---:|---:|
| 90 | 1799.3162 | 8.50423 | 3 | -999.90945 | 4 |
| 120 | 1996.8744 | 10.43896 | 3 | -999.90966 | 5 |
| 150 | 1984.8025 | 11.44888 | 3 | -999.90921 | 6 |
| 180 | 1817.3109 | 10.19781 | 3 | -999.90946 | 6 |

## Weight Threshold

`af44_ambfix_s86c7171_dir_all_h14_probe.csv`: x125.633 ผ่าน / x125.634 fail

## No-Blow Guard

-999.91 pass / -1000 pass

## Look-Ahead Bias Audit

- S86RUN detection ใช้ closed bars, fill `j+1`; filters ใช้ข้อมูล ณ ตอนเข้าไม้
- ambiguity 0 → ไม่มีการแตะ resolution; Research/backtest-only

## Verdict

```text
AF44 = AF43 + AMBFIX_DIR_S86RUNc7171_ALL_H14x125.633
```

ชนะ AF43 ทั้ง avg (1846.11 → 1899.58) และ min (1768.82 → 1799.32) — เหลือ ~$100
ถึงเป้า avg $2000
