# Order-level analysis

วิเคราะห์จาก closed orders สาธารณะครบ 35,462 รายการ ช่วงเวลาจริงที่แก้ Vantage server offset แล้ว `2026-08-23T22:05:02Z` ถึง `2026-10-08T01:17:55Z`

## ภาพรวม

| Metric | Value |
|---|---:|
| Wins / losses / breakeven | 25,531 / 9,758 / 173 |
| Win rate | 71.9954% |
| Gross P/L | +$3,159,742.59 |
| Profit factor | 1.469895 |
| Expected gross/order | +$89.1022 |
| Median P/L | +$3.73 |
| Avg win / avg loss | +$387.14 / -$689.11 |
| Payoff ratio | 0.5618 |
| Median hold | 13 วินาที |
| P90 / P95 hold | 157 / 593 วินาที |
| Best / worst | +$149,450 / -$151,190 |

## XAUUSD+ core scalp

| Metric | Value |
|---|---:|
| Orders | 31,210 |
| Win / loss / breakeven | 22,733 / 8,309 / 168 |
| Win rate | 72.8388% |
| Profit factor | 1.4740 |
| Median hold | 11 วินาที |
| Q1 / Q3 hold | 6 / 23 วินาที |
| Average hold | 78.7 วินาที |
| Median winning pips | +37 |
| Q1 / Q3 winning pips | +14 / +80 |
| Median losing pips | -100 |
| Losses exactly -100 pips | 7,880 (94.84% ของ losses) |
| Orders with `[sl ...]` | 31,123 (99.72%) |

Average hold สูงกว่ามัธยฐานมากเพราะมี exceptional hedges ถือหลายชั่วโมง/หลายวัน; สำหรับ `[sl]` group average เหลือ 39.7 วินาที

### Lot regime

| Lot | Orders | ช่วงที่พบ (UTC) | Gross P/L | Win rate |
|---:|---:|---|---:|---:|
| 0.01 | 7,485 | 24 ส.ค. – 1 ก.ย. | +$1,540.91 | 73.41% |
| 1.00 | 1,910 | 31 ส.ค. – 1 ก.ย. | +$27,650.00 | 72.72% |
| 10.00 | 21,814 | 1 ก.ย. – 8 ต.ค. | +$3,132,960.00 | 72.65% |
| 0.40 | 1 | 30 ก.ย. | +$1,230.40 | — |

Win rate ใกล้กันทุก lot regime แต่ dollar P/L ระเบิดขึ้นจาก sizing ไม่ใช่ signal accuracy ที่ดีขึ้น

### ความถี่และเวลาทำงาน

- Median gap ระหว่าง XAU entries: 41 วินาที
- Q1 / Q3: 21 / 79 วินาที
- 56.89% ของ orders อยู่ในนาทีที่มี entry ตั้งแต่ 2 ไม้ขึ้นไป
- ชั่วโมง 04:00 BKK ไม่มี closed-order entry ในชุดนี้
- ปริมาณมากช่วง 22:00–00:59 BKK และ 10:00–12:59 BKK แต่ทุกชั่วโมงที่ active ยังมีกำไร gross ใน sample นี้
- การกระจาย second-of-minute ไม่มีวินาทีเดียวครองชัดเจน: วินาที 0 มากที่สุดเพียง 2.13% จึงไม่น่าใช่ scheduler ที่ยิงต้นนาทีเท่านั้น

### Exit structure

`sl=0` ใน field ส่วนใหญ่ไม่ได้แปลว่าไม่มี stop เพราะ MT5 history comment ระบุ `[sl ราคา]` เมื่อถูกปิดด้วย stop และราคา comment ตรงกับ close price ตัวอย่างเช่นขาดทุน -100 pips หรือ trailing stop ฝั่งกำไร

ไม่พบ XAU ที่จบด้วย `[tp ...]` ในประวัติชุดนี้ กลไก exit หลักจึงเป็น stop/trailing stop

## FixedVol20 basket engine

| Metric | Value |
|---|---:|
| Orders | 4,252 |
| Win / loss / breakeven | 2,798 / 1,449 / 5 |
| Gross P/L | -$3,638.72 |
| Profit factor | 0.9289 |
| Median hold | 425 วินาที |
| Orders with `[tp ...]` | 4,076 |
| Opens while another position active | 58.00% |
| Max simultaneous positions | 28 |
| Orders closed in multi-order same-second group | 77.09% |
| Opposite-side hedge while basket active | 0 ที่ตรวจพบ |

Volume progression เป็นลำดับเพิ่มความเสี่ยง ไม่ได้เป็น fixed volume แม้ชื่อ symbol จะมีคำว่า FixedVol20 ลำดับที่พบซ้ำมีลักษณะคล้าย progression/Fibonacci ที่ปรับเพดานจนถึง 174 lots

### Basket loss สำคัญ

วันที่ 26–27 ก.ย. UTC มี BUY basket 17 ไม้:

`0.1 → 0.2 → 0.3 → 0.5 → 0.8 → 1.3 → 2.2 → 3.7 → 6.2 → 10.4 → 17.5 → 29.4 → 49.4 → 83 → 139.4 → 174 → 174 lots`

รวม volume 692.4 lots และปิดรวม `-$39,958.09` เหตุการณ์นี้อธิบาย tail risk ของ engine ได้ชัดกว่าค่า win rate 65.8%

## Cost analysis

| รายการ | ค่า |
|---|---:|
| Gross trade P/L | +$3,159,742.59 |
| Commission | -$1,320,571.32 |
| Commission / gross profit | 41.79% |
| Implied average commission / lot | -$5.73035 |
| Gross minus commission | +$1,839,171.27 |
| Balance gain over $1,000 deposit | +$1,836,540.91 |
| Other unexplained cost/adjustment | -$2,630.36 |

ต้นทุนส่วนสุดท้ายอาจเป็น swap หรือ adjustment แต่ public order schema ไม่มี commission/swap ราย ticket จึงยังแยกไม่ได้

## ข้อจำกัดของการคำนวณ

- `profit` ใน order file เป็น gross ก่อน commission
- ไม่มี equity/balance ณ entry
- ไม่มี tick path, spread, slippage, MAE/MFE
- ไม่มี magic number แม้หน้าเว็บใช้ magic แยก EA/manual
- timestamp แหล่งข้อมูลถูกติดป้าย ISO UTC แต่เป็น Vantage server clock UTC+3; การวิเคราะห์ลบ 3 ชั่วโมงก่อน และไฟล์ aggregate แปลงเวลาจริงเป็น BKK แล้ว
- overlapping orders ที่เปิดเวลาใกล้กันทำให้การนับ win/loss streakอาจต่างจากเว็บ 1 ไม้ตามวิธี sort

