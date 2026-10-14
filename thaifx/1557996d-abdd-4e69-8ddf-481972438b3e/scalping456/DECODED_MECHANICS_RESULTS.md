# ผลถอดกลไก: feed ทอง/FixedVol20, entry-exit mechanics และเพดานของ causal replay

9 ตุลาคม 2026 — ต่อจากงานเดิม ไม่เริ่มใหม่ ใช้ Vantage demo ที่พี่ล็อกอินไว้ (อ่าน market data และ `symbol_info` เท่านั้น ไม่ส่ง/แก้/ปิด order ไม่เปลี่ยนบัญชีหรือ Market Watch ไม่แตะ production bot) ผลสำคัญ: **ถอดกฎหลักได้จริงและวัดได้ แต่เป้า 35,462 orders ตรง 100% ยังไม่ผ่าน** continuous causal replay ที่ดีที่สุด (run 10) ตรง **6,213 / 35,462 (17.52%)**, missing 29,249, extra 51,418 (ดู §7) ผล forward holdout ที่ไม่เคยใช้เลือกพารามิเตอร์ (§13) ให้อัตราเท่าเดิม (ทอง 26.2% เทียบ 25.6% ในช่วง E4) จึงไม่ใช่ overfit แต่ก็ไม่ทะลุเพดาน ส่วนที่ไม่ตรงมาจากสามกลุ่ม: (ก) ความสุ่มของ EA/server ที่ replay แบบ causal จำลองให้ตรงทุก order ไม่ได้ (§9), (ข) ช่วงที่ EA หยุด/ถือ position ไม่มี SL/ปิดมือ ซึ่ง feed และ ledger ไม่บอกเวลา (§10), (ค) กลไกบางส่วนที่ยังถอดไม่ครบ

## 1. สิ่งที่เปลี่ยนจากความเชื่อเดิม

| เดิม | ตอนนี้ (พร้อมหลักฐาน) |
|---|---|
| ราคาเข้าทอง 6,039/7,312 แถวไม่เห็นบน executable quote ในวินาทีนั้น เลยสรุปว่า "quote-fill ทำซ้ำไม่ได้" | entry เป็น **pending stop ที่ fill ที่ระดับ pending** ไม่ใช่ราคา tick: ระดับถูก cross ใกล้วินาทีเปิด 94.1% (control เลื่อนเวลา 3.6–7.7%) และ feed ทองของ source ≈ demo `XAUUSD` ขยับเข้าใน bid+0.06 / ask−0.05 |
| trailing 40/30 หรือ 16/16 | ระยะ trailing **เท่ากับ `trade_stops_level` ของ broker**: ทอง 20 points = 0.20, FixedVol20 2800 points = 2.800 (อ่านจาก `symbol_info` read-only, `data/decoded_symbol_specs_20261009/`); EA ขอ SL ที่ระยะต่ำสุดที่อนุญาต และ server ปฏิเสธคำขอที่ราคาเคลื่อนเข้าหา SL ระหว่างทาง → นี่คือที่มาของ "EA ไม่ update ทุก tick" |
| entry distance คงที่ 1.00 ตลอด | D เปลี่ยนเป็นช่วง (input ของผู้ใช้): 1.05 (23 ส.ค.–26 ส.ค. 08:00 แต่ EA ตอบสนองช้า/สุ่ม มัธยฐาน 680 ms), 1.00 (26 ส.ค. 08:47–27 ส.ค. 06:02), 1.05 (27 ส.ค. 06:10–28 ส.ค.), 1.00 (30 ส.ค.–30 ก.ย. 14:20), 1.10 (30 ก.ย. 14:23–16:12), EA หยุด 16:12–20:54, 1.30 (หลัง 20:54) |
| FixedVol20 feed ไม่ยืนยันว่าเหมือน source | **bit-identical ระดับ tick**: ราคาเข้า = ask/bid ตรงเป๊ะ 54.3% (offset อื่น <0.3%), TP/SL crossing ตรงวินาทีปิด 96% ของ SL −1000 |
| FixedVol20 grid/hedge ไม่ทราบกฎ | stop-entry ±D จาก quote 1 tick หลังปิด basket; เพิ่ม leg เมื่อสวนทาง step; lot ×1.68 ปัด 0.1 cap 174; TP = ถัวเฉลี่ยถ่วงน้ำหนักปัดครึ่งขึ้น 0.001 ± tp; ก่อน 6 ก.ย. 04:30 เป็นอีก engine (single-leg trailing, §4); 6–12 ก.ย. วางคู่ใหม่ได้เฉพาะช่วงเวลา (sessions) |

## 2. Feed ทอง: ความสัมพันธ์ source ↔ Vantage demo `XAUUSD`

ทดสอบด้วย 7,876 stop-out ที่ขาดทุนพอดี −100 pips (ราคาปิด = ระดับ SL ที่ source ใช้จริง) ว่าเมื่อบวก offset c เข้า bid (BUY) หรือ ask (SELL) แล้ว "ครั้งแรกที่ตัดระดับ SL" ตกในวินาทีปิดเดียวกับ ledger กี่ %:

| ชุด | BUY best c | rate (c=0) | SELL best c | rate (c=0) |
|---|---:|---:|---:|---:|
| development (เปิดก่อน 21 ก.ย.) 5,579 แถว | +0.06 → 87.9% | 62.4% | −0.05 → 88.7% | 63.8% |
| later (ไม่ใช่ unseen) 2,297 แถว ที่ c ของ dev | 80.5% | 52.3% | 81.5% | 58.5% |

offset ดีสุดคงที่ทุกวัน 24 ส.ค.–7 ต.ค. (c=+0.055/−0.05; ทดสอบให้ขึ้นกับ spread ของ demo 0.21/0.22 แล้ว ค่าคงที่ +6/−5 cent ยังดีสุด) แปลว่า spread ฝั่ง source แคบกว่า demo 0.11 (demo 0.21–0.22 → source ≈ 0.10–0.11) ตรงกับ commission-based account ตอนแรกไม่พบ `XAUUSD+` ใน terminal นี้; ต่อมาบัญชี RAW ECN demo ที่พี่เพิ่มมี `XAUUSD+` จริงและ tick ต่างจาก `XAUUSD` ที่ bid +0.06 / ask −0.05 พอดี (§15) ส่วนที่เหลือ 11–20% ไม่ตรงบอกว่า tick ของ source ไม่เหมือน demo ทุกตัว (mid ใกล้ แต่ spread/จังหวะ tick ต่าง) → ราคาทองระดับ cent ตรง 100% ด้วย feed นี้ไม่ได้

