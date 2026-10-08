# Exception paths: ledger evidence, not a completed EA clone

ต้นทางคือ `data/orders_35462.jsonl` ที่ไม่แก้ทับ รัน `audit_exception_paths.py` เพื่อสร้าง `data/exception_paths_report.json` ตัวเลขทั้งหมดด้านล่างใช้ครบ 35,462 rows ตามกลุ่ม ไม่ตัดข้อยกเว้นออกจากเป้าหมาย

## Payoff support ของ XAU SL-labelled

31,123 rows ที่มี comment `[sl ...]` ไม่ใช่ EA instance ID และไม่แสดง initial SL/modify history

| สิ่งที่พบ | Orders | ผลต่อ candidate ideal initial 100 + activation 40/distance 30 |
|---|---:|---|
| Loss -100 points พอดี | 7,879 | อธิบายได้ในเชิง payoff แต่ไม่ยืนยัน entry/timing |
| Loss ต่ำกว่า -100 | 372 | initial stop แบบ non-loosening + level fill สร้างไม่ได้ |
| Loss ระหว่าง -100 กับ 0 | 0 | ไม่สนับสนุน immediate trail แบบ continuous negative exits |
| Positive pips 1–9 | 4,258 | ต่ำกว่า minimum trailing profit +10 ของ candidate |
| Zero-pip closes | 162 | อยู่นอก support -100 หรือ >=10 |

รวม counterexamples ของ ideal 40/30 = 4,792 rows การเปลี่ยน TF ของ entry ไม่เปลี่ยน support นี้ Quote fills, different activation/distance, stop changes และ engine overlays ยังเป็นทางเลือกที่ต้องพิสูจน์ ไม่อ้างว่า counterexamples นี้หักล้าง trailing ทุกแบบ

ตัวอย่าง tail: ticket `1645015941` SELL 10 lots, raw open `2026-09-17 14:49:04`, raw close `2026-09-18 19:33:34`, entry 4331.45, exit 4381.82, -5,037 points / -$50,370 ถือ 103,470 วินาที และไม่มี XAU order อื่นทับซ้อนช่วงถือ จึงไม่อธิบายด้วย concurrent hedge ที่เห็นใน closed ledger ได้ ข้อเท็จจริงนี้ยังไม่บอกว่าเกิดจาก stop modification, settings, execution หรือ intervention

## Portfolio chronology

ตรวจ interval ของ XAU ทั้ง 31,210 rows รวม special exits ใช้เงื่อนไข positive overlap: `min(close) > max(open)` ไม่ใช้ future closes เป็น causal signal

ตัวเลขนี้วัดเฉพาะ positions ใน closed snapshot ตามความละเอียดวินาที ไม่ยืนยัน exposure รวมของบัญชี ณ ทุก millisecond หรือ positions ที่ไม่ได้อยู่ใน snapshot

- Maximum concurrent positive-duration positions: 3
- Overlap pairs: 303, ครอบคลุม 351 orders
- Opposed pairs: 182, ครอบคลุม 235 orders
- 293 rows เปิดในขณะที่ order ที่เปิดก่อนหน้ายังไม่ปิด
- 10 rows มี opening time ตรงวินาทีเดียวกับอีก order; ลำดับภายในวินาทีไม่ทราบ
- 18 rows อยู่ที่ prior close วินาทีเดียวกัน; ไม่สมมติลำดับ close/open
- จาก losses ต่ำกว่า -100 จำนวน 372 rows: มี strict overlap 25, opposed overlap 23, prior opposed active at open 8 และไม่มี strict overlap 347

Overlap ไม่ยืนยันว่าอยู่ EA เดียวกันหรือเป็น hedge/recovery และไม่ระบุ magic หรือ manual 5 orders

## Close-by 12 orders / 6 pairs

Source มี comment `#... by #...` และสองขา opposite/equal volume ปิดวินาทีเดียวกัน ราคาปิดของแต่ละขาตรงราคาเปิดของอีกขา ทั้งสองมี negative pips แต่ลง gross loss เพียงขาเดียว อีกขาเป็นศูนย์

