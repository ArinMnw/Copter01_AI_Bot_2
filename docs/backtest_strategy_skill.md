# Backtest Strategy Skill / Checklist

เอกสารนี้เป็น runbook สำหรับทำงาน goal: ปรับ backtest/compare ให้จำลอง auto trade ใกล้ bot จริงขึ้น โดยให้ทำ **backtest ราย strategy ให้ครบก่อน** แล้วค่อยกลับมา compare auto trade รวมทั้งระบบ

ให้อัปเดตไฟล์นี้ทุกครั้งที่ทำ step เสร็จ เพื่อให้ model ถัดไปทำต่อได้ทันทีถ้า context/token หมด

## กติกาหลัก

- ยึด `AGENTS.md` เป็นหลักเสมอ
- เวลา input ของพี่เป็น Bangkok UTC+7
- หลังแก้ Markdown/ข้อความไทย/emoji ให้รัน `python check_mojibake.py`
- หลังแก้ Python ให้รัน `python -m py_compile <ไฟล์>` และถ้าทำได้ให้รัน `python verify_repo.py`
- อย่าให้ diagnostic mode ทับ baseline report: ถ้าเพิ่ม flag diagnostic ต้องแยก suffix report อัตโนมัติ
- ทำราย strategy ให้ครบก่อน แล้วค่อยกลับมา compare auto trade รวม

## Definition Of Done ต่อ Strategy

ถือว่า strategy backtest "เสร็จ" เมื่อครบทุกข้อ:

- [ ] มี replay/timewindow script หรือ central replay path ที่รันเฉพาะ strategy นั้นได้
- [ ] ใช้ config จริงจาก `bot_state.json` / `config.py` เท่าที่ bot runtime ใช้จริง
- [ ] จำลอง lifecycle ที่ strategy นั้นเกี่ยวข้อง: create, pending/fill, cancel, close, trail, guard, scale out, PD/trend/RSI recheck ตาม config
- [ ] มี compare กับ MT5 history ได้ หรือมีเหตุผลชัดเจนว่าทำไมยัง compare ไม่ได้
- [ ] มี CSV/XLSX/report แยก folder ตาม strategy
- [ ] มี command ตัวอย่างใน `commands_and_tips.md`
- [ ] รัน verification ผ่านหลังแก้
- [ ] ระบุ known gap ที่ยังเหลือ พร้อมไฟล์/command/evidence

## สถานะรวม

- [x] สร้าง central compare/report พื้นฐานใน `backtest_auto_trade.py`
- [x] แยก output folder ตาม strategy ใน `excel_reports/backtest_compare/s<sid>/`
- [x] เพิ่ม progress elapsed log ระหว่างรัน เช่น `[00:10] Running S14 replay on M15...`
- [x] เพิ่ม CSV/XLSX compare report และ `*_summary.csv`
- [x] เพิ่ม scale-out columns `live_scale_out_1_pnl` ถึง `live_scale_out_4_pnl` และฝั่ง BT
- [x] เพิ่ม SL Guard diagnostics จาก log: `live_sl_guard_*`, `bt_sl_guard_*`
- [x] เพิ่ม system-level SL Guard Group overlay ข้าม strategy เมื่อรันหลาย strategy พร้อมกัน
- [x] เพิ่ม system-level Opposite Order overlay ข้าม strategy เมื่อรันหลาย strategy พร้อมกัน
- [x] เพิ่ม system-level Limit Guard overlay ข้าม strategy เมื่อรันหลาย strategy พร้อมกัน
- [x] แยก `PD_FAIL` pending cancel ออกจาก `PD_FILL_FAIL` หลัง fill เพื่อให้ `--exclude-cancelled` ยังนับ order จริงที่โดน PD ปิด
- [x] เพิ่ม optional `--hybrid-live-guard-context` และ suffix `_hybrid_guard`
- [x] เพิ่ม S14 normalized family diagnostics และ optional `--prefer-same-s14-family` พร้อม suffix `_s14_family`
- [x] อัปเดต `commands_and_tips.md` สำหรับ command/report/diagnostic ล่าสุด
- [ ] ทำ backtest ราย strategy ให้ครบทุกท่าก่อนกลับไป compare auto trade รวม

## Strategy Checklist

### S1

- [x] สร้าง/รวม replay ราย strategy baseline
- [x] จำลอง zone/swing mode, forward confirm, pending cancel, fill close ตาม runtime baseline
- [x] เทียบ MT5 history รายช่วง baseline
- [x] จด command ใน `commands_and_tips.md`

S1 runtime coverage audit (updated 2026-06-19):

| Feature | Runtime for S1 | Replay status | Note |
|---|---|---|---|
| S1 detect / zone filter | apply | apply | Replay uses range-based MT5 fetch, calls shared `strategy1.strategy_1()`, and carries `s1_zone_meta`. |
| Pending limit lifecycle | apply | partial | Replay models pending fill, `cancel_bars`, fixed SL/TP with bar high/low. |
| S1 forward confirm | apply | apply | Replay cancels pending or closes filled position if no S2/S3 confirm within 5 bars. |
| S1 zone/swing post-check | apply | apply | Replay models zone cancel/loss-exit and swing confirm/cancel/exit according to `S1_ZONE_MODE`. |
| PD Fibo Plus | skip_s1 | skip_s1 | Runtime currently skips S1 in pending/fill PD Fibo Plus. |
| Limit Trend Recheck / Fill Trend Recheck | skip_s1 | skip_s1 | Runtime currently skips S1 approach/fill trend recheck. |
| RSI Fill Recheck | skip_s1 | skip_s1 | Runtime currently skips S1 RSI fill recheck. |
| Trail SL / Opposite / Limit Guard | apply if enabled | partial | Single S1 now routes through unified S1-S5/S8 replay, which applies shared lifecycle baseline; fine-grained live state can still drift. |

Evidence ล่าสุด:

```bash
python backtest_auto_trade.py --start "2026-05-28 08:00" --end "2026-06-08 10:00" --since "2026-05-28 00:00" --tf M15 --strategies 1 --exclude-cancelled --symbol XAUUSD.iux --compare-mt5-history --compare-csv --compare-xlsx --match-minutes 180 --match-entry-points 5
```

- S1 replay raw events: 366; kept M15 filled events in window: 37.
- Backtest P&L: `-98.49`.
- MT5 live rows loaded: 435; after M15 filter: 28.
- Matched: 17; mismatches: 17; live-only: 11; backtest-only: 20.
- Matched P&L live `+128.53` | BT `-23.79` | diff `+152.32`.
- Largest mismatch groups: `PNL_DIFF_SAME_BUCKET BUY +115.03`, `CLOSE_BUCKET_DIFF SELL +29.10`, `LOOSE_MATCH_SL_GUARD SELL +8.19`.
- Compare summary no longer contains generic S14-family UNKNOWN buckets after regenerating the report.
- Report: `excel_reports/backtest_compare/s1/compare_s1_M15_20260528_0800_20260608_1000.csv`.

Known remaining S1 gaps:

- S1 replay baseline now includes forward confirm, zone/swing post-check, and shared lifecycle baseline through the unified runner, but P&L parity still depends on exact trail/guard/live-state timing.
- PD/Trend/RSI recheck are runtime skips for S1, so S1 parity should focus on S1-specific confirm/zone checks plus shared trail/guard/opposite lifecycle.
- Current `S1_ZONE_MODE` is `swing` in both `config.py` and `bot_state.json`; replay therefore produces many `S1_SWING_EXIT` closes. Live history in this window still contains PD / Fill Trend / SL Guard closes from older runtime behavior, so compare after current S1 skip-list and swing-mode behavior should be cleaner.
- Trail SL and SL Guard Group context are still visible live mismatch sources, but the largest current drift is S1 swing-exit timing versus historical live close reasons.

### S2

- [x] สร้าง/รวม replay ราย strategy baseline
- [ ] รองรับ FVG normal/parallel, confirm lookback, cancel bars, limit TP/SL break skip pattern 1 ให้ครบ
- [x] เทียบ MT5 history รายช่วง baseline
- [x] จด command ใน `commands_and_tips.md`

S2 runtime coverage audit (updated 2026-06-18):

Checklist status note:

- `strategy2.strategy_2()`, normal confirm lookback, swing fallback, pending fill, `cancel_bars`, S2-only multi-TF `FVG_PARALLEL` context, composite TF comment/member filtering, optimized sweep scan block, RSI Fill Recheck, Limit Guard, Opposite Order, Trail SL, and SL Guard baseline are implemented.
- The remaining unchecked checklist item is still valid because exact cross-TF FVG cancel/re-place timing is not complete yet; Limit TP/SL Break Cancel is now a ready/off layer because current config has `LIMIT_BREAK_CANCEL=False`.

| Feature | Runtime for S2 | Replay status | Note |
|---|---|---|---|
| S2 FVG detect | apply | apply | Replay uses range-based MT5 fetch and calls shared `strategy2.strategy_2()`. |
| S2 normal confirm lookback | apply | apply | Replay uses scanner `_find_recent_signal_confirmation()` plus swing fallback. |
| S2 FVG parallel intersection | apply | partial | Unified S2 replay can include context TFs, replace overlapping pending gaps with intersection entries, and report rows whose composite `parallel_tfs` contains the requested TF. |
| Pending limit lifecycle | apply | partial | Replay models pending fill, `cancel_bars`, fixed SL/TP with bar high/low. |
| PD Fibo Plus | skip_s2 | skip_s2 | Runtime currently skips S2 in pending/fill PD Fibo Plus. |
| Limit Trend / Fill Trend Recheck | skip_s2 | skip_s2 | Runtime currently skips S2 approach/fill trend recheck. |
| Trend Filter scan block | apply if enabled | partial | Unified replay now calls scanner `trend_allows_signal()` with current-TF historical HHLL when enabled; higher-TF/exported scanner state can still drift. |
| Sweep Filter scan block | apply | partial | Unified S2 replay uses optimized historical sweep detection to block counter-sweep scan signals. |
| RSI Fill Recheck | apply if enabled | off/ready | Config is currently OFF in tested state; unified replay calls the shared fill RSI recheck layer when enabled. |
| Limit TP/SL Break Cancel | apply if enabled | off/ready | Config is currently OFF in tested state; replay now cancels pending orders on confirmed TP/SL break and skips S2 engulf pattern 1 when enabled. |
| Trail SL / Opposite / Limit Guard | apply if enabled | partial | Replay applies Limit Guard, Opposite Order, engulf Trail SL baseline, SL Guard/Group retry/unblock baseline, and counts only losing SL/loss-guard closes for SL Guard like runtime; shared order-state and focus/reversal nuances can still drift. |

