# AF16 — Ambfix Ladder: Inverse S84 RD 2.0-2.7 H9

วันที่: 2026-07-04
สถานะ: research/backtest-only, ยังไม่ wire เข้า live bot
กติกา: ambfix resolution (ดู `create_af1.md` / `create_ambfix_audit.md`)
หมายเหตุ: base chain ผ่านการ audit แล้ว สะอาด — ดู `create_base_chain_audit.md`

## Baseline

```text
AF15 = AF14 + AMBFIX_INV_S84_RD4.0_5.0_H15x156.917
```

| Metric | AF15 |
|---|---:|
| Avg $/day | 808.8552 |
| Min $/day | 735.8204 |
| Min PF | 5.69462 |
| Max streak | 3 |
| Worst day | -999.90950 |

## Search รอบนี้ (ambfix sweep บน AF15 base — top)

| Mode | Band | Hour | Best w | avg | min |
|---|---|---|---:|---:|---:|
| **inverse** | **2.0-2.7** | **H9** | **158** | **827.58** | **747.49** | ✅ ผู้ชนะ |
| inverse | 5.0-7.0 | H8 | 86 | 812.03 | 743.09 | candidate AF17 |
| direct | 4.0-5.0 | H8 | 10 | 811.82 | 737.60 | candidate |

## New Leg

```text
AMBFIX_INV_S84_RD2.0_2.7_H9 — inverse, `2.0 <= risk_distance <= 2.7`, fill_hour == 9 BKK
```

- Raw trades: 10/13/20/25 ที่ 90/120/150/180d
- Leg stats: lot_max 0.02, DD 1.44%, skipped 10

## New Champion

```text
AF16 = AF15 + AMBFIX_INV_S84_RD2.0_2.7_H9x158.086
```

| Metric | AF16 |
|---|---:|
| Avg $/day | 827.5897 |
| Min $/day | 747.5012 |
| Min PF | 5.69157 |
| Max losing-day streak | 3 |
| Worst day | -999.90950 |

| Window | $/day | PF | Streak | Worst day | Raw trades |
|---:|---:|---:|---:|---:|---:|
| 90 | 874.8435 | 6.86185 | 2 | -999.90854 | 10 |
| 120 | 909.0348 | 7.20840 | 2 | -999.90805 | 13 |
| 150 | 778.9794 | 5.69157 | 3 | -999.90950 | 20 |
| 180 | 747.5012 | 5.79332 | 3 | -999.90935 | 25 |

## Weight Threshold

`af16_ambfix_inv_rdmin20_rd27_h9_probe.csv`: x158.086 ผ่าน / x158.087 fail

## No-Blow Guard

-999.91 pass / -1000 pass

## Look-Ahead Bias Audit

- Detection closed bar `j`, fill `j+1`, filters ใช้ข้อมูล ณ ตอนเข้าไม้
- M1 replay ตัดสินเฉพาะผลไม้ ไม่มี look-ahead; pessimistic fallback = ขอบล่าง
- Research/backtest-only

## Verdict

```text
AF16 = AF15 + AMBFIX_INV_S84_RD2.0_2.7_H9x158.086
```

ชนะ AF15 ทั้ง avg (808.86 → 827.59) และ min (735.82 → 747.50) — ไล่ AF17 ต่อ
(INV 5.0-7.0 H8 / DIR 4.0-5.0 H8 คิวถัดไป; config screen 8,192 ตัว × s84/s86
กำลังรันเบื้องหลังเพื่อเปิด space ใหม่)
