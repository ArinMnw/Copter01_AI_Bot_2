# AGENTS.md

เอกสารสรุปกติกาหลักสำหรับทำงานใน repository นี้

## เป้าหมายของเอกสารนี้

- ใช้เป็นไฟล์หลักสำหรับ context การทำงานใน repo นี้
- ช่วยให้เปิดไฟล์ถูกจุดโดยไม่ต้องไล่อ่านทั้ง repo
- เตือนกติกาสำคัญและ behavior ที่พังซ้ำได้ง่าย
- ถ้าข้อมูลใน `CLAUDE.md` หรือ `codex.md` ซ้ำกับไฟล์นี้ ให้ยึด `AGENTS.md` เป็นหลัก

## Persona

- ผู้ช่วยใน repo นี้คือ "อลิซ"
- ให้พูดกับผู้ใช้แบบผู้หญิง
- ให้เรียกผู้ใช้ว่า "พี่"
- โทนการคุยควรสุภาพ กระชับ และร่วมมือกันทำงาน

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

## วิธีเริ่มงาน

- ถ้างานยังไม่ชัด ให้เปิด `AGENTS.md` ก่อน
- อย่าไล่ scan ทั้ง repo ถ้ายังไม่จำเป็น
- เปิดเฉพาะไฟล์ที่เกี่ยวกับงานนั้นจริง ๆ
- ถ้าโจทย์ชัดและไม่เสี่ยง ให้ลงมือแก้เลย
- ถ้าเป็น flow หลัง fill ให้เช็กผลกระทบต่อ state, trailing, cancel และ notify เสมอ

prompt แนะนำ:

```txt
Read AGENTS.md first.
Do not scan the whole repo.
Open only the files needed for this task.
Keep the answer short and make the fix directly.
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

## แผนที่ไฟล์แบบเร็ว

| งานที่ต้องทำ | เปิดไฟล์ก่อน |
|---|---|
| startup, scheduler, loop | `main.py` |
| config, symbol, strategy toggle | `config.py` |
| scan signal, create order, order message | `scanner.py` |
| trailing, state machine, post-fill lifecycle | `trailing.py` |
| logic ของแต่ละท่า | `strategy1.py` ถึง `strategy5.py`, `strategy8.py`, `strategy9.py`, `strategy10.py`, `strategy11.py`, `strategy12.py`, `strategy13.py` |
| swing helper | `strategy4.py` |
| HHLL swing structure, trend from structure | `hhll_swing.py` |
| คำนวณ entry / TP / SL | `entry_calculator.py` |
| utility ฝั่ง MT5 | `mt5_utils.py` |
| Telegram notify และ close detection | `notifications.py` |
| เมนู Telegram | `handlers/keyboard.py`, `handlers/callback_handler.py` |
| MT5 indicator HHLL labels | `mql5/HHLLStrategy.mq5` |
| MT5 indicator Premium/Discount zone | `mql5/PremiumDiscount.mq5` |

## เอกสารแยก

- `CLAUDE.md`
- `codex.md`
- `docs/strategies.md`
- `docs/trailing.md`
- `docs/runtime-state.md`
- `docs/telegram-ui.md`
- `docs/logging.md`

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
- `PD_ZONE_CHECK_ENABLED` (default `True`) — gate สำหรับ PD Zone Recheck ใน `trailing.py`, persist ใน `bot_state.json` key `pd_zone_check_enabled`

หมายเหตุ:

- `6` = S6
- `7` = S6i

## Scheduler โดยย่อ

ดูใน `main.py`

- symbol switch: ทุก 1 นาที
- pattern scan: ทุก 5 วินาที
- trailing และ position checks: ทุก 5 วินาที
- save state: ทุก 15 วินาที

## Runtime State

state หลักอยู่ใน `trailing.py` และ `config.py`

ตัวแปรสำคัญ:

- `fvg_order_tickets`
- `pending_order_tf`
- `position_tf`
- `position_sid`
- `position_pattern`
- `position_zone_meta`
- `_trail_state`
- `_bar_count`
- `_entry_state`
- `_s6_state`
- `_s6i_state`

state ที่เกี่ยวข้องใน `config.py`:

- `fvg_pending`
- `pb_pending`
- `last_traded_per_tf`
- `tracked_positions`

state เพิ่มเติมใน `trailing.py`:

- `_pd_zone_state: dict` — per-ticket state ของ PD Zone Recheck (round, results, tf, signal)
- `_triple_check_state: dict` — per-ticket state ของ Triple Recheck เก็บ `{rsi, trend, pd, tf, signal}` แต่ละตัวเป็น `None|True|False`

ข้อควรระวัง:

- หลัง limit fill ต้องเช็กการส่งต่อ metadata จาก pending order ไปยัง position
- เวลาตามบั๊ก lifecycle ให้ไล่ `pending_order_tf -> position_tf -> position_sid`

state ถาวรถูกบันทึกลง `bot_state.json`

## รูปแบบ Comment ของ Order

ใช้รูปแบบประมาณนี้:

```text
{TF}_S{SID}_{PATTERN_CODE}
```

ตัวอย่าง:

- `M1_S1_PA`
- `[M5_M15]_S2`
- `[H1-M1]_S10_#1`
- `M15_S13_EZ_#1`

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
- `ENTRY_CANDLE_ENABLED` เป็น master toggle - ถ้า `False` `check_entry_candle_quality()` จะ return ทันที
- default ปัจจุบันคือ `ENTRY_CANDLE_ENABLED = False`

