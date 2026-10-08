# Strategy hypothesis and extraction plan

เอกสารนี้แยกสิ่งที่ **ยืนยันจาก orders** ออกจากสิ่งที่เป็น **สมมติฐาน** เพื่อไม่รีบเขียน EA เลียนแบบจากตัวเลขปลายทางอย่างเดียว

## XAU core: candidates ที่ต้องทดสอบต่อ

```text
FLAT: ทดลอง fixed-close bracket / running extrema / lookback momentum
  └─ causal trigger → BUY หรือ SELL
       └─ OPEN: candidate initial SL 100 points, ไม่มี TP
            ├─ adverse ถึง SL → close -100 points
            └─ favorable → ratchet SL ตามราคา → close ที่ trailing SL
```

คุณสมบัติที่ยืนยัน:

- core XAU `[sl ...]` มี 31,123 orders
- direction ทั้งสองฝั่งใกล้ 50/50 และปกติถือ position เดียว
- comment `[sl PRICE]` เท่ากับ `close_price` ครบ 31,123/31,123
- TP เป็น 0 ทุก core order และมี SL closing label แต่ไม่เห็น initial SL หรือประวัติการ modify จึงยังแยก server stop, trailing, manual modification หรือแต่ละ engine ไม่ได้
- core loss 7,879 จาก 8,251 รายการ (`95.49%`) เท่ากับ -100 points พอดี; ไม่ใช่ loss ของ XAU ทุกกลุ่มรวมกัน
- entry เกิดต่อเนื่อง ไม่ผูกกับแท่งหรือวินาที 0; median hold 11 วินาที
- เมื่อรวม special exits ก่อนหา predecessor: 30,751/30,994 eligible transitions (`99.215977%`) เปิดไปตาม displacement จาก close ก่อนหน้า นี่เป็นทิศทางหลัง fill ไม่ใช่การยืนยัน entry rule
- ระยะ absolute จาก close ก่อนหน้ามี median 108 points; p25=101, p75=118
- ตั้งแต่ 1 ต.ค. median ที่เห็นราว 135 points แต่ยังแยกไม่ได้เด็ดขาดว่า owner เปลี่ยน parameter หรือ volatility/latency ทำให้ overshoot สูงขึ้น
- เดิมการข้าม special exits ทำให้ core 68 รายการใช้ predecessor ผิด แก้ direction exceptions ได้ 8 รายการ แต่ยังเหลือ 243 eligible transitions สวน displacement ยังไม่มีหลักฐานว่า rolling-extrema อธิบายได้ครบ
- tick momentum ก่อน entry 10 วินาทีทาย direction ได้ 88.45%; TF 5m/15m/30m/H1 ลดเหลือประมาณ 60%/55.6%/53.7%/52.4% จึงไม่พบหลักฐานว่า candle TF สูงเป็นตัวเปิดหลัก

ส่วนที่ยังต้องพิสูจน์ด้วย tick ของ Vantage ต้นทาง:

- trigger ที่แท้เป็น 100 points จาก running extremum หรือ fixed bracket จาก close แล้วมี reset บางกรณี
- trailing distance/activation/step ที่แน่นอน; giveback จาก proxy ไม่ยืนยัน trail 100 ส่วน conditional IUX fit ให้ 40/30 เป็น candidate แต่ seed entry จริงและใช้ขอบเขต actual close+30s จึงไม่ใช่ causal clone
- ค่า entry ระยะราว 130 points ช่วงท้ายเป็น parameter change หรือ execution overshoot
- Overlaps, close/open ที่ชนวินาทีเดียวกัน และ long gaps ต้องตรวจทั้ง sequence ของทุก XAU order ไม่ถือ one-position เป็น invariant ของต้นฉบับ

### ข้อจำกัดที่ปฏิเสธ candidate เดิมได้โดยไม่ใช้ proxy

Ideal level fill, initial SL 100, activation 40/distance 30 ออกได้ที่ -100 หรืออย่างน้อย +10 points เท่านั้น แต่ XAU SL-labelled 4,792 rows อยู่นอก support นี้ (372 loss below -100, 4,258 positive <10, 162 zero pips) จึงไม่สามารถเป็นโมเดลของทั้ง cohort ได้ แม้เปลี่ยน entry TF ก็ไม่แก้ข้อขัดแย้งของ exit support ค่า default ถูกเก็บเพื่อ benchmark ไม่ใช่ deployment preset

