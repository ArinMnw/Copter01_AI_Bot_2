# AF7 — Ambfix Ladder: Inverse S84 RD 4.0-5.0 H22

วันที่: 2026-07-04
สถานะ: research/backtest-only, ยังไม่ wire เข้า live bot
กติกา: ambfix resolution (ดู `create_af1.md` / `create_ambfix_audit.md`)

## Baseline

```text
AF6 = AF5 + AMBFIX_DIR_S84_RD5.0_7.0_H14x222.360
```

| Metric | AF6 |
|---|---:|
| Avg $/day | 688.1419 |
| Min $/day | 606.2169 |
| Min PF | 5.16973 |
| Max streak | 3 |
| Worst day | -999.90950 |

## Search รอบนี้ (ambfix sweep บน AF6 base — top)

| Mode | Band | Hour | Best w | avg | min |
|---|---|---|---:|---:|---:|
| **inverse** | **4.0-5.0** | **H22** | **258** | **705.76** | **632.22** | ✅ ผู้ชนะ |
| direct | 5.0-7.0 | H15 | 74 | 703.80 | 617.09 | candidate AF8 |
| direct | 3.4-4.0 | H22 | 192 | 701.41 | 612.46 | candidate |
| direct | 2.7-3.4 | H17 | 96 | 698.37 | 623.33 | candidate |

## New Leg

```text
AMBFIX_INV_S84_RD4.0_5.0_H22 — inverse, `4.0 <= risk_distance <= 5.0`, fill_hour == 22 BKK
```

- Config เดียวกับ S124 ของ ladder เดิม แต่รอดใต้กติกาซื่อสัตย์
- Raw trades: 9/9/11/14 ที่ 90/120/150/180d
- Leg stats: lot_max 0.01, DD 0.85%, skipped 0

## New Champion

```text
AF7 = AF6 + AMBFIX_INV_S84_RD4.0_5.0_H22x258.309
```

| Metric | AF7 |
|---|---:|
| Avg $/day | 705.7808 |
| Min $/day | 632.2487 |
| Min PF | 5.78932 |
| Max losing-day streak | 3 |
| Worst day | -999.90950 |

| Window | $/day | PF | Streak | Worst day | Raw trades |
|---:|---:|---:|---:|---:|---:|
| 90 | 754.2430 | 7.57572 | 3 | -999.90232 | 9 |
| 120 | 763.2703 | 6.86716 | 3 | -999.90708 | 9 |
| 150 | 673.3610 | 6.67130 | 3 | -999.90950 | 11 |
| 180 | 632.2487 | 5.78932 | 3 | -999.90790 | 14 |

## Weight Threshold

`af7_ambfix_inv_rdmin40_rd50_h22_probe.csv`: x258.309 ผ่าน / x258.310 fail

## No-Blow Guard

-999.91 pass / -1000 pass

## Look-Ahead Bias Audit

- Detection closed bar `j`, fill `j+1`, filters ใช้ข้อมูล ณ ตอนเข้าไม้
- M1 replay ตัดสินเฉพาะผลไม้ ไม่มี look-ahead; pessimistic fallback = ขอบล่าง
- Research/backtest-only

## Verdict

```text
AF7 = AF6 + AMBFIX_INV_S84_RD4.0_5.0_H22x258.309
```

ชนะ AF6 ทั้ง avg (688.14 → 705.78) และ min (606.22 → 632.25) — ไล่ AF8 ต่อ
(DIR 5.0-7.0 H15 / DIR 3.4-4.0 H22 / DIR 2.7-3.4 H17 คือ candidates ถัดไป)
