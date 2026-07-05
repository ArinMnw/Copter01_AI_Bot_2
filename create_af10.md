# AF10 — Ambfix Ladder: Direct S84 RD 5.0-7.0 H11

วันที่: 2026-07-04
สถานะ: research/backtest-only, ยังไม่ wire เข้า live bot
กติกา: ambfix resolution (ดู `create_af1.md` / `create_ambfix_audit.md`)

## Baseline

```text
AF9 = AF8 + AMBFIX_INV_S84_RD3.4_4.0_H19x232.335
```

| Metric | AF9 |
|---|---:|
| Avg $/day | 746.8804 |
| Min $/day | 667.4057 |
| Min PF | 5.55098 |
| Max streak | 3 |
| Worst day | -999.90950 |

## Search รอบนี้ (ambfix sweep บน AF9 base — top, ข้าม repeat: DIR 2.7-3.4 H10=AF2)

| Mode | Band | Hour | Best w | avg | min |
|---|---|---|---:|---:|---:|
| **direct** | **5.0-7.0** | **H11** | **212** | **762.71** | **707.17** | ✅ ผู้ชนะ |
| direct | 3.4-4.0 | H22 | 214 | 761.67 | 674.36 | candidate AF11 |
| direct | 2.7-3.4 | H17 | 96 | 757.11 | 684.52 | candidate |
| direct | 2.7-3.4 | H20 | 60 | 753.60 | 671.05 | candidate |

## New Leg

```text
AMBFIX_DIR_S84_RD5.0_7.0_H11 — direct, `5.0 <= risk_distance <= 7.0`, fill_hour == 11 BKK
```

- Raw trades: 8/11/13/16 ที่ 90/120/150/180d
- Leg stats: lot_max 0.01, DD 1.51%, skipped 0

## New Champion

```text
AF10 = AF9 + AMBFIX_DIR_S84_RD5.0_7.0_H11x212.057
```

| Metric | AF10 |
|---|---:|
| Avg $/day | 762.7122 |
| Min $/day | 707.1781 |
| Min PF | 5.95823 |
| Max losing-day streak | 3 |
| Worst day | -999.90950 |

| Window | $/day | PF | Streak | Worst day | Raw trades |
|---:|---:|---:|---:|---:|---:|
| 90 | 771.2892 | 6.81650 | 3 | -999.90672 | 8 |
| 120 | 828.3627 | 7.38045 | 3 | -999.90708 | 11 |
| 150 | 744.0189 | 7.14696 | 3 | -999.90950 | 13 |
| 180 | 707.1781 | 5.95823 | 3 | -999.90935 | 16 |

## Weight Threshold

`af10_ambfix_dir_rdmin50_rd70_h11_probe.csv`: x212.057 ผ่าน / x212.058 fail

## No-Blow Guard

-999.91 pass / -1000 pass

## Look-Ahead Bias Audit

- Detection closed bar `j`, fill `j+1`, filters ใช้ข้อมูล ณ ตอนเข้าไม้
- M1 replay ตัดสินเฉพาะผลไม้ ไม่มี look-ahead; pessimistic fallback = ขอบล่าง
- Research/backtest-only

## Verdict

```text
AF10 = AF9 + AMBFIX_DIR_S84_RD5.0_7.0_H11x212.057
```

ชนะ AF9 ทั้ง avg (746.88 → 762.71) และ min (667.41 → 707.18) — ไล่ AF11 ต่อ
(DIR 3.4-4.0 H22 / DIR 2.7-3.4 H17 / DIR 2.7-3.4 H20 คือ candidates ถัดไป)
