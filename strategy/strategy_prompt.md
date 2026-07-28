# 🚀 คำสั่งสำหรับสร้างสุดยอด Strategy (Next-Generation S115)

**บริบทสำหรับ AI Model:**
คุณคือสุดยอดนักพัฒนา Quant (God-Tier Quantitative Developer) และผู้เชี่ยวชาญด้าน Algorithmic Trading คุณกำลังเขียนโค้ดเพื่อพัฒนาระบบเทรดอัจฉริยะบน MetaTrader 5 (MT5) ด้วยภาษา Python

---

## 🔍 ข้อมูลเป้าหมายกลยุทธ์ถัดไปที่ต้องสร้าง (Strategy Target)
*   **ชื่อไฟล์ส่งมอบ:** `strategy115.py`
*   **ชื่อฟังก์ชันการตรวจจับ:** `detect_s115(rates, tf, dt_bkk, cfg)`
*   **รหัสกลยุทธ์ในผลลัพธ์ (pattern):** `S115 [Setup Tag]` (เช่น `S115 Momentum FTR`)

---

## 📊 รายชื่อกลยุทธ์ปัจจุบันที่มีอยู่ในระบบ (เพื่อหลีกเลี่ยงตรรกะซ้ำซ้อน)

ให้ตรวจสอบคลังกลยุทธ์ที่มีอยู่ เพื่อสร้างตรรกะใหม่ที่ไม่แย่งออเดอร์ หรือช่วยกระจายความเสี่ยงให้ระบบ LTS (Ladder Trading System) ได้ดีที่สุด:
*   **S84 & S86 (Advanced Filter - AF):** ระบบกรองขั้นสูง ผสมผสานอินดิเคเตอร์ไดนามิก
*   **S95 / S99 / S100 / S101 / S112:** กลุ่มกลยุทธ์ Smart Money Concepts (SMC) ตรวจจับ Liquidity Sweep, Rejection, Order Block Mitigation และ Fair Value Gap (FVG) Retrace
*   **S96:** Trend Pullback โดยอิงตาม EMA50 + Dynamic ATR Stop Loss
*   **S97 / S102 / S106:** กลยุทธ์ Breakout วิเคราะห์โครงสร้างราคา, Session Breakout และ Asian Range Stop Hunt
*   **S103 / S105:** Mean-Reversion และ Volatility Anomaly Fade ในภาวะตลาดบีบตัว
*   **S108:** RandomForest Machine Learning (Statistical Features)
*   **S109:** Harmonic Pattern Sniper (Gartley / Bat / Butterfly)
*   **S110:** Multi-Timeframe Fractal Structural Alignment (H4+H1+M15+M5)
*   **S111:** Weekend Gap Fill + Mega Imbalance Void
*   **S113:** Wyckoff Spring & Upthrust Sniper ร่วมกับ Volume Spread Analysis (VSA)
*   **S114:** Effort/Result Absorption Continuation (ตรวจจับการดูดซับแรงฝั่งตรงข้ามหลังเกิด Impulse เพื่อรอจังหวะกลับไปตามเทรนด์เดิม)

---

## 🧠 ข้อกำหนดหลักสำหรับ Strategy ตัวใหม่ `S115` นี้:

1. **จุดได้เปรียบระดับสถาบันการเงิน (The Alpha Edge):**
   ห้ามเขียนโค้ดที่อิงตามตรรกะง่ายๆ (เช่น แค่เส้นตัดกัน) แต่ให้เลือกนำหนึ่งในแนวคิดขั้นสูงเหล่านี้มาใช้ให้เกิด Confluence:
   - **Order Flow & Institutional Imbalances:** การตรวจหา Failed-to-Return (FTR), Break of Structure (BOS) ร่วมกับ Imbalance ที่ทิ้งไว้
   - **Advanced Wyckoff & VSA:** การเล่นตามรอบสะสม (Accumulation) / กระจายตัว (Distribution)
   - **Volatility Squeeze & Statistical Mean-Reversion:** Z-Score, Bollinger Squeeze, Hurst Exponent
   - **Multi-Timeframe Fractal Structure:** การประสานสัญญาณระหว่าง TF ใหญ่คุมแนวโน้ม และ TF ย่อยจับจังหวะเข้าเทรด
   - **Volume Delta & Price Action Divergence:** ความผิดปกติระหว่างกำลังซื้อขายและระยะทางวิ่งของราคาทองคำ (XAUUSD)

2. **โครงสร้างของโค้ดที่เข้มงวด:**
   โค้ดต้องแยกเขียนเป็นไฟล์เดี่ยวและมีฟังก์ชัน `detect_s115(rates, tf, dt_bkk, cfg)`
   - `rates`: List of Dictionaries ของแท่งเทียน (มี `time, open, high, low, close, tick_volume` ตามมาตรฐาน MT5)
   - `tf`: Timeframe ปัจจุบัน (เช่น "M5", "M15")
   - `dt_bkk`: เวลาปัจจุบัน (datetime object ในเขตเวลากรุงเทพฯ UTC+7)
   - `cfg`: Dictionary ของ Hyperparameters

   ฟังก์ชัน **ต้องคืนค่า (Return)** ในรูปแบบ Dictionary นี้อย่างแม่นยำ:
   ```python
   # กรณีที่มีจังหวะเข้าเทรดที่ชัดเจน (Limit Order หรือ Market Order):
   return {
       "signal": "BUY",  # หรือ "SELL"
       "entry": 4500.25, # float: ราคาเข้าเทรด
       "sl": 4490.00,    # float: ราคาตัดขาดทุน
       "tp": 4530.00,    # float: ราคาทำกำไร
       "order_type": "limit", # หรือ "market"
       "pattern": "S115 [Setup Tag]", # เช่น "S115 FTR Breakout"
       "reason": "รายละเอียดเหตุผลในการเข้าออเดอร์",
       "be_rr": 1.0,          # float หรือ None: ดึง SL บังหน้าทุนเมื่อบวกถึง R:R เท่านี้ (ถ้าไม่ใช้ใส่ None/ละเว้น)
       "cancel_bars": 5       # int หรือ None: ยกเลิก Pending ถ้าไม่ fill ใน N แท่ง (ถ้าไม่ใช้ใส่ None/ละเว้น)
   }
   
   # กรณีที่ยังไม่เกิดเงื่อนไขที่ได้เปรียบ:
   return {
       "signal": "WAIT",
       "reason": "ตลาดไม่มีสัญญาณสะสมพลังที่ได้เปรียบ"
   }
   ```

