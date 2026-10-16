# Scalping456 7129 — unblock new orders

Recorded: 2026-10-16T15:41:56.150533+07:00

## Status

Implemented and offline-verified, **awaiting the user's restart of7129**. User explicitly chose to restart it personally. The agent did not restart/stop any bot or MT5, modify live state or send/cancel/modify an order. The monitor remains PAUSED. No live post-fix execution has been verified.

## Cause and change

Exness historical pending-order rows for4878801646/4878801649 return magic0/position_id0 while the original submission and native entry deals prove ownership. The old strict history guard raised before close reconciliation, retaining known_orders/pending_closes and preventing a new pair.

- Only the exact Exness entry profile may use the zero-magic fallback. Filled history must match the known order ticket, exact symbol, owned entry-deal magic, direction, complete filled volume and a unique positive position identifier. Conflicting/foreign data still fails closed; unavailable/incomplete history waits without placing another pair.
- Final cancellation/expiry/rejection stubs without fills additionally require an original matching protected pending request and successful broker acknowledgement in the strategy journal. Partial fills are reconciled by their proven identifier instead of dropped.
- Confirm complete entry/exit volume before booking a close; include entry/exit commission, swap and fees once. Allocate whole-position realized net to the final exit's BKK day, not the recovery day. No synthetic broker-clock offset.
- Save close accounting and follow-up intent atomically before journal I/O. Retry failed opposite-pending cancellation, confirm no old pending remains, then permit rearm; disappearance alone cannot trigger cancellation/rearm. Restart recovery cannot double the old PnL or duplicate the pair.
- Lot0.01, entry1.30, SL1.00, trailing0.20, delays, max exposure3, daily entry gate20USD, target allowlist and preflight are unchanged. No changes to INDI1/EA2.1 or other profile data.

## Verification

- Existing32 tests passed before modification. New regression fails on the frozen old adapter with the original identity mismatch.
- **47 unit tests PASS**, including stuck-pair recovery/new pair, foreign ownership refusal, incomplete history, partial and duplicate deals, opposite-pending retention until confirmed close, failed-cancel retry, restart after saved accounting/journal failure, rearm deduplication and recovered daily-loss gate.
- Python compile and scoped UTF-8/LF/mojibake checks PASS. AST comparisons prove Params/Target/target_for/preflight unchanged. Full verify_repo.py was not run because its mojibake phase unconditionally traverses the repository, including unrelated MT5 data; changed-file checks were used.
- [Saved real broker-history offline replay](data/forward_7129_20261015/fix_offline_replay_20261016.json) PASS: both original positions reconciled, pending_closes empty, old-day net-3.07 including excluded baseline, cycles2→3, exactly two new **fake-broker** pending requests. This does not claim live orders or live profitability.
- New adapter SHA256: `8f8b7984758c5cdf6f31be9d98fbc2b0eb8f36f0251938888728de397c786624`; test SHA256: `6f0d3e3704c5d1f66474ccd175fd39cf647f82de7afefa05a1b55d82396a5d99`.
- history_deals_get(ticket=...) filters DEAL_ORDER, independently checked against the [official MetaTrader5 Python reference](https://www.mql5.com/en/docs/python_metatrader5/mt5historydealsget_py).

## Handoff

Restart only the7129 bot through the existing supervised workflow; **do not delete/reset scalping456_state.json**. Existing state will be reconciled by the new code when loaded. With Scalping456 enabled, correct demo account/terminal and live quotes, the next eligible cycle can place the native BUY_STOP/SELL_STOP pair. Restarting MT5 itself is not required for this code change. After the user restarts, verify the loaded revision, cleared stuck IDs, historical accounting and actual native pending responses. Keep the monitor paused unless requested again; preserve original failed cohort history.
