# สรุปการทำงานของ Scalping456

## ข้อสรุปสั้นที่สุด

Scalping456 มีพฤติกรรมหลักอย่างน้อย 2 กลุ่มที่ต่างกันชัดเจน แต่จำนวน EA instances ที่แท้จริงยังยืนยันไม่ได้:

1. **XAUUSD+ — ultra-short scalper มีSL-labelled exitsและรูปแบบคล้ายtrailing** จำนวน 31,210 ไม้; initialstop/modifyrulesยังไม่ยืนยันทุกไม้
2. **FixedVol20 — grid/basket แบบเพิ่ม lot ตามลำดับ** จำนวน 4,252 ไม้

หน้าเว็บจัดหมวด EA 35,457 ไม้ และ manual 5 ไม้ แต่ประวัติสาธารณะไม่ได้เปิด field `magic` จึงระบุไม่ได้ว่า manual คือ ticket ใด หรือมี EA instances กี่ตัว

**ล่าสุด 9 ต.ค.**: ถอดกฎหลักได้จริง — ทอง = BUY/SELL STOP ±D (D ผู้ใช้ปรับ 1.05/1.00/1.10/1.30)  จาก quote หลังไม้ปิด, SL 1.00, trailing ห่างเท่า stops level ของ broker (0.20) ที่ server ปฏิเสธคำขอเมื่อราคาถอย, source feed ≈ demo ขยับเข้าใน 0.06/0.05; FixedVol20 = stop-entry ±3.0 + grid ×1.68 + TP ถัวเฉลี่ย ± 3.0/15.0 บน feed ที่ตรง tick ทุกตัว แต่ continuous causal replay ตรงเพียง 6,213/35,462 (17.52%) และมีหลักฐานเพดานจากความสุ่มของ EA ต้นทาง ดู `DECODED_MECHANICS_RESULTS.md` (ยังไม่ผ่านเป้า 100%) — forward holdout (order ที่เกิดหลัง snapshot) ให้ทอง 26.2% เท่าเดิม ไม่ overfit แต่ไม่ทะลุเพดาน; oracle ceiling ชี้ว่าตัวแปรซ่อนที่เสียมากสุดคือ tick อ้างอิงที่ EA อ่าน

สถานะล่าสุดอยู่ใน `RECONSTRUCTION_STATUS.md` / `VANTAGE_FEED_REPORT.md`: หลังพี่ตั้งค่า Vantage อ่านทองและ FixedVol20 ได้ เก็บ27,473,009 ticks และตรวจครบ35,462 orders แต่ **ยังไม่จำลองตรงทุก order 100%** 4 benchmarks เดิมบน Vantage ถูกทดสอบต่อเนื่องโดยไม่ reset ตาม ledger; strict matcher เวลา tolerance0 ตรงทุก observable fields ดีที่สุด17 rows / missing35,445 / extra56,807 ใน source window นี่ไม่ใช่ recovered EA และยังต้องทดลอง candle/grid/hedge/session/lot rules เพิ่ม

อัปเดตต่อ: closed-candle5TF/grid/trial38candidates+portfolio2prototypesรันแล้วและทำซ้ำ118data filesเหมือนกันครบ Bestของรอบใหม่Fixed grid3/progressive/rolling/quoteตรง14 (validation0), XAU M1 breakout/levelตรง6; portfolioที่กำหนดไว้ก่อนรันตรง6และ1 ทั้งหมดยังไม่ผ่าน35,462ordersหนึ่งต่อหนึ่ง ไม่ปรับobjectiveเป็นsubset ดู `CANDLE_GRID_RESULTS.md` /tests43ผ่าน

Pathdiagnosticsครบทุกrowพบข้อขัดแย้งกับuniformSL/trailingบนVantagefeedและระยะ2.8ที่ซ้ำในFixedtrial แต่distance2.8continuousreplayอีกสองแบบยังตรง0 PublicopenobservationsมีopeningcommentsPipScalperEA V2 BUY/SELL STOPเป็นเบาะแสpending-stop ไม่ยืนยันชื่อ/version/inputsของประวัติทั้งชุด ดู`PATH_CONSTRAINT_RESULTS.md`