## Limit Fill Notify

- ฟังก์ชัน: `check_limit_fill_notify(app)` ใน `trailing.py`
- **อิสระจาก `ENTRY_CANDLE_ENABLED`** — ทำงานทุกครั้งเมื่อมี position fill ใหม่
- รันใน `main.py` `run_position_check` **ก่อนสุด** (ก่อน RSI recheck และ entry candle)
- ใช้ set `_fill_notified` กันแจ้งซ้ำ
- First-run guard: positions ที่อายุเกิน `_FILL_INIT_SUPPRESS_SEC` (180s) จะถูก mark notified ตอน restart (กัน re-notify)
- Skip: `sid=12, 13` (มี flow notification ของตัวเอง)
- ส่ง Telegram 2 ข้อความ: "Limit Fill" + "Trend At Fill"
- log event: `ENTRY_FILL`

## RSI Fill Recheck

- ฟังก์ชัน: `check_fill_rsi_recheck(app)` ใน `trailing.py`
- **อิสระจาก `ENTRY_CANDLE_ENABLED`** — gate ด้วย `PENDING_RSI_RECHECK_ENABLED` เท่านั้น
- รันใน `main.py` `run_position_check` **ก่อน** `check_entry_candle_quality` (ถ้า fail จะปิด position ทันที)
- ครอบคลุม **ทุก sid** (รวม S12, S13 — เปิดตั้งแต่ 2026-05-18)
- **Triple mode**: ถ้าเปิดครบทั้ง 3 (`PD_ZONE_CHECK_ENABLED AND LIMIT_TREND_RECHECK AND PENDING_RSI_RECHECK_ENABLED`) จะไม่ปิด position ทันที แต่ record ผลใน `_triple_check_state[ticket]["rsi"]` แล้ว evaluate 2/3 ก่อนตัดสิน

## Limit Trend Recheck

- อยู่ใน `check_cancel_pending_orders` (trailing.py)
- เช็ค trend ก่อน fill เมื่อราคาใกล้ entry (`LIMIT_TREND_RECHECK_POINTS` = 300pt)
- ถ้า trend ไม่ allow → cancel pending
- **Skip**: S1 (zone-based), S9 (RSI div), S10 (CRT-managed), S11 (Fibo)
- **Apply**: S2, S3, S4, S5, S6, S8, **S12, S13** (เปิดตั้งแต่ 2026-05-18)
- กฎ:
  - BUY  → ต้อง `RSI < PENDING_RSI_BUY_MAX` (default `50.0`) ไม่งั้นปิด
  - SELL → ต้อง `RSI > PENDING_RSI_SELL_MIN` (default `50.0`) ไม่งั้นปิด
- ใช้ `_pending_rsi_rule_result(side, tf)` คำนวณ RSI ของ TF ที่ position เปิด
- เก็บใน set `_fill_rsi_checked` กันไม่ให้เช็คซ้ำต่อ ticket
- skip: `sid=13` (S13 มี TP/SL คนละแบบ)
- log events: `ENTRY_FILL_RSI_RECHECK_FAIL`, `ENTRY_FILL_RSI_RECHECK_SKIP` (กรณี RSI unavailable)
- **Triple mode**: ถ้าเปิดครบทั้ง 3 จะไม่ cancel pending ทันที แต่ record ผลใน `_triple_check_state[ticket]["trend"]` แล้ว evaluate 2/3 ก่อนตัดสิน

## PD Zone Recheck

- ฟังก์ชัน: `_pd_zone_process(ticket, app)` ใน `trailing.py`
- gate: `config.PD_ZONE_CHECK_ENABLED` (default `True`)
- Return `(status: str, tg_msgs: list)` — status เป็น `"pass"` / `"fail"` / `"wait"`
- state: `_pd_zone_state: dict` (module-level ใน `trailing.py`)

**Logic การเช็ค 3 รอบ 2/3 ชั้นใน:**

- H = swing high ล่าสุด (HH/LH) จาก `hhll_swing.get_swing_hl_pts(tf)`
- L = swing low ล่าสุด (HL/LL) จาก `hhll_swing.get_swing_hl_pts(tf)`
- EQ = (H + L) / 2
- รอบ 1: เมื่อ order เกิด → เช็ค entry vs EQ ณ ขณะนั้น
- รอบ 2: H หรือ L เปลี่ยนครั้งแรก → เช็ค EQ ใหม่
- รอบ 3: H หรือ L เปลี่ยนครั้งที่สอง (หลังรอบ 2) → เช็ค EQ ใหม่

**กฎ pass/fail:**

