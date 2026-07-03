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
- `13`: EzAlgo V5
- `14`: Sweep RSI
- `15`: Volume Profile POC + Absorption
- `16`: AMD x iFVG (Asian Range Sweep + Inversion FVG)
- `17`: Sweep Sniper (Triple-Confluence Mean Reversion — M1 only)

## ท่าที่ 1: กลืนกิน / ตำหนิ / ย้อนโครงสร้าง

ไฟล์หลัก: `strategy1.py`

แนวคิด:
- ใช้แท่ง `[2]`, `[1]`, `[0]` เป็นแกน
- มีทั้งฝั่ง `BUY` และ `SELL`
- ใช้ `engulf_min_price()` เป็นระยะขั้นต่ำของคำว่า "กลืนกิน"
- ถ้าเปิด `S1_ZONE_MODE = "zone"` ระบบจะยังยอมให้ตั้ง order ได้ก่อน แล้วค่อยใช้กฎ zone หลังจากมี pending หรือมี position แล้ว
- การเช็ก zone ของ S1 ปัจจุบันใช้ `min low` หรือ `max high` ของทุกแท่งใน pattern ไม่ได้อิงแค่แท่ง `[1]`

### S1 Zone Mode (behavior ปัจจุบัน)

- ขั้น detect pattern จะไม่ block setup เพราะหลุด zone แล้ว
- ถ้ายังเป็น pending และอยู่นอก zone -> ยกเลิก limit
- ถ้ายังเป็น pending และยังอยู่ใน zone -> ไม่ยกเลิก
- ถ้า fill แล้ว แต่อยู่นอก zone และ `profit < 0` -> ปิด position
- ถ้า fill แล้ว แต่อยู่นอก zone แต่ `profit >= 0` -> ไม่ปิด
- metadata ของ zone จะถูกแนบไปกับ setup ในชื่อ `s1_zone_meta`

### S1 Forward Confirm

- `S1` จะตั้ง order ไปก่อน
- จากนั้นรอดู `S2` หรือ `S3` ฝั่งเดียวกันใน TF เดียวกันภายใน 5 แท่งข้างหน้า
- ถ้ายังไม่ fill และครบ 5 แท่งแล้วไม่เจอ -> ยกเลิก pending
- ถ้า fill แล้วและครบ 5 แท่งแล้วไม่เจอ -> ปิด position
- ถ้าเจอแล้ว ไม่ว่าจะยัง pending หรือ fill แล้ว -> ไม่ทำอะไรต่อ

### Pattern A

BUY:
- `[2]` แดง
- `[1]` เขียว และ `Close[1] > High[2] + gap`
- `[0]` เขียว และ `Close[0] > High[1] + gap`
- body ของแท่ง `[1]` ต้องอย่างน้อย `35%`
- ถ้าใช้ zone mode ตัวอ้างอิงฝั่ง BUY จะดู `min low` ของแท่งใน pattern เทียบกับ `Swing Low`

SELL:
- สลับสีตรงข้าม
- `[2]` เขียว
- `[1]` แดง และ `Close[1] < Low[2] - gap`
- `[0]` แดง และ `Close[0] < Low[1] - gap`
- body ของแท่ง `[1]` ต้องอย่างน้อย `35%`
- ถ้าใช้ zone mode ตัวอ้างอิงฝั่ง SELL จะดู `max high` ของแท่งใน pattern เทียบกับ `Swing High`

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

- `S2` แบบปกติจะต้องเจอ `S1` / `S2` / `S3` ฝั่งเดียวกันย้อนหลังภายใน `S2_NORMAL_CONFIRM_LOOKBACK_BARS` แท่งก่อน จึงจะยอมตั้ง order
- `S2 parallel` ไม่ใช้กฎยืนยันย้อนหลังนี้

## ท่าที่ 3: DM / SP / Marubozu

ไฟล์หลัก: `strategy3.py`

แนวคิด:
- ใช้ 3 แท่งหลัก `[2]`, `[1]`, `[0]`
- เน้นแท่งต้นทางมี body ชัด, แท่งกลางพัก, แท่งล่าสุดกลืนกลับ
- ใช้ `ENGULF_MIN_POINTS` เช่นกัน
- ก่อนตั้ง order จริง `S3` จะย้อนดู `S1` / `S2` / `S3` ฝั่งเดียวกันย้อนหลังภายใน `8` แท่งก่อน

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

### No-Engulf Pending

- ถ้าแท่ง `[0]` ถูกทิศ (เขียว/แดง) แต่ **ยังไม่กลืนกิน** High/Low ของ `[1]`
- ระบบจะส่งเป็น `WAIT` แล้วเก็บ `marubozu_pending` พร้อม `source="noengulf"`
- รอแท่งถัดไปปิดถูกทิศและกลืน `[1]` → indices เลื่อน: `[3][2][1][0]` กลายเป็น setup ใหม่
- BUY: รอแท่งถัดไปปิดเขียว | SELL: รอแท่งถัดไปปิดแดง
- ใช้ handler เดียวกับ `check_s3_maru_pending()` ใน `scanner.py`

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
  (concept จาก S1 - ไม่เรียก S1 จริง)

