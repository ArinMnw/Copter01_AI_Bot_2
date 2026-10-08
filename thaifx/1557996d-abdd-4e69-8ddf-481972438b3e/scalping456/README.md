# Scalping456 research snapshot

แหล่งข้อมูลหลัก: [ThaiFXBook — Scalping456](https://thaifxbook.com/p/1557996d-abdd-4e69-8ddf-481972438b3e)

ชุดนี้เป็น snapshot สำหรับถอดพฤติกรรมระบบจากประวัติ closed orders สาธารณะ ณ วันที่ 8 ตุลาคม 2569 ไม่ใช่ source code ของ EA และยังไม่ใช่กฎ entry ที่ยืนยันแล้ว

## เริ่มอ่านจากตรงไหน

- [`SUMMARY.md`](SUMMARY.md) — บทสรุปสำคัญและคำตอบว่าเทคนิคทำงานอย่างไร
- [`PROFILE_SNAPSHOT.md`](PROFILE_SNAPSHOT.md) — ตัวเลขที่หน้าเว็บแสดงและข้อควรระวังเรื่อง snapshot
- [`ORDER_ANALYSIS.md`](ORDER_ANALYSIS.md) — ผลวิเคราะห์จาก closed orders 35,462 รายการ
- [`STRATEGY_HYPOTHESIS.md`](STRATEGY_HYPOTHESIS.md) — state machine ที่อนุมานได้/ยังอนุมานไม่ได้ และแผนถอดเป็น strategy
- [`TIMEZONE_EVIDENCE.md`](TIMEZONE_EVIDENCE.md) — หลักฐานสนับสนุน inferred server UTC+3 และวิธีแยก raw/web/chart time
- [`RECONSTRUCTION_STATUS.md`](RECONSTRUCTION_STATUS.md) — สถานะ goal, เกณฑ์ 100%, ผล replay และข้อมูลที่ยังขาด
- [`VANTAGE_FEED_REPORT.md`](VANTAGE_FEED_REPORT.md) — ล่าสุดหลังตั้งค่า Vantage: 27.47 ล้าน ticks, เวลา server/raw, full-source quote audit และ strict replay benchmarks
- [`VANTAGE_EXPERIMENT_PLAN.md`](VANTAGE_EXPERIMENT_PLAN.md) — แผนก่อนเลือก parameters ใหม่, read-only guards และข้อจำกัดของ holdout
- [`CANDLE_GRID_RESULTS.md`](CANDLE_GRID_RESULTS.md) — closed-candle5TF /grid/trial/portfolio38+2ชุด แบบcontinuous พร้อมfull-source QA และคำสั่งทำซ้ำ
- [`PATH_CONSTRAINT_RESULTS.md`](PATH_CONSTRAINT_RESULTS.md) — quote pathsครบ35,462rows, SL/trailingข้อขัดแย้ง, publicpending-stopcommentsใหม่ และdistance2.8replaysที่ยังไม่ผ่าน
- [`PENDING_STOP_RESULTS.md`](PENDING_STOP_RESULTS.md) — pending-stop32แบบและguarded32แบบเสร็จแล้ว เทียบครบทุกsource row; bestexact29/missing35,433/extra91,768 ยังไม่ใช่clone
- [`LOT_SIZING_SCOPE_RESULTS.md`](LOT_SIZING_SCOPE_RESULTS.md) — ตามพี่ให้แคบลง: แยกlot sizing/ทุน$1,000จากprice mechanism ตรวจtimelineครบทุกrowและกำหนดทอง0.01ช่วงแรก7,312เป็นcomponent study ยังไม่ใช่recoveredauto-lot
- [`NARROW_RESEARCH_PLAN.md`](NARROW_RESEARCH_PLAN.md) — กรอบก่อนlotdiagnostic: accountgrossไม่ใช่balance/equity, no source-clock lot switches, ไม่รวมFixedVol20กับทอง
- [`FIRST001_RESULTS.md`](FIRST001_RESULTS.md) — ล่าสุด: ลงมือcomponentทอง0.01ครบ7,312แล้ว 4controlsbestexact9ยังไม่ผ่าน; sourceentryprices6,039ไม่ปรากฏบนexecutablequotesในreportedsecondภายใต้directquote-fillassumption
- [`EXCEPTION_PATHS.md`](EXCEPTION_PATHS.md) — payoff counterexamples, portfolio overlaps, close-by และ FixedVol20 trial
- [`SOURCE_DATA_REQUIRED.md`](SOURCE_DATA_REQUIRED.md) — ข้อจำกัดของข้อมูลสาธารณะต่อการพิสูจน์exact replay ไม่ใช่รายการให้พี่หาEAหรือรหัสผ่านมาเพิ่ม
- [`data/README.md`](data/README.md) — data dictionary, วิธีตรวจความครบ และไฟล์ข้อมูลดิบ

## ไฟล์สำหรับทำซ้ำ

- `download_orders.py` — ดึง 1,774 หน้า หน้าละ 20 รายการผ่าน public Next.js server action
- `analyze_orders.py` — สร้างสถิติและไฟล์ aggregate ใหม่จาก CSV ดิบ
- `research_scalping456.py` — เทียบ orders กับ tick feed อิสระและวัด entry/exit features
- `infer_state_machine.py` — วิเคราะห์ transition ระหว่าง orders และ replay trigger hypothesis
- `strategy_scalping456.py` — tick-driven research candidates; ยังไม่ใช่ clone ที่ยืนยัน 100%
- `audit_ledger.py` — reconcile ทุก order และตรวจ predecessor โดยไม่ข้าม special exits
- `audit_exception_paths.py` — all-row pips/gross reconciliation พร้อม close-by allocation และ chronological overlaps
- `export_proxy_ticks.py` — read-only MT5 tick export สำหรับ offline replay ไม่ส่ง trade requests
- `replay_causal.py` / `replay_vector.py` — continuous reference/accelerated replay ไม่ reset ตาม observed orders
- `test_reconstruction.py` — behavior, causality, matching และ vector/reference parity tests ไม่ใช่หลักฐานว่า source EA ถูก clone สำเร็จ
- `replay_pending_vector.py` / `replay_vantage_pending.py` — pure pending-stop lifecycle, continuous32models, guard controls, full-source/extras/entry-only diagnostics
- `verify_pending_experiment.py` / `test_pending_*.py` — population/hash/one-to-one/causality/parity checks; ณรอบpendingรวมresearch tests74ผ่าน
- `analyze_lot_scope.py` / `verify_lot_scope.py` / `test_lot_scope.py` — all-source lot/pre-entrygross timelineและindependentQA; ณรอบlot-scopefullresearch suite81testsผ่าน
- `first001_components.py` / `replay_first001.py` / `diagnose_first001.py` / `verify_first001.py` — bounded4controlsและentry/exitforensics แยกpredictionsจากwitnesses; fullsuiteล่าสุด89testsผ่าน

ตัวเลขจำนวน order ที่ยืนยันจากหน้าเว็บและข้อมูลดิบคือ **35,462 รายการ** ไม่ใช่ 36,462 รายการ

