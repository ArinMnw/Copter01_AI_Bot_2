# AF54 — Ambfix Ladder: S86c6275 Direct H14

วันที่: 2026-07-07
สถานะ: research/backtest-only, ยังไม่ wire เข้า live bot
กติกา: ambfix resolution (ดู `create_af1.md` / `create_ambfix_audit.md`)

## Baseline

```text
AF53 = AF52 + AMBFIX_DIR_S86RUNc4227_ALL_H16x56.402
```

| Metric | AF53 |
|---|---:|
| Avg $/day | 2265.25 |
| Min $/day | 2097.70 |
| Worst day | -1000.00 |

## Search (sweep2 cfg6275 บน AF53 base)

เปิด space จาก S86 screen index 6275 

| Mode | Band | Hour | Best w | avg | min |
|---|---|---|---:|---:|---:|
| direct | all | H14 | 136.450 | 2340.79 | 2111.20 |

*หมายเหตุ: ข้าม H13 เนื่องจาก W ชน cap 600 (degenerate)*

## New Leg

```text
AMBFIX_DIR_S86RUNc6275_ALL_H14 — direct, all risk_distance, fill_hour == 14 BKK
```

- Raw trades: 2/4/6/7 ที่ 90/120/150/180d 
- Leg stats: binds floor at W=136.450

## New Champion

```text
AF54 = AF53 + AMBFIX_DIR_S86RUNc6275_ALL_H14x136.450
```

| Metric | AF54 |
|---|---:|
| Avg $/day | 2340.79 |
| Min $/day | 2111.20 |
| Max losing-day streak | 3 |
| Worst day | -1000.00 |

## Weight Threshold

`af54_ambfix_s86c6275_dir_all_h14_probe.csv`: x136.450 ผ่าน / x136.451 fail

## No-Blow Guard

-1000.00 pass

## Verdict

```text
AF54 = AF53 + AMBFIX_DIR_S86RUNc6275_ALL_H14x136.450
```

ชนะ AF53 ทั้ง avg (2265.25 → 2340.79) และ min (2097.70 → 2111.20)
ไปต่อที่ AF55!
