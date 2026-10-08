"""Research candidates for the public Scalping456 ledger, not a verified clone.

This is a clean-room, data-driven implementation.  It does not look up ticket
history and it does not contain future information. Fixed-close brackets and
rolling-extrema entries are separate hypotheses. The 100-point initial loss is
strong ledger evidence; entry, trail activation/distance/step and execution are
still candidates. Default trailing 40/30 came from a conditional IUX proxy fit,
not a full causal reproduction. Ideal 40/30 fills are structurally incompatible
with 4,792 SL-labelled XAU rows; ``[sl]`` is not an engine identifier. Close-by
settlement below implements verified accounting, not the unknown hedge trigger.
See STRATEGY_HYPOTHESIS.md for limitations.

Important price convention for two-decimal XAUUSD:
    1 point = 0.01 price units, so 100 points = 1.00 USD.

The public ledger timestamps are not trustworthy timezone labels.  They must be
normalised before replay; this module itself accepts timezone-aware datetimes
and does not silently shift them.
"""

from __future__ import annotations

from dataclasses import dataclass
from collections import deque
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from math import isfinite
from typing import Literal


class Side(str, Enum):
    BUY = "buy"
    SELL = "sell"


@dataclass(frozen=True)
class CloseByPosition:
    """An open leg supplied by portfolio state, not by a source-ticket lookup."""

    symbol: str
    side: Side
    entry_time: datetime
    entry_price: Decimal
    volume: Decimal

    def __post_init__(self) -> None:
        if not self.symbol or not isinstance(self.side, Side):
            raise ValueError("Close-by requires a symbol and a valid Side")
        if self.entry_time.utcoffset() is None:
            raise ValueError("Entry time must be timezone-aware")
        for name in ("entry_price", "volume"):
            value = Decimal(str(getattr(self, name)))
            if not value.is_finite() or value <= 0:
                raise ValueError("Price and volume must be finite and positive")
            object.__setattr__(self, name, value)


@dataclass(frozen=True)
class CloseByExit:
    time: datetime
    symbol: str
    side: Side
    volume: Decimal
    price: Decimal
    pips: Decimal
    gross_profit: Decimal
    remaining_volume: Decimal


def settle_close_by(
    first: CloseByPosition,
    second: CloseByPosition,
    *,
    time: datetime,
    contract_price_multiplier: Decimal,
    point: Decimal,
) -> tuple[CloseByExit, CloseByExit]:
    """Pure MT5 close-by accounting; no market quote or trading API is used.

    Caller must decide when/which legs to close. ``first`` is the request's
    position, ``second`` its position_by. Their minimum volume is offset at
    reciprocal entry prices. Gross P/L is allocated to the first exit only;
    mirrored price/pips on the second exit must not double-count the loss.
    Commission, swaps, currency conversion and hedge timing are not inferred.
    """
    if first.symbol != second.symbol or first.side is second.side:
        raise ValueError("Close-by requires opposite positions on the same symbol")
    if time.utcoffset() is None or time < max(first.entry_time, second.entry_time):
        raise ValueError("Close-by time must be aware and not precede either entry")
    contract = Decimal(str(contract_price_multiplier))
    point_size = Decimal(str(point))
    if any(not value.is_finite() or value <= 0 for value in (contract, point_size)):
        raise ValueError("Contract multiplier and point must be finite and positive")
    matched = min(first.volume, second.volume)
    sign = Decimal(1) if first.side is Side.BUY else Decimal(-1)
    delta = sign * (second.entry_price - first.entry_price)
    pips = delta / point_size
    return (
        CloseByExit(time, first.symbol, first.side, matched, second.entry_price,
                    pips, delta * matched * contract, first.volume - matched),
        CloseByExit(time, second.symbol, second.side, matched, first.entry_price,
                    pips, Decimal(0), second.volume - matched),
    )


