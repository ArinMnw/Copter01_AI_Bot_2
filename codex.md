# CODEX.md

เอกสาร context หลักสำหรับ Codex ใน repository นี้

## เป้าหมายของเอกสารนี้

- ช่วยให้เปิดไฟล์ถูกจุดโดยไม่ต้องไล่อ่านทั้ง repo
- เตือนกติกาสำคัญที่ไม่ควรทำพังซ้ำ
- ช่วยให้ลงมือแก้ได้เร็วและแม่นขึ้น

## วิธีเริ่มงาน

กติกาหลัก:

- อ่านไฟล์นี้ก่อนถ้างานยังไม่ชัด
- อย่าไล่ scan ทั้ง repo ถ้ายังไม่จำเป็น
- เปิดเฉพาะไฟล์ที่เกี่ยวกับงานนั้นจริง ๆ
- ถ้าโจทย์ชัดและไม่เสี่ยง ให้ลงมือแก้เลย
- ถ้าเป็น flow หลัง fill ให้เช็กผลกระทบต่อ state, trailing, cancel, notify เสมอ

prompt แนะนำ:

```txt
Read CODEX.md first.
Do not scan the whole repo.
Open only the files needed for this task.
Keep the answer short and make the fix directly.
```

## ภาพรวมโปรเจกต์

- โปรเจกต์นี้คือ MT5 automated trading bot ควบคุมผ่าน Telegram
- รันเป็น long-lived async Python process
- หน้าที่หลักคือ scan pattern หลาย timeframe, ตั้ง order และจัดการ position
- คู่หลักคือ `XAUUSD.iux` และ `BTCUSD.iux`

## วิธีรัน

```bash
python main.py
```

บน Windows:

```bash
run.bat
```

## แผนที่ไฟล์แบบเร็ว

| งานที่ต้องทำ | เปิดไฟล์ก่อน |
|---|---|
| startup, scheduler, loop | `main.py` |
| config, symbol, strategy toggle | `config.py` |
| scan signal, create order, order message | `scanner.py` |
| trailing, state machine, post-fill lifecycle | `trailing.py` |
| logic ของแต่ละท่า | `strategy1.py` ถึง `strategy5.py`, `strategy8.py`, `strategy9.py`, `strategy10.py`, `strategy11.py` |
| swing helper | `strategy4.py` |
| คำนวณ entry / TP / SL | `entry_calculator.py` |
| utility ฝั่ง MT5 | `mt5_utils.py` |
| Telegram notify และ close detection | `notifications.py` |
| เมนู Telegram | `handlers/keyboard.py`, `handlers/callback_handler.py` |

## ไฟล์แกนหลัก

- `main.py`: entry point และ scheduler jobs
- `config.py`: config หลัก, symbol settings, strategy flags และ helper สำหรับ persist state
- `scanner.py`: scan pattern, สร้าง order และส่งข้อความ order
- `trailing.py`: lifecycle หลัง fill, trailing SL, entry quality, S6, S6i
- `strategy1.py` - `strategy5.py`, `strategy8.py`, `strategy9.py`, `strategy10.py`, `strategy11.py`: logic ของแต่ละท่า
- `strategy4.py`: helper หา swing ที่หลายจุดเรียกใช้ร่วมกัน
- `entry_calculator.py`: logic กลางสำหรับ entry / TP / SL
- `mt5_utils.py`: utility ติดต่อ MT5
- `notifications.py`: ข้อความแจ้งเตือน Telegram และ close detection

## Config ที่ควรรู้

ดูใน `config.py` เป็นหลัก:

- `SYMBOL_CONFIG`
- `TF_LOOKBACK`
- `FVG_NORMAL`, `FVG_PARALLEL`
- `FVG_PARALLEL_GROUPS`
- `TRAIL_GROUPS`
- `active_strategies`
- `ENTRY_CANDLE_MODE`
- `LIMIT_GUARD`
- `LIMIT_SWEEP`

หมายเหตุ:

- `6` = S6
- `7` = S6i

## Scheduler โดยย่อ

ดูใน `main.py`

