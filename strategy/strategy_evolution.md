# Strategy Evolution S115–S999

เอกสารนี้เป็นบริบทสะสมสำหรับพัฒนากลยุทธ์ลำดับถัดไป โดยบันทึก Edge,
ความแตกต่างจากกลยุทธ์ก่อนหน้า และหลักฐาน Backtest ตามกฎ Reality Check เดียวกัน

## Backtest contract

- Symbol: `XAUUSD.iux`
- Timeframe baseline: `M5`
- ระยะทดสอบต่อกลยุทธ์: 2 calendar months
- Lot: `0.01`
- Spread: `0.20`
- ใช้เฉพาะแท่งปิดแล้ว
- Market order เข้า Open ของแท่งถัดไป
- Limit order ต้องผ่าน spread: BUY `low <= entry - spread`, SELL กลับด้าน
- ถ้า SL/TP แตะในแท่งเดียวกัน ให้ SL ก่อน
- BE ที่ถูก trigger ในแท่งหนึ่งเริ่มมีผลแท่งถัดไป
- ถือได้ครั้งละหนึ่ง position ต่อกลยุทธ์
- Runner กลาง: `sim_strategy_backtest.py`

## S115 — Structural FTR Imbalance Continuation

ไฟล์: `strategy115.py`

Edge: BOS ที่สร้าง FVG ตามด้วยการย้อนกลับแบบ volume contraction ซึ่งไม่สามารถ
เจาะ imbalance ได้ลึก ก่อนกลับไปตาม displacement เดิม เป็น continuation regime
ที่ต่างจาก S114 high-effort absorption

ข้อค้นพบ:

- ค่า Default ซ้อนตัวกรองมากเกินไป โดย `BOS_BODY_ATR=1.20` ตัด candidate 91.72%
- การผ่อนค่าทำให้เกิดไม้ แต่ผล OOS 2026-03-30–2026-07-17 คือ 4 ไม้,
  WR 0%, Net -6.88 จึงยังไม่มีหลักฐาน Edge
- Execution retest แบบ fixed-end `2026-07-18`, M5, spread0.20, lot0.01 ยืนยันว่า
  detector ส่ง limit และถูก fill ได้จริง: relaxed 2m มี 5 signals, closed 2,
  expired 3, WR 0%, Net -0.40; relaxed 6m มี 20 signals, closed 8, expired 12,
  WR 25%, Net +16.77, PF 2.12, Max DD 11.18 อย่างไรก็ดี winner ทั้งสองอยู่
  เดือนกุมภาพันธ์และช่วงล่าสุดไม่มี TP จึงยังไม่ควรเปลี่ยน relaxed config เป็น default

ผล Backtest มาตรฐาน 2 เดือน (`2026-05-17`–`2026-07-17`):

| Signals | Closed | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | 0 | N/A | 0.00 | 0.00 | 0.00 | N/A | 0.00 |

บทเรียนสำหรับตัวถัดไป: หลีกเลี่ยง chronology ที่แคบเกินไปและอย่าซ้อน confluence
จนไม่มี sample; ต้องมี regime gate ที่พิสูจน์แยก continuation/mean-reversion

## S116 — Session VWAP Delta-Divergence Exhaustion Fade

ไฟล์: `strategy116.py`

Edge: ในช่วง NY session ราคายืดออกจาก session-anchored VWAP แต่ normalized
tick-volume delta ไม่ยืนยัน extreme ใหม่ พร้อม rejection candle จึงตั้ง limit fade
กลับหา VWAP เป็น mean-reversion regime ที่ต่างจาก S115 โดยโครงสร้าง

ผล Backtest มาตรฐาน 2 เดือน (`2026-05-17`–`2026-07-17`):

| Signals | Closed | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 23 | 18 | 11.11% | -49.61 | -0.81 | -24.81 | 0.49 | 68.32 |

บทเรียนสำหรับ S117: S116 สร้าง sample ได้จริงแต่ fade สวน persistent regime มากเกินไป;
S117 ต้องรวมบทเรียน S115/S116 ด้วยตัววัด regime เช่น Variance Ratio เพื่ออนุญาต
continuation เมื่อ return มี persistence และอนุญาต VWAP fade เฉพาะเมื่อ return
มี mean-reversion เท่านั้น

## S117 — Variance-Ratio Regime Router

ไฟล์: `strategy117.py`

Edge: รวมบทเรียน S115/S116 ด้วย Variance Ratio ของ log return โดย route ไป S115
เมื่อ return มี persistence, route ไป S116 เมื่อ anti-persistent และไม่เทรด neutral regime

ผล Backtest มาตรฐาน 2 เดือน (`2026-05-17`–`2026-07-17`):

| Signals | Closed | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 7 | 5 | 0.00% | -40.37 | -0.66 | -20.19 | 0.00 | 40.37 |

บทเรียนสำหรับ S118: Variance Ratio ระยะสั้นตัวเดียวไม่สามารถ route setup ที่อ่อนแอ
ให้กลายเป็น Edge ได้ และการรวมกลยุทธ์ขาดทุนไม่ใช่ diversification ที่แท้จริง
S118 ต้องสร้าง alpha source ใหม่ ไม่เรียก S115–S117 เป็นตัวกำเนิดออเดอร์ และควรใช้
session microstructure/auction behavior ที่มี sample มากพอแทน chronology หลายชั้น

## S118 — Initial-Balance Value-Area Acceptance Retest

ไฟล์: `strategy118.py`

Edge: สร้าง volume profile จาก Initial Balance 14:00–16:00 BKK, หา POC และ
70% Value Area แล้วรอ first two-close acceptance นอก VA ก่อนตั้ง limit retest ที่
VAH/VAL เป็น auction-market continuation ที่ไม่เรียก S115–S117

ผล Backtest มาตรฐาน 2 เดือน (`2026-05-17`–`2026-07-17`):

| Signals | Closed | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 89 | 49 | 12.24% | -91.06 | -1.49 | -45.53 | 0.45 | 111.10 |

บทเรียนสำหรับ S119: Auction acceptance มี sample เพียงพอ แต่ limit retest หลังสอง close
ยังรับ false acceptance มากเกินไปและ SL หลัง POC กว้างเมื่อเทียบ follow-through
S119 ควรหลีกเลี่ยง breakout/acceptance และสำรวจ time-series alpha ที่ไม่อิงระดับราคา
เช่น volatility term structure หรือ return autocorrelation พร้อมกำหนด entry ที่ fill ได้จริง

## S119 — Volatility Term-Structure Expansion Continuation

ไฟล์: `strategy119.py`

Edge: ตรวจ transition ครั้งแรกที่ short-horizon realized volatility สูงกว่า long-horizon
พร้อม directional efficiency และ volume expansion แล้วตั้ง limit retrace ตามทิศ impulse
โดยไม่อิง swing/FVG/VWAP/value area

ผล Backtest มาตรฐาน 2 เดือน (`2026-05-17`–`2026-07-17`):

| Signals | Closed | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 55 | 35 | 17.14% | -211.34 | -3.46 | -105.67 | 0.52 | 211.34 |

บทเรียนสำหรับ S120: volatility expansion บนทอง M5 ไม่ได้แปลว่า follow-through;
continuation หลัง transition ถูก mean-revert บ่อยและ SL ตาม origin กว้างเกินไป
S120 จะทดสอบสมมติฐานกลับด้าน: fade multi-bar volatility exhaustion เฉพาะเมื่อ
path efficiency ต่ำและแท่งล่าสุดปิดสวน impulse โดยยังคง dynamic risk

## S120 — Volatility Expansion Exhaustion Fade

ไฟล์: `strategy120.py`

Edge: falsify S119 ด้วยการ fade short/long RV expansion เฉพาะ path ที่ efficiency ต่ำ
และมีแท่งกลับทิศปิดแล้ว เป้าหมายคือ pre-expansion mean และต้องให้ reward >=1.5R

ผล Backtest มาตรฐาน 2 เดือน (`2026-05-17`–`2026-07-17`):

| Signals | Closed | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 41 | 26 | 19.23% | +1.32 | +0.02 | +0.66 | 1.01 | 85.63 |

Breakdown: BUY 16 ไม้ Net -48.96; SELL 10 ไม้ Net +50.28 การ fade downside
expansion ล้มเหลว แต่ fade upside expansion มี expectancy บวกใน sample นี้

บทเรียนสำหรับ S121: ทดสอบ asymmetric-volatility hypothesis โดยรับเฉพาะ upside
exhaustion → SELL เนื่องจาก downside volatility ของทองมี clustering/follow-through สูงกว่า
ห้ามเพิ่ม hour filter จาก sample เล็กเพื่อเลี่ยง overfit

## S121 — Asymmetric Upside-Volatility Exhaustion

ไฟล์: `strategy121.py`

Edge: รับเฉพาะ SELL จาก S120 เพื่อทดสอบ volatility asymmetry—ไม่ fade downside
expansion ที่มี clustering แต่ fade inefficient upside expansion ซึ่งอาจเกิดจาก short covering

ผล Backtest มาตรฐาน 2 เดือน (`2026-05-17`–`2026-07-17`):

| Signals | Closed | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 16 | 10 | 30.00% | +50.28 | +0.82 | +25.14 | 2.44 | 31.80 |

ข้อจำกัด: sample เพียง 10 ไม้และเป็น in-sample 2 เดือน ยังไม่ใช่หลักฐาน production

บทเรียนสำหรับ S122: เพิ่ม order-flow deceleration ที่ไม่ใช้ hour mining โดยกำหนดให้
normalized signed tick-volume ช่วงท้ายของ upside expansion อ่อนกว่าช่วงต้นก่อนรับ SELL

## S122 — Upside RV Exhaustion + Signed-Volume Deceleration

ไฟล์: `strategy122.py`

Edge: รับ S121 SELL เฉพาะเมื่อ normalized signed tick-volume ช่วงท้าย 4 แท่ง
ลดลงจากช่วงต้น 4 แท่งอย่างน้อย 0.05 เพื่อยืนยัน buying-pressure deceleration

ผล Backtest มาตรฐาน 2 เดือน (`2026-05-17`–`2026-07-17`):

| Signals | Closed | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 8 | 5 | 20.00% | +31.12 | +0.51 | +15.56 | 2.18 | 26.31 |

ข้อจำกัด: filter ลด sample จาก 10 เหลือ 5 และผลกำไรพึ่ง TP เพียงหนึ่งไม้ จึงยัง fragile

บทเรียนสำหรับ S123: ห้ามเพิ่ม confluence จน sample หายอีก ควรทดสอบ execution/risk
variant ของ S121 ที่มี sample มากกว่า เช่น structural stop compression โดยตรรกะสัญญาณคงเดิม

## S123 — S121 Reversal-Candle Risk Compression

ไฟล์: `strategy123.py`

Edge experiment: คง signal S121 ทุกไม้ แต่ย้าย SL จาก expansion-window extreme
มาไว้หลัง reversal candle +0.20 ATR และคำนวณ TP ใหม่ 1.8R

ผล Backtest มาตรฐาน 2 เดือน (`2026-05-17`–`2026-07-17`):

| Signals | Closed | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 16 | 10 | 30.00% | -3.26 | -0.05 | -1.63 | 0.89 | 14.96 |

บทเรียนสำหรับ S124: stop แคบลด DD ได้มากแต่ถูก noise กิน expectancy; ทดสอบ blended
stop ระหว่าง reversal high และ expansion-window SL โดยไม่เปลี่ยน signal generator

## S124 — Blended Expansion/Reversal Stop

ไฟล์: `strategy124.py`

Edge experiment: คง S121 signal แล้วผสม SL 50% ระหว่าง reversal-candle stop กับ
original expansion-window stop พร้อม TP 1.8R

ผล Backtest มาตรฐาน 2 เดือน (`2026-05-17`–`2026-07-17`):

| Signals | Closed | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 16 | 10 | 20.00% | -30.33 | -0.50 | -15.17 | 0.40 | 30.33 |

บทเรียนสำหรับ S125: การบีบ stop ทั้งแบบเต็มและ blend ไม่ผ่าน ให้คืน original S121
risk geometry แล้วทดสอบ exit dimension แยก โดยปิด BE เพื่อวัดผลของ payoff truncation

## S125 — S121 No-Breakeven Payoff

ไฟล์: `strategy125.py`

Edge experiment: คง signal/entry/SL/TP ของ S121 แต่ตั้ง `be_rr=None`

ผล Backtest มาตรฐาน 2 เดือน (`2026-05-17`–`2026-07-17`):

| Signals | Closed | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 16 | 10 | 30.00% | +34.89 | +0.57 | +17.45 | 1.69 | 40.87 |

บทเรียนสำหรับ S126: ปิด BE ยังบวกแต่ด้อยกว่า S121 (+50.28, DD 31.80) จึงยืนยันว่า
BE 1R เพิ่ม expectancy ใน sample นี้ ให้ทดสอบ delayed BE 1.25R โดยไม่แตะ signal/geometry

## S126 — S121 Delayed Breakeven 1.25R

ไฟล์: `strategy126.py`

ผล Backtest มาตรฐาน 2 เดือน (`2026-05-17`–`2026-07-17`):

| Signals | Closed | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 16 | 10 | 30.00% | +43.96 | +0.72 | +21.98 | 2.06 | 31.80 |

บทเรียนสำหรับ S127: delayed BE ด้อยกว่า S121 BE1.0 แต่ดีกว่า no-BE ให้ทดสอบ early
BE0.75 เพื่อปิด sensitivity curve โดยไม่แก้ signal, entry, SL หรือ TP

## S127 — S121 Early Breakeven 0.75R

ไฟล์: `strategy127.py`

ผล Backtest มาตรฐาน 2 เดือน (`2026-05-17`–`2026-07-17`):

| Signals | Closed | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 16 | 10 | 30.00% | +50.28 | +0.82 | +25.14 | 2.44 | 31.80 |

ผลเท่ากับ S121 BE1.0 ทุกตัว แปลว่าในข้อมูล OHLC ชุดนี้ไม่มี trade ที่ path outcome
ต่างกันระหว่าง trigger 0.75R กับ 1.0R จึงไม่มีหลักฐานให้เลือก early BE

บทเรียนสำหรับ S128: sensitivity curve ยืนยัน original S121 geometry/BE ไม่ควรถูกปรับต่อ
และการสร้าง wrapper เพิ่มไม่ให้ข้อมูลใหม่ S128 ต้องกลับไปสร้าง independent alpha source
จาก cross-session inventory behavior โดยไม่ใช้ FTR, VWAP fade, VA breakout หรือ RV exhaustion

## S128 — Asia-to-London Inventory Carry Reclaim

ไฟล์: `strategy128.py`

Edge: Asia session ต้องมี directional inventory, path efficiency และ signed-volume delta
สอดคล้องกัน จากนั้น London ย่อ 5–80% ของ Asia move และปิด reclaim Asia close ครั้งแรก
ก่อนตั้ง limit ที่ Asia close; SL หลัง Asia midpoint + ATR buffer

ค่าเริ่มต้นรอบแรก efficiency 0.45 ไม่มี sample เพราะ metric เป็น net/path ตลอด 7 ชั่วโมง
จึง calibrate เป็น 0.10 พร้อม Asia move 1.20ATR และ delta 0.03 โดยยังรักษา logic ครบ

ผล Backtest มาตรฐาน 2 เดือน (`2026-05-17`–`2026-07-17`):

| Signals | Closed | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 7 | 7 | 57.14% | +104.71 | +1.72 | +52.36 | 3.83 | 20.82 |

ข้อจำกัด: parameter ถูก calibrate บนช่วงรายงานเดียวกันและ n=7 จึงเป็น in-sample

บทเรียนสำหรับ S129: ทดสอบ high-conviction inventory carry ด้วย Asia move 1.5ATR,
efficiency 0.12, delta 0.05 และ pullback 8–70% เป็น hypothesis ที่เข้มขึ้น

## S129 — High-Conviction Asia Inventory Carry

ไฟล์: `strategy129.py`

Edge: chronology เดียวกับ S128 แต่กำหนด Asia move >=1.5ATR, efficiency >=0.12,
delta >=0.05 และ London pullback 8–70%

ผล Backtest มาตรฐาน 2 เดือน (`2026-05-17`–`2026-07-17`):

| Signals | Closed | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 5 | 5 | 80.00% | +120.94 | +1.98 | +60.47 | 6.81 | 20.82 |

ข้อจำกัด: n=5 และ threshold มาจาก calibration ช่วงเดียวกัน ห้ามอ้างเป็น OOS

บทเรียนสำหรับ S130: หยุดเพิ่มความเข้มของ carry filter แล้วสร้าง complementary event:
Asia inventory liquidation เมื่อ London ปิดทำลาย Asia midpoint เป้ากลับ Asia open

## S130 — London Liquidation of Asia Inventory

ไฟล์: `strategy130.py`

Edge: complementary failure state ของ S128—เมื่อ London ปิดทำลาย Asia midpoint
ครั้งแรก ให้ fade Asia inventory โดย limit retest midpoint และ SL หลัง Asia close

ผล Backtest มาตรฐาน 2 เดือน (`2026-05-17`–`2026-07-17`):

| Signals | Closed | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 4 | 2 | 0.00% | -33.23 | -0.54 | -16.62 | 0.00 | 33.23 |

บทเรียนสำหรับ S131: liquidation hypothesis ไม่ผ่าน ขณะที่ S128/S129 carry บวก
S131 ควรรักษา carry แต่เพิ่ม non-directional capacity filter ว่า Asia ใช้ daily range
ไปมากเกินหรือยัง โดยไม่เพิ่ม hour/direction mining

## สถานะลำดับถัดไป

- S153 optimization ถึง plateau ที่ RR10; เป้าหมายถัดไป S154
- เอกสารนี้ต้องถูกอัปเดตหลัง compile, contract test และ Backtest 2 เดือนของทุก S

## S131 — Asia Carry with Previous-Day Range Capacity

ไฟล์: `strategy131.py`

Edge experiment: คง signal, entry และ risk geometry ของ S128 แต่รับเฉพาะวันที่
Asia range ไม่เกิน 70% ของ range วัน BKK ก่อนหน้า เพื่อให้ยังมี intraday capacity
สำหรับ London continuation โดย gate เป็นกลางต่อทิศทางและใช้ข้อมูลที่ปิดแล้วเท่านั้น

ผล Backtest 2 เดือน (`2026-05-17`–`2026-07-17`, lookback 700):

| Signals | Closed | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 4 | 4 | 50.00% | +16.41 | +0.27 | +8.21 | 1.45 | 36.85 |

บทเรียนสำหรับ S132: ตัวกรองเทียบวันเดียวลด S128 จาก 7 เหลือ 4 ไม้และลด Net
จาก +104.71 เหลือ +16.41 จึงยังไม่เพิ่ม Edge; S132 จะลด single-day noise ด้วย
median range ของหลายวันก่อนหน้า โดยไม่เปลี่ยน chronology หรือ execution

## S132 — Asia Carry Capacity versus Multi-Day Median Range

ไฟล์: `strategy132.py`

Edge experiment: แทน prior day ที่มี noise ด้วย median daily range สูงสุด 5 วันทำการ
ก่อนหน้า และรับ S128 เมื่อ Asia range ไม่เกิน 70% ของ reference ดังกล่าว

ผล Backtest 2 เดือน (`2026-05-17`–`2026-07-17`, lookback 2500):

| Signals | Closed | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 5 | 5 | 60.00% | +39.98 | +0.66 | +19.99 | 2.08 | 20.82 |

บทเรียนสำหรับ S133: multi-day median ดีกว่า S131 แต่ยังตัด contribution บวกของ S128
ออกไปมาก จึงทดสอบ complement โดยรับ carry เฉพาะ Asia/median range >70% เพื่อ
falsify สมมติฐาน exhaustion; ต้องตีความอย่างระวังเพราะ sample จะเล็ก

## S133 — High Range-Consumption Asia Inventory Carry

ไฟล์: `strategy133.py`

Edge experiment: complement ของ S132 โดยรับ S128 เฉพาะเมื่อ Asia range มากกว่า
70% ของ median daily range ก่อนหน้า เพื่อทดสอบว่าการใช้ range สูงหมายถึง persistence
แทน exhaustion หรือไม่

ผล Backtest 2 เดือน (`2026-05-17`–`2026-07-17`, lookback 2500):

| Signals | Closed | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 | 2 | 50.00% | +64.73 | +1.06 | +32.37 | 324.65 | 0.20 |

ข้อจำกัด: PF สูงผิดปกติเพราะมีเพียงหนึ่ง winner และอีกไม้เสียเพียง spread/BE;
n=2 ไม่ใช่หลักฐาน production และ RR ยังเป็น 1.8

บทเรียนสำหรับ S134: เงื่อนไขเป้าหมายใหม่ให้หยุดสร้าง strategy เมื่อพบ RR>=7 ที่พอร์ต
อยู่รอดได้ จึงทดสอบ convex payoff โดยคง S128 generator/SL แต่ขยาย TP เป็น 7R
และใช้ BE 1R; หาก Net บวกและ DD ควบคุมได้จะหยุดที่ S134 เพื่อ optimize

## S134 — Asia Inventory Carry with 7R Convex Payoff

ไฟล์: `strategy134.py`

Edge experiment: คง S128 signal, limit entry และ SL หลัง Asia midpoint แต่ขยาย
target เป็นอย่างน้อย 7R พร้อมเลื่อน BE เมื่อถึง 1R ตาม execution contract

ผล Backtest 2 เดือน (`2026-05-17`–`2026-07-17`):

| Signals | Closed | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 6 | 5 | 0.00% | -16.83 | -0.28 | -8.42 | 0.00 | 16.83 |

มีหนึ่ง position ยังเปิดเมื่อสิ้นสุดช่วงทดสอบและไม่มีไม้ใดถึง 7R จึงไม่เข้าเงื่อนไข
หยุดพัฒนา/optimize ตามเป้าหมายใหม่

บทเรียนสำหรับ S135: 7R ต้องจับ event ที่มี reversal displacement มากกว่า session carry;
ทดสอบ S121 upside-volatility exhaustion ซึ่ง baseline มี PF 2.44 โดยคง signal เดิม
แล้วเปลี่ยนเฉพาะ payoff เป็น 7R เพื่อไม่ให้ sample หายจาก target-distance filter

## S135 — Optimized Upside-Volatility Exhaustion Convex Payoff

ไฟล์: `strategy135.py`

Initial trigger: คง entry/SL ของ S121 แล้วเปลี่ยน target เป็น 7R พร้อม BE 1R
ผลมาตรฐานเริ่มต้น 2 เดือนคือ 16 signals, 10 closed, 6 expired, WR 20.00%,
Net +50.70, P&L/day +0.83, P&L/month +25.35, PF 2.44, Max DD 31.80
จึงเข้าเงื่อนไขเป้าหมายใหม่ให้หยุดสร้าง S136 และ optimize S135

Optimization ที่ทำโดยคง execution contract เดิม:

- payoff grid 7/8/10/12/14/16/18/20/25/30R และ BE 0.75/1.0/1.25
- risk cap 1.0–3.5 ATR
- RV transition grid: current RV 1.55–2.15 และ previous RV max 0.8–1.2
- walk-forward 2 เดือนสามหน้าต่างสิ้นสุด 17 มี.ค., 17 พ.ค. และ 17 ก.ค. 2026
- ไม่ใช้ hour/direction mining; เลือก moderate plateau แทน strict in-sample maximum

Recommended default cfg หลัง optimization:

```python
{
    "SOURCE_CFG": {"S120_CFG": {
        "MAX_RISK_ATR": 2.50,
        "RV_EXPANSION_MIN": 2.00,
        "PREVIOUS_RV_MAX": 1.00,
    }},
    "TP_RR": 14.00,
    "BE_RR": 1.00,
}
```

ผล aggregate 6 เดือนของ recommended cfg (`2026-01-17`–`2026-07-17`):

| Closed | Wins | Win rate | Net | PF | Max DD |
|---:|---:|---:|---:|---:|---:|
| 11 | 3 | 27.27% | +306.06 | 11.42 | 29.17 |

RR sensitivity 6 เดือน: 10R +210.06, 12R +258.06, 14R +306.06,
16R +286.73 โดย 16R สูญเสีย winner หนึ่งไม้ จึงเลือก 14R ก่อน cliff

Walk-forward ของ moderate cfg: Jan–Mar -13.55, Mar–May +147.71,
May–Jul +171.90; มี losing regime จึงต้องใช้ fixed risk sizing และห้ามตีความว่า
win rate/expectancy จะคงที่ทุกเดือน

ผล Backtest มาตรฐาน 2 เดือนของ default ที่ optimize แล้ว
(`2026-05-17`–`2026-07-17`):

| Signals | Closed | Expired | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 5 | 3 | 2 | 66.67% | +171.90 | +2.82 | +85.95 | 860.50 | 0.20 |

Spread stress ช่วงเดียวกันยังคง trade set เดิม: spread 0.30 ได้ Net +171.60,
spread 0.50 ได้ Net +171.00 จึงไม่พบ sensitivity ต่อ spread ใน sample นี้

ข้อจำกัดสำคัญ: ผล 2 เดือนมีเพียง 3 closed trades ทำให้ PF 860.50 ไม่เสถียร;
ตัวเลขที่เหมาะกับการประเมิน survival มากกว่าคือผล 6 เดือน 11 closed, WR 27.27%,
Net +306.06 และ Max DD 29.17 ที่ lot 0.01 ทั้งหมดยังเป็น historical simulation
ไม่ใช่การรับประกันผล live และยังต้องกำหนดเงินทุน/position sizing ให้รองรับ losing regime

## S136 — Downside-Volatility Capitulation Short-Stop 7R

ไฟล์: `strategy136.py`

Edge experiment: complement S135 โดยรับเฉพาะ BUY หลัง first downside RV expansion
ที่ current RV>=2 และ previous RV<=1 ใช้ SL หลัง low ของ reversal candle +0.15ATR,
risk ไม่เกิน 1.25ATR, TP 7R และ BE 1R

ผล Backtest 2 เดือน (`2026-05-18`–`2026-07-18`):

| Signals | Closed | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 4 | 4 | 0.00% | -8.86 | -0.15 | -4.43 | 0.00 | 8.86 |

สามไม้เดินถึง 1R แล้วถูก BE ปิดที่ผลสุทธิ -0.20 ต่อไม้ อีกหนึ่งไม้โดน SL -8.26;
ไม่มีไม้ถึง 7R จึงไม่เข้า optimization trigger

บทเรียนสำหรับ S137: แยกผลของ payoff truncation โดยคง generator/entry/SL/TP เดิม
ทุกจุดแล้วปิด BE; หากยังไม่มี TP แปลว่า downside branch ไม่มี convex tail ใน sample นี้

## S137 — Downside Capitulation 7R without Breakeven

ไฟล์: `strategy137.py`

Edge experiment: คง signal, entry, short structural SL และ TP7R ของ S136 แต่ปิด BE
เพื่อทดสอบว่าสามไม้ที่เคยแตะ 1R มีโอกาสพัฒนาเป็น convex winner ภายหลังหรือไม่

ผล Backtest 2 เดือน (`2026-05-18`–`2026-07-18`):

| Signals | Closed | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 4 | 4 | 0.00% | -25.51 | -0.42 | -12.75 | 0.00 | 25.51 |

บทเรียนสำหรับ S138: ทั้ง BE และ no-BE ไม่มี 7R winner จึงยกเลิก downside fade;
กลับสมมติฐานเป็น trend continuation เมื่อ bullish capitulation reclaim ล้มเหลวในแท่งถัดไป

## S138 — Immediate Failed-Capitulation Continuation SELL 7R

ไฟล์: `strategy138.py`

Edge experiment: หลัง downside RV capitulation BUY reversal ให้แท่งถัดไปต้องปิดต่ำกว่า
reversal low ด้วย bearish body>=0.10ATR แล้วตั้ง SELL limit retest พร้อม short SL/TP7R

ผล Backtest 2 เดือน (`2026-05-18`–`2026-07-18`):

| Signals | Closed | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | 0 | N/A | 0.00 | 0.00 | 0.00 | N/A | 0.00 |

บทเรียนสำหรับ S139: immediate-next-bar chronology แคบเกินไป; ขยายเป็น first failure
ภายในสามแท่งปิด โดยยืนยันว่าแท่งกลางยังไม่เคยปิดทำลาย level เพื่อกัน duplicate signal

## S139 — First Failed Reclaim within Three Bars

ไฟล์: `strategy139.py`

ผล Backtest 2 เดือน (`2026-05-18`–`2026-07-18`):

| Signals | Closed | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 1 | 0.00% | -0.20 | -0.003 | -0.10 | 0.00 | 0.20 |

มีเพียงหนึ่งไม้และจบ BE จึงยุติ failure-reclaim branch เพื่อเลี่ยง chronology mining

บทเรียนสำหรับ S140: ใช้หลักฐานกว้างกว่าจาก S120 ว่า downside volatility มี clustering;
รับ downside RV expansion continuation โดยตรง ไม่รอ multi-stage reclaim failure

## S140 — Asymmetric Downside RV Continuation Short-Stop 7R

ไฟล์: `strategy140.py`

Edge: รับเฉพาะ SELL จาก first coherent downside RV expansion ของ S119 เพราะผลสะสม
S120/S136–S137 ชี้ว่าการ fade downside ล้มเหลวและ volatility ฝั่งลงมี clustering;
ย้าย SL มาเหนือ signal bar +0.15ATR, จำกัด risk<=1.25ATR และ TP7R/BE1R

ผลเริ่มต้น Backtest 2 เดือน (`2026-05-18`–`2026-07-18`):

| Signals | Closed | Expired | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 34 | 27 | 7 | 7.41% | +62.16 | +1.02 | +31.08 | 2.24 | 34.18 |

S140 เข้า trigger RR>=7, Net บวก และ fixed-lot drawdown ยังอยู่รอด จึงหยุด S141
ชั่วคราวเพื่อ optimize payoff/BE, risk geometry และ source thresholds แบบ walk-forward

Optimization S140:

- RR grid 7–40R: current window peak ก่อน cliff คือ 28R แต่ 32R ไม่มี winner
- Walk-forward ชี้ว่า RR14+ ไม่มี winnerใน Mar–May; เลือก RR7 ที่ robust กว่า
- BE0.75 ตัด winners, BE1.25 เพิ่ม DD; เลือก BE1.0
- เพิ่ม price-relative risk cap: 0.3–0.5% เป็น plateau; เลือกค่ากลาง 0.4%
- efficiency 0.70/0.75/0.80 ดีขึ้นต่อเนื่อง แต่ 0.85 ตัด winners 3/4; เลือก 0.80
- previous RV max 1.0 รักษา winners 4 ไม้; 0.8–0.9 ตัดหนึ่ง winner และ 1.1 รับ noise เพิ่ม

