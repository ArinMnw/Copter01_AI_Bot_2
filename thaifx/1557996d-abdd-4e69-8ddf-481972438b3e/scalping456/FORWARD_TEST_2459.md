# Scalping456 experimental forward — IUX demo 2459

> Historical deployment: วันที่ 15 ต.ค. พี่สั่งหยุด monitor และย้าย Scalping456 ไป Demo 7129 ดู [FORWARD_TEST_7129.md](FORWARD_TEST_7129.md) สำหรับสถานะปัจจุบัน เอกสารและผล 2459 ด้านล่างเก็บไว้เป็นหลักฐานเดิม

15 ตุลาคม 2026 พี่ยืนยันให้ **เพิ่มควบ แยก magic และ state** ใน `demo_portfolio` ไม่ปิด/เปลี่ยนออเดอร์ของกลยุทธ์เดิม ไม่ใช่ยืนยันว่าcloneครบ100% ผลdecodedhistorical6,213/35,462ยังไม่ผ่านเป้าเดิม

## Deployment scope

- เฉพาะ `demo-iux-2101182459`, login2101182459, `IUXMarkets-Demo`, accountmodeDEMOและhedging ต้องตรงก่อนทุกtrade request พร้อมterminalpathของprofileนี้ ถ้าไม่ตรงfailclosed
- Symbol `XAUUSD.iux` ที่ตรวจread-onlyแล้ว: digits2, point/tick.01, lotmin/step.01, stop/freezelevel0 ณpreflight ไม่มีsymbol-select/login/account-switchในadapter
- GOLDเท่านั้น ไม่ได้forwardFixedVol20 และไม่ใช้Vantagebid+0.06/ask−0.05บนIUX ใช้ราคาที่brokerให้จริง
- Magic **995456** / portfolio key **SCALPING456**; state `profiles/demo/demo-iux-2101182459/scalping456_state.json`; journal `logs/scalping456_events.jsonl` ภายในprofileเดียวกัน ไม่เขียน `demo_portfolio_state.json` ร่วมกับพอร์ตเดิม
- แยกownership/state ไม่ใช่แยกบัญชีทุน: margin/equityยังแชร์กับกลยุทธ์เดิม จึงไม่ใช้balanceของบัญชีมาขยายlotของการทดลองนี้
- Snapshotก่อนเตรียมมี95positionsของmagicอื่นและไม่มีpending ไม่ถือว่าจำนวนต้องคงที่เพราะระบบเดิมยังเทรดต่อ ระหว่างเตรียมมีEA2_1/INDI1เปิดเพิ่มจากเดิมLTS_AHR2 จึงรักษารายการล่าสุดทั้งสามตามprofile.envแล้วappendSCALPING456เท่านั้น

## Frozen forward parameters / safety deviations

อิงcandidateทองE4ล่าสุดจากdecoded research แต่ไม่importhistoricalregime scheduleและไม่เปลี่ยนlotตามวันที่/sourceorder:

| Item | Forward setting |
|---|---|
| Lot | **0.01 fixed** ไม่คูณจากbalanceจริงของบัญชีที่มากกว่า$1,000 |
| Entry | native BUY STOP=Ask+1.30 / SELL STOP=Bid−1.30 |
| Initial stop | ราคา1.00จากpendingentry ส่งSLพร้อมpending ไม่เปิดแบบไม่มีSLโดยตั้งใจ |
| Trailing | activation>0.20, distance0.20, ต้องimproveมากกว่า0.01; firstseen delay≥0.9s / minmodifyinterval0.27s |
| Reaction | re-armในรอบแรกที่สังเกตcloseได้ ไม่ใส่latencyสมมติลงbrokerrequest |
| Opposite pending | คงฝั่งตรงข้ามเมื่อขาแรกfill; เมื่อownedpositionปิด canceloldownedpendingก่อนre-arm |
| Exposure cap | ownpositions+pendingที่อาจfill ≤3; ไม่รวมพอร์ตเก่าเข้าquotaของScalping456 |
| Loss guard | หยุดเปิดรอบใหม่/ยกเลิกownpendingเมื่อconfirmednetของวันBKK≤−$20; **ไม่ใช่guaranteedmaxloss** และไม่บังคับปิดpositionเดิม |
| Poll | 0.25s, max_instances1/coalesceTrue, เฉพาะprofile2459 |

ชุดนี้เป็นlivebrokeradapterของกลไกที่ศึกษา **ไม่ใช่batchsimulatorตัวเดียวกันเป๊ะ**: ใช้actualfills/SLacceptance/serverexecution, ไม่มีsyntheticfeedoffset/270msserverdelay/idealpricefills ไม่มีฟังก์ชันlookupsource ticketsหรือsource-date inputchanges Nativependings/SLทำงานที่brokerแม้Pythonpollช้าลง Actualpoll/requestlatencyอาจช้ากว่าต้นฉบับ โดยเฉพาะตอนjobsเดิมใช้MT5laneร่วมกัน ต้องวัดจากjournal ไม่อ้างtick-for-tickparity

## Failure / restart / ownership

