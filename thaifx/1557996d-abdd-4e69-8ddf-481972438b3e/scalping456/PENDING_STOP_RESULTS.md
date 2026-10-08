# Pending stop: ผลทดลองครบ 32 แบบ + 32 execution controls

8 ตุลาคม 2026 — ทดลองต่อจาก public opening comments ที่ระบุ `PipScalperEA V2 BUY STOP` / `SELL STOP` ไม่รอหรือขอ EA จากพี่เพิ่ม **ยังไม่พบ strategy ที่ทำซ้ำ 35,462 orders ได้ครบหนึ่งต่อหนึ่ง** ไม่มีการส่ง trade หรือแก้ production bot

## ข้อสรุป

- ทดสอบ pending ที่มีอยู่ก่อน quote ที่ fill ไม่ใช้ market entry หรือวาง pending ย้อนหลังจาก quote ที่เห็นแล้ว
- รอบแรก 32 ideal-paper controls และรอบตรวจ trailing proposal อีก 32 แบบเสร็จแล้ว ใช้ parameters ชุดเดิมทั้งหมด ไม่เลือกเฉพาะผู้ชนะไปปรับค่า
- คะแนนสูงสุดของทั้งสองรอบตรงครบ observable fields เพียง **29 / 35,462 orders**; รอบ guarded มี missing **35,433** และ extra **91,768** จึงปฏิเสธชุดกฎนี้เป็น clone ของประวัติทั้งหมด
- แบบที่ตรงเฉพาะ entry มากที่สุดตรง symbol/side/lot/วินาที/ราคาเข้า 179 rows; เมื่อตัด lot ออกจากการเทียบตรง 259 rows ตัวเลขเหล่านี้ **ไม่ใช่จำนวนออเดอร์ที่จำลองสำเร็จ** และไม่ใช้ reset state
- พฤติกรรม pending stop ยังเป็นเบาะแสที่มีหลักฐาน แต่ last-close/rolling-extrema + ระยะราคา1 + trailing คงที่ + opposite policy อย่างง่าย ยังอธิบายประวัติไม่ได้

## แผนและตัวจำลอง

แผนก่อน predictions: [`EXPERIMENT_PENDING_STOP_PLAN.md`](EXPERIMENT_PENDING_STOP_PLAN.md) และก่อนรอบ guarded: [`EXPERIMENT_PENDING_TRAIL_GUARD_PLAN.md`](EXPERIMENT_PENDING_TRAIL_GUARD_PLAN.md)

2 anchors (`fixed_close` จากราคาปิดที่จำลองเอง / `rolling_extrema` จาก lowAsk/highBid ขณะ flat) × 2 policies (OCO ยกเลิก pending ตรงข้ามเมื่อ fill / retain เก็บฝั่งตรงข้ามและ re-arm ฝั่งที่ปิด) × entry fill level/quote × stop fill level/quote × trailing 40/30 หรือ 16/16 points = 32 แบบ

ทุกแบบใช้ entry distanceราคา1, initial SLราคา1, point.01, lot10 คงที่ ไม่ใส่เวลาเปลี่ยน lot, session, ticket หรือ source entry/exit ลง signal module ค่า16/16มาจาก development path diagnostic ไม่ใช่ recovered EA inputs ส่วน40/30เก็บเป็น benchmark เดิมที่ถูกปฏิเสธแล้ว

ลำดับต่อ quote: ตรวจ SL ของ position เดิม → fill pending เดิม → trailing position ที่รอด → วาง/ขยับ pending ใหม่ Pending ที่เพิ่งสร้างต้องรอ quote event ถัดไป แม้ timestamp millisecond เท่ากัน Newly opened position ไม่ reuse opening quote เพื่อ stop/trail ซึ่งเป็นสมมติฐาน paper execution ไม่ใช่หลักฐานการทำงาน server จริง

