# AF25 — Ambfix Ladder: Inverse S84 cfg5505 RD 5.0-7.0 H11 (เปิด config ที่ 2)

วันที่: 2026-07-04
สถานะ: research/backtest-only, ยังไม่ wire เข้า live bot
กติกา: ambfix resolution (ดู `create_af1.md` / `create_ambfix_audit.md`)
Config 5505: `S84_M30_lb48_rw0.35_wb0.8_eat0.12_fail0.08_op1_mb0.06_mr0.25_mid_revisit_sl0.2_rr1.2`
(= cfg6017 แต่ wick/body 0.8 แทน 1.0 — screen: dir PF 1.15, n=946)

## Baseline

```text
AF24 = AF23 + AMBFIX_DIR_S84c6017_ALL_H12x23.911
```

| Metric | AF24 |
|---|---:|
| Avg $/day | 1038.7604 |
| Min $/day | 1008.8045 |
| Min PF | 6.76284 |
| Max streak | 3 |
| Worst day | -999.90965 |

## Search (sweep2 cfg5505 บน AF24 base)

| Mode | Band | Hour | ผล | หมายเหตุ |
|---|---|---|---|---|
| inverse | 5.0-7.0 | H16 | ชน cap 8000 = degenerate → **stress cap ≈ 0.0002** | ❌ ใช้ไม่ได้ — leg มีไม้บวกตรงวันที่ base ชิด floor (-999.9096) พอดี stress-flip จึงไม่เหลือ headroom |
| **inverse** | **5.0-7.0** | **H11** | **x120 → 1047.18/1017.27** | ✅ ผู้ชนะ (floor bind ปกติ) |
| inverse | 4.0-5.0 | H17 | x92 → 1044.37/1013.13 | candidate AF26 |

บทเรียนใหม่: stress-flip rule สามารถตัด degenerate leg เหลือ weight ~0 ได้เมื่อ
leg fire ตรงวัน floor-edge ของ base — พฤติกรรมถูกต้องตามเจตนา (กันเพิ่มความเสี่ยง
บนวันที่ชิดขอบอยู่แล้ว)

## New Leg

```text
AMBFIX_INV_S84c5505_RD5.0_7.0_H11 — inverse, `5.0 <= risk_distance <= 7.0`, fill_hour == 11 BKK
```

- Raw trades: 4/6/8/9 ที่ 90/120/150/180d
- Leg stats: lot_max 0.01, DD 0.81%, skipped 0; stream ambiguity 11 ไม้ (สะอาด)

## New Champion

```text
AF25 = AF24 + AMBFIX_INV_S84c5505_RD5.0_7.0_H11x121.543
```

| Metric | AF25 |
|---|---:|
| Avg $/day | 1047.2843 |
| Min $/day | 1017.3800 |
| Min PF | 6.53130 |
| Max losing-day streak | 3 |
| Worst day | -999.90965 |

| Window | $/day | PF | Streak | Worst day | Raw trades |
|---:|---:|---:|---:|---:|---:|
| 90 | 1064.4106 | 6.53130 | 2 | -999.90820 | 4 |
| 120 | 1082.1817 | 7.26505 | 2 | -999.90805 | 6 |
| 150 | 1025.1647 | 6.75674 | 3 | -999.90965 | 8 |
| 180 | 1017.3800 | 7.59967 | 3 | -999.90946 | 9 |

## Weight Threshold

`af25_ambfix_c5505_inv_rdmin50_rd70_h11_probe.csv`: x121.543 ผ่าน / x121.544 fail

## No-Blow Guard

-999.91 pass / -1000 pass

## Look-Ahead Bias Audit

- Detection closed bar `j`, fill `j+1`, filters ใช้ข้อมูล ณ ตอนเข้าไม้
- M1 replay ตัดสินเฉพาะผลไม้ ไม่มี look-ahead; pessimistic fallback = ขอบล่าง
- Research/backtest-only

## Verdict

```text
AF25 = AF24 + AMBFIX_INV_S84c5505_RD5.0_7.0_H11x121.543
```

ชนะ AF24 ทั้ง avg (1038.76 → 1047.28) และ min (1008.80 → 1017.38) — ไล่ AF26 ต่อ
(INV c5505 4.0-5.0 H17 / cfg4369 / cfg3057 / s86 screen)
