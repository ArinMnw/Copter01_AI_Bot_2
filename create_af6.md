# AF6 — Ambfix Ladder: Direct S84 RD 5.0-7.0 H14

วันที่: 2026-07-04
สถานะ: research/backtest-only, ยังไม่ wire เข้า live bot
กติกา: ambfix resolution (ดู `create_af1.md` / `create_ambfix_audit.md`)

## Baseline

```text
AF5 = AF4 + AMBFIX_INV_S84_RD3.4_4.0_H11x325.852
```

| Metric | AF5 |
|---|---:|
| Avg $/day | 658.6788 |
| Min $/day | 582.5974 |
| Min PF | 5.00025 |
| Max streak | 3 |
| Worst day | -999.90831 |

## Search รอบนี้ (ambfix sweep บน AF5 base — top)

| Mode | Band | Hour | Best w | avg | min |
|---|---|---|---:|---:|---:|
| **direct** | **5.0-7.0** | **H14** | **222** | **688.09** | **606.18** | ✅ ผู้ชนะ |
| inverse | 4.0-5.0 | H22 | 258 | 676.30 | 608.60 | candidate AF7 |
| direct | 3.4-4.0 | H22 | 214 | 673.47 | 589.55 | candidate |
| direct | 2.7-3.4 | H17 | 96 | 668.91 | 599.71 | candidate |

## New Leg

```text
AMBFIX_DIR_S84_RD5.0_7.0_H14 — direct, `5.0 <= risk_distance <= 7.0`, fill_hour == 14 BKK
```

- Raw trades: 8/10/10/13 ที่ 90/120/150/180d
- Leg stats: lot_max 0.01, DD 0.77%, skipped 0

## New Champion

```text
AF6 = AF5 + AMBFIX_DIR_S84_RD5.0_7.0_H14x222.360
```

| Metric | AF6 |
|---|---:|
| Avg $/day | 688.1419 |
| Min $/day | 606.2169 |
| Min PF | 5.16973 |
| Max losing-day streak | 3 |
| Worst day | -999.90950 |

| Window | $/day | PF | Streak | Worst day | Raw trades |
|---:|---:|---:|---:|---:|---:|
| 90 | 742.0164 | 6.67880 | 3 | -999.90232 | 8 |
| 120 | 754.1004 | 6.28400 | 3 | -999.90708 | 10 |
| 150 | 650.2337 | 5.82144 | 3 | -999.90950 | 10 |
| 180 | 606.2169 | 5.16973 | 3 | -999.90790 | 13 |

## Weight Threshold

`af6_ambfix_dir_rdmin50_rd70_h14_probe.csv`: x222.360 ผ่าน / x222.361 fail

## No-Blow Guard

-999.91 pass / -1000 pass

## Look-Ahead Bias Audit

- Detection closed bar `j`, fill `j+1`, filters ใช้ข้อมูล ณ ตอนเข้าไม้
- M1 replay ตัดสินเฉพาะผลไม้ ไม่มี look-ahead; pessimistic fallback = ขอบล่าง
- Research/backtest-only

## Verdict

```text
AF6 = AF5 + AMBFIX_DIR_S84_RD5.0_7.0_H14x222.360
```

ชนะ AF5 ทั้ง avg (658.68 → 688.14) และ min (582.60 → 606.22) — ไล่ AF7 ต่อ
(INV 4.0-5.0 H22 / DIR 3.4-4.0 H22 / DIR 2.7-3.4 H17 คือ candidates ถัดไป)
