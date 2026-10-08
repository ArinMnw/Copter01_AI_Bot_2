# Quote paths / public metadata: ผลตรวจครบทุก source order

8 ตุลาคม 2026 — เป้าหมาย strategy ตรง 35,462 orders หนึ่งต่อหนึ่งยังไม่ผ่าน ผลนี้เป็น forensic observations บน candidate Vantage feed ไม่ใช่ source-seeded predictions และไม่เปลี่ยนคะแนน replay เดิม

## Provenance และขอบเขต

- Source JSONL SHA-256 `b8f5f75de07ba335ba607855167b5c77600954561c7c740621a335fa1b9825f1` ไม่แก้ทับ
- ใช้ normalized caches เดิม 27,473,009 ticks; ตรวจ SHA-256/symbol/shift/count/chronology ก่อนอ่าน ไม่ดึง ticks ใหม่ ไม่ส่ง trade
- แผนก่อนวิเคราะห์: `PATH_DIAGNOSTIC_PLAN.md`; ผลราย order: `data/vantage_path_constraints_20261008/all_source_quote_paths.jsonl`
- `report.json` และ `qa_constraints.json` ตรวจ 35,462 unique tickets ตรง source population ทุกตัว ไม่มี source missing/extra **ใน diagnostic output** ไม่ใช่ missing/extra0ของ strategy
- ขอบเขต `[open_second+1s, close_second)` ตัดวินาทีเปิด/ปิดซึ่งไม่ทราบลำดับย่อยออก BUY ใช้ bid / SELL ใช้ ask เก็บ 12 close-by และทุก special exit ไว้ ไม่มีสร้าง action จาก ledger

## Initial-stop / past-extrema barriers

ระยะ nominal XAUราคา1 / Fixed trialราคา10เป็น benchmark ที่อนุมานจาก closed outcomes ไม่ยืนยัน initial SLจริง ตรวจ strict beyond nominal+10% และ leadก่อนclose≥5s เพื่อตัดความคลุมเครือใกล้boundary; sensitivityนี้ไม่ใช่ toleranceของ exact matcher

| Cohort | Source rows | มี definite interior quotes | ข้าม nominal+10% ≥5sก่อนclose | ละเมิด ratchet benchmark ≥5sก่อนclose |
|---|---:|---:|---:|---:|
| XAU `[sl]` | 31,123 | 30,699 | 525 | 3,658 |
| XAU other รวมclose-by | 87 | 87 | 77 | 87 |
| Fixed SL trial | 143 | 143 | 1 | 20 |
| Fixed TP | 4,076 | 4,075 | ไม่กำหนด | ไม่กำหนด |
| Fixed other | 33 | 33 | ไม่กำหนด | ไม่กำหนด |

Ratchet benchmark คือ XAU activation.4/distance.3 และ Fixed trial activation0/distance10 ใช้ extremaที่เกิดแล้วเท่านั้น ตรวจ barrierก่อนยกระดับstop ไม่ใช่ simulated fills. Special/close-by ไม่ได้ถูกยืนยันว่าควรใช้ benchmarkนี้ ตัวเลขจึงเป็น compatibility checkของสมมติฐาน uniform rules ไม่ใช่ระบุสาเหตุการปิดจริง

425 source rows ไม่มี interior quotesตามนิยามนี้แต่ยังเก็บครบ ไม่ใช่425rowsที่ถูกตัดออกจากgoal มี71rowsที่interval intersectกับ gaps>60s ซึ่งรวมrollover/weekend; ไม่ถือทุกgapเป็นmissing broker historyโดยอัตโนมัติ

ตัวอย่างworst XAU `[sl]` ticket1645015941: SELLentry4331.45/close4381.82 ถือ103,470s มี835,261 interior quotes, MFE+.70/MAE−68.30ราคา บนfeedนี้ข้ามnominal1.10ตั้งแต่103,424.756sก่อนclose จึงไม่สอดคล้องกับSL1ที่activeตลอดและไม่loosen หากfeed/clockตรงsourceจริง แต่ยังแยก stop changes, terminal/execution, intervention หรือfeeddifferenceไม่ได้ ห้าม hard-code exception ticketเพื่อสร้างstrategy

