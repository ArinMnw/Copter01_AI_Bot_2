# กลยุทธ์

เอกสารนี้สรุปเงื่อนไขเข้า order ของแต่ละท่าในภาพรวม โดยยึดตาม logic ปัจจุบันของโค้ด

## รหัสท่า

- `1`: กลืนกิน / ตำหนิ / ย้อนโครงสร้าง
- `2`: FVG
- `3`: DM / SP / Marubozu
- `4`: นัยยะสำคัญ FVG
- `5`: optional / rarely used
- `6`: trail logic สำหรับ position จากท่า 2/3
- `7`: S6i independent swing logic
- `8`: กินไส้ Swing
- `9`: RSI Divergence
- `10`: CRT TBS (Candle Range Theory + Three Bar Sweep)
- `11`: Fibo S1
- `12`: Range Trading

## ท่าที่ 1: กลืนกิน / ตำหนิ / ย้อนโครงสร้าง

ไฟล์หลัก: `strategy1.py`

แนวคิด:
- ใช้แท่ง `[2]`, `[1]`, `[0]` เป็นแกน
- มีทั้งฝั่ง `BUY` และ `SELL`
- ใช้ `engulf_min_price()` เป็นระยะขั้นต่ำของคำว่า "กลืนกิน"
- ถ้าเปิด `S1_ZONE_MODE = "zone"` จะต้องอยู่ใกล้ swing zone ด้วย

### Pattern A

BUY:
- `[2]` แดง
- `[1]` เขียว และ `Close[1] > High[2] + gap`
- `[0]` เขียว และ `Close[0] > High[1] + gap`
- body ของแท่ง `[1]` ต้องอย่างน้อย `35%`
- ถ้าใช้ zone mode ต้องใกล้ `Swing Low`

SELL:
- สลับสีตรงข้าม
- `[2]` เขียว
- `[1]` แดง และ `Close[1] < Low[2] - gap`
- `[0]` แดง และ `Close[0] < Low[1] - gap`
- body ของแท่ง `[1]` ต้องอย่างน้อย `35%`
- ถ้าใช้ zone mode ต้องใกล้ `Swing High`

### Pattern B

BUY:
- `[2]` แดง
- `[1]` เขียวแบบ "ตำหนิ" คือไส้/ช่วงแท่งเข้าไปใน zone ของแท่ง `[2]`
- body `[1] >= 35%`
- `[0]` เขียวกลืน `[1]`
- ถ้าใช้ zone mode ต้องใกล้ `Swing Low`

SELL:
- สลับสีตรงข้าม

### Pattern C

แนวคิด:
- เป็นชุดย้อนโครงสร้าง 3 แท่ง
- ใช้ logic เฉพาะของ `strategy1.py`
- อยู่ในท่า 1 เหมือนกัน แต่ไม่ใช่ pattern กลืนกินตรง ๆ แบบ A

### Pattern E

BUY:
- `[2]` แดง
- `[1]` แดง
- `[0]` เขียว
- `Close[0] > High[1] + gap`
- body `[0] >= 35%`
- ถ้าใช้ zone mode ต้องใกล้ `Swing Low`

SELL:
- สลับสีตรงข้าม
- `[2]` เขียว
- `[1]` เขียว
- `[0]` แดง
- `Close[0] < Low[1] - gap`
- body `[0] >= 35%`
- ถ้าใช้ zone mode ต้องใกล้ `Swing High`

### Pattern 4 แท่ง

- เป็น pattern ย่อยอีกแบบในท่า 1
- ใช้ code `P4`
- รายละเอียดขึ้นกับ logic ใน `strategy1.py`

### หมายเหตุของท่า 1

- comment ของ order มักใช้ code เช่น `PA`, `PB`, `PC`, `PD`, `PE`, `P4`
- ใช้ fallback `RR 1:1` เมื่อหา swing TP ที่เหมาะสมไม่เจอ
- มี WAIT reason ค่อนข้างละเอียด ใช้ช่วย debug ได้ดี

## ท่าที่ 2: FVG

ไฟล์หลัก: `strategy2.py`

แนวคิด:
- มองหา Fair Value Gap ระหว่าง `[2]`, `[1]`, `[0]`
- ตอนนี้ใช้ `ENGULF_MIN_POINTS` ด้วย โดย `[1]` ต้องกลืน `[2]` ให้เกิน gap ขั้นต่ำ

### BUY

- `[1]` ต้องเป็นแท่งเขียวและ `Close[1] > High[2] + gap`
- `[0]` ต้องยังไม่ปิด gap
  คือ `Low[0] > High[2]`
