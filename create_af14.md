# AF14 — Ambfix Ladder: Direct S84 RD 4.0-5.0 H18

วันที่: 2026-07-04
สถานะ: research/backtest-only, ยังไม่ wire เข้า live bot
กติกา: ambfix resolution (ดู `create_af1.md` / `create_ambfix_audit.md`)

## Baseline

```text
AF13 = AF12 + AMBFIX_DIR_S84_RD0.8_1.3_H18x414.033
```

| Metric | AF13 |
|---|---:|
| Avg $/day | 800.4449 |
| Min $/day | 731.8003 |
| Min PF | 5.71751 |
| Max streak | 3 |
| Worst day | -999.90950 |

## Search รอบนี้ (ambfix sweep บน AF13 base — top)

| Mode | Band | Hour | Best w | avg | min |
|---|---|---|---:|---:|---:|
| **direct** | **4.0-5.0** | **H18** | **138** | **805.56** | **732.37** | ✅ ผู้ชนะ |
| inverse | 4.0-5.0 | H15 | 156 | 803.71 | 735.23 | candidate AF15 |
| inverse | 5.0-7.0 | H8 | 86 | 803.62 | 739.07 | candidate |
| direct | 4.0-5.0 | H8 | 10 | 803.41 | 733.58 | candidate |

## New Leg

```text
AMBFIX_DIR_S84_RD4.0_5.0_H18 — direct, `4.0 <= risk_distance <= 5.0`, fill_hour == 18 BKK
```

- Raw trades: 8/10/13/16 ที่ 90/120/150/180d
- Leg stats: lot_max 0.01, DD 1.07%, skipped 0

## New Champion

```text
AF14 = AF13 + AMBFIX_DIR_S84_RD4.0_5.0_H18x138.139
```

| Metric | AF14 |
|---|---:|
| Avg $/day | 805.5693 |
| Min $/day | 732.3682 |
| Min PF | 5.66582 |
| Max losing-day streak | 3 |
| Worst day | -999.90950 |

| Window | $/day | PF | Streak | Worst day | Raw trades |
|---:|---:|---:|---:|---:|---:|
| 90 | 828.1185 | 6.51196 | 2 | -999.90854 | 8 |
| 120 | 875.6560 | 6.89119 | 2 | -999.90805 | 10 |
| 150 | 786.1346 | 6.59254 | 3 | -999.90950 | 13 |
| 180 | 732.3682 | 5.66582 | 3 | -999.90935 | 16 |

## Weight Threshold

`af14_ambfix_dir_rdmin40_rd50_h18_probe.csv`: x138.139 ผ่าน / x138.140 fail

## No-Blow Guard

-999.91 pass / -1000 pass

## Look-Ahead Bias Audit

- Detection closed bar `j`, fill `j+1`, filters ใช้ข้อมูล ณ ตอนเข้าไม้
- M1 replay ตัดสินเฉพาะผลไม้ ไม่มี look-ahead; pessimistic fallback = ขอบล่าง
- Research/backtest-only

## Verdict

```text
AF14 = AF13 + AMBFIX_DIR_S84_RD4.0_5.0_H18x138.139
```

ชนะ AF13 ทั้ง avg (800.44 → 805.57) และ min (731.80 → 732.37) — ไล่ AF15 ต่อ
(INV 4.0-5.0 H15 / INV 5.0-7.0 H8 / DIR 4.0-5.0 H8 คือ candidates ถัดไป)
