# Vantage: ผลตรวจ feed และ replay หลังตั้งค่า

ตรวจ 8 ตุลาคม 2026 ด้วย terminal ที่พี่ล็อกอินไว้เอง เป้าหมาย 35,462 orders ตรง 100% ยังไม่ผ่าน แต่เงื่อนไขเดิมที่ไม่มี Vantage/FixedVol20 ในเครื่องเปลี่ยนแล้ว จึงมีข้อมูลใหม่ให้ทดลองต่อ ไม่ใช่ blocker เดิม

## บัญชีและสิทธิ์

ยืนยัน terminal `profiles/demo/demo-vantage-26253671/mt5`, server `VantageMarkets-Demo`, Demo, USD, leverage 500, build 6230 และ process เดิมที่กำลังรันก่อน attach ไม่ส่ง/แก้/ปิด order ไม่ relogin ไม่เปิด auto-trade ไม่อ่าน password ไม่ import production config และไม่เปลี่ยน Market Watch

`vantage_readonly.py` ตรวจ account/server/type/path/connection ก่อนและหลังอ่านทุกครั้ง; หากไม่ตรงจะหยุดอ่านและ disconnect Python โดยไม่เปลี่ยนบัญชี ไม่ใช้ `symbol_select` แม้ FixedVol20 ถูกซ่อนไว้

## Symbols และหน่วย

| Feed ที่พบ | Digits | Broker point | Contract | Lot min/step/max |
|---|---:|---:|---:|---|
| XAUUSD | 2 | 0.01 | 100 | 0.01 / 0.01 / 100 |
| XAUUSD.crp | 3 | 0.001 | 100 | 0.01 / 0.01 / 100 |
| FixedVol20 | 3 | 0.001 | 1 | 0.1 / 0.1 / 174 |

ไม่พบ `XAUUSD+` ของ source ledger จึงใช้ XAUUSD เป็น **candidate feed** ไม่รับรองว่าเป็น instrument/execution เดียวกัน Tick arrays ของ XAUUSD กับ XAUUSD.crp ตรงกันทั้ง 74 diagnostic windows ที่เลือกไว้ แต่ specs และ raw M1 arrays ไม่เหมือนกันทั้งหมด จึงไม่อ้างว่า history ทั้งช่วงเหมือนกัน

Web pips ของทั้งสอง source symbols ใช้ราคา / 0.01 จาก accounting audit ส่วน FixedVol20 broker point เป็น 0.001: ราคา 10 = 1,000 web pips = 10,000 broker points ห้ามตีความ trial adapter `point=0.01` เป็น EA input ที่ยืนยันแล้ว

## เวลา: แยก raw ออกจาก UTC จริง

Live anchor ณ `2026-10-08 11:28:33 UTC` ให้ XAU raw tick epoch เทียบเป็น `14:28:35` ต่างประมาณ +10,801 วินาที; FixedVol20 ต่าง +10,801 วินาทีเช่นกัน สนับสนุนว่า numeric epoch ใน terminal นี้เข้ารหัสนาฬิกา server UTC+3 ไม่ใช่ UTC จริง แม้จะใช้ timezone-aware UTC datetime ตาม API

ทดลอง independently กับ ticks 8 จุดกระจายตลอดช่วงต่อ symbol: query raw hour offset 0 ให้ median same-second price error ทอง 0.03 / FixedVol20 0.082; offset ±1–3 ชั่วโมงห่างกว่าชัดเจน ผล M1 ครบทุก order ก็ให้ raw offset 0 เป็นอันดับแรก

ดังนั้นสำหรับ **Vantage terminal นี้และช่วงที่ตรวจ**:

```text
source raw clock = Vantage raw tick/bar clock
inferred actual UTC = raw numeric timestamp - 3h
query Vantage historical ticks = inferred actual UTC + 3h
normalized cache = raw time_msc - 10,800,000
```

นี่ไม่ใช่ IUX query shift +1h; ห้ามนำสูตรข้าม terminal หรือบวก/ลบซ้ำจาก normalized cache

ตัวอย่าง source raw `2026-10-08 01:04:15`: จดเวลาเว็บ `08:04:15` แยกไว้ตามเดิม, inferred UTC `2026-10-07 22:04:15`, Bangkok `05:04:15`, IUX chart `04:04:15`; query Vantage ใช้ numeric timestamp `2026-10-08 01:04:15` ตาม alignment ที่วัดได้ ไม่เอาเลข 01:04 จาก API ไปถือว่าเป็น IUX chart