Fixed TP1,336rowsมีquoteข้ามfinalreportedTPก่อนวินาทีclose ในนี้1,312rows lead≥5s **ไม่ใช่proofว่าTPควรปิดก่อน** เพราะยังไม่ทราบว่าfinalbasketTPถูกตั้งเมื่อใด/เปลี่ยนอย่างไร ข้อเท็จจริงนี้ทำให้ต้องมีmodify historyเพื่อทดสอบdynamicTP

## Trailing / lot constraints ที่เพิ่มขึ้น

- Fixed trial143rowsอยู่developmentก่อนSep21ทั้งหมด ไม่เหลือtrial-specific validation population ภายใต้splitเดิม
- 110/143 มีobservedpeak-to-close distanceราคา2.8พอดีที่feedresolution: price-positive72 / price-negative38 (ไม่เท่ากับgrosswin70เพราะmoneyrounding)
- อีก33rowsมีpipsต่ำกว่า−280 ในนี้27เป็นnominal−1000 losses; จึงยังไม่อ้างว่าactivation0/distance2.8uniformอธิบายทั้งหมด
- XAUprice-positive distance modeราคา.16ในdevelopment1,512rowsและchronologicalvalidation653rows แต่counterexamplesและfeeddifferenceยังอยู่ ไม่ถือmodeเป็นEAinput
- XAU chronological adjacent-volume runs7ช่วง: .01(7,312),1(948),.01(173),1(962),10(17,510),.4(1),10(4,304). เก็บfirst/lastrawtimesในqa report แต่ไม่สร้างclock-basedswitchesจากเวลาที่เห็น Lot .4โดดเดี่ยวไม่พอระบุmanual ticket
- Fixedมี3,145adjacent-volume segments; ไม่ถือแต่ละsegmentเป็นsettingschangeหรือEAinstance ต้องแยกgrid progressionจากrisk/manual/engineด้วยหลักฐานจริง

## Distance2.8 causal replay ที่ทำแล้ว

แผน `EXPERIMENT_TRIAL28_PLAN.md` กำหนดก่อนรัน ใช้entryราคา3/initialSL10/activation0/lot.1เดิม เปลี่ยนเพียงdistance10→2.8 ในlevel/quotefills สร้างpredictionsจากfirstwarm-upquoteโดยไม่อ่านsourceoutcomesก่อนsignals ไม่ reset/sessiongateตามtrialdates

| Candidate | Predictionsรวมwarm-up | Predictionsในsource window | All-field exact | Missingต่อ35,462 | Extra |
|---|---:|---:|---:|---:|---:|
| Trial a0/d2.8 level | 16,107 | 14,369 | 0 | 35,462 | 14,369 |
| Trial a0/d2.8 quote | 16,158 | 14,404 | 0 | 35,462 | 14,404 |

Actual-feedreference/vectorparityทั้งสองผ่าน แต่strictmatcherครบfields/time tolerance0ไม่ผ่าน `data/vantage_trial28_replay_20261008/` เก็บpredictions/allsource results/extras/phase scores/provenance/hashและQAทั้งสองmodels ไม่มี source exceptionsซ่อน ไม่มีtrial rowในvalidationจึงห้ามอ้างtrial holdoutผ่าน

## Public schema / opening comments ที่เพิ่งพบ