`FixedVol20`: ราคาเข้า `[tp` ตรง ask/bid tick ในวินาทีเปิด 54.3%; offset +0.075 → 0.27%, −0.135 → 0.07%; tick มี 1 ตัวต่อวินาทีที่ ms ≈ 9 เหมือน source

## 3. กลไกทอง (PipScalperEA V2 — public open positions ระบุคอมเมนต์ BUY STOP/SELL STOP)

1. **entry**: หลังไม้ปิด EA อ่าน quote แล้วลบ pending เก่า วาง BUY STOP `ask_src + D` และ SELL STOP `bid_src − D` (pending ฝั่งตรงข้ามคงอยู่จนวางคู่ใหม่; entry ซ้อน position อื่นมีแค่ 48/21,814 และทุกคู่ห่าง 2.10–2.15 = pending พี่น้องที่ whipsaw)
2. หลักฐาน D: 10-lot era หา `E − ref = 100` ภายใน 3 tick หลัง predecessor close ได้ 85.5% (control D=99/101 ≈ 26–28%, 98/102 ≈ 18%, 105 ≈ 8%, 130 ≈ 0.2%); ช่วง 1–7 ต.ค. D=130 อธิบาย 97.7%
3. **reference tick** (EA ทำงานตาม tick ไม่ใช่นาฬิกา): "tick ที่ปิด + 1" อธิบาย 60.5% (dev) / 51.9% (later) สูงกว่าดีเลย์คงที่ที่ดีสุด 110 ms (55.4% / 48.0%); ช่วง D=1.30 "tick ที่ปิดเอง" อธิบาย 55.1% (j=1 45.7%) จึงใช้ `place_offset` 1 (ก่อน 30 ก.ย. 20:46) และ 0 (หลังจากนั้น) ส่วน E0 ใช้ดีเลย์ 680 ms; ไม่พบ feature ที่ทำนาย j ได้ (§9), กฎ "รอจน EA ว่างจากคำขอ SL ค้าง" ไม่ดีกว่า j=1 (66.6% vs 67.7%)
4. **exit**: initial SL = entry ∓ 1.00 (ทุกวัน 95–99% ของ loss แถวเป็น −100 พอดี); เมื่อกำไร > 0.20 EA ส่งคำขอ SL = best quote ∓ 0.20 (= stops level) คำขอถึง server หลัง `trail_latency` และถูก **ปฏิเสธถ้าที่ quote ณ ตอนถึง ระยะ 0.20 ไม่เหลือแล้ว** (ราคาถอยหลังจากตัดสินใจ) EA ไม่ว่าง `trail_block` ms; grid บนแถว dev (`data/decoded_evidence_20261009_r4/`): latency 300 / block 300 ms ดีสุด → final-stop ตรง 54.5% และ stop+วินาทีปิด 51.1% (later 59.1% / 54.9%) เทียบโมเดล busy/effect เดิม 35.4% / 32.6%; ปรับต่อ (`_r5`, เลือกบน sample A แล้วให้คะแนนบน B และ later C): SL ใหม่ต้องดีกว่าเดิมมากกว่า 1 cent (trailing step 1 point), ไม่ส่งคำขอก่อน 900 ms หลัง fill, latency/block 270 ms → stop+วินาทีปิด A 57.9%, B 57.3%, C(later) 62.3% (engine ก่อนหน้า 51.3% / 50.3% / 54.6%) — ตระกูล "EA ประมวลผลทีละ tick P ms" 108 แบบ (`data/decoded_processing_20261009/`) ไม่ทะลุ ~34%
5. ไม่มีคาบ timer เด่น (circular statistic สูงสุด ≤ 0.04 เทียบ null 0.013), ไม่ใช่ "tick แรกของวินาทีถัดไป" (11.8%)

era (UTC inferred, ทุกค่า D สแกน 90–200 cent เทียบ control): **E0** 23 ส.ค. 22:05–26 ส.ค. 08:00 D=1.05 อธิบาย 84.7% ภายใน 20 tick แต่ reference tick มัธยฐาน 6 tick/680 ms (IQR 386–1,005 ms, ไม่มีคาบ timer; ดีเลย์คงที่ที่ดีสุด 800 ms ครอบเพียง 16.8%), **E1** 26 ส.ค. 08:47–27 ส.ค. 06:02 D=1.00 (92–99%), **E2** 27 ส.ค. 06:10–28 ส.ค. D=1.05 (92%), **E3** 30 ส.ค. 22:02–30 ก.ย. 14:20 D=1.00 (92–99%/วัน), **T1** 30 ก.ย. 14:23–16:12 D=1.10 (92%), 16:12–20:54 EA ไม่มีไม้, **E4** 20:54 เป็นต้นไป D=1.30 (97.7%) — run 1–2 ตั้ง E0/E2/T เป็น inactive เพราะ classifier แรกลองแค่ D=1.00/1.30; run 3 แก้หลังสแกน D (ผลหลัง run 1–2 จึงไม่ pre-registered, ดู `EXPERIMENT_DECODED_PLAN.md`)

## 4. กลไก FixedVol20

