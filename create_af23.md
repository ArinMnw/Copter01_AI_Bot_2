# AF23 — Ambfix Ladder: Inverse S84 cfg6017 RD 5.0-7.0 H16

วันที่: 2026-07-04
สถานะ: research/backtest-only, ยังไม่ wire เข้า live bot
กติกา: ambfix resolution (ดู `create_af1.md` / `create_ambfix_audit.md`)
Config 6017: `S84_M30_lb48_rw0.35_wb1_eat0.12_fail0.08_op1_mb0.06_mr0.25_mid_revisit_sl0.2_rr1.2`

## Baseline

```text
AF22 = AF21 + AMBFIX_DIR_S84c6017_RD5.0_7.0_H14x244.089
```

| Metric | AF22 |
|---|---:|
| Avg $/day | 1003.8306 |
| Min $/day | 963.6480 |
| Min PF | 6.61060 |
| Max streak | 3 |
| Worst day | -999.90965 |

## Search (sweep2 cfg6017 บน AF22 base — top 3 เป็น 1-ไม้ degenerate ชน cap → ข้าม)

| Mode | Band | Hour | Best w | avg | min |
|---|---|---|---:|---:|---:|
| **inverse** | **5.0-7.0** | **H16** | **344** | **1017.90** | **995.03** | ✅ ผู้ชนะ |
| inverse | 5.0-7.0 | H13 | 106 | 1017.43 | 972.64 | candidate AF24 |

## New Leg

```text
AMBFIX_INV_S84c6017_RD5.0_7.0_H16 — inverse, `5.0 <= risk_distance <= 7.0`, fill_hour == 16 BKK
```

- Raw trades: 2/3/4/5 ที่ 90/120/150/180d — บาง ระบุเป็นคำเตือน
- Leg stats: lot_max 0.01, DD 0.72%, skipped 0

## New Champion

```text
AF23 = AF22 + AMBFIX_INV_S84c6017_RD5.0_7.0_H16x344.837
```

| Metric | AF23 |
|---|---:|
| Avg $/day | 1017.9378 |
| Min $/day | 995.1048 |
| Min PF | 6.89752 |
| Max losing-day streak | 3 |
| Worst day | -999.90965 |

| Window | $/day | PF | Streak | Worst day | Raw trades |
|---:|---:|---:|---:|---:|---:|
| 90 | 1007.1528 | 6.96508 | 2 | -999.90777 | 2 |
| 120 | 1063.8307 | 7.95307 | 2 | -999.90805 | 3 |
| 150 | 1005.6628 | 6.89752 | 3 | -999.90965 | 4 |
| 180 | 995.1048 | 7.61196 | 3 | -999.90946 | 5 |

## Weight Threshold

`af23_ambfix_c6017_inv_rdmin50_rd70_h16_probe.csv`: x344.837 ผ่าน / x344.838 fail

## No-Blow Guard

-999.91 pass / -1000 pass

## Look-Ahead Bias Audit

- Detection closed bar `j`, fill `j+1`, filters ใช้ข้อมูล ณ ตอนเข้าไม้
- M1 replay ตัดสินเฉพาะผลไม้ ไม่มี look-ahead; pessimistic fallback = ขอบล่าง
- Research/backtest-only

## Verdict

```text
AF23 = AF22 + AMBFIX_INV_S84c6017_RD5.0_7.0_H16x344.837
```

ชนะ AF22 ทั้ง avg (1003.83 → 1017.94) และ min (963.65 → 995.10) — เหลือ ~$5
ถึง milestone "ทุก window ≥ $1000" ไล่ AF24 ต่อ