[MetaQuotes close-by documentation](https://www.mql5.com/en/book/automation/experts/experts_closeby) อธิบายว่าปิด minimum volume ของสอง positions ที่ราคาสะท้อน entry กัน ลง financial result ให้ request `position` และให้ `position_by` เป็นศูนย์ การสลับ request order เปลี่ยน attribution ระหว่าง BUY/SELL แต่ไม่เปลี่ยน net ของคู่

| Observed pair tickets | Lot ต่อขา | Pips ต่อขา | Net gross loss | Open gap seconds |
|---|---:|---:|---:|---:|
| 1526631971 / 1526631972 | .01 | -211 | -2.11 | 0 |
| 1530117600 / 1530117601 | .01 | -221 | -2.21 | 544 |
| 1536980281 / 1536980282 | .01 | -221 | -2.21 | 1 |
| 1568291690 / 1568291691 | 10 | -210 | -2,100 | 0 |
| 1596946312 / 1596946313 | 10 | -211 | -2,110 | 9 |
| 1615013349 / 1615013350 | 10 | -210 | -2,100 | 8 |

BUY รับ loss ในทั้ง 6 observed pairs แต่ helper ไม่ generalize ว่า BUY ต้องรับเสมอ Comment numbers ไม่ได้ตรง source opening tickets จึงไม่ใช้เลขใน comment เป็น verified position mapping Request ordering ถูกอนุมานจาก observed P/L allocation เท่านั้น

`settle_close_by()` ใน strategy เป็น pure accounting component รองรับ unequal volume/residuals แต่ไม่มีคำสั่ง trade จริงและไม่สร้าง hedge trigger/timing ที่ยังไม่ทราบ ระยะเปิดต่าง 544 วินาทีในหนึ่งคู่หักล้างคำอธิบายว่าเปิดสองขาพร้อมกันใน quote เดียวทุกคู่

## Contracts และ gross reconciliation

Candidate price P/L multipliers: XAUUSD+ = 100, FixedVol20 = 1; source pips = signed price delta x 100 ทั้งสอง symbols กฎนี้ reconcile pips 35,462/35,462 ภายใน 0.000001 และ gross P/L 35,462/35,462 ภายในครึ่งเซนต์เมื่อจัดสรร close-by ถูกต้อง

ก่อนจัดสรรมี gold 6 zero-profit legs ที่ดูเหมือน mismatch เพราะ mirror prices ไม่ใช่ independent market exit การกระทบยอดนี้ไม่ใช่ account contract confirmation, net-after-commission audit หรือ autonomous strategy reproduction

## FixedVol20 SL trial และ unusual exits

143 trial rows ใช้ .1 lot: 70 wins, 70 losses, 3 gross breakeven มี 27 exact -1,000-point losses และ 43 partial losses ระหว่าง -1,000 กับ 0 ไม่มี loss ต่ำกว่า -1,000 Median hold 236s, p25 115.5s, p75 453.5s, min 18s, max 2,187s

หาก nominal initial SL คือ 1,000 จริง การเกิด partial negative exits ขัดกับ ideal activation>=distance; ต้องทดสอบ trailing ที่ยังติดลบได้, SL rule อื่น หรือ quote execution บน FixedVol20 ต้นทาง ไม่ใช้ XAU path แทน

`fixedvol20_trial()` บังคับให้ caller ระบุ unknown entry/activation/distance ไม่เติมค่าที่ทำให้ดูครบโดยไม่มีหลักฐาน ส่วน unusual exits 120 rows แบ่ง 83 diagnostic closing clusters ด้วย gap <=15s และครอบคลุมแต่ละ ticket ครั้งเดียว กลุ่มนี้ไม่ใช่ recovered EA basket IDs

## Verification boundary

20 unit tests ผ่าน รวม actual six-pair accounting และ all-row pips/gross reconciliation แต่ tests เหล่านี้ไม่สร้าง source orders จาก ticks เป้าหมาย 100% ยังไม่ผ่าน ดู full replay outcomes และ missing source requirements ใน `RECONSTRUCTION_STATUS.md`
