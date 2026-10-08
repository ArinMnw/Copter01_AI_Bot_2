# กรอบแคบลง: ทุน $1,000 / lot sizing / ทองช่วงแรก

8 ตุลาคม 2026 — ตามพี่ให้ตั้งกรอบแคบก่อน แยก **price entry/exit** ออกจาก **lot/risk sizing** แล้วค่อยintegrate ไม่เปลี่ยนfailedreplayเดิมให้เป็นผลสำเร็จ

อัปเดตหลังlot-scope reportนี้: ลงมือcomponent0.01แล้ว4controlsและquote/exitdiagnostics ทุกแบบยังไม่ผ่าน ดูผลล่าสุด[`FIRST001_RESULTS.md`](FIRST001_RESULTS.md) ไม่เปลี่ยนhashesหรือforensicoutputsของlot-scopeรอบเดิม

## ผลที่ตรวจได้

ทุนเริ่ม$1,000ตรงกับข้อมูลจากพี่และaggregate deposits1,000/withdrawals0ในpublicmetadata แต่publicledgerไม่มีfee/swap/cashflow timingครบ จึงยังไม่ทราบactualbalanceหรือequityณทุกentry

สำหรับทอง ข้อมูลจริง **ไม่มี0.1lot**: 0.01จำนวน7,485 / 1จำนวน1,910 / 10จำนวน21,814 / 0.4หนึ่งrow รวม31,210 ส่วนFixedVol20มี0.1จำนวน1,668และlotอื่นตามbasket progression ไม่รวมสองsymbolsเป็นladderเดียว แนวคิดเพิ่มlotตามขนาดพอร์ตยังเป็นhypothesis ไม่กำหนดthresholdเป็น$10k/$100kหรือrisk%เอง

## ลำดับ lot ของทองทั้งหมด

เวลาคอลัมน์นี้เป็น **web display derived = raw+7h** ตามข้อตกลงจดเวลาหน้าเว็บ ไม่ใช่UTCจริง เก็บrawและinferredUTC(raw−3h)แยกในJSONL ตัวเลขคอลัมน์สุดท้ายเป็น$1,000+profitของordersที่closeก่อนวินาทีentry **ยังไม่หักfees/swap ไม่ใช่balance/equity** ปัดสองทศนิยมเฉพาะการแสดงผล ไม่แก้sourceเลขทศนิยม

| Lot | จำนวนใน adjacent run | Entry แรก: เวลาเว็บ derived | ทุนเริ่ม+closed grossก่อนentry |
|---:|---:|---|---:|
| 0.01 | 7,312 | 24 Aug 2026 08:05:02 | $1,000.00 |
| 1 | 948 | 31 Aug 2026 15:13:28 | $2,515.32 |
| 0.01 | 173 | 1 Sep 2026 09:59:50 | $16,583.32 |
| 1 | 962 | 1 Sep 2026 12:06:01 | $16,608.91 |
| 10 | 17,510 | 1 Sep 2026 23:37:24 | $30,190.91 |
| 0.4 | 1 | 30 Sep 2026 22:25:45 | $2,457,726.12 |
| 10 | 4,304 | 30 Sep 2026 22:26:07 | $2,460,536.12 |

ก่อน5entryแรกในตารางไม่มีstrict activepositionsหรือsame-second close events จึงไม่ต้องเลือกsubsecond orderingที่จุดเปลี่ยนเหล่านี้ ช่วง0.4/กลับ10มีทองและFixedVol20ค้างอย่างละหนึ่งposition ไม่ทราบfloatingP/L ตารางจึงไม่ตีความportfolioequity

มีrollback `1→0.01→1` ขณะrealizedgrossไม่ได้กลับลงไปเท่าทุนเริ่ม จึง **ไม่สอดคล้องกับmonotone gross-only lot ladderอย่างง่าย** แต่ยังไม่ใช้สิ่งนี้ปฏิเสธactualbalance/equity sizingทุกชนิด เพราะfee/swap/state/inputs/restartยังไม่ทราบ Adjacent runsไม่เท่ากับEAinstanceหรือsettingschange และ0.4ยังไม่ถูกระบุเป็นmanual ticket

## กรอบ component study ที่กำหนดใหม่

