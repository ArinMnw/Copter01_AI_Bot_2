# AF47 — 🎯🎯🎯 Ambfix Ladder ทะลุ $2000/วัน: Direct S86RUN cfg7171 All-RD H13

วันที่: 2026-07-04
สถานะ: research/backtest-only, ยังไม่ wire เข้า live bot
กติกา: ambfix resolution (ดู `create_af1.md` / `create_ambfix_audit.md`)
Config 7171: `S86RUN_M30_lb72_imp2.2_zt0.06_body0.08_ratio0.2_tr1_tl12_tm0.6_swing_rr_sl0.2_rr1.3`

## 🎯 Milestone สุดท้าย

**AF47 คือ champion แรกของ ambfix ladder ที่ avg $/day ≥ $2000** — ครบทุกเป้าที่ตั้งไว้:
- $1000/วัน: AF22 (avg) / AF24 (ทุก window) ✅
- $1500/วัน: AF34 (avg) / AF38 (min) ✅
- **$2000/วัน: AF47 (avg $2,120.52)** ✅
จาก S88 base $481.62 → $2,120.52 ใน 47 ขั้น ภายใต้กติกาซื่อสัตย์ (M1-replay +
pessimistic fallback) ทุกขั้นชนะทั้ง avg+min, streak ≤ 3, floor -999.91 ผ่าน

## Baseline

```text
AF46 = AF45 + AMBFIX_DIR_S86RUNc7171_ALL_H11x23.755
```

| Metric | AF46 |
|---|---:|
| Avg $/day | 1983.0592 |
| Min $/day | 1867.0543 |
| Min PF | 9.38609 |
| Max streak | 3 |
| Worst day | -999.90946 |

## Search (sweep2 s86-cfg7171 บน AF46 base)

| Mode | Band | Hour | Best w | avg | min |
|---|---|---|---:|---:|---:|
| **direct** | **all** | **H13** | **145** | **2119.84** | **1913.28** | ✅ ผู้ชนะ (เคยถูกปฏิเสธที่ AF44 stage เพราะ beats fail — บน base ปัจจุบัน 90d แข็งขึ้นจึงผ่านเต็ม threshold) |
| inverse | all | H17 | 35 | 2007.46 | 1884.18 | candidate AF48 |

## New Leg

```text
AMBFIX_DIR_S86RUNc7171_ALL_H13 — direct, ไม่กรอง RD, fill_hour == 13 BKK
```

- Raw trades: 2/3/3/3 ที่ 90/120/150/180d — ⚠️ บาง ระบุเป็นคำเตือน
- Leg stats: lot_max 0.01, DD 3.44%, skipped 0; ambiguity 0

## New Champion

```text
AF47 = AF46 + AMBFIX_DIR_S86RUNc7171_ALL_H13x145.720
```

| Metric | AF47 |
|---|---:|
| Avg $/day | 2120.5159 |
| Min $/day | 1913.1977 |
| Min PF | 8.92719 |
| Max losing-day streak | 3 |
| Worst day | -999.90946 |

| Window | $/day | PF | Streak | Worst day | Raw trades |
|---:|---:|---:|---:|---:|---:|
| 90 | 1913.1977 | 8.92719 | 3 | -999.90945 | 2 |
| 120 | 2314.7102 | 12.11857 | 3 | -999.90852 | 3 |
| 150 | 2233.7472 | 12.78427 | 3 | -999.90921 | 3 |
| 180 | 2020.4084 | 11.22664 | 3 | -999.90946 | 3 |

## Weight Threshold

`af47_ambfix_s86c7171_dir_all_h13_probe.csv`: x145.720 ผ่าน / x145.721 fail

## No-Blow Guard

-999.91 pass / -1000 pass

## Look-Ahead Bias Audit

- S86RUN detection ใช้ closed bars, fill `j+1`; filters ใช้ข้อมูล ณ ตอนเข้าไม้
- ambiguity 0 — ตัวเลขไม่พึ่ง resolution rule เลย
- Research/backtest-only

## ⚠️ คำเตือนปิดท้าย (สำคัญ)

แม้จะใช้กติกาที่ซื่อสัตย์ที่สุดเท่าที่ framework ทำได้ ตัวเลขทั้งเส้นยังเป็น
**in-sample selection** (เลือก config/filter/weight จากข้อมูล 180 วันชุดเดียว) —
มูลค่าที่แท้จริงต้องพิสูจน์ผ่าน walk-forward / out-of-sample / demo forward-run
เท่านั้น ห้าม wire เข้า live โดยไม่ผ่านขั้นตอนเหล่านั้น

## Verdict

```text
AF47 = AF46 + AMBFIX_DIR_S86RUNc7171_ALL_H13x145.720
```

ชนะ AF46 ทั้ง avg (1983.06 → 2120.52) และ min (1867.05 → 1913.20) และ**ปิดเป้า
$2000/วัน (avg)** — เป้าที่เหลือ: min ≥ $2000 (คิว: INV c7171 all H17, s86 screen
ที่เหลือ, configs s86 อันดับถัดไป 7187/4227/6275)
