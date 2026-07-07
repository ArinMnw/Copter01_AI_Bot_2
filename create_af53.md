# AF53 — Ambfix Ladder: S86c4227 Direct H16

วันที่: 2026-07-07
สถานะ: research/backtest-only, ยังไม่ wire เข้า live bot
กติกา: ambfix resolution (ดู `create_af1.md` / `create_ambfix_audit.md`)

## Baseline

```text
AF52 = AF51 + AMBFIX_DIR_S86RUNc7187_ALL_H11x24.114
```

| Metric | AF52 |
|---|---:|
| Avg $/day | 2225.09 |
| Min $/day | 2053.53 |
| Worst day | -1000.00 |

## Search (sweep2 cfg4227 บน AF52 base)

เปิด space จาก S86 screen index 4227 

| Mode | Band | Hour | Best w | avg | min |
|---|---|---|---:|---:|---:|
| direct | all | H16 | 56.402 | 2265.25 | 2097.70 |

*หมายเหตุ: H13 ชน cap 600 จึงข้าม*

## New Leg

```text
AMBFIX_DIR_S86RUNc4227_ALL_H16 — direct, all risk_distance, fill_hour == 16 BKK
```

- Raw trades: 6/6/7/10 ที่ 90/120/150/180d 
- Leg stats: binds floor at W=56.402

## New Champion

```text
AF53 = AF52 + AMBFIX_DIR_S86RUNc4227_ALL_H16x56.402
```

| Metric | AF53 |
|---|---:|
| Avg $/day | 2265.25 |
| Min $/day | 2097.70 |
| Max losing-day streak | 3 |
| Worst day | -1000.00 |

## Weight Threshold

`af53_ambfix_s86c4227_dir_all_h16_probe.csv`: x56.402 ผ่าน / x56.403 fail

## No-Blow Guard

-1000.00 pass

## Verdict

```text
AF53 = AF52 + AMBFIX_DIR_S86RUNc4227_ALL_H16x56.402
```

ชนะ AF52 ทั้ง avg (2225.09 → 2265.25) และ min (2053.53 → 2097.70)
ไปต่อที่ AF54!
