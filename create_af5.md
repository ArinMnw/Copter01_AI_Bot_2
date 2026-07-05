# AF5 — Ambfix Ladder: Inverse S84 RD 3.4-4.0 H11

วันที่: 2026-07-04
สถานะ: research/backtest-only, ยังไม่ wire เข้า live bot
กติกา: ambfix resolution (ดู `create_af1.md` / `create_ambfix_audit.md`)

## Baseline

```text
AF4 = AF3 + AMBFIX_DIR_S84_RD5.0_7.0_H17x92.141
```

| Metric | AF4 |
|---|---:|
| Avg $/day | 628.6538 |
| Min $/day | 556.3663 |
| Min PF | 4.98067 |
| Max streak | 3 |
| Worst day | -999.90831 |

## Search รอบนี้ (ambfix sweep บน AF4 base — top, ข้าม repeat: INV 4.0-5.0 H17=AF1)

| Mode | Band | Hour | Best w | avg | min |
|---|---|---|---:|---:|---:|
| **inverse** | **3.4-4.0** | **H11** | **324** | **658.51** | **582.45** | ✅ ผู้ชนะ |
| inverse | 4.0-5.0 | H22 | 258 | 646.27 | 582.37 | candidate AF6 |
| direct | 3.4-4.0 | H22 | 214 | 643.45 | 563.32 | candidate |
| direct | 2.7-3.4 | H17 | 96 | 638.88 | 573.48 | candidate |

## New Leg

```text
AMBFIX_INV_S84_RD3.4_4.0_H11 — inverse, `3.4 <= risk_distance <= 4.0`, fill_hour == 11 BKK
```

- Config เดียวกับ S112 ของ ladder เดิม แต่รอดใต้กติกาซื่อสัตย์ (RD กว้าง → กำกวมน้อย)
- Raw trades: 9/13/13/14 ที่ 90/120/150/180d
- Leg stats: lot_max 0.01, DD 0.69%, skipped 0

## New Champion

```text
AF5 = AF4 + AMBFIX_INV_S84_RD3.4_4.0_H11x325.852
```

| Metric | AF5 |
|---|---:|
| Avg $/day | 658.6788 |
| Min $/day | 582.5974 |
| Min PF | 5.00025 |
| Max losing-day streak | 3 |
| Worst day | -999.90831 |

| Window | $/day | PF | Streak | Worst day | Raw trades |
|---:|---:|---:|---:|---:|---:|
| 90 | 700.5833 | 6.16664 | 2 | -999.90831 | 9 |
| 120 | 724.7674 | 6.02388 | 2 | -999.90708 | 13 |
| 150 | 626.7673 | 5.66808 | 3 | -998.76150 | 13 |
| 180 | 582.5974 | 5.00025 | 3 | -999.90790 | 14 |

## Weight Threshold

`af5_ambfix_inv_rdmin34_rd40_h11_probe.csv`: x325.852 ผ่าน / x325.853 fail

## No-Blow Guard

-999.91 pass / -1000 pass

## Look-Ahead Bias Audit

- Detection closed bar `j`, fill `j+1`, filters ใช้ข้อมูล ณ ตอนเข้าไม้
- M1 replay ตัดสินเฉพาะผลไม้ ไม่มี look-ahead; pessimistic fallback = ขอบล่าง
- Research/backtest-only

## Verdict

```text
AF5 = AF4 + AMBFIX_INV_S84_RD3.4_4.0_H11x325.852
```

ชนะ AF4 ทั้ง avg (628.65 → 658.68) และ min (556.37 → 582.60) — ไล่ AF6 ต่อ
(INV 4.0-5.0 H22 / DIR 3.4-4.0 H22 / DIR 2.7-3.4 H17 คือ candidates ถัดไป)
