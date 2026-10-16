"""Experimental demo-only broker adapter; no historical regimes or feed offsets.

Owns only MAGIC + SYMBOL. Native pending stops and protective SL stay at the
broker; actual fills/latency are observed, never synthesized from the simulator.
"""

import json
import math
import os
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
from pathlib import Path


KEY = "SCALPING456"
MAGIC = 995456
PROFILE = "demo-iux-2101182459"
LOGIN = 2101182459
SERVER = "IUXMarkets-Demo"
SYMBOL = "XAUUSD.iux"
ENTRY_PROFILE = "demo-exness-434237129"
BKK = timezone(timedelta(hours=7))


@dataclass(frozen=True)
class Target:
    login: int
    server: str
    symbol: str


# The old profile remains supported for draining only. Never copy its state.
TARGETS = {
    PROFILE: Target(LOGIN, SERVER, SYMBOL),
    ENTRY_PROFILE: Target(434237129, "Exness-MT5Trial7", "XAUUSDm"),
}


def target_for(profile_dir):
    target = TARGETS.get(Path(profile_dir).name)
    if target is None:
        raise RuntimeError("Scalping456 profile is not allowlisted")
    return target


@dataclass(frozen=True)
class Params:
    lot: float = .01  # legacy fixed sizing only when risk_percent == 0
    entry_distance: float = 1.30  # latest decoded E4 candidate, not an account-wide lot regime
    initial_stop: float = 1.0
    trail_activation: float = .20
    trail_distance: float = .20
    trail_step: float = .01
    reaction_seconds: float = 0.0  # E4: re-arm on the first observed close, no synthetic latency
    modify_interval: float = .270
    first_trail_delay: float = .900
    max_exposure_slots: int = 3  # own positions + potentially filled pending
    daily_net_loss_limit: float = 20.0  # new-entry gate, not forced liquidation
    risk_percent: float = 1.0  # equity / submitted initial-SL price loss, per new order

    def __post_init__(self):
        values = (self.lot, self.entry_distance, self.initial_stop, self.trail_activation,
                  self.trail_distance, self.trail_step,
                  self.modify_interval, self.first_trail_delay, self.daily_net_loss_limit)
        if (any(not math.isfinite(v) or v <= 0 for v in values) or self.max_exposure_slots < 2
                or not math.isfinite(self.risk_percent) or not 0 <= self.risk_percent <= 100
                or not math.isfinite(self.reaction_seconds) or self.reaction_seconds < 0):
            raise ValueError("Invalid forward risk/execution parameters")


def preflight(broker, profile_dir, params=Params()):
    """Read-only identity/spec/book checks; never initialize/login/select/send."""
    profile_dir = Path(profile_dir).resolve()
    target = target_for(profile_dir)
    account, terminal = broker.account_info(), broker.terminal_info()
    if (account is None or terminal is None
            or account.login != target.login or account.server != target.server
            or account.trade_mode != broker.ACCOUNT_TRADE_MODE_DEMO
            or account.margin_mode != broker.ACCOUNT_MARGIN_MODE_RETAIL_HEDGING
            or Path(terminal.path).resolve() != (profile_dir / "mt5").resolve()
            or not terminal.connected):
        raise RuntimeError("Scalping456 demo account/server/hedging/path guard rejected")
    info = broker.symbol_info(target.symbol)
    if info is None or not info.visible:
        raise RuntimeError("Scalping456 configured gold symbol unavailable/hidden")
    quantum = float(info.trade_tick_size or info.point)
    minimum = float(info.trade_stops_level) * float(info.point)
    freeze = float(info.trade_freeze_level) * float(info.point)
    if (quantum <= 0 or any(not math.isfinite(v) or v <= 0 for v in
                           (info.volume_min, info.volume_max, info.volume_step))
            or info.volume_min > info.volume_max
            or (params.risk_percent == 0 and (params.lot < info.volume_min - 1e-9
                or params.lot > info.volume_max + 1e-9
                or abs(params.lot / info.volume_step - round(params.lot / info.volume_step)) > 1e-7))
            or minimum > min(params.entry_distance, params.initial_stop, params.trail_distance) + 1e-9):
        raise RuntimeError("Scalping456 execution parameters incompatible with broker specs")
    return account, terminal, info, quantum, max(minimum, freeze)