- **SL-trial engine (5 ก.ย. 07:58 – 6 ก.ย. 04:21, 143 แถว `[sl`)**: pending ±D จาก quote 1 tick หลังปิด (D=5.000 ถึง 14:50, แล้ว 3.000), stop-level trigger พบครบ 143/143, initial SL 10.000, trailing ห่าง 2.800 (= stops level) เมื่อกำไร ≥ ~2.000; conditional บน entry tick ตรง stop+วินาทีปิด **125/143 (87.4%)** ที่ activation 1.95–2.05 (act 0 = 79, act 2.8 = 98, act −∞ = 66) แยกตามผล: กำไร 72/72, ติด initial SL −10.000 26/27, ขาดทุนเล็ก 27/44 (`data/decoded_trial_20261009/`; ไม่มีช่วง validation เพราะทุกแถวก่อน 21 ก.ย.)
- **Grid engine (เริ่ม ~6 ก.ย. 04:30)**: pending ±D จาก quote **tick หลังปิด basket (j=1)**; D=3.000, หลัง 27 ก.ย. 04:38 D=2.802 (100 baskets); เพิ่ม leg เป็น market ที่ tick แรกที่สวนทาง ≥ step จาก leg ล่าสุด: step=3.000 ถูก 96.4% (ก่อน 27 ก.ย.), หลังจากนั้น step=15.000
- lot ถัดไป = ปัด(lot ก่อนหน้า × 1.68, 0.1) cap 174; base 0.1 หรือ 1.0 ตามช่วง (input ของผู้ใช้)
- TP basket = ปัดครึ่งขึ้น(ถัวเฉลี่ยถ่วงน้ำหนัก, 0.001) ± tp (3.000 → 15.000 หลัง 27 ก.ย.): ตรง 833/836 baskets หลาย leg; ปิดที่ระดับ TP (basket ที่ leg ปิดต่างวินาทีมี 15/1,535)
- **ช่วงเวลา (sessions)**: 6–12 ก.ย. เปิด first-leg เฉพาะ UTC 23:00–10:00, 13:00–13:35, 20:00–21:05 (นอกช่วง 1–2 แถว/7 วัน); leg เพิ่มและการปิดของ basket ที่เปิดแล้วเกิดนอกช่วงได้ (adds นอกช่วง 4%); หลัง 12 ก.ย. ไม่เห็นข้อจำกัดนี้
- **race**: reference tick ของ basket ถัดไปเป็น j=1 (480) vs j=0 (243) เมื่อ basket ก่อนหน้ามี 1 leg (66%/34%) และ j=1 84% (2 legs), 89–93% (≥3 legs); หลัง 27 ก.ย. j=1 เพียง 46% สำหรับ 1 leg; ลองหา predictor (phase ms, overshoot, gap tick, hold, spread, ด้าน, lot) ไม่พบ
- เมื่อ basket ที่มี leg แรกตรง: ทั้งก้อนตรง 74.6% (462/619) ที่เหลือ: leg เพิ่มเกิดช้ากว่า tick แรกที่เข้าเงื่อนไข 10.5%, ปิดช้ากว่า sim 1–23 วินาที 7.3% (ราคาปิดเท่ากัน), จำนวน leg/lot ต่าง 6.3%

## 5. ตารางช่วง regime ที่เป็น input จากผู้ใช้ (อ่านจาก ledger)

`decoded_schedule.py` — ขอบเขตของ lot (ทอง 0.01→1→0.01→1→10, Fixed 0.1↔1.0), D (ทอง 1.05/1.00/1.05/1.00/1.10/1.30 ตาม §3; Fixed 5.0→3.0→2.802), engine ของ Fixed (trailing → grid), step/TP (Fixed 3→15), sessions (Fixed 6–12 ก.ย.), ช่วง EA หยุด (ทอง 30 ก.ย. 16:15–20:46), reaction delay เฉพาะ E0, offset ของ tick อ้างอิง และ `flatten_at_start` 1 ครั้ง (27 ก.ย. 04:38:39 หลัง 2 ไม้ที่ปิดมือ) ถูกอ่านจาก ledger จึงเป็น **ledger-derived scenario input** ไม่ใช่ trade-level lookup: ไม่มี ticket/เวลาเข้า-ออก/ราคา/กำไรต่อ order lot 0.4 ใบเดียว (30 ก.ย. 12:25) และไม้ที่ถูกปิดมือ (คอมเมนต์ว่าง) ไม่ถูกจำลอง

## 6. Mechanics given correct start (conditional — ไม่ใช่คะแนน replay)

เริ่ม engine ใหม่ที่ tick ปิดจริงของ order/basket ก่อนหน้า (ใช้จุดเริ่มจาก ledger จึงห้ามอ้างเป็นผล replay; `data/decoded_conditional_20261009_r4/`):

| ชุด | trials | เปิดวินาที+ด้านตรง | เปิดวินาที+ด้าน+ราคาตรง | ตรงทุก field (เข้า+ออก) |
|---|---:|---:|---:|---:|
| ทอง 10 lot D=1.00 (2–30 ก.ย.) | 1,480 | 69.0% | 46.9% | 27.8% |
| ทอง 10 lot D=1.30 (1–7 ต.ค.) | 1,464 | 81.4% | 53.1% | 40.7% |
| Fixed grid (6–27 ก.ย.) 1,520 baskets / 3,835 orders | — | leg แรกตรง 67.0% | basket ตรงทั้งก้อน 54.5% | orders ตรง 47.2% |

(ก่อนใช้โมเดล stops-level: ทอง 14.5% / 20.0%) ใน trials ที่ entry ตรง exit ตรงต่อ 59% (D=1.00) และ 77% (D=1.30) จึงเหลือคอขวดที่ entry reference tick/feed; ใน trials ที่ side ตรง real entry ช้ากว่า sim เกิน 2 วินาที 12% และสัดส่วนเพิ่มตามความยาวช่วงรอ (1.4% เมื่อรอ ≤5 วินาที → 17% เมื่อรอ >30 วินาที) สอดคล้องกับ feed ที่ไม่เหมือน source ทุก tick มากกว่าจะเป็นกฎของ EA

## 7. คะแนน continuous causal replay (tolerance 0, ทั้ง 35,462 rows, ไม่ reset ตาม ledger)

ทุก run สร้าง predictions ก่อนอ่าน ledger, artifact + SHA-256 ใน `data/decoded_replay_20261009*/`, QA อิสระ `verify_decoded.py` ผ่านทุก run, โค้ด/แผนของแต่ละ run เก็บใน `data/code_snapshots/` และแผนมี addendum ต่อ run (บางส่วนเลือกหลังเห็นผล run ก่อนหน้า จึงไม่ pre-registered)

| Run | สิ่งที่เปลี่ยน | predicted | exact | missing | extra | dev exact / later exact |
|---|---|---:|---:|---:|---:|---|
| 1 | schedule แรก, trailing busy/effect | 53,542 | 2,293 | 33,169 | 51,249 | 1,544 / 749 |
| 2 | วางคู่เมื่อ flat (H9) | 53,532 | 2,293 | 33,169 | 51,239 | 1,544 / 749 |
| 3 | era E0/E2/T1 (D=1.05/1.10) | 61,860 | 2,495 | 32,967 | 59,365 | 1,743 / 752 |
| 4 | FixedVol20 SL-trial engine | 61,850 | 2,567 | 32,895 | 59,283 | 1,815 / 752 |
| 5 | Fixed sessions 6–12 ก.ย. | 60,864 | 2,671 | 32,791 | 58,193 | 1,919 / 752 |
| 6 | flatten 27 ก.ย. | 60,854 | 2,673 | 32,789 | 58,181 | 1,919 / 754 |
| 7 | trailing แบบ stops-level validation | 58,353 | 4,767 | 30,695 | 53,586 | 3,394 / 1,373 |
| 8 | reference tick แบบ tick-based | 58,332 | 5,190 | 30,272 | 53,142 | 3,713 / 1,477 |
| 9 | ยืนยันซ้ำหลังแก้บั๊ก init ของ diagnostics (ไม่กระทบ replay) | 58,332 | 5,190 | 30,272 | 53,142 | เท่ากัน |
| **10** | **trailing step 1 point + first request 900 ms + latency/block 270 ms** | **57,631** | **6,213** | **29,249** | **51,418** | **4,437 / 1,776** |

