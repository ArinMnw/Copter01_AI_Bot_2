# แผนทดลอง decoded engines (ก่อนรัน predictions)

9 ตุลาคม 2026 — แผนนี้ล็อกก่อนรัน `replay_decoded.py` ครั้งแรก ผลหลักฐานที่นำมาสร้างสมมติฐานอยู่ใน `data/decoded_evidence_20261009/` และ `data/decoded_timing_20261009/` (สร้างด้วย `analyze_decoded_evidence.py` / `analyze_decoded_timing.py`; รอบ `_r2` เพิ่มแกน activation strict/inclusive ส่วนรอบแรกเก็บไว้เป็นหลักฐาน)

## สมมติฐานและหลักฐาน

| # | สมมติฐาน | หลักฐานที่ใช้ |
|---|---|---|
| H1 | ราคา source ของ `XAUUSD+` = quote Vantage demo `XAUUSD` ขยับเข้าใน: `bid_src = bid + 0.06`, `ask_src = ask - 0.05` | ราคา SL ขาดทุน −100 pips ตัดผ่าน source bid/ask ในวินาทีปิดจริง dev 87.9%/88.7% (offset 0 = 62%/64%) และ later 80.5%/81.5% |
| H2 | `FixedVol20` ใน feed นี้เหมือน source ทุก tick (1 tick/s) | ราคาเข้า = ask/bid tick ตรงเป๊ะ 54.3% ของ `[tp` ส่วน offset อื่น <0.3% |
| H3 | ทองเข้าด้วย BUY STOP/SELL STOP ที่ fill ที่ระดับ pending | crossing ของระดับเข้าใกล้วินาทีเปิด 94.1% (shift baseline 3.6–7.7%) |
| H4 | หลังไม้ปิด EA อ่าน quote แล้ววาง pending ที่ `ask_src+D` / `bid_src−D` และลบคู่เก่าทิ้ง; D=1.00 ถึง 30 ก.ย., D=1.30 หลังจากนั้น | D=100 อธิบาย 85.5% (control 99/101 ≈ 26–28%), D=130 อธิบาย 97.7% ของ 1–7 ต.ค. |
| H5 | initial SL 1.00; trailing ห่าง 0.20 จาก bid/ask ที่ดีที่สุดเมื่อกำไร > 0.20 (strict); ราคา SL ปิด + 0.20 เป็นค่า tick จริง | 99.1% (control 56–70%); min(peak−stop)=20 |
| H6 | EA ไม่ update trailing ทุก tick: modify ใช้เวลา `busy` และมีผลหลัง `effect` | grid dev (`data/decoded_evidence_20261009_r2/`): activation > 0.20, busy 800 / effect 400 ดีสุด both=32.6% (later 32.4%) |
| H7 | FixedVol20: stop-entry ±D จาก quote 1 tick หลังปิด basket; เพิ่ม leg เมื่อสวนทาง `step`; lot ×1.68 ปัด 0.1 cap 174; TP = volume-weighted entry ปัดครึ่งขึ้น 0.001 ± tp | D=3.000 ที่ j=1 69–78%; grid first-crossing 96.4%; TP rounding 834/836 |
| H8 | พารามิเตอร์ผู้ใช้ (lot, D, step, TP) เปลี่ยนเป็นช่วง ๆ — เป็น scenario input ที่อ่านจาก ledger (`decoded_schedule.py`) | day/6h regime tables |

## ค่าที่ล็อก

Gold: bid +6c, ask −5c, initial SL 100c, trail activation gain > 20c / distance 20c, react_ms=110 (dev-selected, coverage ≈55%), modify busy 800 ms / effect 400 ms (dev-selected), stop fill = level, sibling pending คงอยู่จนวางคู่ใหม่, ค่า regime ตาม `decoded_schedule.py` (era E0/E2/ช่วงเปลี่ยน 30 ก.ย. = inactive เพราะยังไม่ถอดกลไกเข้า)

Fixed: reference tick = close tick + 1, D/step/TP/lot ตาม `decoded_schedule.py`, ช่วง 5 ก.ย. ก่อน 17:40 (D=5.0 + SL trial 143 rows) = inactive

## วิธีรัน/ให้คะแนน

