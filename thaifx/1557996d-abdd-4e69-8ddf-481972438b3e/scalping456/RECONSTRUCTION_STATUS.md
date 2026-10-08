# สถานะการถอด Scalping456

เป้าหมายเดิม: ทำ strategy ที่สร้างครบทุก 35,462 orders ตรง 100% โดยไม่ lookup tickets หรือใช้ผลลัพธ์อนาคต **ยังไม่ผ่าน** ไม่มีการส่ง trade จริงหรือแก้ production bot

## อัปเดตหลังพี่ตั้งค่า Vantage — 8 ตุลาคม 2026

เชื่อมต่อ Demo ที่ระบุได้แล้ว ตรวจ server/account/path และอ่าน FixedVol20 ได้แม้ hidden ไม่เปลี่ยนบัญชี/Market Watch เงื่อนไขเดิมที่ไม่มี Vantage ในเครื่องเปลี่ยนแล้ว ใช้ข้อมูลใหม่ต่อ ไม่ reuse blocked state เดิม

Export bid/ask รวม 27,473,009 ticks (ทอง 23,158,669 + FixedVol20 4,314,340) รวม warm-up โดยแยก raw/normalized/hash/gaps ตรวจทั้ง 35,462 orders ครบ 70,924 open/close events เวลา Vantage raw ตรง source raw; normalized UTC ลบ 3h จากการวัด live anchor และ historical alignment ไม่ใช้ IUX shift

4 benchmarks เดิม replay ต่อเนื่องบน feed ใหม่แล้ว ทุกแบบยังไม่ผ่าน Strict matcher ใหม่เวลา tolerance0 ครบ observable fields ให้ดีที่สุด fixed100 level ตรง17 / missing35,445 / extra56,807 ใน source window ครอบคลุม source denominator ทั้งสอง symbols แต่ 4 models นี้ยังจำลองเฉพาะทอง FixedVol20 4,252 rows ยังนับ missing ทั้งหมด ไม่ถือเป็น full multi-engine replay

พบ 2 gaps มี M1 bars แต่ไม่มี ticks; ดึงซ้ำแล้วไม่มี interior ticks เก็บ evidence ไว้ ไม่สร้าง ticks/รีเซ็ต state เพื่อกลบข้อจำกัด มี tests รวม34 ผ่าน รายละเอียดและงานถัดไปอยู่ใน [`VANTAGE_FEED_REPORT.md`](VANTAGE_FEED_REPORT.md) / [`VANTAGE_EXPERIMENT_PLAN.md`](VANTAGE_EXPERIMENT_PLAN.md) ด้านล่างส่วน IUX เป็นหลักฐานการทดลองก่อนหน้า ไม่ใช่สถานะล่าสุดของ Vantage

## สิ่งที่ทำและตรวจแล้ว

ล่าสุดcomponentทอง0.01ช่วงแรก7,312rowsรัน4frozenfixed-close/OCOcontrolsแล้ว Bestexact9/missing7,303/extra14,085 ในcomponent ส่วนoriginal35,462parentcomparisonexact9/missing35,453/extra14,085 ทั้งหมดไม่ผ่าน Quoteauditครบscopeพบopeningsecondมีticksทุกrowแต่6,039entrypricesไม่เห็นบนexecutablequotes จึงไม่blindlytunequote-fillให้100%โดยไม่แยกexecution/feed/clock assumptions ดู[`FIRST001_RESULTS.md`](FIRST001_RESULTS.md) QA4models/25artifacts+forensics7312rows/bruteforcecrossingsผ่าน Tests89ผ่าน Lotformulaยังไม่identified

ตามพี่ให้ตั้งกรอบแคบลง: แยกทุน$1,000/lot sizingจากentry-exit ตรวจpastclosedgross/strictactive/populationครบ35,462พร้อมindependentQAแล้ว ทองไม่มี0.1 (พบในFixedVol20) และมีrollback1→0.01→1 ยังไม่identifiedbalance/equityformula กำหนดdevelopmentcomponentเป็นทอง0.01ช่วงแรก7,312rowsไม่ตัดexceptions ณlot-scopeรอบแรกยังไม่มีnewscopeentryreplay/auto-lotcloneและTests81ผ่าน (ต่อมารันcomponentตามอัปเดตด้านบนแล้ว) ดู[`LOT_SIZING_SCOPE_RESULTS.md`](LOT_SIZING_SCOPE_RESULTS.md) เป้าหมายเดิมยังไม่ผ่าน ไม่เอาsubsetมาประกาศfullcompletion