(dev = แถวที่เปิดก่อน 21 ก.ย. 24,354 แถว, later = 11,108 แถว; ไม่ใช่ unseen)

| cohort / era (run 10) | source rows | exact |
|---|---:|---:|
| ทอง E0 (D=1.05 ช้า, 23–26 ส.ค.) | 2,867 | 166 |
| ทอง E1 (D=1.00, 26–27 ส.ค.) | 1,257 | 200 |
| ทอง E2 (D=1.05, 27–30 ส.ค.) | 2,463 | 343 |
| ทอง E3 (D=1.00, 30 ส.ค.–30 ก.ย. 14:20) | 20,439 | 3,656 |
| ทอง T1 (D=1.10, 30 ก.ย.) | 125 | 4 |
| ทอง E4 (D=1.30, 30 ก.ย.–7 ต.ค.) | 4,059 | 1,039 |
| Fixed SL-trial (5 ก.ย.–6 ก.ย.) | 143 | 72 |
| Fixed TP ก่อน 27 ก.ย. | 3,860 | 731 |
| Fixed TP หลัง 27 ก.ย. | 216 | 2 |
| Fixed other / ทองคอมเมนต์ไม่ใช่ `[sl` (ปิดมือ ฯลฯ) | 33 + 87 | 0 |

Extra ส่วนใหญ่: ใน E3 ทอง engine เปิด ~36.3k orders เทียบ ledger 20.4k — 9.7k (26%) เกิดในชั่วโมงที่ ledger มี ≤3 ไม้ (137 ชั่วโมงที่ EA หยุด/ถือ position ไม่มี SL/ปิดมือ) และในชั่วโมงที่ ledger ทำงานปกติ engine ยังเปิดมากกว่า 1.28 เท่า (ยังไม่ทราบสาเหตุ); ไม่มีการซ่อนหรือขยาย tolerance

ความตรงรายวันของทอง (run 10, วันที่มี ≥200 ไม้): วันปกติ 25–33% (1, 2, 7 ก.ย., 1–2, 5–7 ต.ค.), 12–22% ช่วงกลางเดือน, 5–10% ช่วง 22–30 ก.ย.; รวม 30 วันที่มี ≥300 ไม้ 17.3% (5,320/30,712)

## 8. QA / tests

- `python -m unittest test_decoded -q` 25 tests (+ `test_forward` 3, `test_vantage_probe_account` 6); ทั้งชุด research suite รวม 123 tests (รวม causality ที่เปลี่ยน tick อนาคตแล้ว decision ก่อนหน้าไม่เปลี่ยน ทั้ง 3 โหมด, determinism, ไม่ import/อ่าน ledger ในโมดูลโมเดล, UTF-8/LF, ปฏิเสธคำขอ SL ที่ stale ตาม stops level, sessions/flatten/trailing ของ Fixed, matcher จับ error 1 cent เป็น missing+extra, report ครบ 35,462 unique tickets)
- `verify_decoded.py --tag ...` คำนวณ match ใหม่ด้วย key builder แยกและเทียบ flag ทุก order, hash artifact, population, count ตรง report

## 9. หลักฐานความสุ่ม (ทำไมเพดานต่ำกว่า 100% แม้ใช้กฎถูก)

| ส่วน | วัดอะไร | ผล | หมายเหตุ |
|---|---|---|---|
| ทอง: tick อ้างอิงวาง pending | reference = tick ที่ปิด + j | j=1 60.5% / 51.9%, j=0 25.7% / 27.0% (D=1.00 dev / later); D=1.30: j=0 55.1% | ไม่พบ feature ทำนาย (ผลแพ้/ชนะ, ด้านเดิม, ชั่วโมง, ช่องว่าง tick, สถานะ EA ถูกบล็อก: 50–67%) |
| ทอง: trailing | stop+วินาทีปิดตรง (dev B / later C) | 57.3% / 62.3% | ใช้กลไก stops-level + trailing step แล้ว เหลือส่วนที่ feed ต่างและ latency สุ่ม |
| ทอง: feed | SL crossing ตรงวินาที | 80–89% | tick ของ source ไม่ใช่ demo ทุกตัว |
| ทอง: feed (เพดานจากเวลาอย่างเดียว) | entry-trigger crossing ตกวินาทีเปิดเดียวกับ ledger เมื่อใช้ offset ดีสุด (ask −5 / bid +6, dev) | BUY 88.5%, SELL 90.2% (ปิด: 87.9% / 88.7% dev, 80.5% / 81.5% later) | ถ้าต้องถูกทั้งวินาทีเปิดและปิด ≈ 0.88² ≈ 77% (dev) / 0.81² ≈ 66% (later) ของ order ก่อนนับ race ของ EA — เวลา tick ของ source ต่างจาก demo ระดับ ~100 ms |
| ทอง: entry ทั้งก้อน | เปิดวินาที+ด้าน+ราคาตรงเมื่อจุดเริ่มถูก | 46.9% (D=1.00), 53.1% (D=1.30) | |
| Fixed: tick อ้างอิง | j=1 vs j=0 | 66% (1 leg) – 93% (≥5 legs); หลัง 27 ก.ย. 46% (1 leg) | race ระหว่าง server ปิด position กับ OnTick |
| Fixed: leg เพิ่ม | เป็น tick แรกที่เข้าเงื่อนไข | 96.4% ต่อ leg | basket 10 leg สะสมเสียเกือบ 30% |
| Fixed: SL-trial exit | stop+วินาทีปิด | 87.4% | ขาดทุนเล็ก 27/44 — ส่วนที่เหลือยังไม่ถอด |
| ทั้งสอง | position ไม่มี SL / ปิดมือ / close-by / orphan leg / EA หยุด | 87 ทอง + 33 Fixed + 12 close-by + ช่วงว่างยาว | trigger ไม่อยู่ใน feed หรือ ledger |

## 10. สิ่งที่ยังขัดแย้ง/ไม่ทราบ

