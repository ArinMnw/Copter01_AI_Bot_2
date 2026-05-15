# ระบบ Log

เอกสารนี้สรุปโครงสร้าง log หลักที่ใช้ในโปรเจกต์นี้

## โครงสร้างไดเรกทอรี log

```
logs/
├── bot.log                   ← log หลัก (rolling, ทุก event สำคัญ)
├── bot-YYYY-MM.log           ← monthly log (สำเนาทุก event เดียวกับ bot.log)
├── error-YYYY-MM.log         ← error log รายเดือน (ERROR level + Python exception)
├── system/
│   └── system.log            ← Python logging (INFO+) ผ่าน logging.FileHandler
└── debug/
    └── sltp_audit.log        ← audit trail ของการเปลี่ยน SL/TP (เขียนโดย trailing.py)
```

## ไฟล์ log หลัก

### `logs/bot.log` และ `logs/bot-YYYY-MM.log`

- เขียนโดย `log_event()` และ `log_block()` ใน `bot_log.py`
- ทุก event สำคัญ (ORDER_CREATED, POSITION_CLOSED, SCAN_SUMMARY ฯลฯ)
- รูปแบบบรรทัด: `[YYYY-MM-DD HH:MM:SS] KIND | message | field=value | ...`
- `bot.log` และ `bot-YYYY-MM.log` ได้รับข้อมูลเดียวกัน

### `logs/error-YYYY-MM.log`

- เขียนโดย `log_error()` ใน `bot_log.py`
- `_ErrorLogHandler` catch Python `logging.ERROR` level → เขียนลงไฟล์นี้ด้วย
- `sys.excepthook` ใน `main.py` เขียน unhandled exception ลงที่นี่
- ใช้ตามรอย crash หรือ exception ที่อาจถูกกลืนไป

### `logs/system/system.log`

- Python `logging` module ระดับ `INFO+`
- เขียนผ่าน `setup_python_logging()` ใน `bot_log.py`
- ใช้ดู library log, APScheduler event, และ warning จาก dependency

### `logs/debug/sltp_audit.log`

- audit trail ของการเปลี่ยน SL/TP ทุกครั้ง
- เขียนโดย `_audit_sltp_event()` ใน `trailing.py`
- `SLTP_AUDIT_DIR = os.path.join(LOG_DIR, "debug")` ใน `trailing.py`

## SCAN_SUMMARY

- log ทุกครั้งที่ body เปลี่ยน (dedup ด้วย `tg_key = body`)
- **force-log ทุก 60 วินาที** แม้ body จะไม่เปลี่ยน (ทั้ง bot.log และ Telegram)
- ควบคุมด้วย `SCAN_SUMMARY_FORCE_INTERVAL = 60` ใน `scanner.py`
- S12 ที่อยู่ใน cooldown จะ **ไม่แสดง** ใน SCAN_SUMMARY (ป้องกัน body ค้างจากค่า 0.00)
- ส่วน `Scan Swing` ใน summary ปัจจุบันมีข้อมูลเวลาเพิ่ม:
  - `AsOf` = สรุปจากแท่งปิดล่าสุดเวลาไหน
  - `H✓` = swing high ล่าสุด confirm ตั้งแต่เวลาไหน
  - `L✓` = swing low ล่าสุด confirm ตั้งแต่เวลาไหน
- ใช้ช่วยไล่เคส pivot `right bars` ว่าพร้อมใช้งานจริงตั้งแต่เมื่อไร

## PATTERN_FOUND

- `PATTERN_FOUND` จะ log หลัง shared TP ถูกคำนวณแล้ว เพื่อให้ `tp` และ `flow_id` ตรงกับ order จริงที่กำลังจะถูกสร้าง
- มี Telegram pattern alert แยกด้วย และ dedup ตาม `flow_id` เพื่อไม่ให้เด้งซ้ำทุก 5 วินาที
- ใช้ดูจังหวะเจอ pattern ก่อน `ORDER_CREATED` และช่วยตามรอยกรณี order ถูก skip หรือ failed ได้ง่ายขึ้น

## Log Retention

- `cleanup_old_logs(retention_days=7)` ใน `bot_log.py` ลบบรรทัดเก่าออก
- monthly log ที่ไม่มีบรรทัดเหลือจะถูกลบทั้งไฟล์

## หมายเหตุสำคัญ

- `bot.log` คือแหล่งข้อมูลหลักเวลาตามรอยปัญหา runtime
- Telegram notification อาจมาช้ากว่า event จริง
- สรุปกำไรจะอ้างอิงจากข้อมูล `POSITION_CLOSED` ใน log
- เวลาใน log เป็น BKK (UTC+7), MT5 chart เป็น broker time

## เวลาแก้โค้ดที่เกี่ยวกับ log

- พยายามให้ field อย่าง `ticket`, `tf`, `sid`, `pattern` สม่ำเสมอ
- ถ้าแก้ parser ของ log ต้องเช็กว่าสรุปผลต่าง ๆ ยัง group ถูกต้อง
- ถ้าเพิ่ม action สำคัญใหม่ ให้คิดด้วยว่าควรเขียนลง `bot.log` หรือไม่

## ลำดับการไล่ปัญหาที่แนะนำ

1. เช็ก `bot.log` (และ monthly log ถ้าปัญหาข้ามเดือน)
2. เช็ก `error-YYYY-MM.log` ถ้าสงสัย crash หรือ exception
3. เช็ก `system/system.log` ถ้าปัญหาเกี่ยวกับ library หรือ scheduler
4. เช็ก `debug/sltp_audit.log` ถ้าปัญหาเกี่ยวกับ SL/TP เปลี่ยนโดยไม่คาดคิด
5. ใช้ Telegram output เป็นข้อมูลประกอบ ไม่ใช่แหล่งอ้างอิงหลัก