- `entry < EQ` → BUY ผ่าน (Discount zone) / SELL ล้มเหลว
- `entry > EQ` → SELL ผ่าน (Premium zone) / BUY ล้มเหลว
- pass ≥ 2 → `"pass"` / fail ≥ 2 → `"fail"` / ยังไม่ครบ → `"wait"`

**Telegram:** ส่งทุกรอบบอกว่าอยู่ Premium/Discount zone + pass/fail

**Zone:**
- Premium (entry > EQ) → SELL ✅ BUY ❌
- Discount (entry < EQ) → BUY ✅ SELL ❌

**Triple mode:** เมื่อเปิดครบทั้ง 3 และได้ผล "pass"/"fail" จะ record ใน `_triple_check_state[ticket]["pd"]` แล้ว evaluate 2/3 ก่อนตัดสิน

## Triple Recheck (Combined 2/3)

- เปิดทำงานเมื่อ: `PD_ZONE_CHECK_ENABLED AND LIMIT_TREND_RECHECK AND PENDING_RSI_RECHECK_ENABLED` ทั้งสามพร้อมกัน
- helper: `_triple_check_all_enabled() -> bool`
- state: `_triple_check_state: dict` = `{ticket: {rsi: None|True|False, trend: None|True|False, pd: None|True|False, tf, signal}}`
- helper: `_triple_check_record(ticket, key, result, tf, signal)`
- helper: `_triple_check_evaluate(ticket) -> "cancel"|"keep"|"wait"`

**ตัดสิน:**
- fails ≥ 2 → `"cancel"` → cancel pending หรือ close position ทันที
- passes ≥ 2 → `"keep"` → คง order ไว้, clear state
- อื่น → `"wait"` → รอข้อมูลเพิ่ม

**Telegram:** เมื่อตัดสินแล้วส่งสรุป `RSI ✅/❌ | Trend ✅/❌ | PD ✅/❌`

**log events:** `TRIPLE_RECHECK` + `CANCEL` หรือ `KEEP`

**พฤติกรรมเมื่อปิดบางตัว (individual mode):**
- แต่ละตัวทำงานอิสระเหมือนเดิม ไม่รอ 2/3

## พฤติกรรมสำคัญของระบบ

### Trail SL

- logic หลักอยู่ใน `trailing.py`
- `TRAIL_SL_ENGULF_MODE` รองรับ `combined` และ `separate`
- `TRAIL_SL_IMMEDIATE` คุมว่าจะ trail ได้ก่อน `_entry_state = done` หรือไม่
- `TRAIL_SL_ENABLED` เป็น master toggle - ถ้า `False` `check_engulf_trail_sl()` จะ return ทันที
- `TRAIL_SL_REVERSAL_OVERRIDE_ENABLED` เป็น top-level toggle แยกจาก submenu อื่น
- ถ้าเปิดอยู่ ระบบจะยอมให้ trail ผ่าน `Focus Opposite` ได้เมื่อแท่งล่าสุดบน TF ของ order เป็น reversal ฝั่งตรงข้าม
- feature นี้ไม่ใช้กับท่า standalone (`S12`, `S13`) และ `S10`

### Limit Guard

- ใช้ยกเลิก pending limit ที่ไกลจาก position ปัจจุบันมากเกินไป
- มีทั้ง mode `separate` และ `combined`
- ปัจจุบัน skip สำหรับ `S10`, `S12`, `S13`

### Limit Sweep

- ใช้ปิด position และจัดการ pending order ต่อ เมื่อแท่ง adverse ปิดทะลุโครงสร้างสำคัญ
- S8 follow-up ต้องเลือก `LL/HH` ที่ยัง valid ไม่ใช่ level ที่แท่งปิดทะลุไปแล้ว

### S8

- S8 ตั้ง limit ก่อน
- SL อาจถูก arm ทีหลังตาม flow ปัจจุบัน
- ถ้า S8 fill ก่อน arm SL ต้องมี fallback ไปตั้ง SL ให้ position ที่ fill แล้ว
- ปุ่ม `strategy_all_on` (เลือกทั้งหมด) ไม่เปิด S8 - ต้องกดเปิดรายตัวเอง

### S2 FVG

- FVG ตรวจทั้ง engulf และ gap distance
- ขั้นต่ำของ gap ใช้ค่าเดียวกับ engulf (`engulf_min_price()`) ไม่ใช่ค่า hardcoded
- `S2` แบบปกติเท่านั้นที่จะย้อนดู `S1` / `S2` / `S3` ฝั่งเดียวกันใน `S2_NORMAL_CONFIRM_LOOKBACK_BARS` แท่งล่าสุดก่อนยอมใช้ order
- `S2 parallel` ไม่ใช้กฎยืนยันย้อนหลังนี้
- pattern ที่เปิดใช้งาน: `เขียวกลืนกิน`/`แดงกลืนกิน` และ `ปฏิเสธราคา`
- pattern `ปฏิเสธราคา` รับได้ทั้งแท่งปิดเขียวและแดง (ไม่มีเงื่อนไขสี)
- pattern default `แดง`/`เขียว` (pattern 3-4) ปิดใช้งาน แต่ยังคง classification logic ไว้เพื่อ log
- pattern `ปฏิเสธราคา` ใช้ `cancel_bars = 1` - ถ้า limit ไม่ fill ภายใน 1 แท่งถัดไปจะยกเลิกอัตโนมัติ (ใช้กลไกเดิมใน `trailing.py`)
- `Limit TP/SL Break Cancel` ไม่ใช้กับ pattern 1 (`เขียวกลืนกิน`/`แดงกลืนกิน`) - skip ผ่าน `c3_type` ใน `pending_order_tf`
- comment ของ `S2 parallel` แบบปัจจุบันคือ `[TF1_TF2]_S2`