เมื่อรวม XAU ทุกชนิด exit พบ strict overlap 303 pairs / 351 orders และ concurrency สูงสุด 3; 182 pairs เป็นคนละฝั่ง ใน 372 losses ต่ำกว่า -100 มี 347 orders ไม่มี strict overlap จึงไม่สรุปว่า hedge อธิบาย tail ทุกไม้ได้ ดู `EXCEPTION_PATHS.md`

## FixedVol20: basket structure และส่วนที่ยังไม่ทราบ

```text
IDLE
  └─ เปิดไม้แรก 0.1 lot ฝั่ง BUY หรือ SELL
       ├─ basket ถึง target → ปิดทั้งชุดด้วย TP
       └─ ราคา adverse → เพิ่มไม้ฝั่งเดิมด้วย lot progression
            ├─ ถึง basket target → ปิดหลาย ticket เวลาเดียวกัน
            └─ ถึง emergency/risk condition → ปิด basket ขาดทุนหนัก
```

TP baskets แสดงพฤติกรรม grid/basket recovery ต่างจาก XAU core แต่ first entry และ emergency/risk/manual closure ยังไม่ยืนยัน รวมถึง 143 SL trial orders ต้องทดสอบแยก ห้ามตัดออกจากเป้าหมาย 35,462 orders

