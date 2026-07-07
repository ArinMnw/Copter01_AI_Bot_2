# AF52 — Ambfix Ladder: S86c7187 Direct H11

วันที่: 2026-07-07
สถานะ: research/backtest-only, ยังไม่ wire เข้า live bot
กติกา: ambfix resolution (ดู `create_af1.md` / `create_ambfix_audit.md`)

## Baseline

```text
AF51 = AF50 + AMBFIX_INV_S86RUNc7171_ALL_H18x20.491
```

| Metric | AF51 |
|---|---:|
| Avg $/day | 2189.5502 |
| Min $/day | 2001.0534 |
| Worst day | -999.90946 |

## Search (sweep2 cfg7187 บน AF51 base)

เปิด space `S86RUN_M30_lb72_imp2.2_zt0.06_body0.14_ratio0.2_tr1_tl16_tm1_swing_rr_sl1.3_rr1.3` (cfg7187) ซึ่งได้จาก screen S86 8,192 ชุด (PF 1.6+)

| Mode | Band | Hour | Best w | avg | min |
|---|---|---|---:|---:|---:|
| direct | all | H11 | 24.114 | 2225.09 | 2053.53 |

*หมายเหตุ: ข้าม INVERSE_H18 และ DIRECT_H10 เนื่องจาก W ชน cap 600 (degenerate 1-3 ไม้).*

## New Leg

```text
AMBFIX_DIR_S86RUNc7187_ALL_H11 — direct, all risk_distance, fill_hour == 11 BKK
```

- Raw trades: 6/6/7/7 ที่ 90/120/150/180d 
- Leg stats: binds floor at W=24.114

## New Champion

```text
AF52 = AF51 + AMBFIX_DIR_S86RUNc7187_ALL_H11x24.114
```

| Metric | AF52 |
|---|---:|
| Avg $/day | 2225.09 |
| Min $/day | 2053.53 |
| Max losing-day streak | 3 |
| Worst day | -1000.00 |

## Weight Threshold

`af52_ambfix_s86c7187_dir_all_h11_probe.csv`: x24.114 ผ่าน / x24.115 fail

## No-Blow Guard

-1000.00 pass

## Verdict

```text
AF52 = AF51 + AMBFIX_DIR_S86RUNc7187_ALL_H11x24.114
```

ชนะ AF51 ทั้ง avg (2189.55 → 2225.09) และ min (2001.05 → 2053.53) ผ่าน validation 
ไปต่อที่ AF53!
