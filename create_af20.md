# AF20 — Ambfix Ladder: เปิด config ใหม่ครั้งแรก! Direct S84 cfg6017 (M30) RD 5.0-7.0 H17

วันที่: 2026-07-04
สถานะ: research/backtest-only, ยังไม่ wire เข้า live bot
กติกา: ambfix resolution (ดู `create_af1.md` / `create_ambfix_audit.md`)

## ที่มา — Config Screen 8,192 ตัว

Screen micro grid ทั้ง 8,192 configs ของ S84 family ใต้ ambfix @180d
(per-trade PF, ทั้ง direct/inverse) — ครั้งแรกที่ใช้ config อื่นนอกจาก index 28:

| Config | TF | n | dir_sum | dir_PF | หมายเหตุ |
|---|---|---:|---:|---:|---|
| **6017** | **M30** | 921 | **+1311.4** | **1.17** | ✅ ดีสุด — เลือกใช้ |
| 5505 | M30 | 946 | +1195.6 | 1.15 | คิวถัดไป |
| 4369 | M30 | 1014 | +1109.2 | 1.13 | คิว |
| 889 | M15 | 1972 | (inverse +791.8) | 1.07 | คิวฝั่ง inverse |
| อ้างอิง 28 | M15 | 1920 | -368.7 | 0.92 | config เดิมของ ladder — whole-stream ติดลบ! |

ข้อสังเกตสำคัญ: config 28 เดิม whole-stream **ติดลบทั้ง direct และ inverse** — ค่าที่
ladder รีดออกมาได้มาจาก slicing ล้วน ๆ ส่วน config ใหม่เริ่มจาก stream ที่บวกจริง

## Config 6017

```text
S84_M30_lb48_rw0.35_wb1_eat0.12_fail0.08_op1_mb0.06_mr0.25_mid_revisit_sl0.2_rr1.2
```

- TF M30 (แท่งใหญ่ + SL 0.2 ATR ของ M30 → กว้างกว่า config 28 มาก)
- Target mode: mid / Mode: revisit / RR 1.2
- **Ambiguity ทั้ง stream แค่ 10 ไม้** (เทียบ 371 ของ config 28) = โปรไฟล์สะอาดแบบ P13/P16

## Baseline

```text
AF19 = AF18 + AMBFIX_INV_S84_RD3.4_4.0_H10x46.265
```

| Metric | AF19 |
|---|---:|
| Avg $/day | 842.7606 |
| Min $/day | 764.3488 |
| Min PF | 5.76921 |
| Max streak | 3 |
| Worst day | -999.90965 |

## Search (sweep2 cfg6017 บน AF19 base — top; ข้าม legs 1 ไม้/ทุก window ที่ชน cap 600 = degenerate)

| Mode | Band | Hour | Best w | avg | min |
|---|---|---|---:|---:|---:|
| **direct** | **5.0-7.0** | **H17** | **584** | **928.11** | **864.99** | ✅ ผู้ชนะ |
| direct | 5.0-7.0 | H10 | 344 | 875.84 | 806.30 | candidate AF21 |
| direct | 5.0-7.0 | H14 | 88 | 858.07 | 784.72 | candidate |
| inverse | 5.0-7.0 | H16 | 344 | 856.83 | 795.73 | candidate |

## New Leg

```text
AMBFIX_DIR_S84c6017_RD5.0_7.0_H17 — direct, `5.0 <= risk_distance <= 7.0`, fill_hour == 17 BKK
```

- Raw trades: 3/4/5/7 ที่ 90/120/150/180d — บางแต่มีไม้ครบทุก window และ floor bind
  ปกติ (x584.897 < cap)
- Leg stats: lot_max 0.01, DD 0.71%, skipped 0

## New Champion

```text
AF20 = AF19 + AMBFIX_DIR_S84c6017_RD5.0_7.0_H17x584.897
```

| Metric | AF20 |
|---|---:|
| Avg $/day | 928.2432 |
| Min $/day | 865.1461 |
| Min PF | 6.21605 |
| Max losing-day streak | 3 |
| Worst day | -999.90965 |

| Window | $/day | PF | Streak | Worst day | Raw trades |
|---:|---:|---:|---:|---:|---:|
| 90 | 949.5674 | 7.39777 | 2 | -999.90672 | 3 |
| 120 | 1005.1814 | 8.03399 | 2 | -999.90805 | 4 |
| 150 | 893.0781 | 6.21605 | 3 | -999.90965 | 5 |
| 180 | 865.1461 | 6.37170 | 3 | -999.90946 | 7 |

## Weight Threshold

`af20_ambfix_c6017_dir_rdmin50_rd70_h17_probe.csv`: x584.897 ผ่าน / x584.898 fail

## No-Blow Guard

-999.91 pass / -1000 pass

## Look-Ahead Bias Audit

- Detection closed bar `j`, fill `j+1`, filters ใช้ข้อมูล ณ ตอนเข้าไม้
- Config selection มาจาก screen ใต้ ambfix (in-sample selection เช่นเดียวกับทุกชั้น)
- M1 replay ตัดสินเฉพาะผลไม้ ไม่มี look-ahead; pessimistic fallback = ขอบล่าง
- Research/backtest-only

## Verdict

```text
AF20 = AF19 + AMBFIX_DIR_S84c6017_RD5.0_7.0_H17x584.897
```

ชนะ AF19 ทั้ง avg (842.76 → 928.24) และ min (764.35 → 865.15) — ก้าวกระโดดใหญ่สุด
ของ AF ladder จากการเปิด config space ใหม่ ไล่ AF21 ต่อ (cfg6017 มี candidates
เหลือ + cfg5505/4369/889 + s86 family ยังรอ screen)