- เริ่ม tick แรกของ warm-up (18 ส.ค. 21:00 UTC) ต่อเนื่อง ไม่ reset ตาม ledger/วัน/ไม้
- ใช้ strict matcher เวลา tolerance 0 ที่ความละเอียด source เทียบทั้ง 35,462 rows (ทอง 31,210 + Fixed 4,252) หนึ่งต่อหนึ่ง; era ที่ inactive นับ missing
- รายงานแยก: ทั้งช่วง, development (< 21 ก.ย.) / later (ไม่ใช่ unseen), cohort, symbol, era
- diagnostic เพิ่ม (ระบุชัดว่าเป็น conditional ไม่ใช่ prediction): เริ่ม Fixed ใหม่จาก tick ปิดจริงของ basket ก่อนหน้าแล้ววัด basket แรก
- เกณฑ์ผ่าน: exact 35,462, missing 0, extra 0 (คาดว่าไม่ผ่าน; ผลจริงจะถูกรายงานตามจริง)

## Run 2 addendum (หลังเห็นผล run 1)

Run 1 (`decoded_replay_20261009`, ไฟล์โค้ด/แผนเดิมเก็บใน `data/code_snapshots/*_e69b63b6be04|5b51ce3ad647|2f3666519d6d|5647ccff6485`) ได้ exact 2,293 / missing 33,169 / extra 51,249 จึงเพิ่ม H9 ตามหลักฐานที่มีอยู่ก่อนรัน (ใน 10-lot era entry ที่ซ้อนกับ position อื่นมีเพียง 48/21,814 และทุกคู่ห่าง 2.10–2.11 = pending พี่น้อง): **EA วางคู่ pending ใหม่เฉพาะตอนไม่มี position เปิดอยู่** (`place_only_when_flat`, เปิดด้วย `--flat-only`) ไม่เปลี่ยนค่าอื่น; run 1 เก็บผลไว้ไม่ทับ ความสัมพันธ์ H9 ถูกเลือกหลังเห็นผล run 1 จึงไม่ถือเป็นผล pre-registered

## Run 3 addendum (หลังเห็น run 1–2)

Run 1–2 ตั้ง era ทอง 23–26 ส.ค., 27–30 ส.ค. และ 30 ก.ย. 12:50–20:46 เป็น inactive เพราะ classifier แรกลองแค่ D=1.00/1.30 หลัง run 2 สแกน D=90–200 ในช่วงเหล่านั้น (`scratchpad` ต่อมาเป็นตาราง §3 ใน DECODED_MECHANICS_RESULTS.md) พบ: **27 ส.ค. 06:10–28 ส.ค.: D=1.05 อธิบาย 92%** (neighbors ≤36%), **23–26 ส.ค.: D=1.05 อธิบาย 84.7% แต่ reference tick ช้ากว่า (มัธยฐาน 680 ms, ไม่มีคาบ timer)**, **30 ก.ย. 14:23–16:12: D=1.10 อธิบาย 92%**, 12:40–14:20 ยังเป็น D=1.00, EA ไม่มีไม้ 16:12–20:54 จึงแก้ schedule เป็น regime ใหม่ (`GoldRegime.react_ms` เฉพาะ E0=680 ms) ค่าอื่นเท่า run 1; ขอบเขต regime อ่านจาก ledger เช่นเดิม (ledger-derived input) และการค้นพบนี้เลือกหลังเห็นผล run 1–2 จึงไม่ถือเป็น pre-registered; โค้ด/แผนของ run 1–2 เก็บใน `data/code_snapshots/`

## Run 4 addendum (FixedVol20 SL-trial engine)

