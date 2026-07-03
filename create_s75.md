# S75 - P16 + All-in-4S Champion Formula Blend

สถานะ: research/backtest-only, ยังไม่ wire เข้า live bot

## เป้าหมาย

หา new Champion Portfolio ที่ชนะ P13/P16 โดยใช้ baseline/sizing เดียวกับ
`strategy/demo_portfolio/excel/demo_portfolio_backtest_summary_demo.csv`
ไม่ใช้ fixed-lot recompute คนละสูตร

## สูตร sizing ที่ใช้

ใช้สูตรเดียวกับ `backtest_demo_portfolio.py`:

```text
raw trades per leg
-> simulate_equity_substream(raw, cfg, START_EQUITY=1000)
-> daily_series_from_trades(twp)
-> sum daily PnL across legs
```

รายละเอียดสำคัญ:

- risk_usd = equity * RISK_PCT / 100
- lot = risk_usd / risk_distance
- มี margin cap จาก `MAX_MARGIN_USAGE_PCT = 30`, leverage 500, contract 100 oz
- ใช้ circuit breaker/reduced-risk ตาม config ของแต่ละ leg
- เทียบแบบเดียวกับ P13/P16 เดิม ไม่ใช่ fixed-lot S72/S74

## Baseline Reproduction

Runner ใหม่: `optimize_s75_champion_formula.py`

| Portfolio | Avg $/day | Min $/day | Min PF | Max streak | Worst day | Max lot |
|---|---:|---:|---:|---:|---:|---:|
| P13 | 282.68 | 275.00 | 5.17 | 4 | -571.41 | 0.19 |
| P16 | 303.79 | 292.80 | 4.92 | 4 | -584.21 | 0.19 |

ใกล้กับ CSV baseline เดิม:

- P13 ประมาณ 270-300 $/day
- P16 ประมาณ 291-321 $/day

## S74 Fixed Retest ด้วยสูตร P13/P16

S74 Fixed ที่เคยดูดีใน fixed-lot พอทดสอบด้วยสูตรเดียวกับ P13/P16 แล้วไม่ผ่าน:

| Candidate | Avg $/day | Min $/day | Min PF | Max streak | Worst day |
|---|---:|---:|---:|---:|---:|
| S74 Fixed | 150.79 | 139.32 | 4.20 | 10 | -858.41 |

สรุป: S74 Fixed ไม่ใช่ champion เมื่อใช้ baseline จริงของ P13/P16

## S75 Candidate

ตัวที่ดีที่สุดภายใต้ guard `worst_day >= -1000`, `max_streak <= 4`, และต้องชนะ P16:

```text
S75 = P16 + S63x8 + S69x24 + S64x8
```

All-in-4S legs:

- S63 = All-in-4S DMxSP/SP breakout engine
- S69 = S63 high-confidence/base-FVG overlay
- S64 = KRH fibo expansion candidate

## S75 Result

| Window | $/day | PF | Max streak |
|---|---:|---:|---:|
| 90d | 334.86 | 5.35 | 3 |
| 120d | 356.02 | 5.25 | 3 |
| 150d | 312.10 | 4.90 | 3 |
| 180d | 331.42 | 4.77 | 3 |

Summary:

- Avg $/day = 333.60
- Min $/day = 312.10
- Min PF = 4.77
- Max losing-day streak = 3
- Worst day = -919.26
- Max leg DD = 55.0%
- Max lot = 0.19

## เทียบกับ P16

| Metric | P16 | S75 |
|---|---:|---:|
| Avg $/day | 303.79 | 333.60 |
| Min $/day | 292.80 | 312.10 |
| Min PF | 4.92 | 4.77 |
| Max streak | 4 | 3 |
| Worst day | -584.21 | -919.26 |
| Max lot | 0.19 | 0.19 |

S75 ชนะ P16 ด้าน avg/min $/day และ streak แต่แลกกับ worst-day หนักขึ้น
ยังอยู่ใน guard ที่ตั้งไว้ (`>-1000`) แต่ต้องถือว่า aggressive กว่า P16

## Look-Ahead Bias Audit

ตรวจระดับ framework แล้ว:

- P13/P16 ใช้ `backtest_demo_portfolio.py` และ `run_single()` ของแต่ละ leg เหมือน baseline เดิม
- HTF lookup ใช้ `close_times <= entry_time` ผ่าน `bisect_right(...)-1`
- S63/S69 detect จาก closed bar แล้ว fill ที่ bar ถัดไป (`fill_idx = j + 1`)
- S64 ใช้ replay แบบ closed-bar แล้วออกผลหลัง signal เช่นเดียวกับ All-in-4S research runner
- ไม่มีการใช้ high/low ของ entry bar เพื่อสร้าง signal ใน S63/S69

ข้อจำกัด:

- ยังควรทำ forensic audit รายไฟล์ของทุก P16 leg ก่อน live deploy
- S75 ยังเป็น research-only ห้าม wire เข้า bot จริงจนกว่า margin/live execution simulation ผ่าน

## Margin / Balance Notes

ใช้ balance baseline เดียวกับ P13/P16 (`START_EQUITY=1000` ต่อ leg stream ตาม runner เดิม)

ผลที่ต้องรู้:

- Max lot ยังไม่เกิน P16 (`0.19`)
- Max leg drawdown เท่ากับ baseline (`55%`)
- Worst day รวมสูงกว่า P16 (`-919` vs `-584`)
- หากใช้บัญชี $1000 จริง ต้อง monitor exposure รวม เพราะ portfolio-level daily drawdown เกือบเต็มบัญชี

## Verdict

S75 คือ new champion candidate รอบนี้:

- ใช้สูตรเดียวกับ P13/P16
- ชนะ P13/P16 หลาย window
- ไม่ใช้ fixed-lot baseline คนละสูตร
- ผ่าน guard เบื้องต้น `worst_day > -1000`, `maxStreak <= 4`
- ยังเป็น research-only และต้องทำ margin/live execution audit ก่อน deploy

## Files

- `optimize_s75_champion_formula.py`
- `s75_champion_formula_summary.csv`
- `create_s75.md`
