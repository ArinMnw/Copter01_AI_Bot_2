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
- [x] เพิ่ม optional `--hybrid-live-guard-context` และ suffix `_hybrid_guard`
- [x] เพิ่ม S14 normalized family diagnostics และ optional `--prefer-same-s14-family` พร้อม suffix `_s14_family`
- [x] อัปเดต `commands_and_tips.md` สำหรับ command/report/diagnostic ล่าสุด
- [ ] ทำ backtest ราย strategy ให้ครบทุกท่าก่อนกลับไป compare auto trade รวม

## Strategy Checklist

### S1

- [x] สร้าง/รวม replay ราย strategy baseline
- [ ] จำลอง zone mode, forward confirm, pending cancel, fill close ตาม runtime ให้ครบ
- [x] เทียบ MT5 history รายช่วง baseline
- [x] จด command ใน `commands_and_tips.md`

S1 runtime coverage audit (2026-06-09):

| Feature | Runtime for S1 | Replay status | Note |
|---|---|---|---|
| S1 detect / zone filter | apply | apply | Replay calls shared `strategy1.strategy_1()` and carries `s1_zone_meta`. |
| Pending limit lifecycle | apply | partial | Replay models pending fill, `cancel_bars`, fixed SL/TP with bar high/low. |
| S1 forward confirm | apply | gap | Runtime can cancel pending or close filled position if no S2/S3 confirm within 5 bars. |
| S1 zone post-check | apply | gap | Runtime can cancel pending outside zone and close losing filled position outside zone. |
| PD Fibo Plus | apply | gap | Runtime applies PD to S1; replay baseline does not yet replay PD close/cancel. |
| Limit Trend Recheck / Fill Trend Recheck | apply | gap | Runtime applies trend recheck to S1; replay baseline does not yet close from trend. |
| RSI Fill Recheck | apply if enabled | gap/off | Config is currently OFF in tested state. |
| Trail SL / Opposite / Limit Guard | apply if enabled | gap | Main live mismatch shows trail/guard lifecycle is still missing in S1 replay. |

Evidence ล่าสุด:

```bash
python backtest_auto_trade.py --start "2026-05-28 08:00" --end "2026-06-08 10:00" --tf M15 --strategies 1 --exclude-cancelled --symbol XAUUSD.iux --compare-mt5-history --compare-csv --compare-xlsx --match-minutes 180 --match-entry-points 5
```

- S1 replay raw events: 191; kept M15 events in window: 92.
- Backtest P&L: `-552.83`.
- MT5 live rows loaded: 431; after M15 filter: 28.
- Matched: 27; mismatches: 27; live-only: 1; backtest-only: 65.
- Matched P&L live `+156.75` | BT `-173.21` | diff `+329.96`.
- Largest mismatch groups: `PNL_DIFF_SAME_BUCKET SELL +195.92`, `TRAIL_SL_DIFF_MISSING_BT SELL +164.60`, `CLOSE_BUCKET_DIFF SELL -51.30`, `CLOSE_LIFECYCLE_PD SELL -16.11`, `LIVE_CLOSE_TREND_RECHECK BUY +31.40`.
- Report: `excel_reports/backtest_compare/s1/compare_s1_M15_20260528_0800_20260608_1000.csv`.

Known remaining S1 gaps:

- S1 replay baseline catches many entries but P&L parity is not ready because runtime lifecycle features still close/trail orders differently.
- Must add S1 forward confirm and post-create/post-fill zone lifecycle next.
- Must replay PD Fibo Plus and Fill Trend Recheck for S1 before using S1 P&L as audit-grade.
- Trail SL and SL Guard Group context are visible live mismatch sources and need lifecycle replay after S1-specific confirm/zone checks.

### S2

- [x] สร้าง/รวม replay ราย strategy baseline
- [ ] รองรับ FVG normal/parallel, confirm lookback, cancel bars, limit TP/SL break skip pattern 1 ให้ครบ
- [x] เทียบ MT5 history รายช่วง baseline
- [x] จด command ใน `commands_and_tips.md`

S2 runtime coverage audit (2026-06-09):

| Feature | Runtime for S2 | Replay status | Note |
|---|---|---|---|
| S2 FVG detect | apply | apply | Replay calls shared `strategy2.strategy_2()`. |
| S2 normal confirm lookback | apply | apply | Replay uses scanner `_find_recent_signal_confirmation()` plus swing fallback. |
| S2 FVG parallel intersection | apply | gap | Runtime intersects existing pending orders across TFs; baseline replay is single-TF normal path. |
| Pending limit lifecycle | apply | partial | Replay models pending fill, `cancel_bars`, fixed SL/TP with bar high/low. |
| PD Fibo Plus | apply | gap | Runtime has S2 gap-aware PD pass and can adjust entry to EQ/50%. |
| Limit Trend / Fill Trend Recheck | apply | gap | Runtime applies trend recheck to S2 pending/fill. |
| RSI Fill Recheck | apply if enabled | gap/off | Config is currently OFF in tested state. |
| Limit TP/SL Break Cancel | apply if enabled | gap/off | Config is currently OFF in tested state; runtime skips engulf pattern 1 when enabled. |
| Trail SL / Opposite / Limit Guard | apply if enabled | gap | Active shared lifecycle features are not replayed in baseline yet. |

