# AF43 — Ambfix Ladder: เปิด S86 family! Direct S86RUN cfg7171 All-RD H22

วันที่: 2026-07-04
สถานะ: research/backtest-only, ยังไม่ wire เข้า live bot
กติกา: ambfix resolution (ดู `create_af1.md` / `create_ambfix_audit.md`)

## ที่มา — S86 Family Screen (งานข้อ 2 ของผู้ใช้)

Screen micro grid 8,192 configs ของ **S86RUN generator** (กลไก impulse-zone-confirm
คนละแบบกับ S84 old-wick) ใต้ ambfix @180d — partial results เผย config คุณภาพสูง
กว่า s84 ทั้งหมด:

| Config | TF | n | dir_sum | dir_PF |
|---|---|---:|---:|---:|
| **7171** | **M30** | 124 | **+1343.7** | **1.66** | ✅ เลือกใช้ |
| 7187 | M30 | 86 | +1007.1 | 1.66 | คิว |
| 4227 | M30 | 122 | +1210.6 | 1.65 | คิว |

Config 7171:

```text
S86RUN_M30_lb72_imp2.2_zt0.06_body0.08_ratio0.2_tr1_tl12_tm0.6_swing_rr_sl0.2_rr1.3
```

**จุดเด่นพิเศษ: stream นี้มีแท่งกำกวม (both-touch) = 0 ไม้** — สะอาดสมบูรณ์แบบ
เหมือน P13/P16 legs; กติกา ambfix ไม่ต้องแตะอะไรเลย = ตัวเลขคือ resolution จริงแท้

## Baseline

```text
AF42 = AF41 + AMBFIX_DIR_S84c889_RD5.0_7.0_H15x32.734
```

| Metric | AF42 |
|---|---:|
| Avg $/day | 1662.1532 |
| Min $/day | 1591.9192 |
| Min PF | 8.28459 |
| Max streak | 3 |
| Worst day | -999.90966 |

## Search (sweep2 s86-cfg7171 บน AF42 base)

| Mode | Band | Hour | Best w | avg | min |
|---|---|---|---:|---:|---:|
| **direct** | **all** | **H22** | **120** | **1839.04** | **1762.71** | ✅ ผู้ชนะ |
| direct | all | H15 | 30 | 1708.35 | 1639.54 | candidate AF44 |
| direct | all | H11 | 20 | 1691.55 | 1626.06 | candidate |

## New Leg

```text
AMBFIX_DIR_S86RUNc7171_ALL_H22 — direct, ไม่กรอง RD, fill_hour == 22 BKK
```

- Raw trades: 4/7/8/8 ที่ 90/120/150/180d
- Leg stats: lot_max 0.01, DD 5.08%, skipped 0; ambiguity 0

## New Champion

```text
AF43 = AF42 + AMBFIX_DIR_S86RUNc7171_ALL_H22x124.801
```

| Metric | AF43 |
|---|---:|
| Avg $/day | 1846.1137 |
| Min $/day | 1768.8165 |
| Min PF | 8.77701 |
| Max losing-day streak | 3 |
| Worst day | -999.90966 |

| Window | $/day | PF | Streak | Worst day | Raw trades |
|---:|---:|---:|---:|---:|---:|
| 90 | 1785.9293 | 8.77701 | 3 | -999.90945 | 4 |
| 120 | 1903.0998 | 10.32095 | 3 | -999.90966 | 7 |
| 150 | 1926.6093 | 11.48493 | 3 | -999.90921 | 8 |
| 180 | 1768.8165 | 10.21134 | 3 | -999.90946 | 8 |

## Weight Threshold

`af43_ambfix_s86c7171_dir_all_h22_probe.csv`: x124.801 ผ่าน / x124.802 fail

## No-Blow Guard

-999.91 pass / -1000 pass

## Look-Ahead Bias Audit

- S86RUN detection ใช้ closed bars, fill `j+1` (โครงเดียวกับ S84 replay)
- Filters ใช้ข้อมูล ณ ตอนเข้าไม้; ambiguity = 0 → ไม่มีการแตะ resolution เลย
- Research/backtest-only

## Verdict

```text
AF43 = AF42 + AMBFIX_DIR_S86RUNc7171_ALL_H22x124.801
```

ชนะ AF42 ทั้ง avg (1662.15 → 1846.11) และ min (1591.92 → 1768.82) — ก้าวกระโดด
ใหญ่สุดของ AF ladder (+$184) จาก generator family ใหม่ เหลือ ~$154 ถึงเป้า $2000
