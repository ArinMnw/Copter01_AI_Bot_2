# Closed-candle / grid experiments ก่อนรัน

รอบต่อจาก Vantage export วันที่8ตุลาคม2026 ใช้ source snapshot เดิม35,462 orders ทุกกลุ่ม ไม่เปลี่ยนเกณฑ์100% Source ledger เคยอ่านแล้วจึงไม่มี unseen holdout ในช่วงนี้ Development ก่อน21กันยายน / chronological validation ตั้งแต่21กันยายน แยกไว้ตามแผนเดิม ไม่ปรับ parameters จาก validation scores

## Closed-candle candidates (20)

ใช้ broker OHLC จริง M1/M5/M15/M30/H1 ไม่สร้างแท่ง/เส้นทาง ticks เพื่อเติม gap Bar จะถูกนำมาใช้เมื่อ close time <= current tick เท่านั้น

- Body: ทิศของแท่งปิดล่าสุด BUY เมื่อ close>open / SELL ตรงข้าม มีสิทธิ์เข้าได้หนึ่งครั้งต่อแท่งที่ปิด เมื่อ flat ไม่อ่านแท่งกำลังก่อตัว
- Engulf: closed body engulf แท่งปิดก่อนหน้า ฝั่งตรงข้าม หนึ่งครั้งต่อแท่งที่ปิด
- Breakout: bid ทะลุ high/low ของแท่งปิดล่าสุดอย่างน้อย0.01 ใช้ระดับเดิมได้หลายครั้งหลัง simulated exit ถ้ายัง flat ไม่มี source resets
- ทุก TF ทดลอง3 entry rules ข้างต้นกับ SL100 / trail activation40 / distance30 / level exit / volume10 =15 candidates; Breakout เพิ่ม quote exit ทั้ง5TF รวม20

SL/trailing/volume นี้เป็น benchmark ที่ถูกปฏิเสธไปแล้วสำหรับทั้ง cohort ใช้ตรึง exit เพื่อวัด entry ทางเลือก ไม่อ้างว่าเป็น recovered inputs หากยังไม่ตรงต้องแยกปัญหา entry กับ exit ไม่จูน timing tolerance

## FixedVol20 candidates (18)

16 grid candidates = grid+target3 หรือ15 × progressiveหรือfixed .1 lot × fixed-closeหรือrolling extrema entry × quoteหรือpending-level grid fill Entry threshold3, progressive ratio1.68, step.1, max174, TP weighted average +/−target ปัดhalf-up3digits

Pending-level mode ตั้งระดับ last filled entry +/−step ก่อน tick ที่ trigger; เมื่อ quote ข้ามระดับให้ fill ระดับนั้นใน hypothesis ไม่หยิบ actual source entry มาเป็นระดับ แต่ยังเติมได้เพียง1leg/tick ไม่มี emergency action ที่เดาจาก ledger ไม่มี date-based switches เป็น presets คงที่ทั้งช่วงเพื่อทดสอบว่า homogeneous engine อธิบายข้อมูลได้หรือไม่

2 SL-trial candidates: volume.1, initial stopราคา10, entryราคา3, activation0/distanceราคา10, levelหรือquote exit เป็น explicit hypothesis สำหรับ partial negative exits ไม่ใช่ recovered trial settings

## Replay/scoring

- State ต่อเนื่องจาก warm-upวันที่18สิงหาคม21UTCถึงก่อน8ตุลาคม01:17:56UTC ไม่ reset ตาม source entry/close/day/session
- Generate predictions ก่อนอ่าน source outcomes; เก็บทุก prediction รวมยังเปิดปลายช่วง ไม่ force close
- Score source window รวม35,462 rows ทุก symbol/trial/exception/manual-unknown; ใช้ strict_source_matcher เวลา tolerance0 กับsource precision
- Warm-up trades ที่ปิดก่อน source windowอยู่นอก comparison scope แต่ stateต้องคงไว้ Positionที่activeข้าม source boundaryยังนับ
- แยก full/development/chronological validation scores โดย stateไม่ reset ตอนแบ่งช่วง ต้องเก็บ missing/extraและunknown source closing behavior ไม่เลือก matched-only rows
- Reference/accelerator parity, future-prefix, future-bar rejection และ grid level/progression/TP priority ต้องผ่านก่อนรันจริง
- เก็บ script/strategy/plan/source/data SHA-256 และ full per-order/extra outputs แต่ tests/accountingผ่านไม่ใช่strategy100%

ยังไม่จำลอง original multi-EA equity/margin/hedge/manual controls ไม่ถือว่า experiment candidates รวมกันเป็น recovered source portfolio

## Reproduction audit เพิ่มหลังรันครั้งแรก

Portfolio prototypes ที่กำหนดใน code ก่อนเห็นผล: M1 breakout level + grid3 progressive fixed-close level + trial level และ M5 breakout quote + grid15 progressive rolling quote + trial quote ไม่เลือก components ตามผล validation ทั้งสองตัวถือเป็น hypotheses ไม่ใช่ EA instances ที่ยืนยัน

เพิ่ม CLI output tags เพื่อให้ทำซ้ำได้โดยไม่ลบ/overwrite snapshots เดิม แล้วรันทั้ง38candidates+2portfolios ซ้ำด้วย frozen parameters/data เดิม ตรวจ prediction file SHA-256 เทียบครั้งแรกครบ38models นี่เป็น reproducibility audit ไม่ใช่ parameter selection ใหม่หรือ unseen validation
