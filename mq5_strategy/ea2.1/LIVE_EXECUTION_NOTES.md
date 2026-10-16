# EA2.1 demo execution hardening (2026-10-16)

Scope: the EA2_1 demo-portfolio route used by demo-exness-434237129.
The legacy standalone scanner retains its existing immediate signal-consumption API.
No running process is reloaded or restarted by these source changes.

## Signal and broker acknowledgement

The demo route opts into `defer_execution=True`. A qualifying closed-bar signal
creates a persisted execution intent instead of committing the cycle/cooldown.
The intent is persisted as inflight before a broker call. Confirmed success commits
the cycle and event timestamp; a definite rejection retains the same intent for a
retry after 15 seconds, only while its M5 decision bar remains the latest closed bar.
An unsent intent expires on the next bar; old setups are never chased.

None/timeout/partial/placed responses and exceptions are ambiguous, not rejections.
Inflight/unknown intents block automatic resends, including across restart. Positive
entry-deal or open-position evidence for the dedicated symbol/magic/side/time window
resolves them. Empty/unavailable history does not prove that a send failed. An
unresolved result requires investigation rather than permission to open again.

Legacy state without an execution intent is retained; historical consumed cycles
cannot safely be reconstructed from a successful order count alone.

## Execution spread

Only EA2.1 passes the optional spread cap to the shared demo market-order helper.
After the margin check, the helper obtains a fresh quote, validates the spread, and
uses that quote's price. Fixed SL/TP distances move with that price. Other demo
portfolios do not opt into this behavior. Network latency and broker slippage still
prevent any promise about the spread or fill price observed by the broker later.

## Causal EMA window

Both research and live seed EMA20/50 from exactly the most recent 200 closed M15
bars available at each decision time. The research filter rejects decisions without
the full window. Older or future rows cannot change that decision's EMA seed.
This intentionally changes research results near boundaries versus the old
whole-history EMA seed. Old 365-day PnL reports are not revalidated by unit tests;
rerun the backtest before comparing new results with old reports.

## Verification limits

Tests cover the signal/filter interface, broker acknowledgement transitions,
explicit rejection, unknown outcomes, restart reconciliation, stale-intent expiry,
spread widening and causal EMA windows. Broker operations are mocked. These tests
do not certify real fills, full-lifecycle management or live/backtest PnL equality.
