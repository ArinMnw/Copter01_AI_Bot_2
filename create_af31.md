# AF31 — Ambfix Ladder: Inverse S84 cfg3057 RD 3.4-4.0 H11

วันที่: 2026-07-04
สถานะ: research/backtest-only, ยังไม่ wire เข้า live bot
กติกา: ambfix resolution (ดู `create_af1.md` / `create_ambfix_audit.md`)
Config 3057: `S84_M15_lb72_rw0.25_wb1_eat0.12_fail0.08_op0_mb0.12_mr0.35_mid_revisit_sl0.2_rr1.2`

## Baseline

```text
AF30 = AF29 + AMBFIX_INV_S84c3057_RD2.7_3.4_H13x525.853
```

| Metric | AF30 |
|---|---:|
| Avg $/day | 1349.7852 |
| Min $/day | 1305.0917 |
| Min PF | 7.48585 |
| Max streak | 3 |
| Worst day | -999.90965 |

## Search (sweep2 cfg3057 บน AF30 base — ข้าม degenerate 1-2 ไม้ชน cap 4 ตัว)

| Mode | Band | Hour | Best w | avg | min |
|---|---|---|---:|---:|---:|
| **inverse** | **3.4-4.0** | **H11** | **320** | **1383.20** | **1326.14** | ✅ ผู้ชนะ |
| inverse | 2.0-2.7 | H11 | 436 | 1378.11 | 1313.42 | บาง 3 ไม้ — candidate |

## New Leg

```text
AMBFIX_INV_S84c3057_RD3.4_4.0_H11 — inverse, `3.4 <= risk_distance <= 4.0`, fill_hour == 11 BKK
```

- Raw trades: 3/4/5/8 ที่ 90/120/150/180d
- Leg stats: lot_max 0.01, DD 0.55%, skipped 0

## New Champion

```text
AF31 = AF30 + AMBFIX_INV_S84c3057_RD3.4_4.0_H11x321.025
```

| Metric | AF31 |
|---|---:|
| Avg $/day | 1383.3074 |
| Min $/day | 1326.2080 |
| Min PF | 7.66922 |
| Max losing-day streak | 3 |
| Worst day | -999.90965 |

| Window | $/day | PF | Streak | Worst day | Raw trades |
|---:|---:|---:|---:|---:|---:|
| 90 | 1379.0670 | 7.66922 | 2 | -999.90820 | 3 |
| 120 | 1419.5128 | 9.19030 | 2 | -999.90805 | 4 |
| 150 | 1408.4416 | 9.37100 | 3 | -999.90965 | 5 |
| 180 | 1326.2080 | 8.73828 | 3 | -999.90946 | 8 |

## Weight Threshold

`af31_ambfix_c3057_inv_rdmin34_rd40_h11_probe.csv`: x321.025 ผ่าน / x321.026 fail

## No-Blow Guard

-999.91 pass / -1000 pass

## Look-Ahead Bias Audit

- Detection closed bar `j`, fill `j+1`, filters ใช้ข้อมูล ณ ตอนเข้าไม้
- M1 replay ตัดสินเฉพาะผลไม้ ไม่มี look-ahead; pessimistic fallback = ขอบล่าง
- Research/backtest-only

## Verdict

```text
AF31 = AF30 + AMBFIX_INV_S84c3057_RD3.4_4.0_H11x321.025
```

ชนะ AF30 ทั้ง avg (1349.79 → 1383.31) และ min (1305.09 → 1326.21) — เหลือ ~$117
ถึงเป้า $1500