จาก[หน้าโปรไฟล์สาธารณะ](https://thaifxbook.com/p/1557996d-abdd-4e69-8ddf-481972438b3e) archiveGET+27observedfirst-partyclient scripts และactionpaginationpage1ตามUIเดิม ไม่authenticate/เดาprivateAPI/อ่านpassword. `data/public_schema_20261008/` แยกจากorders snapshot; `metadata_extract_v2.json`แก้fieldnamesของextractorครั้งแรกโดยรักษา`metadata_extract.json`ไว้

- Closed table+paginationยังให้14fieldsเหมือนJSONLทั้ง35,462rows ไม่มีmagic/deal/position IDsหรือcommissionรายorder ข้อมูลไม่ได้หายเพราะCSVเลือกcolumnsน้อย
- AggregateยังระบุEA35,457/manual5 แต่ไม่ให้5ticketsนั้น แค่UIข้อความบอกว่าใช้magicไม่ใช่magicvaluesที่นำมาauditได้
- Public current-openobservations2rowsมีcomments `PipScalperEA V2 BUY STOP` และ `PipScalperEA V2 SELL STOP`, symbolXAUUSD+, volume10, SL/TP fields0. เป็นเบาะแสpending-stopที่ชัดขึ้น ไม่ยืนยันEA/version/settingsตลอดclosedhistory; openingtickets2153718320/2153718346ไม่ถูกเพิ่มเข้า35,462scope
- มี81sparseequitysnapshotsและaggregatecommission−1,320,571.32/deposits1,000/withdrawals0 แต่ไม่ใช่completebalance/cashflow/restart history ห้ามใช้equityที่sampleภายหลังเป็นlotinputย้อนหลัง
- Searchชื่อEAไม่พบprimarysourceที่ยืนยันconfigurationของScalping456 ไม่ใช้คำโฆษณา/third-partyresellersเป็นsourceEAsettings ไม่contactผู้ขายหรือเข้าaccountอื่น

Public SL/TP0ไม่ยืนยันว่าไม่มีstopจริง เพราะsnapshot/import semanticsยังไม่ทราบ ต้องมีJournalและSL/TPmodifyhistory ข้อมูลopenนี้ไม่ใช่marketquoteหรือoriginalclosebehavior witness

## งานต่อที่มีหลักฐานรองรับ / สถานะgoal

รอบก่อนหน้าinterruptedหลังวางแผนแต่ไม่รัน ไม่ใช่verifiedwaitหรือผลทดลอง รอบนี้เพิ่มpathdatasetครบ, publicmetadataใหม่ และdistance2.8fullcontinuousreplaysที่rejectbenchmarkแล้ว เป้าหมาย100%ยังไม่ผ่าน การขาดEAที่พี่ไม่มีไม่ใช่รายการที่ต้องขอซ้ำเพื่อทำงานต่อ

หลังรายงานนี้ออกแบบและรันpending-stop state machineแล้ว32paper+32guardedcontrols: pendingราคาอยู่ก่อนtickที่fill, BUYtriggerใช้ask/SELLใช้bid, ไม่fillpendingจากsamequoteย้อนหลัง แยกOCO/retainโดยpreregisterparameters ทุกแบบไม่ผ่านgoal ดูผลล่าสุด[`PENDING_STOP_RESULTS.md`](PENDING_STOP_RESULTS.md) Lotchanges/manual/recoveryยังไม่ยืนยันและห้ามใส่sourceclock/ticketlookupเพื่อทำให้match `SOURCE_DATA_REQUIRED.md`บันทึกข้อจำกัดของpublicdata ไม่ใช่คำขอEA/passwordจากพี่

## ทำซ้ำจากresearch folder

ทุกexport/resultใช้freshtag/filenameเพื่อไม่เขียนทับevidence; ห้ามเริ่มprocessซ้ำเมื่อobservationtimeout ให้ตรวจhandleเดิมก่อน

```powershell
python -m unittest test_quote_path_diagnostics test_path_public_trial -q
python diagnose_quote_paths.py --tag NEW_PATH_TAG
python summarize_path_constraints.py --tag NEW_PATH_TAG
python snapshot_public_schema.py --tag NEW_PUBLIC_TAG
python extract_public_metadata.py --snapshot-tag NEW_PUBLIC_TAG
python replay_vantage_trial28.py --tag NEW_TRIAL_TAG
python verify_trial28_experiment.py --tag NEW_TRIAL_TAG
```

PublicliveGETเปลี่ยนได้ ไม่รับประกันbyteเหมือนarchiveเดิม; usearchivedprofile/hashเพื่อทำmetadataextractซ้ำ Fulltestsuite54testsผ่าน (43เดิม+8path+3parser/trial); tests/QAเหล่านี้ไม่พิสูจน์originalgoal100%