Models:
  #1 Order Block — RECOMMENDED
       ค้นต่อหลังแท่ง Phase 1
       SELL: ย้อนหา GREEN bar → entry = OB.open
       BUY:  ย้อนหา RED   bar → entry = OB.open
  #2 FVG 90% (concept S2 — ไม่เรียก S2 จริง)
       ค้นต่อหลังแท่ง Phase 1
       3-bar imbalance: B1=engulf-2, B3=engulf
       gap ต้อง >= `engulf_min_price()`
       Bullish FVG (BUY):  B3.low > B1.high → entry @ 90% deep ใน gap
       Bearish FVG (SELL): B1.low > B3.high → entry @ 90% deep ใน gap
  #3 MSS — confirmation only (log)
       lookback ย้อนจากแท่ง Phase 1
       SELL: lowest low ใน range (armed_at, phase1_idx)
       BUY:  highest high ใน range (armed_at, phase1_idx)

Search range ของ Model 1/2: หลังแท่ง Phase 1
Search range ของ Model 3:   armed_at < bar.time < phase1.time
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

| Mode | Pattern โดยย่อ | Comment |
|---|---|---|
| HTF 2bar | `... BUY/SELL Sweep (2bar)` | `M30_S10` |
| HTF 3bar | `... BUY/SELL Sweep (3bar)` | `H1_S10` |
| MTF | `... MTF [M30→M1] Model1` | `[M30-M1]_S10_#1` |
| MTF | `... MTF [H4→M5] Model2` | `[H4-M5]_S10_#2` |

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

### Triple Scale-Out (TSO) interaction

- S10 ใช้ TSO **always-4-steps** ด้วย **formula พิเศษของ S10** (ตั้งแต่ 2026-05-22)
- lot รวมเสมอ = `base × 4` (XAU 0.04, BTC 0.16)
- formula: `[min(200pt,TP), min(300pt,TP), TP/2, TP]`
  - TP=100pt → [100, 100, 50, 100]
  - TP=500pt → [200, 300, 250, 500]
  - TP=1000pt → [200, 300, 500, 1000]
- ทำผ่าน `config.compute_tso_effective_steps(tp_orig_dist, sid="10")` ที่ `mt5_utils.py`

## Continuous re-trigger flow (S10 MTF, 2026-05-18)

- arm state ใหม่มี field: `pre_arm`, `fired_tickets`, `awaiting_choch`, `fire_count`
- Trigger เปลี่ยน: ต้องเจอ **Model 1 AND Model 2** (ก่อน Model 1 OR Model 2)
- fire 2 orders (entry Model 1 + entry Model 2) แล้ว register ใน `fired_tickets`
- arm **ไม่ถูก consume** หลัง fire — เก็บไว้ continuous
- เมื่อ ticket ปิด: TP hit → consume arm | SL ทั้งคู่ → reset (รอ CHoCH ถ้า pre_arm)
- ดู AGENTS.md > S10 CRT TBS > MTF mode — Continuous re-trigger flow

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
- หา range จาก pivot swing high/low บน M5 เป็นหลัก
- ถ้ายังหา pivot confirm ไม่พอ จะ fallback ไปใช้ raw high/low ตาม lookback
- แบ่ง range เป็น buy zone (ใกล้ swing low) และ sell zone (ใกล้ swing high)
- active zone จะใช้ breakout extreme แบบ sticky ให้สอดคล้องกับ `mql5/S12_RangeZone.mq5`
- เมื่อราคาทะลุ pivot เดิมแล้ว zone ใหม่จะค้างอยู่จนกว่าจะมี pivot ใหม่มายืนยัน ไม่ snap กลับทันที
- ใช้ limit order หลายชั้นใน zone เดียวกันได้
- จำนวน order ต่อชุดคุมด้วย `S12_ORDER_COUNT`
- default `active_strategies[12] = True`
- ปุ่ม "เลือกทั้งหมด" ไม่กระทบ S12 (ต้องเปิด/ปิดรายตัว)

### Config หลัก

| key | ความหมาย |
|---|---|
| `S12_ORDER_COUNT` | จำนวน order ต่อหนึ่งชุด (default 3) |
| `S12_COOLDOWN_SECS` | เวลา cooldown หลัง SL hit (default 1800s = 30 นาที) |

### Cooldown

- หลัง SL hit จะเก็บเวลาใน `_s12_state["last_sl_time"]` และ cleanup ticket ผ่าน `s12_cleanup_tickets()`
- ระหว่าง cooldown S12 จะไม่สร้าง order ใหม่
- `_s12_scan_status = {"cooldown": "⏳ S12 cooldown N นาที (หลัง SL)"}` ใช้เป็นข้อความสถานะ
- SCAN_SUMMARY จะไม่แสดง S12 block ระหว่าง cooldown

### Comment format

```text
M5_S12_...
```

### State

- `_s12_state`: `{"last_sl_time": float}`
- `_s12_scan_status`: dict สำหรับข้อความสถานะ scan (ดูเพิ่มใน `runtime-state.md`)
- มี persist ลง `bot_state.json` (restart แล้วยังจำได้)

## ท่าที่ 13: EzAlgo V5

ไฟล์หลัก: `strategy13.py`

แนวคิด:
- ใช้ `supertrend crossover` เป็นสัญญาณหลัก
- ใช้ config:
  - `S13_SENSITIVITY`
  - `S13_SUPERTREND_ATR`
  - `S13_STOP_ATR_LEN`
  - `S13_STOP_ATR_MULT`
  - `S13_TP1_RR`
  - `S13_TP2_RR`
  - `S13_TP3_RR`

