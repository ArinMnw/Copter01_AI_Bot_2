# Profile Testing Matrix

เอกสารนี้สรุปว่าแต่ละ `BOT_PROFILE` ถูกแยกไว้เพื่อทดสอบอะไร โดยไม่บันทึก token/password/account secret ลงในเอกสาร

## Default / No Profile

- ใช้เมื่อรันบอทแบบไม่ตั้ง `BOT_PROFILE`
- Strategy หลักยังใช้ค่า default จาก `config.py`
- ปิด S20 และ S20 ย่อยทั้งหมด
- ปิด Demo Portfolio ทั้งหมด:
  - `P13 = OFF`
  - `P16 = OFF`
  - `AF22 = OFF`
  - `AF34 = OFF`
  - `AF47 = OFF`

## demo-iux-2101114448

วัตถุประสงค์: profile demo หลักเดิม สำหรับรันชุด strategy หลักเหมือนเดิม แต่ไม่ให้ S20/P/AF เข้ามาปน

- Strategy หลัก: เปิดตาม default เดิมของบอท
- S20 / S20 ย่อย: ปิดทั้งหมด
- Demo Portfolio: ปิดทั้งหมด
- External S20.12 supervisor: ไม่เปิด
- เหมาะสำหรับ: เทียบพฤติกรรมบอทหลักเดิมโดยไม่มี P13/P16/AF/S20.12 รบกวน

## demo-iux-2101182459

วัตถุประสงค์: isolate S20.12 อย่างเดียว

- Strategy หลัก: ปิดทั้งหมด
- S20.12: เปิด
- S20 ตัวอื่น / S20 ย่อยอื่น: ปิด
- Demo Portfolio: ปิดทั้งหมด
- External S20.12 supervisor: เปิด
- Auto scan summary / scan swing: ปิดทั้ง Telegram และ command log
- Trade management extras: ปิด Trail SL, จุดกลับตัว Trail SL, Trail Focus, Opposite Order, Limit Guard, Trend Filter submenu, และ TSO4x
- เหมาะสำหรับ: forward test S20.12 แบบไม่ปน strategy อื่น

## demo-iux-2101182460

วัตถุประสงค์: isolate P13/P16 Demo Portfolio

- Strategy หลัก: ปิดทั้งหมด
- S20 / S20 ย่อย: ปิดทั้งหมด
- Demo Portfolio:
  - `P13 = ON`
  - `P16 = ON`
  - `AF22 = OFF`
  - `AF34 = OFF`
  - `AF47 = OFF`
- External S20.12 supervisor: ไม่เปิด
- Auto scan summary / scan swing: ปิดทั้ง Telegram และ command log
- Trade management extras: ปิด Trail SL, จุดกลับตัว Trail SL, Trail Focus, Opposite Order, Limit Guard, Trend Filter submenu, และ TSO4x
- เหมาะสำหรับ: forward test P13/P16 เทียบกับ backtest โดยไม่ปน AF หรือ strategy หลัก

## demo-iux-2101182461

วัตถุประสงค์: isolate AF ladder portfolios

- Strategy หลัก: ปิดทั้งหมด
- S20 / S20 ย่อย: ปิดทั้งหมด
- Demo Portfolio:
  - `P13 = OFF`
  - `P16 = OFF`
  - `AF22 = ON`
  - `AF34 = ON`
  - `AF47 = ON`
- External S20.12 supervisor: ไม่เปิด
- Auto scan summary / scan swing: ปิดทั้ง Telegram และ command log
- Trade management extras: ปิด Trail SL, จุดกลับตัว Trail SL, Trail Focus, Opposite Order, Limit Guard, Trend Filter submenu, และ TSO4x
- เหมาะสำหรับ: forward test AF22/AF34/AF47 แบบ full ladder แยกจาก P13/P16 และ strategy หลัก

## Config Source

ค่าแยก profile อยู่ใน `profile.env` ของแต่ละ profile:

- `ACTIVE_STRATEGIES`
- `S20_PROFILE_MODE`
- `DEMO_PORTFOLIO_ACTIVE`
- `SCAN_SUMMARY_TELEGRAM_ENABLED`
- `SCAN_SWING_TELEGRAM_ENABLED`
- `SCAN_SUMMARY_LOG_ENABLED`
- `SCAN_SWING_LOG_ENABLED`
- `TRAIL_SL_ENABLED`
- `TRAIL_SL_REVERSAL_OVERRIDE_ENABLED`
- `TRAIL_SL_FOCUS_NEW_ENABLED`
- `OPPOSITE_ORDER_ENABLED`
- `LIMIT_GUARD`
- `TREND_FILTER_PER_TF_ALL_OFF`
- `TREND_FILTER_HIGHER_TF_ENABLED`
- `TREND_FILTER_TRAIL_SL_OVERRIDE_ENABLED`
- `TREND_FILTER_SIDEWAY_HHLL`
- `TREND_FILTER_SCAN_BLOCK`
- `SCALE_OUT_ENABLED`

`config.py` จะอ่านค่าเหล่านี้ตอนเริ่มโปรแกรม และ apply ซ้ำหลัง `restore_runtime_state()` เพื่อให้ค่า profile ชนะ `bot_state.json`

ถ้าลบ `bot_state.json`:

- ค่าเปิด/ปิด strategy/S20/P/AF ตาม profile ยังอยู่
- runtime state ของ order/trailing/fill notify/SL guard/cooldown จะหาย

## Safety Notes

- P13/P16/AF ถูกตั้งให้ใช้ `DEMO_PORTFOLIO_SYMBOL = XAUUSD`
- ถ้า XAUUSD ปิดหรือ tick stale ระบบ Demo Portfolio จะ skip รอบนั้น และทำงานต่อเมื่อ tick สดกลับมา
- `profiles/` ถูก ignore ทั้งก้อนใน git เพื่อไม่ commit token/password, MT5 portable data, logs, และ state runtime

## MT5 Profile Launch

- ห้ามเปิด `profiles/demo/<profile>/mt5/terminal64.exe` โดยตรงถ้าต้องการให้ทำงานเป็น profile แยก
- ให้เปิดผ่าน `profiles/demo/<profile>/run/open_mt5.bat` เพราะสคริปต์นี้ใส่ `/portable` และ account/server ของ profile ให้
- ถ้าปิดแล้วเปิดไม่ขึ้น หรือมี process ค้างแบบไม่มีหน้าต่าง ให้ใช้ `profiles/demo/<profile>/run/restart_mt5.bat`
- `close_mt5.bat` และ `restart_mt5.bat` จะปิดเฉพาะ `terminal64.exe` ของ profile นั้น ไม่ปิด MT5 profile อื่น
