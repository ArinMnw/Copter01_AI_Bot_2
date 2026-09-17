# Standard Operating Procedure: Adding a New MT5 Profile

คู่มือมาตรฐานสำหรับการสร้างและลงทะเบียน Profile บัญชี MT5 ใหม่ในระบบ `Copter01_AI_Bot_2`  
เมื่อผู้ใช้ต้องการเพิ่ม Profile ใหม่ ผู้ใช้จะระบุข้อมูลเพียง 4 อย่างเท่านั้น:
1. **broker**: (เช่น `exness`, `iux`, `vantage`, `vtmarket`, `xm`)
2. **user** (login): (เช่น `434237129`)
3. **server**: (เช่น `Exness-MT5Trial7`, `IUXMarkets-Demo`)
4. **token_telegram**: Token ของบ็อต Telegram จาก BotFather
*(รหัสผ่านหากไม่ระบุ ให้ใช้ค่า default: `cop04TERZ_`)*

---

## ขั้นตอนที่ 1: การสร้างโฟลเดอร์ Profile

ตั้งชื่อโฟลเดอร์ตามมาตรฐาน:
- Demo: `profiles/demo/demo-<broker>-<user>` (เช่น `profiles/demo/demo-exness-434237129`)
- Real: `profiles/real/real-<broker>-<user>` (เช่น `profiles/real/real-vtmarket-26575165`)

### สิ่งที่ต้องคัดลอกและตั้งค่าในโฟลเดอร์ใหม่:
1. **คัดลอก MT5 Portable**: คัดลอกจากโปรไฟล์โบรกเกอร์เดียวกัน (หรือโปรไฟล์ต้นแบบ)
   - ⚠️ **สำคัญมากสำหรับ Exness**: ต้องแน่ใจว่าไฟล์ `mt5/config/servers.dat` มีข้อมูลเซิร์ฟเวอร์ Exness (คัดลอกจากโปรไฟล์ Exness ที่ใช้งานได้ เช่น `demo-exness-416273786/mt5/config/servers.dat`)
2. **สร้าง/แก้ไขไฟล์ `profile.env`**:
   ```env
   BOT_PROFILE=demo-<broker>-<user>
   MT5_PATH=mt5\terminal64.exe
   MT5_PORTABLE=true
   MT5_LOGIN=<user>
   MT5_PASSWORD=cop04TERZ_
   MT5_SERVER=<server>
   MT5_TIMEOUT_MS=120000
   SYMBOL=<symbol>
   SYMBOL_CANDIDATES=<symbol_candidates>
   MAGIC_NUMBER=234001
   MY_USER_ID=8666020453
   TELEGRAM_TOKEN=<token_telegram>
   DEMO_PORTFOLIO_ACTIVE=NONE
   ACTIVE_STRATEGIES=20.18,20.19,20.20,20.21,20.22,20.24,20.28,20.301,20.302,20.303,20.304
   TRAIL_SL_ENABLED=true
   TREND_FILTER_PER_TF_ALL_OFF=true
   ```
   *หมายเหตุเรื่อง Symbol:*
   - Exness: `SYMBOL=XAUUSD`, `SYMBOL_CANDIDATES=XAUUSD,XAUUSDm,XAGUSD,XAGUSDm,EURUSD,EURUSDm,GBPUSD,GBPUSDm,USDJPY,USDJPYm`
   - IUX: `SYMBOL=XAUUSD.iux`, `SYMBOL_CANDIDATES=XAUUSD.iux,XAGUSD.iux,EURUSD.iux,GBPUSD.iux,USDJPY.iux`
3. **สร้าง/แก้ไขไฟล์สคริปต์ในโฟลเดอร์ `run/`**:
   - `open_mt5.bat`: ใส่ `/login:<user> /password:<password> /server:<server>`
   - `run_supervised.bat`: ตั้ง `set BOT_PROFILE=demo-<broker>-<user>`
   - `stop_supervised.bat`: ตั้ง `-Profile demo-<broker>-<user>`