### Signal

BUY:
- `close` ตัดขึ้นเหนือ supertrend

SELL:
- `close` ตัดลงใต้ supertrend

### Entry / SL / TP

- `entry` = ราคาปิดของแท่งสัญญาณ
- `SL`
  - BUY: `signal low - ATR(stop) × multiplier`
  - SELL: `signal high + ATR(stop) × multiplier`
- `TP`
  - `TP1 = 0.7R`
  - `TP2 = 1.2R`
  - `TP3 = 1.5R`

### Order flow

- ระบบจะเลือก mix ของ `market/limit` จากความสัมพันธ์ระหว่าง `current price` กับ `entry`
- BUY:
  - ถ้า `current price > entry`
    - เข้า `market 1 order`
    - `#3 -> TP3`
    - และตั้ง `limit 3 orders`
    - `L1 -> TP1`, `L2 -> TP2`, `L3 -> TP3`
  - ถ้า `current price <= entry`
    - เข้า `market 3 orders`
    - `#1 -> TP1`, `#2 -> TP2`, `#3 -> TP3`
    - และตั้ง `limit 1 order`
    - `L3 -> TP3`
- SELL:
  - ถ้า `current price < entry`
    - เข้า `market 1 order`
    - `#3 -> TP3`
    - และตั้ง `limit 3 orders`
    - `L1 -> TP1`, `L2 -> TP2`, `L3 -> TP3`
  - ถ้า `current price >= entry`
    - เข้า `market 3 orders`
    - `#1 -> TP1`, `#2 -> TP2`, `#3 -> TP3`
    - และตั้ง `limit 1 order`
    - `L3 -> TP3`
- ก่อนเข้าใหม่จะล้างฝั่งตรงข้ามของ `S13` ใน TF เดียวกันก่อน
- แยกการจัดการตาม TF (`M5 ล้าง M5`, `M15 ล้าง M15`)

### Standalone behavior

- `S13` เป็น standalone คล้ายแนวคิดของ S12
- ไม่เข้า flow กลางเหล่านี้:
  - `Entry Candle`
  - `Trail SL`
  - `Opposite Order`
  - `Trend Filter`
  - `Limit Guard`
- **ใช้** flow กลางเหล่านี้ (เปิดตั้งแต่ 2026-05-18):
  - `Limit Trend Recheck` — เช็ค trend ก่อน fill (cancel pending ถ้าสวนเทรนด์)
  - `Fill RSI Recheck` — เช็ค RSI หลัง fill (ปิด position ถ้าไม่ผ่านเกณฑ์)

### Triple Scale-Out (TSO) interaction — Always 4 Orders (ตั้งแต่ 2026-05-22)

- S13 ใช้ TSO **always-4-steps** สร้าง orders แยก **4 ชุดเสมอ** (ไม่ใช่ partial close)
- ใช้ general formula: `[min(200pt,TP), min(300pt,TP), min(600pt,TP), TP]`
  - TP=100pt → 4 orders ที่ [100, 100, 100, 100]
  - TP=500pt → 4 orders ที่ [200, 300, 500, 500]
  - TP=800pt → 4 orders ที่ [200, 300, 600, 800]
  - TP=1200pt → 4 orders ที่ [200, 300, 600, 1200]
- ทำใน `_place_s13_split_orders` (scanner.py) — ใช้ `config.compute_tso_effective_steps(tp_orig_dist)`
- **ไม่ขยาย lot** — แต่ละ order ใช้ `get_volume()` ปกติ (XAU 0.01, BTC 0.04)
- **ไม่ทยอยปิด** — ไม่ลงทะเบียนใน `scale_out_state` (เพราะ orders แยกอยู่แล้ว)
- **ไม่ถูกลบเมื่อ TSO toggle OFF** — S13 orders ไม่ถูก register ใน `scale_out_state`
- log event: `S13_TSO_TP_OVERRIDE` แสดง tp_orig_dist + effective_steps + orders count
- เมื่อ `SCALE_OUT_ENABLED = False`: ใช้ `tp_levels` จาก `strategy_13()` (RR-based ปกติ — 3 orders)

### Comment format

```text
M15_S13_EZ_#1
M15_S13_EZ_#2
M15_S13_EZ_#3
M15_S13_EZ_L1
M15_S13_EZ_L2
M15_S13_EZ_L3
```

หมายเหตุ: ตั้งแต่ TSO dynamic — จำนวน orders ของ S13 อาจไม่เป็น 3 เสมอ (1-4 ตาม TP เดิม)

## ท่าที่ 14: Sweep RSI

ไฟล์หลัก: `strategy14.py`

แนวคิด:
- ใช้ RSI หา reversal zone (LL/HH ของ RSI ในช่วง reversal bars)
- แล้วตรวจ pattern บนแท่งล่าสุดว่ามี Engulf หรือ Sweep ทะลุ zone นั้นหรือไม่
- เปิด market order ทันทีเมื่อเจอ pattern

### Config หลัก