ล่าสุดทดสอบpending-stop32แบบและรอบguardedอีก32แบบครบแล้ว ทุกแบบยังไม่ผ่าน Bestguardedตรงครบobservablefields29/missing35,433/extra91,768ต่อsource35,462 ทั้งสองsymbolsยังอยู่ในdenominator Entry-onlyที่ตัดlotออกตรงสูงสุด259แต่ไม่ใช่full-order success เก็บผลทุกsource row/extras/hashและcode snapshotsไว้ Tests74ผ่าน ดู[`PENDING_STOP_RESULTS.md`](PENDING_STOP_RESULTS.md) ต่อไปตรวจanchor/placement/repricingจากquotesก่อนentry ไม่ขอEAที่พี่ไม่มีและไม่ใส่ticket/time exceptionsเพื่อทำให้match

พี่ให้ตั้งกรอบแคบลงและตรวจเพิ่มlotตามพอร์ต$1,000: ตรวจlot timeline/pastclosedgrossครบ35,462แล้ว ทองจริงไม่มี0.1และมีrollback1→0.01→1 จึงยังไม่กำหนดbalance/equitythresholdเอง กำหนดcomponent studyเป็นทอง0.01ช่วงแรก7,312rowsรวมทุกexception แยกprice mechanismจากsizing ก่อนรวมกลับfullscope ดู[`LOT_SIZING_SCOPE_RESULTS.md`](LOT_SIZING_SCOPE_RESULTS.md)

ล่าสุดลงมือcomponent0.01แล้ว 4fixed controlsbestexact9/7,312/missing7,303/extra14,085 ยังไม่ผ่าน Narrowquoteauditพบทุกopeningsecondมีticksแต่ราคาsourceentry6,039rowsไม่ปรากฏบนexecutablequoteของวินาทีนั้น จึงrejectstrictdirectquote-fillmodelบนfeedนี้ได้ภายใต้no-slippage/same-clockassumptions ไม่ใช่proofว่าfeedผิดหรือว่า1,273witnessesเป็นordersที่cloneได้ ดู[`FIRST001_RESULTS.md`](FIRST001_RESULTS.md) /tests89ผ่าน Parentgoal35,462และlotformulaยังไม่ผ่าน

ผลกำไรมหาศาลไม่ได้มาจาก risk-reward ต่อไม้ที่ดี แต่มาจาก **win rate สูง + เทรดถี่มาก + เร่ง lot จาก 0.01 ไป 1 และ 10 lots ภายในประมาณหนึ่งสัปดาห์** ขณะที่ยอมให้ขาดทุนเฉลี่ยใหญ่กว่ากำไรเฉลี่ยอย่างชัดเจน

## กลไก XAUUSD+ ที่อนุมานได้จากหลักฐาน

### 1. เข้าเทรดแบบต่อเนื่องระดับวินาที

- 31,210 ไม้ในช่วงประมาณ 45 วัน
- เว้นระหว่าง entry มัธยฐาน 41 วินาที
- 65.34% ของ entry ถัดไปเกิดภายใน 60 วินาที
- นาทีที่ระบบ active มีเฉลี่ย 1.53 ไม้ และสูงสุด 12 ไม้/นาที
- กระจายแทบทุกชั่วโมง ยกเว้นช่วง 04:00 BKK ซึ่งสอดคล้องกับช่วง rollover/หยุด feed
- วินาทีที่เข้าไม่ได้ล็อกตายตัวกับต้นแท่ง จึงดูเป็น tick/event-driven มากกว่า “เข้าเฉพาะตอนเปิดแท่ง”

### 2. ปกติไม่ใช่ grid

- ถือเฉลี่ยมัธยฐาน 11 วินาที; 75% ปิดภายใน 23 วินาที
- มี position ซ้อนอยู่ก่อนเพียง 0.98% ของ entry
- มีฝั่งตรงข้ามค้างอยู่ตอนเปิดใหม่เพียง 0.58%
- simultaneous สูงสุด 3 positions

ดังนั้นแกนหลักของ XAU เป็น one-shot scalper: เข้า → จัดการ stop → ปิดเร็ว → หา entry ใหม่ ไม่ใช่สะสมไม้จำนวนมากแบบ grid ในภาวะปกติ