ล่าสุดpending-stop32paper controls+32guarded controlsรันครบแล้ว ทุกแบบไม่ผ่าน100% Bestguardedrolling/retain/level/level/16/16ตรง29/missing35,433/extra91,768 (dev20/validation9/cross0) เทียบdenominatorทั้ง35,462ไม่ตัดFixed4,252หรือunknownclosebehavior108 เก็บ320JSONLartifactsรวมสองรอบพร้อมQA/code snapshots Tests74ผ่าน ดู[`PENDING_STOP_RESULTS.md`](PENDING_STOP_RESULTS.md) งานต่อเป็นentry-anchor/placement diagnosticsที่มีหลักฐานรองรับ ไม่ถือmissingEAของพี่เป็นเหตุให้หยุดหรือขอไฟล์เดิมซ้ำ

รอบpath/publicmetadata: ตรวจdefiniteinteriorทุก35,462rowsพร้อมQAประชากรครบ พบXAU`[sl]`525rowsข้ามnominalSL1.10≥5sก่อนcloseบนcandidatefeed และFixedtrial110/143มีpeak-to-close2.8พอดี ทดสอบdistance2.8continuousอีก2modelsแล้วallfields exact0/missing35,462/extra14,369และ14,404 ไม่ใช่clone Publiccurrent-opencommentsระบุPipScalperEA V2 BUY/SELL STOPเป็นหลักฐานใหม่ ไม่รวมopenrowsเข้าclosedsnapshot ณรอบนั้นTests54ผ่าน ดู[`PATH_CONSTRAINT_RESULTS.md`](PATH_CONSTRAINT_RESULTS.md)

ล่าสุดเพิ่มclosed-candle5TF +FixedVol20 grid/trialและportfolio prototypes38+2ชุด รันเต็มต่อเนื่องและตรวจartifactทุกsource rowผ่านแล้ว ทุกแบบยังไม่ผ่าน100% Bestของรอบนี้Fixed grid3/progressive/rolling/quote exact14 (validation0), XAU M1 breakout/level exact6; portfolioที่กำหนดล่วงหน้าexact6และ1 ไม่เลือกsubsetให้ผ่าน Tests43ผ่าน ดู [`CANDLE_GRID_RESULTS.md`](CANDLE_GRID_RESULTS.md) / `data/vantage_candle_grid_replay_20261008_r2/report.json` รันreproductionเสร็จแล้ว118prediction/source-result/extra filesเหมือนรอบแรกทุกbyte พร้อมQA40models ทั้งหมดนี้ยังไม่ใช่goal completion

- Raw CSV / JSONL / normalized CSV: ทุก source value และ ticket population ตรงกันครบ 35,462 รายการ; audit issue count = 0
- แก้ normalized export ไม่ให้ floating-point parser เปลี่ยนเลขกำไรท้ายทศนิยม 175 รายการ และแก้ timezone label ของ IUX จาก +00:00 ที่ผิดเป็น +06:00
- เพิ่มเวลาเว็บเป็น derived display column แยก raw และ inferred UTC ไม่แก้ข้อมูลดิบทับ
- Audit ทุก order โดยรวม 87 XAU special exits และ 33 FixedVol other exits ไม่ตัด 143 SL trial ออก
- รวม special exits แล้ว 68 core orders เปลี่ยน predecessor; direction exceptions เดิมแก้ได้ 8 รายการ แต่ยังเหลือ 243 รายการ
- เก็บ IUX proxy 11,205,398 ticks / 47 วัน (23 ส.ค.–8 ต.ค.) พร้อม SHA-256/provenance และ normalize empirical query shift กลับแล้ว
- Research strategy รองรับ fixed-close, rolling-extrema, lookback momentum, trail activation/distance/step, level/quote stop fills และ FixedVol basket candidate
- เพิ่ม close-by settlement แบบ pure function และ FixedVol20 trial config ที่บังคับใส่ entry/trailing parameters ที่ยังไม่ทราบเอง ไม่ใส่ trigger หรือ ticket ย้อนหลัง
- Testsเดิม20ชุดผ่าน รวมcausal prefix,missing/extra,stop priority,vector/reference parity,close-byและaccounting35,462rows; ล่าสุดรวม43testsเมื่อเพิ่มread-only/strict matcher/candle-grid/trialchecks
- `py_compile` ของไฟล์ที่แก้ผ่าน และ scoped `check_mojibake` ของ folder นี้ผ่าน; full-repo verifier พบ encoding defects เดิมนอก scope เช่น all_nay.txt และ s294_*.txt ไม่แก้ไฟล์เหล่านั้น
- การตรวจล่าสุด `python verify_repo.py <3 modified Python files>`: compile PASS แต่ overall exit 1 เพราะ global mojibake นอก scope; การรัน global checker อีกครั้งเจอ directory หายระหว่างเดิน tree (`strategy/s20.845`) ด้วย Scoped UTF-8/LF/mojibake ของไฟล์ที่แก้ผ่าน ไม่แก้ checker หรือไฟล์งานอื่น