| key | ความหมาย |
|---|---|
| `S14_RSI_PERIOD` | RSI period (default 14) |
| `S14_RSI_APPLIED_PRICE` | applied price (default `close`) |
| `S14_REVERSAL_LOOKBACK` | bars ย้อนหา reversal zone (default 50) |
| `S14_ENGULF` | เปิด/ปิด sub-pattern Engulf (default True) |
| `S14_SWEEP` | เปิด/ปิด sub-pattern Sweep (default True) |
| `S14_LL_USE_HHLL` | ใช้ HHLL HL/HH เป็น ref เพิ่ม (default False) |
| `S14_FLIP_ENABLED` | Flip: ปิดฝั่งตรงข้ามอัตโนมัติก่อนเปิดใหม่ (default True) |

### Sub-pattern

**Engulf** — แท่งล่าสุด close ทะลุ LL zone (BUY) หรือ HH zone (SELL)

**Sweep** — ไส้แท่งล่าสุดทะลุ zone แต่แท่งปิดกลับเข้ามา (rejection wick)

### Signal

BUY:
- หา `LL zone` จาก reversal bars ย้อนหลัง (`S14_REVERSAL_LOOKBACK`)
- Engulf: `close[0] < ll_val` หรือ Sweep: `low[0] < ll_val` + close กลับเหนือ ll_val

SELL:
- หา `HH zone` จาก reversal bars ย้อนหลัง
- Engulf: `close[0] > hh_val` หรือ Sweep: `high[0] > hh_val` + close กลับต่ำกว่า hh_val

### Order flow

- เปิด **market order** ทันที (ไม่มี pending)
- ก่อนเปิดจะเรียก `_clear_opposite_s14_exposure()` ถ้า `S14_FLIP_ENABLED = True`
  - ปิด S14 position ฝั่งตรงข้ามบน TF เดียวกัน (Flip logic)
  - ส่ง Telegram: `↔️ [TF] S14 Flip — ปิดฝั่ง BUY/SELL → เปิด SELL/BUY แทน`
- log: `S14_REVERSE_CLOSE` (ปิดสำเร็จ) / `S14_REVERSE_CLOSE_FAIL` (ปิดไม่สำเร็จ)

### Standalone behavior

- **bypass Trend Filter** (scan loop): `sid not in (9, 10, 13, 14)` ใน `scanner.py`
- **bypass RSI Fill Recheck**: `sid in (1, 9, 11, 14)` ใน `trailing.py`
- **bypass Fill Trend Recheck**: `sid in (9, 10, 14)` ใน `trailing.py`
- ไม่เข้า flow: `Entry Candle`, `Trail SL`, `Opposite Order`, `Limit Guard`, `SL Guard`
- **ใช้** PD Fibo Plus filter ใน scan loop (entry ต้องอยู่ใน Discount `<38.2%` / Premium `>61.8%` zone)

### Triple Scale-Out (TSO) interaction

- S14 ใช้ TSO ผ่าน `open_order_market()` เหมือนกัน (ตั้งแต่ 2026-05-26)
- `_scale_out_resolve_volume()` จะ scale lot ×4 ถ้า `SCALE_OUT_ENABLED = True`
- `_scale_out_register_ticket()` register state พร้อม `is_pending=True` (trailing.py จะ update entry จาก fill price จริง)

### Comment format

```text
M1_S14_engulf
M1_S14_sweep
```

### Telegram toggle

- Sub-option ใน `📋 เลือก Strategy` → ท่า 14:
  - `🟢 ท่า14: Flip (ปิดฝั่งตรงข้ามอัตโนมัติ)` — callback: `toggle_s14_flip`

## ท่าที่ 15: Volume Profile POC + Absorption

ไฟล์หลัก: `strategy15.py`

> 📊 **ผล order จริง (audit 11/06/2026, ช่วง 01/05-11/06)**: 63 ไม้ รวม +11.09 USD —
> ขาดทุนเกือบทั้งหมดมาจาก **ก่อน** fix 02-03/06 (BUY POC 0/7 ชนะ -59.92, M30 POC -55.71)
> หลัง STRICT_MODE ทำงาน (04/06 เป็นต้นมา): **~+56 USD, WR ~52%, เหลือเฉพาะ VAL/VAH** → คงค่าปัจจุบันไว้
> bucket ที่ดีที่สุด: `M1 BUY VAL` (+63.24 จาก 21 ไม้) | แย่สุดก่อน fix: `M1/M30 BUY POC`

แนวคิด:
- คำนวณ Volume Profile จาก `tick_volume` (proxy) ย้อนหลัง `S15_LOOKBACK` bars
- `POC` = ราคาที่มี volume สูงสุด (แม่เหล็กราคา), `VAH`/`VAL` = ขอบ Value Area 70%
- bucket_size = `ATR/10` → auto-scale ตาม instrument (XAU/BTC)
- ตรวจ **Absorption** ที่ POC/VAL/VAH 2 แบบ:
  - long wick sweep: ไส้ยาว ≥ `S15_ABSORPTION_WICK_PCT` × range แต่ปิดกลับเข้าโซน
  - 2-bar reversal: แท่งก่อนสวนสี → แท่งล่าสุดกลับทิศ
- standalone reversal — เข้าสวนเทรนด์โดยธรรมชาติ

### Entry / SL / TP

BUY (LIMIT ที่ POC หรือ VAL):
- `entry` = POC หรือ VAL (ต้อง `< close` กัน open_order skip)
- `SL` = `low - SL_BUFFER(atr)`
- `TP` = VAH/POC หรือ swing high | RR ≥ `S15_MIN_RR`

