# AF11 — Ambfix Ladder: Direct S84 RD 3.4-4.0 H22

วันที่: 2026-07-04
สถานะ: research/backtest-only, ยังไม่ wire เข้า live bot
กติกา: ambfix resolution (ดู `create_af1.md` / `create_ambfix_audit.md`)

## Baseline

```text
AF10 = AF9 + AMBFIX_DIR_S84_RD5.0_7.0_H11x212.057
```

| Metric | AF10 |
|---|---:|
| Avg $/day | 762.7122 |
| Min $/day | 707.1781 |
| Min PF | 5.95823 |
| Max streak | 3 |
| Worst day | -999.90950 |

## Search รอบนี้ (ambfix sweep บน AF10 base — top, ข้าม repeat: DIR 2.7-3.4 H10=AF2)

| Mode | Band | Hour | Best w | avg | min |
|---|---|---|---:|---:|---:|
| **direct** | **3.4-4.0** | **H22** | **274** | **781.65** | **716.08** | ✅ ผู้ชนะ |
| direct | 2.7-3.4 | H17 | 96 | 772.94 | 724.29 | candidate AF12 |
| direct | 5.0-7.0 | H20 | 54 | 772.78 | 719.71 | candidate |
| direct | 4.0-5.0 | H18 | 198 | 770.06 | 707.99 | candidate |

## New Leg

```text
AMBFIX_DIR_S84_RD3.4_4.0_H22 — direct, `3.4 <= risk_distance <= 4.0`, fill_hour == 22 BKK
```

- Raw trades: 6/9/10/11 ที่ 90/120/150/180d
- Leg stats: lot_max 0.01, DD 0.75%, skipped 0

## New Champion

```text
AF11 = AF10 + AMBFIX_DIR_S84_RD3.4_4.0_H22x274.789
```

| Metric | AF11 |
|---|---:|
| Avg $/day | 781.7078 |
| Min $/day | 716.1088 |
| Min PF | 5.71219 |
| Max losing-day streak | 3 |
| Worst day | -999.90950 |

| Window | $/day | PF | Streak | Worst day | Raw trades |
|---:|---:|---:|---:|---:|---:|
| 90 | 805.0272 | 6.77648 | 3 | -999.90672 | 6 |
| 120 | 843.8882 | 6.76539 | 3 | -999.90805 | 9 |
| 150 | 761.8069 | 6.71379 | 3 | -999.90950 | 10 |
| 180 | 716.1088 | 5.71219 | 3 | -999.90935 | 11 |

## Weight Threshold

`af11_ambfix_dir_rdmin34_rd40_h22_probe.csv`: x274.789 ผ่าน / x274.790 fail

## No-Blow Guard

-999.91 pass / -1000 pass

## Look-Ahead Bias Audit

- Detection closed bar `j`, fill `j+1`, filters ใช้ข้อมูล ณ ตอนเข้าไม้
- M1 replay ตัดสินเฉพาะผลไม้ ไม่มี look-ahead; pessimistic fallback = ขอบล่าง
- Research/backtest-only

## Verdict

```text
AF11 = AF10 + AMBFIX_DIR_S84_RD3.4_4.0_H22x274.789
```

ชนะ AF10 ทั้ง avg (762.71 → 781.71) และ min (707.18 → 716.11) — ไล่ AF12 ต่อ
(DIR 2.7-3.4 H17 / DIR 5.0-7.0 H20 / DIR 4.0-5.0 H18 คือ candidates ถัดไป)
