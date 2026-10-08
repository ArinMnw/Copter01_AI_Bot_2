แคมเปญหากลยุทธ์ XAUUSD ใหม่ต่อเนื่องไม่หยุด (To the Moon) — สร้างทีละตัว S20.<N>, S20.<N+1>, ... ไปเรื่อยๆ
เจอตัวที่ผ่านแล้วก็ไม่หยุด บันทึกไว้แล้วไปตัวถัดไปทันที
ทุกตัวต้องผ่าน docs/quant_strategy_verification_checklist.md

## จุดเริ่มและการ resume
- เริ่มที่ <N> = "next" ใน strategy/s20_gen/progress.json แล้วไล่เลขขึ้นไปทีละ 1
- ทำได้สูงสุด 20 ตัวต่อ 1 รอบแชท แล้วส่งรายงาน (กัน context เต็ม) รอบถัดไปให้ resume ต่อจาก "next" ใน progress.json
- ห้ามรันแคมเปญนี้พร้อมกับ mix_strategy_prompt.md หรือ agent อื่นที่สร้าง S20 ใหม่ เพราะใช้เลข sid / progress.json / strategy.md ร่วมกัน

## กฎเหล็ก (ห้ามฝ่าฝืน)
1. ห้ามเขียน backtester / simulator เอง ให้ใช้ engine ที่มีอยู่เท่านั้น:
   - strategy/s20_gen/engine.py  (SL-first, next-bar-open, spread/swap/slippage, IS70/OOS30, Monte-Carlo, null test, lookahead audit)
   - strategy/s20_gen/run_one.py (backtest 365d 7TF + เช็คสัญญาณซ้ำ Jaccard + สร้าง wrapper + อัปเดต strategy.md/strategy_evolution.md อัตโนมัติ)
   - strategy/s20_gen/final_gate.py (ด่านสุดท้าย: walk-forward 4 ไตรมาส + spread 0.40 + null p<0.01 → เขียน final_gate.txt ให้เอง)
   - strategy/s20_gen/progress_repair.py (ซ่อม/เช็ค progress.json จาก result_365d.json จริงบนดิสก์ — ดูกฎ 7)
   อ่าน 4 ไฟล์นี้ + strategy/s20_gen/scaffold.py + strategy/s20_gen/ind.py และกลยุทธ์ตัวอย่าง strategy/s20.143/strategy20_143.py ก่อนเริ่ม
   ห้ามแก้ engine.py / run_one.py / final_gate.py / progress_repair.py / list_winners.py / docs.py / ind.py / data.py
   (ตั้งแต่ 2026-10-06 run_one.py เช็คเพิ่มอีกชั้น: ถ้า sid นี้มีผล PASS เก็บไว้แล้วแต่ชื่อกลยุทธ์ใหม่ไม่ตรงกับของเดิม จะ exit 7 ปฏิเสธไม่เขียนทับ — เจอกรณีนี้ให้ใช้ sid ใหม่เสมอ)
2. ห้ามพิมพ์ตัวเลขผลลัพธ์ลงเอกสารเอง ตัวเลขทุกตัวต้องมาจาก result_365d.json / output ของ engine เท่านั้น
   ห้ามแก้ strategy.md / strategy_evolution.md ด้วยมือ (run_one.py เขียนให้เอง)
3. ห้ามจูนพารามิเตอร์หลังเห็นผล (checklist ข้อ 14):
   - 1 เลข sid = 1 แนวคิด + 1 ชุดพารามิเตอร์ ตั้งครั้งเดียวจาก market logic
   - ถ้า FAIL/WEAK ให้บันทึกผลลบไว้ตามจริง แล้วไปเลขถัดไปด้วยแนวคิดใหม่
   - ห้ามสร้างตัวใหม่ที่เป็นแค่ตัวเก่าเปลี่ยนตัวเลข (เช่น RSI 55→60, RR 1.5→2.0) เพื่อไล่ให้ผ่าน
