สร้างกลยุทธ์ใหม่ 1 ตัว S20.<N> (XAUUSD) ให้ผ่าน docs/quant_strategy_verification_checklist.md

<N> = เลขถัดไปที่ว่าง: ดู "next" ใน strategy/s20_gen/progress.json แล้วยืนยันว่าไม่มีโฟลเดอร์ strategy/s20.<N>/ อยู่แล้ว

## กฎเหล็ก (ห้ามฝ่าฝืน)
1. ห้ามเขียน backtester / simulator เอง ให้ใช้ engine ที่มีอยู่เท่านั้น:
   - strategy/s20_gen/engine.py  (SL-first, next-bar-open, spread/swap/slippage, IS70/OOS30, Monte-Carlo, null test, lookahead audit)
   - strategy/s20_gen/run_one.py (backtest 365d 7TF + เช็คสัญญาณซ้ำ Jaccard + สร้าง wrapper + อัปเดต strategy.md/strategy_evolution.md อัตโนมัติ)
   - strategy/s20_gen/progress_repair.py (ซ่อม/เช็ค progress.json จาก result_365d.json จริงบนดิสก์)
   อ่าน 3 ไฟล์นี้ + strategy/s20_gen/scaffold.py + strategy/s20_gen/ind.py และกลยุทธ์ตัวอย่าง strategy/s20.143/strategy20_143.py ก่อนเริ่ม
   ห้ามแก้ engine.py / run_one.py / final_gate.py / progress_repair.py / list_winners.py / docs.py / ind.py / data.py
2. ห้ามพิมพ์ตัวเลขผลลัพธ์ลงเอกสารเอง ตัวเลขทุกตัวต้องมาจาก result_365d.json / output ของ engine เท่านั้น
   ห้ามแก้ strategy.md / strategy_evolution.md ด้วยมือ (run_one.py เขียนให้เอง)
3. ห้ามจูนพารามิเตอร์หลังเห็นผล (checklist ข้อ 14) ตั้งค่าครั้งเดียวจาก market logic แล้วรายงานตามจริง
   ถ้า FAIL ก็รายงาน FAIL ไม่ต้องแก้ให้ผ่าน ห้ามรัน run_one ซ้ำด้วยพารามิเตอร์ใหม่ในเลข sid เดิม
4. TF ต้องเป็น M1 M5 M15 M30 H1 H4 D1 เท่านั้น (ห้ามเพิ่ม/ตัด)
5. ห้าม wire เข้า live bot (ห้ามแตะ scanner.py / config.py / bot_state.json / s20_institutional_hub.py)
6. ใน META ต้องใส่เหตุผลทาง market logic ของ sl_atr / rr / max_hold / be_r ในคีย์ "logic" (checklist ข้อ 14)
   ต้องบอก "ทำไม" ไม่ใช่แค่บอกค่า (ผิด: "SL 1.5 RR 2.0 ถือ 24 แท่ง" / ถูก: "SL 1.5 ATR อยู่นอก swing ล่าสุดที่ปกติลึก ~1 ATR, ถือ 24 แท่งเพราะ reversion มักจบใน 1 session")
7. รันคำสั่ง backtest ทีละคำสั่งตามลำดับ ห้ามรันขนานกันหรือเป็น background (progress.json และ strategy.md จะเขียนทับกัน)
8. ไฟล์ข้อความที่เขียนเอง ต้องเขียนด้วย Python open(..., "w", encoding="utf-8")
   ห้ามใช้ PowerShell redirect (>, >>, Out-File, Set-Content) เพราะไฟล์จะมี BOM และตัวอักษรเพี้ยน

## ขั้นตอน
A. ตรวจความซ้ำก่อนเขียนโค้ด
   - เสนอแนวคิด 3 ตัวเลือก แต่ละตัว grep keyword หลักใน strategy/strategy.md (เช่น "Keltner", "Z-Score", "EMA cross", "Ribbon", "VSA")
   - แสดงผล grep ให้ดู แล้วเลือกตัวที่ไม่ชนกับของเดิม
   - ห้ามเป็นแค่ของเดิมที่เปลี่ยนตัวเลข threshold
   - ถ้า indicator หลักของแนวคิดมีอยู่ใน strategy.md แล้ว ≥2 ตัว ให้เลือกแนวคิดอื่น
B. ตรวจ sid ไม่ชน: grep "20.<N>" ใน config.py, scanner.py, s20_institutional_hub.py, strategy/ ต้องไม่มีใครใช้อยู่
   ห้ามใช้ <N> ที่ลงท้ายด้วย 0 เด็ดขาด (เช่น 430) เพราะ 20.430 == 20.43 เป็น float เดียวกัน และชนกับ sid live ได้
   ถ้าเลขถัดไปลงท้าย 0 ให้ข้ามไปเลขถัดไป (ระวังด้วย: 20.141–20.148 ถูกใช้โดย S20.14 group อยู่แล้ว)
C. เขียน strategy/s20.<N>/strategy20_<N>.py ตามสัญญาของ engine (โฟลเดอร์ต้องเป็น s20.<N> มีจุด ไม่ใช่ขีดล่าง):
   META = {"sid": "20.<N>", "name", "concept", "logic", "sl_atr", "rr", "max_hold", "be_r"}
   def generate(df, tf) -> np.ndarray[int8] (+1/-1/0) ตัดสินจากแท่ง i ที่ปิดแล้วเท่านั้น ใช้ indicator จาก strategy/s20_gen/ind.py
   ห้ามใช้ .shift(-k), .iloc[i+1], center=True, หรือ indicator ที่ repaint (ZigZag/fractal ที่ยังไม่ confirm)
