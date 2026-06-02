# AGENTS.md

เอกสารสรุปกติกาหลักสำหรับทำงานใน repository นี้

## เป้าหมายของเอกสารนี้

- ใช้เป็นไฟล์หลักสำหรับ context การทำงานใน repo นี้
- ช่วยให้เปิดไฟล์ถูกจุดโดยไม่ต้องไล่อ่านทั้ง repo
- เตือนกติกาสำคัญและ behavior ที่พังซ้ำได้ง่าย
- ถ้าข้อมูลใน `CLAUDE.md` หรือ `codex.md` ซ้ำกับไฟล์นี้ ให้ยึด `AGENTS.md` เป็นหลัก

## Persona

- ผู้ช่วยใน repo นี้คือ "อลิซ"
- ให้พูดกับผู้ใช้แบบผู้หญิง ใช้คำลงท้ายว่า "ค่ะ" / "นะคะ"
- ให้เรียกผู้ใช้ว่า "พี่" — ห้ามเรียก "พี่ชาย" เด็ดขาด
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

## ⚠️ MT5 Timezone — สำคัญมาก อย่าลืม

- **Chart ของ user (IUXMarkets)** แสดงเวลาเป็น **UTC+6** (server time)
- **Bot log / display** ใช้ **Bangkok UTC+7** (`TZ_OFFSET = 7`)
- **Python MT5 API** (`copy_rates_range`) รับ datetime แบบ timezone-aware → ใช้ BKK (UTC+7) ได้เลย

### กฎการแปลงเวลา (ยืนยันจากข้อมูลจริง 2026-05-25)

| เวลาบน chart (UTC+6) | เวลา BKK (UTC+7) | ใช้ fetch MT5 |
|---|---|---|
| 12:29 | 13:29 | `datetime(..., 13, 29, tzinfo=BKK)` |
| 13:20 | 14:20 | `datetime(..., 14, 20, tzinfo=BKK)` |

- **สูตร**: `BKK_time = chart_time + 1 hour`
- **ถ้า user บอกเวลาบนชาร์ต ให้บวก +1h ก่อน fetch MT5 เสมอ**
- ถ้าเผลอ fetch ด้วยเวลาชาร์ตโดยตรง (ไม่บวก +1h) จะได้ข้อมูลช้ากว่าจริง 1 ชั่วโมง

### ตัวอย่าง Python

