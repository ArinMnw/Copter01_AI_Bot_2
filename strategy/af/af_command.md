# AF Command Reference

เอกสารนี้จดคำสั่ง `ambfix_build2.py` สำหรับ AF milestone ที่นำไปทำ Demo Portfolio
และอธิบายความหมาย argument แต่ละตัว เพื่อให้ย้อนกลับมาตรวจซ้ำได้ง่าย

> หมายเหตุ: ไฟล์สคริปต์ที่เจอล่าสุดอยู่ใน scratchpad:
> `C:\Users\Copter\AppData\Local\Temp\claude\D--Project-Copter01-AI-Bot-2\52340622-92f4-492d-b134-2f612ae82ff9\scratchpad\ambfix_build2.py`

## AF22

AF22 ใช้ S84 M30 cfg6017 แบบ direct กรอง RD 5.0-7.0 และ fill hour H14

```bash
python ambfix_build2.py --base af21_ambfix_c6017_dir_rdmin50_rd70_h10_daily.csv \
  --out-prefix af22_ambfix_c6017_dir_rdmin50_rd70_h14 --mode direct \
  --rd-min 5.0 --rd-max 7.0 --h 14 --w-lo 240 --w-hi 252 --family s84 --cfg-idx 6017
```

Backtest summary:

| Metric | Value |
|---|---:|
| Avg $/day | 1003.8306 |
| Min $/day | 963.6480 |
| Min PF | 6.61060 |
| Max losing-day streak | 3 |
| Worst day | -999.90965 |
| Raw trades 90/120/150/180 | 2 / 2 / 5 / 8 |

## AF34

AF34 ใช้ S84 M15 cfg889 แบบ inverse กรอง RD 2.7-3.4 และ fill hour H13

```bash
python ambfix_build2.py --base af33_ambfix_c889_dir_rdmin34_rd40_h13_daily.csv \
  --out-prefix af34_ambfix_c889_inv_rdmin27_rd34_h13 --mode inverse \
  --rd-min 2.7 --rd-max 3.4 --h 13 --w-lo 268 --w-hi 280 --family s84 --cfg-idx 889
```

Backtest summary:

| Metric | Value |
|---|---:|
| Avg $/day | 1504.9082 |
| Min $/day | 1439.4060 |
| Min PF | 7.81476 |
| Max losing-day streak | 3 |
| Worst day | -999.90965 |
| Raw trades 90/120/150/180 | 1 / 2 / 5 / 6 |

## AF47

AF47 ใช้ S86 M30 cfg7171 แบบ direct ไม่กรอง RD และ fill hour H13

```bash
python ambfix_build2.py --base af46_ambfix_s86c7171_dir_all_h11_daily.csv \
  --out-prefix af47_ambfix_s86c7171_dir_all_h13 --mode direct \
  --h 13 --w-lo 140 --w-hi 152 --family s86 --cfg-idx 7171
```

Backtest summary:

| Metric | Value |
|---|---:|
| Avg $/day | 2120.5159 |
| Min $/day | 1913.1977 |
| Min PF | 8.92719 |
| Max losing-day streak | 3 |
| Worst day | -999.90946 |
| Raw trades 90/120/150/180 | 2 / 3 / 3 / 3 |

## Argument Meaning

`--base`

ไฟล์ daily CSV ของ portfolio ก่อนหน้า ใช้เป็นฐานก่อนเอา leg ใหม่ไป overlay เพิ่ม
เช่น AF22 ใช้ AF21 base, AF34 ใช้ AF33 base, AF47 ใช้ AF46 base

`--out-prefix`

prefix ชื่อไฟล์ output ที่สคริปต์จะสร้าง เช่น daily/probe/search CSV ของ AF ขั้นนั้น

`--mode direct|inverse`

ทิศทางของ leg ใหม่:

- `direct` ใช้สัญญาณเดิมจาก strategy
- `inverse` กลับฝั่ง BUY เป็น SELL / SELL เป็น BUY และสลับ SL/TP

`--rd-min`

