# AF60 — Ambfix Ladder: S84c6017 Direct RD 5.0-7.0 H18

วันที่: 2026-07-07
สถานะ: research/backtest-only, ยังไม่ wire เข้า live bot
กติกา: ambfix resolution (ดู `create_af1.md` / `create_ambfix_audit.md`)

## Baseline

```text
AF59 = AF58 + AMBFIX_INV_S84RUNc28_2.0-2.7_H11x227.609
```

| Metric | AF59 |
|---|---:|
| Avg $/day | 2609.54 |
| Min $/day | 2425.37 |
| Worst day | -1000.00 |

## Search (sweep2 cfg6017 บน AF59 base)

ดึง S84 screen index 6017 ซึ่งเป็น config หลักในช่วง AF20-AF24 กลับมาสแกนช่องโหว่ที่เหลือ 

| Mode | Band | Hour | Best w | avg | min |
|---|---|---|---:|---:|---:|
| direct | 5.0-7.0 | H18 | 159.220 | 2627.05 | 2449.96 |

## New Leg

```text
AMBFIX_DIR_S84RUNc6017_5.0-7.0_H18 — direct, RD 5.0 to 7.0, fill_hour == 18 BKK
```

- Raw trades: 2/3/5/7 ที่ 90/120/150/180d 
- Leg stats: binds floor at W=159.220

## New Champion

```text
AF60 = AF59 + AMBFIX_DIR_S84RUNc6017_5.0-7.0_H18x159.220
```

| Metric | AF60 |
|---|---:|
| Avg $/day | 2627.05 |
| Min $/day | 2449.96 |
| Max losing-day streak | 3 |
| Worst day | -1000.00 |

## Weight Threshold

`af60_ambfix_s84c6017_dir_5.0-7.0_h18_probe.csv`: x159.220 ผ่าน / x159.221 fail

## No-Blow Guard

-1000.00 pass

## Verdict

```text
AF60 = AF59 + AMBFIX_DIR_S84RUNc6017_5.0-7.0_H18x159.220
```

ดัน avg ขึ้นไปถึง $2627.05 เรามาไกลเกิน $2,500 แล้ว! 
ไปต่อที่ AF61!
