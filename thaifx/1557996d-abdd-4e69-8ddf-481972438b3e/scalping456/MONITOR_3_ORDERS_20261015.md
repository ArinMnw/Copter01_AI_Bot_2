# Monitor Scalping456: first 3 new positions

เริ่มนับ: 2026-10-15T13:45:29.583179+07:00 (กรุงเทพฯ UTC+7)

บัญชี Demo 2101182459 / IUXMarkets-Demo / XAUUSD.iux / magic 995456 เท่านั้น ตรวจทุก 15 นาทีในแชตเดิม ไม่รวม INDI1, EA2_1 หรือพอร์ตอื่น

## ขอบเขตการนับ

- นับ 3 positions แรกที่เปิดใหม่หลังเริ่มติดตาม ไม่รวม pending ที่ยังไม่ fill และไม่นับ partial deals/partial exits เป็นหลายไม้
- Pending ที่วางไว้ก่อนเริ่มติดตามสามารถเข้า cohort ได้ หาก fill หลังเริ่มติดตามจริง
- ตัด position ที่เปิด/ปิดก่อน baseline ออกตาม identifiers ในไฟล์ JSON; journal baseline offset 236067 bytes
- จุดเริ่มมี position เปิดอยู่ 0 ไม้ และ pending 2 ไม้; verified 0/3

## เกณฑ์ผ่านต่อไม้

ตรวจหลักฐานจาก request/response journal, state และ broker position/deal history ให้สอดคล้องกัน: account/symbol/magic, native stop pair และ entry ที่คำนวณจาก Bid/Ask จริง, lot 0.01, SL เริ่มต้น 1.00 ไม่มี TP, execution/rounding/fees/slippage จริง, exposure cap 3, ไม่แตะไม้ของพอร์ตอื่น, เก็บสถานะและ PnL ไม่ซ้ำ, การ cancel/re-arm หลังปิด และ daily loss entry gate

ตรวจ trailing เฉพาะเมื่อเงื่อนไขเกิดจริง: activation >0.20, ระยะ 0.20, improvement >0.01, first delay 0.900 วินาทีจาก first seen, modify interval 0.270 วินาที และห้ามคลาย SL หากยังไม่ถึง trigger ให้ระบุว่าไม่ถูกใช้งาน ไม่อ้างว่าทดสอบ path นั้นผ่าน

นับผ่านเมื่อ position ปิดครบวงจรและตรวจ applicable checks ได้ด้วยหลักฐาน ไม่มีข้อขัดแย้งค้าง ไม่ใช้กำไรเป็นเงื่อนไขและไม่ถือว่าเป็นการพิสูจน์ว่าเหมือน EA ต้นฉบับ 100%

## ความปลอดภัยและจุดหยุด

ตรวจแบบ read-only ต่อระบบเทรด: ไม่ส่ง/แก้/ยกเลิก/ปิด order ไม่ restart และไม่แก้ config/risk/state ของบอท อัปเดตได้เฉพาะ ledger ของ monitor นี้ ถ้าพบปัญหาให้แจ้งพี่พร้อมหลักฐานและติดตามต่อ ไม่ลบไม้ที่มีปัญหาแล้วเลือกไม้ดีมาแทน

เมื่อ cohort 3 ไม้แรกผ่านครบ ให้สรุป ticket/side/lot/SL/management/exit/PnL และหยุดเฉพาะ heartbeat ของ monitor นี้ ไม่หยุดบอทและไม่แก้ monitor ของ EA2.1 ในแชตอื่น

Baseline/ledger: data/forward_2459_20261015/monitor_3_orders_state.json

Heartbeat ID: `scalping456-demo-2459-3` (PAUSED — ตรวจสามไม้ครบและผ่านแล้ว)

ติดตามเมื่อเครื่องและแอปยังเปิดอยู่; แจ้งเฉพาะความคืบหน้าที่มีข้อมูลใหม่ ปัญหาที่ต้องจัดการ หรือ completion ไม่ส่งรายงานซ้ำเมื่อสถานะไม่เปลี่ยน

## ผลตรวจรายไม้

ตรวจสามไม้แรกตาม broker entry chronology ครบ 3/3 ผ่าน applicable execution checks และปิดครบวงจร หยุดเฉพาะ heartbeat `scalping456-demo-2459-3` เป็น PAUSED แล้ว ไม่หยุดบอทเทรดและไม่แตะ automation อื่น

| Ticket | ฝั่ง | Lot | SL เริ่มต้น → สุดท้าย | Trailing | ราคาปิด | สุทธิ USD | ผลตรวจ |
|---|---|---|---|---|---|---|---|
| 601687989 | BUY | 0.01 | 4135.04 → 4136.20 | 1 ครั้ง | 4136.20 | +0.12 | PASS |
| 601689254 | SELL | 0.01 | 4135.63 → 4135.63 | ไม่ถึง trigger | 4135.63 | -1.01 | PASS |
| 601691098 | SELL | 0.01 | 4135.22 → 4134.10 | 3 ครั้ง | 4134.10 | +0.12 | PASS |

