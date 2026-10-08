# EA2.1 — M5/M15 Edge Variant

EA2.1 เป็นรุ่นแยกจาก EA2 เดิม ไม่ได้เขียนทับ logic หรือ state ของ EA2

## Live configuration

- SID: `ea2.1` (legacy alias: `436`)
- Magic number: `550021`
- Entry timeframe: `M5`
- Confirmation timeframe: `M15`
- Risk: `1%` ของ balance ต่อรายการ
- SL / TP: `1200 / 5000` points
- Breakeven: trigger `75`, lock `25` points
- Trailing: trigger `100`, distance `75`, step `5` points
- Maximum open EA2.1 positions: `1`
- Maximum spread: `25` points
- Cooldown: `3` M5 bars
- Order block expiry: `100` M5 bars
- จำกัดหนึ่ง entry ต่อ structure leg

ตัวกรอง M15 ใช้เฉพาะแท่งที่ปิดแล้ว: BUY ต้องอยู่เหนือ EMA20 และ EMA20 ไม่ต่ำกว่า EMA50;
SELL ใช้เงื่อนไขกลับด้าน การคำนวณ backtest และ live adapter ใช้ engine ชุดเดียวกัน

EA2.1 ถูกตั้ง `active_strategies["ea2.1"] = False` เป็นค่าเริ่มต้น เพื่อไม่ให้เริ่มส่งคำสั่งจริง
โดยไม่ได้ตั้งใจ EA2 ใช้ SID `ea2` (legacy alias: `435`) หากต้องการ profile
ทดสอบ EA2.1 เพียงตัวเดียว ให้ตั้ง environment `EA2_1_ONLY_MODE=1` แล้ว restart profile นั้น
หลังตรวจ demo/forward test แล้ว

## Final 365-day backtest

ช่วง `2025-10-06 21:57:03` ถึง `2026-10-06 21:57:03` (Bangkok), spread `0.20`, lot `0.01`

| TF / confirmation | PnL | PF | Max DD | Trades |
|---|---:|---:|---:|---:|
| M1 / M5 | 2,049.66 | 1.53 | 86.24 | 3,543 |
| **M5 / M15 (live)** | **1,759.80** | **2.81** | **36.93** | **877** |
| M15 / H1 | 1,121.94 | 4.74 | 25.94 | 258 |
| M30 / H4 | 677.38 | 5.34 | 35.19 | 120 |
| H1 / H4 | 786.14 | 14.10 | 12.00 | 71 |
| H4 / D1 | 152.72 | ไม่มีรายการแพ้ | 0.00 | 11 |
| H12 / D1 | 249.18 | ไม่มีรายการแพ้ | 0.00 | 8 |
| D1 / D1 | 21.86 | 1.91 | 24.00 | 5 |

ระบบ live เลือก M5/M15 เพราะยังเป็นบวกในช่วง holdout ที่ไม่ได้ใช้จูน และมีจำนวนตัวอย่างมากกว่า
timeframe สูง ส่วน M1 ไม่ถูกเปิดใช้แม้ผล in-sample สูง เพราะไม่ผ่าน adverse-cost holdout

## Independent holdout

ช่วง `2024-10-06 21:57:03` ถึง `2025-10-06 21:57:03`

| Test (M5/M15) | PnL | PF | Max DD | Trades |
|---|---:|---:|---:|---:|
| Base cost | 380.53 | 1.55 | 50.08 | 710 |
| Adverse cost | 190.90 | 1.24 | 70.70 | 708 |

ผลนี้เป็นหลักฐานย้อนหลัง ไม่ใช่การรับประกันผลเทรดจริง ก่อนเปิดเงินจริงควร forward test demo และตรวจ
spread, slippage, commission, symbol specification และขนาด point ของ broker ที่ใช้งานจริง

## Files

- `ea_strategy_2_1.py` — engine และ causal M15 filter
- `live_ea2_1.py` — live state, cost/risk/position guards และ signal adapter
- `backtest_ea2_1.py` — all-timeframe backtest runner
- `ea2_1_summary_365d_final.json` — final 365-day result
- `ea2_1_holdout_base_365d.json` — independent base-cost holdout
- `ea2_1_holdout_adverse_365d.json` — independent adverse-cost holdout