@dataclass(frozen=True)
class Scalping456Config:
    """Explicit hypotheses for the 31,123 XAU ``[sl ...]`` orders.

    Defaults are a rejected full-cohort hypothesis, retained as an explicit
    research benchmark, not recovered source EA settings. Do not deploy them.
    ``stop_fill_mode='level'`` assumes ideal stop execution. Use ``quote`` to
    expose gaps/slippage rather than silently treating every stop as exact.
    """

    point: float = 0.01
    entry_reversal_points: int = 100
    initial_stop_points: int = 100
    entry_mode: Literal["fixed_close", "rolling_extrema", "lookback_momentum"] = "fixed_close"
    momentum_window_seconds: int = 10
    trailing_activation_points: int = 40
    trailing_distance_points: int = 30
    trailing_step_points: int = 0
    stop_fill_mode: Literal["level", "quote"] = "level"
    volume: float = 10.0

    def __post_init__(self) -> None:
        positive = (self.point, self.entry_reversal_points, self.initial_stop_points,
                    self.trailing_distance_points, self.volume)
        if any(not isfinite(value) or value <= 0 for value in positive):
            raise ValueError("Point, thresholds, distance and volume must be finite and positive")
        if any(not isfinite(value) or value < 0 for value in
               (self.trailing_activation_points, self.trailing_step_points)):
            raise ValueError("Trail activation and step must be finite and nonnegative")
        if self.entry_mode not in ("fixed_close", "rolling_extrema", "lookback_momentum"):
            raise ValueError("Unknown entry_mode")
        if not isinstance(self.momentum_window_seconds, int) or self.momentum_window_seconds <= 0:
            raise ValueError("momentum_window_seconds must be a positive integer")
        if self.stop_fill_mode not in ("level", "quote"):
            raise ValueError("Unknown stop_fill_mode")

    @property
    def entry_reversal_price(self) -> float:
        return self.entry_reversal_points * self.point

    @property
    def initial_stop_price(self) -> float:
        return self.initial_stop_points * self.point

    @property
    def trailing_distance_price(self) -> float:
        return self.trailing_distance_points * self.point

    @classmethod
    def fixedvol20_trial(
        cls,
        *,
        entry_reversal_points: int,
        trailing_activation_points: int,
        trailing_distance_points: int,
        entry_mode: Literal["fixed_close", "rolling_extrema", "lookback_momentum"] = "fixed_close",
        stop_fill_mode: Literal["level", "quote"] = "quote",
    ) -> "Scalping456Config":
        """Research adapter for the 143 FixedVol20 SL-labelled trial rows.

        Volume .1 and 27 exact -1,000-point losses are ledger observations, not
        recovered settings. Entry/activation/distance remain required inputs.
        This is not the later basket engine. Its 43 partial losses cannot be
        reproduced by ideal fills with activation >= distance and this initial
        stop; quote gaps or a different SL rule remain unresolved alternatives.
        ``point=.01`` is the website's pip unit. The new Vantage FixedVol20
        broker point is .001; these are not confirmed EA broker-point inputs.
        """
        return cls(point=.01, initial_stop_points=1000, volume=.1,
                   entry_reversal_points=entry_reversal_points,
                   trailing_activation_points=trailing_activation_points,
                   trailing_distance_points=trailing_distance_points,
                   entry_mode=entry_mode, stop_fill_mode=stop_fill_mode)


@dataclass(frozen=True)
class Tick:
    time: datetime
    bid: float
    ask: float

    def __post_init__(self) -> None:
        if self.time.utcoffset() is None:
            raise ValueError("Tick.time must be timezone-aware")
        if not isfinite(self.bid) or not isfinite(self.ask) or self.bid <= 0 or self.ask <= 0 or self.ask < self.bid:
            raise ValueError("Invalid bid/ask")


@dataclass(frozen=True)
class EntrySignal:
    time: datetime
    side: Side
    price: float
    stop_loss: float
    volume: float
    reason: str


@dataclass(frozen=True)
class ExitSignal:
    time: datetime
    side: Side
    price: float
    stop_loss: float
    reason: Literal["stop_loss"] = "stop_loss"


