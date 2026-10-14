# ข้อมูลต้นทางที่จำเป็นสำหรับทดสอบทุก order 100%

เป้าหมายยังคงเป็น strategy ที่สร้าง 35,462 source orders ครบหนึ่งต่อหนึ่งด้วยกฎ causal ไม่ใช่ lookup ledger และไม่ใช่ผล proxy ที่คล้ายกัน รายการนี้ไม่ใช่คำขอรหัสผ่านหรือสิทธิ์ส่ง trade

พี่ยืนยันแล้วว่าไม่มี EA ของเจ้าของ Scalping456 และศึกษาเฉพาะ orders ที่เผยแพร่ อลิซจะไม่ขอ EA/.set/Journal จากพี่ซ้ำหรือรอไฟล์เหล่านี้ก่อนทำงาน รายการด้านล่างบันทึก evidence ที่ public ledger ยังไม่มี ไม่ใช่สิ่งที่พี่ต้องจัดหา งานต่อใช้เฉพาะ public snapshots/market data ที่มีสิทธิ์อ่าน และต้องแยกสมมติฐานจากสิ่งที่พิสูจน์ได้

## สิ่งที่มีและตรวจปัจจุบัน

- Public snapshot ครบ 1,774 pages / 35,462 unique tickets มี 14 fields: id, ticket, symbol, trade_type, volume, profit, open/close_time, open/close_price, pips, sl, tp, comment
- ไม่พบ bid/ask path, magic, EA instance/version, original position/deal IDs, opening comments หรือ SL/TP modification history ใน public order fields
- Data hashes และทุก pips/gross result reconcile ได้เมื่อคิด close-by ถูกต้อง แต่ไม่ให้ intratrade path หรือ initial settings
- หลังพี่ตั้งค่าแล้ว อ่าน VantageMarkets-Demo ที่ระบุได้ Export XAUUSD + FixedVol20 รวม27,473,009 ticks แยก raw/normalized/provenance แล้ว แต่ไม่พบ source symbol XAUUSD+ และยังไม่ยืนยัน account/feed/execution เดิม ดู `VANTAGE_FEED_REPORT.md` ไม่ launch/relogin/อ่าน password/เปลี่ยน Market Watch/ส่ง trade
- Full-period IUX proxy replay เสร็จแล้ว ทุก candidate ไม่ผ่าน exact clone และ FixedVol20 เป็น synthetic instrument คนละ price path ไม่แทนด้วย XAU
- New Vantage 4 prespecified tick benchmarks ก็ไม่ผ่าน Strict matcher ครบ observable fields ให้ดีที่สุด17 / missing35,445 / extra56,807 ทุก35,462 rows ยังอยู่ใน scope; FixedVol20 trials/grid/hedge/manual/closed-candle rules ยังมีงานทดลองต่อ ไม่ reuse blocker ไม่มี Vantage เดิม
- ต่อด้วยclosed-candle5TF/grid/trial38candidates+portfolio2prototypesแล้ว ทุกแบบไม่ผ่าน แต่QA40models/reproduction118filesผ่าน ดู `CANDLE_GRID_RESULTS.md` ตอนนี้ยังตรวจtrailing/lot/session/hedge pathได้ ไม่วนจูนarbitrary presetsเพื่อกลบsource/manual/state evidenceที่ยังขาด
- ตรวจquotepathsครบ35,462rowsและpublicschemaเพิ่มแล้ว Closedtable/paginationยัง14fields ไม่มีmagic/position/dealIDs/modifyhistory Publicopenobservationsใหม่มีPipScalperEA V2 BUY/SELL STOPcommentsและ81sparseequitysamples เป็นเบาะแสไม่ใช่historicalEAidentity/inputs Distance2.8trialreplaysอีก2modelsไม่ผ่าน ดู`PATH_CONSTRAINT_RESULTS.md` ตอนนี้ยังมีpending-stopcausalexperimentที่มีเหตุผลรองรับ ไม่ถือว่าimpasseเพียงเพราะbenchmarkไม่ตรง
- Pending-stop32paper+32guardedcontrolsรันเสร็จแล้ว ทุกแบบไม่ผ่าน Best29/missing35,433/extra91,768 เก็บทุกsource/extrasและcode snapshots/QAไว้ Tests74ผ่าน ดู`PENDING_STOP_RESULTS.md` ยังตรวจentry anchor/pending placement/repricingด้วยquotesก่อนentryได้ ไม่ใส่ticket/session/lotchangeเวลาเฉพาะที่อ่านย้อนหลังเพื่อสร้างmatch

## หลักฐานต้นทางที่ public ledger ยังไม่ให้ (ไม่ใช่รายการงานให้พี่)