class ForwardScalper:
    def __init__(self, broker, profile_dir, params=Params(), clock=time.monotonic):
        self.broker, self.directory, self.params, self.clock = broker, Path(profile_dir), params, clock
        self.target = target_for(self.directory)
        self.symbol = self.target.symbol
        self.path = self.directory / "scalping456_state.json"
        self.journal = self.directory / "logs/scalping456_events.jsonl"
        self.state = {"version": 1, "magic": MAGIC, "login": self.target.login, "symbol": self.symbol,
                      "phase": "idle", "known_positions": {}, "pending_closes": {},
                      "closed_positions": {}, "daily_net": {}, "cycles": 0, "last_error": "", "rearm_requested": True}
        if self.path.exists():
            self.state = json.loads(self.path.read_text(encoding="utf-8"))
            if (self.state.get("version") != 1 or self.state.get("magic") != MAGIC
                    or self.state.get("login") != self.target.login or self.state.get("symbol") != self.symbol):
                raise RuntimeError("Scalping456 state identity mismatch")
            if self.state["phase"] in ("submitting", "arming"):
                self.state.update(phase="halted", last_error="Restart after unacknowledged trade intent; review journal")
        self.last_tick = None
        self.tick_changed_at = self.clock()
        self.live_tick_seen = False
        self.due = self.clock() + params.reaction_seconds
        self.first_seen, self.last_modify = {}, {}
        self._lock = None
        self.state.setdefault("known_orders", {})
        if not self.state.get("journal_orders_recovered"):
            # One-time migration also catches native fills/exits missed between polls.
            last_request = {}
            if self.journal.exists():
                for line in self.journal.read_text(encoding="utf-8").splitlines():
                    event = json.loads(line)
                    if event.get("event") == "request":
                        last_request = event.get("request", {})
                    elif (event.get("event") == "response" and event.get("order")
                          and last_request.get("action") == broker.TRADE_ACTION_PENDING
                          and event.get("retcode") in (broker.TRADE_RETCODE_DONE, broker.TRADE_RETCODE_PLACED)):
                        self.state["known_orders"][str(event["order"])] = True
            self.state["journal_orders_recovered"] = True

    def _acquire(self):
        if self._lock is not None:
            return
        lock = (self.directory / "scalping456.lock").open("a+b")
        if os.name == "nt":
            import msvcrt
            try:
                # Do not read the already locked byte: Windows denies that read.
                if os.fstat(lock.fileno()).st_size == 0:
                    lock.write(b"0"); lock.flush()
                lock.seek(0)
                msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError:
                lock.close()
                raise RuntimeError("Another Scalping456 runner owns this profile")
        else:
            import fcntl
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                lock.close()
                raise RuntimeError("Another Scalping456 runner owns this profile")
        self._lock = lock

    def close(self):
        if self._lock is not None:
            self._lock.close()
            self._lock = None

    def _save(self):
        tmp = self.path.with_suffix(f".json.{os.getpid()}.tmp")
        with tmp.open("w", encoding="utf-8", newline="\n") as handle:
            json.dump(self.state, handle, ensure_ascii=False, allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, self.path)

    def _event(self, event, **fields):
        self.journal.parent.mkdir(parents=True, exist_ok=True)
        with self.journal.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps({"bkk": datetime.now(BKK).isoformat(), "event": event, "magic": MAGIC,
                                    "last_observed_quote": getattr(self, "latest_quote", None), **fields},
                                    ensure_ascii=False, allow_nan=False) + "\n")
            handle.flush()
            os.fsync(handle.fileno())

    def _book(self):
        positions, orders = self.broker.positions_get(), self.broker.orders_get()
        if positions is None or orders is None:
            raise RuntimeError("Scalping456 broker snapshot unavailable; no new orders")
        if any(p.magic == MAGIC and p.symbol != self.symbol for p in (*positions, *orders)):
            raise RuntimeError("Scalping456 magic collision on another symbol")
        return ([p for p in positions if p.magic == MAGIC and p.symbol == self.symbol],
                [o for o in orders if o.magic == MAGIC and o.symbol == self.symbol], len(orders))

    def _send(self, request, creates_order=False):
        account, terminal, info, _, _ = preflight(self.broker, self.directory, self.params)
        if not account.trade_allowed or not terminal.trade_allowed:
            return False
        b = self.broker
        if request.get("magic") != MAGIC or request.get("symbol") != self.symbol:
            raise RuntimeError("Refuse foreign trade request")
        if request["action"] not in (b.TRADE_ACTION_PENDING, b.TRADE_ACTION_REMOVE, b.TRADE_ACTION_SLTP):
            raise RuntimeError("Market open/close is not authorized in this adapter")
        creates_order = request["action"] == b.TRADE_ACTION_PENDING
        if request["action"] in (b.TRADE_ACTION_REMOVE, b.TRADE_ACTION_SLTP):
            positions, orders, _ = self._book()
            target = request.get("order") if request["action"] == b.TRADE_ACTION_REMOVE else request.get("position")
            if target not in {p.ticket for p in (orders if request["action"] == b.TRADE_ACTION_REMOVE else positions)}:
                return False
        if creates_order:
            if (request.get("type") not in (b.ORDER_TYPE_BUY_STOP, b.ORDER_TYPE_SELL_STOP)
                    or not request.get("sl") or not self._valid_volume(request.get("volume"), info)
                    or (self.params.risk_percent == 0 and request["volume"] != self.params.lot)):
                raise RuntimeError("Invalid protected pending sizing intent")
            if self.params.risk_percent:
                # Recheck the budget immediately before each native submission.
                try:
                    budget = self._risk_budget(account)
                    loss = self._stop_loss(request["type"], request["volume"], request["price"], request["sl"])
                except RuntimeError as exc:
                    self.state["last_error"] = str(exc)
                    self._event("risk_block", reason=str(exc))
                    return False
                if loss > budget + 1e-9:
                    self.state["last_error"] = "Equity/risk changed before submission; retry sizing"
                    self._event("risk_block", planned_loss=loss, risk_budget=budget)
                    return False
            self.state["phase"] = "submitting"
            self._save()  # durable intent BEFORE side effect; restart cannot blindly resubmit
        self._event("request", request=request)
        try:
            sent_at = self.clock()
            result = b.order_send(request)
        except Exception as exc:
            self.state.update(phase="halted", last_error=f"Uncertain order_send: {type(exc).__name__}")
            self._save()
            self._event("uncertain", action=request["action"])
            return False
        if result is None:
            self.state.update(phase="halted", last_error="Uncertain empty broker acknowledgement; manual review required")
            self._save()
            self._event("uncertain", action=request["action"])
            return False
        ok = result.retcode in (b.TRADE_RETCODE_DONE, b.TRADE_RETCODE_PLACED, b.TRADE_RETCODE_NO_CHANGES)
        if creates_order and ok and not getattr(result, "order", 0):
            self.state.update(phase="halted", last_error="Successful pending response without ticket")
            self._save()
            return False
        self._event("response", retcode=result.retcode, order=getattr(result, "order", 0),
                    elapsed_ms=(self.clock() - sent_at) * 1000, comment=str(getattr(result, "comment", "")))
        if creates_order:
            if ok:
                self.state["known_orders"][str(result.order)] = True
            self.state.update(phase="arming" if ok else "cooldown", last_error="" if ok else f"Pending rejected {result.retcode}")
            self._save()
        return ok

    def _cancel(self, orders):
        ok = True
        for o in orders:
            ok = self._send({"action": self.broker.TRADE_ACTION_REMOVE, "order": o.ticket, "symbol": self.symbol, "magic": MAGIC}) and ok
        return ok

    def _acknowledged_pending(self, ticket):
        """Cancellation stubs have no entry deals: require the original journal ack."""
        request = None
        if self.journal.exists():
            for line in self.journal.read_text(encoding="utf-8").splitlines():
                event = json.loads(line)
                if event.get("event") == "request":
                    request = event.get("request", {})
                elif event.get("event") in ("response", "uncertain"):
                    if (event.get("event") == "response" and event.get("order") == ticket
                            and event.get("retcode") in (self.broker.TRADE_RETCODE_DONE, self.broker.TRADE_RETCODE_PLACED)
                            and request and request.get("action") == self.broker.TRADE_ACTION_PENDING
                            and request.get("magic") == MAGIC and request.get("symbol") == self.symbol
                            and isinstance(request.get("volume"), (int, float))
                            and math.isfinite(request["volume"]) and request["volume"] > 0
                            and request.get("type") in (self.broker.ORDER_TYPE_BUY_STOP, self.broker.ORDER_TYPE_SELL_STOP)):
                        return True
                    request = None
        return False

    def _order_deals(self, order):
        """Equivalent DEAL_ORDER lookup when the native ticket filter errors.

        Use broker raw epochs, never a chart/wall-clock offset. Position IDs
        below are search candidates only: the returned DEAL_ORDER must still
        match, and _stub_position_identifier validates ownership/side/volume.
        An empty guessed-position lookup cannot prove an unfilled cancellation.
        """
        b, ticket = self.broker, int(order.ticket)
        deals = b.history_deals_get(ticket=ticket)
        if deals is not None:
            return deals
        setup = int(getattr(order, "time_setup", 0) or 0)
        done = int(getattr(order, "time_done", 0) or 0)
        if 0 < setup <= done:
            ranged = b.history_deals_get(setup, done + 1)
            if ranged is not None:
                return [d for d in ranged if d.order == ticket]
        # Older history stubs can lack timestamps as well as position_id.
        # Never assume the order ticket IS the position identifier.
        candidates = {ticket, int(order.position_id or 0)}
        for key in ("known_positions", "pending_closes"):
            candidates.update(int(v["identifier"]) for v in self.state[key].values())
        matched = []
        for identifier in sorted(candidates - {0}):
            records = b.history_deals_get(position=identifier)
            if records is None:
                continue
            if any(d.position_id != identifier for d in records):
                raise RuntimeError("Scalping456 position history identifier mismatch")
            matched.extend(d for d in records if d.order == ticket)
        return matched or None

    def _stub_position_identifier(self, order):
        """Exness may strip history-order magic; entry DEAL_ORDER must prove it.

        known_orders was populated from an owned live order or acknowledged
        submission. Never treat a zero-magic history row, or its ticket alone,
        as proof of a fill/position. Unknown/incomplete deal history must wait.
        """
        b = self.broker
        if (self.directory.name != ENTRY_PROFILE or order.magic != 0
                or order.state not in (b.ORDER_STATE_FILLED, b.ORDER_STATE_CANCELED,
                                       b.ORDER_STATE_EXPIRED, b.ORDER_STATE_REJECTED)
                or order.type not in (b.ORDER_TYPE_BUY_STOP, b.ORDER_TYPE_SELL_STOP)):
            raise RuntimeError("Scalping456 order history identity mismatch")
        deals = self._order_deals(order)
        if deals is None:
            return None
        if not deals:
            if order.state == b.ORDER_STATE_FILLED:
                return None
            if not self._acknowledged_pending(int(order.ticket)):
                raise RuntimeError("Scalping456 cancelled history order lacks ownership proof")
            return 0
        expected_side = b.ORDER_TYPE_BUY if order.type == b.ORDER_TYPE_BUY_STOP else b.ORDER_TYPE_SELL
        if any(d.order != order.ticket or d.symbol != self.symbol or d.magic != MAGIC
               or d.entry != b.DEAL_ENTRY_IN or d.type != expected_side
               or d.ticket <= 0 or d.position_id <= 0 or not math.isfinite(d.volume) or d.volume <= 0 for d in deals):
            raise RuntimeError("Scalping456 entry deal ownership mismatch")
        identifiers = {int(d.position_id) for d in deals}
        if len(identifiers) != 1:
            raise RuntimeError("Scalping456 ambiguous history position identifier")
        identifier = identifiers.pop()
        if order.position_id and order.position_id != identifier:
            raise RuntimeError("Scalping456 order/deal position identifier mismatch")
        filled = sum(float(d.volume) for d in self._unique_deals(deals))
        expected = float(order.volume_initial)
        if not math.isfinite(expected) or expected <= 0 or filled > expected + 1e-9:
            raise RuntimeError("Scalping456 history fill volume mismatch")
        if order.state == b.ORDER_STATE_FILLED and abs(filled - expected) > 1e-9:
            return None
        return identifier

    @staticmethod
    def _unique_deals(deals):
        unique = {}
        for d in deals:
            if d.ticket <= 0 or (d.ticket in unique and d != unique[d.ticket]):
                raise RuntimeError("Scalping456 conflicting history deal ticket")
            unique[d.ticket] = d
        return list(unique.values())

    def _resolve_closes(self, live_identifiers=()):
        b = self.broker
        confirmed_new_close = False
        for ticket, saved in list(self.state["pending_closes"].items()):
            identifier_key = str(saved["identifier"])
            if saved["identifier"] in live_identifiers:
                continue
            if ticket in self.state["closed_positions"] or identifier_key in self.state["closed_positions"]:
                del self.state["pending_closes"][ticket]
                self._save()
                continue
            deals = b.history_deals_get(position=saved["identifier"])
            if not deals:
                continue
            # Broker/manual closing deals may carry magic=0. The position identifier
            # was captured only from an owned position; never attribute by symbol alone.
            if any(d.symbol != self.symbol or d.position_id != saved["identifier"] for d in deals):
                raise RuntimeError("Scalping456 close history identity mismatch")
            own = self._unique_deals(deals)
            entries = [d for d in own if d.entry == b.DEAL_ENTRY_IN and d.magic == MAGIC]
            exits = [d for d in own if d.entry in (b.DEAL_ENTRY_OUT, b.DEAL_ENTRY_OUT_BY)]
            if not entries or not exits:
                continue
            if (len(entries) + len(exits) != len(own)
                    or any(d.magic not in (0, MAGIC) or not math.isfinite(d.volume) or d.volume <= 0 for d in own)):
                raise RuntimeError("Scalping456 close history ownership/volume mismatch")
            entered, exited = sum(d.volume for d in entries), sum(d.volume for d in exits)
            if exited > entered + 1e-9:
                raise RuntimeError("Scalping456 exit volume exceeds entry volume")
            if abs(entered - exited) > 1e-9:
                continue  # partial exit / lagging history is not a confirmed full close
            close_ms = max(int(d.time_msc) for d in exits)
            if close_ms <= 0:
                continue  # never book an undated historical close on the recovery day
            net = sum(float(d.profit) + float(d.commission) + float(d.swap) + float(getattr(d, "fee", 0)) for d in own)
            if not math.isfinite(net):
                raise RuntimeError("Scalping456 invalid closed PnL")
            # Whole-position realized net (including entry costs) belongs to the
            # final exit's BKK day, not the day a restart/poll discovers it.
            day = datetime.fromtimestamp(close_ms / 1000, BKK).date().isoformat()
            self.state["daily_net"][day] = self.state["daily_net"].get(day, 0) + net
            self.state["closed_positions"][identifier_key] = net
            self.state["close_rearm_pending"] = True
            confirmed_new_close = True
            del self.state["pending_closes"][ticket]
            self._save()  # accounting + follow-up intent are atomic BEFORE journal I/O
            self._event("closed", ticket=int(identifier_key), net_including_costs=net,
                        close_day_bkk=day, broker_close_time_msc=close_ms)
        return confirmed_new_close

    def _resolve_orders(self, positions, orders):
        """Native pending can fill and stop before positions_get ever sees it."""
        b = self.broker
        live_orders = {str(o.ticket) for o in orders}
        live_positions = {int(getattr(p, "identifier", p.ticket)) for p in positions}
        changed = False
        for ticket in live_orders:
            if ticket not in self.state["known_orders"]:
                self.state["known_orders"][ticket] = True
                changed = True
        for ticket in list(self.state["known_orders"]):
            if ticket in live_orders:
                continue
            history = b.history_orders_get(ticket=int(ticket))
            if history is None or not history:
                continue  # unknown is not a cancelled order; do not re-submit
            order = next((o for o in history if o.ticket == int(ticket) and o.symbol == self.symbol), None)
            if order is None:
                raise RuntimeError("Scalping456 order history identity mismatch")
            identity = None
            if order.magic != MAGIC:
                identity = self._stub_position_identifier(order)
                if identity is None:
                    continue
            if order.state == b.ORDER_STATE_FILLED or identity:
                identity = identity or int(order.position_id or order.ticket)
                if identity not in live_positions and str(identity) not in self.state["closed_positions"]:
                    self.state["pending_closes"].setdefault(str(identity), {"identifier": identity})
                self._event("pending_fill_history", order=int(ticket), position_identifier=identity)
            elif order.state not in (b.ORDER_STATE_CANCELED, b.ORDER_STATE_EXPIRED, b.ORDER_STATE_REJECTED):
                continue
            del self.state["known_orders"][ticket]
            changed = True
        if changed:
            self._save()

    @staticmethod
    def _price(value, quantum, up=False):
        d, q = Decimal(str(value)), Decimal(str(quantum))
        return float((d / q).to_integral_value(rounding=ROUND_CEILING if up else ROUND_FLOOR) * q)

    @staticmethod
    def _valid_volume(volume, info):
        return (isinstance(volume, (int, float)) and math.isfinite(volume)
                and info.volume_min - 1e-9 <= volume <= info.volume_max + 1e-9
                and abs(volume / info.volume_step - round(volume / info.volume_step)) <= 1e-7)

    def _risk_budget(self, account):
        equity = float(getattr(account, "equity", 0) or 0)
        if not math.isfinite(equity) or equity <= 0:
            raise RuntimeError("Scalping456 equity unavailable; no risk-sized entry")
        return equity * self.params.risk_percent / 100

    def _stop_loss(self, pending_type, volume, entry, stop):
        buy = pending_type == self.broker.ORDER_TYPE_BUY_STOP
        if not all(math.isfinite(v) and v > 0 for v in (entry, stop)) or (stop >= entry if buy else stop <= entry):
            raise RuntimeError("Scalping456 invalid initial SL for risk sizing")
        side = self.broker.ORDER_TYPE_BUY if buy else self.broker.ORDER_TYPE_SELL
        profit = self.broker.order_calc_profit(side, self.symbol, volume, entry, stop)
        if profit is None or not math.isfinite(profit) or profit >= 0:
            raise RuntimeError("Scalping456 SL loss calculation unavailable; no new entry")
        return -float(profit)

    def _entry_volume(self, pending_type, entry, stop, account, info):
        if self.params.risk_percent == 0:
            return self.params.lot
        budget = self._risk_budget(account)
        reference = self._price(min(1.0, info.volume_max), info.volume_step)
        reference = max(reference, info.volume_min)
        unit_loss = self._stop_loss(pending_type, reference, entry, stop) / reference
        volume = self._price(min(budget / unit_loss, info.volume_max), info.volume_step)
        if not self._valid_volume(volume, info):
            raise RuntimeError("Scalping456 minimum lot exceeds risk budget; no new entry")
        loss = self._stop_loss(pending_type, volume, entry, stop)
        if loss > budget + 1e-9:
            # Profit/currency rounding must never round the lot UP over budget.
            volume = self._price(volume * budget / loss, info.volume_step)
            if (not self._valid_volume(volume, info)
                    or self._stop_loss(pending_type, volume, entry, stop) > budget + 1e-9):
                raise RuntimeError("Scalping456 no broker-valid volume within risk budget")
        return volume

    def step(self, active):
        self._acquire()
        if self.state["phase"] in ("submitting", "arming"):
            self.state.update(phase="halted", last_error="Incomplete pair/acknowledgement; review journal")
            self._save()
        account, terminal, info, quantum, stop_guard = preflight(self.broker, self.directory, self.params)
        positions, orders, total_orders = self._book()
        now, b, p = self.clock(), self.broker, self.params
        current = {str(v.ticket): {"identifier": int(getattr(v, "identifier", v.ticket))} for v in positions}
        live_identifiers = {v["identifier"] for v in current.values()}
        for ticket, value in list(self.state["pending_closes"].items()):
            if value["identifier"] in live_identifiers:
                del self.state["pending_closes"][ticket]
        known = self.state["known_positions"]
        vanished = set(known) - set(current)
        for ticket in vanished:
            self.state["pending_closes"][ticket] = known[ticket]
            self.first_seen.pop(ticket, None)
            self.last_modify.pop(ticket, None)
        for ticket in current:
            self.state["pending_closes"].pop(ticket, None)
            if ticket not in known:
                self.first_seen[ticket] = now
                live = next(v for v in positions if str(v.ticket) == ticket)
                self._event("fill_seen", ticket=int(ticket), side=int(live.type), volume=float(live.volume),
                            price=float(live.price_open), sl=float(live.sl), tp=float(live.tp),
                            broker_open_time_msc=int(getattr(live, "time_msc", 0)))
        if known != current:
            self.state["known_positions"] = current
            self._save()
        self._resolve_orders(positions, orders)
        history_closed = self._resolve_closes(live_identifiers)
        if history_closed or self.state.get("close_rearm_pending", False):
            cancelled = self._cancel(orders)
            positions, orders, total_orders = self._book()
            if cancelled and not orders:
                self.due = now + p.reaction_seconds
                self.state["rearm_requested"] = True
                self.state["close_rearm_pending"] = False
                self._save()
        day = datetime.now(BKK).date().isoformat()
        loss_paused = self.state["daily_net"].get(day, 0) <= -p.daily_net_loss_limit
        if not active or self.state["phase"] == "halted" or loss_paused:
            self._cancel(orders)
            orders = []
        tick = b.symbol_info_tick(self.symbol)
        if tick is None or not all(math.isfinite(v) and v > 0 for v in (tick.bid, tick.ask)) or tick.ask < tick.bid:
            return
        tick_ms = int(tick.time_msc)
        self.latest_quote = {"broker_time_msc": tick_ms, "bid": float(tick.bid), "ask": float(tick.ask)}
        if self.last_tick is not None and tick_ms > self.last_tick:
            self.live_tick_seen = True
            self.tick_changed_at = now
        elif self.last_tick is not None and tick_ms < self.last_tick:
            self.live_tick_seen = False
        self.last_tick = tick_ms
        fresh = self.live_tick_seen and now - self.tick_changed_at <= 3
        if not fresh:
            return  # observed live updates, not an assumed broker UTC offset
        # Keep protection for owned positions even when opening new cycles is OFF.
        for pos in positions:
            ticket = str(pos.ticket)
            first_seen = self.first_seen.setdefault(ticket, now)
            if now - first_seen < p.first_trail_delay or now - self.last_modify.get(ticket, -1000) < p.modify_interval:
                continue
            buy = pos.type == b.ORDER_TYPE_BUY
            quote = tick.bid if buy else tick.ask
            if pos.sl <= 0:
                candidate = pos.price_open - p.initial_stop if buy else pos.price_open + p.initial_stop
            elif (quote - pos.price_open if buy else pos.price_open - quote) > p.trail_activation:
                candidate = quote - p.trail_distance if buy else quote + p.trail_distance
            else:
                continue
            candidate = self._price(candidate, quantum, up=not buy)
            valid = candidate <= tick.bid - max(stop_guard, quantum) + 1e-9 if buy else candidate >= tick.ask + max(stop_guard, quantum) - 1e-9
            improves = pos.sl <= 0 or (candidate > pos.sl + p.trail_step + 1e-9 if buy else candidate < pos.sl - p.trail_step - 1e-9)
            if valid and improves:
                self.last_modify[ticket] = now
                self._send({"action": b.TRADE_ACTION_SLTP, "position": pos.ticket, "symbol": self.symbol, "magic": MAGIC,
                            "sl": candidate, "tp": float(pos.tp)})
            elif pos.sl <= 0:
                self.state.update(phase="halted", last_error=f"Owned position {pos.ticket} lacks a placeable protective SL; review required")
                self._save()
                self._event("unprotected_position", ticket=pos.ticket)
        if (not active or self.state["phase"] == "halted" or self.state["pending_closes"]
                or self.state.get("close_rearm_pending", False)
                or self.state["daily_net"].get(day, 0) <= -p.daily_net_loss_limit or now < self.due):
            return
        # Re-read before placing a pair; cancellations can race with native fills.
        positions, orders, total_orders = self._book()
        if orders or self.state["known_orders"] or len(positions) + 2 > p.max_exposure_slots:
            return
        # No close => do not continuously add pairs beside the remaining position.
        if positions and not self.state.get("rearm_requested", False):
            return
        if (not account.trade_allowed or not terminal.trade_allowed or info.trade_mode != b.SYMBOL_TRADE_MODE_FULL
                or (account.limit_orders and total_orders + 2 > account.limit_orders - 1)):
            return
        if self.state["phase"] == "cooldown" and now < self.due:
            return
        buy_level = self._price(tick.ask + p.entry_distance, quantum, up=True)
        sell_level = self._price(tick.bid - p.entry_distance, quantum)
        planned = []
        for is_buy, level in ((True, buy_level), (False, sell_level)):
            stop = self._price(level - p.initial_stop if is_buy else level + p.initial_stop, quantum, up=not is_buy)
            pending_type = b.ORDER_TYPE_BUY_STOP if is_buy else b.ORDER_TYPE_SELL_STOP
            volume = self._entry_volume(pending_type, level, stop, account, info)
            request = {"action": b.TRADE_ACTION_PENDING, "symbol": self.symbol, "magic": MAGIC, "volume": volume,
                       "type": b.ORDER_TYPE_BUY_STOP if is_buy else b.ORDER_TYPE_SELL_STOP,
                       "price": level, "sl": stop, "tp": 0.0, "type_time": b.ORDER_TIME_GTC,
                       "type_filling": b.ORDER_FILLING_RETURN, "comment": "M1_S21_S456_B" if is_buy else "M1_S21_S456_S"}
            planned.append(request)
        # Calculate BOTH legs before sending either: missing risk data is not a partial pair.
        self._event("sizing", risk_percent=p.risk_percent, equity=getattr(account, "equity", None),
                    volumes=[r["volume"] for r in planned], entry_prices=[r["price"] for r in planned],
                    initial_stops=[r["sl"] for r in planned])
        for request in planned:
            if not self._send(request, creates_order=True):
                _, remaining, _ = self._book()
                self._cancel(remaining)
                if self.state["phase"] != "halted":
                    self.state["phase"] = "cooldown"
                    self._save()
                self.due = now + 30
                return
        self.state["cycles"] += 1
        self.state["rearm_requested"] = False
        self.state["phase"] = "working"
        self._save()


def status_text(profile_dir, active):
    if Path(profile_dir).name not in TARGETS:
        return "Scalping456: unavailable on this profile (demo allowlist only)"
    target = target_for(profile_dir)
    active = bool(active and Path(profile_dir).name == ENTRY_PROFILE)
    path = Path(profile_dir) / "scalping456_state.json"
    state = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    return (f"Scalping456 experimental demo\nสถานะ: {'🟢 ON' if active else '🔴 OFF'}\n"
            f"{target.symbol} | Magic {MAGIC} | risk {Params().risk_percent:g}% equity per NEW order\n"
            f"Lot from initial SL; fees/slippage excluded | pair may risk 2%, 3 slots may risk 3%\n"
            f"Entry 1.30 / SL 1.00 / trail 0.20 | max own exposure 3\n"
            f"Entry pause at daily net loss $20; existing positions remain protected\n"
            f"Cycles: {state.get('cycles', 0)} | phase: {state.get('phase', 'not started')}\n"
            f"Error: {state.get('last_error') or '-'}\nNot a verified 100% clone; no Vantage quote offsets")