@dataclass(frozen=True)
class FixedVol20Config:
    """Basket-engine research candidates, not recovered EA inputs.

    Two public presets were observed:

    - 2026-09-06 through early 2026-09-27: grid/target = 3.0
    - late 2026-09-27 onward: grid/target = 15.0

    Both progressive and fixed-size baskets were observed. The ledger does not
    identify EA instances or prove that these were parallel independent engines.
    """

    entry_reversal_price: float = 3.0
    grid_step_price: float = 15.0
    basket_target_price: float = 15.0
    initial_volume: float = 0.1
    volume_multiplier: float = 1.68
    max_volume: float = 174.0
    fixed_volume: bool = False
    entry_mode: Literal["fixed_close", "rolling_extrema"] = "fixed_close"
    price_digits: int = 3
    grid_fill_mode: Literal["quote", "level"] = "quote"
    target_rounding: Literal["half_even", "half_up"] = "half_even"

    def __post_init__(self) -> None:
        values = (self.entry_reversal_price, self.grid_step_price,
                  self.basket_target_price, self.initial_volume,
                  self.volume_multiplier, self.max_volume)
        if any(not isfinite(value) or value <= 0 for value in values):
            raise ValueError("Basket parameters must be finite and positive")
        if self.max_volume < self.initial_volume or self.volume_multiplier < 1:
            raise ValueError("Invalid basket sizing")
        if self.entry_mode not in ("fixed_close", "rolling_extrema"):
            raise ValueError("Unknown entry_mode")
        if not isinstance(self.price_digits, int) or not 0 <= self.price_digits <= 10:
            raise ValueError("Invalid price_digits")
        if self.grid_fill_mode not in ("quote", "level") or self.target_rounding not in ("half_even", "half_up"):
            raise ValueError("Unknown grid fill/target rounding")

    @classmethod
    def early_three_dollar(cls, *, fixed_volume: bool = False) -> "FixedVol20Config":
        return cls(
            grid_step_price=3.0,
            basket_target_price=3.0,
            fixed_volume=fixed_volume,
        )

    @classmethod
    def late_fifteen_dollar(cls, *, fixed_volume: bool = False) -> "FixedVol20Config":
        return cls(fixed_volume=fixed_volume)


@dataclass(frozen=True)
class BasketEntrySignal:
    time: datetime
    side: Side
    price: float
    volume: float
    level: int
    basket_take_profit: float
    reason: Literal["initial_reversal", "adverse_grid_step"]


@dataclass(frozen=True)
class BasketExitSignal:
    time: datetime
    side: Side
    price: float
    positions: int
    total_volume: float
    reason: Literal["basket_take_profit"] = "basket_take_profit"


@dataclass(frozen=True)
class BasketLeg:
    time: datetime
    price: float
    volume: float


@dataclass
class Position:
    side: Side
    entry_time: datetime
    entry_price: float
    stop_loss: float
    best_bid: float
    best_ask: float


