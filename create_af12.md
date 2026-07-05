# AF12 — Ambfix Ladder: Direct S84 RD 5.0-7.0 H20

วันที่: 2026-07-04
สถานะ: research/backtest-only, ยังไม่ wire เข้า live bot
กติกา: ambfix resolution (ดู `create_af1.md` / `create_ambfix_audit.md`)

## Baseline

```text
AF11 = AF10 + AMBFIX_DIR_S84_RD3.4_4.0_H22x274.789
```

| Metric | AF11 |
|---|---:|
| Avg $/day | 781.7078 |
| Min $/day | 716.1088 |
| Min PF | 5.71219 |
| Max streak | 3 |
| Worst day | -999.90950 |

## Search รอบนี้ (ambfix sweep บน AF11 base — top, ข้าม repeat: DIR 2.7-3.4 H10=AF2)

| Mode | Band | Hour | Best w | avg | min |
|---|---|---|---:|---:|---:|
| **direct** | **5.0-7.0** | **H20** | **54** | **791.77** | **728.64** | ✅ ผู้ชนะ |
| direct | 4.0-5.0 | H18 | 198 | 789.05 | 716.92 | candidate AF13 |
| inverse | 4.0-5.0 | H15 | 176 | 785.39 | 719.98 | candidate |
| inverse | 5.0-7.0 | H8 | 86 | 784.88 | 723.38 | candidate |

## New Leg

```text
AMBFIX_DIR_S84_RD5.0_7.0_H20 — direct, `5.0 <= risk_distance <= 7.0`, fill_hour == 20 BKK
```

- Raw trades: 19/26/29/29 ที่ 90/120/150/180d (leg เนื้อหนาที่สุดของ AF ladder)
- Leg stats: lot_max 0.01, DD 1.81%, skipped 10

## New Champion

```text
AF12 = AF11 + AMBFIX_DIR_S84_RD5.0_7.0_H20x54.139
```

| Metric | AF12 |
|---|---:|
| Avg $/day | 791.8009 |
| Min $/day | 728.6720 |
| Min PF | 5.79195 |
| Max losing-day streak | 3 |
| Worst day | -999.90950 |

| Window | $/day | PF | Streak | Worst day | Raw trades |
|---:|---:|---:|---:|---:|---:|
| 90 | 806.3686 | 6.54735 | 3 | -999.90672 | 19 |
| 120 | 855.2800 | 6.75884 | 2 | -999.90805 | 26 |
| 150 | 776.8828 | 6.77955 | 3 | -999.90950 | 29 |
| 180 | 728.6720 | 5.79195 | 3 | -999.90935 | 29 |

## Weight Threshold

`af12_ambfix_dir_rdmin50_rd70_h20_probe.csv`: x54.139 ผ่าน / x54.140 fail

## No-Blow Guard

-999.91 pass / -1000 pass

## Look-Ahead Bias Audit

- Detection closed bar `j`, fill `j+1`, filters ใช้ข้อมูล ณ ตอนเข้าไม้
- M1 replay ตัดสินเฉพาะผลไม้ ไม่มี look-ahead; pessimistic fallback = ขอบล่าง
- Research/backtest-only

## Verdict

```text
AF12 = AF11 + AMBFIX_DIR_S84_RD5.0_7.0_H20x54.139
```

ชนะ AF11 ทั้ง avg (781.71 → 791.80) และ min (716.11 → 728.67) — ไล่ AF13 ต่อ
(DIR 4.0-5.0 H18 / INV 4.0-5.0 H15 / INV 5.0-7.0 H8 คือ candidates ถัดไป)
