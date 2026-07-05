# AF22 — 🎯 Ambfix Ladder ทะลุ $1000/วัน: Direct S84 cfg6017 RD 5.0-7.0 H14

วันที่: 2026-07-04
สถานะ: research/backtest-only, ยังไม่ wire เข้า live bot
กติกา: ambfix resolution (ดู `create_af1.md` / `create_ambfix_audit.md`)
Config 6017: `S84_M30_lb48_rw0.35_wb1_eat0.12_fail0.08_op1_mb0.06_mr0.25_mid_revisit_sl0.2_rr1.2`

## 🎯 Milestone

**AF22 คือ champion แรกของ ambfix ladder ที่ avg $/day ≥ $1000** ภายใต้กติกาที่
เข้มกว่า ladder เดิม (M1 ตัดสินแท่งกำกวม + unresolved ปรับแพ้เสมอ) — จาก S88 base
$481.62 → $1,003.83 ใน 22 ขั้น เป้าถัดไป: min ≥ $1000 → $1500 → $2000

## Baseline

```text
AF21 = AF20 + AMBFIX_DIR_S84c6017_RD5.0_7.0_H10x344.492
```

| Metric | AF21 |
|---|---:|
| Avg $/day | 961.3676 |
| Min $/day | 907.1550 |
| Min PF | 6.30188 |
| Max streak | 3 |
| Worst day | -999.90965 |

## Search (sweep2 cfg6017 บน AF21 base — top; ข้าม 1-ไม้ degenerate ที่ชน cap)

| Mode | Band | Hour | Best w | avg | min |
|---|---|---|---:|---:|---:|
| **direct** | **5.0-7.0** | **H14** | **244** | **1003.82** | **963.63** | ✅ ผู้ชนะ |
| inverse | 5.0-7.0 | H16 | 344 | 975.44 | 938.54 | candidate AF23 |

## New Leg

```text
AMBFIX_DIR_S84c6017_RD5.0_7.0_H14 — direct, `5.0 <= risk_distance <= 7.0`, fill_hour == 14 BKK
```

- Raw trades: 2/2/5/8 ที่ 90/120/150/180d — บาง (2 ไม้@90d) ระบุเป็นคำเตือน
- Leg stats: lot_max 0.01, DD 0.64%, skipped 0

## New Champion

```text
AF22 = AF21 + AMBFIX_DIR_S84c6017_RD5.0_7.0_H14x244.089
```

| Metric | AF22 |
|---|---:|
| Avg $/day | 1003.8306 |
| Min $/day | 963.6480 |
| Min PF | 6.61060 |
| Max losing-day streak | 3 |
| Worst day | -999.90965 |

| Window | $/day | PF | Streak | Worst day | Raw trades |
|---:|---:|---:|---:|---:|---:|
| 90 | 1014.8542 | 7.43407 | 2 | -999.90672 | 2 |
| 120 | 1054.1465 | 7.97635 | 2 | -999.90805 | 2 |
| 150 | 982.6737 | 6.61060 | 3 | -999.90965 | 5 |
| 180 | 963.6480 | 6.95569 | 3 | -999.90946 | 8 |

## Weight Threshold

`af22_ambfix_c6017_dir_rdmin50_rd70_h14_probe.csv`: x244.089 ผ่าน / x244.090 fail

## No-Blow Guard

-999.91 pass / -1000 pass

## Look-Ahead Bias Audit

- Detection closed bar `j`, fill `j+1`, filters ใช้ข้อมูล ณ ตอนเข้าไม้
- M1 replay ตัดสินเฉพาะผลไม้ ไม่มี look-ahead; pessimistic fallback = ขอบล่าง
- Research/backtest-only

## ⚠️ คำเตือน

แม้กติกา ambfix จะซื่อสัตย์กว่าเดิมมาก ตัวเลขก็ยังเป็น in-sample selection
(เลือก config/filter/weight จากข้อมูลชุดเดียวกัน) — ก่อน deploy ต้องผ่าน
walk-forward / out-of-sample validation เสมอ

## Verdict

```text
AF22 = AF21 + AMBFIX_DIR_S84c6017_RD5.0_7.0_H14x244.089
```

ชนะ AF21 ทั้ง avg (961.37 → 1003.83) และ min (907.16 → 963.65) และ**ทะลุเป้า
$1000/วัน (avg) ภายใต้กติกาซื่อสัตย์** — ไล่ AF23 ต่อ (เป้า: min ≥ $1000)