หลัง run 3 ตรวจ 143 แถว `[sl` ของ FixedVol20 (5 ก.ย. 07:58–6 ก.ย. 04:21) บน feed ที่ตรง tick: entry เป็น stop-level crossing ครบ 143/143, ระยะ pending จาก quote 1 tick หลังปิด = 5.000 (ถึง 14:50) แล้ว 3.000; exit = initial SL 10.000, trailing ห่าง 2.800 (= `trade_stops_level` 2800 points ของสัญลักษณ์นี้ ซึ่งตรวจ read-only จาก terminal; ทองคือ 20 points = 0.20) เมื่อกำไรถึง activation: conditional บน entry tick, activation 2.000 ตรง stop+วินาทีปิด 125/143 (act 2.8 = 98, act 0 = 79, act −∞ = 66; สแกน 1.7–2.3 สูงสุดที่ 1.95–2.05) จึงเพิ่ม `FixedRegime.mode="trailing"` (initial_stop 10.000, activation 2.000, distance 2.800) และตั้งช่วง 5 ก.ย. 07:50–6 ก.ย. 04:30 เป็นโหมดนี้ แล้วเริ่ม grid engine ที่ 04:30 (เดิม run 1–3 ใช้ grid ตั้งแต่ 5 ก.ย. 17:40 ซึ่งผิดช่วง) ค่า activation เลือกจาก 143 แถวทั้งหมดซึ่งส่วนใหญ่ก่อน 21 ก.ย. (ไม่มี validation แยกสำหรับ engine นี้) และเลือกหลังเห็นผล run 1–3 จึงไม่ถือเป็น pre-registered ค่าอื่นเท่า run 3

## Run 5 addendum (FixedVol20 session windows)

Run 4 ยังมี extra Fixed 7,452 แถวในช่วง grid เพราะ engine เปิดตะกร้าตลอดเวลาขณะ ledger มีช่วงว่างยาว วิเคราะห์เวลาเปิด first-leg ตาม UTC ของ 6–12 ก.ย. (7 วัน): เปิดเฉพาะ 23:00–10:00, 13:00–13:35, 20:00–21:05 (นอกช่วงนี้ 1–2 แถว/7 วัน) ส่วน leg เพิ่มและการปิดของ basket ที่เปิดไว้แล้วเกิดนอกช่วงได้ (adds นอกช่วง 4%) จึงเพิ่ม `FixedRegime.sessions` = ช่วงที่อนุญาตให้ "วางคู่ pending ใหม่" และยกเลิก pending เมื่อออกนอกช่วง (spill หลังปลายช่วง 1 แถวต่อชั่วโมงต่อ 7 วัน) ใช้ตั้งแต่ 6 ก.ย. 04:30 ถึง 12 ก.ย. 14:00 เท่านั้น (หลังจากนั้นเปิดทุกชั่วโมง) ขอบเขตอ่านจากเวลาเปิดใน ledger (ledger-derived input เหมือน regime อื่น) และเลือกหลังเห็นผล run 4 ค่าอื่นเท่าเดิม

## Run 6 addendum (operator flatten at the 27 Sep inputs change)

ใน run 5 ช่วง F2 (หลัง 27 ก.ย. 04:38:39) ได้ exact 0/216 แม้ conditional บอก leg แรกตรง ~50%: ตรวจพบว่า ref ask ที่ tick 04:38:39 + 2.802 = 8719.771 เท่ากับ entry แรกของ ledger (BUY 04:43:52) พอดี แต่ engine ยังค้าง basket จากช่วง F1 จึงไม่ได้วางคู่ใหม่ ledger แสดงว่าพี่ปิด 2 ไม้ด้วยมือ (คอมเมนต์ว่าง 04:28:38 และ 04:38:38) ก่อนเปลี่ยน inputs จึงเพิ่ม `FixedRegime.flatten_at_start` (ทิ้ง basket ที่ค้าง ไม่ถือเป็น order ที่ engine สร้าง และวางคู่ใหม่ทันที) ใช้เฉพาะ regime นี้ เป็น scenario input ที่ระบุเหตุการณ์ปิดมือ 1 ครั้งซึ่งเห็นจาก ledger (ไม่ใช่ reset ตาม order ราย ๆ) ค่าอื่นเท่า run 5

## Run 7 addendum (broker stops level explains the trailing distance and the "lag")

