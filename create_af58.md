# AF58 — Ambfix Ladder: S84c3057 Inverse RD 4.0-5.0 H14

วันที่: 2026-07-07
สถานะ: research/backtest-only, ยังไม่ wire เข้า live bot
กติกา: ambfix resolution (ดู `create_af1.md` / `create_ambfix_audit.md`)

## Baseline

```text
AF57 = AF56 + AMBFIX_DIR_S84RUNc5505_5.0-7.0_H14x428.643
```

| Metric | AF57 |
|---|---:|
| Avg $/day | 2500.35 |
| Min $/day | 2300.13 |
| Worst day | -1000.00 |

## Search (sweep2 cfg3057 บน AF57 base)

นำ S84 screen index 3057 ซึ่งเป็นสายเนื้อแน่นไม้เยอะ มาอัดบนกราฟเพื่อเพิ่มความเสถียร 

| Mode | Band | Hour | Best w | avg | min |
|---|---|---|---:|---:|---:|
| inverse | 4.0-5.0 | H14 | 432.389 | 2534.43 | 2334.53 |

## New Leg

```text
AMBFIX_INV_S84RUNc3057_4.0-5.0_H14 — inverse, RD 4.0 to 5.0, fill_hour == 14 BKK
```

- Raw trades: 5/8/13/18 ที่ 90/120/150/180d  *(ไม้เยอะมาก!)*
- Leg stats: binds floor at W=432.389

## New Champion

```text
AF58 = AF57 + AMBFIX_INV_S84RUNc3057_4.0-5.0_H14x432.389
```

| Metric | AF58 |
|---|---:|
| Avg $/day | 2534.43 |
| Min $/day | 2334.53 |
| Max losing-day streak | 3 |
| Worst day | -1000.00 |

## Weight Threshold

`af58_ambfix_s84c3057_inv_4.0-5.0_h14_probe.csv`: x432.389 ผ่าน / x432.390 fail

## No-Blow Guard

-1000.00 pass

## Verdict

```text
AF58 = AF57 + AMBFIX_INV_S84RUNc3057_4.0-5.0_H14x432.389
```

ทะลุเป้า $2,500 แบบสบายๆ ชนะ AF57 ทั้ง avg (2500.35 → 2534.43) และ min (2300.13 → 2334.53) 
พร้อมจำนวนไม้เทรดช่วยค้ำพอร์ตที่ 18 ไม้/180 วัน
ไปต่อที่ AF59!
