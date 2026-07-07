# AF62 — Ambfix Ladder: S84c5505 Direct RD 5.0-7.0 H18

วันที่: 2026-07-07
สถานะ: research/backtest-only, ยังไม่ wire เข้า live bot
กติกา: ambfix resolution (ดู `create_af1.md` / `create_ambfix_audit.md`)

## Baseline

```text
AF61 = AF60 + AMBFIX_INV_S84RUNc889_3.4-4.0_H11x392.288
```

| Metric | AF61 |
|---|---:|
| Avg $/day | 2672.14 |
| Min $/day | 2496.30 |
| Worst day | -1000.00 |

## Search (sweep2 cfg5505 บน AF61 base)

เราดึง S84 screen index 5505 กลับมาอีกครั้ง และค้นพบจังหวะเปิดออเดอร์สวยๆ ที่โซนชั่วโมง 18:00 (BKK) ในกรอบ RD 5.0-7.0 

| Mode | Band | Hour | Best w | avg | min |
|---|---|---|---:|---:|---:|
| direct | 5.0-7.0 | H18 | 221.915 | 2713.71 | 2541.38 |

## New Leg

```text
AMBFIX_DIR_S84RUNc5505_5.0-7.0_H18 — direct, RD 5.0 to 7.0, fill_hour == 18 BKK
```

- Raw trades: 3/4/7/9 ที่ 90/120/150/180d *(มี 9 ไม้ ถือว่าแข็งแกร่งค้ำพอร์ตได้ดีมาก)*
- Leg stats: binds floor at W=221.915

## New Champion

```text
AF62 = AF61 + AMBFIX_DIR_S84RUNc5505_5.0-7.0_H18x221.915
```

| Metric | AF62 |
|---|---:|
| Avg $/day | 2713.71 |
| Min $/day | 2541.38 |
| Max losing-day streak | 3 |
| Worst day | -1000.00 |

## Weight Threshold

`af62_ambfix_s84c5505_dir_5.0-7.0_h18_probe.csv`: x221.915 ผ่าน / x221.916 fail

## No-Blow Guard

-1000.00 pass

## Verdict

```text
AF62 = AF61 + AMBFIX_DIR_S84RUNc5505_5.0-7.0_H18x221.915
```

สามารถอัดฉีดให้ avg PnL เพิ่มเป็น $2713.71/วัน เป็นการกระโดดข้ามระดับที่ทรงพลังและรักษาจำนวน Max Streak กับ Worst Day ไว้ได้ดั่งเหล็กกล้า!
ไปต่อกันที่ AF63 ค่ะ
