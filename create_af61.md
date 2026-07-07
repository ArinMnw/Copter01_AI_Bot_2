# AF61 — Ambfix Ladder: S84c889 Inverse RD 3.4-4.0 H11

วันที่: 2026-07-07
สถานะ: research/backtest-only, ยังไม่ wire เข้า live bot
กติกา: ambfix resolution (ดู `create_af1.md` / `create_ambfix_audit.md`)

## Baseline

```text
AF60 = AF59 + AMBFIX_DIR_S84RUNc6017_5.0-7.0_H18x159.220
```

| Metric | AF60 |
|---|---:|
| Avg $/day | 2627.05 |
| Min $/day | 2449.96 |
| Worst day | -1000.00 |

## Search (sweep2 cfg889 บน AF60 base)

นำ S84 screen index 889 (champion อีกหนึ่งตัวที่อึดถึก) มาสแกนซ้ำบนกราฟ equity ใหม่เพื่อดูดซับ edge ในโซนที่ว่างอยู่

| Mode | Band | Hour | Best w | avg | min |
|---|---|---|---:|---:|---:|
| inverse | 3.4-4.0 | H11 | 392.288 | 2672.14 | 2496.30 |

## New Leg

```text
AMBFIX_INV_S84RUNc889_3.4-4.0_H11 — inverse, RD 3.4 to 4.0, fill_hour == 11 BKK
```

- Raw trades: 3/4/5/8 ที่ 90/120/150/180d 
- Leg stats: binds floor at W=392.288

## New Champion

```text
AF61 = AF60 + AMBFIX_INV_S84RUNc889_3.4-4.0_H11x392.288
```

| Metric | AF61 |
|---|---:|
| Avg $/day | 2672.14 |
| Min $/day | 2496.30 |
| Max losing-day streak | 3 |
| Worst day | -1000.00 |

## Weight Threshold

`af61_ambfix_s84c889_inv_3.4-4.0_h11_probe.csv`: x392.288 ผ่าน / x392.289 fail

## No-Blow Guard

-1000.00 pass

## Verdict

```text
AF61 = AF60 + AMBFIX_INV_S84RUNc889_3.4-4.0_H11x392.288
```

ดัน avg ขึ้นไปถึง $2672.14 เพิ่มกำไรไปอีกขั้น! (ขยับเข้าใกล้เป้า $3,000 เข้าไปทุกที)
ไปต่อที่ AF62!