1. ทอง E0 (2,867 แถว): D=1.05 ถูกต้องแต่ EA ตอบสนองช้า/สุ่ม (ดีเลย์คงที่ที่ดีสุดครอบเพียง 16.8%; j ของ tick อ้างอิงกระจาย 5–9 tick ราบ ~14%) จึงคะแนน exact ต่ำ (166/2,867); เฟสของ tick อ้างอิงเกาะกลุ่มภายในชั่วโมง (concentration mod 500 ms = 0.34, mod 1000 ms = 0.32 เทียบ null 0.20, 29 ชั่วโมง) บอกว่า EA เวอร์ชันแรกอาจใช้ timer ที่เฟสเลื่อนช้า แต่เฟสเป็นสถานะซ่อนที่อนุมานได้จาก ledger เท่านั้น จึงไม่นำมาใช้
2. Fixed SL-trial: ขาดทุนเล็ก 17/44 แถวไม่ตรง; D=5.0 ก่อน 14:51 ยังมี j=0 อยู่ 11/47
3. Position ทอง 10 lot ไม่มี SL (public open positions ก็เป็นแบบนี้): ตรวจแล้วว่าคำขอ SL เริ่มต้น (entry ∓ 1.00) จะถูก server ปฏิเสธเมื่อราคาเคลื่อนเข้า 0.80 ภายใน 270 ms หลัง fill — เกิดกับ fill 16 จาก 22,267 และ 13 ใน 16 เป็นไม้ special/ขาดทุน <−100 (precision 81%) แต่ครอบ special exits เพียง 8% ของ 167; เวลาและวิธีปิดด้วยมือไม่มีใน feed จึงจำลองช่วงที่ EA หยุดไม่ได้
4. ทอง `[sl` 372 แถว (4.5% ของ loss) ขาดทุนต่ำกว่า −100: ใน 304 แถว lot ≥ 1 ราคาปิดตรง tick ที่ตัด SL เพียง 1/304 และตัด SL ก่อนเวลาปิดจริงเป็นส่วนใหญ่ → ต้องมี order-modify/execution log
5. Engine ทองเปิดมากกว่า ledger: ส่วนเกินกระจุกในวัน/ชั่วโมงที่ ledger ว่าง (เช่น 9 ก.ย. บ่าย 125 vs 725 ไม้ในช่วง 12:30–19:30 UTC, 11 ก.ย. 18/1,020, 16 ก.ย. 47/1,204, 17–18 ก.ย. 0, 28–29 ก.ย. ~0) ขณะที่วันปกติจำนวนไม้ใกล้กัน (2 ก.ย. 1,135 vs 1,157 นอกช่วงนั้น, 8 ก.ย. 871 vs 929) จึงสรุปว่าไม่ใช่อัตราเทรดผิด แต่คือช่วงที่ EA หยุด/ถือไม้ไม่มี SL; ไม่ได้แก้ความต่างของ latency ตามสัปดาห์ (best trailing latency = 270 ms ทุกสัปดาห์ 36–41 ส่วน stop+วินาทีปิดตรง 46–79%)
6. Fixed หลัง 27 ก.ย. (216 แถว) ตรง 2 แถว: basket แรกตรงแต่ j=1 vs 0 สุ่ม (46%/54% สำหรับ 1 leg) ทำให้ sync หลุดทันที

### ผลลบที่ตรวจแล้ว (ไม่ต้องทำซ้ำ)

- **Trailing ทอง — EA ว่างช้ากว่าหลัง update สำเร็จ/ถูกปฏิเสธ:** แยก busy time ตามผลคำขอ (accept 0–200 ms, reject 0–120 ms, latency 200–270) ไม่ดีกว่า 270/270 เดิม (A 57.9% / B 57.3% / C 62.3%) แม้คำขอที่ sim รับแต่ ledger พลาดมักห่างจากคำขอก่อนหน้าแค่ ~330 ms
- **Trailing ทอง — ขอบ stops level:** margin 19/21 cent, `<` แทน `≤`, activation 15–25, step 2–10: แย่กว่าค่าเดิม (ยกเว้น step 1 ที่ใช้อยู่)
- **ตัวทำนาย j (tick อ้างอิง):** ทอง — ผลแพ้/ชนะ, ด้านเดิม, ชั่วโมง, ช่องว่าง tick, สถานะ EA ถูกบล็อกด้วยคำขอ SL, ดีเลย์เวลา+tick ขั้นต่ำ; Fixed — phase ms, overshoot, ระยะกระโดด, spread, ด้าน, lot, hold นอกเหนือจำนวน leg: ไม่ได้กฎที่ดีกว่า j=1
- **Fixed — leg เพิ่มช้ากว่า tick แรกที่เข้าเงื่อนไข:** 3.7% และไม่ขึ้นกับจำนวน leg (3–6% ทุกระดับ) จึงไม่ใช่ EA ยุ่งตอนแก้ TP หลายขา
- **Fixed — sessions หลัง 12 ก.ย.:** ไม่เห็นช่วงเปิดแบบกำหนดเวลา (first-leg กระจายทั้ง 24 ชั่วโมง เบาลง 12–15 UTC เพราะ basket ยาว)
- **ทอง — spread filter ตอนวาง pending:** ไม่มี (tick ที่ spread demo >22 ถูกใช้เป็น tick อ้างอิงบ่อยกว่า 7.4% vs 4.2%)

## 11. สรุปสถานะเทียบเกณฑ์ Goal

| เกณฑ์ | สถานะ |
|---|---|
| จับคู่หนึ่งต่อหนึ่งครบ 35,462 | ไม่ผ่าน (6,213 exact, run 10) |
| missing = 0 และ extra = 0 | ไม่ผ่าน (29,249 / 51,418) |
| ไม่ซ่อนข้อยกเว้น/ไม่ใช้ tolerance กว้าง | ผ่าน (tolerance 0 ที่ความละเอียด source; ทุก row ใน denominator) |
| ผลรายแถว + สรุปกลุ่ม + provenance + คำสั่งทำซ้ำ | ผ่าน (ด้านล่าง) |
| tests causality/matcher | ผ่าน |

**blocker**: เพดานของกฎที่ถอดได้ต่ำกว่า 100% อย่างมีหลักฐาน เพราะผลเข้า-ออกขึ้นกับ (ก) tick ที่ terminal ของ EA ต้นทางเห็นและเวลาที่ส่ง order/modify จริง (ms), (ข) ความสำเร็จ/ล้มเหลวของการตั้ง SL/TP, (ค) การกระทำของผู้ใช้ ข้อมูลที่จะลดความกำกวมได้คือ **MT5 history ของบัญชีต้นทางที่มี `time_msc` ของ orders/deals และ Journal ส่ง/modify** กับ **tick XAUUSD+ ของ server/บัญชีต้นทางเอง**; ไม่ใช่ EA/รหัสผ่าน และเป็นข้อมูลที่ public ledger ไม่มี รายการนี้ไม่ลดเป้า 100% และไม่ทำให้อลิซประกาศ complete แม้กลไกที่ถอดได้เพิ่มขึ้นทุกรอบ (2,293 → 6,213) ยังไม่มีเหตุผลว่าส่วนที่เหลือจะถึง 100% ได้จาก feed + ledger สาธารณะ