Recommended optimized cfg:

```python
{
    "SOURCE_CFG": {
        "RV_EXPANSION_MIN": 1.45,
        "PREVIOUS_RV_MAX": 1.00,
        "EFFICIENCY_MIN": 0.80,
    },
    "MAX_RISK_PRICE_PCT": 0.40,
    "TP_RR": 7.00,
    "BE_RR": 1.00,
}
```

ผล aggregate 6 เดือนของ optimized cfg (`2026-01-18`–`2026-07-18`):

| Closed | Wins | Win rate | Net | PF | Max DD |
|---:|---:|---:|---:|---:|---:|
| 19 | 4 | 21.05% | +177.73 | 10.92 | 10.36 |

Walk-forward efficiency/risk candidate: Jan–Mar ใกล้ flat, Mar–May และ May–Jul
เป็นบวก; optimization ลด 6-month DD จาก 101.20 เหลือ 10.36 โดยไม่ตัด winner

ผล Backtest มาตรฐาน 2 เดือนของ optimized default
(`2026-05-18`–`2026-07-18`):

| Signals | Closed | Expired | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 14 | 12 | 2 | 16.67% | +98.48 | +1.61 | +49.24 | 8.05 | 10.36 |

บทเรียนสำหรับ S141: S135 และ S140 เป็น SELL-only ทั้งคู่; สร้าง complementary BUY
จาก coherent upside RV expansion (efficiency>=0.80) ซึ่งไม่ชน S135 inefficient reversal

## S141 — Coherent Upside RV Continuation Short-Stop 7R

ไฟล์: `strategy141.py`

ผล Backtest 2 เดือน (`2026-05-18`–`2026-07-18`):

| Signals | Closed | Expired | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 9 | 8 | 1 | 0.00% | -17.44 | -0.29 | -8.72 | 0.00 | 17.44 |

Breakdown: 5 BE, 3 SL, 0 TP; upside expansion ไปถึง 1R บ่อยแต่ไม่มี 7R tail

บทเรียนสำหรับ S142: คง generator/entry/SL แล้วลด TP เป็น 2R เพื่อแยกว่า alpha
เป็น short-horizon continuation หรือไม่มี Edge เลย; RR2 ผ่าน minimum contract แต่ไม่ trigger optimize

## S142 — Upside RV Continuation with 2R Payoff

ไฟล์: `strategy142.py`

ผล Backtest 2 เดือน (`2026-05-18`–`2026-07-18`):

| Signals | Closed | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 9 | 8 | 25.00% | -2.54 | -0.04 | -1.27 | 0.85 | 10.22 |

ลด TP แล้วมี 2 winners แต่ expectancy ยังลบ จึงยุติ coherent-upside continuation branch

บทเรียนสำหรับ S143: S128 current-window direction breakdown คือ BUY 3 ไม้ Net +46.21,
SELL 4 ไม้ Net +58.50; isolate bullish carry เป็น BUY diversifier ให้ S135/S140

## S143 — Bullish Asia Inventory Carry BUY Diversifier

ไฟล์: `strategy143.py`

ผล Backtest 2 เดือน (`2026-05-18`–`2026-07-18`):

| Signals | Closed | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 3 | 3 | 66.67% | +46.21 | +0.76 | +23.10 | 232.05 | 0.20 |

sample มีเพียง 3 ไม้และ RR1.8 จึงเป็น diversifier candidate ไม่ใช่ optimize trigger

บทเรียนสำหรับ S144: ทดสอบ portability ของ cross-session inventory carry จาก
Asia→London ไป London→NY โดยคง chronology/math และเปลี่ยน anchor/session เท่านั้น

## S144 — London-to-NY Inventory Carry Transfer

ไฟล์: `strategy144.py`

ผล Backtest 2 เดือน (`2026-05-18`–`2026-07-18`):

| Signals | Closed | Expired | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 9 | 5 | 4 | 0.00% | -52.38 | -0.86 | -26.19 | 0.00 | 52.38 |

บทเรียนสำหรับ S145: inventory carry ไม่ portable ข้าม session; falsify ด้วยการ fade
NY reclaim ฝั่งตรงข้ามที่ wick พร้อม short SL/7R แทนการจูน carry thresholds

## S145 — NY Reclaim Wick Fade Short-Stop 7R

ไฟล์: `strategy145.py`

ผล Backtest 2 เดือน (`2026-05-18`–`2026-07-18`):

| Signals | Closed | Expired | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 11 | 8 | 3 | 0.00% | -8.49 | -0.14 | -4.25 | 0.00 | 8.49 |

short wick stop ลด loss เทียบ S144 แต่ไม่มี 7R winner จึงยุติทั้ง carry/fade ของ
London→NY handoff; S146 ต้องเป็น alpha source ใหม่ ไม่เพิ่ม threshold ใน branch นี้

## S146 — Entropy-Compression Range Release Retest 7R

ไฟล์: `strategy146.py`

Edge: high sign entropy + short/long RV compression ตามด้วย closed volume/body release
นอก compression range แล้วตั้ง limit retest, structural SL และ TP7R

ผล Backtest 2 เดือน (`2026-05-18`–`2026-07-18`):

| Signals | Closed | Expired | Win rate | Net | P&L/day | P&L/month |
|---:|---:|---:|---:|---:|---:|---:|
| 2 | 0 | 2 | N/A | 0.00 | 0.00 | 0.00 |

บทเรียนสำหรับ S147: signals มีแต่ไม่มี retest fill; ใช้ next-open market execution
ตาม reality contract และคำนวณ geometry ใหม่เพื่อแยก execution failure จาก alpha failure

## S147 — Entropy Release Next-Open Market with Candle Stop

ไฟล์: `strategy147.py`

ผล Backtest 2 เดือน (`2026-05-18`–`2026-07-18`): 0 signals/0 closed/Net 0.00
เพราะ market close-to-candle-stop risk เกิน gate ทุก candidate

บทเรียนสำหรับ S148: ใช้ compression boundary เป็น structural invalidation แทน signal
candle extreme—หาก release กลับเข้า range hypothesis ถือว่าล้มเหลวและ stop ได้สั้นกว่า

## S148 — Entropy Market Release with Boundary Stop

ไฟล์: `strategy148.py`

ผล Backtest 2 เดือน: 0 signals/0 closed/Net 0.00 เพราะ breakout extension ถึง
boundary stop ยังเกิน 1.25ATR ทุก candidate; ยุติ entropy branch โดยไม่ผ่อน short-risk gate

บทเรียนสำหรับ S149: เปลี่ยนเป็น independent extreme-value/VSA alpha ที่ใช้ empirical
range/volume quantile และ wick rejection แทน volatility-compression chronology

## S149 — Empirical Extreme-Range/Volume Wick Rejection 7R

ไฟล์: `strategy149.py`

Edge: fade แท่งที่ range>=rolling q90 และ volume>=q80 เมื่อ wick ครอง>=50% และ
close กลับใกล้ปลายตรงข้าม; limit กลาง wick, SL หลัง extreme+0.10ATR, TP7R/BE1R

ผลเริ่มต้น Backtest 2 เดือน (`2026-05-18`–`2026-07-18`):

| Signals | Closed | Expired | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 85 | 42 | 43 | 11.90% | +27.57 | +0.45 | +13.78 | 1.30 | 41.40 |

เข้า RR7 survival trigger จึงหยุด S150 ชั่วคราวเพื่อ optimize payoff/BE,
empirical quantiles และ wick geometry แบบ walk-forward

Optimization S149:

- RR14 เป็น current-window peak ก่อน cliff 16R แต่ Mar–May ไม่มี winnerที่ RR12/14;
  RR7 ให้ aggregate walk-forward ดีกว่า จึงคง RR7
- BE0.75/1.0 ให้ผลเท่ากัน, BE1.25 แย่ลง; คง BE1.0
- range q90 ดีกว่า q85 และ q95; q95 ตัด winners จน Net 6 เดือนติดลบ
- volume q80 ดีกว่า q70/q90; ไม่พบ parameter change ที่ robust กว่า default
- ผล 6 เดือน default: 128 closed, WR 9.38%, Net +75.45, PF1.25, Max DD91.65

สรุป: optimization ไม่เพิ่มประสิทธิภาพโดยไม่เพิ่ม overfit/DD จึงประกาศ plateau และเริ่ม S150

## S150 — Empirical Low-Impact/High-Volume Absorption Reversal 7R

ไฟล์: `strategy150.py`

ผล Backtest 2 เดือน (`2026-05-18`–`2026-07-18`):

| Signals | Closed | Expired | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 20 | 11 | 9 | 0.00% | -24.61 | -0.40 | -12.31 | 0.00 | 24.61 |

บทเรียนสำหรับ S151: opposite breakout หลัง low-impact anchor ไม่ continue; falsify
ด้วยการ fade confirmation wick กลับไปตาม anchor direction พร้อม short stop/7R

## S151 — Absorption Confirmation Trap Fade 7R

ไฟล์: `strategy151.py`

ผลเริ่มต้น Backtest 2 เดือน (`2026-05-18`–`2026-07-18`):

| Signals | Closed | Expired | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 20 | 18 | 2 | 11.11% | +1.50 | +0.02 | +0.75 | 1.08 | 10.86 |

เข้า RR7 survival trigger แบบ marginal จึงทำ bounded payoff/BE sensitivity;
หากไม่มี improvement plateau จะหยุด optimize และเริ่ม S152

Bounded optimization: RR8 เพิ่ม current Net เป็น +4.52 แต่ RR10/12 ติดลบ;
6-month validation RR7 = -19.33/PF0.70/DD29.76 และ RR8 = -21.04/PF0.68/DD32.65
จึงเป็น in-sample false positive ไม่มี robust improvement และเริ่ม S152

## S152 — Realized-Return Skewness Tail Snapback 7R

ไฟล์: `strategy152.py`

ผล Backtest 2 เดือน (`2026-05-18`–`2026-07-18`):

| Signals | Closed | Expired | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 57 | 44 | 13 | 0.00% | -189.15 | -3.10 | -94.57 | 0.00 | 189.15 |

บทเรียนสำหรับ S153: skew-tail snapback ถูก falsify อย่างแรง; trade ตาม tail direction
ที่ opposite wick ของ reversal candle เพื่อจับ trend resumption แทนการผ่อน fade filters

## S153 — Skew-Tail Trend Resumption Short-Stop 7R

ไฟล์: `strategy153.py`

ผลเริ่มต้น Backtest 2 เดือน (`2026-05-18`–`2026-07-18`):

| Signals | Closed | Expired | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 60 | 43 | 17 | 18.60% | +29.07 | +0.48 | +14.54 | 1.54 | 14.81 |

เข้า RR7 survival trigger พร้อม sample 43 closed จึงหยุด S154 ชั่วคราวเพื่อ
optimize payoff/BE และตรวจ 6-month robustness

Optimization S153:

- BE0.75/1.0/1.25 ให้ current result เท่ากัน; คง BE1.0
- current payoff: RR7 +29.07, RR8 +41.19, RR10 +52.25, RR12 +15.12
- 6-month payoff: RR7 +46.28/PF1.27/DD41.48, RR8 +77.61/PF1.46/DD40.11,
  RR10 +92.26/PF1.54/DD37.37
- RR12 สูญเสีย winners มากในช่วงล่าสุด จึงเลือก RR10 ก่อน cliff

Recommended default: `TP_RR=10.0`, `BE_RR=1.0`; เริ่ม S154 หลัง lock/verify

ผล Backtest มาตรฐาน 2 เดือนของ optimized default:

| Signals | Closed | Expired | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 59 | 42 | 17 | 16.67% | +52.25 | +0.86 | +26.12 | 1.97 | 18.39 |

Direction breakdown: BUY 23 closed/Net +40.41, SELL 19 closed/Net +11.84

บทเรียนสำหรับ S154: isolate BUY branch เป็น directional diversifier ให้พอร์ต SELL-heavy
โดยคง optimized RR10 geometry ก่อนทำ direction-specific validation

## S154 — BUY-Only Skew-Tail Resumption RR10

ไฟล์: `strategy154.py`

ผล Backtest 2 เดือน (`2026-05-18`–`2026-07-18`):

| Signals | Closed | Expired | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 34 | 23 | 11 | 17.39% | +40.41 | +0.66 | +20.21 | 2.43 | 15.03 |

Direction-specific optimization: current RR8 +37.19/DD10.71, RR10 +40.41/DD15.03;
6-month RR8 +103.51/PF2.21/DD17.04, RR10 +119.74/PF2.40/DD17.04
จึงคง RR10 และเริ่ม S155 เพื่อวัด SELL branch แยก

## S155 — SELL-Only Skew-Tail Resumption RR10

ไฟล์: `strategy155.py`

ผล Backtest 2 เดือน: 25 signals, 19 closed, WR15.79%, Net +11.84,
P&L/day +0.19, P&L/month +5.92, PF1.46, Max DD14.05

6-month validation: 58 closed, WR6.90%, Net -27.48, PF0.67, Max DD49.28;
เป็น current-window false positive จึงไม่เปิด grid และเริ่ม S156

## S156 — Robust First-Jump Retracement Continuation 7R

ไฟล์: `strategy156.py`

ผล Backtest 2 เดือน (`2026-05-18`–`2026-07-18`, M5, spread 0.20, lot 0.01):

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 71 | 51 | 19 | 0 | 7.84% | -16.17 | -0.27 | -8.09 | 0.89 | 95.54 |

ระบบจำลองเปิดและปิดสถานะได้จริง แต่ผลลัพธ์ไม่ผ่าน survival trigger: sample เพียงพอ,
RR7 ถูกบังคับใช้ และไม่มี invalid order แต่ Net/PF ติดลบและ drawdown สูง จึงไม่ optimize S156
และใช้บทเรียนเรื่อง first-jump continuation เพื่อออกแบบ S157 ต่อไป

## S157 — Robust First-Jump Exhaustion Fade 7R

ไฟล์: `strategy157.py`

ผล Backtest 2 เดือน (`2026-05-18`–`2026-07-18`, M5, spread 0.20, lot 0.01):

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 104 | 93 | 11 | 0 | 8.60% | -28.91 | -0.47 | -14.45 | 0.67 | 50.00 |

การกลับฝั่ง fade robust jump ไม่ผ่านเช่นเดียวกับ continuation: BUY และ SELL ติดลบทั้งคู่
จึง falsify การเลือกทิศทันทีหลัง shock และไม่ optimize S157

## S158 — Post-Jump Acceptance Continuation (Optimized 80R)

ไฟล์: `strategy158.py`

Edge: ไม่เดาทิศจาก jump bar ทันที แต่รอ closed bar ถัดไปยืนยันว่าราคารักษาอย่างน้อยครึ่งหนึ่ง
ของ jump body และปิดใน 20% ปลาย range ตามทิศเดิม จากนั้นเข้า limit บน retrace ของ confirmation
พร้อม SL หลัง acceptance boundary + ATR buffer ทำให้ความเสี่ยงสั้นและแยกจาก jump/fade strategies เดิม

ผลเริ่มต้น RR7, confirmation 70% ใน Backtest 2 เดือน:

| Signals | Closed | Expired | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 5 | 5 | 0 | 20.00% | +21.80 | +0.36 | +10.90 | 2.30 | 16.71 |

เข้า survival trigger จึงหยุดสร้าง S159 และทำ bounded optimization:

- confirmation 80%: 2 เดือน 4 closed/Net +29.00/PF4.05/DD9.51;
  6 เดือน 9 closed/Net +20.67/PF2.16/DD9.51
- confirmation 60% บน 6 เดือนกลับมาติดลบ -2.73 จึงยืนยันว่าคุณภาพ acceptance เป็น gate สำคัญ
- 6-month payoff: RR7 +20.67, RR8 +26.20, RR10 +37.46, RR12 +48.52,
  RR30 +148.06, RR80 +424.56, RR100 +544.47, RR150 -8.33
- payoff cliff อยู่ระหว่าง 100R–150R; เลือก RR80 เป็น haircut 20% จากระดับ 100R ที่พิสูจน์ว่าแตะได้
  แทนการตั้ง TP ใกล้ขอบ MFE ของ winner เดียว

ผล Backtest มาตรฐาน 2 เดือนของ optimized default (`CONFIRM_CLOSE_FRACTION=0.80`, `TP_RR=80`):

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 3 | 3 | 0 | 0 | 33.33% | +432.89 | +7.10 | +216.45 | 47.50 | 9.31 |

ผล 6 เดือนของ optimized RR80 (cached sweep ที่เทียบ RR7 ตรงกับ authoritative runner):
8 signals/8 closed, WR12.50%, Net +424.56, PF25.07, Max DD9.31

ข้อจำกัด: ผลกำไรพึ่งพา tail winner เพียงหนึ่งไม้ แม้ผ่านทั้ง 2 และ 6 เดือน จึงหยุดการจูน feature
ที่เสี่ยง overfit หลังพบ payoff cliff และใช้บทเรียนเรื่อง confirmed acceptance พัฒนา S159 ต่อไป

## S159 — Multi-Bar Post-Jump Acceptance Breakout 7R

ไฟล์: `strategy159.py`

ผล Backtest 2 เดือน (`2026-05-18`–`2026-07-18`, M5, spread 0.20, lot 0.01):

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 3 | 3 | 0 | 0 | 0.00% | -5.19 | -0.09 | -2.60 | 0.00 | 5.19 |

การรอหลายแท่งแล้วตาม first breakout ไม่ช่วยกระจาย tail winner ของ S158 และแพ้ทั้งสามเหตุการณ์
จึงไม่ optimize; S160 จะทดสอบ false-breakout sweep ที่ปิดกลับเข้า accepted range แทน

## S160 — Accepted-Range Failed Sweep 7R

ไฟล์: `strategy160.py`

ผล Backtest 2 เดือน (`2026-05-18`–`2026-07-18`, M5, spread 0.20, lot 0.01):

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 5 | 3 | 2 | 0 | 0.00% | -10.09 | -0.17 | -5.05 | 0.00 | 10.09 |

การ fade sweep หลัง multi-bar acceptance แพ้ทั้งหมดเช่นกัน จึงยุติการขยาย jump-anchor family
หลัง S158 และเปลี่ยน S161 ไปใช้ variance-ratio/serial-persistence edge ที่เป็นคนละแกน

## S161 — SELL Variance-Ratio Trend Burst (Optimized 40R)

ไฟล์: `strategy161.py`

Edge: ใช้ Lo–MacKinlay-style variance ratio ที่ lag 2 แยก regime ซึ่งผลตอบแทนมี serial persistence
จาก noise/mean reversion แล้วเข้า limit บน retrace ของ high-efficiency directional burst โดย SL อยู่หลัง
แท่งยืนยัน + ATR buffer จึงเป็นคนละแกนกับ jump acceptance และ skew-tail strategies

ผลเริ่มต้นสองทิศทาง RR7 ใน Backtest 2 เดือน:

| Signals | Closed | Expired | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 20 | 14 | 6 | 14.29% | +35.47 | +0.58 | +17.73 | 2.27 | 17.41 |

6-month default สองทิศทาง: 48 closed, WR6.25%, Net -48.19, PF0.62, DD94.04
จึงทำ bounded direction diagnostic:

- BUY: 2 เดือน 0/6 TP, Net -11.20; 6 เดือน 0/27 TP, Net -60.73
- SELL: 2 เดือน 2/8 TP, Net +46.67; 6 เดือน 3/21 TP, Net +12.54

ล็อก `ALLOW_BUY=False`, `ALLOW_SELL=True`; Backtest detector ใหม่ที่ RR7:

- 2 เดือน: 12 signals, 8 closed, WR25.00%, Net +46.67, PF3.78, DD9.55
- 6 เดือน: 30 signals, 22 closed, WR13.64%, Net +12.34, PF1.19, DD41.37

Bounded payoff/BE optimization ใช้ cached simulator ที่เทียบ RR7 ตรงกับ authoritative runner:

- 6 เดือน: RR10 +46.08/DD35.19, RR20 +116.67/DD55.80,
  RR30 +207.87/DD55.80, RR40 +299.07/PF5.58/DD55.80
- ที่ RR50 จำนวน winners ลดจาก 2 เหลือ 1 และ Net ลดเป็น +148.46; RR70 +234.06
  จึงพบ payoff cliff ระหว่าง RR40–50 และเลือก RR40 ก่อน cliff
- BE0.75 ที่ RR7 ลด DD เหลือ 26.87 แต่ Net 36.24 ต่ำกว่า payoff optimization;
  คง BE1.0

ผล Backtest มาตรฐาน 2 เดือนของ optimized default (`SELL-only`, `TP_RR=40`, `BE_RR=1`):

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 11 | 7 | 4 | 0 | 28.57% | +347.83 | +5.70 | +173.92 | 21.97 | 9.55 |

ข้อจำกัด: 6-month DD ของ RR40 เท่ากับ 55.80 และกำไรยังพึ่ง winners เพียงสองไม้ แม้ breadth
ดีกว่า S158; หยุด feature tuning หลังพบ direction edge และ payoff cliff แล้วเริ่ม S162 ต่อ

## S162 — Bearish VR Follow-Through Acceptance (Optimized 70R)

ไฟล์: `strategy162.py`

Edge: ต่อจาก SELL variance-ratio burst ของ S161 แต่รอ closed bar ถัดไปยืนยัน lower acceptance
ก่อนเข้า limit บน retrace เพื่อกรอง false burst และลด drawdown โดย SL อิง confirmation wick + ATR

ผลเริ่มต้น RR7 ใน Backtest 2 เดือน (`2026-05-18`–`2026-07-18`, M5, spread 0.20, lot 0.01):

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 7 | 4 | 3 | 0 | 25.00% | +19.84 | +0.33 | +9.92 | 2.40 | 14.20 |

6-month RR7: 12 signals, 7 closed, WR14.29%, Net +16.52, PF1.94, Max DD14.20

Payoff/BE sweep ที่ผ่าน exactness guard:

- 2 เดือน: RR20 +83.41, RR30 +132.31, RR40 +181.21; winner ยังอยู่ครบหนึ่งไม้
- 6 เดือน: RR20 +80.09, RR30 +128.99, RR40 +177.89/PF11.15/DD14.20
- extended 6 เดือน: RR50 +226.79, RR70 +324.59/PF19.53/DD14.20;
  RR100 และ RR150 ไม่ถึง TP และกลับเป็น Net -3.32 จึงพบ payoff cliff ระหว่าง RR70–100
- BE0.75 RR7: 2 เดือน Net +33.44/DD0.60; 6 เดือน Net +30.12/DD3.32
  แต่ expectancy ต่ำกว่า RR70 จึงคง BE1.0

เลือก `TP_RR=70` ซึ่งต่ำกว่าขอบที่ล้มเหลว 100R อยู่ 30% และหยุด payoff tuning หลังพบ cliff

ผล Backtest มาตรฐาน 2 เดือนของ optimized default (`TP_RR=70`, `BE_RR=1`):

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 7 | 4 | 3 | 0 | 25.00% | +327.91 | +5.38 | +163.96 | 24.09 | 14.20 |

ข้อจำกัด: sample 6 เดือนมี winner เพียงหนึ่งไม้ แม้ delayed acceptance ลด DD ได้มากกว่า S161;
จึงไม่จูน feature เพิ่มและเริ่ม S163 เพื่อหา edge ที่มี breadth มากขึ้น

## S163 — VR Failed-Rally Rejection 7R

ไฟล์: `strategy163.py`

ผล Backtest 2 เดือน (`2026-05-18`–`2026-07-18`, M5, spread 0.20, lot 0.01):

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 | 2 | 0 | 0 | 0.00% | -0.40 | -0.01 | -0.20 | 0.00 | 0.40 |

revision จำกัดเฉพาะ execution (`ENTRY_RANGE_FRACTION=0.40`, `CANCEL_BARS=4`) ทำให้ fill ครบ
แต่ทั้งสองไม้จบ BE และไม่มี TP จึงไม่ optimize; S164 เปลี่ยน regime เป็น downside semivariance
imbalance เพื่อเพิ่ม breadth แทนการขยาย variance-ratio family ต่อ

## S164 — Downside-Semivariance Weak-Rally Rejection 7R

ไฟล์: `strategy164.py`

ผล Backtest 2 เดือน (`2026-05-18`–`2026-07-18`, M5, spread 0.20, lot 0.01):

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 73 | 55 | 18 | 0 | 9.09% | -33.42 | -0.55 | -16.71 | 0.79 | 60.03 |

semivariance regime เพิ่ม breadth ได้แต่ weak-rally SELL ไม่มี expectancy ที่ RR7 จึงไม่ optimize;
S165 จะทดสอบ capitulation reversal BUY หลัง high-volume bearish exhaustion และ bullish reclaim

## S165 — Downside-Semivariance Capitulation Reclaim BUY (Optimized 9R)

ไฟล์: `strategy165.py`

Edge: ตรวจ downside semivariance ที่ครอง upside variance พร้อม net bearish displacement แล้วรอ
high-volume bearish exhaustion และ closed bullish reclaim เหนือ midpoint ก่อนเข้า BUY limit ทำให้เป็น
long-side mean-reversion diversifier ต่อพอร์ตที่มี S161/S162 ฝั่ง SELL

ผลเริ่มต้น RR7 ใน Backtest 2 เดือน (`2026-05-18`–`2026-07-18`, M5, spread 0.20, lot 0.01):

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 33 | 27 | 6 | 0 | 7.41% | +43.38 | +0.71 | +21.69 | 1.75 | 36.78 |

6-month RR7: 79 signals, 55 closed, WR9.09%, Net +176.18, PF2.52, Max DD36.78

Exact payoff/BE optimization:

- 6 เดือน RR8: 55 closed/5 TP, Net +218.01, PF2.88, DD36.78
- 6 เดือน RR9: 55 closed/5 TP, Net +259.84, PF3.25, DD36.78
- 6 เดือน RR10: 52 closed/4 TP, Net +187.21 — winner ลดลง จึงพบ cliff ระหว่าง RR9–10
- BE1.25 RR7 เพิ่มเป็น 7 TP/Net +189.42 แต่ DD เพิ่มเป็น 50.15; คง BE1.0
- RR20 เหลือ 1 TP และ RR30+ ไม่มี TP จึงหยุด payoff tuning

ผล Backtest มาตรฐาน 2 เดือนของ optimized default (`TP_RR=9`, `BE_RR=1`):

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 33 | 27 | 6 | 0 | 7.41% | +72.40 | +1.19 | +36.20 | 2.25 | 36.78 |

S165 มี sample และ direction diversification ดีกว่า S158/S162 แม้ win rate ต่ำตาม high-R payoff;
หยุด optimization หลังพบ cliff แล้วเริ่ม S166 ต่อ

## S166 — Upside-Semivariance Capitulation Reclaim SELL (Optimized 16R)

ไฟล์: `strategy166.py`

Edge: symmetric counterpart ของ S165 ใช้ upside semivariance + bullish displacement ตรวจภาวะ
buying capitulation จากนั้นรอ high-volume bullish exhaustion และ bearish reclaim ก่อนเข้า SELL limit
จึงช่วย balance S165 BUY โดยใช้ feature family เดียวกันแต่คนละ direction/regime

ผลเริ่มต้น RR7 ใน Backtest 2 เดือน (`2026-05-18`–`2026-07-18`, M5, spread 0.20, lot 0.01):

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 35 | 19 | 16 | 0 | 10.53% | +77.97 | +1.28 | +38.98 | 8.82 | 8.17 |

6-month RR7: 83 signals, 51 closed, WR7.84%, Net +39.29, PF1.40, Max DD57.38

Exact payoff/BE optimization:

- 2 เดือน RR16: 19 closed/2 TP, Net +191.55, PF20.21, DD8.17; RR20 ไม่มี TP
- 6 เดือน RR8: 51 closed/4 TP, Net +58.92, PF1.61, DD57.38
- 6 เดือน RR16 + BE1.0: 51 closed/2 TP, Net +103.80, PF2.06, DD89.15
- RR17–19 เหลือเพียง 1 TP และ RR20 ไม่มี TP จึงพบ cliff ระหว่าง RR16–17
- interaction RR16 + BE0.75: 52 closed/2 TP, Net +136.60, PF3.10, DD59.94
- BE0.75 ชนะ BE1.0 ที่ RR16 ทั้ง Net, PF และ DD จึงล็อก optimized default เป็น BE0.75

ผล Backtest มาตรฐาน 2 เดือนของ optimized default (`TP_RR=16`, `BE_RR=0.75`):

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 35 | 19 | 16 | 0 | 10.53% | +195.14 | +3.20 | +97.57 | 31.59 | 4.58 |

ข้อจำกัด: RR16 ยังเหลือ winners เพียงสองไม้ในช่วง 6 เดือน แต่ interaction BE0.75 ลด DD จาก 89.15 เหลือ 59.94
พร้อมเพิ่ม Net เป็น +136.60; หยุด payoff tuning หลัง RR16–17 cliff แล้วเริ่ม S167 เพื่อหา regime/filter
ที่รักษา breadth ของฝั่ง SELL ได้มากขึ้น

## S167 — Bearish Directional-Efficiency Volume Hand-off 7R

ไฟล์: `strategy167.py`

Edge: ใช้ Kaufman-style directional efficiency แยกขาลงที่มี displacement จริงออกจาก noise แล้วรอ
low-volume bullish pullback ตามด้วย bearish rejection ที่ volume ขยาย ก่อนตั้ง SELL limit เหนือราคาปิด
เพื่อบีบ structural SL ให้สั้น โดยไม่ใช้ semivariance ซ้ำกับ S164/S166

ผล Backtest 2 เดือน (`2026-05-18`–`2026-07-18`, M5, spread 0.20, lot 0.01):

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 14 | 9 | 5 | 0 | 0.00% | -19.96 | -0.33 | -9.98 | 0.00 | 19.96 |

ไม่มี TP และ expectancy เป็นลบ จึงไม่ optimize และทดสอบ bullish symmetry เป็น S168

## S168 — Bullish Directional-Efficiency Volume Hand-off 7R

ไฟล์: `strategy168.py`

Edge: symmetric BUY ของ S167 ใช้ efficient advance + low-volume bearish pullback + expanding-volume
bullish rejection เพื่อเพิ่ม long-side diversification ให้พอร์ต

ผล Backtest 2 เดือน (`2026-05-18`–`2026-07-18`, M5, spread 0.20, lot 0.01):

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 10 | 8 | 2 | 0 | 0.00% | -16.65 | -0.27 | -8.33 | 0.00 | 16.65 |

