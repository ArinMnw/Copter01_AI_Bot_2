# AF3 — Ambfix Ladder: Direct S84 RD 2.7-3.4 H12

วันที่: 2026-07-04
สถานะ: research/backtest-only, ยังไม่ wire เข้า live bot
กติกา: ambfix resolution (ดู `create_af1.md` / `create_ambfix_audit.md`)

## Baseline

```text
AF2 = AF1 + AMBFIX_DIR_S84_RD2.7_3.4_H10x196.726
```

| Metric | AF2 |
|---|---:|
| Avg $/day | 561.6673 |
| Min $/day | 508.8736 |
| Min PF | 4.61565 |
| Max streak | 3 |
| Worst day | -999.90831 |

## Search รอบนี้ (ambfix sweep บน AF2 base — top, ข้าม repeat: inverse 4.0-5.0 H17 = AF1)

| Mode | Band | Hour | Best w | avg | min |
|---|---|---|---:|---:|---:|
| **direct** | **2.7-3.4** | **H12** | **122** | **597.72** | **531.39** | ✅ ผู้ชนะ |
| direct | 5.0-7.0 | H17 | 92 | 592.25 | 533.62 | candidate AF4 |
| inverse | 3.4-4.0 | H11 | 324 | 591.52 | 534.96 | candidate |
| inverse | 4.0-5.0 | H22 | 258 | 579.29 | 534.87 | candidate |

## New Leg

```text
AMBFIX_DIR_S84_RD2.7_3.4_H12 — direct, `2.7 <= risk_distance <= 3.4`, fill_hour == 12 BKK
```

- Raw trades: 17/19/20/21 ที่ 90/120/150/180d
- Leg stats: lot_max 0.02, DD 0.82%, skipped 0

## New Champion

```text
AF3 = AF2 + AMBFIX_DIR_S84_RD2.7_3.4_H12x123.035
```

| Metric | AF3 |
|---|---:|
| Avg $/day | 598.0241 |
| Min $/day | 531.5803 |
| Min PF | 4.62670 |
| Max losing-day streak | 3 |
| Worst day | -999.90831 |

| Window | $/day | PF | Streak | Worst day | Raw trades |
|---:|---:|---:|---:|---:|---:|
| 90 | 620.4776 | 5.25917 | 2 | -999.90831 | 17 |
| 120 | 664.4666 | 5.71205 | 2 | -984.30288 | 19 |
| 150 | 575.5720 | 5.36376 | 3 | -998.76150 | 20 |
| 180 | 531.5803 | 4.62670 | 3 | -999.90790 | 21 |

## Weight Threshold

`af3_ambfix_dir_rdmin27_rd34_h12_probe.csv`: x123.035 ผ่าน / x123.036 fail

## No-Blow Guard

-999.91 pass / -1000 pass

## Look-Ahead Bias Audit

- Detection closed bar `j`, fill `j+1`, filters ใช้ข้อมูล ณ ตอนเข้าไม้
- M1 replay ตัดสินเฉพาะผลไม้ ไม่มี look-ahead; pessimistic fallback = ขอบล่าง
- Research/backtest-only

## Verdict

```text
AF3 = AF2 + AMBFIX_DIR_S84_RD2.7_3.4_H12x123.035
```

ชนะ AF2 ทั้ง avg (561.67 → 598.02) และ min (508.87 → 531.58) — ไล่ AF4 ต่อ
(direct 5.0-7.0 H17 / inverse 3.4-4.0 H11 คือ candidates ถัดไป)
