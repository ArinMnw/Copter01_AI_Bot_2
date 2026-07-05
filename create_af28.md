# AF28 — Ambfix Ladder: Inverse S84 cfg4369 RD 5.0-7.0 H22

วันที่: 2026-07-04
สถานะ: research/backtest-only, ยังไม่ wire เข้า live bot
กติกา: ambfix resolution (ดู `create_af1.md` / `create_ambfix_audit.md`)
Config 4369: `S84_M30_lb48_rw0.25_wb0.8_eat0.12_fail0.03_op1_mb0.06_mr0.35_mid_revisit_sl0.2_rr1.2`

## Baseline

```text
AF27 = AF26 + AMBFIX_INV_S84c4369_RD5.0_7.0_H11x415.734
```

| Metric | AF27 |
|---|---:|
| Avg $/day | 1134.1146 |
| Min $/day | 1103.9768 |
| Min PF | 6.98467 |
| Max streak | 3 |
| Worst day | -999.90965 |

## Search (sweep2 cfg4369 บน AF27 base — ข้าม degenerate 1-ไม้ชน cap 2 ตัว)

| Mode | Band | Hour | Best w | avg | min |
|---|---|---|---:|---:|---:|
| **inverse** | **5.0-7.0** | **H22** | **222** | **1149.11** | **1109.30** | ✅ ผู้ชนะ |
| inverse | 5.0-7.0 | H20 | 358 | 1146.01 | 1107.19 | candidate AF29 (บาง 3 ไม้@180d) |
| direct | 5.0-7.0 | H21 | 184 | 1141.67 | 1105.87 | candidate (บาง 2 ไม้) |

## New Leg

```text
AMBFIX_INV_S84c4369_RD5.0_7.0_H22 — inverse, `5.0 <= risk_distance <= 7.0`, fill_hour == 22 BKK
```

- Raw trades: 1/2/3/3 ที่ 90/120/150/180d — ⚠️ บาง ระบุเป็นคำเตือน
- Leg stats: lot_max 0.01, DD 0.75%, skipped 0

## New Champion

```text
AF28 = AF27 + AMBFIX_INV_S84c4369_RD5.0_7.0_H22x222.978
```

| Metric | AF28 |
|---|---:|
| Avg $/day | 1149.1737 |
| Min $/day | 1109.3283 |
| Min PF | 7.06513 |
| Max losing-day streak | 3 |
| Worst day | -999.90965 |

| Window | $/day | PF | Streak | Worst day | Raw trades |
|---:|---:|---:|---:|---:|---:|
| 90 | 1167.1388 | 7.06513 | 2 | -999.90820 | 1 |
| 120 | 1191.7799 | 8.24925 | 2 | -999.90805 | 2 |
| 150 | 1128.4478 | 7.56802 | 3 | -999.90965 | 3 |
| 180 | 1109.3283 | 7.95830 | 3 | -999.90946 | 3 |

## Weight Threshold

`af28_ambfix_c4369_inv_rdmin50_rd70_h22_probe.csv`: x222.978 ผ่าน / x222.979 fail

## No-Blow Guard

-999.91 pass / -1000 pass

## Look-Ahead Bias Audit

- Detection closed bar `j`, fill `j+1`, filters ใช้ข้อมูล ณ ตอนเข้าไม้
- M1 replay ตัดสินเฉพาะผลไม้ ไม่มี look-ahead; pessimistic fallback = ขอบล่าง
- Research/backtest-only

## Verdict

```text
AF28 = AF27 + AMBFIX_INV_S84c4369_RD5.0_7.0_H22x222.978
```

ชนะ AF27 ทั้ง avg (1134.11 → 1149.17) และ min (1103.98 → 1109.33) — ไล่ AF29 ต่อ
(คิว: INV c4369 H20, cfg3057, ผล s86 screen)
