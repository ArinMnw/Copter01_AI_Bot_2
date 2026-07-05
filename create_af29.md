# AF29 — Ambfix Ladder: Direct S84 cfg3057 RD 4.0-5.0 H19 (เปิด config ที่ 4)

วันที่: 2026-07-04
สถานะ: research/backtest-only, ยังไม่ wire เข้า live bot
กติกา: ambfix resolution (ดู `create_af1.md` / `create_ambfix_audit.md`)
Config 3057: `S84_M15_lb72_rw0.25_wb1_eat0.12_fail0.08_op0_mb0.12_mr0.35_mid_revisit_sl0.2_rr1.2`
(M15 lookback 72, ไม่บังคับ opposite close; screen: inv_sum +845 แต่ leg เด่นจริงคือฝั่ง direct
หลัง slice; stream ambiguity 43 ไม้)

## Baseline

```text
AF28 = AF27 + AMBFIX_INV_S84c4369_RD5.0_7.0_H22x222.978
```

| Metric | AF28 |
|---|---:|
| Avg $/day | 1149.1737 |
| Min $/day | 1109.3283 |
| Min PF | 7.06513 |
| Max streak | 3 |
| Worst day | -999.90965 |

## Search (sweep2 cfg3057 บน AF28 base — ข้าม degenerate 1-2 ไม้ชน cap 8000 หลายตัว)

| Mode | Band | Hour | Best w | avg | min |
|---|---|---|---:|---:|---:|
| **direct** | **4.0-5.0** | **H19** | **730** | **1291.04** | **1244.01** | ✅ ผู้ชนะ (12 ไม้@180d, floor bind ที่ x733) |
| inverse | 2.7-3.4 | H13 | 524 | 1207.08 | 1169.59 | candidate AF30 |
| inverse | 3.4-4.0 | H11 | 320 | 1182.59 | 1130.38 | candidate |

## New Leg

```text
AMBFIX_DIR_S84c3057_RD4.0_5.0_H19 — direct, `4.0 <= risk_distance <= 5.0`, fill_hour == 19 BKK
```

- Raw trades: 7/8/10/12 ที่ 90/120/150/180d
- Leg stats: lot_max 0.01, DD 0.49%, skipped 0

## New Champion

```text
AF29 = AF28 + AMBFIX_DIR_S84c3057_RD4.0_5.0_H19x733.281
```

| Metric | AF29 |
|---|---:|
| Avg $/day | 1291.6726 |
| Min $/day | 1244.6186 |
| Min PF | 7.31180 |
| Max losing-day streak | 3 |
| Worst day | -999.90965 |

| Window | $/day | PF | Streak | Worst day | Raw trades |
|---:|---:|---:|---:|---:|---:|
| 90 | 1305.1586 | 7.31180 | 2 | -999.90820 | 7 |
| 120 | 1328.1702 | 8.66327 | 2 | -999.90805 | 8 |
| 150 | 1288.7430 | 8.38976 | 3 | -999.90965 | 10 |
| 180 | 1244.6186 | 8.46001 | 3 | -999.90946 | 12 |

## Weight Threshold

`af29_ambfix_c3057_dir_rdmin40_rd50_h19_probe.csv`: x733.281 ผ่าน / x733.282 fail

## No-Blow Guard

-999.91 pass / -1000 pass

## Look-Ahead Bias Audit

- Detection closed bar `j`, fill `j+1`, filters ใช้ข้อมูล ณ ตอนเข้าไม้
- M1 replay ตัดสินเฉพาะผลไม้ ไม่มี look-ahead; pessimistic fallback = ขอบล่าง
- Research/backtest-only

## Verdict

```text
AF29 = AF28 + AMBFIX_DIR_S84c3057_RD4.0_5.0_H19x733.281
```

ชนะ AF28 ทั้ง avg (1149.17 → 1291.67) และ min (1109.33 → 1244.62) — ก้าวใหญ่สุด
ของ AF ladder เหลือ ~$208 ถึงเป้า $1500 (คิว: INV c3057 2.7-3.4 H13, INV 3.4-4.0
H11, ผล s86 screen)