Evidence ล่าสุด:

```bash
python backtest_auto_trade.py --start "2026-05-28 08:00" --end "2026-06-08 10:00" --tf M15 --strategies 2 --exclude-cancelled --symbol XAUUSD.iux --compare-mt5-history --compare-csv --compare-xlsx --match-minutes 180 --match-entry-points 5
```

- S2 replay raw events: 149; kept M15 events in window: 44.
- Backtest P&L: `-125.19`.
- MT5 live rows loaded: 418; after M15 filter: 29.
- Matched: 14; mismatches: 14; live-only: 15; backtest-only: 30.
- Matched P&L live `+95.05` | BT `-149.32` | diff `+244.37`.
- Largest mismatch groups: `CLOSE_LIFECYCLE_PD SELL +61.64`, `PNL_DIFF_SAME_BUCKET BUY +68.50`, `CLOSE_BUCKET_DIFF SELL +64.84`, `TRAIL_SL_DIFF_MISSING_BT SELL +74.36`, `LIVE_CLOSE_TREND_RECHECK SELL -24.97`.
- Report: `excel_reports/backtest_compare/s2/compare_s2_M15_20260528_0800_20260608_1000.csv`.

Known remaining S2 gaps:

- Need cross-TF replay to reproduce `FVG_PARALLEL` intersection/cancel/re-place behavior.
- Need PD Fibo Plus pending/fill lifecycle and S2 entry adjustment before P&L parity can be trusted.
- Need Fill Trend Recheck and shared trail/guard/opposite lifecycle; live mismatch already shows PD, trend, and trail sources.
- Compare summary currently has generic `*_s14_family=UNKNOWN` buckets for non-S14 rows; cosmetic only, but can be renamed later to avoid noise.

### S3

- [x] สร้าง/รวม replay ราย strategy baseline
- [ ] รองรับ DM/SP/Marubozu, confirm/lookback/filter ที่ runtime ใช้ให้ครบ
- [x] เทียบ MT5 history รายช่วง baseline
- [x] จด command ใน `commands_and_tips.md`

S3 runtime coverage audit (2026-06-09):

| Feature | Runtime for S3 | Replay status | Note |
|---|---|---|---|
| S3 DM/SP detect | apply | apply | Replay calls shared `strategy3.strategy_3()`. |
| S3 normal confirm lookback | apply | apply | Replay uses scanner `_find_recent_signal_confirmation()` plus swing fallback. |
| S3 Marubozu / No Engulf pending | apply | apply | Replay waits one closed bar and places limit only when color confirms. |
| Pending limit lifecycle | apply | partial | Replay models pending fill and fixed SL/TP with bar high/low. |
| PD Fibo Plus | apply | gap | Runtime applies PD Fibo Plus to S3 pending/fill. |
| Limit Trend / Fill Trend Recheck | apply | gap | Runtime applies trend recheck to S3 pending/fill. |
| RSI Fill Recheck | apply if enabled | gap/off | Config is currently OFF in tested state. |
| Trail SL / Opposite / Limit Guard | apply if enabled | gap | Active shared lifecycle features are not replayed in baseline yet. |

Evidence ล่าสุด:

```bash
python backtest_auto_trade.py --start "2026-05-28 08:00" --end "2026-06-08 10:00" --tf M15 --strategies 3 --exclude-cancelled --symbol XAUUSD.iux --compare-mt5-history --compare-csv --compare-xlsx --match-minutes 180 --match-entry-points 5
```

- S3 replay raw events: 191; kept M15 events in window: 127.
- Backtest P&L: `+36.88`.
- MT5 live rows loaded: 262; after M15 filter: 15.
- Matched: 13; mismatches: 13; live-only: 2; backtest-only: 114.
- Matched P&L live `-0.09` | BT `-49.64` | diff `+49.55`.
- Largest mismatch groups: `CLOSE_BUCKET_DIFF SELL -78.17`, `PNL_DIFF_SAME_BUCKET SELL +55.09`, `TRAIL_SL_DIFF_MISSING_BT SELL +64.14`, `CLOSE_LIFECYCLE_PD SELL +8.49`.
- Report: `excel_reports/backtest_compare/s3/compare_s3_M15_20260528_0800_20260608_1000.csv`.

Known remaining S3 gaps:

- Need PD Fibo Plus pending/fill lifecycle and Fill Trend Recheck; live rows already show PD close drift.
- Need shared trail/guard/opposite lifecycle; live mismatch has trail-source gaps.
- Need scan-time blocks/filters not yet modeled: sweep filter, trend scan block, adjacent same-sid block, and global runtime state interactions.
- Backtest-only count is high, so S3 baseline is entry-discovery only until lifecycle/filter layers are added.

### S4

