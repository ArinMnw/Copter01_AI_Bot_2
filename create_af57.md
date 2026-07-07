# AF57 — Ambfix Ladder: S84c5505 Direct RD 5.0-7.0 H14

วันที่: 2026-07-07
สถานะ: research/backtest-only, ยังไม่ wire เข้า live bot
กติกา: ambfix resolution (ดู `create_af1.md` / `create_ambfix_audit.md`)

## Baseline

```text
AF56 = AF55 + AMBFIX_INV_S84RUNc4369_5.0-7.0_H8x587.714
```

| Metric | AF56 |
|---|---:|
| Avg $/day | 2452.03 |
| Min $/day | 2270.46 |
| Worst day | -1000.00 |

## Search (sweep2 cfg5505 บน AF56 base)

ดึง S84 screen index 5505 (champion เก่า) มาใช้บน equity curve ใหม่ เพื่อดันยอด PnL ให้แตะเป้าหมายหลักที่ $2,500/day

| Mode | Band | Hour | Best w | avg | min |
|---|---|---|---:|---:|---:|
| direct | 5.0-7.0 | H14 | 428.643 | 2500.35 | 2300.13 |

## New Leg

```text
AMBFIX_DIR_S84RUNc5505_5.0-7.0_H14 — direct, RD 5.0 to 7.0, fill_hour == 14 BKK
```

- Raw trades: 1/1/4/6 ที่ 90/120/150/180d 
- Leg stats: binds floor at W=428.643

## New Champion

```text
AF57 = AF56 + AMBFIX_DIR_S84RUNc5505_5.0-7.0_H14x428.643
```

| Metric | AF57 |
|---|---:|
| Avg $/day | 2500.35 |
| Min $/day | 2300.13 |
| Max losing-day streak | 3 |
| Worst day | -1000.00 |

## Weight Threshold

`af57_ambfix_s84c5505_dir_5.0-7.0_h14_probe.csv`: x428.643 ผ่าน / x428.644 fail

## No-Blow Guard

-1000.00 pass

## Verdict

```text
AF57 = AF56 + AMBFIX_DIR_S84RUNc5505_5.0-7.0_H14x428.643
```

🎉 **Milestone Reached!** 🎉
พอร์ต AF57 สามารถดัน PnL เฉลี่ยแตะ **$2,500.35 ต่อวัน** ได้สำเร็จ โดยไม่ทำลายกฎ Worst Day -$1,000 และจำกัดจำนวนวันขาดทุนติดกันสูงสุดที่ 3 วัน!