4. TF ต้องเป็น M1 M5 M15 M30 H1 H4 D1 เท่านั้น (ห้ามเพิ่ม/ตัด)
5. ห้าม wire เข้า live bot (ห้ามแตะ scanner.py / config.py / bot_state.json / s20_institutional_hub.py)
6. ใน META ต้องใส่เหตุผลทาง market logic ของ sl_atr / rr / max_hold / be_r ในคีย์ "logic"
   ต้องบอก "ทำไม" ไม่ใช่แค่บอกค่า (ผิด: "SL 1.5 RR 2.0 ถือ 24 แท่ง" / ถูก: "SL 1.5 ATR อยู่นอก swing ล่าสุดที่ปกติลึก ~1 ATR, ถือ 24 แท่งเพราะ reversion มักจบใน 1 session")
7. รันทีละตัวตามลำดับเท่านั้น ห้ามรัน run_one.py / wrapper หลายตัวพร้อมกันหรือเป็น background ขนานกัน
   (progress.json และ strategy.md จะเขียนทับกันจนผลหาย)
   หลัง run_one.py ที่ไม่ DUPLICATE/lookahead-fail ทุกตัว (ไม่ว่า PASS/WEAK/FAIL) ต้องรันคำสั่งนี้ทันทีแล้วแปะ output จริง:
   python strategy/s20_gen/progress_repair.py --check
   ถ้าบรรทัด "หายจาก progress.json แต่มีไฟล์จริง" ไม่ใช่ "(ไม่มี)" ห้ามไปตัวถัดไป ให้รัน progress_repair.py (ไม่มี --check) เพื่อซ่อมทันที แล้วค่อยไปต่อ
   ⚠️ บั๊กนี้เกิดซ้ำมาแล้ว 2 ครั้ง (2026-10-04 หาย 34 ตัว, 2026-10-05 หาย 4 ตัว) ทั้งที่ run_one.py พิมพ์ "✅ บันทึกแล้ว" ทุกครั้ง สาเหตุยังไม่ทราบแน่ชัด
   (ไม่ใช่การรันขนาน — timestamp เรียงลำดับปกติ) ห้ามข้ามขั้นเช็คนี้โดยคิดว่า "เพิ่งเจอผ่านไปแล้วคงไม่เกิดอีก"
8. ไฟล์ข้อความที่เขียนเอง (เช่น final_gate.txt) ต้องเขียนด้วย Python open(..., "w", encoding="utf-8")
   ห้ามใช้ PowerShell redirect (>, >>, Out-File, Set-Content) เพราะไฟล์จะมี BOM และตัวอักษรเพี้ยน

## ห้ามหยุดกลางทาง
- ทำต่อเนื่องจนครบ 20 ตัว ห้ามหยุดถาม ห้ามขออนุญาต ห้ามรายงานทีละตัวระหว่างทาง
- หยุดก่อนครบได้แค่ 3 กรณี: (1) MT5 ต่อไม่ได้/ดึงข้อมูลไม่ได้ (2) engine error ที่แก้ไม่ได้โดยไม่แตะไฟล์ต้องห้าม (3) context ใกล้เต็ม
  ถ้าหยุดก่อนครบ ให้บอกเหตุผลจริงในรายงาน พร้อม sid ถัดไป
- ประหยัด context: ไม่ต้องแสดง output เต็มของตัวที่ไม่มี TF PASS ระหว่างทาง (ดูข้อ "สิ่งที่ต้องส่งกลับ")

## การเก็บผล (ทุกตัวต้องเก็บ รวม FAIL/WEAK)
- เก็บเสมอ: strategy/s20.<N>/strategy20_<N>.py, result_365d.json, backtest_s20_<N>.py, แถวใน strategy.md/strategy_evolution.md, entry ใน progress.json
  เหตุผล: ใช้กันสร้างแนวคิดซ้ำ (Jaccard), ใช้นับจำนวนครั้งที่ลองเพื่อประเมินโอกาสผ่านเพราะฟลุก, และเป็นวัตถุดิบของ mix_strategy_prompt.md