Evidence ล่าสุด:

```bash
python backtest_auto_trade.py --start "2026-05-28 08:00" --end "2026-06-08 10:00" --since "2026-05-28 00:00" --tf M15 --strategies 2 --exclude-cancelled --symbol XAUUSD.iux --compare-mt5-history --compare-csv --compare-xlsx --match-minutes 180 --match-entry-points 5
```

- S2 multi-TF replay raw events: 1097; kept M15 filled events in window: 7.
- Backtest P&L: `+7.76`.
- MT5 live rows loaded: 420; after M15 filter: 32.
- Matched: 3; mismatches: 3; live-only: 29; backtest-only: 4.
- Matched P&L live `+6.05` | BT `-27.76` | diff `+33.81`.
- Largest mismatch groups: `LOOSE_MATCH_SL_GUARD SELL +45.66`, `PNL_DIFF_SAME_BUCKET BUY -9.20`, `CLOSE_LIFECYCLE_PD SELL -2.65`.
- `PD_FILL_FAIL` no longer appears in S2 replay after `config.PDFIBOPLUS_SKIP_SIDS` was synced to include S2/S3.
- Report: `excel_reports/backtest_compare/s2/compare_s2_M15_20260528_0800_20260608_1000.csv`.

Known remaining S2 gaps:

- Cross-TF `FVG_PARALLEL` intersection/cancel/re-place, optimized sweep scan block, and current-TF Trend Filter scan block have first-pass replay for S2-only runs; report filtering now recognizes multi-member comments like `[M5_M15_M30]_S2`; remaining drift is exact live tick timing, shared state timing, higher-TF/exported trend scan state, and exact cross-TF re-place behavior.
- Limit TP/SL Break Cancel is implemented as a dormant replay layer for current config (`LIMIT_BREAK_CANCEL=False`); rerun with that config enabled if future audit needs to validate active break-cancel behavior.
- Limit Guard, Opposite Order, Trail SL, and SL Guard are replayed as baseline lifecycle layers, but exact focus/reversal/tick timing can still drift from live.
- PD/Trend recheck are runtime skips for S2 now; live mismatch labels can still appear from historical orders/logs, especially orders created before the skip-list change. Pre-create, pending, and fill PD skip lists are synced in `scanner.py`/`trailing.py`.
- Compare summary now suppresses generic S14-family buckets for non-S14 rows, so S2/S3/S9 reports no longer show `*_s14_family=UNKNOWN` noise.

### S3

- [x] สร้าง/รวม replay ราย strategy baseline
- [ ] รองรับ DM/SP/Marubozu, confirm/lookback/filter ที่ runtime ใช้ให้ครบ
- [x] เทียบ MT5 history รายช่วง baseline
- [x] จด command ใน `commands_and_tips.md`

S3 runtime coverage audit (updated 2026-06-18):

Checklist status note:

- `strategy3.strategy_3()`, DM/SP detection, normal confirm lookback, swing fallback, Marubozu/No Engulf pending confirmation, adjacent same-sid block, sweep scan block, pending fill, RSI Fill Recheck, Limit TP/SL Break Cancel, Limit Guard, Opposite Order, Trail SL, and SL Guard baseline are implemented.
- The remaining unchecked checklist item is still valid because exact global runtime state, exact sweep expiry/state, and higher-TF/exported trend scan state parity are not complete yet.

| Feature | Runtime for S3 | Replay status | Note |
|---|---|---|---|
| S3 DM/SP detect | apply | apply | Replay uses range-based MT5 fetch and calls shared `strategy3.strategy_3()`. |
| S3 normal confirm lookback | apply | apply | Replay uses scanner `_find_recent_signal_confirmation()` plus swing fallback. |
| S3 Marubozu / No Engulf pending | apply | apply | Replay waits one closed bar and places limit only when color confirms. |
| Adjacent same-sid scan block | apply | partial | Unified S1-S5/S8 replay now blocks adjacent same-sid orders when an active same-sid trade remains. |
| Sweep Filter scan block | apply | partial | Unified S1-S5/S8 replay uses historical sweep detection to block counter-sweep scan signals. |
| Pending limit lifecycle | apply | partial | Replay models pending fill and fixed SL/TP with bar high/low. |
| PD Fibo Plus | skip_s3 | skip_s3 | Runtime currently skips S3 in pending/fill PD Fibo Plus. |
| Limit Trend / Fill Trend Recheck | skip_s3 | skip_s3 | Runtime currently skips S3 approach/fill trend recheck. |
| Trend Filter scan block | apply if enabled | partial | Unified replay now calls scanner `trend_allows_signal()` with current-TF historical HHLL when enabled; higher-TF/exported scanner state can still drift. |
| RSI Fill Recheck | apply if enabled | off/ready | Config is currently OFF in tested state; replay supports mode1/mode2/mode3 when enabled. |
| Limit TP/SL Break Cancel | apply if enabled | off/ready | Config is currently OFF in tested state; replay cancels pending orders on confirmed TP/SL break when enabled. |
| Trail SL / Opposite / Limit Guard | apply if enabled | partial | Replay applies Limit Guard, Opposite Order, engulf Trail SL baseline, and SL Guard/Group baseline; SL Guard counts only losing SL/loss-guard closes like runtime, while focus/reversal/retry nuances can still drift. |

Evidence ล่าสุด:

```bash
python backtest_auto_trade.py --start "2026-05-28 08:00" --end "2026-06-08 10:00" --since "2026-05-28 00:00" --tf M15 --strategies 3 --exclude-cancelled --symbol XAUUSD.iux --compare-mt5-history --compare-csv --compare-xlsx --match-minutes 180 --match-entry-points 5
```

- S3 replay raw events: 237; kept M15 filled events in window: 32.
- Backtest P&L: `+207.83`.
- MT5 live rows loaded: 264; after M15 filter: 15.
- Matched: 7; mismatches: 6; live-only: 8; backtest-only: 25.
- Matched P&L live `+48.32` | BT `+12.34` | diff `+35.98`.
- Largest mismatch groups: `PNL_DIFF_SAME_BUCKET SELL +93.52`, `CLOSE_BUCKET_DIFF SELL -37.99`, `CLOSE_LIFECYCLE_PD SELL -19.40`.
- `PD_FILL_FAIL` no longer appears in S3 replay after `config.PDFIBOPLUS_SKIP_SIDS` was synced to include S2/S3.
- Report: `excel_reports/backtest_compare/s3/compare_s3_M15_20260528_0800_20260608_1000.csv`.

Known remaining S3 gaps:

- PD/Trend recheck are runtime skips for S3 now; single S3 uses unified same-TF lifecycle, but exact sweep-state expiry, higher-TF/exported trend scan state, and trail/guard state still drift. Pre-create, pending, and fill PD skip lists are synced in `scanner.py`/`trailing.py`.
- Limit Guard, Opposite Order, Trail SL, RSI modes, Limit TP/SL Break Cancel, and SL Guard are replayed as baseline lifecycle layers, but exact focus/reversal/tick timing can still drift from live.
- Need remaining scan/runtime parity: global runtime state interactions, exact sweep-state expiry, and exact higher-TF/exported trend scan state behavior if `TREND_FILTER_SCAN_BLOCK` is turned back on.
- Backtest-only count is high, so S3 is still partial parity rather than full audit-grade parity.

### S4

- [x] สร้าง/รวม replay ราย strategy baseline
- [x] รองรับนัยยะสำคัญ FVG และ swing helper ที่เกี่ยวข้อง baseline
- [x] เทียบ MT5 history รายช่วง baseline
- [x] จด command ใน `commands_and_tips.md`

S4 runtime coverage audit (updated 2026-06-15):

| Feature | Runtime for S4 | Replay status | Note |
|---|---|---|---|
| S4 significant FVG detect | apply | apply | Replay uses range-based MT5 fetch, injects historical HHLL cache per bar, and calls shared `strategy4.strategy_4(..., tf=tf_name)` like live scanner. |
| Pending limit lifecycle | apply | partial | Replay models pending fill and fixed SL/TP with bar high/low. |
| PD Fibo Plus | apply | partial | Replay applies pending and fill round1/round2 gates. |
| Limit Trend / Fill Trend Recheck | apply | partial | Replay applies pending approach and fill round1/round2 per-TF HHLL trend. |
| RSI Fill Recheck | apply if enabled | off/ready | Config is currently OFF in tested state; replay supports mode1/mode2/mode3 when enabled. |
| Trail SL / Opposite / Limit Guard | apply if enabled | partial | Replay applies Limit Guard, Opposite Order, engulf/reversal/Focus/trend-override Trail SL baseline, SL Guard/Group retry/unblock baseline, and system-level Limit Guard/Opposite/SL Guard Group overlays; full shared state can still drift. |
| Limit Sweep follow-up S8 | apply if enabled | off/ready | Config is currently OFF in tested state; replay can close swept positions and queue S8 follow-up orders when enabled. |