- [x] สร้าง/รวม replay ราย strategy baseline
- [x] รองรับนัยยะสำคัญ FVG และ swing helper ที่เกี่ยวข้อง baseline
- [x] เทียบ MT5 history รายช่วง baseline
- [x] จด command ใน `commands_and_tips.md`

S4 runtime coverage audit (2026-06-09):

| Feature | Runtime for S4 | Replay status | Note |
|---|---|---|---|
| S4 significant FVG detect | apply | apply | Replay calls shared `strategy4.strategy_4()`. |
| Pending limit lifecycle | apply | partial | Replay models pending fill and fixed SL/TP with bar high/low. |
| PD Fibo Plus | apply | gap | Runtime applies PD Fibo Plus to S4 pending/fill. |
| Limit Trend / Fill Trend Recheck | apply | gap | Runtime applies trend recheck to S4 pending/fill. |
| RSI Fill Recheck | apply if enabled | gap/off | Config is currently OFF in tested state. |
| Trail SL / Opposite / Limit Guard | apply if enabled | gap | Active shared lifecycle features are not replayed in baseline yet. |

Evidence ล่าสุด:

```bash
python backtest_auto_trade.py --start "2026-05-28 08:00" --end "2026-06-08 10:00" --since "2026-05-28 00:00" --tf M15 --strategies 4 --exclude-cancelled --symbol XAUUSD.iux --compare-mt5-history --compare-csv --compare-xlsx --match-minutes 180 --match-entry-points 5
```

- S4 replay raw events: 10; kept M15 events in window: 8.
- Backtest P&L: `+81.44`.
- MT5 live rows loaded: 3; after M15 filter: 0.
- Compare result: matched 0, live-only 0, backtest-only 8.
- Report: `excel_reports/backtest_compare/s4/compare_s4_M15_20260528_0800_20260608_1000.csv`.

Known remaining S4 gaps:

- M15 sanity has no live S4 order, so P&L parity cannot be measured on this TF.
- Need rerun S4 on TFs that actually have live rows before marking audit-grade parity.
- Need PD Fibo Plus, Fill Trend Recheck, and shared trail/guard/opposite lifecycle for full parity.

### S5

- [x] สร้าง/รวม replay ราย strategy baseline
- [x] ตรวจ runtime ว่า S5 เป็น limit strategy ปกติและ currently OFF ใน restored config
- [x] เทียบ MT5 history รายช่วง baseline
- [x] จด command ใน `commands_and_tips.md`

S5 runtime coverage audit (2026-06-09):

| Feature | Runtime for S5 | Replay status | Note |
|---|---|---|---|
| S5 scalping detect | apply | apply | Replay calls shared `strategy5.strategy_5()`. |
| S5 internal filters | apply | partial | Runtime code uses current wall-clock hour for no-trade filter; replay currently follows the shared helper, so historical no-trade hour can drift. |
| Pending limit lifecycle | apply | partial | Replay models pending fill and fixed SL/TP with bar high/low. |
| PD Fibo Plus | apply | gap | Runtime applies PD Fibo Plus to S5 pending/fill. |
| Limit Trend / Fill Trend Recheck | apply | gap | Runtime applies trend recheck to S5 pending/fill. |
| RSI Fill Recheck | apply if enabled | gap/off | Config is currently OFF in tested state. |
| Trail SL / Opposite / Limit Guard | apply if enabled | gap | Active shared lifecycle features are not replayed in baseline yet. |

Evidence ล่าสุด:

```bash
python backtest_auto_trade.py --start "2026-05-28 08:00" --end "2026-06-08 10:00" --since "2026-05-28 00:00" --tf M15 --strategies 5 --exclude-cancelled --symbol XAUUSD.iux --compare-mt5-history --compare-csv --compare-xlsx --match-minutes 180 --match-entry-points 5
```

- S5 selected but OFF in restored config; replay still runs for requested strategy audit.
- S5 replay raw events: 29; kept M15 events in window: 21.
- Backtest P&L: `+91.83`.
- MT5 live rows loaded for S5: 0.
- Compare result: matched 0, live-only 0, backtest-only 21.
- Report: `excel_reports/backtest_compare/s5/compare_s5_M15_20260528_0800_20260608_1000.csv`.

Known remaining S5 gaps:

- No live S5 order in the tested MT5 history window, so P&L parity cannot be measured yet.
- S5 time filter in `strategy5.py` uses `datetime.now()` instead of replay bar time; this should be refactored to a pure helper before audit-grade historical S5 replay.
- Need PD Fibo Plus, Fill Trend Recheck, and shared trail/guard/opposite lifecycle for full parity.

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

S8 runtime coverage audit (2026-06-09):