### 3. Stop loss หลักประมาณ 100 pips และกำไรปิดด้วย trailing SL

- ขาดทุน XAU 8,309 ไม้
- เมื่อจำกัดเฉพาะ core `[sl ...]`: ขาดทุน 8,251 ไม้ ในนี้ 7,879 ไม้ หรือ 95.49% ขาดทุนตรง `-100 pips` ตัวเลขนี้ไม่ใช้ denominator ของ XAU ทุกกลุ่มปนกัน
- XAU 31,123/31,210 ไม้ หรือ 99.72% มี comment `[sl ราคา]`
- ในกลุ่ม `[sl]` มีทั้งไม้ขาดทุนและไม้กำไร แปลว่า stop ถูกเลื่อนมาฝั่งกำไร
- ไม้ชนะมี pips มัธยฐาน 37; Q1 14; Q3 80
- ไม้กำไรเล็กตั้งแต่ +1, +2, +3 pips พบจำนวนมาก จึงน่าจะเริ่ม lock/trail ค่อนข้างเร็ว

สิ่งที่เห็นจากledgerคือขาดทุนส่วนใหญ่แถว−100pipsและกำไรจำนวนมากเป็นSL-labelled แต่closedordersไม่มีintratradepath/modifyhistory ตอนนี้คำนวณobservedMFEบนVantagecandidatefeedแล้ว ไม่ใช่MFEต้นทางที่ยืนยัน และยังไม่ระบุtrailingdistance/activation/stepจริงได้ ดูpathresultsสำหรับcounterexamples

### 4. Direction สมดุลและไม่เห็น bias ระยะยาว

- XAU buy 15,618 ไม้; sell 15,592 ไม้
- Win rate buy 72.67%; sell 73.01%
- ทิศทางเปลี่ยนจากไม้ก่อนหน้า 50.70% ใกล้การสลับแบบสมดุล

ข้อมูลนี้หักล้างแนวคิดว่า EA เป็น long-only/short-only หรือ trend-follow ฝั่งเดียว แต่ยังไม่พอระบุว่า entry ใช้ RSI, EMA, price action, order flow หรือโมเดลใด ต้องนำ entry time ไปประกบ tick/M1 ของโบรกเกอร์ก่อน

### 5. มี recovery/hedge overlay บางช่วง

XAU มี 87 ไม้ที่ไม่ได้จบด้วย `[sl ...]` ตาม pattern หลัก กลุ่มนี้รวมไม้ถือยาวและคู่ hedge ขนาดใหญ่ เช่น:

- Buy 10 lots เปิด 25 ก.ย. 23:59 (เวลา BKK ที่แก้ server offset แล้ว) ขาดทุน `-$151,190`
- Sell 10 lots ที่เปิดใกล้กัน กำไร `+$149,450`

สองไม้ถูกถือหลายวันและหักล้างกันเกือบหมด แสดงว่าระบบมี exception/recovery path หรือมีการแทรกแซงบางช่วง ไม่ควรเอาไม้เหล่านี้ไปหา parameter ของ scalp ปกติปนกัน

## กลไก FixedVol20 ที่อนุมานได้

FixedVol20 เป็น engine คนละแบบและมีลักษณะ grid/martingale ชัดเจน:

- เปิดเพิ่มข้างเดิมเมื่อ basket ยังไม่ปิด
- Progressive baskets อธิบายได้ด้วย multiplier 1.68 จาก lot ก่อนหน้า ปัดหนึ่งทศนิยมและ cap 174 เช่น `0.1, 0.2, 0.3, 0.5, 0.8, 1.3, 2.2, 3.7, 6.2, 10.4, 17.5, 29.4, 49.4, 83, 139.4, 174` ไม่ควรนำ lot values ทุก basket มาต่อกันแล้วถือเป็น progression เดียว
- เปิดขณะที่มี position เดิม 58.00% ของทั้งหมด
- simultaneous สูงสุด 28 positions
- ไม่มีการ hedge ฝั่งตรงข้ามใน basket ที่ตรวจพบ
- 77.09% ของ orders ปิดในวินาทีเดียวกับอย่างน้อยอีกหนึ่ง order สะท้อน basket close
- 4,076/4,252 ไม้มี comment `[tp ...]`
- เวลาถือมัธยฐาน 425 วินาที (7 นาที 5 วินาที) ต่างจาก XAU อย่างมาก