ข้อมูล [Vantage เรื่อง synthetic indices](https://www.vantagemarkets.com/en-za/academy/types-of-synthetic-indices/) ระบุว่า FixedVol20 อยู่ใน FixedVol series มี annualized volatility 20% และสร้าง random tick หนึ่งครั้งต่อวินาที ดังนั้นการเอา XAU tick ของ IUX มาแทน price path ของ FixedVol20 ไม่มีหลักฐานรองรับ ต้องได้ history ของ instrument ต้นทางก่อนจึงจะทดสอบ basket entries/exits ระดับ order ได้

## หลักฐานจาก transition และ tick replay

- `data/sequential_transitions.csv` / `state_machine_report.json` เป็น legacy core-only/conditional diagnostic มีข้อจำกัดเรื่อง predecessor และ actual-entry search horizon
- `data/order_audit_35462.csv` / `ledger_audit_report.json` ใช้ตรวจทุก order และ predecessor แบบรวม special exits
- `data/order_tick_features.csv` จับคู่ Exness tick ได้ 31,113/31,123 (`99.968%`)
- feed อิสระพิสูจน์โครงสร้างได้ แต่ไม่สามารถให้ replay 100% ระดับ tick เพราะ source เป็น Vantage และไม่มี source tick archive
- implementation ปัจจุบันอยู่ใน `strategy_scalping456.py` เป็น research candidates ไม่ใช่ source EA ที่ถอดสำเร็จ

## Continuous causal replay

`replay_causal.py` สร้าง signals ก่อนอ่าน source orders เพื่อ scoring ไม่ reset ตาม entry/exit จริง และไม่ reset ตอนเปลี่ยนวัน ทดสอบ 15 candidates รวม fixed-close 100/120/130, rolling 100/160, trailing 40/30, 50/50, legacy 100, level/quote fills และ momentum windows 5s/10s/60s/300s/900s/1800s/3600s ระยะยาวเป็น lookback return ไม่ใช่การอ่านแท่งปิด

Reference replay วันที่ 7–11 กันยายน มี XAU ทุกกลุ่ม 5,326 orders:

| Candidate | ทิศ+เวลาเข้า/ออก ±3s ต่อทุก source order | Predicted | Missing | Extra |
|---|---:|---:|---:|---:|
| Fixed-close 100, trail 40/30 | 29.966204% | 8,428 | 2,445 | 5,547 |
| Rolling 100, trail 40/30 | 25.854300% | 10,005 | 2,749 | 7,428 |
| Momentum 5s/50, trail 40/30 | 26.793090% | 16,121 | 2,675 | 13,470 |
| Fixed-close 100, immediate trail 100 | 7.979722% | 6,251 | 3,662 | 4,587 |

Fixed-close 100 / 40/30 มีเพียง 3 orders ที่ side/lot/open-second/close-second/open-price/close-price ตรงพร้อมกันใน scorer จึงยังไม่ใช่ clone แม้ conditional fit ก่อนหน้าให้ผลดูสูงกว่า ห้ามใช้ matched-only percentage แทน coverage ของทุก source order

Vector accelerator ตรวจ parity กับ reference strategy และเก็บผลแยก ticket/model พร้อม counts ของไม้หายและไม้เกิน Parameter บางส่วนเคย fit ทั้ง proxy dataset แล้ว จึงไม่เรียกการแบ่งวันตรวจว่า unseen holdout

Full-period replay 23 ส.ค.–8 ต.ค. เสร็จแล้ว ใช้ 11,098,339 proxy ticks กับ XAU ทุกกลุ่ม 31,210 orders สูงสุดด้าน direction+open/close ±3s คือ fixed 100 / 40/30 level ที่ 28.641461%, missing 14,746, extra 40,006 และมีแค่ 19 rows ที่ 6 fields ตรงร่วมกัน ทุก model ยัง `full_source_clone_verified=false` ส่วน FixedVol20 4,252 rows ยังไม่มี source tick replay รายละเอียดครบใน `RECONSTRUCTION_STATUS.md`

## Close-by และ FixedVol20 trial ใน implementation

`settle_close_by()` รับ portfolio legs และเวลาปิดจาก caller แล้วคำนวณ minimum offset volume, reciprocal entry-price exits และ gross P/L allocation โดยไม่อ่าน tickets หรือส่ง trade จริง ทั้ง 6 observed pairs กระทบยอดได้ แต่ caller/strategy ยังไม่รู้ hedge-open trigger และ close-by schedule จึงไม่ถือว่าแกะ 12 orders นี้เชิง causal แล้ว

การลง P/L ที่ขาแรกและอีกขาเป็นศูนย์ตรงกับ [MetaQuotes: Closing opposite positions](https://www.mql5.com/en/book/automation/experts/experts_closeby) การสลับ position/position_by เปลี่ยนฝั่งที่รับ P/L ไม่เปลี่ยน net ของคู่ จึงไม่ hard-code ว่า BUY ได้ P/L เสมอ

`Scalping456Config.fixedvol20_trial()` แยก candidate ของ 143 SL-labelled trial จาก basket engine ใช้ observed .1 lot และ nominal initial stop 1,000 points เป็นสมมติฐาน แต่บังคับให้ระบุ entry/activation/distance ที่ยังไม่ทราบ ไม่แอบใช้ค่า XAU 40/30 แทน

## Acceptance criteria ของเป้าหมายเดิม: ทุก order 100%

- Source ticks/bid/ask, timezone, contract/execution settings และ initial state ตรวจสอบได้
- Replay ต่อเนื่องโดยใช้เฉพาะข้อมูล ณ เวลานั้น ไม่ hard-code tickets หรือผลลัพธ์ย้อนหลัง
- จับคู่ครบหนึ่งต่อหนึ่ง 35,462 orders ทุกกลุ่ม ทั้ง side/symbol/engine/lot/open-close time/price/pips/P&L และ closing behavior ตามความละเอียดต้นทาง
- ไม่มี missing หรือ extra orders ที่อธิบายไม่ได้ ไม่ตัด trial/special exits ออกจาก denominator
- Parameter/session/manual changes ต้องมีหลักฐานจาก settings/Journal ไม่เลือกย้อนหลังเฉพาะค่าที่ตรง
- Test ช่วงที่ไม่ได้ใช้เลือก parameters จริง และรายงาน ambiguity/censoring/missing source data

ตอนนี้ยังขาด source ticks โดยเฉพาะ FixedVol20, EA settings/magic/opening comments, Journal และ manual actions ประวัติ closed orders ไม่ระบุอัลกอริทึมที่สร้างมันได้อย่างเป็นเอกลักษณ์ การได้ distribution หรือกำไรคล้ายกันยังไม่ผ่าน completion criteria

## คำเตือนในการนำไปใช้จริง

อย่า clone lot sizing เดิมตรง ๆ พอร์ตเริ่ม $1,000 แล้วขึ้น 10 lots ภายในประมาณ 8 วันเป็น leverage/risk regime ที่รุนแรงมาก บัญชีต้นฉบับเป็น demo และประวัติมี tail events ระดับ ±$150k การถอด “signal” ควรแยกจากการถอด “risk sizing” เสมอ