class Scalping456Strategy:
    """Pure tick-driven state machine.

    Flat state
    ----------
    Fixed-close mode uses the last simulated exit fill as a bracket reference.
    The first startup reference is the first tick midpoint (history unknown).
    Rolling-extrema mode uses running low ask / high bid instead. Both are
    candidates and must be compared on continuous, out-of-sample tick replay.

    Position state
    --------------
    Place the configured initial SL. Activate a ratcheting stop only after the
    configured favorable excursion, optionally with a minimum modify step.
    There is no fixed take-profit. Every core
    public order has ``TP=0`` and its ``[sl PRICE]`` comment exactly equals its
    closing price.
    """

    def __init__(self, config: Scalping456Config | None = None) -> None:
        self.config = config or Scalping456Config()
        self.position: Position | None = None
        self.running_low_ask: float | None = None
        self.running_high_bid: float | None = None
        self.flat_reference_price: float | None = None
        self.last_tick_time: datetime | None = None
        self._momentum_quotes: deque[tuple[float, float]] = deque()

    def reset(self) -> None:
        self.position = None
        self.running_low_ask = None
        self.running_high_bid = None
        self.flat_reference_price = None
        self.last_tick_time = None
        self._momentum_quotes.clear()

    def _check_time(self, tick: Tick) -> None:
        if self.last_tick_time is not None and tick.time < self.last_tick_time:
            raise ValueError("Ticks must be supplied in chronological order")
        self.last_tick_time = tick.time

    def on_tick(self, tick: Tick) -> EntrySignal | ExitSignal | None:
        self._check_time(tick)
        if self.config.entry_mode == "lookback_momentum":
            instant = tick.time.timestamp()
            self._momentum_quotes.append((instant, (tick.bid + tick.ask) / 2))
            cutoff = instant - self.config.momentum_window_seconds
            while len(self._momentum_quotes) > 1 and self._momentum_quotes[1][0] <= cutoff:
                self._momentum_quotes.popleft()
        if self.position is None:
            return self._on_flat_tick(tick)
        return self._on_position_tick(tick)

    def _on_flat_tick(self, tick: Tick) -> EntrySignal | None:
        if self.running_low_ask is None:
            self.running_low_ask = tick.ask
            self.running_high_bid = tick.bid
            self.flat_reference_price = (tick.ask + tick.bid) / 2
            return None

        self.running_low_ask = min(self.running_low_ask, tick.ask)
        self.running_high_bid = max(self.running_high_bid or tick.bid, tick.bid)
        if self.config.entry_mode == "fixed_close":
            assert self.flat_reference_price is not None
            buy_rebound = tick.ask - self.flat_reference_price
            sell_reversal = self.flat_reference_price - tick.bid
        elif self.config.entry_mode == "lookback_momentum":
            cutoff = tick.time.timestamp() - self.config.momentum_window_seconds
            if not self._momentum_quotes or self._momentum_quotes[0][0] > cutoff:
                return None
            change = (tick.bid + tick.ask) / 2 - self._momentum_quotes[0][1]
            buy_rebound, sell_reversal = change, -change
        else:
            buy_rebound = tick.ask - self.running_low_ask
            sell_reversal = self.running_high_bid - tick.bid
        threshold = self.config.entry_reversal_price

        buy_hit = buy_rebound >= threshold - 1e-9
        sell_hit = sell_reversal >= threshold - 1e-9
        if not buy_hit and not sell_hit:
            return None

        # Normally only one side becomes newly true on a tick.  If a sparse or
        # gapped feed makes both true, use the larger normalised excursion.
        side = Side.BUY if buy_hit and (not sell_hit or buy_rebound >= sell_reversal) else Side.SELL
        return self._open_position(tick, side, f"{self.config.entry_mode}_{self.config.entry_reversal_points}pt")

    def _open_position(self, tick: Tick, side: Side, reason: str) -> EntrySignal:
        entry = tick.ask if side is Side.BUY else tick.bid
        stop = (
            entry - self.config.initial_stop_price
            if side is Side.BUY
            else entry + self.config.initial_stop_price
        )
        self.position = Position(
            side=side,
            entry_time=tick.time,
            entry_price=entry,
            stop_loss=stop,
            best_bid=tick.bid,
            best_ask=tick.ask,
        )
        return EntrySignal(
            time=tick.time,
            side=side,
            price=entry,
            stop_loss=stop,
            volume=self.config.volume,
            reason=reason,
        )

    def _on_position_tick(self, tick: Tick) -> ExitSignal | None:
        position = self.position
        assert position is not None

        # A server-side stop acts before a new trailing modification can rescue
        # an already-breached position on the same tick.
        stopped = (
            tick.bid <= position.stop_loss
            if position.side is Side.BUY
            else tick.ask >= position.stop_loss
        )
        if stopped:
            exit_signal = ExitSignal(
                time=tick.time,
                side=position.side,
                price=(position.stop_loss if self.config.stop_fill_mode == "level"
                       else tick.bid if position.side is Side.BUY else tick.ask),
                stop_loss=position.stop_loss,
            )
            self.position = None
            self.running_low_ask = tick.ask
            self.running_high_bid = tick.bid
            self.flat_reference_price = exit_signal.price
            return exit_signal

        if position.side is Side.BUY:
            position.best_bid = max(position.best_bid, tick.bid)
            favorable_points = (position.best_bid - position.entry_price) / self.config.point
            if favorable_points < self.config.trailing_activation_points - 1e-7:
                return None
            candidate = position.best_bid - self.config.trailing_distance_price
            step = self.config.trailing_step_points * self.config.point
            if candidate > position.stop_loss + 1e-9 and candidate >= position.stop_loss + step - 1e-9:
                position.stop_loss = candidate
        else:
            position.best_ask = min(position.best_ask, tick.ask)
            favorable_points = (position.entry_price - position.best_ask) / self.config.point
            if favorable_points < self.config.trailing_activation_points - 1e-7:
                return None
            candidate = position.best_ask + self.config.trailing_distance_price
            step = self.config.trailing_step_points * self.config.point
            if candidate < position.stop_loss - 1e-9 and candidate <= position.stop_loss - step + 1e-9:
                position.stop_loss = candidate
        return None


