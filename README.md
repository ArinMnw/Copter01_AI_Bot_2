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