ไม่มี TP เช่นกัน จึงยุติ directional-efficiency hand-off family และเปลี่ยน S169 เป็น volatility-compression breakout

## S169 — Bearish Volatility-Compression Expansion Retrace 7R

ไฟล์: `strategy169.py`

Edge: วัด median true range ระยะสั้นเทียบ baseline เพื่อยืนยัน compression จากนั้นต้องมี bearish expansion
ปิดต่ำกว่าโครงสร้างเดิมพร้อม volume อยู่ใน upper quantile แล้วจึงรอ SELL limit retrace เพื่อให้ SL อยู่เหนือแท่ง breakout

ผล Backtest 2 เดือน (`2026-05-18`–`2026-07-18`, M5, spread 0.20, lot 0.01):

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 1 | 0 | 0 | 0.00% | -0.20 | -0.00 | -0.10 | 0.00 | 0.20 |

มีเพียงหนึ่ง sample และจบ BE หลัง spread จึงไม่ optimize; ทดสอบ bullish symmetry เป็น S170

## S170 — Bullish Volatility-Compression Expansion Retrace 7R

ไฟล์: `strategy170.py`

Edge: symmetric BUY ของ S169 รอ compression แล้วต้องมี high-volume bullish expansion ปิดเหนือโครงสร้าง
ก่อนรอ limit retrace เพื่อรักษา short structural SL

ผล Backtest 2 เดือน (`2026-05-18`–`2026-07-18`, M5, spread 0.20, lot 0.01):

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 3 | 3 | 0 | 0 | 0.00% | -6.13 | -0.10 | -3.07 | 0.00 | 6.13 |

ไม่มี TP และ breadth ต่ำเช่นเดียวกับ S169 จึงยุติ compression-expansion family แล้วเริ่ม S171 ด้วย regime ใหม่

## S171 — Return-Persistence Structural Breakout Retrace 7R

ไฟล์: `strategy171.py`

Edge: ใช้ lag-1 autocorrelation ของ closed-bar returns เพื่อรับเฉพาะ regime ที่ผลตอบแทนมี positive persistence
และ displacement ชัดเจน จากนั้นต้องมี high-volume breakout ปิดทะลุโครงสร้างตามทิศ regime ก่อนรอ limit retrace
กลยุทธ์รองรับทั้ง BUY/SELL และวาง SL หลังแท่ง breakout ตาม ATR

ผล Backtest 2 เดือน (`2026-05-18`–`2026-07-18`, M5, spread 0.20, lot 0.01):

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 38 | 24 | 14 | 0 | 8.33% | +20.65 | +0.34 | +10.33 | 1.43 | 34.91 |

เนื่องจาก RR7 และ sample 24 ไม้ให้ expectancy บวก จึงหยุดสร้าง ID ชั่วคราวและตรวจ survival 6 เดือน:

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 120 | 91 | 29 | 0 | 4.40% | -54.40 | -0.30 | -9.07 | 0.75 | 95.79 |

Direction decomposition ไม่พบ revision ที่ผ่านทั้งสองช่วง: BUY 2 เดือน +26.76 แต่ 6 เดือน -51.61;
SELL 2 เดือน -6.11 และ 6 เดือน -2.79 จึงไม่เลือก direction จาก sample เฉพาะช่วงและไม่ optimize payoff
หลัง fail survival gate ให้เริ่ม S172 ด้วย feature family ใหม่

## S172 — Lower-Tail Skewness Exhaustion Reclaim BUY (Optimized 10.8R)

ไฟล์: `strategy172.py`

Edge: วัด standardized third moment ของ closed-bar returns เพื่อหา negative-skew regime และใช้ empirical
lower-tail quantile ระบุ bearish shock ที่ผิดปกติ แท่ง shock ต้องมี body/volume แบบ capitulation และปิดใกล้ low;
จากนั้นรอ bullish bar ปิด reclaim เหนือ midpoint พร้อม volume confirmation ก่อนตั้ง BUY limit พร้อม structural SL
ใต้ low ของ shock/reclaim จึงเป็น long-side tail-reversal diversifier ที่ต่างจาก persistence และ compression families

ผลเริ่มต้น RR7/BE1 ใน Backtest 2 เดือน (`2026-05-18`–`2026-07-18`, M5, spread 0.20, lot 0.01):

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 28 | 22 | 6 | 0 | 4.55% | +31.99 | +0.52 | +16.00 | 2.07 | 29.77 |

6-month survival RR7/BE1: 85 signals, 62 closed, 5 TP, WR8.06%, Net +150.75, PF2.22, DD71.78

Exact payoff/BE optimization บนข้อมูล 6 เดือน:

- RR10/BE1: 62 closed/5 TP, Net +268.53, PF3.18, DD71.78
- RR20/BE1: 57 closed/2 TP, Net +272.00, PF3.30, DD71.78 — net ใกล้ RR10 แต่ breadth ต่ำกว่า
- RR10/BE0.75: 63 closed/5 TP, Net +311.00, PF4.86, DD51.73
- RR20/BE0.75: 58 closed/2 TP, Net +314.47, PF5.14, DD51.73 — เพิ่มเพียง 3.47 แต่เสีย 3 winners
- RR10.5/BE0.75: 63 closed/5 TP, Net +330.63, PF5.10, DD51.73
- RR10.8/BE0.75: 63 closed/5 TP, Net +342.42, PF5.25, DD51.73
- RR10.9/BE0.75: winners ลดเหลือ 4 และ Net ลดเป็น +309.82 จึงพบ payoff cliff ระหว่าง RR10.8–10.9

ล็อก optimized default ที่ `TP_RR=10.8`, `BE_RR=0.75` ซึ่งเป็น payoff สูงสุดก่อนเสีย winner breadth

ผล Backtest มาตรฐาน 2 เดือนของ optimized default:

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 29 | 23 | 6 | 0 | 4.35% | +77.01 | +1.26 | +38.50 | 5.19 | 18.38 |

ผลยืนยัน 6 เดือนของ optimized default:

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 86 | 63 | 23 | 0 | 7.94% | +342.42 | +1.89 | +57.07 | 5.25 | 51.73 |

หยุดสร้าง strategy ID ใหม่ไว้ที่ S172 ระหว่าง optimization; payoff tuning สิ้นสุดหลังยืนยัน RR10.8–10.9 cliff
การขยาย validation เป็น 12 เดือนไม่สามารถทำได้จาก authoritative IUX profile เพราะ retained M5 history ไม่พอ
(`not enough MT5 rates`); จึงยึด 6 เดือนเป็นขอบเขตข้อมูลสูงสุดที่ตรวจสอบได้ แล้วกลับไปเริ่ม S173

## S173 — Upper-Tail Skewness Exhaustion Reclaim SELL (Optimized 16.2R)

ไฟล์: `strategy173.py`

Edge: symmetric SELL counterpart ของ S172 ใช้ positive skewness และ empirical upper-tail quantile ระบุ
high-volume bullish shock/buying climax แล้วรอ bearish bar ปิด reclaim ต่ำกว่า midpoint ก่อนตั้ง SELL limit
พร้อม structural SL เหนือ high ของ shock/reclaim จึงช่วย balance S172 BUY ด้วย distribution-tail feature เดียวกัน
แต่คนละ direction

ผลเริ่มต้น RR7/BE1 ใน Backtest 2 เดือน (`2026-05-18`–`2026-07-18`, M5, spread 0.20, lot 0.01):

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 44 | 28 | 16 | 0 | 14.29% | +86.48 | +1.42 | +43.24 | 2.69 | 28.62 |

6-month survival RR7/BE1: 90 signals, 64 closed, 5 TP, WR7.81%, Net +10.17, PF1.06, DD108.41

Exact payoff/BE optimization บนข้อมูล 6 เดือน:

- RR7/BE1.25: 64 closed/7 TP, Net +73.09, PF1.40, DD53.08
- RR7/BE1.50: 63 closed/8 TP, Net +74.83, PF1.37, DD53.08
- RR16/BE1: 64 closed/4 TP, Net +155.38, PF1.97, DD116.35
- RR16/BE0.75: 64 closed/4 TP, Net +212.02, PF3.04, DD71.80
- RR16.2/BE0.75: 64 closed/4 TP, Net +215.99, PF3.08, DD71.80
- RR16.3/BE0.75: winners ลดเหลือ 3 และ Net ลดเป็น +121.67 จึงพบ payoff cliff ระหว่าง RR16.2–16.3

ล็อก optimized default ที่ `TP_RR=16.2`, `BE_RR=0.75` ซึ่งเป็น payoff สูงสุดก่อนเสีย winner breadth

ผล Backtest มาตรฐาน 2 เดือนของ optimized default:

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 43 | 28 | 15 | 0 | 14.29% | +287.39 | +4.71 | +143.70 | 9.86 | 20.12 |

ผลยืนยัน 6 เดือนของ optimized default:

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 89 | 64 | 25 | 0 | 6.25% | +215.99 | +1.19 | +36.00 | 3.08 | 71.80 |

payoff tuning สิ้นสุดหลังยืนยัน RR16.2–16.3 cliff; กลับไปเริ่ม S174 ด้วย feature family ถัดไป

## S174 — Bipower Jump-Exhaustion Reclaim (Optimized 9R)

ไฟล์: `strategy174.py`

Edge: แยก discontinuous price jump ด้วย Realized Variance ลบ Bipower Variation ซึ่งลดอิทธิพลของ
continuous diffusion; jump bar ต้องมี empirical tail magnitude, directional body และ high volume จากนั้นรอ
opposite reclaim ปิดผ่าน midpoint ก่อนเข้า mean-reversion แบบ BUY หรือ SELL กลยุทธ์จึงกระจายสองทิศ
โดยไม่พึ่ง skewness regime ของ S172/S173

ผลเริ่มต้น RR7/BE1 ใน Backtest 2 เดือน (`2026-05-18`–`2026-07-18`, M5, spread 0.20, lot 0.01):

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 42 | 30 | 12 | 0 | 10.00% | +59.58 | +0.98 | +29.79 | 1.83 | 29.60 |

6-month survival RR7/BE1: 116 signals, 76 closed, 7 TP, WR9.21%, Net +118.24, PF1.63, DD68.52

Exact payoff/BE optimization บนข้อมูล 6 เดือน:

- RR7/BE0.5: 76 closed/7 TP, Net +223.78, PF3.75, DD28.97
- RR9/BE1: 76 closed/7 TP, Net +205.82, PF2.10, DD68.52
- RR9/BE0.4: 76 closed/7 TP, Net +313.96, PF4.98, DD28.97
- RR9/BE0.25–0.38: ผลเท่ากัน Net +317.46, PF5.22, DD28.97
- RR9/BE0.39: Net ลดเป็น +313.96 จึงเลือก BE0.38 ซึ่งช้าที่สุดบน plateau
- RR9.1/BE0.4: winners ลดเหลือ 6 และ Net ลดเป็น +280.65 จึงพบ payoff cliff ระหว่าง RR9.0–9.1

ล็อก optimized default ที่ `TP_RR=9.0`, `BE_RR=0.38`

ผล Backtest มาตรฐาน 2 เดือนของ optimized default:

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 42 | 30 | 12 | 0 | 10.00% | +134.94 | +2.21 | +67.47 | 5.02 | 18.84 |

ผลยืนยัน 6 เดือนของ optimized default:

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 116 | 76 | 40 | 0 | 9.21% | +317.46 | +1.75 | +52.91 | 5.22 | 28.97 |

optimization สิ้นสุดหลัง payoff/BE plateau และ RR9.0–9.1 cliff; กลับไปเริ่ม S175

## S175 — Amihud Liquidity-Vacuum Reclaim 7R

ไฟล์: `strategy175.py`

Edge: วัด absolute price displacement ต่อ tick volume แบบ Amihud impact เพื่อหา low-liquidity vacuum shock
แล้วต้องมี opposite reclaim พร้อม volume ฟื้นตัวก่อนเข้า mean-reversion ทั้ง BUY/SELL ซึ่งตรงข้ามกับ S174
ที่ต้องการ high-volume discontinuity

ผล Backtest 2 เดือน (`2026-05-18`–`2026-07-18`, M5, spread 0.20, lot 0.01):

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 31 | 20 | 11 | 0 | 5.00% | -9.02 | -0.15 | -4.51 | 0.80 | 44.88 |

expectancy ติดลบที่ RR7 จึงไม่ optimize และเปลี่ยน S176 เป็น robust median/MAD location anomaly

## S176 — Median/MAD Location-Anomaly Reclaim (Optimized Robust 10R)

ไฟล์: `strategy176.py`

Edge: ใช้ rolling median และ scaled Median Absolute Deviation วัด robust location z-score ซึ่งทน outlier
กว่าค่า mean/std; รับเฉพาะ high-volume close ที่เบี่ยงจากค่ากลางมากและมี directional body จากนั้นรอแท่ง
opposite ปิด reclaim ผ่าน midpoint ก่อนเข้า mean-reversion ทั้ง BUY/SELL พร้อม structural SL

ผลเริ่มต้น RR7/BE1 ใน Backtest 2 เดือน (`2026-05-18`–`2026-07-18`, M5, spread 0.20, lot 0.01):

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 115 | 79 | 36 | 0 | 7.59% | +68.74 | +1.13 | +34.37 | 1.37 | 84.35 |

6-month survival RR7/BE1: 283 signals, 187 closed, 13 TP, WR6.95%, Net +167.55, PF1.33, DD112.99

Exact payoff/BE optimization และ cross-window audit:

- RR7/BE1.5: 6 เดือน 185 closed/21 TP, Net +343.87, PF1.51, DD124.97
- RR10/BE1.25: 6 เดือน 178 closed/16 TP, Net +513.46, PF1.89, DD110.38;
  2 เดือน Net +174.12
- RR16/BE1.25: 6 เดือน Net +626.72 แต่ 2 เดือน +106.00 และ DD6เดือน 153.70
- RR22/BE1.14: 6 เดือน Net +869.34 แต่ 2 เดือนเหลือเพียง +23.81/PF1.13 จึงปฏิเสธ historical optimum
  เพื่อหลีกเลี่ยงการ overfit ช่วงเก่า
- RR10/BE1.16–1.18: ผลเท่ากันทั้งสองหน้าต่าง; 6 เดือน 16 TP/Net +543.21/PF2.00/DD110.38
  และ 2 เดือน 7 TP/Net +203.87/PF1.97/DD73.89
- BE1.15 เสีย winner หนึ่งไม้; BE1.19 เริ่มลด Net จึงเลือก BE1.18 ซึ่งช้าที่สุดบน plateau
- RR10.2 เสีย winner ทั้ง 2 และ 6 เดือน จึงพบ payoff cliff ระหว่าง RR10.0–10.2

ล็อก cross-window robust default ที่ `TP_RR=10.0`, `BE_RR=1.18`

ผล Backtest มาตรฐาน 2 เดือนของ optimized default:

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 112 | 77 | 35 | 0 | 9.09% | +203.87 | +3.34 | +101.94 | 1.97 | 73.89 |

ผลยืนยัน 6 เดือนของ optimized default:

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 272 | 178 | 94 | 0 | 8.99% | +543.21 | +3.00 | +90.53 | 2.00 | 110.38 |

optimization สิ้นสุดหลัง cross-window plateau และ RR10.0–10.2 cliff; กลับไปเริ่ม S177

## S177 — Signed-Volume/Price Divergence Reclaim 7R

ไฟล์: `strategy177.py`

Edge: สร้าง signed tick-volume proxy จากทิศ candle body แล้วเปรียบ cumulative flow กับ net price displacement;
เมื่อราคาทำ structural extreme แต่ signed flow ไม่ยืนยัน ต้องมี high-volume exhaustion และ opposite reclaim
ก่อนเข้า reversal ทั้ง BUY/SELL

ผล Backtest 2 เดือน (`2026-05-18`–`2026-07-18`, M5, spread 0.20, lot 0.01):

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 53 | 42 | 11 | 0 | 4.76% | +5.07 | +0.08 | +2.54 | 1.06 | 31.63 |

6-month survival check: 132 signals, 88 closed, WR6.82%, Net -8.07, PF0.96, DD88.00

ผลล่าสุดบวกเล็กน้อยแต่ 6 เดือนติดลบ จึง fail survival gate และไม่ optimize; เปลี่ยน feature family ใน S178

## S178 — Volume-Weighted Fair-Value Anomaly Reclaim (Optimized 10R)

ไฟล์: `strategy178.py`

Edge: คำนวณ rolling fair value จาก typical price ถ่วงด้วย tick volume และ weighted dispersion เพื่อหา
institutional-price anomaly; exhaustion ต้องเบี่ยงจาก fair value พร้อม body/volume ชัด แล้วรอ opposite bar
ปิด reclaim กลับเข้าหาค่ากลางก่อนเข้า mean-reversion ทั้ง BUY/SELL ต่างจาก unweighted median/MAD ของ S176

ผลเริ่มต้น RR7/BE1 ใน Backtest 2 เดือน (`2026-05-18`–`2026-07-18`, M5, spread 0.20, lot 0.01):

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 94 | 61 | 33 | 0 | 9.84% | +125.58 | +2.06 | +62.79 | 1.97 | 46.25 |

6-month survival RR7/BE1: 241 signals, 158 closed, 12 TP, WR7.59%, Net +160.67, PF1.39, DD110.04

Exact payoff/BE optimization พร้อม cross-window audit:

- RR7/BE1.18: 6 เดือน 16 TP/Net +271.18 แต่ 2 เดือน +120.23/DD64.72
- RR9/BE1: 6 เดือน 10 TP/Net +264.08 และ 2 เดือน +169.46
- RR10/BE1: 6 เดือน 9 TP/Net +231.29 แต่ 2 เดือน +209.95/PF2.72/DD51.12
- RR10/BE1.14–1.18: ผลเท่ากันในทั้งสองหน้าต่าง; 6 เดือน 12 TP/Net +388.04/PF1.87/DD120.13
  และ 2 เดือน 5 TP/Net +186.82/PF2.29/DD69.59
- BE1.12 มีเพียง 11 TP ใน 6 เดือน; BE1.20 เริ่มลด Net จึงเลือก BE1.18 ซึ่งช้าที่สุดบน plateau
- RR10.2 เสีย winner ในทั้งสองหน้าต่าง จึงพบ payoff cliff ระหว่าง RR10.0–10.2

ล็อก cross-window optimized default ที่ `TP_RR=10.0`, `BE_RR=1.18`

ผล Backtest มาตรฐาน 2 เดือนของ optimized default:

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 92 | 60 | 32 | 0 | 8.33% | +186.82 | +3.06 | +93.41 | 2.29 | 69.59 |

ผลยืนยัน 6 เดือนของ optimized default:

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 234 | 153 | 81 | 0 | 7.84% | +388.04 | +2.14 | +64.67 | 1.87 | 120.13 |

optimization สิ้นสุดหลัง cross-window BE plateau และ RR10.0–10.2 cliff; กลับไปเริ่ม S179

## S179 — Empirical-CDF Tail Reentry 7R

ไฟล์: `strategy179.py`

Edge: ใช้ empirical 5%/95% rolling close quantiles แบบ non-parametric ระบุ distribution-tail extension
แล้วบังคับให้แท่งถัดไปปิดกลับเข้า distribution พร้อม volume ก่อนเข้า reversal ทั้ง BUY/SELL

ผล Backtest 2 เดือน (`2026-05-18`–`2026-07-18`, M5, spread 0.20, lot 0.01):

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 71 | 50 | 21 | 0 | 2.00% | -82.61 | -1.35 | -41.31 | 0.29 | 97.58 |

distribution reentry ไม่มี expectancy ที่ RR7 จึงไม่ optimize; S180 จะใช้ trend-adjusted regression residual แทน raw empirical tail

## S180 — Trend-Adjusted Regression-Residual Reclaim (Optimized 16R)

ไฟล์: `strategy180.py`

Edge: ใช้ OLS rolling trend แยก directional drift ออกจากราคาปิด แล้ววัด residual anomaly เทียบกับ residual RMS;
เข้า mean reversion เฉพาะเมื่อแท่ง exhaustion เคลื่อนไปทางเดียวกับ residual พร้อม volume สูง และแท่งถัดมาปิด reclaim
เข้าหา regression trend พร้อม residual contraction ชัดเจน กลยุทธ์จึงต่างจาก raw-tail S179 และช่วยเพิ่ม exposure แบบ
trend-adjusted statistical reversal ทั้ง BUY/SELL โดยวาง limit กลางแท่ง reclaim และจำกัด risk ด้วย ATR

ผลเริ่มต้น RR7/BE1 ใน Backtest 2 เดือน (`2026-05-18`–`2026-07-18`, M5, spread 0.20, lot 0.01):

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 68 | 43 | 25 | 0 | 9.30% | +100.66 | +1.65 | +50.33 | 2.14 | 58.04 |

6-month survival RR7/BE1: 188 signals, 125 closed, WR8.00%, Net +172.84, PF1.50, DD82.74

Exact payoff/BE optimization พร้อม cross-window audit:

- RR16/BE1: 2 เดือน Net +213.74/PF3.74/DD51.03; 6 เดือน Net +421.37/PF2.28/DD108.94
- RR19/BE1: 6 เดือน Net +452.46 แต่ 2 เดือนลดเหลือ +158.58 และ RR20/BE1 พลิกเป็น -78.14 ใน 2 เดือน
  จึงไม่เลือก payoff spike บริเวณ RR19–20
- RR16/BE0.75 เป็นอันดับ 1 ทั้งสองหน้าต่าง: 2 เดือน Net +234.04/PF5.05/DD30.73 และ
  6 เดือน Net +482.46/PF3.17/DD93.31
- BE0.50 ให้ DD ต่ำกว่าแต่ Net ลดลงทั้ง 2 และ 6 เดือน; BE0.90–1.50 ไม่มีค่าที่ชนะ BE0.75 ข้ามทั้งสองหน้าต่าง

ล็อก cross-window optimized default ที่ `TP_RR=16.0`, `BE_RR=0.75`

ผล Backtest มาตรฐาน 2 เดือนของ optimized default:

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 62 | 40 | 22 | 0 | 7.50% | +234.04 | +3.84 | +117.02 | 5.05 | 30.73 |

ผลยืนยัน 6 เดือนของ optimized default:

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 180 | 121 | 59 | 0 | 4.96% | +482.46 | +2.67 | +80.41 | 3.17 | 93.31 |

6 เดือนมี BUY 74 ดีล (3 TP) และ SELL 47 ดีล (3 TP); schema invalid 0 แถว และ effective TP/Risk อยู่ที่ประมาณ 16R
ทั้งสองฝั่ง จึงยืนยันว่า detector สร้างคำสั่ง limit พร้อม entry/SL/TP ที่จำลองการเทรดได้จริงภายใต้ backtester มาตรฐาน

optimization สิ้นสุดที่ cross-window optimum RR16/BE0.75; กลับไปเริ่ม S181

## S181 — Range/Close-Variance Liquidity-Sweep Reclaim 7R

ไฟล์: `strategy181.py`

Edge: วัด dislocation ระหว่างช่วง High–Low กับการเปลี่ยนแปลงราคาปิด แล้วหาแท่ง wide-range ที่ราคาปิดส่งผ่านแรงเคลื่อนไหวน้อย
พร้อม volume, wick dominance และการกวาด swing ก่อนรอแท่งถัดไป reclaim เพื่อ fade liquidity sweep ทั้ง BUY/SELL

ผล Backtest 2 เดือน (`2026-05-18`–`2026-07-18`, M5, spread 0.20, lot 0.01):

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 26 | 21 | 5 | 0 | 9.52% | -10.53 | -0.17 | -5.27 | 0.87 | 63.50 |

baseline ไม่มี expectancy และ PF ต่ำกว่า 1 จึง fail survival gate และไม่ optimize; S182 จะเปลี่ยนเป็น volume-impact residual model

## S182 — Signed-Volume Impact-Residual Reclaim 7R

ไฟล์: `strategy182.py`

Edge: fit OLS ระหว่าง return กับ signed tick-volume pressure เพื่อประมาณ price impact แล้วหา exhaustion return ที่เบี่ยงจากโมเดล
อย่างมีนัยสำคัญ ก่อนเข้า mean reversion เมื่อแท่งถัดไปสร้าง opposite impact residual และปิด reclaim

ผล Backtest 2 เดือน (`2026-05-18`–`2026-07-18`, M5, spread 0.20, lot 0.01):

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 15 | 9 | 6 | 0 | 0.00% | -38.21 | -0.63 | -19.11 | 0.00 | 38.21 |

ไม่มี TP และ baseline ไม่มี expectancy จึง fail survival gate และไม่ optimize; S183 จะนำข้อมูล asymmetry ของ S181 มาแยกเฉพาะ bearish sweep

## S183 — Upper Range/Close-Variance Sweep SELL (Optimized 10.3R)

ไฟล์: `strategy183.py`

Edge: ผล S181 แสดง asymmetry ชัดเจน—BUY 13 ดีลไม่มี TP ขณะที่ SELL 6 ดีลมี 2 TP และ Net เป็นบวก—จึงแยกเฉพาะ
upper-wick structural sweep ที่ range กว้างแต่ราคาปิดส่งผ่านแรงเคลื่อนไหวน้อย พร้อม volume และ bearish reclaim เพื่อจับ
distribution/liquidity absorption ฝั่ง SELL โดยไม่รับ lower-sweep leg ที่ไม่มี expectancy

ผลเริ่มต้น RR7/BE1 ใน Backtest 2 เดือน (`2026-05-18`–`2026-07-18`, M5, spread 0.20, lot 0.01):

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 10 | 8 | 2 | 0 | 25.00% | +59.90 | +0.98 | +29.95 | 6.64 | 10.62 |

6-month survival RR7/BE1: 33 signals, 21 closed, 3 TP, WR14.29%, Net +39.57, PF1.86, DD38.39

Exact payoff/BE optimization พร้อม cross-window audit:

- RR10/BE1: 2 เดือน Net +90.29/PF9.50/DD10.62; 6 เดือน Net +76.56/PF2.66/DD38.39
- RR16/BE1 ให้ 6 เดือน +87.02 แต่เหลือ 2 TP และ 2 เดือนเหลือ 1 TP จึงไม่เลือก payoff spike ที่ sample บางกว่า
- RR10.0–10.3 รักษา winner ครบทั้งสองหน้าต่าง แต่ RR10.4 เสีย TP หนึ่งดีลทันที จึงพบ payoff cliff ระหว่าง 10.3–10.4
- BE0.85–0.92 ให้ผลเท่ากันทั้ง 2 และ 6 เดือน; BE0.95 เพิ่ม loss/DD จึงเลือก BE0.92 ซึ่งเป็นขอบบนสุดของ plateau

ล็อก cross-window optimized default ที่ `TP_RR=10.3`, `BE_RR=0.92`

ผล Backtest มาตรฐาน 2 เดือนของ optimized default:

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 10 | 8 | 2 | 0 | 25.00% | +97.40 | +1.60 | +48.70 | 15.87 | 6.55 |

ผลยืนยัน 6 เดือนของ optimized default:

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 33 | 21 | 12 | 0 | 14.29% | +84.33 | +0.47 | +14.06 | 3.00 | 34.32 |

optimization สิ้นสุดหลังยืนยัน BE plateau และ RR10.3–10.4 cliff; กลับไปเริ่ม S184

## S184 — Volume-Weighted CLV Pressure Divergence Reclaim (Optimized 8.5R)

ไฟล์: `strategy184.py`

Edge: คำนวณ Close Location Value (CLV) ของแต่ละแท่งแล้วถ่วงด้วย tick volume เพื่อประมาณ intrabar order-flow pressure;
เมื่อราคา displacement ไปทำ structural extreme แต่ cumulative CLV pressure ต้านทิศทางราคา แสดงถึง absorption/divergence
จากนั้นรอแท่งปิด reclaim ก่อนวาง limit ทั้ง BUY/SELL จึงต่างจาก body-signed flow ของ S177 และ single-bar variance ของ S181

ผลเริ่มต้น RR7/BE1 ใน Backtest 2 เดือน (`2026-05-18`–`2026-07-18`, M5, spread 0.20, lot 0.01):

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 14 | 11 | 3 | 0 | 9.09% | +11.38 | +0.19 | +5.69 | 1.24 | 47.10 |

6-month survival RR7/BE1: 29 signals, 24 closed, 4 TP, WR16.67%, Net +88.47, PF2.24, DD47.10

Exact payoff/BE optimization พร้อม cross-window audit:

- RR8/BE1: 2 เดือน Net +19.79; 6 เดือน Net +111.40 โดยรักษา 4 TP
- RR8.5/BE0.75–1: 6 เดือน Net สูงสุด +122.87 แต่ DD47.10 ยังเท่า baseline
- BE0.40–0.52 ลด DD เหลือ 15.80 และให้ผลเท่ากันบน plateau; BE0.54 เริ่มลด Net ใน 6 เดือน
- RR8.5/BE0.52: 2 เดือน Net +55.29/PF4.46/DD15.80 และ 6 เดือน Net +108.55/PF5.29/DD15.80
- RR8.6 ขึ้นไปเสีย historical TP หนึ่งดีลใน 6 เดือนทันที จึงพบ payoff cliff ระหว่าง RR8.5–8.6

ล็อก risk-adjusted cross-window default ที่ `TP_RR=8.5`, `BE_RR=0.52`

ผล Backtest มาตรฐาน 2 เดือนของ optimized default:

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 14 | 11 | 3 | 0 | 9.09% | +55.29 | +0.91 | +27.65 | 4.46 | 15.80 |

ผลยืนยัน 6 เดือนของ optimized default:

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 29 | 24 | 5 | 0 | 12.50% | +108.55 | +0.60 | +18.09 | 5.29 | 15.80 |

optimization สิ้นสุดหลัง risk-adjusted plateau และ RR8.5–8.6 cliff; กลับไปเริ่ม S185

## S185 — CLV-Pressure Confirmed Structural-Break Pullback 7R

ไฟล์: `strategy185.py`

Edge: ใช้ volume-weighted CLV pressure ที่ไปทิศเดียวกับ displacement ยืนยัน structural breakout แล้วรอ counter-pullback
volume ต่ำที่ยัง hold ครึ่งแท่ง breakout ก่อนเข้า continuation ทั้ง BUY/SELL เป็น regime ตรงข้ามกับ divergence reversal ของ S184

ผล Backtest 2 เดือน (`2026-05-18`–`2026-07-18`, M5, spread 0.20, lot 0.01):

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 7 | 7 | 0 | 0 | 14.29% | +22.18 | +0.36 | +11.09 | 2.34 | 10.69 |