- ตัวที่ไม่ใช่ "ผู้ชนะ" (FAIL / WEAK / ตกด่านสุดท้าย) ลบได้แค่ reports/s20_<N>/ เพื่อประหยัดพื้นที่
- ห้ามลบหรือเขียนทับผลของตัวที่ FAIL ในส่วนอื่น

**⚠️ ห้ามลบเป็นชุด/เป็นช่วงเด็ดขาด** (เช่น `rm -rf strategy/s20.{700..765}`, wildcard, for-loop ลบหลาย sid)
ลบได้แค่ **ทีละ 1 โฟลเดอร์ ทันทีหลังรู้ผลว่า DUPLICATE/lookahead-fail ของตัวนั้นเท่านั้น** ห้ามมี "ขั้นเก็บกวาด/คืนพื้นที่" แยกรอบทีหลังที่ลบหลาย sid รวดเดียว
(2026-10-06/07 พบว่า strategy/s20.700–765 และ 772 หายไปทั้งโฟลเดอร์แบบต่อเนื่องเป๊ะ ตรงกับลักษณะคำสั่งลบเป็นช่วง หลายตัวเป็นผลที่ต้องเก็บไว้ (บาง PASS ด้วย) กู้คืนได้เกือบหมดเพราะบังเอิญถูก git add ไว้ก่อน — ห้ามให้เกิดซ้ำ)
- ก่อนลบโฟลเดอร์ใดๆ ให้ `git add strategy/s20.<N>/` ทันทีหลัง run_one.py บันทึกผลสำเร็จทุกครั้ง เพื่อให้มีจุดกู้คืนได้เสมอถ้าพลาด

## ขั้นตอนต่อ 1 ตัว (ทำซ้ำทุกเลข)
A. ตรวจความซ้ำก่อนเขียนโค้ด
   - grep keyword หลักของแนวคิดใน strategy/strategy.md แสดงผลให้ดู
   - ห้ามเป็นของเดิมที่เปลี่ยนแค่ threshold และห้ามซ้ำกับตัวที่สร้างไปแล้วในแคมเปญ (รวมตัวที่ FAIL)
   - ถ้า indicator หลักมีอยู่ใน strategy.md แล้ว ≥2 ตัว ให้เลือกแนวคิดอื่น
   - กระจายแนวคิดให้หลากหลาย (session/เวลา, โครงสร้างราคา, volatility regime, breakout, ปฏิทิน) ไม่ใช่วนแค่ indicator crossover
   - ห้ามสร้างแนวคิดด้วยการจับ indicator 2–3 ตัวมาผสมกัน (เช่น "PSAR + Keltner", "Stoch + ADX") นั่นคืองานของ mix_strategy_prompt.md
   - บทเรียนจาก S20.306–427 (122 ตัว, ใช้เป็นแนวทาง ไม่ใช่กฎตายตัว):
     • ได้ผลดีกว่าค่าเฉลี่ย: squeeze/ภาวะซึมแล้วระเบิด, breakout/continuation ตามแรงส่ง, Z-score ของความผันผวน
     • แพ้เกือบทั้งหมด: pullback/fade/mean-reversion, Heikin-Ashi (0/12 ผ่าน), Stochastic, RSI pullback, LinReg slope
     • EMA200 trend filter ไม่ได้ช่วย (ใส่ 80 ตัว ผ่านเท่าค่าเฉลี่ย) ใส่เฉพาะเมื่อมีเหตุผลกับแนวคิดนั้นจริง
     • TF ที่ผ่านบ่อยสุด M30 > H1 ≈ M15; M1 ไม่เคยผ่าน, M5 แทบไม่มี PF ≥ 1.1 (spread กิน)
     • 104/122 ตัวใช้ exit เดียวกัน (SL 1.5 / RR 1.5 / ถือ 24 / BE 1) ให้ตั้ง exit ตามธรรมชาติของแนวคิด
       เช่น breakout ควรให้ RR กว้างกว่า/ถือนานกว่า reversal — และเขียนเหตุผลใน "logic"
