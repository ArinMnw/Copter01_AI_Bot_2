# FixedVol20 trial distance 2.8 — frozen before replay

8 ตุลาคม 2026 หลัง `data/vantage_path_constraints_20261008/qa_constraints.json`:
143 trial rows อยู่ development ทั้งหมด ไม่มี trial row ใน chronological validation เดิม จึงห้ามอ้าง unseen/validation สำเร็จสำหรับ parameters ของ trial นี้

## Evidence / hypothesis

- 110/143 มี interior peak-to-reported-close distance เท่ากับราคา 2.8 ที่ resolution ของ feed โดย 72 เป็น price-positive และ 38 เป็น price-negative; price-positive ไม่เท่ากับ gross-positive เพราะ rounding ถึง cents
- นี่เป็นการวัดจาก source intervals ไม่ใช่ causal predictions และไม่ยืนยัน EA inputs; 33 rows ยังมี pips ต่ำกว่า -280 ซึ่ง 27 เป็น nominal -1000 losses
- ทดสอบเพียงการเปลี่ยน trailing distance จากราคา10เป็น2.8 ในสอง benchmark เดิม ไม่จูน entry/time/activation เพื่อไล่ score

## Frozen parameters

สอง candidates: level/quote stop fill; `Scalping456Config.fixedvol20_trial(entry_reversal_points=300, trailing_activation_points=0, trailing_distance_points=280, stop_fill_mode=...)`.

`point=.01` เป็นหน่วยเว็บ ไม่ใช่ point .001 ของ broker; entry reversalราคา3, initial SLราคา10, trailing2.8, lot .1, fixed-close reference. เริ่ม state ว่างจาก first warm-up quote Aug18 21:00 UTC ถึง END exclusive Oct8 01:17:56 UTC เดิม ไม่มี session gates, ledger-based activation period หรือ reset ตาม actual positions. Entry3/activation0 ยังคือ benchmark ที่ไม่ยืนยัน ไม่ถือว่าค่าระยะ2.8ทำให้ entry เหล่านี้ถูกต้องโดยอัตโนมัติ

ใช้ Vantage FixedVol20 cache เดิม hash/provenance ต้องตรง Reference/vector parity บน actual Sep7 day ก่อน full run แล้วสร้าง predictions ทั้งสองก่อนอ่าน closed ledgerเพื่อ score บันทึกทุก35,462 source resultsและทุก extra; source symbols ที่ไม่ได้สร้างยังนับ missing ไม่ตัดออก

## Validation / success boundary

Split Sep21 00:00 UTC เดิม, state ไม่ reset, validation ไม่ใช่ unseenเพราะเคย inspect ledger. Trial-specific validation population0ต้องแสดงตรงๆ. เป้าหมายทั้งหมด35,462 ordersยังคง missing0/extra0/allfields exact ห้ามใช้ QA/parity/path-distance consistency เป็น successแทน. รอบนี้ยังไม่รวม pending-stop/hedge/lot changes; public opening comments ใหม่เป็นหลักฐานสำหรับออกแบบ experimentแยกต่อ ไม่อ้าง input/versionเดิมโดยยังไม่มี proof.
