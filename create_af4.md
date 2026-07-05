# AF4 — Ambfix Ladder: Direct S84 RD 5.0-7.0 H17

วันที่: 2026-07-04
สถานะ: research/backtest-only, ยังไม่ wire เข้า live bot
กติกา: ambfix resolution (ดู `create_af1.md` / `create_ambfix_audit.md`)

## Baseline

```text
AF3 = AF2 + AMBFIX_DIR_S84_RD2.7_3.4_H12x123.035
```

| Metric | AF3 |
|---|---:|
| Avg $/day | 598.0241 |
| Min $/day | 531.5803 |
| Min PF | 4.62670 |
| Max streak | 3 |
| Worst day | -999.90831 |

## Search รอบนี้ (ambfix sweep บน AF3 base — top, ข้าม repeat: inverse 4.0-5.0 H17=AF1)

| Mode | Band | Hour | Best w | avg | min |
|---|---|---|---:|---:|---:|
| **direct** | **5.0-7.0** | **H17** | **92** | **628.61** | **556.33** | ✅ ผู้ชนะ |
| inverse | 3.4-4.0 | H11 | 324 | 627.88 | 557.66 | candidate AF5 |
| inverse | 4.0-5.0 | H22 | 258 | 615.64 | 557.58 | candidate |
| direct | 3.4-4.0 | H22 | 214 | 612.82 | 538.54 | candidate |

## New Leg

```text
AMBFIX_DIR_S84_RD5.0_7.0_H17 — direct, `5.0 <= risk_distance <= 7.0`, fill_hour == 17 BKK
```

- SL กว้างมาก (5-7 USD) = แท่งกำกวมแทบเป็นศูนย์โดยธรรมชาติ — โปรไฟล์เดียวกับ
  P13/P16 ที่รอดบน live
- Raw trades: 12/14/15/16 ที่ 90/120/150/180d
- Leg stats: lot_max 0.01, DD 1.10%, skipped 0

## New Champion

```text
AF4 = AF3 + AMBFIX_DIR_S84_RD5.0_7.0_H17x92.141
```

| Metric | AF4 |
|---|---:|
| Avg $/day | 628.6538 |
| Min $/day | 556.3663 |
| Min PF | 4.98067 |
| Max losing-day streak | 3 |
| Worst day | -999.90831 |

| Window | $/day | PF | Streak | Worst day | Raw trades |
|---:|---:|---:|---:|---:|---:|
| 90 | 661.4087 | 5.91470 | 2 | -999.90831 | 12 |
| 120 | 694.3817 | 6.35572 | 2 | -971.17841 | 14 |
| 150 | 602.4588 | 5.87700 | 3 | -998.76150 | 15 |
| 180 | 556.3663 | 4.98067 | 3 | -999.90790 | 16 |

## Weight Threshold

`af4_ambfix_dir_rdmin50_rd70_h17_probe.csv`: x92.141 ผ่าน / x92.142 fail

## No-Blow Guard

-999.91 pass / -1000 pass

## Look-Ahead Bias Audit

- Detection closed bar `j`, fill `j+1`, filters ใช้ข้อมูล ณ ตอนเข้าไม้
- M1 replay ตัดสินเฉพาะผลไม้ ไม่มี look-ahead; pessimistic fallback = ขอบล่าง
- Research/backtest-only

## Verdict

```text
AF4 = AF3 + AMBFIX_DIR_S84_RD5.0_7.0_H17x92.141
```

ชนะ AF3 ทั้ง avg (598.02 → 628.65) และ min (531.58 → 556.37) — ไล่ AF5 ต่อ
(inverse 3.4-4.0 H11 / inverse 4.0-5.0 H22 คือ candidates ถัดไป)