```python
BKK = timezone(timedelta(hours=7))
# user บอก "12:29 บนชาร์ต" → fetch 13:29 BKK
start = datetime(2026, 5, 25, 13, 29, tzinfo=BKK)
rates = mt5.copy_rates_range(SYMBOL, mt5.TIMEFRAME_M1, start, end)
# display กลับเป็น chart time: BKK - 1h
t_chart = datetime.fromtimestamp(r['time'], tz=BKK) - timedelta(hours=1)
```

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
| logic ของแต่ละท่า | `strategy1.py` ถึง `strategy5.py`, `strategy8.py`, `strategy9.py`, `strategy10.py`, `strategy11.py`, `strategy12.py`, `strategy13.py`, `strategy14.py`, `strategy15.py` |
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
- `CANCEL_NEXT_BAR_BODY_ENABLED` (default `False`) — ยกเลิก limit ถ้าแท่งถัดจาก detect ปิดสวนทาง body ≥35%
- `PENDING_RSI_RECHECK_ENABLED` (default `False`) — เช็ค RSI หลัง fill ก่อนปล่อยให้ position ทำงาน
- `SL_GUARD_ENABLED` (default `True`) — guard ป้องกัน BUY/SELL LIMIT ใหม่ หลัง SL hit ครบ N ครั้งใน TF นั้น
- `SL_GUARD_COUNT` (default `2`) — จำนวน SL hit ที่ trigger guard
- `SL_GUARD_NEAR_POINTS` (default `200`) — ยกเลิก pending ที่ราคาเข้าใกล้ entry ≤ N pt ขณะ guard active
- `SL_GUARD_LOSS_ENABLED` (default `False`) — นับ close ที่ขาดทุนเกิน threshold ว่าเป็น SL hit ด้วย
- `SL_GUARD_LOSS_THRESHOLD` (default `5.0`) — ขาดทุนเกิน $N → นับเป็น SL hit (ใช้ร่วมกับ SL_GUARD_LOSS_ENABLED)
- `S14_FLIP_ENABLED` (default `True`) — S14 Flip: ปิดฝั่งตรงข้าม per-TF ก่อนเปิด S14 ใหม่, toggle ได้ใน `📋 เลือก Strategy`
- `STRONG_TREND_BLOCK_ENABLED` (default `False`) — กัน signal ที่สวน **strong trend** สำหรับท่า bypass (`STRONG_TREND_BLOCK_SIDS` = `[9,10,11,13,14]`) ใน scan loop (`scanner.py`) ก่อน flip/place order — helper `_strong_trend_blocks_signal()`, log event `STRONG_TREND_BLOCK` (ข้อมูลจริง XAU: counter-strong-trend net +314 ถ้าเปิด)
- `SL_ATR_ENABLED` (default `True`) / `SL_ATR_MULT` (default `2`) — `config.SL_BUFFER(atr)` ใช้ `atr × mult` แทน fixed buffer
- `PENDING_LIMIT_GUARD_ENABLED` (default `True`) / `PENDING_LIMIT_BUFFER` (default `2`) / `ORDERS_LIMIT_COOLDOWN_SEC` (default `60`) — กันยิง pending order ซ้ำตอนเต็ม broker limit (retcode 10033) ดู §SL with ATR / Pending-Limit Guard

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
- `_sl_guard_state: dict` — keyed by `(tf, side)` เก็บ `{count, active, blocked_since_bar, swing_ref, blocked_signals, retry_signals}`

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
- **fallback chain** สำหรับ pattern/tf/sid (4 tier):
  1. `position_pattern/tf/sid` (in-memory)
  2. `fvg_order_tickets` / `pending_order_tf` (in-memory)
  3. parse comment ของ position (เช่น `M30_S2`)
  4. `config.tracked_positions[ticket]` (persist ใน `bot_state.json` — แก้ `pattern=-` หลัง restart)

## RSI Fill Recheck

- ฟังก์ชัน: `check_fill_rsi_recheck(app)` ใน `trailing.py`
- **อิสระจาก `ENTRY_CANDLE_ENABLED`** — gate ด้วย `PENDING_RSI_RECHECK_ENABLED` เท่านั้น
- รันใน `main.py` `run_position_check` **ก่อน** `check_entry_candle_quality` (ถ้า fail จะปิด position ทันที)
- ครอบคลุม **ทุก sid** (รวม S12, S13 — เปิดตั้งแต่ 2026-05-18)
- **Skip**: `sid in (1, 9, 11, 14, 15)` — S14 bypass เพราะเป็น market order, S15 (VP reversal — RSI มัก extreme)
- **Triple mode**: ถ้าเปิดครบทั้ง 3 (`PD_ZONE_CHECK_ENABLED AND LIMIT_TREND_RECHECK AND PENDING_RSI_RECHECK_ENABLED`) จะไม่ปิด position ทันที แต่ record ผลใน `_triple_check_state[ticket]["rsi"]` แล้ว evaluate 2/3 ก่อนตัดสิน

## Limit Trend Recheck

- อยู่ใน `check_cancel_pending_orders` (trailing.py)
- เช็ค trend ก่อน fill เมื่อราคาใกล้ entry (`LIMIT_TREND_RECHECK_POINTS` = 300pt)
- ถ้า trend ไม่ allow → cancel pending
- **Skip**: S1 (zone-based), S9 (RSI div), S10 (CRT-managed), S11 (Fibo)
- **Apply**: S2, S3, S4, S5, S6, S8, **S12, S13** (เปิดตั้งแต่ 2026-05-18)

## Fill Trend Recheck

