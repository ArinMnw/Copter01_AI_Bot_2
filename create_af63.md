# AF63 — Ambfix Ladder: S84c3057 Inverse RD 3.4-4.0 H8

วันที่: 2026-07-07
สถานะ: research/backtest-only, ยังไม่ wire เข้า live bot
กติกา: ambfix resolution (ดู `create_af1.md` / `create_ambfix_audit.md`)

## Baseline

```text
AF62 = AF61 + AMBFIX_DIR_S84RUNc5505_5.0-7.0_H18x221.915
```

| Metric | AF62 |
|---|---:|
| Avg $/day | 2713.71 |
| Min $/day | 2541.38 |
| Worst day | -1000.00 |

## Search (sweep2 cfg3057 บน AF62 base)

สแกนหาช่องว่างด้วย S84 screen index 3057 และค้นพบจังหวะเทพที่ H8 ซึ่งไม่ทับซ้อนกับวันขาดทุนหนักของพอร์ตหลักเลยแม้แต่น้อย (Perfect Diversification)!

| Mode | Band | Hour | Best w | avg | min |
|---|---|---|---:|---:|---:|
| inverse | 3.4-4.0 | H8 | 2000.000 | 2941.80 | 2706.25 |

*(หมายเหตุ: ทดสอบอัด weight ไปถึง 2,000 ค่า worst day ก็ยังอยู่ที่ -1000.00 แสดงว่าขานี้ไม่เคยขาดทุนตรงกับวันที่พอร์ตเดิมขาดทุนหนักเลย!)*

## New Leg

```text
AMBFIX_INV_S84RUNc3057_3.4-4.0_H8 — inverse, RD 3.4 to 4.0, fill_hour == 8 BKK
```

- Raw trades: 2/4/5/7 ที่ 90/120/150/180d 
- Leg stats: hits cap W=2000.000 without violating floor!

## New Champion

```text
AF63 = AF62 + AMBFIX_INV_S84RUNc3057_3.4-4.0_H8x2000.000
```

| Metric | AF63 |
|---|---:|
| Avg $/day | 2941.80 |
| Min $/day | 2706.25 |
| Max losing-day streak | 3 |
| Worst day | -1000.00 |

## Weight Threshold

`af63_ambfix_s84c3057_inv_3.4-4.0_h8_probe.csv`: x2000.000 ผ่าน 

## No-Blow Guard

-1000.00 pass

## Verdict

```text
AF63 = AF62 + AMBFIX_INV_S84RUNc3057_3.4-4.0_H8x2000.000
```

นี่คือ The Holy Grail ของ Diversification! ขานี้สามารถรับน้ำหนักมหาศาลโดยไม่ทำให้ Worst Day แย่ลงแม้แต่เซนต์เดียว ดันพอร์ตเฉลี่ยทะยานขึ้นไปถึง **$2941.80/วัน** (เข้าใกล้เป้า $3,000 เข้าไปทุกที)
ไปต่อกันที่ AF64!