| Feature | Runtime for S8 | Replay status | Note |
|---|---|---|---|
| S8 swing-limit detect | apply | apply | Replay calls shared `strategy8.strategy_8()` and handles `MULTI` orders. |
| Dual-side pending placement | apply | apply | Replay can place both BUY and SELL S8 limits from one scan result. |
| Delayed SL arm | apply | partial | Replay models default breakout arm and fill fallback; time/price delay modes are approximated. |
| S8 swing-change cancel | apply | gap | Runtime cancels S8 pending when the reference swing changes; replay does not yet. |
| Limit Sweep follow-up S8 | apply if enabled | gap/off | Config is currently OFF in tested state; runtime can create S8 after sweep management. |
| PD Fibo Plus | apply | gap | Runtime applies PD Fibo Plus to S8 pending/fill. |
| Limit Trend / Fill Trend Recheck | apply | gap | Runtime applies trend recheck to S8 pending/fill. |
| Trail SL / Opposite / Limit Guard | apply if enabled | gap | Active shared lifecycle features are not replayed in baseline yet. |

Evidence ล่าสุด:

```bash
python backtest_auto_trade.py --start "2026-05-28 08:00" --end "2026-06-08 10:00" --since "2026-05-28 00:00" --tf M15 --strategies 8 --exclude-cancelled --symbol XAUUSD.iux --compare-mt5-history --compare-csv --compare-xlsx --match-minutes 180 --match-entry-points 5
```

- S8 selected but OFF in restored config; replay still runs for requested strategy audit.
- S8 replay raw events: 818; kept M15 events in window: 572.
- Backtest P&L: `-300.58`.
- MT5 live rows loaded for S8: 0.
- Compare result: matched 0, live-only 0, backtest-only 572.
- Report: `excel_reports/backtest_compare/s8/compare_s8_M15_20260528_0800_20260608_1000.csv`.

Known remaining S8 gaps:

- No live S8 order in the tested MT5 history window, so P&L parity cannot be measured yet.
- Replay over-produces heavily because swing-change cancel, PD Fibo Plus, trend recheck, and guard lifecycle are not replayed yet.
- Need add S8 pending cancel when swing changes before using S8 baseline for audit-grade entry count.
- Need model Limit Sweep follow-up S8 when `LIMIT_SWEEP` is enabled.

### S9

- [x] สร้าง/รวม replay ราย strategy baseline
- [x] รองรับ RSI divergence และ skip/recheck rules หลักตาม runtime
- [x] เทียบ MT5 history รายช่วง baseline
- [x] จด command ใน `commands_and_tips.md`

S9 runtime coverage audit (2026-06-09):

| Feature | Runtime for S9 | Replay status | Note |
|---|---|---|---|
| S9 RSI divergence detect | apply | apply | Replay calls shared `strategy9.strategy_9()`. |
| S9 setup dedup / passed-entry | apply | partial | Replay dedups pivot `setup_sig` and invalidates setup when signal-bar close has passed limit entry. |
| Pending limit lifecycle | apply | partial | Replay models pending fill and fixed SL/TP with bar high/low. |
| PD Fibo Plus | skip_s9 | skip_s9 | Runtime skips S9 PD Fibo Plus. |
| Limit Trend / Fill Trend Recheck | skip_s9 | skip_s9 | Runtime skips S9 trend recheck. |
| RSI Fill Recheck | skip_s9 | skip_s9 | Runtime skips S9 RSI fill recheck. |
| Strong Trend Block | apply if enabled | gap/off | Config is currently OFF in tested state. |
| Trail SL / Opposite / Limit Guard | apply if enabled | gap | Active shared lifecycle features are not replayed in baseline yet. |

Evidence ล่าสุด:

```bash
python backtest_auto_trade.py --start "2026-05-28 08:00" --end "2026-06-08 10:00" --since "2026-05-28 00:00" --tf M15 --strategies 9 --exclude-cancelled --symbol XAUUSD.iux --compare-mt5-history --compare-csv --compare-xlsx --match-minutes 180 --match-entry-points 5
```

- S9 selected but OFF in restored config; replay still runs for requested strategy audit.
- S9 replay raw events: 8; kept M15 events in window: 6.
- Backtest P&L: `+31.11`.
- MT5 live rows loaded: 55; after M15 filter: 0.
- Compare result: matched 0, live-only 0, backtest-only 6.
- Report: `excel_reports/backtest_compare/s9/compare_s9_M15_20260528_0800_20260608_1000.csv`.

Known remaining S9 gaps:

- M15 sanity has no live S9 order, so P&L parity cannot be measured on this TF.
- Need rerun S9 on TFs that actually have live rows (likely M1/M5/H1) before marking audit-grade parity.
- Need shared trail/guard/opposite lifecycle if those features are active for S9.

### S10

- [x] มี `backtest_s10_timewindow.py`
- [x] มี `check_s10_parent.py`
- [x] มี central replay path ใน `backtest_auto_trade.py`
- [x] รองรับ compare MT5 history และ CSV/XLSX report
- [x] มี progress log ระหว่างรัน
- [x] จด command หลักใน `commands_and_tips.md`
- [x] Audit ให้ครบทุก config runtime ที่พี่ระบุ: Trail SL, reversal trail, entry candle mode/TP, opposite order, limit sweep, delay SL, limit TP/SL break, limit guard, engulf minimum, trend filter
- [x] รัน compare ช่วงยาวล่าสุดหลัง audit แล้วบันทึกผล