- ฟังก์ชัน: `check_fill_trend_recheck(app)` ใน `trailing.py`
- gate: `LIMIT_TREND_RECHECK`
- เช็ค trend (HHLL structure) หลัง position fill (รอบ 1 ทันที, รอบ 2+ เมื่อ H/L เปลี่ยน)
- ถ้า trend สวนทาง → ปิด position
- **Skip**: `sid in (9, 10, 14, 15)` — S14 bypass เพราะ market order, S15 (VP absorption reversal — counter-trend by design)
- **Apply**: S1, S2, S3, S4, S5, S6, S8, S12, S13
- ใช้ `swing_data_ready(tf)` + `trend_allows_signal(tf, signal)` จาก `scanner.py`
- SIDEWAY + `TREND_FILTER_SIDEWAY_HHLL=True`: ต้องมี `_hhll_data[tf]["last_label"]` ด้วย ถึงจะ `swing_data_ready = True`
- **Race condition fix (2026-05-27)**: ถ้า `swing_data_ready` = False หรือ `trend_allows_signal` คืน sentinel `"?"` → **force-fetch** `fetch_hhll(tf)` ตรงแทนรอ scanner → retry ทันที
  - ถ้ายังไม่พร้อม → log `TREND_RECHECK fill_round1_skip_no_data` → retry cycle ถัดไป
- **Composite TF fix (2026-06-01)**: S2 parallel ใช้ TF แบบ `[M15_H1]` ที่ไม่มีใน `_swing_data` → `swing_data_ready` คืน False เสมอ → recheck skip เงียบ (ไม่มี protection) → หลัง resolve `_tr_tf` ถ้าขึ้นต้น `[` ให้ parse component แล้วใช้ **TF สูงสุด** (`[M15_H1] → H1`)
- log event: `TREND_RECHECK` + sub-event (pass / fail / `fill_round1_skip_no_data`)
- **Triple mode**: ถ้าเปิดครบทั้ง 3 จะไม่ cancel pending ทันที แต่ record ผลใน `_triple_check_state[ticket]["trend"]` แล้ว evaluate 2/3 ก่อนตัดสิน

## PD Zone Recheck

- ฟังก์ชัน: `check_fill_pd_zone(app)` ใน `trailing.py`
- gate: `config.PD_ZONE_CHECK_ENABLED` (default `True`)
- **Skip:** `sid in (9, 15)` — S9 (RSI Div), S15 (VP ใช้ value-area zone เอง ต่าง reference กับ swing-EQ) (S1, S11 ไม่ skip แล้วตั้งแต่ 2026-05-21)
- state: `_pd_zone_fill_state: dict`, `_pd_zone_fill_checked: set` (module-level ใน `trailing.py`)

**ที่มาของ H/L:**

- H = swing high ล่าสุด (HH/LH) จาก `hhll_swing.get_swing_hl_pts(tf)`
- L = swing low ล่าสุด (HL/LL) จาก `hhll_swing.get_swing_hl_pts(tf)`
- EQ = (H + L) / 2

**Logic การเช็ค 2 รอบ:**

- รอบ 1 (fill_check): เช็คทันทีหลัง fill — ถ้า FAIL ปิด position, ถ้า PASS บันทึก H/L รอ round 2
- รอบ 2: เมื่อ H หรือ L เปลี่ยน → re-check EQ ใหม่

**Race condition fix (2026-05-28) — รอบ 1:**

- ถ้า `get_swing_hl_pts` คืน `(None, None)` (HHLL ว่าง) → **force-fetch** `fetch_hhll(tf)` ตรงแทนรอ scanner → retry ทันที
- ถ้ายังไม่พร้อม → log `PD_ZONE_CHECK fill_round1_skip_no_data` → retry cycle ถัดไป

**กฎ pass/fail:**

- `entry < EQ` → BUY ผ่าน (Discount zone) / SELL ล้มเหลว
- `entry > EQ` → SELL ผ่าน (Premium zone) / BUY ล้มเหลว

**Zone:**
- Premium (entry > EQ) → SELL ✅ BUY ❌
- Discount (entry < EQ) → BUY ✅ SELL ❌

**Triple mode:** เมื่อเปิดครบทั้ง 3 และได้ผล PASS/FAIL จะ record ใน `_triple_check_state[ticket]["pd"]` แล้ว evaluate 2/3 ก่อนตัดสิน

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

### SL Guard