### S1 Zone Mode

- ถ้า `S1_ZONE_MODE = "zone"` ระบบจะไม่ block setup ตั้งแต่ขั้น detect แล้ว
- จะเก็บ `s1_zone_meta` ติดไปกับ pending/position แล้วค่อยประเมินภายหลัง
- pending ที่อยู่นอก zone -> ยกเลิก limit
- pending ที่ยังอยู่ใน zone -> คง order ไว้
- position ที่อยู่นอก zone และขาดทุน -> ปิด
- position ที่อยู่นอก zone แต่กำไรหรือเสมอทุน -> ไม่ปิด
- การเช็ก zone ใช้ `min low` / `max high` ของทุกแท่งใน pattern ไม่ได้อิงแค่แท่ง `[1]`
- แยกจาก zone mode, `S1` ยังมี forward confirm rule อีกชุด:
  - ตั้ง order ไปก่อนได้
  - จากนั้นรอดู `S2` หรือ `S3` ฝั่งเดียวกันภายใน 5 แท่งข้างหน้าใน TF เดียวกัน
  - ถ้ายังเป็น pending และครบ 5 แท่งแล้วไม่เจอ -> ยกเลิก order
  - ถ้า fill แล้วและครบ 5 แท่งแล้วไม่เจอ -> ปิด position
  - ถ้าเจอแล้ว ไม่ว่าจะยัง pending หรือ fill แล้ว -> ไม่ทำอะไรต่อ

### Opposite Order Mode

รองรับ 2 แบบ:

- `tp_close`
- `sl_protect`

- `OPPOSITE_ORDER_ENABLED` เป็น master toggle - ถ้า `False` `check_opposite_order_tp()` จะ return ทันที

### SL Protect

- ไม่ควรยิงซ้ำรัวสำหรับ ticket เดิม
- ข้อความ Telegram ฝั่ง protect/trail ควรถูก dedup

### S9 RSI Divergence

- ใช้ pivot RSI ตรงกับ `RSIDivergencePane.mq5` (immediate previous pivot only)
- 4 type: Regular Bullish/Bearish (default ON), Hidden Bullish/Bearish (default OFF)
- Telegram รวมเป็น 2 ปุ่ม: Regular / Hidden
- entry = `LIMIT @ midpoint` ของแท่ง pivot ปัจจุบัน
- setup_sig ใช้แค่ pivot identity เพื่อกัน duplicate
- ค่า config ที่ต้อง sync กับ MQL5: `RSI9_PERIOD`, `RSI9_LEFT`, `RSI9_RIGHT`, `RSI9_RANGE_MIN`, `RSI9_RANGE_MAX`

### S10 CRT TBS

- bypass trend filter (`if sid != 10:` ใน scanner.py)
- ปุ่ม `strategy_all_on` ไม่กระทบ S10 (ต้องเปิด/ปิดรายตัว) - default ON
- `CRT_BAR_MODE` = `2bar` (default - TBS compressed) / `3bar` (TBS classic)
- `CRT_ENTRY_MODE` = `mtf` (default) / `htf`

**HTF detect filters (ทุก mode):**
- Parent range ≥ `CRT_MIN_RANGE_POINTS × points_scale`
- Sweep depth ≥ `CRT_SWEEP_DEPTH_PCT × parent range` (default 10%)
- sweep candle ไม่บังคับสีแล้ว: BUY/SELL ใช้ได้ทั้งแท่งเขียวหรือแดง ถ้าโครงสร้าง sweep ผ่าน

**HTF mode (Entry Model 2):**
- ใช้ M15+ เท่านั้น
- Market BUY/SELL ทันที่ HTF sweep ปิดยืนยัน

**MTF mode — Continuous re-trigger flow (ใหม่):**

