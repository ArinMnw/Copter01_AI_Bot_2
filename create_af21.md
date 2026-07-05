# AF21 — Ambfix Ladder: Direct S84 cfg6017 RD 5.0-7.0 H10

วันที่: 2026-07-04
สถานะ: research/backtest-only, ยังไม่ wire เข้า live bot
กติกา: ambfix resolution (ดู `create_af1.md` / `create_ambfix_audit.md`)
Config 6017: `S84_M30_lb48_rw0.35_wb1_eat0.12_fail0.08_op1_mb0.06_mr0.25_mid_revisit_sl0.2_rr1.2`
(ดู `create_af20.md`)

## Baseline

```text
AF20 = AF19 + AMBFIX_DIR_S84c6017_RD5.0_7.0_H17x584.897
```

| Metric | AF20 |
|---|---:|
| Avg $/day | 928.2432 |
| Min $/day | 865.1461 |
| Min PF | 6.21605 |
| Max streak | 3 |
| Worst day | -999.90965 |

## Search (sweep2 cfg6017 บน AF20 base — top; ข้าม legs 1 ไม้/ทุก window ชน cap = degenerate)

| Mode | Band | Hour | Best w | avg | min |
|---|---|---|---:|---:|---:|
| **direct** | **5.0-7.0** | **H10** | **344** | **961.32** | **907.10** | ✅ ผู้ชนะ |
| direct | 5.0-7.0 | H14 | 88 | 943.55 | 885.51 | candidate AF22 |
| inverse | 5.0-7.0 | H16 | 344 | 942.32 | 896.53 | candidate |

## New Leg

```text
AMBFIX_DIR_S84c6017_RD5.0_7.0_H10 — direct, `5.0 <= risk_distance <= 7.0`, fill_hour == 10 BKK
```

- Raw trades: 3/3/4/5 ที่ 90/120/150/180d — บางแต่ครบทุก window, floor bind ปกติ
- Leg stats: lot_max 0.01, DD 0.65%, skipped 0

## New Champion

```text
AF21 = AF20 + AMBFIX_DIR_S84c6017_RD5.0_7.0_H10x344.492
```

| Metric | AF21 |
|---|---:|
| Avg $/day | 961.3676 |
| Min $/day | 907.1550 |
| Min PF | 6.30188 |
| Max losing-day streak | 3 |
| Worst day | -999.90965 |

| Window | $/day | PF | Streak | Worst day | Raw trades |
|---:|---:|---:|---:|---:|---:|
| 90 | 980.7631 | 7.21793 | 2 | -999.90672 | 3 |
| 120 | 1028.5782 | 7.80714 | 2 | -999.90805 | 3 |
| 150 | 928.9741 | 6.30188 | 3 | -999.90965 | 4 |
| 180 | 907.1550 | 6.63873 | 3 | -999.90946 | 5 |

## Weight Threshold

`af21_ambfix_c6017_dir_rdmin50_rd70_h10_probe.csv`: x344.492 ผ่าน / x344.493 fail

## No-Blow Guard

-999.91 pass / -1000 pass

## Look-Ahead Bias Audit

- Detection closed bar `j`, fill `j+1`, filters ใช้ข้อมูล ณ ตอนเข้าไม้
- M1 replay ตัดสินเฉพาะผลไม้ ไม่มี look-ahead; pessimistic fallback = ขอบล่าง
- Research/backtest-only

## Verdict

```text
AF21 = AF20 + AMBFIX_DIR_S84c6017_RD5.0_7.0_H10x344.492
```

ชนะ AF20 ทั้ง avg (928.24 → 961.37) และ min (865.15 → 907.16) — ไล่ AF22 ต่อ
(cfg6017 เหลือ H14/H16; cfg5505/4369/889 + s86 family รอเข้าคิว)
