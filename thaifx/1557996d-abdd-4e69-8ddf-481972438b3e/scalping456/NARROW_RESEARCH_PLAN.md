# Narrow research: แยก lot sizing ออกจาก entry/exit

8 ตุลาคม 2026 — พี่ให้ตั้งกรอบแคบลงก่อน โดยใช้ทุนเริ่มต้น$1,000และตรวจแนวคิดเพิ่มlotตามขนาดพอร์ต ไม่ยกคะแนน29ordersหรือpartial resultเป็นการผ่านเป้าหมายเดิม และไม่แก้ผลทดลองเก่า

## ข้อเท็จจริงและสมมติฐานต้องแยกกัน

- ทุนเริ่ม$1,000: เป็นข้อมูลจากพี่ และpublicmetadataมีaggregate deposits1,000/withdrawals0 แต่ไม่ได้ให้เวลาฝาก/credit/cashflowครบทุกevent
- แนวคิด `0.01 → 0.1 → 1 → 10 ตามขนาดพอร์ต` เป็นhypothesisที่ต้องตรวจ ไม่กำหนดthresholdหรือbalance/equity formulaจากภาพรวมเอง
- Sourceทองมี0.01จำนวน7,485, 1จำนวน1,910, 10จำนวน21,814 และ0.4หนึ่งrow **ไม่มี0.1ในXAUUSD+**; FixedVol20มี0.1จำนวน1,668พร้อมgrid progressionอื่น จึงไม่รวมสองระบบเป็นlot ladderเดียว
- ทองมีrollback `1 → 0.01 → 1` และ0.4แทรกในช่วง10 ยังไม่ทราบว่าเป็นrisk rule, restart/default/input changes, partial execution หรือmanual action ห้ามตีความว่าเป็นmanual ticketโดยไม่มีหลักฐาน

## กรอบรอบนี้

1. ทำlot/population timelineและpre-entry realized **gross** ledgerจากclosedordersครบ35,462 ไม่จำลองentryใหม่ ไม่ใส่sourceclockเปลี่ยนlotในstrategy
2. บันทึกทั้งall-symbol account grossและXAU-only gross เพราะportfolio equityอาจรับผลจากFixedVol20ด้วย ห้ามเรียกgross ledgerว่าactualbalance/equity
3. นับเฉพาะclose_second < open_second ก่อนentry การปิดวินาทีเดียวกันแยกเป็นambiguity ไม่เรียงticketแล้วสมมติว่าcloseเกิดก่อนopen ไม่ใช้กำไรของorderที่ยังไม่ปิด
4. แยกstrict active positionsจากsame-second events; ไม่สร้างfloatingP/L/fee/swapที่ไม่มีhistory Publicequity81samplesไม่ใช่account equity ณทุกentry และclock/import semanticsของsnapshotยังไม่ยืนยัน
5. รายงานgrossที่จุดเปลี่ยนlotและการกลับlotเล็ก เก็บexceptionsทั้งหมด ไม่หาthresholdที่fitทั้งledgerแล้วอ้างว่าเป็นEAinput

## กรอบ component study ถัดไป

เริ่มจาก **XAUUSD+ช่วง0.01แรกครบ7,312orders** ตั้งแต่rawAug24 01:05:02ถึงentryสุดท้ายAug31 08:11:46 ไม่ปนFixedVol20ซึ่งเริ่มSep5 และไม่ปนการเพิ่มlot/rollbackของทอง เป็นdevelopment scopeที่กำหนดตามchronological lot run ไม่เลือกmatched winners

ในcomponent studyให้lot0.01คงที่เพื่อแยกprice mechanismก่อน ตรวจentry direction/time/priceและexitเป็นคนละชั้น ใช้pipsและgrossต่อlotเพื่อเปรียบเทียบพฤติกรรม แต่close-by allocationต้องแยกจากordinary per-leg returns ไม่ใช้lotคูณ/หารกลบaccounting behavior

ทุก7312rowsรวมclose-by/special exitsต้องเก็บผล/ข้อยกเว้น ไม่รีเซ็ตstrategyด้วยactualentries/exits ไม่สร้างsource-seededpredictions ไม่เรียกsubset100%ว่าfullgoalผ่าน เก็บเดิมทั้ง35,462ไว้สำหรับintegrationเมื่อมีกฎentry/exit/sizingที่มีเหตุผลรองรับ

## สถานะการยืนยันกฎ lot

ยังไม่รู้ว่าใช้balance, equity, free margin, risk% หรือmanual inputs; fee/swapรายorderไม่มี จึงยังคำนวณactualportfolioที่entryทุกไม้ไม่ได้ รอบนี้เป็นforensic evidence/แผนcomponent ไม่ใช่implementedrecoveredauto-lot และไม่ส่งtradeหรือแก้productionconfig

เครื่องมือ `analyze_lot_scope.py` สร้างderivedJSONL/reportด้วยfreshtag เก็บsource/code/plan hashesและQAประชากรครบ ใช้เฉพาะarchiveเดิม ไม่ดึงliveaccount ไม่เปลี่ยนข้อมูลดิบ
