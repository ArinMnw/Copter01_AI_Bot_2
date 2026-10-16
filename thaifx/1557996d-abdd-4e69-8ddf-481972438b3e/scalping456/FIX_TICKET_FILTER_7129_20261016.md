# Scalping456 7129 — ticket-history fallback repair

Status: **SOURCE READY / USER RESTART REQUIRED / LIVE SUBMISSION NOT YET VERIFIED**.

Update17:54: user restarted; new code cleared both old tickets and submitted a real1.03lot pair. SELL filled and closedSL net-105.47; opposite BUY cancelled. Daily-20USD gate is active. A separate unresolved known_orders ticket4886153546 remains, so next-cycle/full-lifecycle certification is withheld. [Post-restart verification](POST_RESTART_7129_20261016.md). The source-ready/handoff statements below describe the earlier17:46 checkpoint, not current live status.

User authorized this repair after the 17:31 diagnosis: “แก้ได้เลยต้องออกออเดอร์ให้ได้”. The user still performs the 7129 bot restart. No agent restart, live state reset or order_send was performed.

## Changes

- `demo_scalping456.py:_order_deals`: if native ticket-filter history returns None, query the order's raw broker setup/done epoch interval and filter exact DEAL_ORDER. If that interval is unavailable/missing, query candidate position identifiers and again require exact original DEAL_ORDER. A guessed ID or empty guessed-position history is never proof of an unfilled cancellation.
- Existing Exness-stub checks still require the target profile, magic0 final-order stub, matching entry magic995456/symbol/side, positive unique position ID/deal tickets, and compatible actual fill volume. Foreign, ambiguous, unavailable or incomplete proof keeps new entry blocked.
- Closed accounting uses the canonical position identifier, so two ticket aliases cannot book the same full close twice. Persisted legacy close keys are still recognized.
- No change to entry geometry, trailing, exposure slots, identity guards, risk sizing, strategy toggle, $20 daily new-entry loss gate, or uncertain-send latch. No configuration/profile state changes.

## Verification

- **78 unit tests PASS** (62 previous +16 regression cases), including the observed invalid ticket filter; already-accounted closes; distinct order/position IDs; partial fills/exits; cancelled-stub acknowledgements; foreign/ambiguous proof; unavailable history; restart and exactly-once costs.
- Python compile PASS for adapter, tests and offline replay helper.
- Reconstructing the exact prior source matches SHA256 `2cabf54eb4a7b9ea59d98c63d4c53d76437ecd2414a683c6673e23ca9933a859`. AST comparison confirms only `_order_deals`, `_stub_position_identifier`, `_resolve_closes` changed. Params, preflight, send, entry, trailing and scheduling logic are unchanged.
- New adapter SHA256: `e1852f77a006b9169229675dbb53d997f81bcbd41aaeda3d8ed654a4d1e61ea9`.
- New tests SHA256: `c5795d887215380f8f9ef261901b2c7ccbef31137b1437c842047a2591b79371`.
- Scoped UTF-8/LF/mojibake check is used. Full `verify_repo.py` is not run because even with explicit filenames it unconditionally recursively scans the whole repo and portable MT5 trees; direct compilation plus scoped `check_mojibake.find_issues` covers edited artifacts.

## Independent native read-only proof — 2026-10-16 17:46:04.969 BKK

Exact terminal was already running before diagnostic initialize. Login434237129/serverExness-MT5Trial7/demo/hedging/path/connected matched. Main79252 and terminal56028 remained unchanged. Own positions0/pending0; journal4873 bytes unchanged and valid prefix. Bot is still on the pre-repair module loaded at15:55.

Native ticket-filter queries still return `(-2, Terminal: Invalid params)`. Both bounded raw-epoch queries return Success; the **new code's actual ownership method** resolves4878801646 and4878801649 correctly with no state mutation or sends.

Native `order_check` accepts both hypothetical BUY_STOP and SELL_STOP requests: retcode0/commentDone. Snapshot equity10403.17USD; each preview1.04lot has modeled104USD initial-SL price loss against104.0317USD budget. Preview prices/lots are not live orders and will be recalculated after restart. `order_check` is validation only, not an execution/fill guarantee.

[Native identity/history/ownership and order_check evidence](data/forward_7129_20261015/repair_ticket_filter_native_20261016T174604.json).

[Captured-state offline replay](data/forward_7129_20261015/repair_ticket_filter_replay_20261016.json) produces exactly two **fake** protected pending requests using the real saved state/history and explicitly simulated tick progression; old PnL remains-3.07 and restart produces no duplicate pair. The replay never connects to MT5 or edits the live profile. [Re-run helper](data/forward_7129_20261015/replay_ticket_filter_repair.py).

The API's documented interval/ticket/position query forms: [official MQL5 reference](https://www.mql5.com/en/docs/python_metatrader5/mt5historydealsget_py). The terminal-specific ticket error is an observed fact; its lower-level cause is not asserted.

## Handoff

1. User stops then starts only the 7129 bot using their normal run_supervised workflow; do not restart MT5 or reset Scalping456 state.
2. Verify new process identity, fresh heartbeat, Scalping456 ON, and journal `pending_fill_history` resolves both old tickets.
3. Verify actual new `sizing/request/response` plus broker pending/entry identifiers, native SL/TP, 1% sizing and no duplicate old PnL. A broker fill additionally requires price to reach a pending entry.
4. If a current account/quote/risk/broker guard blocks, report the actual reason; do not disable safeguards or force a market order.

Risk remains **1% current equity per NEW order**, not a 1% whole-portfolio cap. A pair may expose about2%; up to3 own slots remains unchanged. Fees/slippage/gaps can increase realized loss. Original failed first-five cohort stays failed historically; this repair does not certify profitability or a 100% clone.

Original periodic monitor remains stopped. The existing one-off18:00 read-only appointment is unchanged; it may report waiting for user restart if not yet performed.
