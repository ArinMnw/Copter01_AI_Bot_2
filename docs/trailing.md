# การจัดการ Position และ Trailing

เอกสารนี้สรุป flow สำคัญใน `trailing.py` แบบภาษาไทย เพื่อใช้ตามรอยเวลาระบบเปิด order แล้ว

## ภาพรวม

ฟังก์ชันหลักที่เกี่ยวข้อง:

- `check_entry_candle_quality()`
- `check_fill_rsi_recheck()`
- `check_engulf_trail_sl()`
- `check_opposite_order_tp()`
- `check_breakeven_tp()`
- `check_s6_trail()`
- `check_cancel_pending_orders()`
- `check_limit_sweep()`
- `check_s12_management()`
- `check_s1_zone_rules()`

## Entry Candle Quality

ฟังก์ชัน: `check_entry_candle_quality()`

หน้าที่:

- จับ `Limit Fill`
- หา `entry_bar` และ `next_bar`
- ประเมินคุณภาพแท่ง entry
- อัปเดต `_entry_state`
- บางเคสปิด position ทันที

Master toggle: `ENTRY_CANDLE_ENABLED` ถ้า `False` ฟังก์ชัน return ทันที

state หลัก:

- `done`
- `waiting_next`
- `waiting_bad`
- `closing_fail`

### สิ่งที่เกิดก่อนประเมิน mode

ทุก position ใหม่จะผ่านขั้นตอนนี้ก่อน:

- แจ้ง `Limit Fill`
- หา `tf / sid / pattern` จาก memory, comment หรือ pending metadata
- หา `entry_bar` ที่ fill เกิดขึ้นจริง
- แจ้ง `แท่ง Entry จบ`

หลังจากนั้นจึงเข้า logic ของแต่ละ mode

### กฎโครงสร้างสำคัญที่ใช้ได้ทุก mode

กฎนี้สำคัญมาก เพราะไม่ว่าตั้ง `ENTRY_CANDLE_MODE` เป็นอะไร ระบบก็ยังใช้ได้:

BUY:
- ถ้าแท่ง entry เป็น `แดง`
- และ `close < prev low`
- จะ `ปิดทันที`
- ถ้า `LIMIT_SWEEP = ON` จะวิ่งต่อไปที่ flow `Limit Sweep`

SELL:
- ถ้าแท่ง entry เป็น `เขียว`
- และ `close > prev high`
- จะ `ปิดทันที`
- ถ้า `LIMIT_SWEEP = ON` จะวิ่งต่อไปที่ flow `Limit Sweep`

กฎนี้อยู่เหนือการตีความ body หลายเคส เพราะถือว่าแท่งได้ปิดทะลุโครงสร้างก่อนแล้ว

## รายละเอียดแต่ละ Mode

### 1. classic

แนวคิด:
- ใช้กติกาเดิมแบบ entry candle quality ทั่วไป
- ถ้ายังไม่เกิด adverse close ทะลุ `prev low / prev high` ก็จะเดินตาม logic สีแท่งและ body

BUY:
- แท่ง entry เขียว และ `body >= 35%`
  - `done`
- แท่ง entry เขียว และ `body < 35%`
  - `waiting_next`
- แท่ง entry แดง แต่ยังไม่เข้าเงื่อนไขปิดทันทีจากโครงสร้าง
  - เข้า `waiting_bad`
  - ปรับ `SL` ไปทาง `swing low`
  - ปรับ `TP` ไปทาง `entry open`

SELL:
- สลับฝั่งตรงข้าม
- แดงแข็งแรงพอ -> `done`
- แดงอ่อน -> `waiting_next`
- เขียวแต่ยังไม่ทะลุ `prev high` -> `waiting_bad`

waiting_bad:
- รอแท่งถัดไปปิด
- ถ้าแท่งถัดไปยังไม่ช่วยให้โครงสร้างดีขึ้น อาจปิดหรือปรับ SL/TP อีกรอบตามทิศของ position

### 2. close

แนวคิด:
- เน้น "ปิดเร็ว" ถ้าแท่ง entry ออกสวนทาง
- ใช้ branch ปิดทันทีจากคุณภาพแท่งมากกว่า mode classic

