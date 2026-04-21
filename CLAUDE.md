# CLAUDE.md

เอกสารสรุปกติกาหลักสำหรับทำงานใน repository นี้

## กติกาเรื่อง Encoding

- อ่านและบันทึกไฟล์เป็น `UTF-8` เสมอ
- line ending ของไฟล์ text ให้เป็น `LF` ตาม `.gitattributes`
- ระวังข้อความภาษาไทยและ emoji อย่าใช้เครื่องมือที่อาจเปลี่ยน encoding
- ถ้าแก้ข้อความเยอะ ให้รัน `python check_mojibake.py`
- ถ้าแก้โค้ด ให้รัน `python verify_repo.py` เมื่อทำได้

## Checklist แบบเร็ว

- ถ้าแก้ข้อความไทย, emoji, Telegram message หรือ Markdown: รัน `python check_mojibake.py`
- ถ้าแก้ไฟล์ Python: รัน `python -m py_compile <ไฟล์ที่แก้>` หรือ `python verify_repo.py`
- ถ้าแก้ `scanner.py`, `trailing.py`, `config.py`, หรือ handler ฝั่ง Telegram: เช็ก label, callback name และ config state ให้ตรงกัน
- ถ้าแก้ order comment, log หรือ parser: เช็กว่ายัง parse และสรุปผลได้ถูก
- พยายามเช็กทีละรอบหลังแก้ อย่ารอค่อยเช็กทั้งหมดตอนท้าย

## ภาพรวมโปรเจกต์

- เป็น MT5 trading bot ที่ควบคุมผ่าน Telegram
- runtime หลักเป็น async Python process ที่รันยาว
- ไม่มี build step
- จุดเริ่มต้นหลักคือ `main.py`
- dependency สำคัญคือ `MetaTrader5`, `python-telegram-bot`, `apscheduler`

## วิธีรัน

```bash
python main.py
```

บน Windows:

```bash
run.bat
```

## ไฟล์สำคัญ

- `config.py`: config, flag และ helper สำหรับ save/restore state
- `scanner.py`: scan signal, scan summary และสร้าง order
- `trailing.py`: entry handling, trail, pending cancel, sweep, protect, breakeven
- `mt5_utils.py`: helper ฝั่ง MT5 และการสร้าง comment
- `notifications.py`: ข้อความแจ้งเตือนเปิด/ปิด order
- `handlers/keyboard.py`: ข้อความเมนูและ summary ใน Telegram
- `handlers/callback_handler.py`: callback action ของปุ่มต่าง ๆ
- `bot_log.py`: การเขียน log

## เอกสารแยก

- `docs/strategies.md`
- `docs/trailing.md`
- `docs/runtime-state.md`
- `docs/telegram-ui.md`
- `docs/logging.md`

## Runtime State

state หลักอยู่ใน `trailing.py` และ `config.py`

ตัวแปรสำคัญ:

- `pending_order_tf`
- `position_tf`
- `position_sid`
- `position_pattern`
- `_entry_state`
- `_s6_state`
- `_s6i_state`

state ถาวรถูกบันทึกลง `bot_state.json`

## รูปแบบ Comment ของ Order

ใช้รูปแบบประมาณนี้:

```text
Bot_{TF}_S{SID}_{PATTERN_CODE}
```

ตัวอย่าง:

- `Bot_M1_S1_PA`
- `Bot_H1_S2_FVG`
- `Bot_M5_S6i_buy`

และต้องระวังไม่ให้ยาวเกิน limit ของ MT5

## Entry Candle Mode

mode ที่รองรับ:

- `classic`
- `close`
- `close_percentage`

หมายเหตุ:

- `close` ใช้ reverse market/limit toggle ได้
- `close_percentage` เป็น mode แยกจาก `close`
- กฎโครงสร้างแบบ limit sweep ควรทำงานได้ไม่ว่าตั้ง `ENTRY_CANDLE_MODE` เป็นอะไร
- `ENTRY_CANDLE_ENABLED` เป็น master toggle — ถ้า `False` `check_entry_candle_quality()` จะ return ทันที

## พฤติกรรมสำคัญของระบบ

### Trail SL

- logic หลักอยู่ใน `trailing.py`
- `TRAIL_SL_ENGULF_MODE` รองรับ `combined` และ `separate`
- `TRAIL_SL_IMMEDIATE` คุมว่าจะ trail ได้ก่อน `_entry_state = done` หรือไม่
- `TRAIL_SL_ENABLED` เป็น master toggle — ถ้า `False` `check_engulf_trail_sl()` จะ return ทันที

