# สรุปสุดท้าย — งานวิจัยกลยุทธ์ XAUUSD Standalone (S21-S58 + Blend/Regime/Exit Optimization)

วันที่ปิดรอบ: 2026-06-29
สถานะ: ✅ ปิดรอบด้วย **13-way Lean Blend** เป็น champion สุดท้าย

---

## 🏆 "Champion": 13-way Lean Blend (Consistency-Tuned) — ตัวเลือก default

**หมายเหตุการตั้งชื่อ (2026-06-29):** โปรเจกต์นี้มี blend ที่ใช้งานได้จริง 2 ตัว ไม่ใช่แค่ตัวเดียว —
**"Champion"** (13-way, เอกสารนี้) กับ **"Max-Yield Blend"** (16-way, เน้น $ สูงสุด, ดูท้ายเอกสาร)
ทั้งคู่ผ่านการทดสอบครบ ไม่มีตัวไหน "ตก" เป็นแค่ trade-off ระหว่าง consistency กับเงินดิบ

รัน 13 ระบบพร้อมกันเต็มทุนบนทุน $1000 แต่ละระบบ (ที่ทุนระดับนี้ lot ติดพื้นขั้นต่ำ 0.01 เสมอ ทำให้
แบ่งทุนแบบ fractional ไม่ต่างจากรันเต็มทุนพร้อมกันแล้วรวม PnL)

**ตัวเลข robust (เฉลี่ย 5 window 60-180 วัน):**
- **$/เดือน: $7,908 - $8,658** (~$264-289/วัน จากทุน $1,000)
- **Sharpe-like: 0.49 - 0.71**
- **Max losing-day streak: 3-4 วัน**
- **% วันบวก: ~62-69%**

**ห่างเป้า $1,000/วัน อยู่ ~3.5-3.8 เท่า** (จากที่เริ่มต้นประเมินว่าห่าง 200-330 เท่า)

### รายชื่อ 13 ระบบ (leg) ในทุน

| leg | กลยุทธ์ | contribution (LOO Δsharpe) |
|---|---|---|
| **S56** | Prev-Week High/Low Reversal (counter-trend) | 🏆 **+0.088** (แรงสุด) |
| **S39** | Demand/Supply Zone base-breakout | +0.023 |
| **S37** | Horizontal S/R Pivot Bounce | +0.009 |
| S47 | SuperTrend flip | +0.003 |
| S44 | Volume Profile POC/VAH/VAL | +0.0003 ($เยอะสุด +$1672/mo) |
| S51 | Prev-Day High/Low bounce | +0.0017 |
| S49 | Session VWAP Bounce | +0.0017 |
| S36 | FVG/ICT-SMC | +0.0017 |
| S34 | Volume Breakout | +0.0013 |
| S42 | CRT sweep+reversal | +0.0010 |
| S41 | RSI Divergence | +0.0003 |
| S40 | Elliott Wave proxy | -0.0003 (neutral) |
| S46 | Opening Range Breakout | -0.0090 (เก็บไว้เพราะให้ $เยอะ +$753/mo) |

**ถอดออกจาก 16-way เดิม (leave-one-out พบว่าเป็น sharpe-drag):** S38 (Fibonacci OTE), S45 (Order
Block), S31 (Engulfing) — ทำให้ sharpe ดีขึ้น 4/5 window (60d ยกเว้น) แลกกับ $/mo ต่ำลง ~7-11%

---

## เส้นทางงานวิจัย (ภาพรวม)

1. **S21-S36**: เทคนิคพื้นฐาน (engulfing, volume-breakout, FVG) — ปูฐาน
2. **S37-S45**: ครบ 100% ของลิสต์เทคนิคแรก (ICT/SMC, Elliott, S/R, FVG, Demand/Supply, CRT, RSI
   Divergence, Fibonacci) — S37 (S/R bounce) กลายเป็น breakthrough ตัวแรก
3. **S43-S48**: ครบลิสต์รอบ 2 (Turtle, Volume Profile, Order Block, ORB, SuperTrend, MACD) — S44
   (Volume Profile) และ S46 (ORB) เป็น contributor ใหญ่, S43/S48 ตก
4. **S49-S55**: self-research รอบ 3-4 (VWAP, Judas Swing, PDH/PDL, Pin Bar, Regression Channel,
   Floor Pivot, Round Number) — S49/S51 ผ่าน, ที่เหลือตก (บางตัวเจอ **position-sizing compounding
   artifact** ที่ทำให้ backtest ดูดีเกินจริง)
5. **S56**: 🏆 **breakthrough ใหญ่ที่สุดรอบหลัง** — Prev-Week H/L Reversal จาก meta-insight
   "endogenous level ชนะ exogenous level"