@dataclass(frozen=True)
class PendingStopConfig:
    """Paper pending hypotheses; never connects to a trading terminal."""

    anchor_mode: Literal["fixed_close", "rolling_extrema"] = "fixed_close"
    opposite_policy: Literal["oco", "retain"] = "oco"
    entry_distance_price: float = 1.0
    entry_fill_mode: Literal["level", "quote"] = "level"
    price_digits: int = 2
    execution: Scalping456Config = Scalping456Config()
    require_valid_trail: bool = False  # False preserves archived ideal-paper controls.

    def __post_init__(self):
        if self.anchor_mode not in ("fixed_close", "rolling_extrema") or self.opposite_policy not in ("oco", "retain"):
            raise ValueError("Unknown pending anchor/opposite policy")
        if self.entry_fill_mode not in ("level", "quote"):
            raise ValueError("Unknown pending fill mode")
        if not isfinite(self.entry_distance_price) or self.entry_distance_price <= 0:
            raise ValueError("Pending distance must be positive and finite")
        if not isinstance(self.price_digits, int) or not 0 <= self.price_digits <= 10:
            raise ValueError("Invalid pending price precision")
        if not isinstance(self.execution, Scalping456Config):
            raise ValueError("Pending execution must be an explicit research config")
        if not isinstance(self.require_valid_trail, bool):
            raise ValueError("Trailing proposal guard must be boolean")


def pending_price(value: float, digits: int) -> float:
    return float(Decimal(str(value)).quantize(Decimal(1).scaleb(-digits), rounding=ROUND_HALF_UP))


@dataclass(frozen=True)
class PendingStop:
    side: Side
    price: float
    created_quote_sequence: int


@dataclass(frozen=True)
class PendingTradeEvent:
    time: datetime
    action: Literal["entry", "exit"]
    position_id: int  # Generated local identity, NEVER a source ticket.
    side: Side
    price: float
    volume: float
    reason: str


