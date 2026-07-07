# AF56 — Ambfix Ladder: S84c4369 Inverse RD 5.0-7.0 H8

วันที่: 2026-07-07
สถานะ: research/backtest-only, ยังไม่ wire เข้า live bot
กติกา: ambfix resolution (ดู `create_af1.md` / `create_ambfix_audit.md`)

## Baseline

```text
AF55 = AF54 + AMBFIX_INV_S84RUNc889_3.4-4.0_H12x402.161
```

| Metric | AF55 |
|---|---:|
| Avg $/day | 2357.84 |
| Min $/day | 2120.72 |
| Worst day | -1000.00 |

## Search (sweep2 cfg4369 บน AF55 base)

ย้อนกลับไปใช้ S84 screen index 4369 บน base ของ AF55 เพื่อดันกำไรให้ใกล้เคียง $2,500 

| Mode | Band | Hour | Best w | avg | min |
|---|---|---|---:|---:|---:|
| inverse | 5.0-7.0 | H8 | 587.714 | 2452.03 | 2270.46 |

## New Leg

```text
AMBFIX_INV_S84RUNc4369_5.0-7.0_H8 — inverse, RD 5.0 to 7.0, fill_hour == 8 BKK
```

- Raw trades: 6/6/7/7 ที่ 90/120/150/180d 
- Leg stats: binds floor at W=587.714

## New Champion

```text
AF56 = AF55 + AMBFIX_INV_S84RUNc4369_5.0-7.0_H8x587.714
```

| Metric | AF56 |
|---|---:|
| Avg $/day | 2452.03 |
| Min $/day | 2270.46 |
| Max losing-day streak | 3 |
| Worst day | -1000.00 |

## Weight Threshold

`af56_ambfix_s84c4369_inv_5.0-7.0_h8_probe.csv`: x587.714 ผ่าน / x587.715 fail

## No-Blow Guard

-1000.00 pass

## Verdict

```text
AF56 = AF55 + AMBFIX_INV_S84RUNc4369_5.0-7.0_H8x587.714
```

ชนะ AF55 อย่างขาดลอย ทั้ง avg (2357.84 → 2452.03) และ min (2120.72 → 2270.46)
เตรียมตัวทะลุ $2,500 ใน AF57!
