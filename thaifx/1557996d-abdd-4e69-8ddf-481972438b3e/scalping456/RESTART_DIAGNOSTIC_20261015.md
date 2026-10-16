# ตรวจ WinError 5 และแก้ lifecycle ของ Demo 2459

ตรวจและเปิดใช้งานกลับ: 2026-10-15 เวลา 13:23 น. กรุงเทพฯ (UTC+7)

## ข้อค้นพบ

- Traceback ที่ได้รับเกิดใน `multiprocessing.spawn` ขณะ `rebuild_pipe_connection` เรียก `DuplicateHandle` ก่อนเข้า worker target ไม่ใช่ exception จากสูตรคำนวณสัญญาณเทรด
- ทดสอบแยกด้วย Python 3.11 บนเครื่องนี้ โดยไม่เชื่อม MT5 และไม่โหลดกลยุทธ์: ให้ process หลักออกขณะที่ลูกกำลัง unpickle queue สามารถสร้าง `PermissionError: [WinError 5] Access is denied` ที่ตำแหน่งเดียวกันได้
- ลำดับ force-stop ที่หยุด main ก่อน worker มีความเสี่ยงดังกล่าว จึงเปลี่ยนทาง restart ปกติให้เป็น cooperative shutdown
- ยังระบุไม่ได้ว่า traceback ต้นฉบับมาจากการปิดครั้งใด เพราะข้อความไม่มีเวลา/PID ประกอบ ก่อนแก้พบ marker ปิด supervisor เวลา 13:05 และไม่มี process ของโปรไฟล์เหลืออยู่
- ค่า `MT5_WORKER_MODE=subprocess` สืบทอดจาก environment ของ process ที่เปิดบอท แม้ `profile.env` ของ 2459 ไม่ได้ระบุ key นี้ ไม่ได้เปลี่ยน worker mode เพื่อหลบ error

## ตรวจกลยุทธ์ที่เพิ่ม

- `INDI1`: adapter และ core สร้างสัญญาณ ไม่มีการสร้าง multiprocessing worker เอง
- `EA2_1`: bridge/live adapter ใช้ MT5 worker ส่วนกลาง ไม่มี subprocess ของตัวเอง
- `SCALPING456`: broker adapter ไม่ initialize/login/spawn เมื่อ import; เรียก broker ที่ส่งเข้ามา ใช้ reader ส่วนกลางเช่นเดียวกัน
- ทดสอบ import ทั้งสาม adapter โดยตั้งให้การเรียก start_worker/initialize/order_send ทำให้ test ล้มทันที: ผ่าน ไม่พบการเรียกดังกล่าวตอน import
- ไม่พบหลักฐานว่า strategy ใดเป็นต้นเหตุของ traceback นี้ แต่ไม่ได้หมายความว่าทุกพฤติกรรมการเทรดผ่านการพิสูจน์ครบแล้ว

## สิ่งที่แก้

- `mt5_worker.py`: เพิ่ม `stop_worker()` ส่ง sentinel และรอ reader จบ หาก native read ค้างให้หยุดเฉพาะ child ของตัวเองแล้ว join ขณะที่ main ยังมีชีวิต ปิด queue หลัง child จบ และ latch ไม่ให้ late call สร้าง worker/ส่ง trade ใหม่ระหว่าง shutdown
- `demo_restart_control.py`: รับคำขอที่ตรง profile, PID และมีอายุไม่เกิน 120 วินาที; pause scheduler, save state, หยุด Application ตาม lifecycle และเขียน acknowledgment หลังหยุด worker
- Cleanup task ของ Telegram send queue และ news loop ก่อนปิด event loop แก้ `RuntimeError: Event loop is closed` ที่พบเพิ่มระหว่างทดสอบ shutdown
- `main.py`: เปิด control job/hooks เฉพาะ `demo-iux-2101182459` และปิด reader ใน finally ของโปรไฟล์นี้
- `restart_demo_2459.ps1`: เริ่มโปรไฟล์เมื่อหยุดอยู่ หรือขอ restart แบบ cooperative หากกำลังรัน; ป้องกัน operator ซ้อน รอ acknowledgment/heartbeat ใหม่ และไม่มีคำสั่ง force-kill fallback
- `run/restart_demo_2459.bat`: ทางเรียกใช้งานแบบดับเบิลคลิกสำหรับโปรไฟล์นี้
- ไม่เปลี่ยนสูตรเข้า/ออก, lot, magic, risk limit หรือ active portfolio flags และไม่รีสตาร์ตโปรไฟล์อื่น