Evidence ล่าสุด:

```bash
python backtest_auto_trade.py --start "2026-05-28 08:00" --end "2026-06-08 10:00" --since "2026-05-28 00:00" --strategies 4 --exclude-cancelled --symbol XAUUSD.iux --compare-mt5-history --compare-csv --compare-xlsx --match-minutes 180 --match-entry-points 5
```

- S4 replay after historical HHLL injection and scanner-style PD pre-create: ALL-TF kept 4 events after `--exclude-cancelled` retains `PD_FILL_FAIL`.
- Latest M15 range-fetch sanity inside ALL run: raw events 25; kept M15 events 2; Backtest P&L `-28.37`; compare matched 0, live-only 3, backtest-only 4 at ALL scope.
- ALL-TF compare result: matched 0, mismatches 0, live-only 3, backtest-only 4; S4 M1 live orders are still not discovered by current-config replay.
- ALL-TF Backtest P&L: `-72.02`.
- Report: `excel_reports/backtest_compare/s4/compare_s4_ALL_20260528_0800_20260608_1000.csv`.
- Post-fix sanity (`2026-06-13 00:00` to `2026-06-15 21:00`) removed the false `2026-06-15 10:08` S4 M1 replay order; live scanner log at that time had `Swing Low:4327.91` outside gap and replay now matches that detect decision.
- Post-fix sanity still has one backtest-only `2026-06-13 01:45` row, but available bot log starts at `2026-06-14 22:06`, so there is no live runtime log context for that earlier replay row.

Known remaining S4 gaps:

- M15 sanity has no live S4 order, so P&L parity cannot be measured on this TF.
- ALL-TF sanity has live M1 S4 rows from `2026-05-28`, `2026-06-03`, and `2026-06-04 08:39`, but current replay blocks comparable M1 candidates at PD pre-create.
- Confirmed by `git blame`: scanner PD pre-create block moved before `PATTERN_FOUND` in commit `d867a202` at `2026-06-12 23:59 +0700`; these S4 live rows are historical behavior before the current strict pre-create gate.
- Need compare S4 again on live history after `2026-06-12 23:59 +0700` before marking current-config parity.

### S5

- [x] สร้าง/รวม replay ราย strategy baseline
- [x] ตรวจ runtime ว่า S5 เป็น limit strategy ปกติและ currently OFF ใน restored config
- [x] เทียบ MT5 history รายช่วง baseline
- [x] จด command ใน `commands_and_tips.md`

S5 runtime coverage audit (updated 2026-06-15):

| Feature | Runtime for S5 | Replay status | Note |
|---|---|---|---|
| S5 scalping detect | apply | apply | Replay calls shared `strategy5.strategy_5()`. |
| S5 internal filters | apply | apply | Replay uses range-based MT5 fetch, injects historical signal time and HHLL cache so no-trade-hour and zone filters use bar-time context. |
| Pending limit lifecycle | apply | partial | Replay models pending fill and fixed SL/TP with bar high/low. |
| PD Fibo Plus | apply | partial | Replay applies pending and fill round1/round2 gates. |
| Limit Trend / Fill Trend Recheck | apply | partial | Replay applies pending approach and fill round1/round2 per-TF HHLL trend. |
| RSI Fill Recheck | apply if enabled | off/ready | Config is currently OFF in tested state; replay supports mode1/mode2/mode3 when enabled. |
| Trail SL / Opposite / Limit Guard | apply if enabled | partial | Replay applies Limit Guard, Opposite Order, engulf/reversal/Focus/trend-override Trail SL baseline, SL Guard/Group retry/unblock baseline, and system-level Limit Guard/Opposite/SL Guard Group overlays; full shared state can still drift. |
| Limit Sweep follow-up S8 | apply if enabled | off/ready | Config is currently OFF in tested state; replay can close swept positions and queue S8 follow-up orders when enabled. |

Evidence ล่าสุด:

```bash
python backtest_auto_trade.py --start "2026-05-28 08:00" --end "2026-06-08 10:00" --since "2026-05-28 00:00" --tf M15 --strategies 5 --exclude-cancelled --symbol XAUUSD.iux --compare-mt5-history --compare-csv --compare-xlsx --match-minutes 180 --match-entry-points 5
```

- S5 selected but OFF in restored config; replay still runs for requested strategy audit.
- S5 replay raw events: 38; kept M15 events in window: 1 after `PD_FILL_FAIL` rows are retained as real filled closes.
- Backtest P&L: `+4.11`.
- MT5 live rows loaded for S5: 0.
- Compare result: matched 0, live-only 0, backtest-only 1.
- Report: `excel_reports/backtest_compare/s5/compare_s5_M15_20260528_0800_20260608_1000.csv`.

Known remaining S5 gaps:

- No live S5 order in the tested MT5 history window, so P&L parity cannot be measured yet.
- Historical no-trade-hour and HHLL zone context are now replayed; remaining parity needs shared cross-strategy state and TFs with live S5 rows.

### S6 / S6i

- [x] ตรวจ runtime ว่าเป็น strategy id จริงหรือเป็น trail logic state (`6`, `7`)
- [x] จดเป็น dependency ของ strategy อื่นแทน standalone replay
- [x] ตรวจ MT5 history baseline ว่าไม่มี live filled order sid 6/7 ในช่วงทดสอบ

S6/S6i runtime coverage audit (2026-06-09):

| Item | Runtime behavior | Replay status | Note |
|---|---|---|---|
| S6 (`sid=6`) | management state | dependency gap | `check_s6_trail()` runs when strategy toggle 6 is ON and processes existing S2/S3 positions. It does not create new standalone orders. |
| S6i (`sid=7`) | management state | dependency gap | `check_s6_trail()` also manages `_s6i_state` for positions not in `_s6_state` after entry flow is done. It does not create new standalone orders. |
| MT5 history | no standalone fills | confirmed | Long-window MT5 history count: S6=0, S7=0. |

Evidence ล่าสุด:

```bash
python -c "import MetaTrader5 as mt5, config; import backtest_auto_trade as b; from collections import Counter; start=b.parse_bkk_dt('2026-05-28 08:00'); end=b.parse_bkk_dt('2026-06-08 10:00'); mt5.initialize(); config.restore_runtime_state(); config.set_runtime_symbol('XAUUSD.iux'); rows=b.load_mt5_history_orders(start,end,config.SYMBOL,set(range(1,17)),close_search_days=14); c=Counter(int(r.get('sid',0) or 0) for r in rows); print('S6', c.get(6,0)); print('S7', c.get(7,0)); mt5.shutdown()"
```

- Output: `S6 0`, `S7 0`.
- Code references: `main.py` calls `check_s6_trail(app)`; `trailing.py` owns `_s6_state`, `_s6i_state`, and `check_s6_trail()`.
- Scanner summary only reports current S6/S6i management state; it does not place S6/S6i orders.

Known remaining S6/S6i gaps:

- No separate `sim_s6_backtest.py` or `sim_s7_backtest.py` is needed for entry replay.
- S6/S6i must be added later as shared lifecycle/trailing overlays for S2/S3 and other eligible positions when moving from per-strategy baseline to audit-grade full lifecycle replay.

### S8

- [x] สร้าง/รวม replay ราย strategy baseline
- [x] รองรับ native swing limit และ delayed SL baseline บางส่วน
- [x] เทียบ MT5 history รายช่วง baseline
- [x] จด command ใน `commands_and_tips.md`

S8 runtime coverage audit (updated 2026-06-15):

| Feature | Runtime for S8 | Replay status | Note |
|---|---|---|---|
| S8 swing-limit detect | apply | apply | Replay injects historical HHLL cache, calls shared `strategy8.strategy_8(..., tf=tf_name)`, and handles `MULTI` orders. |
| Dual-side pending placement | apply | apply | Replay can place both BUY and SELL S8 limits from one scan result. |
| Delayed SL arm | apply | partial | Replay models default breakout arm and fill fallback; time/price delay modes are approximated. |
| S8 swing-change cancel | apply | partial | Replay cancels pending when the same-side reference swing changes in historical scan. |
| Limit Sweep follow-up S8 | apply if enabled | off/ready | Config is currently OFF in tested state; replay can close swept positions and queue S8 follow-up orders when enabled. |
| PD Fibo Plus | apply | partial | Replay applies pending and fill round1/round2 gates. |
| Limit Trend / Fill Trend Recheck | apply | partial | Replay applies pending approach and fill round1/round2 per-TF HHLL trend. |
| RSI Fill Recheck | apply if enabled | off/ready | Config is currently OFF in tested state; replay supports mode1/mode2/mode3 when enabled. |
| Trail SL / Opposite / Limit Guard | apply if enabled | partial | Replay applies Limit Guard, Opposite Order, same-bar duplicate setup overlay, engulf/reversal/Focus/trend-override Trail SL baseline, SL Guard/Group retry/unblock baseline, runner-level group context overlay, and system-level Limit Guard/Opposite/SL Guard Group overlays; full shared order-state can still drift. |

Evidence ล่าสุด:

```bash
python backtest_auto_trade.py --start "2026-05-28 08:00" --end "2026-06-08 10:00" --since "2026-05-28 00:00" --tf M15 --strategies 8 --exclude-cancelled --symbol XAUUSD.iux --compare-mt5-history --compare-csv --compare-xlsx --match-minutes 180 --match-entry-points 5
```