class PendingStopStrategy:
    """Independent per-side positions with causal paper pending lifecycle.

    Stops -> existing pending fills -> trailing -> new/replacement pending.
    One position per side; no inferred manual, close-by or recovery trigger.
    The opening quote is not reused to stop/trail a newly opened position.
    """

    def __init__(self, config: PendingStopConfig):
        self.config = config
        self.pending: dict[Side, PendingStop] = {}
        self.positions: dict[Side, tuple[int, Position]] = {}
        self.reference_price: float | None = None
        self.low_ask: float | None = None
        self.high_bid: float | None = None
        self.last_tick_time: datetime | None = None
        self.quote_sequence = 0
        self.next_position_id = 0

    def _desired_level(self, side):
        if self.config.anchor_mode == "fixed_close":
            value = self.reference_price + (1 if side is Side.BUY else -1) * self.config.entry_distance_price
        else:
            value = self.low_ask + self.config.entry_distance_price if side is Side.BUY else self.high_bid - self.config.entry_distance_price
        return pending_price(value, self.config.price_digits)

    def _place_after_quote(self, tick):
        if self.config.opposite_policy == "oco" and self.positions:
            return
        flat = not self.positions
        if flat:
            self.low_ask = min(self.low_ask, tick.ask)
            self.high_bid = max(self.high_bid, tick.bid)
        for side in (Side.BUY, Side.SELL):
            if side in self.positions:
                continue
            old = self.pending.get(side)
            desired = self._desired_level(side)
            if old is not None:
                if self.config.anchor_mode != "rolling_extrema" or not flat:
                    continue
                desired = min(old.price, desired) if side is Side.BUY else max(old.price, desired)
                if desired == old.price:
                    continue
            valid = desired > tick.ask + 1e-9 if side is Side.BUY else desired < tick.bid - 1e-9
            if valid:
                self.pending[side] = PendingStop(side, desired, self.quote_sequence)

    def on_tick(self, tick: Tick) -> list[PendingTradeEvent]:
        if self.last_tick_time is not None and tick.time < self.last_tick_time:
            raise ValueError("Ticks must be chronological")
        self.last_tick_time = tick.time
        self.quote_sequence += 1
        if self.reference_price is None:
            self.reference_price = (tick.bid + tick.ask) / 2
            self.low_ask, self.high_bid = tick.ask, tick.bid
            self._place_after_quote(tick)
            return []
        execution = self.config.execution
        events = []
        survivors = set(self.positions)
        for side in (Side.BUY, Side.SELL):
            if side not in self.positions:
                continue
            identity, position = self.positions[side]
            quote = tick.bid if side is Side.BUY else tick.ask
            hit = quote <= position.stop_loss if side is Side.BUY else quote >= position.stop_loss
            if hit:
                price = position.stop_loss if execution.stop_fill_mode == "level" else quote
                events.append(PendingTradeEvent(tick.time, "exit", identity, side, price, execution.volume, "stop_loss"))
                self.reference_price = price
                del self.positions[side]
                survivors.remove(side)
        if events and not self.positions:
            self.low_ask, self.high_bid = tick.ask, tick.bid
        breached = []
        for side, pending in self.pending.items():
            quote = tick.ask if side is Side.BUY else tick.bid
            excursion = quote - pending.price if side is Side.BUY else pending.price - quote
            if pending.created_quote_sequence < self.quote_sequence and excursion >= -1e-9:
                breached.append((excursion, side is Side.BUY, side))
        for _, _, side in sorted(breached, reverse=True):
            if side not in self.pending or side in self.positions:
                continue
            pending = self.pending.pop(side)
            price = pending.price if self.config.entry_fill_mode == "level" else tick.ask if side is Side.BUY else tick.bid
            stop = price - execution.initial_stop_price if side is Side.BUY else price + execution.initial_stop_price
            identity = self.next_position_id
            self.next_position_id += 1
            self.positions[side] = (identity, Position(side, tick.time, price, stop, tick.bid, tick.ask))
            events.append(PendingTradeEvent(tick.time, "entry", identity, side, price, execution.volume, "pending_stop_" + side.value))
            if self.config.opposite_policy == "oco":
                self.pending.clear()
        for side in survivors:
            _, position = self.positions[side]
            if side is Side.BUY:
                position.best_bid = max(position.best_bid, tick.bid)
                gain = (position.best_bid - position.entry_price) / execution.point
                candidate = position.best_bid - execution.trailing_distance_price
                improves = candidate > position.stop_loss + 1e-9 and candidate >= position.stop_loss + execution.trailing_step_points * execution.point - 1e-9
            else:
                position.best_ask = min(position.best_ask, tick.ask)
                gain = (position.entry_price - position.best_ask) / execution.point
                candidate = position.best_ask + execution.trailing_distance_price
                improves = candidate < position.stop_loss - 1e-9 and candidate <= position.stop_loss - execution.trailing_step_points * execution.point + 1e-9
            valid = (candidate < tick.bid - 1e-9 if side is Side.BUY else candidate > tick.ask + 1e-9) if self.config.require_valid_trail else True
            if gain >= execution.trailing_activation_points - 1e-7 and improves and valid:
                position.stop_loss = candidate
        self._place_after_quote(tick)
        return events


@dataclass(frozen=True)
class ClosedBar:
    """Actual completed OHLC, with explicit availability time."""

    open_time: datetime
    minutes: int
    open: float
    high: float
    low: float
    close: float

    def __post_init__(self) -> None:
        if self.open_time.utcoffset() is None or self.minutes not in (1, 5, 15, 30, 60):
            raise ValueError("Bar requires aware time and supported timeframe")
        if any(not isfinite(value) or value <= 0 for value in (self.open, self.high, self.low, self.close)):
            raise ValueError("Invalid OHLC values")
        if self.low > min(self.open, self.close) or self.high < max(self.open, self.close) or self.low > self.high:
            raise ValueError("Invalid OHLC range")

    @property
    def close_time(self) -> datetime:
        return self.open_time + timedelta(minutes=self.minutes)


@dataclass(frozen=True)
class ClosedCandleConfig:
    minutes: int = 1
    entry_mode: Literal["body", "engulf", "breakout"] = "body"
    breakout_buffer_price: float = .01
    body_min_price: float = 0
    allow_breakout_reentry: bool = True

    def __post_init__(self) -> None:
        if self.minutes not in (1, 5, 15, 30, 60) or self.entry_mode not in ("body", "engulf", "breakout"):
            raise ValueError("Invalid closed-candle hypothesis")
        if any(not isfinite(value) or value < 0 for value in (self.breakout_buffer_price, self.body_min_price)):
            raise ValueError("Invalid closed-candle thresholds")