## 12. ทำซ้ำ

```powershell
python analyze_decoded_evidence.py --tag NEW_TAG        # feed calibration, mechanics, trailing grids (dev/later)
python analyze_decoded_timing.py --tag NEW_TAG          # reaction tick/delay coverage
python analyze_decoded_processing.py --tag NEW_TAG      # EA processing-time model families (dev only)
python analyze_decoded_trial.py --tag NEW_TAG           # FixedVol20 SL-trial engine evidence
python replay_decoded.py --tag NEW_TAG [--flat-only]    # continuous replay + strict scoring + artifacts (run 10 = ไม่ใส่ flag)
python verify_decoded.py --tag NEW_TAG                  # independent QA
python diagnose_decoded_conditional.py --tag NEW_TAG    # mechanics given observed start (not a score)
python diagnose_decoded_oracle.py --tag NEW_TAG         # oracle ceilings for j / SL-request variants (not a score)
python fetch_forward_orders.py --tag NEW_TAG [--watch --interval 600 --hours 24]   # public rows after the frozen snapshot (read-only)
python export_vantage_ticks.py --symbol XAUUSD --tag vantage_gold_fwd1 --start 2026-10-08T01:17:56+00:00 --end 2026-10-09T02:00:00+00:00 --query-shift-hours 3   # และ FixedVol20
python replay_forward.py --tag NEW_TAG                  # forward holdout (predictions hashed before forward rows are read)
python diagnose_forward_conditional.py --tag NEW_TAG    # conditional diagnostic on forward rows (not a score)
python vantage_probe_account.py --terminal PATH --expected-login N --tag NEW_TAG [--export-start ... --export-end ...]   # ข้อ 15: probe/export terminal เพิ่ม (read-only)
python analyze_goldplus_feed.py --tag NEW_TAG           # SL-crossing second: demo+offset vs XAUUSD+
python replay_decoded.py --tag NEW_TAG --gold-feed xauusd_plus   # run 15
python -m unittest test_decoded -q
```

ไฟล์หลัก: `strategy_scalping456_decoded.py` (engines), `decoded_schedule.py`, `decoded_common.py`; หลักฐาน: `data/decoded_evidence_20261009{,_r2,_r3,_r4,_r5}/`, `data/decoded_timing_20261009{,_r2}/`, `data/decoded_processing_20261009/`, `data/decoded_trial_20261009/`, `data/decoded_symbol_specs_20261009/`, `data/decoded_conditional_20261009{,_r2,_r3,_r4}/`; ผล replay: `data/decoded_replay_20261009*/` (predictions, all_source_results, extras, report.json พร้อม SHA-256); code snapshots ของแต่ละ run: `data/code_snapshots/`

ทุกค่าในรอบนี้ (run 1–11) ใช้ข้อมูลทั้ง ledger ในการ *สังเกต* กลไก จึงไม่มี unseen holdout ภายในชุด 35,462 แถว; holdout จริงชุดแรกคือ forward rows หลัง snapshot (§13); ค่า numeric ที่ตั้งเป็นพารามิเตอร์ (offset feed, ดีเลย์, latency/block, activation) เลือกจากแถวก่อน 21 ก.ย. เมื่อมี (SL-trial และ D=1.30 ไม่มี dev จึงเลือกจากช่วงเดียวกัน) แล้วรายงานช่วงหลังแยก


## 13. Forward holdout (run 12–14, 9 ต.ค. 2026): engine ที่ล็อกแล้ว vs order ที่เกิดหลัง snapshot

**ตั้งค่า (pre-registered ก่อนเปิดแถวทอง):** แผนอยู่ใน `EXPERIMENT_DECODED_PLAN.md` (Run 12 addendum); order ใหม่ดึงแบบ read-only ด้วย `fetch_forward_orders.py` ลง `data/forward_watch_20261009/` (snapshot 35,462 แถวไม่ถูกแตะ) = 527 แถวที่ปิดหลัง 2026-10-08T04:17:55 raw (ทอง 512, FixedVol20 15); tick demo ช่วงเดียวกันส่งออก read-only (`vantage_gold_fwd1`, `vantage_fixed_fwd1`); `replay_forward.py` รัน simulator ต่อเนื่องจาก tick แรก warm-up จน 2026-10-09T02:00 inferred ด้วยโค้ด/พารามิเตอร์ run 10/11 และ schedule เดิมไม่เพิ่มแถว (regime สุดท้ายเดิม: ทอง E4 D=1.30 / Fixed F2) เขียน `predictions_forward.jsonl` + hash ลง `pre_score_manifest.json` ก่อนอ่านแถว forward

| รายการ | ผล |
|---|---|
| exact / source | **134 / 527** (25.4%); missing 393; extra 738; predicted 872 |
| ทอง | 134 / 512 = **26.2%** (run 10 ช่วง E4 ที่ใช้เลือกพารามิเตอร์: 1,039 / 4,059 = 25.6%) |
| FixedVol20 | 0 / 15 (run 10 ช่วง F2: 2 / 221) |
| extras | ทอง 716 + Fixed 22; 278 รายการทองอยู่ในช่วง 01:17–10:55 inferred ที่ ledger ไม่มีเทรดเลย |

**อ่านผลอย่างตรงไปตรงมา:** (1) ไม่มีสัญญาณ overfit — อัตราบน forward เท่าที่เคยวัดในช่วง E4 (2) ไม่ผ่านเป้า: ยังห่างจาก 527/527 มาก และไม่ได้ชี้ว่าเพดาน 100% ทะลุได้ (3) extras ส่วนใหญ่มาจากเหตุการณ์ภายนอกแบบที่รายงานไว้แล้ว: ledger แสดง position ทอง 10 lot สองไม้ (เปิด 01:14:00 และ 02:18:14 raw) ค้างจนถูกปิด 13:55:03 / 13:55:11 raw (ไม้แรกคอมเมนต์ว่าง −1,088 pips น่าจะเป็นการปิดมือ) และไม่มีออเดอร์ใหม่ 12.7 ชม. ส่วน FixedVol20 ก็เริ่มเทรดอีกครั้งในเวลาใกล้กัน (13:54:25 raw) แปลว่าเป็นช่วงที่ EA/terminal หยุดทำงานทั้งคู่ แล้วพี่เปิดใหม่ — engine ที่ไม่รู้เรื่องนี้จึงเทรดต่อ หลัง resume จำนวนไม้ต่อชั่วโมงใกล้เคียง ledger (เช่น 36/36, 54/57, 66/65, 46/50 ไม้ต่อชั่วโมง) (4) Fixed ยัง sync หลุดตั้งแต่ basket แรก (ลำดับ basket ที่ทำนายหน้าตาเหมือนจริงแต่เวลา/ราคาเข้าเลื่อนทีละวินาที/เซนต์)