- ขนาด gap ต้องไม่เล็กเกินไป
- คำนวณ entry จากด้านในของ gap
- ถ้าแท่ง `[0]` เป็น marubozu จะเข้าโหมดรอ confirm แทนการตั้งทันที

### SELL

- สลับเงื่อนไขตรงข้าม
- `[1]` ต้องเป็นแท่งแดงและ `Close[1] < Low[2] - gap`
- `[0]` ต้องยังไม่ปิด gap
  คือ `High[0] < Low[2]`

### หมายเหตุของท่า 2

- เหตุผลย่อยของแท่ง `[0]` เช่น เขียว, แดง, กลืนกิน, ปฏิเสธราคา ถูกใช้ในข้อความแจ้งเตือน
- มีทั้ง mode ปกติและ mode parallel ตาม config ปัจจุบัน

## ท่าที่ 3: DM / SP / Marubozu

ไฟล์หลัก: `strategy3.py`

แนวคิด:
- ใช้ 3 แท่งหลัก `[2]`, `[1]`, `[0]`
- เน้นแท่งต้นทางมี body ชัด, แท่งกลางพัก, แท่งล่าสุดกลืนกลับ
- ใช้ `ENGULF_MIN_POINTS` เช่นกัน

### BUY

- `[2]` เขียว และ body อย่างน้อย `35%`
- `[1]` แดง หรือ doji
- `[0]` เขียว
- `Close[0] > High[1] + gap`

### SELL

- `[2]` แดง และ body อย่างน้อย `35%`
- `[1]` เขียว หรือ doji
- `[0]` แดง
- `Close[0] < Low[1] - gap`

### Marubozu Pending

- ถ้าแท่ง `[0]` เป็น marubozu จะไม่เข้า order ทันที
- ระบบจะส่งเป็น `WAIT` แล้วเก็บ `marubozu_pending`
- รอแท่งถัดไป confirm ตามทิศเดิมก่อน

## ท่าที่ 4: นัยยะสำคัญ FVG

ไฟล์หลัก: `strategy4.py`

แนวคิด:
- ต้องเป็น FVG ที่กลืน swing สำคัญจริง ไม่ใช่แค่ gap ธรรมดา

### BUY

- `[1]` เขียว และ `High[1] > High[2]`
- `[0]` ต้องยังไม่ปิด gap เช่น `Low[0] > High[2]`
- ต้องหา `Swing High` ก่อนหน้าให้เจอ
- `Close[1]` ต้องปิดเหนือ swing นั้น และห่างจาก swing อย่างน้อย `engulf_min_price()`
- swing ที่กลืนต้องอยู่ "ใน gap" จริง

### SELL

- สลับเงื่อนไขตรงข้าม
- `[1]` แดง และ `Low[1] < Low[2]`
- `[0]` ต้องยังไม่ปิด gap
- `Close[1]` ต้องปิดต่ำกว่า `Swing Low` ก่อนหน้า และห่างจาก swing อย่างน้อย `engulf_min_price()`

## ท่าที่ 5

- ยังไม่ใช่แกนหลักของระบบในตอนนี้
- ถ้าจะปรับหรือใช้งาน ควรเปิดอ่าน logic จริงก่อนทุกครั้ง

## ท่าที่ 6

- ไม่ใช่ท่าเข้า order แบบปกติ
- เป็น state machine สำหรับจัดการ position ต่อจากท่า 2/3
- logic หลักอยู่ใน `trailing.py`

## ท่าที่ 7 (S6i)

- เป็น swing logic อิสระ
- ใช้ state machine เช่นกัน
- สามารถตั้ง order ใหม่ได้ภายใต้เงื่อนไขของ swing และ pattern ตรงข้าม

## ท่าที่ 8: กินไส้ Swing

ไฟล์หลัก: `strategy8.py`

แนวคิด:
- ใช้ swing high และ swing low ที่หาได้จาก `strategy4.py`
- ตั้ง order ได้ทั้งสองฝั่งในรอบเดียว

### SELL

- ใช้ `Swing High`
- `Entry = High + 17% ของ range swing`
- `SL = High + 31% ของ range swing`
- `TP = Swing Low`
- ปัจจุบันมี logic พิเศษเรื่อง "ตั้ง limit ก่อน แล้วค่อย arm SL" ตาม flow ของระบบ

### BUY

- ใช้ `Swing Low`
- `Entry = Low - 17% ของ range swing`
- `SL = Low - 31% ของ range swing`
- `TP = Swing High`

### หมายเหตุของท่า 8