S10 runtime coverage audit (2026-06-09):

| Feature | Runtime for S10 | Replay status | Note |
|---|---|---|---|
| CRT detect / model orders | apply | apply | Uses `strategy10.strategy_10()` in replay, including HTF arm and LTF model orders. |
| S10 sibling cancel | apply | apply | Replay closes sibling pending after one model fills. |
| S10 sweep / structure / parent-touch cancel | apply | apply | Replay has S10 invalidation checks. |
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

S10 latest evidence (2026-06-09):

```bash
python backtest_auto_trade.py --start "2026-05-28 08:00" --end "2026-06-08 10:00" --tf H1 --strategies 10 --exclude-cancelled --symbol XAUUSD.iux --compare-mt5-history --compare-csv --compare-xlsx --match-minutes 180 --match-entry-points 5
```

Result after fixing S10 live TF filter to match exact HTF (`H1`) instead of any `M1` child comment:

- Runtime coverage warning is shown before replay.
- S10 replay raw events: 431; kept in window: 18.
- Backtest P&L: `+25.88`.
- MT5 live rows loaded: 54; after exact `H1` filter: 7.
- Matched: 1.
- Mismatches: 1.
- Live only: 6.
- Backtest only: 17.
- Matched P&L diff: `-95.96`.
- Report: `excel_reports/backtest_compare/s10/compare_s10_H1_20260528_0800_20260608_1000.csv`.

Known remaining S10 gaps:

- Old live orders in this window still include at least one S10 close reason `PD Zone fill...`; current runtime now skips PD for S10, so this is expected historical drift unless comparing only after the PD skip fix date.
- Replay gaps only matter if future config enables them: RSI Fill Recheck, Delay SL, Strong Trend Block, Limit Sweep.

### S11

- [x] สร้าง/รวม replay ราย strategy baseline
- [ ] รองรับ Fibo S1 และ PD/recheck skip/apply ตาม runtime ล่าสุดให้ครบ
- [x] เทียบ MT5 history รายช่วง baseline
- [x] จด command ใน `commands_and_tips.md`

S11 runtime coverage audit (2026-06-09):

| Feature | Runtime for S11 | Replay status | Note |
|---|---|---|---|
| S1 anchor hook | apply | apply | Replay calls `strategy1.strategy_1()` and `strategy11.record_s1_pattern()`. |
| S11 Fibo state/cascade | apply | apply | Replay calls shared `strategy11.strategy_11()`. |
| Pending limit lifecycle | apply | partial | Replay models pending fill and fixed SL/TP with bar high/low. |
| PD Fibo Plus | apply | gap | Runtime applies PD Fibo Plus to S11 pending/fill. |
| Limit Trend / RSI Recheck | skip_s11 | skip_s11 | Runtime skips S11 in pending trend and RSI fill recheck. |
| Strong Trend Block | apply if enabled | gap/off | Config is currently OFF in tested state. |
| Duplicate/adjacent guards | apply | gap | Runtime avoids duplicate pending setups and adjacent same-SID bars. |
| S1 linked cleanup | apply | gap | Runtime can cancel/close linked S11 when S1 forward lifecycle invalidates. |
| Trail SL / Opposite / Limit Guard | apply if enabled | gap | Active shared lifecycle features are not replayed in baseline yet. |

Evidence ล่าสุด:

```bash
python backtest_auto_trade.py --start "2026-05-28 08:00" --end "2026-06-08 10:00" --since "2026-05-28 00:00" --tf M15 --strategies 11 --exclude-cancelled --symbol XAUUSD.iux --compare-mt5-history --compare-csv --compare-xlsx --match-minutes 180 --match-entry-points 5
```

- S11 replay optimized to use rolling `TF_LOOKBACK + 6` strategy window, matching scanner-style input and avoiding the earlier 240s timeout from ever-growing full-history slices.
- S11 replay raw events: 102; kept M15 events in window: 77.
- Backtest P&L: `+177.92`.
- MT5 live rows loaded: 104; after M15 filter: 11.
- Matched: 10; mismatches: 10; live-only: 1; backtest-only: 67.
- Matched P&L live `-1.67` | BT `+46.66` | diff `-48.33`.
- Largest mismatch groups: `CLOSE_LIFECYCLE_PD SELL +19.10`, `CLOSE_BUCKET_DIFF SELL -69.14`, `LIVE_CLOSE_TREND_RECHECK BUY +5.60`, `PNL_DIFF_SAME_BUCKET BUY -3.89`.
- Report: `excel_reports/backtest_compare/s11/compare_s11_M15_20260528_0800_20260608_1000.csv`.

Known remaining S11 gaps:

- Need PD Fibo Plus pending/fill lifecycle before P&L parity can be trusted.
- Need duplicate pending setup guard and adjacent same-SID block; current baseline over-produces backtest-only rows.
- Need S1 linked cleanup when S1 forward lifecycle invalidates the anchor/order.
- Live history contains a `Fill Trend Recheck` close on S11 even though current runtime skip table says S11 skips trend/RSI recheck; this is likely historical/runtime-version drift and should be rechecked on post-fix orders.