### Limit Guard

- ใช้ยกเลิก pending limit ที่ไกลจาก position ปัจจุบันมากเกินไป
- มีทั้ง mode `separate` และ `combined`

### Limit Sweep

- ใช้ปิด position และจัดการ pending order ต่อ เมื่อแท่ง adverse ปิดทะลุโครงสร้างสำคัญ
- S8 follow-up ต้องเลือก `LL/HH` ที่ยัง valid ไม่ใช่ level ที่แท่งปิดทะลุไปแล้ว

### S8

- S8 ตั้ง limit ก่อน
- SL อาจถูก arm ทีหลังตาม flow ปัจจุบัน
- ถ้า S8 fill ก่อน arm SL ต้องมี fallback ไปตั้ง SL ให้ position ที่ fill แล้ว
- ปุ่ม `strategy_all_on` (เลือกทั้งหมด) ไม่เปิด S8 — ต้องกดเปิดรายตัวเอง

### S2 FVG

- FVG ตรวจทั้ง engulf และ gap distance
- ขั้นต่ำของ gap ใช้ค่าเดียวกับ engulf (`engulf_min_price()`) ไม่ใช่ค่า hardcoded
- pattern ที่เปิดใช้งาน: `เขียวกลืนกิน`/`แดงกลืนกิน` และ `ปฏิเสธราคา`
- pattern `ปฏิเสธราคา` รับได้ทั้งแท่งปิดเขียวและแดง (ไม่มีเงื่อนไขสี)
- pattern default `แดง`/`เขียว` (pattern 3-4) ปิดใช้งาน แต่ยังคง classification logic ไว้เพื่อ log
- pattern `ปฏิเสธราคา` ใช้ `cancel_bars = 1` — ถ้า limit ไม่ fill ภายใน 1 แท่งถัดไปจะยกเลิกอัตโนมัติ (ใช้กลไกเดิมใน `trailing.py`)
- `Limit TP/SL Break Cancel` ไม่ใช้กับ pattern 1 (`เขียวกลืนกิน`/`แดงกลืนกิน`) — skip ผ่าน `c3_type` ใน `pending_order_tf`

### Opposite Order Mode

รองรับ 2 แบบ:

- `tp_close`
- `sl_protect`

- `OPPOSITE_ORDER_ENABLED` เป็น master toggle — ถ้า `False` `check_opposite_order_tp()` จะ return ทันที

### SL Protect

- ไม่ควรยิงซ้ำรัวสำหรับ ticket เดิม
- ข้อความ Telegram ฝั่ง protect/trail ควรถูก dedup

## Telegram Toggle Icons

- ปุ่มและ status text ของฟังก์ชันที่เปิด/ปิดได้ใช้ icon: `🟢ON` = เปิด, `🔴OFF` = ปิด
- ถ้า OFF ไม่แสดง suffix รายละเอียด (ไม่มี `|` ตามหลัง)
- ฟังก์ชันที่มี master toggle และ submenu: Trail SL, Entry Candle Mode, Opposite Order
- ฟังก์ชันที่ toggle ตรงจากหน้าหลัก: Entry Candle TP, Limit Sweep, Delay SL (3 mode)

## Log และสรุปกำไร

- log หลักคือ `logs/bot.log`
- มี monthly log เช่น `logs/bot-YYYY-MM.log`
- `POSITION_CLOSED` ใช้เป็นฐานของสรุปกำไร
- เวลา Telegram มากับ log ไม่ตรงกัน ให้เชื่อ `bot.log` ก่อน

## กติกาเวลาแก้ไฟล์

- แก้เฉพาะจุดเท่าที่จำเป็น
- ถ้าเป็นงาน text-only ห้ามเปลี่ยน trading logic
- อย่าเปลี่ยน callback name, config key หรือชื่อ state field โดยไม่แก้ให้ครบทั้งระบบ
- ถ้าแก้ text ใน handler Telegram ให้เช็ก `py_compile` หลังแก้
- ถ้าไม่แน่ใจว่า behavior หนึ่งเป็นของตั้งใจหรือไม่ ให้ดู code และ log ก่อนสรุป

## คำสั่งตรวจงาน

เช็กข้อความเพี้ยน:

```bash
python check_mojibake.py
```

เช็กทั้ง repo:

```bash
python verify_repo.py
```

เช็กเฉพาะไฟล์ที่แก้:

```bash
python verify_repo.py handlers/keyboard.py config.py
```