SELL (LIMIT ที่ POC หรือ VAH):
- `entry` = POC หรือ VAH (ต้อง `> close`)
- `SL` = `high + SL_BUFFER(atr)`
- `TP` = VAL/POC หรือ swing low | RR ≥ `S15_MIN_RR`

### Standalone behavior

- **bypass / skip filter ของระบบหลักทั้งหมด** (เหมือน S10/S12/S13/S14):
  - bypass Trend Filter (scan), skip Fill Trend Recheck, RSI Fill Recheck
  - skip PD Fibo Plus — VP ใช้ value-area zone เอง (ต่าง reference กับ swing-EQ)
  - skip Entry Candle, Trail SL, Opposite Order (ถือ BUY+SELL พร้อมกันได้), Limit Guard
  - **คงไว้**: SL Guard
- รองรับ Strong-Trend Block (อยู่ใน `STRONG_TREND_BLOCK_SIDS`, เปิดได้ถ้าต้องการกันไม้สวน strong trend)
- รองรับ MULTI (POC + VAL/VAH พร้อมกัน)
- **แยกตาม TF**: VP/POC/VAL/VAH คำนวณต่อ TF, order/pending/dedup แยกตาม TF

### Triple Scale-Out (TSO)

- **ใช้ TSO ได้ (ไม่ skip)** — S15 ผ่าน `open_order()` → `_scale_out_resolve_volume()` ซึ่ง skip แค่ `sid=13`
- เมื่อ `SCALE_OUT_ENABLED=True` → scale lot ×4 + ทยอยปิด 4 ขั้นผ่าน `check_scale_out_partial`
- MULTI (POC+VAL): แต่ละไม้ได้ ×4 อิสระ (volume cap เป็น per-order = `base×4` → ผ่านทุกไม้)

### Comment format

```text
M5_S15_POC
M5_S15_VAL
M5_S15_VAH
```

### Telegram toggle

- Sub-option ใน `📋 เลือก Strategy` → ท่า 15:
  - `🟢 ท่า15: VAL/VAH zones` — callback: `toggle_s15_val_vah`
  - `ท่า15: Lookback 50/100/200` — callback: `set_s15_lookback_*`
  - `ท่า15: RR 1:1 / 1.5 / 2:1` — callback: `set_s15_min_rr_*`

## ท่าที่ 16: AMD x iFVG

ไฟล์หลัก: `strategy16.py` — รันเฉพาะ **M1**

> ⚠️ **default OFF ตั้งแต่ 11/06/2026** — order จริง 08-10/06: **-510.54 USD จาก 35 ไม้** (WR 42.9%)
> และ sim A/B (24/05-11/06) ติดลบทุก config: เดิม -145.51 → fix ครบ (ดีสุด) -15.38
> เปิดใหม่ได้ผ่าน Telegram ถ้าอยากเก็บข้อมูลต่อ แต่ควรใช้ lot เล็กสุด

### Fixes 11/06/2026 (จากข้อมูล order จริง)

1. **One-shot dedup ต่อ (tf, side, killzone)** — เคส 09/06 19:46:52 มี SELL 13 ไม้ fill
   วินาทีเดียวกัน + รอบ 20:47 อีก 8 ไม้ (-226 USD ในนาทีเดียว) เพราะ scanner dup check
   เทียบ (entry, tp) แต่ TP คำนวณจาก ATR ที่ drift ทุกนาที → pending สะสม
   แก้: `s16_state["fired"]` key `tf|side|kz_start` — persist ข้าม restart, prune > 2 วัน
2. **SL buffer ของตัวเอง** `S16_SL_ATR_BUFFER=0.5` (เดิม `SL_BUFFER` กลาง = 2×ATR
   → แพ้เฉลี่ย -$30..-$49/ไม้ ขณะชนะ ~+$10) + `S16_MAX_RISK_ATR_MULT=4.0` skip setup risk กว้าง
3. sim (`sim_s16_backtest.py`) mirror ทั้ง 2 ข้อ + flag `S16_KZ_ONE_SHOT` สำหรับ A/B

แนวคิด (Accumulation–Manipulation–Distribution + Inversion FVG):
- **Asian Range**: คำนวณ High/Low จากช่วง `08:00–12:00 BKK` (ตีกรอบหลัง 12:00)
- **Killzones**: เทรดเฉพาะ London `14:00–17:00` และ NY `19:00–22:00` BKK
- **Sweep**: ราคาใน killzone ทะลุ Asian_Low (→ BUY) หรือ Asian_High (→ SELL)
- **Inversion FVG**: หลัง sweep ราคาพุ่งกลับ ปิดผ่าน FVG ฝั่งตรงข้าม → iFVG กลายเป็น entry zone
- **Entry**: LIMIT ที่ขอบ iFVG หรือ midline (`S16_ENTRY_MODE`)
- **SL**: ใต้/เหนือจุด sweep + `SL_BUFFER(atr)`
- **TP**: ขอบ Asian ฝั่งตรงข้าม หรือ fallback RR `S16_MIN_RR` (default 1.5)

### Standalone behavior (เหมือน S10/S14/S15)

- bypass Trend Filter (scan) + Sweep Filter block
- skip: Fill Trend Recheck, RSI Recheck, Entry Candle, Trail SL, Opposite Order, Limit Guard, Near Approach Cancel, PD Fibo pre-check
- อยู่ใน `STRONG_TREND_BLOCK_SIDS` (เปิดกันไม้สวน strong trend ได้)

