# AF13 — Ambfix Ladder: Direct S84 RD 0.8-1.3 H18

วันที่: 2026-07-04
สถานะ: research/backtest-only, ยังไม่ wire เข้า live bot
กติกา: ambfix resolution (ดู `create_af1.md` / `create_ambfix_audit.md`)

## Baseline

```text
AF12 = AF11 + AMBFIX_DIR_S84_RD5.0_7.0_H20x54.139
```

| Metric | AF12 |
|---|---:|
| Avg $/day | 791.8009 |
| Min $/day | 728.6720 |
| Min PF | 5.79195 |
| Max streak | 3 |
| Worst day | -999.90950 |

## Search รอบนี้ (ambfix sweep บน AF12 base — top, ข้าม repeat: DIR 2.7-3.4 H10=AF2)

| Mode | Band | Hour | Best w | avg | min |
|---|---|---|---:|---:|---:|
| **direct** | **0.8-1.3** | **H18** | **414** | **800.44** | **731.80** | ✅ ผู้ชนะ |
| direct | 4.0-5.0 | H18 | 138 | 796.92 | 729.24 | candidate AF14 |
| inverse | 4.0-5.0 | H15 | 156 | 795.07 | 732.10 | candidate |
| inverse | 5.0-7.0 | H8 | 86 | 794.98 | 735.94 | candidate |

## New Leg

```text
AMBFIX_DIR_S84_RD0.8_1.3_H18 — direct, `0.8 <= risk_distance <= 1.3`, fill_hour == 18 BKK
```

- ⚠️ Leg บาง: 1/1/3/3 ไม้ที่ 90/120/150/180d (precedent เดียวกับ S128 ของ ladder เดิม)
  — ความเชื่อมั่นต่ำกว่า leg อื่น แต่ผ่านเกณฑ์ beats/floor/streak ครบใต้ ambfix
- Leg stats: lot_max 0.04, DD 0.57%, skipped 0

## New Champion

```text
AF13 = AF12 + AMBFIX_DIR_S84_RD0.8_1.3_H18x414.033
```

| Metric | AF13 |
|---|---:|
| Avg $/day | 800.4449 |
| Min $/day | 731.8003 |
| Min PF | 5.71751 |
| Max losing-day streak | 3 |
| Worst day | -999.90950 |

| Window | $/day | PF | Streak | Worst day | Raw trades |
|---:|---:|---:|---:|---:|---:|
| 90 | 822.1939 | 6.65622 | 3 | -999.90672 | 1 |
| 120 | 867.1489 | 6.83876 | 2 | -999.90805 | 1 |
| 150 | 780.6367 | 6.65265 | 3 | -999.90950 | 3 |
| 180 | 731.8003 | 5.71751 | 3 | -999.90935 | 3 |

## Weight Threshold

`af13_ambfix_dir_rdmin08_rd13_h18_probe.csv`: x414.033 ผ่าน / x414.034 fail

## No-Blow Guard

-999.91 pass / -1000 pass

## Look-Ahead Bias Audit

- Detection closed bar `j`, fill `j+1`, filters ใช้ข้อมูล ณ ตอนเข้าไม้
- M1 replay ตัดสินเฉพาะผลไม้ ไม่มี look-ahead; pessimistic fallback = ขอบล่าง
- Research/backtest-only

## Verdict

```text
AF13 = AF12 + AMBFIX_DIR_S84_RD0.8_1.3_H18x414.033
```

ชนะ AF12 ทั้ง avg (791.80 → 800.44) และ min (728.67 → 731.80) — ไล่ AF14 ต่อ
(DIR 4.0-5.0 H18 / INV 4.0-5.0 H15 / INV 5.0-7.0 H8 คือ candidates ถัดไป)