ผล M1 bid-range containment: ทอง 59,644/62,408 market witnesses; FixedVol20 8,051/8,504 หลังชดเชย M1 spread แบบ diagnostic เป็น 62,214/62,408 (99.689142%) และ 8,435/8,504 (99.188617%) ตามลำดับ Spread ของ M1 ไม่ใช่ spread ทุก tick และ containment ไม่ใช่ proof ว่า execution ตรง

หลักฐานดิบ/metadata: `data/vantage_initial_20261008/` และ `data/vantage_tick_clock_20261008/` เก็บ source hash, specs, offset scores, tick windows และ live anchors

## Export เต็มช่วงและ gaps

ช่วง export inferred UTC `2026-08-18 21:00:00` ถึงก่อน `2026-10-08 01:17:56` รวม warm-up ประมาณ 5 วันก่อน source แรก มีไฟล์รายวัน 52 วันต่อ symbol:

- XAUUSD: 23,158,669 ticks
- FixedVol20: 4,314,340 ticks
- รวม 27,473,009 ticks; invalid quotes = 0

Raw structured arrays เก็บทุก field ที่ API ส่งใน `data/vantage_raw_ticks_vantage_gold_shift3/` และ `data/vantage_raw_ticks_vantage_fixed_shift3/`; time_msc/bid/ask normalized แยกที่ `data/proxy_ticks_vantage_gold_shift3/` / `data/proxy_ticks_vantage_fixed_shift3/` ไม่เขียนทับ raw orders หรือ IUX cache ทุกวันมี SHA-256, query bounds, first/last raw times, spread และ intertick gaps

พบ gaps >60s ทอง 44 จุด / FixedVol20 30 จุด รวมวันหยุด/rollover และช่วงอื่นที่ยังไม่ทราบเหตุ ไม่เรียกทุก gap ว่าข้อมูลสูญหายโดยอัตโนมัติ ตรวจเทียบ M1 แล้วมี 2 จุดที่มี bars แต่ไม่มี ticks:

- XAU: raw `2026-09-01 02:41:32.837`–`02:57:27.940`, 14 M1 bars ด้านใน
- FixedVol20: raw `2026-09-01 02:41:32.009`–`02:58:05.010`, 15 M1 bars ด้านใน

ดึงซ้ำตรงช่วงดังกล่าวแล้วได้เฉพาะ boundary ticks ไม่มี interior ticks ทั้งสอง symbol ไม่มี source order ถือคาบช่วงนี้ แต่ state ของ strategy อาจยังได้รับผล จึงไม่ซ่อน gap/สร้าง ticks จากแท่ง/รีเซ็ต state ตาม ledger เก็บ supplemental response แยกที่ `data/vantage_gap_audit_20261008/`

## Audit ทุก source order

เขียนผลครบ 70,924 events = เปิด+ปิดของ 35,462 orders ใน `data/vantage_full_quotes_20261008/all_source_events.jsonl` รวม close-by 12 close events ที่เป็นราคา reciprocal ไม่ใช่ market quotes จึงมี applicable market witnesses 70,912

| Source symbol | Market witnesses | มี tick ในวินาทีเดียวกัน | มีราคาตรงในวินาทีเดียวกัน | Orders ที่เปิด+ปิดมีราคาตรงในวินาทีเดียวกันทั้งคู่ |
|---|---:|---:|---:|---:|
| XAUUSD+ | 62,408 | 62,396 | 10,637 | 948 |
| FixedVol20 | 8,504 | 8,495 | 2,311 | 29 |

Window -2/+3 วินาทีแสดงแยกในไฟล์ ไม่ยกระดับเป็น exact time match ทุก applicable event มี ticks ใน window นี้ แต่ราคาไม่ตรงจำนวนมาก โดยเฉพาะ FixedVol20 TP level fills การไม่มีราคาตรง tick ไม่ได้พิสูจน์ feed ผิดโดยตัวมันเอง: pending/TP/SL levels, execution/latency และคนละ account conditions ยังต้องแยกทดสอบ

## Continuous replay ที่ทดลองแล้ว

ลอง 4 hypotheses เดิมที่กำหนดไว้ก่อน feed ใหม่: fixed-close level/quote, rolling extrema และ momentum 10s/50 ด้วย SL100/trail40/30, volume10 ทุกแบบ ปล่อย state ต่อเนื่องจาก warm-up ไม่ reset ตาม actual orders/day ไม่จูน parameters จากผลนี้ และไม่เรียกช่วงที่เคยอ่าน ledger แล้วว่า unseen holdout