### Config

- `S16_KILLZONES`, `S16_ASIAN_START_BKK="08:00"`, `S16_ASIAN_END_BKK="12:00"`
- `S16_MIN_RR=1.5`, `S16_ENTRY_MODE`
- `S16_SL_ATR_BUFFER=0.5`, `S16_MAX_RISK_ATR_MULT=4.0`, `S16_KZ_ONE_SHOT=True` (11/06/2026)
- state เก็บใน `s16_state` (asian_high/low, range_date, swept_high/low, **fired**) → persist ผ่าน `config.save_runtime_state()`

## ท่าที่ 17: Sweep Sniper

ไฟล์หลัก: `strategy17.py` — TF ที่อนุญาต: **M1, M30, H1** (`S17_ALLOWED_TFS`, ปรับ 03/07/2026)

⚠️ **ความเข้าใจที่ถูกต้อง**: win rate สูงของท่านี้มาจาก "TP สั้น + SL กว้าง" (RR ต่ำ ~0.17)
— 1 SL กิน TP ~6 ไม้ ไม่ใช่เวทมนตร์ ต้องคุม lot เล็กและยอมรับ tail risk

แนวคิด (4 ชั้น confluence — เข้าเฉพาะ setup ที่กรองครบ):
1. **Liquidity Sweep**: แท่ง signal ไส้ทะลุ low/high ของกรอบ `S17_LOOKBACK` (60) แท่ง
   แต่ **เปิดในกรอบ + ปิดกลับเข้ากรอบ** (stop hunt แล้วถูกปฏิเสธ — เช็ค open ด้วยตามบทเรียน sweep_filter)
2. **Rejection Wick**: ไส้ฝั่ง sweep ≥ `S17_WICK_MIN_PCT` (30%) ของ range แท่ง
3. **RSI Extreme**: RSI ≤ 32 (BUY) / ≥ 68 (SELL) ที่แท่ง signal
4. **PD Fibo Zone**: close อยู่ Discount (<38.2%) / Premium (>61.8%) ของกรอบ
+ **Session**: เทรดเฉพาะ Killzones London `14:00–18:00` / NY `19:00–23:00` BKK

Entry/Exit:
- **Entry**: LIMIT รอ retrace 61.8% ของแท่ง sweep (`S17_ENTRY_MODE="limit_618"`)
  ไม่ fill ภายใน `S17_LIMIT_CANCEL_BARS` (5) แท่ง → ยกเลิกผ่านกลไก `cancel_bars` กลาง
- **TP**: entry ± `S17_TP_ATR_MULT` (0.3) × ATR — สั้นมากโดยตั้งใจ
- **SL**: ใต้/เหนือไส้ sweep ∓ `S17_SL_ATR_BUFFER` (1.5, ปรับจาก 1.0 เมื่อ 03/07/2026) × ATR (buffer ของท่าเอง ไม่ใช้ `SL_BUFFER` กลาง)
- dedup: 1 ไม้/แท่ง signal + level cooldown `S17_LEVEL_COOLDOWN_BARS` (20) แท่ง (in-memory ไม่ persist)

### ผล backtest (sim_s17_backtest.py, spread $0.20/ไม้, lot 0.01)

| ช่วง | n | WR | P/L | แพ้ติดกันสูงสุด |
|---|---|---|---|---|
| M1 30 วัน (05-06/2026) | 146 | 92.5% | +$42.96 | 1 |
| M1 60 วัน (03-06/2026) | 248 | 91.1% | +$78.90 | 2 |
| M1 30 วัน spread $0.35 | 146 | 89.0% | +$21.06 | 5 |
| M1 60 วัน **bid/ask model** (04-07/2026) | 226 | 89.4% | +$86.20 | 2 |
| M1 60 วัน bid/ask **SLB=1.5** (default ใหม่ 03/07) | 226 | **92.5%** | **+$92.24** | 1 |

### WR tune 03/07/2026 (`S17_SL_ATR_BUFFER` 1.0 → 1.5)

- sweep entry mode × TP × SLB × RSI × wick บน M1 60d (bid/ask model): **SLB=1.5 ชนะทั้ง WR และ P/L**
  (SL กว้างขึ้นพลิก ~7 SL เป็น TP; แลก avgL −3.91 → −5.50/ไม้)
- validation: 30d WR 93.5% +$46.14 | 22d WR 96.0% +$30.28 | stress spread $0.35: WR 90.3% +$70.62
  | M30+H1 60d: **19/19 ชนะ +$94.00**
- ทางที่แพ้: `limit_786` แย่กว่า `limit_618` ทุก combo, RSI/wick เข้มขึ้น → n ลดและ P/L ลด
- **ทางเลือก WR สูงสุด**: `S17_TP_ATR_MULT=0.2` + SLB 1.5 → **WR 94.7%** แต่ P/L เหลือ +$56.70
- ทางเลือก `S17_TP_ATR_MULT=0.4`: WR 87.1% แต่กำไรมากกว่า (+$89.73 / 60 วัน, model เดิม)
- trend filter แบบ EMA slope (`S17_TREND_FILTER`) ตัด setup เกือบหมด → default OFF
- time stop (`S17_TIME_STOP_BARS`) ไม่ช่วยใน backtest → default 0

### Audit live 3 สัปดาห์แรก (11/06–03/07/2026)