- gate: `config.SL_GUARD_ENABLED` (default `True`)
- เมื่อ BUY/SELL โดน SL ครบ `SL_GUARD_COUNT` (default 2) ครั้งใน TF นั้น → guard active
- **Guard active:**
  - บล็อก BUY/SELL LIMIT ใหม่ใน TF+side นั้น (scanner.py)
  - ยกเลิก pending ที่ราคาเข้าใกล้ entry ≤ `SL_GUARD_NEAR_POINTS` (200pt) (check_cancel_pending_orders)
  - เก็บ signal ที่ถูก block ไว้ใน `blocked_signals`
- **Guard deactivate:** เมื่อ swing Low ใหม่เกิด (BUY guard) หรือ swing High ใหม่เกิด (SELL guard) หลัง block
- **หลัง deactivate:** re-place blocked signals ทันที ผ่าน `_sl_guard_place_retries()` ใน scanner.py
  - validate: entry ยังไม่ถูก fill (ราคาไม่ผ่าน entry), SL ไม่ถูก breach
  - หลัง retry: count reset เป็น 0, scan กลับปกติ
- **BUY guard ไม่กระทบ SELL** และกลับกัน (state แยกตาม key `(tf, side)`)
- **State แยกตาม TF:** M1 BUY guard ≠ M5 BUY guard
- Telegram แจ้ง "🛡️ SL Guard เปิดใช้งาน" เมื่อ activate, "🛡️ Re-place Order" เมื่อ retry
- helper ใน `trailing.py`: `_sl_guard_record_sl()`, `_sl_guard_check_unblock()`, `_sl_guard_get_retry_signals()`
- Telegram toggle: Settings → Trend Filter → SL Guard (toggle + count + pts)
- **3 variants:** per-TF (`SL_GUARD_ENABLED`), Combined (`SL_GUARD_COMBINED_ENABLED`), **Group** (`SL_GUARD_GROUP_ENABLED` — mode default ที่ active จริง). per-TF/Combined default OFF
- ⚠️ **Bug fix `swing_ref=0` (2026-06-01):** เดิมทั้ง 3 variant ตั้ง `swing_ref=0` ตอน activate → `*_check_unblock()` เจอ `swing_ref<=0 → unblock ทันที` → guard **ไม่เคยบล็อกได้จริง**
  - แก้: `_sl_guard_record_sl()` ตั้ง `swing_ref` จาก tick ตอน activate + ทุก `*_check_unblock()` init จาก rates แทน unblock ถ้า `swing_ref<=0`
  - log: เพิ่ม `SL_GUARD_ACTIVATE` / `SL_GUARD_GROUP_ACTIVATE`

### SL Guard Loss

- gate: `config.SL_GUARD_LOSS_ENABLED` (default `True`)
- threshold: `config.SL_GUARD_LOSS_THRESHOLD` (default `5.0` USD)
- ถ้า position ปิดด้วยขาดทุน > threshold → นับเป็น SL hit เพิ่มใน guard count ของ TF นั้น
- ทำงานร่วมกับ `SL_GUARD_ENABLED` — ถ้า guard ไม่ ON จะไม่นับ
- logic อยู่ใน `notifications.py` หลัง close detection
- Telegram toggle: Settings → Trend Filter → Loss Guard (toggle + threshold: $3/$5/$10/$20)

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

### S14 Sweep RSI

- strategy market order standalone
- ใช้ RSI หา reversal zone (LL/HH) แล้วตรวจ Engulf/Sweep pattern บนแท่งล่าสุด
- เปิด market order ทันที ไม่มี pending
- **bypass Trend Filter** ทุกจุด:
  - scan loop: `sid not in (9, 10, 13, 14)` ใน `scanner.py`
  - fill trend recheck: `sid in (9, 10, 14)` ใน `trailing.py`
- **bypass RSI Fill Recheck**: `sid in (1, 9, 11, 14)` ใน `trailing.py`
- **PD Zone filter** ใน scan loop (entry ต้องอยู่ใน Premium/Discount zone)
- **Flip logic** (`S14_FLIP_ENABLED`, default True): ปิดฝั่งตรงข้าม per-TF ก่อนเปิดใหม่
  - ฟังก์ชัน: `_clear_opposite_s14_exposure(app, tf_name, signal)` ใน `scanner.py`
  - log: `S14_REVERSE_CLOSE` / `S14_REVERSE_CLOSE_FAIL`
  - Telegram toggle: `📋 เลือก Strategy` → sub-option ท่า 14