- Trigger ต้องเจอ **ทั้ง Model 1 AND Model 2** (ไม่ใช่ OR เหมือนเดิม) ก่อน fire
- เมื่อเจอครบ → fire **2 orders** (entry Model 1 + entry Model 2)
- หลัง fire — `register_fired_tickets()` บันทึก ticket ลง `arm_state["fired_tickets"]`
- `arm_state` **ไม่ถูก consume** หลัง fire — เก็บไว้สำหรับ re-trigger
- ถ้ามี `fired_tickets` ใน arm → ไม่ search Model ใหม่ (รอ position ปิดก่อน)
- เมื่อ ticket ปิด (TP/SL) → `handle_ticket_closed()` ลบจาก list
  - **TP hit** → consume arm (success cleanup)
  - **SL hit ทั้งคู่** → reset ready for next search
    - ถ้า `pre_arm=True` → set `awaiting_choch=True` (รอ CHoCH ก่อนค่อยหา Model ใหม่)
    - ถ้า `pre_arm=False` (normal arm) → ค้น Model 1+2 ใหม่ได้ทันที
- ถ้า `awaiting_choch=True`:
  - ค้น Model 3 (MSS) — ถ้าไม่เจอ → wait
  - ถ้าเจอ Model 3 — Model 1, 2 ใหม่ต้องอยู่**ก่อนแท่ง CHoCH** ถึงจะ valid

**MTF mode (Entry Model 3 - CRT TBS Classic):**
- LTF mapping: D1/H12→M15, H4→M5, H1/M30/M15→M1
- Phase 1: failed-push (BUY=RED+close<parent.low / SELL=GREEN+close>parent.high)
- Phase 2: body engulf 2-bar (concept S1 - ไม่เรียก S1 จริง)
- Models (คำนวณหลัง engulfing):
  - #1 Order Block - ค้นต่อหลังแท่ง Phase 1 → entry = OB.open (LIMIT)
  - #2 FVG 90% - ค้นต่อหลังแท่ง Phase 1 ด้วย 3-bar imbalance → entry @ 90% deep (concept S2 - ไม่เรียก S2 จริง) และ gap ต้อง >= `engulf_min_price()`
  - #3 MSS - swing low/high แบบ lookback ย้อนจากแท่ง Phase 1 (log only, ไม่ใช้เป็น entry)
- Priority: Model 1 → fallback Model 2 → ถ้าทั้งคู่ None ไม่เข้า
- `order_mode = "limit"` (เปลี่ยนจาก market - รอ price retrace)
- SL = HTF sweep level ± buffer (`state["sl_target"]`)
- TP = HTF parent opposite (`state["tp_target"]`)
- Search range ของ Model 1/2: หลังแท่ง `Phase 1`
- Search range ของ Model 3: `armed_at < bar.time < phase1.time`

**State:**
- `_armed_states` save/restore ผ่าน `bot_state.json` (key `s10_armed_states`)
- `armed_at` = HTF sweep candle's open time
- expiry = `armed_at + 2 × htf_secs`
- pending MTF ถูกยกเลิกทันทีถ้าก่อน fill ราคาไปแตะ HTF parent low/high ฝั่งตรงข้ามของ setup แล้ว

**Re-arm guard (กัน duplicate orders ใน HTF bar เดียวกัน):**

- `_last_fired_armed_at[htf_tf]` เก็บ **HTF bar window start (unix)** ของ bar ที่ fire ไปแล้ว
- helper `_current_htf_bar_start(htf_tf)` = `(now // htf_secs) * htf_secs`
- main scan และ pre-arm ใช้ค่าเดียวกัน → guard ครอบทั้ง 2 paths
- ก่อนหน้านี้เคยเกิด bug: main scan ตั้ง `_last_fired = last_closed_bar_time`, pre-arm ตั้ง = `in-progress_bar_time` → 2 paths ไม่กัน → duplicate orders

**Min SL Distance Guard:**

- helper `_sl_distance_ok(direction, entry, sl)` เช็คก่อน return result
- ใช้ `mt5.symbol_info(SYMBOL).trade_stops_level + 20pt buffer` (fallback 30pt × `points_scale`)
- ป้องกัน broker reject pending order ที่ SL ชิด entry เกินไป
- ใช้ใน: `_check_ltf_trigger` (MTF mode), `_strategy_10_2bar`/`_strategy_10_3bar` (HTF mode)
- ถ้าไม่ผ่าน — return None/`WAIT` พร้อม log `S10_TRIGGER_SKIP_MIN_SL`

**Comment format:**
- HTF mode: `<TF>_S10`
- MTF mode: `[<HTF>-<LTF>]_S10_#<model>`

### S11 Fibo S1

- Hook ติด S1 - เมื่อ S1 fire จะ record anchor (แท่งสีตรงกับ direction ตัวล่าสุด)
- 3 trigger levels: KRH1 (1.617) / KRH2 (3.097) / KRH3 (5.165)
- entry LIMIT, TP=7.044, SL=-0.31, Recovery=-0.95 (phase 2 ยังไม่ implement)
- `_s11_state` ไม่ persist - restart แล้วต้องรอ S1 fire ใหม่
- comment ใช้ pattern code: `KRH1_50` / `KRH2_50` / `KRH3_KRH1` / fallback `FIBO`
- default `active_strategies[11] = False`

### S12 Range Trading

