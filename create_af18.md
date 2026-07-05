# AF18 — Ambfix Ladder: Direct S84 RD 4.0-5.0 H14

วันที่: 2026-07-04
สถานะ: research/backtest-only, ยังไม่ wire เข้า live bot
กติกา: ambfix resolution (ดู `create_af1.md` / `create_ambfix_audit.md`)

## Baseline

```text
AF17 = AF16 + AMBFIX_INV_S84_RD5.0_7.0_H8x86.290
```

| Metric | AF17 |
|---|---:|
| Avg $/day | 830.7769 |
| Min $/day | 754.7975 |
| Min PF | 5.69111 |
| Max streak | 3 |
| Worst day | -999.90950 |

## Search รอบนี้ (ambfix sweep บน AF17 base — top, ข้าม repeat: INV 4.0-5.0 H17=AF1)

| Mode | Band | Hour | Best w | avg | min |
|---|---|---|---:|---:|---:|
| **direct** | **4.0-5.0** | **H14** | **84** | **842.14** | **763.41** | ✅ ผู้ชนะ |
| direct | 5.0-7.0 | H20 | 4 | 831.52 | 755.73 | ❌ leg เดิม AF12 (re-weight) |
| direct | 4.0-5.0 | H18 | 14 | 831.30 | 754.86 | ❌ leg เดิม AF14 (re-weight) |
| inverse | 3.4-4.0 | H10 | 46 | 831.22 | 755.60 | candidate AF19 |

## New Leg

```text
AMBFIX_DIR_S84_RD4.0_5.0_H14 — direct, `4.0 <= risk_distance <= 5.0`, fill_hour == 14 BKK
```

- Raw trades: 13/14/14/16 ที่ 90/120/150/180d
- Leg stats: lot_max 0.01, DD 0.55%, skipped 0

## New Champion

```text
AF18 = AF17 + AMBFIX_DIR_S84_RD4.0_5.0_H14x85.289
```

| Metric | AF18 |
|---|---:|
| Avg $/day | 842.3136 |
| Min $/day | 763.5443 |
| Min PF | 5.80023 |
| Max losing-day streak | 3 |
| Worst day | -999.90950 |

| Window | $/day | PF | Streak | Worst day | Raw trades |
|---:|---:|---:|---:|---:|---:|
| 90 | 889.3744 | 7.40465 | 2 | -999.90672 | 13 |
| 120 | 921.5797 | 7.86087 | 2 | -999.90805 | 14 |
| 150 | 794.7558 | 5.82266 | 3 | -999.90950 | 14 |
| 180 | 763.5443 | 5.80023 | 3 | -999.90935 | 16 |

## Weight Threshold

`af18_ambfix_dir_rdmin40_rd50_h14_probe.csv`: x85.289 ผ่าน / x85.290 fail

## No-Blow Guard

-999.91 pass / -1000 pass

## Look-Ahead Bias Audit

- Detection closed bar `j`, fill `j+1`, filters ใช้ข้อมูล ณ ตอนเข้าไม้
- M1 replay ตัดสินเฉพาะผลไม้ ไม่มี look-ahead; pessimistic fallback = ขอบล่าง
- Research/backtest-only

## Verdict

```text
AF18 = AF17 + AMBFIX_DIR_S84_RD4.0_5.0_H14x85.289
```

ชนะ AF17 ทั้ง avg (830.78 → 842.31) และ min (754.80 → 763.54) — ไล่ AF19 ต่อ
(INV 3.4-4.0 H10 คิวถัดไป; config screens ยังรันเบื้องหลัง)