## Continuous replay

Reference replay 15 candidates วันที่ 7–11 กันยายน ใช้ 1,580,504 ticks กับ XAU 5,326 source orders เสร็จแล้ว ผลใน `data/causal_replay_week1.json` และผลราย ticket/candidate ใน CSV ชื่อเดียวกัน

Fixed-close 100 / activation 40 / distance 30 ตรง direction+เวลาเข้า/ออกภายใน ±3s 29.966204% แต่ missing 2,445 และ extra 5,547 รายการ มีเพียง 3 รายการที่ side/lot/seconds/prices ตรงร่วมกันใน scorer จึงไม่ใช่ 100% ทั้งนี้ scorer ยังไม่ยืนยัน source broker execution/P&L/magic

Vector/reference parity บน actual week ผ่านแล้ว: predicted trades 179,017 รายการจาก 15 candidates มีทุก field ตรงกันทั้งหมดระหว่าง `causal_predictions_week1.csv` และ `causal_predictions_week1_vector.csv` ไม่ใช่เฉพาะคะแนนรวม

Replay ครบช่วง `2026-08-23 21:50:00 UTC` ถึงก่อน `2026-10-08 01:17:56 UTC` (inferred clock) **เสร็จแล้ว**: 15 candidates ใช้ 11,098,339 ticks ในขอบเขตกับ XAU ทุกกลุ่ม 31,210 source orders ปล่อย state ต่อเนื่อง ไม่ reset ตาม actual entry/close/day ผลอยู่ใน `data/causal_replay_full_period.json` / `.csv` และ `causal_predictions_full_period.csv` ผลนี้ไม่ได้ replay FixedVol20 อีก 4,252 orders

| Candidate | ทิศ+เวลาเข้า/ออก ±3s ต่อ XAU ทุก source order | Predicted | Missing | Extra | side/lot/seconds/prices ตรงร่วมกัน |
|---|---:|---:|---:|---:|---:|
| Fixed-close 100, level fill, trail 40/30 | 28.641461% | 56,470 | 14,746 | 40,006 | 19 |
| Fixed-close 100, quote fill, trail 40/30 | 28.551746% | 56,182 | 14,776 | 39,748 | 4 |
| Momentum 5s/50, level fill, trail 40/30 | 26.594040% | 108,043 | 15,357 | 92,190 | 21 |
| Rolling 100, level fill, trail 40/30 | 25.059276% | 66,934 | 16,584 | 52,308 | 16 |

แม้คะแนน field joint สูงสุดมี 21 rows แต่เป็นแค่ 6 fields ไม่ใช่ทุกเงื่อนไขของเป้าหมาย ยังไม่ตรวจ execution/P&L/engine และไม่ได้ทำซ้ำครบทุก symbol ผลเต็มผูกกับ strategy SHA-256 `6da188b0971b541518300bccf7c47607bc3ec54a053e048ec27900bf574173c0` ก่อนเพิ่ม close-by helper/trial adapter; ไม่อ้างว่าเป็น full replay ของ file revision ปัจจุบัน

## ตรวจ exception paths จาก source ledger

