# AF17 — Ambfix Ladder: Inverse S84 RD 5.0-7.0 H8

วันที่: 2026-07-04
สถานะ: research/backtest-only, ยังไม่ wire เข้า live bot
กติกา: ambfix resolution (ดู `create_af1.md` / `create_ambfix_audit.md`)

## Baseline

```text
AF16 = AF15 + AMBFIX_INV_S84_RD2.0_2.7_H9x158.086
```

| Metric | AF16 |
|---|---:|
| Avg $/day | 827.5897 |
| Min $/day | 747.5012 |
| Min PF | 5.69157 |
| Max streak | 3 |
| Worst day | -999.90950 |

## Search รอบนี้ (ambfix sweep บน AF16 base — top, ข้าม repeats: INV 4.0-5.0 H17=AF1,
INV 4.0-5.0 H15=AF15)

| Mode | Band | Hour | Best w | avg | min |
|---|---|---|---:|---:|---:|
| **inverse** | **5.0-7.0** | **H8** | **86** | **830.77** | **754.77** | ✅ ผู้ชนะ |
| inverse | 3.4-4.0 | H10 | 46 | 828.03 | 748.30 | candidate AF18 |

## New Leg

```text
AMBFIX_INV_S84_RD5.0_7.0_H8 — inverse, `5.0 <= risk_distance <= 7.0`, fill_hour == 8 BKK
```

- Raw trades: 13/19/24/29 ที่ 90/120/150/180d
- Leg stats: lot_max 0.01, DD 1.59%, skipped 5

## New Champion

```text
AF17 = AF16 + AMBFIX_INV_S84_RD5.0_7.0_H8x86.290
```

| Metric | AF17 |
|---|---:|
| Avg $/day | 830.7769 |
| Min $/day | 754.7975 |
| Min PF | 5.69111 |
| Max losing-day streak | 3 |
| Worst day | -999.90950 |

| Window | $/day | PF | Streak | Worst day | Raw trades |
|---:|---:|---:|---:|---:|---:|
| 90 | 874.3162 | 7.17266 | 2 | -999.90672 | 13 |
| 120 | 910.2860 | 7.65022 | 2 | -999.90805 | 19 |
| 150 | 783.7081 | 5.69111 | 3 | -999.90950 | 24 |
| 180 | 754.7975 | 5.78060 | 3 | -999.90935 | 29 |

## Weight Threshold

`af17_ambfix_inv_rdmin50_rd70_h8_probe.csv`: x86.290 ผ่าน / x86.291 fail

## No-Blow Guard

-999.91 pass / -1000 pass

## Look-Ahead Bias Audit

- Detection closed bar `j`, fill `j+1`, filters ใช้ข้อมูล ณ ตอนเข้าไม้
- M1 replay ตัดสินเฉพาะผลไม้ ไม่มี look-ahead; pessimistic fallback = ขอบล่าง
- Research/backtest-only

## Verdict

```text
AF17 = AF16 + AMBFIX_INV_S84_RD5.0_7.0_H8x86.290
```

ชนะ AF16 ทั้ง avg (827.59 → 830.78) และ min (747.50 → 754.80) — space config-28
ใกล้อิ่ม (~+$3/รอบ) รอผล config screen 8,192 ตัว (s84) + s86 family เพื่อเปิด
space ใหม่สำหรับ AF18+