- S8 selected but OFF in restored config; replay still runs for requested strategy audit.
- S8 replay raw events: M1 11475, M5 1827, M15 467, M30 218, H1 101; context replay included `M1`, `M5`, `M15`, `M30`, and `H1` via range-based MT5 fetch for SL Guard Group; kept M15 events in window: 28 before system same-bar duplicate overlay and 22 final report events after swing-change cancel + PD/trend/RSI lifecycle, Limit Guard, same-bar duplicate setup overlay, Opposite Order, engulf/reversal/Focus/trend-override Trail SL, SL Guard retry/unblock baseline, Limit Sweep follow-up readiness, and S8 group context overlay.
- Backtest P&L: `+19.37`.
- MT5 live rows loaded for S8: 0.
- Compare result: matched 0, live-only 0, backtest-only 22.
- Report: `excel_reports/backtest_compare/s8/compare_s8_M15_20260528_0800_20260608_1000.csv`.

Known remaining S8 gaps:

- No live S8 order in the tested MT5 history window, so P&L parity cannot be measured yet.
- Historical HHLL detect context and range-based SL Guard Group context are now replayed; remaining gap is full shared cross-strategy pending/open order-state fidelity before audit-grade parity.

### S9

- [x] สร้าง/รวม replay ราย strategy baseline
- [x] รองรับ RSI divergence และ skip/recheck rules หลักตาม runtime
- [x] เทียบ MT5 history รายช่วง baseline
- [x] จด command ใน `commands_and_tips.md`

S9 runtime coverage audit (updated 2026-06-18):

| Feature | Runtime for S9 | Replay status | Note |
|---|---|---|---|
| S9 RSI divergence detect | apply | apply | Replay calls shared `strategy9.strategy_9()`. |
| S9 setup dedup / passed-entry | apply | partial | Replay dedups pivot `setup_sig` and invalidates setup when signal-bar close has passed limit entry. |
| Pending limit lifecycle | apply | partial | Replay models pending fill and fixed SL/TP with bar high/low. |
| PD Fibo Plus | skip_s9 | skip_s9 | Runtime skips S9 PD Fibo Plus. |
| Limit Trend / Fill Trend Recheck | skip_s9 | skip_s9 | Runtime skips S9 trend recheck. |
| RSI Fill Recheck | skip_s9 | skip_s9 | Runtime skips S9 RSI fill recheck. |
| Strong Trend Block | apply if enabled | gap/off | Config is currently OFF in tested state. |
| SL Guard Group | apply if enabled | partial | Runner replays context TFs and applies central close-on-activate overlay before filtering back to requested TF. |
| Limit Guard | apply if enabled | partial | Replay applies pending cancel baseline against open S9 rows. |
| Opposite Order | apply if enabled | partial | Replay applies central opposite-order close/TP-link baseline for open S9 rows. |
| Trail SL | apply if enabled | partial | Replay applies central engulf/reversal/safe Trail SL baseline for open S9 rows. |

Evidence ล่าสุด:

```bash
python backtest_auto_trade.py --start "2026-05-28 08:00" --end "2026-06-08 10:00" --since "2026-05-28 00:00" --tf M15 --strategies 9 --exclude-cancelled --symbol XAUUSD.iux --compare-mt5-history --compare-csv --compare-xlsx --match-minutes 180 --match-entry-points 5
```

- S9 selected but OFF in restored config; replay still runs for requested strategy audit.
- S9 replay now uses range-based MT5 fetch when the central runner has a date window, so M1/M5 context can reach the requested May 28 to June 8 history instead of only the latest bars.
- M15 sanity after range fetch and shared lifecycle baseline: context raw M1 `97`, M5 `30`, M15 `8`, M30 `5`, H1 `0`; kept M15 events in window: `6`; Backtest P&L `+28.77`.
- MT5 live rows loaded: 56; after M15 filter: 0.
- Compare result: matched 0, live-only 0, backtest-only 6.
- Latest M15 run included SL Guard Group context TFs `M1`, `M5`, `M15`, `M30`, `H1`; overlay changed 1 M15 close to `SL_GUARD_GROUP` (`2026-06-03 20:30`, BUY, PnL `-5.07`).
- Report: `excel_reports/backtest_compare/s9/compare_s9_M15_20260528_0800_20260608_1000.csv`.
- M1 parity sanity after range fetch: kept M1 events `84`, Backtest P&L `-104.27`; live rows 48; matched 43, mismatches 42, live-only 5, backtest-only 41; matched P&L live `-113.04` | BT `-78.71` | diff `-34.33`.
- M1 report: `excel_reports/backtest_compare/s9/compare_s9_M1_20260528_0800_20260608_1000.csv`.
- M5 parity sanity after range fetch: kept M5 events `27`, Backtest P&L `-18.72`; live rows 6; matched 6, mismatches 6, live-only 0, backtest-only 21; matched P&L live `+31.12` | BT `-21.60` | diff `+52.72`.
- M5 report: `excel_reports/backtest_compare/s9/compare_s9_M5_20260528_0800_20260608_1000.csv`.

Known remaining S9 gaps:

- M15 sanity has no live S9 order, so P&L parity must be judged from M1/M5/H1 instead.
- M1/M5 now have live parity evidence; remaining gap is high backtest-only count and P&L drift from signal timing, tick ordering, SL trail source, and shared state.
- Trail SL, Opposite Order, and Limit Guard are now partially replayed for S9; remaining drift is bar/tick timing, shared runtime state, and TFs that actually have live S9 rows.
- SL Guard Group overlay is still a bar/order-event approximation of shared runtime guard state.

### S10

- [x] มี `backtest_s10_timewindow.py`
- [x] มี `check_s10_parent.py`
- [x] มี central replay path ใน `backtest_auto_trade.py`
- [x] รองรับ compare MT5 history และ CSV/XLSX report
- [x] มี progress log ระหว่างรัน
- [x] จด command หลักใน `commands_and_tips.md`
- [x] Audit ให้ครบทุก config runtime ที่พี่ระบุ: Trail SL, reversal trail, entry candle mode/TP, opposite order, limit sweep, delay SL, limit TP/SL break, limit guard, engulf minimum, trend filter
- [x] รัน compare ช่วงยาวล่าสุดหลัง audit แล้วบันทึกผล

S10 runtime coverage audit (updated 2026-06-18):

| Feature | Runtime for S10 | Replay status | Note |
|---|---|---|---|
| CRT detect / model orders | apply | apply | Uses `strategy10.strategy_10()` in replay, including HTF arm and LTF model orders. |
| S10 sibling cancel | apply | apply | Replay closes sibling pending after one model fills. |
| S10 sweep / structure / parent-touch cancel | apply | apply | Replay has S10 invalidation checks. |
| S10 arm state on pending cancel | apply | apply | Replay mirrors runtime: pending/sibling cancel does not call `strategy10.handle_ticket_closed()`, while real position close still does. |
| Fixed SL/TP close | apply | apply | Replay uses bar high/low. |
| SL Guard per-TF / combined / group | apply | apply | Includes close-on-activate and loss guard counting. |
| PD Fibo Plus | skip_s10 | skip_s10 | Runtime skips SIDs 9,10,13,14,15,16. |
| Limit Trend Recheck | skip_s10 | skip_s10 | Runtime skips S10 because CRT is managed by S10-specific invalidation. |
| RSI Fill Recheck | apply if `PENDING_RSI_RECHECK_ENABLED` | gap | Config is currently OFF, but runtime does not skip S10; replay must be added before enabling this for S10 backtests. |
| Entry Candle mode / TP update | skip_s10 | skip_s10 | Runtime skips S10 in `check_entry_candle_quality()`. |
| Trail SL / reversal trail | skip_s10 | skip_s10 | Runtime skips S10 in `check_engulf_trail_sl()`. |
| Opposite Order | skip_s10 | skip_s10 | Runtime filters S10 positions and orders. |
| Limit Guard | skip_s10 | skip_s10 | Runtime skips S10 pending orders. |
| Limit TP/SL Break Cancel | skip_s10 | skip_s10 | S10 uses parent-touch cancel instead. |
| Delay SL | apply if `DELAY_SL_MODE != "off"` | gap | Config is currently OFF; S10 model limit orders can delay SL when enabled. |
| Engulf minimum | apply | apply | Model-2 FVG uses `engulf_min_price()` through shared `strategy10` code. |
| Normal Trend Filter scan block | skip_s10 | skip_s10 | S10 bypasses normal trend filter scan block. |
| Strong Trend Block | apply if enabled for S10 | gap | Config is currently OFF; replay must be added before enabling this for S10 backtests. |
| Limit Sweep | apply if `LIMIT_SWEEP` | gap | Config is currently OFF; replay must be added before enabling this for S10 backtests. |

S10 latest evidence (2026-06-18):

```bash
python backtest_auto_trade.py --start "2026-05-28 08:00" --end "2026-06-08 10:00" --since "2026-05-28 00:00" --tf H1 --strategies 10 --exclude-cancelled --symbol XAUUSD.iux --compare-mt5-history --compare-csv --compare-xlsx --match-minutes 180 --match-entry-points 5
```

Result after current S10 sanity compare with exact HTF (`H1`) live filter:

- Runtime coverage warning is shown before replay.
- S10 replay raw events: 473; kept in window: 13.
- Backtest P&L: `+34.44`.
- MT5 live rows loaded: 54; after exact `H1` filter: 7.
- Matched: 1.
- Mismatches: 1.
- Live only: 6.
- Backtest only: 12.
- Matched P&L live `-9.00` | BT `+86.96` | diff `-95.96`.
- Latest fix reduced duplicate same-parent replay rows by matching runtime S10 arm behavior on pending/sibling cancel.
- Current config has no active unreplayed S10 gap: RSI Fill Recheck OFF, Delay SL `off`, Strong Trend Block OFF, Limit Sweep OFF.
- Report: `excel_reports/backtest_compare/s10/compare_s10_H1_20260528_0800_20260608_1000.csv`.

