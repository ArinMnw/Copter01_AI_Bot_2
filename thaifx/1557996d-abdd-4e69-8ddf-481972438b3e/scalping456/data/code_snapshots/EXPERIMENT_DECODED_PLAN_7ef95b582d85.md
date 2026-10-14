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
