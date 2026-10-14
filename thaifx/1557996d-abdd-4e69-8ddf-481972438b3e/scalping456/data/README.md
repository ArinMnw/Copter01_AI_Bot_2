# Data files

## Raw closed orders

- `orders_35462.csv` — ตารางหลักสำหรับ Excel/pandas
- `orders_35462.jsonl` — raw records แบบหนึ่ง JSON object ต่อบรรทัด
- `orders_35462_normalized.csv` — ชุดเดียวกันที่เพิ่มเวลา actual UTC/BKK/IUX หลังแก้ Vantage server offset
- `manifest.json` — provenance และผลตรวจจำนวน

ตรวจแล้ว:

- 1,774 pages
- 35,462 rows
- 35,462 unique `id`
- 35,462 unique `ticket`
- หน้า 1–1,773 มี 20 rows; หน้าสุดท้ายมี 2 rows

## Field dictionary

| Field | ความหมาย |
|---|---|
| `id` | UUID ภายใน ThaiFXBook |
| `ticket` | MT5 order/deal ticket ที่เว็บแสดง |
| `symbol` | XAUUSD+ หรือ FixedVol20 |
| `trade_type` | buy/sell |
| `volume` | lot |
| `profit` | gross P/L ของ trade ก่อน commission |
| `open_time`, `close_time` | Raw ISOติดป้าย `+00:00`; price/live-clock evidenceสนับสนุนserver UTC+3 จึงใช้raw−3hเป็นinferredUTC แยกderivedcolumnsโดยไม่แก้ต้นฉบับ ยังไม่ใช่officialserializer/source-account confirmation |
| `open_price`, `close_price` | ราคาเข้า/ออก |
| `pips` | pips ตามนิยามของเว็บ/symbol |
| `sl`, `tp` | ค่า history field; ค่า 0 ไม่ได้แปลว่า order ไม่ได้ปิดด้วย SL/TP ให้ดู `comment` ร่วมด้วย |
| `comment` | เช่น `[sl 4103.63]`, `[tp 8375.923]`, ticket linkage หรือว่าง |

## Derived files

- `analysis_metrics.json` — metrics หลักทั้งหมด
- `daily_stats.csv` — รายวัน แยก symbol ตามเวลา BKK
- `hourly_stats_bkk.csv` — hour-of-day ตามเวลา BKK
- `volume_stats.csv` — distribution ของ lot และผลงาน
- `xau_open_second_stats.csv` — ตรวจว่า entry ผูกกับวินาทีใดหรือไม่

## Time normalization

ตรวจราคาเข้าเทียบ independent XAUUSD M1 จำนวน 7,577 ตัวอย่างจากทุกวัน:

- raw ไม่แก้เวลา: ราคาอยู่ใน high-low ของนาทีเดียวกัน 4.33%
- raw ลบ 3 ชั่วโมง: ราคาอยู่ใน high-low ของนาทีเดียวกัน 95.26%

ผลเทียบราคาสนับสนุนสมมติฐาน source server UTC+3 (ยังไม่ใช่การยืนยันอย่างเป็นทางการจาก broker) ไฟล์ normalized จึงใช้:

```text
actual_utc = raw - 3h
bkk        = raw + 4h
iux_chart  = raw + 3h
web_display_derived = raw + 7h
```

`web_open_display_derived` / `web_close_display_derived` เป็นเวลาเว็บที่คำนวณจาก raw ไม่ใช่ค่าที่ capture จาก UI แยกครบทุกแถว ห้ามถือเป็น Bangkok จริงโดยอัตโนมัติ ส่วน `open_iux_chart` / `close_iux_chart` เป็น timestamp +06:00 ของ instant เดียวกับ inferred UTC ไม่ใช่เลขนาฬิกาที่บวกแล้วแต่ยังติด +00:00

## Audit และ replay เพิ่มเติม

ล่าสุดหลังตั้งค่า Vantage (8 ตุลาคม2026):

