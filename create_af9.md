# AF9 — Ambfix Ladder: Inverse S84 RD 3.4-4.0 H19

วันที่: 2026-07-04
สถานะ: research/backtest-only, ยังไม่ wire เข้า live bot
กติกา: ambfix resolution (ดู `create_af1.md` / `create_ambfix_audit.md`)

## Baseline

```text
AF8 = AF7 + AMBFIX_DIR_S84_RD5.0_7.0_H15x116.366
```

| Metric | AF8 |
|---|---:|
| Avg $/day | 730.4027 |
| Min $/day | 649.3481 |
| Min PF | 5.64059 |
| Max streak | 3 |
| Worst day | -999.90950 |

## Search รอบนี้ (ambfix sweep บน AF8 base — top, ข้าม repeat: DIR 2.7-3.4 H10=AF2)

| Mode | Band | Hour | Best w | avg | min |
|---|---|---|---:|---:|---:|
| **inverse** | **3.4-4.0** | **H19** | **232** | **746.86** | **667.38** | ✅ ผู้ชนะ |
| direct | 3.4-4.0 | H22 | 214 | 745.20 | 656.30 | candidate AF10 |
| direct | 2.7-3.4 | H17 | 96 | 740.63 | 666.46 | candidate |
| direct | 5.0-7.0 | H11 | 100 | 737.87 | 668.10 | candidate |

## New Leg

```text
AMBFIX_INV_S84_RD3.4_4.0_H19 — inverse, `3.4 <= risk_distance <= 4.0`, fill_hour == 19 BKK
```

- Config เดียวกับ S114 ของ ladder เดิม แต่รอดใต้กติกาซื่อสัตย์
- Raw trades: 7/9/12/18 ที่ 90/120/150/180d
- Leg stats: lot_max 0.01, DD 0.69%, skipped 0

## New Champion

```text
AF9 = AF8 + AMBFIX_INV_S84_RD3.4_4.0_H19x232.335
```

| Metric | AF9 |
|---|---:|
| Avg $/day | 746.8804 |
| Min $/day | 667.4057 |
| Min PF | 5.55098 |
| Max losing-day streak | 3 |
| Worst day | -999.90950 |

| Window | $/day | PF | Streak | Worst day | Raw trades |
|---:|---:|---:|---:|---:|---:|
| 90 | 786.4630 | 7.34256 | 3 | -999.90672 | 7 |
| 120 | 814.3315 | 7.46740 | 3 | -999.90708 | 9 |
| 150 | 719.3213 | 7.04927 | 3 | -999.90950 | 12 |
| 180 | 667.4057 | 5.55098 | 3 | -999.90790 | 18 |

## Weight Threshold

`af9_ambfix_inv_rdmin34_rd40_h19_probe.csv`: x232.335 ผ่าน / x232.336 fail

## No-Blow Guard

-999.91 pass / -1000 pass

## Look-Ahead Bias Audit

- Detection closed bar `j`, fill `j+1`, filters ใช้ข้อมูล ณ ตอนเข้าไม้
- M1 replay ตัดสินเฉพาะผลไม้ ไม่มี look-ahead; pessimistic fallback = ขอบล่าง
- Research/backtest-only

## Verdict

```text
AF9 = AF8 + AMBFIX_INV_S84_RD3.4_4.0_H19x232.335
```

ชนะ AF8 ทั้ง avg (730.40 → 746.88) และ min (649.35 → 667.41) — ไล่ AF10 ต่อ
(DIR 3.4-4.0 H22 / DIR 2.7-3.4 H17 / DIR 5.0-7.0 H11 คือ candidates ถัดไป)