- ถ้าเป็น S8 ที่มาจาก `Limit Sweep` ต้องระวังบริบทของ `LL/HH`
- ห้ามใช้ swing ที่แท่งปิดทะลุผ่านไปแล้ว
- ถ้า pending fill ก่อน arm SL ต้องมี fallback ไปตั้ง SL ให้ position หลัง fill

## ท่าที่ 9: RSI Divergence

ไฟล์หลัก: `strategy9.py`

แนวคิด:
- ใช้ `RSI(close)` ชุดเดียวกับ `mql5/RSIDivergencePane.mq5`
- ค่า default ปัจจุบันคือ `RSI(14)`
- ไม่ใช้ pivot divergence แบบ indicator สำเร็จรูป
- ใช้ `swing ราคา` ของระบบเดิม แล้วเอาค่า RSI ที่ bar เวลาเดียวกับ swing นั้นมาเทียบ
- เจอ setup แล้วจะตั้ง `BUY STOP` หรือ `SELL STOP` ทันที

### แหล่งข้อมูล RSI

- period มาจาก `config.RSI9_PERIOD`
- applied price มาจาก `config.RSI9_APPLIED_PRICE`
- ตอนนี้ล็อกให้ตรงกับ pane บน MT5 เป็น `close`
- ถ้าจะเปลี่ยน period ของท่า 9 ต้องเปลี่ยนทั้ง `config.py` และ compile `RSIDivergencePane.mq5` ใหม่ให้ตรงกัน

### Pivot detection

- ใช้ pivot RSI แบบเดียวกับ TV / `RSIDivergencePane.mq5`
- pivot left = `RSI9_LEFT` (default 5), pivot right = `RSI9_RIGHT` (default 5)
- หา pivot คู่ติดกัน (immediate previous pivot only) ภายใน range `RSI9_RANGE_MIN..RSI9_RANGE_MAX`

### Divergence types

รองรับ 4 แบบ ผ่าน toggle ใน config:

- `RSI9_PLOT_BULLISH` (default ON) — Regular Bullish: price LL + RSI HL → BUY
- `RSI9_PLOT_BEARISH` (default ON) — Regular Bearish: price HH + RSI LH → SELL
- `RSI9_PLOT_HIDDEN_BULLISH` (default OFF) — Hidden Bullish: price HL + RSI LL → BUY
- `RSI9_PLOT_HIDDEN_BEARISH` (default OFF) — Hidden Bearish: price LH + RSI HH → SELL

ปุ่ม Telegram รวมแล้วเหลือ 2 ปุ่ม: **Regular** (Bullish + Bearish) และ **Hidden** (Bullish + Bearish)

### Entry / SL / TP

ปัจจุบันใช้ `LIMIT @ midpoint` ของแท่งที่ pivot ปัจจุบันชี้:

BUY (BUY LIMIT):
- `entry = (cur_high + cur_low) / 2` ของแท่ง pivot ปัจจุบัน
- `SL = cur_low - SL_BUFFER`
- `TP` = swing TP / fallback RR 1:1

SELL (SELL LIMIT):
- `entry = (cur_high + cur_low) / 2` ของแท่ง pivot ปัจจุบัน
- `SL = cur_high + SL_BUFFER`
- `TP` = swing TP / fallback RR 1:1

`order_mode = "limit"` — ต่างจากเวอร์ชันเก่าที่เป็น STOP

### หมายเหตุของท่า 9

- setup_sig ใช้แค่ pivot identity (`tf|signal|div_type|pivot_prev_time|pivot_cur_time`) เพื่อกัน duplicate
- ถ้า pane RSI บน MT5 กับ bot ให้ค่าไม่ตรงกัน ให้เช็ค period ก่อนเป็นอย่างแรก
- code Python (`strategy9.py`) กับ MQL5 indicator ทำงานแยกกัน แต่ใช้สูตรเดียวกัน → ให้ผลตรงกันบน RSI ชุดเดียว
- เวลาเทียบ chart: log ใน `bot.log` เป็น BKK, MT5 chart เป็น broker time

## ท่าที่ 10: CRT TBS

ไฟล์หลัก: `strategy10.py`

แนวคิด:
- รวม Candle Range Theory (CRT) + Three Bar Sweep (TBS)
- หา pattern ที่ราคาทำ liquidity sweep แล้วกลับด้าน
- bypass trend filter (`if sid != 10: trend_allows_signal()` ใน `scanner.py`)
- default `active_strategies[10] = True` (ปุ่ม "เปิดทั้งหมด" ไม่กระทบ)

### Mode: bar count

