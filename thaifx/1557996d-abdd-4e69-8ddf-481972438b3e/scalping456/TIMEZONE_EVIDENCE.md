# Timezone evidence

อัปเดต 8 ตุลาคมหลังตั้งค่า Vantage: raw tick/bar epoch ของ terminal ใหม่เท่ากับ source raw clock จาก historical alignment และ live anchor แสดง +3h จาก UTC จริง จึง query Vantage = inferred UTC+3h และ normalize `time_msc-10,800,000` ต่างจาก IUX query shift+1h เดิม เก็บหลักฐานดิบที่ `data/vantage_tick_clock_20261008/` และดู `VANTAGE_FEED_REPORT.md` ห้ามแก้ raw/web time ทับหรือบวก/ลบ cache ซ้ำ

## วิธีจดเวลาโดยไม่ปนกัน

- ถ้าหน้าเว็บแสดง `08:04` ให้จด `08:04` ตามเดิมในช่อง **เวลาที่หน้าเว็บแสดง** ไม่แก้ทับด้วยเวลา UTC
- เก็บค่า API ดิบแยกต่างหาก เช่น ticket `1716728516` มี `open_time = 2026-10-08T01:04:15+00:00` ค่านี้มาจาก ThaiFXBook ไม่ใช่ชาร์ต IUX ของผู้ใช้
- เวลา UTC สำหรับเทียบราคาเป็นค่าที่แปลงเพิ่มอีกช่อง ต้องระบุที่มาและสมมติฐาน offset ไม่ลบ 7 ชั่วโมงจากเวลาเว็บโดยถือว่าเป็นเวลาประเทศไทยจริงโดยอัตโนมัติ
- `UTC+6` เป็นเขตเวลาของชาร์ต IUX ตามข้อตกลงใน repo ไม่ใช่คำสั่งให้บวก 6 ชั่วโมงกับเลขที่อ่านจากชาร์ต

ตัวอย่าง **เฉพาะกรณีอ่าน `01:04` จากชาร์ต IUX UTC+6 จริง**:

```text
IUX chart 01:04 UTC+6 -> UTC 19:04 วันก่อน -> Bangkok 02:04 UTC+7
```

ดังนั้น `01:04 + 6 ชั่วโมง = 07:04` และ `01:04 + 7 ชั่วโมง = 08:04` ถูกต้องทางเลขคณิต แต่การเลือกว่าจะบวก/ลบเท่าไรต้องรู้ก่อนว่า `01:04` มาจากชาร์ต, API หรือหน้าเว็บ

## ข้อสรุป

ผลเทียบราคาในชุดข้อมูลนี้สนับสนุนการตีความว่าเวลาใน API ของ ThaiFXBook ซึ่งเขียนท้ายว่า `+00:00` มีตัวเลขนาฬิกาภายในเป็นเวลา server **UTC+3** ไม่ใช่ UTC จริง ส่วนเวลาหน้าเว็บ `08:04` เมื่อเทียบกับ raw `01:04` ต่างกัน 7 ชั่วโมง หากสมมติฐาน UTC+3 นี้ถูกต้อง เวลาเว็บจะมากกว่า Bangkok จริง 3 ชั่วโมง ข้อนี้เป็นการอนุมานจากการเทียบราคา ไม่ใช่การยืนยัน timezone อย่างเป็นทางการจาก broker

สูตรที่ใช้กับชุด orders นี้:

```text
actual UTC       = ThaiFXBook raw - 3 ชั่วโมง
IUX chart UTC+6  = ThaiFXBook raw + 3 ชั่วโมง
Bangkok UTC+7    = ThaiFXBook raw + 4 ชั่วโมง
web display      = ThaiFXBook raw + 7 ชั่วโมง  (ค่าที่หน้าเว็บแสดง แต่ไม่ใช่เวลาตลาดจริง)
```

ถ้าจดเวลาจากหน้าเว็บเป็น `08:04`:

```text
web display 08:04
actual Bangkok 05:04  (ลบ 3 ชั่วโมง)
IUX chart 04:04       (ลบ 4 ชั่วโมง)
actual UTC 22:04 ของวันก่อน (ลบ 10 ชั่วโมง)
```

ดังนั้นห้ามนำ `08:04` ไปถือว่าเป็น Bangkok จริงสำหรับดึง OHLC/Tick โดยตรง

## หลักฐานตัวอย่าง

[Vantage Help Center](https://global.vantagehelpcenter.com/hc/en-us/articles/10955835737871-How-do-I-change-the-time-displayed-on-the-trading-platform) ระบุว่า server ใช้ GMT+2 และเปลี่ยนเป็น GMT+3 ระหว่าง daylight saving time กฎทั่วไปนี้สนับสนุน offset ที่เทียบราคาได้ แต่ไม่ได้ยืนยันเองว่า ThaiFXBook serialize timestamp ของบัญชีนี้อย่างไร จึงยังเก็บ raw แยกจากค่า inferred UTC

Ticket `1716728516`:

- ThaiFXBook raw: `2026-10-08 01:04:15+00:00`
- ราคาเปิดจาก Vantage: `4113.030`
- ถ้า raw เป็น UTC จริง ราคาจาก independent Exness `XAUUSDm` เวลา `01:04:15 UTC` อยู่ราว `4131.800` ต่างประมาณ `$18.77`
- เมื่อเลื่อน raw กลับ 3 ชั่วโมงเป็น `2026-10-07 22:04:15 UTC` ราคา Exness อยู่ราว `4112.823` ต่างเพียง `$0.207`

การตรวจแบบสุ่มครอบคลุม 7,577 orders หลายวันให้ผล:

- ใช้ raw เป็น UTC: ราคา order อยู่ในช่วง High/Low ของ M1 เดียวกันเพียง `4.33%`
- ใช้ raw ลบ 3 ชั่วโมง: อยู่ในช่วง High/Low `95.26%`

ความต่างที่เหลืออาจเกิดจากคนละ broker, spread, bid/ask, timestamp/execution latency หรือเหตุอื่น ต้องตรวจเพิ่ม ไม่สรุปว่าเป็นสาเหตุใดโดยไม่มีหลักฐานราย event

## ตัวอย่าง `01:04`

| ความหมาย | เวลา |
|---|---:|
| ThaiFXBook raw / Vantage server UTC+3 | 01:04 |
| UTC จริง | 22:04 วันก่อน |
| IUX chart UTC+6 | 04:04 |
| Bangkok UTC+7 | 05:04 |
| หน้า ThaiFXBook render | 08:04 (ผิดจากเวลาจริง +3h) |

## IUX proxy feed alignment สำหรับ replay

ผลใน `data/time_alignment_iux.json` ทดสอบทุก 31,123 core orders: query IUX ด้วย inferred UTC+1h ให้ราคาอยู่ใน M1 range 94.0937% ของ bars ที่หาได้ ส่วนไม่เลื่อน query ให้เพียง 6.51453% นี่เป็น empirical alignment ของ historical feed ใน terminal นี้ ไม่ใช่การเปลี่ยนข้อตกลง IUX chart UTC+6

ไฟล์ `proxy_ticks_iux_shift1/*.npz` ลบ query shift 1h กลับจาก `time_msc` ก่อน replay แล้ว จึงใช้ canonical/inferred UTC ได้ตรง ๆ ห้ามบวกหรือลบซ้ำเมื่อนำ cache นี้ไปวิเคราะห์

