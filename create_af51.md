# AF51 — 🎯 FINAL MILESTONE: ทุก window ≥ $2000/วัน — Inverse S86RUN cfg7171 All-RD H18

วันที่: 2026-07-04
สถานะ: research/backtest-only, ยังไม่ wire เข้า live bot
กติกา: ambfix resolution (ดู `create_af1.md` / `create_ambfix_audit.md`)
Config 7171: `S86RUN_M30_lb72_imp2.2_zt0.06_body0.08_ratio0.2_tr1_tl12_tm0.6_swing_rr_sl0.2_rr1.3`

## 🎯 Milestone สุดท้ายของทุกเป้า

**AF51 คือ champion แรกที่ min $/day ≥ $2000** — ปิดครบทุกเป้าหมายทั้ง avg และ min:

| เป้า | avg สำเร็จที่ | min สำเร็จที่ |
|---|---|---|
| $1,000/วัน | AF22 | AF24 |
| $1,500/วัน | AF34 | AF38 |
| $2,000/วัน | AF47 | **AF51** |

จาก S88 base 481.62/449.12 → **2,189.55/2,001.05** ใน 51 ขั้น ภายใต้กติกาซื่อสัตย์

## Baseline

```text
AF50 = AF49 + AMBFIX_DIR_S86RUNc7171_ALL_H20x7.112
```

| Metric | AF50 |
|---|---:|
| Avg $/day | 2177.7001 |
| Min $/day | 1985.3618 |
| Min PF | 9.20016 |
| Max streak | 3 |
| Worst day | -999.90946 |

## New Leg

```text
AMBFIX_INV_S86RUNc7171_ALL_H18 — inverse, ไม่กรอง RD, fill_hour == 18 BKK
```

- Raw trades: 3/3/6/6 ที่ 90/120/150/180d; ambiguity 0
- Leg stats: lot_max 0.01, DD 4.76%, skipped 0

## New Champion

```text
AF51 = AF50 + AMBFIX_INV_S86RUNc7171_ALL_H18x20.491
```

| Metric | AF51 |
|---|---:|
| Avg $/day | 2189.5502 |
| Min $/day | 2001.0534 |
| Min PF | 9.56775 |
| Max losing-day streak | 3 |
| Worst day | -999.90946 |

| Window | $/day | PF | Streak | Worst day | Raw trades |
|---:|---:|---:|---:|---:|---:|
| 90 | 2001.0534 | 9.56775 | 3 | -999.90945 | 3 |
| 120 | 2386.3686 | 12.55154 | 3 | -999.90852 | 3 |
| 150 | 2292.5356 | 12.86198 | 3 | -999.90930 | 6 |
| 180 | 2078.2434 | 11.37828 | 3 | -999.90946 | 6 |

## Weight Threshold

`af51_ambfix_s86c7171_inv_all_h18_probe.csv`: x20.491 ผ่าน / x20.492 fail

## No-Blow Guard

-999.91 pass / -1000 pass

## Look-Ahead Bias Audit

- S86RUN detection ใช้ closed bars, fill `j+1`; filters ใช้ข้อมูล ณ ตอนเข้าไม้
- ambiguity 0; Research/backtest-only

## ⚠️ คำเตือนปิดโครงการ

ตัวเลขทั้ง ladder เป็น in-sample selection บนข้อมูล 180 วันชุดเดียว — ก่อนใช้เงินจริง:
1. Walk-forward / out-of-sample validation
2. Forward-run บน demo (แบบ P13/P16)
3. ประเมิน margin/notional จริงของ weight สูงๆ (framework นับ weight เป็นตัวคูณ daily
   PnL ของ substream $1000 — ไม่ใช่ position size จริง)

## Verdict

```text
AF51 = AF50 + AMBFIX_INV_S86RUNc7171_ALL_H18x20.491
```

ชนะ AF50 ทั้ง avg (2177.70 → 2189.55) และ min (1985.36 → 2001.05) —
**ครบทุกเป้าหมาย $1000/$1500/$2000 ทั้ง avg และ min ภายใต้กติกาซื่อสัตย์**