- ระบุ range ด้วย pivot swing บน M5 เป็นหลัก และ fallback raw high/low ถ้ายังไม่มี pivot
- active zone ใช้ raw breakout extremes แบบ sticky เพื่อให้ขยับตาม `S12_RangeZone.mq5` และไม่ snap กลับทันที
- ตั้ง limit order หลายชั้น (จำนวนสูงสุด = `S12_ORDER_COUNT`)
- ปุ่ม `strategy_all_on` ไม่กระทบ S12 - default ON ต้องปิด/เปิดรายตัวเอง
- cooldown 1800s หลัง SL hit (`S12_COOLDOWN_SECS`)
- **SCAN_SUMMARY**: ระหว่าง cooldown จะ **ไม่แสดง** S12 block เลย (ป้องกัน body ค้างจากค่า 0.00 → ทำให้ force-log ทำงานได้ตามปกติ)
- comment โดยรวมยังอิง `M5_S12_...` จาก `mt5_utils.py`

### S13 EzAlgo V5

- strategy ใหม่แบบ standalone
- ใช้สัญญาณ `supertrend crossover`
- ใช้ได้ทุก TF ที่เปิด scan
- ไม่เข้า flow กลางพวก `Entry Candle`, `Trail SL`, `Opposite Order`, `RSI recheck`, `Trend Filter` ของระบบหลัก
- เจอสัญญาณแล้วจะเลือก mix ของ `market/limit` จากความสัมพันธ์ระหว่าง `current price` กับ `entry`
- BUY:
  - ถ้า `current price > entry` -> เปิด `market 1 order` ที่ `TP3` (`#3`) และตั้ง `limit 3 orders` (`L1/L2/L3`)
  - ถ้า `current price <= entry` -> เปิด `market 3 orders` (`#1/#2/#3`) และตั้ง `limit 1 order` ที่ `TP3` (`L3`)
- SELL:
  - ถ้า `current price < entry` -> เปิด `market 1 order` ที่ `TP3` (`#3`) และตั้ง `limit 3 orders` (`L1/L2/L3`)
  - ถ้า `current price >= entry` -> เปิด `market 3 orders` (`#1/#2/#3`) และตั้ง `limit 1 order` ที่ `TP3` (`L3`)
- ถ้าเจอสัญญาณฝั่งตรงข้าม จะล้าง exposure ของ `S13` เฉพาะ TF เดียวกันก่อนเปิดฝั่งใหม่
- comment:
  - market: `<TF>_S13_EZ_#1`, `<TF>_S13_EZ_#2`, `<TF>_S13_EZ_#3`
  - limit: `<TF>_S13_EZ_L1`, `<TF>_S13_EZ_L2`, `<TF>_S13_EZ_L3`

### BTC Lot / Points Scaling

- `points_scale()` คืน `4.0` สำหรับ BTCUSD ส่วน symbol อื่น = `1.0`
- ใช้กับ `get_volume()` และระยะ point ทุกจุด (engulf min, CRT min/buffer, trailing offsets)
- Telegram UI ยังเห็นค่า config base ของ XAUUSD - scaling ทำหลังบ้าน

### Triple Scale-Out (TSO) — `📈 Scale-Out 3X`

- master toggle: `SCALE_OUT_ENABLED` (default `True`) - ปุ่มอยู่บนหน้าเมนู `⚙️ ตั้งค่า` หลัก
- คอนเซปต์: ขยาย lot ของ pending/limit order ใหม่เป็น `×SCALE_OUT_MULTIPLIER` (default `3`) แล้วทยอยปิดเป็น 3 ขั้นเมื่อราคาผ่าน entry
- pulse close ครั้งละ `SCALE_OUT_TP_LOT × points_scale()` (XAU = 0.01, BTC = 0.04)
- ระยะ TP แต่ละขั้นมาจาก `SCALE_OUT_TP_POINTS = [300, 700, 1000]` (XAU point - BTC auto ×4 ผ่าน `points_scale`)

**Scope:**

- ใช้กับ pending/limit ที่สร้างผ่าน `open_order()` และ `open_order_stop()` เท่านั้น
- `open_order_market()` ไม่ scale (ตามสเปคปัจจุบัน)
- **`sid=13` (S13 EzAlgo V5)** ถูก **ยกเว้น**: ไม่ขยาย lot และไม่ทยอยปิด - ใช้ TSO ปรับ TP ของแต่ละ S13 order แทน (TP1=300pt, TP2=700pt, TP3=1000pt)

**Dynamic Effective Steps (ปัจจุบัน — ตั้งแต่ 2026-05-18):**

- คำนวณ TSO steps แบบ **dynamic** ตาม TP เดิมของ order
- helper: `config.compute_tso_effective_steps(tp_orig_dist)`
- Logic:
  - ถ้า `tp_orig < TP1` (= 300pt × scale) → ใช้ TP1 step เดียว (override TP)
  - filter `SCALE_OUT_TP_POINTS` ที่ `<= tp_orig`
  - append `tp_orig` เป็น step สุดท้าย (ถ้ายังไม่ match exact)
