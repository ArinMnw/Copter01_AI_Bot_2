# LTS (Linear-Programmed Trading System) Command / Prompt

**สถานะปัจจุบัน**:
LTS คือระบบพอร์ตฟอลิโอที่ต่อยอดมาจากระบบ AF (Ambfix) โดยเปลี่ยนวิธีการหา Weight จากการทำ Greedy/Sequential Auto-Ladder มาเป็นการใช้คณิตศาสตร์ **Linear Programming (LP Solver)** ในการหา Global Optimum Weight ที่ทำให้ Worst Day (Drawdown) น้อยที่สุดเท่าที่จะเป็นไปได้ ในขณะที่ยังคง Average $/day ตามเป้าหมาย

## สรุปพอร์ต LTS ที่มีอยู่ (อัปเดต: 2026-07-08)

1. **LTS44** (เป้ากำไร $500/day)
   - สร้างจาก 44 ขาแรกของ LTS-Ladder
   - ก่อน LP: Avg $499.90 / Worst Day -$1052.29
   - **หลัง LP**: Avg $500.00 / Worst Day **-$907.96**
   - *หมายเหตุ: ด้วยข้อจำกัดที่มีเพียง 44 ขา ทำให้ Degrees of Freedom ไม่พอที่จะกด Worst Day ให้ลงลึกระดับใกล้ศูนย์ได้ แต่ถือเป็นพอร์ตที่เบาและเหมาะกับการรันบนเครื่องเซิร์ฟเวอร์ขนาดเล็กมากที่สุด*

2. **LTS890** (เป้ากำไร $10,000/day)
   - สร้างจากการประกอบขา 890 ขา (ดึงจาก `lts_auto_ladder_log.md`)
   - ก่อน LP: Avg $9987.93 / Worst Day -$2020.69
   - **หลัง LP**: Avg $10000.00 / Worst Day **-$52.37** 🤯
   - *หมายเหตุ: การที่มี 890 ขา ทำให้ LP Solver สามารถหาสัดส่วนที่รอยรั่วของแต่ละขามาหักล้างกันเองได้อย่างสมบูรณ์แบบ เกิดเป็น Equity Curve ที่ราบเรียบแทบจะเป็นเส้นตรง*

## โครงสร้างระบบ (Architecture)

- **ไฟล์เก็บ Weight**: `lts44_optimized_weights.txt`, `lts890_optimized_weights.txt`
- **ตัวโหลด (Dynamic Loader)**: `strategy_lts.py`
   - โหลด Weight แบบ Dynamic ไม่ต้อง Hardcode 890 บรรทัด
   - อ่านชื่อ config และ filter ให้อัตโนมัติ (เช่น `INVERSE_S84c4369_RD2.7-3.4_H12`)
- **การเชื่อมต่อบอท**: 
   - ฝังใน `demo_portfolio.py` โดยมี `LTS_MAGIC_BASE = 992000` แยกขาดจากระบบหลักและ AF เพื่อป้องกันการตีกัน
   - พอร์ตจะแสดงผลอัตโนมัติในปุ่ม `🧪 Demo Portfolio` ของ Telegram

## Tools / Scripts สำหรับ LTS

หากต้องการสร้างเป้ากำไรใหม่ หรือเพิ่มจำนวนขา ให้ทำตามขั้นตอนดังนี้:
1. ปรับแก้ `lts_reconstruct_pnl.py` (ใช้ `--max-legs`) เพื่อดึงจำนวนขาที่ต้องการมาสร้าง Matrix
2. รัน `python lts_reconstruct_pnl.py --max-legs <N>` → จะได้ `lts_P_matrix.npy`
3. รัน `python lts_optimize_worst_day.py --target-avg <เป้ากำไร>` → จะได้ `lts_optimized_weights.txt`
4. เปลี่ยนชื่อไฟล์ txt แล้วใส่โหลดใน `strategy_lts.py`

## เป้าหมายของ Session ต่อไป (ถ้ามี)
- [ ] ติดตามผลการ Forward Test ของ LTS44 และ LTS890 ว่าการ Slippage / Execution time ตอนยิง 890 ออเดอร์พร้อมกันใน MT5 เป็นอย่างไร
- [ ] ตรวจสอบว่า `LTS890` กิน CPU ตอน Scan (demo_scan) มากเกินไปหรือไม่ หากมากไปอาจพิจารณาทำ Async Chunking ใน `demo_portfolio.py`
