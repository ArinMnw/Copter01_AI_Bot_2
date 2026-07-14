# Demo Portfolio — คำสั่งที่ใช้ได้ทั้งหมด

รายละเอียดเต็มของ P13/P16 ดูที่ `strategy_champion.md` (project root) — ไฟล์นี้เป็น**คำสั่งอ้างอิงเร็ว**
เท่านั้น

**ทุกคำสั่งรันจาก project root (`D:\Project\Copter01_AI_Bot_2`) โดยตรง** ไม่ต้อง `cd` เข้าโฟลเดอร์ย่อย
(script ใช้ path แบบอิงตำแหน่งไฟล์ตัวเอง ไม่ใช่ current directory จึงรันจากไหนก็ได้ — แต่ในเอกสารนี้
จะใช้ full path จาก root ตลอดเพื่อความชัดเจน):

```bash
python strategy/demo_portfolio/backtest-sim/<script>.py [args...]
```

---

## 0. เลือกบัญชีด้วย `BOT_PROFILE` บน Windows

สคริปต์ในหน้านี้ import `config.py` ดังนั้นถ้าต้องการใช้ profile แยก ต้องตั้ง `BOT_PROFILE` ก่อนรัน

Profile ที่ใช้บ่อย:

- `demo-iux-2101182460` = Demo Portfolio `P13,P16`
- `demo-iux-2101182461` = Demo Portfolio `AF22,AF34,AF47`
- `demo-iux-2101183586` = Demo Portfolio `LTS44`
- `demo-iux-2101183587` = Demo Portfolio `LTS890`

Windows `cmd` ใช้ syntax แบบ bash ไม่ได้ คำสั่งนี้ใช้ไม่ได้:

```bat
BOT_PROFILE=demo-iux-2101182460 python strategy/demo_portfolio/backtest-sim/export_demo_portfolio_compare.py all --days 7
```

ให้ใช้แบบ 2 บรรทัด:

```bat
set BOT_PROFILE=demo-iux-2101182460
python strategy\demo_portfolio\backtest-sim\export_demo_portfolio_compare.py all --days 7
```

หรือแบบบรรทัดเดียว:

```bat
set BOT_PROFILE=demo-iux-2101182460 && python strategy\demo_portfolio\backtest-sim\export_demo_portfolio_compare.py all --days 7
```

ถ้าใช้ PowerShell:

```powershell
$env:BOT_PROFILE="demo-iux-2101182460"; python strategy/demo_portfolio/backtest-sim/export_demo_portfolio_compare.py all --days 7
```

เช็ก profile ก่อนรัน:

```bat
set BOT_PROFILE=demo-iux-2101182460 && python -c "import config; print(config.BOT_PROFILE, config.MT5_LOGIN, config.DEMO_PORTFOLIO_ACTIVE)"
```

ตัวอย่างสำหรับบัญชี AF:

```bat
set BOT_PROFILE=demo-iux-2101182461 && python -c "import config; print(config.BOT_PROFILE, config.MT5_LOGIN, config.DEMO_PORTFOLIO_ACTIVE)"
```

---

## 1. Backtest — `backtest_demo_portfolio.py`

รัน backtest จำลองย้อนหลัง (ดึง config จาก `demo_portfolio.py` โดยตรง ไม่มี drift)

```bash
python strategy/demo_portfolio/backtest-sim/backtest_demo_portfolio.py P13
python strategy/demo_portfolio/backtest-sim/backtest_demo_portfolio.py P16 --days 30,60,90
python strategy/demo_portfolio/backtest-sim/backtest_demo_portfolio.py all --days 30,60,90,120,150,180 --env demo
python strategy/demo_portfolio/backtest-sim/backtest_demo_portfolio.py all --env real   # ต้องตั้ง env var ก่อน (ดูข้อ 4)
```

| Argument | ความหมาย | Default |
|---|---|---|
| `portfolio` (positional) | `P13` / `P16` / `all` | `all` |
| `--days` | รายการ window วัน คั่นด้วย comma | `30,60,90,120,150,180` |
| `--spread` | spread สมมติที่ใช้ backtest ($) | `0.20` |
| `--env` | บัญชีที่จะดึงราคามา backtest — `demo`/`real` | `demo` |

**ผลลัพธ์:** `strategy/demo_portfolio/excel/demo_portfolio_backtest_summary_<env>.csv`

---