กรองเฉพาะไม้ที่ `risk_distance >= ค่านี้`
เช่น `--rd-min 5.0` คือเอาเฉพาะไม้ที่ระยะ entry ถึง SL อย่างน้อย 5.0

`--rd-max`

กรองเฉพาะไม้ที่ `risk_distance <= ค่านี้`
เช่น `--rd-max 7.0` คือเอาเฉพาะไม้ที่ระยะ entry ถึง SL ไม่เกิน 7.0

`--h`

กรองชั่วโมงเข้าไม้ตามเวลา BKK จาก `fill_time_ts`
เช่น `--h 14` คือเอาเฉพาะไม้ที่ fill ตอน 14:xx BKK

`--w-lo` / `--w-hi`

ช่วง weight ที่ให้สคริปต์ค้นหาน้ำหนัก overlay ของ leg ใหม่
เช่น `--w-lo 240 --w-hi 252` คือ sweep น้ำหนักประมาณ x240 ถึง x252
เพื่อหา weight ที่ดีที่สุดภายใต้ no-blow guard

`--family`

บอกว่าสัญญาณมาจาก strategy family ไหน:

- `s84` = S84 All-in-4S Old Wick Close-Fail
- `s86` = S86 Fibo 50-60 RUN

`--cfg-idx`

เลข config index จาก grid/search ก่อนหน้า ใช้เลือก parameter set ที่แน่นอน:

- `6017` = S84 M30 config ของ AF22
- `889` = S84 M15 config ของ AF34
- `7171` = S86 M30 config ของ AF47

## Related Verification

Demo Portfolio live-style strategy ถูกตรวจเทียบ backtest แล้วด้วย:

```bash
python strategy\demo_portfolio\backtest-sim\verify_af_strategy_consistency.py all --symbol XAUUSD --days 90 120 150 180
```

BTCUSD:

```bash
python strategy\demo_portfolio\backtest-sim\verify_af_strategy_consistency.py all --symbol BTCUSD --days 90 120 150 180
```

ถ้าไม่ใส่ `--spread` สคริปต์จะอ่าน spread ปัจจุบันจาก MT5 ด้วย `ask - bid` ของ symbol นั้นเอง
แต่ยังสามารถใส่ `--spread <value>` เพื่อ override ค่าเองได้

Output CSV:

- `strategy/demo_portfolio/excel/af_strategy_consistency_<symbol>.csv`
- `strategy/demo_portfolio/excel/af_pnl_orders_<symbol>.csv`
- `strategy/demo_portfolio/excel/af_pnl_orders_<symbol>_af22.csv`
- `strategy/demo_portfolio/excel/af_pnl_orders_<symbol>_af34.csv`
- `strategy/demo_portfolio/excel/af_pnl_orders_<symbol>_af47.csv`
- `strategy/demo_portfolio/excel/af_pnl_daily_<symbol>.csv`
- `strategy/demo_portfolio/excel/af_pnl_monthly_<symbol>.csv`

P/L columns:

- `pnl_per_001lot` = P/L ต่อ 0.01 lot หลังหัก spread จาก MT5 หรือค่าที่ override ด้วย `--spread`
- `pnl_weighted_full` = `pnl_per_001lot * AF weight`
- `entry`, `tp`, `sl` = ราคาเข้า, เป้ากำไร, จุดตัดขาดทุนของ order นั้น
- `raw_outcome` = outcome ก่อนกลับฝั่ง ใช้ดู raw generator
- `effective_outcome` = outcome หลังใช้ `direct/inverse` จริง

ผลล่าสุด `MATCH` ครบทุก window:

| Strategy | 90d | 120d | 150d | 180d |
|---|---:|---:|---:|---:|
| AF22 | MATCH | MATCH | MATCH | MATCH |
| AF34 | MATCH | MATCH | MATCH | MATCH |
| AF47 | MATCH | MATCH | MATCH | MATCH |

## Live Demo Portfolio Sizing

AF weighted sizing ถูกเพิ่มไว้ใน Demo Portfolio แล้ว แต่ default ปิดไว้ก่อน:

```python
DEMO_PORTFOLIO_AF_WEIGHT_ENABLED = False
DEMO_PORTFOLIO_AF_WEIGHT_SCALE = 1.0
DEMO_PORTFOLIO_AF_WEIGHT_SCALE_CHOICES = [0.01, 0.05, 0.10, 0.25, 0.50, 1.0]
DEMO_PORTFOLIO_AF_MAX_LOT = 0.0
DEMO_PORTFOLIO_AF_MAX_POS_PER_LEG = 0
```

Telegram menu มีปุ่ม:

- `AF Weight OFF/ON` เปิด/ปิด weighted sizing
- `Scale ...x` หมุน scale 0.01 -> 0.05 -> 0.10 -> 0.25 -> 0.50 -> 1.00

สูตร lot:

```text
lot = 0.01 * AF weight * scale
```

ตัวอย่างเมื่อ scale = 1.00:

| Strategy | Weight | Live lot |
|---|---:|---:|
| AF22 | 244.089 | 2.44 |
| AF34 | 273.830 | 2.74 |
| AF47 | 145.720 | 1.46 |

เมื่อ AF Weight ปิด ทุกตัวกลับไปใช้ `0.01 lot` เหมือน Demo Portfolio เดิม
เพื่อใช้ forward test แบบปลอดภัยกว่า

## AF Ladder Composition Report

ใช้คำสั่งนี้เพื่อดูว่า AF22/AF34/AF47 ทั้งก้อนมี leg อะไรบ้างในแต่ละ window
ไม่ใช่เฉพาะ milestone leg ล่าสุด:

```bash
python strategy\af\export_af_ladder_composition.py --targets 22 34 47 --days 30 60 90 120 150 180
```

Output:

- `strategy/af/excel/af_ladder_components.csv`
- `strategy/af/excel/af_ladder_leg_window_summary.csv`
- `strategy/af/excel/af_ladder_leg_daily.csv`
- `strategy/af/excel/af_ladder_leg_monthly.csv`
- `strategy/af/excel/af_ladder_leg_window_summary_af22.csv`
- `strategy/af/excel/af_ladder_leg_window_summary_af34.csv`
- `strategy/af/excel/af_ladder_leg_window_summary_af47.csv`
- `strategy/af/excel/af_ladder_leg_monthly_af22.csv`
- `strategy/af/excel/af_ladder_leg_monthly_af34.csv`
- `strategy/af/excel/af_ladder_leg_monthly_af47.csv`

ความหมายหลัก:

- `component_no=0` คือ S88 base
- `component_no=1..N` คือ AF overlay leg ตามลำดับ ladder
- `raw_trades` คือจำนวน raw trades จากเอกสาร AF เดิม เฉพาะ windows ที่ daily CSV เดิมมีโดยตรง
- `derived_window=yes` หมายถึง 30/60 วันถูก derive จาก daily data ของ 90 วันล่าสุด
- `pnl` คือ contribution ของ component นั้นใน window นั้น
- `pnl_per_day` คือ `pnl / window_days`

## AF Ladder Sim Order Trace

ใช้คำสั่งนี้เมื่อต้องการดูแบบเดียวกับ P13/P16 ว่าแต่ละ order ใน backtest
มาจาก AF leg ไหนบ้าง โดย replay S84/S86 generator แยกตาม leg และใช้ ambfix
resolution สำหรับแท่งกำกวม:

```bash
python strategy\af\export_af_ladder_sim_orders.py --targets 22 34 47 --days 30 60 90 120 150 180
```

Output:

- `strategy/af/excel/af_ladder_sim_orders.csv`
- `strategy/af/excel/af_ladder_sim_leg_summary.csv`
- `strategy/af/excel/af_ladder_sim_daily.csv`
- `strategy/af/excel/af_ladder_sim_monthly.csv`
- `strategy/af/excel/af_ladder_sim_orders_af22.csv`
- `strategy/af/excel/af_ladder_sim_orders_af34.csv`
- `strategy/af/excel/af_ladder_sim_orders_af47.csv`
- `strategy/af/excel/af_ladder_sim_leg_summary_af22.csv`
- `strategy/af/excel/af_ladder_sim_leg_summary_af34.csv`
- `strategy/af/excel/af_ladder_sim_leg_summary_af47.csv`