จุดเสี่ยงถูกเห็นจริงวันที่ 27 ก.ย. 2569 เวลา BKK: basket BUY 17 ไม้ ไล่ lot 0.1 ถึง 174 รวม 692.4 lots ถูกปิดภายในประมาณ 12 วินาที ขาดทุนรวม `-$39,958.09` เหตุการณ์เดียวกินกำไรสะสมของ engine นี้จน FixedVol20 รวมทั้งช่วงกลายเป็น `-$3,638.72`

## ผลงานที่คำนวณจาก 35,462 closed orders

| ตัวชี้วัด | ทั้งพอร์ต | XAUUSD+ | FixedVol20 |
|---|---:|---:|---:|
| Orders | 35,462 | 31,210 | 4,252 |
| Win rate | 72.00% | 72.84% | 65.80% |
| Gross P/L | +$3,159,742.59 | +$3,163,381.31 | -$3,638.72 |
| Profit factor | 1.4699 | 1.4740 | 0.9289 |
| Avg win | +$387.14 | +$432.70 | +$16.98 |
| Avg loss | -$689.11 | -$803.13 | -$35.30 |
| Median hold | 13 วินาที | 11 วินาที | 425 วินาที |

หน้าเว็บแสดง commission รวม `-$1,320,571.32` หรือเฉลี่ยเชิงสัดส่วนประมาณ `-$5.73035` ต่อ 1 lot เมื่อหารด้วย lots รวม ทำให้:

- Gross P/L: `+$3,159,742.59`
- หัก commission ที่หน้าเว็บแสดง: เหลือ `+$1,839,171.27`
- บวกทุนเริ่ม $1,000 จะได้ $1,840,171.27
- แต่ balance จริงบนหน้าเว็บคือ $1,837,540.91 ต่ำกว่าอีก $2,630.36 ซึ่งน่าจะเป็น swap/fee/adjustment อื่นที่ไม่ได้อยู่ใน order fields
- กำไรสุทธิจาก balance เทียบทุนเริ่มคือประมาณ `+$1,836,540.91`

คำว่า “กำไรต่อไม้” ในหน้าเว็บเป็น gross ก่อน commission จึงดูดีกว่าผลที่เข้ายอดเงินจริงมาก

## ทำไมผลตอบแทนถึงสูงมาก

1. ทุนเริ่ม $1,000 แต่ lot XAU เปลี่ยนจาก 0.01 เป็น 1.00 และ 10.00 อย่างรวดเร็ว
2. XAU 21,814 ไม้ใช้ 10 lots; 7,485 ไม้ใช้ 0.01; 1,910 ไม้ใช้ 1 lot
3. Win rate ประมาณ 73% ทำให้ระบบทน payoff ratio ที่เสียเปรียบได้ใน sample นี้
4. ความถี่สูงมาก ทำให้ edge เล็ก ๆ ถูกทบซ้ำหลายหมื่นครั้ง
5. lot ถูก cap ที่ 10 หลัง 1 ก.ย. จึงสร้าง P/L วันละหลักหมื่นถึงหลักแสนในบัญชี demo

ผลดังกล่าวไม่ใช่หลักฐานว่าใช้ทุน $1,000 แล้วทำซ้ำในบัญชีจริงได้ เพราะบัญชีนี้เป็น **Demo, ยังไม่ยืนยันบัญชี, leverage 1:500**, มีต้นทุน commission สูงมาก และช่วงทดสอบเพียงประมาณ 45 วัน

## ความเสี่ยงหลัก