BUY:
- ถ้าแท่งเขียว
  - `body >= 35%` -> `done`
  - `body < 35%` -> `waiting_next`
- ถ้าแท่งแดงและเข้า adverse structure (`close < prev low`)
  - `close_immediate`
  - ถ้าเปิด `LIMIT_SWEEP` จะไปต่อ sweep
- ถ้าแท่งแดงแต่ยังไม่หลุดโครงสร้าง
  - อยู่ในกลุ่มที่ปิดเร็วตาม logic close mode
  - โดยรวมถือว่าเข้มกว่า classic

SELL:
- สลับฝั่งตรงข้าม
- ถ้าแท่งเขียวและ `close > prev high`
  - `close_immediate`
  - ถ้าเปิด `LIMIT_SWEEP` จะไปต่อ sweep

หมายเหตุ:
- mode นี้เกี่ยวข้องกับ reverse market / reverse limit มากกว่า mode อื่น
- แต่ reverse จะขึ้นอยู่กับ toggle และ branch ของโค้ดในรอบนั้นด้วย

### 3. close_percentage

แนวคิด:
- ใช้สีแท่ง + เปอร์เซ็นต์ body ประกอบการตัดสิน
- แต่ถ้าแท่งปิดทะลุ `prev low / prev high` จะปิดทันทีโดยไม่สนเปอร์เซ็นต์

BUY:
- แท่งเขียว และ `body >= 35%`
  - ถ้าราคาปิดยังเหนือ entry อาจขยับ `SL = entry + spread`
  - จากนั้น `done`
- แท่งเขียว และ `body < 35%`
  - ถ้าราคาปิดยังเหนือ entry อาจขยับ `SL = entry + spread`
  - จากนั้น `waiting_next`
- แท่งแดง และ `close < prev low`
  - ปิดทันที
  - ถ้า `LIMIT_SWEEP = ON` จะไปต่อ sweep
- แท่งแดง และยังไม่หลุด `prev low`
  - ถ้า `body < 70%`
    - ระบบดู `ask` เทียบกับ `entry + spread`
    - ถ้า `ask > entry + spread`
      - ไม่ปิด
      - ปรับ `SL = entry + spread`
      - แล้ว `done`
    - ถ้า `ask <= entry + spread`
      - ปิดทันที
      - ถ้า `LIMIT_SWEEP = ON` จะไปต่อ sweep
  - ถ้า `body >= 70%`
    - ปิดทันที
    - ถ้า `LIMIT_SWEEP = ON` และยังเข้า adverse structure ก็ไปต่อ sweep

SELL:
- สลับฝั่งตรงข้าม
- แท่งแดงแข็งแรงพอ -> `done`
- แท่งแดงอ่อน -> `waiting_next`
- แท่งเขียวและ `close > prev high`
  - ปิดทันที
  - ถ้า `LIMIT_SWEEP = ON` จะไปต่อ sweep
- ถ้าเขียวแต่ยังไม่หลุด `prev high`
  - ใช้ logic เปอร์เซ็นต์แบบสลับฝั่งกับ BUY
  - อาจเลือก protect ที่ `entry - spread` หรือปิดทันที

### สรุปความต่างของ 3 mode

classic:
- ใจเย็นสุด
- ยอมให้เข้า `waiting_bad` ได้ชัดเจน
- ใช้แท่งถัดไปช่วยตัดสินต่อ

close:
- ตัดสินเร็วขึ้น
- เจอแท่งสวนทางแรง ๆ จะปิดไวกว่า classic

close_percentage:
- ใช้ body % เป็นเกณฑ์ชัด
- แต่ถ้าแท่งปิดทะลุโครงสร้าง (`prev low / prev high`) จะปิดทันทีโดยไม่สนเปอร์เซ็นต์
- มี logic ปรับ `SL = entry ± spread` ในบางกรณีแทนการปิดทันที

### หมายเหตุเพิ่มเติม

- reverse position มี branch พิเศษของตัวเอง
- reverse ticket อาจถูกตรวจด้วยกฎเฉพาะก่อนเข้า logic ปกติ
- S8 ที่ fill มาโดยยังไม่มี SL อาจถูกตั้ง SL หลัง fill ก่อนเข้าส่วนอื่นของ lifecycle