B. ตรวจ sid ไม่ชน: grep "20.<N>" ใน config.py, scanner.py, s20_institutional_hub.py, strategy/
   ห้ามใช้ <N> ที่ลงท้ายด้วย 0 เด็ดขาด (เช่น 430, 440) เพราะ 20.430 == 20.43 เป็น float เดียวกัน และชนกับ sid live ได้
   (S20.310–420 ที่ลงท้าย 0 ชนกับ 48_New_God_S20 20.31–20.42 ไปแล้ว) ถ้าเลขถัดไปลงท้าย 0 ให้ข้ามไปเลขถัดไป
   (ระวังด้วย: 20.141–20.148 ถูกใช้โดย S20.14 group อยู่แล้ว)
C. เขียน strategy/s20.<N>/strategy20_<N>.py ตามสัญญาของ engine (โฟลเดอร์ s20.<N> มีจุด):
   META = {"sid": "20.<N>", "name", "concept", "logic", "sl_atr", "rr", "max_hold", "be_r"}
   def generate(df, tf) -> np.ndarray[int8] (+1/-1/0) ตัดสินจากแท่ง i ที่ปิดแล้วเท่านั้น ใช้ indicator จาก ind.py
   ห้ามใช้ .shift(-k), .iloc[i+1], center=True, หรือ indicator ที่ repaint
D. (ทำครั้งเดียวตอนเริ่มรอบแชท) ถ้า meta.json (fetched_utc) เก่ากว่า 2 วัน ให้ data.refresh() ก่อน
   ห้าม refresh กลางรอบ เพื่อให้ทุกตัวในรอบเดียวกันใช้ข้อมูลชุดเดียวกัน
E. รัน: python strategy/s20_gen/run_one.py <N>
   - ถ้า run_one บอก DUPLICATE (Jaccard > 0.5) หรือ lookahead ไม่ผ่าน → ลบโฟลเดอร์ strategy/s20.<N>/ และ reports/s20_<N>/ ทิ้ง
     แล้วใช้เลขเดิมกับ "แนวคิดใหม่" (ห้ามแก้แนวคิดเดิมนิดหน่อยแล้วรันซ้ำ)
F. ถ้ามี TF ที่ verdict = PASS ไม่ต้องทำอะไรเพิ่ม — ตั้งแต่ 2026-10-06 run_one.py เรียก final_gate.py ให้อัตโนมัติในคำสั่งเดียวกัน (ขั้น E)
   แปะ output ของขั้น E ให้ครบรวมส่วนด่านสุดท้าย แล้วไปเลขถัดไป ไม่ว่าผลจะเป็นยังไง

## ด่านสุดท้าย (เฉพาะตัวที่มี TF ได้ PASS) — รันอัตโนมัติโดย run_one.py แล้ว กันตัวที่ผ่านเพราะฟลุก
เมื่อลองหลายสิบตัว จะมีบางตัวผ่าน null test (p<0.05) ได้เองโดยบังเอิญ final_gate.py จึงเช็คเพิ่มด้วยพารามิเตอร์เดิม (ห้ามแก้):
1. Walk-forward 4 ไตรมาส: TF ที่ PASS ต้อง Net บวก ≥3 ใน 4 ไตรมาส
2. Stress spread 0.40: TF ที่ PASS ต้อง Net ยังบวก
3. null p ของ TF นั้นต้อง < 0.01 (เข้มกว่าเกณฑ์ปกติ 0.05 เพราะลองหลายตัว)
4. ทดสอบ argument --start/--end และ --day 30 ให้อัตโนมัติ (ถ้าต้องการ --compare ใส่ flag --compare และต้องเปิด MT5)
- final_gate.py เขียน strategy/s20.<N>/final_gate.txt เอง บรรทัดแรกเป็น WINNER / BORDERLINE_INFO_ONLY / FAILED_GATE
  ห้ามเขียนหรือแก้ไฟล์นี้เอง และไม่ต้องรัน run_one.py ซ้ำ (final_gate.py ไม่เขียนทับ result_365d.json)
