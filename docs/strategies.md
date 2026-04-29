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

## ท่าที่ 1: กลืนกิน / ตำหนิ / ย้อนโครงสร้าง

ไฟล์หลัก: `strategy1.py`

แนวคิด:
- ใช้แท่ง `[2]`, `[1]`, `[0]` เป็นแกน
- มีทั้งฝั่ง `BUY` และ `SELL`
- ใช้ `engulf_min_price()` เป็นระยะขั้นต่ำของคำว่า “กลืนกิน”
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
- `[1]` เขียวแบบ “ตำหนิ” คือไส้/ช่วงแท่งเข้าไปใน zone ของแท่ง `[2]`
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
- swing ที่กลืนต้องอยู่ “ใน gap” จริง

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
- ปัจจุบันมี logic พิเศษเรื่อง “ตั้ง limit ก่อน แล้วค่อย arm SL” ตาม flow ของระบบ

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

### BUY

- หา `Swing Low` ปัจจุบัน และ `Swing Low` ก่อนหน้า
- เอาค่า RSI ที่ bar ของ swing low ทั้งสองจุดมาเทียบกัน
- ต้องเป็น `RSI low ปัจจุบัน > RSI low ก่อนหน้า`
- และราคาเข้าได้ 2 แบบ:
  - `HL`: low ปัจจุบันสูงกว่า low ก่อนหน้า
  - `LL แต่ยังไม่ MSS`: low ปัจจุบันต่ำกว่า low ก่อนหน้า แต่ close ล่าสุดยังไม่ปิดเหนือ swing high ก่อนหน้า
- ถ้าผ่าน จะตั้ง `BUY STOP = swing high ก่อนหน้า + buffer`
- `SL = swing low ปัจจุบัน - buffer`
- `TP = swing TP` ถ้าหาได้ ไม่งั้น fallback `RR 1:1`

### SELL

- สลับด้านจาก BUY
- ต้องเป็น `RSI high ปัจจุบัน < RSI high ก่อนหน้า`
- และราคาเข้าได้ 2 แบบ:
  - `LH`: high ปัจจุบันต่ำกว่า high ก่อนหน้า
  - `HH แต่ยังไม่ MSS`: high ปัจจุบันสูงกว่า high ก่อนหน้า แต่ close ล่าสุดยังไม่ปิดต่ำกว่า swing low ก่อนหน้า
- ถ้าผ่าน จะตั้ง `SELL STOP = swing low ก่อนหน้า - buffer`
- `SL = swing high ปัจจุบัน + buffer`
- `TP = swing TP` ถ้าหาได้ ไม่งั้น fallback `RR 1:1`

### หมายเหตุของท่า 9

- ตอนนี้ถือว่า “ยืนยัน setup” ตอน scan เจอ divergence
- ส่วน “ยืนยันเข้าไม้” จริง คือเมื่อราคามาชน stop order
- ถ้า pane RSI บน MT5 กับ bot ให้ค่าไม่ตรงกัน ให้เช็ค period ก่อนเป็นอย่างแรก