ความหมายหลัก:

- `component_no` คือเลข AF overlay leg เช่น `22` = AF22 leg ล่าสุด
- `component_name` คือชื่อ leg/generator/filter จริง
- `order_no` คือเลข order ภายใน leg + window นั้น
- `entry`, `tp`, `sl`, `exit_price` คือราคาจาก sim order-level
- `pnl_per_001lot` คือ P/L ต่อ 0.01 lot หลังหัก spread
- `pnl_weighted_full` คือ P/L หลังคูณ weight ของ leg
- `ambiguous`, `m1_sl`, `m1_tp`, `unresolved` ใน summary คือ audit ของ ambfix resolution

หมายเหตุ: ไฟล์นี้ trace เฉพาะ AF overlay legs (AF1..AF47) แบบ order-level
ส่วน S88 base ยังดูจาก `af_ladder_leg_*` composition report เพราะ S88 เป็น base chain รวมหลายชั้นเดิม
ไม่ใช่ raw generator เดี่ยวแบบ P13/P16 leg ปกติ

## MT5 Live Wiring Status

Demo Portfolio ฝั่ง MT5 ใช้ full AF ladder แล้ว:

- `AF22` = เปิด scan `AF1..AF22`
- `AF34` = เปิด scan `AF1..AF34`
- `AF47` = เปิด scan `AF1..AF47`
- P13/P16/AF ใช้ `DEMO_PORTFOLIO_SYMBOL = "XAUUSD"` เท่านั้น และ resolve เป็น broker symbol
  เช่น `XAUUSD.iux` โดยไม่ตาม runtime symbol switch ไป BTCUSD
- ถ้า XAUUSD ปิดหรือ tick stale ระบบจะ skip Demo Portfolio ทั้งรอบ ไม่ mark signal และรอรอบถัดไป
  หลังตลาดเปิด

MT5 order comment ของ AF:

- รูปแบบ `{entry_tf}-{portfolio}-{leg}`
- ตัวอย่าง `M15-AF22-AF1`, `M30-AF47-AF43`
- P13/P16 ใช้รูปแบบเดียวกัน เช่น `M5-P13-B`, `M5-P16-Q`

Sizing:

- ถ้า `AF Weight OFF`: ทุก leg ใช้ `0.01` lot เพื่อ forward-run แบบปลอดภัย แต่จะไม่ตรง backtest weight
- ถ้า `AF Weight ON` และ `Scale 1.00x`: lot ต่อ leg = `0.01 * leg_weight * scale`
- ไม่มี internal max-lot cap ของ AF แล้ว (`DEMO_PORTFOLIO_AF_MAX_LOT = 0.0`) แต่ broker `volume_min/max/step`
  ยังอาจทำให้ lot ถูก normalize ตามข้อจำกัด MT5 จริง
- `DEMO_PORTFOLIO_AF_MAX_POS_PER_LEG = 0` หมายถึงไม่ cap จำนวน position ต่อ leg เพื่อไม่ใส่ constraint
  ที่ backtest AF ไม่ได้ใช้

ข้อจำกัดของคำว่า 100%:

- Live broker อาจมี spread/slippage/fill price/volume step ต่างจาก backtest
- Backtest ambfix ใช้ M1 replay + pessimistic fallback สำหรับแท่งกำกวม ส่วน live ให้ broker SL/TP ตัดสินตาม tick จริง
- ดังนั้น code path/leg/entry rule/weight ตั้งใจให้ตรง backtest แต่ผลลัพธ์เงินจริงอาจต่างได้จาก execution จริง

ตัวอย่างจำนวน component:

| Target | Components |
|---|---:|
| AF22 | S88 base + 22 overlay legs |
| AF34 | S88 base + 34 overlay legs |
| AF47 | S88 base + 47 overlay legs |
