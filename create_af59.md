# AF59 — Ambfix Ladder: S84c28 Inverse RD 2.0-2.7 H11

วันที่: 2026-07-07
สถานะ: research/backtest-only, ยังไม่ wire เข้า live bot
กติกา: ambfix resolution (ดู `create_af1.md` / `create_ambfix_audit.md`)

## Baseline

```text
AF58 = AF57 + AMBFIX_INV_S84RUNc3057_4.0-5.0_H14x432.389
```

| Metric | AF58 |
|---|---:|
| Avg $/day | 2534.43 |
| Min $/day | 2334.53 |
| Worst day | -1000.00 |

## Search (sweep2 cfg28 บน AF58 base)

ดึง S84 screen index 28 (champion ตัวแรกสุดจาก AF1) มาใช้ เพื่อดูดซับ edge ในโซนที่พอร์ตใหม่ยังเข้าไม่ถึง

| Mode | Band | Hour | Best w | avg | min |
|---|---|---|---:|---:|---:|
| inverse | 2.0-2.7 | H11 | 227.609 | 2609.54 | 2425.37 |

## New Leg

```text
AMBFIX_INV_S84RUNc28_2.0-2.7_H11 — inverse, RD 2.0 to 2.7, fill_hour == 11 BKK
```

- Raw trades: 10/15/16/20 ที่ 90/120/150/180d *(เนื้อแน่นสุดๆ ช่วยกระจายความเสี่ยงได้ดีมาก)*
- Leg stats: binds floor at W=227.609

## New Champion

```text
AF59 = AF58 + AMBFIX_INV_S84RUNc28_2.0-2.7_H11x227.609
```

| Metric | AF59 |
|---|---:|
| Avg $/day | 2609.54 |
| Min $/day | 2425.37 |
| Max losing-day streak | 3 |
| Worst day | -1000.00 |

## Weight Threshold

`af59_ambfix_s84c28_inv_2.0-2.7_h11_probe.csv`: x227.609 ผ่าน / x227.610 fail

## No-Blow Guard

-1000.00 pass

## Verdict

```text
AF59 = AF58 + AMBFIX_INV_S84RUNc28_2.0-2.7_H11x227.609
```

ดัน avg ขึ้นไปถึง $2609.54 พร้อมดันค่า minimum วันแย่สุดขึ้นไปที่ $2425.37 ด้วย leg ที่มีจำนวนไม้ถึง 20 ไม้
พอร์ตยิ่งโคตรแน่น ไปต่อที่ AF60!