- ตัวอย่าง:
  - TP เดิม 100pt (< 300) → 1 step ที่ 300pt → lot 0.01
  - TP เดิม 300pt → 1 step → lot 0.01
  - TP เดิม 500pt → 2 steps (300, 500) → lot 0.02
  - TP เดิม 700pt (= TP2) → 2 steps (300, 700) → lot 0.02
  - TP เดิม 800pt → 3 steps (300, 700, 800) → lot 0.03
  - TP เดิม 1000pt (= TP3) → 3 steps (300, 700, 1000) → lot 0.03
  - TP เดิม 1200pt → 4 steps (300, 700, 1000, 1200) → lot 0.04
- **ทุกท่า** (S1-S12 + S10) ใช้ logic เดียวกัน — lot รวม = `len(effective_steps) × base_volume`
- **S13** ใช้เหมือนกันแต่ออกเป็น **orders แยก** (1-4 orders) แทน 1 order ที่ partial close

**State และ lifecycle:**

- state `scale_out_state` อยู่ใน `config.py` (key: `ticket`) - persist ใน `bot_state.json` (`scale_out_state`)
- watcher: `check_scale_out_partial(app)` ใน `trailing.py` ถูกเรียกจาก `run_position_check` ใน `main.py`
- ตอน register ticket จะเก็บ `direction`, `entry`, `base_volume`, `per_tp_volume`, `tp_distances`, `step`, `is_pending`
- เมื่อ pending fill กลายเป็น position - flag `is_pending` ถูก update ใน watcher และ entry refresh จาก `pos.price_open`

**Cleanup ตอน toggle OFF (`scale_out_cleanup_on_disable`):**

- position TSO ที่ fill แล้ว → ปิดทั้งหมด (`_close_position` ด้วย `pos.volume` ปัจจุบัน)
- pending TSO ที่ยังไม่ fill → cancel + สร้างใหม่ด้วย `base_volume` (lot เดิมก่อน scale)
- **S13 ไม่ถูกแตะ** (เพราะไม่ถูก register ใน `scale_out_state`)
- S10 ถูก register แล้ว → จะถูก cleanup ตามกฎทั่วไปเหมือนท่าอื่น
- callback แจ้ง summary `closed: N` / `reset_pending: M`

**ข้อควรระวัง:**

- การ scale ทำที่ `_scale_out_resolve_volume()` ใน `mt5_utils.py` - ต้องรับ `sid` ทุกครั้ง (skip ถ้า `sid == "13"`)
- `scale_out_state` ต้องเก็บ `sid` + `tp_original` (ใช้ตอน partial close)
- TP cap คำนวณจาก `pos.tp` (ค่าจริงปัจจุบัน) ในแต่ละรอบ scan — รองรับกรณี TP ถูก edit ภายหลัง
- ค่า return ของ `open_order()` เพิ่ม key `scale_out`, `scaled_volume` (additive - ไม่กระทบ caller เดิม)
- S13 TP override ทำใน `_place_s13_split_orders` (scanner.py) ก่อนเริ่มลูปสร้าง order - validate side ก่อนใช้ ถ้า invalid จะ fallback กลับใช้ RR เดิม
- Reset Config ไม่ trigger cleanup TSO state - order เดิมที่ลงทะเบียนไว้ยังทำงานต่อจนกว่าจะปิดเอง

### numpy rates check

- `rates` ที่ส่งให้ `strategy_*` เป็น numpy structured array
- `if not rates:` จะ throw `ValueError: ambiguous` - **ห้ามใช้**
- ใช้ `if rates is None or len(rates) == 0:` แทน

### hhll_swing.py — HHLL Swing Structure

- เก็บ swing structure data แบบ per-TF ใน `_hhll_data[tf]`
- `get_swing_hl_pts(tf)` → `(H, L)` คืน swing high/low ล่าสุด
  - H = ราคา swing high ล่าสุด (HH หรือ LH)
  - L = ราคา swing low ล่าสุด (HL หรือ LL)
- `get_trend_from_structure(tf_name)` → `{"trend": "BULL"/"BEAR"/"SIDEWAY"/"UNKNOWN", "strength": "strong"/"weak"/"-", "label": str}`
  - อ่าน `_hhll_data[tf]["structure"]` list (newest-first)
  - แยก H-labels (HH/LH) และ L-labels (HL/LL)
  - BULL strong: h0="HH", l0="HL", h1="HH", l1="HL"
  - BULL weak: h0="HH", l0="HL" (แต่ไม่ครบ 2 คู่)
  - BEAR strong: h0="LH", l0="LL", h1="LH", l1="LL"
  - BEAR weak: h0="LH", l0="LL" (แต่ไม่ครบ 2 คู่)
  - SIDEWAY: กรณีอื่น

### scanner.py — Trend filter sync กับ HHLLStrategy

- `fetch_hhll(tf_name)` รันก่อน `_compute_trend_info()` ทุกรอบ scan
- `_trend_info` ใช้ `hhll_swing.get_trend_from_structure(tf_name)` เป็นหลัก
- fallback: `_compute_trend_info(...)` เดิม ถ้า HHLL ไม่มีข้อมูล

