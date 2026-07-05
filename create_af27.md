# AF27 — Ambfix Ladder: Inverse S84 cfg4369 RD 5.0-7.0 H11 (เปิด config ที่ 3)

วันที่: 2026-07-04
สถานะ: research/backtest-only, ยังไม่ wire เข้า live bot
กติกา: ambfix resolution (ดู `create_af1.md` / `create_ambfix_audit.md`)
Config 4369: `S84_M30_lb48_rw0.25_wb0.8_eat0.12_fail0.03_op1_mb0.06_mr0.35_mid_revisit_sl0.2_rr1.2`
(screen: dir PF 1.13, n=1014; stream ambiguity 13 ไม้)

## Baseline

```text
AF26 = AF25 + AMBFIX_DIR_S84c5505_RD5.0_7.0_H14x114.571
```

| Metric | AF26 |
|---|---:|
| Avg $/day | 1061.4651 |
| Min $/day | 1039.8614 |
| Min PF | 6.57251 |
| Max streak | 3 |
| Worst day | -999.90965 |

## Search (sweep2 cfg4369 บน AF26 base — ข้าม degenerate 1-ไม้ชน cap)

| Mode | Band | Hour | Best w | avg | min |
|---|---|---|---:|---:|---:|
| **inverse** | **5.0-7.0** | **H11** | **414** | **1133.81** | **1103.71** | ✅ ผู้ชนะ |
| inverse | 5.0-7.0 | H16 | 442 | 1120.43 | 1093.26 | candidate AF28 |
| inverse | 5.0-7.0 | H22 | 222 | 1076.46 | 1045.19 | candidate |

## New Leg

```text
AMBFIX_INV_S84c4369_RD5.0_7.0_H11 — inverse, `5.0 <= risk_distance <= 7.0`, fill_hour == 11 BKK
```

- Raw trades: 3/4/4/7 ที่ 90/120/150/180d
- Leg stats: lot_max 0.01, DD 0.67%, skipped 0

## New Champion

```text
AF27 = AF26 + AMBFIX_INV_S84c4369_RD5.0_7.0_H11x415.734
```

| Metric | AF27 |
|---|---:|
| Avg $/day | 1134.1146 |
| Min $/day | 1103.9768 |
| Min PF | 6.98467 |
| Max losing-day streak | 3 |
| Worst day | -999.90965 |

| Window | $/day | PF | Streak | Worst day | Raw trades |
|---:|---:|---:|---:|---:|---:|
| 90 | 1151.6543 | 6.98467 | 2 | -999.90820 | 3 |
| 120 | 1169.8909 | 7.77283 | 2 | -999.90805 | 4 |
| 150 | 1110.9366 | 7.23839 | 3 | -999.90965 | 4 |
| 180 | 1103.9768 | 7.97564 | 3 | -999.90946 | 7 |

## Weight Threshold

`af27_ambfix_c4369_inv_rdmin50_rd70_h11_probe.csv`: x415.734 ผ่าน / x415.735 fail

## No-Blow Guard

-999.91 pass / -1000 pass

## Look-Ahead Bias Audit

- Detection closed bar `j`, fill `j+1`, filters ใช้ข้อมูล ณ ตอนเข้าไม้
- M1 replay ตัดสินเฉพาะผลไม้ ไม่มี look-ahead; pessimistic fallback = ขอบล่าง
- Research/backtest-only

## Verdict

```text
AF27 = AF26 + AMBFIX_INV_S84c4369_RD5.0_7.0_H11x415.734
```

ชนะ AF26 ทั้ง avg (1061.47 → 1134.11) และ min (1039.86 → 1103.98) — ไล่ AF28 ต่อ
(INV c4369 5.0-7.0 H16/H22 คิว + รอ s86 screen) — ระยะถึง $1500 เหลือ ~$366
