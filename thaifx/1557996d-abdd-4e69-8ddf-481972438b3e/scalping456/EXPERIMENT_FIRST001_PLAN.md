# First 0.01 component — frozen before predictions and quote diagnostics

8 ตุลาคม 2026 พี่ให้ลุยหลังตั้งกรอบแคบ: ทอง0.01ช่วงแรก7,312rows ไม่ปนrisk scaling/FixedVol20 เป้าหมายเดิม35,462ยังไม่ผ่านและไม่ประกาศsubsetแทนfullgoal

## Frozen four controls

Pending fixed_close/OCO, entrydistanceราคา1, initialSLราคา1, point.01, trailingactivation16/distance16points, volume0.01, correct-side trailing proposal guard=True ค่าเหล่านี้เป็นpreviousresearchcontrols ไม่ใช่EAinputsที่ยืนยัน ไม่เลือกค่าใหม่จากcomponentoutcomes

Entryfill level/quote × stopfill level/quote =4modelsเท่านั้น ใช้reference/vector parityก่อนfullcomponentreplay ไม่เปลี่ยนanchor/opposite/trail/lot/sessionเพื่อให้scoreดีขึ้นในรอบนี้ Newpositionsไม่trail/stopopeningquoteตามpaper lifecycleเดิม ไม่อ้างว่าเป็นsourcebrokerexecution

Warmup Aug18 21:00 inferredUTC → END exclusiveAug31 05:12:19UTC (sourcecomponentmaxclose Aug31raw08:12:18) Sourcewindowเริ่มAug23 22:05:02UTC (rawAug24 01:05:02); stateต่อเนื่องไม่resetตามorders/day Source-derivedwindowใช้เพื่อกำหนดขอบเขตstudyเท่านั้น ไม่สร้างentry/exitที่sourceboundary และไม่force-closeท้ายreplay

Generateทั้ง4trajectoriesก่อนparseoutcomeledger Scoringcomponentทุก7,312rowsรวมSL7,272/other34/close-by6พร้อมextras เวลาtolerance0และallobservablefields เดิมstrict matcherยังไม่certifyunknownbehavior แยกentry-only(symbol/side/lot/second/price)เป็นdiagnosticไม่ใช่fullsuccess

เก็บoriginalscopeinventoryทุก35,462ticketsและfull-sourcecomparisonแยกด้วย เพื่อไม่ลืม28,150rowsนอกcomponent การmatchedsubsetไม่ทำให้parentgoalผ่าน ไม่มีunseenholdoutในช่วงนี้และไม่เปลี่ยนlotจากsourceclock

## Entry quote forensics — not signals

ตรวจทุก7,312rowsบนcandidateVantagecacheเดียวกัน: lastquoteก่อนopeningsecond, quotesเฉพาะreportedopeningsecond, sourcepriceเทียบBID/ASKแยกและexecutable side (BUYask/SELLbid), spreadก่อนentry และsignedreturnจากpastquote1/5/10seconds

Predecessorใช้lateststrictcompletedclose_second < entry_secondรวมทุกclosingtype ถ้าหลายcloseราคาไม่เหมือนกันในวินาทีเดียวให้เก็บanchorsทั้งหมดและแสดงambiguity ไม่เลือกticketเพื่อตีความsubsecondordering

เฉพาะuniquepredecessorprice ตรวจnominalprice1thresholdถูกcrossในdefiniteinterval[prevclose_second+1s,entry_second)หรือไม่ โดยใช้AskBUY/BidSELL First-crossingเป็นconditional observationจากactualpredecessor ไม่ใช่causalprediction ไม่ใช้seeding/reset strategyและไม่นับเป็นorderclone

ดึงexit/MFE/MAE/peak-close/earlybarrier observationsของscopeจากall-sourcepatharchiveที่ตรวจhashแล้ว ไม่รันsource-seededexitfitting/หาค่าactivationจากvalidation ไม่ใช้close-by reciprocal exitsเป็นmarketquote witnesses

## Audit / decisions

Separatetruth: componentreplay vsentry-only vsforensicquotes vsaccounting ไม่ใช้windowcoverage/priceonBidแทนBUYexecution ไม่แปลfeeddifferenceเป็นrecoveredsource spread

ตรวจsourcepopulation/hashes/extras/one-to-one/4models/actualsampleparity+futureprefix ถ้าผลไม่ตรงให้จำกัดสาเหตุตามหลักฐานก่อนกำหนดnextcausalhypothesis ห้ามblindlyเพิ่มpresetsหรือtime/ticketexceptions ห้ามส่งtrade/แก้productionbot/ขอEAที่พี่ไม่มีอีก
