# AF15 — Ambfix Ladder: Inverse S84 RD 4.0-5.0 H15

วันที่: 2026-07-04
สถานะ: research/backtest-only, ยังไม่ wire เข้า live bot
กติกา: ambfix resolution (ดู `create_af1.md` / `create_ambfix_audit.md`)

## Baseline

```text
AF14 = AF13 + AMBFIX_DIR_S84_RD4.0_5.0_H18x138.139
```

| Metric | AF14 |
|---|---:|
| Avg $/day | 805.5693 |
| Min $/day | 732.3682 |
| Min PF | 5.66582 |
| Max streak | 3 |
| Worst day | -999.90950 |

## Search รอบนี้ (ambfix sweep บน AF14 base — top)

| Mode | Band | Hour | Best w | avg | min |
|---|---|---|---:|---:|---:|
| **inverse** | **4.0-5.0** | **H15** | **156** | **808.84** | **735.80** | ✅ ผู้ชนะ |
| inverse | 5.0-7.0 | H8 | 86 | 808.75 | 739.64 | candidate AF16 |
| direct | 4.0-5.0 | H8 | 10 | 808.54 | 734.14 | candidate |

## New Leg

```text
AMBFIX_INV_S84_RD4.0_5.0_H15 — inverse, `4.0 <= risk_distance <= 5.0`, fill_hour == 15 BKK
```

- Raw trades: 6/9/11/11 ที่ 90/120/150/180d
- Leg stats: lot_max 0.01, DD 0.83%, skipped 0

## New Champion

```text
AF15 = AF14 + AMBFIX_INV_S84_RD4.0_5.0_H15x156.917
```

| Metric | AF15 |
|---|---:|
| Avg $/day | 808.8552 |
| Min $/day | 735.8204 |
| Min PF | 5.69462 |
| Max losing-day streak | 3 |
| Worst day | -999.90950 |

| Window | $/day | PF | Streak | Worst day | Raw trades |
|---:|---:|---:|---:|---:|---:|
| 90 | 827.8744 | 6.27284 | 2 | -999.90854 | 6 |
| 120 | 881.4488 | 6.89170 | 2 | -999.90805 | 9 |
| 150 | 790.2773 | 6.47930 | 3 | -999.90950 | 11 |
| 180 | 735.8204 | 5.69462 | 3 | -999.90935 | 11 |

## Weight Threshold

`af15_ambfix_inv_rdmin40_rd50_h15_probe.csv`: x156.917 ผ่าน / x156.918 fail

## No-Blow Guard

-999.91 pass / -1000 pass

## Look-Ahead Bias Audit

- Detection closed bar `j`, fill `j+1`, filters ใช้ข้อมูล ณ ตอนเข้าไม้
- M1 replay ตัดสินเฉพาะผลไม้ ไม่มี look-ahead; pessimistic fallback = ขอบล่าง
- Research/backtest-only

## Verdict

```text
AF15 = AF14 + AMBFIX_INV_S84_RD4.0_5.0_H15x156.917
```

ชนะ AF14 ทั้ง avg (805.57 → 808.86) และ min (732.37 → 735.82) — ไล่ AF16 ต่อ
(INV 5.0-7.0 H8 / DIR 4.0-5.0 H8 คือ candidates ถัดไป; gain ต่อรอบเริ่มบางลง
ควรพิจารณาเปิดมิติใหม่: config index อื่น / preset tiny / S86 family ใต้ ambfix)
