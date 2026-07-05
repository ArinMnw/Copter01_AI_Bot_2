# AF8 — Ambfix Ladder: Direct S84 RD 5.0-7.0 H15

วันที่: 2026-07-04
สถานะ: research/backtest-only, ยังไม่ wire เข้า live bot
กติกา: ambfix resolution (ดู `create_af1.md` / `create_ambfix_audit.md`)

## Baseline

```text
AF7 = AF6 + AMBFIX_INV_S84_RD4.0_5.0_H22x258.309
```

| Metric | AF7 |
|---|---:|
| Avg $/day | 705.7808 |
| Min $/day | 632.2487 |
| Min PF | 5.78932 |
| Max streak | 3 |
| Worst day | -999.90950 |

## Search รอบนี้ (ambfix sweep บน AF7 base — top, ข้าม repeat: DIR 2.7-3.4 H10=AF2)

| Mode | Band | Hour | Best w | avg | min |
|---|---|---|---:|---:|---:|
| **direct** | **5.0-7.0** | **H15** | **116** | **730.33** | **649.29** | ✅ ผู้ชนะ |
| direct | 3.4-4.0 | H22 | 192 | 719.05 | 638.49 | candidate AF9 |
| inverse | 3.4-4.0 | H19 | 170 | 717.84 | 645.46 | candidate |
| direct | 2.7-3.4 | H17 | 96 | 716.01 | 649.36 | candidate |

## New Leg

```text
AMBFIX_DIR_S84_RD5.0_7.0_H15 — direct, `5.0 <= risk_distance <= 7.0`, fill_hour == 15 BKK
```

- Raw trades: 14/19/19/22 ที่ 90/120/150/180d
- Leg stats: lot_max 0.01, DD 0.71%, skipped 0

## New Champion

```text
AF8 = AF7 + AMBFIX_DIR_S84_RD5.0_7.0_H15x116.366
```

| Metric | AF8 |
|---|---:|
| Avg $/day | 730.4027 |
| Min $/day | 649.3481 |
| Min PF | 5.64059 |
| Max losing-day streak | 3 |
| Worst day | -999.90950 |

| Window | $/day | PF | Streak | Worst day | Raw trades |
|---:|---:|---:|---:|---:|---:|
| 90 | 778.6411 | 7.40263 | 3 | -999.90672 | 14 |
| 120 | 794.9316 | 7.00753 | 3 | -999.90708 | 19 |
| 150 | 698.6900 | 6.79679 | 3 | -999.90950 | 19 |
| 180 | 649.3481 | 5.64059 | 3 | -999.90790 | 22 |

## Weight Threshold

`af8_ambfix_dir_rdmin50_rd70_h15_probe.csv`: x116.366 ผ่าน / x116.367 fail

## No-Blow Guard

-999.91 pass / -1000 pass

## Look-Ahead Bias Audit

- Detection closed bar `j`, fill `j+1`, filters ใช้ข้อมูล ณ ตอนเข้าไม้
- M1 replay ตัดสินเฉพาะผลไม้ ไม่มี look-ahead; pessimistic fallback = ขอบล่าง
- Research/backtest-only

## Verdict

```text
AF8 = AF7 + AMBFIX_DIR_S84_RD5.0_7.0_H15x116.366
```

ชนะ AF7 ทั้ง avg (705.78 → 730.40) และ min (632.25 → 649.35) — ไล่ AF9 ต่อ
(DIR 3.4-4.0 H22 / INV 3.4-4.0 H19 / DIR 2.7-3.4 H17 คือ candidates ถัดไป)