- `vantage_initial_20261008/`, `vantage_tick_clock_20261008/` — specs/raw M1/tick witnesses, offset grid และ live UTC anchors
- `vantage_raw_ticks_vantage_gold_shift3/`, `vantage_raw_ticks_vantage_fixed_shift3/` — structured raw ticks ทุก fields ไม่ normalize ทับ
- `proxy_ticks_vantage_gold_shift3/`, `proxy_ticks_vantage_fixed_shift3/` — normalized inferred UTC (raw-3h), bid/ask พร้อม hashes/coverage/gaps รวม27,473,009 ticks; source feed identity ยังไม่ยืนยัน
- `vantage_full_quotes_20261008/` — 70,924 events ของทุก35,462 orders; close-by reciprocal prices ไม่ถือเป็น market witnesses แต่ rows ไม่ถูกตัด
- `vantage_gap_audit_20261008/` — gaps เทียบ M1 และ raw responses จากการดึงซ้ำ; ไม่เติม/เขียนทับ cache เดิม
- `vantage_prespecified_benchmarks_20261008/` — 4 continuous baseline predictions รวม warm-up, ไม่มี source resets/parameter fitting ใหม่
- `vantage_prespecified_source_window_20261008/` — strict all-source scoring ใน ledger window คง warm-up state; excludes เฉพาะ warm-up trades ที่ปิดก่อน source เริ่ม ไม่ตัด source outliers/FixedVol20 ออกจาก denominator
- `vantage_broker_bars_20261008/` — actual broker OHLC M1/M5/M15/M30/H1 ทั้งทองและFixedVol20 raw/inferred/hashes; final incomplete barsไม่ถูกconsume
- `vantage_candle_grid_replay_20261008/`, `_r2/` — 38continuous candidates+2portfolios พร้อมfull-sourceผลทุกrow/extras,configs/phase scores/hash QA; ทั้งหมดไม่ผ่านgoal100%
- `vantage_candle_grid_entry_diagnostics_20261008/` — entry-onlyทุกsource rowและทุกmodel เป็นdiagnosticไม่ใช่full-order success
- `vantage_path_constraints_20261008/` — allsourcequote-pathobservations35,462unique tickets, MFE/MAE/earlybarriers/finalTPwitness/gaps/lotsegmentsพร้อมhashและQA ไม่ใช่predictions
- `public_schema_20261008/` — publicHTML+27observedfirst-partyJS/actionpage1/hashmanifest และmetadataextractv1/v2; currentopencomments/equity81samplesเก็บแยก ไม่mergeกับclosedsnapshot
- `vantage_trial28_replay_20261008/` — 2distance2.8continuoustrialbenchmarks/allsource results/extras/phase scores/QA; exact0ทั้งคู่ ไม่มีtrial-specificvalidationrows
- `vantage_pending_replay_20261008/` — 32ideal-paperpending-stopmodels/160JSONLartifacts; allsource results/extrasและentry-onlydiagnostics,hashes/configs/phases; bestexact29 ยังไม่ผ่านgoal
- `vantage_pending_guarded_replay_20261008/` — 32same-parametercontrolsเพิ่มcorrect-sideSLproposalguard/160JSONLartifacts; best29/missing35,433/extra91,768; guardไม่ยืนยันoriginalbrokerexecution
- `code_snapshots/` — hash-verifiedresearchcodeก่อนpending/ก่อนguard รักษาoldexperimentprovenance; pendingverifierใช้explicit`--allow-archived-code`เมื่อตรวจoldreportกับrevisionที่ต่างจากปัจจุบัน ไม่ลดhashchecks
- `lot_scope_20261008/` — all_source_lot_states35,462unique tickets/pastclosedgross/same-second ambiguity/strictactive/all-symbolvsXAU/volume runs/component membership +report/hash/populationQA/independentsequentialQA; ทอง0.01ช่วงแรก7,312rowsเป็นnarrowcomponentเท่านั้น ไม่ใช่recoveredbalance/equity/auto-lotหรือpredictions
- `first001_replay_20261008/` — 4frozenpendingfixed/OCO/lot.01controls/25JSONLartifactsรวมcomponent7312/full-original35462/entry-only/extras/inventory พร้อมhashes/QA; bestcomponentexact9ยังไม่ผ่าน
- `first001_diagnostics_20261008/` — 7,312entryquote/predecessor/conditionalnominalcross/archivedexitobservations,side-distributions/hash/population/quote/bruteforceQA; ไม่ใช่source-seededpredictionsและไม่ใช้witnesscountsแทนgoalmetrics

แผนเลือก parameters/ข้อจำกัด holdout ดู `../VANTAGE_EXPERIMENT_PLAN.md`; สรุปfeedดู `../VANTAGE_FEED_REPORT.md` / ผลcomponentล่าสุดดู `../FIRST001_RESULTS.md` การอ่าน feeds ใหม่ไม่ทำให้ original EA settings/manual actions ถูกยืนยันโดยอัตโนมัติ

- `order_audit_35462.csv` — ทุก ticket พร้อม predecessor แบบรวม special exits, latest completed predecessor, active positions และสถานะยังไม่ยืนยัน clone
- `ledger_audit_report.json` — reconciliation ดิบ/JSONL/normalized, SHA-256, จำนวนทุกกลุ่มและข้อยกเว้น
- `proxy_ticks_iux_shift1/` — NPZ bid/ask/time_msc และ JSON provenance รายวัน; IUX proxy ไม่ใช่ source feed มี empirical query offset +1h แล้ว normalize กลับก่อน replay
- `causal_replay_*.json` / `.csv` — continuous replay scores และผลแต่ละ source ticket/candidate นับ missing และ extra
- `causal_predictions_*.csv` — signals จาก strategy ก่อน scorer อ่าน source ledger

การผ่าน reconciliation หมายถึงข้อมูลถูกเก็บครบและค่าต้นทางไม่เปลี่ยน ไม่ได้หมายถึง strategy จำลองตรง 100% และ legacy state-machine/exit-fit reports เป็น conditional diagnostics ไม่ใช่ continuous replay

## Reproduce