### Export Trend State (สำหรับ MT5 indicator)

- ฟังก์ชัน: `_export_trend_state_for_mt5()` ใน `scanner.py`
- เขียนสถานะ trend ลงไฟล์ `<MT5 commondata>/Files/trend_state.txt` และ `trend_state_<SYMBOL>.txt`
- MQL5 indicator `TrendFilterLines.mq5` อ่านไฟล์เพื่อวาดเส้น trend บน chart
- รัน auto ทุก scan loop จาก `scanner.auto_scan`
- Error categorization (2026-05-18): `MT5_NOT_CONNECTED`, `NO_COMMONDATA_PATH`, `PERMISSION_DENIED_*`, `FILE_NOT_FOUND`, `OS_ERROR_*`, `ENCODING_ERROR`, `UNEXPECTED_ERROR`
- ทุก error log ลง `bot.log` ผ่าน `log_event("EXPORT_TREND_STATE_ERROR", ...)` พร้อม `err_type`, `err_message`, `detail`

### Markdown Safety (Telegram replies)

- helper `_md_escape(s)` ใน `handlers/text_handler.py` — escape `\`, `` ` ``, `*`, `_`, `[`, `]`
- `_safe_reply_md(message, text, **kwargs)` — ลอง Markdown ก่อน, fallback plain text ถ้า `BadRequest: can't parse entities`
- ใช้ใน `_handle_ticket_lookup` เพื่อกัน silent fail เมื่อ comment/pattern มีตัวอักษรพิเศษ
- ถ้าต้องเพิ่ม Telegram reply ใหม่ที่ใช้ dynamic content — ใช้ pattern นี้

## Telegram Toggle Icons

- ปุ่มและ status text ของฟังก์ชันที่เปิด/ปิดได้ใช้ icon: `🟢ON` = เปิด, `🔴OFF` = ปิด
- ถ้า OFF ไม่แสดง suffix รายละเอียด (ไม่มี `|` ตามหลัง)
- ฟังก์ชันที่มี master toggle และ submenu: Trail SL, Entry Candle Mode, Opposite Order
- ฟังก์ชันที่ toggle ตรงจากหน้าหลัก: Entry Candle TP, Limit Sweep, Delay SL (3 mode)
- มี top-level toggle แยก: `↩️ จุดกลับตัว -> Trail SL`

## Log และสรุปกำไร

- log หลักคือ `logs/bot.log` และ `logs/bot-YYYY-MM.log` (สำเนารายเดือน)
- `logs/error-YYYY-MM.log`: error + Python exception (จาก `log_error()` และ `_ErrorLogHandler`)
- `logs/system/system.log`: Python `logging` module (INFO+)
- `logs/debug/sltp_audit.log`: audit trail การเปลี่ยน SL/TP
- ไฟล์ใน `logs/`, `__pycache__/`, `*.tmp`, `*.bak` และไฟล์ compile เช่น `*.ex5` ไม่ควรถูก commit เข้า git
- `POSITION_CLOSED` ใช้เป็นฐานของสรุปกำไร
- เวลา Telegram มากับ log ไม่ตรงกัน ให้เชื่อ `bot.log` ก่อน

## SCAN_SUMMARY

- log ทุกครั้งที่ body เปลี่ยน (dedup ด้วย `tg_key`)
- **force-log ทุก 60 วินาที** แม้ body จะไม่เปลี่ยน (ทั้ง bot.log และ Telegram)
- ควบคุมด้วย `SCAN_SUMMARY_FORCE_INTERVAL = 60` ใน `scanner.py`
- S12 cooldown: ไม่แสดง S12 block ใน body ระหว่าง cooldown
- `Scan Swing` ใน summary มี `AsOf`, `H✓`, `L✓` เพื่อบอกเวลาแท่งปิดล่าสุดและเวลาที่ swing confirm แล้ว

## กติกาเวลาแก้ไฟล์

- แก้เฉพาะจุดเท่าที่จำเป็น
- ถ้าเป็นงาน text-only ห้ามเปลี่ยน trading logic
- อย่าเปลี่ยน callback name, config key หรือชื่อ state field โดยไม่แก้ให้ครบทั้งระบบ
- ถ้าแก้ text ใน handler Telegram ให้เช็ก `py_compile` หลังแก้
- ถ้าไม่แน่ใจว่า behavior หนึ่งเป็นของตั้งใจหรือไม่ ให้ดู code และ log ก่อนสรุป

## จุดเริ่มเวลาตามบั๊ก

- เข้า order ผิด: `scanner.py`, `strategy*.py`, `entry_calculator.py`
- TP/SL แปลก: `entry_calculator.py`, `trailing.py`, `tp_sl/*`
- fill แล้ว state เพี้ยน: `trailing.py`
- pending order ไม่ยกเลิก: `trailing.py`
- Telegram แจ้งซ้ำหรือไม่แจ้ง: `notifications.py`, `config.py`
- timeframe mapping เพี้ยน: `trailing.py`, `config.py`, `mt5_utils.py`

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
