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

## S303 — Rollover ORB + HTF Bias (10R)

ไฟล์: `strategy303.py`

Edge: ใช้ first break ของ anchored opening range ช่วง 04:00–06:00 BKK และรับเฉพาะ
ทิศที่ราคาปิดอยู่ถูกฝั่งของ SMA 96 แท่ง M5 เพื่อตัด counter-trend rollover break
ออกจาก S224 ผลระยะยาวดีขึ้นด้าน risk-adjusted return แต่ช่วง fade ล่าสุดมี sample ต่ำมาก

| Window | Signals | Closed | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน | 1 | 1 | 0 | 0.00% | -0.20 | -0.003 | -0.10 | 0.00 | 0.20 |
| 2026-H1 | 12 | 12 | 0 | 33.33% | +277.58 | +1.53 | +46.26 | 18.29 | 10.32 |
| 2025-H2 WF | 31 | 31 | 0 | 9.68% | +36.14 | +0.20 | +6.02 | 1.88 | 13.66 |

## S304 — Rolling Rollover Drive + HTF Bias (10R)

ไฟล์: `strategy304.py`

Edge: ทดสอบ HTF bias เดียวกับ S303 บน rolling micro-range break ของ S206
แทน anchored range ผลยืนยันว่า HTF bias ช่วย rollover edge ได้มากกว่าหนึ่งโครงสร้าง
แต่ 2 เดือนล่าสุดเป็น fade regime และไม่มี TP เลย

| Window | Signals | Closed | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน | 9 | 8 | 0 | 0.00% | -10.43 | -0.17 | -5.22 | 0.00 | 10.43 |
| 2026-H1 | 31 | 31 | 0 | 19.35% | +420.09 | +2.32 | +70.02 | 8.74 | 20.22 |
| 2025-H2 WF | 38 | 38 | 0 | 13.16% | +106.12 | +0.58 | +17.69 | 2.76 | 26.94 |

## S305 — Rollover Drive + HTF + Robust Participation (10R)

ไฟล์: `strategy305.py`

Edge: เป็น one-variable ablation ของ S304 โดยกำหนดให้ tick volume ของ breakout bar
ไม่น้อยกว่า 0.90 เท่าของ median volume ใน rolling range 8 แท่งก่อนหน้า Median ลดผลกระทบ
จาก quote-volume spike เพียงแท่งเดียว และกรอง unusually quiet break ที่มีโอกาส fade สูง

ผล Backtest มาตรฐาน M5, spread 0.20, lot 0.01, next-bar market fill และ conservative
SL-first:

| Window | Signals | Closed | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน | 6 | 5 | 0 | 0.00% | -4.21 | -0.07 | -2.11 | 0.00 | 4.21 |
| 2026-H1 | 21 | 20 | 0 | 25.00% | +353.64 | +1.95 | +58.94 | 10.32 | 13.60 |
| 2025-H2 WF | 22 | 22 | 0 | 18.18% | +95.87 | +0.52 | +15.98 | 4.53 | 12.72 |

สรุป: participation gate ลด loss/DD ของ recent regime เทียบ S304 แต่ยังไม่ผ่านเกณฑ์
survivor เพราะ 2 เดือนล่าสุดไม่มีผู้ชนะ จึงยังไม่ควร register เข้า live portfolio และไม่ควร
หยุดสร้าง strategy ID เพื่อ optimize ตัวนี้

## S306 — Controlled Rollover Participation (10R)

ไฟล์: `strategy306.py`

Edge: เพิ่มเพียงเพดาน body/high-low 0.90 บน S305 เพื่อกันแท่ง breakout แบบเกือบไม่มี wick
ซึ่ง feature audit พบว่า non-winner มี median body fraction สูงกว่า TP ทั้ง 2026-H1 และ WF

| Window | Signals | Closed | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน | 5 | 4 | 0 | 0.00% | -4.01 | -0.07 | -2.01 | 0.00 | 4.01 |
| 2026-H1 | 19 | 18 | 0 | 27.78% | +354.04 | +1.96 | +59.01 | 10.43 | 13.20 |
| 2025-H2 WF | 15 | 15 | 0 | 20.00% | +65.00 | +0.35 | +10.83 | 6.30 | 4.73 |

ข้อสรุป: ลด WF drawdown ได้มากแต่ recent SL หลักมี body fraction เพียง 0.83 จึงไม่ใช่
climax และ 2 เดือนยังไม่มี TP ไม่ผ่าน survivor gate

## S307 — Rollover Momentum Run + HTF Bias (10R)

ไฟล์: `strategy307.py`

Edge: นำ HTF SMA bias ที่ช่วย S303/S304 ไปทดสอบกับ expanding three-bar run ของ S221
ซึ่งเป็น trigger คนละ geometry และเคยบวกสอง half-year แต่ DD สูง

| Window | Signals | Closed | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน | 5 | 5 | 0 | 20.00% | +46.70 | +0.77 | +23.35 | 14.58 | 3.24 |
| 2026-H1 | 14 | 14 | 0 | 14.29% | +74.98 | +0.41 | +12.50 | 2.85 | 33.93 |
| 2025-H2 WF | 14 | 13 | 1 | 7.69% | -2.18 | -0.01 | -0.36 | 0.94 | 29.90 |

Bias-horizon audit 48/72/96/144/288 แท่งยังให้ WF ใกล้ -2 และ DD ~30 ทั้งหมด จึงเป็น
mechanism failure ไม่ใช่ parameter miss และ market-gap ทำให้ invalid 1 ครั้ง

## S308 — Counter-Bias Rollover Repricing Run (10R)

ไฟล์: `strategy308.py`

Edge: ทดสอบ causal complement ของ S307 โดยยังตาม expanding run แต่รับเฉพาะ run ที่สวน
SMA reference เดิม เพื่อจับ fresh repricing แทน trend chasing

| Window | Signals | Closed | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน | 3 | 3 | 0 | 0.00% | -20.44 | -0.34 | -10.22 | 0.00 | 20.44 |
| 2026-H1 | 7 | 7 | 0 | 14.29% | +5.88 | +0.03 | +0.98 | 1.20 | 20.44 |
| 2025-H2 WF | 9 | 8 | 1 | 25.00% | +125.75 | +0.68 | +20.96 | 12.62 | 7.84 |

S307/S308 แยก epoch ชัด แต่ไม่มีตัวใดรอดทั้ง recent และ WF

## S309 — Regime-Routed Rollover Run (10R)

ไฟล์: `strategy309.py`

Edge: ใช้ continuation-rate แบบ causal ของ S218 เลือก S307 ใน fade regime, S308 ใน drive
regime และงดช่วง 0.50–0.55 ใช้ lookback 700 แท่งเพราะ estimator ต้องการ 600 แท่ง

| Window | Signals | Closed | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน | 2 | 2 | 0 | 0.00% | -10.88 | -0.18 | -5.44 | 0.00 | 10.88 |
| 2026-H1 | 7 | 7 | 0 | 14.29% | +13.90 | +0.08 | +2.32 | 1.66 | 10.88 |
| 2025-H2 WF | 9 | 8 | 1 | 25.00% | +126.53 | +0.69 | +21.09 | 13.60 | 6.66 |

## S310 — Binary Regime-Routed Rollover Run (10R)

ไฟล์: `strategy310.py`

Edge: ถอด abstention band ของ S309 แล้ว route ทุก regime ที่ threshold 0.55 เพื่อทดสอบว่า
การงดช่วงกำกวมเป็นสาเหตุที่ทำ recent TP หายหรือไม่

| Window | Signals | Closed | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน | 4 | 4 | 0 | 0.00% | -11.28 | -0.18 | -5.64 | 0.00 | 11.28 |
| 2026-H1 | 11 | 11 | 0 | 9.09% | +4.01 | +0.02 | +0.67 | 1.13 | 19.54 |
| 2025-H2 WF | 13 | 12 | 1 | 16.67% | +105.63 | +0.57 | +17.61 | 4.41 | 27.56 |

ข้อสรุป S309–S310: continuation-rate อธิบาย rollover family ใน aggregate แต่ไม่ทำนายว่า
momentum run รายเหตุการณ์ควร aligned หรือ counter-bias; ห้ามวน optimize threshold router นี้ซ้ำ

## S311 — Cramér–von Mises Distribution-Shift Release (SELL 10.1R)

ไฟล์: `strategy311.py`

Edge: ใช้ two-sample Cramér–von Mises statistic วัดพื้นที่ squared ECDF separation
ตลอด pooled ranks ระหว่าง baseline 48 และ recent 16 closed log returns จึงต่างจาก KS ที่ดู
ระยะห่างสูงสุดจุดเดียว, Anderson–Darling ที่เน้นหาง และ Wasserstein ที่วัดระยะในหน่วย return
จากนั้นใช้ median shift/MAD กำหนดทิศและ closed release candle ยืนยัน regime ใหม่

Baseline ทั้ง BUY/SELL, CvM0.30, RR10/BE1:

| Window | Signals | Closed | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน | 19 | 19 | 0 | 10.53% | +97.75 | +1.60 | +48.88 | 2.34 | 36.12 |
| 2026-H1 | 41 | 41 | 0 | 12.20% | +196.49 | +1.09 | +32.75 | 2.21 | 76.11 |
| 2025-H2 WF | 43 | 43 | 0 | 6.98% | +75.13 | +0.41 | +12.52 | 2.16 | 53.61 |

เนื่องจากบวกครบสามหน้าต่างที่ RR10 จึงหยุดสร้าง ID ใหม่และเข้าสู่ optimization ตาม survivor gate

Optimization แบบ exact next-open replay:

- Direction audit: SELL-only ยังบวก +44.41/+162.44/+68.07 ใน 2m/6m/WF และลด long DD
  จาก 74.95 ของ BUY เหลือ 34.11 จึงปิด BUY
- `CVM_MIN`: 0.275–0.300 เป็น cross-window plateau; 0.20 ปล่อย noise จน WF เหลือ +8.06
  DD63.99 และ 0.40 เสีย TP ทุกตัว จึงเลือก midpoint 0.2875
- `MEDIAN_SHIFT_MAD_MIN`: 0.20–0.25 ให้ผลเหมือนกันทุกหน้าต่าง; winner อ่อนที่สุดอยู่ที่
  0.310MAD จึงเลือก midpoint 0.225
- BE0.20–0.30 เป็น plateau ต่ำ-DD ร่วมกัน เลือก 0.25; BE0.30 ทำ WF DD เพิ่มจาก 15.10
  เป็น 23.51
- Recent TP อยู่รอดถึง 10.3R และหายที่ 10.4R ขณะที่ WF อยู่ถึง 12R และ 6m เกิน 30R
  จึงเลือก 10.1R เว้น 0.2R จาก recent payoff cliff
- Shape sweep 100 ชุด (`body × range × close-location`) มี 60 ชุดที่บวกครบทุก window;
  เพิ่ม `RELEASE_RANGE_ATR_MIN` จาก 0.8375 เป็น 1.00 ตัด loss ออกโดยไม่เสีย TP ล่าสุด
  ทำให้ 12m net เพิ่ม +1.00, DD ลดจาก 13.24 เป็น 12.64 และ return/DD เพิ่ม
  21.66 → 22.76 ส่วน body=0.70 แม้ ratio สูงกว่าแต่ตัด winner 2026-H1 จึงไม่เลือก

Robustness audit ของ return windows:

- `RECENT_RETURNS=14` และ `18` ไม่มี TP ในช่วงล่าสุด ขณะที่ 16 มี TP; baseline 44/48/52
  ยังบวกแต่ผลเปลี่ยนมาก แสดงว่า single-window มี parameter concentration ที่ต้องระวัง
- ทดสอบ multi-window median CvM พร้อมบังคับทิศทางตรงกันทุก window แล้ว:
  `(14,16,18)` บวกครบที่ threshold 0.20–0.25 แต่ค่าที่ดีที่สุดยังได้เพียง
  +133.34/DD21.82 ใน 2026-H1 และ +83.85/DD13.44 ใน WF
  เทียบ default +196.81/DD8.46 และ +90.91/DD12.64
- `(13,16,19)` ที่ threshold 0.25 ได้ +76.74/+139.57/+87.98 ใน 2m/6m/WF
  แต่ 12m net +227.55 ยังต่ำกว่า default +287.72 และ DD สูงกว่า
- ensemble กว้าง `(12,16,20)` ต้องลด threshold ต่ำกว่า 0.195 เพื่อเก็บ TP ล่าสุด
  และทำให้ 2026-H1 DD สูงถึง 35.17–41.52; ที่ 0.195 TP ล่าสุดหายทันที
  จึงเป็น payoff cliff ไม่ใช่ robust plateau

สรุป: ensemble ช่วยยืนยันว่าทิศ SELL ของ winner ไม่ได้กลับข้างเมื่อเปลี่ยน window
แต่ไม่ชนะ single-window ด้าน net/DD จึงเก็บเป็น optional research control และไม่เปิดเป็น default

ผล official optimized default:

| Window | Signals | Closed | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน | 10 | 10 | 0 | 10.00% | +70.91 | +1.16 | +35.46 | 6.03 | 8.06 |
| 2026-H1 | 16 | 16 | 0 | 18.75% | +196.81 | +1.09 | +32.80 | 10.13 | 8.46 |
| 2025-H2 WF | 19 | 19 | 0 | 5.26% | +90.91 | +0.49 | +15.15 | 7.87 | 12.64 |
| รวม 12 เดือน | 35 | 35 | 0 | 11.43% | +287.72 | +0.79 | +23.98 | 9.27 | 12.64 |

Combined return/DD = 22.76. Retest 2 เดือนถึง `2026-07-29` ยังบวก +67.93, WR9.09%,
DD9.21. Spread sensitivity จาก market execution: ที่ spread0.50 net จะเหลือประมาณ
+67.91/+192.01/+85.21 ใน 2m/6m/WF จึงไม่พึ่ง spread0.20 แบบเปราะบาง

Portfolio overlap 2026-H1: S301=14/18 timestamps จึงต้องใช้เป็น alternative selector
ไม่ stack เต็มน้ำหนักพร้อมกัน; S302/S303/S304=0 overlap จึงกระจายจาก KS-rejection และ
rollover family ได้ดี

## S312 — Energy-Distance Distribution Break (SELL 10.1R)

ไฟล์: `strategy312.py`

Edge: วัด two-sample energy distance จาก absolute distance ทุกคู่ระหว่าง baseline/recent
closed log returns ลบด้วย within-sample distances แล้ว normalize ด้วย pooled MAD จึงตรวจ
location/scale/shape break ได้พร้อมกันโดยไม่ใช้ bins หรือ Gaussian assumption ต่างจาก
S311 CvM ที่ integrate squared ECDF rank separation จากนั้นใช้ median shift/MAD ระบุทิศ
และ closed release candle ยืนยัน ก่อนเข้า market ที่ next-bar open; SL อยู่พ้น release
extreme + 0.08ATR และ TP ไม่ต่ำกว่า 7R

ผล baseline ทั้ง BUY/SELL, Energy0.20, body0.575/range1.0/close0.8325,
RR10/BE0.25:

| Window | Signals | Closed | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน | 29 | 29 | 0 | 6.90% | +111.26 | +1.82 | +55.63 | 2.87 | 28.95 |
| 2026-H1 | 67 | 67 | 0 | 5.97% | +153.75 | +0.85 | +25.63 | 2.03 | 48.23 |
| 2025-H2 WF | 63 | 63 | 0 | 4.76% | +135.09 | +0.73 | +22.52 | 3.91 | 32.40 |

ผ่าน survivor gate ที่ 10R ครบสามช่วง จึงหยุดสร้าง S313 และ optimize S312:

- Direction audit: BUY ที่ Energy0.20 ขาดทุน -22.81 ใน 2026-H1 ขณะที่ SELL ได้
  +58.74/+176.56/+127.10 ใน 2m/H1/WF จึงปิด BUY
- Energy threshold 0.22–0.235 รักษา SELL winner ครบ; 0.24 ทำ WF เสียหนึ่ง TP และ
  0.30 ทำ recent SELL ไม่มี TP จึงเลือก midpoint `0.225` โดย winner floor=0.235574
- Payoff sweep RR7–20 และ BE0.15–1.00 ตามด้วย local sweep พบ RR9.75–10.35
  รักษา TP ครบ แต่ 10.40 ไม่ viable ครบ window จึงเลือก `TP_RR=10.1`
  เว้น 0.30R จาก cliff
- BE0.05–0.10 ให้ผล identical ทั้งสาม window และลด WF DD จาก 12.04 ที่ BE0.20–0.25
  เหลือ 7.06 จึงเลือก midpoint `BE_RR=0.075`
- Shape sweep 60 ชุดและ local 120 ชุดพบ plateau body0.775–0.80,
  range0.70–0.90, close0.8325 จึงใช้ midpoint body0.7875/range0.80
  ลด worst-window DD จาก 18.78 เป็น 12.07 โดยกำไรรวมลดเพียงประมาณ 2.7%

ผล official optimized default:

| Window | Signals | Closed | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน | 12 | 12 | 0 | 8.33% | +76.14 | +1.25 | +38.07 | 9.59 | 8.06 |
| 2026-H1 | 20 | 20 | 0 | 10.00% | +179.90 | +0.99 | +29.98 | 18.53 | 9.06 |
| 2025-H2 WF | 19 | 19 | 0 | 10.53% | +139.76 | +0.76 | +23.29 | 10.40 | 12.07 |
| รวม 12 เดือน | 39 | 39 | 0 | 10.26% | +319.66 | +0.87 | +26.64 | 13.72 | 12.07 |

Combined return/DD = 26.48. Risk distance ของ 39 trades อยู่ที่ 1.63–14.53 USD,
median 6.03 USD สำหรับ 0.01 lot. Retest 2 เดือนถึง `2026-07-29` ยังบวก +73.16,
WR7.69%, PF7.18, DD7.86. ที่ spread0.50 net โดยประมาณยังเป็น
+72.54/+173.90/+134.06 ใน 2m/H1/WF

Robustness caveat:

- baseline 44/48/52 เสถียร: recent net ประมาณ +75.74/+76.14/+76.34 และ H1
  +179.30/+179.90/+179.90
- recent window ยัง concentrated: 14 และ 18 ไม่มี recent TP; recent18 ทำ WF -8.81
- ensemble `(14,16,18)`, Energy0.20 รักษากำไร +75.54/+172.29/+136.57 แต่ H1 DD
  เพิ่มเป็น 16.67 เทียบ default 9.06 จึงเก็บเป็น optional research mode ไม่เปิด default

Portfolio overlap 2026-H1: ซ้ำ S311 และ S301 อย่างละ 12 จาก 20 timestamps
จึงไม่ควร stack เต็ม risk พร้อมกัน แต่มี 8 timestamps ใหม่; overlap กับ S302/S303/S304
เป็นศูนย์ จึงยังเพิ่ม diversification จาก KS-rejection และ rollover family ได้

## S313 — Kendall Volume–Volatility Coupling Release (SELL 12.1R)

ไฟล์: `strategy313.py`

Edge: ใช้ Kendall tau-b แบบ non-parametric วัด rank concordance ระหว่าง absolute
closed-bar log return กับ tick volume แยก baseline 48 และ recent 16 แท่ง หาก recent
coupling สูงขึ้น แปลว่าการขยายตัวของราคาเกิดพร้อม participation แทน thin-liquidity noise
จากนั้นใช้ directional path efficiency และแท่ง release ที่ปิดแล้วกำหนดทิศ เข้า market
ที่ next-bar open และวาง SL พ้น release extreme + 0.08ATR จึงเป็น cross-domain dependency
shift ที่ต่างจาก S311/S312 ซึ่งเปรียบเทียบ distribution ของ return เพียงตัวแปรเดียว

ค่าเริ่มต้นเดิมที่ tau/jump0.24, efficiency0.34, body0.70 มีเพียง 1 BE และ Net -0.20
ใน 2 เดือน จึงทำ coarse sensitivity 6 ชุด พบ profitable region ที่ tau0.10–0.20,
jump0.20, efficiency0.20 และ body0.45 ชุด tau0.10 ให้ 14 trades, WR14.29%,
Net +102.05, PF6.43, DD17.98 ที่ 8R จึงผ่าน survivor gate และหยุดสร้าง S314
เพื่อ optimize S313

Optimization ที่ยืนยันแล้ว:

- Direction audit: SELL-only บวก +70.42/+153.93/+73.58 ใน 2m/6m/WF ที่ 8R
  และลด DD เหลือ 4.11/15.81/5.02; BUY เป็นลบ -11.91 ใน WF จึงปิด BUY
- RR9, RR10 และ RR12 รักษา SELL winner ครบทุก window และเพิ่ม net โดย DD ไม่เพิ่ม
- WF winner อ่อนที่สุดมี MFE ประมาณ 12.40R; RR13 ทำให้ winner หายและ WF กลับเป็น
  -9.07 จึงเลือก 12.1R เว้น excursion margin 0.30R จาก payoff cliff
- BE0.05/0.075/0.10/0.20: 0.05 ทำ 2026-H1 +268.30/DD7.40 เทียบ
  +259.46/DD15.81, +251.27/DD15.81 และ +243.96/DD22.90 ตามลำดับ โดย 2m/WF
  ไม่เปลี่ยน จึงเลือก 0.05
- Local tau audit: tau0.10–0.15 identical และ tau0.20 ยังบวกครบ; jump0.25–0.35
  เก็บ TP ครบทุก window. Winner jump floor=0.3657 และ SL เดียวอยู่ที่ 0.3307
  จึงเลือก jump0.335 ซึ่งตัด SL แต่ยังมี margin0.0307 ใต้ winner floor
- Geometry audit: SL มี body0.6687ATR ขณะที่ TP floor=0.8381ATR; body0.70–0.80
  เป็น plateau ที่เก็บ TP ครบ จึงเลือก midpoint0.75 และลด noise โดยไม่แตะ winner
- Baseline44/48/52 รักษา TP ครบและบวกทุกช่วง แสดงว่า baseline ไม่ concentrated
- Recent window ยัง concentrated: recent14 ไม่มี TP ใน WF และ recent18 เสียหนึ่ง TP
  ใน H1 แม้ recent18 ยังบวกครบ; จึงคง recent16 แต่ต้องถือเป็น robustness caveat
- Risk distance ของ official 12 เดือนอยู่ที่ 2.72–14.44 USD, median 9.18 USD
  สำหรับ 0.01 lot

ผล official optimized default (SELL-only, RR12.1, BE0.05, jump0.335, body0.75):

| Window | Signals | Closed | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน | 3 | 3 | 0 | 33.33% | +113.03 | +1.85 | +56.52 | 283.58 | 0.20 |
| 2026-H1 | 6 | 6 | 0 | 33.33% | +285.98 | +1.58 | +47.66 | 358.47 | 0.40 |
| 2025-H2 WF | 3 | 3 | 0 | 33.33% | +124.41 | +0.68 | +20.74 | 312.03 | 0.40 |
| รวม 12 เดือน | 9 | 9 | 0 | 33.33% | +410.39 | +1.12 | +34.20 | 342.99 | 0.40 |

Combined return/DD = 1,025.98 แต่ sample เหลือเพียง 9 trades จึงต้องตีความ PF/DD
อย่างระมัดระวัง ไม่ใช่หลักฐานว่าความเสี่ยงจริงเกือบศูนย์. Retest 2 เดือนถึง
`2026-07-29` ยังได้ 2 trades, WR50%, Net +113.23, DD0.20. Market-spread
sensitivity ที่ spread0.50 หักเพิ่มตรงตามจำนวนไม้ เหลือประมาณ
+112.13/+284.18/+123.51 ใน 2m/H1/WF

Portfolio overlap 2026-H1 ต่ำ: ซ้ำ S301/S311/S312 เพียงกลยุทธ์ละ 1 จาก 6 timestamps
และเป็นเวลาเดียวกัน (`2026-05-25 20:10 BKK`) จึงเพิ่ม diversification ได้ดีกว่า
S311/S312 ที่ overlap กันสูง. ขยาย session จาก 17–21 เป็น 16–22 BKK แล้วยังได้
+113.03/+285.98/+124.21 ใน 2m/H1/WF (เพิ่มเพียง 1 BE ใน WF) จึงไม่ได้พึ่ง
session boundary แบบเปราะบาง

ทดลอง optional majority ensemble recent `(14,16,18)`, agree≥2 แล้ว:

- 2m: +113.03, WR33.33%, DD0.20 — เท่า default
- H1: +112.43, WR16.67%, DD0.80 — เสีย TP หนึ่งตัวจาก default +285.98
- WF: +124.21, WR25.00%, DD0.60 — ใกล้ default +124.41

ensemble ยืนยันทิศและช่วยเป็น research control แต่ไม่ชนะ default ด้าน cross-window net
จึงเก็บเป็น optional config ไม่เปิดค่าเริ่มต้น. หลัง direction/payoff/BE/threshold/shape/
window/session/spread/portfolio audits ยังไม่พบทางเพิ่ม robustness โดยไม่เสีย H1 winner
จึงถือว่า S313 จบรอบ optimization นี้และกลับไปสร้าง S314 ต่อ

## S314 — Renewal-Drought Participation Shock Breakout 8R

ไฟล์: `strategy314.py`

Edge hypothesis: มอง range+volume expansion candles เป็น arrivals ของ renewal process
โดยทุก historical event ใช้ ATR และ rolling median volume ที่มีอยู่ก่อนแท่งนั้นเท่านั้น
จากนั้นสร้าง empirical waiting-time distribution และเข้าเฉพาะ structural breakout shock
แรกหลัง gap ที่ยาวกว่าค่า quantile ของอดีต จึงต่างจาก distribution/coupling family
S311–S313 และไม่มี look-ahead

ผล baseline ทั้ง BUY/SELL, M5, spread0.20, lot0.01, TP8R:

| Window | Signals | Closed | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน | 67 | 67 | 0 | 1.49% | +35.01 | +0.57 | +17.51 | 1.58 | 45.47 |

Direction audit ใน 2m: BUY 33 ไม้ Net -26.06, SELL 34 ไม้ Net +61.07 จึงทำ
SELL-only validation โดย replay ใหม่ ไม่ได้กรอง CSV:

| Window | Signals | Closed | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน | 35 | 35 | 2.86% | +60.87 | +1.00 | +30.44 | 2.75 | 23.01 |
| 2026-H1 | 93 | 93 | 4.30% | +176.27 | +0.97 | +29.38 | 3.26 | 41.63 |
| 2025-H2 WF | 81 | 81 | 3.70% | -13.57 | -0.07 | -2.26 | 0.81 | 39.80 |

แม้ recent มี TP8R จริง แต่ WF ติดลบและ return/DD ต่ำ จึงไม่ผ่าน portfolio-survival
gate. ไม่ Optimize ต่อจาก winner ช่วงล่าสุดเพื่อลดความเสี่ยง overfit และเดินหน้า S315

## S315 — Signed-Volume to Return Transfer-Entropy Release 8R

ไฟล์: `strategy315.py`

Edge hypothesis: ประมาณ empirical transfer entropy จาก signed-volume state ไปยัง
next-return state โดย condition บน prior return แล้วใช้ conditional context ทำนายทิศ
แท่ง release ที่ต้องปิดทะลุโครงสร้าง จึงวัด directional information flow ตามเวลา
ต่างจาก ordinary mutual information/correlation. ตัว estimator fit จาก bars ก่อนแท่ง
signal เท่านั้นและเข้า market ที่ next-open

ผล Backtest มาตรฐาน 2 เดือน, M5, spread0.20, lot0.01, TP8R:

| Signals | Closed | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 49 | 49 | 0 | 2.04% | -36.76 | -0.60 | -18.38 | 0.51 | 42.31 |

Direction decomposition: BUY 25 ไม้มี 1 TP แต่ Net -3.07; SELL 24 ไม้ไม่มี TPและ
Net -33.69. ทั้ง baseline และแต่ละฝั่งไม่ผ่าน survival gate จึงไม่ tune threshold
ย้อนหลังเข้าหา BUY winner เพียงไม้เดียว และเดินหน้า S316

## S316 — Permutation-Entropy Compression Release 8R

ไฟล์: `strategy316.py`

Edge hypothesis: วัด normalized Shannon entropy ของ distribution ของ ordinal
return patterns order3 ใน baseline54 เทียบ recent18 แบบ non-overlap แล้วตาม structural
breakout เมื่อ entropy ลดลงและ recent path มีทิศ/efficiency ชัดเจน ต่างจาก S263
ที่ประมาณ posterior ของ pattern เดียว และ S280 ที่ใช้ Lempel–Ziv phrase count

ผล Backtest มาตรฐาน 2 เดือน, M5, spread0.20, lot0.01, TP8R:

| Signals | Closed | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 25 | 25 | 0 | 0.00% | -35.24 | -0.58 | -17.62 | 0.00 | 35.24 |

ไม่มี TP ทั้งสองทิศ จึงไม่ผ่าน survival gate และไม่ผ่อน entropy threshold เพื่อสร้าง
sample ย้อนหลัง เดินหน้า S317

## S317 — Theil–Sen Robust Slope-Acceleration Release 8R

ไฟล์: `strategy317.py`

Edge hypothesis: ใช้ median ของ pairwise slopes เป็น robust trend estimate แยก
baseline36/recent14 แบบ non-overlap แล้วรับ structural release เมื่อ recent slope
เร่งจาก baseline พร้อม directional efficiency จึงลดอิทธิพล shock candle ต่อ slope
เมื่อเทียบ OLS

ผล baseline 2 เดือน:

| Signals | Closed | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 96 | 96 | 0 | 3.13% | +39.95 | +0.65 | +19.98 | 1.58 | 47.37 |

Direction decomposition พบ BUY +40.37 และ SELL -0.42 จึง replay BUY-only:

| Window | Signals | Closed | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน | 48 | 48 | 4.17% | +40.37 | +0.66 | +20.19 | 1.98 | 28.34 |
| 2026-H1 | 168 | 168 | 4.76% | +245.82 | +1.36 | +40.97 | 2.20 | 106.74 |
| 2025-H2 WF | 240 | 240 | 3.33% | -0.64 | -0.00 | -0.11 | 1.00 | 133.95 |

WF ไม่ทำกำไรและ DD สูงกว่า recent net มาก จึงไม่ผ่าน portfolio-survival gate
ไม่ Optimize ต่อ และเดินหน้า S318

## S318 — Corwin–Schultz Implied-Spread Compression Release 8R

ไฟล์: `strategy318.py`

Edge hypothesis: ใช้ Corwin–Schultz two-bar high/low estimator แยก implied
effective-spread component จาก range volatility แล้วรับ efficient structural breakout
เมื่อ recent median spread ต่ำกว่า baseline แบบ non-overlap จึงเป็น microstructure
liquidity-cost signal ไม่ใช่ ATR/RS/Parkinson compression หรือ Amihud impact

ผล Backtest มาตรฐาน 2 เดือน, M5, spread0.20, lot0.01, TP8R:

| Signals | Closed | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 39 | 39 | 0 | 5.13% | +13.16 | +0.22 | +6.58 | 1.25 | 51.11 |

Direction decomposition: BUY 19 ไม้ Net +14.29 แต่ DDประมาณ23.35; SELL 20 ไม้
Net -1.13. Baseline และ BUY มี return/DD ต่ำกว่า1 จึงไม่ถือว่าพอร์ตอยู่รอด
 ไม่ Optimize จาก TP สองไม้ และเดินหน้า S319

## S319 — Higuchi Fractal-Dimension Collapse Release 8R

ไฟล์: `strategy319.py`

Edge hypothesis: ประมาณ Higuchi fractal dimension ของ close path หลาย sampling
scales แยก baseline64/recent32 แล้วตาม structural breakout เมื่อ recent dimension
ลดลงและ path efficiency สูงขึ้น จึงเป็น geometric roughness regime ไม่ใช่ entropy
count, distribution distance หรือ linear slope

ผล Backtest มาตรฐาน 2 เดือน, M5, spread0.20, lot0.01, TP8R:

| Signals | Closed | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 23 | 23 | 0 | 0.00% | -22.86 | -0.37 | -11.43 | 0.00 | 22.86 |

ไม่มี TP จึงไม่ผ่าน survival gate และไม่ผ่อน fractal threshold ย้อนหลัง เดินหน้า S320

## S320 — Spectral-Entropy Compression Release 8R

ไฟล์: `strategy320.py`

Edge hypothesis: คำนวณ normalized Shannon entropy ของ exact return periodogram
แยก baseline64/recent32 แล้วตาม structural breakout เมื่อพลังงานเปลี่ยนจาก broadband
noise ไปกระจุกในไม่กี่ความถี่พร้อม directional path ต่างจาก permutation entropy
ใน ordinal-state domain และ Higuchi geometric roughness

ผล Backtest มาตรฐาน 2 เดือน, M5, spread0.20, lot0.01, TP8R:

| Signals | Closed | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 18 | 18 | 0 | 0.00% | -26.09 | -0.43 | -13.05 | 0.00 | 26.09 |

ไม่มี TP และไม่ผ่าน survival gate จึงไม่ tune entropy threshold ย้อนหลัง เดินหน้า S321

## S321 — BDS-Style Nonlinear-Dependence Release 8R

ไฟล์: `strategy321.py`

Edge hypothesis: เปรียบเทียบ correlation integral excess
`C2(epsilon) - C1(epsilon)^2` ของ robust-standardized returns ระหว่าง baseline64
และ recent32 เพื่อหา nonlinear serial dependence ที่ ordinary autocorrelation
อาจมองไม่เห็น แล้วรอ directional structural release

ผล Backtest มาตรฐาน 2 เดือน, M5, spread0.20, lot0.01, TP8R:

| Signals | Closed | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | 0 | 0 | — | 0.00 | 0.00 | 0.00 | — | 0.00 |

BDS shift + path + breakout chronology ซ้อนกันจนไม่มี sample จึงไม่ผ่อน threshold
เพื่อบังคับ trade และเดินหน้า S322

## S322 — Distance-Correlation Volume Coupling Release (10.7R)

ไฟล์: `strategy322.py`

Edge: ใช้ distance correlation จาก double-centered pairwise distance matrices
ตรวจ arbitrary nonlinear dependence ระหว่าง absolute closed returns กับ tick volume
แยก baseline48/recent18 แบบ non-overlap จึงต่อยอด S313 volume-volatility coupling
แต่ไม่จำกัดความสัมพันธ์ให้เป็น monotonic rank concordance แบบ Kendall. Direction มาจาก
recent path และต้องมี strong closed release; เข้า market ที่ next-open พร้อม SL
พ้น release extreme +0.08ATR

Baseline dCor0.42/jump0.12, both sides, RR10/BE0.05:

| Window | Signals | Closed | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน | 19 | 19 | 0 | 15.79% | +188.64 | +3.09 | +94.32 | 6.80 | 18.98 |
| 2026-H1 | 51 | 51 | 0 | 7.84% | +281.02 | +1.55 | +46.84 | 4.37 | 33.95 |
| 2025-H2 WF | 64 | 64 | 0 | 3.13% | +100.46 | +0.55 | +16.74 | 3.93 | 15.85 |

BUY และ SELL เป็นบวกครบทุกหน้าต่าง จึงหยุด S323 และเข้าสู่ optimization:

- RR12 เพิ่ม recent/H1 แต่ทำให้ WF BUY winner หาย; MFE ของ winner อ่อนสุดประมาณ
  10.97R จึงเลือก 10.7R เว้น margin0.27R
- Winner floors: recent dCor0.5100 และ jump0.2131. เลือก gates0.46/0.18
  เว้น margin0.05/0.033 และลด noise โดยรักษา TP ทุกตัว
- geometry ไม่แยก loss ชัด: body winner floor0.7522ATR อยู่ใกล้ default0.75,
  จึงไม่ยก body เพื่อหลีกเลี่ยง payoff cliff
- BE0.025/0.05 ให้ recent/H1 เหมือนกันและ 0.025 เพิ่ม WF เพียง +4.09 แต่ trigger
  ขั้นต่ำต่ำกว่า spread จึงคง0.05 เพื่อ execution realism; BE0.075–0.10 ลด H1/WF
- baseline44/48/52 รักษา TP ครบและผลใกล้กัน. recent14/16/18 บวกทุก window;
  recent18 เพิ่ม H1/WF net และลด DD พร้อมเก็บ current TP ครบ จึงเปลี่ยน defaultเป็น18
- ปรับสูตร dCor ให้คำนวณ centered-distance inner products จาก row sums โดยตรง
  numerical difference <1e-12 แต่ลด 2m replay จากหลายนาทีเหลือประมาณ9วินาที

ผล official optimized default:

| Window | Signals | Closed | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน | 14 | 14 | 0 | 21.43% | +221.19 | +3.63 | +110.60 | 15.27 | 11.17 |
| 2026-H1 | 24 | 24 | 0 | 16.67% | +357.54 | +1.98 | +59.59 | 12.03 | 15.71 |
| 2025-H2 WF | 42 | 42 | 0 | 4.76% | +126.50 | +0.69 | +21.08 | 8.16 | 11.18 |
| รวม 12 เดือน | 66 | 66 | 0 | 9.09% | +484.04 | +1.33 | +40.34 | 10.67 | 26.89 |

Risk distance 12 เดือนอยู่ที่ 1.41–15.11 USD, median4.81 USD สำหรับ 0.01 lot.
Combined return/DD=18.00. Retest 2 เดือนถึง `2026-07-29` ยังบวก +128.68,
WR16.67%, PF9.41, DD11.17. ที่ spread0.50 net โดยประมาณยังเป็น
+216.99/+350.34/+113.90 ใน 2m/H1/WF

Portfolio overlap 2026-H1: S301/S311/S312 อย่างละ2 จาก24 timestamps และ S313
4 จาก24 จึงต่างจาก Kendall survivor ส่วนใหญ่และเพิ่ม diversification ได้.
Session sensitivity 16–22 BKK ยังบวก +208.25/+319.84/+150.39 ใน 2m/H1/WF
จึงไม่พึ่ง boundary เดิม แต่ default17–21 มี combined net/DD ดีกว่าและถูกคงไว้
หลัง payoff/threshold/shape/BE/window/latest/spread/overlap/session audits ไม่พบ
การปรับที่เพิ่ม robustness ต่อโดยไม่เสียจุดอื่น จึงปิดรอบ optimization หลักและไป S323

## S323 — Lead-Lag Volume-Pressure Coupling Release 8R

ไฟล์: `strategy323.py`

Edge hypothesis: วัด distance correlation แบบ lead-lag ระหว่าง signed tick-volume
pressure ของแท่ง `t` กับ closed return ของแท่ง `t+1` โดยแบ่ง baseline/recent
แบบไม่ซ้อนกัน แล้วเข้า next-open เมื่อ coupling เพิ่มขึ้น, signed covariance,
recent path และ release candle ชี้ทิศเดียวกัน กลไกต่างจาก S322 ซึ่งวัด
contemporaneous dependence ระหว่าง absolute return กับ tick volume

Baseline M5, spread0.20, 0.01 lot, 2026-05-20 ถึง 2026-07-20:

| Signals | Closed | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 12 | 12 | 0 | 0.00% | -21.12 | -0.35 | -10.56 | 0.00 | 21.12 |

BUY 3 ดีล Net -4.92 และ SELL 9 ดีล Net -16.20; ทั้งสอง branch ไม่มี TP
(รวม SL3/BE9) จึงไม่มี direction survivor และไม่ทำ threshold/payoff optimization.
ผลชี้ว่า nonlinear lead-lag dependence ที่ประเมินจาก tick-volume pressure ไม่ได้
แปลเป็น continuation ระยะ 8R แม้จะมี coupling shift จึงไป S324

## S324 — Empirical Volume–Return Upper-Tail Dependence Release 8R

ไฟล์: `strategy324.py`

Edge hypothesis: ประเมิน conditional co-exceedance แบบ non-parametric ว่าเมื่อ
tick volume อยู่ upper 30% แล้ว absolute closed return อยู่ upper 30% พร้อมกัน
บ่อยเพียงใด เปรียบ baseline48 กับ recent20 แบบไม่ซ้อนกัน แล้วตาม recent path
เฉพาะ joint-tail price-discovery shift ในช่วง 17:00–21:00 BKK

Baseline M5, spread0.20, 0.01 lot, 2026-05-20 ถึง 2026-07-20:

| Signals | Closed | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 3 | 3 | 0 | 0.00% | -0.60 | -0.01 | -0.30 | 0.00 | 0.60 |

ทั้ง 3 ดีลจบ BE หลังหัก spreadและไม่มี TP จึงยังไม่มีหลักฐานว่า conditional
upper-tail coupling ส่งผ่านไปถึง payoff 8R; ไม่ optimize และไป S325

## S325 — Kendall Volatility-Clustering Release 8R

ไฟล์: `strategy325.py`

Edge: ใช้ Kendall tau-b ระหว่าง `|return_t|` กับ `|return_t+1|` วัด volatility
clustering แบบ rank-robust แล้วเปรียบ baseline48/recent20 ที่ไม่ซ้อนกัน เมื่อ
tau เพิ่มและ recent path มี displacement จึงตาม release candle ช่วง
17:00–21:00 BKK ด้วย release-extreme+0.08ATR stop และ TP8R

Baseline M5, spread0.20, 0.01 lot:

| Window | Signals | Closed | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน | 7 | 7 | 0 | 14.29% | +62.13 | +1.02 | +31.06 | 9.69 | 7.15 |
| 2026-H1 | 12 | 12 | 0 | 16.67% | +139.09 | +0.77 | +23.18 | 70.55 | 1.20 |
| 2025-H2 WF | 11 | 11 | 0 | 0.00% | -10.44 | -0.06 | -1.74 | 0.00 | 10.44 |

Direction attribution: recent BUY 4 ดีล/1TP/+62.73, SELL 3/0TP/-0.60;
H1 BUY 8/2TP/+139.89, SELL 4/0TP/-0.80; WF BUY 6/0TP/-1.20,
SELL 5/0TP/-9.24 จึงทดสอบ BUY-only เป็น branch หลัก

Optimization audits:

- BUY-only RR7 ยังบวก recent +54.05 และ H1 +122.21 แต่ WF -1.20/0TP
- ปิด BE ทำ WF แย่ลงเป็น -28.94; จึงไม่ใช้ no-BE
- recent16 ให้ +54.05/+84.47/-6.70 และ recent24 ให้
  -6.15/-11.67/-0.40 ใน recent/H1/WF
- tau gates หลวม `.12/.10` ให้ +54.05/+103.01/-4.00; แบบเข้ม
  `.20/.18` เหลือ sample2/3/3 และยัง WF -0.60/0TP
- session16–22 ให้ +36.79/+117.09/-7.40 และ session07–23 ให้
  +28.07/+189.53/-28.85; WF ไม่มี TP ทุกกรณีและ recent DD เพิ่ม

จึงไม่มี payoff, direction, window, threshold หรือ session plateau ที่ทำให้ WF
อยู่รอด หลักฐานบ่งชี้ regime instability มากกว่า Edge ข้ามช่วง ปิด optimization
โดยคง baseline defaults เพื่อบันทึก experiment แล้วกลับไปสร้าง S326

## S326 — Gaussian-Kernel MMD Distribution-Shift Release 8R

ไฟล์: `strategy326.py`

Edge: ใช้ Gaussian-kernel Maximum Mean Discrepancy เปรียบ return distribution
ทั้งรูปทรงใน RKHS โดยใช้ median pairwise distance เป็น bandwidth และวัด
baseline drift จาก baseline สองครึ่งก่อนเทียบ baseline48 กับ recent20
เมื่อ MMD shift สูงกว่า drift พร้อม efficient directional path และ closed release
จึงเข้า next-open ด้วย release-extreme+0.08ATR stop และ TP8R

Baseline gates `.08/.04` ผ่าน survivor gate:

| Window | Signals | Closed | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน | 4 | 4 | 0 | 25.00% | +74.33 | +1.22 | +37.17 | 124.88 | 0.40 |
| 2026-H1 | 9 | 9 | 0 | 11.11% | +57.87 | +0.32 | +9.65 | 4.39 | 16.66 |
| 2025-H2 WF | 12 | 12 | 0 | 16.67% | +45.95 | +0.25 | +7.66 | 23.98 | 1.40 |

Direction attribution แสดง regime diversification: recent/H1 winner มาจาก SELL
แต่ WF winners ทั้งสองมาจาก BUY จึงคงทั้งสองทิศ

Optimization:

- winner floors คือ MMD0.1373 และ jump0.1135; gates `.12/.09` เว้น margin
  `.017/.023` และตัด weak BE noise โดยรักษา TP ครบ
- RR9–10 เพิ่ม recent/H1 payoff แต่ทำ WF winner หายหนึ่งตัว จึงคง 8R
- BE0.05 ให้ผลเท่า0.08แต่บาง trigger ต่ำกว่า spread; BE0.10 ลด H1 net
  และเพิ่ม DD จึงคง0.08
- gates `.11/.08` ยังบวกครบ แต่เพิ่มเฉพาะ BE; `.12/.09` สะอาดกว่า
- recent16 ยังบวก +74.53/+73.73/+41.34 แต่ WF DD เพิ่มเป็น6.21;
  recent24 ไม่มี winnerทั้งสามช่วง จึงคง recent20
- baseline44/46/48/50 ยังบวกครบ; 48–50 รักษา WF winners ทั้งสอง,
  แต่52เสีย current/H1 winners จึงคง48ให้ห่าง upper cliff
- bandwidth multiplier0.9/1.0/1.1 รักษา winner และบวกครบทุก window

ผล official optimized defaults:

| Window | Signals | Closed | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน | 1 | 1 | 0 | 100.00% | +74.93 | +1.23 | +37.47 | inf | 0.00 |
| 2026-H1 | 5 | 5 | 0 | 20.00% | +66.70 | +0.37 | +11.12 | 9.10 | 8.23 |
| 2025-H2 WF | 4 | 4 | 0 | 50.00% | +47.55 | +0.26 | +7.93 | 119.88 | 0.40 |
| รวม H2+H1 | 9 | 9 | 0 | 33.33% | +114.25 | +0.31 | +9.52 | 14.24 | 8.23 |

Combined return/DD=13.88 และ risk distance อยู่1.72–15.31 USD,
median6.11 USD ที่0.01 lot. Retest 2 เดือนถึง `2026-07-29` คง +74.93.
ที่ spread0.50 ยังบวก +74.63/+65.20/+46.35 ใน 2m/H1/WF

Portfolio overlap H1: S301 0/5 timestamps; S311/S312/S313/S322 อย่างละ1/5.
Session16–22 ยังบวก +63.49/+57.01/+63.52 ทุก window แม้ DD สูงขึ้น
จึงไม่พึ่ง boundary17–21; defaultเดิมมี recent/H1 risk-adjusted return ดีกว่า.
หลัง threshold/payoff/BE/window/baseline/bandwidth/latest/spread/overlap/session
audits ไม่พบการปรับที่เพิ่ม robustness โดยไม่เสีย breadth จึงปิด optimization หลัก
และไป S327

## S327 — Hawkes-Style Return-Shock Self-Excitation Release 8R

ไฟล์: `strategy327.py`

Edge: มอง absolute closed returns ที่เกิน empirical baseline quantile เป็น
point-process events แล้วคำนวณ exponentially decayed recent intensity เทียบ
expected intensity จาก baseline event rate แบบ causal หาก shock events กระจุกตัว
และ signed event direction/recent path/release candle สอดคล้องกัน จึงเข้า
next-open ด้วย release-extreme+0.08ATR stop และ TP8R

Baseline quantile0.80/events4/session16–22 ผ่าน survivor gate:

| Window | Signals | Closed | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน | 11 | 11 | 0 | 27.27% | +162.89 | +2.67 | +81.45 | 12.69 | 12.94 |
| 2026-H1 | 26 | 26 | 0 | 15.38% | +257.97 | +1.43 | +43.00 | 7.24 | 21.16 |
| 2025-H2 WF | 49 | 49 | 0 | 6.12% | +86.72 | +0.47 | +14.45 | 3.02 | 20.73 |

BUY และ SELL บวกครบทุก window จึงคงสองทิศ

Optimization:

- winner floor event count=5; เปลี่ยน4→5 รักษา TP ครบและปรับ WF
  +86.72/DD20.73 เป็น +108.10/DD11.14
- direction0.20→0.24 ตัดเพียง BE หนึ่งไม้และเพิ่มแค่0.20 จึงไม่ใช้;
  excitation ratio2.20 อยู่ต่ำกว่า winner floor2.2485 และถูกคงไว้
- RR8.5/9/10 ทำ H1 winner หายตัวเดียวกัน จึงคง8R ก่อน payoff cliff
- BE0.05 มี trigger ต่ำกว่า spreadบางไม้; BE0.10 เพิ่ม H1 DD เป็น27.27
  จึงคง0.08
- quantile0.75/0.80 บวกครบ; 0.75 เพิ่ม WF winnerและ netทุก window
  ส่วน0.70 ทำ WFเกือบเสมอทุน และ0.85 ลด recent/H1
- decay3/4 รักษา winners ครบ; decay5 เสีย WF winner จึงคง4
- recent14/16 รักษา winners ครบ; recent18 เสีย H1/WF winner จึงคง16
- baseline60/64 รักษา winners ครบ; baseline68 เสีย H1 winner จึงคง64
- session15–23 เพิ่ม current/H1/WF winnerอย่างละหนึ่งเมื่อเทียบ16–22;
  ขยาย14–24 ไม่เพิ่ม winnerแต่เพิ่ม WF DD เป็น26.40 จึงเลือก15–23

ผล official optimized defaults:

| Window | Signals | Closed | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน | 11 | 11 | 0 | 36.36% | +246.93 | +4.05 | +123.47 | 18.97 | 12.94 |
| 2026-H1 | 28 | 28 | 0 | 17.86% | +352.98 | +1.95 | +58.83 | 12.71 | 21.76 |
| 2025-H2 WF | 52 | 52 | 0 | 9.62% | +163.97 | +0.89 | +27.33 | 5.76 | 20.48 |
| รวม H2+H1 | 80 | 80 | 0 | 12.50% | +516.95 | +1.42 | +43.08 | 9.01 | 22.76 |

Combined return/DD=22.71. Risk distance 12 เดือนอยู่2.18–15.22 USD,
median6.28 USD ที่0.01 lot. Retest 2 เดือนถึง `2026-07-29` ยังบวก
+172.87, WR25.00%, +2.83/day, +86.44/month, PF10.33, DD17.92.
ที่ spread0.50 ยังบวก +243.63/+344.58/+148.37 ใน 2m/H1/WF

Portfolio overlap H1: S301 2/28, S311 1/28, S312 2/28, S313 2/28,
S322 3/28 และ S326 1/28 timestamps จึงให้ breadth และ diversification ดี.
หลัง event/direction/payoff/BE/quantile/decay/window/session/latest/spread/overlap
audits ไม่พบการปรับที่เพิ่ม robustness ต่อโดยไม่เสีย breadth จึงปิด optimization
หลักและไป S328

## S328 — Anderson–Darling Tail-Weighted Distribution-Shift Release 8R

ไฟล์: `strategy328.py`

Edge: ใช้ two-sample Anderson–Darling rank statistic ซึ่งให้น้ำหนัก pooled
distribution tails มากกว่า center เปรียบ baseline48 กับ recent20 และหัก
baseline drift ที่วัดจาก baseline สองครึ่ง เมื่อ tail-weighted shift สูงพอพร้อม
efficient directional path และ closed release จึงเข้า next-open ด้วย
release-extreme+0.08ATR stop และ TP8R

Baseline และ official defaults:

| Window | Signals | Closed | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน | 16 | 16 | 0 | 6.25% | +48.08 | +0.79 | +24.04 | 2.79 | 26.65 |
| 2026-H1 | 39 | 39 | 0 | 5.13% | +110.26 | +0.61 | +18.38 | 3.30 | 23.48 |
| 2025-H2 WF | 62 | 62 | 0 | 9.68% | +145.74 | +0.79 | +24.29 | 4.17 | 32.58 |
| รวม H2+H1 | 101 | 101 | 0 | 7.92% | +256.00 | +0.70 | +21.33 | 3.73 | 32.58 |

Current/H1 winners มาจาก SELL แต่ WF winnersทั้งหกมาจาก BUY จึงคงสองทิศ
เพื่อรองรับ regime rotation

Optimization audits:

- winner floors AD2.3410/jump1.0209; gates2.25/0.95 ตัดเพียง BEหนึ่งไม้
  และเพิ่ม0.20 จึงคง2.20/0.90 เพื่อ margin
- RR9–10 เพิ่ม net แต่ทำ WF winner หายหนึ่งตัว จึงคง8R
- BE0.05 เพิ่ม WF DD เป็น40.58และ trigger ต่ำกว่า spreadบางไม้;
  BE0.10 ลด H1 net จึงคง0.08
- recent18/20/22 บวกครบ; 20 ให้ combined risk-adjusted result ดีกว่า
  ส่วน16เกือบล้ม WF และ24เสีย current/H1 winners
- baseline44/48/52 บวกครบ; 44 ลด breadth/net และ52เอียง recent/H1
  พร้อมลด WF จึงคง48
- session14–24 ยังบวกแต่เพิ่ม WF DD เป็น44.86 โดยไม่เพิ่ม current winner
  จึงคง15–23

Combined return/DD=7.86. Risk distance 12 เดือนอยู่1.63–15.62 USD,
median6.60 USD ที่0.01 lot. Retest 2 เดือนถึง `2026-07-29` ยังบวก
+41.48, WR5.26%, +0.68/day, +20.74/month, PF2.24, DD33.45.
ที่ spread0.50 ยังบวก +43.28/+98.56/+127.14 ใน 2m/H1/WF

Portfolio overlap H1: S301 2/39, S311 3/39, S312 4/39, S313 1/39,
S322 1/39, S326 3/39 และ S327 5/39 timestamps. ผลแข็งแรงน้อยกว่า
S327 แต่ยังผ่าน cross-window survival และมี tail-weighted timestamps เพิ่มเติม.
หลัง gate/payoff/BE/window/session/latest/spread/overlap audits ไม่พบการปรับ
ที่เพิ่ม robustness พร้อมกัน จึงปิด optimization และไป S329

## S329 — Brownian-Bridge Path-Coherence Release 8R

ไฟล์: `strategy329.py`

Edge hypothesis: ลบเส้นตรงระหว่างต้น–ปลายของ cumulative log-return path แล้ว
วัด RMS bridge residual เทียบ realized return energy เปรียบ recent16 กับ median
ของ baseline blocks ขนาดเท่ากัน หาก recent path wandering ยุบและมี directional
displacement จึงตาม closed release

Baseline M5, spread0.20, 0.01 lot, 2026-05-20 ถึง 2026-07-20:

| Signals | Closed | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 10 | 10 | 0 | 0.00% | -8.69 | -0.14 | -4.35 | 0.00 | 8.69 |

BUY 2 ดีล Net -0.40 และ SELL 8 ดีล Net -8.29; ทั้งสอง branch ไม่มี TP
จึงไม่มี survivor และไม่ทำ threshold/payoff optimization. Bridge coherence
อย่างเดียวไม่ส่งผ่านไปถึง continuation8R จึงไป S330

## S330 — Distributed Realized-Quarticity Drive Release 8R

ไฟล์: `strategy330.py`

Edge hypothesis: ใช้ normalized realized quarticity วัดว่าพลังงาน return ถูก
ครอบด้วย jumpไม่กี่แท่งหรือกระจายต่อเนื่องหลายแท่ง เปรียบ recent16 กับ median
baseline blocks ขนาดเท่ากัน แล้วตาม efficient directional release เฉพาะเมื่อ
recent quarticity ยุบ

Baseline M5, spread0.20, 0.01 lot:

| Window | Signals | Closed | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน | 14 | 14 | 0 | 14.29% | +34.71 | +0.57 | +17.36 | 2.25 | 18.33 |
| 2026-H1 | 51 | 51 | 0 | 1.96% | -35.39 | -0.20 | -5.90 | 0.43 | 53.41 |
| 2025-H2 WF | 50 | 50 | 0 | 6.00% | +98.93 | +0.54 | +16.49 | 4.49 | 18.97 |

รวมสองทิศไม่ผ่าน H1. Direction attribution แสดง SELL ใกล้รอดที่สุด:
recent -0.51, H1 +1.65, WF +79.65 แต่ recent/H1 marginต่ำมากและ DD16–28.
SELL-only BE0.05 ให้ผลเหมือน0.08ทุก window จึงไม่มี improvement ที่แท้จริง
และ triggerต่ำกว่า spreadบางไม้. BUY branch recentดีแต่ H1 -37.04.
จึงไม่มี direction/payoff survivor ที่บวกครบสามช่วง ปิด optimization และไป S331

## S331 — Runs-Declustered Extremal-Index Release 8R

ไฟล์: `strategy331.py`

Edge hypothesis: กำหนด absolute-return exceedances จาก baseline quantile แล้ว
รวม events ที่ห่างกันไม่เกิน run gap เป็น cluster อัตรา clusters/events เป็น
extremal-index proxy; ค่าที่ลดลงหมายถึง tail events รวมเป็น bursts ก่อนตาม
directional release

Baseline M5, spread0.20, 0.01 lot:

| Window | Signals | Closed | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน | 24 | 24 | 0 | 4.17% | +19.05 | +0.31 | +9.52 | 1.38 | 44.51 |
| 2026-H1 | 59 | 59 | 0 | 3.39% | +57.09 | +0.32 | +9.52 | 1.60 | 66.97 |
| 2025-H2 WF | 116 | 116 | 0 | 3.45% | +33.19 | +0.18 | +5.53 | 1.36 | 62.77 |

ผลบวกครบแต่ return/DD ต่ำและ overtrading. SELL ลบ recent/WF; BUY-only
บวก +37.41/+4.25/+66.17 ใน recent/H1/WF แต่ H1 DD52.85.
ใช้ winner floors แบบมี margin (`events>=7`, `theta<=0.50`) ช่วยเป็น
+42.33/+9.77/+72.88 แต่ DD ยัง26.75/52.25/45.86 และ H1 marginบางมาก.
การไล่ theta/drop ให้ชิด winners จะเป็น sample fitting จึงยุติ optimization;
S331 ไม่ผ่าน efficiency survivor gate และไป S332

## S332 — Directional Return–Volume Tail-Copula Release 12R

ไฟล์: `strategy332.py`

Edge hypothesis: แยก upper/lower tail ของ signed closed return แล้ววัด conditional
co-exceedance เฉพาะแท่งที่ tick volume อยู่ใน upper tail ของแต่ละ sample หาก recent
tail dependence เพิ่มจาก baseline อย่างมีนัย มี asymmetry ชัด และ direction ตรงกับ
efficient recent path กับ release candle แปลว่า participation หนาแน่นกำลังเกาะอยู่กับ
price discovery ฝั่งเดียว ไม่ใช่เพียง volatility สูงทั่วไป จึงตาม next-open market
ด้วย stop หลัง release extreme และ payoff แบบ convex

Optimized default M5, spread0.20, 0.01 lot:

| Window | Signals | Closed | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน ถึง 2026-07-20 | 18 | 18 | 0 | 16.67% | +335.01 | +5.49 | +167.51 | 46.77 | 6.72 |
| 2026-H1 | 39 | 39 | 0 | 7.69% | +291.80 | +1.61 | +48.63 | 6.77 | 43.81 |
| 2025-H2 WF | 69 | 69 | 0 | 5.80% | +188.26 | +1.02 | +31.38 | 5.75 | 17.53 |

ล็อกค่า `TAIL_ASYMMETRY_MIN=0.35`, `TP_RR=12.0`, `BE_RR=0.08`,
`TAIL_QUANTILE=0.75`, `RECENT_RETURNS=20`, `BASELINE_RETURNS=64` และ session
15:00–22:59 BKK. Winner floors ต่ำสุดคือ recent dependence 0.60, jump 0.225 และ
asymmetry 0.40 จึงเหลือ margin 0.05 ที่ asymmetry gate. RR13–15 ทำ WF winner หาย
หนึ่งตัว ขณะที่ RR12 รักษา 3/3/4 winners ใน recent/H1/WF จึงไม่ไล่ payoff ผ่าน cliff.

Sensitivity audit:

- BE0.05 ให้ผลเท่ากันเกือบทั้งหมดแต่เพิ่ม WF BE หนึ่งไม้; BE0.10 ลด H1 เป็น
  +282.82 และเพิ่ม DD เป็น52.79 จึงคง0.08
- quantile0.70 ยังบวก +214.89/+183.30/+137.84 แต่ลด breadth และ net;
  quantile0.80 ไม่มี recent/H1 TP และ WF เหลือ +10.83 จึงคง0.75
- recent18/22/24 ยังบวกครบแต่ลด winner หรือ breadth ข้ามหน้าต่าง ส่วน recent16
  ไม่มี TP ทุกหน้าต่าง จึงคง20
- baseline60/68 และ session14–24/16–22 ยังบวกครบ แต่ไม่มีตัวใดเพิ่ม robustness
  พร้อมกันทั้งสามหน้าต่าง; session14–24 เพิ่ม H1/WF DD เป็น51.84/31.24
- spread0.50 ยังบวก +329.61/+280.10/+167.56 ใน recent/H1/WF

Direction attribution: recent BUY +97.88, SELL +237.13; H1 BUY +66.63,
SELL +225.17; WF BUY +76.17, SELL +112.09 จึงบวกทั้งสองฝั่งทุก validation window.
อย่างไรก็ตาม rolling 2 เดือนถึง 2026-07-29 ได้ 20 ดีล, WR10.00%, Net +219.99,
+3.61/day, +110.00/month, PF13.00, DD17.94 โดย BUY -17.14 และกำไรทั้งหมดมาจาก
SELL จึงยังมี direction-regime risk.

รวม WF ต่อ H1 ตามเวลาได้ 108 ดีล, 7 TP, Net +480.06, PF6.32, DD61.34,
return/DD7.83. Risk distance 12 เดือนอยู่ 1.28–12.48 USD, median5.52 USD
ที่0.01 lot. H1 exact timestamp overlap จาก 39 ดีลคือ S301 3, S311 3,
S312 3, S313 2, S322 6, S326 1, S327 11 และ S328 7; overlap สูงสุดกับ
S327 แต่ยังมี timestamps อิสระ 28/39.

หลัง gate/payoff/BE/quantile/window/session/latest/spread/direction/overlap audits
ไม่พบการปรับที่เพิ่ม robustness พร้อมกันโดยไม่เสีย winner หรือ breadth จึงปิด
optimization ของ S332 และเริ่ม S333

## S333 — Lagged Directional Participation-Response Release 9R

ไฟล์: `strategy333.py`

Edge hypothesis: แปลง volume ของแท่งถัดไปเป็น high/normal state แล้ววัด
Laplace-smoothed log-odds ว่า positive หรือ negative closed return ในแท่งก่อนหน้า
เพิ่มโอกาสเกิด high-volume response มากกว่า unconditional rate เท่าใด เปรียบ recent
กับ baseline และตาม direction ที่ response เพิ่มพร้อม asymmetry, efficient path และ
closed release. นี่เป็น lagged price-to-participation effect ต่างจาก S332 ซึ่งวัด
return-volume co-exceedance พร้อมกันในแท่งเดียว

Optimized default M5, spread0.20, 0.01 lot:

| Window | Signals | Closed | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน ถึง 2026-07-20 | 20 | 20 | 0 | 10.00% | +92.39 | +1.51 | +46.19 | 3.93 | 17.90 |
| 2026-H1 | 66 | 66 | 0 | 4.55% | +150.77 | +0.83 | +25.13 | 2.91 | 34.55 |
| 2025-H2 WF | 94 | 94 | 0 | 4.26% | +127.79 | +0.69 | +21.30 | 3.07 | 33.53 |

ล็อกค่า `BASELINE_PAIRS=68`, `RECENT_PAIRS=24`,
`VOLUME_STATE_QUANTILE=0.65`, `LAPLACE_ALPHA=1.0`,
`RECENT_RESPONSE_MIN=0.22`, `RESPONSE_JUMP_MIN=0.14`,
`RESPONSE_ASYMMETRY_MIN=0.575`, `TP_RR=9.0`, `BE_RR=0.06`
และ session15:00–22:59 BKK. Winner floors หลัง optimize คือ response0.2469,
jump0.2693 และ asymmetry0.6242 จึงเหลือ margin0.0269/0.1293/0.0492.

Optimization audits:

- gate baseline .18/.12/.20 ให้ +77.77/+80.90/+47.45 แต่ DD H1/WF
  70.41/47.93; combined .22/.14/.575 รักษา winners และลด noise
- asymmetry .575–.59 เป็น plateau; เลือก .575 เพื่อ margin มากสุด
- 9R รักษา 2/3/3 winners และให้ +92.19/+125.13/+69.56 ก่อน baseline/BE
  optimization; 9.25R ทำ H1 winner หายทันทีจึงเลือก9R พร้อม0.25R margin
- baseline66/68/70 เพิ่ม WF เป็น4 TP; 68–70 ให้ WF เท่ากันที่ BE.07 จึงเลือก
  68 ต้น plateau. BE.05/.06 ให้ผลเท่ากันที่ baseline64 และ .06 conservative กว่า;
  เมื่อรวม baseline68+BE.06 ได้ official results ด้านบน
- quantile0.60 ลด winners, 0.70 ทำ recent/H1 ลบ; recent22/26 และ
  baseline/session/alpha variants ไม่มีตัวใดเพิ่ม robustness พร้อมกันทุกหน้าต่าง
- spread0.50 ยังบวก +86.39/+130.97/+99.59 ใน recent/H1/WF

Direction attribution: recent BUY +34.33, SELL +58.06; H1 BUY +0.58,
SELL +150.19; WF BUY +56.43, SELL +71.36. ทั้งสองฝั่งยังบวกทุก validation
window แต่ H1 BUY margin ต่ำมาก จึงไม่ควรตีความว่า direction robustness เท่ากัน.
Rolling 2 เดือนถึง 2026-07-29 มี22ดีล, WR9.09%, Net +91.99,
+1.51/day, +46.00/month, PF3.88, DD18.90.

รวม WF ต่อ H1 ตามเวลาได้160ดีล, 7 TP, Net +278.56, PF2.98, DD35.15,
return/DD7.93. Risk distance 12 เดือนอยู่1.66–15.87 USD, median5.42 USD
ที่0.01 lot. H1 exact timestamp overlap จาก66ดีลคือ S301 4, S311 2,
S312 4, S313 1, S322 2, S326 1, S327 8, S328 8 และ S332 9;
ยังมี timestamps อิสระจาก S332 57/66.

หลัง gate/payoff/BE/quantile/window/smoothing/session/latest/spread/direction/
overlap audits ไม่พบ robust improvement ต่อโดยไม่เสีย winner หรือ breadth
จึงปิด optimization ของ S333 และเริ่ม S334

## S334 — Directional Realized-Semivariance Rotation Release 8.5R

ไฟล์: `strategy334.py`

Edge hypothesis: แบ่ง squared closed log returns เป็น positive/negative realized
semivariance แล้วตรวจว่า recent energy rotation ไปฝั่งใดเมื่อเทียบ disjoint baseline.
บังคับ largest-return energy share ไม่เกิน cap เพื่อไม่ตีความ single jump เป็น regime,
จากนั้นตาม efficient path และ closed release ฝั่งเดียวกัน. Alpha นี้วัดทิศที่
volatility budget ถูกใช้ ต่างจาก tail/volume dependence ของ S332–S333

Optimized default M5, spread0.20, 0.01 lot:

| Window | Signals | Closed | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน ถึง 2026-07-20 | 49 | 49 | 0 | 6.12% | +87.40 | +1.43 | +43.70 | 2.61 | 18.99 |
| 2026-H1 | 141 | 141 | 0 | 4.26% | +261.69 | +1.45 | +43.62 | 2.54 | 68.35 |
| 2025-H2 WF | 170 | 170 | 0 | 5.88% | +251.27 | +1.37 | +41.88 | 2.68 | 75.91 |

ล็อกค่า `BASELINE_RETURNS=64`, `RECENT_RETURNS=20`,
`RECENT_SEMIVARIANCE_SHARE_MIN=0.68`, `SEMIVARIANCE_SHARE_JUMP_MIN=0.12`,
`SEMIVARIANCE_ASYMMETRY_MIN=0.36`, `MAX_SINGLE_RETURN_ENERGY_SHARE=0.55`,
`TP_RR=8.5`, `BE_RR=0.06` และ session15:00–22:59 BKK.

Optimization audits:

- baseline8R/BE.08 ได้ +78.81/+202.29/+219.32 ใน recent/H1/WF
- 8.5R รักษา3/6/10 TP ครบ; 8.75R ทำ WF เหลือ9 TP จึงเลือก8.5R พร้อม
  0.25R margin ก่อน payoff cliff
- BE.05/.06 ให้ recentเท่ากัน; .06 conservative กว่าและให้ H1/WF
  +261.69/+251.27 กับ DD68.35/75.91 ดีกว่า .08/.10
- baseline60/64/68, single-energy cap.50/.55/.60 และ loose gates ยังบวกครบ
  แสดง neighborhood support; cap.50 ตัด WF winnerหนึ่งตัวจึงคง.55
- recent18/22 ยังบวกแต่เสีย validation winners; session14–24 เพิ่ม DD และ
  session16–22 ลด breadth จึงคง20และ sessionเดิม
- spread0.50 ยังบวก +72.70/+219.39/+200.27 ใน recent/H1/WF

Direction attribution: recent BUY +14.29, SELL +73.11; H1 BUY +42.19,
SELL +219.50; WF BUY +168.40, SELL +82.87 จึงบวกทั้งสองทิศทุก validation
window แต่ H1 BUY return/DD ต่ำ. Rolling 2 เดือนถึง 2026-07-29 มี53ดีล,
2 TP, WR3.77%, Net +59.76, +0.98/day, +29.88/month, PF2.13, DD35.54.

รวม WF ต่อ H1 ตามเวลาได้311ดีล, 16 TP, Net +512.96, PF2.61, DD75.91,
return/DD6.76. Risk distance 12 เดือนอยู่1.41–15.87 USD, median5.50 USD
ที่0.01 lot. H1 exact timestamp overlap จาก141ดีลคือ S301 8, S311 6,
S312 7, S313 2, S322 9, S326 1, S327 11, S328 24, S332 20 และ
S333 35; แม้ density สูงแต่ยังมี timestamps อิสระจาก S333 106/141.

หลัง payoff/BE/window/baseline/cap/gate/session/latest/spread/direction/overlap
audits ไม่พบ robust improvement ต่อโดยไม่เสีย winner หรือ breadth จึงปิด
optimization ของ S334 และเริ่ม S335

## S335 — Recurrence-Determinism Expansion Release 8R

ไฟล์: `strategy335.py`

Edge hypothesis: สร้าง recurrence plot จาก closed log returns โดยใช้ระยะ
MAD-scaled แล้ววัดสัดส่วน recurrence points ที่ต่อเป็น diagonal lines
(determinism) หาก recent determinism เพิ่มจาก disjoint baseline แปลว่า
multi-step return trajectories เริ่มทำซ้ำ ก่อนตาม efficient path และ release.

ผล Backtest มาตรฐาน 2 เดือน, M5, spread0.20, 0.01 lot:

| Signals | Closed | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 5 | 5 | 0 | 0.00% | -9.66 | -0.16 | -4.83 | 0.00 | 9.66 |

BUY4ดีล Net -0.80 และ SELL1ดีล Net -8.86; ไม่มี TP ทั้งสองทิศ
จึงไม่ผ่อน recurrence/determinism gates หรือ optimize จาก sample ที่ไม่มี winner.
Repeated return motifs ไม่ส่งผ่านถึง continuation8R ในช่วงทดสอบ จึงไป S336

## S336 — Range–Volume Liquidity-Elasticity Release 8R

ไฟล์: `strategy336.py`

Edge hypothesis: fit OLS ของ log(relative intrabar range) ต่อ log(tick volume)
แยก baseline64/recent24 หาก recent elasticity, R² และ volume activity เพิ่ม
แปลว่ากิจกรรมเพิ่มกำลังสร้าง price range มากขึ้นในสภาพคล่องบาง ก่อนตาม
directional path และ release.

ผล Backtest M5, spread0.20, 0.01 lot:

| Window | Signals | Closed | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน | 22 | 22 | 0 | 4.55% | +25.82 | +0.42 | +12.91 | 1.45 | 42.84 |
| 2026-H1 | 38 | 38 | 0 | 7.89% | +154.64 | +0.85 | +25.77 | 2.84 | 27.12 |
| 2025-H2 WF | 59 | 59 | 0 | 1.69% | -30.14 | -0.16 | -5.02 | 0.46 | 38.86 |

Direction audit ไม่พบ survivor: SELL recent/H1 +49.73/+146.19 แต่ WF
-26.11 และไม่มี TP; BUY recent -23.91 ไม่มี TP แม้ H1/WF +8.45/-4.03.
จึงไม่ tune elasticity/R² gates เข้าหา winner บางจุดและไป S337

## S337 — Fair-Value Crossing-Collapse Release 8R

ไฟล์: `strategy337.py`

Edge hypothesis: วัดอัตราที่ closed prices สลับข้าม sample median ใน
baseline64 เทียบ recent20 หาก crossing rate ยุบและ terminal displacement
ค้างฝั่งเดียว แปลว่า auction เลิกหมุนรอบ fair value และเริ่ม value migration
ก่อนตาม directional release.

ผล Backtest มาตรฐาน 2 เดือน, M5, spread0.20, 0.01 lot:

| Signals | Closed | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 4 | 4 | 0 | 0.00% | -6.75 | -0.11 | -3.38 | 0.00 | 6.75 |

BUY3ดีล Net -6.55 และ SELL1ดีล Net -0.20; ไม่มี TP จึงไม่ผ่อน
crossing/drop/terminal-distance gates และเดินหน้า S338 ด้วย alpha source ใหม่

## S338 — Multivariate Price–Volume PCA-Coherence Release 8R

ไฟล์: `strategy338.py`

Edge hypothesis: สร้าง correlation matrix ของ closed return, log tick-volume
change และ log relative range แล้ววัด PC1 explained-variance share หาก recent
coherence เพิ่มจาก baseline พร้อม return/volume loadings ไปทิศเดียวกัน จึงตาม
directional path และ release.

ผล Backtest มาตรฐาน 2 เดือน, M5, spread0.20, 0.01 lot:

| Signals | Closed | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 24 | 23 | 0 | 4.35% | -12.17 | -0.20 | -6.08 | 0.73 | 25.10 |

BUY22 closed มี1 TPแต่ Net -11.97; SELL1ดีล Net -0.20 ไม่มี TP.
PCA coherence สร้าง sample ได้แต่ expectancy ลบ จึงไม่ tune share/loadings
จาก winner เดียวและเดินหน้า S339

## S339 — BUY-Only Directional Record-Statistics Discovery 8R

ไฟล์: `strategy339.py`

Edge hypothesis: นับ sequential record highs/lows ของราคาปิดใน recent20
แล้วเทียบ directional record rate กับ median ของ equal-sized disjoint baseline
blocks. Record creation ที่เร่งและมี asymmetry เป็น distribution-free signature
ของ genuine price discovery ก่อน efficient BUY release.

Optimized default M5, spread0.20, 0.01 lot:

| Window | Signals | Closed | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน ถึง 2026-07-20 | 41 | 41 | 0 | 7.32% | +116.37 | +1.91 | +58.18 | 3.72 | 31.59 |
| 2026-H1 | 98 | 98 | 0 | 4.08% | +159.83 | +0.88 | +26.64 | 2.30 | 55.93 |
| 2025-H2 WF | 135 | 135 | 0 | 5.19% | +110.28 | +0.60 | +18.38 | 1.91 | 75.57 |

ล็อก `ALLOW_BUY=True`, `ALLOW_SELL=False`, `BASELINE_BARS=60`,
`RECENT_BARS=20`, record rate/jump/asymmetry `.25/.10/.15`,
minimum records5, `TP_RR=8.0`, `BE_RR=0.08` และ session15–23.

Optimization audits:

- baselineสองทิศได้ +137.01/+377.98/+32.48 แต่ SELL WF -64.94;
  BUY-only replay บวก +109.91/+144.12/+97.42 จึงปิด SELL
- RR9 ทำ recent/H1 winners หาย; RR12 ทำ H1 ลบ จึงคง8R
- BE.05/.06 ลด H1 DD แต่เพิ่ม WF signals/DD และไม่เพิ่ม net พร้อมกัน
  จึงคง.08
- recent18 ทำ recent/H1 ลบ; recent22 ลด winners. Record count4 เหมือน
  default แต่6 ตัด winners จึงคง20/5
- baseline56–68 บวกครบ; 58/60/62 เป็น plateau และ60 รักษา3/4/7 TP
  พร้อม net/DD สมดุลกว่า64 จึงเลือก60
- session14–24 เพิ่ม H1 breadth แต่เพิ่ม WF DD/ลด net; 16–22 ทำ WF ลบ
- spread0.50 ยังบวก +104.07/+130.43/+69.78 ใน recent/H1/WF

Rolling 2 เดือนถึง 2026-07-29 มี43ดีล, 2 TP, WR4.65%, Net +43.78,
+0.72/day, +21.89/month, PF1.95, DD38.59. รวม WF ต่อ H1 ตามเวลา
ได้233ดีล, 11 TP, Net +270.11, PF2.10, DD75.57, return/DD3.57.
Risk distance 12 เดือนอยู่1.39–15.62 USD, median5.32 USD ที่0.01 lot.

H1 exact timestamp overlap จาก98ดีลคือ S301/311/312/313/326 เท่ากับ0,
S322=6, S327=4, S328=18, S332=12, S333=12 และ S334=54.
Record selector มี diversification จากกลุ่ม distribution-shift แต่ overlap สูงกับ
S334 directional semivariance release จึงควรจำกัด portfolio weight.

หลัง direction/payoff/BE/window/baseline/record/session/latest/spread/overlap
audits ไม่พบ robust improvement ต่อโดยไม่เสีย winner หรือ breadth จึงปิด
optimization ของ S339 และเริ่ม S340

## S340 — Distributed Volume-Participation Release 8R

ไฟล์: `strategy340.py`

Edge hypothesis: แปลง tick volume เป็น participation shares แล้วใช้ inverse
Herfindahl/effective participation ratio วัดว่า activity กระจายหลายแท่งหรือไม่
หาก recent breadth เพิ่มจาก baseline พร้อม signed-volume imbalance, path และ
release ทิศเดียวกัน จึงตาม continuation.

ผล Backtest M5, spread0.20, 0.01 lot:

| Window | Signals | Closed | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน | 11 | 11 | 0 | 9.09% | +27.56 | +0.45 | +13.78 | 6.45 | 4.86 |
| 2026-H1 | 46 | 46 | 0 | 0.00% | -60.63 | -0.33 | -10.11 | 0.00 | 60.63 |
| 2025-H2 WF | 72 | 72 | 0 | 4.17% | +15.54 | +0.08 | +2.59 | 1.23 | 46.57 |

H1 ไม่มี TP ทั้ง BUY29/SELL17; BUY recent winnerเดียวไม่ใช่ independent
cross-window edge. จึงไม่ optimize participation/imbalance gates และให้ S341
ทดสอบ complementary concentrated-participation ignition regime

## S341 — Concentrated Volume-Participation Ignition Release 8R

ไฟล์: `strategy341.py`

Edge hypothesis: complement ของ S340 โดยบังคับ recent effective
participation ratio ลดจาก baseline และ signed-volume imbalance/path/release
ไปทิศเดียวกัน เพื่อจับ institutional ignition ที่ activity กระจุกไม่กี่แท่ง.

ผล Backtest มาตรฐาน 2 เดือน, M5, spread0.20, 0.01 lot:

| Signals | Closed | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | 0 | 0 | N/A | 0.00 | 0.00 | 0.00 | N/A | 0.00 |

participation ratio≤.62, drop≥.08 และ imbalance/path/release ไม่ทับกัน
ในช่วงทดสอบ จึงไม่ผ่อน threshold เพื่อสร้าง sample ย้อนหลังและไป S342

## S342 — Mann–Whitney Volume-Dominance Release 8R

ไฟล์: `strategy342.py`

Edge hypothesis: ใช้ distribution-free AUC วัดความน่าจะเป็นที่ tick volume
บน positive-return bars สูงกว่า negative-return bars ทั้ง distribution แล้ว
ตาม direction เมื่อ recent dominance เพิ่มจาก baseline พร้อม path/release.

ผล Backtest มาตรฐาน 2 เดือน, M5, spread0.20, 0.01 lot:

| Signals | Closed | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 17 | 17 | 0 | 0.00% | -18.30 | -0.30 | -9.15 | 0.00 | 18.30 |

ไม่มี TP จึงไม่ tune AUC/dominance gates และเปลี่ยน S343 ไปใช้
geometric auction-overlap source ที่ไม่พึ่ง conditional volume distribution

## S343 — Auction Range-Overlap Fragmentation Release 8R

ไฟล์: `strategy343.py`

Edge hypothesis: วัด normalized interval overlap ของ high-low ranges
ระหว่างแท่งติดกัน หาก recent mean overlap ลดจาก baseline และ non-overlap
transitions เพิ่ม แปลว่า price acceptance กำลัง migrate ก่อน directional release.

ผล Backtest มาตรฐาน 2 เดือน, M5, spread0.20, 0.01 lot:

| Signals | Closed | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | 0 | 0 | N/A | 0.00 | 0.00 | 0.00 | N/A | 0.00 |

overlap≤.45, drop≥.10, non-overlap≥.15 และ path/release ไม่ทับกัน
จึงไม่ผ่อน geometric gates เพื่อสร้าง sample และเดินหน้า S344

## S344 — Circular Candle-Control Synchronization Release 8R

ไฟล์: `strategy344.py`

Edge hypothesis: แปลง body fraction และ close-location value ของแต่ละแท่ง
เป็น unit vector แล้วใช้ mean-resultant length วัดการ synchronize ของแรงควบคุม
แท่งเทียน หาก recent concentration เพิ่มจาก baseline พร้อม mean direction,
path และ release ไปทางเดียวกัน จึงตาม continuation.

ผล Backtest มาตรฐาน 2 เดือน, M5, spread0.20, 0.01 lot:

| Signals | Closed | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | 0 | 0 | N/A | 0.00 | 0.00 | 0.00 | N/A | 0.00 |

resultant≥.72, jump≥.12, directional component≥.55 และ path/release
ไม่ทับกันในช่วงทดสอบ จึงยังยืนยันว่าเทรดได้จริงไม่ได้ ไม่ลด threshold
ย้อนหลังเพื่อสร้าง sample และเดินหน้า S345

## S345 — Directional Wick-Rejection Pressure Release 8R

ไฟล์: `strategy345.py`

Edge hypothesis: normalize lower-wick ลบ upper-wick ด้วย range ของแต่ละแท่ง
แล้วเทียบ recent mean กับ baseline พร้อมบังคับให้แท่งส่วนใหญ่มี rejection
ทิศเดียวกัน ก่อนยืนยันด้วย directional path และ release.

ผล Backtest มาตรฐาน 2 เดือน, M5, spread0.20, 0.01 lot:

| Signals | Closed | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 | 2 | 0 | 0.00% | -7.06 | -0.12 | -3.53 | 0.00 | 7.06 |

ตัวจำลองสร้างและปิดออเดอร์ได้จริง แต่ทั้งสองดีลไม่ถึง TP 8R จึงไม่ผ่าน
survivor gate และไม่ optimize threshold จาก sample เพียงสองดีล

## S346 — Hellinger Return-Distribution Shift Release 11R

ไฟล์: `strategy346.py`

Edge: แบ่ง closed-return distribution ด้วย baseline quantiles แล้วใช้
discrete Hellinger distance วัดการเปลี่ยน probability mass แบบรากที่สอง
พร้อมหัก baseline two-half drift. รับเฉพาะ shift ที่ recent median เคลื่อน
อย่างน้อย .70 baseline MAD และ directional path/release ยืนยันทางเดียวกัน.
Metric นี้ต่างจาก Wasserstein/CvM/energy/MMD เพราะเปรียบ probability
amplitudes ใน adaptive quantile bins และไม่ให้น้ำหนักตามระยะ return โดยตรง.

Optimized default M5, spread0.20, 0.01 lot:

| Window | Signals | Closed | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน ถึง 2026-07-20 | 9 | 9 | 0 | 22.22% | +135.91 | +2.23 | +67.95 | 11.75 | 11.44 |
| 2026-H1 | 24 | 24 | 0 | 8.33% | +216.95 | +1.20 | +36.16 | 18.10 | 9.29 |
| 2025-H2 WF | 44 | 44 | 0 | 9.09% | +201.51 | +1.10 | +33.59 | 11.12 | 14.19 |

ล็อก `BASELINE_RETURNS=64`, `RECENT_RETURNS=20`, 6 bins,
Hellinger/excess `.30/.10`, median shift `.70 MAD`, session15–23,
`TP_RR=11.0` และ `BE_RR=0.08`.

Optimization audits:

- baseline 8R บวก +94.68/+134.01/+134.22 ใน recent/H1/WF แล้ว RR9–11
  เพิ่ม net ทุกหน้าต่างโดยไม่เสีย TP; RR12 เสีย WF หนึ่ง TP และ RR14
  เหลือ WF สอง TP จึงเลือก 11R ก่อน payoff cliff
- BUY-only เพิ่ม recent/H1 แต่ลด WF +134.22→+56.77; SELL มี WF winner
  และ net +77.45 จึงคงสองทิศ
- BE .08–.10 เป็น plateau; .05–.06 ลด H1 DD แต่เพิ่ม WF DD และไม่เพิ่ม
  combined net อย่างมีนัย จึงคง .08
- median gate .60–.70 เพิ่มทุกหน้าต่างและรักษา 2/2/4 TP; .75 ทำ WF
  เหลือสาม TPและ netร่วง +201.51→+88.47 จึงเลือก .70 ก่อน cliff
- Hellinger .25 เพิ่ม loser, .35 เสีย H1 winner; excess .08/.12 ไม่ให้
  robust improvement จึงคง `.30/.10`
- bins5 ไม่มี H1 TP, bins6–7 เป็น plateau; baseline60 เพิ่ม recent เล็กน้อย
  แต่ WF DD เพิ่ม14.19→24.99 จึงคง 6 bins/64 returns
- recent18 เพิ่ม recent/H1 แต่ WF TP ลด4→2, netเหลือ+83.13 และ DD49.78;
  recent22 ไม่เพิ่ม edge จึงคง20
- session14–24 ไม่เพิ่ม H1; 16–22 เสียหนึ่ง TP. Path efficiency
  .18 ไม่เพิ่มผลและ .26 เสียหนึ่ง TP จึงคง session15–23/efficiency.22
- spread0.50 ยังบวก +133.21/+209.75/+188.31 ใน recent/H1/WF โดย
  รักษา TP count เดิม

Rolling 2 เดือนถึง 2026-07-29 มี8ดีล, 1 TP, WR12.50%, Net +40.59,
+0.67/day, +20.29/month, PF4.21, DD11.64. รวม WF ต่อ H1 ตามเวลา
ได้68ดีล, 6 TP, Net +418.46, DD14.19, return/DD29.49. Risk distance
อยู่1.72–15.62 USD, median5.89 USD ที่0.01 lot.

H1 exact timestamp overlap จาก24ดีลคือ S332=5, S333=3, S334=14 และ
S339=14. Hellinger source ช่วยกระจายจาก S332/S333 ชัด แต่มี release-timing
overlap กับ S334/S339 จึงควรจำกัด portfolio weight. หลัง payoff, direction,
BE, distribution gates, bins, baseline/recent window, session, path, latest,
spread และ overlap audits ไม่พบ robust improvement ต่อ จึงปิด optimization
ของ S346 และเริ่ม S347

## S347 — Range-Coordinate Acceptance-Shelf Breakout 8R

ไฟล์: `strategy347.py`

Edge hypothesis: map ราคาปิดลง baseline high-low coordinate แล้วหา recent
cluster ที่ย้ายจาก baseline median ไปยอมรับใกล้ขอบ range ด้วย IQR แคบและ
edge-acceptance rate สูง ก่อนตาม closed breakout จาก recent shelf.

ผล Backtest M5, spread0.20, 0.01 lot:

| Window | Signals | Closed | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน | 19 | 19 | 0 | 5.26% | +12.76 | +0.21 | +6.38 | 1.49 | 25.48 |
| 2026-H1 | 64 | 64 | 0 | 0.00% | -114.78 | -0.63 | -19.13 | 0.00 | 114.78 |
| 2025-H2 WF | 65 | 65 | 0 | 1.54% | -42.04 | -0.23 | -7.01 | 0.35 | 59.66 |

rolling ล่าสุดยังบวก +24.06 แต่ H1 ไม่มี TP จาก64ดีลและ WF ติดลบ
จึงยืนยันว่า recent winner ไม่ใช่ continuation edge. ไม่ tune coordinate
gates ย้อนหลังและให้ S348 ทดสอบ complementary failed-breakout reclaim fade.

## S348 — Acceptance-Edge Failed-Breakout Reclaim Fade 8R

ไฟล์: `strategy348.py`

Edge hypothesis: complement ของ S347 โดยหา migrated acceptance edge เดิม
แต่ไม่ตาม breakout; รอแท่งปิดกวาด recent edge แล้ว reclaim กลับเข้า coordinate
threshold พร้อม rejection wick ก่อน fade ไปฝั่งตรงข้าม.

ผล Backtest มาตรฐาน 2 เดือน, M5, spread0.20, 0.01 lot:

| Signals | Closed | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | 0 | 0 | N/A | 0.00 | 0.00 | 0.00 | N/A | 0.00 |

migration, sweep, reclaim และ wick confirmation ไม่ทับกันในช่วงทดสอบ
จึงไม่ลด gate ย้อนหลังเพื่อสร้าง sample และเดินหน้า S349

## S349 — BUY-Only Jensen–Shannon Quantile-Occupancy Tilt 8R

ไฟล์: `strategy349.py`

Edge: แบ่ง closed returns ด้วย baseline quantiles แล้ววัด normalized
Jensen–Shannon divergence ซึ่งเป็น information gain ระหว่าง baseline/recent
probability distributions พร้อมหัก baseline two-half drift. Direction มาจาก
probability mass ในสอง upper bins ลบสอง lower bins ไม่ใช้ median/MAD แบบ S346.
รับเฉพาะ BUY เมื่อ upper-tail occupancy tilt ≥.35 และ directional path/release
ยืนยันทางเดียวกัน.

Optimized default M5, spread0.20, 0.01 lot:

| Window | Signals | Closed | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน ถึง 2026-07-20 | 3 | 3 | 0 | 33.33% | +38.24 | +0.63 | +19.12 | 96.60 | 0.40 |
| 2026-H1 | 9 | 9 | 0 | 11.11% | +96.06 | +0.53 | +16.01 | 61.04 | 1.00 |
| 2025-H2 WF | 22 | 22 | 0 | 18.18% | +74.16 | +0.40 | +12.36 | 3.98 | 24.10 |

ล็อก `ALLOW_BUY=True`, `ALLOW_SELL=False`, `JS_DIVERGENCE_MIN=.12`,
`JS_EXCESS_MIN=.03`, `RECENT_MASS_TILT_MIN=.35`,
`MASS_TILT_SHIFT_MIN=.12`, baseline64/recent20, 6 bins, session15–23,
`TP_RR=8.0` และ `BE_RR=.05`.

Optimization audits:

- baselineสองทิศ 8R บวก +17.34/+63.43/+29.15 แต่ SELL recent/H1/WF
  มี12/24/32ดีล, 0 TP และลบทั้งหมด; BUY-only เพิ่มทุกหน้าต่างและลด DD
  จึงปิด SELL
- RR9 เสีย WF winnerหนึ่งตัวและ netลด; RR7 เพิ่ม WF winner4→5 แต่ลด
  recent/H1 มากกว่า gain รวม จึงคง8R
- BE .04–.05 เป็น plateau และ .05 เพิ่ม H1/WF พร้อมลด WF DD
  46.61→41.54 เทียบ .08 จึงเลือก .05
- JS gate .08→.12 เพิ่มทุกหน้าต่างและรักษา1/1/4 TP; .14 ทำ recent
  winner หาย จึงเลือก .12 ก่อน cliff
- mass tilt .20→.35 ลด loserพร้อมเพิ่มทุกหน้าต่างและรักษา1/1/4 TP;
  .40 ทำ recent winner หายและ WF เหลือ2 TP จึงเลือก .35 ก่อน cliff
- excess .04, path efficiency .26 และ tilt-shift .16 ไม่ให้ robust
  improvement จึงคง `.03/.22/.12`
- bins7, baseline60/68 และ recent18 ไม่เพิ่ม robustly; recent22 ทำ WF
  เสีย winnerและลด net จึงคง bins6/baseline64/recent20
- session14–24 ให้ผลเท่าเดิมแต่เพิ่ม exposure window จึงคง15–23
- spread0.50 ยังบวก +37.34/+93.36/+67.56 ใน recent/H1/WF โดย
  รักษา TP count เดิม

Rolling 2 เดือนถึง 2026-07-29 เท่ากับ3ดีล, 1 TP, WR33.33%,
Net +38.24, +0.63/day, +19.12/month, PF96.60, DD0.40. รวม WF ต่อ H1
ตามเวลาได้31ดีล, 5 TP, Net +170.22, DD24.70, return/DD6.89.
Risk distance อยู่1.92–12.13 USD, median5.27 USD ที่0.01 lot.

H1 exact timestamp overlap จาก9ดีลคือ S332=2, S333=0, S334=7,
S339=5 และ S346=8. แม้ JS formulation เป็น independent falsification
แต่ optimized selector เป็น strict subset เชิง timing ของ S346/S334 จึงไม่เพิ่ม
portfolio breadth มากและควรใช้เป็น confirmation/จำกัด weight. หลัง direction,
payoff, BE, JS/excess/tilt gates, bins, windows, session, latest, spread และ
overlap audits ไม่พบ robust improvement ต่อ จึงปิด optimization และเริ่ม S350

## S350 — Volume-Weighted Occupation-Imbalance Exhaustion Fade 8R

ไฟล์: `strategy350.py`

Edge hypothesis: anchor fair value ด้วย baseline typical price ถ่วง tick volume
แล้ววัด fraction ของ recent closes ที่ค้างด้านเดียวของ anchor และ median
distance เป็น ATR. เมื่อ occupation imbalance สูง รอแท่งกวาด recent edge
พร้อม rejection wick และเคลื่อนกลับหา anchor ก่อน fade.

ผล Backtest M5, spread0.20, 0.01 lot:

| Window | Signals | Closed | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน | 30 | 30 | 0 | 6.67% | +38.78 | +0.64 | +19.39 | 1.94 | 26.34 |
| 2026-H1 | 77 | 77 | 0 | 2.60% | +47.34 | +0.26 | +7.89 | 1.40 | 85.35 |
| 2025-H2 WF | 65 | 65 | 0 | 0.00% | -70.25 | -0.38 | -11.71 | 0.00 | 70.25 |

rolling ล่าสุดบวก +57.66 แต่ WF ไม่มี TP จาก65ดีลและ H1 DD สูงกว่า net
จึงเป็น regime-local exhaustion ไม่ใช่ cross-window edge. ไม่ tune occupation
หรือ rejection gates เข้าหา recent winners และเดินหน้า S351

## S351 — Price-Bridge Late-Acceleration Release 9R

ไฟล์: `strategy351.py`

Edge: normalize close path ให้เริ่ม0และจบ1 แล้ววัด mean deviation จาก
endpoint chord. Path ที่ค้างหลังเส้น chord ก่อนเร่งตามทันช่วงท้ายมี negative
bridge area จึงแปลงเป็น positive acceleration score. เทียบ recent score กับ
median ของ equal-size disjoint baseline blocks แล้วรับเฉพาะ tail progress,
path efficiency และ closed release ที่ยืนยัน direction เดียวกัน.

Optimized default M5, spread0.20, 0.01 lot:

| Window | Signals | Closed | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน ถึง 2026-07-20 | 15 | 15 | 0 | 33.33% | +297.98 | +4.88 | +148.99 | 12.44 | 17.83 |
| 2026-H1 | 33 | 33 | 0 | 12.12% | +221.79 | +1.23 | +36.96 | 4.39 | 39.67 |
| 2025-H2 WF | 50 | 50 | 0 | 8.00% | +150.93 | +0.82 | +25.16 | 5.51 | 19.84 |

ล็อก `BASELINE_BARS=80`, `RECENT_BARS=20`, acceleration/jump `.10/.06`,
tail5/progress.30, path efficiency.26, release body.80ATR, session15–23,
`TP_RR=9.0` และ `BE_RR=.05`.

Optimization audits:

- baseline 8R บวก +187.47/+93.22/+122.66 ใน recent/H1/WF. BUY และ
  SELL ต่างมี TP/net บวกข้ามช่วง จึงคงสองทิศ
- RR9 เพิ่มทุกหน้าต่างโดยรักษา4/3/5 TP; RR10 ทำ WF เสียหนึ่ง TPและ
  netลด จึงเลือก9R ก่อน cliff
- BE.05 ให้ recent/H1 เท่า .08 และเพิ่ม WF netเล็กน้อย; .04–.05 เป็น
  plateau จึงเลือก.05
- path efficiency .22→.26 เพิ่มทุกหน้าต่างและลด DD พร้อมรักษา TP;
  .30 ทำ recent/H1/WF เสีย winnerอย่างละหนึ่ง จึงเลือก.26
- release body .72→.80 เพิ่ม net/ลด DD ทุกหน้าต่างและรักษา TP;
  .90 ทำ recent/H1 เสีย winnerจำนวนมาก จึงเลือก.80 ก่อน cliff
- acceleration .12 และ jump .08 ไม่เพิ่มผล; tail progress .40 ลด H1 DD
  แต่ทำ WF เสียหนึ่ง TP จึงคง `.10/.06/.30`
- recent18 ทำ H1 เกือบหมด edge; recent22 เพิ่ม recent/H1 แต่ทำ WF
  เสีย2 TP จึงคง20
- baseline40 เสีย H1 winner. Baseline80/100 เป็น plateau ที่บวกครบ;
  80 ให้ net สูงกว่าทุกหน้าต่างและใช้ lookback สั้นกว่าจึงเลือก80.
  Baseline70/90 ที่หาร recent20 ไม่ลงตัวทำ disjoint-block alignment แย่
- tail4 เสีย H1 winner, tail6 ไม่เพิ่มผล จึงคง5
- session14–24 เพิ่ม H1 winnerแต่ลด recent/WF และเพิ่ม DD จึงคง15–23
- spread0.50 ยังบวก +293.48/+211.89/+135.93 ใน recent/H1/WF
  โดยรักษา TP count เดิม

Rolling 2 เดือนถึง 2026-07-29 มี18ดีล, 3 TP, WR16.67%,
Net +177.35, +2.91/day, +88.68/month, PF5.66, DD17.83. รวม WF ต่อ H1
ตามเวลาได้83ดีล, 8 TP, Net +372.72, DD40.47, return/DD9.21.
Risk distance อยู่1.41–15.06 USD, median6.37 USD ที่0.01 lot.

H1 exact timestamp overlap จาก33ดีลคือ S332=7, S333=6, S334=16,
S339=10, S346=1 และ S349=0. Price-bridge source จึงเพิ่ม diversification
จาก distribution-shift survivors S346/S349 ได้ชัด แม้ overlap ปานกลางกับ
S334. หลัง direction, payoff, BE, acceleration/tail/path/release gates,
baseline/recent windows, session, latest, spread และ overlap audits ไม่พบ
robust improvement ต่อ จึงปิด optimization และเริ่ม S352

## S352 — Price-Bridge Early-Displacement Exhaustion Fade 8R

ไฟล์: `strategy352.py`

Edge hypothesis: falsification complement ของ S351 โดยหา path ที่เคลื่อนนำ
endpoint chord ตั้งแต่ต้นแล้วชะลอช่วงท้าย เทียบ deceleration กับ baseline
blocks ก่อน fade ด้วยแท่งปิดกลับทิศและ rejection wick.

ผล Backtest มาตรฐาน 2 เดือน, M5, spread0.20, 0.01 lot:

| Signals | Closed | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 18 | 18 | 0 | 0.00% | -12.12 | -0.20 | -6.06 | 0.00 | 12.12 |

ไม่มี TP จึงยืนยันว่า edge ของ bridge family อยู่ฝั่ง late acceleration
continuation ไม่ใช่ early-displacement fade. ไม่ tune deceleration/rejection
gates เข้าหา sample และเดินหน้า S353

## S353 — Haar-Wavelet Coarse-Energy Coherence Release 8R

ไฟล์: `strategy353.py`

Edge hypothesis: ใช้ orthonormal Haar transform บน closed returns แล้วหาร
พลังงานของ final approximation coefficient ด้วย total return energy เพื่อวัด
สัดส่วน coherent directional drift ต่อ high-frequency detail. Recent coherence
ต้องสูงกว่า absolute floor และ median ของ equal-size baseline blocks.

ผล Backtest มาตรฐาน 2 เดือน, M5, spread0.20, 0.01 lot:

| Signals | Closed | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 1 | 0 | 0.00% | -0.20 | -0.00 | -0.10 | 0.00 | 0.20 |

coarse-energy shift มี sample/payoff ไม่พอและดีลเดียวจบ BE หลัง spread.
ไม่ลด coherence/jump gates เพื่อสร้าง sample ย้อนหลังและเดินหน้า S354

## S354 — Haar Finest-Detail Energy-Compression Release 8R

ไฟล์: `strategy354.py`

Edge hypothesis: วัดสัดส่วน total return energy ที่อยู่ใน first-level Haar
details. หาก recent finest-scale share ลดจาก median baseline blocks แปลว่า
adjacent-return noise ถูกกดและพลังงานย้ายไป slower scales ก่อน directional
path/release โดยไม่ต้องผ่าน rare final-coarse coherence แบบ S353.

ผล Backtest มาตรฐาน 2 เดือน, M5, spread0.20, 0.01 lot:

| Signals | Closed | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 18 | 18 | 0 | 5.56% | -6.95 | -0.11 | -3.47 | 0.82 | 30.53 |

detail compression เพิ่ม sampleและมีหนึ่ง TP แต่ expectancy/PF ติดลบและ DD
สูงกว่า payoff จึงไม่ใช่ survivor. ไม่ tune wavelet gates เข้าหา winnerเดียว
และยุติสาย Haar ก่อนเดินหน้า S355

## S355 — Arcsine Extremum-Time Migration Release 8R

ไฟล์: `strategy355.py`

Edge: วัดตำแหน่งเชิงเวลาของ adverse/favorable extrema ภายใน closed
price path ตามแนวคิด arcsine extremum timing. รับเฉพาะโครงสร้างที่ adverse
extreme เกิดต้นหน้าต่าง ก่อนราคาค้นพบ favorable extreme ใกล้ปลายหน้าต่าง
และ chronological span กระโดดจาก median ของ equal-size baseline blocks.
จากนั้นต้องมี directional path efficiency และแท่ง release ปิดยืนยันทางเดียวกัน.

Optimized default M5, spread0.20, 0.01 lot:

| Window | Signals | Closed | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน ถึง 2026-07-20 | 18 | 18 | 0 | 11.11% | +85.55 | +1.40 | +42.77 | 4.82 | 9.06 |
| 2026-H1 | 46 | 46 | 0 | 6.52% | +188.24 | +1.04 | +31.37 | 6.21 | 18.03 |
| 2025-H2 WF | 80 | 80 | 0 | 7.50% | +113.29 | +0.62 | +18.88 | 2.98 | 20.16 |

ล็อก baseline72/recent24, favorable time≥.75, adverse time≤.20,
span/jump≥.45/.15, path efficiency≥.30, release body≥.72ATR,
session15–23, `TP_RR=8.0` และ `BE_RR=.05`.

Optimization audits:

- baseline เดิม `.40/.22/BE.08` บวก +65.17/+126.11/+57.78
  ใน recent/H1/WF. ลด adverse-time gate ถึง.20 และเพิ่ม efficiency ถึง.30
  รักษา2/3/6 TP พร้อมเพิ่ม net ทุกหน้าต่าง; adverse.10 หรือ efficiency.34
  เริ่มทำ winner หาย จึงเลือกค่าก่อน cliff
- BE.05 เพิ่มทุกหน้าต่างเทียบ .08 โดยไม่เสีย TP; RR9 ทำ H1/WF
  winner หาย จึงคง8R
- BUY-only เพิ่ม recent แต่ทำ combined net/DD แย่ลง และทั้ง BUY/SELL
  มี TP ข้ามช่วง จึงคงสองทิศ
- release body.80 ทำ WF เสีย2 TP; span jump.20 แย่ลง; net-move.80
  ไม่เพิ่ม H1 จึงคง `.72/.15/.60`
- baseline96 เพิ่ม H1 เล็กน้อยเป็น +191.16 แต่ลด recent/WF เหลือ
  +72.41/+85.53 และ latest เหลือ +11.79 จึงคง72. recent20/28 และ
  baseline80/84 ไม่ให้ robust improvement
- session14–24 เพิ่ม H1 แต่เพิ่ม DD และ exposure พร้อมยังไม่ยืนยัน
  ข้ามช่วง จึงคง15–23
- spread0.50 ยังบวก +80.15/+174.44/+89.29 ใน recent/H1/WF
  โดยรักษา TP count 2/3/6 เดิม

Rolling 2 เดือนถึง 2026-07-29 มี17ดีล, 1 TP, WR5.88%,
Net +24.93, +0.41/day, +12.47/month, PF2.82, DD8.09. รวม WF ต่อ H1
ตามเวลาได้126ดีล, 9 TP, Net +301.53, DD23.46, return/DD12.85.
Risk distance อยู่1.44–15.87 USD, median5.18 USD ที่0.01 lot.

H1 exact timestamp overlap จาก46ดีลคือ S346=3, S349=1 และ S351=6.
เมื่อเพิ่ม S355 เข้ากับ S346/S349/S351 บน WF ต่อ H1, combined net
เพิ่ม +961.40→+1,262.93 และ return/DD เพิ่ม19.04→19.84 แม้ DD
เพิ่ม50.50→63.66. Extremum-time source จึงให้ diversification เพิ่มจาก
distribution-shift และ price-bridge survivors. หลัง direction, payoff, BE,
time/path/release gates, windows, session, latest, spread และ overlap audits
ไม่พบ robust improvement ต่อ จึงปิด optimization และเริ่ม S356

## S356 — Markov Sign-Entropy Compression Release 8R

ไฟล์: `strategy356.py`

Edge hypothesis: แปลงเครื่องหมายของ closed returns เป็น two-state Markov
chain แล้ววัด conditional transition entropy. เมื่อ recent entropy ลดจาก
median ของ disjoint baseline blocks พร้อม same-sign persistence, directional
occupation, path efficiency และ closed release ทางเดียวกัน จึงตามภาวะ
auction ที่ลำดับทิศทางเริ่มคาดเดาได้มากขึ้น.

ผล Backtest M5, spread0.20, 0.01 lot:

| Window | Signals | Closed | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน | 6 | 6 | 0 | 0.00% | -19.10 | -0.31 | -9.55 | 0.00 | 19.10 |
| 2026-H1 | 14 | 14 | 0 | 0.00% | -9.46 | -0.05 | -1.58 | 0.00 | 9.46 |
| 2025-H2 WF | 31 | 31 | 0 | 6.45% | +31.22 | +0.17 | +5.20 | 2.87 | 15.33 |

recent และ H1 ไม่มี TP แม้ WF มี2 TPและบวก แสดงว่า Markov sign
compression continuation ไม่อยู่รอดข้าม regime. ไม่ลด entropy/persistence
gatesหรือเลือกเฉพาะ WF winners ย้อนหลัง และเดินหน้า S357

## S357 — Directional Displacement-Concentration Release 8R

ไฟล์: `strategy357.py`

Edge hypothesis: วัดสัดส่วน favorable displacement ที่กระจุกอยู่ใน top-3
closed returns. หาก concentration สูงและกระโดดจาก baseline แปลว่ามี
institutional-sized impulses จำนวนน้อยครองการค้นพบราคา ก่อนตาม closed
release ทางเดียวกัน.

ผล Backtest M5, spread0.20, 0.01 lot:

| Window | Signals | Closed | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน | 15 | 14 | 0 | 0.00% | -35.97 | -0.59 | -17.98 | 0.00 | 35.97 |
| 2026-H1 | 28 | 28 | 0 | 0.00% | -59.71 | -0.33 | -9.95 | 0.00 | 59.71 |
| 2025-H2 WF | 42 | 42 | 0 | 2.38% | -3.83 | -0.02 | -0.64 | 0.89 | 22.94 |

recent/H1 ไม่มี TP และ WF มีเพียง1 TPแต่ยังติดลบ จึงหักล้างสมมติฐานว่า
top-k impulse concentration ให้ continuation ที่8R. ไม่ tune ตาม winnerเดียว
และเดินหน้า S358

## S358 — SELL-Only Variance-Ratio Trend-Emergence Release 12R

ไฟล์: `strategy358.py`

Edge: ใช้ Lo–MacKinlay-style overlapping variance ratio ที่ horizon 4
เปรียบเทียบ recent24 กับ median ของ disjoint baseline96 blocks. ค่า VR>1
และกระโดดจาก baseline บอกว่า multi-bar displacement โตเร็วกว่าความแปรปรวน
ของ one-bar return หรือมี positive serial dependence. รับเฉพาะ SELL ที่มี
directional path และ closed release ยืนยัน พร้อม dynamic structure/ATR SL.

Optimized default M5, spread0.20, 0.01 lot:

| Window | Signals | Closed | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน ถึง 2026-07-20 | 4 | 4 | 0 | 25.00% | +100.65 | +1.65 | +50.32 | 9.50 | 11.64 |
| 2026-H1 | 13 | 13 | 0 | 7.69% | +97.91 | +0.54 | +16.32 | 7.72 | 14.38 |
| 2025-H2 WF | 29 | 29 | 0 | 3.45% | +115.51 | +0.63 | +19.25 | 14.98 | 8.06 |

ล็อก baseline96/recent24, horizon4, VR≥1.15, jump≥.15,
path efficiency≥.20, release body/range≥.72/.80ATR, SELL-only,
session15–23, `TP_RR=12.0` และ `BE_RR=.05`.

Optimization audits:

- baseline สองทิศ8R บวก +50.75/+39.23/+41.24 ใน recent/H1/WF.
  BUY-only ไม่มี TP ใน recent/H1 และติดลบ -12.34/-21.12/-25.78;
  SELL-only รักษา TP อย่างน้อยหนึ่งตัวทุกช่วงและเพิ่ม net/DD จึงปิด BUY
- RR8→12 เพิ่มทุกหน้าต่างโดยรักษา TP; RR13 ทำ WF TP หายทั้งหมด
  จึงเลือก12R ก่อน payoff cliff
- BE.03–.05 เป็น plateau; .08 ลด WF +115.51→+108.34 และเพิ่ม DD,
  .12 แย่ลงอีก จึงเลือก.05
- VR1.25, efficiency.22–.26, body.80 หรือ range1.0–1.2 สามารถตัด
  BE/SL และเพิ่ม netราว $11–15 แต่ทำ recent sample ลด4→1–2 และ
  H1 ลด13→2–4. การซ้อน gates เหลือเพียง1ดีล recent จึงปฏิเสธ
  curve-fit และคง baseline gates ที่มี breadth สูงกว่า
- horizon2–4 รักษา winners แต่ q2 ร่วมกับ gate เข้มทำ sample collapse;
  q5 ไม่มี TP ทุกหน้าต่าง จึงคง horizon4 ที่เป็น formulation เดิม
- range1.30, body.85, close fraction.85 หรือ efficiency.30 ทำ
  recent/H1 winner หาย จึงไม่เลือกค่าบริเวณ cliff
- baseline72/120 ให้ recentเท่าเดิมแต่ลด WF และเพิ่ม DD;
  recent20/baseline80 เพิ่ม noiseและลด H1/WF จึงคง96/24
- spread0.50 ยังบวก +99.45/+94.01/+106.81 ใน recent/H1/WF
  และรักษา TP countเดิม

Rolling 2 เดือนถึง 2026-07-29 มี8ดีล, 1 TP, WR12.50%,
Net +99.85, +1.64/day, +49.92/month, PF8.90, DD12.44. รวม WF ต่อ H1
ตามเวลาได้42ดีล, 2 TP, Net +213.42, DD14.58, return/DD14.64.
Risk distance อยู่1.63–12.87 USD, median5.06 USD ที่0.01 lot.

H1 exact timestamp overlap จาก13ดีลคือ S346=1, S349=0, S351=2 และ
S355=0. เมื่อเพิ่ม S358 เข้ากับ S346/S349/S351/S355 บน WF ต่อ H1,
combined net เพิ่ม +1,262.93→+1,476.35 และ return/DD เพิ่ม19.84→21.87
แม้ DD เพิ่ม63.66→67.52. Variance-ratio SELL source จึงช่วย diversify
จาก distribution shift, price bridge และ extremum timing ได้. หลัง direction,
payoff, BE, VR/path/release gates, horizons, windows, latest, spread และ
overlap audits ไม่พบ robust improvement ที่คุ้มกับ sample breadth ต่อ
จึงปิด optimization และเริ่ม S359

## S359 — Bipower Jump-Variation Directional Release 8R

ไฟล์: `strategy359.py`

Edge: แยก discontinuous return energy ออกจาก continuous volatility ด้วย
realized variance เทียบ bipower variation. Recent jump-share ต้องสูงกว่า
absolute floor และเพิ่มจาก median ของ disjoint baseline blocks พร้อม
squared-return directional energy, net path และ closed release ไปทางเดียวกัน.
จึงจับช่วงที่ราคาไม่ได้เพียงผันผวนต่อเนื่อง แต่มี directional jump component.

Optimized default M5, spread0.20, 0.01 lot:

| Window | Signals | Closed | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน ถึง 2026-07-20 | 24 | 23 | 0 | 4.35% | +21.36 | +0.35 | +10.68 | 1.64 | 31.85 |
| 2026-H1 | 54 | 54 | 0 | 7.41% | +246.68 | +1.36 | +41.11 | 5.07 | 17.11 |
| 2025-H2 WF | 76 | 76 | 0 | 3.95% | +59.47 | +0.32 | +9.91 | 2.56 | 13.34 |

ล็อก baseline100/recent20, jump share≥.18, increase≥.16,
directional energy≥.24, efficiency≥.20, release body/range≥.72/.80ATR,
session15–23, `TP_RR=8.0` และ `BE_RR=.02`.

Optimization audits:

- baseline `.08/BE.08` บวก +20.56/+214.11/+7.18 ใน recent/H1/WF.
  เพิ่ม jump-share increase ถึง.16 และลด BE ถึง.02 เพิ่ม H1/WF
  พร้อมรักษา1/4/3 TP; BE.02–.03 เป็น plateau ใน recent/H1 แต่ .02
  เพิ่ม WF และลด DD
- BUY-only ช่วย recent/WF เล็กน้อยแต่ลด H1 +214.11→+150.11;
  SELL มี H1 TPและเพิ่ม combined net จึงคงสองทิศ
- RR9 ทำ recent TP หาย; RR7 เพิ่ม WF TP 3→4 แต่ลด recent/H1 และ
  combined H1+WF จึงคง8R
- increase.20 ทำ H1 เสีย2 TP; .24 ทำ recent TP หาย จึงเลือก.16
  ก่อน cross-window degradation
- jump share.22/.25 เพิ่ม WF แต่ทำ H1 เสีย2 TPและลด netมาก;
  directional energy.40, path efficiency.24, body.80 ต่างเสีย winner
  ในอย่างน้อยหนึ่งหน้าต่าง จึงคง baseline gates
- baseline100 รักษา trade/winner breadth เท่า80 แต่เพิ่ม WF
  +50.41→+59.47 และลด DD; baseline120/140 ลด WF, baseline60
  ลด H1. recent18/24 ทำ recent TP หาย จึงเลือก100/20
- spread0.50 ยังบวก +14.46/+230.48/+36.67 ใน recent/H1/WF
  โดยรักษา TP countเดิม

Rolling 2 เดือนถึง 2026-07-29 มี24ดีล, 1 TP, WR4.17%,
Net +16.76, +0.27/day, +8.38/month, PF1.44, DD37.05. รวม WF ต่อ H1
ตามเวลาได้130ดีล, 7 TP, Net +306.15, DD17.11, return/DD17.89.
Risk distance อยู่1.41–15.51 USD, median5.31 USD ที่0.01 lot.

H1 exact timestamp overlap จาก54ดีลคือ S346=4, S349=3, S351=8,
S355=11 และ S358=1. เมื่อเพิ่ม S359 เข้ากับ S346/S349/S351/S355/S358
บน WF ต่อ H1, combined net เพิ่ม +1,476.35→+1,782.50 และ
return/DD เพิ่ม21.87→23.61 แม้ DD เพิ่ม67.52→75.50. Jump-variation
source จึงเพิ่ม portfolio breadth โดย overlap กับ S358 ต่ำมาก. หลัง direction,
payoff, BE, jump/path/release gates, windows, latest, spread และ overlap
audits ไม่พบ robust improvement ต่อ จึงปิด optimization และเริ่ม S360

## S360 — Realized-Semivariance Exhaustion Reversal 8R

ไฟล์: `strategy360.py`

Edge hypothesis: แยก upside/downside realized semivariance แล้วหา recent
energy share ที่เอียงสุดขั้วและเพิ่มจาก baseline blocks ก่อน fade ฝั่ง dominant
energy ด้วย closed reversal candle, directional close และ rejection wick.

ผล Backtest M5, spread0.20, 0.01 lot:

| Window | Signals | Closed | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน | 19 | 19 | 0 | 5.26% | +33.07 | +0.54 | +16.53 | 10.19 | 3.60 |
| 2026-H1 | 52 | 52 | 0 | 1.92% | -21.89 | -0.12 | -3.65 | 0.63 | 56.36 |
| 2025-H2 WF | 57 | 57 | 0 | 1.75% | +39.08 | +0.21 | +6.51 | 1.97 | 20.27 |

แม้ recent/WF บวก แต่ H1 ติดลบและ DD สูงกว่า payoff มาก จึงยืนยันว่า
semivariance exhaustion fade เป็น regime-local ไม่ใช่ cross-window survivor.
ไม่ tune dominance/shift/rejection gates เข้าหา recent winner และเดินหน้า S361

## S361 — Rogers–Satchell Drift-Efficiency Release 7R

ไฟล์: `strategy361.py`

Edge: คำนวณ directional log-price drift เทียบ Rogers–Satchell intrabar
variance ซึ่งใช้ OHLC และยังประมาณ volatility ได้ภายใต้ non-zero drift.
Recent drift-to-volatility efficiency ต้องสูงกว่า absolute floor และเพิ่มจาก
median ของ disjoint baseline blocks พร้อม path efficiency และ closed release
ทางเดียวกัน จึงแยก directional price discovery ออกจาก noisy range expansion.

Optimized default M5, spread0.20, 0.01 lot:

| Window | Signals | Closed | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน ถึง 2026-07-20 | 65 | 65 | 0 | 10.77% | +283.66 | +4.65 | +141.83 | 4.54 | 40.94 |
| 2026-H1 | 151 | 151 | 0 | 6.62% | +450.68 | +2.49 | +75.11 | 4.26 | 31.60 |
| 2025-H2 WF | 210 | 210 | 0 | 5.71% | +235.89 | +1.28 | +39.32 | 2.71 | 46.72 |

ล็อก baseline60/recent20, RS efficiency≥.82, increase≥.15,
path efficiency≥.20, release body/range≥.72/.80ATR, session15–23,
`TP_RR=7.0` และ `BE_RR=.02`.

Optimization audits:

- baseline8R บวก +235.04/+357.53/+63.99 ใน recent/H1/WF.
  BUY และ SELL ต่างมี TP/net บวกครบช่วง จึงคงสองทิศ
- RR7+BE.05 เพิ่มทุกหน้าต่างและ TP เป็น7/10/11; RR9 เสีย recent/H1
  winners. BE.02 เพิ่มต่อเป็น +277.24/+421.33/+139.21 เทียบ baseline80;
  BE.01 ทำ WF เสียหนึ่ง TPและลด net จึงเลือก.02 ก่อน cliff
- RS floor .55→.82 เพิ่มทุกหน้าต่างและรักษา7/10/11 TP; .84–.85
  ทำ WF เสีย winner จึงเลือก.82 ก่อน threshold cliff
- increase.20, path.24 และ body.76/.80 ทำ winner หายในอย่างน้อยหนึ่ง
  หน้าต่าง แม้บางค่าลด DD จึงคง `.15/.20/.72`
- baseline60 เพิ่ม recent/H1/WF เป็น +283.66/+450.68/+235.89,
  เพิ่ม WF TP 11→12 และลด DD เทียบ80. Baseline40 เสีย recent TP;
  baseline50/70 เพิ่ม H1 แต่ลด WF หรือเพิ่ม DD; baseline100 และ
  recent24 แย่ลง จึงเลือก60/20
- spread0.50 ยังบวก +264.16/+405.38/+172.89 ใน recent/H1/WF
  และรักษา TP countเดิม

Rolling 2 เดือนถึง 2026-07-29 มี68ดีล, 5 TP, WR7.35%,
Net +192.39, +3.15/day, +96.20/month, PF3.21, DD57.69. รวม WF ต่อ H1
ตามเวลาได้361ดีล, 22 TP, Net +686.57, DD46.72, return/DD14.70.
Risk distance อยู่1.39–15.87 USD, median5.50 USD ที่0.01 lot.

H1 exact timestamp overlap จาก151ดีลคือ S346=19, S349=5, S351=20,
S355=29, S358=4 และ S359=27. เมื่อเพิ่ม S361 เข้ากับ survivors เหล่านี้
บน WF ต่อ H1, combined net เพิ่ม +1,782.50→+2,469.07 และ
return/DD เพิ่ม23.61→26.04 แม้ DD เพิ่ม75.50→94.82. OHLC
drift-efficiency source จึงเพิ่ม portfolio payoff และ breadth อย่างมีนัย.
หลัง direction, payoff, BE, RS/path/release gates, windows, latest, spread
และ overlap audits ไม่พบ robust improvement ต่อ จึงปิด optimization
และเริ่ม S362

## S362 — Close-Location Entropy-Compression Release 10R

ไฟล์: `strategy362.py`

Edge: แปลงตำแหน่ง close ภายใน high-low เป็น CLV ระหว่าง -1 ถึง1,
แบ่งเป็น4 directional auction states แล้ววัด normalized Shannon entropy.
Recent entropy ต้องลดจาก median ของ baseline blocks พร้อม mean CLV,
net path และ closed release ไปทางเดียวกัน จึงจับการปิดซ้ำด้านเดียวอย่าง
เป็นระบบแทน diffuse/random candle closes.

Optimized default M5, spread0.20, 0.01 lot:

| Window | Signals | Closed | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน ถึง 2026-07-20 | 5 | 5 | 0 | 40.00% | +141.04 | +2.31 | +70.52 | 31.53 | 4.42 |
| 2026-H1 | 11 | 11 | 0 | 18.18% | +175.81 | +0.97 | +29.30 | 31.21 | 4.42 |
| 2025-H2 WF | 23 | 23 | 0 | 8.70% | +54.65 | +0.30 | +9.11 | 5.03 | 9.69 |

ล็อก baseline80/recent20, bins4, normalized entropy≤.92,
entropy drop≥.11, |mean CLV|≥.20, path efficiency≥.18,
session15–23, `TP_RR=10.0` และ `BE_RR=.05`.

Optimization audits:

- baseline8R บวก +111.04/+131.34/+26.33 ใน recent/H1/WF.
  BUY มี WF TP ส่วน SELL มี recent/H1 TP จึงคงสองทิศ
- RR9 และ10 เพิ่มทุกหน้าต่างโดยรักษา2/2/2 TP; RR11 ทำ H1
  เสียหนึ่ง TP จึงเลือก10R ก่อน payoff cliff
- BE.02–.05 เป็น plateau จึงเลือก.05 ที่ไม่ arm ไวเกินจำเป็น
- mean CLV .16→.20 เพิ่ม H1/WF และรักษา winners; .24 ทำ
  recent/H1 เสีย winner จึงเลือก.20 ก่อน cliff
- entropy drop .08→.11 เพิ่มทุกหน้าต่างและรักษา winners; .12
  ทำ H1 เสีย TP จึงเลือก.11 ก่อน cliff
- path.22 ลด noiseแต่ไม่เพิ่ม robustly. bins3/5 ทำ H1 ไม่มี TP,
  จึงคง path.18 และ bins4
- baseline60/100 ไม่เพิ่มทุกช่วง; recent18 ทำ H1 เสีย winner
  จึงคง80/20
- spread0.50 ยังบวก +139.54/+172.51/+47.75 ใน recent/H1/WF
  และรักษา TP countเดิม

Rolling 2 เดือนถึง 2026-07-29 เท่ากับ5ดีล, 2 TP, WR40.00%,
Net +141.04, +2.31/day, +70.52/month, PF31.53, DD4.42. รวม WF ต่อ H1
ตามเวลาได้34ดีล, 4 TP, Net +230.46, DD10.49, return/DD21.97.
Risk distance อยู่1.28–15.62 USD, median4.16 USD ที่0.01 lot.

H1 exact timestamp overlap จาก11ดีลคือ S346=4, S349=1, S351=2,
S355=3, S358=0, S359=2 และ S361=8. เมื่อเพิ่ม S362 เข้าพอร์ต,
combined net เพิ่ม +2,469.07→+2,699.53 และ return/DD เพิ่ม
26.04→26.08 แต่ overlap กับ S361 สูง จึงควรใช้เป็น high-conviction
confirmation/จำกัด weight มากกว่า independent full allocation.
หลัง direction, payoff, BE, CLV/entropy/path gates, bins, windows, latest,
spread และ overlap audits ไม่พบ robust improvement ต่อ จึงปิด optimization
และเริ่ม S363

## S363 — Directional Amihud-Illiquidity Expansion Release 8R

ไฟล์: `strategy363.py`

Edge: ประมาณ intraday illiquidity ด้วย absolute log return ต่อ tick volume
แบบ Amihud proxy. Recent mean ต้องสูงกว่า median ของ disjoint baseline
blocks พร้อม signed return-per-volume pressure, path efficiency และ closed
release ทางเดียวกัน จึงตามช่วงที่ราคาสามารถเคลื่อนมากต่อ displayed activity
หนึ่งหน่วย หรือมี directional displacement ในสภาพคล่องบาง.

Optimized default M5, spread0.20, 0.01 lot:

| Window | Signals | Closed | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน ถึง 2026-07-20 | 15 | 15 | 0 | 20.00% | +95.22 | +1.56 | +47.61 | 5.95 | 12.04 |
| 2026-H1 | 31 | 31 | 0 | 12.90% | +210.05 | +1.16 | +35.01 | 13.81 | 7.60 |
| 2025-H2 WF | 34 | 34 | 0 | 8.82% | +125.08 | +0.68 | +20.85 | 5.10 | 11.20 |

ล็อก baseline80/recent20, illiquidity ratio≥1.20,
directional pressure≥.20, path efficiency≥.22, release body≥.80ATR,
session15–23, `TP_RR=8.0` และ `BE_RR=.02`.

Optimization audits:

- baseline8R บวก +78.83/+193.32/+116.24 ใน recent/H1/WF.
  BUY และ SELL ต่างมี TP/net บวกข้ามช่วง จึงคงสองทิศ
- RR9 ทำ recent เสีย winner; RR7 ลดทุกหน้าต่าง จึงคง8R
- BE.01–.02 เป็น plateau และ .02 เพิ่ม H1/WF พร้อมลด DD เทียบ.08
  จึงเลือก.02
- body .72→.80 เพิ่มทุกหน้าต่างและลด recent DD 28.43→12.04
  โดยรักษา3/4/3 TP; .90 ทำ winner หายมาก จึงเลือก.80 ก่อน cliff
- path .18→.22 เพิ่ม H1/WF เล็กน้อยและรักษา winners; .24 ทำ
  recent/H1 เสีย TP จึงเลือก.22
- illiquidity ratio1.30 และ pressure.25 ลด winner/net; baseline60
  ทำ recent/WF เสีย TP, baseline100 ทำ WF เสีย TP และ recent24
  ลด breadth จึงคง1.20/.20 และ80/20
- spread0.50 ยังบวก +90.72/+200.75/+114.88 ใน recent/H1/WF
  และรักษา TP countเดิม

Rolling 2 เดือนถึง 2026-07-29 มี18ดีล, 2 TP, WR11.11%,
Net +60.58, +0.99/day, +30.29/month, PF3.27, DD19.45. รวม WF ต่อ H1
ตามเวลาได้65ดีล, 7 TP, Net +335.13, DD18.46, return/DD18.15.
Risk distanceอยู่2.15–15.62 USD, median5.82 USD ที่0.01 lot.

H1 exact timestamp overlap จาก31ดีลคือ S346=2, S349=0, S351=3,
S355=5, S358=0, S359=5, S361=19 และ S362=2. เมื่อเพิ่ม S363
เข้าพอร์ต, combined net เพิ่ม +2,699.53→+3,034.66 และ return/DD
เพิ่ม26.08→26.73 แม้ DD เพิ่ม103.51→113.51. Amihud source มี overlap
กับ S361 สูงแต่ต่างจาก S358/S362 ชัด จึงเพิ่ม payoff ได้แต่ควรคุม
correlated weight กับ OHLC drift family. หลัง direction, payoff, BE,
illiquidity/pressure/path/release gates, windows, latest, spread และ overlap
audits ไม่พบ robust improvement ต่อ จึงปิด optimization และเริ่ม S364

## S364 — Roll Implied-Spread Compression Release 8R

ไฟล์: `strategy364.py`

Edge hypothesis: ใช้ negative lag-1 covariance ของ closed returns ประมาณ
Roll implied spread. Recent spread proxy ต้องหดจาก median baseline blocks
ก่อน directional path และ closed release เพื่อเล่น liquidity restoration
ที่ bid-ask bounce ลดลง.

ผล Backtest M5, spread0.20, 0.01 lot:

| Window | Signals | Closed | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน | 33 | 33 | 0 | 6.06% | +39.45 | +0.65 | +19.73 | 2.49 | 14.92 |
| 2026-H1 | 71 | 71 | 0 | 7.04% | +274.43 | +1.52 | +45.74 | 3.50 | 48.39 |
| 2025-H2 WF | 49 | 49 | 0 | 0.00% | -39.18 | -0.21 | -6.53 | 0.00 | 39.18 |

WF ไม่มี TP จาก49ดีลและติดลบทั้งหมด แม้ recent/H1 บวก จึงยืนยันว่า
Roll-spread compression continuation เป็น regime-local. ไม่ tune covariance,
compression หรือ release gates เข้าหา recent/H1 winners และเดินหน้า S365

## S365 — Kyle Price-Impact Expansion Release 8R

ไฟล์: `strategy365.py`

Edge: ประมาณ Kyle-style price-impact slope โดยถดถอย closed returns
กับ signed square-root tick volume. Recent lambda ต้องสูงกว่า median ของ
disjoint baseline blocks พร้อม signed volume imbalance, net path และ
closed release ทางเดียวกัน จึงจับช่วงที่ order-flow proxy หนึ่งหน่วย
ขยับราคาได้แรงขึ้น.

Optimized default M5, spread0.20, 0.01 lot:

| Window | Signals | Closed | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน ถึง 2026-07-20 | 12 | 12 | 0 | 8.33% | +64.45 | +1.06 | +32.22 | 4.32 | 18.99 |
| 2026-H1 | 31 | 31 | 0 | 9.68% | +247.53 | +1.37 | +41.26 | 15.37 | 8.58 |
| 2025-H2 WF | 43 | 43 | 0 | 13.95% | +251.23 | +1.37 | +41.87 | 17.77 | 5.04 |

ล็อก baseline80/recent20, lambda ratio≥1.18,
signed root-volume imbalance≥.26, path efficiency≥.18,
session15–23, `TP_RR=8.0` และ `BE_RR=.01`.

Optimization audits:

- baseline8R บวก +38.51/+206.94/+210.55 ใน recent/H1/WF.
  BUY มี WF winners ส่วน SELL มี recent/H1 winners จึงคงสองทิศ
- RR9 ทำ WF เสีย winnerและ net; RR7 เพิ่ม recent/H1 แต่ลด
  combined H1+WF จึงคง8R
- BE.01–.02 เป็น plateau ใน recent/H1 และ .01 เพิ่ม WF
  พร้อมรักษา1/3/6 TP จึงเลือก.01
- imbalance .18→.26 เพิ่มทุกหน้าต่างและลด DD โดยรักษา winners;
  .28/.30 ทำ WF เสีย winner จึงเลือก.26 ก่อน cliff
- lambda1.30 ทำ recent winner หาย; 1.10 เพิ่ม noiseและลด net
  จึงคง1.18
- body.80 และ path.22 ทำ WF เสีย winner; baseline60/100 และ
  recent24 ทำ winner หายในอย่างน้อยหนึ่งหน้าต่าง จึงคง baseline
  body/path .72/.18 และ window80/20
- spread0.50 ยังบวก +60.85/+238.23/+238.33 ใน recent/H1/WF
  และรักษา TP countเดิม

Rolling 2 เดือนถึง 2026-07-29 มี15ดีล, 1 TP, WR6.67%,
Net +56.94, +0.93/day, +28.47/month, PF3.12, DD26.70. รวม WF ต่อ H1
ตามเวลาได้74ดีล, 9 TP, Net +498.76, DD8.58, return/DD58.13.
Risk distanceอยู่2.18–17.34 USD, median6.16 USD ที่0.01 lot.

H1 exact timestamp overlap จาก31ดีลคือ S346=7, S349=3, S351=2,
S355=5, S358=1, S359=7, S361=17, S362=3 และ S363=8. เมื่อเพิ่ม
S365 เข้าพอร์ต, combined net เพิ่ม +3,034.66→+3,533.42,
DDเพิ่มเพียง113.51→113.91 และ return/DD เพิ่ม26.73→31.02.
Kyle impact source จึงเพิ่ม risk-adjusted portfolio payoff ชัด แม้ overlap
กับ S361 ปานกลาง. หลัง direction, payoff, BE, lambda/imbalance/path/release
gates, windows, latest, spread และ overlap audits ไม่พบ robust improvement
ต่อ จึงปิด optimization และเริ่ม S366

## S366 — VPIN-Style Volume-Toxicity Release 9R

ไฟล์: `strategy366.py`

Edge: จัด signed tick volume ลง equal-volume buckets แล้วเฉลี่ย absolute
buy-sell imbalance ต่อ bucket เป็น VPIN-style toxicity proxy. Recent VPIN
ต้องสูงกว่า absolute floor และ median baseline พร้อม aggregate directional
volume, net path และ closed release ทางเดียวกัน.

Optimized default M5, spread0.20, 0.01 lot:

| Window | Signals | Closed | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน ถึง 2026-07-20 | 21 | 21 | 0 | 9.52% | +159.49 | +2.61 | +79.75 | 13.45 | 12.01 |
| 2026-H1 | 46 | 46 | 0 | 6.52% | +270.52 | +1.49 | +45.09 | 24.20 | 4.86 |
| 2025-H2 WF | 68 | 68 | 0 | 7.35% | +106.13 | +0.58 | +17.69 | 3.16 | 34.06 |

ล็อก baseline120/recent20, 4 volume buckets, VPIN≥.34,
VPIN ratio≥1.15, directional volume≥.34, path efficiency≥.18,
session15–23, `TP_RR=9.0` และ `BE_RR=.01`.

Optimization audits:

- baseline8R บวก +74.98/+61.45/+50.13 ใน recent/H1/WF.
  BUY และ SELL ต่างเพิ่ม netข้ามช่วง แม้ SELL ไม่มี WF TP จึงคงสองทิศ
- RR9 เพิ่มทุกหน้าต่างและรักษา2/2/5 TP; RR10 ทำ WF เสีย winner
  จึงเลือก9R ก่อน cliff
- BE.01 เพิ่ม H1/WF และลด DD เทียบ.02/.05 โดยรักษา winners
- directional volume .18→.34 เพิ่มทุกหน้าต่างและลด DD พร้อมรักษา
  winners; .38 ทำ WF เสีย TP จึงเลือก.34 ก่อน cliff
- VPIN.40, body.80, path.22 และ buckets5 ทำ winner หายในอย่างน้อย
  หนึ่งหน้าต่าง; buckets3 เพิ่ม H1แต่ทำ WF เสีย TP จึงคง `.34/.18`,
  body.72 และ4 buckets
- baseline100–140 เป็น plateau ที่เพิ่ม recent/H1 และรักษา WF TP.
  Baseline120 ให้ WF ดีสุดใน plateau; 160 เริ่มลด WF/เพิ่ม DD,
  baseline60 ทำ recent/H1 เสีย TP จึงเลือก120
- spread0.50 ยังบวก +153.19/+256.72/+85.73 ใน recent/H1/WF
  และรักษา TP countเดิม

Rolling 2 เดือนถึง 2026-07-29 มี24ดีล, 1 TP, WR4.17%,
Net +74.73, +1.23/day, +37.36/month, PF4.81, DD19.01. รวม WF ต่อ H1
ตามเวลาได้114ดีล, 8 TP, Net +376.65, DD34.06, return/DD11.06.
Risk distanceอยู่1.39–15.62 USD, median5.52 USD ที่0.01 lot.

H1 exact timestamp overlap จาก46ดีลคือ S346=11, S349=4, S351=8,
S355=9, S358=0, S359=10, S361=33, S362=4, S363=3 และ S365=15.
เมื่อเพิ่ม S366 เข้าพอร์ต, combined net เพิ่ม +3,533.42→+3,910.07
แต่ DDเพิ่ม113.91→126.81 และ return/DD ลด31.02→30.83. VPIN source
จึงมี standalone edge แต่ correlation สูงกับ S361/S365; ควรจำกัด weight
หรือใช้เป็น confirmation ไม่ใช่ full independent allocation. หลัง direction,
payoff, BE, VPIN/directional/path/release gates, buckets, windows, latest,
spread และ overlap audits ไม่พบ robust improvement ต่อ จึงปิด optimization
และเริ่ม S367

## S367 — Ordinal-Pattern Entropy-Compression Release 7R

ไฟล์: `strategy367.py`

Edge: แปลงลำดับราคาปิดซ้อนกันครั้งละ3แท่งเป็นหนึ่งใน6 ordinal
permutations แล้วคำนวณ normalized permutation entropy. Recent entropy
ต้องลดจาก median ของ disjoint baseline blocks พร้อม monotone-pattern
imbalance, net displacement, path efficiency และ closed release ทางเดียวกัน.
แหล่งข้อมูลนี้ไม่ใช้ tick volume จึงต่างเชิง feature จาก Kyle/VPIN แม้
release timing บางส่วนยังซ้ำกับ continuation family.

Optimized default M5, spread0.20, 0.01 lot:

| Window | Signals | Closed | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน ถึง 2026-07-20 | 41 | 41 | 0 | 9.76% | +155.39 | +2.55 | +77.70 | 3.25 | 30.06 |
| 2026-H1 | 69 | 69 | 0 | 7.25% | +199.46 | +1.10 | +33.24 | 3.29 | 39.65 |
| 2025-H2 WF | 106 | 106 | 0 | 11.32% | +265.60 | +1.44 | +44.27 | 5.18 | 27.94 |

ล็อก baseline80/recent20, entropy≤.88, entropy drop≥.07,
monotone imbalance≥.08, path efficiency≥.18, release close control≥.76,
session15–23, `TP_RR=7.0` และ `BE_RR=.02`.

Optimization audits:

- baseline8R บวก +109.31/+101.16/+203.26 ใน recent/H1/WF.
  BUY เด่นใน WF ส่วน SELL เด่นใน H1 จึงคงทั้งสองฝั่งเพื่อกระจาย regime
- RR7+BE.02 รักษา/เพิ่ม breadth เป็น4/4/11 TP และให้
  +161.57/+167.22/+224.85 ก่อน shape tuning; RR8–10 มี TP น้อยลง
  และ RR9–10 ลด WF จึงเลือก7R
- BE.01 เพิ่ม H1 แต่ลด WF; BE.02 รักษา recent, เพิ่ม WF และลด DD
  เทียบ default .08 จึงเลือก.02
- entropy drop .05→.07 เพิ่มทุกหน้าต่างพร้อมรักษา4/4/11 TP;
  .09 ทำ H1/WF เสีย winner จึงเลือก.07 ก่อน cliff. entropy max .88
  อยู่บน plateau ของ recent/H1 และตัดเพียง1 loser ใน WF
- close-control .74–.76 เป็น plateau ที่เพิ่ม H1/WF winners โดยไม่เสีย
  recent TP; เลือก .76 ซึ่งเป็นขอบเข้มของ plateau. ที่ .78 เสีย
  H1/WF winner และ .82 เสียทุกช่วง
- path .22/.26 และ body .80/.90 ช่วย recent/H1 แต่ทำ WF เสีย
  2–3 TP; monotone .12 ทำ recent เสีย TP จึงคง .18/.72/.08
- baseline60/100/120 และ recent16/24 ทำ TP หายในอย่างน้อยหนึ่งหน้าต่าง
  จึงคง80/20. net-move .40–.60 เป็น plateau จึงคงค่ากลาง .50
- spread0.50 ยังบวก +143.09/+178.76/+233.80 ใน recent/H1/WF
  และรักษา4/5/12 TP เดิม

Rolling 2 เดือนถึง 2026-07-29 มี43ดีล, 3 TP, WR6.98%,
Net +101.77, +1.67/day, +50.88/month, PF2.64, DD30.06. รวม WF ต่อ H1
ตามเวลาได้175ดีล, 17 TP, Net +465.06, DD39.65, return/DD11.73.
Risk distanceอยู่1.39–16.21 USD, median5.56 USD ที่0.01 lot.

H1 exact timestamp overlap จาก69ดีลคือ S346=10, S349=3, S351=12,
S355=11, S358=2, S359=10, S361=37, S362=4, S363=4, S365=12
และ S366=30. เมื่อเพิ่ม S367 เต็มน้ำหนักเข้าพอร์ต, combined net เพิ่ม
+3,910.07→+4,375.13 แต่ DDเพิ่ม126.81→142.20 และ return/DD ลดเล็กน้อย
30.83→30.77. แม้ ordinal entropy ไม่ใช้ volume แต่ release filter ทำให้
timing ซ้ำ continuation family สูง จึงควรใช้เป็น confirmation หรือจำกัด
weight ไม่ใช่ full independent allocation. Payload smoke ที่
2026-05-20 22:05 BKK คืน SELL entry4476.27, SL4482.14,
TP4435.18 และ RR7.0000. หลัง direction, payoff/BE, entropy/shape,
windows, latest, spread, overlap, portfolio และ payload audits ไม่พบ
robust improvement ต่อ จึงปิด optimization และเริ่ม S368

## S368 — Bipower-Variation Jump-Exhaustion Reversal 7R

ไฟล์: `strategy368.py`

Edge hypothesis: ใช้ realized bipower variation ประมาณ continuous return
variance แล้วหา closed candle ที่ squared log return สูงกว่า BPV หลังราคา
วิ่งทางเดียวกัน แต่มี wick/recovery ปฏิเสธปลาย jump จึง fade failed auction
โดยวาง SL หลัง event extreme และ TP7R.

ผล Backtest M5, spread0.20, 0.01 lot:

| Window | Signals | Closed | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน | 7 | 7 | 0 | 0.00% | -28.25 | -0.46 | -14.13 | 0.00 | 28.25 |
| 2026-H1 | 23 | 23 | 0 | 8.70% | +114.48 | +0.63 | +19.08 | 9.52 | 6.67 |
| 2025-H2 WF | 27 | 27 | 0 | 0.00% | -33.68 | -0.18 | -5.61 | 0.00 | 33.68 |

รุ่นเข้ม jump ratio4, wick≥.30/recovery≥.55 มีเพียง0/1/2ดีล.
Breadth audit ลด jump ratioเป็น3, wick/recoveryเป็น.15/.45,
event return/rangeเป็น.50/1.00ATR และทดสอบ pre-shock8/12แท่ง,
pre-gate0 รวมถึง jump ratio4 แล้วยังไม่มี TP ใน recent/WF. รุ่นกว้างสุด
wick/recovery .10/.40 ให้ sample7/23/27 แต่ recentและ WF ไม่มี TP
ขณะที่ H1 บวกจาก2 TP จึงเป็น regime-local reversal ชัดเจน. ไม่ tune
เข้าหา H1 winners และเดินหน้า S369

## S369 — Rogers–Satchell Directional Range-Control Release 26R

ไฟล์: `strategy369.py`

Edge: แยก Rogers–Satchell range-variance estimator เป็น upper/lower
excursion contributions. หาก lower contribution เด่น แปลว่าแท่งในหน้าต่าง
ปิดควบคุมใกล้ upper range อย่างต่อเนื่องและให้ bullish control; upper เด่น
ให้ bearish control. Recent absolute control ต้องขยายจาก median ของ
disjoint baseline blocks พร้อม net path และ closed release ทางเดียวกัน.

Optimized default M5, spread0.20, 0.01 lot:

| Window | Signals | Closed | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน ถึง 2026-07-20 | 6 | 6 | 0 | 16.67% | +271.84 | +4.46 | +135.92 | 272.84 | 0.80 |
| 2026-H1 | 19 | 19 | 0 | 5.26% | +269.24 | +1.49 | +44.87 | 75.79 | 3.00 |
| 2025-H2 WF | 22 | 22 | 0 | 13.64% | +281.35 | +1.53 | +46.89 | 21.51 | 10.24 |

ล็อก baseline80/recent20, RS control≥.20, control ratio≥1.20,
path efficiency≥.22, release body≥.80ATR, session15–23,
`TP_RR=26.0` และ `BE_RR=.01`.

Optimization audits:

- baseline8R บวก +75.78/+41.29/+51.14 ใน recent/H1/WF.
  SELL พยุง recent/H1 ส่วน BUY พยุง WF จึงคงทั้งสองฝั่งเพื่อกระจาย regime
- RR8→26 เพิ่ม net ทุกหน้าต่างและรักษา1/1/3 TP. RR27 ทำ recent/H1
  เหลือ0 TP และ WFเสีย1 TP ทันที จึงเลือก26R ก่อน cliff
- BE.01 เพิ่มทุกหน้าต่างและลด recent/H1 DD เทียบ .02/.05/.08/.12
  โดยรักษา TP breadth เดิม
- path .18→.22 เพิ่ม H1/WF, ลด DD และรักษา1/1/3 TP. path .14
  เพิ่ม noise จึงเลือก.22
- body .72→.80 เพิ่มทุกช่วงและลด DD พร้อมรักษา TP; .84 ทำ WF
  เสีย1 TP และ .88 ทำ recent/H1 เหลือ0 TP จึงเลือก.80 ก่อน cliff
- control .25/.30 ช่วย recent/H1 แต่ทำ WF เสีย winner; ratio1.30,
  close-control .85 ก็ทำ recent winner หาย จึงคง .20/1.20/.80
- baseline60 ลด WF, baseline100/120 ไม่เพิ่ม combined net,
  recent16 ทำ H1 แย่และ recent24 ทำ winner หาย จึงคง80/20.
  net-move .40–.60 เป็น plateau จึงคงค่ากลาง .50
- spread0.50 ยังบวก +270.04/+263.54/+274.75 ใน recent/H1/WF
  และรักษา1/1/3 TP เดิม

Rolling 2 เดือนถึง 2026-07-29 ให้ผลเท่า recent window: 6ดีล, 1 TP,
WR16.67%, Net +271.84, +4.46/day, +135.92/month, PF272.84, DD0.80.
รวม WF ต่อ H1 ตามเวลาได้41ดีล, 4 TP, Net +550.59, DD10.24,
return/DD53.77. Risk distanceอยู่1.28–13.39 USD, median5.96 USD
ที่0.01 lot.

H1 exact timestamp overlap จาก19ดีลคือ S346=1, S349=1, S351=4,
S355=2, S358=1, S359=4, S361=9, S362=2, S363=0, S365=2,
S366=8 และ S367=8. เมื่อเพิ่ม S369 เต็มน้ำหนักเข้าพอร์ต combined net
เพิ่ม +4,375.13→+4,925.72, DDเพิ่มเพียง142.20→142.40 และ
return/DD เพิ่ม30.77→34.59. Payload smoke ที่ 2026-06-04 19:05 BKK
คืน BUY entry4477.51, SL4471.56, TP4632.21 และ RR26.0000.
หลัง direction, payoff/BE, control/path/body/close gates, windows, latest,
spread, overlap, portfolio และ payload audits ไม่พบ robust improvement ต่อ
จึงปิด optimization และเริ่ม S370

## S370 — Garman–Klass Volatility-Energy Concentration Release 8R

ไฟล์: `strategy370.py`

Edge: คำนวณ Garman–Klass range variance ต่อแท่ง แล้วใช้ normalized
Herfindahl index วัดว่า recent volatility energy กระจุกในแท่งส่วนน้อยกว่า
baseline blocks หรือไม่. Variance-weighted candle direction, net path และ
closed release ต้องตรงกันก่อนตาม institutional volatility burst.

Optimized default M5, spread0.20, 0.01 lot:

| Window | Signals | Closed | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน ถึง 2026-07-20 | 11 | 10 | 0 | 10.00% | +44.28 | +0.73 | +22.14 | 2.44 | 29.65 |
| 2026-H1 | 19 | 19 | 0 | 21.05% | +278.38 | +1.54 | +46.40 | 22.46 | 10.17 |
| 2025-H2 WF | 22 | 22 | 0 | 4.55% | +7.55 | +0.04 | +1.26 | 1.43 | 17.07 |

ล็อก baseline80/recent20, normalized GK concentration≥.08,
concentration ratio≥1.20, directional energy≥.24, path efficiency≥.22,
session15–23, `TP_RR=8.0` และ `BE_RR=.01`.

Optimization audits:

- baseline BE.08 ให้ +43.68/+268.54/-8.86 ใน recent/H1/WF.
  BE.01/.02 ทำ WF กลับบวก +6.55 พร้อมเพิ่ม H1 และรักษา1/4/1 TP;
  เลือก .01 ที่ขอบต้นของ plateau
- RR9/10 เพิ่ม recent แต่ทำ H1 เสีย1 TP; RR7 ลดทุกช่วง จึงคง8R
- BUY เป็นตัวพยุง WF ส่วน SELL พยุง recent; H1 ได้กำไรจากทั้งสองฝั่ง
  จึงคงทั้ง BUY/SELL
- path .18→.22 เพิ่มทุกหน้าต่างและลด DD พร้อมรักษา TP.
  path .14 เพิ่ม noise จึงเลือก.22
- directional energy .22–.24 เป็น plateau ที่กรอง H1 loserหนึ่งดีล
  โดยไม่เปลี่ยน recent/WF; .26 ทำ H1 เสีย winner จึงเลือก.24 ก่อน cliff
- concentration .10/.12 และ body .80 ทำ WF winner หาย; ratio1.10–1.30
  ไม่เปลี่ยนผล, concentration .06/path .14/body .60 เพิ่ม noise
  จึงคง .08/1.20 และ body .72
- baseline60/100 ให้ผลเท่า80และ120เพิ่ม loser. recent16 เพิ่ม WF
  แต่ recent18ไม่ยืนยัน plateau; recent22/24 ทำ H1เสีย winner จึงคง20.
  net-move .40–.60 เป็น plateau จึงคงค่ากลาง .50
- spread0.50 ยังบวก +41.28/+272.68/+0.95 ใน recent/H1/WF
  และรักษา1/4/1 TP แม้ WF margin บางมาก

Rolling 2 เดือนถึง 2026-07-29 มี8ดีล, 1 TP, WR12.50%,
Net +44.68, +0.73/day, +22.34/month, PF2.48, DD29.85. รวม WF ต่อ H1
ตามเวลาได้41ดีล, 5 TP, Net +285.93, DD18.47, return/DD15.48.
Risk distanceอยู่2.28–12.34 USD, median7.83 USD ที่0.01 lot.

H1 exact timestamp overlap จาก19ดีลคือ S346=1, S349=0, S351=4,
S355=4, S358=4, S359=8, S361=12, S362=1, S363=3, S365=3,
S366=0, S367=1 และ S369=0. เมื่อเพิ่ม S370 เต็มน้ำหนักเข้าพอร์ต
combined net เพิ่ม +4,925.72→+5,211.65 แต่ DDเพิ่ม142.40→154.39
และ return/DD ลด34.59→33.76; แม้ timing ต่างจาก S366/S369 ชัด
แต่ควรใช้เป็น confirmation/จำกัดน้ำหนัก. Payload smoke ที่
2026-05-21 18:35 BKK คืน SELL entry4508.62, SL4518.51,
TP4429.49 และ RR8.0010. หลัง direction, payoff/BE,
concentration/energy/path/release gates, windows, latest, spread, overlap,
portfolio และ payload audits ไม่พบ robust improvement ต่อ จึงปิด
optimization และเริ่ม S371

## S371 — Realized-Skewness Tail-Asymmetry Release 8R

ไฟล์: `strategy371.py`

Edge: คำนวณ standardized realized skewness จาก closed log returns เพื่อจับ
directional heavy tail. Recent absolute skewness ต้องสูงกว่า floor และ median
ของ disjoint baseline blocks พร้อม sign, net displacement, path efficiency
และ closed release ทางเดียวกัน.

Optimized default M5, spread0.20, 0.01 lot:

| Window | Signals | Closed | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน ถึง 2026-07-20 | 43 | 42 | 0 | 11.90% | +148.23 | +2.43 | +74.12 | 2.86 | 35.34 |
| 2026-H1 | 109 | 109 | 0 | 6.42% | +212.11 | +1.17 | +35.35 | 2.48 | 49.48 |
| 2025-H2 WF | 143 | 143 | 0 | 6.99% | +194.90 | +1.06 | +32.48 | 3.77 | 25.45 |

ล็อก baseline60/recent20, absolute skewness≥.70, skewness ratio≥1.20,
path efficiency≥.22, release body≥.60ATR, close-control≥.85,
session15–23, `TP_RR=8.0` และ `BE_RR=.02`.

Optimization audits:

- baseline8R/BE.08 บวก +102.89/+88.58/+66.18 แต่ H1 DD135.34.
  BE.02 เพิ่มเป็น +109.53/+155.32/+111.16, ลด H1 DDเหลือ75.24
  และรักษา4/5/7 TP; BE.01 ให้ WFสูงกว่าเล็กน้อยแต่ H1 net/DDด้อยกว่า
- RR7 ลด recent/H1; RR9/10 ทำ recent/H1 เสีย winners จึงคง8R.
  BUY เด่นใน WF ส่วน SELL เด่น recent แต่สองฝั่งช่วย H1 จึงคงทั้งคู่
- skew .45→.70 และ path .18→.22 เพิ่มทุกช่วงพร้อมรักษา TP.
  path .26 ทำ recent/H1 เสีย winner; ratio1.30 ทำ recent/H1 เสีย winner
- close-control .85 เพิ่มทุกช่วงและลด DD. .88 ทำ winner หายทุกช่วง,
  .82 เพิ่ม WF แต่ลด recent/H1และเพิ่ม DD จึงเลือก.85
- body .72→.60 เพิ่ม H1/WF winners. เมื่อรวม skew/path/close แล้ว
  body .60 ให้5/7/9 TP; .65 เริ่มเสีย winners และ .50/.55 ลด WF
- ชุดรวม skew.70/path.22/body.60/close.85 ให้
  +147.45/+210.47/+163.14 ก่อน window tuning เทียบ baseline shape
  +109.53/+155.32/+111.16
- baseline60 เพิ่มทุกช่วงและเพิ่ม WF TP9→10. baseline40 มี combined
  netใกล้กันแต่ WF TPน้อยกว่าและ H1/WF DDสูงกว่า; 50/70 ไม่เป็น plateau,
  100ไม่เพิ่มผลรวม และ120ทำ WFเสีย2 winners จึงเลือก60
- recent16/24 ทำ winner หายในทุกช่วงอย่างน้อยหนึ่งตัว. net-move
  .40–.60 เป็น plateau จึงคง recent20 และ net .50
- spread0.50 ยังบวก +135.63/+179.41/+152.00 ใน recent/H1/WF
  และรักษา5/7/10 TP เดิม

Rolling 2 เดือนถึง 2026-07-29 มี42ดีล, 4 TP, WR9.52%,
Net +125.04, +2.05/day, +62.52/month, PF2.65, DD40.96. รวม WF ต่อ H1
ตามเวลาได้252ดีล, 17 TP, Net +407.01, DD51.68, return/DD7.88.
Risk distanceอยู่1.52–15.51 USD, median5.65 USD ที่0.01 lot.

H1 exact timestamp overlap จาก109ดีลคือ S346=4, S349=0, S351=12,
S355=16, S358=4, S359=26, S361=53, S362=3, S363=8, S365=4,
S366=12, S367=13, S369=7 และ S370=9. เมื่อเพิ่ม S371 เต็มน้ำหนัก
เข้าพอร์ต combined net เพิ่ม +5,211.65→+5,618.66 แต่ DDเพิ่ม
154.39→174.63 และ return/DD ลด33.76→32.17 จึงควรใช้เป็น
skewness confirmation/จำกัดน้ำหนัก. Payload smoke ที่
2026-05-20 19:20 BKK คืน BUY entry4496.05, SL4490.87,
TP4537.50 และ RR8.0019. หลัง direction, payoff/BE,
skewness/path/release gates, windows, latest, spread, overlap, portfolio
และ payload audits ไม่พบ robust improvement ต่อ จึงปิด optimization
และเริ่ม S372

## S372 — Realized-Kurtosis Directional Tail-Energy Release 8R

ไฟล์: `strategy372.py`

Edge: คำนวณ excess concentration ของ closed log returns ผ่าน realized
kurtosis แล้วเปรียบ recent window กับ median ของ disjoint baseline blocks.
Signed quartic energy ระบุว่าหางหนาเกิดจาก BUY หรือ SELL จริง ไม่ใช่เพียง
volatility สองทิศทาง ก่อนยืนยันด้วย net path และ closed release ทางเดียวกัน.

Optimized default M5, spread0.20, 0.01 lot:

| Window | Signals | Closed | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน ถึง 2026-07-20 | 43 | 42 | 0 | 7.14% | +115.08 | +1.89 | +57.54 | 2.80 | 42.34 |
| 2026-H1 | 94 | 94 | 0 | 6.38% | +293.34 | +1.62 | +48.89 | 3.12 | 59.93 |
| 2025-H2 WF | 116 | 116 | 0 | 6.90% | +185.39 | +1.01 | +30.90 | 5.33 | 13.40 |

ล็อก baseline60/recent20, realized kurtosis≥3.00, kurtosis ratio≥1.15,
directional quartic tail energy≥.50, path efficiency≥.22,
release body/range≥.60/.80ATR, close-control≥.80, session15–23,
`TP_RR=8.0` และ `BE_RR=.01`.

Optimization audits:

- baseline8R/BE.08 บวก +80.50/+229.85/+36.18 ใน recent/H1/WF.
  BE.01 รักษา recent เท่าเดิม, เพิ่ม H1/WF เป็น +270.35/+96.36
  และลด DD เป็น56.19/17.41. BE.02 ให้ H1 สูงกว่าเล็กน้อยแต่ WF ต่ำกว่า.
- RR7 ลด recent/H1 แม้เพิ่ม WF; RR9/10 ทำ recent/H1 เสีย winner
  จึงคง8R. BUY และ SELL พยุงคนละ regime จึงคงทั้งสองฝั่ง.
- path .18→.22 เพิ่ม net และลด DD ครบสามช่วงโดยรักษา TP.
  body .72→.60 เพิ่ม recent/WF winners; เมื่อนำมารวมกับ directional
  tail .50 ได้ +103.08/+281.00/+153.39 ก่อน window tuning.
- kurtosis floor3.50/4.50 และ ratio1.25/1.40 ทำ recent เสีย winner.
  close-control .85 ช่วย recent แต่ทำ H1/WF เสีย winner จึงคง .80.
- baseline60 เพิ่มเป็น +115.08/+293.34/+185.39 และเพิ่ม WF TP7→8
  โดยไม่เพิ่ม DD. baseline100/120 ลดผลรวม; recent16 ทำทุกช่วงแย่ลง
  และ recent24 ทำ H1 เสีย2 winners จึงเลือก60/20.
  net-move .40–.60 เป็น plateau จึงคงค่ากลาง .50.
- spread0.50 ยังบวก +102.48/+265.14/+150.59 ใน recent/H1/WF
  และรักษา3/6/8 TP เดิม.

Rolling 2 เดือนถึง 2026-07-29 มี41ดีล, 3 TP, WR7.32%,
Net +112.86, +1.85/day, +56.43/month, PF2.71, DD54.22. รวม WF ต่อ H1
ตามเวลาได้210ดีล, 14 TP, Net +478.73, DD59.93, return/DD7.99.
Risk distanceอยู่1.40–15.51 USD, median5.43 USD ที่0.01 lot.

H1 exact timestamp overlap จาก94ดีลคือ S346=3, S349=1, S351=7,
S355=16, S358=3, S359=31, S361=42, S362=1, S363=5, S365=8,
S366=11, S367=12, S369=5, S370=10 และ S371=64. แม้ overlap กับ
realized-skewness family สูง แต่เมื่อเพิ่ม S372 เต็มน้ำหนักเข้าพอร์ต,
combined net เพิ่ม +5,618.66→+6,097.39, DDลด174.63→131.08 และ
return/DD เพิ่ม32.17→46.52. Payload smoke ที่ 2026-06-30 17:30 BKK
คืน SELL entry4013.46, SL4019.07, TP3968.58, RR8.0000,
market order และ BE.01. หลัง direction, payoff/BE, kurtosis/tail/path/
release gates, windows, latest, spread, overlap, portfolio และ payload
audits ไม่พบ robust improvement ต่อ จึงปิด optimization และเริ่ม S373.

## S373 — Signed Amihud Liquidity-Impact Release 10R

ไฟล์: `strategy373.py`

Edge: วัด absolute log return ต่อ tick volume แบบ Amihud proxy แล้วเทียบ
recent window กับ median ของ disjoint baseline blocks. Signed price impact,
net displacement และ path efficiency ต้องไปทิศเดียวกัน ขณะที่ recent volume
ไม่ขยายตามราคา เพื่อจับ liquidity-vacuum repricing ก่อนตาม closed release
ด้วย SL หลัง event extreme.

Optimized default M5, spread0.20, 0.01 lot:

| Window | Signals | Closed | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน ถึง 2026-07-20 | 14 | 14 | 0 | 21.43% | +159.60 | +2.62 | +79.80 | 18.62 | 8.46 |
| 2026-H1 | 35 | 35 | 0 | 8.57% | +181.02 | +1.00 | +30.17 | 8.67 | 13.35 |
| 2025-H2 WF | 38 | 38 | 0 | 13.16% | +241.10 | +1.31 | +40.18 | 14.13 | 8.59 |

ล็อก baseline60/recent20, Amihud impact ratio≥1.10,
directional impact≥.15, recent volume ratio≤1.15, path efficiency≥.26,
release body/range≥.65/.80ATR, close-control≥.80, session15–23,
`TP_RR=10.0` และ `BE_RR=.05`.

Optimization audits:

- baseline8R ให้ +26.83/+87.38/+18.90 ใน recent/H1/WF ด้วย sample
  เพียง3/8/10ดีล. BE.01–.12 เป็น plateau เหมือนกันทุกช่วง จึงคงค่ากลาง.05.
- RR8→10 เพิ่มทุกช่วงและรักษา1/2/1 TP. RR11 ทำ H1 เสีย winnerครึ่งหนึ่ง
  ทันที และ RR20 ทำ WF เหลือ0 TP จึงเลือก10R ก่อน cliff.
- SELL พยุง recent ส่วน BUY พยุง WF และทั้งสองฝั่งทำกำไร H1
  จึงคง BUY/SELL.
- impact ratio1.25→1.10 และ directional impact.30→.15 เพิ่ม breadth.
  Local audit impact1.05 เพิ่ม noise/DD ขณะที่1.15/1.20 เริ่มเสีย TP;
  directional.10–.15 เป็น plateau แต่.10/.12 เพิ่ม H1 loser จึงเลือก.15.
- volume ratio cap1.15 จำเป็น: คลายเป็น2.0 เพิ่ม recent/H1 แต่ทำ WF
  เหลือ +13.64 และ DD14.75; จำกัด1.0 ทำ WF ไม่มี TP.
- path .22→.26 เพิ่ม net และลด DD ครบสามช่วงพร้อมรักษา3/3/5 TP.
  body.80 ทำ WF เสีย winner; close.85 ไม่เพิ่มผลรวม จึงคง.65/.80.
- baseline40/80/100 และ recent16/24 ไม่เพิ่มครบสามช่วง. recent24
  เพิ่ม recent แต่ทำ H1/WF เสีย winners; net-move .40–.60 เป็น plateau
  จึงคง baseline60/recent20/net.50.
- spread0.50 ยังบวก +155.40/+170.52/+229.70 ใน recent/H1/WF
  และรักษา3/3/5 TP เดิม.

Rolling 2 เดือนถึง 2026-07-29 มี15ดีล, 2 TP, WR13.33%,
Net +118.46, +1.94/day, +59.23/month, PF8.37, DD8.46. รวม WF ต่อ H1
ตามเวลาได้73ดีล, 8 TP, Net +422.12, DD13.75, return/DD30.70.
Risk distanceอยู่1.57–14.96 USD, median4.76 USD ที่0.01 lot.

H1 exact timestamp overlap จาก35ดีลคือ S346=2, S349=1, S351=6,
S355=0, S358=1, S359=4, S361=21, S362=1, S363=12, S365=4,
S366=1, S367=3, S369=0, S370=4, S371=11 และ S372=6.
เมื่อเพิ่ม S373 เต็มน้ำหนักเข้าพอร์ต combined net เพิ่ม
+6,097.39→+6,519.51, DDเพิ่มเพียง131.08→136.84 และ return/DD
เพิ่ม46.52→47.64. Payload smoke ที่ 2026-06-29 21:00 BKK คืน BUY
entry4050.63, SL4043.08, TP4126.14, RR10.0013, market order และ BE.05.
หลัง direction, RR cliff/BE, impact/directional/volume/path/release gates,
local plateau, windows, latest, spread, overlap, portfolio และ payload
audits ไม่พบ robust improvement ต่อ จึงปิด optimization และเริ่ม S374.

## S374 — Directional Volume-Participation Release 7R

ไฟล์: `strategy374.py`

Edge: กำหนดเครื่องหมายให้ tick volume ตาม closed close-to-close return
แล้ววัด signed participation imbalance. Recent directional volume ต้องสูงกว่า
absolute floor และ median ของ disjoint baseline blocks ขณะที่ aggregate
participation ไม่หดมากเกินไป. Net path และ closed release ต้องไปทิศเดียวกัน
ก่อนตาม institutional participation repricing. เป็น regime คู่ตรงข้ามกับ S373
ซึ่งจับ high price impact ใน liquidity ที่บางกว่า.

Optimized default M5, spread0.20, 0.01 lot:

| Window | Signals | Closed | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน ถึง 2026-07-20 | 18 | 18 | 0 | 16.67% | +184.27 | +3.02 | +92.14 | 16.80 | 9.06 |
| 2026-H1 | 49 | 49 | 0 | 8.16% | +263.71 | +1.46 | +43.95 | 15.93 | 14.46 |
| 2025-H2 WF | 58 | 58 | 0 | 12.07% | +202.76 | +1.10 | +33.79 | 7.06 | 11.71 |

ล็อก baseline60/recent20, directional volume≥.25,
directional-volume ratio≥1.60, aggregate-volume ratio≥.90,
path efficiency≥.26, release body/range≥.85/.80ATR,
close-control≥.80, session15–23, `TP_RR=7.0` และ `BE_RR=.01`.

Optimization audits:

- baseline8R/BE.05 ให้ +114.32/+183.90/-5.86 ใน recent/H1/WF.
  RR7 เพิ่ม TP เป็น3/4/6 และ BE.01 ทำ WF กลับบวก; ชุดรวมให้
  +164.02/+249.39/+60.22 พร้อมลด DD. RR9/10 ทำ WF เสีย winners
  และ BE.08/.12 เพิ่ม DD จึงเลือก7R/.01.
- BUY พยุง WF ขณะที่ BUY/SELL ต่างทำกำไรใน recent/H1 จึงคงทั้งสองฝั่ง.
- directional ratio1.20→1.60 และ path.22→.26 เพิ่ม Net/ลด DD
  ครบทุกช่วง; ratio1.80 และ path.28 เริ่มเสีย winners.
- aggregate-volume ratio1.05→.90 เพิ่ม H1/WF winners. Local audit
  .85–.90 เป็น recent plateau แต่.95/1.00 ทำ WF เสีย1–2 winners
  จึงเลือก.90 ก่อน cliff. ผลนี้ยังคง thesis ว่าต้องไม่มี volume contraction
  มากกว่า10% ไม่ได้ปิด participation gate.
- body .65→.85 เพิ่มทุกช่วงและลด DD. .82–.85 เป็น plateau;
  .88 ทำ recent/H1/WF เสีย winner อย่างละหนึ่งตัว จึงเลือก.85 ก่อน cliff.
  close-control.85 ทำ recent/H1 เสีย winners จึงคง.80.
- baseline40/80/100 และ recent16/24 ทำ recent/H1 เสีย winners.
  baseline100 ช่วย WF เล็กน้อยแต่ลดสองช่วงปัจจุบันมาก; net-move
  .40–.60 เป็น plateau จึงคง baseline60/recent20/net.50.
- spread0.50 ยังบวก +178.87/+249.01/+185.36 ใน recent/H1/WF
  และรักษา3/4/7 TP เดิม.

Rolling 2 เดือนถึง 2026-07-30 มี19ดีล, 2 TP, WR10.53%,
Net +119.02, +1.95/day, +59.51/month, PF8.30, DD14.31. รวม WF ต่อ H1
ตามเวลาได้107ดีล, 11 TP, Net +466.47, DD14.46, return/DD32.26.
Risk distanceอยู่1.69–15.31 USD, median5.89 USD ที่0.01 lot.

H1 exact timestamp overlap จาก49ดีลคือ S346=8, S349=3, S351=9,
S355=10, S358=1, S359=7, S361=35, S362=3, S363=4, S365=15,
S366=28, S367=26, S369=6, S370=1, S371=10, S372=12 และ S373=3.
เมื่อเพิ่ม S374 เต็มน้ำหนักเข้าพอร์ต combined net เพิ่ม
+6,519.51→+6,985.98, DDเพิ่มเพียง136.84→138.24 และ return/DD
เพิ่ม47.64→50.54. Payload smoke ที่ 2026-06-30 17:30 BKK คืน SELL
entry4013.46, SL4019.07, TP3974.19, RR7.0000, market order และ BE.01.
หลัง direction, payoff/BE, volume/directional-ratio/path/body/close gates,
local cliff, windows, latest, spread, overlap, portfolio และ payload audits
ไม่พบ robust improvement ต่อ จึงปิด optimization และเริ่ม S375.

## S375 — Volume-Impact Absorption Reversal 7R

ไฟล์: `strategy375.py`

Edge: หา auction ที่ tick volume ขยายแต่ absolute log return ต่อ volume
หดจาก median ของ disjoint baseline blocks ซึ่งตีความเป็น high effort /
weak price progress. Signed volume, net move และ path ต้องชี้ทิศ auction
ก่อนรอ closed rejection ที่มี wick ปฏิเสธ แล้ว fade สวนด้วย SL หลัง
rejection extreme. เป็น mean-reversion alpha ที่ต่างจาก S373/S374.

Optimized default M5, spread0.20, 0.01 lot:

| Window | Signals | Closed | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน ถึง 2026-07-20 | 10 | 10 | 0 | 20.00% | +121.22 | +1.99 | +60.61 | 21.07 | 6.04 |
| 2026-H1 | 59 | 59 | 0 | 5.08% | +73.44 | +0.41 | +12.24 | 1.90 | 62.52 |
| 2025-H2 WF | 79 | 79 | 0 | 7.59% | +78.99 | +0.43 | +13.17 | 2.28 | 18.18 |

ล็อก baseline60/recent20, impact contraction≤.85,
volume expansion≥1.10, directional volume≥.20, path efficiency≥.12,
pre-move≥.40ATR, rejection body/range≥.12/.80ATR, wick≥.30,
close-control≥.55, session15–23, `TP_RR=7.0` และ `BE_RR=.01`.

Optimization audits:

- baseline body.25/path.15/BE.05 มี0 TP/-5.44 ใน recent แม้ H1/WF
  บวก +14.21/+49.40. Breadth audit ทีละ gate พบ body.15 และ path.10
  ทำ recent กลับเป็น2 TP/+121.02 โดย H1/WF ยังบวก.
- impact contraction.70 ลด WF edgeเหลือ +12.02 และ interaction
  body/path/impact.70 ทำ WFเหลือ +4.44; impact.95/1.05 เพิ่ม recent
  losersโดยไม่มี TP จึงคง.85.
- ผ่อน directional volume.10 และ wick.20 เพิ่ม WF แต่ลด current/H1
  พร้อมเพิ่ม DD; wick.40 ทำ H1 ไม่มี TP จึงคง.20/.30.
- RR8/9 เพิ่ม recent/H1 แต่ทำ WF TP5→3 ทันที จึงคง7R.
  BE.01 เพิ่ม H1/WF และลด H1 DD; .01–.02 เป็น WF plateau
  และ recentไม่เปลี่ยน จึงเลือก.01.
- BUY พยุง recent/WF ส่วน SELL พยุง H1 จึงคงทั้งสองฝั่ง.
- local body.10–.15 รักษา recent/H1 winners; body.12 เพิ่ม WF TP5→6
  และลด WF DD. path.12 กรอง loserหนึ่งดีลใน recent/H1โดยไม่เสีย TP;
  path.15 ทำ recentเสีย winner จึงเลือก body/path .12/.12.
- baseline40 ช่วย H1 แต่ทำ WFเสีย winner; baseline80/100 ทำ recent/WF
  เสีย winners. recent16/24 ทำ recentไม่มี TPและ H1ติดลบ.
  net-move .30–.50 เป็น plateau จึงคง60/20/.40.
- spread0.50 ยังบวก +118.22/+55.74/+55.29 ใน recent/H1/WF
  และรักษา2/3/6 TP เดิม.

Rolling 2 เดือนถึง 2026-07-30 มี8ดีล, 1 TP, WR12.50%,
Net +52.78, +0.87/day, +26.39/month, PF38.70, DD0.80. รวม WF ต่อ H1
ตามเวลาได้138ดีล, 9 TP, Net +152.43, DD67.18, return/DD2.27.
Risk distanceอยู่1.36–14.32 USD, median4.27 USD ที่0.01 lot.

H1 exact timestamp overlap จาก59ดีลเป็น0กับ S346, S349, S351, S355,
S358, S359, S361, S362, S363, S365, S366, S367, S369, S370,
S371, S372, S373 และ S374 ซึ่งยืนยัน timing mean-reversion อิสระ.
อย่างไรก็ดี เมื่อเพิ่มเต็มน้ำหนัก พอร์ต combined net เพิ่ม
+6,985.98→+7,138.41 แต่ DDเพิ่ม138.24→160.86 และ return/DDลด
50.54→44.38 จึงควรใช้เป็น confirmation/จำกัดน้ำหนัก ไม่ใช่ full
independent allocation. Payload smoke ที่ 2026-06-18 17:10 BKK คืน BUY
entry4267.86, SL4259.21, TP4328.41, RR7.0000, market order และ BE.01.
หลัง breadth/falsification, interaction, direction, payoff/BE, local
body/path, windows, latest, spread, overlap, portfolio และ payload audits
ไม่พบ robust improvement ต่อ จึงปิด optimization และเริ่ม S376.

## S376 — Lagged Signed-Volume Return Forecast 9R

ไฟล์: `strategy376.py`

Edge: วัด Pearson correlation แบบไม่ lookahead ระหว่าง signed tick-volume
participation ของแท่ง t กับ close-to-close return ของแท่ง t+1 จาก closed bars
เท่านั้น แล้วเทียบ absolute recent correlation กับ median ของ disjoint
baseline blocks. เมื่อ lead relationship ขยายและแท่ง event มี volume/body/range
เพียงพอ จะตามทิศ event เฉพาะ positive persistence ด้วย market order ที่
next-bar open และวาง SL หลัง event extreme. Timing จึงต่างจาก price-pattern
และ absorption reversal เดิมในพอร์ต.

Optimized default M5, spread0.20, 0.01 lot:

| Window | Signals | Closed | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน ถึง 2026-07-20 | 37 | 37 | 0 | 10.81% | +241.02 | +3.95 | +120.51 | 8.55 | 16.82 |
| 2026-H1 | 107 | 107 | 0 | 7.48% | +433.52 | +2.40 | +72.25 | 4.12 | 65.09 |
| 2025-H2 WF | 170 | 170 | 0 | 5.88% | +182.45 | +0.99 | +30.41 | 2.35 | 37.09 |

ล็อก baseline60/recent24, absolute lead correlation≥.20,
correlation expansion≥1.40x, event volume≥1.10x, body/range≥.25/.60ATR,
body fraction≥.45, persistence-only, session15–23,
`TP_RR=9.0` และ `BE_RR=.01`.

Optimization audits:

- ค่าเริ่มต้นที่เปิด persistence/reversal รวมกันให้ recent/H1/WF
  +82.79/+10.03/-55.38. แยก mode แล้ว persistence บวก
  +117.36/+97.49/+11.90 แต่ reversal ลบ -34.57/-87.46/-67.28
  ทุกช่วง จึงปิด reversal โดยค่าเริ่มต้นแต่คง research toggle ไว้.
- เพิ่ม correlation expansion 1.20→1.40 ทำ recent/H1/WF
  +126.85/+125.97/+86.33; 1.60 ลด current/H1 และ correlation
  threshold .25/.30 ลดความสม่ำเสมอ จึงเลือก1.40.
- recent window20→24 เพิ่มผลครบทุกช่วงเป็น
  +180.20/+250.50/+125.12. baseline80 ทำ H1/WF แย่ลงและ
  recent16 ไม่ชนะข้ามช่วง จึงคง baseline60/recent24.
- แยก direction พบ BUY-only ติดลบ -18.51 ใน WF ขณะที่ SELL-only
  ลด H1/current diversification จึงคงทั้งสองฝั่ง.
- RR9 เพิ่มกำไรครบทุกช่วงเทียบ7R; 9R+BE.01 ให้
  +241.02/+433.52/+182.45 และลด H1/WF DD เทียบ BE.05.
  correlation .25/.30 แม้ลด DD แต่ลด net รวมและ sample มาก จึงไม่ใช้.
- spread0.50 ยังบวก +229.92/+401.42/+131.45 ใน recent/H1/WF
  พร้อมรักษา4/8/10 TP ตามลำดับ.

Rolling 2 เดือนถึง 2026-07-30 มี33ดีล, 3 TP, WR9.09%,
Net +157.67, +2.58/day, +78.84/month, PF5.04, DD29.09.
รวม WF ต่อ H1 ตามเวลาได้277ดีล, 18 TP, Net +615.97, DD65.09,
return/DD9.46. Risk distanceอยู่0.99–16.85 USD, median4.54 USD
ที่0.01 lot.

H1 exact timestamp overlap จาก107ดีลคือ S346=0, S349=0, S351=5,
S355=2, S358=3, S359=3, S361=8, S362=0, S363=1, S365=2,
S366=2, S367=0, S369=2, S370=2, S371=8, S372=9, S373=3,
S374=2 และ S375=0. เมื่อเพิ่ม S376 เต็มน้ำหนัก พอร์ต combined net
เพิ่ม +7,138.41→+7,754.38, DDลด160.86→139.51 และ return/DD
เพิ่ม44.38→55.58 จึงเหมาะเป็น independent allocation.
Payload smoke ที่ 2026-06-30 21:15 BKK คืน BUY, event-close entry4029.89,
SL4021.64, TP4104.14, RR9.0085, market order และ BE.01; simulator
fill next-open ที่4029.82 ตาม execution model. หลัง mode falsification,
correlation/volume/shape, windows, direction, payoff/BE, interaction,
latest, spread, overlap, portfolio และ payload audits ไม่พบ robust
improvement ต่อ จึงปิด optimization และเริ่ม S377.

## S377 — Second-Order Sign-Transition Forecast 7R (Rejected)

ไฟล์: `strategy377.py`

Edge hypothesis: ประเมิน Laplace-smoothed posterior
`P(next return sign | previous two return signs)` จาก recent closed bars
และต้องมี support, posterior edge และ edge expansion เหนือ disjoint
baseline ก่อน forecast next bar. ใช้ event-candle extreme+ATR เป็น SL,
market fill ที่ next-open, TP7R และ BE.05 โดยไม่มี lookahead.

Initial M5, spread0.20, 0.01 lot:

| Window | Signals | Closed | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน ถึง 2026-07-20 | 172 | 172 | 0 | 7.56% | -79.35 | -1.30 | -39.68 | 0.64 | 142.22 |
| 2026-H1 | 533 | 532 | 1 | 9.02% | -110.98 | -0.61 | -18.50 | 0.87 | 252.59 |
| 2025-H2 WF | 400 | 400 | 0 | 5.50% | -94.62 | -0.51 | -15.77 | 0.73 | 118.39 |

Mode falsification พบ continuation ขาดทุน -72.68/-67.97/-49.56
และ reversal ขาดทุน -6.67/-43.01/-45.06 ใน recent/H1/WF.
BUY ขาดทุนครบทุกช่วง; SELL บวกเฉพาะ H1 +89.25 แต่ขาดทุน
recent/WF -28.81/-54.17. แม้มี TP7R และ sample เพียงพอ แต่ combined
กับทุก branch ไม่รอด จึงไม่เข้า optimization/portfolio audit และเริ่ม S378.

## S378 — Volatility-State Persistence Release 9R

ไฟล์: `strategy378.py`

Edge: สร้าง binary high-volatility state จาก true range เทียบ median
reference range แล้วประมาณ Laplace-smoothed
`P(high range at t+1 | high range at t)` จาก recent closed bars.
Probability ต้องสูงและขยายเหนือ disjoint baseline ก่อนให้แท่ง high-range
ที่ body/close คุมทิศเป็น release trigger. เข้า market ที่ next-bar open,
SL หลัง event extreme+ATR และ TP9R จึงจับ volatility clustering พร้อม
directional repricing โดยไม่ใช้ volume/sign forecast และไม่มี lookahead.

Optimized default M5, spread0.20, 0.01 lot:

| Window | Signals | Closed | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน ถึง 2026-07-20 | 108 | 107 | 0 | 6.54% | +541.12 | +8.87 | +270.56 | 7.64 | 29.28 |
| 2026-H1 | 344 | 343 | 0 | 4.08% | +1,079.52 | +5.96 | +179.92 | 4.82 | 67.42 |
| 2025-H2 WF | 415 | 415 | 0 | 4.34% | +549.49 | +2.99 | +91.58 | 3.14 | 48.58 |

ล็อก baseline72/recent30, high-range ratio1.15, support5/10,
persistence≥.60, persistence expansion≥.12, event range≥1.20x,
body≥.50ATR, body fraction≥.55, close-control≥.80, session15–23,
SL buffer.18ATR, `TP_RR=9.0` และ `BE_RR=.02`.

Optimization audits:

- initial 7R/BE.05/expansion.08/close.70/buffer.08 ให้
  +324.07/+563.98/+330.62 ใน recent/H1/WF และผ่าน survivor gate.
- BUY-only ติดลบ -34.30 ใน recent แต่พยุง WF +264.79; SELL-only
  เด่น current/H1 +342.91/+549.13 แต่ WFเพียง+173.14 จึงคงสองฝั่ง.
- RR9 เพิ่ม aggregate ข้ามช่วง; RR10 เพิ่ม current/H1 บางชุดแต่เสีย
  WF winners. BE.02 ช่วย H1/WF และลด DD เทียบ.05/.08/.12.
- persistence expansion.08→.12 เพิ่มครบทุกช่วง; .10–.14 เป็น local
  plateau แต่.14 ลด current/H1. high-range ratio1.35 ช่วย H1/WF
  แต่ทำ recentลดมาก; support variantsไม่เพิ่ม robust edge.
- close-control.70→.80 เพิ่มครบทุกช่วง; .78/.82 ใน final interaction
  ทำ current/H1 ลด. Event range/body/body-fraction variantsต่างมี
  trade-off จึงคง1.20/.50/.55.
- baseline48/60/90/120 และ recent20/24/36/48 ไม่มีค่าที่ชนะครบช่วง:
  recent20ช่วย WF แต่ลด current/H1, recent36ช่วย H1 แต่ลด current/WF.
- interaction expansion.12/close.80/RR9/BE.02 ให้
  +475.73/+936.88/+497.73 ก่อน risk tuning.
  SL buffer.18ATR เพิ่มเป็น +541.12/+1,079.52/+549.49;
  .12–.20 เป็น plateau แต่.20 ทำ H1เสีย2 winnersและ.24เกิด cliff
  จึงเลือก.18. เพดาน risk1.25/1.50 เสีย winners จึงคง1.75ATR.
- spread0.50 ยังบวก +509.02/+976.62/+424.99 ใน recent/H1/WF
  พร้อมรักษา7/14/18 TP เดิม.

Rolling 2 เดือนถึง 2026-07-30 มี125ดีล, 5 TP, WR4.00%,
Net +398.43, +6.53/day, +199.22/month, PF5.16, DD39.77.
รวม WF ต่อ H1 ตามเวลาได้758ดีล, 32 TP, Net +1,629.01, DD67.42,
return/DD24.16. Risk distanceอยู่1.82–17.13 USD, median7.05 USD
ที่0.01 lot.

H1 exact timestamp overlap จาก343ดีลคือ S346=7, S349=4, S351=11,
S355=8, S358=5, S359=14, S361=22, S362=3, S363=5, S365=13,
S366=13, S367=16, S369=3, S370=4, S371=20, S372=17, S373=4,
S374=15, S375=0 และ S376=8. เมื่อเพิ่ม S378 เต็มน้ำหนัก พอร์ต
combined net เพิ่ม +7,754.38→+9,383.39, DDเพิ่ม139.51→161.19
แต่ return/DD ยังเพิ่ม55.58→58.21 จึงผ่าน full-allocation audit.
Payload smoke ที่ 2026-06-29 22:50 BKK คืน BUY, event-close
entry4026.22, SL4017.60, TP4103.80, RR9.0000, market order และ BE.02;
simulator fill next-open ที่4026.23. หลัง direction, payoff/BE, state,
event, windows, interaction, risk geometry, local cliff, latest, spread,
overlap, portfolio และ payload audits ไม่พบ robust improvement ต่อ
จึงปิด optimization และเริ่ม S379.

## S379 — Wald–Wolfowitz Runs-Compression Release 8R

ไฟล์: `strategy379.py`

Edge: ใช้ Wald–Wolfowitz runs statistic กับเครื่องหมายของ closed
close-to-close returns เพื่อตรวจว่าจำนวน direction runs ต่ำกว่าค่าคาดหมาย
ของ random sequence หรือไม่. Recent clustering ต้องขยายเหนือ median
ของ disjoint baseline blocks พร้อม sign imbalance, path efficiency,
net move และ event release ที่ไปทิศเดียวกัน. เข้า market ที่ next-open
และใช้ event extreme+ATR เป็น SL โดยไม่มี lookahead.

Optimized default M5, spread0.20, 0.01 lot:

| Window | Signals | Closed | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน ถึง 2026-07-20 | 14 | 14 | 0 | 14.29% | +87.54 | +1.44 | +43.77 | 5.96 | 16.05 |
| 2026-H1 | 45 | 45 | 0 | 6.67% | +142.91 | +0.79 | +23.82 | 4.53 | 18.71 |
| 2025-H2 WF | 57 | 57 | 0 | 7.02% | +146.43 | +0.80 | +24.41 | 5.32 | 19.71 |

ล็อก baseline72/recent24, cluster strength≥.40,
cluster expansion≥.30, sign imbalance≥.20, path≥.24,
net move≥.45ATR, event body/range≥.60/.80ATR,
body fraction≥.60, close-control≥.75, session15–23,
SL buffer.12ATR, `TP_RR=8.0` และ `BE_RR=.02`.

Optimization audits:

- strict initial cluster≥1.00 มี8/18/26ดีล, recent/H1 ไม่มี TP
  และ -8.32/-22.29; WF มี1 TP/+25.63. Breadth probe พบ cluster.60
  ฟื้นครบช่วงเป็น +40.04/+56.94/+87.91 จึงเข้าสู่ optimization.
- BUY-only บวกครบช่วงแต่ลด WF contribution; SELL-only ขาดทุน
  current/H1 แต่พยุง WF จึงคงสองฝั่งเพื่อไม่เลือก direction จาก sample เล็ก.
- RR8 เพิ่มครบทุกช่วง; RR9 ทำ H1 เสีย winner. BE.02 เพิ่มครบทุกช่วง
  เทียบ.05; BE.01 ทำ WF เสีย winner และ .12 เด่นเฉพาะ H1.
- cluster.40 เพิ่ม sample/winners เป็น +84.83/+129.99/+138.23.
  Fine audit .38–.42 ให้ผลเหมือนกันทุกช่วง จึงเลือกค่ากลาง.40;
  .44 ทำ current/H1 เสีย winner ส่วน.20–.36 เพิ่ม losers.
- expansion/sign/path/close/baseline/recent variants ไม่มีค่าที่ชนะครบ:
  recent20 ช่วย H1แต่ทำ WF ลด, baseline96 ช่วย WFแต่ลด H1,
  path.15 ช่วย WFแต่ลด current/H1.
- SL buffer.12ATR เพิ่มครบทุกช่วงเป็นผล final;
  .16 ช่วย WFเล็กน้อยแต่ H1ลด และ.20ทำ H1เสีย winner จึงเลือก.12.
- spread0.50 ยังบวก +83.34/+129.41/+129.33 ใน recent/H1/WF
  พร้อมรักษา2/3/4 TP เดิม.

Rolling 2 เดือนถึง 2026-07-30 มี12ดีล, 1 TP, WR8.33%,
Net +16.62, +0.27/day, +8.31/month, PF1.95, DD16.25.
รวม WF ต่อ H1 ตามเวลาได้102ดีล, 7 TP, Net +289.34, DD19.71,
return/DD14.68. Risk distanceอยู่1.33–16.20 USD, median4.74 USD
ที่0.01 lot.

H1 exact timestamp overlap จาก45ดีลคือ S346=9, S349=3, S351=4,
S355=9, S358=3, S359=8, S361=21, S362=3, S363=3, S365=7,
S366=18, S367=15, S369=5, S370=0, S371=10, S372=7, S373=0,
S374=17, S375=0, S376=6 และ S378=8. เมื่อเพิ่ม S379 เต็มน้ำหนัก
พอร์ต combined net เพิ่ม +9,383.39→+9,672.73 แต่ DDเพิ่ม
161.19→169.45 และ return/DD ลด58.21→57.08 จึงควรใช้เป็น
confirmation/จำกัดน้ำหนัก. Payload smoke ที่ 2026-06-29 17:50 BKK
คืน SELL, event-close entry4034.47, SL4041.02, TP3982.06,
RR8.0015, market order และ BE.02; simulator fill next-open ที่4034.44.
หลัง breadth, payoff/BE, direction, cluster local/fine plateau, state/event,
windows, risk, latest, spread, overlap, portfolio และ payload audits
ไม่พบ robust improvement ต่อ จึงปิด optimization และเริ่ม S380.

## S380 — Mann–Kendall Monotonic-Order Release 12R

ไฟล์: `strategy380.py`

Edge: ใช้ non-parametric Mann–Kendall statistic เปรียบเทียบ close ทุกคู่
ใน recent closed-bar window เพื่อวัด monotonic price ordering.
Absolute trend Z-score ต้องขยายเหนือ median ของ disjoint baseline blocks
พร้อม net displacement, path efficiency และ event release ที่ตรงทิศ.
เข้า market ที่ next-open และใช้ event extreme+ATR เป็น SL จึงต่างจาก
S379 runs test ที่วัดเฉพาะลำดับเครื่องหมาย และไม่มี lookahead.

Optimized default M5, spread0.20, 0.01 lot:

| Window | Signals | Closed | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน ถึง 2026-07-20 | 59 | 59 | 0 | 11.86% | +539.59 | +8.85 | +269.80 | 8.16 | 27.80 |
| 2026-H1 | 133 | 133 | 0 | 6.02% | +682.64 | +3.77 | +113.77 | 6.21 | 52.94 |
| 2025-H2 WF | 182 | 182 | 0 | 4.95% | +313.84 | +1.71 | +52.31 | 3.08 | 56.60 |

ล็อก baseline60/recent20, trend Z≥1.00, trend expansion≥.80,
path≥.24, net move≥.45ATR, event body/range≥.50/.70ATR,
body fraction≥.70, close-control≥.70, session15–23,
SL buffer.16ATR, `TP_RR=12.0` และ `BE_RR=.02`.

Optimization audits:

- initial expansion.30/body fraction.50/buffer.08/7R/BE.05 ให้
  +192.80/+177.61/+92.02 ใน recent/H1/WF และผ่าน survivor gate.
- BUY-only พยุง WF ขณะที่ SELL-only เด่น current/H1แต่ WFติดลบ
  จึงคงสองฝั่ง.
- trend expansion.30→.80 เพิ่มครบช่วงเป็น
  +197.68/+254.40/+160.84 และลด DD. Z thresholds .60–1.50
  กับ net thresholdsถูก expansion/event gatesครอบอยู่แล้ว;
  path.35 ทำ WF edge ลดมาก.
- event body fraction.50→.70 เพิ่มครบช่วงเป็น
  +253.11/+254.73/+216.07. close.80 เพิ่มแต่ผลน้อยกว่า;
  close.90/body.80/range.90 ทำ winners หาย จึงคง fraction.70.
- baseline40 ช่วย H1/WFแต่ลด current; recent24/28 ช่วย WFแต่ลด
  current/H1 และ recent28 ทำ H1ติดลบ จึงคง60/20.
- interaction expansion.80/fraction.70/RR9/BE.02 ให้
  +354.59/+491.04/+257.01. RR12 เพิ่มครบช่วงเป็น
  +498.27/+620.27/+312.20; RR13 เริ่มทำ WFลดและ RR14–16
  ลด WF winners ต่อเนื่อง จึงเลือก12R ก่อน cliff.
- BE.01 ช่วย H1เล็กน้อยแต่ทำ WFเสีย winnerและ netลด จึงคง.02.
  SL buffer.16ATR เพิ่มครบช่วงเป็นผล final; .18 ทำ current/H1
  เสีย winner และ.20เสียเพิ่ม จึงเลือก.16 ก่อน cliff.
- spread0.50 ยังบวก +521.89/+642.74/+259.24 ใน recent/H1/WF
  พร้อมรักษา7/8/9 TP เดิม.

Rolling 2 เดือนถึง 2026-07-30 มี60ดีล, 6 TP, WR10.00%,
Net +457.13, +7.49/day, +228.57/month, PF7.33, DD33.52.
รวม WF ต่อ H1 ตามเวลาได้315ดีล, 17 TP, Net +996.48, DD56.60,
return/DD17.61. Risk distanceอยู่1.30–16.33 USD, median5.40 USD
ที่0.01 lot.

H1 exact timestamp overlap จาก133ดีลคือ S346=11, S349=5, S351=12,
S355=14, S358=1, S359=14, S361=59, S362=6, S363=10, S365=8,
S366=21, S367=27, S369=11, S370=3, S371=30, S372=27, S373=15,
S374=24, S375=0, S376=5, S378=17 และ S379=16. แม้ overlap
กับ momentum survivors ปานกลาง เมื่อเพิ่ม S380 เต็มน้ำหนัก พอร์ต
combined net เพิ่ม +9,672.73→+10,669.21, DDเพิ่ม169.45→178.14
แต่ return/DD เพิ่ม57.08→59.89 จึงผ่าน full-allocation audit.
Payload smoke ที่ 2026-06-30 19:05 BKK คืน BUY, event-close
entry4031.09, SL4028.12, TP4066.74, RR12.0034, market order และ BE.02;
simulator fill next-open ที่4031.06. หลัง direction, payoff/BE,
trend/event gates, windows, interaction, RR cliff, risk geometry,
latest, spread, overlap, portfolio และ payload audits ไม่พบ robust
improvement ต่อ จึงปิด optimization และเริ่ม S381.

## S381 — Spearman Volume-Range Decoupling Reversal 7R (Rejected)

ไฟล์: `strategy381.py`

Edge hypothesis: วัด Spearman rank correlation ระหว่าง tick volume กับ
true range ใน recent closed bars แล้วหา correlation deterioration เทียบ
disjoint baseline เพื่อชี้ high effort / poor range response. Directional
volume และ net displacement กำหนด exhausted auction ก่อนรอ closed
rejection สวนทาง, market fill ที่ next-open และ SL หลัง rejection+ATR.

Initial M5, spread0.20, 0.01 lot:

| Window | Signals | Closed | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน ถึง 2026-07-20 | 2 | 2 | 0 | 0.00% | -2.90 | -0.05 | -1.45 | 0.00 | 2.90 |
| 2026-H1 | 8 | 8 | 0 | 0.00% | -9.96 | -0.06 | -1.66 | 0.00 | 9.96 |
| 2025-H2 WF | 4 | 4 | 0 | 0.00% | -0.80 | -0.00 | -0.13 | 0.00 | 0.80 |

Breadth falsification ผ่อน correlation max .10→.30/.50 เพิ่ม recent sample
เป็น12/16ดีลแต่ยัง0 TP และ -23.57/-36.68. การผ่อน correlation drop,
directional volume, path, net move, rejection volume/body/range/wick/close
ทีละ gate ยัง0 TPทั้งหมด; recent16 เพิ่มเป็น9ดีลแต่ -10.66.
จึงสรุปว่า rank-decoupling reversal ไม่มี payoff ในช่วงทดสอบ ไม่เข้า
optimization/portfolio audit และเริ่ม S382.

## S382 — Spearman Volume-Range Coupling Release 7R

ไฟล์: `strategy382.py`

Edge: ใช้ Spearman rank correlation ระหว่าง tick volume กับ true range
เพื่อหา regime ที่ participation เริ่มแปลงเป็น price travel อย่างมี
ประสิทธิภาพ. Recent correlation ต้องเป็นบวกและเพิ่มจาก disjoint baseline,
จากนั้น directional volume, path efficiency, net displacement และ event
candle ต้องยืนยัน release ทิศเดียวกัน. เข้า market ที่ next-open และใช้
event extreme+ATR เป็น SL; เป็น continuation counterpart ของ S381 ที่ถูก
reject และช่วยเพิ่ม exposure ต่อ volume-price coupling โดยไม่ใช้ lookahead.

Optimized default M5, spread0.20, 0.01 lot:

| Window | Signals | Closed | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน ถึง 2026-07-20 | 13 | 13 | 0 | 15.38% | +125.93 | +2.06 | +62.97 | 7.30 | 12.92 |
| 2026-H1 | 29 | 29 | 0 | 13.79% | +295.36 | +1.63 | +49.23 | 16.07 | 8.89 |
| 2025-H2 WF | 40 | 40 | 0 | 20.00% | +207.89 | +1.13 | +34.65 | 9.87 | 12.64 |

ล็อก baseline80/recent28, recent Spearman≥.30, correlation rise≥.10,
directional volume≥.15, path≥.20, net move≥.45ATR,
event volume≥1.15x, body/range≥.50/.70ATR, body fraction≥.70,
close-control≥.75, session15–23, SL buffer.16ATR, `TP_RR=7.0`
และ `BE_RR=.01`.

Optimization audits:

- initial 60/20, rise.20, event volume.90, body fraction.60,
  buffer.08 และ BE.05 ผ่าน survivor gateด้วย
  +9.02/+72.30/+43.04 ใน recent/H1/WF.
- BUY และ SELL ต่างเป็นบวกใน H1/WF จึงคงสองฝั่ง. RR8–10 ลดหรือทำ
  WF ติดลบ/เกือบศูนย์ จึงคง7R. BE.01 เพิ่ม H1/WFโดยไม่ลด recent.
- correlation rise.10 เพิ่มครบช่วงเป็น +73.16/+153.38/+70.60;
  directional volume.20 และ path.28 ช่วยเดี่ยวเล็กน้อย แต่เมื่อรวมทุก gate
  current เสีย winners จึงไม่ใช้.
- baseline80 เพิ่มครบช่วงเป็น +35.34/+151.30/+101.84;
  recent28 เป็นบวกครบและเด่นใน WF. event volume1.05 และ body fraction.70
  เพิ่มครบช่วงและลด DD ก่อนนำมาทดสอบ interaction.
- focused core 80/28/rise.10/volume1.05/fraction.70/BE.01 ให้
  +115.92/+265.46/+190.64. Local perturbation ยืนยัน plateau รอบ
  rise.05–.15, volume.95–1.15 และ fraction.65–.75.
- buffer.16ATR และ volume1.15 เพิ่มครบทุกช่วง; interaction final ให้
  +125.93/+295.36/+207.89. rise.15 ช่วย recent/H1แต่ลด WF จึงคง.10.
- spread0.50 ยังบวก +122.03/+286.66/+195.89 ใน recent/H1/WF
  และรักษา2/4/8 TP เดิม.

Rolling 2 เดือนถึง 2026-07-30 มี13ดีล, 2 TP, WR15.38%,
Net +113.73, +1.86/day, +56.86/month, PF4.53, DD25.92.
รวม WF ต่อ H1 ตามเวลาได้69ดีล, 12 TP, Net +503.25, DD16.09,
return/DD31.28. Risk distanceอยู่1.57–16.59 USD, median6.26 USD
ที่0.01 lot.

H1 exact timestamp overlap จาก29ดีลคือ S346=7, S349=2, S351=2,
S355=4, S358=2, S359=5, S361=11, S362=2, S363=1, S365=9,
S366=8, S367=5, S369=3, S370=3, S371=8, S372=9, S373=0,
S374=7, S375=0, S376=2, S378=12, S379=8 และ S380=13.
เมื่อเพิ่ม S382 เต็มน้ำหนัก พอร์ต combined net เพิ่ม
+10,669.21→+11,172.46, DDเพิ่ม178.14→185.03 แต่ return/DD
เพิ่ม59.89→60.38 จึงผ่าน full-allocation audit. Payload smoke ที่
2026-06-24 20:20 BKK คืน SELL, event-close entry4032.97,
SL4042.48, TP3966.39, market order และ BE.01; simulator fill
next-open ที่4032.92 และปิด TP +66.33. หลัง payoff/direction,
coupling/event/windows, focused interaction, local plateau, risk geometry,
latest, spread, overlap, portfolio และ payload audits ไม่พบ robust
improvement ต่อ จึงปิด optimization และเริ่ม S383.

## S383 — Volume-Range Upper-Tail Co-exceedance Release 7R

ไฟล์: `strategy383.py`

Edge: วัด joint upper-tail events ที่ tick volume และ true range สูงกว่า
quantile ของ window พร้อมกัน แล้วเทียบ lift กับ disjoint baseline blocks.
Lift ที่เร่งขึ้นแปลว่า participation กำลัง consume liquidity แบบ nonlinear
แทนที่จะเป็น noise ปกติ. Signed volume เฉพาะ joint-tail bars กำหนดทิศทาง
ร่วมกับ net displacement/path efficiency ก่อนรอ closed release candle.
เข้า market ที่ next-open และใช้ event extreme+ATR เป็น SL จึงไม่มี lookahead
และต่างจาก S382 ที่วัด rank correlation ทั้ง distribution.

Optimized default M5, spread0.20, 0.01 lot:

| Window | Signals | Closed | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน ถึง 2026-07-20 | 26 | 26 | 0 | 11.54% | +222.89 | +3.65 | +111.45 | 22.29 | 7.27 |
| 2026-H1 | 51 | 51 | 0 | 9.80% | +355.34 | +1.96 | +59.22 | 14.18 | 13.89 |
| 2025-H2 WF | 60 | 60 | 0 | 16.67% | +323.99 | +1.76 | +54.00 | 19.94 | 6.80 |

ล็อก baseline80/recent28, tail quantile.60, joint rate≥.18,
tail lift≥1.25, lift rise≥.08, tail directional volume≥.15,
path≥.20, net move≥.45ATR, event volume≥1.10x,
body/range≥.50/.70ATR, body fraction≥.70, close-control≥.75,
session15–23, SL buffer.19ATR, `TP_RR=7.0` และ `BE_RR=.02`.

Optimization audits:

- initial lift rise.12/event volume1.05/body fraction.65/buffer.12 ให้
  +122.82/+252.47/+153.02 ใน recent/H1/WF และผ่าน survivor gate.
- SELL เด่น recent/H1 แต่ BUY เป็นกำไรหลักใน WF จึงคงสองฝั่ง.
  RR8–10 เสีย winners current/H1 และ BE.01 เสีย WF winner จึงคง7R/.02.
- lift rise.05 เพิ่มครบช่วงเป็น +189.53/+313.32/+280.55;
  quantile.55 ช่วยเดี่ยวแต่ interaction ทำ WFลด จึงคง quantile.60.
- baseline60/100 และ recent20/24/32 ไม่มีค่าชนะครบ. Buffer.18ATR
  เพิ่มครบเป็น +201.04/+331.76/+306.61; .20เริ่มเสีย winners
  current/H1 จึงค้นละเอียดรอบ cliff.
- rise.08–.11 อยู่ plateau เดียวกันและเพิ่มครบ จึงเลือกขอบผ่อน .08.
  Body fraction.70, event volume1.10 และ buffer.19 เพิ่มครบทุกช่วง;
  interaction final ให้ +222.89/+355.34/+323.99.
- neighborhood volume1.08/1.12, fraction.69/.71 และ buffer.185/.195
  ไม่ชนะครบ; .195เสีย winner current/H1 จึงปิด optimization.
- spread0.50 ยังบวก +215.09/+340.04/+305.99 ใน recent/H1/WF
  พร้อมรักษา3/5/10 TP เดิม.

Rolling 2 เดือนถึง 2026-07-30 มี27ดีล, 3 TP, WR11.11%,
Net +210.16, +3.45/day, +105.08/month, PF10.06, DD15.73.
รวม WF ต่อ H1 ตามเวลาได้111ดีล, 15 TP, Net +679.33, DD13.89,
return/DD48.91. Risk distanceอยู่1.57–17.00 USD, median5.71 USD
ที่0.01 lot.

H1 exact timestamp overlap จาก51ดีลคือ S346=4, S349=0, S351=6,
S355=10, S358=5, S359=5, S361=22, S362=2, S363=5, S365=8,
S366=10, S367=9, S369=4, S370=5, S371=11, S372=9, S373=1,
S374=10, S375=0, S376=3, S378=14, S379=11, S380=18 และ S382=24.
เมื่อเพิ่ม S383 เต็มน้ำหนัก พอร์ต combined net เพิ่ม
+11,172.46→+11,851.79, DDเพิ่ม185.03→192.51 และ return/DD
เพิ่ม60.38→61.56 จึงผ่าน full-allocation audit. Payload smoke ที่
2026-06-29 22:10 BKK คืน SELL, event-close entry4008.90,
SL4019.42, TP3935.26, market order และ BE.02; simulator fill
next-open ที่4008.86. หลัง payoff/direction, tail/event/windows,
focused interaction, local/final plateau, risk geometry, latest, spread,
overlap, portfolio และ payload audits ไม่พบ robust improvement ต่อ
จึงปิด optimization และเริ่ม S384.

## S384 — Joint-Tail Interarrival Compression Release 7R

ไฟล์: `strategy384.py`

Edge: มอง simultaneous upper-tail tick-volume/true-range bars เป็น
liquidity-consumption events แล้ววัดระยะห่างเฉลี่ยระหว่าง events.
Recent interarrival clock ต้องสั้นลงจาก disjoint baseline ขณะที่ signed
volume ภายใน tail events, path efficiency และ net displacement ต้องไปทาง
เดียวกัน ก่อนยืนยันด้วย closed release candle. สถิตินี้จับ temporal
acceleration ต่างจาก S383 ที่วัด joint-tail lift โดยไม่สนลำดับเวลา.
Market fill ใช้ next-open และ SL อิง event extreme+ATR ไม่มี lookahead.

Optimized default M5, spread0.20, 0.01 lot:

| Window | Signals | Closed | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน ถึง 2026-07-20 | 16 | 16 | 0 | 18.75% | +225.91 | +3.70 | +112.96 | 31.32 | 6.05 |
| 2026-H1 | 32 | 32 | 0 | 15.62% | +365.57 | +2.02 | +60.93 | 22.85 | 7.88 |
| 2025-H2 WF | 39 | 39 | 0 | 15.38% | +234.54 | +1.27 | +39.09 | 19.21 | 5.17 |

ล็อก baseline80/recent28, tail quantile.60, minimum3 tail events,
interarrival compression≥1.15, tail rate rise≥0, directional tail volume≥.15,
path≥.20, net move≥.45ATR, event volume≥1.10x,
body/range≥.65/.70ATR, body fraction≥.72, close-control≥.75,
session15–23, SL buffer.19ATR, `TP_RR=7.0` และ `BE_RR=.02`.

Optimization audits:

- initial rate rise.02/body.50/fraction.70 ให้
  +147.16/+287.62/+161.24 ใน recent/H1/WF และผ่าน survivor gate.
- SELL เด่น recent/H1 แต่ BUY จำเป็นต่อ WF จึงคงสองฝั่ง. RR8–10
  เสีย winners และ BE.01 เสีย WF winner จึงคง7R/.02.
- quantile.55 และ rate rise0 ช่วยเดี่ยวครบช่วง แต่ interaction ทำ H1/WF
  ลดเทียบ rate rise0 จึงคง quantile.60 และเลือก rise0.
- body.65ATR เพิ่มครบเป็น +225.91/+365.37/+234.34 บน rise0;
  fraction.60 เพิ่ม netบางช่วงแต่ DDสูงขึ้นมาก จึงไม่ใช้.
- baseline60/100 และ recent20/24/32 ไม่มีค่าชนะครบ. Buffer.19ATR
  อยู่ก่อน cliff ที่.20ทำ current/H1เสีย winner.
- compression1.05–1.10 เพิ่ม WFแต่ลด current/H1; 1.20–1.25ทำ WF
  เสีย winners จึงคง1.15. Body.66 ทำ WFเสีย winner.
- fraction.71–.73 อยู่ local plateau และเพิ่มครบเล็กน้อย; เลือก.72
  กลาง plateau ก่อน cliffที่.75เคยเสีย H1 winner.
- spread0.50 ยังบวก +221.11/+355.97/+222.84 ใน recent/H1/WF
  พร้อมรักษา3/5/6 TP เดิม.

Rolling 2 เดือนถึง 2026-07-30 มี16ดีล, 3 TP, WR18.75%,
Net +225.91, +3.70/day, +112.96/month, PF31.32, DD6.65.
รวม WF ต่อ H1 ตามเวลาได้71ดีล, 11 TP, Net +600.11, DD7.88,
return/DD76.16. Risk distanceอยู่2.11–14.89 USD, median6.16 USD
ที่0.01 lot.

H1 exact timestamp overlap จาก32ดีลคือ S346=5, S349=0, S351=4,
S355=7, S358=3, S359=3, S361=18, S362=2, S363=3, S365=7,
S366=8, S367=6, S369=2, S370=3, S371=7, S372=9, S373=1,
S374=7, S375=0, S376=2, S378=11, S379=9, S380=12, S382=15
และ S383=27. เมื่อเพิ่ม S384 เต็มน้ำหนัก พอร์ต combined net เพิ่ม
+11,851.79→+12,451.90, DDเพิ่ม192.51→199.79 และ return/DD
เพิ่ม61.56→62.32 จึงผ่าน full-allocation audit. Payload smoke ที่
2026-06-30 16:00 BKK คืน BUY, event-close entry4035.76,
SL4030.86, TP4070.06, market order และ BE.02; simulator fill
next-open ที่4035.71. หลัง payoff/direction, clock/event/windows,
focused/local/final plateau, risk geometry, latest, spread, overlap,
portfolio และ payload audits ไม่พบ robust improvement ต่อ จึงปิด
optimization และเริ่ม S385.

## S385 — Joint-Tail Bernoulli CUSUM Release 7R

ไฟล์: `strategy385.py`

Edge: ใช้ baseline window สร้าง upper-tail thresholds คงที่สำหรับ tick
volume และ true range แล้วแปลง recent bars เป็น Bernoulli joint-tail states.
One-sided CUSUM ตรวจ sequential change-point ว่า liquidity-consumption
events เปลี่ยนสู่อัตราสูงขึ้นอย่างต่อเนื่องหรือไม่. Signed volume ภายใน
recent tail events, path efficiency และ net displacement กำหนดทิศ ก่อน
closed release candle ยืนยัน. ต่างจาก S383 joint lift และ S384 interarrival
clock เพราะใช้ accumulated change statistic กับ baseline thresholds คงที่.
Market fill ใช้ next-open และ SL อิง event extreme+ATR ไม่มี lookahead.

Optimized default M5, spread0.20, 0.01 lot:

| Window | Signals | Closed | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน ถึง 2026-07-20 | 17 | 17 | 0 | 17.65% | +213.64 | +3.50 | +106.82 | 11.83 | 13.99 |
| 2026-H1 | 46 | 46 | 0 | 13.04% | +473.04 | +2.61 | +78.84 | 25.88 | 8.88 |
| 2025-H2 WF | 65 | 65 | 0 | 9.23% | +206.49 | +1.12 | +34.42 | 9.40 | 8.80 |

ล็อก baseline80/recent20, baseline tail quantile.60, minimum3 events,
CUSUM drift.08, CUSUM≥1.00, tail rate rise≥.06,
directional tail volume≥.15, path≥.20, net move≥.45ATR,
event volume≥1.10x, body/range≥.65/.70ATR, body fraction≥.72,
close-control≥.75, session15–23, SL buffer.19ATR,
`TP_RR=7.0` และ `BE_RR=.02`.

Optimization audits:

- initial 80/28, drift.03, rate rise.02 ให้
  +127.53/+376.70/+178.39 ใน recent/H1/WF และผ่าน survivor gate.
- SELL เด่น recent/H1 แต่ BUYจำเป็นต่อ WF จึงคงสองฝั่ง. RR8–10
  เสีย current/H1 winners และ BE.01 เสีย WF winner จึงคง7R/.02.
- CUSUM threshold.50–1.50 อยู่ plateau ถูก gates อื่นครอบ. Quantile.65
  ช่วย current/H1แต่ลด WF. Rate rise.05 และ drift.06 เพิ่มครบเล็กน้อย.
- interaction rise.05/drift.06 ให้ +127.53/+377.10/+178.99;
  event volume/body/fraction/close variantsไม่มีค่าชนะครบ.
- baseline100 และ recent20 ต่างเพิ่มครบ แต่ interactionไม่เสริมกัน.
  Recent20 เดี่ยวได้ +213.64/+473.04/+206.09 และ DDต่ำกว่า จึงเลือก20.
- recent19–20 เป็น local plateau; 18เสีย current/H1 winner และ21–22
  ลด WFมาก. Buffer.20ทำ current/H1เสีย winners จึงคง.19.
- rise.06/drift.08 เพิ่ม WFโดยไม่ลด current/H1 เป็น final;
  rise.07 ทำ WFเสีย winner และ drift.10ไม่เพิ่มผล.
- spread0.50 ยังบวก +208.54/+459.24/+186.99 ใน recent/H1/WF
  พร้อมรักษา3/6/6 TP เดิม.

Rolling 2 เดือนถึง 2026-07-30 มี21ดีล, 3 TP, WR14.29%,
Net +200.31, +3.28/day, +100.16/month, PF7.06, DD27.52.
รวม WF ต่อ H1 ตามเวลาได้111ดีล, 12 TP, Net +679.53, DD8.88,
return/DD76.52. Risk distanceอยู่1.57–15.81 USD, median6.48 USD
ที่0.01 lot.

H1 exact timestamp overlap จาก46ดีลคือ S346=7, S349=0, S351=8,
S355=6, S358=3, S359=7, S361=26, S362=4, S363=6, S365=10,
S366=10, S367=12, S369=4, S370=5, S371=12, S372=10, S373=4,
S374=12, S375=0, S376=3, S378=15, S379=10, S380=15,
S382=15, S383=21 และ S384=19. เมื่อเพิ่ม S385 เต็มน้ำหนัก พอร์ต
combined net เพิ่ม +12,451.90→+13,131.43, DDเพิ่ม199.79→207.07
และ return/DD เพิ่ม62.32→63.42 จึงผ่าน full-allocation audit.
Payload smoke ที่ 2026-06-24 20:20 BKK คืน SELL,
event-close entry4032.97, SL4042.72, TP3964.72, market order และ BE.02;
simulator fill next-open ที่4032.92 และปิด TP +68.00.
หลัง payoff/direction, CUSUM/event/windows, interaction/local/final
plateau, risk geometry, latest, spread, overlap, portfolio และ payload
audits ไม่พบ robust improvement ต่อ จึงปิด optimization และเริ่ม S386.

## S386 — Joint-Tail EWMA Hazard Acceleration Release 7R

ไฟล์: `strategy386.py`

Edge: ใช้ baseline upper-tail thresholds คงที่แปลง recent bars เป็น
Bernoulli joint volume-range events แล้วอัปเดต fast/slow EWMA hazards.
Fast hazard ต้องสูงกว่าทั้ง baseline rate และ slow hazard เพื่อยืนยัน
fresh acceleration. Direction ใช้ recency-weighted signed volume เฉพาะ
tail events ร่วมกับ path/net displacement และ closed release candle.
ต่างจาก S385 CUSUM เพราะให้น้ำหนักข้อมูลล่าสุดแบบ exponential และวัด
fast-slow hazard spread. Market fill ใช้ next-open, SL ใช้ event+ATR.

Optimized default M5, spread0.20, 0.01 lot:

| Window | Signals | Closed | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน ถึง 2026-07-20 | 9 | 9 | 0 | 33.33% | +209.24 | +3.43 | +104.62 | 37.52 | 5.13 |
| 2026-H1 | 26 | 26 | 0 | 15.38% | +280.72 | +1.55 | +46.79 | 19.22 | 8.08 |
| 2025-H2 WF | 46 | 46 | 0 | 13.04% | +212.59 | +1.16 | +35.43 | 11.40 | 7.00 |

ล็อก baseline60/recent20, tail quantile.60, minimum3 events,
fast/slow alpha=.30/.10, direction alpha=.20, hazard rise≥.12,
acceleration≥.08, directional tail volume≥.15, path≥.20,
net move≥.45ATR, event volume≥1.10x, body/range≥.65/.70ATR,
body fraction≥.78, close-control≥.75, session15–23,
SL buffer.19ATR, `TP_RR=7.0` และ `BE_RR=.02`.

Optimization audits:

- initial 80/20, fast/slow .35/.10, rise.05, acceleration.03,
  fraction.72 ให้ +201.14/+195.56/+162.73 ใน recent/H1/WF.
- SELL เด่น recent/H1 แต่ BUYจำเป็นต่อ WF จึงคงสองฝั่ง. RR8–10
  เสีย current/H1 winners และ BE variantsไม่เพิ่ม robustly จึงคง7R/.02.
- hazard variantsส่วนใหญ่อยู่ plateau. Rise.10 และ acceleration.06
  เพิ่ม current/H1โดยไม่ลด WF; direction.25เสีย WF winner.
- baseline60 และ fraction.75 เพิ่มครบ; interactionกับ rise.10/accel.06
  ให้ +208.84/+279.52/+206.67 และลด WF DDเหลือ7.40.
- baseline50/70 ไม่ชนะครบ. Buffer.20+ทำ current/H1เสีย winners
  จึงคง.19. Fast alpha.30 และ rise.12 ช่วยครบเล็กน้อย.
- fraction.76–.79 เพิ่มครบเป็น plateau; .80ทำ current/H1เสีย winner
  จึงเลือก.78 ก่อน cliff. Finalได้ +209.24/+280.72/+212.59.
- spread0.50 ยังบวก +206.54/+272.92/+198.79 ใน recent/H1/WF
  พร้อมรักษา3/4/6 TP เดิม.

Rolling 2 เดือนถึง 2026-07-30 มี9ดีล, 2 TP, WR22.22%,
Net +136.34, +2.24/day, +68.17/month, PF11.01, DD8.49.
รวม WF ต่อ H1 ตามเวลาได้72ดีล, 10 TP, Net +493.31, DD8.08,
return/DD61.05. Risk distanceอยู่1.87–13.91 USD, median5.73 USD
ที่0.01 lot.

H1 exact timestamp overlap จาก26ดีลคือ S346=4, S349=1, S351=5,
S355=4, S358=3, S359=3, S361=10, S362=2, S363=3, S365=7,
S366=6, S367=9, S369=1, S370=4, S371=1, S372=4, S373=2,
S374=7, S375=0, S376=2, S378=12, S379=4, S380=9, S382=8,
S383=11, S384=8 และ S385=16. เมื่อเพิ่ม S386 เต็มน้ำหนัก พอร์ต
combined net เพิ่ม +13,131.43→+13,624.74, DDเพิ่ม207.07→214.15
และ return/DD เพิ่ม63.42→63.62 จึงผ่าน full-allocation audit.
Payload smoke ที่ 2026-06-24 20:20 BKK คืน SELL,
event-close entry4032.97, SL4042.72, TP3964.72, market order และ BE.02;
simulator fill next-open ที่4032.92 และปิด TP +68.00.
หลัง payoff/direction, hazard/breadth, focused/local/final plateau,
risk geometry, latest, spread, overlap, portfolio และ payload audits
ไม่พบ robust improvement ต่อ จึงปิด optimization และเริ่ม S387.

## S387 — Joint-Tail Markov Persistence Release 7R

ไฟล์: `strategy387.py`

Edge: แปลงแท่งย้อนหลังเป็นสถานะ Bernoulli joint volume-range tail ด้วย
threshold จาก baseline คงที่ แล้วเปรียบเทียบ Laplace-smoothed
`P(tail[t+1]=1 | tail[t]=1)` ของ recent กับ baseline. ความน่าจะเป็น
transition ที่สูงขึ้นแยก liquidity cascade ต่อเนื่องออกจาก spike เดี่ยว.
ทดสอบแล้ว edge อยู่เฉพาะ downside cascade จึงล็อก SELL-only และใช้
signed tail volume, path/net displacement กับ closed release candle ยืนยัน.
Market fill ใช้ next-open, SL ใช้ event extreme+ATR และไม่มี lookahead.

Optimized default M5, spread0.20, 0.01 lot:

| Window | Signals | Closed | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน ถึง 2026-07-20 | 6 | 6 | 0 | 33.33% | +136.77 | +2.24 | +68.39 | 11.37 | 12.79 |
| 2026-H1 | 8 | 8 | 0 | 37.50% | +230.12 | +1.27 | +38.35 | 231.12 | 0.60 |
| 2025-H2 WF | 13 | 13 | 0 | 23.08% | +147.93 | +0.80 | +24.66 | 74.97 | 1.00 |

ล็อก baseline60/recent20, tail quantile.60, minimum3 events,
Laplace alpha1.0, recent P11≥.35, P11 rise≥.15,
directional tail volume≥.25, path≥.20, net move≥.45ATR,
event volume≥1.10x, body/range≥.65/.70ATR, body fraction≥.75,
close-control≥.75, session15–23, SELL-only, SL buffer.19ATR,
`TP_RR=7.0` และ `BE_RR=.02`.

Optimization audits:

- ค่าเริ่มต้นสองฝั่งได้ +119.35/+210.86/+178.42 ใน recent/H1/WF
  แต่ BUY-only ขาดทุน -17.22/-18.66/+31.69 ขณะที่ SELL-onlyได้
  +136.57/+229.52/+146.73 จึงยืนยัน downside-specific edge.
- RR8–10 ทำ recent/H1 เสีย winners; BE.01/.05/.10 ไม่เพิ่มครบ จึงคง
  7R/.02. P11 minimum .25–.55 ส่วนใหญ่อยู่ plateau เพราะ rise gate.
- quantile.55/.65, rise.05–.25, Laplace alpha.5–2.0 และ minimum4
  ยังบวกครบ แต่ไม่มีค่าชนะทั้งสามหน้าต่างพร้อมกัน.
- บน SELL-only, directional volume.25 ลดดีลอ่อนโดยรักษา TP ทั้งหมด:
  recent6/2TP, H1 8/3TP, WF13/3TP และเพิ่มผลรวมเล็กน้อย จึงเป็น final.
- quantile.65+direction.25 ลด H1 DD แต่เพิ่ม WF DD และกำไรต่ำกว่า;
  rise.20/.25 ทำ WF เสีย breadth/winner จึงไม่เลือก.
- spread0.50 ยังบวก +134.97/+227.72/+144.03 ใน recent/H1/WF
  และ TP count เท่าเดิมทั้งหมด.

Rolling 2 เดือนถึง 2026-07-30 มี7ดีล, 2 TP, WR28.57%,
Net +128.88, +2.11/day, +64.44/month, PF7.11, DD20.68.
รวม WF ต่อ H1 ตามเวลาได้21ดีล, 6 TP, Net +378.05, DD1.00,
return/DD378.05. Risk distanceอยู่1.87–12.75 USD, median6.16 USD
ที่0.01 lot.

H1 exact timestamp overlap จาก8ดีลคือ S346=2, S349=0, S351=1,
S355=1, S358=2, S359=3, S361=6, S362=1, S363=1, S365=4,
S366=3, S367=4, S369=2, S370=2, S371=3, S372=3, S373=0,
S374=3, S375=0, S376=0, S378=6, S379=0, S380=2, S382=4,
S383=5, S384=4, S385=6 และ S386=4. แม้ overlap สูงกับกลุ่ม tail
แต่ SELL-only payoff ลด drawdown รวม: เมื่อเพิ่ม S387 เต็มน้ำหนัก พอร์ต
combined net เพิ่ม +13,624.74→+14,002.79, DDคงเดิม214.15 และ
return/DD เพิ่ม63.62→65.39 จึงผ่าน full-allocation audit.
Payload smoke ที่ 2026-06-24 20:20 BKK คืน SELL,
event-close entry4032.97, SL4042.72, TP3964.72, market order และ BE.02;
simulator fill next-open ที่4032.92 และปิด TP +68.00.
หลัง Markov/payoff/direction/focused, latest, spread, risk, overlap,
portfolio และ payload audits ไม่พบ robust improvement ต่อ จึงปิด
optimization และพร้อมเริ่ม S388.

## S388 — Joint-Tail Duration-Dependence Release 10R (portfolio reject)

ไฟล์: `strategy388.py`

Edge: ต่อจาก first-order Markov persistence ของ S387 โดยวัด higher-order
duration dependence ของ joint volume-range tail runs. ใช้ event-weighted
mean run length `sum(run_len²)/sum(run_len)` ของ recent เทียบ baseline,
กำหนด longest run และสัดส่วน events ที่อยู่ใน run≥2 แล้วจึงผ่าน release
engine แบบ closed bars/next-open/event+ATR SL. แนวคิดต้องการแยก cascade
ที่ self-reinforcing ออกจาก tail pair สั้น ๆ.

Optimized standalone M5, spread0.20, 0.01 lot:

| Window | Signals | Closed | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน ถึง 2026-07-20 | 8 | 8 | 0 | 12.50% | +96.72 | +1.59 | +48.36 | 5.73 | 20.03 |
| 2026-H1 | 19 | 19 | 0 | 10.53% | +223.29 | +1.23 | +37.21 | 23.60 | 8.08 |
| 2025-H2 WF | 36 | 36 | 0 | 11.11% | +201.98 | +1.10 | +33.66 | 19.03 | 6.60 |

Standalone optimum ใช้ baseline80/recent24, quantile.60, minimum4 events,
longest run≥3, run-mean rise≥1.00, long-run share≥.50,
directional volume≥.15, path≥.20, net move≥.45ATR, event gatesเดิม,
สองฝั่ง, SL buffer.19ATR, `TP_RR=10.0`, `BE_RR=.02`.

Optimization/falsification audits:

- initial 7R ได้ +61.33/+152.84/+182.22 ใน recent/H1/WF.
  Run-mean rise1.00 เพิ่มครบเป็น +61.53/+153.24/+183.22 และลด DD.
- Direction.25 ทำ WF เสีย TP; BUY-only ขาดทุน recent/H1 แต่ยังจำเป็น
  ต่อ WF. SELL-onlyลด DDแต่กำไรรวมต่ำกว่า จึงคงสองฝั่ง standalone.
- RR8/9/10 เพิ่มครบ โดย10Rได้ +96.72/+223.29/+201.98.
  RR11 ทำ WF เสีย TP และ RR12/14 เสียสอง TP จึงล็อก10Rก่อน cliff.
- Run-mean1.25/1.50 เสีย WF winner; long-run share.35/.65 และ
  longest2/4 อยู่ plateau จึงไม่เพิ่ม complexity.
- spread0.50 ยังบวก +94.32/+217.59/+191.18 ใน recent/H1/WF.

Rolling 2 เดือนถึง 2026-07-30 มี10ดีล, 1 TP, WR10.00%,
Net +88.63, +1.45/day, +44.31/month, PF4.11, DD28.32.
รวม WF+H1 ได้55ดีล, 6 TP, Net +425.27, DD8.08,
return/DD52.63. Risk distance2.07–14.89 USD, median6.69 USD.

H1 overlap จาก19ดีลสูงกับ tail family: S382=13, S383=13,
S384=12, S385=11, S386=8, S387=4. Full-weight portfolio net เพิ่ม
+14,002.79→+14,428.06 แต่ DDเพิ่ม214.15→220.83 และ return/DDลด
65.3878→65.3356. น้ำหนัก .25/.50/.75 ก็ลด return/DD ต่อเนื่องเป็น
65.3744/65.3613/65.3483 จึง reject จาก active portfolio ทุกน้ำหนัก.
Payload smoke ยืนยัน market payload 10R ครบและ simulator ใช้ next-open.
สรุป: standalone เทรดได้และ robust ต่อ spread แต่ duration edge ซ้ำกับ
tail family มากเกินไป ไม่ผ่าน diversification gate จึงไป S389.

## S389 — Signed-Flow Lead-Lag Release 11R

ไฟล์: `strategy389.py`

Edge: ใช้ tick volume คูณเครื่องหมาย body เป็น causal signed-flow proxy
แล้ววัด Pearson correlation ระหว่าง pressure ที่แท่ง t-1 กับ return ที่
แท่ง t. Recent lag-one correlation ต้องเป็นบวกและเพิ่มจาก baseline ก่อน
ยืนยันด้วย cumulative directional flow, path/net displacement และ closed
release candle. ต่างจาก S382–S388 เพราะไม่ใช้ joint-tail state หรือ event
clustering. SL ใช้ event extreme+ATR, market fill next-open ไม่มี lookahead.

Optimized default M5, spread0.20, 0.01 lot:

| Window | Signals | Closed | Invalid | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน ถึง 2026-07-20 | 7 | 7 | 0 | 42.86% | +276.63 | +4.53 | +138.31 | 14.27 | 20.44 |
| 2026-H1 | 12 | 12 | 0 | 16.67% | +242.30 | +1.34 | +40.38 | 122.15 | 1.60 |
| 2025-H2 WF | 19 | 19 | 0 | 10.53% | +139.16 | +0.76 | +23.19 | 25.89 | 3.99 |

ล็อก baseline80/recent24, lead correlation≥.195, rise≥.15,
directional flow≥.10, path≥.15, net move≥.35ATR,
event volume≥1.10x, body/range≥.65/.70ATR, body fraction≥.72,
close-control≥.75, session15–23, SL buffer.25ATR,
`TP_RR=11.0` และ `BE_RR=.02`.

Optimization audits:

- initial gate บังคับ lead correlation สูงกว่า same-bar correlation ทำให้
  closed=0 เพราะ signed body-volume กับ same-bar returnสัมพันธ์สูงโดยนิยาม.
  ถอดเฉพาะ tautological comparison แต่คง causal lag-one+baseline rise.
- lead.25 ให้ +147.41/+146.81/-4.26; lead.15 คืน WF winners และบวก
  +155.83/+140.58/+79.62. Local .10–.18 เป็น robust plateau.
- lead.19 เพิ่มครบและ .195 กรอง BE เพิ่มโดยรักษา winners; .20 ทำ
  recent/WF เสีย winner จึงล็อก .195 ก่อน cliff.
- BUY/SELL แยกกันกำไรรวมต่ำกว่า จึงคงสองฝั่ง. RR8–11 เพิ่มครบ;
  RR12 ทำ WF เสียหนึ่งในสอง TP จึงล็อก11R.
- Buffer .19→.25ATR เพิ่มผลครบทุกขั้น. .25 ได้
  +276.63/+242.30/+139.16; .26 ทำ WF เสีย TPทันทีเหลือ+11.63
  จึงล็อก .25 ก่อน cliff. BE.01/.05 อยู่ plateau.
- spread0.50 ยังบวก +274.53/+238.70/+133.46 ใน recent/H1/WF
  พร้อมรักษา3/2/2 TP เท่าเดิม.

Rolling 2 เดือนถึง 2026-07-30 มี8ดีล, 2 TP, WR25.00%,
Net +162.12, +2.66/day, +81.06/month, PF6.52, DD28.96.
รวม WF+H1 ได้31ดีล, 4 TP, Net +381.46, DD3.99,
return/DD95.60. Risk distance1.65–13.23 USD, median5.33 USD.

H1 exact timestamp overlap จาก12ดีลคือ S346=2, S349=0, S351=4,
S355=3, S358=0, S359=2, S361=7, S362=0, S363=1, S365=2,
S366=7, S367=4, S369=2, S370=0, S371=3, S372=4, S373=0,
S374=7, S375=0, S376=6, S378=3, S379=9, S380=6, S382=3,
S383=6, S384=5, S385=8, S386=3 และ S387=0.
เมื่อเพิ่ม S389 เต็มน้ำหนัก พอร์ต net เพิ่ม +14,002.79→+14,384.25,
DDแทบคงเดิม214.15→214.35 และ return/DD เพิ่ม65.39→67.11.
น้ำหนัก .25/.50/.75 เพิ่ม ratio ต่อเนื่อง จึงผ่าน full allocation.
Payload smoke ที่ 2026-06-19 16:15 BKK คืน BUY,
event-close entry4170.24, SL4164.00, TP4238.88, market order และ BE.02;
simulator fill next-open4170.21 และจัด execution ตาม11R.
หลัง lead/local/RR/buffer/BE, latest, spread, risk, overlap, portfolio
และ payload audits ไม่พบ robust improvement ต่อ จึงปิด optimization
และเริ่ม S390.

## S390 — Conditional Signed-Flow Partial-Correlation Release 7R (Rejected)

ไฟล์: `strategy390.py`

สมมติฐาน: residualize lagged signed-flow predictor และ next return ต่อ
prior return ก่อนวัด partial correlation เพื่อหา incremental order-flow
information ที่ไม่ใช่ return autocorrelation. ใช้ recent partial correlation
และ rise จาก baseline เป็น gate ก่อนผ่าน S389 release engine แบบผ่อน raw
correlation, market next-open และ dynamic event+ATR SL.

Default M5, spread0.20, 0.01 lot:

| Window | Closed | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน ถึง 2026-07-20 | 5 | 0.00% | -17.62 | -0.29 | -8.81 | 0.00 | 17.62 |
| 2026-H1 | 6 | 0.00% | -5.43 | -0.03 | -0.91 | 0.00 | 5.43 |
| 2025-H2 WF | 23 | 4.35% | -1.32 | -0.01 | -0.22 | 0.89 | 10.28 |

Falsification:

- partial minimum .10/.15/.20/.25/.30 ให้ recent 4–8ดีล แต่ไม่มี TP
  ทุกค่าและ Net -17.42 ถึง -18.22.
- partial rise .05–.25, raw lead .00/.05/.10 และ baseline60/80/100
  ยังไม่มี recent TP; recent window20/24/28 ก็ลบทั้งหมด.
- H1 narrow variants 4–9ดีล ไม่มี TPและลบ -5.03 ถึง -6.03.
- WF baseมี1 TPจาก23ดีลแต่ยัง -1.32; recent20 บวก +17.48 เฉพาะ WF
  ขณะที่ recent/H1 ยังลบ จึงไม่ใช่ robust improvement.
- สมมติฐาน positive conditional continuation ถูกหักล้างในทุก regime
  สำคัญ จึงหยุดก่อน payoff/spread/portfolio audit และ reject S390.

บทเรียน: predictive contribution ของ signed flow ใน S389 ไม่ได้มาจาก
partial correlation หลัง control prior return แบบเส้นตรง; conditioning นี้
กลับเลือก release ที่ล้มเหลว จึงควรเปลี่ยน family ใน S391.

## S391 — Conditional Signed-Flow Exhaustion Reversal 7R (Rejected)

ไฟล์: `strategy391.py`

สมมติฐานตรงข้าม S390: เมื่อ partial correlation ของ lagged signed flow
กับ next return เป็นลบและลดจาก baseline ให้ตีความเป็น aggressive-flow
exhaustion/passive absorption แล้ว fade release candle. SL วางหลัง event
extreme+ATR, market fill next-open และ TP7R.

Default M5, spread0.20, 0.01 lot:

| Window | Closed | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน ถึง 2026-07-20 | 4 | 0.00% | -4.51 | -0.07 | -2.26 | 0.00 | 4.51 |
| 2026-H1 | 14 | 0.00% | -17.65 | -0.10 | -2.94 | 0.00 | 17.65 |
| 2025-H2 WF | 22 | 9.09% | +7.42 | +0.04 | +1.24 | 1.31 | 12.83 |

Falsification:

- initial raw lead/rise constraintsให้ recentเพียง1ดีลและแพ้. อนุญาต
  config ค่าลบใน S389 validation โดย default/ผล S389ไม่เปลี่ยน แล้วปิด
  raw gatesเฉพาะ S391 เพื่อทดสอบ partial reversal โดยตรง.
- หลังปลด raw gates recentมี3–6ดีลตาม negative strength .10–.30,
  partial drop .05–.25, baseline60–100 และ recent20–28 แต่ไม่มี TP.
- H1 narrow variantsมี7–21ดีล ไม่มี TPทุกค่าและลบ -9.14 ถึง -28.21.
- WF baseมี2 TP/22ดีลและ +7.42 แต่ negative.30ลบ, recent20ลบ
  -16.51 และผล recent/H1 เป็นศูนย์ TP จึงไม่ robust.
- ทั้ง conditional continuation (S390) และ conditional reversal (S391)
  ล้มเหลว แสดงว่า linear partial correlation ไม่ใช่ stable state variable
  สำหรับ release execution ชุดนี้ จึง reject ก่อน spread/portfolio audit.

## S392 — Signed-Flow Information-Gain Release 8R (Rejected)

ไฟล์: `strategy392.py`

Edge hypothesis: discretize signed tick-volume pressure เป็น weak/strong
buy/sell states แล้ววัด normalized mutual information ว่า state ลด entropy
ของ next-bar direction ได้เท่าไร. Recent information gain ต้องสูงกว่า
baseline และ current state ต้องมี Laplace-smoothed confidence/support เพียงพอ.
Directionมาจาก conditional probability จึงรองรับทั้ง continuation/reversal
แบบ nonlinear; SL event extreme+ATR และ market next-open.

Optimized candidate M5, spread0.20, 0.01 lot:

| Window | Closed | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน ถึง 2026-07-20 | 8 | 12.50% | +64.05 | +1.05 | +32.03 | 6.12 | 12.51 |
| 2026-H1 | 26 | 19.23% | +136.36 | +0.75 | +22.73 | 5.19 | 18.14 |
| 2025-H2 WF | 39 | 7.69% | +29.22 | +0.16 | +4.87 | 1.75 | 24.02 |

Candidate ใช้ baseline80/recent28, pressure quantile.55, info≥.08,
rise≥.03, confidence≥.75, support≥4, BUY-only, buffer.24ATR,
`TP_RR=8.0`, `BE_RR=.02`.

Optimization/falsification:

- baseสองฝั่งได้ recent +12.89/H1 +87.70 แต่ WF -57.48.
  Confidence.75 ลด noiseเป็น +39.34/+93.08/-9.48.
- TP8R ทำ confidence.75 บวกครบ +48.70/+116.12/+4.14;
  RR9เสีย H1 winners และ RR10เสีย WF winner จึงคง8R.
- Support4 เพิ่ม H1/WF; support5 เสีย WF winner. Confidence.78/.80
  ทำ recentเสีย winner จึงล็อก.75ก่อน cliff.
- SELL-only ลบทั้งสามหน้าต่าง; BUY-onlyเพิ่มเป็น
  +62.96/+123.94/+23.23. Buffer.24เพิ่มเป็น final candidate ข้างต้น.
- spread0.50 ยังบวก +61.65/+128.56/+17.52 ใน standard windows.
- แต่ rolling 2 เดือนถึง 2026-07-30 มี9ดีล, 0 TP, WR0%,
  Net -15.10, -0.25/day, -7.55/month, DD15.10;
  spread0.50ยิ่งลบ -17.80. Edge จึงเสื่อมในข้อมูลต่อท้ายทันที.
- แม้ payload smoke และ8R geometryผ่าน แต่ latest robustness gateล้มเหลว
  จึง reject ก่อน portfolio audit ไม่ใช้ cutoff selection บัง regime failure.

## S393 — Realized-Semivariance Dominance Release 9R

ไฟล์: `strategy393.py`

Edge: แยก close returns เป็น upside/downside realized semivariance แล้วใช้
normalized imbalance `(RS+−RS−)/(RS++RS−)` วัดทิศทางที่ variance
concentrate. Recent imbalance ต้องแรงและเพิ่มในทิศเดียวจาก baseline พร้อม
path/net displacement และ closed release candle. เดิมเพิ่ม bipower-variation
jump ratio แต่ถูก falsify; final edge ใช้ semivariance dominance ล้วน.
Market fill next-open, SL event extreme+ATR ไม่มี lookahead.

Optimized default M5, spread0.20, 0.01 lot:

| Window | Closed | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน ถึง 2026-07-20 | 45 | 8.89% | +214.77 | +3.52 | +107.39 | 4.88 | 28.49 |
| 2026-H1 | 109 | 5.50% | +383.24 | +2.12 | +63.87 | 4.75 | 43.65 |
| 2025-H2 WF | 148 | 5.41% | +321.71 | +1.75 | +53.62 | 5.69 | 28.28 |

ล็อก baseline80/recent24, imbalance≥.25, directional rise≥.15,
jump gate0, path≥.15, net move≥.35ATR, event volume≥1.05x,
body/range≥.65/.75ATR, body fraction≥.72, close-control≥.75,
session15–23, สองฝั่ง, buffer.18ATR, `TP_RR=9.0`, `BE_RR=.02`.

Optimization audits:

- initial jump.10/7R ให้ +8.77/+193.90/+187.89 ใน recent/H1/WF.
  ปิด jump gateเพิ่มเป็น +161.25/+352.66/+276.02; jump≥.15ทำ
  recentไม่มี TP จึง falsify jump component และเปลี่ยนชื่อ final strategy.
- imbalance.35–.55 และ rise.25–.35 ลด current/H1 winners แม้ช่วย WF
  DD จึงคง .25/.15. BUY/SELL ต่างสร้างกำไรและจำเป็นทั้งคู่.
- RR8เสีย H1/WF winners; RR9ให้ผลรวมสูงสุด
  +222.43/+394.20/+232.43; RR10เสีย H1สอง winners จึงคง9R.
- Buffer .16–.18 ทำ WFได้8 TP เทียบ6 TPที่.19–.24. ค่า.18เพิ่มครบ
  เทียบ.17 และ .19เป็น cliff จึงล็อก.18.
- BE.05/.10 ลดผลและเพิ่ม H1/WF DD; baseline60/recent20 ไม่ชนะครบ.
- spread0.50 ยังบวก +201.27/+350.54/+277.31 ใน recent/H1/WF
  พร้อมรักษา4/6/8 TP.

Rolling 2 เดือนถึง 2026-07-30 มี43ดีล, 2 TP, WR4.65%,
Net +83.44, +1.37/day, +41.72/month, PF2.20, DD40.48;
spread0.50ยัง +70.54. รวม WF+H1 ได้257ดีล, Net +704.95,
DD46.45, return/DD15.18. Risk1.53–16.27 USD, median5.67 USD.

H1 overlap จาก109ดีลสูงตาม sample: S361=43, S380=40, S385=29,
S383=26, S372=26, S378=24, S384=21, S355=19, S389=10 และ
S387=4. แต่ portfolio interaction ยังผ่าน: full-weight netเพิ่ม
+14,384.25→+15,089.20, DDเพิ่ม214.35→222.56 และ return/DDเพิ่ม
67.11→67.80. น้ำหนัก .25/.50/.75 เพิ่ม ratioต่อเนื่อง
67.28/67.46/67.63 จึงรับเต็มน้ำหนัก.
Payload smoke ที่ 2026-06-30 16:00 BKK คืน BUY,
event-close entry4035.76, SL4030.91, TP4079.42, market order, BE.02;
simulator fill next-open4035.71 และประเมิน9Rตามกฎ conservative.
หลัง jump/semivariance/rise/direction/RR/buffer/BE, latest, spread,
risk, overlap, portfolio และ payload audits ไม่พบ robust improvement ต่อ
จึงปิด optimization และเริ่ม S394.

## S394 — Variance-Ratio Serial-Dependence Release 10R

ไฟล์: `strategy394.py`

Edge: ใช้ overlapping variance ratio แบบ Lo–MacKinlay เปรียบเทียบ variance
ของผลตอบแทนหลายแท่งกับ one-bar variance เพื่อหา regime ที่ราคาเริ่มมี
serial dependence เชิง continuation. Recent VR ต้องสูงกว่า baseline และผ่าน
path/net displacement พร้อม closed release candle; market fill ที่ next open,
SL หลัง event extreme บวก ATR buffer และไม่มี lookahead.

Optimized default M5, spread0.20, 0.01 lot:

| Window | Closed | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน ถึง 2026-07-20 | 11 | 9.09% | +96.38 | +1.58 | +48.19 | 4.62 | 25.84 |
| 2026-H1 | 30 | 6.67% | +246.60 | +1.36 | +41.10 | 24.22 | 5.42 |
| 2025-H2 WF | 41 | 7.32% | +189.81 | +1.03 | +31.64 | 11.73 | 8.84 |

ค่าที่ล็อกคือ baseline80/recent28, horizon3, VR≥1.15, rise≥.10,
path≥.18, net move≥.40ATR, event volume≥1.05x, body/range≥.65/.75ATR,
body fraction≥.72, close-control≥.75, session15–23, สองฝั่ง,
buffer.225ATR, `TP_RR=10.0`, `BE_RR=.02`.

Optimization audits:

- Horizon3 ให้ +57.32/+158.81/+184.83 ใน recent/H1/WF และแข็งแรงกว่า
  horizon4 โดยเฉพาะ WF.
- RR10 เพิ่มเป็น +93.14/+234.05/+184.54; RR11 ทำ WF เสียสอง TP และ
  RR12/14 ไม่มี WF TP จึงล็อก 10R ก่อน payoff cliff.
- SELL-only ให้ +106.03/+117.42/+194.00 แต่ BUY มี winner ที่ช่วย recent/H1;
  จึงคงสองฝั่งเพื่อกระจาย regime.
- Buffer .20/.21/.215/.22/.225 เพิ่มผลอย่างต่อเนื่องทุก window; ที่ .23
  WF เสียหนึ่ง TP และลดจาก +189.81 เหลือ +136.25 จึงล็อก .225 ก่อน cliff.
- spread0.50 ยังบวก +93.08/+237.60/+177.51 ใน recent/H1/WF.

Rolling 2 เดือนถึง 2026-07-30 มี12ดีล, 1 TP, WR8.33%, Net +88.24,
+1.45/day, +44.12/month, PF3.54, DD34.38; spread0.50 ยัง +84.64.
รวม WF+H1 ได้71ดีล, Net +436.41, DD8.84, return/DD49.37.
Risk ต่อดีล 2.16–14.81 USD, median7.38 USD.

H1 overlap จาก30ดีลสูงสุดกับ S393=17, S385=15, S383/S384=14,
S361/S382=11 และ S379/S380=10. Portfolio interaction ผ่านชัดเจน:
full-weight net เพิ่ม +15,089.20→+15,525.61, DD เพิ่มเพียง
222.56→223.16 และ return/DD เพิ่ม 67.798→69.572. น้ำหนัก
.25/.50/.75 เพิ่ม ratio ต่อเนื่องเป็น 68.243/68.686/69.129
จึงรับ S394 เต็มน้ำหนัก.

Payload smoke ที่ 2026-06-30 16:00 BKK คืน BUY, event-close
entry4035.76, SL4030.69, TP4086.47, market order, BE.02;
simulator fill next-open4035.71 และประเมิน 10R ตามกฎ conservative.
หลัง horizon/VR/rise/direction/RR/buffer/BE, latest, spread, risk,
overlap, portfolio และ payload audits ไม่พบ robust improvement ต่อ
จึงปิด optimization และเริ่ม S395.

## S395 — Spectral-Entropy Compression Release 7R (Rejected)

ไฟล์: `strategy395.py`

Edge hypothesis: แปลง closed-bar returns เข้าสู่ compact Fourier basis แล้ววัด
normalized spectral entropy และสัดส่วนพลังงาน low-frequency. หาก entropy ลดจาก
baseline พร้อม low-frequency share เพิ่ม ให้ตีความว่า diffuse noise รวมตัวเป็น
coherent directional process ก่อนยืนยันด้วย path/net displacement และแท่ง release.
Market fill next-open, SL หลัง event extreme+ATR และ TP อย่างน้อย7R.

Default M5, spread0.20, 0.01 lot:

| Window | Closed | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน ถึง 2026-07-20 | 1 | 0.00% | -0.20 | -0.00 | -0.10 | 0.00 | 0.20 |
| 2026-H1 | 7 | 0.00% | -1.40 | -0.01 | -0.23 | 0.00 | 1.40 |
| 2025-H2 WF | 22 | 4.55% | +2.44 | +0.01 | +0.41 | 1.12 | 13.55 |

Falsification:

- จำนวน spectral bins 5/6/8/10, low bins1/2/3, entropy max .80/.86/.92,
  entropy drop0/.03/.06, low-frequency share .30/.38/.46 และ rise0/.04/.08
  ไม่มี recent TP ทุกค่า; net อยู่ระหว่าง -13.50 ถึง 0.00.
- สมมติฐาน follow มี0 TP ใน recent/H1 และได้เพียง1 TP/22ดีลใน WF.
- ทดสอบคู่ตรงข้ามแบบ coherent-exhaustion fade ที่ RR7/8/10 และ BE.05:
  recent 2ดีล WR0% Net -2.73, H1 12ดีล WR0% Net -19.98;
  WF ดีที่สุดที่ RR8 ยัง Net -4.40, PF0.89.
- ทั้ง continuation และ reversal ล้มเหลวใน recent/H1 จึงไม่มีหลักฐาน Edge
  ที่ robust. Reject ก่อน latest/spread/risk/portfolio audit เพื่อไม่เลือก cutoff
  หรือ sizing มาบัง core hypothesis failure และเริ่ม S396.

## S396 — Studentized Return-CUSUM Drift-Shift Release 7R

ไฟล์: `strategy396.py`

Edge: ประเมิน mean/scale จาก closed baseline returns แล้วแปลง recent returns
เป็น standardized residual ก่อนป้อน two-sided Page CUSUM. Terminal excursion
ต้องแรง, เด่นกว่าฝั่งตรงข้าม และยังเร่งขึ้นจากครึ่งแรก จึงตีความเป็น active
drift change ไม่ใช่ isolated candle. ใช้ mean shift, path/net displacement,
volume และ closed release candle ยืนยัน; market fill next-open, SL หลัง
event extreme+ATR และไม่มี lookahead.

Optimized default M5, spread0.20, 0.01 lot:

| Window | Closed | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน ถึง 2026-07-20 | 18 | 22.22% | +238.77 | +3.91 | +119.39 | 12.26 | 13.09 |
| 2026-H1 | 34 | 23.53% | +568.57 | +3.14 | +94.76 | 26.52 | 11.76 |
| 2025-H2 WF | 63 | 14.29% | +302.19 | +1.64 | +50.37 | 16.50 | 6.37 |

ค่าที่ล็อกคือ baseline80/recent24, allowance.30, strength≥4,
dominance≥.45, rise≥1, mean shift≥.18z, path≥.16,
net move≥.35ATR, event volume≥1.05x, body/range≥.65/.75ATR,
body fraction≥.72, close-control≥.75, session15–23, สองฝั่ง,
buffer.18ATR, `TP_RR=7.0`, `BE_RR=.02`.

Optimization audits:

- Initial allowance.10 ให้ +240.15/+558.04/+230.05 ใน recent/H1/WF.
  Allowance .15→.30 รักษา TP ครบและลด noise ต่อเนื่อง; .30 ให้
  +242.97/+577.58/+272.41 และ DD13.30/11.91/6.43.
- Allowance .35 ทำ H1/WF เสียอย่างละ2 TP ทันที จึงล็อก .30 ก่อน cliff.
- Dominance.65 ลด recent DD เหลือ7.22 แต่ทำ H1 เสีย1 TP; baseline60 และ
  combinations ไม่ชนะ allowance.30 ครบทุก window จึงคงค่าอื่นเดิม.
- RR8–11 เพิ่ม recent payoff แต่ RR8/9 ทำ WF เสีย2/3 TP และ RR10/11
  ทำ H1 เหลือ5 TP พร้อมทำ WF เหลือ5/3 TP จึงคง robust floor ที่7R.
- BUY/SELL ต่างมี2/2 recent TP และ4/4 H1/WF TP จึงคงสองฝั่ง.
  BE.05/.10 ไม่เพิ่ม robust result.
- Buffer .14–.18 รักษา recent/H1 TP และ .14–.18 เพิ่ม WF เป็น9 TP;
  .18 ให้ผลรวมสูงสุดใน plateau. ที่ .19 WF ลดเหลือ8 TP จึงล็อก .18
  เป็นค่าสุดท้ายก่อน cliff.
- Path/net/volume/body/fraction probes ไม่มีค่าที่ชนะครบสาม window;
  ค่าที่เข้มตัด winners และค่าที่ผ่อนเพิ่ม noise จึงคง defaults.

Rolling 2 เดือนถึง 2026-07-30 ซึ่งไม่ใช้จูนมี18ดีล, 3 TP, WR16.67%,
Net +166.11, +2.72/day, +83.06/month, PF6.67, DD28.09;
spread0.50 ยัง +160.71. Spread0.50 ใน recent/H1/WF ยังบวก
+233.37/+558.37/+283.29 และรักษา TP count ทุกช่วง.

รวม WF+H1 ได้97ดีล, Net +870.76, DD12.56, return/DD69.33.
Risk ต่อดีล 2.05–12.97 USD, median6.44 USD. H1 overlap สูงสุดกับ
S393=27, S361=16, S378=14, S380=13, S372/S385=11 และ S394=10.
แม้ overlap สูงบางตัว แต่ portfolio interaction ผ่านมาก: full-weight net
เพิ่ม +15,525.61→+16,396.37, DD เพิ่มเพียง223.16→223.36 และ
return/DD เพิ่ม69.572→73.408. น้ำหนัก .25/.50/.75 เพิ่ม ratio ต่อเนื่อง
70.531/71.491/72.449 จึงรับ S396 เต็มน้ำหนัก.

Payload smoke ที่ 2026-06-29 17:50 BKK คืน SELL, event-close
entry4034.47, SL4041.35, TP3986.31, market order, BE.02;
simulator fill next-open4034.44 และประเมิน7R ตามกฎ conservative.
หลัง CUSUM allowance/strength/dominance/rise/window, direction, RR, BE,
buffer, signal-quality, latest, spread, risk, overlap, portfolio และ payload
audits ไม่พบ robust improvement ต่อ จึงปิด optimization และเริ่ม S397.

## S397 — Bowley Quantile-Skew Rotation Release 7R (Rejected)

ไฟล์: `strategy397.py`

Edge hypothesis: ใช้ Bowley quartile skewness `(Q3+Q1-2Q2)/(Q3-Q1)`
วัด asymmetry ของ closed returns แบบ robust ต่อ outlier. Recent skew ต้องแรง
และ rotate ออกจาก baseline ในทิศเดียวกับ path/net displacement ก่อนยืนยันด้วย
volume และ closed release candle. Market fill next-open, dynamic event-extreme
plus ATR stop และ TP7R.

Default M5, spread0.20, 0.01 lot:

| Window | Closed | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน ถึง 2026-07-20 | 18 | 5.56% | +9.27 | +0.15 | +4.64 | 1.55 | 16.37 |
| 2026-H1 | 43 | 9.30% | +175.46 | +0.97 | +29.24 | 5.22 | 19.30 |
| 2025-H2 WF | 66 | 4.55% | +23.62 | +0.13 | +3.94 | 1.58 | 25.38 |

Falsification:

- Skew .08/.14/.20/.28, rotation0/.08/.14/.22, IQR0/.08/.14ATR,
  baseline60/80/100 และ recent20/24/28/32 ถูกทดสอบ. Recent28/32 เพิ่ม
  recent เป็น +74.63/+73.37 และ H1 เป็น +253.85/+254.62 แต่ WF กลับลบ
  -5.47/-8.90 จึงเป็น window overfit.
- Skew.28 ลด noise และ recent DD แต่ทำ H1 เสีย1 TP และ WF เหลือ1 TP;
  rotation.22 ทำ WF ติดลบ. Base24 เป็นค่าเดียวที่บวกครบ standard windows.
- BUY-only ลบ recent -7.39 แต่บวก WF +43.61; SELL-only บวก recent +16.66
  แต่ลบ WF -19.99 จึงไม่มี direction ที่ robust ข้าม regime.
- RR8–11 เพิ่ม recent และบางค่าเพิ่ม WF แต่ทำ H1 เสีย1–3 TP; RR10/11
  ทำ H1 กลายเป็น -4.50/-0.70. BE.10 ช่วยเฉพาะ H1; buffer.14/.22
  ไม่เพิ่มผลครบทุกช่วง จึงคง base7R/.18 สำหรับ final falsification.
- spread0.50 ยังบวก recent/H1/WF +3.87/+162.56/+3.82 แต่ WF PF เหลือ
  เพียง1.06 และ DD เพิ่มเป็น35.28 แสดง transaction-cost margin ต่ำมาก.
- Untouched latest 2 เดือนถึง 2026-07-30 มี16ดีล, 0 TP, WR0%,
  Net -16.77, -0.27/day, -8.38/month, DD16.77; spread0.50 ลดเป็น -21.57.
  Edge เสื่อมในข้อมูลต่อท้าย จึง reject ก่อน risk/overlap/portfolio audit
  และเริ่ม S398. Payload geometry/signature ผ่าน แต่ไม่ชดเชย latest failure.

## S398 — L-Moment Tail-Asymmetry Expansion Release 7R

ไฟล์: `strategy398.py`

Edge: สร้าง sample probability-weighted moments จาก closed returns แล้วคำนวณ
`L2=2b1-b0`, `L3=6b2-6b1+b0`, `L-skewness=L3/L2`. Linear order-statistic
weights ใช้ข้อมูลทั้ง distribution แต่ robust กว่า third moment และละเอียดกว่า
Bowley สาม quantiles. Recent absolute L-skew ต้องขยายจาก median ของ disjoint
baseline blocks พร้อม path/net displacement, volume และ closed release candle.
Market fill next-open, SL event extreme+ATR และไม่มี lookahead.

Optimized default M5, spread0.20, 0.01 lot:

| Window | Closed | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน ถึง 2026-07-20 | 12 | 8.33% | +72.46 | +1.19 | +36.23 | 6.47 | 12.25 |
| 2026-H1 | 31 | 9.68% | +194.00 | +1.07 | +32.33 | 11.10 | 12.21 |
| 2025-H2 WF | 45 | 8.89% | +140.17 | +0.76 | +23.36 | 10.16 | 8.70 |

ค่าที่ล็อกคือ baseline72/recent24, L-skew≥.14, rise≥.05,
L-scale≥.08ATR, path≥.14, net move≥.30ATR, event volume≥1.05x,
body/range≥.65/.75ATR, body fraction≥.72, close-control≥.75,
session15–23, สองฝั่ง, buffer.22ATR, `TP_RR=7.0`, `BE_RR=.02`.

Optimization audits:

- Initial buffer.18 ให้ +69.63/+188.29/+134.27 ใน recent/H1/WF.
  Skew.20/.28 และ rise.10/.16 ลด recent noise แต่ตัด H1/WF winners;
  skew.28 และ rise.16 ทำ WF ไม่มี TP จึงคง .14/.05.
- L-scale0/.08/.14 ไม่เปลี่ยน winner set. baseline48/72/96 และ
  recent20/24/28/32 ไม่ชนะ base ครบทุก window; recent32 เพิ่ม H1 เพียง1.60
  แต่ลด WF มากกว่า31 USD จึงคง72/24.
- RR8–11 เพิ่ม recent จาก winner เดิม แต่ RR8/9 ทำ H1/WF เสีย1 TP,
  RR10 ทำ H1 เสีย2 TP และ RR11 ทำ WF เสีย2 TP จึงคง7R.
- BUY-only recent ลบแต่ SELL-only มี recent winner; H1/WF ทั้งสองฝั่งบวก
  และแบ่ง winners กัน จึงคงสองฝั่ง. BE.05/.10 ลด H1/WF และเพิ่ม DD.
- Buffer .18→.22 รักษา TP1/3/4 และเพิ่ม net ทุก window. ที่ .24 WF
  เสีย1 TP และที่ .26 H1 เสีย1 TP จึงล็อก .22 ก่อน cliff.

Rolling 2 เดือนถึง 2026-07-30 ซึ่งไม่ใช้จูนมี10ดีล, 1 TP, WR10.00%,
Net +72.86, +1.19/day, +36.43/month, PF6.67, DD12.45;
spread0.50 ยัง +69.86. Spread0.50 recent/H1/WF ยังบวก
+68.86/+184.70/+126.67 และรักษา TP count ทุกช่วง.

รวม WF+H1 ได้76ดีล, Net +334.17, DD14.81, return/DD22.56.
Risk ต่อดีล 1.60–12.97 USD, median6.66 USD. H1 overlap สูงสุดกับ
S393=28, S372=15, S361=13, S371=12, S380=10 และ S396=8.
Portfolio interaction ผ่าน: full-weight net เพิ่ม
+16,396.37→+16,730.54, DD เพิ่มเพียง223.36→223.56 และ return/DD เพิ่ม
73.408→74.837. น้ำหนัก .25/.50/.75 เพิ่ม ratio ต่อเนื่อง
73.765/74.123/74.480 จึงรับ S398 เต็มน้ำหนัก.

Payload smoke ที่ 2026-06-30 16:00 BKK คืน BUY, event-close
entry4035.76, SL4030.71, TP4071.12, market order, BE.02;
simulator fill next-open4035.71 และประเมิน7R ตามกฎ conservative.
หลัง L-skew/rise/scale/window, direction, RR, BE, buffer, latest, spread,
risk, overlap, portfolio และ payload audits ไม่พบ robust improvement ต่อ
จึงปิด optimization และเริ่ม S399.

## S399 — L-Kurtosis Tail-Weight Expansion Release 7R

ไฟล์: `strategy399.py`

Edge: ใช้ probability-weighted moments สร้าง
`L4=20b3-30b2+12b1-b0` และ `L-kurtosis=L4/L2` เพื่อวัด tail weight
ของ closed-return distribution แบบ linear order statistics ซึ่ง robust กว่า
fourth conventional moment. Recent L-kurtosis ต้องสูงและขยายจาก median ของ
disjoint baseline blocks; เนื่องจาก kurtosis ไม่มี sign จึงใช้ net displacement
และ path efficiency กำหนดทิศ ก่อนยืนยันด้วย volume และ closed release candle.
Market fill next-open, SL event extreme+ATR และไม่มี lookahead.

Optimized default M5, spread0.20, 0.01 lot:

| Window | Closed | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน ถึง 2026-07-20 | 29 | 10.34% | +208.45 | +3.42 | +104.23 | 10.00 | 19.97 |
| 2026-H1 | 69 | 10.14% | +484.20 | +2.68 | +80.70 | 9.41 | 28.06 |
| 2025-H2 WF | 95 | 8.42% | +209.32 | +1.14 | +34.89 | 5.70 | 20.63 |

ค่าที่ล็อกคือ baseline84/recent28, L-kurtosis≥.10, rise≥.02,
L-scale≥.08ATR, path≥.14, net move≥.30ATR, event volume≥1.05x,
body/range≥.65/.75ATR, body fraction≥.72, close-control≥.75,
session15–23, สองฝั่ง, buffer.20ATR, `TP_RR=7.0`, `BE_RR=.02`.

Optimization audits:

- Initial72/24/rise.04 ให้ +59.96/+330.31/+153.25 ใน recent/H1/WF.
  ปิด rise gate และ window28/32 เพิ่ม recent winners; cross-window พบ
  84/28/rise0 ให้ +208.05/+482.40/+195.12 และ TP3/7/8.
- Local window26–30 แสดงผลบวกกว้าง แต่ window27/29/30 เปลี่ยน winner set
  มาก. ที่84/28 rise0/.01/.02 รักษา TP3/7/8 และผลเพิ่มต่อเนื่อง;
  rise.03 ทำ WF เสีย1 TP และ .04 ทำเสียเพิ่ม จึงล็อก .02 ก่อน cliff.
- Kurtosis.22 เพิ่ม selectivity แต่ไม่ชนะ core84/28/.02 ครบทุก window;
  scale0/.08/.14 ไม่มีประโยชน์เพิ่ม.
- RR8/9 เพิ่ม recent แต่ทำ H1/WF เสีย winners; RR10/11 เสียมากขึ้น
  จึงคง7R. BUY/SELL ต่างบวก H1/WF และ recent winners มาจาก SELL
  จึงคงสองฝั่ง. BE.05/.10 ลดผลและเพิ่ม H1 DD.
- Buffer .18/.19/.20 รักษา TP3/7/8; ที่ .21 WF ลดจาก8เหลือ6 TP และ
  .23/.24 เหลือ5 TP จึงคง .20 ก่อน cliff.

Rolling 2 เดือนถึง 2026-07-30 ซึ่งไม่ใช้จูนมี29ดีล, 3 TP, WR10.34%,
Net +195.81, +3.21/day, +97.91/month, PF6.47, DD33.81;
spread0.50 ยัง +187.11. Spread0.50 recent/H1/WF ยังบวก
+199.75/+463.50/+180.82 และรักษา TP count ทุกช่วง.

รวม WF+H1 ได้164ดีล, Net +693.52, DD28.06, return/DD24.72.
Risk ต่อดีล 1.62–16.42 USD, median6.03 USD. H1 overlap สูงสุดกับ
S393=38, S361=21, S378=19, S380=18, S372/S396/S398=17 และ
S383/S384/S385=16. Portfolio interaction ยังผ่าน: full-weight net เพิ่ม
+16,730.54→+17,424.06, DD เพิ่ม223.56→224.16 และ return/DD เพิ่ม
74.837→77.730. น้ำหนัก .25/.50/.75 เพิ่ม ratio ต่อเนื่อง
75.562/76.286/77.009 จึงรับ S399 เต็มน้ำหนัก.

Payload smoke ที่ 2026-06-30 16:00 BKK คืน BUY, event-close
entry4035.76, SL4030.81, TP4070.42, market order, BE.02;
simulator fill next-open4035.71 และประเมิน7R ตามกฎ conservative.
หลัง L-kurtosis/rise/scale/window, direction, RR, BE, buffer, latest,
spread, risk, overlap, portfolio และ payload audits ไม่พบ robust improvement ต่อ
จึงปิด optimization และเริ่ม S400.

## S400 — Gini Return–Volume Rank-Coupling Release 7R (Portfolio Rejected)

ไฟล์: `strategy400.py`

Edge: แปลง tick volume เป็น empirical-CDF average ranks แล้วคำนวณ normalized
Gini covariance ระหว่าง centered closed returns กับ rank scores. ค่าบวกหมายถึง
ผลตอบแทนสูงสอดคล้องกับ volume rank สูง; ค่าลบเป็น auction ฝั่งตรงข้าม.
Recent absolute coupling ต้องขยายจาก median ของ disjoint baseline blocks
และตรงกับ net path ก่อนยืนยันด้วย volume/release candle. Market next-open,
SL event extreme+ATR และไม่มี lookahead.

Optimized default M5, spread0.20, 0.01 lot:

| Window | Closed | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน ถึง 2026-07-20 | 17 | 11.76% | +125.16 | +2.05 | +62.58 | 5.68 | 25.75 |
| 2026-H1 | 34 | 8.82% | +192.66 | +1.06 | +32.11 | 7.79 | 21.17 |
| 2025-H2 WF | 50 | 12.00% | +224.88 | +1.22 | +37.48 | 14.31 | 7.10 |

ค่าที่ล็อกคือ baseline72/recent24, coupling≥.20, rise≥.13,
path≥.14, net move≥.30ATR, event volume≥1.05x,
body/range≥.65/.75ATR, body fraction≥.72, close-control≥.75,
session15–23, สองฝั่ง, buffer.22ATR, `TP_RR=7.0`, `BE_RR=.02`.

Optimization/falsification:

- Initial coupling.14/rise.05/buffer.20 ให้ +122.21/+185.93/+190.72
  ใน recent/H1/WF. Coupling.28 ลด recent DD แต่ตัด WF จาก6เหลือ3 TP;
  rise.16 ตัด WF เหลือ5 TP.
- Local coupling .18–.24/rise .08–.12 พบ .20/.08–.12 เป็น plateau
  ที่รักษา TP2/3/6. ขยาย rise พบ .13 ยังรักษา winners และเพิ่ม WF
  เป็น +221.23/DD7.03; ที่ .14 WF เสีย1 TP จึงล็อก .13 ก่อน cliff.
- RR8–11 เพิ่ม recent แต่ทำ H1/WF เสีย winners; BUY/SELL ต่างมี contribution
  และ SELL เด่นใน WF จึงคงสองฝั่ง. BE.05/.10 ไม่ชนะครบทุกช่วง.
- Buffer .18–.22 รักษา TP2/3/6 และ net เพิ่ม; ที่ .23 WF ลดเหลือ5 TP
  จึงล็อก .22 ก่อน cliff.

Rolling 2 เดือนถึง 2026-07-30 ซึ่งไม่ใช้จูนมี15ดีล, 1 TP, WR6.67%,
Net +46.29, +0.76/day, +23.15/month, PF2.17, DD39.02;
spread0.50 ยัง +41.79. Spread0.50 recent/H1/WF ยังบวก
+120.06/+182.46/+209.88 และรักษา TP count.

รวม WF+H1 ได้84ดีล, Net +417.54, DD23.17, return/DD18.02.
Risk ต่อดีล 1.88–14.20 USD, median6.62 USD. H1 overlap สูงสุดกับ
S393=25, S361=15, S399=14, S384=13, S385=12 และ S372/S383/S398=11.
Portfolio interaction ไม่ผ่าน: baseline net17,424.06, DD224.16,
return/DD77.730. น้ำหนัก .25/.50/.75/1.00 เพิ่ม net แต่ ratio ลดต่อเนื่อง
เป็น77.584/77.441/77.299/77.160 เพราะ DD เพิ่มถึง231.23 ที่ full weight.
จึง reject ทุกน้ำหนัก ไม่ใช้ standalone profit บัง adverse interaction.

Payload smoke ที่ 2026-06-30 16:00 BKK คืน BUY, event-close
entry4035.76, SL4030.71, TP4071.12, market order, BE.02;
simulator fill next-open4035.71 และประเมิน7R ตามกฎ conservative.
หลัง coupling/rise/window, direction, RR, BE, buffer, latest, spread,
risk, overlap, portfolio และ payload audits ไม่พบ allocation ที่เพิ่ม
risk-adjusted return จึง reject S400 และเริ่ม S401.

## S401 — Rousseeuw–Croux Qn Scale-Expansion Release 7R (Accepted)

ไฟล์: `strategy401.py`

Edge: ใช้ Rousseeuw–Croux Qn ซึ่งเป็น robust scale estimator จากควอไทล์ที่ 25
ของระยะห่างแบบคู่ระหว่าง closed returns เพื่อหา volatility expansion โดยไม่ถูก outlier
เดี่ยวครอบงำเหมือน standard deviation จากนั้นเปรียบเทียบ recent Qn กับ median ของ
disjoint baseline blocks และยืนยันด้วย ATR-normalized rise, net path และ release candle.
กลยุทธ์เข้า market ที่ next open, วาง SL หลัง event extreme บวก ATR buffer, TP 7R
และย้าย BE ที่ 0.02R โดยไม่ใช้ข้อมูลอนาคต.

Optimized default M5, spread0.20, 0.01 lot:

| Window | Closed | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน ถึง 2026-07-20 | 31 | 12.90% | +203.55 | +3.34 | +101.78 | 4.99 | 38.36 |
| 2026-H1 | 74 | 10.81% | +486.28 | +2.69 | +81.05 | 8.66 | 25.37 |
| 2025-H2 WF | 112 | 8.04% | +269.35 | +1.46 | +44.89 | 4.70 | 25.42 |

ค่าที่เลือกคือ baseline72/recent24, Qn ratio ≥1.14, rise ≥.03ATR,
buffer .18ATR, `TP_RR=7.0`, `BE_RR=.02` และใช้สัญญาณทั้ง BUY/SELL.

Optimization/falsification:

- Qn ratio .10–.14 เป็นบริเวณที่ยังรักษาผู้ชนะข้ามหน้าต่าง; ที่ .15 recent และ H1
  เสียผู้ชนะ จึงล็อก .14 ก่อน cliff.
- RR8/9 เพิ่มกำไร recent และ H1 แต่ลด WF winners; RR10/11 ลด winners มากขึ้น
  จึงคง 7R. BUY/SELL ต่างสร้างกำไรใน recent, H1 และ WF.
- Buffer .14–.18 รักษา WF 9 winners; ที่ .19 ลดเหลือ 8 และ net ลด
  +269.35→+237.23 จึงล็อก .18 ก่อน cliff. BE .05/.10 ไม่ให้ผล robust improvement.

Rolling 2 เดือนถึง 2026-07-30 ซึ่งไม่ใช้จูนมี 29 ดีล, 2 TP, WR6.90%,
Net +104.44, +1.71/day, +52.22/month, PF2.76, DD58.76.
Spread0.50 recent/H1/WF/latest ยังบวก +194.25/+464.08/+235.75/+95.74
และรักษาจำนวน winners ทุกหน้าต่าง.

รวม WF+H1 ได้186ดีล, Net +755.63, DD29.79, return/DD25.37.
Risk ต่อดีล 1.77–14.75 USD, median6.57 USD. Portfolio interaction ผ่าน:
full-weight net เพิ่ม +17,424.06→+18,179.69, DD 224.16→232.57 และ return/DD
เพิ่ม 77.730→78.169. น้ำหนัก .25/.50/.75 เพิ่ม ratio ต่อเนื่องเป็น
77.843/77.954/78.062 จึงรับ S401 เต็มน้ำหนัก.

Payload smoke คืน SELL market order พร้อม entry4013.65, SL4024.30,
TP3939.10, BE.02 และ simulator ปิดดีลครบทุก signal. หลัง Qn threshold,
window, direction, RR, BE, buffer, latest, spread, risk, overlap, portfolio
และ payload audits ไม่พบ robust improvement ต่อ จึงปิด optimization และเริ่ม S402.

## S402 — Bipower Jump-Variation Exhaustion Fade 8R (Accepted)

ไฟล์: `strategy402.py`

Edge: realized variance รวมทั้ง auction noise แบบต่อเนื่องและ discontinuous repricing
ขณะที่ bipower variation ประเมินส่วนต่อเนื่องจากผลคูณของ absolute returns ที่ติดกัน.
ส่วนต่างบวกจึงเป็น jump variation. S402 เปรียบเทียบ recent jump share กับ disjoint
baseline blocks พร้อมกำหนด jump energy ต่อ ATR² แล้ว fade ทิศทาง net path หลังแท่ง
participated release ปิดสมบูรณ์. เข้า market ที่ next open, SL หลัง event extreme
บวก ATR buffer, TP 8R และ BE .02R โดยไม่มี lookahead.

Optimized default M5, spread0.20, 0.01 lot:

| Window | Closed | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน ถึง 2026-07-20 | 25 | 16.00% | +45.44 | +0.74 | +22.72 | 2.50 | 12.49 |
| 2026-H1 | 81 | 13.58% | +244.14 | +1.35 | +40.69 | 2.89 | 31.67 |
| 2025-H2 WF | 97 | 10.31% | +29.76 | +0.16 | +4.96 | 1.29 | 38.58 |

ค่าที่เลือกคือ baseline84/recent28, jump share ≥.12, ratio ≥1.80,
rise ≥.03, energy ≥.18ATR², path ≥.14, buffer .20ATR,
`TP_RR=8.0`, `BE_RR=.02`, fade mode และใช้ทั้ง BUY/SELL.

Optimization/falsification:

- Initial continuation ให้ recent 16 ดีล/0 winner/−16.04 แม้ H1/WF บวก
  +281.48/+108.09 จึงไม่ robust ข้าม regime. Exhaustion fade window28 บวกครบ
  recent/H1/WF +11.70/+150.87/+12.99 จึงใช้ fade hypothesis.
- Ratio1.80 ปรับ Net และ DD ดีขึ้นครบสามช่วงเทียบ ratio1.20 แม้ WF เสีย 1 winner;
  ratio2.00 ไม่เพิ่มผล จึงคง1.80. Share .16–.24 ลดดีลแพ้ recent แต่ตัด H1 winners.
- Buffer local .10–.24 พบ .20 ให้ +41.05/+202.15/+25.50 ที่ 7R;
  ที่ .22 H1 เริ่มเสีย winner และ .24 WF เสื่อม จึงล็อก .20 ก่อน cross-window cliff.
- RR8 เพิ่ม Net จาก7R ครบสามช่วงเป็น +45.44/+244.14/+29.76 และเพิ่ม
  return/DD แม้เสีย winner ช่วงละหนึ่ง. ที่ RR9 H1 เสียเพิ่มสอง winners และ Net ลด,
  RR12 ทำ H1 DD กระโดด จึงล็อก8R. BUY เด่นใน WF แต่ SELL เด่นใน H1
  จึงคงทั้งสองฝั่ง. BE .05/.10 ไม่เปลี่ยนผล.

Rolling 2 เดือนถึง 2026-07-30 ซึ่งไม่ใช้จูนมี23ดีล, 4 TP, WR17.39%,
Net +52.15, +0.85/day, +26.07/month, PF3.22, DD12.18.
Spread0.50 recent/H1/WF/latest ยังบวก +37.94/+219.84/+0.66/+45.25;
WF stress margin บางจึงต้องพึ่ง portfolio gate เป็นตัวตัดสิน.

รวม WF+H1 ได้178ดีล, Net +273.90, DD41.21, return/DD6.65.
Risk ต่อดีล 0.61–11.92 USD, median1.79 USD จัดเป็น short-SL survivor ที่ TP8R.
Portfolio interaction ผ่านและช่วยกระจายความเสี่ยง: full-weight net เพิ่ม
+18,179.69→+18,453.59 ขณะที่ DD ลด232.57→231.25 และ return/DD เพิ่ม
78.169→79.799. น้ำหนัก .25/.50/.75 เพิ่ม ratio ต่อเนื่องเป็น
78.575/78.982/79.390 จึงรับ S402 เต็มน้ำหนัก.

Payload smoke คืน SELL market order พร้อม entry4062.65, SL4065.19,
TP4042.33, BE.02 และ simulator ปิดดีลครบทุก signal. หลังทดสอบ jump gates,
window, continuation/fade, direction, RR, BE, buffer, latest, spread, risk,
overlap, portfolio และ payload ไม่พบ robust improvement ต่อ จึงปิด optimization S402
และเริ่ม S403 ตามลำดับ.

## S403 — Realized-Semivariance Dominance Continuation 9R (Portfolio Rejected)

ไฟล์: `strategy403.py`

Edge: แยก positive/negative realized semivariance จากผลรวม squared closed returns
เพื่อวัดว่าพลังความผันผวนถูกครองโดยฝั่งขึ้นหรือลงมากเพียงใด. Recent dominance
ต้องขยายจาก median ของ disjoint baseline blocks, มี dominant energy ต่อ ATR²,
ตรงกับ net path และยืนยันด้วย participated release candle. เข้า market ที่ next open,
SL หลัง event extreme+ATR, TP9R และ BE.02 โดยไม่ใช้ future bars.

Optimized default M5, spread0.20, 0.01 lot:

| Window | Closed | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน ถึง 2026-07-20 | 40 | 10.00% | +232.13 | +3.81 | +116.07 | 7.11 | 20.68 |
| 2026-H1 | 96 | 5.21% | +305.65 | +1.69 | +50.94 | 5.00 | 45.45 |
| 2025-H2 WF | 136 | 5.88% | +322.22 | +1.75 | +53.70 | 5.73 | 31.12 |

ค่าที่เลือกคือ baseline72/recent24, dominance ≥.66, ratio ≥1.04,
rise ≥.02, dominant energy ≥.05ATR², path ≥.12, buffer .18ATR,
continuation mode, `TP_RR=9.0`, `BE_RR=.02` และใช้ BUY/SELL.

Optimization/falsification:

- Initial fade มี63ดีล, WR4.76%, Net −60.51; continuation กลับเป็น +81.94
  ใน recent และบวก H1/WF จึง reject exhaustion hypothesis.
- Window24 เพิ่ม winners/Net ครบ recent/H1/WF เทียบ window28 เป็น
  4/+156.82, 6/+264.08, 11/+291.30 ก่อน threshold tuning.
- Dominance .66 รักษา winner set และเพิ่ม Net/ลด DD ครบสามช่วง;
  ที่ .67 recent เสีย1 winner และ .70 H1 เสียครึ่ง จึงล็อก .66 ก่อน cliff.
- RR9 เพิ่ม Net และ return/DD ครบสามช่วงเทียบ7R; RR10 ทำ H1 winners ลดและ
  DD เพิ่ม จึงล็อก9R. BE .05/.10 แย่ลง. BUY/SELL ต่างบวก.
- Buffer .14–.18 รักษา winner set; ที่ .20 WF winners ลด8→6 และ Net ลด
  322.22→232.94 จึงคง .18 ก่อน cliff.

Rolling 2 เดือนถึง 2026-07-30 ซึ่งไม่ใช้จูนมี38ดีล, 2 TP, WR5.26%,
Net +107.59, +1.76/day, +53.80/month, PF3.36, DD29.30.
Spread0.50 recent/H1/WF/latest ยังบวก +220.13/+276.85/+281.42/+96.19.

รวม WF+H1 ได้232ดีล, Net +627.87, DD48.05, return/DD13.07.
Risk ต่อดีล 1.53–16.58 USD, median5.99 USD. H1 overlap สูงกับ
S393=86, S361/S401=41, S380=33, S399=32 และ S371=30.

Portfolio interaction ไม่ผ่าน: baseline net18,453.59, DD231.25,
return/DD79.799. Default dominance .66 ที่น้ำหนัก .25/.50/.75/1.00 ให้ ratio
79.753/79.707/79.663/79.619. Portfolio-aware variants .70 และ .74 ก็ต่ำกว่า
baseline ทุกน้ำหนัก; ค่าสูงสุดของ .74 คือ79.642 ที่25%. จึง reject S403
ทุก allocation แม้ standalone profit สูง เพราะ adverse DD timing.

Payload smoke คืน BUY market order พร้อม entry4035.76, SL4030.91,
TP4079.42, BE.02 และ simulator ปิดดีลครบทุก signal. หลัง direction, window,
dominance, ratio, rise, energy, RR, BE, buffer, latest, spread, risk, overlap,
portfolio และ selectivity audits ไม่พบ allocation ที่เพิ่ม risk-adjusted return
จึงปิด S403 เป็น Portfolio Rejected และเริ่ม S404.

## S404 — Amihud Illiquidity-Shock Reversal 8R (Portfolio Rejected)

ไฟล์: `strategy404.py`

Edge: ใช้ absolute closed return ต่อ tick volume เป็น price-impact proxy แบบ Amihud
แล้ว normalize volume ภายในแต่ละ block. Recent upper-quantile impact ต้องขยายจาก
median ของ disjoint baseline blocks, มี signed impact ตรงกับ net path และ top impulse
มากพอ ก่อนรอ participated reversal candle ฝั่งตรงข้าม. Timing จึงต่างจาก release
continuation: เข้า market next-open หลัง reversal, SL event extreme+ATR, TP8R, BE.02.

Optimized default M5, spread0.20, 0.01 lot:

| Window | Closed | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน ถึง 2026-07-20 | 64 | 4.69% | +145.50 | +2.39 | +72.75 | 2.70 | 31.82 |
| 2026-H1 | 197 | 4.06% | +292.53 | +1.62 | +48.76 | 2.20 | 65.64 |
| 2025-H2 WF | 210 | 5.71% | +351.61 | +1.91 | +58.60 | 3.09 | 40.57 |

ค่าที่เลือกคือ baseline72/recent24, impact quantile .65, ratio ≥1.15,
rise ≥.01ATR, top impulse ≥.30ATR, signed impulse ≥.08ATR, path ≥.08,
reversal mode, buffer .18ATR, `TP_RR=8.0`, `BE_RR=.02`, BUY/SELL.

Optimization/falsification:

- Initial reversal +99.04 ใน recent ขณะที่ continuation +32.82/DD77.68;
  H1 reversal +212.29 และ WF +234.91 จึงคง reversal timing.
- Quantile .65 เพิ่ม recent/H1/WF เป็น +116.49/+225.17/+286.12 ที่7R.
  Local .64–.68 เป็น plateau; .70 ทำ WF เสีย2 winners จึงล็อก .65.
- Window28 เพิ่ม H1 แต่ WF ลดเหลือ +97.04/DD84.80; ratio1.30 ก็ลด WF
  จึงคง window24/ratio1.15. Signed gate .15 ตัด cross-window winners.
- RR8 รักษา H1/WF winners และเพิ่ม Net; RR9 ทำ H1 winners ลด8→6 และ DD
  กระโดด65.64→138.17 จึงล็อก8R. BE .05/.10 แย่ลง. BUY/SELL ต่างบวก.
- Buffer .18 เป็นค่าสุดท้ายก่อน WF cliff: ที่ .20 winners ลด12→11 แม้ Net เพิ่ม.

Rolling 2 เดือนถึง 2026-07-30 ซึ่งไม่ใช้จูนมี70ดีล, 3 TP, WR4.29%,
Net +140.72, +2.31/day, +70.36/month, PF2.55, DD47.01.
Spread0.50 recent/H1/WF/latest ยังบวก +126.30/+233.43/+288.61/+119.72.

รวม WF+H1 ได้407ดีล, Net +644.14, DD65.64, return/DD9.81.
Risk ต่อดีล 1.50–17.15 USD, median6.88 USD. H1 signal-time overlap ต่ำมาก:
S378=52, S376=5 และกลยุทธ์ active อื่นทั้งหมด=0 แสดงว่า entry timing กระจายจริง.

Portfolio interaction ยังไม่ผ่านเพราะ adverse exit-time DD: baseline net18,453.59,
DD231.25, return/DD79.799. น้ำหนัก .25/.50/.75/1.00 เพิ่ม Net แต่ DD เพิ่มเร็วกว่า
และ ratio ลดเป็น77.579/75.513/73.588/71.788; full DD เพิ่มเป็น266.03.
จึง reject S404 ทุก allocation แม้ signal overlap ต่ำและ standalone profit บวก.

Payload smoke คืน BUY market order พร้อม entry4023.78, SL4018.35,
TP4067.23, BE.02 และ simulator ปิดดีลตามกฎ conservative. หลัง impact threshold,
quantile, window, reversal/continuation, direction, RR, BE, buffer, latest, spread,
risk, overlap และ portfolio audits ไม่พบ allocation ที่เพิ่ม risk-adjusted return
จึงปิด S404 เป็น Portfolio Rejected และเริ่ม S405.

## S405 — Lo–MacKinlay Variance-Ratio Excursion Reversal 7R (Portfolio Rejected)

ไฟล์: `strategy405.py`

Edge: คำนวณ overlapping q-period return variance เทียบกับ q เท่าของ one-period
variance. `VR(q)<1` หมายถึง negative serial correlation/mean-reverting auction.
Recent VR ต้องต่ำกว่า disjoint baseline blocks และลดลงขั้นต่ำ ก่อนมี excursion
กับ participated reversal candle ฝั่งตรงข้าม. เข้า market next-open, SL หลัง event
extreme+ATR, TP7R และ BE.02 โดยใช้เฉพาะ closed bars.

Optimized default M5, spread0.20, 0.01 lot:

| Window | Closed | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2 เดือน ถึง 2026-07-20 | 62 | 3.23% | +94.73 | +1.55 | +47.36 | 4.73 | 10.67 |
| 2026-H1 | 195 | 4.62% | +357.13 | +1.97 | +59.52 | 3.30 | 69.71 |
| 2025-H2 WF | 214 | 3.74% | +180.59 | +0.98 | +30.10 | 2.36 | 51.76 |

ค่าที่เลือกคือ baseline72/recent24, horizon4, VR≤.95,
baseline/recent ratio≥1.05, VR drop≥.08, path≥.08, excursion≥.28ATR,
reversal mode, buffer .18ATR, `TP_RR=7.0`, `BE_RR=.02`, BUY/SELL.

Optimization/falsification:

- Initial reversal window32 ไม่มี7R winnerและ −53.15; continuation recent +87.16
  แต่ WF −33.07 จึงไม่ robust. Reversal window24 บวกครบ recent/H1/WF
  +93.73/+328.58/+162.16 จึงใช้ reversal window24.
- Horizon5 เพิ่ม recent winnerแต่ลด H1 Net/winner และ WF Net; horizon3 ก็ไม่ชนะ
  ครบทุกช่วง จึงคง horizon4. Ratio1.20 ตัด WF winner.
- VR drop .04–.08 รักษา winner setและปรับ Net/DD ต่อเนื่อง; ที่ .10 WF winners
  ลด8→7 และ Net180.59→140.12 จึงล็อก .08 ก่อน cliff.
- RR8 ทำ recent/H1 เสีย winners แม้ WF ดีขึ้น; RR9+ ทำ H1 DD สูงขึ้นมาก
  จึงคง7R. BE .05/.10 แย่ลง. Buffer .14 ตัด WF winnerและ .22 ตัด recent winner
  จึงคง .18. BUY เด่นใน WF ส่วน SELL เด่น recent/H1 จึงทดสอบทั้งคู่และแยกฝั่ง.

Rolling 2 เดือนถึง 2026-07-30 ซึ่งไม่ใช้จูนมี71ดีล, 2 TP, WR2.82%,
Net +83.13, +1.36/day, +41.56/month, PF3.25, DD20.13.
Spread0.50 recent/H1/WF/latest ยังบวก +76.13/+298.63/+116.39/+61.83.

รวม WF+H1 ได้409ดีล, Net +537.72, DD69.71, return/DD7.71.
Risk ต่อดีล 1.21–16.96 USD, median5.59 USD. H1 signal-time overlap ต่ำ:
S378=30, S376=4 และ active strategy อื่น=0.

Portfolio interaction ไม่ผ่าน: baseline net18,453.59, DD231.25,
return/DD79.799. ทั้งสองฝั่งที่น้ำหนัก .25/.50/.75/1.00 ให้ ratio
77.035/74.492/72.144/69.970. Portfolio-aware direction variants ก็ไม่ผ่าน:
BUY-only 25%=78.027 และ SELL-only 25%=78.353 ก่อนลดลงเมื่อเพิ่มน้ำหนัก.
จึง reject S405 ทุก allocation เพราะ adverse exit-time DD.

Payload smoke คืน SELL market order พร้อม entry4028.40, SL4032.81,
TP3997.53, BE.02 และ simulator ปิดดีลครบทุก signal. Event cache ของ active
baseline และ candidate ถูกบันทึกที่ `scratch/portfolio_s405_events.json`
สำหรับ audit รอบถัดไป. หลัง direction, window, horizon, VR thresholds, RR, BE,
buffer, latest, spread, risk, overlap, portfolio และ direction-allocation audits
ไม่พบ allocation ที่เพิ่ม risk-adjusted return จึง reject S405 และเริ่ม S406.

## S406 — Asian Garman–Klass Compression Release 7R (Cross-Window Rejected)

ไฟล์: `strategy406.py`

Edge hypothesis: ใช้ Garman–Klass range volatility จาก high/low และ open/close
เพื่อหา recent compression ต่ำกว่า disjoint baseline blocks แล้วเข้า next-open หลัง
participated close breakout ในช่วง 06:00–15:00 BKK ซึ่งเป็น session ที่ active
portfolio มี event น้อย. SL อยู่หลัง release extreme+ATR, TP7R และ BE.02.

Default M5, spread0.20, 0.01 lot, 2 เดือนถึง 2026-07-20:

| Closed | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|
| 28 | 0.00% | −30.19 | −0.49 | −15.10 | 0.00 | 30.19 |

Falsification:

- Continuation default และ compression ratio/window/release/session variants ทุกตัว
  ไม่มี7R winner ใน recent; no-close-break มี1 winnerแต่ยัง −18.49.
- ทดสอบ false-break fade เป็นสมมติฐานตรงข้าม. Fade no-break ให้ recent 134ดีล,
  WR11.94%, Net +8.51, PF1.07, DD38.98 และ H1 +0.90 แต่ WF −25.65/DD67.02.
- Fade ratio.70 ให้ recent +0.21 และ H1 +69.13 แต่ WF −54.29.
  Fade base/release/window/session variants อื่น WF ลบทั้งหมด −52.73 ถึง −103.31.
- จึงไม่มี configuration ที่บวกครบ recent/H1/WF และไม่เข้าสู่ payoff/latest/spread/
  portfolio optimization เพื่อหลีกเลี่ยงการ overfit กลยุทธ์ที่ cross-window edge ล้มเหลว.

โค้ดรองรับทั้ง continuation/fade, close-break toggle, dynamic ATR/structure risk,
payload `be_rr`/`cancel_bars` และไม่มี lookahead. สรุป reject S406 ที่ cross-window
gate; active portfolio ยังคงถึง S402 และเริ่ม S407.

## S407 — Corwin–Schultz Implied-Spread Expansion 7R (Accepted + Optimized)

ไฟล์: `strategy407.py`

Edge hypothesis: Corwin–Schultz estimator ใช้ high/low ของแท่งคู่แยก implied
transaction-cost shock ออกจาก directional return โดยตรง. S407 เปรียบ recent
upper-tail spread กับ disjoint baseline blocks, ต้องมี directional path ที่มี
efficiency และใช้ participated closed candle ยืนยันทิศทาง. เข้า market ที่ next-open,
SL หลัง event extreme บวก ATR .18 และ TP7R จึงไม่มี lookahead และไม่ใช้ fixed SL.

Default M5, spread0.20, 0.01 lot, 2 เดือนถึง 2026-07-20:

| Closed | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|
| 62 | 4.84% | +149.25 | +2.45 | +74.63 | 2.82 | 38.16 |

ความถูกต้องข้ามช่วงและ stress:

- H1 หกเดือน: 162 ดีล, WR4.32%, Net +319.80, PF2.85, DD52.57.
- WF หกเดือน disjoint: 229 ดีล, WR3.06%, Net +93.94, PF1.66, DD78.39.
- Latest rolling ถึง 2026-07-30: 62 ดีล, WR4.84%, Net +150.85,
  +2.47/day, +75.43/month, PF2.88, DD49.98.
- Spread0.50 recent/H1/WF/latest ยังบวก +130.65/+271.20/+25.24/+132.25.
- WF+H1 รวม391ดีล, Net +413.74, DD85.59. Risk ต่อดีล 1.56–17.82 USD,
  median6.11 USD; quoted payoff คง7R และ BE เริ่ม .02R บนแท่งถัดไป.

Portfolio gate ผ่านชัดเจน: frozen active baseline ถึง S402 มี Net18,453.59,
DD231.25, return/DD79.799. เพิ่ม S407 ที่น้ำหนัก1.00 ทำ Net18,867.33,
DD197.80 และ return/DD95.386. Weight .25/.50/.75 ให้83.257/86.985/91.015;
ส่วน1.25/1.50/2.00 ลดลงเป็น94.967/94.443/93.430 จึงล็อก1.00.

Optimization ครอบคลุม reversal/continuation, spread ratio/rise/quantile,
positive-pair fraction, window20/24/28, path/net move, event volume/body/range/
close, session, direction, RR7–10, BE, ATR buffer, risk cap และ portfolio weight.
Continuation ชนะ reversal ทุก cross-window. Body fraction .70 ทำ standalone
ดีขึ้น แต่ portfolio DD แย่ลงจน ratio78.526 จึงไม่ overfit ตาม standalone.
Ratio1.00, path.06 และ buffer.22 ได้ portfolio ratio84.536/94.920/95.299
ซึ่งยังต่ำกว่า default95.386. ไม่พบ robust portfolio improvement เพิ่มเติม.

Default ที่แนะนำอยู่ใน `DEFAULT_CFG`: baseline72, recent24, quantile.70,
spread ratio1.20, path.12, event body.45ATR, body fraction.58, session15–23,
SL buffer.18ATR, max risk1.75ATR, continuation, TP7R, BE.02 และ cancel3.
Payload smoke จากสัญญาณจริงคืน BUY entry4033.99, SL4030.45, TP4058.77,
`be_rr=.02`, `cancel_bars=3`. S407 ผ่านเกณฑ์ short dynamic SL + TP>=7R และ
portfolio survival; หยุดเลขใหม่ระหว่าง optimization แล้ว เมื่อ plateau ยืนยัน
จึงรับ S407 เข้าสู่ active baseline และลำดับถัดไปคือ S408.

## S408 — Yang–Zhang Gap-Share Dislocation Release 7R (Accepted + Optimized)

ไฟล์: `strategy408.py`

Edge hypothesis: แยก bar-to-bar opening jump energy ออกจาก Rogers–Satchell
intrabar diffusion และ open-close energy แบบ Yang–Zhang components. Recent gap
share ต้องขยายเหนือ disjoint baseline blocks พร้อม efficient directional path;
จากนั้นใช้ participated closed candle ยืนยันทิศและเข้า next-open. กลไกนี้วัด
aggregate microstructure repricing ไม่ใช่ weekend gap และไม่ซ้ำ S407 high-low
implied spread. SL หลัง event extreme บวก ATR .18, TP7R และไม่มี lookahead.

Final M5, spread0.20, 0.01 lot, 2 เดือนถึง 2026-07-20:

| Closed | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|
| 40 | 7.50% | +91.24 | +1.50 | +45.62 | 2.92 | 17.48 |

Cross-window และ stress:

- H1 หกเดือน: 109 ดีล, WR4.59%, Net +154.41, PF2.55, DD47.93.
- WF หกเดือน disjoint: 107 ดีล, WR5.61%, Net +82.69, PF2.42, DD22.26.
- Latest rolling ถึง 2026-07-30: 37 ดีล, WR5.41%, Net +37.57,
  +0.62/day, +18.78/month, PF2.02, DD17.48.
- Spread0.50 recent/H1/WF/latest ยังบวก +79.24/+121.71/+50.59/+26.47.
- WF+H1 รวม216ดีล, Net +237.10, DD47.93. Risk1.27–17.16 USD,
  median5.21 USD; quoted payoff7R และ BE .02R เริ่มประเมินแท่งถัดไป.

Portfolio gate ใช้ frozen baseline ที่รวม S407: Net18,867.33, DD197.80,
return/DD95.386. เพิ่ม final S408 ที่1.00x เป็น Net19,104.43, DD198.16,
return/DD96.409. Allocation .25/.50/.75 ได้95.729/95.956/96.183.
1.25x ให้ theoretical maximum96.635 ก่อนลดเป็น96.595 ที่1.50x และ91.601
ที่2.00x; แต่ฐาน0.01 lot ไม่สามารถ deploy0.0125 lot จึงล็อก executable1.00x.

Optimization ครอบคลุม continuation/fade, gap share/ratio/rise/energy,
window20/24/28, path, Asian/US sessions, direction, RR7–10, BE, SL buffer,
risk cap, volume/body/range/close gates และ portfolio allocation. Asian07–15
ทำ standalone H1+WF +372.29 แต่ทำ portfolio ratioลดเหลือ91.946 จึง reject.
RR10, BUY-only และ share.0005 ได้95.585/95.951/95.553 ต่ำกว่า final.

Close-location sensitivity .72/.75/.78/.80 ให้ portfolio ratio
96.190/96.339/96.409/96.321 จึงเลือก midpoint .78 บน plateau ไม่ชิด cliff.
Body.60 และ close.75+body.60 ได้96.298/96.228 จึงไม่เพิ่ม confluence.
Default ที่แนะนำ: baseline72, recent24, gap share≥.0002, ratio≥1.20,
rise≥.00005, energy≥3e-9, path≥.12, event close fraction≥.78,
session15–23, SL buffer.18ATR, max risk1.75ATR, TP7R, BE.02, cancel3.

Payload smoke จริงคืน BUY entry4033.99, SL4030.45, TP4058.77,
`be_rr=.02`, `cancel_bars=3`. S408 ผ่าน short dynamic SL + TP>=7R และ
portfolio survival; หลัง optimization ไม่พบ robust executable improvement
เหนือ close.78/weight1.00 จึงรับ S408 เข้าสู่ active baseline และเริ่ม S409.

## S409 — Opening-Gap Response-Correlation Follow-Through 8.25R (Accepted + Optimized)

ไฟล์: `strategy409.py`

Edge hypothesis: วัด Pearson dependence ระหว่าง bar-to-bar opening gap กับ
open-to-close return ในแท่งเดียวกัน. Positive correlation ที่ขยายเหนือ disjoint
baseline หมายถึง opening repricing ได้รับ follow-through ไม่ถูก fade. ต้องมี
directional gap bias, aligned efficient close path และ participated closed event
ใน Asian 07:00–15:00 BKK. Edge นี้วัด response dependence ต่างจาก S408 ที่วัด
gap magnitude share. เข้า next-open, SL หลัง event extreme+.18ATR และไม่มี lookahead.

Final M5, spread0.20, 0.01 lot, 2 เดือนถึง 2026-07-20:

| Closed | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|
| 15 | 6.67% | +81.80 | +1.34 | +40.90 | 17.13 | 3.07 |

Cross-window และ stress:

- H1 หกเดือน: 39 ดีล, WR12.82%, Net +358.58, PF10.75, DD22.46.
- WF หกเดือน disjoint: 51 ดีล, WR5.88%, Net +60.15, PF2.87, DD26.89.
- Latest rolling: 15 ดีล, WR6.67%, Net +77.89, +1.28/day,
  +38.95/month, PF9.67, DD7.18.
- Spread0.50 recent/H1/WF/latest ยังบวก +77.30/+346.88/+44.85/+73.39.
- WF+H1 รวม90ดีล, Net +418.73, DD26.89. Risk1.14–15.28 USD,
  median5.27 USD และ TP8.25R.

Portfolio gate ใช้ frozen baseline ที่รวม S408: Net19,104.43, DD198.16,
return/DD96.409. Final S409 ที่1x ให้ Net19,523.16, DD198.56,
return/DD98.324. Allocation curve .25/.50/.75/1.00/1.50/2.00/2.50/2.75/
3.00/3.25/4.00 ให้96.888/97.367/97.846/98.324/99.278/100.231/101.181/
101.656/101.793/101.003/98.752. จึงล็อก executable weight3.00 = 0.03 lot
ก่อน DD acceleration; portfolio final Net20,360.62, DD200.02, ratio101.793.

Optimization ครอบคลุม follow-through/fade, path alignment, correlation
absolute/ratio/rise, gap bias, windows, path, session, direction, RR7–10,
BE, ATR buffer, volume/body/fraction/close gates และ allocation. US default
ล้ม WF −0.86 แต่ Asian07–15 บวกครบและ portfolio timing ดี. No-align แม้
standalone +498.64 ให้ portfolio ratio98.429 ต่ำกว่า final weighted setup.

Payoff sensitivity รักษา H1 5 TP ที่ RR7.50/8.00/8.25 และลดเหลือ4ตั้งแต่
8.50R; WF รักษา3 TP. จึงเลือก8.25R ก่อน cliff .25R. RR8/9/10 ที่1x ให้
portfolio ratio98.249/98.142/98.223 ต่ำกว่า8.25R=98.324. Volume1.20 และ
body fraction.70 ให้98.116/98.151 จึงคง event gates เดิม.

Default แนะนำ: baseline72, recent24, |corr|≥.15, corr ratio≥1.20,
rise≥.05, gap bias≥.08, path≥.12, aligned follow-through, session07–15,
event body≥.45ATR, close fraction≥.72, SL buffer.18ATR, max risk1.75ATR,
TP8.25R, BE.02, cancel3. Payload smoke คืน SELL entry4169.26, SL4179.79,
TP4082.38 พร้อม `be_rr=.02`/`cancel_bars=3`. S409 ผ่าน short dynamic SL,
TP>=7R และ portfolio survival; หลัง optimize ถึง allocation peak จึงรับ S409
ที่ weight3.00 เข้าสู่ active baseline และเริ่ม S410.

## S410 — Rousseeuw–Croux Sn/Qn Robust-Shape Release 7R (Portfolio Rejected)

ไฟล์: `strategy410.py`

Edge hypothesis: Sn ใช้ median ของ median-distance รอบ observation แต่ละตัว
ส่วน Qn ใช้ lower quartile ของ pairwise distances ทั้งหมด. อัตรา Sn/Qn จึงวัด
robust distribution shape ไม่ใช่ raw volatility expansion แบบ S401. Recent
shape ต้องขยายเหนือ disjoint baseline พร้อม Sn scale, efficient path และ
participated closed event. เข้า next-open, SL event extreme+.18ATR และ TP7R.

Default M5, spread0.20, 0.01 lot, 2 เดือนถึง 2026-07-20:

| Closed | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|
| 36 | 16.67% | +281.57 | +4.62 | +140.79 | 13.20 | 8.34 |

Cross-window และ stress standalone ผ่าน:

- H1 หกเดือน: 101 ดีล, WR5.94%, Net +223.77, PF3.53, DD41.05.
- WF หกเดือน disjoint: 131 ดีล, WR3.05%, Net +80.15, PF1.90, DD59.00.
- Latest rolling: 38 ดีล, WR10.53%, Net +179.68, +2.95/day,
  +89.84/month, PF6.55, DD16.03.
- Spread0.50 recent/H1/WF/latest ยังบวก +270.77/+193.47/+40.85/+168.28.
- H1+WF รวม232ดีล, Net +303.92, DD59.00. Risk1.68–16.87 USD,
  median6.10 USD และ quoted TP7R.

แต่ portfolio interaction ไม่ผ่าน: frozen baseline ที่รวม S409 weight3.00 มี
Net20,360.62, DD200.02, return/DD101.793. เพิ่ม default S410 ที่น้ำหนัก
.25/.50/.75/1.00 ทำ ratio ลดเป็น98.549/95.527/92.706/90.065 เพราะ exit losses
ซ้อนกับ drawdown เดิม แม้ standalone จะดีมาก.

Falsification/optimization ครอบคลุม shape expansion/contraction, path fade,
shape ratio/rise, Sn ratio/rise, windows20/24/28, path, Asian/US sessions,
BUY/SELL และ late-US segmentation. Salvage candidates ทั้งหมดไม่ผ่าน:

- recent28 standalone H1+WF +397.19 แต่ portfolio .25x=99.767.
- recent28 BUY-only standalone +302.35 แต่ portfolio .25x=101.181.
- SELL-only standalone +281.41 แต่ portfolio .25x=98.760.
- session17–23 / 19–23 standalone +307.50/+297.09 แต่ .25x=99.050/99.037.
- ค่าเหล่านี้ต่ำกว่า baseline101.793 ทุก allocation ที่ทดสอบ จึงไม่มี
  portfolio-aware direction/window salvage.

Payload smoke คืน SELL entry4032.97, SL4042.64, TP3965.28, BE.02 และ cancel3.
โค้ดไม่มี lookaheadและ spread stress ผ่าน แต่ objective เป็นพอร์ตไม่ใช่ standalone;
จึง reject S410 ไม่เพิ่มใน frozen baseline และเริ่ม S411.

## S411 — Tail-Range Wick-Absorption Release 7R (Portfolio Rejected)

ไฟล์: `strategy411.py`

Edge hypothesis: เลือกเฉพาะแท่งที่ range อยู่ upper-tail ของแต่ละ block แล้ววัด
normalized lower-wick minus upper-wick. Tail-conditioned wick asymmetry แยก
liquidity rejection ตอน stress จาก wick noise ปกติ และเปรียบ recent strength กับ
disjoint baseline. Final standalone ใช้ baseline60/recent20, US15–23, efficient
path และ participated event; เข้า next-open, SL event extreme+.18ATR, TP7R.

Final M5, spread0.20, 0.01 lot, 2 เดือนถึง 2026-07-20:

| Closed | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|
| 65 | 4.62% | +99.97 | +1.64 | +49.99 | 2.72 | 47.50 |

Cross-window และ stress standalone ผ่าน:

- H1 หกเดือน: 179 ดีล, WR7.82%, Net +604.59, PF5.34, DD36.84.
- WF หกเดือน disjoint: 226 ดีล, WR4.87%, Net +191.68, PF2.45, DD46.44.
- Latest rolling: 66 ดีล, WR6.06%, Net +108.82, +1.78/day,
  +54.41/month, PF2.61, DD55.60.
- Spread0.50 recent/H1/WF/latest ยังบวก +80.47/+550.89/+123.88/+89.02.
- H1+WF รวม405ดีล, Net +796.27, DD46.44. Risk1.02–16.96 USD,
  median5.58 USD และ quoted TP7R.

Direction falsification พบว่า initial Asian wick-direction continuation ไม่มี TP
และ −51.79; opposite/fade ได้ +91.34. แต่ US continuation ได้ recent +110.81,
H1 +519.77, WF +179.72. Window20 ช่วย cross-window จึงเลือก US+window20 เป็น
standalone final. Fade+window20 ก็ผ่าน +129.75/+632.28/+82.99.

Portfolio interaction ไม่ผ่านทุก finalist. Baseline ถึง S409 weight3 มี
Net20,360.62, DD200.02, return/DD101.793:

- final US+window20 ที่ .25/.50/.75/1.00 ให้101.435/100.829/100.210/99.609.
- fade+window20 ให้101.466/101.146/100.834/100.529.
- US window24 ให้101.169 ที่.25; Asian fade ให้101.111 ที่.25.
- แม้ standalone return/DD สูง15–17 แต่ exit losses ซ้อน portfolio drawdown.

Optimization ครอบคลุม wick/fade direction, path alignment, tail quantile,
imbalance/ratio/rise, tail-range distinction, path, windows20/24/28 และ sessions.
ไม่มี portfolio-aware allocation ที่ชนะ101.793 จึง reject S411 ไม่เพิ่มใน frozen
baseline. Payload smoke คืน SELL entry4026.34, SL4032.99, TP3979.79,
BE.02/cancel3; โค้ดไม่มี lookaheadและพร้อม audit. ลำดับถัดไป S412.

## S412 — Consecutive-Range IoU Auction Displacement 7R (Cross-Window Rejected)

ไฟล์: `strategy412.py`

Edge hypothesis: คำนวณ intersection-over-union ของ high-low ranges ระหว่าง
แท่งติดกัน. Recent median IoU ที่ลดจาก disjoint baseline หมายถึง auction ย้าย
territory ออกจากกรอบเดิม ไม่ใช่เพียง volatility ใหญ่ขึ้น. ใช้ช่วง overnight
00:00–07:00 BKK เพื่อกระจาย timing, efficient path และ participated closed
event; เข้า next-open, SL event extreme+.18ATR และ TP7R.

Default M5, spread0.20, 0.01 lot, 2 เดือนถึง 2026-07-20:

| Closed | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|
| 13 | 7.69% | +18.66 | +0.31 | +9.33 | 1.88 | 20.58 |

Cross-window ไม่ผ่าน:

- H1 หกเดือน: 36 ดีล, WR5.56%, Net +24.28, PF1.58, DD21.25.
- WF หกเดือน disjoint: 32 ดีล, WR3.13%, Net −21.09, PF0.24, DD22.67.
- Latest rolling: 13 ดีล, WR7.69%, Net +24.08, +0.39/day,
  +12.04/month, PF2.53, DD14.56.
- Spread0.50 recent/H1 ยังบวก +14.76/+13.48 แต่ WF ลดเป็น −30.69;
  latest ยัง +20.18.

Falsification ครอบคลุม contraction/expansion, continuation/fade, overlap
ratio/drop, expansion threshold, path, windows20/24/28 และ overnight/Asian/US.
Asian continuation recent/H1 +41.63/+207.22 แต่ WF −55.07; path.20 Asian
WF −36.09. Overnight drop.08 และ expansion variants ก็ WF ลบ.

Direction ablation ไม่ salvage: BUY-only recent/H1/WF −6.22/+2.20/−6.71,
SELL-only +24.88/+22.08/−14.38; drop.08 BUY/SELL WF −4.73/−13.98.
จึงไม่มี configuration ที่บวกครบ recent/H1/WF และไม่เข้าสู่ portfolio
optimization เพื่อหลีกเลี่ยง overfit กลยุทธ์ที่ regime survival ล้มเหลว.

Payload smoke คืน SELL entry4115.63, SL4121.35, TP4075.58, BE.02/cancel3.
โค้ดไม่มี lookaheadและ spread/SL-first rules ครบ แต่ reject S412 ที่
cross-window gate; frozen baseline ยังคงถึง S409 weight3 และเริ่ม S413.

## S413 — Robust-Shape / Gap-Response Decoupled BUY Release 7R (Portfolio Rejected)

ไฟล์: `strategy413.py`

Edge hypothesis: แยกปัจจัย Sn/Qn robust-shape displacement ของ S410 ออกจาก
opening-gap response ของ S409 โดยรับเฉพาะช่วงที่ absolute gap-response correlation
ต่ำ ใช้ recent28 BUY-only, US session15–23, efficient path และแท่ง event ที่มี
participation; เข้า next-open, SL event extreme+.18ATR และ TP7R. เป้าหมายคือเก็บ
distribution-shape repricing โดยไม่เพิ่ม exposure ที่ซ้ำกับ S409 weight3.

Final M5, spread0.20, 0.01 lot, 2 เดือนถึง 2026-07-20:

| Closed | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|
| 9 | 11.11% | +34.85 | +0.57 | +17.43 | 22.78 | 1.00 |

Cross-window และ spread stress standalone ผ่าน:

- H1 หกเดือน: 41 ดีล, WR4.88%, Net +103.74, PF3.43, DD21.29.
- WF หกเดือน disjoint: 55 ดีล, WR10.91%, Net +167.00, PF11.85, DD6.00.
- Latest rolling: 11 ดีล, WR9.09%, Net +28.07, +0.46/day,
  +14.04/month, PF4.35, DD7.58.
- Spread0.50 recent/H1/WF/latest ยังบวก +32.15/+91.44/+150.50/+24.77.

Portfolio interaction ไม่ผ่าน. Baseline ถึง S409 weight3 มี Net20,360.62,
DD200.02, return/DD101.793. Candidate ที่ดีที่สุดคือ session17–23 ที่ .25x
ได้101.437; default ได้101.390. corr010/corr025/both/path020 และ allocation
.25/.50/.75/1.00 ต่ำกว่า baseline ทั้งหมด จึงไม่มี portfolio-aware salvage.

Payload smoke คืน BUY entry4163.99, SL4156.84, TP4214.04, BE.02/cancel3.
โค้ดสร้างคำสั่งเทรดได้จริง ไม่มี lookahead และผ่าน spread/SL-first rules แต่
objective คือความแข็งแรงของพอร์ต จึง reject S413 และไม่เพิ่มใน frozen baseline.

## S414 — Volume-Normalized Price-Impact Fade BUY 8R (Portfolio Accepted)

ไฟล์: `strategy414.py`

Edge hypothesis: วัด median ของ absolute intrabar log-return ต่อ square-root
tick volume แล้วเทียบ recent24 กับ baseline72 ที่แบ่งเป็น block ไม่ทับกัน. Impact
ที่ขยายขึ้นพร้อม signed square-root-volume imbalance ฝั่งลบเป็น proxy ว่า sell flow
ใช้สภาพคล่องมากผิดปกติ; S414 fade กลับ BUY เมื่อแท่ง bullish event ที่ปิดแล้วมี
body≥0.65ATR และ participation ยืนยัน. เข้า next-open, SL ต่ำกว่า event low+.18ATR,
TP8R, BE0.02R และใช้เฉพาะ session07–15 BKK.

Final M5, spread0.20, 0.01 lot, 2 เดือนถึง 2026-07-20:

| Closed | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|
| 25 | 4.00% | +11.92 | +0.20 | +5.96 | 1.38 | 26.09 |

Cross-window และ stress ผ่านครบ:

- H1 หกเดือน: 45 ดีล, WR6.67%, Net +112.26, PF3.90, DD21.56.
- WF หกเดือน disjoint: 39 ดีล, WR7.69%, Net +93.12, PF3.95, DD21.37.
- Latest rolling: 24 ดีล, WR4.17%, Net +11.08, +0.18/day,
  +5.54/month, PF1.35, DD30.96.
- Spread0.50 recent/H1/WF/latest ยังบวก +4.42/+98.76/+81.42/+3.88.
- Payload smoke คืน BUY entry3978.95, SL3966.41, TP4079.27 หรือ 8R,
  BE0.02/cancel3.

Optimization เริ่มจาก continuation/fade, direction, impact/imbalance/path,
windows, sessions, event gates และ RR7–9. Survivor คือ fade-BUY. Neighborhood
ของ body0.50/0.55/0.60/0.65 และ imbalance0.10/0.12/0.15 ยังบวกครบ; body0.70
ยังบวกแต่ portfolio แย่ลง และ body0.75 เป็น cliff เพราะ H1 เสีย winner สำคัญ.
RR8 ดีสุดที่ยังผ่าน recent; RR8.25 ทำ recent ไม่มี winner จึงไม่ใช้.

Portfolio baseline ถึง S409 weight3 มี Net20,360.62, DD200.02,
return/DD101.793. Final S414 body0.65/imbalance0.15/TP8 ที่ weight7.85 ให้
Net21,972.85, DD189.42, return/DD116.000. ค่า body0.55/0.60 ให้115.202/115.294
และ body0.70 ให้111.397 จึงเลือก 0.65 ซึ่งเป็นจุดก่อน cliff. Frozen cache ใหม่คือ
`scratch/portfolio_s414_events.json`; หยุดสร้างหมายเลขใหม่เพื่อ optimize S414
ตามกติกา survivor และจะกลับไปสร้าง S415 เมื่อไม่มี robust improvement เพิ่ม.

## S415 — Conditional Direction-Entropy Release 7R (Portfolio Rejected)

ไฟล์: `strategy415.py`

Edge hypothesis: แปลงทิศของแท่งปิดเป็น first-order two-state Markov chain แล้ว
คำนวณ conditional binary entropy ของ P(UP|UP) และ P(UP|DOWN). Recent entropy
ที่ต่ำกว่า disjoint baseline หมายถึงลำดับ order flow มี predictability ชั่วคราว;
ใช้ state ของแท่ง event ที่ปิดแล้วเลือก forecast สำหรับแท่งถัดไป. Final standalone
ใช้ session15–23 BKK, event participation/body/range control, next-open entry,
event-extreme+.18ATR SL และ TP7R.

Final M5, spread0.20, 0.01 lot, 2 เดือนถึง 2026-07-20:

| Closed | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|
| 26 | 15.38% | +76.96 | +1.26 | +38.48 | 3.03 | 18.29 |

Cross-window standalone:

- H1 หกเดือน: 71 ดีล, WR14.08%, Net +139.82, PF2.33, DD28.75.
- WF หกเดือน disjoint: 108 ดีล, WR10.19%, Net +158.00, PF2.70, DD35.78.
- Latest rolling: 28 ดีล, WR7.14%, Net +2.82, PF1.07, DD17.02.
- Spread0.50 recent/H1/WF ยังบวก +69.16/+118.52/+125.60 แต่ latest ลดเป็น
  −5.58 จึงมี rolling spread fragility.

Direction falsification สนับสนุน edge: default recent +71.57 แต่ inverted forecast
−90.95. Session15–23 แข็งกว่าช่วงอื่น; H1/WF +139.82/+158.00. Entropy drop0.08
ได้ +141.55/+123.38 และ SELL-only late session ให้ DD24.11/15.85.

Portfolio baseline ถึง S414 weight7.85 มี Net21,972.85, DD189.42,
return/DD116.000. ทุก finalist และทุก positive allocation ทำให้ ratio ลดลง:
ที่ 0.05x session15–23=115.635, drop0.08=115.626, BUY-only=115.737 และ
SELL-only=115.895. จึงไม่มี portfolio-aware salvage แม้ standalone ดี.
Payload smoke คืน BUY entry4030.65, SL4029.76, TP4036.88, BE0.02/cancel3.
Reject S415; frozen baseline ยังคง `scratch/portfolio_s414_events.json` และเริ่ม S416.

## S416 — Bipower Jump-Energy Release 7R (Portfolio/Stress Rejected)

ไฟล์: `strategy416.py`

Edge hypothesis: realized variance รวม continuous variation และ jumps ขณะที่
bipower variation ทนต่อ isolated jumps มากกว่า. ใช้ RV/BV ratio ของ recent24
เทียบ disjoint baseline72 และ signed quadratic-return energy ระบุฝั่งที่ครอง jump
risk. Final standalone ใช้ absolute jump ratio≥0.90, expansion≥1.10,
participated confirming event, full session, next-open entry, event-extreme+.18ATR
SL และ TP7R.

M5, spread0.20, 0.01 lot, 2 เดือนถึง 2026-07-20:

| Closed | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|
| 171 | 2.92% | +16.46 | +0.27 | +8.23 | 1.08 | 70.18 |

Cross-window standalone ที่ spread0.20:

- H1 หกเดือน: 456 ดีล, WR3.51%, Net +381.08, PF1.79, DD87.35.
- WF หกเดือน disjoint: 512 ดีล, WR4.49%, Net +354.12, PF2.33, DD134.70.
- Latest rolling: 160 ดีล, WR2.50%, Net −1.21, PF0.99, DD78.57.
- Spread0.50 H1/WF ยังบวก +244.28/+200.52 แต่ recent/latest ลดเป็น
  −34.84/−49.21 จึงไม่ผ่าน spread robustness.

Falsification พบ default jump1.10 recent −8.02; ลด absolute threshold เป็น0.90
ทำให้บวกครบ recent/H1/WF. Recent20 ก็ +7.83/+233.06/+219.53. Session filters
ไม่เสถียร. Direction ablation ของ jump0.90: BUY recent/H1/WF
−5.99/+177.93/+259.06; SELL +22.45/+202.75/+93.46.

Portfolio baseline ถึง S414 มี return/DD116.000. ที่ allocation0.05x:
jump0.90=115.758, recent20=114.748, jump-BUY=115.789,
jump-SELL=115.864; allocation สูงกว่านี้ยิ่งแย่ จึงไม่มี portfolio salvage.
Payload smoke คืน BUY entry4049.32, SL4041.48, TP4104.20, BE0.02/cancel3.
Reject S416; frozen baseline ยังคง S414 และเริ่ม S417.

## S417 — Multi-Horizon Variance-Ratio Contract/Fade 7R (Portfolio Accepted)

ไฟล์: `strategy417.py`

Edge hypothesis: คำนวณ Lo–MacKinlay-style variance ratio จาก variance ของ
overlapping 4-bar log returns หารด้วย 4 เท่าของ one-bar variance. VR ที่หดตัว
จาก disjoint baseline บ่งชี้ negative serial dependence/mean reversion; final
branch fade ทิศของ recent path หลัง participated confirming event. ใช้เฉพาะ
แท่งปิด, full session, path efficiency≥0.08, next-open entry, event extreme+.18ATR
SL, TP7R และ BE0.02R.

Final M5, spread0.20, 0.01 lot, 2 เดือนถึง 2026-07-20:

| Closed | Win rate | Net | P&L/day | P&L/month | PF | Max DD |
|---:|---:|---:|---:|---:|---:|---:|
| 156 | 2.56% | +87.81 | +1.44 | +43.90 | 2.01 | 43.43 |

Cross-window และ spread stress ผ่านครบ:

- H1 หกเดือน: 430 ดีล, WR4.42%, Net +719.21, PF3.31, DD51.33.
- WF หกเดือน disjoint: 497 ดีล, WR3.02%, Net +208.94, PF1.74, DD83.97.
- Latest rolling: 167 ดีล, WR2.40%, Net +70.41, +1.15/day,
  +35.20/month, PF1.68, DD43.43.
- Spread0.50 recent/H1/WF/latest ยังบวก +41.01/+590.21/+59.84/+20.31.
- Payload smoke คืน SELL entry4028.40, SL4032.81, TP3997.53 หรือ7R,
  BE0.02/cancel3.

Falsification ครอบคลุม VR expansion/contraction, continuation/fade, horizon2–6,
contraction ratio/drop, path, windows, sessions, direction, event filters และ RR.
Expansion default recent +164.56 แต่ contract-fade กระจาย portfolio ดีกว่า.
TP7.5/8 ลด recent จาก +75.41 เป็น +30.31/+38.31 จึงพบ RR cliff หลัง7R.
Horizon5 standalone ดีขึ้นบางช่วงแต่ portfolio121.301 ต่ำกว่า horizon4=121.874.

Local path cliff: 0.07/0.08/0.09 ให้ portfolio return/DD
122.228/124.587/124.576. Path0.09 เสีย recent winner หนึ่งดีล จึงเลือก0.08
ก่อน cliff. Final allocation0.78 ได้ Net22,696.81, DD182.18,
return/DD124.587 เทียบ frozen S414 Net21,972.85, DD189.42, ratio116.000.
Frozen cache ใหม่คือ `scratch/portfolio_s417_events.json`. หยุด numbering เพื่อ
optimize S417 จน plateau นี้; รอบถัดไปกลับไปสร้าง S418.