**Conditional diagnostic บนแถว forward** (`data/decoded_forward_conditional_20261009/`, ไม่ใช่คะแนน replay, ไม่ปรับโมเดล): ทอง 490 trials หลัง resume — ฐาน (j=0) ตรงทุกฟิลด์ 209 (42.7%; E4 ใน dev/later 40.7%), oracle j ทำให้ entry ตรง 446 (91.0%; E4 92.7%), oracle j + trailing 383 (78.2%; E4 81.1%); Fixed 8 baskets: first-leg ตรง 2, basket ตรงทั้งก้อน 2, order ตรง 4/14 — กลไกที่ล็อกไว้ทำงานบนข้อมูลใหม่เท่าเดิม ส่วนที่ขาดคือตัวแปรซ่อน

forward watcher (`fetch_forward_orders.py --watch`) ยังเก็บแถวใหม่ต่อได้ — ชุดใหม่ที่ไม่ได้ใช้ตัดสินใจอะไรเลยเป็น holdout ครั้งถัดไปได้เสมอ (ห้ามใช้ชุด 527 แถวนี้จูนโมเดลแล้วเรียกว่า unseen อีก)

## 14. Oracle ceiling: ตัวแปรซ่อนแต่ละตัวทำให้เสียเท่าไร (run 13, conditional)

`diagnose_decoded_oracle.py` เริ่มจาก close จริงของ order ก่อนหน้า (ตัวอย่างสุ่ม seed เดียวกับ diagnostic เดิม) แล้วให้ oracle เลือกค่าตัวแปรซ่อนจากชุดที่ประกาศล่วงหน้า (j ∈ {0..4}; ชุด trailing/SL-request 8 แบบ) นับว่า "อธิบายได้" เมื่อ (วินาทีเปิด, ด้าน, ราคาเปิด, วินาทีปิด, ราคาปิด) ตรงทั้งหมด **ใช้ ledger เลือกค่า จึงเป็นเพดานเชิงโครงสร้าง ไม่ใช่คะแนน replay**

| ขั้น | E3 dev (D=1.00, n=1,487) | E4 (D=1.30, n=1,464) |
|---|---:|---:|
| โมเดลล็อก (j คงที่ตาม era) | 453 (30.5%) | 596 (40.7%) |
| + oracle j: entry ตรง | 1,131 (76.1%) | 1,357 (92.7%) |
| + oracle j: ตรงทุกฟิลด์ด้วย trailing ที่ล็อก | 675 (45.4%) | 1,041 (71.1%) |
| + oracle trailing/SL-request | 822 (55.3%) | 1,187 (81.1%) |
| ยังอธิบายไม่ได้แม้ใช้ oracle ทั้งหมด | 665 (44.7%) | 277 (18.9%) |

ข้อสรุป: (ก) tick อ้างอิงที่ EA อ่าน (j) คือตัวแปรซ่อนที่ทำให้เสียมากสุด — E4 +30 จุด, E3 +15 จุด; (ข) คำขอ SL/trailing ที่สุ่มทำให้เสียอีก ~10 จุดในทั้งสอง era; (ค) ส่วนที่เหลือ (19% E4, 45% E3) คือ jitter ของ feed ระดับ ms ที่ `XAUUSD+` ต้นทางต่างจาก demo และกรณีที่ยังไม่เข้าใจ — ใน E3 แถวที่ราคาตรงแต่วินาทีเปิดต่าง 175 แถว และวินาทีตรงแต่ราคาต่าง 118 แถว; (ง) เมื่อเดินแบบต่อเนื่อง ความเสียหายซ้ำซ้อนอีก: โมเดลล็อก 40.7% แบบ conditional ในช่วง E4 เหลือ 25.6% ใน continuous replay (sync หลุดหลังไม้ที่พลาด) — นี่คือข้อมูลเชิงปริมาณว่าข้อมูลต้นทางประเภทใดมีค่ามากสุด (เวลา ms ของ EA อ่าน quote/ส่ง order/modify และ tick `XAUUSD+` ต้นทาง) ต่อให้ได้ถูกครบ ผลนี้ไม่ได้รับประกัน 100% เพราะยังเหลือส่วนที่ oracle ชุดนี้อธิบายไม่ได้

## 15. `XAUUSD+` จริงจากบัญชี Raw ECN demo (run 15, 9 ต.ค. 2026)

พี่เพิ่มบัญชี demo ชนิด RAW ECN (`profiles/demo/demo-vantage-26257644`, server `VantageMarkets-Demo` เดิม, นาฬิกา tick − UTC จริง = +3.00 ชม. เท่าเดิม) อลิซ attach แบบอ่านอย่างเดียวด้วย `vantage_probe_account.py` (ไม่ launch/ไม่ส่ง login/ไม่เลือก symbol/ไม่ส่ง order; ยอมเฉพาะ demo + login ที่ระบุ; `data/vantage_probe_raw_ecn_probe_20261009/`) ผลที่เป็นข้อเท็จจริง:

- บัญชีชนิดนี้ **มี `XAUUSD+`** (path `Gold+\XAUUSD+`, spread 10 points, `trade_stops_level` 20 ตรงกับที่ถอดได้) ในขณะที่บัญชี demo เดิมไม่มี — จึงเป็นหลักฐานโดยตรงว่าสัญลักษณ์ใน ledger มาจากบัญชีชนิดคิดคอมมิชชั่น (ที่พี่เลือกชื่อ RAW ECN) ส่วนที่ยังไม่รู้คือบัญชีต้นทางจริงของ Scalping456 ใช้ชนิดนี้ที่ server นี้หรือไม่ — ยืนยันตัวตนบัญชีต้นทางไม่ได้
- export `XAUUSD+` 2026-08-18T21:00 → 2026-10-09T02:00 (`data/proxy_ticks_vantage_goldplus_full/`, 53 วัน, 23,602,010 ticks, invalid 0, hash ต่อวัน): history ย้อนหลังครบทั้งช่วง