## ผลทดสอบ

- Unit/mock: restart + worker lifecycle 13, Scalping456 25, EA2_1 4 และ portfolio manager 10 รวม 52 เคสผ่าน
- Mock process-tree stop/supervisor regressions ผ่าน ไม่มีการหยุด process จริงในการทดสอบชุดนั้น
- ทดสอบ isolated pipe handoff หลังแก้: join worker สำเร็จก่อน parent ออก ไม่มี WinError 5/Traceback
- Python compile, PowerShell parse, UTF-8/LF และ scoped mojibake ผ่าน; PowerShell helper มี UTF-8 BOM
- เรียก `verify_repo.py` แล้วพบปัญหา encoding เดิมนอกไฟล์ที่แก้ รวมทั้งไฟล์ config แบบ binary/UTF-16 ของ MT5 จึงยุติการสแกนกว้าง ไม่อ้างว่าทั้ง repository ผ่าน

## ยืนยันรอบ restart หลังแก้ครบ

- Main เดิม PID 39336 รับคำขอและยืนยัน `worker_stopped=true` ก่อน main ออก
- Main ใหม่ PID 35004, reader PID 36272 และ supervisor PID 16088; พบ main/reader อย่างละหนึ่ง instance
- MT5 PID 40028 เดิมยังอยู่ ไม่ได้ปิด terminal ระหว่าง cooperative restarts
- หลังรอบสุดท้าย stderr ไม่เพิ่มจาก baseline 1,782 bytes: ไม่มี WinError 5, Event loop is closed หรือ traceback ใหม่ (ข้อความ cleanup เก่าจากรอบก่อนแก้ยังเก็บไว้ ไม่ลบ log)
- Scheduler ของ Scalping456, EA2_1, กลุ่มที่รัน INDI1 และ demo portfolio กลับมาทำงาน ไม่พบ warning/error ในช่วงตรวจหลัง restart
- บัญชี 2101182459, IUXMarkets-Demo, hedging, connected/trade_allowed และ Auto ON
- Active flags ยังคง `LTS_AHR2,INDI1,EA2_1,SCALPING456`
- Snapshot 13:23:33: Scalping456 magic 995456 มี pending สองไม้ lot 0.01 (601678681/601678682), SL ครบ, ไม่มี position ค้างของตัวเอง และไม่มี pending ซ้ำ
- State `working`, cycles 55, last_error ว่าง, pending_closes ว่าง; ปิดแล้ว 54 positions สุทธิรวมต้นทุน -13.97 USD ตาม state
- ยังมี position ของพอร์ตอื่น 97 ไม้ อลิซไม่ได้ส่งคำสั่งปิด/แก้ไขให้พอร์ตอื่นระหว่างงานนี้
- Snapshot เป็นข้อมูลระหว่างระบบรันจริง จำนวนออเดอร์/PnL เปลี่ยนตามตลาดได้

## วิธี restart ครั้งต่อไป

ดับเบิลคลิก `run/restart_demo_2459.bat` หรือรันจาก repository:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\restart_demo_2459.ps1
```

หากไม่ยืนยัน completion ภายในเวลาที่กำหนด สคริปต์จะรายงาน failure ให้ตรวจสอบ ไม่ฆ่า process หลักทิ้งเป็น fallback และไม่ลบ trading state

ทางนี้แก้การ restart ปกติ ไม่สามารถรับประกัน graceful cleanup เมื่อ Windows ถูก force-terminate/ปิดเครื่องทันทีได้ จึงไม่ควรปิดหน้าต่างหรือ kill main เพื่อ restart

Scalping456 ยังเป็น experimental demo ไม่ใช่หลักฐานว่ากำไรหรือเหมือน EA ต้นฉบับ 100%; daily loss -20 USD เป็น gate หยุดเปิดใหม่ ไม่ใช่การรับประกันขาดทุนสูงสุด

`deployment_manifest.json` เดิมเก็บ snapshot ของการ deploy รอบแรกไว้ตามเดิม; ไฟล์ main.py และ lifecycle layer มีการแก้ตามบันทึกฉบับนี้หลัง manifest นั้น
