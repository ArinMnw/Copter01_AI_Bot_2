# AF55 — Ambfix Ladder: S84c889 Inverse RD 3.4-4.0 H12

วันที่: 2026-07-07
สถานะ: research/backtest-only, ยังไม่ wire เข้า live bot
กติกา: ambfix resolution (ดู `create_af1.md` / `create_ambfix_audit.md`)

## Baseline

```text
AF54 = AF53 + AMBFIX_DIR_S86RUNc6275_ALL_H14x136.450
```

| Metric | AF54 |
|---|---:|
| Avg $/day | 2340.79 |
| Min $/day | 2111.20 |
| Worst day | -1000.00 |

## Search (sweep2 cfg889 บน AF54 base)

ย้อนกลับไปใช้ S84 screen index 889 (champion เก่า) บน base ของ AF54 เพื่อดึง profit จาก zone ที่ยังไม่ถูก absorb.

| Mode | Band | Hour | Best w | avg | min |
|---|---|---|---:|---:|---:|
| inverse | 3.4-4.0 | H12 | 402.161 | 2357.84 | 2120.72 |

## New Leg

```text
AMBFIX_INV_S84RUNc889_3.4-4.0_H12 — inverse, RD 3.4 to 4.0, fill_hour == 12 BKK
```

- Raw trades: 3/4/6/8 ที่ 90/120/150/180d 
- Leg stats: binds floor at W=402.161

## New Champion

```text
AF55 = AF54 + AMBFIX_INV_S84RUNc889_3.4-4.0_H12x402.161
```

| Metric | AF55 |
|---|---:|
| Avg $/day | 2357.84 |
| Min $/day | 2120.72 |
| Max losing-day streak | 3 |
| Worst day | -1000.00 |

## Weight Threshold

`af55_ambfix_s84c889_inv_3.4-4.0_h12_probe.csv`: x402.161 ผ่าน / x402.162 fail

## No-Blow Guard

-1000.00 pass

## Verdict

```text
AF55 = AF54 + AMBFIX_INV_S84RUNc889_3.4-4.0_H12x402.161
```

ชนะ AF54 ทั้ง avg (2340.79 → 2357.84) และ min (2111.20 → 2120.72)
ไปต่อที่ AF56!