- **live: 26 ไม้ WR 69.2% −$11.21** vs sim ช่วงเดียวกัน (bid/ask model): 50 ไม้ WR 90% +$22.70
- สาเหตุ gap ที่พบ:
  1. **Bot downtime**: สัปดาห์ W24 (15–21/06) live มี 0 ไม้ทั้งสัปดาห์ → เทรดหายไปเกือบครึ่ง
  2. **sid=None leak**: ไม้ 23/06 21:59 ถูก "Fill Trend Recheck" ปิด 3 วิหลัง fill ทั้งที่ S17 อยู่ใน skip list
     — race ตอน metadata ยังไม่ handoff → `position_sid.get()` คืน None → หลุด skip
     **แก้แล้ว**: `_resolve_pos_sid()` ใน `trailing.py` (4 ชั้น: memory → pending meta → tracked → parse comment)
     ใช้กับ RSI Recheck / Fill Trend Recheck / PD Fibo Plus fill
  3. SL Guard Group ปิด S17 อีก 3 ไม้ (by design — คงไว้)
- sim bid/ask fill model (03/07): BUY fill ต้อง `low ≤ entry−spread`, SELL TP ต้อง `low ≤ tp−spread`,
  SELL SL โดนเร็วขึ้น `high ≥ sl−spread` — ตัวเลขต่างจาก model เดิมเล็กน้อย (91.1% → 89.4%)
- **TF review (sim 60d bid/ask)**: M1 +86.20 (n=226) | M30 +28.78 (n=12) | H1 +42.02 (n=7)
  | **M5 −16.83 (ลบซ้ำ 2 รอบ) | M15 −4.67 + live ลบ** → `S17_ALLOWED_TFS = ["M1","M30","H1"]`
  (config เคยถูกขยายเป็น M1–H4 ระหว่างทาง — ดึง M5/M15/H4 ออกแล้ว)
- ⚠️ M30/H1 n ยังน้อยมาก (12/7 ไม้) และ avgL ต่อไม้ใหญ่กว่า M1 ~4 เท่า (−$19 ต่อไม้) — เฝ้าดูต่อ

### Standalone behavior (เหมือน S14/S15/S16)

- bypass Trend Filter (scan) + Sweep Filter block
- skip: Fill Trend Recheck, Pending Trend Check, RSI Recheck (เข้าที่ RSI extreme by design), PD Fibo Plus ทั้ง fill+pending (ใช้ PD ใน detect เอง), Entry Candle, Trail SL, Opposite Order, Limit Guard
- **ไม่เข้า TSO** — ออก lot คงที่ `AUTO_VOLUME` ต่อไม้ (backtest validate แบบ flat lot; TP สั้นเกินกว่าจะแบ่ง 4 step)
- **Compounding (03/07/2026 — แบบเดียวกับ S20.12)**: `S17_COMPOUNDING_ENABLED` (default OFF)
  → lot = balance × `S17_RISK_PCT`% / (ระยะ SL × contract), cap `S17_MAX_LOT`
  ส่งผ่าน `quant_lot_multiplier` ใน result → scanner คูณ base lot ตอน place order
  Telegram: `📋 เลือก Strategy` → ท่า 17 → ปุ่ม Compounding + Risk %
  sim 60d (risk 2%, เริ่ม $1,000): **$1,520.88 (+52.1%), max DD 4.3%**, lot 0.01-0.14
  (risk 5%: +161.4% แต่ DD 11.3%) — เทียบ fixed 0.01 = +$192.76
- อยู่ใน `STRONG_TREND_BLOCK_SIDS` (เปิดกันไม้สวน strong trend ได้)
- comment: `M1_S17_SNB` (BUY) / `M1_S17_SNS` (SELL)

### Config

- `S17_ALLOWED_TFS=["M1","M30","H1"]`, `S17_LOOKBACK=60`, `S17_RSI_BUY_MAX=32`, `S17_RSI_SELL_MIN=68`
- `S17_WICK_MIN_PCT=0.30`, `S17_TP_ATR_MULT=0.3`, `S17_SL_ATR_BUFFER=1.5`, `S17_MAX_RISK_ATR_MULT=4.0`
- `S17_ENTRY_MODE="limit_618"` (มี `"limit_786"` เพิ่ม 03/07 แต่ backtest แย่กว่า — ไม่ใช้), `S17_LIMIT_CANCEL_BARS=5`, `S17_PD_FILTER=True`
- `S17_SESSION_FILTER=True`, `S17_SESSIONS=[("14:00","18:00"),("19:00","23:00")]`
- `S17_LEVEL_COOLDOWN_BARS=20`
- `S17_COMPOUNDING_ENABLED=False`, `S17_RISK_PCT=2.0`, `S17_MAX_LOT=50.0` (persist ใน `bot_state.json`)

## Sweep Filter (override trend ก่อน trend filter ปกติ)

ไฟล์หลัก: `sweep_filter.py` — เรียกใน `scanner.trend_allows_signal()` **ก่อน** trend filter ปกติ

แนวคิด:
- `SWEEP_LOW`  → **Block SELL, Unblock BUY**  (ราคา sweep ใต้ swing low แล้ว bounce ขึ้น)
- `SWEEP_HIGH` → **Block BUY, Unblock SELL** (ราคา sweep เหนือ swing high แล้ว reject ลง)
- **swing low** = `HL`/`LL` ของ HHLL ที่ใหม่กว่า | **swing high** = `HH`/`LH` ที่ใหม่กว่า