## Trail SL แบบ Engulf

ฟังก์ชัน: `check_engulf_trail_sl()`

แนวคิด:
- ใช้ TF group ตาม `TRAIL_GROUPS`
- หาแท่ง engulf ที่ให้ SL ดีขึ้น

mode:
- `combined`
- `separate`

ตัวเลือกเสริม:
- `TRAIL_SL_IMMEDIATE`
  - ถ้าเปิด อาจ trail ได้ก่อน `_entry_state = done`
- `TRAIL_SL_ENABLED`
  - master toggle ถ้า `False` ฟังก์ชัน return ทันที
- `Trend Filter override`
  - เปิด/ปิดได้จาก `Trend Filter > Trail SL Override`
  - config: `TREND_FILTER_TRAIL_SL_OVERRIDE_ENABLED`
  - ถ้าเปิด Trend Filter แบบ Per-TF หรือ Higher TF แล้ว trend ของ TF อ้างอิง "เปลี่ยนเป็นฝั่งตรงข้ามของ position" ระบบจะยอมให้ Trail SL ทำงานแม้ `TRAIL_SL_FOCUS_NEW_ENABLED` กำลัง freeze อยู่
  - position `SELL`: ต้องเปลี่ยนจาก `BEAR` หรือ `SIDEWAY` ไปเป็น `BULL` ทั้ง `weak` หรือ `strong`
  - position `BUY`: ต้องเปลี่ยนจาก `BULL` หรือ `SIDEWAY` ไปเป็น `BEAR` ทั้ง `weak` หรือ `strong`
  - `SIDEWAY` ใช้เป็นฐานก่อนเปลี่ยนฝั่งได้ แต่ตัว `SIDEWAY` เองยังไม่ trigger trail
  - `UNKNOWN` ไม่ถือเป็น trend ใหม่ และไม่ล้าง trend เดิม

หลักการ:
- BUY: หา SL ที่สูงขึ้นแต่ยังสมเหตุผล
- SELL: หา SL ที่ต่ำลงหรือป้องกันดีขึ้นตามฝั่ง

หมายเหตุปัจจุบัน:
- `S10`, `S12`, `S13` ไม่เข้า flow นี้
- ถ้าเปิด `TRAIL_SL_REVERSAL_OVERRIDE_ENABLED`
  - ระบบจะยอมให้ Trail SL ทำงานได้แม้ `TRAIL_SL_FOCUS_NEW_ENABLED` กำลัง freeze อยู่
  - ใช้เฉพาะท่าที่ไม่ standalone
  - ดูจากแท่งกลับตัวของฝั่งตรงข้ามบน `TF` ของ order
  - BUY position: ยอม trail เมื่อเจอ bearish reversal
  - SELL position: ยอม trail เมื่อเจอ bullish reversal

## Opposite Order Mode

ฟังก์ชัน: `check_opposite_order_tp()`

มี 2 mode:
- `tp_close`
- `sl_protect`

Master toggle: `OPPOSITE_ORDER_ENABLED` ถ้า `False` ฟังก์ชัน return ทันที

หมายเหตุปัจจุบัน:
- `S10`, `S12`, `S13` ไม่เข้า flow กลางนี้
- `S13` ใช้ logic ปิดฝั่งตรงข้ามของตัวเองใน `scanner.py`

### tp_close

- ใช้ order ฝั่งตรงข้ามมาเป็นเงื่อนไขปิดหรือปรับ TP

### sl_protect

- ปรับ SL เพื่อกันความเสี่ยง เช่น `entry ± spread`
- ปัจจุบันมี guard ไม่ให้ยิง protect ซ้ำรัวสำหรับ ticket เดิม
- Telegram และ log ถูก dedup แล้ว

## Breakeven TP

ฟังก์ชัน: `check_breakeven_tp()`

แนวคิด:
- หลัง position ผ่าน entry candle แล้ว
- ถ้าราคาวิ่งย้อนผิดทางและเกิดแท่งตำหนิ/กลืนกินตามเงื่อนไข
- ระบบจะตั้ง `TP = entry`

BUY:
- ดูตอนราคาต่ำกว่า entry