ไฟล์ original predictions รวม warm-up อยู่ที่ `data/vantage_prespecified_benchmarks_20261008/` คะแนนเปรียบเทียบ ledger window ต้องอ่าน `data/vantage_prespecified_source_window_20261008/report.json`: ตัดเฉพาะ warm-up trades ที่ปิดก่อน source แรกออกจาก scoring โดย **ไม่เปลี่ยน state** และคง position ที่ active ข้าม boundary ไม่ตัดไม้ใน source window

Scorer ใหม่เทียบ symbol/side/lot/open-close seconds/prices/pips/gross P&L/closing label แบบ multiset หนึ่งต่อหนึ่ง เวลา tolerance 0 และความละเอียดราคาต้นทาง ทุก 35,462 rows อยู่ใน denominator รวม FixedVol20 ที่ 4 benchmark นี้ยังไม่จำลอง

| Benchmark | Predictions ใน source window | ตรงทุก observable field | Missing | Extra |
|---|---:|---:|---:|---:|
| Fixed100, level fill | 56,824 | 17 | 35,445 | 56,807 |
| Fixed100, quote fill | 56,379 | 2 | 35,460 | 56,377 |
| Rolling100, level fill | 65,691 | 9 | 35,453 | 65,682 |
| Momentum10s50, level fill | 112,074 | 9 | 35,453 | 112,065 |

ทั้งหมดไม่ผ่าน Source behavior ที่ public closing comment ยังยืนยันไม่ได้มี 108 rows ไม่ใช่การระบุว่า manual 108 ไม้ (เว็บระบุ manual5 แต่ยังไม่รู้ tickets) Matcher ไม่ให้ unknown labels ผ่านเอง และความตรงกับ observable fields ไม่ได้ยืนยัน original EA instance/execution

## สิ่งที่ยังต้องทำ

1. Closed-candle M1/M5/M15/M30/H1 ทดลอง20candidatesแล้ว ทุกแบบยังไม่ผ่าน ดู `CANDLE_GRID_RESULTS.md`; งานถัดไปคือtrailing/SL constraintsจากquote path ไม่จูนpresetวนจากvalidation
2. FixedVol20 grid16presets+trial2candidatesและportfolio2prototypes replayแล้ว รันซ้ำเหมือนกันทุกfield แต่ยังไม่ถอดparameter/session changesหรือemergency paths BestFixed exact14 / validation0 ไม่ใช่source engineที่ยืนยัน
3. ทดสอบ XAU overlap/hedge/recovery/close-by และ lot changes ด้วย causal rules ไม่เติม source entries/close times เป็น actions
4. ขอ original EA inputs/magic/opening comments/Journal/initial state/manual action evidence ถ้ามี ไม่ขอ password; ใช้ประกอบการลด ambiguity ไม่ใช่แทนผล replay

Testsก่อนcandle/gridรอบนี้34ผ่าน ล่าสุดรวม43ผ่าน และartifactQA40models/reproduction118filesผ่าน รายละเอียดใน `CANDLE_GRID_RESULTS.md` ก่อนหน้ารัน `verify_repo.py` compile11scriptsผ่าน แต่globalmojibakeไม่ผ่านจากไฟล์เดิมนอกresearch เช่น `all_nay.txt` /UTF-16strategy outputs ไม่แก้unrelated files; รอบนี้compile10scriptsและresearch-scope mojibakeผ่าน ไม่อ้างglobal repoผ่าน

## คำสั่งทำซ้ำ

```powershell
python -m unittest test_reconstruction test_vantage_readonly test_strict_source_matcher -v
python export_vantage_ticks.py --symbol XAUUSD --tag vantage_gold_shift3 --query-shift-hours 3 --start 2026-08-18T21:00:00 --end 2026-10-08T01:17:56
python export_vantage_ticks.py --symbol FixedVol20 --tag vantage_fixed_shift3 --query-shift-hours 3 --start 2026-08-18T21:00:00 --end 2026-10-08T01:17:56
```

Exporter resume ตรวจ hashes และ metadata ก่อน skip ไม่ overwrite cache ที่ไม่ตรง Probe/audit/benchmark output เป็น exclusive snapshot; ควรเก็บ results เดิมและใช้ชื่อชุดใหม่เมื่อต้องทดลองใหม่ ไม่ลบหลักฐานเดิมเพื่อ rerun
