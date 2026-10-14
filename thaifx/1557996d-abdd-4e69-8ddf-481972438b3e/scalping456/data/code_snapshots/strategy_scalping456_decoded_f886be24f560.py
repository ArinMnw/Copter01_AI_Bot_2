"""Evidence-decoded Scalping456 engines (research only; never wired to trading).

Two causal tick simulators decoded from the public ledger plus the Vantage
demo feed.  Neither imports or reads the ledger: every decision uses only ticks
at or before the current tick and the explicit regime schedule passed in.

Gold (``XAUUSD+``) -- "PipScalperEA V2"-style pending-stop straddle
    * Source quotes = Vantage demo ``XAUUSD`` quotes moved inward:
      ``bid_src = bid + 0.06`` and ``ask_src = ask - 0.05`` (see
      DECODED_MECHANICS_RESULTS.md for the calibration evidence).
    * After every position close the EA reads the quotes one reaction delay
      later, deletes old pendings and places BUY STOP ``ask_src + D`` and SELL
      STOP ``bid_src - D``.  Pending stops fill at their own level.
    * Initial stop 1.00 from the fill; trailing stop 0.20 behind the best bid
      (ask) once the position is more than 0.20 in profit.  A modify call blocks the EA
      for ``modify_busy_ms`` and takes effect ``modify_effect_ms`` later.
Fixed volatility 20 (``FixedVol20``) -- stop-entry grid basket
    * The Vantage demo feed is bit-identical to the source feed (1 tick/s).
    * One tick after a basket closes: BUY STOP ask+D / SELL STOP bid-D.
    * Adds a market leg whenever price moves ``grid_step`` against the last
      leg, lots x1.68 rounded to 0.1 (cap 174); basket TP is the volume
      weighted entry rounded half-up to 0.001, +/- ``tp_distance``.

Timing that is NOT deterministic in the evidence (EA reaction races, tick
sampling inside the EA terminal) is exposed as explicit parameters; the
fixed values used for replays are documented, and no value is tuned per order.
All prices are integers (gold: cents, fixed: thousandths); times are
milliseconds on the inferred-UTC clock (raw server clock minus 3 h).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from fractions import Fraction
from typing import Optional, Sequence

# ---------------------------------------------------------------------------
# Gold
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GoldRegime:
    """Operator-controlled inputs that change over time (inferred schedule)."""

    start_ms: int
    active: bool
    stop_distance: int = 100   # cents between reference quote and pending level
    lot: str = "10"


@dataclass(frozen=True)
class GoldParams:
    bid_add: int = 6            # cents added to demo bid -> source bid
    ask_add: int = -5           # cents added to demo ask -> source ask
    initial_stop: int = 100
    trail_activation: int = 20
    trail_distance: int = 20
    react_ms: int = 110         # EA reads quotes this long after a close (dev-selected)
    modify_busy_ms: int = 800   # EA blocked while a SL modify is in flight
    modify_effect_ms: int = 400  # modify reaches the server this long after send
    place_only_when_flat: bool = False  # run-2 hypothesis H9: no new pair while any position is open


def _regime_index(starts: Sequence[int], t: int) -> int:
    lo, hi = 0, len(starts)
    while lo < hi:
        mid = (lo + hi) // 2
        if starts[mid] <= t:
            lo = mid + 1
        else:
            hi = mid
    return lo - 1


def simulate_gold(times, bids, asks, regimes: Sequence[GoldRegime], params: GoldParams = GoldParams(),
                  *, begin: int = 0, end: Optional[int] = None, initial_close_ms: Optional[int] = None,
                  stop_after_trades: Optional[int] = None):
    """Run the gold engine over demo-feed ticks (integer cents) and return trades.

    ``times``/``bids``/``asks`` are sequence-indexable (numpy arrays are fine).
    The loop is strictly forward; ``regimes`` must be sorted by ``start_ms``.
    Positions still open at the end are returned with ``close_ms=None``.
    ``initial_close_ms`` (diagnostics only) starts the run as if a position had
    just closed at that instant; ``stop_after_trades`` ends the run early.
    """
    n = len(times) if end is None else end
    starts = [r.start_ms for r in regimes]
    trades = []
    positions = []              # dict per open position
    buy_level = sell_level = None
    pending_lot = None
    place_due = None            # ms at which the EA reads quotes to place a pair
    if initial_close_ms is not None:
        place_due = initial_close_ms + params.react_ms
    last_regime = -2
    p = params
    i = begin
    while i < n:
        t = int(times[i])
        ri = _regime_index(starts, t)
        if ri != last_regime:
            last_regime = ri
            regime = regimes[ri] if ri >= 0 else None
            if regime is not None and regime.active and not positions and place_due is None:
                place_due = t - 1   # EA (re)starts: reference is the current tick
            if regime is None or not regime.active:
                buy_level = sell_level = None
                place_due = None
        regime = regimes[ri] if ri >= 0 else None
        if regime is None or (not regime.active and not positions):
            # Nothing to do until the next regime starts: jump there.
            nxt = ri + 1
            if nxt >= len(regimes):
                break
            target = regimes[nxt].start_ms
            while i < n and int(times[i]) < target:
                i += 1
            continue
        bid = int(bids[i]) + p.bid_add
        ask = int(asks[i]) + p.ask_add
        # 1) EA placement (reference quote = last tick at/before the due time)
        if place_due is not None and t > place_due and regime.active and i > begin:
            ref_b = int(bids[i - 1]) + p.bid_add
            ref_a = int(asks[i - 1]) + p.ask_add
            buy_level = ref_a + regime.stop_distance
            sell_level = ref_b - regime.stop_distance
            pending_lot = regime.lot
            place_due = None
        elif place_due is not None and not regime.active:
            place_due = None
        # 2) stops / trailing for open positions
        still = []
        closed_any = False
        for pos in positions:
            if pos["pend_t"] is not None and pos["pend_t"] <= t:
                pos["stop"] = max(pos["stop"], pos["pend_s"]) if pos["side"] == 1 else min(pos["stop"], pos["pend_s"])
                pos["pend_t"] = None
            quote = bid if pos["side"] == 1 else ask
            hit = quote <= pos["stop"] if pos["side"] == 1 else quote >= pos["stop"]
            if hit:
                trades.append({"open_ms": pos["open_ms"], "close_ms": t, "side": "buy" if pos["side"] == 1 else "sell",
                               "volume": pos["lot"], "open_price": pos["entry"] / 100, "close_price": pos["stop"] / 100,
                               "close_behavior": "sl"})
                closed_any = True
                continue
            if t >= pos["busy_until"]:
                gain = quote - pos["entry"] if pos["side"] == 1 else pos["entry"] - quote
                if gain > p.trail_activation:
                    candidate = quote - p.trail_distance if pos["side"] == 1 else quote + p.trail_distance
                    better = candidate > pos["stop"] if pos["side"] == 1 else candidate < pos["stop"]
                    if better:
                        pos["busy_until"] = t + p.modify_busy_ms
                        pos["pend_t"] = t + p.modify_effect_ms
                        pos["pend_s"] = candidate
            still.append(pos)
        positions = still
        if closed_any and regime.active and not (p.place_only_when_flat and positions):
            place_due = t + p.react_ms
        if stop_after_trades is not None and len(trades) >= stop_after_trades:
            break
        # 3) pending stop triggers (levels active strictly after placement tick)
        if buy_level is not None and ask >= buy_level:
            positions.append({"side": 1, "entry": buy_level, "stop": buy_level - p.initial_stop, "open_ms": t,
                              "lot": pending_lot, "busy_until": 0, "pend_t": None, "pend_s": 0})
            buy_level = None   # the SELL STOP sibling stays until the next placement
        elif sell_level is not None and bid <= sell_level:
            positions.append({"side": -1, "entry": sell_level, "stop": sell_level + p.initial_stop, "open_ms": t,
                              "lot": pending_lot, "busy_until": 0, "pend_t": None, "pend_s": 0})
            sell_level = None
        i += 1
    for pos in positions:
        trades.append({"open_ms": pos["open_ms"], "close_ms": None, "side": "buy" if pos["side"] == 1 else "sell",
                       "volume": pos["lot"], "open_price": pos["entry"] / 100, "close_price": None,
                       "close_behavior": "still_open"})
    return trades


# ---------------------------------------------------------------------------
# FixedVol20
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FixedRegime:
    start_ms: int
    active: bool
    entry_distance: int = 3000   # thousandths from the reference quote
    grid_step: int = 3000
    tp_distance: int = 3000
    base_lot_tenths: int = 1


@dataclass(frozen=True)
class FixedParams:
    multiplier: Fraction = Fraction(168, 100)
    lot_cap_tenths: int = 1740
    place_delay_ticks: int = 1   # reference tick = close tick + 1 (1 Hz feed)


def next_lot_tenths(previous: int, params: FixedParams = FixedParams()) -> int:
    """Previous (already rounded) lot x1.68 rounded half-up to 0.1, capped."""
    value = Fraction(previous, 10) * params.multiplier * 10
    return min(math.floor(value + Fraction(1, 2)), params.lot_cap_tenths)


def basket_take_profit(legs, side: int, distance: int) -> int:
    """Volume weighted entry rounded half-up to 0.001, then +/- distance."""
    numerator = sum(entry * lots for entry, lots, _ in legs)
    denominator = sum(lots for _, lots, _ in legs)
    return math.floor(Fraction(numerator, denominator) + Fraction(1, 2)) + side * distance


def simulate_fixed(times, bids, asks, regimes: Sequence[FixedRegime], params: FixedParams = FixedParams(),
                   *, begin: int = 0, end: Optional[int] = None, max_baskets: Optional[int] = None):
    n = len(times) if end is None else end
    starts = [r.start_ms for r in regimes]
    trades = []
    state = "flat"
    place_at = begin
    buy_level = sell_level = None
    pending_regime = None
    legs = []
    side = 0
    tp = 0
    basket_regime = None
    baskets = 0
    i = begin
    while i < n:
        t = int(times[i])
        ri = _regime_index(starts, t)
        regime = regimes[ri] if ri >= 0 else None
        if state == "flat":
            if regime is not None and regime.active and i >= place_at:
                buy_level = int(asks[i]) + regime.entry_distance
                sell_level = int(bids[i]) - regime.entry_distance
                pending_regime = regime
                state = "pending"
            i += 1
            continue
        if state == "pending":
            if regime is None or not regime.active:
                state = "flat"
                place_at = i + 1
            elif int(asks[i]) >= buy_level:
                side, basket_regime = 1, pending_regime
                legs = [[buy_level, pending_regime.base_lot_tenths, t]]
                tp = buy_level + basket_regime.tp_distance
                state = "open"
            elif int(bids[i]) <= sell_level:
                side, basket_regime = -1, pending_regime
                legs = [[sell_level, pending_regime.base_lot_tenths, t]]
                tp = sell_level - basket_regime.tp_distance
                state = "open"
            i += 1
            continue
        quote = int(bids[i]) if side == 1 else int(asks[i])
        if (side == 1 and quote >= tp) or (side == -1 and quote <= tp):
            for entry, lots, opened in legs:
                trades.append({"open_ms": int(opened), "close_ms": t, "side": "buy" if side == 1 else "sell",
                               "volume": lots / 10, "open_price": entry / 1000, "close_price": tp / 1000,
                               "close_behavior": "tp"})
            state = "flat"
            place_at = i + params.place_delay_ticks
            baskets += 1
            if max_baskets is not None and baskets >= max_baskets:
                break
            i += 1
            continue
        last_entry = legs[-1][0]
        add = None
        if side == 1 and int(asks[i]) <= last_entry - basket_regime.grid_step:
            add = int(asks[i])
        elif side == -1 and int(bids[i]) >= last_entry + basket_regime.grid_step:
            add = int(bids[i])
        if add is not None:
            legs.append([add, next_lot_tenths(legs[-1][1], params), t])
            tp = basket_take_profit(legs, side, basket_regime.tp_distance)
        i += 1
    for entry, lots, opened in legs if state == "open" else []:
        trades.append({"open_ms": int(opened), "close_ms": None, "side": "buy" if side == 1 else "sell",
                       "volume": lots / 10, "open_price": entry / 1000, "close_price": None,
                       "close_behavior": "still_open"})
    return trades