6. **S57-S59**: สำรวจรอบ S56 ครบทุกทิศทาง (monthly/daily/session-level/weekly-open/confluence) —
   ทุกตัวตก ยืนยันว่า S56 นั่งบน sweet spot เฉพาะตัว
7. **Blend/Regime/Exit optimization**: leave-one-out ได้ 13-way lean champion, ทดสอบ regime-switch
   และ exit-logic (breakeven/trailing/partial-TP) — ทั้งคู่แย่กว่า always-on + fixed SL/TP เดิม
8. **Intermarket (gold↔DXY)**: ปิดด้วย market microstructure (ไม่มี lead/lag, ไม่ใช่ pairs trade
   scope)

---

## บทเรียนสำคัญที่สุด 5 ข้อ (จากทั้งหมด 34 ข้อที่บันทึกไว้)

1. **🎯 Endogenous level ชนะ, exogenous level แพ้เสมอ** — level ที่ราคาเคยเทรดจริง (pivot, volume
   node, VWAP, prior H/L) ใช้ได้ ส่วนสูตร/เลขกลม (floor pivot, round number, regression fit) ตกหมด
2. **Weekly extreme คือ sweet spot เดี่ยวของ prior-period reversal** — daily noisy, monthly stale,
   weekly-open เป็น center ไม่ใช่ extreme — มีแค่ weekly H/L เท่านั้นที่มี edge
3. **⚠️ Fixed-lot sanity check จำเป็นเสมอที่ trade frequency สูง (>5 ไม้/วัน)** — position-sizing
   compounding สามารถสร้าง PF ปลอมทางคณิตศาสตร์ล้วนๆ (พบใน S53/S54/S55) ต้องตรวจด้วย fixed lot 0.01
   ก่อนเชื่อผลใดๆ
4. **Always-on diversified blend ชนะ regime-switching เสมอที่ทุนนี้** — เพราะไม่มี leg ไหนขาดทุนใน
   regime ที่ไม่เอื้อ (แค่กำไรน้อยลง) + lot floor ทำ fractional weighting ไม่ได้
5. **Fixed SL/TP (grid-searched RR) ดีกว่า exit-management ที่ซับซ้อนกว่าเสมอ** — breakeven/trailing/
   partial-TP ล้วนทำให้แย่ลง เพราะตัด upside ก่อนเวลาโดยไม่ลด downside จริง

---

## 💰 "Max-Yield Blend": 16-way Full Blend — ตัวเลือกเน้นเงินสูงสุด

รัน 16 ระบบพร้อมกัน (13-way champion + S38 Fibonacci OTE + S45 Order Block + S31 Engulfing)

| | Champion (13-way) | Max-Yield Blend (16-way) |
|---|---|---|
| $/เดือน | $7,908 – $8,658 | **$8,442 – $9,319** (มากกว่า ~7-11%) |
| Sharpe | **0.49 – 0.71** | 0.47 – 0.73 |
| Max losing streak | **3-4 วัน** | 4-5 วัน |

**ใช้ Max-Yield Blend เมื่อ:** ให้น้ำหนักเงินดิบมากกว่าความสม่ำเสมอของผลตอบแทน — config เต็มอยู่ใน
`create_s56.md` (16-way blend test)

## ทิศทางที่ยังไม่ปิด (ถ้าต้องการทำต่อในอนาคต)

- News/economic calendar avoidance (ต้องเช็คว่า MT5/broker มี calendar data)
- Multi-leg confluence แบบ meta-signal (ต้องมี 2+ leg ยิงพร้อมกันถึงเข้า)
- ทดสอบที่ทุนสูงกว่า $1000 (ปลด lot-floor constraint อาจทำให้ regime-switch/fractional-weighting
  กลับมามีประโยชน์)

---

## ไฟล์ที่เกี่ยวข้อง

ทุกไฟล์อยู่ใน standalone research-only mode — ไม่มี wiring เข้า live bot, ไม่แก้ S1-S20 (live) หรือ
ไฟล์ระบบหลักใดๆ ตลอดทั้งโปรเจกต์

- `strategy21.py` - `strategy58.py` + `sim_s<N>_backtest.py` คู่กัน — กลยุทธ์แต่ละตัว
- `create_s<N>.md` — เอกสารผลการทดสอบราย strategy (grid search, robustness, blend test)
- `create_blend_optimization.md` — leave-one-out analysis + regime-switch test
- `create_exit_optimization.md` — exit-logic test + session-H/L + confluence test
- `docs/new_strategy_research_template.md` — กฎกลางที่ใช้ทั้งโปรเจกต์ (อัพเดทด้วย fixed-lot sanity
  check rule)
