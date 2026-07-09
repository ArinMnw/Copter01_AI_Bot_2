Read AGENTS.md first.

สถานะ: LTS Auto Ladder สร้างสำเร็จไปแล้ว 890 ขา (สิ้นสุดที่ AF890) ดึงเป้าหมายจากทุน 1,000 ไปถึงกำไรวันละ 10,000+ ได้แล้วแบบ In-sample 
เป้าหมายของ Session นี้: การขยายพอร์ต LTS ต่อไปจากขาที่ 891 ไปจนถึงขาที่ 999 (และต่อๆ ไป) 
เพื่อให้พอร์ตครอบคลุมสภาวะตลาดกว้างขึ้น (Ultimate Diversification) และเพิ่ม Degrees of Freedom ให้กับ LP Solver

═══ บริบทจาก sessions ก่อน (2026-07-08) ═══

1. โครงสร้างของ LTS Ladder ปัจจุบัน:
   - บันทึกการปีนบันไดอยู่ที่ไฟล์ `lts_auto_ladder_log.md`
   - ขาล่าสุดคือ **AF890** (Base file: `lts890_ambfix_s84c4369_dir_2.7-3.4_h12_daily.csv`)
   - ระบบนี้ต่อยอดจากโครงสร้างของ `af_champion_prompt.md` โดยใช้เครื่องมือเดียวกัน แต่เน้นการขยายฐานขาแบบรวดเร็วและใช้ข้อมูล 2 ปีเต็ม (550 วัน) 

2. เครื่องมือที่ใช้ปีนบันได (Tools):
   - สคริปต์หลัก: `lts_auto_ladder_2y.py`
   - คำสั่ง: `python lts_auto_ladder_2y.py --base <base_csv_ล่าสุด> --start-idx 891 --target <เป้ากำไรใหม่>`
   - สคริปต์นี้จะอ่าน base CSV, สุ่มหรือไล่หา Config ใหม่ใน `CONFIG_POOL`, จำลอง PnL (ผ่าน `optimize_s88_allin4s_fast.py` โหมด `_simulate_leg`), ถ้าน้ำหนักผ่านเกณฑ์ (W_MAX ไม่ชนขอบ และรอดเงื่อนไข Floor-drop) ก็จะบวกขานั้นเข้าไปใน Ladder และเขียนต่อท้ายใน `lts_auto_ladder_log.md` อัตโนมัติ

3. สิ่งที่ห้ามทำเด็ดขาด (Rules of Engagement):
   - ห้ามรัน ML บนข้อมูล PnL เดี่ยวๆ เพราะการ Randomness สูงมาก เรายึดโครงสร้างการปีนบันไดแบบ Greedy/LP
   - ห้ามลบ History เดิมใน `lts_auto_ladder_log.md` การต่อยอดจะต้องเริ่มจากบรรทัดล่าสุดเสมอ
   - หากเจอสภาวะ Dead-end (สคริปต์หาขามาเติมไม่ได้) ให้ปรับค่า `target` หรือเพิ่ม `CONFIG_POOL` ใน `lts_auto_ladder_2y.py`

═══ PHASE 1: CONTINUING THE LADDER (AF891 - AF999) ═══

คำถามที่ต้องตอบ: จะขยายฐานให้ถึง 999 ขาได้อย่างไร?

วิธีที่แนะนำ:
1. เช็คไฟล์ base ของขาล่าสุดในโฟลเดอร์ปัจจุบัน (เช่น `lts890_*_daily.csv`)
2. รันคำสั่ง `python lts_auto_ladder_2y.py --base <ไฟล์_base> --start-idx 891 --target 11000`
3. สคริปต์จะวิ่งทำงานไปเรื่อยๆ จนกว่าผลรวมจะถึงเป้าหมาย หรือจนกว่าจะสร้างขาครบ
4. (Optional) ระหว่างที่รัน ให้ดู Output ของ PowerShell / Log เพื่อตรวจสอบว่าระบบไม่ติดลูปหาขาใหม่ไม่ได้

═══ PHASE 2: LP SOLVER RE-OPTIMIZATION (หลังปีนบันไดเสร็จ) ═══

วิธีที่แนะนำ:
1. เมื่อได้จำนวนขาครบที่ต้องการ (เช่น ได้ 999 ขาแล้ว) ให้ใช้ข้อมูล `lts_auto_ladder_log.md` เป็น Base Vector
2. หากต้องการหาจุด Optimum (Minimize Worst Day) ให้ใช้ `lts_optimize_worst_day.py`
3. ได้ไฟล์ Weights ใหม่ (เช่น `strategy/lts/optimized_weights/lts_optimized_weights.txt`) และนำไปเสียบใน `strategy_lts.py` เพื่อใช้งานต่อไป
4. ทำการรัน `simulate_compounding.py` เพื่อหาสัดส่วนการทบต้น (Compounding) ที่ปลอดภัยที่สุด (Ultra Safe)

═══ PHASE 3: ขุดข้อมูลจากมันสมองของ AI (True ML Feature Scoring) ═══

หลังจากขยายพอร์ตจนนิ่งแล้ว การหาวัตถุดิบใหม่จะต้องฉลาดขึ้น:
1. **เชื่อมต่อ `ml_scoring.py`:** สั่งการให้ดึงข้อมูลสภาพตลาดจริง (RSI, ATR, Trend, Volatility) มาป้อนให้ AI เรียนรู้พฤติกรรมของขา LTS ต่างๆ
2. **ขุดมันสมอง AI (AI's Brain Research):** ให้ AI (RandomForest/XGBoost) วิเคราะห์และคัดกรองจุดเข้า (Entry) ก่อนที่จะรัน LP Solver เพื่อเพิ่ม Win Rate ตั้งแต่ต้นทาง
3. **Global Online Research (วิจัยแหล่งข้อมูลทั่วโลก):** สั่งให้ AI ทำ Web Search สืบค้น Paper, บทความ Quant, และเทคนิคจาก Hedge Fund ทั่วโลก เพื่อดึง Features หรือกลยุทธ์ใหม่ๆ มาเสริมทัพใน LTS แบบไม่หยุดนิ่ง
4. **Dynamic Lot Sizing:** ใช้ค่า ATR และ AI Score มาปรับลดหรือเพิ่ม Lot แบบ Real-time ตามความเสี่ยงของตลาด

═══ PHASE 4: กลไกจัดการจุดออกอัจฉริยะ (Dynamic Exit & Market Conditions) ═══

หลังจากที่ออเดอร์ถูกเปิดไปแล้ว บอทไม่ควรตั้งหน้าตั้งตารอชน TP/SL แบบตายตัว:
1. **จุดยอมแพ้อัจฉริยะ (Dynamic Cut-loss):** วิเคราะห์สภาพตลาดระหว่างที่ถือออเดอร์อยู่ หากโครงสร้างตลาดเปลี่ยน (เช่น มีข่าวแทรก, เกิด Momentum สวนทางรุนแรง, หรือ Trend พัง) ให้ AI สั่งปิดออเดอร์ทิ้งก่อนชน SL เพื่อรักษาทุน
2. **จุดพอใจอัจฉริยะ (Dynamic Take-profit / Trailing):** หากตลาดวิ่งแรงและยังไม่มีสัญญาณหมดแรง ให้ใช้ Trailing Stop แบบอิงความผันผวน (เช่น ATR Trailing) คอยล็อกกำไรตามไปเรื่อยๆ แต่ถ้าเจอสภาวะตลาดตันหรือชนแนวต้านแข็ง ให้รีบเก็บกำไรเข้ากระเป๋าก่อนชน TP 

ลุยครับ!