**Feed identity (analysis เทียบกับ demo `XAUUSD` ทั้ง 52 วัน):** `XAUUSD+` 23.15 ล้าน tick vs demo 23.16 ล้าน tick; timestamp ตรงกัน 98.7% (22,858,623 tick) และในส่วนที่ตรงกัน **bid +0.06 / ask −0.05 ตรง 99.987%** แปลว่า offset ที่ถอดจาก stop-out มาตลอดเป็นส่วนต่างจริงของ feed ไม่ใช่ค่าประมาณ; tick อีก ~1.3% มี timestamp ฝั่งเดียว

**ทดสอบว่าใช้ feed จริงแล้วดีขึ้นไหม (ผลลบ):**

| ทดสอบ | demo + offset | `XAUUSD+` ตรง |
|---|---:|---:|
| จุดตัด SL ตรงวินาทีปิด (stop-out −100 pips, 7,879 แถว) dev / later | 88.3% / 80.9% | **88.3% / 80.9%** (เท่ากันทุกแถว) |
| continuous replay ทั้ง 35,462 แถว (run 10 vs run 15) | exact 6,213 / missing 29,249 / extra 51,418 | exact **6,207** / missing 29,255 / extra 51,375 |
| ทอง E4 (เทียบ run 10) | 1,039 / 4,059 | 1,036 / 4,059 |

อ่านผล: feed ต้นทาง ≈ feed ที่ใช้อยู่แล้ว จึงไม่ใช่คอขวด; tick ส่วนต่าง 1.3% ไม่ช่วยให้ตรงเพิ่ม (−6 exact ซึ่งอยู่ในระดับสุ่ม) ความไม่ตรงของวินาทีปิด 11–20% จึงไม่ได้มาจากค่าราคา; shift เวลาปิดคงที่ L ไม่ช่วยด้วย (best L=+25 ms ได้ 88.6% / 81.3%, L=±100 ms แย่ลง 4–8 จุด) ในกลุ่มที่ไม่ตรง ตัดสินจากรูปแบบ: ตรง ~90% เมื่อ tick ตัดตกที่ 100–799 ms ของวินาที แต่ 74% เมื่อ 0–99 ms และ 68% เมื่อ 900–999 ms และ close-ช้ากว่า-tick ≥ 1 วินาที ราว 10% ทุกช่วง ซึ่งเข้ากับความสุ่มของการประมวลผล stop ที่ server/ledger มากกว่าความต่างของ feed (เป็นข้อสังเกต ไม่ได้ทดลองเพิ่ม)

ผลต่อเป้า: ข้อมูลตัวนี้ตัดสมมติฐาน "ถ้าได้ `XAUUSD+` แล้วจะแม่นขึ้น" ออกไปเรียบร้อย ส่วนที่ขาดยังเป็น tick ที่ EA ต้นทางอ่านตอนวาง pending, คำขอ SL/trailing, ช่วง EA หยุดและการปิดมือ (§9, §14) ซึ่งไม่อยู่ใน feed ใดๆ ที่อ่านได้

## 16. Open positions ของหน้าสาธารณะ และการหยุด sync (9 ต.ค. 2026)

**แก้ข้อมูลที่เคยเขียนผิด:** `PROFILE_SNAPSHOT.md` สรุปตาราง open positions แค่ symbol/side/volume/floating P/L แต่ข้อมูล hydration ของหน้าเว็บ (`metadata_extract_v2.json`) มีต่อ position ครบกว่านั้น: `ticket, open_price, current_price, sl, tp, comment, open_time, profit, pips, swap` และมี `updated_at` ของการ sync ข้อมูลทั้งหน้า

**เครื่องมือ:** `poll_open_positions.py` (+`test_poll_open_positions.py` 4 tests) GET หน้า `/p/<profile>` (robots.txt อนุญาต `/p/`) บันทึกเฉพาะเมื่อ `updated_at` หรือฟิลด์ใด ๆ เปลี่ยน + heartbeat ทุก 10 นาที; ช้า (180 วินาที) ขณะหน้า stale และเร็ว (15 วินาที) หลัง sync ล่าสุดไม่เกิน 3 นาที; ปฏิเสธการตั้งถี่กว่า 10/60 วินาที; ไม่ล็อกอิน/ไม่ส่งฟอร์ม; ผลลง `data/open_positions_watch_20261009/` (รัน 24 ชม.)

**ข้อค้นพบตอนทดสอบ (ข้อเท็จจริง):**
- ณ 07:43–07:46 UTC หน้ายังแสดง `updated_at = 2026-10-09T01:54:47Z` ไม่เปลี่ยนเลยในการ poll 5 ครั้ง (ห่างกัน 10 วินาที) — ข้อมูลหน้าเว็บ **หยุดอัปเดตมา ~6 ชม.**; ledger ปิดล่าสุด 04:53:31 raw = 01:53:31 UTC ตรงกัน และ forward watcher ก็ไม่ได้แถวใหม่เลยตั้งแต่ pass แรก
- open positions ที่ค้างในหน้าคือ FixedVol20 buy 5 ไม้ (0.1/0.2/0.3/0.5/0.8, คอมเมนต์ `GoldTrap`, TP เดียวกัน 8287.849) ราคา `current_price` 8251.255 ใกล้ demo ณ 01:54:47 (bid 8251.567) แต่ตอนนี้ demo FixedVol20 อยู่ที่ ~8333 ซึ่งข้าม TP ไปนานแล้ว — ถ้าบัญชีต้นทางยังเชื่อมต่อ TP ที่ฝั่ง server จะปิด basket ไปแล้ว จึงสรุปได้ว่า **การ sync ข้อมูลของ ThaiFXBook หยุด** (ไม่ใช่แค่ EA หยุด) ซึ่งอลิซควบคุมไม่ได้
- ยังไม่มีทางรู้ว่า sync จะกลับมาเมื่อใด/หรือไม่; ถ้ากลับมา ledger จะมีแถวช่วง 01:54–ตอนนั้นให้เป็น holdout ชุดใหม่ (รวม Fixed 5 ไม้นี้) และ watcher นี้จะเก็บ cadence ของ `updated_at` กับ `sl` ของ position ที่เปิดอยู่

**ข้อจำกัดของแนวทางนี้:** ต่อให้ sync กลับมา ความละเอียดอยู่ที่ cadence ของ `updated_at` (ยังไม่ทราบ) และ position ทองมักเปิดไม่กี่วินาที จึงไม่น่าเห็นลำดับ SL trailing ครบ ส่วนที่น่าจะได้คือ (ก) cadence การ sync, (ข) ว่าช่วงที่ EA ค้างมี position ไม่มี SL จริงตอนไหน (เช่น 01:14–13:55 raw วันที่ 8 ต.ค. มี `sl: 0`, คอมเมนต์ `PipScalperEA V2 BUY STOP/SELL STOP`)
