# 🚀 คำสั่งสำหรับสร้างสุดยอด Strategy แบบอัตโนมัติ (Next-Generation S114 - S999 Loop)

**บริบทสำหรับ AI Model:**
คุณคือสุดยอดนักพัฒนา Quant (God-Tier Quantitative Developer) และผู้เชี่ยวชาญด้าน Algorithmic Trading คุณกำลังเขียนโค้ดเพื่อพัฒนาระบบเทรดอัจฉริยะบน MetaTrader 5 (MT5) ด้วยภาษา Python

---

## 🔍 กฎการค้นหาชื่อและเลขไฟล์กลยุทธ์ถัดไปอัตโนมัติ (Dynamic Strategy Target)

ก่อนเริ่มเขียนโค้ด ให้ทำตามขั้นตอนต่อไปนี้เสมอ:
1. **ตรวจสอบหมายเลขสูงสุดที่มีอยู่:** แสกนไฟล์ใน root directory ของโปรเจกต์ ค้นหาไฟล์ที่ตั้งชื่อในรูปแบบ `strategy<NUM>.py` (เช่น `strategy112.py`, `strategy113.py` เป็นต้น) เพื่อหาตัวเลขสูงสุดที่มีอยู่ สมมติว่ามีค่าสูงสุดเป็น `N`
2. **กำหนดเลขกลยุทธ์ใหม่เป็น `N + 1`:** 
   *   คุณต้องสร้างกลยุทธ์ใหม่โดยตั้งชื่อไฟล์ว่า `strategy<N+1>.py` (เช่น ถ้าพบว่ามีถึง `strategy113.py` แล้ว ให้สร้างไฟล์ใหม่เป็น `strategy114.py`)
   *   กำหนดชื่อฟังก์ชันการตรวจจับสัญญาณเป็น `detect_s<N+1>(rates, tf, dt_bkk, cfg)`
   *   กำหนดรหัสกลยุทธ์ในผลลัพธ์เป็น `S<N+1>` (เช่น ในฟิลด์ `pattern` ให้ระบุว่า `S<N+1> ...`)

---

## 📊 รายชื่อกลยุทธ์ปัจจุบันที่มีอยู่ในระบบ (เพื่อหลีกเลี่ยงตรรกะซ้ำซ้อน)

ให้ตรวจสอบไฟล์กลยุทธ์ที่มีอยู่ในระบบ (ตั้งแต่ S84 จนถึง `S<N>`) เพื่อสร้างตรรกะใหม่ที่ไม่แย่งออเดอร์ หรือช่วยกระจายความเสี่ยงให้ระบบ LTS (Ladder Trading System) ได้ดีที่สุด:
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

---

## 🧠 ข้อกำหนดหลักสำหรับ Strategy ตัวใหม่ `S<N+1>` นี้:

1. **จุดได้เปรียบระดับสถาบันการเงิน (The Alpha Edge):**
   ห้ามเขียนโค้ดที่อิงตามตรรกะง่ายๆ (เช่น แค่เส้นตัดกัน) แต่ให้เลือกนำหนึ่งในแนวคิดขั้นสูงเหล่านี้มาใช้ให้เกิด Confluence:
   - **Wyckoff Method & Volume Spread Analysis (VSA):** วิเคราะห์ความสัมพันธ์ระหว่างการเคลื่อนไหวของราคากับ Tick Volume เพื่อหาจังหวะสะสม/กระจายของรายใหญ่
   - **Smart Money Concepts (SMC):** โครงสร้าง CHoCH, BOS, Order Blocks, Liquidity Sweeps, Fair Value Gaps
   - **Volatility Squeeze & Statistical Arbitrage:** Z-Score, Bollinger Squeeze, Keltner Channel, Hurst Exponent
   - **Multi-Timeframe Fractal Analysis:** การคอนเฟิร์มโครงสร้างราคาและ Momentum ข้ามกรอบเวลา (Multi-Timeframe)
   - **Volume Delta & Order Flow Anomaly:** การประเมินกำลังซื้อขายที่ผิดปกติของทองคำ (XAUUSD)

2. **โครงสร้างของโค้ดที่เข้มงวด:**
   โค้ดต้องแยกเขียนเป็นไฟล์เดี่ยวและมีฟังก์ชัน `detect_s<N+1>(rates, tf, dt_bkk, cfg)`
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
       "pattern": "S<N+1> [Setup Tag]", # เช่น "S114 Spring"
       "reason": "รายละเอียดเหตุผลในการเข้าออเดอร์"
   }
   
   # กรณีที่ยังไม่เกิดเงื่อนไขที่ได้เปรียบ:
   return {
       "signal": "WAIT",
       "reason": "คำอธิบายว่าทำไมถึงต้องรอ"
   }
   ```

3. **การจัดการความเสี่ยงและ SL/TP แบบไดนามิก:**
   - ห้ามใช้ SL/TP แบบคงที่ (Fixed Points) เด็ดขาด SL ต้องคำนวณแบบยืดหยุ่นตามความผันผวนของราคา (เช่น `ATR * multiplier`) หรืออิงตามโครงสร้างราคาสวิงสูงสุด/ต่ำสุดจริง
   - อัตราส่วน Risk to Reward (R:R) ต้องคุ้มค่าเฉลี่ย 1:1.5 หรือดีกว่า

4. **การคัดกรองสัญญาณด้วย Machine Learning (ไม่บังคับ):**
   - สามารถเรียกใช้ `ml_scoring.score_signal('XAUUSD.iux', tf, 'BUY', entry, dt_bkk, historical_rates=rates)` เพื่อกรองเอาเฉพาะออเดอร์ที่มีความน่าจะเป็น (Win Probability) เกินกว่า 55%

## 📝 สิ่งที่คุณต้องส่งมอบ:
1. อธิบายตรรกะทางคณิตศาสตร์และ **จุดได้เปรียบ (EDGE)** ของกลยุทธ์ใหม่ตัวนี้
2. เขียนโค้ด Python ที่สมบูรณ์ ไร้บั๊ก และอ่านง่าย สำหรับ `strategy<N+1>.py`
3. กำหนดตัวแปร `cfg` (Hyperparameters) สำหรับการทดสอบและใช้งานใน Backtest

**เริ่มลงมือสร้างสรรค์ได้เลย!** แสดงให้เห็นความเหนือชั้นในการเขียนบอทเทรดของคุณ!