```powershell
python download_orders.py --workers 8
python analyze_orders.py
```

Downloader ใช้ public Next.js server action ที่หน้าเว็บเรียกเมื่อกด pagination ไม่มีข้อมูลส่วนตัวหรือ session login

หน้าเว็บเป็นข้อมูล live และจำนวนอาจเพิ่มขึ้นภายหลัง การ rerun โดยไม่ปรับ `EXPECTED_COUNT` จะตั้งใจ fail เพื่อป้องกันการปน snapshot คนละเวลา

ล่าสุด 9 ตุลาคม 2026 (decoded mechanics):

- `decoded_evidence_20261009/`, `_r2/`, `_r3/`, `_r5/` (+`_r4/`) — ตารางหลักฐาน feed calibration (dev/later), stop-level crossing, placement distance/era, trailing edge/grid, Fixed mechanics; r2 เพิ่มแกน activation strict, r3 เพิ่ม TP rounding/first-leg regime/overlap
- `decoded_timing_20261009/` — coverage ของดีเลย์การอ่าน quote (dev/later)
- `decoded_processing_20261009/` — ตระกูลโมเดลเวลาประมวลผล EA (108 แบบ, dev เท่านั้น) ไม่ดีกว่า busy/effect เดิม
- `decoded_conditional_20261009/`, `_r2/`, `_r3/`, `_r4/` — mechanics-given-observed-start (ไม่ใช่คะแนน replay; r4 = engine สุดท้าย)
- `decoded_trial_20261009/` — หลักฐาน SL-trial engine ของ FixedVol20 (activation grid, entry distance)
- `decoded_symbol_specs_20261009/` — `symbol_info` read-only ของ XAUUSD/XAUUSD.crp/FixedVol20 (trade_stops_level 20 และ 2800 points)
- `decoded_timing_20261009_r2/` — reference tick j vs ดีเลย์คงที่
- `decoded_replay_20261009/`, `decoded_replay_20261009_r2_flat_only/`, `decoded_replay_20261009_r3_eras/`, `_r4_fixed_trial/`, `_r5_fixed_sessions/`, `_r6_flatten/`, `_r7_stops_level/`, `_r8_next_tick/`, `_r9_confirm/`, `_r10_trail_step/` — continuous replay ทั้ง 35,462 rows: predictions, all_source_results, extras, report.json + SHA-256 (QA: `verify_decoded.py`)
- `code_snapshots/*_e69b63b6be04|5b51ce3ad647|2f3666519d6d|5647ccff6485` — โค้ด/แผนของ run 1
- `forward_probe_20261009/`, `forward_watch_20261009/` — order สาธารณะที่ปิดหลัง snapshot (read-only, `first_seen_utc` = เวลา poll; manifest.json เขียนเมื่อ watcher จบ); snapshot `orders_35462.*` ไม่ถูกแก้
- `vantage_raw_ticks_vantage_{gold,fixed}_fwd1/`, `proxy_ticks_vantage_{gold,fixed}_fwd1/` — tick demo 2026-10-08T01:17:56→2026-10-09T02:00 inferred UTC (raw epoch + normalized − 3 h + sha256)
- `decoded_forward_20261009/` — forward holdout run 12 (predictions_forward.jsonl, pre_score_manifest.json เขียนก่อนอ่านแถว forward, forward_results.jsonl, extras.jsonl, report.json)
- `decoded_oracle_20261009/` — oracle ceiling (conditional, ไม่ใช่คะแนน replay)
- `decoded_forward_conditional_20261009/` — conditional diagnostic บนแถว forward
- `decoded_replay_20261009_r11_offset_general/` — ยืนยัน place_offset ทั่วไปไม่เปลี่ยนผล (6,213)
- `vantage_probe_raw_ecn_probe_20261009/`, `vantage_probe_raw_ecn_day_test/`, `vantage_probe_vantage_goldplus_full/` — probe read-only ของ terminal RAW ECN demo (`demo-vantage-26257644`): รายชื่อสัญลักษณ์ XAU*, spec, clock probe, hash ของ export
- `vantage_raw_ticks_vantage_goldplus_full/`, `proxy_ticks_vantage_goldplus_full/` — tick `XAUUSD+` 2026-08-18T21:00→2026-10-09T02:00 inferred UTC (raw + normalized − 3 h + sha256 ต่อวัน; `*_raw_ecn_day_test` เป็นวันเดียว 2026-09-01)
- `decoded_goldplus_feed_20261009/` — จุดตัด SL ตรงวินาทีปิด: demo+offset vs `XAUUSD+`
- `decoded_replay_20261009_r15_xauusd_plus/` — continuous replay ทั้ง 35,462 แถวด้วย `XAUUSD+` ตรง (exact 6,207)
- `open_positions_watch_20261009/` — บันทึก open positions + `updated_at` ของหน้าสาธารณะ (เฉพาะเมื่อเปลี่ยน + heartbeat; manifest.json เขียนเมื่อรันจบปกติ); ณ 07:46 UTC หน้า stale ตั้งแต่ 01:54:47Z
