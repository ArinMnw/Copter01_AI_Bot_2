# แผนตรวจ Vantage หลังตั้งค่าแล้ว

เริ่ม 8 ตุลาคม 2026 ก่อนเลือก parameters จาก feed ใหม่ เป้าหมายยังเป็น causal replay ตรง 35,462 orders ครบทุก field ไม่ใช่ percentage/subset

## ขอบเขตและสิทธิ์

อ่านเฉพาะ terminal Demo ที่พี่เปิดและล็อกอินไว้ (`demo-vantage-26253671`, `VantageMarkets-Demo`) ไม่ launch/relogin ไม่อ่าน credentials ไม่เปลี่ยน Market Watch และไม่ส่ง/แก้/ปิด orders โค้ดอยู่ใน research folder ไม่ import production config/bot

## ลำดับทดลองที่กำหนดก่อนเห็นผล

1. เก็บ specs, raw M1 และ raw bid/ask windows ของ `XAUUSD`, `XAUUSD.crp`, `FixedVol20`; ตรวจ raw-to-query offsets -8 ถึง +3 ชั่วโมง ไม่ยก IUX shift มาใช้
2. เปรียบเทียบทั้ง 35,462 rows เป็น clock diagnostics; close-by reciprocal close price ไม่ใช้เป็น market-quote witness แต่ order ยังอยู่ใน scope ทั้งหมด
3. Tick witnesses เลือกตามลำดับเวลา 16 จุดกระจายต่อ cohort + 4 จุดท้าย ไม่เลือกเฉพาะไม้ที่ตรง ตรวจราคาตาม bid/ask และวินาทีต้นทาง
4. หาก alignment มีหลักฐานชัด export ช่วงเต็มและ warm-up แยก raw/normalized/hash/coverage; ชื่อ broker เหมือนกันไม่ยืนยัน source feed identity
5. Development window ก่อน 21 กันยายน และ chronological validation ตั้งแต่ 21 กันยายน–8 ตุลาคม แยกก่อนจูน feed ใหม่ แต่ ledger ช่วงนี้เคยถูกวิเคราะห์แล้ว จึง **ไม่ใช่ unseen holdout** ผลต้องติดป้ายตามจริง หากต้องการ unseen ต้องมีช่วง source orders ใหม่ที่ยังไม่อ่าน
6. ทดสอบ continuous tick-driven/closed-candle M1/M5/M15/M30/H1 โดย state ไม่ reset ตาม ledger/day; lot/grid/hedge/close-by เป็นกฎที่ต้องมีหลักฐาน ไม่เติม source outcomes เป็น actions

## หน่วยที่ต้องแยก

Public pips = price delta / 0.01 ของทั้งสอง symbols จาก accounting audit ส่วน Vantage `FixedVol20` broker point = 0.001 จาก metadata ดังนั้นราคา 10 = 1,000 web pips = 10,000 broker points ค่า trial adapter เดิม `point=0.01` เป็นหน่วยเว็บ ไม่ใช่ broker point/EA input ที่ยืนยันแล้ว

M1 containment เป็นเครื่องมือตรวจเวลา ไม่ใช่ exact execution verification; spread ของ M1 ไม่แทน bid/ask ทุก tick และการพบราคาใกล้เคียงไม่ได้พิสูจน์ causal trigger