Known remaining S10 gaps:

- Old live orders in this window still include at least one S10 close reason `PD Zone fill...`; current runtime now skips PD for S10, so this is expected historical drift unless comparing only after the PD skip fix date.
- Replay gaps only matter if future config enables them: RSI Fill Recheck, Delay SL, Strong Trend Block, Limit Sweep.
- Main current parity gap is not an active config feature gap; it is remaining signal/order-count drift (`BT-only 12`) and live fill timing/entry drift, especially 2026-06-05 live BUY fills around 09:25 versus replay setup around 08:01.
- 2026-06-05 diagnostic: live orders were set at 08:00:09 with entries `4452.22` / `4453.00`, SL `4450.29`, TP `4499.89`; current replay uses the same parent/SL/TP but current `strategy10` chooses latest failed-push at 07:27 and produces Model1/2 `4464.44` / `4464.58`. Treat this as S10 model-selection historical drift unless reproduced by new live orders after the current code version.

### S11

- [x] สร้าง/รวม replay ราย strategy baseline
- [x] รองรับ Fibo S1 และ PD/recheck skip/apply ตาม runtime ล่าสุดให้ครบ
- [x] เทียบ MT5 history รายช่วง baseline
- [x] จด command ใน `commands_and_tips.md`

S11 runtime coverage audit (updated 2026-06-18):

Checklist status note:

- S11 Fibo state/cascade, S1 anchor hook, S1 shadow linked cleanup, PD skip-list parity, Limit Trend/RSI skip parity, Limit Guard, Opposite Order, Trail SL, and SL Guard Group baseline are implemented.
- Fibo/S1 and PD/recheck skip/apply coverage is now checked; exact bar/tick timing and shared runtime state still drift as known gaps.

| Feature | Runtime for S11 | Replay status | Note |
|---|---|---|---|
| S1 anchor hook | apply | apply | Replay uses range-based MT5 fetch, calls `strategy1.strategy_1()`, and records S1 anchors for strategy11. |
| S11 Fibo state/cascade | apply | apply | Replay calls shared `strategy11.strategy_11()` on scanner-style rolling windows. |
| Pending limit lifecycle | apply | partial | Replay models pending fill and fixed SL/TP with bar high/low. |
| PD Fibo Plus | skip_s11 | skip_s11 | Runtime currently skips S11 via `config.PDFIBOPLUS_SKIP_SIDS`; replay now follows the same skip list. |
| Limit Trend / RSI Recheck | skip_s11 | skip_s11 | Runtime skips S11 in pending trend and RSI fill recheck. |
| Strong Trend Block | apply if enabled | gap/off | Config is currently OFF in tested state. |
| Duplicate/adjacent guards | apply | partial | Replay blocks same pending setup and adjacent same-SID bar while S11 exposure is active. |
| S1 linked cleanup | apply | partial | Replay runs a shadow S1 lifecycle and cancels/closes S11 when a filled S1 invalidates; pending S11 cleanup is emitted as `CANCEL` so `--exclude-cancelled` filters it correctly. |
| SL Guard Group | apply if enabled | partial | Runner replays context TFs and applies central close-on-activate overlay before filtering back to requested TF. |
| Limit Guard | apply if enabled | partial | Replay applies pending cancel baseline against open S11 rows. |
| Opposite Order | apply if enabled | partial | Replay applies central opposite-order close/TP-link baseline for open S11 rows. |
| Trail SL | apply if enabled | partial | Replay applies central engulf/reversal/safe Trail SL baseline for open S11 rows. |

Evidence ล่าสุด:

```bash
python backtest_auto_trade.py --start "2026-05-28 08:00" --end "2026-06-08 10:00" --since "2026-05-28 00:00" --tf M15 --strategies 11 --exclude-cancelled --symbol XAUUSD.iux --compare-mt5-history --compare-csv --compare-xlsx --match-minutes 180 --match-entry-points 5
```

- S11 replay now uses range-based MT5 fetch for main/trail TF data and rolling `TF_LOOKBACK + 6` strategy windows, matching scanner-style input while avoiding the earlier timeout from ever-growing full-history slices.
- S11 linked cleanup now has a shadow S1 lifecycle; S11 pending cleanup is recorded as cancelled, while filled S11 rows close at the replay bar close with `S11_LINKED_CLEANUP`.
- S11 context raw events after range fetch + linked-cleanup + Limit Guard + Opposite + Trail SL baseline: M1 `31`, M5 `551`, M15 `175`, M30 `90`, H1 `51`; kept M15 filled events in window after `--exclude-cancelled`: `35`.
- Backtest P&L: `-21.11`.
- MT5 live rows loaded: 104; after M15 filter: 11.
- Matched: 10; mismatches: 9; live-only: 1; backtest-only: 25.
- Matched P&L live `-1.67` | BT `+8.60` | diff `-10.27`.
- Latest M15 run included SL Guard Group context TFs `M1`, `M5`, `M15`, `M30`, `H1`; overlay ran after S11 context replay but the current summary did not produce an M15 `SL_GUARD_GROUP` close.
- Largest mismatch groups: `CLOSE_BUCKET_DIFF SELL -35.78`, `PNL_DIFF_SAME_BUCKET SELL +15.32`, `LIVE_CLOSE_TREND_RECHECK BUY +5.60`, `CLOSE_LIFECYCLE_PD BUY +4.01`.
- Report: `excel_reports/backtest_compare/s11/compare_s11_M15_20260528_0800_20260608_1000.csv`.

Known remaining S11 gaps:

- Current replay follows the new S11 PD skip list, but live history in this window still contains older `PD Zone fill check` closes; treat those as historical/runtime-version drift.
- Duplicate pending setup, adjacent same-SID block, S1 linked cleanup, Limit Guard, Opposite Order, and Trail SL are now partially replayed; current baseline still over-produces backtest-only rows mainly from bar/tick timing, shared runtime state, and historical runtime drift.
- Live history contains a `Fill Trend Recheck` close on S11 even though current runtime skip table says S11 skips trend/RSI recheck; this is likely historical/runtime-version drift and should be rechecked on post-fix orders.
- SL Guard Group overlay is still a bar/order-event approximation of shared runtime guard state.

### S12

- [x] สร้าง/รวม replay ราย strategy baseline
- [x] รองรับ standalone/range behavior และ skip limit guard/notifications ตาม runtime baseline
- [x] เทียบ MT5 history รายช่วง baseline
- [x] จด command ใน `commands_and_tips.md`

S12 runtime coverage audit (updated 2026-06-18):

| Feature | Runtime for S12 | Replay status | Note |
|---|---|---|---|
| S12 M5 range zone scan | apply | apply | Replay uses `strategy12` zone helpers on M5 bars. |
| S12 market lifecycle | apply | partial | Replay approximates entry/close with M5 bar close instead of live bid/ask tick. |
| S12 order count / side state | apply | apply | Replay tracks side, order count, and last entry price. |
| S12 breakout / flip close-all | apply | partial | Replay closes open S12 rows on breakout/flip using M5 close. |
| S12 SL cooldown | apply | partial | Replay blocks new S12 entries for `S12_COOLDOWN_SECONDS` after replay SL close. |
| PD / Trend / Limit Guard | skip_s12_or_market | skip_s12_or_market | S12 is market/standalone and runtime skips normal pending limit guard path. |

Evidence ล่าสุด:

```bash
python backtest_auto_trade.py --start "2026-05-28 08:00" --end "2026-06-08 10:00" --since "2026-05-28 00:00" --tf M5 --strategies 12 --exclude-cancelled --symbol XAUUSD.iux --compare-mt5-history --compare-csv --compare-xlsx --match-minutes 180 --match-entry-points 5
```

- S12 selected but OFF in restored config; replay still runs for requested strategy audit.
- S12 replay raw events: 39; kept M5 events in window: 16 after SL cooldown.
- Backtest P&L: `+50.04`.
- MT5 live rows loaded for S12: 0.
- Compare result: matched 0, live-only 0, backtest-only 16.
- Report: `excel_reports/backtest_compare/s12/compare_s12_M5_20260528_0800_20260608_1000.csv`.

Known remaining S12 gaps:

- No live S12 order in the tested MT5 history window, so P&L parity cannot be measured yet.
- Need live tick bid/ask/spread replay for audit-grade S12 because current baseline uses M5 close.
- SL cooldown is now replayed from bar close time; runtime stamps cooldown when `s12_cleanup_tickets()` observes the SL close, so exact wall-clock timing can still drift by scan/MT5 latency.

### S13

- [x] สร้าง/รวม replay ราย strategy
- [x] รองรับ EzAlgo baseline, TP split, same-side skip, opposite flip, skip rules หลักตาม runtime
- [x] เทียบ MT5 history รายช่วง baseline
- [x] จด command ใน `commands_and_tips.md`

S13 runtime coverage audit (updated 2026-06-18):

| Feature | Runtime for S13 | Replay status | Note |
|---|---|---|---|
| S13 EzAlgo detect | apply | apply | Replay calls shared `strategy13.strategy_13()`. |
| S13 market/split TP | apply | partial | Replay opens split TP rows as market rows; live can mix market and limit depending tick vs entry. |
| S13 opposite flip | apply | apply | Replay closes opposite S13 rows on same TF before new signal. |
| PD Fibo Plus | skip_s13 | skip_s13 | Runtime skips SIDs 9,10,13,14,15,16. |
| Fill Trend Recheck | apply | partial | Replay applies fill trend recheck round1 with injected HHLL trend context; round2 / scan-cycle timing can still drift. |
| RSI Fill Recheck | apply if enabled | gap/off | Config is currently OFF in tested state. |
| SL Guard Group | apply if enabled | partial | Runner replays context TFs and applies central close-on-activate overlay before filtering back to requested TF. |
| Trail SL | skip_s13 | skip_s13 | Runtime skips standalone S13. |
| Opposite Order | skip_s13 | skip_s13 | Runtime filters S13 positions/orders. |