- WINNER = ผู้ชนะ ยังต้อง forward demo ก่อน live เสมอ / BORDERLINE = ตกแค่ null p = 0.010 ไม่นับเป็นผู้ชนะ

## หมายเหตุเรื่องต้นทุน (checklist ข้อ 8)
- ค่าเริ่มต้นเป็นบัญชี Exness Standard (XAUUSDm) ไม่มี commission จึงใช้ --commission 0 ได้
- ถ้า symbol ใน meta.json ไม่ใช่ XAUUSDm หรือเป็นบัญชี Raw/Zero ต้องส่ง --commission ตามจริง และรายงานค่าที่ใช้
- ไม้ BE จะขาดทุนราว $0.10 จาก SL slippage ที่โมเดลไว้ ถือว่าปกติ

## สิ่งที่ต้องส่งกลับทุกรอบแชท (ถ้าขาดข้อใดถือว่างานไม่เสร็จ)
1. ตารางสรุปทุกตัวที่ลองในรอบนี้ (รวมตัวที่ FAIL): sid | ชื่อ | แนวคิดย่อ | TF ที่ PASS | Net รวม | PF รวม | max Jaccard | ผล (FAIL/WEAK/FAILED_GATE/WINNER)
   ตัวเลขต้องตรงกับ strategy/s20_gen/progress.json และ result_365d.json
   ตารางนี้ต้องสร้างด้วยสคริปต์ Python ที่อ่าน result_365d.json ของแต่ละตัว ไม่พิมพ์ตัวเลขเอง แปะทั้งสคริปต์และ output
2. สถิติสะสมทั้งแคมเปญ คำนวณจาก progress.json ด้วยสคริปต์ (ไม่นับเอง): จำนวนที่ลองทั้งหมด / มี TF PASS / ผู้ชนะ
3. output ดิบจาก terminal ของ run_one.py เฉพาะตัวที่มี TF PASS (ตัวอื่นใช้ตารางข้อ 1 แทน)
4. ผล grep ข้อ A และ B สรุปสั้นๆ ต่อตัว (keyword ที่ grep + จำนวนที่เจอ)
5. ถ้ามีตัวที่เข้าด่านสุดท้าย: บรรทัดสรุปที่ final_gate.py พิมพ์ออกมา (ผลรวม + quarter nets + spread + null p ต่อ TF)
   และยืนยันว่าทุกตัวที่มี TF PASS มี final_gate.txt ครบ
6. git diff --stat ของ strategy/strategy.md และ strategy/strategy_evolution.md
7. TF ไหน error ให้บอกสาเหตุจริง (M1 จะมีข้อมูลแค่ ~100 วันเพราะ terminal จำกัด 100,000 แท่ง ให้ระบุจำนวนวันจริง)
8. ห้ามใช้คำว่า "ผ่าน checklist" หรือ "พร้อม live" สำหรับตัวที่ไม่ใช่ WINNER
9. git status --short ต้องมีแค่ strategy/s20.<N>/, reports/s20_<N>/, strategy.md, strategy_evolution.md, progress.json
10. sid ถัดไปที่จะเริ่มในรอบหน้า
11. ปิดท้ายรายงานด้วย output ของ python strategy/s20_gen/list_winners.py (รวมผู้ชนะทุกแคมเปญ ไม่ใช่แค่รอบนี้ — ใช้เช็คว่าตัวที่คิดว่าชนะยังอยู่ในลิสต์จริง)
