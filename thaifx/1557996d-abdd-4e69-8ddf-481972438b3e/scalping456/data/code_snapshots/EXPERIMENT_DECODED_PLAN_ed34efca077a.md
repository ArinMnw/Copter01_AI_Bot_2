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