### S12

- [x] สร้าง/รวม replay ราย strategy baseline
- [x] รองรับ standalone/range behavior และ skip limit guard/notifications ตาม runtime baseline
- [x] เทียบ MT5 history รายช่วง baseline
- [x] จด command ใน `commands_and_tips.md`

S12 runtime coverage audit (2026-06-09):

| Feature | Runtime for S12 | Replay status | Note |
|---|---|---|---|
| S12 M5 range zone scan | apply | apply | Replay uses `strategy12` zone helpers on M5 bars. |
| S12 market lifecycle | apply | partial | Replay approximates entry/close with M5 bar close instead of live bid/ask tick. |
| S12 order count / side state | apply | apply | Replay tracks side, order count, and last entry price. |
| S12 breakout / flip close-all | apply | partial | Replay closes open S12 rows on breakout/flip using M5 close. |
| S12 SL cooldown | apply | gap | Replay does not yet enforce wall-time cooldown after SL. |
| PD / Trend / Limit Guard | skip_s12_or_market | skip_s12_or_market | S12 is market/standalone and runtime skips normal pending limit guard path. |

Evidence ล่าสุด:

```bash
python backtest_auto_trade.py --start "2026-05-28 08:00" --end "2026-06-08 10:00" --since "2026-05-28 00:00" --tf M5 --strategies 12 --exclude-cancelled --symbol XAUUSD.iux --compare-mt5-history --compare-csv --compare-xlsx --match-minutes 180 --match-entry-points 5
```

- S12 selected but OFF in restored config; replay still runs for requested strategy audit.
- S12 replay raw events: 23; kept M5 events in window: 20.
- Backtest P&L: `+42.04`.
- MT5 live rows loaded for S12: 0.
- Compare result: matched 0, live-only 0, backtest-only 20.
- Report: `excel_reports/backtest_compare/s12/compare_s12_M5_20260528_0800_20260608_1000.csv`.

Known remaining S12 gaps:

- No live S12 order in the tested MT5 history window, so P&L parity cannot be measured yet.
- Need live tick bid/ask/spread replay for audit-grade S12 because current baseline uses M5 close.
- Need SL cooldown replay; current baseline can over-trade after SL compared with runtime.

### S13

- [x] สร้าง/รวม replay ราย strategy
- [x] รองรับ EzAlgo baseline, TP split, same-side skip, opposite flip, skip rules หลักตาม runtime
- [x] เทียบ MT5 history รายช่วง baseline
- [x] จด command ใน `commands_and_tips.md`

S13 runtime coverage audit (2026-06-09):

| Feature | Runtime for S13 | Replay status | Note |
|---|---|---|---|
| S13 EzAlgo detect | apply | apply | Replay calls shared `strategy13.strategy_13()`. |
| S13 market/split TP | apply | partial | Replay opens split TP rows as market rows; live can mix market and limit depending tick vs entry. |
| S13 opposite flip | apply | apply | Replay closes opposite S13 rows on same TF before new signal. |
| PD Fibo Plus | skip_s13 | skip_s13 | Runtime skips SIDs 9,10,13,14,15,16. |
| Fill Trend Recheck | apply | gap | Active runtime feature; replay baseline does not close S13 from trend yet. |
| RSI Fill Recheck | apply if enabled | gap/off | Config is currently OFF in tested state. |
| Trail SL | skip_s13 | skip_s13 | Runtime skips standalone S13. |
| Opposite Order | skip_s13 | skip_s13 | Runtime filters S13 positions/orders. |

Evidence ล่าสุด:

```bash
python backtest_auto_trade.py --start "2026-05-28 08:00" --end "2026-06-08 10:00" --tf M15 --strategies 13 --exclude-cancelled --symbol XAUUSD.iux --compare-mt5-history --compare-csv --compare-xlsx --match-minutes 180 --match-entry-points 5
```

- S13 replay raw events: 200; kept M15 events in window: 112.
- Backtest P&L: `-85.47`.
- MT5 live rows loaded for S13: 0.
- Compare result: matched 0, live-only 0, backtest-only 112.
- Report: `excel_reports/backtest_compare/s13/compare_s13_M15_20260528_0800_20260608_1000.csv`.

Known remaining S13 gaps:

- No live S13 order in the tested MT5 history window, so P&L parity cannot be measured yet.
- Fill Trend Recheck is active in runtime for S13 but not replayed yet.
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
- [ ] ไล่ gap ที่เหลือ: `SELL_SWEEP` live-only, `SELL_ENGULF` drift, `TRAIL_SL_DIFF_SOURCE`
- [x] Audit ให้ครบทุก config runtime ที่พี่ระบุเหมือน S10

S14 runtime coverage audit (2026-06-09):