- **TSO**: รองรับผ่าน `open_order_market()` (ตั้งแต่ 2026-05-26) — scale ×4 ถ้า `SCALE_OUT_ENABLED`
- ไม่เข้า: `Entry Candle`, `Trail SL`, `Opposite Order`, `Limit Guard`, `SL Guard`
- comment: `M1_S14_engulf` / `M1_S14_sweep`
- config: `S14_RSI_PERIOD`, `S14_REVERSAL_LOOKBACK`, `S14_ENGULF`, `S14_SWEEP`, `S14_LL_USE_HHLL`, `S14_FLIP_ENABLED`

### S15 Volume Profile POC + Absorption

- ไฟล์: `strategy15.py` — strategy **standalone reversal** (Win Rate อ้างอิง 85-90%: POC defense + absorption)
- คำนวณ Volume Profile จาก tick_volume (proxy) ย้อนหลัง `S15_LOOKBACK` bars → `POC` / `VAH` / `VAL`
  - bucket_size = `ATR/10` (auto-scale XAU/BTC), Value Area = 70% volume (`S15_VAL_VAH_PCT`)
  - **helper `_bar_volume(bar)`**: ใช้ index access (`bar["tick_volume"]`) เท่านั้น — ห้าม `.get()` เพราะ numpy.void (ดู §numpy rates check)
- Absorption 2 pattern: long wick sweep (≥ `S15_ABSORPTION_WICK_PCT` × range) + 2-bar reversal
- Entry **LIMIT** ที่ POC/VAL (BUY) หรือ POC/VAH (SELL) — guard `entry < close` (BUY) / `entry > close` (SELL) กัน `open_order` skip
- รองรับ **MULTI** (POC + VAL/VAH พร้อมกัน) — เป็น range play ถือ BUY+SELL พร้อมกันได้
- **แยกตาม TF เต็มตัว**: คำนวณ VP จาก rates ของ TF นั้น, order/pending/dedup แยกตาม TF (`M1_S15`/`M5_S15`/...)
- **TSO ใช้ได้ (ไม่ skip)**: ผ่าน `open_order()` → `_scale_out_resolve_volume()` (skip แค่ `sid=13`) → scale ×4 อัตโนมัติเมื่อ `SCALE_OUT_ENABLED`, watcher `check_scale_out_partial` ทยอยปิดได้ (volume cap เป็น per-order = `base×4` → MULTI หลายไม้ผ่านหมด)
- **Standalone — bypass/skip filter ของระบบหลักทั้งหมด** (เหมือน S10/S12/S13/S14):
  - bypass Trend Filter (scan): `sid not in (9, 10, 13, 14, 15)` ใน `scanner.py`
  - skip Fill Trend Recheck: `sid in (9, 10, 14, 15)`
  - skip RSI Fill Recheck: `sid in (1, 9, 11, 14, 15)`
  - skip PD Zone Recheck (fill + pending): `sid in (9, 15)` — VP ใช้ value-area zone เอง (ต่าง reference กับ swing-EQ)
  - skip Entry Candle, Trail SL, **Opposite Order** (ถือ 2 ฝั่งได้), Limit Guard: `(10, 12, 13, 15)`
  - **คงไว้**: SL Guard (risk protection)
- **Strong-Trend Block**: S15 อยู่ใน `STRONG_TREND_BLOCK_SIDS` (default `[9,10,11,13,14,15]`) — เปิด `STRONG_TREND_BLOCK_ENABLED` เพื่อกันไม้สวน strong trend ได้ (default OFF)
- comment: `M5_S15_POC` / `M5_S15_VAL` / `M5_S15_VAH` (code ใน `_pattern_comment_code`)
- default `active_strategies[15] = False`
- config: `S15_LOOKBACK`, `S15_ZONE_ATR_MULT`, `S15_VAL_VAH_PCT`, `S15_ABSORPTION_WICK_PCT`, `S15_USE_VAL_VAH`, `S15_MIN_RR`
- Telegram toggle: `📋 เลือก Strategy` → ท่า 15: VAL/VAH zones, Lookback (50/100/200), Min RR (1/1.5/2)

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