- CentraltradeguardยอมเฉพาะPENDING/REMOVE/SLTPสำหรับmagic+symbolนี้ ไม่มีmarketcloseของพอร์ตเก่า ก่อนmodify/removeตรวจtargetกับbrokerอีกครั้ง
- SnapshotNoneไม่ใช่emptybook; connection/accountเปลี่ยนให้หยุดส่งคำสั่ง ไม่เดาไม่มีpositionsแล้ววางซ้ำ
- Trackacknowledgedpendingticketsและreconcilehistoryorders/dealsด้วยidentifierด้วย แม้positionเปิดแล้วปิดระหว่างสองpollก็ไม่ตกหล่นจากnet/lossguard Unknownorderhistoryต้องรอ ไม่สมมติว่าถูกcancelแล้ววางใหม่ Journalเก่าก่อนเพิ่มfieldนี้กู้ackticketsได้หนึ่งครั้ง
- Persistintentก่อนsend ถ้าackNone/exception/ไม่มีticket หรือrestartกลางpairให้latchhaltและไม่resubmitเอง CancelเฉพาะownpendingsและคงการดูแลSLของownfills ต้องreviewjournalก่อนreset
- Processlockแยกกันสองrunnerถือstateเดียวกัน Brokerbookเป็นตัวจริงเมื่อrestart ไม่วางpendingpairเพิ่มทับของเดิม
- การปิดpositionต้องมีhistoryexitของpositionidentifierที่เคยยืนยันmagicของเรา ก่อนนับnet/re-arm HistoryMagic0บนmanual/serverclosingdealยังผูกด้วยidentifier ไม่เหมากำไรของทั้งsymbolมาเป็นของเรา
- OFFจากปุ่มDemo Portfolioยกเลิกเฉพาะownpendingและไม่เปิดรอบใหม่ แต่ยังtrail/protectownpositionsที่ค้าง พอร์ตอื่นไม่ถูกแก้ nativeSL/TPเดิมไม่ถูกถอด
- Genericmainmanagersมีmagic≥990000 exclusionsอยู่แล้ว และadapterลงcompatibilitysid21ของownpositions ไม่ใช้mainstrategyfilters/scale-out/weightedlotsกับระบบนี้

## Rollout / verification

ConfigdefaultOFFทุกprofile มีschedulerเฉพาะ2459 เปิดในprofile.envผ่านDEMO_PORTFOLIO_ACTIVEร่วมกับLTS_AHR2,INDI1,EA2_1 ใช้supervisorเดิมแบบโหลดenvใหม่; restartเฉพาะprocess treeของ2459ที่ตรวจheartbeat/supervisorparentchainแล้ว ไม่restartterminalหรือเปลี่ยนบัญชี

Pre-activation: 23mockunittestsผ่าน และlegacydemo-manager10casesผ่าน (เติมsymbol_infofixtureให้ตรงAPIที่managerใช้อยู่เดิม) เพิ่มhistoryreconciliation/flash-filltestsแล้วรวม **25testsผ่าน** และreloadเฉพาะmainของ2459ผ่านsupervisorเดิมอีกครั้ง compile/scopedUTF-8/LF/mojibakeผ่าน ไม่อ้างว่าglobalrepoverificationทั้งหมดผ่าน

สถานะliveต้องดูหลักฐานหลังrestartในjournal/brokerbookด้านล่าง ไม่ถือunitpassหรือconfigenabledว่าforwardเริ่มสำเร็จแล้ว

```powershell
python -m unittest test_demo_scalping456 -v
python test_demo_portfolio_manage.py
python -m py_compile demo_scalping456.py demo_portfolio.py config.py main.py
```

ปุ่มTelegram: Demo Portfolio → Scalping456 Forward → เปิด/หยุด ดูstatusแยก Fixedlot, cycles, phase/error ส่วนnetจริงของownclosedpositionsเก็บในstate/journal ไม่ใช้balanceทั้งบัญชีเป็นperformanceหรือauto-lot

## Live verification

เปิดDemoจริงแล้วหลังpreflight; ไม่ใช่shadowmode:

- 15 Oct 11:29:40–41 BKK: brokerretcode10009รับBUY STOP601630595/SELL STOP601630597 lot.01พร้อมSL
- SELL601630597ถูกพบfill11:31:26 BKK และปิด11:32:18 โดยnetที่กระทบยอดdealhistoryรวมต้นทุน **−$1.04** ยกเลิกoppositependingเก่าของเราแล้วre-armรอบที่2สำเร็จ
- Read-onlybrokerbookหลังreload: BUY STOP601631172 entry4147.91/SL4146.91 และSELL STOP601631174 entry4145.17/SL4146.17, lot.01/TP0ทั้งคู่ ไม่มีownopenpositionในsnapshotนั้น ownexposure2≤3 ทั้งคู่มีSL ส่วนพอร์ตอื่นยังมี96positionsและไม่มีpendingในsnapshotนี้ (จำนวนเปลี่ยนตามการเทรดของระบบเดิม)
- Supervisorใหม่36528; mainหลังhistory-reconciliationreload35460; terminalเดิมไม่restart/ไม่เปลี่ยนaccount Heartbeatmt5_ok1และstatephaseworking/last_errorว่าง
- ตรวจjournalrecoveryแล้วไม่double-countไม้แรก KnownpendingIDsตรงbrokerbook NetของScalping456แยกจากPnLของLTS/INDI1/EA2_1

`data/forward_2459_20261015/deployment_manifest.json` เก็บparams/codehashes/tests/authorizedcoexistence; `live_smoke_verification.json`เก็บหลักฐานตรวจรอบนี้ Snapshotเหล่านี้ไม่ใช่livefeedถาวร หลังอ่านไฟล์orderอาจfill/ปิดไปแล้วได้

ข้อสรุปคือ**functionalforwardเริ่มทำงานแล้ว** ไม่ใช่ผลกำไรที่พิสูจน์แล้วและไม่ทำให้เป้าclone100%ผ่าน ยังไม่อ้างว่าทดสอบbroker-sideprofitabletrailingทุกเส้นทางครบจากไม้แรกที่จบด้วยSL; รายการนี้มีmockcoverageและต้องเก็บactualjournalต่อ
