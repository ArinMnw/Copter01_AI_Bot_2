# AF19 — Ambfix Ladder: Inverse S84 RD 3.4-4.0 H10 (ปิดท้าย config-28 space)

วันที่: 2026-07-04
สถานะ: research/backtest-only, ยังไม่ wire เข้า live bot
กติกา: ambfix resolution (ดู `create_af1.md` / `create_ambfix_audit.md`)

## Baseline

```text
AF18 = AF17 + AMBFIX_DIR_S84_RD4.0_5.0_H14x85.289
```

| Metric | AF18 |
|---|---:|
| Avg $/day | 842.3136 |
| Min $/day | 763.5443 |
| Min PF | 5.80023 |
| Max streak | 3 |
| Worst day | -999.90950 |

## Search รอบนี้

Sweep บน AF18 base: top candidates เกือบทั้งหมดเป็น re-weight ของ leg เดิม
(AF1/AF12/AF14/AF15) — **leg ใหม่เหลือตัวเดียว**:

| Mode | Band | Hour | Best w | avg | min |
|---|---|---|---:|---:|---:|
| **inverse** | **3.4-4.0** | **H10** | **46** | **842.76** | **764.34** | ✅ ผู้ชนะ (gain เล็ก) |

⚠️ **Space "config-28 × RD band × hour" ใต้ ambfix อิ่มตัวแล้ว** (gain รอบนี้
~+$0.45/วัน) — AF20+ ต้องมาจาก space ใหม่: config index อื่น / S86 family
(screen 8,192 configs × 2 families กำลังรันอยู่)

## New Leg

```text
AMBFIX_INV_S84_RD3.4_4.0_H10 — inverse, `3.4 <= risk_distance <= 4.0`, fill_hour == 10 BKK
```

- Raw trades: 6/6/11/13 ที่ 90/120/150/180d
- Leg stats: lot_max 0.01, DD 0.73%, skipped 0

## New Champion

```text
AF19 = AF18 + AMBFIX_INV_S84_RD3.4_4.0_H10x46.265
```

| Metric | AF19 |
|---|---:|
| Avg $/day | 842.7606 |
| Min $/day | 764.3488 |
| Min PF | 5.76921 |
| Max losing-day streak | 3 |
| Worst day | -999.90965 |

| Window | $/day | PF | Streak | Worst day | Raw trades |
|---:|---:|---:|---:|---:|---:|
| 90 | 889.3230 | 7.40997 | 2 | -999.90672 | 6 |
| 120 | 921.5412 | 7.81263 | 2 | -999.90805 | 6 |
| 150 | 795.8292 | 5.76921 | 3 | -999.90965 | 11 |
| 180 | 764.3488 | 5.77906 | 3 | -999.90935 | 13 |

## Weight Threshold

`af19_ambfix_inv_rdmin34_rd40_h10_probe.csv`: x46.265 ผ่าน / x46.266 fail

## No-Blow Guard

-999.91 pass / -1000 pass

## Look-Ahead Bias Audit

- Detection closed bar `j`, fill `j+1`, filters ใช้ข้อมูล ณ ตอนเข้าไม้
- M1 replay ตัดสินเฉพาะผลไม้ ไม่มี look-ahead; pessimistic fallback = ขอบล่าง
- Research/backtest-only

## Verdict

```text
AF19 = AF18 + AMBFIX_INV_S84_RD3.4_4.0_H10x46.265
```

ชนะ AF18 ทั้ง avg (842.31 → 842.76) และ min (763.54 → 764.35) — config-28 space
ปิดฉาก รอผล config screen เพื่อเริ่ม AF20 จาก space ใหม่
