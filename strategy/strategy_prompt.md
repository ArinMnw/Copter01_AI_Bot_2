# 🚀 คำสั่งสำหรับสร้างสุดยอด Strategy (Next-Generation S99/S100)

**บริบทสำหรับ AI Model:**
คุณคือสุดยอดนักพัฒนา Quant (God-Tier Quantitative Developer) และผู้เชี่ยวชาญด้าน Algorithmic Trading คุณกำลังเขียนโค้ดเพื่อพัฒนาระบบเทรดอัจฉริยะบน MetaTrader 5 (MT5) ด้วยภาษา Python

ปัจจุบันบอทมี Strategy ที่ทำกำไรได้สูงมากอยู่แล้ว ได้แก่:
- **S84 & S86 (Advanced Filter - AF):** ระบบกรองขั้นสูงที่ผสมผสานอินดิเคเตอร์แบบไดนามิกเข้าด้วยกันจนเกิดเป็นรูปแบบนับพัน
- **S95 (Liquidity Sweep):** กลยุทธ์สวนเทรนด์ที่ดักกิน Stop-Loss ตามจุด Swing High/Low เสริมความแม่นยำด้วยสมองกล AI (Machine Learning - Random Forest) และกรองจุดเข้าด้วย Premium/Discount Zone
- **S96 (Trend Pullback):** กลยุทธ์ตามเทรนด์ที่ดุดันและทำกำไรได้มหาศาล โดยใช้ EMA50 + การเลื่อน Stop-Loss ตามความผันผวน (ATR)
- **S97:** กลยุทธ์วิเคราะห์โครงสร้างแบบเบรกเอาต์ (Breakout)
- **S21 - S94 (Research & Legacy Library):** คลังกลยุทธ์กว่า 70 รูปแบบที่ใช้ในการทดลองแนวคิดต่างๆ (เช่น S36 ที่ใช้หา FVG หรือกลยุทธ์อื่นๆ) ซึ่งแสดงให้เห็นว่าระบบของเรารองรับตรรกะที่ซับซ้อนได้ทุกรูปแบบ
- **LTS (Ladder Trading System):** ระบบ Portfolio ผู้จัดการกองทุนอัจฉริยะ ที่นำ Strategy ย่อยๆ (Legs) มายำรวมกันแล้วเทรดเป็นตะกร้าพร้อมกัน (เช่น จับ S95, S96 มาทำงานร่วมกันและปรับน้ำหนักความเสี่ยง)

**ภารกิจของคุณ:**
ให้ออกแบบ คิดค้น และเขียนโค้ด Python สำหรับ **"สุดยอดกลยุทธ์ (Holy Grail)"** (เช่น `strategy99.py` หรือ `strategy100.py`) ที่ต้อง **เหนือกว่าและเอาชนะ** S84, S86, S95, S96, และ S97 ได้อย่างขาดลอย ทั้งในด้าน **ความแม่นยำ (Win Rate)** และ **กำไรสุทธิ (Net Profit)**

## 🧠 ข้อกำหนดหลักสำหรับ Strategy ตัวใหม่นี้:

1. **จุดได้เปรียบที่ไม่เหมือนใคร (The Alpha):**
   ห้ามใช้แค่จุดตัด RSI หรือเส้น EMA แบบพื้นฐาน เราต้องการตรรกะระดับสถาบันการเงิน (Institutional-grade logic) คุณต้องนำหนึ่งในแนวคิดเหล่านี้มาใช้:
   - **Smart Money Concepts (SMC):** การตรวจหา Order Blocks (OB), Fair Value Gaps (FVG) และการกวาดสภาพคล่อง (Liquidity Sweeps) แบบขั้นสูง
   - **Multi-Timeframe Fractal Confirmation:** การวิเคราะห์โครงสร้างย่อย (Micro-structures) ที่ซ้อนอยู่ในเทรนด์ใหญ่
   - **Volatility & Statistical Arbitrage:** ใช้ Z-Score แบบขั้นสูง, การบีบตัวของ Bollinger Band หรือ Hurst Exponent เพื่อแยกแยะสภาวะตลาด (Trend vs. Ranging)
   - **Volume/Momentum Divergence:** ใช้ Tick Volume ร่วมกับความผิดปกติของพฤติกรรมราคา