## 1.1 Unified Portfolio Backtest Simulation — `run_backtest_sim.py`

รัน backtest จำลองการเทรดแบบลึก (สร้างไฟล์สรุปผล `trades`, `daily` และ `monthly` CSV แยกสำหรับทั้ง 19 พอร์ต พร้อมระบบ Caching สปีดสูงประหยัดเวลา)

```bash
python strategy/demo_portfolio/backtest-sim/run_backtest_sim.py --portfolio all
python strategy/demo_portfolio/backtest-sim/run_backtest_sim.py --portfolio LTS_AVENGERS_HIGH_RISK --days 550
python strategy/demo_portfolio/backtest-sim/run_backtest_sim.py --portfolio S102 --start "2026-06-01 08:00" --end "2026-06-10 17:00"
```

| Argument | ความหมาย | Default |
|---|---|---|
| `--portfolio` | ชื่อพอร์ตที่ต้องการรัน (`P13`, `AF22`, `LTS890`, `LTS_AVENGERS_HIGH_RISK` ฯลฯ) หรือ `all` | `all` |
| `--days` | จำนวนวันย้อนหลัง (ถ้าเลือก `all` พอร์ตแต่ละตัวจะมีจำนวนวันตั้งต้นที่เหมาะสมอยู่แล้ว) | `365` |
| `--start` / `--end` | กำหนดวันเริ่มต้นและสิ้นสุดแบบเจาะจง (รองรับ YYYY-MM-DD, YYYY-MM-DD HH:MM หรือ YYYY-MM-DD HH:MM:SS) — หากระบุเฉพาะ `--start` ส่วน `--end` จะถูกอ้างอิงถึงเวลาปัจจุบัน (Now) โดยอัตโนมัติ | None |
| `--balance` | กำหนดเงินทุนเริ่มต้นสำหรับคำนวณ Balance ($) | None (ใช้ตามพอร์ตนั้นๆ) |
| `--scale` | ตัวคูณ Lot / PnL เพื่อจำลองขนาดพอร์ตที่ใหญ่ขึ้น | `1.0` |
| `--spread` | ค่า Spread สมมติสำหรับทดสอบ ($) | `0.20` |
| `--out-dir` | โฟลเดอร์ปลายทางหลักของไฟล์ CSV | `strategy/demo_portfolio/excel` |

**ผลลัพธ์การบันทึกไฟล์รายงาน (แยกโฟลเดอร์ตามประเภทอัตโนมัติ):**
- `strategy/demo_portfolio/excel/p/` -> รายงานพอร์ตกลุ่ม Blend (`P13`, `P16`, `P18`)
- `strategy/demo_portfolio/excel/s/` -> รายงานพอร์ตกลุ่ม Standalone (`S101`, `S102`, `S105`, `S106`, `S111`)
- `strategy/demo_portfolio/excel/af/` -> รายงานพอร์ตกลุ่ม AF (`AF22`, `AF34`, `AF47`)
- `strategy/demo_portfolio/excel/lts/` -> รายงานพอร์ตกลุ่ม LTS (`LTS44`, `LTS890`, `LTS999` และ Avengers)

---

## 2. Compare กับผลจริงบน MT5 — `export_demo_portfolio_compare.py`

ดึงไม้จริงที่เข้าไปแล้ว (จาก `demo_portfolio_state.json` + MT5 deal history) มาสรุป realized/floating
PnL แยกราย leg

```bash
python strategy/demo_portfolio/backtest-sim/export_demo_portfolio_compare.py                    # ทุกไม้ (P13+P16 ไม่กรองเวลา)
python strategy/demo_portfolio/backtest-sim/export_demo_portfolio_compare.py P13 --days 7        # เฉพาะ P13, 7 วันล่าสุด
python strategy/demo_portfolio/backtest-sim/export_demo_portfolio_compare.py all --days 1 --env demo
```

| Argument | ความหมาย | Default |
|---|---|---|
| `portfolio` (positional) | `P13` / `P16` / `all` | `all` |
| `--days` | เอาเฉพาะไม้ที่เกิดใน N วันล่าสุด | ไม่ระบุ = ทุกไม้ |
| `--env` | บัญชีที่จะดึงผลจริง — `demo`/`real` | `demo` |