read-only `symbol_info` (`data/decoded_symbol_specs_20261009/specs.json`) ให้ `trade_stops_level` = **20 points (0.20) สำหรับ XAUUSD** และ **2800 points (2.800) สำหรับ FixedVol20** ตรงกับระยะ trailing ที่ถอดได้ทั้งสอง จึงตั้งสมมติฐาน H10: EA ขอ SL ที่ระยะต่ำสุดที่ broker อนุญาต (best quote ∓ stops level) server ตรวจระยะนี้กับ quote ณ ตอนคำขอมาถึง (ดีเลย์ `trail_latency_ms`) ถ้าราคาเคลื่อนเข้าหา SL ระหว่างทางก็ปฏิเสธและ EA ลองใหม่ตอน tick ถัดไป (EA ไม่ว่างเป็นเวลา `trail_block_ms`) เหตุผลนี้แทนโมเดล busy/effect เดิมที่เป็นตัวประมาณเชิงประจักษ์ เลือก latency/block จากแถว dev (ก่อน 21 ก.ย.) ใน `data/decoded_evidence_20261009_r4/`: latency 300 / block 300 ms ดีสุด dev both 51.1% final-stop 54.5% (later 54.9% / 59.1%) เทียบ busy/effect เดิม 32.6% / 35.4% ค่าอื่นเท่า run 6 โมเดลเดิมยังเลือกได้ด้วย `trail_model="busy_effect"` และ snapshot ของ run 1–6 เก็บใน `data/code_snapshots/`

## Run 8 addendum (tick-based reaction instead of a constant delay)

`data/decoded_timing_20261009_r2/` เทียบ "reference = tick ที่ปิด + j" กับดีเลย์คงที่: D=1.00/1.05 (ก่อน 30 ก.ย.) j=1 อธิบาย 60.5% (dev) / 51.9% (later) สูงกว่าดีเลย์คงที่ที่ดีสุด 110 ms (55.4% / 48.0%), D=1.30 (1–7 ต.ค. ซึ่งเป็นช่วงหลัง 21 ก.ย. ทั้งหมด) j=0 อธิบาย 55.1% (j=1 45.7%) จึงเปลี่ยนจาก `react_ms` เป็น `GoldRegime.place_offset`: 1 สำหรับ E1/E2/E3/T1 และ 0 สำหรับ E4 (E0 ยังใช้ดีเลย์ 680 ms) เหตุผลเชิงกลไก: EA ทำงานเมื่อมี tick (OnTick) ไม่ใช่ตามนาฬิกา; offset ของ E4 เลือกจากข้อมูลช่วงเดียวกัน (ไม่มี holdout); ทดสอบกฎ "รอจน EA ว่างจากคำขอ SL ที่ค้าง" แล้วไม่ดีกว่า j=1 (66.6% vs 67.7%) จึงไม่ใช้ ค่าอื่นเท่า run 7

## Run 10 addendum (trailing step and first-request delay)

`data/decoded_evidence_20261009_r5/` เลือกพารามิเตอร์เพิ่มบน dev sample A (seed 7, 1,500 แถว) แล้วให้คะแนนบน dev sample B (seed 8) และ later sample C (seed 9) ที่ไม่ได้ใช้เลือก: SL ใหม่ต้องดีกว่าเดิม **มากกว่า 1 cent** (`trail_step` = 1 point แบบ trailing-step มาตรฐาน), ไม่ส่งคำขอ SL ก่อน 900 ms หลัง fill (`trail_first_delay_ms`), latency/block 270 ms ผลที่ตัวชนะ stop+วินาทีปิด: A 57.9%, B 57.3%, C(later) 62.3% เทียบ engine run 7–9 (step 0, delay 0, 300/300): 51.3% / 50.3% / 54.6% ค่าอื่นเท่า run 8–9; โมเดลเก่าเลือกได้ด้วย `trail_model="busy_effect"` และโค้ด run 1–9 เก็บใน `data/code_snapshots/`

## Run 11 addendum (no behavior change: general tick offset)

`place_offset` ตอนนี้รองรับค่า ≥ 0 ใด ๆ (เดิมรองรับเฉพาะ 0/1) เพื่อใช้ทดสอบ diagnostic ตามที่วางไว้ ผล replay เต็มยืนยันว่าไม่เปลี่ยน (`data/decoded_replay_20261009_r11_offset_general`: exact 6,213 / missing 29,249 / extra 51,418 เท่า run 10)

## Run 12 addendum (FORWARD HOLDOUT — pre-registered before any forward order is read)

**เป้าหมาย:** ทดสอบ engine ที่ล็อกแล้ว (run 10/11) กับ order ที่เกิด *หลัง* snapshot 35,462 แถว ซึ่งไม่เคยถูกใช้เลือกพารามิเตอร์ ประเมินโดยเทียบ "ทำนายทั้งหมดก่อน" กับ ledger ใหม่

