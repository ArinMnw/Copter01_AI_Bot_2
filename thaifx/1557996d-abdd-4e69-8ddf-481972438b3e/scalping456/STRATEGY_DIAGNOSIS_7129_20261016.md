# Scalping456 7129 — why the strategy is not opening orders

Checked: 2026-10-16T17:31:13.152+07:00

Update17:46: user subsequently authorized the repair. [Ticket-filter repair](FIX_TICKET_FILTER_7129_20261016.md) is ready on disk;78tests/captured-state replay PASS, new ownership method resolves both tickets on native read-only history, and both order_check previews pass. Running main still uses the old module until USER restart. No live state reset or real order_send. The diagnosis below is historical evidence, not a claim the repair remains unimplemented.

## Finding

**The entry strategy is blocked by adapter bookkeeping, not waiting for a signal.** Current ownpositions0/pending0; strategy ON, phaseworking, rearm_requestedtrue, pending_closes empty and old-day PnL-3.07 recovered. known_orders still contains4878801646/4878801649.

The dedicated adapter should place native BUY_STOP at Ask+1.30 and SELL_STOP at Bid-1.30 (tick rounding), with SL1.00 and TP0. It has no RSI, candle-confirmation or trend entry gate. It still requires identity, enabled state, live-quote observation, exposure/limit capacity and daily-net checks. Native quotes observed here did not change across450ms, so this audit does not claim direct proof of the bot's internal freshness flag.

## Causal evidence

1. Current raw native history_deals_get(ticket=...) returnsNone with **(-2, Terminal: Invalid params)** for each old ticket. Per-position queries returnSuccess and owned entry/exit deals. Do not call this ordinary lagging history or attribute the exact SDK/broker cause without evidence.
2. `_stub_position_identifier` atdemo_scalping456.py298-300 returnsNone. `_resolve_orders` continues without removing either known order.
3. The new-entry guard at556 sees nonempty known_orders and returns before `_entry_volume` or any sizing/request event. No amount of waiting for an entry signal bypasses that guard with the same state/API behavior.
4. [Current native and offline causal evidence](data/forward_7129_20261015/strategy_diagnosis_20261016T173113.json) reproduces the actual None behavior with a fake broker:0fake sends. A counterfactual **temporary in-memory test only**, after saved entry-deal ownership proof, removes only the stale tracking and produces2fake pending orders. No live state was reset and this is not a recommendation to clear it blindly.

## Risk sizing is downstream, not the current blocker

Native read-only calculation on equity10474.27 gives a1% budget104.7427USD. Each leg rounds down to1.04lot with modeled104USD price loss to SL (about0.9929% of snapshot equity). These are **hypothetical previews, not submitted orders**; quoted prices/equity can change and fees/slippage/gaps are excluded. Buy/Sell together can expose about2%, not a portfolio-wide1% cap.

The62 earlier unit tests passed a fake API that returned ticket-filter history successfully. They established offline code paths, not compatibility of this actual terminal filter; the live verification found the gap. The earlier adapter fix is incomplete even though historical close accounting now works.

## Required repair, not implemented by this check

Add an alternative history lookup that can use independently proven position identifiers/entry deals when the ticket filter is invalid, still verifying exact original DEAL_ORDER, magic, symbol, side, volume and unique identifier. Release only proven resolved known orders; retain exactly-once accounting and reject foreign/ambiguous data. Add a regression whose fake ticket-filter API returnsNone/-2 while the position query succeeds. No strategy-distance change, reduced signal requirement, forced order or manual live-state reset is needed.

User requested diagnosis only on this turn. Trading code/config/risk/live state/orders/processes were not changed. Original cohort failures remain historical, and the one-time18:00read-only appointment is untouched.