**ผลลัพธ์:**
- `strategy/demo_portfolio/excel/demo_portfolio_trades_detail.csv` (รายไม้: entry/exit/sl/tp/status/profit)
- `strategy/demo_portfolio/excel/demo_portfolio_summary.csv` (สรุปรายleg: Trades/WinRate/P&L/AvgWin/AvgLoss/MaxSLStreak/OtherClose)

**คอลัมน์ `OtherClose` สำคัญ:** ควรเป็น 0 เสมอสำหรับไม้ที่เปิดหลัง 2026-07-01 15:31 — ถ้าไม่ใช่ 0
แปลว่ามีไม้โดน generic-management ของบอทหลักปิดก่อนถึง SL/TP จริง (ดู `strategy_champion.md`
หัวข้อบั๊ก sid=21)

---

## 3. Verify Logic-Level — `verify_signal_consistency.py`

เอาไม้จริงย้อนกลับไปรัน `detect_s<N>()` เดียวกับ backtest ที่เวลาเป๊ะ ดูว่า signal/SL/TP ตรงกับที่
เกิดขึ้นจริงไหม — พิสูจน์ว่า live กับ backtest logic ไม่ drift ได้ทันที ไม่ต้องรอสะสมข้อมูลนาน

```bash
python strategy/demo_portfolio/backtest-sim/verify_signal_consistency.py P13 --days 7
python strategy/demo_portfolio/backtest-sim/verify_signal_consistency.py all --days 3 --limit 50   # จำกัดสูงสุด 50 ไม้ กันช้าเกินไป
```

| Argument | ความหมาย | Default |
|---|---|---|
| `portfolio` (positional) | `P13` / `P16` / `all` | `all` |
| `--days` | ตรวจไม้ทุกตัวที่เกิดใน N วันล่าสุด (ครอบคลุมทุก leg เท่ากัน) | `7` |
| `--limit` | จำกัดจำนวนไม้สูงสุด (optional) | ไม่จำกัด |
| `--env` | บัญชีที่จะดึงราคามาตรวจ — `demo`/`real` | `demo` |

**ผลลัพธ์ต่อไม้:** `MATCH` / `SIGNAL_MISMATCH` / `SL_TP_MISMATCH` / `NO_SIGNAL` / `SKIP_NO_RAW_TS`
(ไม้เก่าก่อน 2026-07-01 ที่ยังไม่มี `entry_bar_ts`) / `ERROR` / `NO_DATA`

**ผลลัพธ์ไฟล์:** `strategy/demo_portfolio/excel/signal_consistency_check.csv`

---

## 4. รันกับบัญชีจริง (`--env real`)

**ไม่มี credential บัญชีจริง hardcode ไว้ในโค้ดเลย** — ต้องตั้ง environment variable เองทุกครั้งก่อนรัน:

```bash
# Windows PowerShell
$env:MT5_LOGIN_REAL = "your_login"
$env:MT5_PASSWORD_REAL = "your_password"
$env:MT5_SERVER_REAL = "your_server"

# Linux/Mac/Git Bash
export MT5_LOGIN_REAL=your_login
export MT5_PASSWORD_REAL=your_password
export MT5_SERVER_REAL=your_server
```

ถ้าไม่ตั้งค่าแล้วรัน `--env real` จะ error ทันทีพร้อมบอกวิธีตั้งค่า ไม่มี fallback ไปบัญชีอื่นแบบเงียบๆ

---

## Quick Reference (สรุปสั้น — รันจาก project root ทั้งหมด)

| ต้องการ | คำสั่ง |
|---|---|
| ดูกำไรจริงตอนนี้ | `python strategy/demo_portfolio/backtest-sim/export_demo_portfolio_compare.py all` |
| ดูกำไรจริง 7 วันล่าสุด | `python strategy/demo_portfolio/backtest-sim/export_demo_portfolio_compare.py all --days 7` |
| เช็คว่า logic ยังตรงกับ backtest ไหม | `python strategy/demo_portfolio/backtest-sim/verify_signal_consistency.py all --days 7` |
| ดูตัวเลข backtest อ้างอิง | `python strategy/demo_portfolio/backtest-sim/backtest_demo_portfolio.py all` |
| รันจำลองประวัติและสร้างรายงานทั้งหมด (19 พอร์ต) | `python strategy/demo_portfolio/backtest-sim/run_backtest_sim.py --portfolio all` |
| เตรียมย้ายไป real account | ตั้ง env var 3 ตัว (ข้อ 4) แล้วเติม `--env real` |
