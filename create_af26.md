# AF26 — Ambfix Ladder: Direct S84 cfg5505 RD 5.0-7.0 H14

วันที่: 2026-07-04
สถานะ: research/backtest-only, ยังไม่ wire เข้า live bot
กติกา: ambfix resolution (ดู `create_af1.md` / `create_ambfix_audit.md`)
Config 5505: `S84_M30_lb48_rw0.35_wb0.8_eat0.12_fail0.08_op1_mb0.06_mr0.25_mid_revisit_sl0.2_rr1.2`

## Baseline

```text
AF25 = AF24 + AMBFIX_INV_S84c5505_RD5.0_7.0_H11x121.543
```

| Metric | AF25 |
|---|---:|
| Avg $/day | 1047.2843 |
| Min $/day | 1017.3800 |
| Min PF | 6.53130 |
| Max streak | 3 |
| Worst day | -999.90965 |

## Search (sweep2 cfg5505 บน AF25 base — ข้าม degenerate 4 ตัวที่ชน cap รวม INV H16
ที่ stress-cap ≈ 0)

| Mode | Band | Hour | Best w | avg | min |
|---|---|---|---:|---:|---:|
| **direct** | **5.0-7.0** | **H14** | **114** | **1061.39** | **1039.75** | ✅ ผู้ชนะ |
| inverse | 4.0-5.0 | H17 | 92 | 1052.89 | 1021.71 | candidate AF27 |

## New Leg

```text
AMBFIX_DIR_S84c5505_RD5.0_7.0_H14 — direct, `5.0 <= risk_distance <= 7.0`, fill_hour == 14 BKK
```

- Raw trades: 1/1/4/7 ที่ 90/120/150/180d — ⚠️ บาง (1 ไม้@90d)
- Leg stats: lot_max 0.01, DD 0.64%, skipped 0

## New Champion

```text
AF26 = AF25 + AMBFIX_DIR_S84c5505_RD5.0_7.0_H14x114.571
```

| Metric | AF26 |
|---|---:|
| Avg $/day | 1061.4651 |
| Min $/day | 1039.8614 |
| Min PF | 6.57251 |
| Max losing-day streak | 3 |
| Worst day | -999.90965 |

| Window | $/day | PF | Streak | Worst day | Raw trades |
|---:|---:|---:|---:|---:|---:|
| 90 | 1072.3415 | 6.57251 | 2 | -999.90820 | 1 |
| 120 | 1088.1299 | 7.29949 | 2 | -999.90805 | 1 |
| 150 | 1045.5278 | 6.87109 | 3 | -999.90965 | 4 |
| 180 | 1039.8614 | 7.57052 | 3 | -999.90946 | 7 |

## Weight Threshold

`af26_ambfix_c5505_dir_rdmin50_rd70_h14_probe.csv`: x114.571 ผ่าน / x114.572 fail

## No-Blow Guard

-999.91 pass / -1000 pass

## Look-Ahead Bias Audit

- Detection closed bar `j`, fill `j+1`, filters ใช้ข้อมูล ณ ตอนเข้าไม้
- M1 replay ตัดสินเฉพาะผลไม้ ไม่มี look-ahead; pessimistic fallback = ขอบล่าง
- Research/backtest-only

## Verdict

```text
AF26 = AF25 + AMBFIX_DIR_S84c5505_RD5.0_7.0_H14x114.571
```

ชนะ AF25 ทั้ง avg (1047.28 → 1061.47) และ min (1017.38 → 1039.86) — ไล่ AF27 ต่อ
(INV c5505 4.0-5.0 H17 / cfg4369 / cfg3057 / รอ s86 screen)