class ClosedCandleStrategy(Scalping456Strategy):
    """Past-closed-bar entry hypotheses; stops/trailing remain tick-driven.

    Caller delivers each new bar exactly once, only on/after its closing time.
    No ledger, date-based actions, current-bar OHLC or synthetic tick path.
    """

    def __init__(self, candle: ClosedCandleConfig | None = None,
                 execution: Scalping456Config | None = None) -> None:
        super().__init__(execution)
        self.candle = candle or ClosedCandleConfig()
        self.closed_bars: deque[ClosedBar] = deque(maxlen=2)
        self._used_bar_open: datetime | None = None

    def reset(self) -> None:
        super().reset()
        self.closed_bars.clear()
        self._used_bar_open = None

    def on_tick(self, tick: Tick, closed_bars: tuple[ClosedBar, ...] = ()) -> EntrySignal | ExitSignal | None:
        prior_open = self.closed_bars[-1].open_time if self.closed_bars else None
        for bar in closed_bars:
            if bar.minutes != self.candle.minutes or bar.close_time > tick.time:
                raise ValueError("Future/wrong-timeframe bar must not be consumed")
            if prior_open is not None and bar.open_time <= prior_open:
                raise ValueError("Closed bars must arrive once in chronological order")
            prior_open = bar.open_time
        self._check_time(tick)
        self.closed_bars.extend(closed_bars)
        if self.position is not None:
            return self._on_position_tick(tick)
        if not self.closed_bars:
            return None
        bar = self.closed_bars[-1]
        once = self.candle.entry_mode != "breakout" or not self.candle.allow_breakout_reentry
        if once and self._used_bar_open == bar.open_time:
            return None
        body = bar.close - bar.open
        if self.candle.entry_mode == "body":
            buy = body > 0 and body >= self.candle.body_min_price
            sell = body < 0 and -body >= self.candle.body_min_price
        elif self.candle.entry_mode == "engulf":
            if len(self.closed_bars) < 2:
                return None
            prior = self.closed_bars[-2]
            buy = (prior.close < prior.open and body > 0 and bar.open <= prior.close
                   and bar.close >= prior.open and body >= self.candle.body_min_price)
            sell = (prior.close > prior.open and body < 0 and bar.open >= prior.close
                    and bar.close <= prior.open and -body >= self.candle.body_min_price)
        else:
            buy = tick.bid >= bar.high + self.candle.breakout_buffer_price - 1e-9
            sell = tick.bid <= bar.low - self.candle.breakout_buffer_price + 1e-9
        if not buy and not sell:
            return None
        self._used_bar_open = bar.open_time
        return self._open_position(tick, Side.BUY if buy else Side.SELL,
                                   f"closed_{self.candle.entry_mode}_M{self.candle.minutes}")