`CRT_BAR_MODE`:
- `2bar`: ดู 2 แท่ง — แท่งกลาง sweep + แท่งล่าสุดยืนยัน
- `3bar`: ดู 3 แท่ง — มีแท่ง setup เพิ่มก่อน sweep

### HTF detect filters

- TF restriction: HTF mode ใช้ M15+ เท่านั้น; MTF mode ใช้ทุก TF (เพราะ LTF ตีจาก HTF อยู่แล้ว)
- `CRT_MIN_RANGE_POINTS` (default `200` × points_scale) — กรอง swing range เล็กเกิน
- `CRT_SWEEP_DEPTH_PCT` (default `0.10`) — แท่ง sweep wick ต้องลึกอย่างน้อย X% ของ parent range
- `CRT_SL_BUFFER_POINTS` (default `50` × points_scale)

### Mode: entry timing

`CRT_ENTRY_MODE`:

**`htf` — Entry Model 2 (Confirmation Market):**
- เจอ HTF CRT → market BUY/SELL ทันที (เมื่อ HTF sweep candle ปิดยืนยัน)
- entry = HTF sweep_close.close (2bar) / confirm.close (3bar)
- SL = HTF sweep level ± buffer
- TP = HTF parent opposite

**`mtf` (default) — Entry Model 3 (LTF Confirmation, CRT TBS Classic):**

หลัง HTF arms → ทุก scan tick (5s) วน LTF rates หา trigger:

```
Phase 1: Failed-push (pattern confirmation)
  BUY  (HTF sweep low):  LTF RED  + close < HTF parent.low
  SELL (HTF sweep high): LTF GREEN + close > HTF parent.high
  เริ่มค้นจาก bar.time > armed_at

Phase 2: Body engulf 2-bar (entry trigger search)
  BUY engulf:  prev RED + curr GREEN + curr.close > prev.open
  SELL engulf: prev GREEN + curr RED + curr.close < prev.open
  ค้นต่อจาก phase1_idx + 1
  (concept จาก S1 — ไม่เรียก S1 จริง)

Models (คำนวณพร้อมกันหลังเจอ Phase 2):
  #1 Order Block — RECOMMENDED
       SELL: ย้อนหา GREEN bar → entry = OB.open
       BUY:  ย้อนหา RED   bar → entry = OB.open
  #2 FVG 90% (concept S2 — ไม่เรียก S2 จริง)
       3-bar imbalance: B1=engulf-2, B3=engulf
       Bullish FVG (BUY):  B3.low > B1.high → entry @ 90% deep ใน gap
       Bearish FVG (SELL): B1.low > B3.high → entry @ 90% deep ใน gap
  #3 MSS — confirmation only (log)
       SELL: lowest low ใน range / BUY: highest high

Search range ของ Model 1/3: bar.time > armed_at ถึง engulf_idx-1
                              (ไม่ใช้ lookback คงที่ — boundary คือ HTF sweep open)
```

**Entry priority:**
- ใช้ Model 1 ก่อน → ถ้า None → fallback Model 2 → ถ้า None → ไม่เข้า
- Model 3 = log เท่านั้น

**Order properties:**
- `order_mode = "limit"` — รอราคา retrace มาแตะ entry
- SL = HTF sweep level ± buffer (= `state["sl_target"]`)
- TP = HTF parent opposite (= `state["tp_target"]`)
- Validate `BUY: sl < entry < tp` / `SELL: tp < entry < sl`

**LTF mapping (HTF → LTF):**
- `D1/H12 → M15`
- `H4 → M5`
- `H1/M30/M15 → M1`

**State management:**
- `_armed_states[htf_tf]` save/restore ผ่าน `bot_state.json` (key `s10_armed_states`)
- `armed_at` = HTF sweep candle's open time
- expiry = `armed_at + 2 × htf_secs` (= 1 HTF bar หลัง HTF close)

### Comment / Pattern code

| Mode | Pattern ตัวอย่าง | Comment |
|---|---|---|
| HTF 2bar | `... — Sweep Low (2bar)` | `Bot_M30_S10_CRT` |
| HTF 3bar | `... — Sweep High (3bar)` | `Bot_H1_S10_CRT` |
| MTF | `... — MTF [M30→M1] Model1` | `Bot_[M30-M1]_S10_CRT` |
| MTF | `... — MTF [H4→M5] Model2` | `Bot_[H4-M5]_S10_CRT` |

### Telegram message

แสดง HTF candles (CRT detected) ก่อน LTF candles (trigger):
```
📍 HTF M30 (เจอ CRT):
🟢 แท่ง[1]: O:... H:... L:... C:... <time>
🟢 แท่ง[0]: O:... H:... L:... C:... <time>
📍 LTF M1 (trigger):
🔴 แท่ง[2]: ...
🟢 แท่ง[1]: ...
🔴 แท่ง[0]: ... ← engulfing bar
```