### Triple Scale-Out (TSO) — `📈 Scale-Out 4X`

- master toggle: `SCALE_OUT_ENABLED` (default `True`) - ปุ่มอยู่บนหน้าเมนู `⚙️ ตั้งค่า` หลัก
- คอนเซปต์: ขยาย lot ของ pending/limit order ใหม่เป็น `base × 4` เสมอ แล้วทยอยปิด 4 ขั้นเมื่อราคาผ่าน entry
- pulse close ครั้งละ `SCALE_OUT_TP_LOT × points_scale()` (XAU = 0.01, BTC = 0.04)
- **volume รวมเสมอ = base × 4** (XAU = 0.04, BTC = 0.16) ไม่ขึ้นกับ TP distance อีกต่อไป

**Scope:**

- ใช้กับ pending/limit ที่สร้างผ่าน `open_order()` และ `open_order_stop()` เท่านั้น
- `open_order_market()` รองรับ TSO ตั้งแต่ 2026-05-26 — ใช้กับ **S14** (Sweep RSI)
- **`sid=13` (S13 EzAlgo V5)** ถูก **ยกเว้น** จาก lot scale — ใช้ TSO สร้าง orders แยก 4 ชุดแทน

**Always-4-Steps Formula (ตั้งแต่ 2026-05-22):**

- helper: `config.compute_tso_effective_steps(tp_orig_dist, sid="")`
- คืน **เสมอ 4 steps** — lot รวม = `base × 4` เสมอ

**General (ทุกท่า ยกเว้น S10/S13):**

| steps | formula |
|-------|---------|
| step 1 | `min(200pt, TP)` |
| step 2 | `min(300pt, TP)` |
| step 3 | `min(600pt, TP)` |
| step 4 | `TP` |

ตัวอย่าง: TP=100pt→[100,100,100,100] | TP=500pt→[200,300,500,500] | TP=800pt→[200,300,600,800] | TP=1200pt→[200,300,600,1200]

**S10 (special):**

| steps | formula |
|-------|---------|
| step 1 | `min(200pt, TP)` |
| step 2 | `min(300pt, TP)` |
| step 3 | `TP / 2` |
| step 4 | `TP` |

**S13** ใช้ general formula แต่ออกเป็น **orders แยก 4 ชุด** (ไม่ partial close)

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

**Symbol/Volume Guard (กันออเดอร์ปนข้าม symbol ตอนสลับ XAU↔BTC) — ตั้งแต่ 2026-06-01:**

- ปัญหาเดิม: `config.SYMBOL` เป็น global ที่ `set_runtime_symbol()` mutate กลางอากาศ (symbol_switch_job ทุก 1 นาที) ขณะ scan jobs (ทุก 5 วิ) อ่าน rates + เรียก `get_volume()`/`points_scale()` พร้อมกัน + per-TF cache ไม่ถูกล้าง → order รอบนั้นอาจได้ "ราคา/level ของ symbol หนึ่ง" ผสม "volume scaling ของอีก symbol"
  - เคสจริง: XAU order (entry≈4571) ติด `base=0.04` ของ BTC → lot **0.16** บน XAU (ควรเป็น 0.04); BTC order ติด `tp` ราคา XAU (4518) → step ขยะ
  - **หมายเหตุ:** lot 0.16 ของ **BTC แท้ๆ ถูกต้อง** (base 0.04 × TSO 4) — ที่เห็นถูกปิดพร้อมกันตอน ~05:02 คือ `_close_btc_exposure_before_xau_switch()` ปิด BTC ตอน XAU เปิดตลาด ไม่ใช่ double-scale
**(A) Order-level guard — ปลายทาง (ตาข่ายนิรภัย):**