| Feature | Runtime for S14 | Replay status | Note |
|---|---|---|---|
| S14 Sweep/Engulf detect | apply | apply | Replay calls shared `strategy14.strategy_14()`. |
| S14 market fill | apply | partial | Replay fills at strategy market reference price on the detect bar; live fills at broker tick price. |
| S14 Flip | apply | apply | Replay closes opposite S14 exposure on same TF before new order. |
| S14 exit color rule | apply | apply | Sweep checks entry TF; engulf checks mapped HTF/secondary HTF. |
| Trail SL / reversal nuances | apply | partial | Replay models engulf trail across `TRAIL_GROUPS` with granular lifecycle price path, but focus/opposite/reversal nuances can still drift. |
| SL Guard Group overlay | apply | partial | Replay approximates close-on-activate from replayed TF context. |
| PD Fibo Plus | skip_s14 | skip_s14 | Runtime skips SIDs 9,10,13,14,15,16; replay was corrected to skip S14. |
| Limit Trend Recheck | skip_s14 | skip_s14 | Runtime skips S14. |
| RSI Fill Recheck | skip_s14 | skip_s14 | Runtime skips S14. |
| Entry Candle | skip_s14 | skip_s14 | Runtime skips S14 standalone/market flow. |
| Opposite Order | skip_s14 | skip_s14 | Runtime filters S14 positions/orders. |
| Limit Guard | skip_s14 | skip_s14 | S14 uses market orders. |
| Delay SL | skip_s14 | skip_s14 | S14 does not use delayed pending SL. |
| Strong Trend Block | apply if enabled for S14 | gap | Config is currently OFF; replay must be added before enabling this for S14 backtests. |

Evidence ล่าสุด:

```bash
python backtest_auto_trade.py --start "2026-05-28 08:00" --end "2026-06-08 10:00" --tf M15 --strategies 14 --exclude-cancelled --symbol XAUUSD.iux --compare-mt5-history --compare-csv --compare-xlsx --match-minutes 180 --match-entry-points 5
```

ผล baseline ล่าสุด:

- S14 replay raw events by context TF: M1=269, M5=150, M15=43, M30=26, H1=10
- S14 replay kept M15 events in window: 29
- Backtest P&L: `+220.09`
- MT5 live rows loaded: 435; after `M15` filter: 32
- Matched: 14
- Mismatches: 13
- Live only: 18
- Backtest only: 15
- Matched P&L diff: `-2.67`
- Main mismatch gap after market-fill fix: `S14_FAMILY_DIFF SELL count=5 pnl=-15.82`
- Remaining explicit trail-source gap after family-first classifier: `TRAIL_SL_DIFF_SOURCE SELL count=1 pnl=-17.88`
- Lifecycle note: granular price path now checks current SL/TP before applying newly trailed SL, so same-bar trail look-ahead is avoided.
- Market-fill note: S14 market replay now fills on the detect bar using strategy reference entry instead of next-bar open, matching runtime timing more closely.
- Report: `excel_reports/backtest_compare/s14/compare_s14_M15_20260528_0800_20260608_1000.csv`

Known remaining S14 gaps:

- `SELL_SWEEP` live-only still largest family: live `SELL_SWEEP` count 6, BT `SELL_SWEEP` count 5.
- Historical live duplicates remain in old rows, for example live has extra S14 fills 15 minutes after/near a replayed signal (`NEAREST_ALREADY_MATCHED_OR_GREEDY`). Current `strategy14.py` de-duplicates these, so this is tracked as historical/live-version drift unless reproduced after the current fix date.
- `SELL_ENGULF` mismatch/drift remains; family-first classifier now reports these as `S14_FAMILY_DIFF` before trail-source drift.
- `TRAIL_SL_DIFF_SOURCE` remains on 1 SELL row after excluding family mismatch.
- SL Guard Group / Fill Trend Recheck close rows remain because replay only approximates cross-TF runtime state.
- Old live orders still contain `PD Zone fill...` close reasons in this historical window; current runtime and replay now skip PD for S14, so compare after the skip-fix date should be cleaner.

Diagnostic strict-family:

```bash
python backtest_auto_trade.py --start "2026-05-28 08:00" --end "2026-06-08 10:00" --tf M15 --strategies 14 --exclude-cancelled --symbol XAUUSD.iux --compare-mt5-history --compare-csv --compare-xlsx --match-minutes 180 --match-entry-points 5 --prefer-same-s14-family
```

ผล strict-family แย่กว่า baseline (`diff=-24.82`) จึงเก็บเป็น diagnostic เท่านั้น ไม่เปิด default

### S15

- [x] สร้าง/รวม replay ราย strategy
- [x] รองรับ VP absorption/value-area zone, pending limit fill baseline, skip RSI/trend/PD ตาม runtime
- [x] เทียบ MT5 history รายช่วง
- [x] จด command ใน `commands_and_tips.md`

S15 runtime coverage audit (2026-06-09):

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

Evidence ล่าสุด:

```bash
python backtest_auto_trade.py --start "2026-05-28 08:00" --end "2026-06-08 10:00" --tf M15 --strategies 15 --exclude-cancelled --symbol XAUUSD.iux --compare-mt5-history --compare-csv --compare-xlsx --match-minutes 180 --match-entry-points 5
```