1. Bid/ask tick exports ของบัญชี/server Vantage ต้นทาง ทั้ง `XAUUSD+` และ `FixedVol20` ตลอดช่วงประมาณ 24 ส.ค.–8 ต.ค. 2026 ตาม source server clock รวมช่วงก่อนเริ่มเพื่อ initialize state หากมี เก็บ `time_msc`, bid, ask, symbol, original timestamp/timezone และ server/build/provenance อย่าแก้ raw timestamps ทับ
2. MT5 deals/orders/positions history ที่มี magic, position/deal linkage, reason, opening comments, commission/swap และ original precision ปิดข้อมูลส่วนบุคคลได้
3. EA inputs `.set`, ชื่อ/version และ change log ของ parameters/lot/session แต่ละช่วง โดยเฉพาะEAที่publicopencommentsเรียกPipScalperEA V2; ต้องยืนยันว่าใช้กับประวัติเดิมช่วงไหน ไม่ถือชื่อcommentแทนversion/settings หากมี source code ก็ช่วยลด ambiguity ได้ แต่ไม่ใช้ source code ที่ไม่มีสิทธิ์เข้าถึง
4. Experts/Journal logs ที่ระบุเปิด/ปิด/modify SL/TP, close-by, failures/retries, restart/initial state และ manual actions โดยเฉพาะ manual 5 orders ที่เว็บระบุ
5. Symbol/account contract specifications เช่น point/tick size, contract multiplier, lot step/cap, account currency, execution rules และหลักฐาน timezone anchor เพื่อเทียบ raw server clock กับ UTC จริง

ไม่ต้องส่ง password, investor password, token หรือข้อมูล login และไม่ต้องเปิด auto-trade เพื่อเก็บไฟล์เหล่านี้

## Blocker ที่มีหลักฐานเชิงปริมาณ (9 ตุลาคม 2026)

ถอดกฎได้แล้ว (ดู `DECODED_MECHANICS_RESULTS.md`) แต่ 100% ถูกจำกัดด้วยสิ่งที่ feed และ ledger สาธารณะไม่มี: (1) เวลา ms ที่ EA ต้นทางอ่าน quote/ส่ง order/modify SL — reference tick ทองอธิบายได้ 52–61% (j=1) และ Fixed j=1 66% (1 leg) – 93% (≥5 legs) โดยหา predictor ไม่เจอ; (2) trailing update จริง — ใช้กลไก stops-level + trailing step แล้ว stop+วินาทีปิดตรง 57–62% ส่วนที่เหลือคือ latency/feed ที่สุ่ม; (3) tick `XAUUSD+` ต้นทาง — feed demo ตรงเฉพาะ bid+0.06/ask−0.05 ที่ 80–89% ของ stop crossing; (4) position ไม่มี SL/ปิดมือ/close-by/คอมเมนต์ว่าง 120+ แถวไม่มี trigger ใน feed

ข้อมูลที่จะลดความกำกวมได้: history deals/orders ของบัญชีต้นทางที่มี `time_msc` และ Journal ส่ง/modify; tick `XAUUSD+` ของ server ต้นทาง — ไม่ต้องส่ง EA/รหัสผ่าน และไม่ใช่เงื่อนไขให้หยุดทำงานเท่าที่เหลือ; ถ้าไม่มีข้อมูลนี้ ผล replay จะรายงานตามจริงว่าไม่ถึง 100%

### เส้นทางที่ไม่ต้องใช้ข้อมูลจากเจ้าของ EA (9 ตุลาคม 2026)

- **Forward holdout**: order สาธารณะใหม่หลัง snapshot ใช้ทดสอบ engine ที่ล็อกแล้ว (ทอง 26.2% เท่าเดิม) — เก็บต่อด้วย `fetch_forward_orders.py --watch`
- **Raw ECN demo (ทำแล้ว)**: บัญชี `demo-vantage-26257644` มี `XAUUSD+`; tick ตรงกับ demo `XAUUSD` + offset ที่ใช้อยู่ ผล replay ไม่ดีขึ้น (§15) — ข้อ 1 ด้านบนจึงเหลือเฉพาะ tick ที่ terminal ต้นทางเห็นจริงและเวลา ms ของการส่ง order/modify

## สิ่งที่จะตรวจเมื่อได้ข้อมูล

- ตรวจ provenance/clock/coverage และ missing periods ก่อน simulation ไม่ถือป้าย `+00:00` เป็น UTC จริงโดยไม่มี alignment check
- ใช้ source quotes ของแต่ละ symbol; seed state/parameter changes จากหลักฐานที่มีอยู่ก่อนเวลานั้นเท่านั้น
- Replay กฎโดยไม่อ่าน future closed ledger แล้วค่อย score ทุก symbol/engine/side/lot/open-close time/price/pips/P&L/close reason ไม่มี missing/extra orders
- หากข้อมูลยังไม่ระบุ manual actions หรือ execution latency ที่จำเป็น จะรายงานส่วนที่ยังพิสูจน์ไม่ได้ ไม่เปลี่ยน objective เป็น percentage หรือ subset ที่ผ่าน

การได้ไฟล์เหล่านี้เปิดทางให้ทดสอบต่อ แต่ไม่ใช่คำรับประกันว่าจะถอด source EA ได้ 100% Closed outcomes สามารถเกิดจากหลาย algorithms และต้องให้ผล replay จริงเป็นหลักฐาน