SELL:
- ดูตอนราคาสูงกว่า entry

## Strategy 6 และ S6i

ฟังก์ชัน:
- `check_s6_trail()`
- `_s6_process_ticket()`
- `_s6i_process_ticket()`

### S6

- ใช้กับ position ที่มาจากท่า 2/3 เป็นหลัก
- flow โดยทั่วไป:
  - รอสัมผัส swing
  - เริ่มนับแท่ง
  - ถ้าทะลุเงื่อนไข จะ trail SL
  - ถ้าไม่ผ่านครบจำนวนแท่ง อาจตั้ง TP = breakeven

### S6i

- เป็น swing logic อิสระ
- ใช้ pattern ฝั่งตรงข้ามประกอบ
- อาจตั้ง TP ใหม่
- อาจตั้ง limit order ใหม่

## S12 Management

ฟังก์ชัน: `check_s12_management()`

หน้าที่:
- รันทุก cycle ก่อน `scan_one_tf()` และก่อน SCAN_SUMMARY
- เรียก `s12_cleanup_tickets()` จาก `strategy12.py` เพื่อตรวจ ticket S12 ที่ปิดแล้ว
- ถ้าพบ SL hit จะตั้ง `_s12_state["last_sl_time"]` ทำให้เข้า cooldown

ผลกระทบ:
- cooldown เริ่มต้นจาก `check_s12_management()` (รัน BEFORE SCAN_SUMMARY)
- `scan_s12()` รัน AFTER SCAN_SUMMARY → `_s12_scan_status` ที่ SCAN_SUMMARY เห็นเป็น cycle ก่อนหน้า

## S1 Zone Rules

ฟังก์ชัน: `check_s1_zone_rules()`

หน้าที่:
- ใช้กับ `S1` เมื่อ `S1_ZONE_MODE = "zone"`
- แยกการตัดสินใจเรื่อง zone ออกจากขั้น detect pattern
- ดูทั้ง pending order และ position ที่ fill แล้ว

กฎปัจจุบัน:
- pending `S1` ที่อยู่นอก zone -> ยกเลิก order
- pending `S1` ที่ยังอยู่ใน zone -> คง order ไว้
- position `S1` ที่อยู่นอก zone และ `profit < 0` -> ปิด position
- position `S1` ที่อยู่นอก zone แต่ `profit >= 0` -> ไม่ปิด

metadata ที่ใช้:
- `pending_order_tf[ticket]["s1_zone_meta"]`
- `position_zone_meta[ticket]`

หมายเหตุ:
- zone จะถูกประเมินซ้ำจาก rates ปัจจุบันทุก cycle
- ถ้าไม่ได้ใช้ `S1_ZONE_MODE = "zone"` ฟังก์ชันนี้จะ return ทันที

## Auto Cancel Pending

ฟังก์ชัน: `check_cancel_pending_orders()`

หน้าที่:
- ยกเลิก pending order เมื่อ setup ไม่ valid แล้ว

ตัวอย่าง:
- โดน swing หลัก invalidate
- แท่งถัดไปทำให้ setup ล้มเหลว
- reverse limit หมดอายุ
- S8 arm SL / retry logic ก็พัวพันใน flow นี้ด้วย

## RSI Fill Recheck (Pending RSI Recheck)

ฟังก์ชัน: `check_fill_rsi_recheck(app)` ใน `trailing.py`

- **อิสระจาก `ENTRY_CANDLE_ENABLED`** — gate ด้วย `PENDING_RSI_RECHECK_ENABLED` เท่านั้น
- รันใน `main.py` `run_position_check` **ก่อน** `check_entry_candle_quality`
- ใช้ RSI ของ `TF` เดียวกับ order ณ รอบที่ position fill

เกณฑ์:
- BUY: RSI ต้องไม่เกิน buy max (`PENDING_RSI_BUY_MAX`, default `50.0`)
- SELL: RSI ต้องไม่ต่ำกว่า sell min (`PENDING_RSI_SELL_MIN`, default `50.0`)
- ถ้าไม่ผ่าน — **individual mode**: ปิด position หลัง fill ทันที
- ถ้าไม่ผ่าน — **triple mode** (เปิดครบทั้ง 3): record ผลใน `_triple_check_state[ticket]["rsi"]` แล้ว evaluate 2/3 ก่อนตัดสิน