- S15 replay raw events: 10; kept M15 events in window: 6.
- Backtest P&L: `-18.87`.
- MT5 live rows loaded: 45; after M15 filter: 2.
- Matched: 1; mismatches: 1; live-only: 1; backtest-only: 5.
- Matched P&L diff: `+9.46`.
- Report: `excel_reports/backtest_compare/s15/compare_s15_M15_20260528_0800_20260608_1000.csv`.

Known remaining S15 gaps:

- Replay does not yet apply SL Guard Group context; live-only M15 row closed by `SL Guard Group`.
- Limit fill/TP/SL ordering is bar-based, so broker tick ordering and spread can drift.

### S16

- [x] สร้าง/รวม replay ราย strategy
- [x] รองรับ AMD x iFVG baseline และ skip/recheck rules หลักตาม runtime
- [x] เทียบ MT5 history รายช่วง baseline
- [x] จด command ใน `commands_and_tips.md`

S16 runtime coverage audit (2026-06-09):

| Feature | Runtime for S16 | Replay status | Note |
|---|---|---|---|
| S16 AMD/iFVG detect | apply | apply | Replay injects simulated BKK time and Asian range instead of using `config.now_bkk()`. |
| S16 limit lifecycle | apply | partial | Replay models pending limit fill then fixed SL/TP; broker tick ordering can drift. |
| PD Fibo Plus | skip_s16 | skip_s16 | Runtime skips SIDs 9,10,13,14,15,16. |
| Limit Trend Recheck | skip_s16 | skip_s16 | Runtime skips S16 fill trend recheck. |
| Trail/Opposite Order | skip_s16 | skip_s16 | Runtime filters standalone S16 from Trail SL and Opposite Order. |

Evidence ล่าสุด:

```bash
python backtest_auto_trade.py --start "2026-05-28 08:00" --end "2026-06-08 10:00" --tf M1 --strategies 16 --exclude-cancelled --symbol XAUUSD.iux --compare-mt5-history --compare-csv --compare-xlsx --match-minutes 180 --match-entry-points 5
```

- S16 M1 replay raw events: 42; kept events in window: 35.
- Backtest P&L: `+12.08`.
- MT5 live rows loaded for S16: 0.
- Compare result: matched 0, live-only 0, backtest-only 35.
- Report: `excel_reports/backtest_compare/s16/compare_s16_M1_20260528_0800_20260608_1000.csv`.

M15 sanity command also passed:

```bash
python backtest_auto_trade.py --start "2026-05-28 08:00" --end "2026-06-08 10:00" --tf M15 --strategies 16 --exclude-cancelled --symbol XAUUSD.iux --compare-mt5-history --compare-csv --compare-xlsx --match-minutes 180 --match-entry-points 5
```

- S16 M15 replay raw events: 2; Backtest P&L: `-74.66`.
- Report: `excel_reports/backtest_compare/s16/compare_s16_M15_20260528_0800_20260608_1000.csv`.

Known remaining S16 gaps:

- ~~No live S16 order in the tested MT5 history window~~ → live orders เกิดแล้ว 08-10/06: **35 ไม้ -510.54 USD** (ดู update 11/06 ด้านล่าง)
- Replay duplicates the S16 time/Asian-range logic in `sim_s16_backtest.py`; future cleanup can expose a pure helper from `strategy16.py` to reduce drift risk.

S16 update 11/06/2026 (audit จาก live orders จริง):

- พบ duplicate storm: 09/06 19:46:52 SELL 13 ไม้ fill วินาทีเดียวกัน + 20:47 อีก 8 ไม้ (-226 USD/นาที) — TP drift จาก ATR ทำ scanner dup check หลุด
- Fix: one-shot dedup ต่อ (tf, side, killzone) ใน `s16_state["fired"]` + `S16_SL_ATR_BUFFER=0.5` (เดิม SL_BUFFER กลาง 2×ATR) + `S16_MAX_RISK_ATR_MULT=4.0`
- sim mirror ครบทั้ง 2 fix + flag `S16_KZ_ONE_SHOT` สำหรับ A/B
- sim A/B (SINCE 24/05, M1+M5+M15): OLD -145.51 → one-shot -173.11 → SLbuf1.0 -71.71 → **SLbuf0.5 -15.38 (ดีสุด)** → SLbuf0.3 -57.00
- ทุก config ยังติดลบ → `active_strategies[16] = False` (default OFF) — ผู้ใช้ต้องปิดใน Telegram ด้วยเพราะ state เดิม persist ค่า True

## ลำดับงานถัดไปที่แนะนำ

1. เลือก strategy ถัดไปที่มี live order เยอะที่สุดจาก MT5 history แล้วสร้าง replay ราย strategy
2. เติม runtime features ที่ยังเป็น partial/gap ของ S13/S15/S16 ถ้าเริ่มมี live order ให้เทียบ
3. เริ่มกลุ่ม S11/S12 หรือ S1-S5 ตาม live history density
4. เมื่อ S1-S16 ราย strategy ครบ ค่อยกลับมาทำ compare auto trade รวมทั้งระบบ

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