รวมสามไม้ **-0.77 USD** การผ่านหมายถึงการทำงานตรงกติกา ไม่ใช่กำไรหรือการพิสูจน์ clone ต้นฉบับ 100%

### หลักฐานที่ตรวจ

- Native order/deal history ยืนยัน account, magic, symbol, direction, volume, initial pending entry/SL/TP และ exit ด้วย SL; รวม profit/commission/swap/fee ตรง journal และ state ทุกไม้ ไม่มี closed event ซ้ำ
- ตรวจ quote ตอนวาง pending กับ native tick epoch โดยตรงทั้งสามไม้ ไม่แปลงด้วยค่า UTC+6 ของชาร์ต
- ไม้ 601687989 เลื่อน SL ครั้งเดียวที่กำไรเชิงราคา 0.32 หลัง first seen 20.315887 วินาที; candidate SL 4136.20 ตรง Bid-0.20 และ native tick
- ไม้ 601689254 มี favorable gain สูงสุดจาก native ticks เพียง 0.01 จึงไม่ควร trigger trailing; ปิด SL เดิมถูกต้อง
- ไม้ 601691098 เลื่อน SL 4134.18 → 4134.15 → 4134.10 ที่ gain 0.24/0.27/0.32; modify interval 1.987155 และ 0.770208 วินาที ผ่านขั้นต่ำ 0.270 และไม่คลาย SL
- Entry slippage adverse จริงเป็น 0.04, 0.01 และ 0.00 ตามลำดับ จึงแยก initial SL distance จากราคาวาง pending กับราคาที่ fill จริง ไม่บังคับว่าต้องเท่ากัน
- Native history ของ opposite pending ยืนยันคงไว้จน position ปิดแล้วจึง cancel และรับคู่ใหม่สำเร็จทุกไม้
- สร้าง exposure timeline จาก native setup/fill/cancel/exit ได้สูงสุด 2 slots ระหว่าง cohort และ re-arm หลังไม้สาม ไม่เกิน cap 3; ไม่ได้ทดสอบเส้นทาง 3 slots เต็มจริง
- Daily loss gate ยังไม่ถูก trigger ระหว่าง cohort จึงไม่อ้างว่าทดสอบ boundary -20 จริงในสามไม้นี้
- Prefix SHA256 ของ journal baseline ตรง และ code SHA256 ทั้งห้าไฟล์ไม่เปลี่ยน; day net ตรง baseline บวก unique closes ใหม่

หลักฐานเต็ม: `data/forward_2459_20261015/monitor_3_orders_audit_20261015.json` และ `monitor_3_orders_broker_evidence_20261015T140424.json`

### ปัญหาที่พบภายหลัง cohort — ยังไม่ได้แก้

เริ่มเวลา 14:00:18.861 โบรกเกอร์ปฏิเสธ pending รอบใหม่ด้วย **10040 / Position limit reached** หลังไม้สามปิดตั้งแต่ 13:53:37 แล้ว ตรวจถึง 14:12:21 พบ 25 responses รหัสนี้ Snapshot บัญชีมี 100 positions, Scalping456 ไม่มี own positions/pending และ state เป็น cooldown; โปรแกรมยัง retry ตาม policy เดิม ไม่ได้ถูกปิด

ตาม [MQL5 return codes](https://www.mql5.com/en/docs/constants/errorswarnings/enum_trade_return_codes) บัญชี hedging นับ pending รวมกับ open positions ในเพดานนี้ เป็นข้อจำกัดโควตารวมของบัญชี ไม่ใช่หลักฐานว่าต้องเพิ่ม lot หรือเลื่อน SL

บันทึกเป็น operational alert แยกจาก first-three execution audit ซึ่งผ่านและจบขอบเขตแล้ว ไม่อ้างว่าระบบรอบถัดไป healthy ไม่มีปัญหา ไม่ปิดออเดอร์ของพอร์ตอื่น ไม่เปลี่ยนโควตา/config และไม่แก้บอทโดยไม่ได้รับอนุญาต หากต้องการให้เปิดรอบใหม่ต้องให้ผู้ใช้ตัดสินใจเรื่องโควตาบัญชีก่อน

ใช้ OpenAI Docs ตรวจวิธีหยุดเฉพาะ scheduled follow-up แล้วเปลี่ยน status ผ่าน automation_update โดยคงชื่อ prompt schedule และ target thread เดิม ไม่เขียน automation config ด้วยมือ