D. ถ้าข้อมูลใน strategy/s20_gen/.cache/meta.json (fetched_utc) เก่ากว่า 2 วัน ให้ refresh ด้วย data.refresh() ก่อน
E. ทดสอบ argument ทั้ง 4 ตัว (ต้องรันหลัง run_one ครั้งแรกสร้าง wrapper แล้ว) และแปะ output จริง:
   python strategy/s20_gen/run_one.py <N> --no-docs
   python strategy/s20.<N>/backtest_s20_<N>.py --day 365
   python strategy/s20.<N>/backtest_s20_<N>.py --start 2026-01-01 --end 2026-06-30
   python strategy/s20.<N>/backtest_s20_<N>.py --day 30 --compare
F. Walk-forward แบบหลายหน้าต่าง (checklist ข้อ 15) — พารามิเตอร์เดิม ห้ามแก้ระหว่างหน้าต่าง:
   แบ่ง 365 วันล่าสุดเป็น 4 ไตรมาสด้วย --start/--end แล้วรันทีละไตรมาส
   รายงาน Net/PF ต่อ TF ต่อไตรมาส เป็นตาราง (ตัวเลขจาก output ของ engine เท่านั้น)
G. รันครั้งสุดท้ายเพื่อบันทึกผลและเอกสาร (ต้องเป็นขั้นสุดท้าย เพราะการรัน wrapper --day 365 จะเขียนทับ result_365d.json และทำช่อง uniqueness หาย):
   python strategy/s20_gen/run_one.py <N>
   แล้วรันทันทีแปะ output จริง: python strategy/s20_gen/progress_repair.py --check
   ถ้าบรรทัด "หายจาก progress.json แต่มีไฟล์จริง" ไม่ใช่ "(ไม่มี)" ให้รัน progress_repair.py (ไม่มี --check) เพื่อซ่อม
   ⚠️ เจอมาแล้ว 2 ครั้งว่า run_one.py พิมพ์ "✅ บันทึกแล้ว" แต่ progress.json ไม่มี entry จริง สาเหตุยังไม่ทราบแน่ชัด ห้ามข้ามขั้นนี้
H. ถ้ามี TF ที่ verdict = PASS ไม่ต้องทำอะไรเพิ่ม — ตั้งแต่ 2026-10-06 run_one.py เรียก final_gate.py ให้อัตโนมัติในคำสั่งเดียวกัน (ขั้น G)
   ผล WINNER / BORDERLINE_INFO_ONLY / FAILED_GATE อยู่ในบรรทัดแรกของ strategy/s20.<N>/final_gate.txt (ห้ามเขียนหรือแก้ไฟล์นี้เอง)
   แปะ output ของขั้น G ให้ครบรวมส่วนด่านสุดท้ายในรายงาน ไม่ต้องรันคำสั่งแยกเพิ่ม

## หมายเหตุเรื่องต้นทุน (checklist ข้อ 8)
- ค่าเริ่มต้นเป็นบัญชี Exness Standard (XAUUSDm) ซึ่งไม่มี commission จึงใช้ --commission 0 ได้
- ถ้า symbol ใน meta.json ไม่ใช่ XAUUSDm หรือเป็นบัญชี Raw/Zero ต้องส่ง --commission ตามจริง (USD ต่อไม้ lot 0.01) และรายงานค่าที่ใช้
- ไม้ BE ใน engine จะขาดทุนราว $0.10 จาก SL slippage ที่โมเดลไว้ ถือว่าปกติ ไม่ต้องแก้

## สิ่งที่ต้องส่งกลับ (ถ้าขาดข้อใดถือว่างานไม่เสร็จ)
1. output ดิบจาก terminal ของ run_one.py ขั้น G (ตารางต่อ TF ทั้ง 7 TF + บรรทัด uniqueness) แบบ copy-paste ไม่สรุปเอง
2. ผล grep ข้อ A และ B
3. ตาราง walk-forward 4 ไตรมาสจากขั้น F
4. git diff ของ strategy/strategy.md และ strategy/strategy_evolution.md (ต้องตรงกับ output ข้อ 1)
5. TF ไหน error ให้บอกสาเหตุจริง ห้ามเขียนว่าผ่าน
   (M1 จะมีข้อมูลแค่ ~100 วันเพราะ terminal จำกัด 100,000 แท่ง ให้ระบุจำนวนวันจริงจากคอลัมน์ days)
6. สรุป verdict ต่อ TF ตามที่ engine ให้ (PASS/WEAK/FAIL) ห้ามใช้คำว่า "ผ่าน checklist" ถ้า engine ไม่ได้ให้ PASS
7. รายการไฟล์ที่สร้าง/แก้ทั้งหมด (git status --short) ต้องมีแค่ strategy/s20.<N>/, reports/s20_<N>/, strategy.md, strategy_evolution.md, progress.json
8. ถ้าตัวนี้ได้ WINNER ให้ปิดท้ายด้วย output ของ python strategy/s20_gen/list_winners.py (เช็คว่าติดอยู่ในลิสต์ผู้ชนะรวมทุกแคมเปญจริง)