Evidence ล่าสุด:

```bash
python backtest_auto_trade.py --start "2026-05-28 08:00" --end "2026-06-08 10:00" --since "2026-05-28 00:00" --tf M15 --strategies 13 --exclude-cancelled --symbol XAUUSD.iux --compare-mt5-history --compare-csv --compare-xlsx --match-minutes 180 --match-entry-points 5
```

- S13 context raw events: M1 `1896`, M5 `928`, M15 `264`, M30 `144`, H1 `84`; kept M15 events in window: `112`.
- Backtest P&L: `-35.39`.
- MT5 live rows loaded for S13: 0.
- Compare result: matched 0, live-only 0, backtest-only 112.
- Latest M15 run included SL Guard Group context TFs `M1`, `M5`, `M15`, `M30`, `H1`; fill trend round1 closed 68 M15 split rows as `TREND_RECHECK` at entry price.
- Report: `excel_reports/backtest_compare/s13/compare_s13_M15_20260528_0800_20260608_1000.csv`.

Known remaining S13 gaps:

- No live S13 order in the tested MT5 history window, so P&L parity cannot be measured yet.
- Fill Trend Recheck round1 is now replayed; round2 and exact 5-second scan-cycle timing are still approximated.
- SL Guard Group overlay is still a bar/order-event approximation of shared runtime guard state.
- Market-vs-limit split depends on live tick versus strategy entry; replay baseline uses market rows for split TP.

### S14

- [x] มี `backtest_s14_timewindow.py`
- [x] มี `sim_s14_backtest.py`
- [x] มี central replay path ใน `backtest_auto_trade.py`
- [x] รองรับ S14 context replay สำหรับ SL Guard Group TFs
- [x] รองรับ MT5 history compare, CSV/XLSX, summary, scale-out columns
- [x] เพิ่ม S14 family diagnostics: `BUY_SWEEP`, `BUY_ENGULF`, `SELL_SWEEP`, `SELL_ENGULF`
- [x] เพิ่ม optional `--prefer-same-s14-family` เป็น diagnostic mode
- [x] เพิ่ม optional `--hybrid-live-guard-context` เป็น diagnostic mode
- [x] เพิ่ม granular S14 lifecycle price path: SL/TP/trail/scale-out ใช้ TF ย่อยจาก `TRAIL_GROUPS` ระหว่างแท่งหลัก
- [x] รัน baseline ช่วง `2026-05-28 08:00` ถึง `2026-06-08 10:00`, `M15`, `XAUUSD.iux`
- [ ] ไล่ gap ที่เหลือ: `SELL_SWEEP` live-only และ `SELL_ENGULF` drift; `TRAIL_SL_DIFF_SOURCE` ถูกตรวจแล้วว่า live source ว่างเพราะไม่มี bot log ช่วง 2026-05-29
- [x] Audit ให้ครบทุก config runtime ที่พี่ระบุเหมือน S10

S14 runtime coverage audit (updated 2026-06-18):

| Feature | Runtime for S14 | Replay status | Note |
|---|---|---|---|
| S14 Sweep/Engulf detect | apply | apply | Replay calls shared `strategy14.strategy_14()`. |
| S14 HHLL swing reference | apply | apply | Replay now injects historical HHLL by default because S14 swing modes read `hhll_swing` refs even when legacy `S14_LL_USE_HHLL` is not defined. |
| S14 market fill | apply | partial | Replay fills at strategy market reference price on the detect bar; live fills at broker tick price. |
| S14 Flip | apply | apply | Replay closes opposite S14 exposure on same TF before new order. |
| S14 exit color rule | apply | apply | Sweep checks entry TF; engulf checks mapped HTF/secondary HTF. |
| Range-based MT5 fetch | apply | apply | Replay fetches TF/HTF/trail context by date range so low TF context can reach the requested historical window. |
| Trail SL / reversal nuances | apply | partial | Replay models engulf trail across `TRAIL_GROUPS` with granular lifecycle price path, but focus/opposite/reversal nuances can still drift. |
| SL Guard Group overlay | apply | partial | Replay approximates close-on-activate from replayed TF context. |
| PD Fibo Plus | skip_s14 | skip_s14 | Runtime skips SIDs 9,10,13,14,15,16; replay was corrected to skip S14. |
| Limit Trend Recheck | skip_s14 | skip_s14 | Runtime skips S14. |
| RSI Fill Recheck | skip_s14 | skip_s14 | Runtime skips S14. |
| Entry Candle | skip_s14 | skip_s14 | Runtime skips S14 standalone/market flow. |
| Opposite Order | skip_s14 | skip_s14 | Runtime filters S14 positions/orders. |
| Limit Guard | skip_s14 | skip_s14 | S14 uses market orders. |
| Delay SL | skip_s14 | skip_s14 | S14 does not use delayed pending SL. |
| Strong Trend Block | apply if enabled for S14 | off/ready | Config is currently OFF; replay now blocks counter-strong-trend S14 signals when enabled. |

Evidence ล่าสุด:

```bash
python backtest_auto_trade.py --start "2026-05-28 08:00" --end "2026-06-08 10:00" --since "2026-05-28 00:00" --tf M15 --strategies 14 --exclude-cancelled --symbol XAUUSD.iux --compare-mt5-history --compare-csv --compare-xlsx --match-minutes 180 --match-entry-points 5
```

ผล baseline ล่าสุด:

- S14 replay raw events by context TF after range fetch + HHLL injection + Strong Trend Block ready path: M1=268, M5=62, M15=11, M30=10, H1=2.
- S14 replay kept M15 events in window: 3.
- Backtest P&L: `+34.37`.
- MT5 live rows loaded: 433; after `M15` filter: 32.
- Matched: 1; mismatches: 1; live-only: 31; backtest-only: 2.
- Matched P&L live `+11.14` | BT `-1.24` | diff `+12.38`.
- Main mismatch gap: `PNL_DIFF_SAME_BUCKET SELL count=1 pnl=+12.38`.
- Trail-source diagnostic note: the remaining `TRAIL_SL_DIFF_SOURCE SELL count=1 pnl=+12.38` row has live ticket `534295319` on `2026-05-29`, but available `logs/bot.log` starts on `2026-06-18`, so live trail source cannot be reconstructed from bot logs for that historical row.
- Lifecycle note: granular price path now checks current SL/TP before applying newly trailed SL, so same-bar trail look-ahead is avoided.
- Market-fill note: S14 market replay now fills on the detect bar using strategy reference entry instead of next-bar open, matching runtime timing more closely.
- HHLL note: the previous 0-event run came from missing historical HHLL injection; the replay now injects HHLL by default for S14 swing refs.
- Strong Trend Block note: config is OFF in the tested state, but S14 replay now follows the runtime counter-strong-trend block when enabled.
- Report: `excel_reports/backtest_compare/s14/compare_s14_M15_20260528_0800_20260608_1000.csv`

Known remaining S14 gaps:

- Live-only remains high after the HHLL replay fix: live families are BUY_ENGULF 9, SELL_SWEEP 9, BUY_SWEEP 7, SELL_ENGULF 6 while replay kept only 3 M15 rows in the requested window.
- S14 signal sensitivity check points to historical gate/config drift rather than range-fetch failure: with current config replay kept 3 M15 rows; forcing `S14_RSI_DIV_ENABLED=False` in-process kept 13; forcing `S14_SWEEP_RETURN=True` kept 15; forcing both kept 60, which overshoots live.
- Current replay uses HHLL swing refs and current `S14_RSI_DIV_ENABLED=True`, `S14_SWEEP_RETURN=False` from `bot_state.json`; older live rows in this window likely came from looser S14 gates or a prior `strategy14.py` version.
- `TRAIL_SL_DIFF_SOURCE` remains on 1 SELL matched row, but current evidence points to missing historical bot log trail metadata rather than a confirmed replay trail-source bug.
- SL Guard Group / Fill Trend Recheck close rows remain because replay only approximates cross-TF runtime state.
- Old live orders still contain `PD Zone fill...` close reasons in this historical window; current runtime and replay now skip PD for S14, so compare after the skip-fix date should be cleaner.

Diagnostic strict-family:

```bash
python backtest_auto_trade.py --start "2026-05-28 08:00" --end "2026-06-08 10:00" --since "2026-05-28 00:00" --tf M15 --strategies 14 --exclude-cancelled --symbol XAUUSD.iux --compare-mt5-history --compare-csv --compare-xlsx --match-minutes 180 --match-entry-points 5 --prefer-same-s14-family
```

ผล strict-family แย่กว่า baseline (`diff=-24.82`) จึงเก็บเป็น diagnostic เท่านั้น ไม่เปิด default

### S15

- [x] สร้าง/รวม replay ราย strategy
- [x] รองรับ VP absorption/value-area zone, pending limit fill baseline, skip RSI/trend/PD ตาม runtime
- [x] เทียบ MT5 history รายช่วง
- [x] จด command ใน `commands_and_tips.md`

S15 runtime coverage audit (updated 2026-06-18):