6-month survival check: 14 signals/closed, 1 TP, WR7.14%, Net -16.37, PF0.70, DD49.24

ผล 2 เดือนเป็น recent-window effect และทั้ง BUY/SELL ไม่บวกใน full 6-month window จึง fail survival gate และไม่ optimize;
S186 จะเปลี่ยนเป็น variance-ratio gated statistical reversal

## S186 — Variance-Ratio Gated Return-Shock Reclaim 7R

ไฟล์: `strategy186.py`

Edge: ใช้ Lo–MacKinlay-style overlapping variance ratio ตรวจ anti-persistent regime ก่อน fade closed return shock ที่มี
volume/body alignment และแท่งถัดไปปิด reclaim เพื่อลดการสวน shock ใน trending regime

ผล Backtest 2 เดือน (`2026-05-18`–`2026-07-18`, M5, spread 0.20, lot 0.01):

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 34 | 25 | 9 | 0 | 4.00% | -12.07 | -0.20 | -6.04 | 0.77 | 35.16 |

BUY leg ไม่มี TP แต่ SELL leg มี TP และ Net บวก จึง fail baseline รวมและไม่ optimize; S187 จะแยกเฉพาะ bearish variance-ratio edge

## S187 — Bearish Variance-Ratio Return-Shock Reclaim (Optimized 8.1R)

ไฟล์: `strategy187.py`

Edge: แยกเฉพาะ return shock ฝั่งขึ้นที่เกิดใน anti-persistent variance-ratio regime แล้วปิด bearish reclaim;
ผล S186 แสดงว่า BUY leg ไม่มี TP ขณะที่ SELL leg เป็นบวก จึงตัด bullish asymmetry ที่ไม่มี expectancy ออก

ผลเริ่มต้น RR7/BE1 ใน Backtest 2 เดือน (`2026-05-18`–`2026-07-18`, M5, spread 0.20, lot 0.01):

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 21 | 12 | 9 | 0 | 8.33% | +16.29 | +0.27 | +8.15 | 1.68 | 17.87 |

6-month survival RR7/BE1: 41 signals, 21 closed, 2 TP, WR9.52%, Net +52.28, PF1.92, DD43.02

Exact payoff/BE optimization พร้อม cross-window audit:

- RR7/BE0.4–0.75: 6 เดือน Net +84.39/PF4.39/DD10.91 และ 2 เดือน +28.29/PF3.34/DD6.24
- RR8/BE0.5–0.75: 6 เดือน Net +100.06/PF5.02/DD10.91 และ 2 เดือน +34.09/PF3.82/DD6.24
- RR16/BE1 ดูดีที่สุดใน 2 เดือนจาก winner เดียว แต่ 6 เดือนเหลือ 1 TP/Net +35.38 จึงปฏิเสธ recent-window payoff spike
- RR8.1 ยังรักษา 2 TP ใน 6 เดือน/Net +101.62 แต่ RR8.2 เสีย TP หนึ่งดีลทันที จึงพบ cliff ระหว่าง RR8.1–8.2
- BE0.70–0.76 ให้ผลเท่ากันทั้งสองหน้าต่าง; BE0.78 เพิ่ม DD และลด Net จึงเลือกขอบบน plateau ที่ 0.76

ล็อก cross-window optimized default ที่ `TP_RR=8.1`, `BE_RR=0.76`

ผล Backtest มาตรฐาน 2 เดือนของ optimized default:

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 21 | 12 | 9 | 0 | 8.33% | +34.67 | +0.57 | +17.34 | 3.86 | 6.24 |

ผลยืนยัน 6 เดือนของ optimized default:

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 41 | 21 | 20 | 0 | 9.52% | +101.62 | +0.56 | +16.94 | 5.08 | 10.91 |

optimization สิ้นสุดหลัง BE plateau และ RR8.1–8.2 cliff; กลับไปเริ่ม S188

## S188 — Empirical Expected-Shortfall Return-Tail Reclaim 7R

ไฟล์: `strategy188.py`

Edge: คำนวณ empirical VaR และ Expected Shortfall ของ rolling close returns แยกสอง tail แล้ว fade เฉพาะแท่งปิดที่ทะลุ
ค่าเฉลี่ยของ tail พร้อม body/volume exhaustion และ opposite reclaim

ผล Backtest 2 เดือน (`2026-05-18`–`2026-07-18`, M5, spread 0.20, lot 0.01):

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 103 | 74 | 29 | 0 | 5.41% | -52.75 | -0.86 | -26.38 | 0.71 | 70.60 |

ทั้ง BUY และ SELL ติดลบและ trigger ถี่เกินไป จึง fail baseline และไม่ optimize; S189 จะเพิ่ม structural-sweep confluence
เพื่อแยก tail breach ที่เกิดจาก liquidity run จริง

## S189 — Expected-Shortfall Structural-Sweep Reclaim (Optimized 16.9R)

ไฟล์: `strategy189.py`

Edge: เพิ่ม structural liquidity sweep ให้ S188—return ต้องทะลุ empirical Expected Shortfall พร้อมกวาด rolling high/low
ก่อนแท่งถัดไป reclaim—จึงกรอง tail breach ทั่วไปออกและเหลือ tail-risk event ที่มีโครงสร้าง stop run รองรับทั้ง BUY/SELL

ผลเริ่มต้น RR7/BE1 ใน Backtest 2 เดือน (`2026-05-18`–`2026-07-18`, M5, spread 0.20, lot 0.01):

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 38 | 26 | 12 | 0 | 11.54% | +50.47 | +0.83 | +25.24 | 1.97 | 33.13 |

6-month survival RR7/BE1: 104 signals, 65 closed, 4 TP, WR6.15%, Net +38.76, PF1.26, DD54.55

Exact payoff/BE optimization พร้อม cross-window audit:

- RR16/BE1: 2 เดือน Net +130.93/PF3.52/DD33.53; 6 เดือน Net +229.47/PF2.54/DD77.23
- RR16/BE0.5: 2 เดือน Net +166.12/PF10.86/DD8.61; 6 เดือน Net +301.06/PF4.87/DD43.24
- BE0.45–0.52 เป็น plateau ที่ให้ผลเท่ากัน; BE0.54 เริ่มลด Net และเพิ่ม DD ใน 2 เดือน
- RR16.9/BE0.52 รักษา 2 TP ใน 2 เดือนและ 3 TP ใน 6 เดือน พร้อม Net +176.44/+322.41 ตามลำดับ
- RR17.0 เสีย winner หนึ่งดีลในทั้งสองหน้าต่างทันที จึงพบ payoff cliff ระหว่าง RR16.9–17.0

ล็อก cross-window optimized default ที่ `TP_RR=16.9`, `BE_RR=0.52`

ผล Backtest มาตรฐาน 2 เดือนของ optimized default:

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 39 | 27 | 12 | 0 | 7.41% | +176.44 | +2.89 | +88.22 | 11.48 | 8.61 |

ผลยืนยัน 6 เดือนของ optimized default:

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 105 | 66 | 39 | 0 | 4.55% | +322.41 | +1.78 | +53.74 | 5.15 | 43.24 |

optimization สิ้นสุดหลัง BE plateau และ RR16.9–17.0 cliff; กลับไปเริ่ม S190

## S190 — EVT Hill-Tail Structural-Sweep Reclaim 7R

ไฟล์: `strategy190.py`

Edge: ใช้ Hill estimator ประมาณ Pareto tail index จาก absolute returns และสร้าง dynamic EVT exceedance threshold ก่อนรับ
structural sweep + reclaim ทั้ง BUY/SELL เพื่อปรับ tail trigger ตาม fat-tail regime

ผล Backtest 2 เดือน (`2026-05-18`–`2026-07-18`, M5, spread 0.20, lot 0.01):

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 17 | 9 | 8 | 0 | 11.11% | +21.18 | +0.35 | +10.59 | 2.10 | 18.82 |

6-month survival check: 46 signals, 23 closed, 1 TP, WR4.35%, Net -10.30, PF0.80, DD50.30

BUY leg ไม่มี TP แต่ SELL leg ยังบวกทั้ง 2/6 เดือน จึง fail รวมและไม่ optimize; S191 จะแยกเฉพาะ upper-tail EVT edge

## S191 — Upper EVT Hill-Tail Structural-Sweep SELL (Optimized 16R)

ไฟล์: `strategy191.py`

Edge: แยกเฉพาะ upper-tail EVT exceedance ที่กวาด structural high แล้วปิด bearish reclaim; ตัด BUY leg ของ S190
ที่ไม่มี TP ในทั้ง 2/6 เดือนออก เพื่อเก็บ bearish fat-tail asymmetry เท่านั้น

ผลเริ่มต้น RR7/BE1 ใน Backtest 2 เดือน (`2026-05-18`–`2026-07-18`, M5, spread 0.20, lot 0.01):

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 8 | 3 | 5 | 0 | 33.33% | +40.00 | +0.66 | +20.00 | 101.00 | 0.20 |

6-month survival RR7/BE1: 18 signals, 7 closed, 1 TP, WR14.29%, Net +34.15, PF6.46, DD6.05

Exact payoff/BE optimization พร้อม sample-size audit:

- BE0.4–1.5 ให้ผลเหมือนกัน เนื่องจาก losing trades ที่เหลือเป็น BE/SL path เดิม จึงคง `BE_RR=1.0`
- RR7–16 รักษา winner เดียวกัน; RR16 ให้ 2 เดือน +92.20 และ 6 เดือน +86.35
- RR17 ขึ้นไปไม่มี TP และพลิก 6 เดือนเป็น -6.45 จึงพบ cliff ระหว่าง RR16–17
- ทั้ง 2/6 เดือนใช้ winner ล่าสุดดีลเดียวกัน ไม่ใช่ independent cross-window replication จึงไม่จูนทศนิยมชิด maximum excursion;
  เลือก coarse RR16 ซึ่งเว้น safety margin 1R ก่อน observed cliff

ล็อก sample-aware optimized default ที่ `TP_RR=16.0`, `BE_RR=1.0`

ผล Backtest มาตรฐาน 2 เดือนของ optimized default:

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 8 | 3 | 5 | 0 | 33.33% | +92.20 | +1.51 | +46.10 | 231.50 | 0.20 |

ผลยืนยัน 6 เดือนของ optimized default:

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 18 | 7 | 11 | 0 | 14.29% | +86.35 | +0.48 | +14.39 | 14.82 | 6.05 |

คำเตือน: sample บางมาก (7 closed/1 TP ใน 6 เดือน) จึงต้อง forward-test เพิ่มและไม่ควรตีความ PF สูงเป็นค่าคงที่

optimization สิ้นสุดหลัง sample-aware payoff cliff audit; กลับไปเริ่ม S192

## S192 — EWMA Volatility-of-Volatility Structural-Sweep Reclaim (Optimized 16.9R)

ไฟล์: `strategy192.py`

Edge: เปรียบเทียบ EWMA ของ True Range ระยะสั้น/ยาวเพื่อหา volatility shock ที่กำลังเร่งตัว แล้วรับเฉพาะแท่ง
directional exhaustion ที่กวาด rolling structure ก่อนแท่งถัดไป reclaim กลับเข้า range พร้อม volume confirmation ทั้ง BUY/SELL
จึงแยก liquidity sweep ใน regime ที่ความผันผวนกำลังเปลี่ยนระดับออกจาก sweep ทั่วไป และช่วยกระจาย trigger จากกลุ่ม
return-tail/EVT ของ S189–S191

ผลเริ่มต้น RR7/BE1 ใน Backtest 2 เดือน (`2026-05-18`–`2026-07-18`, M5, spread 0.20, lot 0.01):

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 13 | 8 | 5 | 0 | 12.50% | +15.41 | +0.25 | +7.71 | 1.62 | 15.10 |

6-month survival RR7/BE1: 34 signals, 18 closed, 2 TP, WR11.11%, Net +71.02, PF2.29, DD22.97

Exact payoff/BE optimization พร้อม cross-window cliff audit:

- RR16/BE1: 2 เดือน Net +67.61/PF3.71/DD15.10; 6 เดือน Net +233.47/PF5.25/DD22.97
- ลด BE จาก 1.0 เป็น 0.5 ทำให้ RR16 ดีขึ้นเป็น +83.00 ใน 2 เดือน และ +255.23 ใน 6 เดือน
- BE0.48–0.52 เป็น plateau ที่ให้ผลเท่ากัน; BE0.54 เริ่มลด Net และเพิ่ม DD ใน 2 เดือน
- RR16.9/BE0.52 รักษา 1 TP ใน 2 เดือนและ 2 TP ใน 6 เดือน พร้อม Net +88.22/+271.48 ตามลำดับ
- RR17.0 ทำให้ 2 เดือนเหลือ 0 TP/Net -9.80 และ 6 เดือนเสีย winner หนึ่งดีลทันที จึงพบ payoff cliff ระหว่าง RR16.9–17.0

ล็อก cross-window optimized default ที่ `TP_RR=16.9`, `BE_RR=0.52`

ผล Backtest มาตรฐาน 2 เดือนของ optimized default:

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 13 | 8 | 5 | 0 | 12.50% | +88.22 | +1.45 | +44.11 | 10.19 | 5.61 |

ผลยืนยัน 6 เดือนของ optimized default:

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 34 | 18 | 16 | 0 | 11.11% | +271.48 | +1.50 | +45.25 | 9.18 | 22.97 |

คำเตือน: sample ยังบาง (18 closed/2 TP ใน 6 เดือน) และกำไรพึ่งพา rare large-payoff winners จึงผ่าน historical simulation
แต่ต้อง forward-test เพื่อยืนยัน fill/slippage และห้ามตีความว่าเป็นการรับรองผล live

optimization สิ้นสุดหลัง BE plateau และ RR16.9–17.0 cliff; กลับไปเริ่ม S193

## S193 — Bipower Jump-Variation Structural-Sweep Reclaim (Optimized 16.9R)

ไฟล์: `strategy193.py`

Edge: ใช้ realized bipower variation เป็นตัวแทน continuous variance ที่ทนต่อ isolated jump แล้ววัด squared return
ของแท่ง exhaustion เทียบกับ variance ดังกล่าว เพื่อรับเฉพาะ discontinuous price jump ที่กวาด rolling structure ก่อนแท่งถัดไป
reclaim พร้อม volume confirmation ทั้ง BUY/SELL จึงกระจาย regime detector จาก EWMA volatility shock ของ S192 และ
return-tail/EVT ของ S189–S191

ผลเริ่มต้น RR7/BE1 ใน Backtest 2 เดือน (`2026-05-18`–`2026-07-18`, M5, spread 0.20, lot 0.01):

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 38 | 25 | 13 | 0 | 16.00% | +114.83 | +1.88 | +57.42 | 3.33 | 32.93 |

6-month survival RR7/BE1: 105 signals, 62 closed, 5 TP, WR8.06%, Net +105.49, PF1.73, DD50.31

Exact payoff/BE optimization พร้อม cross-window audit:

- RR10/BE0.5 ให้ 2 เดือนดีที่สุดใน broad grid ที่ +188.27 แต่ 6 เดือน +269.37
- RR16/BE0.5 ให้ 2 เดือน +168.52 และ 6 เดือน +323.12 พร้อม DD8.41/27.17 จึงเหนือกว่าเมื่อให้น้ำหนัก cross-window survival
- BE0.48–0.52 เป็น plateau ที่ให้ผลเท่ากัน; BE0.53 เริ่มลด Net และเพิ่ม DD ใน 2 เดือน
- RR16.9/BE0.52 รักษา 2 TP ใน 2 เดือนและ 3 TP ใน 6 เดือน พร้อม Net +178.84/+344.47 ตามลำดับ
- RR17.0 เสีย winner หนึ่งดีลในทั้งสองหน้าต่างทันที จึงพบ payoff cliff ระหว่าง RR16.9–17.0

ล็อก cross-window optimized default ที่ `TP_RR=16.9`, `BE_RR=0.52`

ผล Backtest มาตรฐาน 2 เดือนของ optimized default:

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 39 | 26 | 13 | 0 | 7.69% | +178.84 | +2.93 | +89.42 | 13.39 | 8.41 |

ผลยืนยัน 6 เดือนของ optimized default:

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 106 | 63 | 43 | 0 | 4.76% | +344.47 | +1.90 | +57.41 | 7.19 | 27.17 |

คำเตือน: กำไรยังพึ่ง rare large-payoff winners (3 TP จาก 63 closed ใน 6 เดือน) จึงต้อง forward-test เพิ่มและ
ไม่ควรตีความ PF สูงเป็นค่าคงที่ของผล live

optimization สิ้นสุดหลัง BE plateau และ RR16.9–17.0 cliff; กลับไปเริ่ม S194

## S194 — Amihud Liquidity-Dislocation Structural-Sweep Reclaim 7R

ไฟล์: `strategy194.py`

Edge hypothesis: ใช้ absolute log return ต่อ tick volume แบบ Amihud-style เพื่อหา price-impact shock ในสภาพคล่องบาง
แล้ว fade เฉพาะแท่งที่กวาด rolling structure ก่อนแท่งถัดไป reclaim ทั้ง BUY/SELL ซึ่งเป็น liquidity regime
คนละแกนกับ volatility/jump detector ของ S192–S193

ผล Backtest 2 เดือน (`2026-05-18`–`2026-07-18`, M5, spread 0.20, lot 0.01):

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 24 | 14 | 10 | 0 | 0.00% | -39.37 | -0.65 | -19.68 | 0.00 | 39.37 |

BUY 7 closed/Net -19.56 และ SELL 7 closed/Net -19.81 โดยไม่มี TP ทั้งสองฝั่ง จึง fail baseline และไม่ optimize;
S195 จะทดสอบสมมติฐานตรงข้าม คือใช้ liquidity impact เป็น breakout continuation แทนการ fade

## S195 — Amihud Liquidity-Impact Breakout Acceptance Continuation 7R

ไฟล์: `strategy195.py`

Edge hypothesis: กลับสมมติฐานของ S194 จาก fade เป็น continuation โดยรับเฉพาะ price-impact shock ที่ปิดนอก rolling
structure และแท่งถัดไปยัง hold/accept เหนือหรือใต้ breakout level ก่อนตั้ง limit ตามทิศทางเดิม

ผล Backtest 2 เดือน (`2026-05-18`–`2026-07-18`, M5, spread 0.20, lot 0.01):

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 8 | 8 | 0 | 0 | 0.00% | -13.84 | -0.23 | -6.92 | 0.00 | 13.84 |

BUY 3 closed และ SELL 5 closed ไม่มี TP ทั้งสองฝั่ง จึง fail baseline และไม่ optimize; ยุติสาย Amihud/tick-volume
liquidity proxy หลังทั้ง fade และ continuation ไม่ผ่าน แล้ว S196 จะเปลี่ยนไปวัด serial dependence ของ return

## S196 — Variance-Ratio Anti-Persistent Structural-Sweep Reclaim (Optimized 16.9R)

ไฟล์: `strategy196.py`

Edge: ใช้ Lo–MacKinlay-style multi-horizon variance ratio คัด regime ที่ return มี anti-persistence ก่อนรับเฉพาะ
locally extreme directional bar ที่กวาด rolling structure และมีแท่งถัดไป reclaim พร้อม volume confirmation
ทั้ง BUY/SELL จึงเพิ่ม serial-dependence regime ที่ไม่ซ้ำกับ tail, volatility, jump และ liquidity-impact detectors ก่อนหน้า

ผลเริ่มต้น RR7/BE1 ใน Backtest 2 เดือน (`2026-05-18`–`2026-07-18`, M5, spread 0.20, lot 0.01):

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 42 | 25 | 17 | 0 | 12.00% | +44.12 | +0.72 | +22.06 | 1.64 | 32.07 |

6-month survival RR7/BE1: 98 signals, 67 closed, 7 TP, WR10.45%, Net +52.12, PF1.28, DD88.69

Exact payoff/BE optimization พร้อม cross-window/DD audit:

- RR16/BE0.4–0.5 ให้ 2 เดือน +236.29/DD9.65 แต่ 6 เดือน +193.71/+185.80 และ DD75.80/83.71
- RR16/BE0.75 ให้ 2 เดือน +222.43/DD16.56 และ 6 เดือน +349.26/DD55.40 จึงเป็น cross-window compromise ที่ดีกว่า
- RR20/BE0.75 ให้ 6 เดือน +351.06 มากกว่า RR16 เพียง +1.80 แต่เหลือ 5 TP และ 2 เดือนลดเหลือ +171.59 จึงไม่เลือก
- BE0.70–0.78 เป็น plateau ของ candidate ใน 6 เดือน; เลือกค่า round `BE_RR=0.75` แทนการจูนชิดขอบ
- RR16.9 รักษา 3 TP ใน 2 เดือนและ 6 TP ใน 6 เดือน; RR17.0 เสีย winner หนึ่งดีลทันทีทั้งสองหน้าต่าง

ล็อก cross-window optimized default ที่ `TP_RR=16.9`, `BE_RR=0.75`

ผล Backtest มาตรฐาน 2 เดือนของ optimized default:

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 41 | 24 | 17 | 0 | 12.50% | +237.10 | +3.89 | +118.55 | 7.30 | 16.56 |

ผลยืนยัน 6 เดือนของ optimized default:

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 97 | 66 | 31 | 0 | 9.09% | +375.80 | +2.08 | +62.63 | 4.11 | 55.40 |

optimization สิ้นสุดหลัง cross-window/DD plateau และ RR16.9–17.0 cliff; กลับไปเริ่ม S197

## Campaign continuation — verified worktree through S226

สถานะ worktree ณ `2026-07-26` มี detector ต่อเนื่องถึง `strategy226.py`; เริ่มบันทึก continuation รอบนี้ที่ S227
โดยคงหน้าต่างมาตรฐานเดิม (`2026-05-18`–`2026-07-18`, M5, spread 0.20, lot 0.01)

## S227 — Rollover OR First-Break Failure Fade 10R

ไฟล์: `strategy227.py`

Edge hypothesis: fade breakout แรกของ anchored rollover opening range เมื่อแท่งถัดไปปิดกลับเข้ากรอบ โดย SL อยู่หลัง
wick ของ failed break เพื่อจับ trapped-breakout mean reversion

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 | 2 | 0 | 0 | 0.00% | -1.61 | -0.03 | -0.80 | 0.00 | 1.61 |

sample บางและไม่มี TP จึง fail baseline และไม่ optimize

## S228 — Rollover OR Immediate Retest Continuation 10R

ไฟล์: `strategy228.py`

Edge hypothesis: หลัง first opening-range breakout รอแท่งถัดไป retest ขอบที่แตกแล้วปิดยอมรับอยู่นอกกรอบ
ก่อนตาม continuation ด้วย structural stop หลัง retest wick

ผล Backtest 2 เดือน:

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 | 2 | 0 | 0 | 50.00% | +21.41 | +0.35 | +10.71 | 10.69 | 2.21 |

6-month check ยังเป็นสองดีลชุดเดียวกันทั้งหมด: WR50.00%, Net +21.41, +0.12/day, +3.57/month, PF10.69,
DD2.21 จึงไม่มี independent survival evidence และไม่ optimize จาก winner เดียว

## S229 — Rollover OR First Retest Within Three Bars 10R

ไฟล์: `strategy229.py`

Edge hypothesis: ขยาย S228 ให้ first retest มาถึงได้ภายในสามแท่ง โดยทุกแท่งคั่นกลางต้องปิดยอมรับนอกกรอบและ
ห้ามแตะ boundary ก่อน acting bar

ผล 2 เดือนและ 6 เดือนเหมือน S228 ทุกดีล: 2 signals/2 closed, WR50.00%, Net +21.41; การขยาย timing
ไม่เพิ่ม sample เลย จึงยุติสาย OR retest และไม่ optimize

## S230 — Opening-Auction Bias Micro-Range Break 10R

ไฟล์: `strategy230.py`

Edge hypothesis: หลัง opening range ครบหกแท่ง รับ S206-style rolling micro-range breakout เฉพาะเมื่อทิศทางตรงกับ
net opening-auction move และราคาอยู่ในครึ่งที่ถูกต้องของ opening range

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | 0 | 0 | 0 | — | 0.00 | 0.00 | 0.00 | — | 0.00 |

เงื่อนไข opening auction ครบแล้วกับ large-body 8-bar breakout ไม่ทับซ้อนกันในหน้าต่างทดสอบ จึง fail จาก no sample
และไม่ผ่อน parameter แบบไม่มีหลักฐาน

## S231 — First Asian Rejection of Each Rollover-Range Edge 10R

ไฟล์: `strategy231.py`

Edge hypothesis: แก้ overtrading ของ S216 โดยรับเพียง first touch/rejection ต่อขอบต่อวันในช่วง 07:00–11:00 BKK;
touch ก่อนหน้าถือว่าระดับถูก consume แล้วแม้ไม่เกิด rejection signal

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 10 | 10 | 0 | 0 | 0.00% | -28.85 | -0.47 | -14.42 | 0.00 | 28.85 |

การ deduplicate ลดจำนวนดีลได้แต่ยังไม่มี TP จึง fail baseline และไม่ optimize; S232 จะย้ายออกจาก OR retest/
range-edge fade เพื่อหา edge source ใหม่

## S232 — Rogers–Satchell Compression Efficiency Breakout 10R

ไฟล์: `strategy232.py`

Edge hypothesis: ใช้ Rogers–Satchell OHLC variance วัด intrabar diffusion โดยไม่ถูก directional drift bias แล้วรับ
body-efficient breakout เมื่อ short-window RS variance ยุบเทียบ long-window baseline กลไกต่างจาก high-low
range compression ของ S212 และทำงานตลอดวัน

ผล Backtest 2 เดือน (`2026-05-18`–`2026-07-18`, M5, spread 0.20, lot 0.01):

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 191 | 191 | 0 | 0 | 5.24% | -45.03 | -0.74 | -22.52 | 0.90 | 159.99 |

session-agnostic trigger overtrades และ fail baseline; hour audit พบ coherent scheduled-liquidity sub-regime เฉพาะ
17:00–19:00 BKK จึงให้ S233 ทดสอบกลไกนั้นแทนการเลือกชั่วโมงบวกกระจัดกระจาย

## S233 — US-Liquidity-Window RS Compression Breakout (Optimized 27.2R)

ไฟล์: `strategy233.py`

Edge: คง RS-compression/efficient-break detector และ risk model ของ S232 ทุกส่วน แต่เปิดเฉพาะ 17:00–19:00 BKK
ซึ่งเป็น scheduled US liquidity overlap เพื่อตัด quiet/mean-reverting sessions ที่ทำให้ S232 overtrade

ผลเริ่มต้น RR10/BE1 ใน Backtest 2 เดือน:

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 22 | 22 | 0 | 0 | 18.18% | +118.72 | +1.95 | +59.36 | 3.47 | 16.38 |

6-month survival RR10/BE1: 50 signals/50 closed, 5 TP, WR10.00%, Net +23.06, PF1.13, DD99.85

Exact market-order payoff/BE optimization:

- สร้าง market replay ที่ตรง generic backtester: fill ที่ next-bar open, TP อิง quoted signal price และ BE อิง actual-fill risk
- RR20/BE1 ให้ 2 เดือน +286.43 และ 6 เดือน +228.57 โดยยังรักษา TP 4/5
- RR26–27 เพิ่ม cross-window return; RR27/BE0.85 ให้ +297.63/+275.45 และลด 6m DD จาก 99.85 เหลือ 76.83
- fine grid พบ RR27.2/BE0.85 ให้ +300.15/+278.72; RR27.3 เสีย winner หนึ่งดีลทันทีทั้งสองหน้าต่าง
- BE0.85 เป็นจุดแรกที่รักษา trade sequencing/winner ครบ; BE0.84 เสีย winner และเพิ่มจำนวนดีล

ล็อก optimized default ที่ `TP_RR=27.2`, `BE_RR=0.85`

ผล Backtest มาตรฐาน 2 เดือนของ optimized default:

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 22 | 22 | 0 | 0 | 13.64% | +300.15 | +4.92 | +150.08 | 8.07 | 16.38 |

ผลยืนยัน 6 เดือน:

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 50 | 50 | 0 | 0 | 8.00% | +278.72 | +1.54 | +46.45 | 2.67 | 76.83 |

คำเตือน: ผล 6 เดือนยังเอียงมาช่วงล่าสุดและ 12-month stress check รันไม่ได้เพราะ MT5 retained M5 history ไม่พอ
จึงต้อง forward-test เพิ่ม แม้ optimized result ผ่าน 2/6-month historical survival แล้ว

optimization สิ้นสุดหลัง market-replay guard, BE sequencing boundary และ RR27.2–27.3 payoff cliff; กลับไปเริ่ม S234

## S234 — US-Window Parkinson Volatility-Compression Breakout 10R

ไฟล์: `strategy234.py`

Edge ablation: คง session 17:00–19:00 BKK, breakout geometry และ risk model ของ S233
แต่เปลี่ยนเฉพาะตัววัด compression จาก Rogers–Satchell เป็น Parkinson high-low variance
เพื่อทดสอบว่า edge เป็น generic volatility compression หรือขึ้นกับข้อมูล open/close path ของ RS

ผล Backtest 2 เดือน:

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 24 | 24 | 0 | 0 | 8.33% | +24.59 | +0.40 | +12.30 | 1.41 | 52.83 |

ผล survival 6 เดือน:

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 54 | 54 | 0 | 0 | 5.56% | -92.85 | -0.51 | -15.48 | 0.57 | 130.61 |

S234 fail 6-month survival และไม่ optimize; BUY ขาดทุนทั้ง 2/6 เดือน ส่วน SELL บวกเพียง
หน้าต่าง 2 เดือนและเกือบ flat ใน 6 เดือน หลักฐานจึงไม่รองรับ generic compression
และชี้ว่า OHLC path information ของ Rogers–Satchell อาจเป็นส่วนสำคัญของ S233

## S235 — US-Window RS/Parkinson Disagreement Breakout (Optimized 32.5R)

ไฟล์: `strategy235.py`

Edge: รับเฉพาะช่วง 17:00–19:00 BKK ที่ Rogers–Satchell short/long ratio ≤ 0.65
แต่ Parkinson ratio > 0.65 ก่อนเกิด body-efficient range breakout เงื่อนไข disagreement นี้
แยกภาวะที่ open-to-close diffusion สงบ แต่ intrabar high-low excursion ยังไม่ยุบ
ซึ่งเป็นกลไกที่ S233 มองเห็นและ Parkinson-only S234 มองไม่เห็น

ผลเริ่มต้น RR10/BE1 ใน Backtest 2 เดือน:

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 5 | 5 | 0 | 0 | 40.00% | +75.23 | +1.23 | +37.62 | 12.65 | 6.26 |