**ข้อมูล:** (1) snapshot เดิม `data/orders_35462.jsonl` (sha256 `b8f5f75d…`) ปิดล่าสุด 2026-10-08T04:17:55 (raw server clock) = 01:17:55 inferred UTC; (2) order ใหม่ที่ `fetch_forward_orders.py` ดึงแบบ read-only จากหน้าโปรไฟล์สาธารณะลง `data/forward_watch_20261009/` (ไฟล์ exclusive, ไม่แก้ snapshot) — ก่อนเขียนแผนนี้ผู้ทดลอง *เคยเห็น* เฉพาะ: จำนวนแถว (512 ทอง + 15 FixedVol20), ช่วง open/close ต่ำสุด–สูงสุด, และแถว FixedVol20 15 แถว (lot 0.1–0.5, TP ±15 ชนิดเดียวกับ F2) ไม่เคยเห็นแถวทอง; (3) tick demo Vantage XAUUSD และ FixedVol20 ช่วง 2026-10-08T01:17:56–2026-10-09T02:00:00 inferred UTC ส่งออก read-only ด้วย `export_vantage_ticks.py` (tag `vantage_gold_fwd1` / `vantage_fixed_fwd1`, query shift +3 h เท่าเดิม)

**ค่าล็อก (ห้ามแก้หลังเห็นผล):** โค้ด/พารามิเตอร์ของ run 10/11 ทุกตัว; schedule = `decoded_schedule.py` เดิมไม่เพิ่มแถวใหม่ ดังนั้นช่วง forward ใช้ regime สุดท้ายเดิม: ทอง E4 (D=1.30, lot 10, place_offset 0) และ Fixed F2 (entry 2.802, step/TP 15.0, base 0.1) โดยสมมติว่าพี่ไม่เปลี่ยน inputs — ถ้า ledger ใหม่แสดงว่า inputs เปลี่ยน นั่นคือส่วนของความผิดพลาดที่ต้องรายงาน ไม่ใช่เหตุให้แก้ย้อนหลังแล้วเรียก holdout

**วิธี:** รัน simulator ต่อเนื่องจาก tick แรก warm-up (18 ส.ค. 21:00 UTC) จนถึง horizon 2026-10-09T02:00:00 inferred UTC โดยต่อ tick cache เดิมกับ cache ใหม่ (ตรวจ hash/ลำดับเวลา/รอยต่อ) ไม่ reset; เขียน `predictions.jsonl` + sha256 ลง `pre_score_manifest.json` *ก่อน* โหลดแถว forward; แล้วให้คะแนนด้วย strict matcher (tolerance 0 ที่ความละเอียด source) ระหว่างแถว forward ที่ปิดภายใน horizon กับ prediction ที่ปิดหลัง 01:17:55 inferred และไม่เกิน horizon (position ที่ยังเปิดตอน horizon ไม่เข้าการให้คะแนนทั้งสองฝั่ง รายงานจำนวนแยก); รายงานแยก symbol/วัน/ชั่วโมง extras เทียบกับช่วงที่ ledger ว่าง

**เกณฑ์ผ่าน/ไม่ผ่านที่ประกาศก่อนเห็นผล:** ผลนี้ใช้ "ประเมินการวางนัยทั่วไป" เท่านั้น ไม่ใช่การพิสูจน์ 100%: exact/missing/extra ถูกรายงานตามจริง, ไม่ปรับโมเดลเพื่อเพิ่มคะแนนบนแถว forward ชุดนี้ (ถ้าจะปรับต้องรอ forward ชุดใหม่ที่ไม่ได้ใช้เลือก)

## Run 12 result note (บันทึกหลังรัน; ไม่แก้ค่าที่ล็อก)

`data/decoded_forward_20261009/`: ทำนายเขียน hash ใน `pre_score_manifest.json` ก่อนโหลดแถว forward. ผล exact 134 / 527 (ทอง 134/512 = 26.2%, FixedVol20 0/15), predicted 872, extra 738 — เทียบ run 10 ในช่วง E4 (D=1.30) ที่ใช้เลือกพารามิเตอร์: 1,039/4,059 = 25.6% และ F2 Fixed 2/221 ดังนั้นไม่มีสัญญาณ overfit แต่ก็ไม่ทะลุเพดานเดิม extras ส่วนใหญ่ (≈280 รายการทอง) อยู่ในช่วง 01:17–10:55 inferred UTC ที่ ledger ไม่มีการเทรดเลย (position 2 ไม้ขนาด 10 lot ไม่มี SL ค้าง 12 ชม. แล้วถูกปิดมือ/trailing 13:55 raw) ซึ่งเป็นเหตุการณ์ภายนอกแบบเดียวกับ stuck/idle ใน §ผลลบ เดิม

