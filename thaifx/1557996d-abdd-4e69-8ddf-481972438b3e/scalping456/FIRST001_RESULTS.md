# ทอง 0.01 ช่วงแรก: แยก entry / exit / execution

8 ตุลาคม 2026 — ลงมือในกรอบที่พี่ให้แคบลงแล้ว ใช้ทุก7,312ordersในlot0.01ช่วงแรก ไม่ปนFixedVol20/การเพิ่มlot และไม่ตัดclose-byหรือspecial exits **ยังไม่ผ่านแม้กรอบcomponentนี้**

## ผล causal replay

แผนก่อนpredictions/diagnostics: [`EXPERIMENT_FIRST001_PLAN.md`](EXPERIMENT_FIRST001_PLAN.md) ใช้เพียง4controls: pending fixed_close/OCO, entrydistanceราคา1, initialSLราคา1, trailing16/16points, lot0.01, valid-trailing-proposalguard=True ต่างกันเฉพาะentryfill/stopfilllevelหรือquote ไม่เพิ่มparametersหลังเห็นผล

Warmup Aug18 21:00inferredUTC → END exclusiveAug31 05:12:19UTC ใช้5,798,341 cachedticks สร้างทั้ง4trajectoriesก่อนอ่านoutcomeledger ไม่มีsource-entry/exit/day resets ไม่มีclock-basedlotchanges ไม่force-closeท้ายscope Unknownstartupและoriginalfeed/executionยังไม่verified

| Entry / Stop fill | Predictionsรวมwarmup | Predictionsในcomponent window | Exactครบfields / 7,312 | Missing | Extra | Entry-onlyตรง ไม่ใช่fullsuccess |
|---|---:|---:|---:|---:|---:|---:|
| level / level | 20,833 | 14,094 | 9 | 7,303 | 14,085 | 57 |
| level / quote | 20,898 | 14,174 | 3 | 7,309 | 14,171 | 64 |
| quote / level | 19,714 | 13,200 | 8 | 7,304 | 13,192 | 37 |
| quote / quote | 20,290 | 13,746 | 3 | 7,309 | 13,743 | 49 |

Exactใช้symbol/side/lot/open-close second/prices/pips/grossP&L/closebehavior ณsourceprecision เวลาtolerance0 จับคู่หนึ่งต่อหนึ่ง 34other-closingrowsยังไม่certifybehaviorและนับmissing ไม่ระบุว่าเป็นmanual ส่วน6close-byrowsยังอยู่ในscopeทั้งหมด ไม่มีmodelนี้สร้างclose-by triggerได้

เก็บoriginalinventoryทั้ง35,462แยก: 7,312ในcomponent / 28,150นอกcomponentพร้อมfull-sourcecomparisonทุกmodel Best4controlรอบนี้เมื่อเทียบoriginalgoalคือexact9/missing35,453/extra14,085 ไม่อ้างsubsetผ่านหรือเอา9ไปบวก29จากคนละmodel/ช่วง/lotconfig ไม่มีunseenholdoutในcomponentนี้

## หลักฐาน entry quote ที่แยกออกมาได้

ทั้ง7,312sourceentriesมีVantagequotesในreportedopeningsecond ไม่มีrowถูกตัดเพราะopeningsecondไม่มีticks แต่sourceentrypriceที่ตรงบนexecutablequote(BUYask/SELLbid)มีเพียง1,273rows:

| Side | Source rows | มีquotesในopeningsecond | ราคาentryเห็นบนexecutablequoteในวินาทีนั้น | Median sourceentry−firstexecutablequote |
|---|---:|---:|---:|---:|
| BUY (Ask) | 3,715 | 3,715 | 671 | +0.11ราคา |
| SELL (Bid) | 3,597 | 3,597 | 602 | −0.10ราคา |
| รวม | 7,312 | 7,312 | 1,273 | ไม่รวมสองฝั่งให้signหักล้างกัน |

อีก **6,039rowsไม่พบราคาentryนั้นบนexecutablequoteของวินาทีที่sourceระบุ** ดังนั้น ภายใต้สมมติฐานfill=currentcachedquote/เวลาเดิม/ไม่มีslippage โมเดลquote-fillใดก็ตามไม่สามารถทำซ้ำ6039entriesเหล่านี้ได้ ไม่ว่ากฎsignalหรือlotจะเป็นอะไร นี่เป็นcompatibility boundของexecutionmodel **ไม่ใช่1,273ordersที่cloneสำเร็จ** หรือproofว่าfeedผิดแน่นอน

ยังแยกไม่ได้ว่าเป็นsourcefeedต่าง, order-vs-deal timestamp/import semantics, execution/slippage หรือpendinglevelfill การเห็นBUYentryบนBidไม่ใช่BUYexecutablewitness ไม่เลื่อนเวลาหรือแก้quoteย้อนหลังให้match Medianด้านบนเทียบfirstquoteในsecond ไม่ใช่quoteณfillmillisecondจริง จึงไม่ถือเป็นrecoveredspread/slippage parameter

Spreadก่อนentrymedianราคา.22ทั้งสองฝั่ง; lastpastquoteมีmedianage49msSELL/50msBUY Sourceentriesสัมพันธ์กับpast5sreturnตามฝั่ง6,529/7,312rows แต่directioncorrelationไม่ใช่entryruleหรือผลreplay

## Predecessor และ nominal price1

ใช้latest**strictcompleted**sourcecloseก่อนentrysecondรวมทุกclosingtype เก็บsimultaneousdistinctpriceanchorsเป็นambiguityไม่เลือกticketมาตั้งreferenceตามใจ:

- 7,311rowsมีstrictpredecessor / 4มีdistinctpriceambiguity / 1ไม่มีpredecessorแรก จึงมี7,307unique-priceeligibleobservations
- Signeddisplacementไปทางentrypositive7,203 / negative104; medianราคา1.09ทั้งBUY/SELL นี่เป็นclosed-outcomegeometry ไม่ใช่causalproofของราคาtrigger1
- ในdefiniteinterval[predecessorclose_second+1s,entry_second) thresholdราคา1จากactualpredecessorถูกcrossก่อนentrysecond4,009rows ในนี้1,478rowsอย่างน้อย5sก่อนentry
- ผลนี้ไม่สอดคล้องกับimmediatefixed1entryบนcandidatequotesในrowsดังกล่าว แต่ยังแยกgate/cooldown/repricing/latency/feeddifferenceไม่ได้ **thresholdwitnessเป็นconditionalforensicsที่ใช้actualpredecessor ไม่ใช่predictions และไม่ถูกใช้resetstrategy**

## Exit constraints ในscopeเดียวกัน

ยกobservationsจากall-sourcepatharchiveเดิมที่ตรวจhash ไม่seedstrategyจากactualentryเพื่อfitexitใหม่ ช่วงdefiniteinteriorตัดวินาทีเปิด/ปิดที่ไม่ทราบลำดับย่อยออก:

| Closing type | Source rows | มีinteriorquotes | ข้ามnominalSL1.10 ≥5sก่อนclose | ละเมิดold40/30barrier ≥5sก่อนclose |
|---|---:|---:|---:|---:|
| SL-labelled | 7,272 | 7,129 | 61 | 760 |
| Other | 34 | 34 | 27 | 34 |
| Close-by | 6 | 6 | 6 | 6 |

SL-labelledprice-positiveobservedpeak−close modeราคา.16มี456rows (.17=418,.15=411,.18=380) ไม่ใช่uniformdistanceที่พิสูจน์แล้ว และinteriorไม่ได้ครอบpeakในopening/closingsecondครบ No-interior143rowsยังอยู่ในreplaydenominator ทุกother/close-byไม่ได้ถูกยืนยันว่าควรใช้uniformSL/trail benchmark จึงไม่สรุปว่าเป็นbrokerstop failures

## สิ่งที่ได้จากการตั้งกรอบแคบ

แยกlotออกได้จริง: lot0.01ตรงทั้งsourceและcontrolsทุกprediction แต่timing/price/closingbehaviorยังไม่ตรงจำนวนมาก จึงไม่ใช้dynamiclotแก้คะแนนก่อนแก้price mechanism

Rejectเฉพาะ4controlsและstrictdirectquoteexecution assumptionsที่ระบุ ไม่ได้rejectpending-stopทุกแบบหรือระบุว่าsourceEAต้องใช้TFใด/inputsเท่าไร ข้อจำกัดของsourcequotes/executionไม่ทำให้การแกะจากordersหยุด แต่ต้องแยกobservationalrulesจากcausalonesต่อไป

งานต่อที่มีหลักฐานรองรับคือ bounded **execution/clock witnesses และpending-anchor/repricing study** ในscopeเดิมก่อนกำหนดnewcausalcontrol เช่นตรวจว่าความคลาดของprice/timeเป็นsystematicจริงหรือไม่ ไม่เลือกoffsetที่matchดีที่สุดแล้วประกาศtimezoneใหม่ และไม่ตั้งsession/lotthresholdจากsourceoutcomesเพื่อกลบmissing ทั้งหมดไม่ต้องมีEAจากพี่

## Artifacts / QA / ทำซ้ำ

- `data/first001_replay_20261008/`: 4models/25JSONLartifacts — predictions, componentresults, original35,462results, extras, entry-onlyresults/extras และoriginalscopeinventory พร้อมcache/code/plan/sourcehashes
- Replayreport SHA-256 `6c9edb669c2d74b57ffcdcb885b9c2a3f0b01308e430014edbd5c4ad4084a484`
- `data/first001_diagnostics_20261008/`: observationsครบ7,312unique tickets พร้อมrawsource/pre-entryquotes/one-second witnesses/allpredecessoranchors/archivedexitobservations ไม่ใช่signal module
- Diagnosticreport SHA-256 `dafcdec6336b3f43314196c81ec0b218122cc9f54785848f747c9de94aad11f5`
- `qa_full_audit.json` / `qa_quote_audit.json`: score/extras/entryuniqueness/maximalmatching/ทุกsourcepopulation/hash ผ่าน; thresholdcrossingตรวจซ้ำbruteforceทุกrow ไม่ตรวจแค่จำนวนรวม
- ActualAug24 00:00–01:00UTCreference/vectorparityทุก4controlsตรงทุกfieldก่อนfullcomponentrun รวม89testsผ่าน (81เดิม+8component); codecompileและscopedUTF-8/LF/mojibakeผ่าน QA/testpassไม่ใช่sourceEAclonepass

```powershell
python -m unittest test_first001 -q
python replay_first001.py --tag NEW_FIRST001_REPLAY_TAG
python diagnose_first001.py --tag NEW_FIRST001_DIAGNOSTIC_TAG
python verify_first001.py --replay-tag NEW_FIRST001_REPLAY_TAG --diagnostics-tag NEW_FIRST001_DIAGNOSTIC_TAG
```

ใช้freshtag ไม่overwriteevidence สัญญาณอ่านเฉพาะpastquotesและsimulatedstate ก่อนsourceoutcomesparse ข้อมูลดิบ35,462ordersไม่ได้ถูกเปลี่ยนหรือหายไป การจดเวลาหน้าเว็บยังใช้raw+7hแยกจากinferredUTC(raw−3h)ตามเดิม ไม่ใช้IUXshiftกับVantage