- ฟังก์ชัน: `_symbol_consistency_error(entry, sl, tp, send_volume, ...)` ใน `mt5_utils.py` — เรียกใน `open_order()`, `open_order_stop()`, `open_order_market()` ก่อน `order_send` ทุกตัว ถ้าผิดปกติ return `{"success": False, "skipped": True}` + log event `SYMBOL_GUARD_BLOCK`
- ตรวจ 3 ชั้น อิงราคา live ของ SYMBOL ปัจจุบัน (ground truth เดียวกับ order_send):
  0. **switch-guard**: ถ้า `config.symbol_switch_in_progress == True` → block ทุกออเดอร์ (กำลังสลับ symbol อยู่ เลื่อนไปรอบ scan ถัดไป)
  1. **price-band**: `entry`/`sl`/`tp` ต้องอยู่ในช่วง `[0.5×, 2.0×]` ของ mid price (XAU~4500 vs BTC~77000 ต่าง ~17 เท่า → จับการปนข้ามได้ชัด, order ปกติ SL/TP ห่าง entry ไม่กี่ % → ไม่ false-positive)
  2. **volume-cap**: `send_volume` ห้ามเกิน `get_volume() × 4` ของ symbol ปัจจุบัน (XAU cap=0.04, BTC cap=0.16) — reverse-limit (base 0.01 จาก `SYMBOL_CONFIG`) ยังผ่านทุกกรณี
- fail-safe: exception ใดๆ ภายใน guard → return `None` (ไม่ขวาง flow ปกติ)

**(B) Root-cause fix — ต้นทาง (ตัด race + stale data):**

- **switch flag** `config.symbol_switch_in_progress` (default `False`) — `check_symbol_switch()` ใน `main.py` set `True` ครอบช่วง close BTC + `set_runtime_symbol()` + save (try/finally กัน flag ค้าง) แล้ว reset `False` **ก่อน** เรียก `auto_scan` รอบ immediate → ระหว่างสลับ ออเดอร์ใหม่ถูก block ที่ guard layer 0 ทั้งหมด
- **cache clear ตอนสลับ**: `set_runtime_symbol()` เช็ค `changed` ถ้า symbol เปลี่ยนจริง → ล้าง per-symbol cache ผ่าน `sys.modules` (เลี่ยง circular import):
  - `hhll_swing.clear_cache()` (`_hhll_data`), `amp_trend.clear_cache()` (`_amp_data`), `scanner.clear_symbol_caches()` (`_swing_data` + `_scan_results`)
  - ปลอดภัย self-healing: `scan_one_tf` เรียก `fetch_hhll()`/`fetch_amp_trend()` ทุกรอบ → cache repopulate ด้วยข้อมูล symbol ใหม่ทันที
- **residual ที่ยังเหลือ**: reverse-**market** ใน `trailing.py` ยิง `mt5.order_send` ตรง (ไม่ผ่าน 3 ฟังก์ชัน) — ความเสี่ยงต่ำเพราะ market ใช้ราคา live แต่ volume ยังปนได้ในทางทฤษฎี

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

### Sideway HHLL Filter (`TREND_FILTER_SIDEWAY_HHLL`)

- gate: `config.TREND_FILTER_SIDEWAY_HHLL` (default `True`)
- ทำงานเมื่อ trend = `SIDEWAY` เท่านั้น (ดู `last_label` — swing point ล่าสุดที่เกิด)
- logic (ตั้งแต่ 2026-05-22):

| last_label | BUY | SELL |
|-----------|-----|------|
| HH | ✅ ผ่าน | ❌ block |
| HL | ✅ ผ่าน | ❌ block |
| LH | ❌ block | ✅ ผ่าน |
| LL | ❌ block | ✅ ผ่าน |

- ทำงานทั้ง `basic` mode และ `breakout` mode
- Telegram toggle: Settings → Trend Filter → Sideway Filter → Sideway HHLL Filter

### Strong-Trend Block สำหรับท่า bypass (`STRONG_TREND_BLOCK_ENABLED`, ใหม่ 2026-06-01)

- gate: `config.STRONG_TREND_BLOCK_ENABLED` (default `False`) + `STRONG_TREND_BLOCK_SIDS` (default `[9,10,11,13,14]`)
- ปกติ S9/S10/S11/S13/S14 ข้าม trend filter (เป็นท่า reversal/mean-reversion) — flag นี้บล็อกเฉพาะ signal ที่สวน **strong trend**
  - BULL strong + SELL → block / BEAR strong + BUY → block (weak/sideway ปล่อยผ่าน)