6-month survival RR10/BE1: 14 signals/14 closed, 2 TP, WR14.29%, Net +47.53,
+0.26/day, +7.92/month, PF2.39, DD27.90 จึงผ่านเกณฑ์หยุดสร้าง ID เพื่อ optimize payoff

Exact market-fill payoff/BE optimization:

- broad grid RR7–40 / BE0.25–2.00 ให้ RR30/BE1 บวก +239.43 ใน 2 เดือน
  และ +211.73 ใน 6 เดือน โดยรักษา TP สองดีลทั้งสองหน้าต่าง
- fine grid พบ BE0.85 เป็น sequencing boundary: BE0.84 เสีย winner หนึ่งดีลทันทีทั้ง 2/6 เดือน
- RR32.5 รักษา TP สองดีลครบ; RR32.6 เสีย winner หนึ่งดีลทันทีทั้งสองหน้าต่าง
- เลือกค่าติดขอบฝั่งที่ยังรักษา winner คือ `TP_RR=32.5`, `BE_RR=0.85`

ผล Backtest มาตรฐาน 2 เดือนของ optimized default:

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 5 | 5 | 0 | 0 | 40.00% | +265.82 | +4.36 | +132.91 | 444.03 | 0.40 |

ผลยืนยัน 6 เดือน:

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 14 | 14 | 0 | 0 | 14.29% | +244.20 | +1.35 | +40.70 | 11.99 | 21.82 |

ทั้ง BUY และ SELL เป็นบวกในสองหน้าต่าง แต่ sample รวมยังมีเพียง 14 ดีลและกำไรขึ้นกับ TP
สองดีล จึงจัดเป็น promising sparse candidate ที่ต้อง forward-test ไม่ใช่ production proof
optimization สิ้นสุดที่ BE0.84–0.85 และ RR32.5–32.6 cliff; กลับไปเริ่ม S236

## S236 — US-Window Dual-Estimator Compression Breakout 10R

ไฟล์: `strategy236.py`

Edge hypothesis: ทดสอบ complement ของ S235 โดยบังคับให้ทั้ง Rogers–Satchell และ
Parkinson short/long ratio ≤ 0.65 พร้อมกัน ก่อนรับ efficient range breakout ในช่วง
17:00–19:00 BKK หากผ่านจะหมายถึง estimator confluence ช่วยคัด quiet regime ที่แข็งแรงขึ้น

ผล Backtest 2 เดือน:

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 18 | 18 | 0 | 0 | 11.11% | +43.29 | +0.71 | +21.65 | 2.03 | 37.66 |

ผล survival 6 เดือน:

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 39 | 39 | 0 | 0 | 7.69% | -35.08 | -0.19 | -5.85 | 0.78 | 82.56 |

S236 fail 6-month survival และไม่ optimize; estimator agreement เพิ่ม sample แต่ลดคุณภาพ
จึงเสริมหลักฐานว่า edge ของ S235 อยู่ใน RS/Parkinson disagreement ไม่ใช่ generic
หรือ dual-confirmed compression

## S237 — US-Window Garman–Klass Compression Breakout 10R

ไฟล์: `strategy237.py`

Edge hypothesis: ใช้ Garman–Klass variance ซึ่งรวม high-low range และหัก open-close drift
โดยคง session, breakout geometry และ structural stop ของ S233 เพื่อทดสอบว่า edge ขยายไปยัง
OHLC estimator อื่นที่ใช้ path information ได้หรือไม่

ผล Backtest 2 เดือน:

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 25 | 25 | 0 | 0 | 12.00% | +81.58 | +1.34 | +40.79 | 2.57 | 29.81 |

ผล survival 6 เดือน:

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 53 | 53 | 0 | 0 | 7.55% | -21.57 | -0.12 | -3.60 | 0.89 | 107.34 |

S237 fail 6-month survival และไม่ optimize; Garman–Klass เพิ่ม sample แต่กำไรไม่คงทน
จึงยุติสาย estimator ablation และให้ S238 เปลี่ยนไปหา edge source ใหม่

## S238 — Signed-Effort Absorption Release Breakout 10R

ไฟล์: `strategy238.py`

Edge hypothesis: ถ่วง tick volume ด้วย signed body/range efficiency ตลอด 24 แท่ง
เพื่อหาแรงซื้อหรือขายสะสมสูง ขณะที่ net displacement ยังไม่เกิน 0.60 ATR แล้วรอ
efficient 8-bar range release ในทิศเดียวกับแรงสะสม

ผล Backtest 2 เดือน:

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | 0 | 0 | 0 | — | 0.00 | 0.00 | 0.00 | — | 0.00 |

เงื่อนไข absorption และ breakout ไม่ทับกันในหน้าต่างทดสอบ จึง fail จาก no sample
และไม่ผ่อน threshold ย้อนหลัง; S239 จะ ablate เฉพาะ displacement cap เพื่อทดสอบ
signed-effort continuation โดยตรง

## S239 — Signed-Effort Aligned Range Breakout (Optimized 46.9R)

ไฟล์: `strategy239.py`

Edge: ตัดเฉพาะ low-displacement absorption gate ของ S238 ออก แต่ยังต้องมี signed
tick-volume effort ratio ≥ 0.18 และ efficient 8-bar range break ไปในทิศเดียวกับ effort
ช่วง 17:00–21:00 BKK จึงเป็น order-flow continuation มากกว่า volatility compression

ผลเริ่มต้น RR10/BE1 ใน Backtest 2 เดือน:

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 7 | 7 | 0 | 0 | 14.29% | +6.48 | +0.11 | +3.24 | 1.19 | 29.18 |

6-month survival RR10/BE1: 18 signals/18 closed, 2 TP, WR11.11%, Net +11.10,
+0.06/day, +1.85/month, PF1.15, DD64.59 จึงผ่านแบบบางและเข้าสู่ payoff optimization

Exact market-fill payoff/BE optimization:

- broad grid RR7–80 / BE0.25–3.00 พบว่าผลทั้งสองหน้าต่างดีขึ้นเมื่อขยาย payoff
  และ 6 เดือนเกิด sequencing plateau ที่ BE ประมาณ 1.01 ขึ้นไป
- fine grid ให้ RR46.9/BE1.01–1.15 รักษา 1 TP ใน 2 เดือนและ 3 TP ใน 6 เดือน
- เลือกค่า round ภายใน BE plateau ที่ `BE_RR=1.05`
- RR47.0 เป็น payoff cliff: 2 เดือนเสีย TP เดียวทั้งหมดและ Net กลายเป็น -29.38;
  6 เดือนลดจาก 3 TP เหลือ 2 TP จึงล็อก `TP_RR=46.9`

ผล Backtest มาตรฐาน 2 เดือนของ optimized default:

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 7 | 7 | 0 | 0 | 14.29% | +157.77 | +2.59 | +78.89 | 5.59 | 29.18 |

ผลยืนยัน 6 เดือน:

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 17 | 17 | 0 | 0 | 17.65% | +753.08 | +4.16 | +125.51 | 11.36 | 50.39 |

6 เดือน BUY +349.08 และ SELL +404.00 แต่ 2 เดือน SELL ยัง -21.04; sample รวมเพียง
17 ดีลและผลขึ้นกับ 3 TP จึงเป็น sparse candidate ที่ต้อง forward-test เพิ่ม
optimization สิ้นสุดที่ BE plateau และ RR46.9–47.0 cliff; กลับไปเริ่ม S240

## S240 — Long-Only CLV-Volume Pressure Breakout (Optimized 42R)

ไฟล์: `strategy240.py`

Edge: ใช้ Close Location Value ของแต่ละแท่ง
`CLV=((close-low)-(high-close))/(high-low)` ถ่วงด้วย tick volume ตลอด 24 แท่ง
เพื่อวัด auction pressure ที่ไม่ขึ้นกับสีแท่ง แล้วรับ efficient 8-bar range break
ช่วง 17:00–21:00 BKK ในทิศเดียวกับ pressure

ผลเริ่มต้นทั้งสองฝั่ง RR10/BE1 ใน Backtest 2 เดือน:

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 13 | 13 | 0 | 0 | 15.38% | +14.87 | +0.24 | +7.44 | 1.21 | 69.86 |

6-month survival RR10/BE1: 38 signals/38 closed, 4 TP, WR10.53%, Net +26.65,
+0.15/day, +4.44/month, PF1.15, DD96.89 จึงผ่านแบบบางและเข้าสู่ optimization

Exact market-fill payoff/BE optimization:

- broad grid RR7–50 / BE0.25–2.00 และ fine grid พบ RR42.0 เป็นขอบสุดท้ายที่รักษา
  winner ครบทั้ง 2/6 เดือน; RR42.1 ทำให้ 2 เดือนเสีย TP ทั้งหมดและ 6 เดือนเหลือ TP เดียว
- ค่าดิบ BE0.01–0.03 ให้ Net สูงสุด แต่ trigger distance ของบางดีลต่ำ/ใกล้ spread 0.20
  จึงปฏิเสธเป็น microstructure artifact ไม่ใช้เป็น default
- risk ต่ำสุดของ sample คือ 3.29; เลือก `BE_RR=0.08` กลาง plateau 0.06–0.09
  ทำให้ BE trigger ต่ำสุดประมาณ 0.26 ซึ่งมากกว่า spread
- direction audit หลัง payoff optimization พบ BUY บวก +178.05/+328.56 ใน 2/6 เดือน
  ขณะที่ SELL -23.86/-31.63 และไม่มี TP จึงตั้ง `ALLOW_SELL=False`

ผล Backtest มาตรฐานของ optimized long-only default:

| Window | Signals | Closed | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน | 6 | 6 | 16.67% | +178.05 | +2.92 | +89.03 | 7.89 | 25.64 |
| 6 เดือน | 26 | 26 | 7.69% | +328.56 | +1.82 | +54.76 | 6.64 | 54.11 |

sample ยังบางและกำไรขึ้นกับ 1/2 TP ใน 2/6 เดือน จึงต้อง forward-test เพิ่ม
optimization สิ้นสุดที่ realistic BE plateau, RR42.0–42.1 cliff และ direction survival;
กลับไปเริ่ม S241

## S241 — Negative CLV-Pressure Downside Sweep Reclaim 10R

ไฟล์: `strategy241.py`

Edge hypothesis: หลัง volume-weighted CLV pressure ติดลบ ≤ -0.18 ให้ BUY เมื่อแท่ง
กวาด 8-bar low แล้วปิด reclaim พร้อม bullish body และ lower rejection wick โดยวาง SL
ใต้ sweep wick เพื่อทดสอบ failed downside auction หลังแรงขายถูกดูดซับ

ผล Backtest 2 เดือน:

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 5 | 5 | 0 | 0 | 0.00% | -14.55 | -0.24 | -7.27 | 0.00 | 14.55 |

ไม่มี TP จึง fail baseline และไม่ optimize; negative-pressure reversal ไม่ได้รับการสนับสนุน

## S242 — Positive CLV-Pressure Downside Sweep Reclaim 10R

ไฟล์: `strategy242.py`

Edge hypothesis: เปลี่ยน S241 เป็น continuation-pullback โดยต้องมี positive CLV pressure
≥ 0.18 ก่อน downside sweep-reclaim เพื่อให้ long direction ตรงกับแขนงที่รอดของ S240

ผล Backtest 2 เดือน:

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | 0 | 0 | 0 | — | 0.00 | 0.00 | 0.00 | — | 0.00 |

positive pressure และ downside sweep-reclaim ไม่ทับกันในหน้าต่างทดสอบ จึง fail จาก
no sample และไม่ผ่อน threshold; ยุติสาย sweep-reclaim แล้วให้ S243 เปลี่ยน entry geometry

## S243 — Positive CLV-Pressure Pullback Engulf Continuation 10R

ไฟล์: `strategy243.py`

Edge hypothesis: ใน positive volume-weighted CLV regime รับ bearish pullback หนึ่งแท่ง
แล้ว BUY เมื่อแท่ง bullish ถัดไปปิดเหนือ pullback high ด้วย efficient body โดยใช้ low ของ
โครงสร้างสองแท่งเป็น short structural stop

ผล Backtest 2 เดือน:

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 | 2 | 0 | 0 | 50.00% | +41.01 | +0.67 | +20.51 | 6.15 | 7.97 |

ผลตรวจ 6 เดือน: 5 signals/5 closed, WR20.00%, Net +28.76, +0.16/day,
+4.79/month, PF2.42, DD20.22 แต่ TP เดียวใน 6 เดือนคือดีล `2026-07-01 18:45`
ซึ่งเป็น winner เดียวกับหน้าต่าง 2 เดือน ไม่มี independent older winner
จึงถือว่า survival evidence ไม่พอและไม่ optimize จาก winner เดียว; เดินหน้า S244

## S244 — CLV-Pressure Acceleration Breakout 10R

ไฟล์: `strategy244.py`

Edge hypothesis: ให้ volume-weighted CLV 6 แท่ง ≥ 0.25 เร่งขึ้นจาก baseline 24 แท่ง
อย่างน้อย 0.20 ขณะที่ baseline ยัง ≤ 0.12 แล้วรับ long-only upside range breakout
เพื่อแยก fresh pressure transition ออกจาก persistent pressure ของ S240

ผล Backtest 2 เดือน:

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 3 | 3 | 0 | 0 | 0.00% | -13.25 | -0.22 | -6.63 | 0.00 | 13.25 |

ไม่มี TP จึง fail baseline และไม่ optimize; fresh CLV acceleration ไม่ได้เพิ่มคุณภาพ

## S245 — CLV-Pressure Breakout with Tick-Volume Surprise 10R

ไฟล์: `strategy245.py`

Edge hypothesis: คง positive CLV pressure breakout ของ S240 แต่กำหนดให้ volume ของ
breakout bar ≥ 1.50 เท่าของ median 24 แท่ง เพื่อยืนยัน fresh participation

ผล Backtest 2 เดือน:

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 3 | 3 | 0 | 0 | 0.00% | -18.80 | -0.31 | -9.40 | 0.00 | 18.80 |

ไม่มี TP จึง fail baseline และไม่ optimize; high participation ไม่ได้ยืนยัน S240 edge

## S246 — CLV-Pressure Liquidity-Vacuum Breakout 10R

ไฟล์: `strategy246.py`

Edge hypothesis: complement ของ S245 โดยรับ positive CLV breakout เฉพาะเมื่อ breakout
volume ≤ 0.85 เท่าของ median 24 แท่ง เพื่อทดสอบการวิ่งผ่าน low opposing liquidity

ผล Backtest 2 เดือน:

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | 0 | 0 | 0 | — | 0.00 | 0.00 | 0.00 | — | 0.00 |

ไม่มี S240 breakout อยู่ใน volume-vacuum regime นี้ จึง fail จาก no sample

## S247 — CLV-Pressure Normal-Participation Breakout (Optimized 42R)

ไฟล์: `strategy247.py`

Edge: หลัง S245 high-volume chase ล้มเหลวและ S246 volume vacuum ไม่มี sample
รับ partition ที่เหลือแบบกำหนดล่วงหน้า คือ long-only positive CLV breakout ที่ breakout
volume อยู่ระหว่าง 0.85–1.50 เท่าของ median 24 แท่ง เป็น normal participation regime

ผลเริ่มต้น RR10/BE1 ใน Backtest 2 เดือน:

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 4 | 4 | 0 | 0 | 50.00% | +77.89 | +1.28 | +38.95 | 12.06 | 7.04 |

6-month survival RR10/BE1: 18 signals/18 closed, 4 TP, WR22.22%, Net +119.34,
+0.66/day, +19.89/month, PF2.39, DD66.86 และมี older independent winners
จึงผ่าน survival และเข้าสู่ optimization

Exact market-fill payoff/BE optimization:

- broad grid RR7–50 / BE0.25–2.00 ให้ผล cross-window สูงสุดใกล้ RR40
- fine grid ยืนยัน RR42.0 เป็นขอบสุดท้ายที่รักษา winner ชุดสำคัญ ก่อน payoff cliff
- BE0.05 ให้ค่าดิบ +200.00/+351.51 แต่ risk ต่ำสุด 3.29 ทำให้ trigger ต่ำสุดประมาณ
  0.16 ซึ่งต่ำกว่า spread 0.20 จึงปฏิเสธเป็น microstructure artifact
- BE0.06–0.15 เป็น plateau เดียวกัน; เลือกค่า round กลาง plateau ที่ `BE_RR=0.10`
  ซึ่ง trigger ต่ำสุดประมาณ 0.33 มากกว่า spread และล็อก `TP_RR=42.0`

ผล Backtest มาตรฐานของ optimized default:

| Window | Signals | Closed | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน | 4 | 4 | 25.00% | +196.65 | +3.22 | +98.33 | 28.16 | 7.04 |
| 6 เดือน | 19 | 19 | 10.53% | +348.16 | +1.92 | +58.03 | 10.02 | 34.91 |

6 เดือนยังมีเพียง 2 TP และ 2 เดือน 1 TP จึงเป็น sparse candidate ที่ต้อง forward-test
optimization สิ้นสุดหลัง realistic BE plateau และ payoff cliff; กลับไปเริ่ม S248

## S248 — Multi-Scale Hurst-Persistence Range Breakout 10R

ไฟล์: `strategy248.py`

Edge hypothesis: ประเมิน Hurst exponent ด้วย rescaled-range slope บน return 64 แท่ง
ที่ scale 8/16/32 และรับ efficient US-window range breakout เมื่อ H ≥ 0.62
เพื่อจับ cross-scale return persistence ที่ต่างจาก variance ratio และ entropy

ผล Backtest 2 เดือน:

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 46 | 46 | 0 | 0 | 6.52% | +16.94 | +0.28 | +8.47 | 1.11 | 121.68 |

ผล survival 6 เดือน:

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 123 | 123 | 0 | 0 | 4.88% | -171.01 | -0.94 | -28.50 | 0.66 | 299.51 |

S248 overtrade และ fail 6-month survival จึงไม่ optimize; S249 ทดสอบ
anti-persistent complement ด้วย failed-sweep fade

## S249 — Hurst Anti-Persistent Failed-Sweep Fade 10R

ไฟล์: `strategy249.py`

Edge hypothesis: เมื่อ multi-scale Hurst ≤ 0.40 ให้ fade fresh 12-bar range sweep
ที่ปิด reclaim กลับเข้ากรอบพร้อม rejection wick โดยใช้ sweep extreme เป็น short stop

ผล Backtest 2 เดือน:

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 5 | 5 | 0 | 0 | 20.00% | +49.07 | +0.80 | +24.53 | 62.34 | 0.80 |

ผลตรวจ 6 เดือน: 9 signals/9 closed, WR11.11%, Net +39.74, +0.22/day,
+6.62/month, PF4.92, DD9.33 แต่ TP เดียวคือดีล `2026-05-19 20:35`
ซึ่งเป็น winner เดียวกับหน้าต่าง 2 เดือน ไม่มี independent older winner
จึงไม่ optimize จาก sample เดียวและเดินหน้า S250

## S250 — CUSUM Return Change-Point Structural Breakout 10R

ไฟล์: `strategy250.py`

Edge hypothesis: ใช้ return baseline 64 แท่ง standardize monitoring window 16 แท่ง
และรับเฉพาะ one-sided CUSUM ที่ข้าม control threshold 3.0 บนแท่งปัจจุบัน พร้อม
efficient structural range break ในทิศเดียวกัน เพื่อจับ fresh process shift

ผล Backtest 2 เดือน:

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 36 | 36 | 0 | 0 | 5.56% | -3.69 | -0.06 | -1.85 | 0.97 | 75.59 |

ทั้งพอร์ต fail baseline; direction audit พบ BUY 17 ดีล +2.27 และ SELL 19 ดีล -5.96
จึงให้ S251 ทำ BUY-only survival ablation เพียงครั้งเดียว

## S251 — BUY-Only CUSUM Return Change-Point Breakout 10R

ไฟล์: `strategy251.py`

Edge hypothesis: แยกเฉพาะ upside CUSUM branch ที่บวกเล็กน้อยใน S250 เพื่อทดสอบ
direction survival โดยไม่เปลี่ยน threshold, breakout geometry หรือ risk model

ผล Backtest 2 เดือน:

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 17 | 17 | 0 | 0 | 5.88% | +2.27 | +0.04 | +1.13 | 1.05 | 27.31 |

ผล survival 6 เดือน:

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 46 | 46 | 0 | 0 | 4.35% | -112.65 | -0.62 | -18.78 | 0.43 | 142.23 |

S251 fail 6-month survival และไม่ optimize; ยุติสาย CUSUM และเดินหน้า S252

## S252 — ATR Directional-Change Regime Reversal 10R

ไฟล์: `strategy252.py`

Edge hypothesis: reconstruct up/down directional-change regime จาก close 96 แท่ง
ด้วย threshold 0.75 ATR แล้วรับเฉพาะ fresh reversal event บนแท่งปัจจุบัน พร้อม
event-extreme stop เป็น event-time sampling ที่ต่างจาก fixed-bar indicators

ผล Backtest 2 เดือน:

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 128 | 128 | 0 | 0 | 3.91% | -124.87 | -2.05 | -62.44 | 0.70 | 197.19 |

ทั้งพอร์ต fail และ overtrade; BUY 52 ดีล +10.61 แต่ SELL 76 ดีล -135.48
จึงให้ S253 ทำ BUY-only survival ablation โดยไม่เปลี่ยน threshold

## S253 — BUY-Only ATR Directional-Change Reversal 10R

ไฟล์: `strategy253.py`

Edge hypothesis: direction-survival ablation ของ S252 โดยปิด SELL และคง event threshold,
geometry และ payoff เดิม

ผล Backtest 2 เดือน:

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 92 | 92 | 0 | 0 | 5.43% | -37.02 | -0.61 | -18.51 | 0.87 | 195.43 |

เมื่อปิด SELL, one-position sequencing เปิดทางให้ BUY เพิ่มจาก 52 เป็น 92 ดีลและผลติดลบ
จึง fail baseline, ไม่ optimize และยุติสาย Directional Change; เดินหน้า S254

## S254 — VPIN-Style Informed-Flow Toxicity Breakout 10R

ไฟล์: `strategy254.py`

Edge hypothesis: จัดสรร tick volume เป็น buy/sell flow ด้วย normal-CDF proxy จาก
standardized open-close move แล้วกำหนด VPIN proxy ≥ 0.35, signed flow ≥ 0.12
ก่อนรับ efficient 8-bar range break ในทิศเดียวกับ informed flow

ผล Backtest 2 เดือน:

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 13 | 13 | 0 | 0 | 0.00% | -61.44 | -1.01 | -30.72 | 0.00 | 61.44 |

ไม่มี TP จึง fail baseline และไม่ optimize; S255 ทดสอบ toxic-flow climax fade

## S255 — VPIN Toxic-Flow Breakout Climax Fade 10R

ไฟล์: `strategy255.py`

Edge hypothesis: fade trigger ชุดเดียวกับ S254 ในฐานะ trapped toxic-flow climax
และใช้ breakout wick ฝั่งตรงข้ามเป็น structural stop

ผล Backtest 2 เดือน:

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 12 | 12 | 0 | 0 | 8.33% | +2.48 | +0.04 | +1.24 | 1.17 | 14.82 |

ผล survival 6 เดือน:

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 26 | 26 | 0 | 0 | 3.85% | -31.59 | -0.17 | -5.27 | 0.36 | 34.27 |

S255 fail 6-month survival และไม่ optimize; ยุติสาย VPIN และเดินหน้า S256

## S256 — Adaptive Kalman-Innovation Structural Breakout 10R

ไฟล์: `strategy256.py`

Edge hypothesis: ใช้ local-level Kalman filter บน close 96 แท่งด้วย process noise
0.10 ATR และ measurement noise 0.50 ATR แล้วรับ fresh innovation crossing |z| ≥ 2.50
ที่ตรงกับ efficient structural breakout

ผล Backtest 2 เดือน:

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 68 | 68 | 0 | 0 | 4.41% | -77.78 | -1.28 | -38.89 | 0.68 | 118.28 |

BUY -10.49 และ SELL -67.29 ต่าง fail จึงไม่ทำ direction split; S257 ทดสอบ
adaptive fair-value overshoot fade เป็น complement เพียงครั้งเดียว

## S257 — Adaptive Kalman-Innovation Overshoot Fade (Optimized 30.1R)

ไฟล์: `strategy257.py`

Edge: fade fresh |z| ≥ 2.50 Kalman fair-value innovation ที่ S256 continuation
ตามแล้วล้มเหลว โดยใช้ breakout wick ฝั่งตรงข้ามเป็น short structural stop

ผลเริ่มต้น RR10/BE1 ใน Backtest 2 เดือน:

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 65 | 65 | 0 | 0 | 9.23% | +25.71 | +0.42 | +12.86 | 1.43 | 27.89 |

6-month survival RR10/BE1: 177 signals/177 closed, 21 TP, WR11.86%,
Net +169.25, +0.94/day, +28.21/month, PF1.87, DD35.46
จึงผ่านด้วย sample และ independent winners เพียงพอ

Exact market-fill payoff/BE optimization:

- broad grid ให้ 2 เดือนชอบ RR8 แต่ 6 เดือนชอบ RR40; RR30 ยังบวกทั้งสองหน้าต่าง
  จึงใช้ cross-window compromise แทนเลือก optimum ของหน้าต่างเดียว
- actual-fill risk ต่ำสุด 0.46 ทำให้ BE0.25 trigger ต่ำกว่า spread 0.20 จึงตัดทิ้ง
- BE0.44–0.49 เป็น plateau ที่ trigger ครอบ spread; เลือกค่ากลาง `BE_RR=0.46`
- RR30.1/BE0.46 ให้ +28.87/+318.29 ใน 2/6 เดือน
- RR30.2 เสีย winner หนึ่งดีลทั้งสองหน้าต่าง; 2 เดือนกลับเป็น -14.64 และ 6 เดือน
  ลดเหลือ +276.16 จึงล็อก `TP_RR=30.1`

ผล Backtest มาตรฐานของ optimized default:

| Window | Signals | Closed | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน | 60 | 60 | 3.33% | +28.87 | +0.47 | +14.43 | 1.53 | 50.75 |
| 6 เดือน | 169 | 169 | 5.33% | +318.29 | +1.76 | +53.05 | 2.80 | 77.76 |

ทั้ง BUY และ SELL เป็นบวกใน 2/6 เดือน (6m BUY +100.93, SELL +217.36)
จึงไม่ split direction; optimization สิ้นสุดที่ realistic BE plateau และ RR30.1–30.2 cliff
แล้วกลับไปเริ่ม S258

## S258 — Local-Linear-Trend Kalman Innovation Fade (Optimized 28.1R)

ไฟล์: `strategy258.py`

Edge: แยก fair value เป็น level และ slope ด้วย two-state Kalman model ก่อน fade
เฉพาะ fresh standardized innovation ที่ยัง extreme หลังหัก adaptive trend แล้ว
เพื่อลดการตีความแนวโน้มปกติเป็น overshoot แบบ local-level model ของ S257

ผลเริ่มต้น RR10/BE1:

| Window | Signals | Closed | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน | 44 | 44 | 18.18% | +87.43 | +1.43 | +43.72 | 3.29 | 12.32 |
| 6 เดือน | 140 | 140 | 15.71% | +240.86 | +1.33 | +40.14 | 2.49 | 34.76 |

ผ่าน survival ด้วย sample 140 ดีลและ 22 TP ใน 6 เดือน จึงเข้าสู่ exact
market-fill payoff/BE optimization

- broad sweep พบ time-regime tradeoff: 2 เดือนชอบ RR25 แต่ 6 เดือนชอบ RR40
- fine cross-window sweep ให้ RR28.1 สูงสุดร่วมกัน; RR28.2 เสีย winner หนึ่งดีล
  ทั้งสองหน้าต่าง จึงเป็น payoff cliff ที่ต้องระวัง
- actual-fill risk ต่ำสุด 0.47 และ spread 0.20; เลือก `BE_RR=0.50`
  ซึ่งมี minimum trigger ประมาณ 0.235 มากกว่า spread และอยู่ใน plateau กว้าง
- ล็อก optimized default ที่ `TP_RR=28.10`, `BE_RR=0.50`

ผล Backtest มาตรฐานของ optimized default:

| Window | Signals | Closed | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน | 43 | 43 | 9.30% | +146.13 | +2.40 | +73.07 | 4.77 | 14.92 |
| 6 เดือน | 139 | 139 | 7.91% | +417.92 | +2.31 | +69.65 | 3.76 | 63.22 |

Direction audit: 2 เดือน BUY 23 ดีล/4 TP/+166.94 แต่ SELL 20 ดีล/0 TP/-20.81;
6 เดือน BUY 68 ดีล/6 TP/+244.62 และ SELL 71 ดีล/5 TP/+173.30
จึงไม่ตัด SELL จาก recent window เพราะมี independent older winners และกำไรรวมแข็งแรง
ใน survival window การ optimize สิ้นสุดที่ realistic BE plateau และ RR28.1–28.2 cliff

## S259 — Bipower-Variation Jump-Exhaustion Fade 10R

ไฟล์: `strategy259.py`

Edge hypothesis: ใช้ realized bipower variation ประเมิน continuous variance แล้วหา
fresh return jump ที่ผิดจาก diffusion ปกติ ก่อน fade เฉพาะ event ที่ sweep โครงสร้าง
แต่ปิดออกจาก extreme พร้อม rejection wick และ volume participation

ผล Backtest 2 เดือน:

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 8 | 8 | 0 | 0 | 0.00% | -30.29 | -0.50 | -15.15 | 0.00 | 30.29 |

ไม่มี TP จึง fail baseline และไม่ optimize; S260 ทดสอบ continuation complement
บน jump event เดิมเพียงครั้งเดียว

## S260 — Bipower Jump-Rejection Continuation 10R

ไฟล์: `strategy260.py`

Edge hypothesis: กลับทิศ S259 เพื่อตาม non-continuous jump หลัง rejection pause โดยคง
jump threshold, structure และ volume regime เดิม แต่ย้าย SL ไปหลัง event wick ฝั่งต้นทาง

ผล Backtest 2 เดือน:

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 | 2 | 0 | 0 | 0.00% | -13.33 | -0.22 | -6.67 | 0.00 | 13.33 |

ไม่มี TP และ sample ลดจาก risk geometry จึง fail baseline; ยุติสาย bipower jump
โดยไม่ผ่อน threshold และให้ S261 เปลี่ยนเป็น Bayesian sign-transition persistence