เริ่ม **ทอง0.01ช่วงแรกทั้งหมด7,312orders**: web-derived firstentry24 Aug 08:05:02 ถึงlastentry31 Aug 15:11:46; lastcloseของscope31 Aug 15:12:18 (rawfirstAug24 01:05:02 / lastentryAug31 08:11:46 / lastclose08:12:18)

- Lot0.01คงที่ ไม่มีFixedVol20ซึ่งเริ่มrawSep5 10:58:34 และไม่ปนช่วงเพิ่มlot/rollbackภายหลัง
- มีSL-labelled7,272 / other34 / close-by6rowsรวม3คู่ ทั้งหมดอยู่ในscope ไม่ตัดข้อยกเว้นให้โมเดลผ่าน
- มี7,306entriesที่ไม่มีstrict prioractive และ6ที่มีหนึ่งpositionเดิมค้าง ไม่ถือone-positionเป็นinvariant ลำดับsame-secondยังต้องรายงานแยก
- กำไร/pipsต่อlotช่วยแยกผลposition sizeออกจากprice mechanismได้ แต่close-byเป็นaccountingallocationเฉพาะ ไม่เทียบเหมือนordinary single-leg exits
- รอบต่อไปทดสอบprice entryกับexitเป็นคนละชั้นบนscopeนี้ โดยยังต้องcontinuous/past-only/no actual-entry resetsและเก็บmissing/extraครบ นี่เป็นdevelopmentcomponent **ไม่ใช่unseenholdoutหรือfull35,462goalผ่าน**

ณlot-scopeรอบที่รายงานในไฟล์นี้ยังไม่ได้รันentryreplayใหม่ในscope7,312และยังไม่ได้สร้างrecoveredauto-lot (ต่อมารันcomponentแล้วตามlinkด้านบน) คะแนน29ของรอบก่อนยังเป็นfailedbenchmarkตามเดิม การเพิ่มdynamiclotเองไม่แก้entry/exit time-price mismatchesโดยอัตโนมัติ

## ผลข้อมูลและการตรวจ

แผนก่อนderivedoutput: [`NARROW_RESEARCH_PLAN.md`](NARROW_RESEARCH_PLAN.md) เครื่องมือใหม่ `analyze_lot_scope.py` / verifier `verify_lot_scope.py` ไม่อ่านMT5 ไม่ส่งtrade ไม่แก้productioncode

`data/lot_scope_20261008/`:

- `all_source_lot_states.jsonl` — ครบ35,462unique tickets แยกsymbol/lot/raw/webderived/inferredUTC/pastgross/accountvsXAU/strictactive/same-second ambiguity/component membership
- `report.json` — volume countsทั้งสองsymbols, adjacentXAU runs, scopepopulation/exceptioncounts, source/code/plan/artifact hashes; ระบุactualbalance/equityและlotformulaยังไม่identified
- `qa_lot_scope.json` / `qa_independent.json` — population/source hashesผ่าน และตรวจsequentialpastgrossทุก35,462rowsด้วยindependentevent sweep; strictactivecountsตรวจซ้ำด้วยopen/close timestamp ranks รวมzero-duration edges
- Source SHA-256ยัง `b8f5f75de07ba335ba607855167b5c77600954561c7c740621a335fa1b9825f1` ไม่แก้ต้นฉบับ
- 7lot-scope testsใหม่ผ่าน รวมsame-second/zero-duration/futureprofit/symbol separation/rollback/fullpopulation boundaries; fullresearch suite **81testsผ่าน** และpy_compile/scopedUTF-8/LF/mojibake checksผ่าน

```powershell
python -m unittest test_lot_scope -q
python analyze_lot_scope.py --tag NEW_LOT_SCOPE_TAG
python verify_lot_scope.py --tag NEW_LOT_SCOPE_TAG
```

ใช้freshtagและexclusiveoutputเสมอ Publicequity81samples/aggregatecommissionไม่ใช่feeหรือequityของentryทุกไม้ ไม่ปันfeeตามlotแบบไม่มีหลักฐานเพื่อหาthresholdที่อยากได้ ข้อมูลในรอบนี้เป็นforensicobservations ไม่ถูกส่งเข้าstrategyเป็นlookupตารางเวลา/lot
