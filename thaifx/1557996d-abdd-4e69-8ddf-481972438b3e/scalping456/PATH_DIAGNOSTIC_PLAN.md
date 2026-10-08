# Quote-path / state constraints ก่อนรัน

8ตุลาคม2026 หลัง38candidate+2portfolio causal replaysไม่ผ่าน เป้าหมาย35,462 orders/100%คงเดิม รอบนี้เป็นforensic diagnostics ไม่ใช่prediction replay ไม่instantiate/resetstrategyจากsource entry/close และไม่เปลี่ยนmissing/extraของreplayที่ผ่านมา

## ขอบเขตที่กำหนดก่อนวิเคราะห์

1. ใช้untouched JSONLทั้ง35,462 rowsและVantage normalized cachesเดิม SHA-256/provenance/gapsต้องตรง ไม่ดึง/สร้างticksใหม่ ไม่ส่งtrade
2. Quotesช่วง `[open_second+1s, close_second)` เป็นdefinite interiorตามtimestampความละเอียดวินาที หากfeed/clockตรงsourceจริง Positionควรยังเปิดอยู่ Quotesช่วงเข้า/ปิดวินาทีเดียวกันมีลำดับไม่ทราบ ไม่ใช้ตัดสินearly-stop contradiction
3. คำนวณMFE/MAEราคา,จำนวนquotes,first crossings และgapsของทุกrow แยกbidBUY/askSELL ไม่มีเปลี่ยนsourceexecutionpriceไปเป็นquoteที่เลือกให้ผลสวย
4. ตรวจnominal initialSLราคา1ของXAUทุก31,210 rowsและราคา10เฉพาะFixed143trial (เป็นhypothesesจากledger ไม่ยืนยันinitial orders) รายงานstrict beyond0/10%ของnominal stop; marginนี้เป็นsensitivity diagnostic ไม่ใช่toleranceของexactmatcher ใช้early lead≥5sแยกtimezone/subsecond/latency uncertainty
5. ตรวจกฎratcheting benchmark XAU activationราคา.4/distance.3 และFixedtrial activation0/distance10 ผ่านanalytical past-running extrema/stop-before-modify barrier ไม่generate source-seeded predictions ไม่fitparametersจากผลใหม่
6. Implied trail distanceจากpeakก่อนcloseกับreportedcloseเป็นdiagnosticที่มีexecution/slippage/unknownactivation/unknownSLmodifyข้อจำกัด ไม่ถือค่าที่fitจากแต่ละorderเป็นcausalinputs
7. FixedTP4076 rowsตรวจfirst crossingของfinalreportedTPเป็นobservational witness ไม่ถือfinalTPถูกวางไว้ตั้งแต่เปิด เพราะgridอาจrepriceTPภายหลัง Other/close-byยังเก็บpathแต่ไม่ตีราคาreciprocalcloseว่าเป็นmarket barrier
8. Lot run segments/source chronologyรวมspecial exitsและรายงานvolume changesไม่ตั้งclock-basedswitches/EAinstance IDsจากclosinglabels Risk sizingต้องมีbalance/deposits/commissions/EAinputsซึ่งsnapshotไม่ให้
9. ตรวจpublic page/client/schemaตามUIปกติว่ามีmagic/manual IDs/EAinputs/modify historyที่เปิดเผยเพิ่มไหม ไม่เดาprivate API/credentialsหรือเปลี่ยนsource snapshotliveปนกับ35,462ชุดเดิม

ผลต้องระบุว่าconditional on candidate feed ไม่ใช่prooforiginalbrokerexecution และไม่ใช้diagnosticsแทนfullcausal100%gate ถ้าหลักฐานที่จำเป็นยังไม่มี ให้บันทึกข้อจำกัดเดิมอย่างเจาะจง ไม่วนจูนarbitrarypresetsหรือสร้างledger-drivenstrategy