## S261 — Bayesian Return-Sign Persistence Breakout 10R

ไฟล์: `strategy261.py`

Edge hypothesis: ประมาณ first-order Markov transition matrix ของเครื่องหมาย return
ด้วย symmetric beta prior แล้วรับ efficient structural breakout เฉพาะเมื่อ posterior
probability ของการคงทิศ ≥ 0.62 และมี transition sample ของ state นั้นเพียงพอ

ผล Backtest 2 เดือน:

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 4 | 4 | 0 | 0 | 25.00% | +30.67 | +0.50 | +15.34 | 6.21 | 5.89 |

ผล survival 6 เดือน:

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 11 | 11 | 0 | 0 | 9.09% | -0.57 | -0.00 | -0.09 | 0.98 | 37.13 |

TP เดียวใน 6 เดือนคือ BUY วันที่ 2026-07-15 ซึ่งเป็น winner เดิมในหน้าต่าง 2 เดือน
จึงไม่มี independent older winner และ fail survival; ไม่ optimize หรือทำ direction split
จากหลักฐานหนึ่งดีล ให้ S262 ทดสอบ anti-persistent failed-sweep complement

## S262 — Bayesian Sign-Switch Failed-Sweep Reclaim (Optimized SELL-Only 27R)

ไฟล์: `strategy262.py`

Edge: ประมาณ posterior probability ของการสลับเครื่องหมาย return ด้วย beta prior
และรับ failed local high/low sweep ที่ปิด reclaim กลับเข้ากรอบ เฉพาะ regime ที่
sign-switch probability ≥ 0.58 เพื่อใช้ anti-persistence เป็น statistical confluence
ให้ structural reversal พร้อม event-extreme short stop

ผลเริ่มต้น RR10/BE1 ทั้งสองทิศ:

| Window | Signals | Closed | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน | 13 | 13 | 15.38% | +67.01 | +1.10 | +33.51 | 2.92 | 22.70 |
| 6 เดือน | 28 | 28 | 10.71% | +186.61 | +1.03 | +31.10 | 3.26 | 56.38 |

6 เดือนมี 3 independent TP วันที่ 2026-03-02, 2026-05-26 และ 2026-06-01
จึงผ่าน survival แต่ direction audit พบ SELL 10 ดีล/3 TP/+242.51 ขณะที่ BUY
18 ดีล/0 TP/-55.90 จึงปิด BUY

SELL-only RR10/BE1:

| Window | Signals | Closed | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน | 6 | 6 | 33.33% | +86.13 | +1.41 | +43.07 | 6.45 | 12.22 |
| 6 เดือน | 11 | 11 | 27.27% | +242.31 | +1.34 | +40.39 | 10.03 | 23.05 |

Exact market-fill payoff/BE optimization:

- broad sweep พบ 2 เดือนชอบประมาณ RR25 ส่วน 6 เดือนยังเพิ่มถึง RR50 เพราะ winner
  เดือนมีนาคม จึงไม่เลือก optimum จาก long-window ดีลเดียว
- fine cross-window sweep ให้ RR27.0 สูงสุดร่วมกันและยังรักษา 2 TP ใน 6 เดือน
- RR27.1 เสีย recent winner: 2 เดือนจาก +154.98 เหลือ -13.02 และ 6 เดือน
  จาก +599.25 เหลือ +432.92 จึงเป็น payoff cliff
- actual-fill risk ต่ำสุด 3.18; BE0.30–0.56 เป็น plateau เดียวกันทั้ง 2/6 เดือน
  และ trigger ต่ำสุดที่ BE0.43 ≈ 1.37 สูงกว่า spread 0.20 มาก จึงเลือกค่ากลาง
- ล็อก `ALLOW_BUY=False`, `ALLOW_SELL=True`, `TP_RR=27.0`, `BE_RR=0.43`

ผล Backtest มาตรฐานของ optimized default:

| Window | Signals | Closed | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน | 6 | 6 | 16.67% | +154.98 | +2.54 | +77.49 | 13.09 | 12.22 |
| 6 เดือน | 10 | 10 | 20.00% | +599.25 | +3.31 | +99.88 | 31.48 | 18.86 |

S262 เป็น candidate ที่กำไรสูงแต่ sample บางและ payoff ไวต่อ 27.0–27.1R cliff
จึงต้อง forward-test ก่อนเงินจริง การ optimize สิ้นสุดที่ direction survival,
realistic BE plateau และ payoff cliff; รอบถัดไปกลับไปเริ่ม S263

## S263 — Bayesian Ordinal-Pattern Structural Breakout 10R

ไฟล์: `strategy263.py`

Edge hypothesis: แปลง close 3 แท่งเป็น permutation rank state ที่ไม่ขึ้นกับระดับราคา
แล้วประมาณ posterior ของทิศแท่งถัดไปจาก occurrences ก่อนหน้า รับเฉพาะ efficient
structural breakout ที่ตรงกับ posterior ≥ 0.65 และมี pattern sample ≥ 5

ผล Backtest 2 เดือน:

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 6 | 6 | 0 | 0 | 0.00% | -21.06 | -0.35 | -10.53 | 0.00 | 21.06 |

BUY 4 ดีล -14.11 และ SELL 2 ดีล -6.95 ไม่มี TP ทั้งสองฝั่ง จึง fail baseline
และไม่ทำ direction split; S264 ทดสอบ ordinal-breakout fade complement เพียงครั้งเดียว

## S264 — Bayesian Ordinal-Breakout Failure Fade 10R

ไฟล์: `strategy264.py`

Edge hypothesis: fade trigger ชุดเดียวกับ S263 เพื่อทดสอบว่า ordinal-predicted
structural break เป็น false-break state โดยใช้ event wick ฝั่งตรงข้ามเป็น short stop

ผล Backtest 2 เดือน:

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 | 2 | 0 | 0 | 0.00% | -4.71 | -0.08 | -2.35 | 0.00 | 4.71 |

ไม่มี TP จึง fail baseline และไม่ optimize; ยุติสาย ordinal pattern แล้วให้ S265
เปลี่ยนเป็น lagged volume-return mutual information

## S265 — Lagged Volume-Return Mutual-Information Breakout 10R

ไฟล์: `strategy265.py`

Edge hypothesis: แบ่ง tick volume เป็น high/low participation เทียบ rolling median
แล้ววัด mutual information ระหว่าง volume state กับเครื่องหมาย return แท่งถัดไป
ใช้ beta posterior เลือกทิศและรับเฉพาะ efficient structural breakout ที่ตรงกัน

ผล Backtest 2 เดือน:

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 4 | 4 | 0 | 0 | 0.00% | -7.31 | -0.12 | -3.65 | 0.00 | 7.31 |

ไม่มี TP จึง fail baseline และไม่ optimize; S266 ทดสอบ volume-information
breakout fade complement เพียงครั้งเดียว

## S266 — Volume-Information Breakout Failure Fade 10R

ไฟล์: `strategy266.py`

Edge hypothesis: fade MI-conditioned breakout ชุดเดียวกับ S265 โดยวาง short stop
หลัง event wick เพื่อทดสอบ false information-driven break

ผล Backtest 2 เดือน:

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 3 | 3 | 0 | 0 | 0.00% | -6.30 | -0.10 | -3.15 | 0.00 | 6.30 |

ไม่มี TP จึง fail baseline และไม่ optimize; ยุติสาย mutual information แล้วให้ S267
ใช้ Wald-Wolfowitz runs test เป็น regime estimator คนละแกน

## S267 — Wald-Wolfowitz Persistent-Runs Structural Breakout 10R

ไฟล์: `strategy267.py`

Edge hypothesis: ใช้ distribution-free runs test เปรียบเทียบจำนวน positive/negative
return runs ที่สังเกตกับค่าภายใต้ independent signs แล้วตาม efficient structural
breakout เฉพาะเมื่อ z ≤ -1.20 ซึ่งหมายถึง directional runs ยาวผิดปกติ

ผล Backtest 2 เดือน:

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 4 | 4 | 0 | 0 | 25.00% | +30.67 | +0.50 | +15.34 | 6.21 | 5.89 |

ผล survival 6 เดือน:

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 15 | 15 | 0 | 0 | 6.67% | -12.99 | -0.07 | -2.17 | 0.74 | 49.55 |

TP เดียวคือ BUY วันที่ 2026-07-15 ซึ่งซ้ำกับ S261; trade set 6 เดือน overlap
S261 จำนวน 7 ดีลและอีก 8 ดีลใหม่ไม่สร้าง winner จึง fail survival และไม่ optimize
รอบถัดไปเริ่ม S268

## S268 — Wald-Wolfowitz Anti-Runs Failed-Sweep Reclaim (Optimized SELL-Only 27R)

ไฟล์: `strategy268.py`

Edge: ใช้ runs-test z ≥ 1.20 ระบุ regime ที่ return signs สลับทิศมากกว่าสุ่ม
แล้ว fade local high/low sweep เฉพาะเมื่อ event candle ปิด reclaim กลับเข้ากรอบ
พร้อม rejection wick และ event-extreme structural stop

ผลเริ่มต้น RR10/BE1 ทั้งสองทิศ:

| Window | Signals | Closed | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน | 16 | 16 | 12.50% | +62.97 | +1.03 | +31.49 | 2.62 | 26.74 |
| 6 เดือน | 30 | 30 | 13.33% | +230.00 | +1.27 | +38.33 | 3.89 | 43.00 |

6 เดือนมี 4 independent SELL TP วันที่ 2026-03-02, 2026-03-12,
2026-05-26 และ 2026-06-01 Direction audit พบ SELL 13 ดีล/4 TP/+279.22
แต่ BUY 17 ดีล/0 TP/-49.22 จึงปิด BUY

SELL-only RR10/BE1:

| Window | Signals | Closed | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน | 8 | 8 | 25.00% | +82.29 | +1.35 | +41.15 | 5.19 | 12.22 |
| 6 เดือน | 14 | 14 | 28.57% | +279.02 | +1.54 | +46.50 | 10.10 | 23.05 |

Exact market-fill payoff/BE optimization:

- broad sweep พบ 2 เดือนชอบ RR25 ส่วน 6 เดือนยังเพิ่มถึง RR50 จาก large March winner
- fine sweep พบ 6 เดือนสูงสุดในช่วงร่วมที่ RR24.2/3 TP แต่ cross-window minimum
  สูงสุดที่ RR27.0 ซึ่งยังรักษา 1 recent TP และ 2 long-window TP
- RR27.1 เสีย recent winner: 2 เดือนจาก +154.58 เหลือ -13.42 และ 6 เดือน
  ลดจาก +598.85 เหลือ +432.52 จึงเป็น payoff cliff
- actual-fill risk ต่ำสุด 3.18; BE0.30–0.56 เป็น plateau เดียวกันทั้ง 2/6 เดือน
  จึงเลือกค่ากลาง `BE_RR=0.43`
- ล็อก `ALLOW_BUY=False`, `ALLOW_SELL=True`, `TP_RR=27.0`, `BE_RR=0.43`

ผล Backtest มาตรฐานของ optimized default:

| Window | Signals | Closed | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน | 8 | 8 | 12.50% | +154.58 | +2.53 | +77.29 | 12.69 | 12.22 |
| 6 เดือน | 12 | 12 | 16.67% | +598.85 | +3.31 | +99.81 | 30.85 | 18.86 |

Portfolio overlap audit: S268 optimized overlap S262 optimized ทั้ง 10 timestamps
และเพิ่มเพียง 2 SELL ที่จบ BE -0.20 ทั้งคู่ จึงเป็น robustness confirmation ของ
SELL failed-sweep edge มากกว่า diversification ใหม่ การ optimize สิ้นสุดที่
direction survival, BE plateau และ RR cliff; รอบถัดไปเริ่ม S269

## S269 — Ornstein-Uhlenbeck Residual Snapback 10R

ไฟล์: `strategy269.py`

Edge hypothesis: detrend close ด้วย rolling OLS แล้ว fit residual เป็น AR(1)
ซึ่งเป็น discrete OU process รับเฉพาะ stationary residual ที่ half-life 2–20 แท่ง,
เกิด fresh |z| ≥ 2.25 และแท่ง event reject กลับหา equilibrium

ผล Backtest 2 เดือน:

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | 0 | 0 | 0 | — | 0.00 | 0.00 | 0.00 | — | 0.00 |

fresh stationary excursion และ rejection ไม่ทับกันในหน้าต่างทดสอบ จึง fail จาก
no sample โดยไม่ผ่อน threshold; S270 ทดสอบ OU continuation complement

## S270 — Stationary OU Residual Structural Continuation 10R

ไฟล์: `strategy270.py`

Edge hypothesis: ใช้ stationary OU residual excursion และ half-life regime เดียวกับ
S269 แต่ตามทิศ excursion เฉพาะเมื่อเกิด efficient structural breakout

ผล Backtest 2 เดือน:

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 26 | 26 | 0 | 0 | 7.69% | +60.18 | +0.99 | +30.09 | 1.80 | 31.29 |

ผล survival 6 เดือน:

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 68 | 68 | 0 | 0 | 4.41% | -87.96 | -0.49 | -14.66 | 0.71 | 187.70 |

ทั้งพอร์ต fail survival แต่ BUY บวกใน 2/6 เดือน (17 ดีล/2 TP/+90.64 และ
42 ดีล/3 TP/+33.88) ขณะที่ SELL ไม่มี TP (-30.46/-121.84)
จึงให้ S271 ทำ BUY-only survival ablation โดยไม่เปลี่ยน OU parameters

## S271 — BUY-Only Stationary OU Residual Continuation (Optimized 21.3R)

ไฟล์: `strategy271.py`

Edge: direction-survival branch ของ S270 รับเฉพาะ BUY เมื่อ detrended residual
เป็น stationary OU process, half-life 2–20 แท่ง, เกิด fresh positive |z| ≥ 2.25
และมี efficient upside structural breakout

ผลเริ่มต้น RR10/BE1:

| Window | Signals | Closed | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน | 17 | 17 | 11.76% | +90.64 | +1.49 | +45.32 | 3.04 | 23.86 |
| 6 เดือน | 42 | 42 | 7.14% | +33.88 | +0.19 | +5.65 | 1.19 | 108.76 |

6 เดือนมี 3 independent TP วันที่ 2026-04-17, 2026-05-28 และ 2026-07-01
จึงผ่าน survival และเข้าสู่ exact market-fill payoff/BE optimization

- broad sweep ให้ cross-window candidate ที่ RR20/BE0.25: +255.32/+187.10
  ใน 2/6 เดือน และลด DD จาก baseline อย่างชัดเจน
- actual-fill risk ต่ำสุด 2.51; BE0.08–0.11 เป็น long-window plateau และ
  `BE_RR=0.10` ให้ minimum trigger ≈0.251 ซึ่งมากกว่า spread 0.20
- fine RR sweep เพิ่มผลต่อเนื่องถึง RR21.3 โดยยังรักษา 2 TP ทั้งสองหน้าต่าง
- RR21.4 เสีย winner หนึ่งดีล: 2 เดือนลดจาก +272.71 เป็น +88.48 และ
  6 เดือนลดจาก +236.91 เป็น +52.68 จึงเป็น payoff cliff
- ล็อก `ALLOW_BUY=True`, `ALLOW_SELL=False`, `TP_RR=21.3`, `BE_RR=0.10`

ผล Backtest มาตรฐานของ optimized default:

| Window | Signals | Closed | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน | 17 | 17 | 11.76% | +272.71 | +4.47 | +136.36 | 18.84 | 10.78 |
| 6 เดือน | 42 | 42 | 4.76% | +236.91 | +1.31 | +39.49 | 5.64 | 36.20 |

Portfolio overlap audit: optimized S271 overlap S262/S268 เป็น 0 timestamps
จึงช่วยกระจายจาก SELL failed-sweep cluster ได้จริง; overlap S258 จำนวน 10 จาก
42 timestamps ยังไม่ใช่ clone ทั้งชุด อย่างไรก็ดี optimized result เหลือเพียง 2 TP
ใน 6 เดือนและอ่อนไหวต่อ RR21.3–21.4 cliff จึงต้อง forward-test ก่อนเงินจริง
การ optimize สิ้นสุดที่ realistic BE plateau และ payoff cliff; รอบถัดไปเริ่ม S272

## S272 — ARCH-LM Volatility-Cluster Structural Breakout 10R

ไฟล์: `strategy272.py`

Edge hypothesis: ใช้ Engle ARCH-LM lag-1 (`n × rho²`) บน squared demeaned returns
ตรวจ conditional-variance clustering และรับ fresh variance impulse ≥ 2.5 เท่า
เฉพาะเมื่อเกิด efficient structural breakout ในทิศเดียวกัน

ผล Backtest 2 เดือน:

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 1 | 0 | 0 | 0.00% | -5.17 | -0.08 | -2.58 | 0.00 | 5.17 |

ไม่มี TP และ sample บาง จึง fail baseline โดยไม่ผ่อน ARCH significance;
S273 ทดสอบ volatility-cluster exhaustion fade complement เพียงครั้งเดียว

## S273 — ARCH-Cluster Breakout Exhaustion Fade 10R

ไฟล์: `strategy273.py`

Edge hypothesis: fade significant ARCH variance-impulse breakout ชุดเดียวกับ S272
เพื่อทดสอบ volatility exhaustion โดยใช้ event wick เป็น short stop

ผล Backtest 2 เดือน:

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 1 | 0 | 0 | 0.00% | -1.64 | -0.03 | -0.82 | 0.00 | 1.64 |

ไม่มี TP และ sample บาง จึง fail baseline; ยุติสาย ARCH และให้ S274
เปลี่ยนเป็น multi-scale detrended fluctuation analysis

## S274 — Multi-Scale DFA-Persistence Structural Breakout 10R

ไฟล์: `strategy274.py`

Edge hypothesis: ใช้ detrended fluctuation analysis บน scales 8/16/32/64
ประมาณ scaling exponent หลังลบ local linear trends แล้วตาม efficient structural
breakout เฉพาะ persistent regime ที่ alpha ≥ 0.62

ผล Backtest 2 เดือน:

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 19 | 19 | 0 | 0 | 0.00% | -83.95 | -1.38 | -41.98 | 0.00 | 83.95 |

ไม่มี TP และ overtrade จึง fail baseline; S275 ทดสอบ DFA anti-persistent
failed-sweep reclaim complement

## S275 — DFA Anti-Persistent Failed-Sweep Reclaim (Optimized SELL-Only 20.8R)

ไฟล์: `strategy275.py`

Edge: ใช้ multi-scale DFA exponent ≤ 0.45 ระบุ anti-persistent regime แล้ว fade
local high/low sweep เฉพาะเมื่อ event candle ปิด reclaim กลับเข้ากรอบ พร้อม
rejection wick และ event-extreme structural stop

ผลเริ่มต้น RR10/BE1 ทั้งสองทิศ:

| Window | Signals | Closed | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน | 31 | 31 | 16.13% | +195.96 | +3.21 | +97.98 | 5.21 | 19.79 |
| 6 เดือน | 84 | 84 | 9.52% | +251.51 | +1.39 | +41.92 | 1.97 | 101.79 |

6 เดือนมี 8 TP หลายเดือน Direction audit พบ SELL 47 ดีล/7 TP/+344.67
แต่ BUY 37 ดีล/1 TP/-93.16 จึงปิด BUY; sequencing หลังปิด BUY เพิ่ม SELL
winner อีกหนึ่งดีล

SELL-only RR10/BE1:

| Window | Signals | Closed | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน | 20 | 20 | 25.00% | +226.08 | +3.71 | +113.04 | 9.69 | 12.04 |
| 6 เดือน | 49 | 49 | 16.33% | +394.34 | +2.18 | +65.72 | 4.10 | 50.37 |

Exact market-fill payoff/BE optimization:

- broad sweep มี high-R results สูงมากแต่พึ่ง winner น้อย จึงใช้ breadth-preserving
  selection แทนเลือก raw maximum
- RR20.8/BE1.5 ยังรักษา 3 TP ใน 2 เดือนและ 7 TP ใน 6 เดือน
  ให้ +357.92/+1168.31 ขณะที่ RR20.9 ลดเหลือ 2/6 TP ทันที
- fine BE sweep ยืนยัน BE1.50–1.56 เป็น plateau สูงสุดร่วมกันทั้งสองหน้าต่าง
  จึงเลือกค่ากลาง `BE_RR=1.53`
- ล็อก `ALLOW_BUY=False`, `ALLOW_SELL=True`, `TP_RR=20.8`, `BE_RR=1.53`

ผล Backtest มาตรฐานของ optimized default:

| Window | Signals | Closed | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน | 18 | 18 | 16.67% | +357.92 | +5.87 | +178.96 | 10.81 | 18.79 |
| 6 เดือน | 45 | 45 | 15.56% | +1168.31 | +6.45 | +194.72 | 9.34 | 52.98 |

Portfolio overlap audit: S275 overlap S262/S268 เพียง 4 จาก 45 timestamps
และ overlap S271 เป็นศูนย์ จึงเพิ่ม diversification จากทั้ง SELL failed-sweep cluster
เดิมและ BUY OU branch ได้ดีกว่า S268 มี sample 45 ดีล/7 TP แต่ยังต้อง forward-test
เพราะ RR20.8–20.9 เป็น payoff cliff การ optimize สิ้นสุดที่ direction survival,
breadth-preserving TP cliff และ BE plateau; รอบถัดไปเริ่ม S276

## S276 — Robust Tick-Volume Lead/Lag Structural Breakout 10R

ไฟล์: `strategy276.py`

Edge hypothesis: standardize tick-volume surprise ด้วย median/MAD แล้วประมาณ
continuous correlation ระหว่าง volume surprise กับ return แท่งถัดไป ต้องมี
|rho| ≥ 0.20, |t| ≥ 2 และ current surprise ≥ 1 ก่อนรับ aligned structural breakout

ผล Backtest 2 เดือน:

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 3 | 3 | 0 | 0 | 0.00% | -15.13 | -0.25 | -7.56 | 0.00 | 15.13 |

ไม่มี TP จึง fail baseline และไม่ optimize; S277 ทดสอบ volume-led breakout
failure fade complement เพียงครั้งเดียว

## S277 — Significant Volume-Led Breakout Failure Fade 10R

ไฟล์: `strategy277.py`

Edge hypothesis: fade significant volume-led structural breakout ชุดเดียวกับ S276
โดยใช้ event wick เป็น short structural stop

ผล Backtest 2 เดือน:

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 | 2 | 0 | 0 | 0.00% | -5.28 | -0.09 | -2.64 | 0.00 | 5.28 |

ไม่มี TP จึง fail baseline และไม่ optimize; ยุติสาย volume lead/lag แล้วให้ S278
เปลี่ยนเป็น path-dependent directional Ulcer asymmetry

## S278 — Directional Ulcer-Asymmetry Structural Breakout 10R

ไฟล์: `strategy278.py`

Edge hypothesis: เปรียบเทียบ RMS drawdown จาก running peak กับ RMS drawup จาก
running trough บน close 64 แท่ง แล้วรับ efficient structural breakout เฉพาะทิศ
ที่ path-dependent inventory stress ratio ≥ 1.50

ผล Backtest 2 เดือน:

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 38 | 38 | 0 | 0 | 7.89% | -4.50 | -0.07 | -2.25 | 0.97 | 73.51 |

ทั้งพอร์ต fail เล็กน้อย แต่ BUY 21 ดีล/2 TP/+21.61/PF1.34 ขณะที่ SELL
17 ดีล/-26.11/PF0.63 จึงให้ S279 ทำ BUY-only survival ablation

## S279 — BUY-Only Directional Ulcer-Asymmetry Breakout 10R

ไฟล์: `strategy279.py`

Edge hypothesis: direction-survival ablation ของ S278 โดยคง Ulcer ratio,
breakout geometry และ payoff เดิม แต่ปิด SELL

ผล Backtest 2 เดือน:

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 21 | 21 | 0 | 0 | 9.52% | +21.61 | +0.35 | +10.80 | 1.34 | 45.10 |

ผล survival 6 เดือน:

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 55 | 55 | 0 | 0 | 5.45% | -74.17 | -0.41 | -12.36 | 0.69 | 146.69 |

S279 fail 6-month survival และไม่ optimize; ยุติสาย Directional Ulcer
แล้วรอบถัดไปเริ่ม S280

## S280 — Lempel-Ziv Low-Complexity Structural Breakout 10R

ไฟล์: `strategy280.py`

Edge hypothesis: วัด LZ76 phrase-count complexity ของ return-sign sequence 96 แท่ง
และรับ efficient structural breakout เฉพาะ normalized complexity ≤ 0.78

ผล Backtest 2 เดือน:

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | 0 | 0 | 0 | — | 0.00 | 0.00 | 0.00 | — | 0.00 |

finite-sample diagnostic ใน US window พบ normalized LZ ช่วง 0.98–1.46,
median 1.24 ทำให้ pre-set low-complexity gate ไม่มี sample จึงไม่ผ่อน threshold;
S281 ทดสอบ high-complexity failed-sweep reclaim complement

## S281 — Lempel-Ziv High-Complexity Reclaim (Optimized SELL-Only 27R)

ไฟล์: `strategy281.py`

Edge: ใช้ normalized LZ sign complexity ≥ 1.25 ระบุ path ที่มี algorithmic novelty
สูง แล้ว fade local range sweep เฉพาะเมื่อ event candle ปิด reclaim พร้อม rejection
wick และ event-extreme short stop

ผลเริ่มต้น RR10/BE1 ทั้งสองทิศ:

| Window | Signals | Closed | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน | 38 | 38 | 10.53% | +165.50 | +2.71 | +82.75 | 3.18 | 46.32 |
| 6 เดือน | 106 | 106 | 7.55% | +59.78 | +0.33 | +9.96 | 1.17 | 192.31 |

6 เดือนมี 8 independent TP แต่ direction audit พบ SELL 51 ดีล/5 TP/+92.29
ขณะที่ BUY 55 ดีล/3 TP/-32.51 จึงปิด BUY

SELL-only RR10/BE1:

| Window | Signals | Closed | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน | 21 | 21 | 19.05% | +194.12 | +3.18 | +97.06 | 6.60 | 17.70 |
| 6 เดือน | 60 | 60 | 10.00% | +132.90 | +0.73 | +22.15 | 1.77 | 75.87 |

Exact market-fill payoff/BE optimization:

- broad sweep มี raw maximum ที่ RR50 แต่ recent window เหลือ winner เดียว
  จึงใช้ breadth-preserving selection
- RR27.0/BE1.5 ยังรักษา 2 TP ใน 2 เดือนและ 5 TP ใน 6 เดือน
  แต่ RR27.1 ลดเหลือ 1/4 TP จึงเป็น payoff cliff
- BE sweep พบ 0.30–0.33 เป็น plateau สูงสุดร่วมกันทั้งสองหน้าต่างที่ RR27
  และลด DD อย่างมาก จึงเลือกค่ากลาง `BE_RR=0.32`
- actual-fill risk ต่ำสุด 2.39 ทำให้ minimum BE trigger ที่ 0.32R ≈0.76
  มากกว่า spread 0.20
- ล็อก `ALLOW_BUY=False`, `ALLOW_SELL=True`, `TP_RR=27.0`, `BE_RR=0.32`

ผล Backtest มาตรฐานของ optimized default:

| Window | Signals | Closed | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน | 19 | 19 | 10.53% | +359.45 | +5.89 | +179.73 | 22.72 | 5.98 |
| 6 เดือน | 59 | 59 | 6.78% | +504.45 | +2.79 | +84.08 | 7.38 | 31.95 |

Portfolio overlap audit: S281 overlap S262/S268 จำนวน 6 timestamps, S271 เป็น 0,
และ S275 จำนวน 21 จาก 59 จึงยังมี 38 timestamps ต่างจาก S275 แต่เป็น SELL reclaim
family บางส่วนเหมือนกัน Optimized 6 เดือนมี 4 TP จึงต้อง forward-test โดยเฉพาะ
RR27.0–27.1 cliff การ optimize สิ้นสุดที่ direction survival, BE plateau และ
breadth-preserving payoff cliff; รอบถัดไปเริ่ม S282

## S282 — Distribution-Free Low-Turning Structural Breakout 10R

ไฟล์: `strategy282.py`

Edge hypothesis: ใช้ turning-point count ของลำดับราคาปิด 64 แท่งเทียบกับค่าคาดหมาย
ภายใต้ลำดับสุ่มแบบ distribution-free หากค่า z-score ≤ -1.50 แสดงว่าเส้นทางราคามี
จุดกลับตัวน้อยผิดปกติและมี persistence สูง จากนั้นรับ structural breakout ตามทิศทาง
โดยใช้ event-extreme เป็น short stop, TP 10R และ BE 1R

ผล Backtest มาตรฐาน:

| Window | Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน | 83 | 83 | 0 | 0 | 7.23% | +30.67 | +0.50 | +15.33 | 1.11 | 135.21 |
| 6 เดือน | 250 | 250 | 0 | 0 | 4.40% | -389.25 | -2.15 | -64.87 | 0.62 | 476.51 |

ตัว detector และ execution path ทำงานจริง: ทุกสัญญาณถูกเปิดและปิดครบ ไม่มี invalid
หรือ expired แต่ผลบวก 2 เดือนไม่รอด out-of-window 6 เดือน จึงสรุปว่า low-turning
breakout ไม่มี Edge ที่เสถียรและไม่ควร optimize ต่อ รอบถัดไปทดสอบ high-turning
anti-persistent complement ใน S283

## S283 — Distribution-Free High-Turning Failed-Sweep Reclaim 10R

ไฟล์: `strategy283.py`

Edge hypothesis: ใช้ turning-point count ของราคาปิด 64 แท่งเพื่อหาเส้นทางที่มี
จุดกลับตัวมากกว่าลำดับสุ่มอย่างมีนัยสำคัญ (`z >= 1.50`) แล้ว fade failed structural
sweep ที่ปิด reclaim กลับเข้ากรอบ พร้อม event-extreme short stop, TP 10R และ BE 1R

ผล Backtest 2 เดือน:

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | 0 | 0 | 0 | — | 0.00 | 0.00 | 0.00 | — | 0.00 |

Diagnostic ใน US window จำนวน 2,160 ช่วงพบ turning z: min -6.72, median -2.51,
p90 -0.70, p95 -0.40 และ max +0.20 จึงไม่มีช่วงใดผ่าน `z >= 1.50`
แม้ failed-sweep reclaim เกิด 102 ครั้ง สรุปว่า no sample มาจาก high-turning regime
ไม่ปรากฏจริง ไม่ใช่ execution bug และไม่ลด threshold แบบ post-hoc รอบถัดไป S284
เปลี่ยนไปใช้ path statistic คนละสมมติฐาน