- helper: `_strong_trend_blocks_signal(tf_name, signal)` ใน `scanner.py` (อ่าน `_swing_data[tf]["trend"]`)
- จุดเช็ค: scan loop **หลัง** bypass check **ก่อน** S13/S14 flip + place order → `continue` กันทั้ง flip+order
- log event: `STRONG_TREND_BLOCK`
- ที่มา: ข้อมูลจริง XAU (26 พ.ค.+) counter-strong-trend บนท่า bypass = 46% win, net **+314** ถ้าเปิด

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

### Telegram message ยาวเกิน (fix 2026-06-01)

- `_TgWrapper._worker()` ใน `config.py`: ก่อนส่ง **ตัดข้อความที่ยาว > 4096** เชิงรุก (Telegram limit) → กัน drop
- auto-fix ตอน error ดักทั้ง `"Message is too long"` **และ** `"Text is too long"` (เดิมดักแค่ "Message") + retry plain ถ้า Markdown ยัง fail
- เดิม Scan Summary ยาวเกินทำให้ `TG_DROP "Text is too long"` หลายพันครั้ง

### SL with ATR — True Range + RMA (fix 2026-06-02)

- `config.SL_BUFFER(atr)` คืน `atr × SL_ATR_MULT` (เมื่อ `SL_ATR_ENABLED=True`) แทน fixed buffer
- **ATR กลาง: `mt5_utils.calc_atr(rates, period=14)`** — True Range + Wilder's RMA ตรงกับ `mql5/ATR_TrueRange.mq5`
  - `TR = max(H-L, |H-prevClose|, |L-prevClose|)` (แท่งแรก = H-L), seed=SMA period แรก, `ATR[i]=α·TR[i]+(1-α)·ATR[i-1]`, α=1/period
- ทุกท่าที่คำนวณ SL เรียก `calc_atr` แล้ว: `get_structure()` (S1/S2/S4 ผ่าน `ms["atr"]`), S3, S9, S14 — เดิมใช้ค่าเฉลี่ย H-L 14 แท่ง (ไม่รวม gap)
  - S13 มี `_atr_values()` (RMA) ของตัวเองอยู่แล้ว — ไม่แตะ
- XAU เทรดต่อเนื่อง gap น้อย → ATR ใหม่ ≈ เก่า (ต่างเฉลี่ย ~2%); sim isolated backtest (5/24+) ต่าง ~-143 USD = threshold noise ไม่ใช่ regression เชิงระบบ
- sim: `sim_atr_compare.py` (monkey-patch `mt5_utils.calc_atr` + `strategy3/9/14.calc_atr` เป็น OLD แล้วเทียบ) — `call_strategy()` เรียกตาม signature (S3 รับแค่ `rates`)

### Pending-Limit Guard — retcode 10033 (fix 2026-06-02)

- Broker จำกัด pending orders (`account_info().limit_orders`, เคสจริง = **50**) เต็มแล้ว bot ยังยิงซ้ำทุก scan cycle → `ORDER_FAILED 10033 "Orders limit reached"` (เคสจริง 2026-05-31 BTC: **46,339 ครั้ง/วัน**)
- `mt5_utils._pending_limit_blocked()` pre-check ก่อน `order_send` ทั้ง 3 ฟังก์ชัน (`open_order_stop` / `open_order` / `open_order_market`):
  - อยู่ใน cooldown หลังเพิ่งโดน 10033 → block | `orders_total ≥ cap - PENDING_LIMIT_BUFFER` → block
  - block → คืน `{"skipped": True, "silent": True}` → caller เข้า branch `skipped` ที่ dedup (`_print_skip_once`) → **ไม่ log `ORDER_FAILED`**
- โดน 10033 จริง → `_note_orders_limit_hit()` ตั้ง cooldown `ORDERS_LIMIT_COOLDOWN_SEC` (60s)
- log `PENDING_LIMIT_BLOCK` (throttle 5 นาที/ครั้ง) — `silent` flag ทำให้ caller (scanner S2 FVG, pending.py FVG/PB) ไม่ log/tg ซ้ำ
- ผล: log spam 10033 ลด ~99% (51,302 → ~288/วัน worst case) + ไม่ยิง `order_send` รัวๆ ไป broker

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