หมายเหตุ:
- ครอบคลุมทุก sid รวม S12, S13 (เปิดตั้งแต่ 2026-05-18)
- log events: `ENTRY_FILL_RSI_RECHECK_FAIL`, `ENTRY_FILL_RSI_RECHECK_SKIP`

config ที่เกี่ยวข้อง:
- `PENDING_RSI_RECHECK_ENABLED`
- `PENDING_RSI_PERIOD`
- `PENDING_RSI_APPLIED_PRICE`
- `PENDING_RSI_BUY_MAX`
- `PENDING_RSI_SELL_MIN`

## PD Zone Recheck

ฟังก์ชัน: `_pd_zone_process(ticket, app)` ใน `trailing.py`

gate: `config.PD_ZONE_CHECK_ENABLED` (default `True`)

Return: `(status: str, tg_msgs: list)` — `"pass"` / `"fail"` / `"wait"`

state: `_pd_zone_state: dict` (module-level)

### ที่มาของ H/L

- H = swing high ล่าสุด (HH/LH) จาก `hhll_swing.get_swing_hl_pts(tf)`
- L = swing low ล่าสุด (HL/LL) จาก `hhll_swing.get_swing_hl_pts(tf)`
- EQ = (H + L) / 2

### การเช็ค 3 รอบ 2/3 ชั้นใน

- รอบ 1: เมื่อ order เกิด → เช็ค entry vs EQ ณ ขณะนั้น
- รอบ 2: H หรือ L เปลี่ยนครั้งแรก → เช็ค EQ ใหม่
- รอบ 3: H หรือ L เปลี่ยนครั้งที่สอง (หลังรอบ 2) → เช็ค EQ ใหม่

### กฎ zone

- `entry < EQ` (Discount zone) → BUY ผ่าน, SELL ล้มเหลว
- `entry > EQ` (Premium zone) → SELL ผ่าน, BUY ล้มเหลว

### การตัดสิน

- pass ≥ 2 → `"pass"`
- fail ≥ 2 → `"fail"`
- ยังไม่ครบ → `"wait"`

ส่ง Telegram ทุกรอบบอกว่าอยู่ Premium/Discount zone + pass/fail

### Triple mode

- ถ้าเปิดครบทั้ง 3 และได้ผล `"pass"` หรือ `"fail"` จะ record ใน `_triple_check_state[ticket]["pd"]` แล้ว evaluate 2/3 ก่อนตัดสิน
- ถ้าเปิดเฉพาะตัว: เมื่อ `"fail"` จะ cancel pending หรือ close position ทันที

## Triple Recheck (Combined 2/3)

เปิดทำงานเมื่อ: `PD_ZONE_CHECK_ENABLED AND LIMIT_TREND_RECHECK AND PENDING_RSI_RECHECK_ENABLED` ทั้งสามพร้อมกัน

helper: `_triple_check_all_enabled() -> bool`

state: `_triple_check_state: dict`

```python
{
    ticket: {
        "rsi":    None | True | False,
        "trend":  None | True | False,
        "pd":     None | True | False,
        "tf":     str,
        "signal": str,
    }
}
```

helper:
- `_triple_check_record(ticket, key, result, tf, signal)` — บันทึกผลแต่ละตัว
- `_triple_check_evaluate(ticket) -> "cancel"|"keep"|"wait"` — ตัดสิน 2/3

### การตัดสิน

- fails ≥ 2 → `"cancel"` → cancel pending หรือ close position ทันที
- passes ≥ 2 → `"keep"` → คง order ไว้, clear state
- อื่น → `"wait"` → รอข้อมูลเพิ่ม

Telegram: เมื่อตัดสินแล้วส่งสรุป `RSI ✅/❌ | Trend ✅/❌ | PD ✅/❌`

log events: `TRIPLE_RECHECK` + `CANCEL` หรือ `KEEP`

### พฤติกรรมเมื่อเปิดไม่ครบ 3 (individual mode)

