# Telegram UI และเมนู

เอกสารนี้สรุปหลักการแก้ไขเมนู, label และ callback ของฝั่ง Telegram

## ไฟล์หลัก

- `handlers/keyboard.py`: ข้อความเมนู, inline keyboard และข้อความสรุป
- `handlers/callback_handler.py`: action ของ callback ต่าง ๆ

## กติกาเวลาแก้ไข

- ให้มอง `handlers/keyboard.py` เป็นไฟล์ที่ text-sensitive
- อย่าเปลี่ยน callback name ถ้ายังไม่ได้แก้ handler logic ให้รองรับด้วย
- ระวัง encoding ของข้อความไทยและ emoji
- ถ้าเป็นงานแก้ text อย่างเดียว อย่าแตะ logic ส่วนอื่นที่ไม่เกี่ยวข้อง

## การตรวจสอบหลังแก้

- รัน `python check_mojibake.py` หลังแก้ text หนัก ๆ
- รัน `python -m py_compile handlers/keyboard.py handlers/callback_handler.py`

## ความเสี่ยงที่พบบ่อย

- ข้อความไทยหรือ emoji เพี้ยนเพราะ encoding
- เปลี่ยน label แล้วลืมอัปเดต callback ให้สอดคล้อง
- ข้อความเมนูกับ config state แสดงผลไม่ตรงกัน

## Convention เรื่อง Toggle Icon

- ฟังก์ชันที่เปิด/ปิดได้ ให้ใช้ icon `🟢ON` สำหรับเปิด และ `🔴OFF` สำหรับปิด
- ถ้าสถานะเป็น OFF ห้ามต่อ `|` แล้วใส่รายละเอียดต่อท้าย ให้แสดงแค่ `🔴OFF`
- ถ้าเป็น ON และมีรายละเอียดเสริม ใช้รูปแบบ `🟢ON | รายละเอียด`
- ปุ่มในเมนูและ status text ในเมนูเดียวกันต้องใช้ suffix เดียวกัน

## โครงสร้าง Master Toggle

ฟังก์ชันที่มี submenu (Trail SL, Entry Candle Mode, Opposite Order):

- ปุ่ม master toggle อยู่ **ด้านในสุด** ของ submenu ตัวเอง (ไม่ใช่หน้าหลัก)
- Label ใช้รูปแบบ `🟢 เปิดใช้งาน <ชื่อ>` เมื่อ ON, `🔴 ปิดใช้งาน <ชื่อ>` เมื่อ OFF
- callback ของ master toggle ใช้ pattern `toggle_<name>_enabled`
- ฟังก์ชันจริงใน `trailing.py` ใช้ `getattr(config, "<FLAG>", True)` gate เพื่อ early-return ถ้า OFF

ฟังก์ชันที่ toggle ตรง (Entry Candle TP, Limit Sweep, Delay SL):

- toggle ที่หน้าหลักเลย ไม่มี submenu แยก
- Delay SL มี 3 mode: `off` → `🔴OFF`, `time` → `🟢ON | ช่วงท้าย TF`, `price` → `🟢ON | ราคาผ่าน Entry`
