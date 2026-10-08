# Pending trailing proposal validity — before guarded predictions

8 ตุลาคม 2026 หลัง 32 unguarded paper benchmarks เสร็จและ QA32/160filesผ่าน: best29/all35,462; no candidate passes. Preserve all artifacts and exact code snapshots; no overwrite/relabel old scores.

## Execution defect isolated from parameters

Level pending fill may gap well into profit on openingquote. Engine deliberately does not trail newly opened position on thatquote. On nextquote, historical peak may propose BUY SL above currentBid or SELL SL below currentAsk. That is not an accepted server-side trailing modification; original benchmarks treat it as ideal paper state and must not be called actualbrokerexecution.

[MetaQuotes distance rules](https://www.mql5.com/en/book/automation/symbols/symbols_spreads_levels) use Bid for BUY protective levels and Ask for SELL, with symbol stop/freeze distances. This correction enforces only proposal correct-side validity: BUY candidate < Bid; SELL candidate > Ask. No assumed source modification acceptance, latency or nonzero stop/freeze levels is added. Current demo specs are not historical source specs. Freeze/minimum-distance/execution behavior remain unverified.

## Frozen intervention / scope

Run ALL same32 configurations from `EXPERIMENT_PENDING_STOP_PLAN.md` with `require_valid_trail=True`; preserve entrydistance1, all execution modes, both anchors/policies/trails, lot10, same warm-up/ticks/split/source precision. Not select winners or tune values after validation. Only difference is rejecting wrong-side trailing proposals while retaining the previously accepted SL. Later quotes may permit the same candidate again. Check existingSL before any proposal.

Generate all trajectories before source parsing. Save all35,462source results/strict extras/explicit entry-only diagnostics again. Fixed4,252 remain missing in these XAU prototypes. No claiming subset or accounting/unit tests as goal completion. Validate reference/vector parity on synthetic gaps+actual samples, futureprefix and unchanged default-control behavior.

The historical unguarded controls remain available by explicitly `require_valid_trail=False`. The feature is paper-only and never invokes MT5 trades/order_check. No external action is required from the user; unavailable source EA is not requested again.