แต่ละตัวทำงานอิสระเหมือนเดิม:</p>
- Trend Recheck: cancel pending ทันทีถ้า trend ไม่ผ่าน
- PD Zone: cancel/close ทันทีถ้า fail
- RSI Fill Recheck: close position ทันทีถ้าไม่ผ่าน

## SL Guard

gate: `config.SL_GUARD_ENABLED` (default `True`)

แนวคิด:
- ป้องกันการเข้า order ฝั่งเดิมซ้ำหลังจากโดน SL หลายครั้ง
- แยก state ตาม `(tf, side)` — BUY guard ไม่กระทบ SELL และกลับกัน

### Flow การทำงาน

1. `notifications.py` detect SL hit → เรียก `_sl_guard_record_sl(tf, side)`
2. เมื่อ `count >= SL_GUARD_COUNT` → guard active
3. **Guard active:**
   - `scanner.py`: block BUY/SELL LIMIT ใหม่ + เก็บ signal ไว้ใน `blocked_signals`
   - `check_cancel_pending_orders()`: ยกเลิก pending ที่ราคาเข้าใกล้ ≤ `SL_GUARD_NEAR_POINTS` pt
4. **Unblock:** `_sl_guard_check_unblock()` เช็คทุก cycle — ถ้า swing Low ใหม่เกิด (BUY) หรือ swing High ใหม่เกิด (SELL) หลัง block → deactivate
5. **หลัง deactivate:** `_sl_guard_place_retries()` ใน `scan_one_tf` re-place blocked signals ทันที
   - validate entry ยังไม่ผ่านตลาด, SL ไม่ถูก breach
   - count reset เป็น 0

### State

- `_sl_guard_state[(tf, side)]`:
  - `count`: จำนวน SL hits สะสม
  - `active`: guard เปิดอยู่หรือเปล่า
  - `blocked_since_bar`: unix timestamp ตอน activate
  - `swing_ref`: swing low/high ณ เวลา activate (ใช้ตรวจ unblock)
  - `blocked_signals`: list ของ signals ที่ถูก block ระหว่าง active
  - `retry_signals`: พร้อม re-place (หลัง deactivate)

### Telegram

- Activate → "🛡️ SL Guard เปิดใช้งาน"
- Re-place → "🛡️ SL Guard: Re-place Order"
- Toggle ผ่าน Settings → Trend Filter → SL Guard

## Limit Guard

อยู่ใน flow ของ `check_cancel_pending_orders()`

แนวคิด:
- ยกเลิก pending limit ที่ห่างจาก position ปัจจุบันมากเกินไป

mode:
- `separate`: ดูเฉพาะ TF เดียวกัน
- `combined`: ดูทุก TF

หมายเหตุปัจจุบัน:
- `S10`, `S12`, `S13` ไม่เข้า `Limit Guard`

## Limit Sweep

ฟังก์ชัน:
- `check_limit_sweep()`
- `_run_limit_sweep_followup()`

แนวคิด:
- เมื่อแท่ง adverse ปิดทะลุโครงสร้างสำคัญ
- ปิด position
- และอาจจัดการ pending order ที่เกี่ยวข้องต่อ

S8 follow-up:
- ถ้าใช้ `LL/HH`
- ต้องเลือก level ที่ยัง valid
- ถ้าแท่งปิดทะลุ `LL/HH` ไปแล้ว ต้องไล่หาตัวถัดไป

## SL/TP Audit และ Logging

เครื่องมือหลัก:
- `_audit_sltp_event()`
- `_notify_sltp_audit()`
- `_notify_sltp_audit_v2()`

ใช้เมื่อ:
- trail SL
- protect SL
- เปลี่ยน TP
- ตรวจย้อนหลังว่าใครแก้ SL/TP

ไฟล์ log:
- `logs/debug/sltp_audit.log` (path กำหนดโดย `SLTP_AUDIT_DIR = os.path.join(LOG_DIR, "debug")`)

## หมายเหตุสำคัญ

- Telegram อาจมาช้ากว่า event จริง
- เวลาตามรอยปัญหา ให้เช็ก `bot.log` ก่อนเสมอ
- ถ้างานเกี่ยวกับ SL/TP ซับซ้อน ให้ดูทั้ง log และ state map ประกอบกัน