Reason log แสดงราคา Model 1, 2, 3 ทั้งหมด + ระบุ Model ที่ใช้

## ท่าที่ 11: Fibo S1

ไฟล์หลัก: `strategy11.py`

แนวคิด:
- Hook ติดท่าที่ 1 — เมื่อ S1 fire BUY/SELL ให้ลง anchor บนแท่งสีตรงกับ direction (BUY=green ตัวล่าสุด, SELL=red ตัวล่าสุด)
- ตี Fibo บน anchor: BUY → `1=high, 0=low` | SELL → `1=low, 0=high`
- รอราคา wick แตะ trigger level → ตั้ง LIMIT
- default `active_strategies[11] = False`

### Fibo grid (`FIBO_LEVELS`)

| level | label |
|---|---|
| -1.31 | Liquidity day |
| -0.95 | Liquidity m5 |
| -0.31 | XXL |
| -0.17 | XL |
| 0 | 0 |
| 0.242 | KRL |
| 0.382 | 0.382 |
| 0.5 | 50% |
| 0.57 | 60% |
| 1 | 1 |
| 1.617 | KRH1 |
| 3.097 | KRH2 |
| 5.165 | KRH3 |
| 7.044 | Run Engulfing |
| 7.467 | RUN |
| 8.237 | X Divergence |

### Trigger / Entry pairs

| Pattern | Trigger (wick แตะ) | Entry LIMIT |
|---|---|---|
| 1 | KRH1 (1.617) | 50% (0.5) |
| 2 | KRH2 (3.097) | 50% (0.5) |
| 3 | KRH3 (5.165) | KRH1 (1.617) |

- TP = `7.044` (Run Engulfing) ทุก pattern
- SL = `-0.31` (XXL) ทุก pattern
- Recovery = `-0.95` (Liquidity m5) — phase 2 ยังไม่ implement

### Touch detection

- BUY: `last_high >= trigger_price`
- SELL: `last_low <= trigger_price`

### State

- `_s11_state[tf_name]` per-TF: `{direction, anchor_high, anchor_low, anchor_time, phase, triggered_level}`
- phase: `armed` (รอ touch) → `triggered` (ออก order แล้ว)
- ไม่ persist (reset ทุกครั้งที่ restart — รอ S1 fire ใหม่)

### Comment / Pattern code

| Pattern | comment ตัวอย่าง |
|---|---|
| 1 | `Bot_H1_S11_KRH1_50` |
| 2 | `Bot_H1_S11_KRH2_50` |
| 3 | `Bot_H1_S11_KRH3_KRH1` |
| fallback | `Bot_H1_S11_FIBO` |

## ท่าที่ 12: Range Trading

ไฟล์หลัก: `strategy12.py`

แนวคิด:
- ระบุ range ด้วย swing high และ swing low บน M5
- แบ่ง range เป็น buy zone (ใกล้ swing low) และ sell zone (ใกล้ swing high)
- ตั้ง limit order หลายชั้นใน zone ที่เหมาะสม
- จัดการ order หลาย ticket พร้อมกันภายใต้ `S12_ORDER_COUNT`
- default `active_strategies[12] = True`
- ปุ่ม "เปิดทั้งหมด" ไม่กระทบ S12 (ต้องเปิด/ปิดรายตัว)

### Config หลัก

| key | ความหมาย |
|---|---|
| `S12_ORDER_COUNT` | จำนวน order สูงสุดต่อด้าน (default 3) |
| `S12_COOLDOWN_SECS` | เวลา cooldown หลัง SL hit (default 1800s = 30 นาที) |

### Cooldown

- หลัง SL hit ระบบตั้ง `_s12_state["last_sl_time"]` ผ่าน `s12_cleanup_tickets()`
- ระหว่าง cooldown S12 จะไม่เข้า order ใหม่
- `_s12_scan_status = {"cooldown": "⏳ S12 cooldown N นาที (หลัง SL)"}` ระหว่างนี้
- SCAN_SUMMARY จะไม่แสดง S12 block เลยระหว่าง cooldown

### Comment format

```
Bot_M5_S12_buy
Bot_M5_S12_sell
```

### State

- `_s12_state`: `{"last_sl_time": float}`
- `_s12_scan_status`: dict สรุปสถานะรอบปัจจุบัน (ดูรายละเอียดใน `runtime-state.md`)
- ไม่ persist ผ่าน `bot_state.json` (restart แล้วนับใหม่)