4. **ทำความสะอาด Logs และ State เก่า**:
   - ลบไฟล์ทั้งหมดใน `logs/` (สร้างเฉพาะ `.gitkeep`)
   - ลบไฟล์ใน `mt5/logs/`
   - รีเซ็ต `bot_state.json` เป็น `{}`
   - ลบไฟล์ `bot_heartbeat.txt`, `supervisor.lock`, `supervisor_closed.marker` (ถ้ามี)

---

## ขั้นตอนที่ 2: อัปเดตไฟล์ระบบส่วนกลาง (Central Registration Checklist)

ต้องอัปเดตไฟล์ดังต่อไปนี้ให้ครบทุกไฟล์เสมอ:

### 1. `profiles/demo/demo_control_center.bat`
- **[open_mt5_menu]**: เพิ่มตัวเลือกเมนู และ block `if "%sub_opt%"=="X"` กำหนด `P_NAME`, `P_LOGIN`, `P_PASS`, `P_SRV`
- **[open_all_mt5]**: เพิ่มการสั่ง start terminal ของโปรไฟล์ใหม่
- **[run_bot_menu]**: เพิ่มตัวเลือกเมนู และ block `if "%sub_opt%"=="X" set "P_NAME=..."`
- **[run_all_bots]**: เพิ่มคำสั่งเปิดรันบ็อตโปรไฟล์ใหม่

### 2. `run/stop_supervised_all.bat`
- เพิ่มโปรไฟล์ใหม่ใน **Phase 1** (`powershell ... -Profile demo-<broker>-<user> -SkipWindowClose`)
- เพิ่มโปรไฟล์ใหม่ใน **Phase 2** (`powershell ... -Profile demo-<broker>-<user> -OnlyCloseWindow`)
- ปรับตัวเลขหัวเรื่อง (เช่น `root + N profiles`)

### 3. `run/cleanup_mt5_profiles.py`
- ตรวจสอบฟังก์ชัน `cleanup_mt5_folder()`: หากโปรไฟล์นี้มีการเทรดหลายเหรียญ (เช่น S20.304 Multi-Asset) ให้เพิ่มชื่อโปรไฟล์ใน `is_multi_needed` เพื่อป้องกันการลบข้อมูลกราฟของคู่เงินอื่น (`xagusd`, `eurusd`, `gbpusd`, `usdjpy`)

### 4. `dashboard.py`
- **`ACCOUNT_LABELS`**: เพิ่มคู่ key-value สำหรับแสดงชื่อใน Dropdown ของ Dashboard:
  ```python
  "demo-<broker>-<user>": "🟢 Demo • <Broker> <ShortID> — <Description>",
  ```
- **`ACCOUNT_BACKTEST_STRATEGIES`**: เพิ่มรายชื่อกลยุทธ์ที่ใช้กับบัญชีนี้ (เช่น `["S20_ALL", "S20_301", "S20_302", "S20_303", "S20_304"]`)

### 5. `profiles/profiles.md`
- เพิ่มบันทึกรายละเอียดบัญชีในหัวข้อ Demo Accounts หรือ Real Accounts:
  - เลข Terminal, โบรกเกอร์, เซิร์ฟเวอร์, วัตถุประสงค์การใช้งาน และกลยุทธ์ที่เปิดรัน

---

## ขั้นตอนที่ 3: การทดสอบความถูกต้อง (Verification)

1. **ทดสอบ Login ผ่าน Python**:
   ```bash
   python -c "from strategy.s20_compare_engine import connect_profile_mt5; import MetaTrader5 as mt5; print('Connected:', connect_profile_mt5('demo-<broker>-<user>')); print('Acc:', mt5.account_info().login, 'Limit:', mt5.account_info().limit_orders); mt5.shutdown()"
   ```
2. **ทดสอบรัน Backtest Compare**:
   ```bash
   python strategy/backtest_s20_unified.py --strategy S20_301 --start "YYYY-MM-DD HH:MM" --compare --compare-profile demo-<broker>-<user> --concurrent
   ```
