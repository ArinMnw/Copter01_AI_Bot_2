# S74 - Demo Portfolio Subset + All-in-4S Target Blend

สถานะ: research/backtest-only, ยังไม่ wire เข้า live bot

## เป้าหมาย

หา new champion ที่:

- ชนะ P13/P16 ด้านกำไรต่อวัน
- ผสม All-in-4S แบบ portfolio ได้
- มีทาง scale ไปถึงเป้า $1000/day

## Baseline ที่ใช้เทียบ

จาก `optimize_s72_vs_demo_portfolio.py` แบบ fixed-lot/live-style 0.01 lot ต่อ logical leg:

| Portfolio | Avg $/day 90-180d | Min PF | Max losing-day streak |
|---|---:|---:|---:|
| P13 | 62.32 | 1.07 | 5 |
| P16 | 61.68 | 1.05 | 5 |

หมายเหตุ: ตัวเลขนี้ต่างจาก backtest compounding เก่า เพราะใช้ fixed-lot ตาม `demo_portfolio.py` จริง

## S72 ก่อนแตก S74

S72 top = `P13 + S63x8 + S69x24 + S64x4`

| Window | $/day | PF | Streak |
|---|---:|---:|---:|
| 90d | 131.82 | 1.20 | 4 |
| 120d | 118.43 | 1.16 | 4 |
| 150d | 83.46 | 1.12 | 4 |
| 180d | 96.67 | 1.15 | 4 |

สรุป: ชนะ P13/P16 แต่ถ้าจะให้ทุก window >= $1000/day ต้อง scale 11.98x และ worst day ประมาณ -$14,014

## S74 Candidate

S74 ใช้ subset จาก P16 แทนการถือ P13/P16 ทั้งก้อน:

```text
Demo subset: B C E G H I M N P R
All-in-4S overlay: S63x4 + S69x32 + S64x8
```

แปลชื่อ leg:

- B = S34 Volume Breakout
- C = S36 FVG / ICT-SMC
- E = S38 Fibonacci OTE
- G = S40 Elliott proxy
- H = S41 RSI Divergence
- I = S42 CRT
- M = S46 Opening Range Breakout
- N = S47 SuperTrend
- P = S49 VWAP
- R = S56 PrevWeekHL
- S63/S69/S64 = All-in-4S research legs

ตัดออก: A, D, F, K, L, Q เพราะเป็นตัวถ่วงใน fixed-lot/current-window search

## S74 Fixed-Lot Result

| Window | $/day | PF | Streak | Worst day |
|---|---:|---:|---:|---:|
| 90d | 128.24 | 1.40 | 4 | -698.17 |
| 120d | 145.21 | 1.44 | 4 | -709.81 |
| 150d | 106.48 | 1.34 | 4 | -709.81 |
| 180d | 112.23 | 1.38 | 4 | -903.15 |

Summary:

- Min $/day = 106.48
- Avg $/day = 123.04
- Min PF = 1.34
- Max losing-day streak = 4

## S74T Target Scale

เพื่อให้ทุก window >= $1000/day:

```text
required scale = 1000 / 106.48 = 9.39x
```

ผลหลัง scale โดยประมาณ:

| Window | $/day scaled | Worst day scaled |
|---|---:|---:|
| 90d | 1204 | -6556 |
| 120d | 1364 | -6665 |
| 150d | 1000 | -6665 |
| 180d | 1054 | -8482 |

## Verdict

S74T เป็น candidate ที่ตรงเป้าเชิงตัวเลขที่สุดตอนนี้:

- ชนะ P13/P16
- ทุก window มากกว่า $1000/day หลัง scale
- PF ดีกว่า P13/P16 และ S72
- worst-day หลัง scale ดีกว่า S73 target-scale เดิมมาก (-$8.5k vs -$14k)

แต่ยังเป็น research-only และยังไม่ควร wire live จนกว่าจะเพิ่ม exposure guard:

- max simultaneous position/unit cap
- per-leg cap โดยเฉพาะ All-in-4S overlay
- account-size assumption สำหรับรับ worst-day อย่างน้อย $8.5k
- margin simulation จาก MT5 ก่อน deploy

## Files

- `optimize_s72_vs_demo_portfolio.py`
- `s72_vs_demo_portfolio_search.csv`
- `optimize_s73_target_scaling.py`
- `s73_target_scaling_audit.csv`
- `optimize_s74_subset_search.py`
- `s74_subset_search.csv`