### เงื่อนไข detect (⚠️ แก้ bug 05/06/2026)

SWEEP_LOW — ต้องครบทุกข้อ:
1. **`bar.open > ref_price`** ← bar ต้องเปิด **เหนือ** swing low ก่อน (ราคายังอยู่เหนือ ref)
2. `bar.low < ref_price` ← แล้วค่อย dip ลงต่ำกว่า swing low (= sweep จริง)
3. แท่งถัดไปปิดเขียว (`close > open`)
4. HTF confirm: HTF bar ที่ cover trigger มี `low < ref` + HTF ถัดไปปิดเขียว

SWEEP_HIGH — สมมาตร: `bar.open < ref_price` + `bar.high > ref_price` + แท่งถัดไปปิดแดง + HTF confirm

> **Bug เดิม**: ไม่เช็ค `bar.open` → bar ที่ trade อยู่ **ใต้** swing low อยู่แล้ว (เช่น downtrend ต่อเนื่อง)
> ก็ trigger SWEEP_LOW ได้ → BUY ถูก unblock ใน `bear_strong` โดยไม่ควร
> เช่น order #537988219 (BUY M5 ขณะ bear_strong) → fill → ขาดทุน
> **แก้**: เพิ่ม `bo > ref` (LOW) / `bo < ref` (HIGH) ทั้ง Pattern A และ B

### Persistence & Reset

- sweep active → คงสถานะไว้ จนกว่า `update_trend_and_check_reset()` จะ reset
- reset เมื่อ: trend เปลี่ยน (BULL↔BEAR↔SIDEWAY) หรือ (ตอน SIDEWAY) last swing label เปลี่ยน
- **Expiry** (เพิ่ม 05/06/2026): sweep หมดอายุหลัง `SWEEP_FILTER_EXPIRY_MIN` นาที (default 60)
  - กัน sweep เก่าค้าง override trend นานเกิน (เช่น order #537988219 sweep valid 03:30 แต่ยัง unblock ที่ 07:40)
  - `_sweep_ts[tf]` เก็บ unix ของ trigger bar → `get_sweep_state()` + `check_and_update()` เช็ค `_is_expired()` ก่อนคืนค่า
  - `SWEEP_FILTER_EXPIRY_MIN = 0` → ปิด expiry (persist จนกว่า trend/label เปลี่ยน — behavior เดิม)
- bypass: S9/S10/S13/S14/S15/S16/S17/S18/S19 ไม่ผ่าน sweep filter (standalone)

---

## Strategy 18: TJR / ICT Full-Confluence (Standalone)

ไฟล์หลัก: `strategy18.py`

นำ concept การเทรดของ TJR (ICT-based) มารวมเป็น 1 ท่า แบบ "ครบทุกชั้นจึงเข้า" เป็น Standalone strategy ไม่เช็คเทรนด์รวมหรือ PD Fibo ตรงกลาง

**ลำดับ Confluence (ต้องผ่านครบ):**
1. **Killzone**: เทรดเฉพาะช่วง London/NY (`S18_SESSIONS` default: 14:00-18:00, 19:00-23:00 BKK)
2. **HTF Bias**: เทรดตามทิศ HTF (`S18_HTF_MAP`)
3. **Liquidity Sweep**: ไส้กวาด swing low (BUY) / swing high (SELL) แล้วถูกปฏิเสธ (ทิ้งไส้)
4. **MSS (Market Structure Shift)**: หลัง sweep ราคา *close* ทะลุ internal structure ในทิศเดียวกับ bias
5. **Entry Zone**: ราคาอยู่ใน FVG หรือ Order Block ที่อยู่ในแถบ OTE (Optimal Trade Entry 62–79%)
6. **RSI Confirm**: (Optional) เช็คค่า RSI ประกอบ (`S18_RSI_FILTER`)
7. **Target & Risk**: RR เป้าหมายที่ `S18_MIN_RR` และ SL หลังไส้ sweep

---

## Strategy 19: ICT Advanced (Silver Bullet + Breaker + BPR) (Standalone)

ไฟล์หลัก: `strategy19.py`

ต่อยอดจาก S18 ด้วยเทคนิค ICT ขั้นสูง เป็น Standalone strategy ไม่เช็คเทรนด์รวมหรือ PD Fibo ตรงกลาง

**ลำดับ Confluence (ต้องผ่านครบ):**
1. **Silver Bullet Window**: เทรดเฉพาะหน้าต่างเวลาสั้นๆ (`S19_SILVER_BULLET_SESSIONS` default: 13:00-15:00, 21:00-23:00 BKK)
2. **HTF Bias**: เทรดตามทิศ HTF (`S19_HTF_MAP`)
3. **Power of 3 (AMD)**: ไส้ sweep ต้องเกิดภายใน Session เดียวกัน (Manipulation phase)
4. **Liquidity Sweep & MSS**: กวาดสภาพคล่องแล้วเบรกโครงสร้างเหมือน S18
5. **Advanced Entry Zone**: เลือกหา **Breaker Block**, **BPR (Balanced Price Range)**, หรือ **FVG** ที่ทับซ้อนในโซน OTE
6. **Dynamic Target (NDOG/Liq)**: ใช้ **NDOG (New Day Opening Gap)** หรือ Liquidity levels เป็นจุด TP แรก
