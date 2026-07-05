# AF2 — Ambfix Ladder: **Direct** S84 RD 2.7-3.4 H10 (leg direct ตัวแรกของทุก ladder)

วันที่: 2026-07-04
สถานะ: research/backtest-only, ยังไม่ wire เข้า live bot
กติกา: ambfix resolution (ดู `create_af1.md` / `create_ambfix_audit.md`)

## Baseline

```text
AF1 = S88 + AMBFIX_INV_S84_M15_OLDWICK_FOLLOW_RD4.0_5.0_H17x172.759
```

| Metric | AF1 |
|---|---:|
| Avg $/day | 522.9762 |
| Min $/day | 465.2004 |
| Min PF | 4.35870 |
| Max streak | 3 |
| Worst day | -999.90790 |

## Search รอบนี้ (ambfix sweep บน AF1 base — top)

| Mode | Band | Hour | Best w | avg | min |
|---|---|---|---:|---:|---:|
| **direct** | **2.7-3.4** | **H10** | **196** | **561.52** | **508.71** | ✅ ผู้ชนะ |
| direct | 2.7-3.4 | H12 | 122 | 559.03 | 487.72 | candidate AF3 |
| direct | 5.0-7.0 | H17 | 92 | 553.56 | 489.95 | candidate |
| inverse | 3.4-4.0 | H11 | 280 | 548.78 | 487.74 | candidate |
| inverse | 4.0-5.0 | H22 | 258 | 540.59 | 491.20 | candidate |

## New Leg

```text
AMBFIX_DIR_S84_M15_lb48_rw0.25_wb0.8_eat0.06_fail0.03_op1_mb0.06_mr0.35_rr_follow_sl0.2_rr0.9_Frdmin2.7_rd3.4_h10
```

- **Mode: DIRECT** (ตามทิศ S84 old-wick follow ไม่กลับฝั่ง) — เป็น leg direct
  ตัวแรกที่ขึ้น ladder ได้ เพราะกติกา ambfix คืนไม้ชนะที่ SL-first เคยขโมย
  (m1_tp = 62 ไม้ใน stream) ให้ฝั่ง direct
- Post-filter: `2.7 <= risk_distance <= 3.4`, Time filter: `fill_hour == 10` BKK
- Raw trades: 16/16/19/22 ที่ 90/120/150/180d
- Leg stats: lot_max 0.02, DD 1.76%, skipped 3
- Unresolved ambiguous 235 ไม้ของ stream ถูกปรับเป็น SL (แพ้) ตามกติกา pessimistic
  — leg นี้ชนะทั้งที่โดนปรับ

## New Champion

```text
AF2 = AF1 + AMBFIX_DIR_S84_RD2.7_3.4_H10x196.726
```

| Metric | AF2 |
|---|---:|
| Avg $/day | 561.6673 |
| Min $/day | 508.8736 |
| Min PF | 4.61565 |
| Max losing-day streak | 3 |
| Worst day | -999.90831 |

| Window | $/day | PF | Streak | Worst day | Raw trades |
|---:|---:|---:|---:|---:|---:|
| 90 | 568.1740 | 4.91714 | 2 | -999.90831 | 16 |
| 120 | 628.7454 | 5.68375 | 2 | -984.30288 | 16 |
| 150 | 540.8761 | 5.22097 | 3 | -998.76150 | 19 |
| 180 | 508.8736 | 4.61565 | 3 | -999.90790 | 22 |

## Weight Threshold

`af2_ambfix_dir_rdmin27_rd34_h10_probe.csv`: x196.726 ผ่าน / x196.727 fail

## No-Blow Guard

-999.91 pass / -1000 pass (floors ต่ำกว่านั้น fail จาก base เดิมที่ชิด -1000)

## Look-Ahead Bias Audit

- Detection closed bar `j`, fill `j+1`, filters ใช้ข้อมูล ณ ตอนเข้าไม้
- M1 replay ตัดสินเฉพาะผลไม้หลังเข้า ไม่แตะการเลือกไม้ — no look-ahead
- Pessimistic fallback = ขอบล่าง
- Research/backtest-only

## Verdict

```text
AF2 = AF1 + AMBFIX_DIR_S84_RD2.7_3.4_H10x196.726
```

ชนะ AF1 ทั้ง avg (522.98 → 561.67) และ min (465.20 → 508.87) ใต้กติกาซื่อสัตย์
— ไล่ AF3 ต่อ (direct 2.7-3.4 H12 / direct 5.0-7.0 H17 คือ candidates ถัดไป)