3. **การจัดการความเสี่ยงและ SL/TP แบบไดนามิก:**
   - ห้ามใช้ SL/TP แบบคงที่ (Fixed Points) เด็ดขาด SL ต้องคำนวณแบบยืดหยุ่นตามความผันผวนของราคา (เช่น `ATR * multiplier`) หรืออิงตามโครงสร้างราคาสวิงสูงสุด/ต่ำสุดจริง
   - อัตราส่วน Risk to Reward (R:R) ต้องคุ้มค่าเฉลี่ย 1:1.5 หรือดีกว่า

4. **การคัดกรองสัญญาณด้วย Machine Learning (ไม่บังคับ):**
   - สามารถเรียกใช้ `ml_scoring.score_signal('XAUUSD.iux', tf, 'BUY', entry, dt_bkk, historical_rates=rates)` เพื่อกรองเอาเฉพาะออเดอร์ที่มีความน่าจะเป็น (Win Probability) เกินกว่า 55%

5. **กฎเหล็กป้องกัน Look-Ahead Bias และ Reality Check (LTS & AF Compatibility):**
   - **ห้ามมี Look-Ahead Bias:** สัญญาณตรวจจับต้องมาจากแท่งเทียนที่ **ปิดตัวสมบูรณ์แล้วเท่านั้น** ห้ามใช้ข้อมูลราคาในอนาคต หากมีการทำ Resampling ข้อมูลแท่งเทียนข้าม Timeframe (เช่น จาก M1 ไป M15/M30) ให้ **ตัดแท่งเทียนแท่งสุดท้ายที่ยังปิดไม่สมบูรณ์ออกไปเสมอ**
   - **Spread Reality Check สำหรับ Limit Entry:** ในโปรแกรมทดสอบ Backtest การเข้าเทรดด้วย Limit Order จะถูก Fill ได้ก็ต่อเมื่อราคาเคลื่อนที่ผ่านและมีระยะคลุมค่า Spread ด้วย (สำหรับ BUY: `low <= entry - spread` / สำหรับ SELL: `high >= entry + spread`)
   - **Market Entry Price Bias Guard:** หากเลือกส่งคำสั่งเป็น Market Order ออเดอร์นั้นจะต้องจำลองให้เข้าเทรดที่ราคาเปิด (Open Price) ของแท่งเทียนถัดไปทันที (ไม่ใช่ราคา Close ของแท่งสัญญาณ) เพื่อป้องกันความลำเอียงของการจำลองราคาเปิดที่สวยเกินจริง
   - **SL-First Evaluation (Same Bar Touch):** ในแท่งเทียนที่คำสั่งได้รับการเติมเต็ม (Fill) หากแท่งนั้นมีการเคลื่อนไหวไปแตะทั้ง SL และ TP ในแท่งเดียวกัน ให้ถือว่าคำสั่งชน **Stop Loss (SL) ก่อนเสมอ** (กฎการ Backtest แบบปลอดภัยสูงสุด)
   - **LTS Portfolio Parameters:** ในตัวแปรที่คืนค่าจากฟังก์ชัน นอกจาก `entry`, `sl`, `tp`, และ `order_type` แล้ว ต้องคืนค่าพารามิเตอร์คุมความเสี่ยงหน้างานสำหรับ LTS และระบบ Trailing ด้วย ได้แก่:
     - `be_rr` (float หรือ None): ระดับ R:R ที่จะดึง Stop Loss มาบังหน้าทุน (Breakeven - BE) เช่น `1.0` (เมื่อได้กำไรเท่ากับความเสี่ยงเริ่มต้น)
     - `cancel_bars` (int หรือ None): จำนวนแท่งเทียนบน Timeframe เทรดที่จะยกเลิก Pending Order ที่รอหากยังไม่ได้รับการ Fill (เช่น `5` แท่งเทียน)

## 📝 สิ่งที่คุณต้องส่งมอบ:
1. อธิบายตรรกะทางคณิตศาสตร์และ **จุดได้เปรียบ (EDGE)** ของกลยุทธ์ใหม่ตัวนี้
2. เขียนโค้ด Python ที่สมบูรณ์ ไร้บั๊ก และอ่านง่าย สำหรับ `strategy115.py`
3. กำหนดตัวแปร `cfg` (Hyperparameters) สำหรับการทดสอบและใช้งานใน Backtest

**เริ่มลงมือสร้างสรรค์ได้เลย!** แสดงให้เห็นความเหนือชั้นในการเขียนบอทเทรดของคุณ!
