# AF30 — Ambfix Ladder: Inverse S84 cfg3057 RD 2.7-3.4 H13

วันที่: 2026-07-04
สถานะ: research/backtest-only, ยังไม่ wire เข้า live bot
กติกา: ambfix resolution (ดู `create_af1.md` / `create_ambfix_audit.md`)
Config 3057: `S84_M15_lb72_rw0.25_wb1_eat0.12_fail0.08_op0_mb0.12_mr0.35_mid_revisit_sl0.2_rr1.2`

## Baseline

```text
AF29 = AF28 + AMBFIX_DIR_S84c3057_RD4.0_5.0_H19x733.281
```

| Metric | AF29 |
|---|---:|
| Avg $/day | 1291.6726 |
| Min $/day | 1244.6186 |
| Min PF | 7.31180 |
| Max streak | 3 |
| Worst day | -999.90965 |

## Search (sweep2 cfg3057 บน AF29 base — ข้าม degenerate 1-2 ไม้ชน cap 4 ตัว)

| Mode | Band | Hour | Best w | avg | min |
|---|---|---|---:|---:|---:|
| **inverse** | **2.7-3.4** | **H13** | **524** | **1349.58** | **1304.88** | ✅ ผู้ชนะ |
| inverse | 3.4-4.0 | H11 | 320 | 1325.09 | 1265.67 | candidate AF31 |

## New Leg

```text
AMBFIX_INV_S84c3057_RD2.7_3.4_H13 — inverse, `2.7 <= risk_distance <= 3.4`, fill_hour == 13 BKK
```

- Raw trades: 1/2/4/6 ที่ 90/120/150/180d — ⚠️ บาง ระบุเป็นคำเตือน
- Leg stats: lot_max 0.02, DD 0.78%, skipped 0

## New Champion

```text
AF30 = AF29 + AMBFIX_INV_S84c3057_RD2.7_3.4_H13x525.853
```

| Metric | AF30 |
|---|---:|
| Avg $/day | 1349.7852 |
| Min $/day | 1305.0917 |
| Min PF | 7.48585 |
| Max losing-day streak | 3 |
| Worst day | -999.90965 |

| Window | $/day | PF | Streak | Worst day | Raw trades |
|---:|---:|---:|---:|---:|---:|
| 90 | 1341.1503 | 7.48585 | 2 | -999.90820 | 1 |
| 120 | 1381.6319 | 8.97173 | 2 | -999.90805 | 2 |
| 150 | 1371.2669 | 8.86296 | 3 | -999.90965 | 4 |
| 180 | 1305.0917 | 8.57041 | 3 | -999.90946 | 6 |

## Weight Threshold

`af30_ambfix_c3057_inv_rdmin27_rd34_h13_probe.csv`: x525.853 ผ่าน / x525.854 fail

## No-Blow Guard

-999.91 pass / -1000 pass

## Look-Ahead Bias Audit

- Detection closed bar `j`, fill `j+1`, filters ใช้ข้อมูล ณ ตอนเข้าไม้
- M1 replay ตัดสินเฉพาะผลไม้ ไม่มี look-ahead; pessimistic fallback = ขอบล่าง
- Research/backtest-only

## Verdict

```text
AF30 = AF29 + AMBFIX_INV_S84c3057_RD2.7_3.4_H13x525.853
```

ชนะ AF29 ทั้ง avg (1291.67 → 1349.79) และ min (1244.62 → 1305.09) — เหลือ ~$150
ถึงเป้า $1500 (คิว: INV c3057 3.4-4.0 H11, ผล s86 screen)