## Run 13 addendum (oracle-ceiling diagnostic, conditional — NOT a replay score)

คำถาม: ตัวแปรที่ซ่อนอยู่แต่ละตัวทำให้เสีย exact เท่าใด? ใช้การทดลองแบบ conditional (เริ่มจาก close จริงของ order ก่อนหน้า เหมือน `diagnose_decoded_conditional.py`, สุ่มตัวอย่าง seed 20261009 ชุดเดียวกัน) แล้วให้ "oracle" เลือกค่าตัวแปรที่ซ่อนจากชุดจำกัดที่ประกาศล่วงหน้า: (a) offset ของ reference tick j ∈ {0,1,2,3,4} ต่อการวางคู่ (b) ชุดพารามิเตอร์ trailing/คำขอ SL ∈ {(270,step1,delay900) ฐาน, (0,0,0), (100,1,900), (200,1,900), (400,1,900), (270,0,900), (270,1,0), (270,1,1500)} (latency=block) นับ order ว่า "อธิบายได้" ถ้ามีค่าใดค่าหนึ่งในชุดทำให้ (วินาทีเปิด, ด้าน, ราคาเปิด, วินาทีปิด, ราคาปิด) ตรงทั้งหมด รายงานเป็นเพดานเชิงโครงสร้างที่สะสมทีละตัวแปร (ฐาน → +oracle j → +oracle trailing) และจำนวนที่ยังอธิบายไม่ได้แม้ใช้ oracle ทั้งหมด (= ข้อผิดพลาดของ *โครงสร้าง* ที่ไม่ใช่ตัวแปรซ่อนในชุดนี้) ผลนี้ใช้ข้อมูล ledger เป็นตัวเลือกค่า จึงห้ามอ้างเป็น replay score; ไม่เปลี่ยนโมเดลที่ล็อกไว้

## Run 13 result note

`data/decoded_oracle_20261009/report.json` (conditional, ไม่ใช่คะแนน replay): E3 dev (n=1,487) ฐาน 453 (30.5%) → oracle j ทำให้ entry ตรง 1,131 (76.1%) → +trailing ฐาน 675 (45.4%) → +oracle trailing 822 (55.3%); E4 (n=1,464) ฐาน 596 (40.7%) → entry ตรง 1,357 (92.7%) → 1,041 (71.1%) → 1,187 (81.1%) oracle j คือตัวแปรซ่อนที่ทำให้เสียมากสุด (E4 +30 จุดที่ exact, E3 +15 จุด) รองลงมาคือ SL-request/trailing (~+10 จุดทั้งสอง era); ที่เหลือ 19% (E4) / 45% (E3) อธิบายไม่ได้แม้ใช้ oracle ชุดนี้ (E3: ราคาตรงแต่วินาทีเปิดต่าง 175 แถว หรือวินาทีตรงแต่ราคาต่าง 118 แถว = jitter ของ feed/เวลา)

## Run 14 addendum (conditional diagnostic on the forward holdout rows)

หลังเห็นคะแนน run 12: ใช้ forward ledger ชุดเดียวกันทำ diagnostic แบบ conditional (เริ่มจาก close จริงของ order ก่อนหน้า, ไม่ใช่คะแนน replay และไม่ปรับโมเดล) เพื่อตอบว่ากลไกที่ล็อกไว้ *ถ้า sync ถูก* ทำนายแถว forward ได้เท่าที่เคยวัดบน dev/later หรือไม่: ทอง (D=1.30, j=0 ฐาน, oracle j และ oracle trailing เหมือน run 13, เฉพาะแถวหลังที่ EA กลับมาทำงานปกติ 10:55 inferred ซึ่งอ่านจาก ledger) และ FixedVol20 F2 (basket ที่เริ่มจาก close จริงของ basket ก่อนหน้า, นับ first-leg exact และ order exact) ค่าที่ใช้เหมือน run 13 ทั้งหมด