| Feature | Runtime for S15 | Replay status | Note |
|---|---|---|---|
| S15 VP absorption detect | apply | apply | Replay calls shared `strategy15.strategy_15()` with replay-safe cooldown. |
| S15 limit lifecycle | apply | partial | Replay models pending limit fill then fixed SL/TP; broker tick ordering can drift. |
| PD Fibo Plus | skip_s15 | skip_s15 | Runtime skips SIDs 9,10,13,14,15,16. |
| Limit Trend Recheck | skip_s15 | skip_s15 | Runtime skips S15 trend recheck. |
| RSI Fill Recheck | skip_s15 | skip_s15 | Runtime skips S15 RSI fill recheck. |
| Trail SL | skip_s15 | skip_s15 | Runtime skips standalone S15. |
| Opposite Order | skip_s15 | skip_s15 | Runtime filters S15 positions/orders. |
| Limit Guard | skip_s15 | skip_s15 | Runtime skips S15 limit guard because VP levels can be intentionally far. |
| SL Guard | apply if enabled | partial | S15 keeps SL Guard; replay applies SL Guard Group close-on-activate overlay as a baseline. |

Evidence ล่าสุด:

```bash
python backtest_auto_trade.py --start "2026-05-28 08:00" --end "2026-06-08 10:00" --since "2026-05-28 00:00" --tf M15 --strategies 15 --exclude-cancelled --symbol XAUUSD.iux --compare-mt5-history --compare-csv --compare-xlsx --match-minutes 180 --match-entry-points 5
```

- S15 context replay raw events: M1 `62`, M5 `48`, M15 `14`, M30 `2`, H1 `0`; kept M15 events in window: 6.
- Backtest P&L: `-18.87`.
- MT5 live rows loaded: 45; after M15 filter: 2.
- Matched: 1; mismatches: 1; live-only: 1; backtest-only: 5.
- Matched P&L diff: `+9.46`.
- Latest M15 run included SL Guard Group context TFs `M1`, `M5`, `M15`, `M30`, `H1`; overlay made no additional close in this window.
- Report: `excel_reports/backtest_compare/s15/compare_s15_M15_20260528_0800_20260608_1000.csv`.

Known remaining S15 gaps:

- SL Guard Group overlay baseline exists; hybrid live guard context was tested and did not change S15 compare because the live-only 2026-06-03 row has no matching replay S15 signal to close. Treat this as S15 signal-discovery/version drift first, not a guard-close overlay miss.
- Limit fill/TP/SL ordering is bar-based, so broker tick ordering and spread can drift.

### S16

- [x] สร้าง/รวม replay ราย strategy
- [x] รองรับ AMD x iFVG baseline และ skip/recheck rules หลักตาม runtime
- [x] เทียบ MT5 history รายช่วง baseline
- [x] จด command ใน `commands_and_tips.md`

S16 runtime coverage audit (updated 2026-06-18):

| Feature | Runtime for S16 | Replay status | Note |
|---|---|---|---|
| S16 AMD/iFVG detect | apply | apply | Replay injects simulated BKK time and Asian range instead of using `config.now_bkk()`. |
| S16 limit lifecycle | apply | partial | Replay models pending limit fill then fixed SL/TP; broker tick ordering can drift. |
| PD Fibo Plus | skip_s16 | skip_s16 | Runtime skips SIDs 9,10,13,14,15,16. |
| Limit Trend Recheck | skip_s16 | skip_s16 | Runtime skips S16 fill trend recheck. |
| SL Guard Group | apply | partial | Runner now replays context TFs and applies central close-on-activate overlay before filtering back to requested TF. |
| Trail/Opposite Order | skip_s16 | skip_s16 | Runtime filters standalone S16 from Trail SL and Opposite Order. |

Evidence ล่าสุด:

```bash
python backtest_auto_trade.py --start "2026-05-28 08:00" --end "2026-06-08 10:00" --since "2026-05-28 00:00" --tf M1 --strategies 16 --exclude-cancelled --symbol XAUUSD.iux --compare-mt5-history --compare-csv --compare-xlsx --match-minutes 180 --match-entry-points 5
```

- S16 M1 context raw events: M1 `15`, M5 `7`, M15 `3`; kept M1 events in window after overlay/filter: `0`.
- Backtest P&L: `+0.00`.
- MT5 live rows loaded for S16: 0.
- Compare result: matched 0, live-only 0, backtest-only 0.
- Latest M1 run included SL Guard Group context TFs `M1`, `M5`, `M15`.
- Report: `excel_reports/backtest_compare/s16/compare_s16_M1_20260528_0800_20260608_1000.csv`.

M15 sanity command also passed:

```bash
python backtest_auto_trade.py --start "2026-05-28 08:00" --end "2026-06-08 10:00" --since "2026-05-28 00:00" --tf M15 --strategies 16 --exclude-cancelled --symbol XAUUSD.iux --compare-mt5-history --compare-csv --compare-xlsx --match-minutes 180 --match-entry-points 5
```

- S16 M15 context raw events: M1 `15`, M5 `7`, M15 `3`, M30 `1`, H1 `0`; kept M15 events in window after overlay/filter: `0`.
- Backtest P&L: `+0.00`; compare result: matched 0, live-only 0, backtest-only 0.
- Report: `excel_reports/backtest_compare/s16/compare_s16_M15_20260528_0800_20260608_1000.csv`.

Known remaining S16 gaps:

- Tested window 28/05 08:00 ถึง 08/06 10:00 ยังไม่มี live S16 rows; live S16 duplicate storm ที่เจอจริงอยู่หลัง window นี้ (09-10/06) ตาม update 11/06 ด้านล่าง.
- Post-window duplicate-storm sanity (`2026-06-09 00:00` to `2026-06-10 23:59`, M1) loaded 31 live S16 rows and replay kept 4 rows. The 4 current replay setups all matched live loosely, but 27 live-only rows remain, mostly repeated SELL entries closed by `SL Guard Group`; treat this as historical duplicate-storm/runtime-version drift rather than current replay under-producing normal signals.
- Post-window report: `excel_reports/backtest_compare/s16/compare_s16_M1_20260609_0000_20260610_2359.csv`.
- SL Guard Group overlay baseline exists, but it is still a bar/order-event approximation of shared runtime guard state.
- Replay duplicates the S16 time/Asian-range logic in `sim_s16_backtest.py`; future cleanup can expose a pure helper from `strategy16.py` to reduce drift risk.

S16 update 11/06/2026 (audit จาก live orders จริง):

- พบ duplicate storm: 09/06 19:46:52 SELL 13 ไม้ fill วินาทีเดียวกัน + 20:47 อีก 8 ไม้ (-226 USD/นาที) — TP drift จาก ATR ทำ scanner dup check หลุด
- Fix: one-shot dedup ต่อ (tf, side, killzone) ใน `s16_state["fired"]` + `S16_SL_ATR_BUFFER=0.5` (เดิม SL_BUFFER กลาง 2×ATR) + `S16_MAX_RISK_ATR_MULT=4.0`
- sim mirror ครบทั้ง 2 fix + flag `S16_KZ_ONE_SHOT` สำหรับ A/B
- sim A/B (SINCE 24/05, M1+M5+M15): OLD -145.51 → one-shot -173.11 → SLbuf1.0 -71.71 → **SLbuf0.5 -15.38 (ดีสุด)** → SLbuf0.3 -57.00
- ทุก config ยังติดลบ → `active_strategies[16] = False` (default OFF) — ผู้ใช้ต้องปิดใน Telegram ด้วยเพราะ state เดิม persist ค่า True

### S17

- [x] สร้าง/รวม replay ราย strategy baseline เข้ากับ `backtest_auto_trade.py`
- [x] รองรับ Sweep Sniper detect, session/PD/RSI gates, limit fill/cancel baseline
- [x] เทียบ MT5 history รายช่วง baseline และสร้าง CSV/XLSX
- [x] จด command ใน `commands_and_tips.md`

S17 runtime coverage audit (updated 2026-06-18):

| Feature | Runtime for S17 | Replay status | Note |
|---|---|---|---|
| S17 Sweep Sniper detect | apply | apply | Central replay calls pure `strategy17.detect_s17()` through `sim_s17_backtest.backtest_tf()`. |
| Session / PD / RSI gates | apply | apply | Detector reads restored `S17_*` config and receives historical BKK signal time. |
| Limit lifecycle | apply | partial | Replay models `S17_LIMIT_CANCEL_BARS`, fixed SL/TP, optional time stop, and conservative same-bar SL-before-TP. |
| Standalone recheck bypass | skip_s17 | skip_s17 | Runtime skips PD/trend/RSI fill recheck, entry candle, trail SL, Opposite Order, and limit guard for S17. |
| SL Guard | apply if enabled | partial | S17 keeps SL Guard; replay applies SL Guard Group close-on-activate overlay as a baseline. |

Evidence ล่าสุด:

```bash
python backtest_auto_trade.py --start "2026-05-28 08:00" --end "2026-06-08 10:00" --since "2026-05-28 00:00" --tf M1 --strategies 17 --exclude-cancelled --symbol XAUUSD.iux --compare-mt5-history --compare-csv --compare-xlsx --match-minutes 180 --match-entry-points 5
```

- S17 M1 replay raw events: 44; kept events in window: 22; Backtest P&L: `-5.46`.
- Latest M1 run included SL Guard Group context TFs `M1`, `M5`, `M15`; context raw events were M1 `44`, M5 `22`, M15 `7`.
- MT5 live rows loaded for S17: 0 in the tested baseline window.
- Compare result: matched 0, live-only 0, backtest-only 22.
- Reports:
  - `excel_reports/backtest_compare/s17/compare_s17_M1_20260528_0800_20260608_1000.csv`
  - `excel_reports/backtest_compare/s17/compare_s17_M1_20260528_0800_20260608_1000.xlsx`

Known remaining S17 gaps:

- No live S17 order in the tested MT5 history window, so P&L parity cannot be measured yet.
- Need exact per-TF/combined SL Guard nuances before S17 can be audit-grade when guard is active.

### S18

