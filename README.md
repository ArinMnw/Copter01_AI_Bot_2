# Copter01_AI_Bot

บอทเทรดอัตโนมัติสำหรับ MT5 ที่ควบคุมผ่าน Telegram

## ภาพรวม

- สแกน pattern หลาย timeframe
- เปิด pending order และ market order ตามเงื่อนไขของแต่ละท่า
- จัดการ SL / TP / trail / sweep / pending cancel หลังเปิด position

## วิธีรัน

```bash
python main.py
```

บน Windows:

```bash
run.bat
```

## ไฟล์สำคัญ

- `config.py`
- `scanner.py`
- `trailing.py`
- `handlers/keyboard.py`
- `handlers/callback_handler.py`

## เอกสารเพิ่มเติม

- `CLAUDE.md`
- `codex.md`
- `docs/strategies.md`
- `docs/trailing.md`
- `docs/runtime-state.md`
- `docs/telegram-ui.md`
- `docs/logging.md`

## เวลา MT5 -> BKK

ตอนเทียบเวลาในโปรเจกต์นี้ broker time (MT5 server) ต่างจาก BKK ตามฤดู:

| ฤดู | offset | ตัวอย่าง |
| --- | --- | --- |
| MT5 -> winter (UTC+1) | `+6 ชม.` ไป BKK | broker `11:32` → `17:32 BKK` |
| MT5 -> summer (UTC+2) | `+5 ชม.` ไป BKK | broker `12:32` → `17:32 BKK` |

หมายเหตุ:
- เวลาใน `bot.log` เป็น BKK (UTC+7) — ใช้เป็นแหล่งอ้างอิงหลัก
- เวลาใน MT5 chart, order time, history เป็น broker time
- ถ้าตามรอย order ระหว่าง bot.log กับ MT5 ให้ปรับ offset ด้วยเสมอ