## S284 — Mann–Kendall Monotonic-Trend Structural Breakout 10R

ไฟล์: `strategy284.py`

Edge hypothesis: ใช้ tie-corrected Mann–Kendall test ซึ่งไม่สมมติ distribution
ตรวจ monotonic tendency ของราคาปิด 64 แท่ง รับ efficient structural breakout
เฉพาะเมื่อ `|z| >= 2.00` และทิศ breakout ตรงกับเครื่องหมายของ z พร้อม short
event-candle stop, TP 10R และ BE 1R

ผล Backtest 2 เดือน baseline ทั้งสองทิศ:

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 42 | 42 | 0 | 0 | 7.14% | -12.01 | -0.20 | -6.01 | 0.91 | 73.87 |

Direction audit พบ BUY 22 ดีล/2 TP/+17.33 ขณะที่ SELL 20 ดีล/1 TP/-29.34
จึงทดสอบ BUY-only survival:

| Window | Signals | Closed | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน | 22 | 22 | 9.09% | +17.33 | +0.28 | +8.66 | 1.26 | 49.38 |
| 6 เดือน | 62 | 62 | 4.84% | -112.69 | -0.62 | -18.78 | 0.59 | 179.40 |

ผล BUY-only ไม่รอด 6 เดือน จึงไม่ optimize และคง baseline defaults ทั้งสองทิศไว้
เป็นหลักฐาน รอบ S285 ใช้ Mann–Kendall no-trend regime กับ failed-sweep reclaim
ซึ่งจับคู่ regime กับ entry geometry แบบ mean-reversion โดยตรง

## S285 — Mann–Kendall No-Trend Failed-Sweep Reclaim 10R

ไฟล์: `strategy285.py`

Edge hypothesis: failed structural sweep เป็น mean-reversion event จึงอนุญาตเฉพาะ
เมื่อราคาปิด 64 แท่งไม่มี monotonic tendency (`|MK z| <= 0.75`) เพื่อหลีกเลี่ยง
การ fade สวน trend ก่อนใช้ reclaim candle extreme เป็น short stop, TP 10R และ BE 1R

ผล Backtest 2 เดือน:

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 7 | 7 | 0 | 0 | 0.00% | -10.57 | -0.17 | -5.29 | 0.00 | 10.57 |

ไม่มี TP จึง fail baseline และไม่ optimize รอบ S286 เปลี่ยนเป็น trend-aligned
liquidity-sweep reclaim: กวาดฝั่งสวน MK trend แล้วเข้า continuation ตาม trend เดิม

## S286 — Mann–Kendall Trend Sweep-Reclaim (Optimized SELL-Only 27R)

ไฟล์: `strategy286.py`

Edge: ใช้ tie-corrected Mann–Kendall test ตรวจ monotonic trend ของราคาปิด
แล้วรับเฉพาะ liquidity sweep ฝั่งสวน trend ที่ event candle ปิด reclaim กลับมา
ตามทิศ trend เดิม เช่น downtrend + กวาด local high + bearish reclaim = SELL
โดยใช้ event extreme + ATR buffer เป็น short structural stop

ผล baseline `MK_Z_MIN_ABS=2.00`, sweep 10, RR10/BE1 ทั้งสองทิศ:

| Window | Signals | Closed | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน | 35 | 35 | 5.71% | +32.02 | +0.52 | +16.01 | 1.40 | 66.64 |
| 6 เดือน | 87 | 87 | 5.75% | +51.83 | +0.29 | +8.64 | 1.18 | 98.84 |

Direction survival พบ SELL 15 ดีล/2 TP/+86.19 ใน 2 เดือน และ 49 ดีล/4 TP/
+188.16 ใน 6 เดือน ขณะที่ BUY ขาดทุน -54.17/-136.33 จึงล็อก SELL-only

Optimization แบบ exact next-open market replay:

- MK threshold `2.25–2.50` เป็นช่วงแข็งแรงร่วมกัน; `2.75` ทำให้กำไร 6 เดือน
  ลดจาก +227.46 เหลือ +136.38 ที่ RR10 และ `3.00` ใกล้เสีย Edge จึงเลือก 2.50
- MK lookback 64/80 รักษา 2 TP ล่าสุดและ 5 TP ระยะยาว แต่ 48 ไม่มี TP และ
  96 เสีย breadth; midpoint 72 ก็เสีย recent winner จึงคง original 64 ไม่เลือก
  80 จากกำไรย้อนหลังที่สูงกว่าเพียงเล็กน้อย
- sweep lookback 12–16 รักษา breadth 2/5 TP และลด DD; 18 ทำให้เหลือ 1/4 TP
  จึงเลือกค่ากลาง 14 ก่อน structural cliff
- RR27.0 รักษา 2/5 TP แต่ RR27.1 เหลือ 1/4 TP จึงเป็น payoff cliff
- BE1.50–1.59 เป็น plateau ร่วมกันทั้งสองหน้าต่าง; เลือก 1.59 โดย minimum
  actual-fill risk 2.53 ทำให้ BE trigger ต่ำสุด 4.02 มากกว่า spread 0.20
- ล็อก `ALLOW_BUY=False`, `ALLOW_SELL=True`, `MK_Z_MIN_ABS=2.50`,
  `SWEEP_LOOKBACK=14`, `TP_RR=27.0`, `BE_RR=1.59`

ผล Backtest มาตรฐานของ optimized default:

| Window | Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน | 11 | 11 | 0 | 0 | 18.18% | +286.10 | +4.69 | +143.05 | 17.04 | 11.99 |
| 6 เดือน | 35 | 35 | 0 | 0 | 14.29% | +1,223.35 | +6.76 | +203.89 | 14.90 | 24.58 |

Portfolio overlap ใน 6 เดือน: S258=0, S262=5, S268=5, S271=0,
S275=15 และ S281=17 จาก S286 ทั้งหมด 35 timestamps จึงกระจายจาก breakout
S258 และ BUY S271 ได้ดี แต่มี overlap กับ SELL-reclaim family ตามธรรมชาติ
Optimization ครอบคลุม direction, MK threshold/lookback, structural sweep,
payoff cliff และ BE plateau แล้ว จึงสิ้นสุด S286 branch และรอบถัดไปเริ่ม S287

## S287 — Pettitt Location-Shift Resumption (Optimized BUY-Only 29.8R)

ไฟล์: `strategy287.py`

Edge: ใช้ Pettitt rank change-point test ตรวจการเปลี่ยนระดับ location/median
ของราคาปิด 64 แท่งแบบ distribution-free โดย change point ต้องมีอายุ 8–24 แท่ง
จากนั้นรอ one-bar pullback สวน regime ใหม่และแท่งปัจจุบันปิด resume ตาม shift
พร้อม directional close control ใช้ low ของ pullback/event + ATR buffer เป็น
short structural stop กลยุทธ์นี้ไม่ใช้ breakout หรือ failed-sweep geometry

ผล baseline p0.05/shift0.50ATR/RR10/BE1 ทั้งสองทิศ:

| Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 59 | 59 | 0 | 0 | 6.78% | -18.48 | -0.30 | -9.24 | 0.89 | 115.02 |

Direction audit พบ BUY 32 ดีล/3 TP/+25.33/PF1.27 ขณะที่ SELL 27 ดีล/
1 TP/-43.81 จึงทดสอบ BUY-only survival:

| Window | Signals | Closed | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน | 32 | 32 | 9.38% | +25.33 | +0.42 | +12.67 | 1.27 | 58.19 |
| 6 เดือน | 70 | 70 | 8.57% | +65.26 | +0.36 | +10.88 | 1.26 | 120.69 |

Optimization แบบ exact next-open market replay:

- RR29.8 รักษา 2 TP ใน 2 เดือนและ 4 TP ใน 6 เดือน แต่ RR29.9 ลดเหลือ
  1/3 TP จึงเป็น payoff cliff
- BE0.68–0.72 เป็น plateau เดียวกันทั้งสองหน้าต่าง เลือกค่ากลาง 0.70;
  BE1.20–1.35 ให้ long net สูงกว่าแต่เพิ่ม DD จากประมาณ 138.7 เป็น 186.3
  และ recent net ต่ำกว่า จึงไม่เลือก long-window optimum
- Pettitt p0.01–0.10 รักษา 2/4 TP ครบ; p0.025 ให้ recent สูงสุดร่วมและ
  long +299.92 ก่อน shift tuning จึงเลือกค่าที่เข้มงวดนี้
- shift gate 1.0–1.5ATR เป็น plateau; 1.25ATR ให้ long net สูงสุด +342.12
  และ DD ต่ำสุดใน plateau ขณะที่ 2.0ATR เสีย recent winner
- max change age 20 เสีย long winner เหลือ 3 TP ส่วน 28 เพิ่ม loser/DD ใน recent
  จึงคง original 24
- ล็อก `ALLOW_BUY=True`, `ALLOW_SELL=False`, `PETTITT_P_MAX=0.025`,
  `SHIFT_ATR_MIN=1.25`, `CHANGE_MAX_AGE=24`, `TP_RR=29.8`, `BE_RR=0.70`

ผล Backtest มาตรฐานของ optimized default:

| Window | Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน | 30 | 30 | 0 | 0 | 6.67% | +174.09 | +2.85 | +87.05 | 3.86 | 43.10 |
| 6 เดือน | 64 | 64 | 0 | 0 | 6.25% | +342.12 | +1.89 | +57.02 | 3.23 | 120.65 |

Minimum actual-fill risk 1.56 ทำให้ BE trigger ต่ำสุด 1.09 มากกว่า spread 0.20
Portfolio overlap 6 เดือน: S258=1, S262=0, S268=0, S271=1, S275=0,
S281=0 และ S286=0 จาก 64 timestamps จึงเป็น BUY change-point diversifier
ที่แยกจาก SELL-reclaim portfolio อย่างชัดเจน แม้ DD สูงกว่า S286
Optimization ครบ direction, Pettitt p/shift/age, payoff cliff และ BE plateau แล้ว;
รอบถัดไปเริ่ม S288

## S288 — Mood Scale-Expansion Resumption (Optimized 38.3R)

ไฟล์: `strategy288.py`

Edge: ใช้ Mood two-sample rank scale test เปรียบ dispersion ของ log return
ช่วงล่าสุด 16 แท่งกับ baseline 48 แท่งแบบ distribution-free รับเฉพาะ scale
expansion ที่ recent displacement มีทิศชัดและ event candle ปิด resume ทิศเดียวกัน
ด้วย directional close control โดยวาง SL หลัง event extreme + ATR buffer
จึงไม่ใช้ breakout, failed-sweep หรือ location-shift geometry

ผล baseline z2/displacement0.50ATR/RR10/BE1:

| Window | Signals | Closed | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน | 16 | 15 | 13.33% | +111.01 | +1.82 | +55.50 | 4.39 | 16.14 |
| 6 เดือน | 43 | 42 | 9.52% | +179.05 | +0.99 | +29.84 | 2.60 | 53.26 |

หนึ่ง signal ท้ายช่วง baseline ยังไม่ปิดก่อน fixed cutoff จึงไม่นับ P&L
Direction audit พบทั้งสองแขนรอด: 2 เดือน BUY 7/1 TP/+33.64 และ SELL
8/1 TP/+77.37; 6 เดือน BUY 16/2 TP/+57.90 และ SELL 26/2 TP/+121.15
จึงคงทั้ง BUY/SELL เพื่อรักษา breadth และ diversification

Optimization แบบ exact next-open market replay:

- RR38.3 รักษา 2 TP ล่าสุดและ 4 TP ระยะยาว แต่ RR38.4 ลดเหลือ 0/2 TP
  จึงเป็น payoff cliff ที่ชัดเจน
- BE0.20 ให้กำไร/PF สูงสุดและ DD ต่ำสุดทั้งสองหน้าต่าง; minimum actual-fill
  risk 2.79 ทำให้ BE trigger ต่ำสุด 0.56 มากกว่า spread 0.20 จึงผ่าน
  spread-honesty ไม่ใช่ BE ที่ไวเกินจริง
- Mood z 1.75–2.00 รักษา breadth 2/4 TP; z1.50 ไม่มี recent TP และ z2.25
  เหลือ 1/2 TP จึงคง original z2.00 ซึ่งให้ net/DD ดีสุดใน plateau
- window 48/12 และ 48/16 รักษา 2 recent TP แต่ 48/12 เหลือ 3 long TP
  ขณะที่ 40/16, 48/20 และ 56/16 เสีย recent winner จึงคง original 48/16
- displacement gate 1.0–1.5ATR รักษา 2/4 TP; เลือก 1.0 เพราะ long net
  สูงสุดและ DD ต่ำสุดใน plateau ส่วน 2.0ATR ทำให้เหลือ 0/2 TP
- ล็อก `MOOD_Z_MIN=2.00`, `MOOD_BASELINE_WINDOW=48`,
  `MOOD_RECENT_WINDOW=16`, `DISPLACEMENT_ATR_MIN=1.00`,
  `TP_RR=38.3`, `BE_RR=0.20` และเปิดทั้งสองทิศ

ผล Backtest มาตรฐานของ optimized default:

| Window | Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน | 14 | 14 | 0 | 0 | 14.29% | +544.08 | +8.92 | +272.04 | 68.84 | 6.62 |
| 6 เดือน | 36 | 36 | 0 | 0 | 11.11% | +1,074.27 | +5.94 | +179.04 | 25.49 | 17.91 |

Optimized 6 เดือนประกอบด้วย BUY 14/2 TP และ SELL 22/2 TP
Portfolio overlap: S258=2, S262=0, S268=0, S271=0, S275=0, S281=0,
S286=0 และ S287=2 จาก 36 timestamps จึงเป็น two-sided volatility-scale
diversifier ที่แยกจาก candidate portfolio เดิมมาก
Optimization ครบ direction, Mood threshold/windows, displacement, RR cliff
และ BE reality plateau แล้ว; รอบถัดไปเริ่ม S289

## S289 — Mood Scale-Contraction Directional Release (Optimized 14.8R)

ไฟล์: `strategy289.py`

Edge: ใช้ Mood two-sample rank scale test ตรวจว่าการกระจายของ log return ช่วง
ล่าสุด 16 แท่งหดตัวเทียบ baseline 48 แท่ง แล้วรอแท่ง directional release ที่มี
body/range และตำแหน่ง close แข็งแรง เข้า market ที่ open แท่งถัดไปพร้อม SL หลัง
event extreme + ATR buffer จึงเป็น volatility-contraction release ที่กลับด้าน
regime จาก S288 scale-expansion และไม่ต้องรอ breakout ของกรอบราคา

ผล baseline z-1.50/body0.60ATR/RR10/BE1 ทั้งสองทิศ:

| Window | Signals | Closed | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน | 46 | 46 | 6.52% | +6.06 | +0.10 | +3.03 | 1.05 | 47.66 |
| 6 เดือน | 115 | 115 | 6.96% | +86.91 | +0.48 | +14.49 | 1.25 | 105.33 |

Direction audit ของ baseline พบ SELL แข็งแรงกว่า แต่ห้ามล็อก SELL-only เพราะ
single-position occupancy เปลี่ยนผล: ทั้งสองทิศได้ 2 เดือน +6.06 ขณะที่ SELL-only
กลับเป็น -4.22; จึงคง BUY/SELL และ Optimize regime โดยตรง

Optimization แบบ exact next-open market replay:

- Mood z ที่ผ่อนเกิน -0.95 เพิ่มไม้เสีย ส่วนช่วง -1.00 ถึง -1.05 รักษา 4 recent
  TP และ 10 long TP; เลือก midpoint `-1.025`
- release body 0.85–1.00ATR รักษา 4 recent TP ครบ; 1.05ATR เหลือ 2 TP และ
  1.10ATR ทำให้ long TP ลดจาก 9–11 เหลือ 5 จึงเลือกค่ากลาง `0.925ATR`
- RR14.86 ยังรักษา 11 long TP แต่ RR14.88 เหลือ 10 TP จึงเลือก `14.80R`
  เพื่อเว้นระยะจาก payoff cliff
- BE1.80–1.85 เป็น plateau; เลือก midpoint `1.825R`
- แม้ recent optimum ที่ 19.5R ให้ +312.74 แต่ 6 เดือนเหลือ 6 TP/+192.00/
  DD179.46 เทียบ 14.8R ที่ 11 TP/+420.44/DD85.25 จึงไม่เลือก local peak
- ล็อก `MOOD_Z_MAX=-1.025`, `RELEASE_BODY_ATR_MIN=0.925`,
  `TP_RR=14.80`, `BE_RR=1.825` และคงทั้งสองทิศ

ผล Backtest มาตรฐานของ optimized default:

| Window | Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน | 45 | 45 | 0 | 0 | 8.89% | +183.26 | +3.00 | +91.63 | 2.31 | 62.61 |
| 6 เดือน | 110 | 110 | 0 | 0 | 10.00% | +420.44 | +2.32 | +70.07 | 1.93 | 85.25 |

Optimized 2 เดือนประกอบด้วย BUY 23/1 TP/-0.86 และ SELL 22/3 TP/+184.12;
6 เดือน BUY 56/4 TP/+53.79 และ SELL 54/7 TP/+366.65 จึงรักษา breadth ของทั้ง
สองทิศ Minimum actual-fill risk 2.71 ทำให้ BE trigger ต่ำสุด 4.95 มากกว่า
spread 0.20 อย่างชัดเจน

Portfolio overlap 6 เดือน: S258=14, S262=0, S268=0, S271=6, S275=1,
S281=1, S286=0, S287=4 และ S288=0 จาก 110 timestamps จึงแยกจาก S288
scale-expansion โดยตรงและไม่ซ้ำ SELL rank-reclaim S262/S268/S286
Optimization ครบ direction occupancy, Mood threshold, release strength,
RR cliff และ BE plateau แล้ว; รอบถัดไปเริ่ม S290

## S290 — Wasserstein Return-Distribution Drift (Optimized 25.4R)

ไฟล์: `strategy290.py`

Edge: เปรียบ empirical distribution ของ log return ช่วงล่าสุด 16 แท่งกับ
baseline 48 แท่งด้วย first Wasserstein distance ซึ่งวัดการย้ายของ distribution
ทั้งก้อน แล้ว normalize ด้วย baseline MAD; signed median shift ระบุทิศและต้องมี
แท่ง directional release ปิดยืนยันก่อนเข้า next-open market พร้อม event-extreme
stop จึงต่างจาก S287 price-level change point และ S288/S289 ที่วัด scale เท่านั้น

ผล baseline W1=0.75/median-shift=0.20MAD/RR10/BE1:

| Window | Signals | Closed | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน | 57 | 57 | 3.51% | -83.79 | -1.37 | -41.90 | 0.62 | 107.18 |
| 6 เดือน | 122 | 122 | 3.28% | -238.77 | -1.32 | -39.79 | 0.53 | 251.84 |

Threshold survival audit พบ median shift ต้องมีนัยสำคัญจริง ช่วง
0.825–0.850MAD รักษา 2 recent/4 long TP แต่ 0.875 ทำให้ long เหลือ 3 TP
จึงเลือก midpoint `0.8375MAD`

Optimization แบบ exact next-open market replay:

- ใช้ exact one-dimensional CDF integral ซึ่งผ่าน invariant ว่า distribution
  เดียวกันต้องมี W1=0; ช่วง W1 0.40–0.65 รักษา 2 recent/4 long TP ส่วน 0.70
  เสีย recent winner จึงล็อก `WASSERSTEIN_MAD_MIN=0.625` ให้ห่าง cliff
- RR25.50 ยังรักษา 2 recent/4 long TP แต่ RR25.55 ลด recent เหลือ 1 TP
  และ RR26 ลด long เหลือ 3 TP จึงเลือก `25.40R` เพื่อเว้นระยะจาก cliff
- BE1.45–1.50 เป็น plateau ร่วมกันทั้งสองหน้าต่าง จึงเลือก midpoint `1.475R`
- 25.4R/BE1.475 ให้ breadth ดีกว่า long-window local optimum 40R ซึ่งเหลือ
  3 long TP และไม่มี recent breadth ที่เทียบเท่า
- Direction audit ของ optimized combined replay พบ BUY เป็นแขนหลัก แต่ SELL
  ยังบวก +159.41 ใน 6 เดือน; จึงคงทั้งสองทิศเพื่อรักษา long-window
  diversification ไม่ตัด SELL จาก recent window เดียว

ผล Backtest มาตรฐานของ optimized default:

| Window | Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน | 23 | 23 | 0 | 0 | 8.70% | +230.81 | +3.78 | +115.41 | 4.37 | 40.55 |
| 6 เดือน | 46 | 46 | 0 | 0 | 8.70% | +440.60 | +2.43 | +73.43 | 3.50 | 45.09 |

Optimized 6 เดือนประกอบด้วย BUY 21/3 TP/+281.19 และ SELL 25/1 TP/
+159.41 Minimum actual-fill risk 1.94 ทำให้ BE trigger ต่ำสุด 2.86 มากกว่า
spread 0.20 อย่างชัดเจน

Portfolio overlap 6 เดือน: S258=7, S262=1, S268=1, S271=5, S275=1,
S281=1, S286=1, S287=1, S288=3 และ S289=2 จาก 46 timestamps จึงเป็น
return-distribution diversifier ที่ overlap ต่ำกับ candidate portfolio
Optimization ครบ direction occupancy, median/W1 thresholds, payoff cliff
และ BE plateau แล้ว; รอบถัดไปเริ่ม S291

## S291 — Wasserstein Distribution-Drift Rejection Fade 10R

ไฟล์: `strategy291.py`

Edge hypothesis: ใช้ exact W1 และ signed median shift ชุดเดียวกับ S290 แต่
ทดสอบ failure regime ฝั่งตรงข้าม โดยแท่งปิดต้องสวน distribution drift มี
directional close control และทิ้ง wick ไปทาง drift เดิมก่อน fade ที่ next open
พร้อม event-extreme stop

ผล Backtest มาตรฐาน:

| Window | Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน | 18 | 18 | 0 | 0 | 0.00% | -68.94 | -1.13 | -34.47 | 0.00 | 68.94 |
| 6 เดือน | 43 | 43 | 0 | 0 | 2.33% | -103.49 | -0.57 | -17.25 | 0.36 | 162.36 |

Direction audit ก็ไม่พบแขนที่รอดพร้อมกัน: 2 เดือน BUY 9/0 TP/-51.38 และ
SELL 9/0 TP/-17.56; 6 เดือน BUY 22/1 TP/-42.09 และ SELL 21/0 TP/-61.40
จึงไม่มีหลักฐานว่า drift rejection ให้ 10R fade edge และไม่ทำ payoff
optimization บน sample ที่ไม่มี recent winner; รอบถัดไปเริ่ม S292

## S292 — Ljung–Box Multi-Lag Persistence Release (Optimized SELL 52.5R)

ไฟล์: `strategy292.py`

Edge: ใช้ Ljung–Box portmanteau statistic ตรวจว่า return autocorrelation หลาย
lag แตกต่างจากศูนย์ร่วมกัน พร้อมบังคับ weighted autocorrelation เป็นบวกและมี
directional displacement ก่อนรับแท่ง release ตาม regime จึงวัด multi-lag
magnitude dependence ต่างจาก S171 lag-1 autocorrelation และ S267/S268
sign-run dependence; ใช้ event-extreme stop และ next-open market fill

Baseline z1.35/rho0.055/RR10/BE1 ทั้งสองทิศใน 2 เดือนมีเพียง 1 signal,
0 TP, Net -14.73, P&L/day -0.24, P&L/month -7.37, WR 0%, PF0 และ
DD14.73 Gate diagnostics พบ z/rho ซ้อนกันจน sample starvation

Survival/optimization แบบ exact next-open market replay:

- ผ่อนเป็น z0.50/rho>0 แล้ว direction audit พบ BUY-only แพ้ทั้ง 2m/6m
  (-7.76/-76.44) แต่ SELL-only รอด +80.82/+37.83 จึงล็อก SELL-only
- หลัง payoff tuning, z0.25–0.35 รักษา 1 recent TP และ 2 independent long TP;
  z0.20 หรือ 0.40 เหลือ long TP เดียว จึงเลือก midpoint `LJUNG_BOX_Z_MIN=0.30`
- `WEIGHTED_AUTOCORR_MIN=0.00` ยังบังคับ weighted rho ไม่ติดลบ ขณะที่
  0.02 ขึ้นไปตัด recent winner จึงคง boundary เชิงสมมติฐานที่ศูนย์
- RR52.95 ยังรักษา 1 recent/2 long TP แต่ RR53.00 ไม่เหลือ recent TP และ
  long winner หาย จึงเลือก `52.50R` เว้นระยะ 0.50R จาก payoff cliff
- BE0.40–0.55 เป็น plateau เดียวกันทั้งสองหน้าต่าง เลือก midpoint `0.475R`

ผล Backtest มาตรฐานของ optimized default:

| Window | Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน | 7 | 7 | 0 | 0 | 14.29% | +476.93 | +7.82 | +238.47 | 31.07 | 9.66 |
| 6 เดือน | 20 | 20 | 0 | 0 | 10.00% | +893.90 | +4.94 | +148.98 | 26.77 | 28.09 |

Long window มี TP สองเหตุการณ์อิสระวันที่ 18 มีนาคมและ 5 มิถุนายน ไม่ใช่
winner เดียวซ้ำจาก nested window แต่กลยุทธ์ยังมี sample ต่ำและควรจัดเป็น
sparse satellite ไม่ใช่ core allocation Minimum actual-fill risk 3.17 ทำให้
BE trigger ต่ำสุด 1.51 มากกว่า spread 0.20

Portfolio overlap 6 เดือน: S258=1, S262=0, S268=0, S271=0, S275=0,
S281=0, S286=0, S287=0, S288=1, S289=0 และ S290=4 จาก 20 timestamps
จึงกระจายจาก candidate portfolio ได้ดี Optimization ครบ direction survival,
z/rho gates, payoff cliff และ BE plateau แล้ว; รอบถัดไปเริ่ม S293

## S293 — Ljung–Box Anti-Persistence Failed-Sweep Reclaim (SELL 25.1R)

ไฟล์: `strategy293.py`

Edge: ใช้ Ljung–Box joint serial-dependence gate เหมือน S292 แต่บังคับ
weighted return autocorrelation ติดลบ แล้วรอแท่งกวาด liquidity high/low ที่ปิด
reclaim กลับพร้อม rejection wick ก่อนเข้า next-open fade ด้วย event-extreme stop
จึงเป็น magnitude anti-persistence + price-structure confluence ไม่ใช่ sign-run
reclaim แบบ S268

ผล baseline z0.50/rho≤-0.015/sweep12/RR10/BE1 ทั้งสองทิศ:

| Window | Signals | Closed | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน | 34 | 34 | 11.76% | +153.82 | +2.52 | +76.91 | 3.53 | 30.63 |
| 6 เดือน | 85 | 85 | 10.59% | +356.90 | +1.97 | +59.48 | 2.70 | 64.40 |

Direction audit พบ BUY ขาดทุน -35.88/-42.99 ใน 2m/6m ขณะที่ SELL
+189.70/+399.89; SELL-only exact occupancy เพิ่ม recent เป็น +189.50/PF8.58/
DD8.44 และ long +394.92/PF5.24/DD41.24 จึงล็อก SELL-only

Optimization แบบ exact next-open market replay:

- RR25.2 ยังรักษา 3 recent/5 long TP แต่ RR25.3 ลดเป็น 2/4 TP จึงเลือก
  `25.1R` ให้ห่าง payoff cliff 0.2R
- BE0.70–1.05 เป็น plateau ร่วมกันทั้งสองหน้าต่าง เลือก midpoint `0.875R`
- z0.25–0.50 รักษา 3/5 TP แต่ z0.75 เสีย long winner; เลือก z0.50 ซึ่งลด
  long DD จาก 57.16 ที่ z0.25 เหลือ 41.04
- rho=-0.03 เป็นขอบ plateau ที่รักษา 5 long TP; -0.04 เหลือ 4 TP ขณะที่
  -0.02 ถึง 0 เพิ่ม loser จึงล็อก `WEIGHTED_AUTOCORR_MAX=-0.03`
- sweep lookback14–16 รักษา 3/5 TP และลด loser; 18 ลดเป็น 2/4 TP จึงเลือก 16

ผล Backtest มาตรฐานของ optimized default:

| Window | Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน | 15 | 15 | 0 | 0 | 20.00% | +414.79 | +6.80 | +207.40 | 18.00 | 12.76 |
| 6 เดือน | 42 | 42 | 0 | 0 | 11.90% | +863.80 | +4.77 | +143.97 | 11.08 | 41.04 |

Minimum actual-fill risk 2.32 ทำให้ BE trigger ต่ำสุด 2.03 มากกว่า spread0.20
Portfolio overlap 6 เดือน: S258=0, S262=4, S268=4, S271=0, S275=16,
S281=12, S286=10, S287=0, S288=0, S289=1, S290=0 และ S292=0
จาก 42 timestamps จึงมี Edge แข็งแรงแต่ overlap สูงกับ SELL-reclaim family;
ควรเป็น alternative selector ไม่ใช่เพิ่ม exposure ซ้อนเต็มน้ำหนัก
Optimization ครบ direction, z/rho, sweep geometry, RR cliff และ BE plateau
แล้ว; รอบถัดไปเริ่ม S294

## S294 — Chow Structural Slope-Break Release (BUY 21.1R)

ไฟล์: `strategy294.py`

Edge: เปรียบ OLS เส้นเดียวตลอดหน้าต่าง 64 bars กับ OLS แยก baseline 40
และ recent 24 bars แบบ Chow-style F statistic เพื่อหาการเปลี่ยน slope regime
จาก residual error โดยตรง จากนั้นเข้า BUY เฉพาะแท่ง release ที่ไปตาม recent
slope และปิดใกล้ high ใช้ event-low เป็น short stop จึงวัด structural
trend break ต่างจาก return-dependence ของ S292/S293

Baseline F3/RR10/BE1 ทั้งสองทิศ:

| Window | Signals | Closed | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน | 83 | 83 | 6.02% | +28.73 | +0.47 | +14.37 | 1.10 | 83.85 |
| 6 เดือน | 206 | 206 | 5.83% | -82.39 | -0.46 | -13.73 | 0.89 | 190.42 |

Direction audit ที่ RR10 พบ SELL-only +67.97 ใน 2m แต่ -86.64 ใน 6m;
BUY-only -39.24 ใน 2m และ +4.25 ใน 6m เมื่อผ่อน F จาก 3 เป็น 2
BUY-only รอดพร้อมกันเป็น +17.25/+60.74 จึงหยุดสร้าง ID ใหม่และ optimize
candidate ตามกติกา short-SL TP≥7R