- Ideal initial SL 100 + trailing activation 40/distance 30 มี payoff support `-100` หรือ `>=10` points แต่ source XAU SL-labelled พบ 372 losses ต่ำกว่า -100, 4,258 small wins ต่ำกว่า 10 และ 162 zero-pip closes รวม 4,792 counterexamples ค่า default นี้จึงถูกปฏิเสธเป็นโมเดลสำหรับทั้ง cohort ไม่ใช่ค่า EA ที่แกะได้
- XAU ถือพร้อมกันสูงสุด 3 positions; พบ positive-duration overlap 303 คู่ / 351 orders โดย 182 คู่เป็นคนละฝั่ง การเปิด/ปิดวินาทีเดียวกันยังไม่ทราบลำดับย่อย
- 372 losses ต่ำกว่า -100 มีเพียง 25 orders ที่ทับซ้อนกับไม้อื่น และ 23 ที่ทับซ้อนฝั่งตรงข้าม อีก 347 ไม่มี strict overlap จึงไม่ใช้คำอธิบาย hedge ครอบทุก tail loss
- Close-by ทั้ง 12 orders / 6 คู่กระทบยอดได้ ไม่มี unresolved pair การลง gross P/L เป็นขาแรก + ขาสองศูนย์แก้ 6 mismatches จากสูตรคิดแยกขา ทำให้ pips และ gross P/L กระทบยอดครบ 35,462 rows; นี่เป็น accounting validation ไม่ใช่ proof ของ trigger/timing
- FixedVol20 trial 143 orders: 70 wins / 70 losses / 3 gross breakeven; 27 losses ตรง -1,000 points และ 43 partial losses ระหว่าง -1,000 กับ 0 ต้องมี exit rule ต่างจาก ideal activation>=distance หรือมี quote/execution effects
- Unusual exits 120 rows ถูกเก็บครบใน 83 diagnostic groups ไม่ถือ group เป็น recovered EA instance/basket ID

รายละเอียดและข้อจำกัดอยู่ใน `EXCEPTION_PATHS.md` / `data/exception_paths_report.json`

## หลักฐานที่ยังไม่มีสำหรับพิสูจน์ 100% (ไม่ใช่รายการให้พี่จัดหา)

1. Bid/ask tick history ของ Vantage ต้นทาง ทั้ง XAUUSD+ และ FixedVol20 พร้อม timezone/contract specs
2. EA settings/version, magic/instance IDs, opening comments, initial state และ Journal
3. หลักฐานของการเปลี่ยน lot/parameters, session stops, hedge/recovery และ forced/manual actions
4. Full causal replay ที่ตรง side/symbol/engine/lot/open-close times/prices/pips/P&L ครบหนึ่งต่อหนึ่ง ไม่มี missing/extra หรือการตัดข้อยกเว้นออก

พี่ยืนยันว่าไม่มีEAต้นทางแล้ว งานต่อใช้ข้อมูลสาธารณะ/marketdataที่อ่านได้ ไม่รอหรือขอEA/.set/Journalจากพี่ซ้ำ Closed orders อย่างเดียวระบุ source algorithm ไม่เป็นเอกลักษณ์ การได้ distribution คล้ายหรือ matched-only percentages สูงยังไม่ผ่านเป้าหมายเดิม

Inventory ก่อนพี่ตั้งค่า Vantage เคยมีเพียง Exness/IUX และ real VT Markets; ขณะนี้มี Vantage Demo และ export ตลาดแล้ว แต่ `XAUUSD+` ไม่พบ (มี XAUUSD/.crp) และยังไม่ยืนยัน original feed/account execution Public ledger ยังมี 14 fields ไม่ให้ magic/modify history รายการ original source exports/EA evidence และ verification boundary อยู่ใน `SOURCE_DATA_REQUIRED.md` ไม่ต้องส่งรหัสผ่าน ไม่สร้างบัญชีหรือเปิด trade เพิ่ม

## ทำซ้ำ

รันจาก folder นี้ โดยใช้ bundled Python สำหรับ offline analysis; MT5 exporter ใช้ Python ที่มี MetaTrader5 connector ซึ่งไม่มีใน bundled runtime:

```powershell
python audit_ledger.py
python audit_exception_paths.py
python -m unittest test_reconstruction -v
python replay_causal.py --start 2026-09-07 --end 2026-09-12 --tag week1 --engine reference
python replay_causal.py --start 2026-08-23T21:50:00 --end 2026-10-08T01:17:56 --tag full_period --engine vector
```

ต้องตรวจ cache provenance และผล process จริงก่อน rerun ไม่เริ่มซ้ำเพียงเพราะไม่ได้รับ output ระหว่างรอ