- Payoff ratio ทั้งพอร์ตเพียง 0.562: แพ้หนึ่งครั้งต้องใช้กำไรเฉลี่ยประมาณ 1.78 ไม้ชนะมาชดเชย
- Drawdown หน้าเว็บ 20.26%; AI snapshot เก่าระบุ intraday DD 27.1% วันที่ 31 ส.ค.
- Best/Worst trade `+$149,450 / -$151,190` แสดง tail risk สูงมาก
- FixedVol20 มี martingale/grid tail risk ที่พิสูจน์ด้วย basket loss จริง
- XAU มี rare recovery/hedge path ที่ยังไม่รู้ trigger
- Commission รวมคิดเป็น 41.79% ของ gross trading profit
- หน้าเว็บ AI ระบุ overleveraging และ volume หลัง loss แต่ snapshot AI ใช้เพียง 24,281 ไม้และเก่ากว่าข้อมูลปัจจุบัน จึงใช้เป็นข้อสังเกต ไม่ใช่ฐานตัวเลขหลัก

## สิ่งที่ยังตอบไม่ได้จากลิงก์นี้เพียงอย่างเดียว

- indicator/เงื่อนไข entry ที่แท้จริง
- trailing activation, distance และ step
- magic number ของแต่ละ engine และ ticket manual 5 ไม้
- balance/equity ณ เวลาเปิดแต่ละไม้
- spread, slippage และ latency จริง
- MFE/MAE ระหว่างถือ
- trigger ของ recovery hedge และ trigger ปิด basket ผิดปกติ

รอบถัดไปควรประกบ order ทุกไม้กับ tick หรือ M1 ของ XAUUSD+ ตาม timestamp UTC แล้วทำ event study ก่อนเขียน strategy เพื่อแยก entry signal ออกจาก exit edge และ recovery overlay

## การแก้ timezone ที่จำเป็นก่อนประกบราคา

ผลเทียบราคาสนับสนุนสมมติฐานว่าเลขนาฬิกาใน API ThaiFXBook เป็น server time ของ Vantage UTC+3 ในช่วงข้อมูลนี้ แม้ ISO field ติดป้าย `+00:00` เมื่อเลื่อน `-3 ชั่วโมง` ราคาเข้าอยู่ใน high-low ของ XAUUSD M1 ที่ตรงกัน 95.26% ของตัวอย่าง 7,577 ไม้; ถ้าไม่เลื่อนตรงเพียง 4.33% นี่เป็นการอนุมานจาก price alignment ไม่ใช่การยืนยัน serializer/timezone โดยเจ้าของข้อมูล

สูตร inferred clock ที่ใช้กับชุดข้อมูลนี้คือ:

```text
actual UTC = ThaiFXBook raw - 3h
BKK        = ThaiFXBook raw + 4h
IUX UTC+6  = ThaiFXBook raw + 3h
```

ให้จด `08:04` ในช่องเวลาหน้าเว็บตามต้นฉบับ ส่วน raw `01:04` แยกอีกช่อง ไม่ใช่เวลาอ่านจากชาร์ต IUX หากสมมติฐาน offset ถูกต้อง order ตัวอย่างนี้เทียบได้กับ `05:04 BKK` / `04:04 IUX chart` ห้ามแก้ source time ทับหรือถือว่า web-7h เป็น UTC จริงโดยอัตโนมัติ ดู `TIMEZONE_EVIDENCE.md`

## ผลตรวจ strategy ล่าสุด

Full-period continuous replay 15 candidates เสร็จแล้วบน IUX proxy 11,098,339 ticks และ XAU 31,210 source orders โมเดล fixed-close 100 / trail 40/30 level มี direction+เวลาเข้า/ออก ±3s 28.641461%, missing 14,746, extra 40,006; ไม่ใช่การทำซ้ำ 100% และยังไม่รวม replay FixedVol20 4,252 orders

Audit payoff พบว่า ideal initial SL 100 + activation 40/distance 30 สร้างผลของ XAU SL-labelled 4,792 rows ไม่ได้ จึงปฏิเสธเป็นโมเดลสำหรับทุก order ได้โดยไม่ขึ้นกับ entry TF นอกจากนี้พบ concurrency สูงสุด 3 และ close-by 6 คู่ การคิด P/L แบบ close-by ทำให้ pips/gross profit กระทบยอดได้ครบ 35,462 rows แต่ไม่พิสูจน์ timing/trigger ของ strategy รายละเอียดใน `EXCEPTION_PATHS.md` และ `RECONSTRUCTION_STATUS.md`