class FixedVol20GridStrategy:
    """Second-engine candidate for ``FixedVol20`` basket orders.

    This candidate has no inferred emergency stop. Reported SL fields were zero
    but that does not rule out internal EA risk controls. A basket reached 174
    lots before a large loss. Emergency behavior has not been reconstructed.
    """

    def __init__(self, config: FixedVol20Config | None = None) -> None:
        self.config = config or FixedVol20Config.late_fifteen_dollar()
        self.side: Side | None = None
        self.legs: list[BasketLeg] = []
        self.take_profit: float | None = None
        self.running_low_ask: float | None = None
        self.running_high_bid: float | None = None
        self.flat_reference_price: float | None = None
        self.last_tick_time: datetime | None = None

    @property
    def total_volume(self) -> float:
        return sum(leg.volume for leg in self.legs)

    @property
    def weighted_average_entry(self) -> float | None:
        total = self.total_volume
        if total == 0:
            return None
        return sum(leg.price * leg.volume for leg in self.legs) / total

    def _next_volume(self) -> float:
        if not self.legs or self.config.fixed_volume:
            return self.config.initial_volume
        raw = self.legs[-1].volume * self.config.volume_multiplier
        rounded_half_up = int(raw * 10.0 + 0.5 + 1e-9) / 10.0
        return min(self.config.max_volume, rounded_half_up)

    def _recalculate_take_profit(self) -> float:
        average = self.weighted_average_entry
        assert average is not None and self.side is not None
        offset = self.config.basket_target_price
        target = average + offset if self.side is Side.BUY else average - offset
        self.take_profit = (float(Decimal(str(target)).quantize(
            Decimal(1).scaleb(-self.config.price_digits), rounding=ROUND_HALF_UP))
            if self.config.target_rounding == "half_up" else round(target, self.config.price_digits))
        return self.take_profit

    def _add_leg(
        self,
        tick: Tick,
        side: Side,
        reason: Literal["initial_reversal", "adverse_grid_step"],
        fill_price: float | None = None,
    ) -> BasketEntrySignal:
        price = fill_price if fill_price is not None else tick.ask if side is Side.BUY else tick.bid
        volume = self._next_volume()
        self.side = side
        self.legs.append(BasketLeg(time=tick.time, price=price, volume=volume))
        target = self._recalculate_take_profit()
        return BasketEntrySignal(
            time=tick.time,
            side=side,
            price=price,
            volume=volume,
            level=len(self.legs),
            basket_take_profit=target,
            reason=reason,
        )

    def _reset_after_exit(self, tick: Tick, fill_price: float) -> None:
        self.side = None
        self.legs.clear()
        self.take_profit = None
        self.running_low_ask = tick.ask
        self.running_high_bid = tick.bid
        self.flat_reference_price = fill_price

    def on_tick(self, tick: Tick) -> BasketEntrySignal | BasketExitSignal | None:
        if self.last_tick_time is not None and tick.time < self.last_tick_time:
            raise ValueError("Ticks must be supplied in chronological order")
        self.last_tick_time = tick.time

        if not self.legs:
            if self.running_low_ask is None:
                self.running_low_ask = tick.ask
                self.running_high_bid = tick.bid
                self.flat_reference_price = (tick.ask + tick.bid) / 2
                return None
            self.running_low_ask = min(self.running_low_ask, tick.ask)
            self.running_high_bid = max(self.running_high_bid or tick.bid, tick.bid)
            if self.config.entry_mode == "fixed_close":
                assert self.flat_reference_price is not None
                rise = tick.ask - self.flat_reference_price
                fall = self.flat_reference_price - tick.bid
            else:
                rise = tick.ask - self.running_low_ask
                fall = self.running_high_bid - tick.bid
            threshold = self.config.entry_reversal_price
            if rise < threshold and fall < threshold:
                return None
            side = Side.BUY if rise >= threshold and (fall < threshold or rise >= fall) else Side.SELL
            return self._add_leg(tick, side, "initial_reversal")

        assert self.side is not None and self.take_profit is not None
        target_hit = (
            tick.bid >= self.take_profit
            if self.side is Side.BUY
            else tick.ask <= self.take_profit
        )
        if target_hit:
            signal = BasketExitSignal(
                time=tick.time,
                side=self.side,
                price=self.take_profit,
                positions=len(self.legs),
                total_volume=self.total_volume,
            )
            self._reset_after_exit(tick, signal.price)
            return signal

        last_entry = self.legs[-1].price
        adverse = (
            last_entry - tick.ask
            if self.side is Side.BUY
            else tick.bid - last_entry
        )
        if adverse >= self.config.grid_step_price:
            # This pending level exists before the crossing tick. It is not
            # copied from actual source fills, and adds remain one leg per tick.
            fill = (last_entry - self.config.grid_step_price if self.side is Side.BUY
                    else last_entry + self.config.grid_step_price) if self.config.grid_fill_mode == "level" else None
            return self._add_leg(tick, self.side, "adverse_grid_step", fill)
        return None


def strategy_scalping456(
    strategy: Scalping456Strategy,
    *,
    time: datetime,
    bid: float,
    ask: float,
) -> EntrySignal | ExitSignal | None:
    """Small functional adapter for scanners/backtesters."""

    return strategy.on_tick(Tick(time=time, bid=bid, ask=ask))


__all__ = [
    "EntrySignal",
    "ExitSignal",
    "BasketEntrySignal",
    "BasketExitSignal",
    "BasketLeg",
    "CloseByPosition",
    "CloseByExit",
    "ClosedBar",
    "ClosedCandleConfig",
    "ClosedCandleStrategy",
    "FixedVol20Config",
    "FixedVol20GridStrategy",
    "Scalping456Config",
    "Scalping456Strategy",
    "Side",
    "Tick",
    "strategy_scalping456",
    "settle_close_by",
]
