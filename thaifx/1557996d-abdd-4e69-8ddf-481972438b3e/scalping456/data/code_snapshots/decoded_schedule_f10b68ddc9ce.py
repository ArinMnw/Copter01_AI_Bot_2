"""Operator-input schedule (regimes) for the decoded engines.

The EA owner changed inputs over time (stop/grid distance, lot, TP) and
sometimes acted manually.  Those changes are exogenous to the price feed, so a
causal replay needs them as scenario inputs.  Every boundary below was read off
the public ledger (see DECODED_MECHANICS_RESULTS.md, "Regime schedule") and is
therefore LEDGER-DERIVED INPUT, disclosed as such: it fixes which parameter set
is in force, never an order, ticket, fill time, price or P/L.  Eras whose
entry mechanism is not identified are marked inactive (their source orders
count as missing).  All instants are inferred UTC (raw server clock - 3 h).
"""

from decoded_common import ms
from strategy_scalping456_decoded import FixedRegime, GoldRegime

# Gold: lot boundaries = previous run's last close + 1 s (EA idle at the switch).
GOLD_REGIMES = (
    GoldRegime(ms("2026-08-18T21:00:00"), False),                                    # warm-up
    GoldRegime(ms("2026-08-23T22:00:00"), True, 105, "0.01", 680),                   # E0: D=1.05, slow/jittery reaction
    GoldRegime(ms("2026-08-26T08:00:00"), True, 100, "0.01"),                        # E1: D=1.00
    GoldRegime(ms("2026-08-27T06:05:00"), True, 105, "0.01"),                        # E2: D=1.05
    GoldRegime(ms("2026-08-30T22:00:00"), True, 100, "0.01"),                        # E3: D=1.00
    GoldRegime(ms("2026-08-31T05:12:19"), True, 100, "1"),
    GoldRegime(ms("2026-08-31T20:42:24"), True, 100, "0.01"),
    GoldRegime(ms("2026-09-01T02:05:51"), True, 100, "1"),
    GoldRegime(ms("2026-09-01T13:37:20"), True, 100, "10"),
    GoldRegime(ms("2026-09-30T14:20:00"), True, 110, "10"),                          # T1: D=1.10 (14:23-16:12)
    GoldRegime(ms("2026-09-30T16:15:00"), False),                                    # EA idle until 20:54
    GoldRegime(ms("2026-09-30T20:46:00"), True, 130, "10"),                          # E4: D=1.30
)

# Fixed: Sep 5 07:50-Sep 6 04:30 is a single-leg trailing (SL-trial) engine, later the grid engine.
# Lot boundaries = previous basket's last close + 1 s; Sep 27 04:38:39 follows
# two manual (comment-less) closes and starts TP/step 15.0 with entry distance 2.802.
# Daily trading windows seen on Sep 6-12 (UTC minutes of day): 13:00-13:35, 20:00-21:05, 23:00-10:00.
FIXED_SESSIONS = ((13 * 60, 13 * 60 + 35), (20 * 60, 21 * 60 + 5), (23 * 60, 10 * 60))
FIXED_REGIMES = (
    FixedRegime(ms("2026-08-18T21:00:00"), False),
    FixedRegime(ms("2026-09-05T07:50:00"), True, 5000, mode="trailing", base_lot_tenths=1),   # SL-trial engine, D=5.0
    FixedRegime(ms("2026-09-05T14:51:00"), True, 3000, mode="trailing", base_lot_tenths=1),   # SL-trial engine, D=3.0
    FixedRegime(ms("2026-09-06T04:30:00"), True, 3000, 3000, 3000, 1, sessions=FIXED_SESSIONS),   # grid + basket TP engine
    FixedRegime(ms("2026-09-06T05:18:53"), True, 3000, 3000, 3000, 10, sessions=FIXED_SESSIONS),
    FixedRegime(ms("2026-09-07T10:14:40"), True, 3000, 3000, 3000, 1, sessions=FIXED_SESSIONS),
    FixedRegime(ms("2026-09-12T14:00:00"), True, 3000, 3000, 3000, 1),                        # windows no longer visible
    FixedRegime(ms("2026-09-13T13:06:46"), True, 3000, 3000, 3000, 10),
    FixedRegime(ms("2026-09-17T14:00:10"), True, 3000, 3000, 3000, 1),
    FixedRegime(ms("2026-09-27T04:38:39"), True, 2802, 15000, 15000, 1, flatten_at_start=True),   # after two manual closes
)
