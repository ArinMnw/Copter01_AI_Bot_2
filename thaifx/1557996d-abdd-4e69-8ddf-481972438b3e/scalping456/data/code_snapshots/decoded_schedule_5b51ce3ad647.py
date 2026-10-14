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
    GoldRegime(ms("2026-08-18T21:00:00"), False),                              # warm-up
    GoldRegime(ms("2026-08-26T00:00:00"), True, 100, "0.01"),                   # era E1 (D=1.00)
    GoldRegime(ms("2026-08-27T06:05:00"), False),                              # E2: entry rule not identified
    GoldRegime(ms("2026-08-30T22:00:00"), True, 100, "0.01"),                   # era E3 (D=1.00)
    GoldRegime(ms("2026-08-31T05:12:19"), True, 100, "1"),
    GoldRegime(ms("2026-08-31T20:42:24"), True, 100, "0.01"),
    GoldRegime(ms("2026-09-01T02:05:51"), True, 100, "1"),
    GoldRegime(ms("2026-09-01T13:37:20"), True, 100, "10"),
    GoldRegime(ms("2026-09-30T12:50:00"), False),                              # transition: mechanism not identified
    GoldRegime(ms("2026-09-30T20:46:00"), True, 130, "10"),                     # era E4 (D=1.30)
)

# Fixed: lot boundaries = previous basket's last close + 1 s; Sep 27 04:38:39 follows
# two manual (comment-less) closes and starts TP/step 15.0 with entry distance 2.802.
FIXED_REGIMES = (
    FixedRegime(ms("2026-08-18T21:00:00"), False),
    FixedRegime(ms("2026-09-05T17:40:00"), True, 3000, 3000, 3000, 1),
    FixedRegime(ms("2026-09-06T05:18:53"), True, 3000, 3000, 3000, 10),
    FixedRegime(ms("2026-09-07T10:14:40"), True, 3000, 3000, 3000, 1),
    FixedRegime(ms("2026-09-13T13:06:46"), True, 3000, 3000, 3000, 10),
    FixedRegime(ms("2026-09-17T14:00:10"), True, 3000, 3000, 3000, 1),
    FixedRegime(ms("2026-09-27T04:38:39"), True, 2802, 15000, 15000, 1),
)