รอบแรกพบว่า level fill ผ่าน gap อาจทำให้ peak จาก opening quote เสนอ trailing SL ผิดด้าน current price ใน quote ถัดมา จึงเก็บรอบแรกไว้แล้ว rerun **ทุก32แบบ** โดยรับเฉพาะ BUY proposal < currentBid / SELL proposal > currentAsk และเก็บ SL เดิมเมื่อ proposal ใช้ไม่ได้ [กฎ protective price ของ MetaQuotes](https://www.mql5.com/en/book/automation/symbols/symbols_spreads_levels) รองรับการใช้ Bid/Ask ตามฝั่ง แต่ guard นี้ยังไม่จำลอง minimum stop distance, freeze level, latency หรือ server acceptance ของบัญชีต้นทาง

## ขอบเขตและเกณฑ์ exact

- Cache Vantage เดิม: export ทอง23,158,669 ticks / FixedVol20 4,314,340 ticks; ตรวจ hashes, chronology, symbol และ raw→inferredUTC shift ก่อน replay รอบ pending ใช้เฉพาะทอง
- Warm-up เริ่ม Aug18 21:00 UTC; จบก่อน Oct8 01:17:56 UTC ไม่มี day/split/source-entry resets สร้างทั้ง32 trajectories ก่อนอ่าน source outcomes เพื่อ scoring
- Source JSONL SHA-256 `b8f5f75de07ba335ba607855167b5c77600954561c7c740621a335fa1b9825f1` ไม่แก้ทับ ทุก model มี source results ครบ35,462 unique tickets และเก็บ predicted extras ทุกตัว
- Exact เทียบ symbol, side, lot, open/close second, open/close price, pips, gross P/L และ close behavior แบบหนึ่งต่อหนึ่ง ณ source precision เวลา tolerance0 ไม่เทียบแค่ทิศหรือกำไรคล้ายกัน
- ทั้ง4,252 FixedVol20 source rows นับ missing ในรอบ XAU นี้ ไม่อ้างว่าเป็น full multi-engine replay และไม่เอาผล Fixed experiments เดิมมาเติมให้ดูผ่าน
- Close behavior ที่ public ledger ยังยืนยันไม่ได้108rowsยังอยู่ใน denominator ไม่ตีความว่าเป็น108manual orders; aggregate manual5 ยังไม่ทราบ tickets
- Split Sep21 00:00 UTC: development24,350 / cross-boundary4 / chronological validation11,108 ประวัติถูกอ่านแล้วจึง **ไม่ใช่ unseen holdout** ไม่ใช้ validation scores เลือก parameters

## ผลทุก configuration

รูปแบบตัวเลขในสองคอลัมน์ท้ายคือ **exact / missing / extra** ต่อ source35,462ทุกครั้ง `level` เป็น ideal fill ที่ pendinglevel/SLlevel; `quote` เป็น executable Ask/Bid ณ hit ส่วน Guarded เพิ่มเพียง trailing proposal validity ไม่ใช่ certified broker execution

| Anchor / Policy | Entry / Stop / Trail | Paper control | Guarded proposal |
|---|---|---:|---:|
| fixed_close / oco | level / level / 40/30 | 22 / 35440 / 53546 | 22 / 35440 / 52540 |
| fixed_close / oco | level / level / 16/16 | 24 / 35438 / 68713 | 25 / 35437 / 67471 |
| fixed_close / oco | level / quote / 40/30 | 2 / 35460 / 57128 | 2 / 35460 / 57092 |
| fixed_close / oco | level / quote / 16/16 | 5 / 35457 / 68991 | 5 / 35457 / 68930 |
| fixed_close / oco | quote / level / 40/30 | 17 / 35445 / 55052 | 17 / 35445 / 55052 |
| fixed_close / oco | quote / level / 16/16 | 18 / 35444 / 66411 | 18 / 35444 / 66411 |
| fixed_close / oco | quote / quote / 40/30 | 2 / 35460 / 56377 | 2 / 35460 / 56377 |
| fixed_close / oco | quote / quote / 16/16 | 4 / 35458 / 67167 | 4 / 35458 / 67167 |
| fixed_close / retain | level / level / 40/30 | 0 / 35462 / 260 | 0 / 35462 / 260 |
| fixed_close / retain | level / level / 16/16 | 0 / 35462 / 258 | 0 / 35462 / 258 |
| fixed_close / retain | level / quote / 40/30 | 0 / 35462 / 290 | 0 / 35462 / 290 |
| fixed_close / retain | level / quote / 16/16 | 0 / 35462 / 286 | 0 / 35462 / 285 |
| fixed_close / retain | quote / level / 40/30 | 0 / 35462 / 278 | 0 / 35462 / 278 |
| fixed_close / retain | quote / level / 16/16 | 0 / 35462 / 263 | 0 / 35462 / 263 |
| fixed_close / retain | quote / quote / 40/30 | 0 / 35462 / 303 | 0 / 35462 / 303 |
| fixed_close / retain | quote / quote / 16/16 | 0 / 35462 / 284 | 0 / 35462 / 284 |
| rolling_extrema / oco | level / level / 40/30 | 21 / 35441 / 66622 | 21 / 35441 / 66601 |
| rolling_extrema / oco | level / level / 16/16 | 24 / 35438 / 83140 | 24 / 35438 / 83094 |
| rolling_extrema / oco | level / quote / 40/30 | 5 / 35457 / 66638 | 5 / 35457 / 66617 |
| rolling_extrema / oco | level / quote / 16/16 | 3 / 35459 / 83161 | 3 / 35459 / 83115 |
| rolling_extrema / oco | quote / level / 40/30 | 9 / 35453 / 65682 | 9 / 35453 / 65682 |
| rolling_extrema / oco | quote / level / 16/16 | 8 / 35454 / 80580 | 8 / 35454 / 80580 |
| rolling_extrema / oco | quote / quote / 40/30 | 2 / 35460 / 65689 | 2 / 35460 / 65689 |
| rolling_extrema / oco | quote / quote / 16/16 | 0 / 35462 / 80588 | 0 / 35462 / 80588 |
| rolling_extrema / retain | level / level / 40/30 | 21 / 35441 / 74325 | 21 / 35441 / 74295 |
| rolling_extrema / retain | level / level / 16/16 | 29 / 35433 / 91821 | 29 / 35433 / 91768 |
| rolling_extrema / retain | level / quote / 40/30 | 3 / 35459 / 74343 | 3 / 35459 / 74313 |
| rolling_extrema / retain | level / quote / 16/16 | 4 / 35458 / 91846 | 4 / 35458 / 91793 |
| rolling_extrema / retain | quote / level / 40/30 | 13 / 35449 / 73102 | 13 / 35449 / 73102 |
| rolling_extrema / retain | quote / level / 16/16 | 12 / 35450 / 89058 | 12 / 35450 / 89058 |
| rolling_extrema / retain | quote / quote / 40/30 | 1 / 35461 / 73114 | 1 / 35461 / 73114 |
| rolling_extrema / retain | quote / quote / 16/16 | 2 / 35460 / 89068 | 2 / 35460 / 89068 |

คะแนนสูงสุด rolling/retain/level/level/16/16 ของรอบ guarded สร้าง100,741 predictionsรวมwarm-up / 91,797ในsource window: exact29, missing35,433, extra91,768 ทั้ง29เป็นXAU SL-labelled rows (development20 / validation9 / cross0) ทุกcohortอื่นexact0 การลด extrasเพียง53จากcontrolเดิมไม่แก้ความไม่ตรงระดับระบบ

Entry-only สูงสุด fixed/OCO/entrylevel/stopquote/16/16 ของรอบ guarded: predictions68,935; with-lot matched179/missing35,283/extra68,756; without-lot matched259/missing35,203/extra68,676 ขณะที่ full-order exactเพียง5 ไม่ใช้259แทนผล29หรืออ้างว่ารู้ entry rule แล้ว

## หลักฐานที่เก็บและ QA

- `data/vantage_pending_replay_20261008/` — 32 paper controls; report SHA-256 `96abe51c37e957d20abdddd001386246f584b48476ac3b9fa852106b3fd2f43f`
- `data/vantage_pending_guarded_replay_20261008/` — 32 guarded controls; report SHA-256 `9fe7ca7a8aac1644ee1970463eefc3dd43e4fbf28a4a883d92c8f332c9163c70`
- แต่ละ folder มี160 JSONL artifacts: predictionsรวมwarm-up, all_source_results, extras, entry_all_source_results, entry_extras อย่างละไฟล์ต่อmodel พร้อมconfig/phase/cohort/cache/code/plan hashesในreport
- QA ตรวจsource population, one-to-one uniqueness, full matcher recomputation, diagnostic maximal multiset matching, extrasครบ, split/cohort sums และ160artifact hashes ไม่ใช่ตรวจแค่คะแนนรวม
- QAทั้งสองรอบเสร็จและexit0: control `qa_audit.json` / ตรวจซ้ำกับarchivedrevision `qa_archived_code.json`; guarded `qa_audit.json` ตรวจกับcurrentcodeตรงsealedhash ทั้งสองreportระบุ`full_source_clone_complete=False`
- Reference/vector parity ของทุก32แบบในแต่ละรอบบน actual Sep7 00:00–01:00 UTC sample ตรงทุก prediction field ไม่อ้างว่าreference engineรันครบfullperiod; fullperiodใช้acceleratorที่ผ่านparity/synthetic/future-prefix tests
- รวม74 unit testsผ่าน (54เดิม+10pending lifecycle+4entry matcher+6guard) รวมgap, spread, same-millisecond events, invalid placement, retained opposite, stop-before-modify และ changed-future prefix Tests/QAไม่ใช่proofของoriginalEA
- ก่อนเปลี่ยนcodeเก็บhash-verified copiesใน `data/code_snapshots/` รวมstrategyก่อนpendingและก่อนguard ไม่แก้old experiment data รอบแรกverifyกับarchived revisionได้ผ่านexplicit flag; default verifierยังrejecthashต่างตามเดิม
- `py_compile` ทั้ง7modifiedPython filesผ่าน และscoped `check_mojibake.find_issues` + strictUTF-8/LFตรวจ16code/plan/Markdown filesผ่าน ไม่อ้างglobalrepoverificationผ่าน (รอบก่อนพบencoding issuesนอกscope ดู `RECONSTRUCTION_STATUS.md`)

## สิ่งที่ตัดออกได้ / สิ่งที่ยังไม่รู้

ปฏิเสธได้เฉพาะ32ชุดกฎที่ระบุ บนcandidatefeed/initialstate/execution assumptionsนี้ ไม่ได้ปฏิเสธpending-stopทุกชนิดหรือพิสูจน์EAของเจ้าของ Profileopencommentsเป็นหลักฐานณsnapshotปัจจุบัน ไม่ยืนยันทุกclosedrowใช้EA/versionเดียวกัน

Fixed-close+retainสร้างsource-window ordersเพียง258–303และexact0: ราคาตรงข้ามเก่าหรือpending levelผิดด้านทำให้policyอย่างง่ายนี้ไม่รักษาการเทรดต่อเนื่องของsource ส่วนrolling+retainยิงเกินมาก ยังไม่มีหลักฐานสำหรับpending repricing/throttling, SL arming, originalfeed/latency, startup state, source max3 positions, close-by/recovery หรือ lot/risk transitions

งานถัดไปที่มีเหตุผลคือ forensic entry-anchor/placement diagnostics บนquotesที่เกิดก่อนentry แยกผล spread/rounding/gapจากanchor/repricing และแยกprice mechanismจากlot changesก่อนกำหนดcausal hypothesisใหม่ ไม่ใส่sourceclock/ticketexceptionsหรือจูนค่าให้matchย้อนหลัง ข้อมูลที่publicledgerไม่มีบันทึกใน `SOURCE_DATA_REQUIRED.md` เป็นข้อจำกัดของการพิสูจน์ ไม่ใช่รายการให้พี่หาEAมาเพิ่ม

หลังพี่ให้ตั้งกรอบแคบลง กำหนดcomponentเป็นทอง0.01ช่วงแรก7,312rowsและตรวจlot/pastgrossแยกก่อนแล้ว ดู[`LOT_SIZING_SCOPE_RESULTS.md`](LOT_SIZING_SCOPE_RESULTS.md) ยังไม่แก้scoresหรือconfigsของpendingexperimentsนี้ และยังไม่ยืนยันกฎทุน$1,000→lotจากbalance/equityจริง

## ทำซ้ำ

รันจากresearch folder ใช้freshtagเสมอ ไม่เขียนทับevidence และถ้าtoolหมดเวลาสังเกตให้ติดตามprocessเดิม ไม่เริ่มreplayซ้ำ

```powershell
python -m unittest test_reconstruction test_vantage_readonly test_strict_source_matcher test_candle_grid_replay test_broker_bars_trial test_quote_path_diagnostics test_path_public_trial test_pending_stop test_pending_entry_matcher test_pending_trail_guard -q
python replay_vantage_pending.py --tag NEW_GUARDED_TAG --require-valid-trail
python verify_pending_experiment.py --tag NEW_GUARDED_TAG
```

ตรวจold controlsเมื่อcodeปัจจุบันต่างจากตอนทดลอง โดยexplicitlyยอมรับarchivedrevisionและใช้auditfilenameใหม่:

```powershell
python verify_pending_experiment.py --tag vantage_pending_replay_20261008 --allow-archived-code --audit-name NEW_AUDIT.json
```

`--allow-archived-code` ตรวจdigestที่reportsealedไว้กับsnapshotที่ตรงกัน ไม่ลดเกณฑ์hash ไม่คัดลอกledgerเข้าpredictions Currentdefault `require_valid_trail=False` เก็บไว้เพื่อcompatibilityกับideal-paper controls; งานใหม่ควรระบุguardexplicitlyและยังไม่ถือเป็นproduction execution