2. **โครงสร้างของโค้ดที่เข้มงวด:**
   Strategy ต้องเขียนแยกเป็นไฟล์เดี่ยวๆ และต้องมีฟังก์ชัน `detect_s99(rates, tf, dt_bkk, cfg)`
   - `rates`: ข้อมูลแท่งเทียนแบบ List of Dictionaries (มี `time, open, high, low, close, tick_volume` ตามมาตรฐาน MT5)
   - `tf`: Timeframe ปัจจุบัน (เช่น "M5", "M15")
   - `dt_bkk`: เวลาปัจจุบัน (datetime object)
   - `cfg`: Dictionary ของค่า Hyperparameters ต่างๆ

   ฟังก์ชัน **ต้องคืนค่า (Return)** เป็น Dictionary ในรูปแบบนี้เป๊ะๆ:
   ```python
   # กรณีที่มีจังหวะเข้าเทรดที่ชัดเจน:
   return {
       "signal": "BUY",  # หรือ "SELL"
       "entry": 4500.25, # float: ราคาเข้าที่แม่นยำ
       "sl": 4490.00,    # float: จุดตัดขาดทุนที่คำนวณมาอย่างดี
       "tp": 4530.00,    # float: จุดทำกำไร
       "reason": "SMC Order Block + Volatility Squeeze" # คำอธิบายเหตุผลในการเข้าเทรด
   }
   
   # กรณีที่ตลาดยังไม่น่าเทรด:
   return {
       "signal": "WAIT",
       "reason": "ตลาดเป็นไซด์เวย์ ยังไม่มีจุดได้เปรียบ"
   }
   ```

3. **การจัดการความเสี่ยง (Risk Management) และ SL/TP แบบไดนามิก:**
   - ห้ามใช้ Stop Loss (SL) แบบตายตัว (Fixed) SL ต้องคำนวณแบบยืดหยุ่นตามความผันผวน (เช่น `ATR * multiplier`) หรือจุดสวิงโครงสร้างที่แม่นยำ (เช่น วาง SL ห่างจากไส้เทียน 2 จุด)
   - Take Profit (TP) ต้องมีอัตราส่วน Risk:Reward อย่างน้อย 1:1.5 หรือขยายเป้าหมายตาม Liquidity Pool ถัดไป

5. **โฟกัสที่ Win Rate สูงปรี๊ด (High Win Rate):**
   - กลยุทธ์นี้จะต้องถูกออกแบบมาให้ชนะตลาดได้อย่างเด็ดขาด (เป้าหมาย Win Rate 70-85%+) เพื่อลดความกดดันของพอร์ตและสร้างเส้น Equity Curve ที่เติบโตอย่างราบรื่น (Smooth Growth)

4. **การใช้งาน Machine Learning ร่วมด้วย (ไม่บังคับ แต่แนะนำ):**
   - สามารถเรียกใช้ `ml_scoring.score_signal('XAUUSD.iux', tf, 'BUY', entry, dt_bkk, historical_rates=rates)` เพื่อกรองทิ้งออเดอร์ที่มีความน่าจะเป็น (Win Probability) ต่ำกว่า 55% ได้

## 📝 รูปแบบสิ่งที่คุณต้องส่งมอบ:
1. อธิบายตรรกะทางคณิตศาสตร์และ **จุดได้เปรียบ (EDGE)** ของกลยุทธ์ใหม่นี้ ทำไมมันถึงเหนือกว่า S95/S96?
2. เขียนโค้ด Python ที่สมบูรณ์ ไร้บั๊ก และอ่านง่าย สำหรับ `strategy99.py`
3. กำหนดตัวแปร `cfg` (Hyperparameters) ที่เหมาะสมที่สุดสำหรับใช้รันในระบบ Backtester

**เริ่มปฏิบัติการได้** แสดงให้ฉันเห็นว่า AI ระดับเทพสามารถสร้างอะไรออกมาได้บ้าง!