- symbol switch: ทุก 1 นาที
- pattern scan: ทุก 5 วินาที
- trailing และ position checks: ทุก 5 วินาที
- save state: ทุก 15 วินาที

## Shared State

state สำคัญส่วนใหญ่อยู่ใน `trailing.py`:

- `fvg_order_tickets`
- `pending_order_tf`
- `position_tf`
- `position_sid`
- `position_pattern`
- `_trail_state`
- `_entry_state`
- `_s6_state`
- `_s6i_state`
- `_bar_count`

state ที่เกี่ยวข้องใน `config.py`:

- `fvg_pending`
- `pb_pending`
- `last_traded_per_tf`
- `tracked_positions`

ข้อควรระวัง:

- หลัง limit fill ต้องเช็กการส่งต่อ metadata จาก pending order ไปยัง position
- เวลาตามบั๊ก lifecycle ให้ไล่ `pending_order_tf -> position_tf -> position_sid`

## สรุปแต่ละท่า

### ท่าที่ 1

- logic แบบกลืนกิน / ตำหนิ / ย้อนโครงสร้าง
- ใช้ pattern code เช่น `PA`, `PB`, `PC`, `PD`, `PE`, `P4`

### ท่าที่ 2

- FVG
- รองรับโหมดปกติและ parallel

### ท่าที่ 3

- DM / SP / Marubozu

### ท่าที่ 4

- นัยยะสำคัญ FVG
- ใช้ swing helper อย่างหนัก

### ท่าที่ 5

- ปิดไว้เป็นหลัก

### ท่าที่ 6 / 6i

- ไม่ใช่ท่าเข้า order แบบปกติ
- เป็น flow หลังบ้านสำหรับจัดการ position และ swing logic

### ท่าที่ 8

- กินไส้ Swing
- มี logic พิเศษเรื่อง limit, sweep และ arm SL

### ท่าที่ 9

- RSI Divergence (Regular + Hidden)
- ใช้ pivot RSI แบบเดียวกับ `RSIDivergencePane.mq5`
- entry = `LIMIT @ midpoint` ของแท่ง pivot ปัจจุบัน

### ท่าที่ 10

- CRT TBS — Candle Range Theory + Three Bar Sweep
- bypass trend filter (`if sid != 10:`)
- HTF filters: parent range, sweep depth ≥ 10%, sweep close < 50% ของ parent
- สอง mode:
  - `htf` (Entry Model 2): market entry ทันที่ HTF sweep ปิด — M15+ เท่านั้น
  - `mtf` (Entry Model 3, CRT TBS Classic): Phase 1 failed-push + Phase 2 engulf + 3 Models (OB/FVG/MSS) → LIMIT entry
- MTF Models: Model 1 OB (recommended) → fallback Model 2 FVG 90% → Model 3 MSS (log only)
- `_armed_states` persist ลง `bot_state.json` (key `s10_armed_states`)
- Comment: HTF = `Bot_<TF>_S10_CRT`, MTF = `Bot_[<HTF>-<LTF>]_S10_CRT`

### ท่าที่ 11

- Fibo S1 — ตี Fibo บน anchor ของ S1 pattern
- รอ wick แตะ trigger level → LIMIT
- 6 ระดับหลัก: KRH1/KRH2/KRH3 (trigger), 50%/KRH1 (entry), 7.044 (TP), -0.31 (SL)
- ไม่ persist phase — รอ S1 fire ใหม่หลัง restart

## จุดเริ่มเวลาตามบั๊ก

- เข้า order ผิด: `scanner.py`, `strategy*.py`, `entry_calculator.py`
- TP/SL แปลก: `entry_calculator.py`, `trailing.py`, `tp_sl/*`
- fill แล้ว state เพี้ยน: `trailing.py`
- pending order ไม่ยกเลิก: `trailing.py`
- Telegram แจ้งซ้ำหรือไม่แจ้ง: `notifications.py`, `config.py`
- timeframe mapping เพี้ยน: `trailing.py`, `config.py`, `mt5_utils.py`

## เอกสารเสริม

- `CLAUDE.md`
- `docs/strategies.md`
- `docs/trailing.md`
- `docs/runtime-state.md`
- `docs/telegram-ui.md`
- `docs/logging.md`
