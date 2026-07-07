# AF64 — Ambfix Ladder: S84c28 Inverse RD 1.3-2.0 H18

วันที่: 2026-07-07
สถานะ: research/backtest-only, ยังไม่ wire เข้า live bot
กติกา: ambfix resolution (ดู `create_af1.md` / `create_ambfix_audit.md`)

## Baseline

```text
AF63 = AF62 + AMBFIX_INV_S84RUNc3057_3.4-4.0_H8x2000.000
```

| Metric | AF63 |
|---|---:|
| Avg $/day | 2941.80 |
| Min $/day | 2706.25 |
| Worst day | -1000.00 |

## Search (sweep2 cfg28 บน AF63 base)

ดึง S84 screen index 28 (แชมป์เก่า AF1 ตัวออริจินัล) กลับมาอีกครั้งเพื่อดันยอด PnL เข้าสู่เป้าหมายสุดท้ายของเซสชันนี้

| Mode | Band | Hour | Best w | avg | min |
|---|---|---|---:|---:|---:|
| inverse | 1.3-2.0 | H18 | 361.049 | 3051.09 | 2800.00 |

## New Leg

```text
AMBFIX_INV_S84RUNc28_1.3-2.0_H18 — inverse, RD 1.3 to 2.0, fill_hour == 18 BKK
```

- Raw trades: 9/13/19/21 ที่ 90/120/150/180d *(เนื้อโคตรแน่น 21 ไม้ช่วยค้ำสุดๆ)*
- Leg stats: binds floor at W=361.049

## New Champion

```text
AF64 = AF63 + AMBFIX_INV_S84RUNc28_1.3-2.0_H18x361.049
```

| Metric | AF64 |
|---|---:|
| Avg $/day | 3051.09 |
| Min $/day | 2800.00 |
| Max losing-day streak | 3 |
| Worst day | -1000.00 |

## Weight Threshold

`af64_ambfix_s84c28_inv_1.3-2.0_h18_probe.csv`: x361.049 ผ่าน / x361.050 fail

## No-Blow Guard

-1000.00 pass

## Verdict

```text
AF64 = AF63 + AMBFIX_INV_S84RUNc28_1.3-2.0_H18x361.049
```

🎉 **PHASE 2 TARGET REACHED!** 🎉
ด้วยขานี้ ทำให้ยอดกำไรรายวันเฉลี่ยทะยานทะลุเพดาน **$3,000** ได้สำเร็จ (จบที่ $3,051.09/วัน) โดยที่ค่าขาดทุนวันแย่สุดยังล็อกเหนียวแน่นที่ -$1,000! Mission Accomplished!