- [x] สร้าง/รวม replay ราย strategy baseline เข้ากับ `backtest_auto_trade.py`
- [x] รองรับ TJR/ICT detect, historical HTF bias slice, session/RSI gates, limit fill/cancel baseline
- [x] เทียบ MT5 history รายช่วง baseline และสร้าง CSV/XLSX
- [x] จด command ใน `commands_and_tips.md`

S18 runtime coverage audit (updated 2026-06-18):

| Feature | Runtime for S18 | Replay status | Note |
|---|---|---|---|
| S18 TJR/ICT detect | apply | apply | Central replay calls pure `strategy18.detect_s18()` through `sim_s18_backtest.backtest_tf()`. |
| HTF bias / session / RSI | apply | apply | Replay injects historical BKK signal time and sliced HTF rates to avoid look-ahead bias. |
| Limit lifecycle | apply | partial | Replay models `S18_LIMIT_CANCEL_BARS`, fixed SL/TP, and conservative same-bar SL-before-TP. |
| Standalone recheck bypass | skip_s18 | skip_s18 | Runtime skips PD/trend/RSI fill recheck, entry candle, trail SL, Opposite Order, and limit guard for S18. |
| SL Guard | apply if enabled | partial | S18 keeps SL Guard; replay applies SL Guard Group close-on-activate overlay as a baseline. |

Evidence ล่าสุด:

```bash
python backtest_auto_trade.py --start "2026-05-28 08:00" --end "2026-06-08 10:00" --since "2026-05-28 00:00" --tf M1 --strategies 18 --exclude-cancelled --symbol XAUUSD.iux --compare-mt5-history --compare-csv --compare-xlsx --match-minutes 180 --match-entry-points 5
python backtest_auto_trade.py --start "2026-05-28 08:00" --end "2026-06-08 10:00" --since "2026-05-28 00:00" --tf M5 --strategies 18 --exclude-cancelled --symbol XAUUSD.iux --compare-mt5-history --compare-csv --compare-xlsx --match-minutes 180 --match-entry-points 5
```

- S18 M1 replay raw events: 10; kept events in window: 4; Backtest P&L: `-13.15`.
- S18 M5 replay raw events: 0; kept events in window: 0; Backtest P&L: `+0.00`.
- MT5 live rows loaded for S18: 0 in both M1/M5 baseline windows.
- Latest M1 run included SL Guard Group context TFs `M1`, `M5`, `M15`; M5 run included `M1`, `M5`, `M15`, `M30`; overlay made no additional close in this window.
- Reports:
  - `excel_reports/backtest_compare/s18/compare_s18_M1_20260528_0800_20260608_1000.csv`
  - `excel_reports/backtest_compare/s18/compare_s18_M5_20260528_0800_20260608_1000.csv`

Known remaining S18 gaps:

- No live S18 order in the tested MT5 history window, so P&L parity cannot be measured yet.
- Need exact per-TF/combined SL Guard nuances before S18 can be audit-grade when guard is active.
- Scanner standalone bypass list was updated to include S18 in sweep/trend scan blocks.

### S19

- [x] สร้าง/รวม replay ราย strategy baseline เข้ากับ `backtest_auto_trade.py`
- [x] รองรับ Silver Bullet / Power of 3 / Breaker-BPR-FVG / NDOG baseline
- [x] เทียบ MT5 history รายช่วง baseline และสร้าง CSV/XLSX
- [x] จด command ใน `commands_and_tips.md`

S19 runtime coverage audit (updated 2026-06-18):

| Feature | Runtime for S19 | Replay status | Note |
|---|---|---|---|
| S19 ICT Advanced detect | apply | apply | Central replay calls pure `strategy19.detect_s19()` through `sim_s19_backtest.backtest_tf()`. |
| Silver Bullet / P3 / NDOG | apply | apply | Replay injects historical BKK signal time and uses S19 config gates. |
| Limit lifecycle | apply | partial | Replay models `S19_LIMIT_CANCEL_BARS`, fixed SL/TP, and conservative same-bar SL-before-TP. |
| Standalone recheck bypass | skip_s19 | skip_s19 | Runtime skips PD/trend/RSI fill recheck, entry candle, trail SL, Opposite Order, and limit guard for S19. |
| SL Guard | apply if enabled | partial | S19 keeps SL Guard; replay applies SL Guard Group close-on-activate overlay as a baseline. |

Evidence ล่าสุด:

```bash
python backtest_auto_trade.py --start "2026-05-28 08:00" --end "2026-06-08 10:00" --since "2026-05-28 00:00" --tf M1 --strategies 19 --exclude-cancelled --symbol XAUUSD.iux --compare-mt5-history --compare-csv --compare-xlsx --match-minutes 180 --match-entry-points 5
python backtest_auto_trade.py --start "2026-05-28 08:00" --end "2026-06-08 10:00" --since "2026-05-28 00:00" --tf M5 --strategies 19 --exclude-cancelled --symbol XAUUSD.iux --compare-mt5-history --compare-csv --compare-xlsx --match-minutes 180 --match-entry-points 5
```

- S19 M1 replay raw events: 31; kept events in window: 13; Backtest P&L: `-42.13`.
- S19 M5 replay raw events: 2; kept events in window: 1; Backtest P&L: `+19.56`.
- MT5 live rows loaded for S19: 0 in both M1/M5 baseline windows.
- Latest M1 run included SL Guard Group context TFs `M1`, `M5`, `M15`; M5 run included `M1`, `M5`, `M15`, `M30`; overlay made no additional close in this window.
- Reports:
  - `excel_reports/backtest_compare/s19/compare_s19_M1_20260528_0800_20260608_1000.csv`
  - `excel_reports/backtest_compare/s19/compare_s19_M5_20260528_0800_20260608_1000.csv`

Known remaining S19 gaps:

- No live S19 order in the tested MT5 history window, so P&L parity cannot be measured yet.
- Need exact per-TF/combined SL Guard nuances before S19 can be audit-grade when guard is active.
- Scanner standalone bypass list was updated to include S19 in sweep/trend scan blocks.

## ลำดับงานถัดไปที่แนะนำ

1. เติม runtime lifecycle overlay ที่ยังเป็น partial/gap: full shared pending/open order-state fidelity ระดับ unified simulator
2. รัน compare MT5 ซ้ำกับ strategy ที่มี live order เยอะเพื่อวัด P&L parity หลัง overlay
3. เมื่อราย strategy S1-S19 ครบและ lifecycle overlay สำคัญพร้อม ค่อยกลับมาทำ compare auto trade รวมทั้งระบบ

Latest system-context sanity:

```bash
python backtest_auto_trade.py --start "2026-05-28 08:00" --end "2026-06-08 10:00" --since "2026-05-28 00:00" --tf M15 --strategies 4,5,8 --exclude-cancelled --symbol XAUUSD.iux --compare-mt5-history --compare-csv --compare-xlsx --match-minutes 180 --match-entry-points 5
```

- Unified S4/S5/S8 runner processes shared pending/open state in one bar loop per TF and uses range-based MT5 fetch to replay SL Guard Group context TFs before filtering report output back to the requested TF.
- Context replay included `M1`, `M5`, `M15`, `M30`, and `H1` for this M15 sanity window; if a context TF has no overlapping MT5 history, it is skipped with a progress log instead of silently implying it was replayed.
- System-level Limit Guard overlay runs after S4/S5/S8 trades are merged; this sanity window had no additional cancels.
- System-level same-bar duplicate setup overlay runs after Limit Guard as a safety layer; this sanity window removed 6 duplicate S4/S5/S8 setup events.
- System-level Opposite Order overlay runs after Limit Guard overlay; this sanity window had no additional adjustments.
- Unified S4/S5/S8 SL Guard Group context overlay ran before requested-TF filtering and changed 3 M15 closes to `SL_GUARD_GROUP`.
- System-level SL Guard Group overlay runs after Opposite Order overlay; this sanity window had no additional closes after the unified context overlay.
- Kept M15 filled events: 26; Backtest P&L: `+16.85`.
- Compare result: matched 0, live-only 0, backtest-only 26.
- Report: `excel_reports/backtest_compare/s4-5-8/compare_s4-5-8_M15_20260528_0800_20260608_1000.csv`.

Latest S1-S5 unified sanity:

```bash
python backtest_auto_trade.py --start "2026-05-28 08:00" --end "2026-06-08 10:00" --since "2026-05-28 00:00" --tf M15 --strategies 1,2,3,4,5 --exclude-cancelled --symbol XAUUSD.iux --compare-mt5-history --compare-csv --compare-xlsx --match-minutes 180 --match-entry-points 5
```

- Unified S1-S5/S8 runner now supports selected S1/S2/S3/S4/S5 together in one same-TF pending/open state loop.
- For selected sets without S8, cross-TF SL Guard Group context is intentionally not replayed yet to keep S1-S5 same-TF sanity fast; system-level same-TF overlays still run after merge.
- S1 forward confirm and S1 zone/swing post-check are now replayed; PD Fibo Plus skip list uses `config.PDFIBOPLUS_SKIP_SIDS` across `scanner.py`, `trailing.py`, and replay for S1/S2/S3/S9/S10/S11/S13/S14/S15/S16/S17/S18/S19.
- M15 raw events: 709; kept after window/exclude/system overlays: 60; Backtest P&L: `+217.00`.
- Compare result: matched 22, mismatches 22, live-only 50, backtest-only 38.
- Report: `excel_reports/backtest_compare/s1-2-3-4-5/compare_s1-2-3-4-5_M15_20260528_0800_20260608_1000.csv`.

## Commands Verification ล่าสุด

หลังแก้ไฟล์นี้หรือ docs อื่น ให้รัน:

```bash
python check_mojibake.py
python verify_repo.py
```

หลังแก้ Python ให้เพิ่ม:

```bash
python -m py_compile backtest_auto_trade.py
```