Optimization แบบ exact next-open market replay:

- ล็อก BUY-only; SELL มี recent/long regime conflict และไม่ผ่าน survival
- `CHOW_F_MIN=1.5–2.5` รักษา 3 recent/6 long TP เหมือนกัน ก่อนเสีย winner
  ที่ F3 จึงเลือก 2.0 กลาง plateau
- recent slope 0.015–0.025 ATR และ slope-change 0.01–0.03 ATR รักษา
  winner set; 0.035/0.05 เริ่มตัด winner จึงคง 0.025/0.020
- acceleration 0.8–1.1 รักษา 3/6 TP แต่ 1.4 เหลือ 3/5 จึงเลือก 1.1
- RR21.3 ยังมี 3/6 TP แต่ RR21.4 ลดเป็น 2/5 จึงเลือก `21.1R`
  เว้นระยะ 0.3R จาก payoff cliff
- BE0.50–0.55 เป็น recent plateau จึงเลือก midpoint `0.525R`;
  แม้ long optimum อยู่ 1.35–1.45 แต่ 0.525 ให้ผลบวกแข็งแรงทั้งสองหน้าต่าง
  และลดการพึ่ง long-window optimization

ผล Backtest มาตรฐานของ optimized default:

| Window | Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน | 44 | 44 | 0 | 0 | 6.82% | +276.77 | +4.54 | +138.39 | 3.56 | 50.65 |
| 6 เดือน | 101 | 101 | 0 | 0 | 5.94% | +459.27 | +2.54 | +76.55 | 2.89 | 98.72 |

Long window มี TP อิสระในวันที่ 6, 18, 27 กุมภาพันธ์ และ recent TP วันที่
28 พฤษภาคม, 1, 2 กรกฎาคม Minimum actual-fill risk 2.28 และ minimum BE
trigger 1.20 มากกว่า spread0.20 Portfolio overlap 6 เดือน:
S258=4, S262=0, S268=0, S271=9, S275=0, S281=0, S286=0, S287=18,
S288=2, S289=12, S290=9, S292=0, S293=0 จาก 101 timestamps
จึงกระจายจาก SELL family ได้ดี แต่สัมพันธ์กับ BUY momentum/break families
บางส่วน และยังต้องถือเป็น high-R sparse-winner satellite

## S295 — Sup-Chow Adaptive Slope-Break Release 10R

ไฟล์: `strategy295.py`

Edge: ต่อจาก fixed 40/24 split ของ S294 โดยค้นหาจุดแบ่งที่ให้ Chow F สูงสุด
ใน recent segment 16–32 bars บนหน้าต่าง 72 bars แล้วรับ release ตาม slope
ใหม่ จุดแบ่งทั้งหมดประกาศล่วงหน้าและใช้เฉพาะแท่งปิด จึงไม่มี look-ahead;
แนวคิดมุ่งลดความเสี่ยงที่ S294 ผูกกับ breakpoint ตายตัว

ผล baseline F5/RR10/BE1 ทั้งสองทิศ:

| Window | Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน | 85 | 85 | 0 | 0 | 5.88% | +60.63 | +0.99 | +30.32 | 1.23 | 73.65 |
| 6 เดือน | 224 | 224 | 0 | 0 | 4.46% | -239.39 | -1.32 | -39.90 | 0.72 | 373.67 |

Direction audit ไม่พบแขนที่รอดพร้อมกัน: BUY-only 2m +26.25 แต่ 6m
-101.94; SELL-only 2m +34.38 แต่ 6m -137.45 Sup-Chow threshold
sensitivity F0/2/3/5/7/10/15/20 ก็ไม่สร้าง plateau ร่วม: BUY F20
พลิก long เป็น +7.98 แต่ recent เป็น -12.03 ขณะที่ threshold ที่ recent
เป็นบวกยังทำให้ long ติดลบทั้งหมด จึงสรุปว่า adaptive breakpoint เพิ่ม
multiple-testing noise มากกว่า edge และไม่ทำ payoff optimization หลังไม่ผ่าน
cross-window survival gate; รอบถัดไปเริ่ม S296

## S296 — Sup-Chow Slope-Break Rejection Fade (SELL 26.8R)

ไฟล์: `strategy296.py`

Edge: ใช้ adaptive Sup-Chow slope break จาก S295 เป็น crowding regime แต่ไม่
ไล่ตาม slope; รอราคา extend ตาม slope ไปกวาด extreme 16 bars แล้วปิด reclaim
สวนพร้อม rejection wick ก่อนเข้า next-open fade ใช้ event extreme + ATR buffer
เป็น short stop จึงทดสอบ failed structural break แทน continuation ที่ล้มเหลว
ใน S295

ผล baseline F10/wick0.28/RR10/BE1 ทั้งสองทิศ:

| Window | Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน | 34 | 34 | 0 | 0 | 14.71% | +182.46 | +2.99 | +91.23 | 3.64 | 21.21 |
| 6 เดือน | 100 | 100 | 0 | 0 | 7.00% | +217.97 | +1.20 | +36.33 | 1.75 | 163.04 |

Direction audit พบ BUY-only 2m +49.99 แต่ 6m -58.98 ขณะที่ SELL-only
รอดพร้อมกัน +129.33/+273.61 จึงล็อก SELL-only และหยุดสร้าง ID ใหม่เพื่อ
optimize ตามกติกา short-SL TP≥7R

Optimization แบบ exact next-open market replay:

- RR27.0 ยังรักษา 2 recent/3 long TP แต่ RR27.1 ลดเป็น 1/2 TP จึงเลือก
  `26.8R` เว้นระยะ 0.3R จาก payoff cliff
- BE0.300–0.325 เป็น plateau เดียวกันทั้งสองหน้าต่าง; เลือก midpoint
  `0.3125R` โดยต่ำกว่านี้ที่ 0.275 เริ่มเสีย winner
- Sup-Chow F5–10 รักษา 2/3 TP ก่อน F12.5 ลดเป็น 1/2 จึงคง F10
- sweep lookback 10–20 รักษา winner set ทั้งหมด จึงคง midpoint 16
- rejection wick 0.24–0.32 รักษา 2/3 TP ก่อน 0.36 ลดเป็น 1/2;
  เลือก 0.30 ห่าง cliff และลด loser จาก baseline
- reclaim 0–0.04 ATR ให้ผลแทบเหมือนกัน จึงคง 0.02 ตามนิยาม closed reclaim

ผล Backtest มาตรฐานของ optimized default:

| Window | Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน | 16 | 16 | 0 | 0 | 12.50% | +367.04 | +6.02 | +183.52 | 60.49 | 5.17 |
| 6 เดือน | 45 | 45 | 0 | 0 | 6.67% | +752.53 | +4.16 | +125.42 | 11.99 | 49.36 |

Long window มี TP อิสระวันที่ 2 มีนาคม, 26 พฤษภาคม และ 5 มิถุนายน
Minimum actual-fill risk 1.95 และ minimum BE trigger 0.61 มากกว่า spread0.20
Portfolio overlap 6 เดือน: S258=0, S262=2, S268=2, S271=0, S275=13,
S281=13, S286=9, S287=0, S288=0, S289=0, S290=0, S292=0, S293=13,
S294=0 จาก 45 timestamps จึงมี edge/ผลตอบแทนแข็งแรงแต่ overlap สูงกับ
SELL failed-sweep family; ควรเป็น alternative selector หรือ capped satellite
ไม่ใช่ stack exposure เต็มน้ำหนักพร้อม S275/S281/S293

## S297 — Jarque–Bera Asymmetric-Tail Release (SELL 52.5R)

ไฟล์: `strategy297.py`

Edge: ใช้ Jarque–Bera omnibus statistic วัด skewness และ excess kurtosis
ร่วมกันบน closed log returns เพื่อคัด non-Gaussian tail regime แล้วรับเฉพาะ
release ที่ไปทาง skew tail ใช้ event-extreme + ATR buffer เป็น short stop
ต่างจาก S152–S155/S172–S173 ที่ใช้ skewness เดี่ยวโดยไม่มี omnibus
distribution-shape gate

ผล baseline lookback64/JB6/skew0.25/RR10/BE1 ทั้งสองทิศ:

| Window | Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน | 63 | 63 | 0 | 0 | 4.76% | -50.39 | -0.83 | -25.20 | 0.80 | 116.35 |
| 6 เดือน | 145 | 145 | 0 | 0 | 4.83% | -104.80 | -0.58 | -17.47 | 0.82 | 147.42 |

Direction audit พบ BUY-only ลบ -63.51/-142.30 แต่ SELL-only รอดบาง
+13.12/+37.30 ใน 2m/6m จึงล็อก SELL-only และเข้าสู่ optimization

Optimization แบบ exact next-open market replay:

- RR52.8 ยังรักษา 1 recent/2 long TP แต่ RR53.0 ลดเป็น 0/1 จึงเลือก
  `52.5R` เว้นระยะ 0.5R จาก payoff cliff
- BE0.225–0.350 เป็น plateau เดียวกันทั้งสองหน้าต่าง เลือก midpoint
  `0.2875R`
- JB20–29 รักษา 1/2 TP และค่อยลด loser แต่ JB30 เสีย winner เหลือ 0/1;
  เลือก `JARQUE_BERA_MIN=28` ห่าง cliff 2 จุด
- abs skew 0.10–0.50 รักษา 1/2 TP; 0.75 เสีย long winner และ 1.25
  เสียทั้งหมด จึงเลือก 0.40
- return lookback64–72 รักษา 1/2 TP ขณะที่ 48/56/80 เสีย recent winner;
  เลือก midpoint 68 ซึ่งให้ PF/DD long ดีกว่า 64 โดยไม่เปลี่ยน recent result

ผล Backtest มาตรฐานของ optimized default:

| Window | Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน | 15 | 15 | 0 | 0 | 6.67% | +474.61 | +7.78 | +237.31 | 27.11 | 11.03 |
| 6 เดือน | 39 | 39 | 0 | 0 | 5.13% | +988.91 | +5.46 | +164.82 | 20.29 | 26.17 |

Long window มี TP อิสระวันที่ 18 มีนาคมและ 5 มิถุนายน Minimum actual-fill
risk 3.83 และ minimum BE trigger 1.10 มากกว่า spread0.20 Portfolio overlap
6 เดือน: S258=0, S262=0, S268=0, S271=0, S275=1, S281=1, S286=0,
S287=0, S288=3, S289=1, S290=2, S292=6, S293=0, S294=0, S296=1
จาก 39 timestamps จึงกระจายจาก SELL reclaim cluster ได้ดี แต่ผลกำไรยังพึ่ง
winner เพียงสองเหตุการณ์และต้องจัดเป็น sparse high-R satellite

## S298 — Jarque–Bera Tail-Exhaustion Reclaim (SELL 24R)

ไฟล์: `strategy298.py`

Edge: เป็น counterpart ของ S297 โดยไม่ตาม skew tail แต่รอ extension ตาม
positive skew กวาด recent high แล้วปิด reclaim พร้อม upper rejection wick
ก่อนเข้า SELL fade ด้วย event-high + ATR buffer stop จึงทดสอบ tail exhaustion
ผ่าน price structure

ผล baseline lookback68/JB6/skew0.25/sweep16/wick0.28/RR10/BE1 ทั้งสองทิศ:

| Window | Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน | 15 | 15 | 0 | 0 | 0.00% | -22.08 | -0.36 | -11.04 | 0.00 | 22.08 |
| 6 เดือน | 42 | 42 | 0 | 0 | 4.76% | -51.00 | -0.28 | -8.50 | 0.65 | 73.99 |

Direction baseline ก็ไม่รอด: BUY-only -6.95/-56.51 และ SELL-only
-21.08/-0.64 ใน 2m/6m แต่ relaxed audit JB0/skew0 พบ SELL-only พลิกเป็น
+7.35/+130.22 ขณะที่ BUY ยังลบ จึงล็อก SELL-only และ optimize จาก relaxed
candidate แทนการยุติ branch

Optimization แบบ exact next-open market replay:

- RR24.2 ยังรักษา 2 recent/5 long TP แต่ RR24.3 ลด long เหลือ 3 TP
  จึงเลือก `24.0R` เว้นระยะ 0.3R จาก long-window payoff cliff
- BE1.50–1.65 เป็น plateau เดียวกันทั้งสองหน้าต่าง เลือก midpoint `1.575R`
- JB0–0.25 รักษา 2/5 TP และ JB0.25 ลด loser; JB0.50 เสีย long winner
  จึงเลือก weak-shape floor `JARQUE_BERA_MIN=0.25`
- abs skew0–0.10 รักษา 2/5 TP แต่ 0.15 เสีย long winner จึงเลือก 0.10
- sweep lookback10–16 รักษา 2/5 TP ก่อน 18 เสีย 1/1 จึงเลือก midpoint 14
- rejection wick0.20–0.45 รักษา 2/5 TP และค่อยลด loser; 0.50 ลดเป็น
  0/3 TP จึงเลือก 0.45

ผล Backtest มาตรฐานของ optimized default:

| Window | Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน | 15 | 15 | 0 | 0 | 13.33% | +228.20 | +3.74 | +114.10 | 6.44 | 31.96 |
| 6 เดือน | 39 | 39 | 0 | 0 | 12.82% | +787.72 | +4.35 | +131.29 | 7.44 | 74.95 |

Long window มี TP อิสระวันที่ 2, 5, 12 มีนาคม, 26 พฤษภาคม และ 2 มิถุนายน
Minimum actual-fill risk 2.88 และ minimum BE trigger 4.54 มากกว่า spread0.20
Portfolio overlap 6 เดือน: S258=0, S262=3, S268=3, S271=0, S275=12,
S281=11, S286=9, S287=0, S288=0, S289=0, S290=0, S292=0, S293=13,
S294=0, S296=14, S297=0 จาก 39 timestamps จึงเป็น robust SELL-reclaim
candidate แต่ overlap สูงมากกับ S296/S293/S275; ควรใช้เป็น alternative
selector ไม่ใช่ stack exposure เพิ่ม

## S299 — Gini Volatility-Concentration Release (SELL 52.5R)

ไฟล์: `strategy299.py`

Edge: วัดความกระจุกตัวของ absolute closed log returns ด้วย Gini coefficient
ร่วมกับสัดส่วน movement ที่อยู่ใน top quartile เพื่อแยก regime ที่ volatility
เกิดจาก shock bars ไม่กี่แท่งออกจากความผันผวนแบบกระจายตัว แล้วรับเฉพาะ
directional SELL release ที่มี displacement และ body ยืนยัน ใช้ event high +
ATR buffer เป็น short stop แนวคิดจึงต่างจาก S297/S298 ซึ่งคัด regime ด้วย
skewness/kurtosis และช่วยเพิ่มตัวเลือกจาก distribution concentration โดยตรง

ผล strict baseline Gini0.55/share0.60/RR10/BE1 ทั้งสองทิศ:

| Window | Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน | 0 | 0 | 0 | 0 | N/A | 0.00 | 0.00 | 0.00 | N/A | 0.00 |
| 6 เดือน | 2 | 2 | 0 | 0 | 0.00% | -8.52 | -0.05 | -1.42 | 0.00 | 8.52 |

Baseline เข้มเกินจน sample starvation จึงทำ relaxed audit ที่ Gini0/share0:
BUY-only ลบ -16.88/-352.27 และ SELL-only บวก +40.31 ใน 2m แต่ -34.36
ใน 6m จากนั้น concentration grid พบ SELL Gini0.45/share0.55 รอดพร้อมกัน
+19.76/+35.78 จึงล็อก SELL-only และหยุดสร้าง ID ใหม่เพื่อ optimize ตามกติกา
short-SL TP≥7R

Optimization แบบ exact next-open market replay:

- RR52.8 ยังรักษา 1 recent/2 long TP แต่ RR53.0 ลดเป็น 0/1 จึงเลือก
  `52.5R` เว้นระยะ 0.5R จาก payoff cliff
- BE0.225–0.350 เป็น recent plateau และ 0.225–0.275 ยังรอดใน long window;
  เลือก `0.25R` ซึ่งอยู่ภายในช่วงร่วมและห่างจากขอบล่าง
- Gini0.46–0.48 และ top-quartile share0.56–0.58 รักษา winner set เดิม
  แต่ Gini0.49 หรือ share0.59 ทำให้ winner หาย จึงเลือก midpoint
  `GINI_MIN=0.47` และ `TOP_QUARTILE_SHARE_MIN=0.57`
- direction window8–16 และ displacement0.25–0.65 ATR รักษา 1/2 TP
  จึงเลือกค่ากลาง 12 bars และ 0.45 ATR
- release body0.40–0.70 ATR รักษา winner set เดิม โดย 0.60 ลด loser
  ได้โดยยังไม่ชิดขอบ plateau จึงเลือก 0.60 ATR

ผล Backtest มาตรฐานของ optimized default:

| Window | Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน | 5 | 5 | 0 | 0 | 20.00% | +483.02 | +7.92 | +241.51 | 50.44 | 6.03 |
| 6 เดือน | 37 | 37 | 0 | 0 | 5.41% | +955.40 | +5.28 | +159.23 | 12.27 | 55.52 |

Long window มี TP อิสระวันที่ 18 มีนาคมและ 5 มิถุนายน Minimum actual-fill
risk 3.34 และ minimum BE trigger 0.835 มากกว่า spread0.20 Portfolio overlap
6 เดือนที่เด่น: S257=6, S282=9, S292=6, S297=7 ส่วน S296 และ S298
ไม่พบ timestamp ตรงกัน จาก 37 timestamps จึงกระจายจาก SELL reclaim cluster
ได้พอสมควร แต่กำไรยังพึ่ง winner เพียงสองเหตุการณ์และ recent window มีเพียง
5 เทรด จึงต้องจัดเป็น sparse high-R satellite ไม่ใช่กลยุทธ์แกนหลัก

## S300 — Anderson–Darling Asymmetric-Tail Release (BUY 12R)

ไฟล์: `strategy300.py`

Edge: เปรียบ empirical CDF ของ closed log returns กับ normal CDF ด้วย
Anderson–Darling statistic ซึ่งให้น้ำหนัก observations บริเวณสองหางสูงกว่า
กลาง distribution แล้วใช้ signed extreme-tail energy imbalance ระบุว่าหางบน
หรือหางล่างครอง regime ก่อนรับ closed release candle ไปทางเดียวกัน ต่างจาก
S297 Jarque–Bera ที่สรุปรูปร่างด้วย skewness/kurtosis moments และจาก S299
ที่วัดเพียงความกระจุกตัวของ absolute movement

ผล baseline lookback64/AD1.25/imbalance0.15/RR10/BE1 ทั้งสองทิศ:

| Window | Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน | 5 | 5 | 0 | 0 | 20.00% | +30.32 | +0.50 | +15.16 | 2.50 | 14.93 |
| 6 เดือน | 11 | 11 | 0 | 0 | 18.18% | +56.87 | +0.31 | +9.48 | 2.53 | 16.87 |

Direction audit ยืนยันด้วย replay ใหม่ต่อฝั่ง: BUY-only ดีขึ้นเป็น +45.05/+88.07
และ WR25.00%/28.57% ใน 2m/6m ส่วน SELL-only ไม่มี TP และลบ -14.73/-31.20
จึงล็อก BUY-only และหยุดสร้าง ID ใหม่เพื่อ optimize ตามกติกา short-SL TP≥7R

Optimization แบบ exact next-open market replay:

- RR12.15 ยังรักษา 1 recent/2 long TP แต่ RR12.20 ทำให้ recent winner หาย
  จึงเลือก `12.0R` เว้นระยะ 0.20R จาก payoff cliff
- BE0.20–0.70 ให้ recent plateau สูงสุดและ long ยังคงแข็งแรง; 0.80 เริ่มเสีย
  recent P&L ขณะที่ long ดีขึ้นเพียงเล็กน้อย จึงเลือก midpoint `0.50R`
- AD1.40–1.50 รักษา 1/2 TP แต่ AD1.60 เสีย recent winner จึงเลือก midpoint
  `ANDERSON_DARLING_MIN=1.45`
- tail imbalance0.14–0.15 รักษา winner ทั้งสองหน้าต่าง แต่ 0.16 เสีย long
  winner จึงเลือก midpoint `TAIL_IMBALANCE_MIN=0.145`
- tail fraction0.10–0.15 รักษา 1/2 TP และค่อยลด loser แต่ 0.175 เสีย long
  winner จึงเลือก 0.15 ซึ่งห่าง cliff ที่ทดสอบ 0.025
- return lookback56–64 รักษา 1/2 TP แต่ 68 เสีย recent winner จึงเลือก 62
  แทนการวาง default ไว้ที่ขอบ 64
- release body0.35–0.55 และ range0.55–0.75 รักษา 1/2 TP ก่อน body0.65
  หรือ range0.85 เสีย long winner จึงเลือก body0.55/range0.65;
  close fraction0.55–0.70 ไม่เปลี่ยน winner set จึงคง midpoint 0.62

ผล Backtest มาตรฐานของ optimized default:

| Window | Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน | 3 | 3 | 0 | 0 | 33.33% | +60.27 | +0.99 | +30.14 | 151.67 | 0.40 |
| 6 เดือน | 8 | 8 | 0 | 0 | 25.00% | +104.84 | +0.58 | +17.47 | 14.15 | 7.57 |

Long window มี TP อิสระวันที่ 11 พฤษภาคมและ 26 มิถุนายน Minimum actual-fill
risk 3.83 และ minimum BE trigger 1.915 มากกว่า spread0.20 Portfolio overlap
6 เดือน: S257=1, S282=1, S294=1 และ S258/S275/S281/S288/S292/S293/
S296/S297/S298/S299=0 จาก 8 timestamps จึงกระจายจากกลุ่มเดิมได้ดีมาก
แต่ sample ยังบางและกำไรพึ่ง winner เพียงสองเหตุการณ์ จึงต้องจัดเป็น sparse
high-R satellite และไม่ควรตีความ PF สูงเป็นความแน่นอนของผลในอนาคต

## S301 — Two-Sample KS Distribution-Break Release (SELL 10.2R)

ไฟล์: `strategy301.py`

Edge: แบ่ง closed log returns เป็น baseline 48 และ recent 16 observations
แบบไม่ซ้อนกัน แล้วใช้ exact two-sample Kolmogorov–Smirnov distance วัดจุดที่
empirical CDF สองช่วงแยกจากกันมากที่สุด พร้อมใช้ median shift ที่ normalize
ด้วย pooled MAD ระบุทิศ ก่อนรับแท่ง release ที่ปิดยืนยัน distribution regime ใหม่
ต่างจาก S290 Wasserstein ซึ่งอินทิเกรตระยะห่างตลอด distribution และอาจเจือจาง
การเปลี่ยนแปลงที่กระจุกอยู่เฉพาะบาง quantile

ผล baseline KS1.15/shift0.20MAD/RR10/BE1 ทั้งสองทิศ:

| Window | Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน | 22 | 22 | 0 | 0 | 9.09% | +93.04 | +1.53 | +46.52 | 2.20 | 34.49 |
| 6 เดือน | 53 | 53 | 0 | 0 | 5.66% | +37.84 | +0.21 | +6.31 | 1.21 | 86.95 |

Direction audit แบบ replay ใหม่พบ SELL-only รอดพร้อมกัน +39.24/+51.95
ขณะที่ BUY-only recent +53.80 แต่ long -14.11 จึงล็อก SELL-only และหยุดสร้าง
ID ใหม่เพื่อ optimize ตามกติกา short-SL TP≥7R

Optimization แบบ exact next-open market replay:

- recent winner อยู่ถึง RR10.30 แต่หายที่ RR10.40 จึงเลือก `10.2R`
  เว้นระยะ 0.20R จาก payoff cliff
- BE0.20–0.30 เป็น plateau ร่วมที่ให้ recent +74.51 และ long +100.40
  พร้อม DD ต่ำกว่า long-only optimum BE1.10 จึงเลือก midpoint `0.25R`
- KS1.00–1.15 ยังรักษา cross-window survival; KS1.05 ให้ recent +63.83
  และ long +179.93 พร้อม 3 TP ขณะที่ 1.25 เสีย winner ทั้งหมด จึงเลือก
  `KS_SCALED_MIN=1.05` ซึ่งไม่ชิด KS=1.154701 ของ recent winner
- median shift0.10–0.15MAD ให้ผลดีที่สุดร่วมกัน จึงเลือก midpoint
  `MEDIAN_SHIFT_MAD_MIN=0.125`
- baseline44–56 รักษา recent/long โดย 48 ให้ 3 long TP และผลดีที่สุด;
  recent12–16 รักษา 1/3 TP ก่อน 18 เสีย recent winner จึงคง 48/16
  เพราะ recent16 ลด DD เหลือ 15.13 เทียบ 26.48 ที่ recent12
- release body0.55–0.60 รักษา 3 long TP แต่ 0.625 เสียหนึ่ง winner จึงเลือก
  0.575; range0.80–0.875 เป็น plateau จึงเลือก midpoint 0.8375
- close fraction0.830–0.835 ให้ local plateau สูงสุด แต่ 0.840 ทำ long P&L
  ลดจาก 217.54 เป็น 195.83 จึงเลือก midpoint 0.8325

ผล Backtest มาตรฐานของ optimized default:

| Window | Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน | 9 | 9 | 0 | 0 | 11.11% | +73.73 | +1.21 | +36.87 | 7.09 | 6.08 |
| 6 เดือน | 21 | 21 | 0 | 0 | 14.29% | +217.54 | +1.20 | +36.26 | 9.73 | 10.81 |

Long window มี TP อิสระวันที่ 18 มีนาคม, 6 เมษายน และ 24 มิถุนายน Minimum
actual-fill risk 4.13 และ minimum BE trigger 1.033 มากกว่า spread0.20
Portfolio overlap 6 เดือน: S257=4, S282=7, S290=8, S288=3, S299=3,
S258/S292/S297=1 และ S275/S281/S293/S294/S296/S298/S300=0 จาก 21
timestamps จึงกระจายจาก S300 และ reclaim families ได้ดี แต่ overlap สูงกับ
S290 ตามธรรมชาติของ distribution-drift family; ควรใช้เป็น alternative selector
หรือจำกัด exposure ร่วม ไม่ stack น้ำหนักเต็มพร้อม S290

## S302 — KS Distribution-Break Rejection Fade (SELL 26.3R)

ไฟล์: `strategy302.py`

Edge: ใช้ KS/MAD regime gate แบบ S301 แต่ทดสอบ complementary failure regime:
แท่งปิดต้องเคลื่อนสวน median shift, ปิดควบคุมทิศ reversal และทิ้ง wick ไปทาง
distribution drift เดิม ก่อนเข้า next-open fade ด้วย event-extreme + ATR buffer
stop จึงไม่ใช่ continuation signal ซ้ำ แต่เป็นหลักฐานว่าการเปลี่ยน empirical CDF
ถูก price action ปฏิเสธ

ผล baseline KS1.05/shift0.125/body0.40/range0.80/wick0.18/RR10/BE1
ทั้งสองทิศ:

| Window | Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน | 27 | 27 | 0 | 0 | 3.70% | -0.52 | -0.01 | -0.26 | 0.99 | 58.33 |
| 6 เดือน | 69 | 69 | 0 | 0 | 5.80% | +48.71 | +0.27 | +8.12 | 1.25 | 108.70 |

Combined recent ยังไม่ผ่าน แต่ direction audit พบ SELL-only รอดพร้อมกัน
+32.27/+89.83 ขณะที่ BUY-only ลบ -36.51/-50.68 ใน 2m/6m จึงล็อก
SELL-only และเข้าสู่ optimization

Optimization แบบ exact next-open market replay:

- recent รักษา TP ถึง RR27.0 แต่ long รักษา 3 TP ถึง RR26.4 และลดเหลือ 2
  ที่ 26.5 จึงเลือก `26.3R` เว้นระยะ 0.2R จาก long payoff cliff
- BE0.90–1.00 รักษา 3 long TP และ recent ยังบวกสูง จึงเลือก midpoint
  `0.95R`; ไม่เลือก BE0.30 ที่ลด DD แต่เหลือเพียง 2 long TP
- KS0.95–1.00 รักษา 2 recent/4 long TP ก่อน 1.025 เสีย winner จึงเลือก
  midpoint `KS_SCALED_MIN=0.975`
- median shift0–0.03MAD รักษา 2/4 TP แต่ 0.035 เสียหนึ่ง winner จึงเลือก
  `0.02MAD` เพื่อคง non-zero direction floor และห่าง cliff
- rejection body0.35–0.40 รักษา 2/4 TP ก่อน 0.425 เสีย winner จึงเลือก
  0.375; range0.90–1.10 เป็น plateau ก่อน 1.20 เสีย winner จึงเลือก 1.00
- drift-side wick0.20–0.30 เป็น plateau ก่อน 0.35 เสีย winner จึงเลือก
  midpoint 0.275; close fraction0.55–0.70 ไม่เปลี่ยน winner set จึงเลือก 0.625
- sample audit พบ baseline48 เป็นจุดเดียวใน 40/44/48/52/56 ที่รักษา
  2 recent/4 long TP และ recent16 ดีกว่า 12/14/18/20 ทั้ง breadth/P&L/DD
  จึงคง 48/16 แต่ต้องถือเป็น concentration risk ไม่ใช่ broad parameter plateau

ผล Backtest มาตรฐานของ optimized default:

| Window | Signals | Closed | Expired | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน | 12 | 12 | 0 | 0 | 16.67% | +395.52 | +6.48 | +197.76 | 27.91 | 10.45 |
| 6 เดือน | 24 | 24 | 0 | 0 | 16.67% | +716.91 | +3.96 | +119.49 | 32.58 | 10.45 |

Long window มี TP อิสระวันที่ 12 กุมภาพันธ์, 27 เมษายน, 26 พฤษภาคม และ
5 มิถุนายน Minimum actual-fill risk 3.45 และ minimum BE trigger 3.278
มากกว่า spread0.20 Portfolio overlap 6 เดือน: S281=10, S275/S293/S296=6,
S298=2, S288/S292/S297/S299=1 และ S257/S258/S282/S290/S294/S300/S301=0
จาก 24 timestamps จึงกระจายจาก distribution-continuation family ได้ดี แต่
ซ้ำกับ SELL reclaim/fade cluster สูง และผลไวต่อ sample 48/16 กับ shift cliff
0.035MAD; ต้องจัดเป็น experimental high-R satellite หรือ alternative selector
ไม่ stack exposure เต็มน้ำหนักพร้อม S275/S281/S293/S296
