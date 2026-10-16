"""No broker connection: demo guards, ownership, restart and order failure tests."""

import ast
import json
import tempfile
import unittest
import asyncio
from unittest.mock import Mock, patch
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace as NS

from demo_scalping456 import (BKK, ENTRY_PROFILE, TARGETS, ForwardScalper, LOGIN, MAGIC,
                              Params, PROFILE, SERVER, SYMBOL, preflight, status_text, target_for)


class Broker:
    ACCOUNT_TRADE_MODE_DEMO = 0
    ACCOUNT_MARGIN_MODE_RETAIL_HEDGING = 2
    SYMBOL_TRADE_MODE_FULL = 4
    TRADE_ACTION_PENDING, TRADE_ACTION_SLTP, TRADE_ACTION_REMOVE = 5, 6, 8
    ORDER_TYPE_BUY, ORDER_TYPE_SELL = 0, 1
    ORDER_TYPE_BUY_STOP, ORDER_TYPE_SELL_STOP = 4, 5
    TRADE_RETCODE_DONE, TRADE_RETCODE_PLACED, TRADE_RETCODE_NO_CHANGES = 10009, 10008, 10025
    ORDER_TIME_GTC, ORDER_FILLING_RETURN = 0, 2
    DEAL_ENTRY_IN, DEAL_ENTRY_OUT, DEAL_ENTRY_OUT_BY = 0, 1, 3
    ORDER_STATE_CANCELED, ORDER_STATE_FILLED, ORDER_STATE_REJECTED, ORDER_STATE_EXPIRED = 2, 4, 5, 6

    def __init__(self, directory):
        target = target_for(directory)
        self.symbol = target.symbol
        self.account = NS(login=target.login, server=target.server, trade_mode=0, margin_mode=2,
                          trade_allowed=True, limit_orders=50, equity=100.0, currency='USD')
        self.terminal = NS(path=str(directory / "mt5"), connected=True, trade_allowed=True)
        self.info = NS(visible=True, point=.01, trade_tick_size=.01, trade_stops_level=0, trade_freeze_level=0,
                       volume_min=.01, volume_max=100, volume_step=.01, trade_mode=4)
        self.tick = NS(bid=100.0, ask=100.13, time_msc=3600000)
        self.positions, self.orders, self.sent, self.deals = [], [], [], {}
        self.next_ticket, self.failure = 100, None
        self.order_history = {}

    def account_info(self): return self.account
    def terminal_info(self): return self.terminal
    def symbol_info(self, symbol): return self.info if symbol == self.symbol else None
    def symbol_info_tick(self, symbol): return self.tick
    def positions_get(self): return self.positions
    def orders_get(self): return self.orders
    def order_calc_profit(self, side, symbol, volume, entry, stop):
        return (stop - entry) * volume * 100 * (1 if side == self.ORDER_TYPE_BUY else -1)
    def history_deals_get(self, *dates, position=None, ticket=None):
        if dates:
            start, end = dates
            return tuple(d for deals in self.deals.values() for d in deals
                         if start * 1000 <= d.time_msc < (end + 1) * 1000)
        if ticket is not None:
            return tuple(d for deals in self.deals.values() for d in deals if d.order == ticket)
        return self.deals.get(position, ())
    def history_orders_get(self, ticket):
        if ticket in self.order_history: return (self.order_history[ticket],)
        if any(p.identifier == ticket for p in self.positions) or ticket in self.deals:
            return (NS(ticket=ticket, magic=MAGIC, symbol=self.symbol, state=self.ORDER_STATE_FILLED, position_id=ticket),)
        return ()

    def order_send(self, request):
        self.sent.append(dict(request))
        if self.failure:
            response = self.failure(request)
            if response != "continue": return response
        ticket = 0
        if request["action"] == self.TRADE_ACTION_PENDING:
            self.next_ticket += 1; ticket = self.next_ticket
            self.orders.append(NS(ticket=ticket, magic=request["magic"], symbol=request["symbol"], type=request["type"], sl=request["sl"]))
        elif request["action"] == self.TRADE_ACTION_REMOVE:
            self.order_history[request['order']] = NS(ticket=request['order'], magic=MAGIC, symbol=self.symbol,
                                                     state=self.ORDER_STATE_CANCELED, position_id=0)
            self.orders = [o for o in self.orders if o.ticket != request["order"]]
        else:
            for p in self.positions:
                if p.ticket == request["position"]: p.sl = request["sl"]
        return NS(retcode=self.TRADE_RETCODE_DONE, order=ticket, comment="ok")


def position(ticket=1, magic=MAGIC, side=0, price=100, sl=99):
    return NS(ticket=ticket, identifier=ticket, magic=magic, symbol=SYMBOL, type=side,
              price_open=price, sl=sl, tp=0.0, volume=.01)


def deal(identifier=1, entry=1, magic=MAGIC, symbol=SYMBOL, volume=.01,
         profit=0, commission=0, swap=0, fee=0, ticket=None, order=None,
         time_msc=1792051206831, side=None):
    return NS(ticket=ticket or identifier * 10 + entry, order=identifier if order is None else order,
              position_id=identifier, entry=entry, magic=magic, symbol=symbol, volume=volume,
              profit=profit, commission=commission, swap=swap, fee=fee, time_msc=time_msc,
              type=(0 if entry == 0 else 1) if side is None else side)


class ForwardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.directory = Path(self.temp.name) / PROFILE
        self.directory.mkdir()
        self.now = 0.0
        self.b = Broker(self.directory)
        self.runner = ForwardScalper(self.b, self.directory, clock=lambda: self.now)

    def tearDown(self):
        self.runner.close()
        self.temp.cleanup()

    def advance(self, seconds=.3, bid=None):
        self.now += seconds
        self.b.tick.time_msc += round(seconds * 1000)
        if bid is not None: self.b.tick.bid, self.b.tick.ask = bid, bid + .13
        self.runner.step(True)

    def arm(self):
        self.runner.step(True)
        self.advance()

    def test_no_orders_before_live_quote_change_and_pair_has_native_sl(self):
        self.runner.step(True)
        self.assertFalse(self.b.sent)
        self.advance()
        self.assertEqual(len(self.b.orders), 2)
        self.assertTrue(all(r["volume"] == .01 and r["magic"] == MAGIC and r["sl"] > 0 for r in self.b.sent))
        self.assertEqual(self.b.sent[0]["price"], 101.43)
        self.assertEqual(self.b.sent[1]["price"], 98.7)

    def test_wrong_account_real_server_netting_and_path_fail_closed(self):
        for obj, name, value in ((self.b.account, "login", 999), (self.b.account, "trade_mode", 2),
                                 (self.b.account, "server", "REAL"), (self.b.account, "margin_mode", 0),
                                 (self.b.terminal, "path", "/other"), (self.b.terminal, "connected", False)):
            old = getattr(obj, name); setattr(obj, name, value)
            with self.assertRaises(RuntimeError): self.runner.step(True)
            setattr(obj, name, old)
        self.assertFalse(self.b.sent)

    def test_specs_cannot_silently_increase_lot_or_change_distances(self):
        self.b.info.volume_min = .1
        with self.assertRaises(RuntimeError): preflight(self.b, self.directory, Params(risk_percent=0))
        self.b.info.volume_min = .01; self.b.info.trade_stops_level = 50
        with self.assertRaises(RuntimeError): preflight(self.b, self.directory)
        self.assertFalse(self.b.sent)

    def test_none_snapshot_is_not_empty_book(self):
        self.b.orders = None
        with self.assertRaises(RuntimeError): self.runner.step(True)
        self.assertFalse(self.b.sent)

    def test_foreign_positions_orders_and_tp_are_untouched(self):
        foreign = position(99, magic=992015)
        self.b.positions = [foreign]
        self.b.orders = [NS(ticket=98, magic=171135, symbol=SYMBOL)]
        self.arm()
        self.advance(1, bid=102)
        self.assertEqual(foreign.sl, 99)
        self.runner.step(False)
        self.assertEqual([o.ticket for o in self.b.orders], [98])
        self.assertFalse(any(r.get("position") == 99 or r.get("order") == 98 for r in self.b.sent))

    def test_restart_adopts_broker_pending_pair_without_duplicates(self):
        self.arm(); n = len(self.b.sent)
        self.runner.close()
        self.runner = ForwardScalper(self.b, self.directory, clock=lambda: self.now)
        self.runner.step(True); self.advance()
        self.assertEqual(len(self.b.sent), n)

    def test_uncertain_ack_latches_across_restart_and_never_resubmits(self):
        self.b.failure = lambda request: None
        self.arm()
        self.assertEqual(self.runner.state["phase"], "halted")
        self.runner.close()
        self.runner = ForwardScalper(self.b, self.directory, clock=lambda: self.now)
        self.b.failure = None
        self.advance(10)
        self.assertEqual(len(self.b.sent), 1)

    def test_partial_pair_rejection_cancels_only_owned_order(self):
        self.b.orders = [NS(ticket=90, magic=992015, symbol=SYMBOL)]
        self.b.failure = lambda r: NS(retcode=10016, order=0, comment="reject") if r.get("type") == 5 else "continue"
        self.arm()
        self.assertEqual([o.ticket for o in self.b.orders], [90])
        self.assertEqual(self.runner.state["phase"], "cooldown")
        self.assertFalse(any(r.get("order") == 90 for r in self.b.sent))

    def test_trail_uses_bid_ask_never_loosens_and_respects_first_delay(self):
        self.b.positions = [position()]
        self.runner.state["rearm_requested"] = False
        self.runner.step(True)
        self.advance(.3, 101)
        self.assertFalse(self.b.sent)
        self.advance(1, 101)
        self.assertEqual(self.b.positions[0].sl, 100.8)
        count = len(self.b.sent)
        self.advance(1, 100.9)
        self.assertEqual(len(self.b.sent), count)

    def test_opposite_pending_retained_after_fill(self):
        self.arm()
        self.b.orders = self.b.orders[1:]
        self.b.positions = [position(101, price=101.13, sl=100.13)]
        self.advance()
        self.assertEqual(len(self.b.orders), 1)
        self.assertFalse(any(r["action"] == self.b.TRADE_ACTION_REMOVE for r in self.b.sent))

    def test_own_exposure_cap_includes_potential_pending_fills(self):
        self.b.positions = [position(1), position(2)]
        self.arm()
        self.assertFalse(self.b.sent)

    def test_close_must_be_confirmed_before_rearm_and_counts_magic_zero_exit(self):
        self.b.positions = [position()]
        self.runner.state["rearm_requested"] = False
        self.runner.step(True)
        self.b.positions = []
        self.advance()
        self.advance()
        self.assertFalse(self.b.sent)
        self.b.deals[1] = [deal(entry=0), deal(magic=0, profit=1, commission=-.06)]
        self.advance()
        self.assertEqual(len(self.b.orders), 2)
        self.assertAlmostEqual(self.runner.state["closed_positions"]["1"], .94)

    def test_daily_loss_pauses_new_orders_and_does_not_close_foreign_positions(self):
        self.runner.state["daily_net"][datetime.now(BKK).date().isoformat()] = -20
        self.b.positions = [position(90, magic=992015)]
        self.arm()
        self.assertFalse(self.b.sent)
        self.assertEqual(len(self.b.positions), 1)

    def test_stale_quote_cannot_place_pending(self):
        self.runner.step(True)
        self.runner.due = 10  # establish freshness while arming is deliberately not yet due
        self.b.tick.time_msc += 1
        self.runner.step(True)
        self.now += 10
        self.runner.step(True)
        self.assertFalse(self.b.sent)

    def test_incomplete_intent_on_disk_halts_restart(self):
        self.runner.state["phase"] = "submitting"
        self.runner._save()
        self.runner = ForwardScalper(self.b, self.directory, clock=lambda: self.now)
        self.arm()
        self.assertEqual(self.runner.state["phase"], "halted")
        self.assertFalse(self.b.sent)

    def test_configuration_default_off_and_job_cannot_overlap(self):
        tree = ast.parse(Path('config.py').read_text(encoding='utf-8'))
        item = next(n for n in tree.body if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'DEMO_PORTFOLIO_ACTIVE' for t in n.targets))
        values = {ast.literal_eval(k): v for k, v in zip(item.value.keys, item.value.values) if k is not None}
        self.assertFalse(ast.literal_eval(values['SCALPING456']))
        tree = ast.parse(Path('main.py').read_text(encoding='utf-8'))
        jobs = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == 'add_job'
                and any(k.arg == 'id' and isinstance(k.value, ast.Constant) and k.value.value == 'scalping456_tick_job' for k in n.keywords)]
        self.assertEqual(len(jobs), 1)
        keywords = {k.arg: k.value for k in jobs[0].keywords}
        self.assertEqual(ast.literal_eval(keywords['max_instances']), 1)
        self.assertTrue(ast.literal_eval(keywords['coalesce']))

    def test_rearm_after_close_with_one_surviving_owned_position(self):
        self.b.positions = [position(1), position(2, side=1, price=101, sl=102)]
        self.runner.state['rearm_requested'] = False
        self.runner.step(True)
        self.b.positions = self.b.positions[1:]
        self.b.deals[1] = [deal(entry=0), deal(profit=-1)]
        self.advance()
        self.assertEqual(len(self.b.orders), 2)
        self.assertEqual(len(self.b.positions) + len(self.b.orders), 3)

    def test_account_switch_between_pair_legs_stops_second_submission(self):
        def change_after_first(r):
            if r['action'] == self.b.TRADE_ACTION_PENDING:
                self.b.account.login = 999
            return 'continue'
        self.b.failure = change_after_first
        self.runner.step(True)
        with self.assertRaises(RuntimeError): self.advance()
        self.assertEqual(len(self.b.sent), 1)
        self.b.failure = None; self.b.account.login = LOGIN
        self.advance()
        self.assertEqual(self.runner.state['phase'], 'halted')
        self.assertFalse(self.b.orders)
        self.assertEqual(sum(r['action'] == self.b.TRADE_ACTION_PENDING for r in self.b.sent), 1)

    def test_symbol_magic_collision_and_foreign_target_fail_closed(self):
        p = position(); p.symbol = 'BTCUSD'
        self.b.positions = [p]
        with self.assertRaises(RuntimeError): self.runner.step(True)
        self.b.positions = [position(99, magic=992015)]
        self.assertFalse(self.runner._send({'action':self.b.TRADE_ACTION_SLTP, 'symbol':SYMBOL, 'magic':MAGIC, 'position':99, 'sl':100}))
        self.assertFalse(self.b.sent)

    def test_equal_broker_stop_distance_is_valid_not_silently_skipped(self):
        self.b.info.trade_stops_level = 20
        self.b.positions = [position()]
        self.runner.state['rearm_requested'] = False
        self.runner.step(True)
        self.advance(1, bid=101)
        self.assertAlmostEqual(self.b.positions[0].sl, 100.8)

    def test_off_continues_trailing_owned_positions(self):
        self.b.positions = [position()]
        self.runner.step(False)
        self.now += 1
        self.b.tick.time_msc += 1000
        self.b.tick.bid, self.b.tick.ask = 101, 101.13
        self.runner.step(False)
        self.assertAlmostEqual(self.b.positions[0].sl, 100.8)
        self.assertFalse(any(r['action'] == self.b.TRADE_ACTION_PENDING for r in self.b.sent))

    def test_second_runner_cannot_share_the_same_state_owner(self):
        self.runner.step(False)
        second = ForwardScalper(self.b, self.directory)
        try:
            with self.assertRaises((RuntimeError, BlockingIOError)): second.step(True)
        finally:
            second.close()

    def test_pending_intent_cannot_bypass_protection_validation(self):
        with self.assertRaises(RuntimeError):
            self.runner._send({'action':self.b.TRADE_ACTION_PENDING, 'magic':MAGIC, 'symbol':SYMBOL,
                               'type':self.b.ORDER_TYPE_BUY_STOP, 'volume':1, 'sl':0})
        self.assertFalse(self.b.sent)

    def test_flash_fill_and_exit_are_accounted_without_a_position_snapshot(self):
        self.arm()
        ticket = self.b.orders[0].ticket
        self.b.orders = self.b.orders[1:]
        self.b.deals[ticket] = [deal(ticket, entry=0), deal(ticket, profit=-1, commission=-.06)]
        self.advance()
        self.assertAlmostEqual(self.runner.state['closed_positions'][str(ticket)], -1.06)
        # Remaining old opposite was cancelled first; re-arm waits for its history.
        self.advance()
        self.assertEqual(len(self.b.orders), 2)
        self.assertEqual(len(self.runner.state['closed_positions']), 1)

    def test_missing_order_history_blocks_new_cycles_instead_of_guessing_cancelled(self):
        self.arm()
        self.b.orders = []
        self.advance()
        self.assertEqual(self.runner.state['cycles'], 1)
        self.assertEqual(sum(r['action']==self.b.TRADE_ACTION_PENDING for r in self.b.sent), 2)


class Migration7129Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.directory = Path(self.temp.name) / ENTRY_PROFILE
        self.directory.mkdir()
        self.b = Broker(self.directory)
        self.b.info.point = self.b.info.trade_tick_size = .001
        self.now = 0.0
        self.runner = ForwardScalper(self.b, self.directory, clock=lambda: self.now)

    def tearDown(self):
        self.runner.close()
        self.temp.cleanup()

    def advance(self, active=True):
        self.now += 1
        self.b.tick.time_msc += 1000
        self.runner.step(active)

    def test_exact_exness_identity_and_native_three_decimal_symbol(self):
        self.runner.step(True)
        self.advance()
        self.assertEqual(self.runner.state['login'], 434237129)
        self.assertEqual(self.runner.state['symbol'], 'XAUUSDm')
        self.assertEqual(len(self.b.orders), 2)
        for request in self.b.sent:
            self.assertEqual(request['symbol'], 'XAUUSDm')
            self.assertEqual(request['volume'], .01)
            self.assertAlmostEqual(abs(request['price'] - request['sl']), 1.0)
        self.assertEqual(self.runner.state['daily_net'], {})
        self.assertEqual(self.runner.state['closed_positions'], {})

    def test_iux_account_or_server_on_target_path_cannot_submit(self):
        for key, value in [('login', LOGIN), ('server', SERVER), ('trade_mode', 2), ('margin_mode', 0)]:
            old = getattr(self.b.account, key)
            setattr(self.b.account, key, value)
            with self.assertRaises(RuntimeError): self.runner.step(True)
            setattr(self.b.account, key, old)
        self.assertFalse(self.b.sent)

    def test_copying_old_state_to_target_is_rejected(self):
        state = dict(self.runner.state, login=LOGIN, symbol=SYMBOL)
        self.runner.path.write_text(json.dumps(state), encoding='utf-8')
        with self.assertRaisesRegex(RuntimeError, 'state identity'):
            ForwardScalper(self.b, self.directory)
        self.assertFalse(self.b.sent)

    def test_unknown_profile_refused_and_target_status_uses_actual_symbol(self):
        self.assertEqual(set(TARGETS), {PROFILE, ENTRY_PROFILE})
        with self.assertRaises(RuntimeError):
            ForwardScalper(self.b, self.directory.parent / 'demo-exness-99997129')
        self.assertIn('XAUUSDm', status_text(self.directory, True))
        self.assertIn('OFF', status_text(self.directory.parent / PROFILE, True))

    def test_target_close_costs_are_isolated_and_accounted_once(self):
        pos = position()
        pos.symbol = self.b.symbol
        self.b.positions = [pos]
        self.runner.step(False)
        self.b.positions = []
        self.b.deals[1] = [deal(entry=0, symbol=self.b.symbol),
                           deal(symbol=self.b.symbol, profit=.5, commission=-.06, swap=-.01, fee=-.02, magic=0)]
        self.advance(False)
        self.advance(False)
        self.assertAlmostEqual(self.runner.state['closed_positions']['1'], .41)
        self.assertAlmostEqual(sum(self.runner.state['daily_net'].values()), .41)

    def stalled_pair(self):
        """The observed 7129 metadata/state, entirely inside a temp profile."""
        self.runner.state.update(phase='working', cycles=2, rearm_requested=False,
                                 known_orders={'4878801646': True, '4878801649': True},
                                 pending_closes={'4878801646': {'identifier': 4878801646},
                                                 '4878801649': {'identifier': 4878801649}},
                                 closed_positions={'4878797096': -1.06}, daily_net={'2026-10-15': -1.06})
        for identifier, side, loss, stamp in ((4878801646, 0, -1.01, 1792051206831),
                                              (4878801649, 1, -1.00, 1792067402228)):
            self.b.order_history[identifier] = NS(ticket=identifier, magic=0, position_id=0,
                                                  symbol=self.b.symbol, type=4+side, state=4, volume_initial=.01)
            self.b.deals[identifier] = [deal(identifier, entry=0, side=side, symbol=self.b.symbol),
                                        deal(identifier, magic=0, side=1-side, symbol=self.b.symbol,
                                             profit=loss, order=0, time_msc=stamp)]

    def restart(self):
        self.runner.close()
        self.runner = ForwardScalper(self.b, self.directory, clock=lambda: self.now)

    def test_exness_zero_magic_stub_clears_stuck_pair_and_places_new_orders(self):
        self.stalled_pair()
        self.runner._save()
        self.restart()
        self.runner.step(True)
        self.advance()
        self.assertEqual(len(self.b.orders), 2)
        self.assertEqual(self.runner.state['cycles'], 3)
        self.assertEqual(self.runner.state['pending_closes'], {})
        self.assertAlmostEqual(self.runner.state['daily_net']['2026-10-15'], -3.07)
        self.assertEqual(set(self.runner.state['closed_positions']), {'4878797096', '4878801646', '4878801649'})
        self.assertTrue(all(r['volume'] == .01 and r['magic'] == MAGIC and r['tp'] == 0 for r in self.b.sent))
        self.assertEqual([r['type'] for r in self.b.sent], [4, 5])
        before = len(self.b.sent)
        self.restart()
        self.runner.step(True)
        self.advance()
        self.assertEqual(len(self.b.sent), before)
        self.assertAlmostEqual(self.runner.state['daily_net']['2026-10-15'], -3.07)

    def test_percent_sizing_recovers_legacy_fixed_lot_before_new_risk_pair(self):
        self.b.account.equity = 1000
        self.stalled_pair()
        self.runner.step(True)
        self.advance()
        self.assertEqual([r['volume'] for r in self.b.sent], [.1, .1])
        self.assertAlmostEqual(self.runner.state['daily_net']['2026-10-15'], -3.07)
        self.assertEqual(self.runner.state['pending_closes'], {})

    def invalid_ticket_filter(self):
        native = self.b.history_deals_get
        self.b.history_deals_get = Mock(side_effect=lambda *a, **kw:
                                       None if 'ticket' in kw else native(*a, **kw))

    def history_window(self):
        for order in self.b.order_history.values():
            order.time_setup, order.time_done = 1792050951, 1792067402

    def test_actual_invalid_ticket_filter_and_already_booked_closes_rearm_at_one_percent(self):
        self.stalled_pair()
        # Actual 17:31 production state: PnL recovered, known_orders still stuck.
        self.runner.state.update(pending_closes={}, rearm_requested=True,
                                 closed_positions={'4878797096': -1.06, '4878801646': -1.01,
                                                   '4878801649': -1.0},
                                 daily_net={'2026-10-15': -3.07})
        self.b.account.equity = 10474.27
        self.invalid_ticket_filter()
        self.runner._save()
        self.restart()
        self.runner.step(True)
        self.advance()
        self.assertEqual([r['type'] for r in self.b.sent], [4, 5])
        self.assertEqual([r['volume'] for r in self.b.sent], [1.04, 1.04])
        self.assertFalse({'4878801646', '4878801649'} & self.runner.state['known_orders'].keys())
        self.assertEqual(self.runner.state['daily_net']['2026-10-15'], -3.07)
        self.assertTrue(any(c.kwargs == {'position': 4878801646}
                            for c in self.b.history_deals_get.call_args_list))
        self.restart()
        self.runner.step(True)
        self.advance()
        self.assertEqual(len(self.b.sent), 2)
        self.assertEqual(self.runner.state['daily_net']['2026-10-15'], -3.07)

    def test_invalid_ticket_filter_recovers_complete_close_costs_once(self):
        self.stalled_pair()
        self.b.deals[4878801646][0].commission = -.02
        self.b.deals[4878801646][1].fee = -.01
        self.invalid_ticket_filter()
        self.runner.step(True)
        self.advance()
        self.assertEqual(len(self.b.orders), 2)
        self.assertAlmostEqual(self.runner.state['daily_net']['2026-10-15'], -3.10)
        self.restart()
        self.runner.step(True)
        self.advance()
        self.assertAlmostEqual(self.runner.state['daily_net']['2026-10-15'], -3.10)

    def test_invalid_ticket_filter_bounded_raw_epoch_history_finds_different_identifier(self):
        self.stalled_pair()
        self.history_window()
        records = self.b.deals.pop(4878801646)
        for d in records: d.position_id = 7654321
        self.b.deals[7654321] = records
        self.runner.state['pending_closes'].pop('4878801646')
        # Foreign history in the same interval must not become owned exposure.
        self.b.deals[900] = [deal(900, entry=0, magic=123, symbol='BTCUSD')]
        self.invalid_ticket_filter()
        self.runner.step(True)
        self.advance()
        self.assertEqual(len(self.b.orders), 2)
        self.assertIn('7654321', self.runner.state['closed_positions'])
        self.assertNotIn('4878801646', self.runner.state['closed_positions'])
        self.assertAlmostEqual(self.runner.state['daily_net']['2026-10-15'], -3.07)
        self.assertNotIn('900', self.runner.state['closed_positions'])
        self.assertIn(((1792050951, 1792067403), {}),
                      [(c.args, c.kwargs) for c in self.b.history_deals_get.call_args_list])

    def test_same_position_identifier_under_two_ticket_aliases_cannot_double_book(self):
        self.stalled_pair()
        self.runner.state['pending_closes']['other_ticket'] = {'identifier': 4878801646}
        self.invalid_ticket_filter()
        self.runner.step(True)
        self.advance()
        self.assertAlmostEqual(self.runner.state['daily_net']['2026-10-15'], -3.07)
        self.assertNotIn('other_ticket', self.runner.state['closed_positions'])
        self.assertEqual(self.runner.state['pending_closes'], {})
        self.restart()
        self.runner.step(True)
        self.advance()
        self.assertAlmostEqual(self.runner.state['daily_net']['2026-10-15'], -3.07)

    def test_old_invalid_filter_behavior_blocks_but_fixed_lookup_submits_pair(self):
        self.stalled_pair()
        self.invalid_ticket_filter()
        # Counterfactual old implementation, no live profile or state involved.
        with patch.object(self.runner, '_order_deals', side_effect=lambda order:
                          self.b.history_deals_get(ticket=int(order.ticket))):
            self.runner.step(True)
            self.advance()
            self.assertFalse(self.b.sent)
            self.assertEqual(set(self.runner.state['known_orders']), {'4878801646', '4878801649'})
        self.advance()
        self.assertEqual(len(self.b.orders), 2)

    def test_failed_range_query_can_recover_via_verified_position(self):
        self.stalled_pair()
        self.history_window()
        native = self.b.history_deals_get
        self.b.history_deals_get = Mock(side_effect=lambda *a, **kw:
                                       None if a or 'ticket' in kw else native(**kw))
        self.runner.step(True)
        self.advance()
        self.assertEqual(len(self.b.orders), 2)
        self.assertAlmostEqual(self.runner.state['daily_net']['2026-10-15'], -3.07)

    def test_invalid_ticket_filter_cancel_range_without_ack_is_not_trusted(self):
        self.runner.state['known_orders']['999'] = True
        self.b.order_history[999] = NS(ticket=999, magic=0, symbol=self.b.symbol, type=4,
                                       state=self.b.ORDER_STATE_CANCELED, position_id=0,
                                       volume_initial=.01)
        self.history_window()
        self.invalid_ticket_filter()
        with self.assertRaisesRegex(RuntimeError, 'ownership proof'): self.runner.step(True)
        self.assertIn('999', self.runner.state['known_orders'])
        self.assertFalse(self.b.sent)

    def test_incomplete_filled_volume_via_fallback_keeps_new_entries_blocked(self):
        self.stalled_pair()
        self.b.deals[4878801646][0].volume = .004
        self.b.deals[4878801646][1].volume = .002
        self.invalid_ticket_filter()
        self.runner.step(True)
        self.advance()
        self.assertIn('4878801646', self.runner.state['known_orders'])
        self.assertNotIn('4878801646', self.runner.state['closed_positions'])
        self.assertFalse(self.b.sent)

    def test_invalid_ticket_filter_position_candidate_must_match_original_order(self):
        self.stalled_pair()
        self.b.deals[4878801646][0].order = 999
        self.invalid_ticket_filter()
        self.runner.step(True)
        self.advance()
        self.assertIn('4878801646', self.runner.state['known_orders'])
        self.assertFalse(self.b.sent)

    def test_invalid_ticket_filter_known_position_candidate_can_differ_from_order(self):
        self.stalled_pair()
        records = self.b.deals.pop(4878801646)
        for d in records: d.position_id = 7654321
        self.b.deals[7654321] = records
        self.runner.state['pending_closes']['4878801646']['identifier'] = 7654321
        self.invalid_ticket_filter()
        self.runner.step(True)
        self.advance()
        self.assertEqual(len(self.b.orders), 2)
        self.assertIn('7654321', self.runner.state['closed_positions'])
        self.assertNotIn('4878801646', self.runner.state['closed_positions'])
        self.assertAlmostEqual(self.runner.state['daily_net']['2026-10-15'], -3.07)

    def test_invalid_ticket_filter_rejects_foreign_or_malformed_entry_proof(self):
        for field, value in [('magic', 0), ('magic', 123), ('symbol', 'BTCUSD'),
                              ('type', 1), ('position_id', 0), ('volume', -.01), ('ticket', -1)]:
            with self.subTest(field=field):
                self.stalled_pair()
                setattr(self.b.deals[4878801646][0], field, value)
                self.b.history_deals_get = Broker.history_deals_get.__get__(self.b)
                self.invalid_ticket_filter()
                with self.assertRaises(RuntimeError): self.runner.step(True)
                self.assertFalse(self.b.sent)

    def test_invalid_ticket_filter_rejects_ambiguous_range_and_conflicting_metadata(self):
        self.stalled_pair()
        self.history_window()
        self.b.deals[900] = [deal(900, entry=0, symbol=self.b.symbol, order=4878801646,
                                  volume=.005)]
        self.invalid_ticket_filter()
        with self.assertRaisesRegex(RuntimeError, 'ambiguous'): self.runner.step(True)
        del self.b.deals[900]
        self.b.order_history[4878801646].position_id = 12345
        with self.assertRaisesRegex(RuntimeError, 'identifier mismatch'): self.runner.step(True)
        self.assertFalse(self.b.sent)

    def test_failed_all_history_queries_never_clear_known_orders(self):
        self.stalled_pair()
        self.history_window()
        self.b.history_deals_get = Mock(return_value=None)
        self.runner.step(True)
        self.advance()
        self.assertEqual(set(self.runner.state['known_orders']), {'4878801646', '4878801649'})
        self.assertFalse(self.b.sent)

    def test_empty_guessed_position_cannot_prove_cancelled_order_without_range(self):
        self.stalled_pair()
        self.b.order_history[4878801646].state = self.b.ORDER_STATE_CANCELED
        del self.b.deals[4878801646]
        self.invalid_ticket_filter()
        self.runner.step(True)
        self.advance()
        self.assertIn('4878801646', self.runner.state['known_orders'])
        self.assertFalse(self.b.sent)

    def test_invalid_ticket_filter_cancelled_pair_uses_ack_and_complete_range(self):
        self.b.account.equity = 1000
        self.runner.step(True)
        self.advance()
        for o in self.b.orders:
            self.b.order_history[o.ticket] = NS(ticket=o.ticket, magic=0, symbol=self.b.symbol,
                                                type=o.type, state=self.b.ORDER_STATE_CANCELED,
                                                position_id=0, volume_initial=.1)
        self.b.orders = []
        self.history_window()
        self.invalid_ticket_filter()
        self.advance()
        self.assertEqual(self.runner.state['cycles'], 2)
        self.assertEqual(len(self.b.orders), 2)
        self.assertEqual(self.runner.state['closed_positions'], {})

    def test_invalid_ticket_filter_partly_filled_cancel_must_wait_for_full_position_exit(self):
        self.stalled_pair()
        self.history_window()
        self.b.order_history[4878801646].state = self.b.ORDER_STATE_CANCELED
        self.b.deals[4878801646][0].volume = .004
        exit_deal = self.b.deals[4878801646].pop()
        self.invalid_ticket_filter()
        self.runner.step(True)
        self.advance()
        self.assertIn('4878801646', self.runner.state['pending_closes'])
        self.assertFalse(self.b.sent)
        exit_deal.volume = .004
        self.b.deals[4878801646].append(exit_deal)
        self.advance()
        self.assertEqual(len(self.b.orders), 2)
        self.assertAlmostEqual(self.runner.state['closed_positions']['4878801646'], -1.01)

    def test_zero_magic_stub_rejects_foreign_entry_proof(self):
        for field, value in [('magic', 0), ('magic', 234001), ('symbol', 'BTCUSD'),
                              ('type', 1), ('position_id', 0), ('order', 999)]:
            with self.subTest(field=field, value=value):
                self.stalled_pair()
                setattr(self.b.deals[4878801646][0], field, value)
                # Wrong DEAL_ORDER yields an empty order-filter query and must wait.
                if field == 'order':
                    self.runner.step(True)
                    self.assertIn('4878801646', self.runner.state['known_orders'])
                else:
                    with self.assertRaises(RuntimeError): self.runner.step(True)
                self.assertFalse(self.b.sent)
                if field != 'order':
                    self.assertNotIn('4878801646', self.runner.state['closed_positions'])

    def test_nonzero_foreign_history_magic_is_not_relaxed(self):
        self.stalled_pair()
        self.b.order_history[4878801646].magic = 234001
        with self.assertRaisesRegex(RuntimeError, 'identity mismatch'): self.runner.step(True)
        self.assertFalse(self.b.sent)

    def test_zero_magic_stub_waits_for_entry_history_then_recovers(self):
        self.stalled_pair()
        entry = self.b.deals[4878801646].pop(0)
        self.runner.step(True)
        self.advance()
        self.assertFalse(self.b.sent)
        self.assertIn('4878801646', self.runner.state['known_orders'])
        self.b.deals[4878801646].insert(0, entry)
        self.advance()
        self.assertEqual(len(self.b.orders), 2)
        self.assertAlmostEqual(self.runner.state['daily_net']['2026-10-15'], -3.07)

    def test_zero_magic_stub_uses_entry_identifier_not_assumed_order_ticket(self):
        self.stalled_pair()
        deals = self.b.deals.pop(4878801646)
        for d in deals: d.position_id = 7654321
        self.b.deals[7654321] = deals
        self.runner.state['pending_closes'].pop('4878801646')
        self.runner.step(True)
        self.assertIn('7654321', self.runner.state['closed_positions'])
        self.assertNotIn('4878801646', self.runner.state['closed_positions'])

    def test_partial_exit_does_not_book_close_or_rearm_until_volume_balances(self):
        self.b.positions = [position()]
        self.b.positions[0].symbol = self.b.symbol
        self.runner.step(False)
        self.b.positions = []
        self.b.deals[1] = [deal(entry=0, symbol=self.b.symbol, commission=-.02),
                           deal(symbol=self.b.symbol, volume=.004, profit=.4, ticket=12)]
        self.advance()
        self.assertNotIn('1', self.runner.state['closed_positions'])
        self.assertFalse(self.b.sent)
        self.b.deals[1].append(deal(symbol=self.b.symbol, magic=0, volume=.006,
                                    profit=.6, commission=-.03, swap=-.01, fee=-.02, ticket=13))
        self.advance()
        self.assertAlmostEqual(self.runner.state['closed_positions']['1'], .92)
        self.assertEqual(len(self.b.orders), 2)

    def test_disappearance_alone_cannot_cancel_opposite_pending(self):
        self.runner.step(True)
        self.advance()
        ticket = self.b.orders[0].ticket
        self.b.orders = self.b.orders[1:]
        pos = position(ticket)
        pos.symbol = self.b.symbol
        self.b.positions = [pos]
        self.advance()
        self.b.positions = []
        self.advance()
        self.assertEqual(len(self.b.orders), 1)
        self.assertFalse(any(r['action'] == self.b.TRADE_ACTION_REMOVE for r in self.b.sent))
        self.b.deals[ticket] = [deal(ticket, entry=0, symbol=self.b.symbol), deal(ticket, symbol=self.b.symbol)]
        self.advance()
        self.assertTrue(any(r['action'] == self.b.TRADE_ACTION_REMOVE for r in self.b.sent))
        self.advance()
        self.assertEqual(len(self.b.orders), 2)

    def test_crash_after_accounting_save_keeps_rearm_intent_without_double_pnl(self):
        self.stalled_pair()
        original_event = self.runner._event
        def fail_closed_event(event, **fields):
            if event == 'closed': raise OSError('simulated journal failure')
            return original_event(event, **fields)
        self.runner._event = fail_closed_event
        with self.assertRaises(OSError): self.runner.step(True)
        self.assertTrue(json.loads(self.runner.path.read_text(encoding='utf-8'))['close_rearm_pending'])
        self.restart()
        self.runner.step(True)
        self.advance()
        self.assertEqual(len(self.b.orders), 2)
        self.assertAlmostEqual(self.runner.state['daily_net']['2026-10-15'], -3.07)

    def test_rejected_cancel_is_retried_before_rearm(self):
        self.stalled_pair()
        self.b.orders = [NS(ticket=901, magic=MAGIC, symbol=self.b.symbol)]
        self.b.failure = lambda r: NS(retcode=10016, order=0, comment='reject') if r['action'] == self.b.TRADE_ACTION_REMOVE else 'continue'
        self.runner.step(True)
        self.advance()
        self.assertTrue(self.runner.state['close_rearm_pending'])
        self.assertFalse(any(r['action'] == self.b.TRADE_ACTION_PENDING for r in self.b.sent))
        self.b.failure = None
        self.advance()
        self.advance()
        self.assertEqual(len(self.b.orders), 2)
        self.assertFalse(self.runner.state['close_rearm_pending'])

    def test_zero_magic_cancelled_stubs_need_original_ack_and_allow_next_cycle(self):
        self.runner.step(True)
        self.advance()
        for o in self.b.orders:
            self.b.order_history[o.ticket] = NS(ticket=o.ticket, magic=0, symbol=self.b.symbol,
                                                type=o.type, state=self.b.ORDER_STATE_CANCELED,
                                                position_id=0, volume_initial=.01)
        self.b.orders = []
        self.advance()
        self.assertEqual(self.runner.state['cycles'], 2)
        self.assertEqual(len(self.b.orders), 2)
        self.assertEqual(self.runner.state['closed_positions'], {})

    def test_zero_magic_cancelled_stub_without_ack_is_not_trusted(self):
        self.runner.state['known_orders']['999'] = True
        self.b.order_history[999] = NS(ticket=999, magic=0, symbol=self.b.symbol, type=4,
                                       state=self.b.ORDER_STATE_CANCELED, position_id=0, volume_initial=.01)
        with self.assertRaisesRegex(RuntimeError, 'ownership proof'): self.runner.step(True)
        self.assertFalse(self.b.sent)

    def test_zero_magic_stub_rejects_conflicting_position_and_ambiguous_fills(self):
        self.stalled_pair()
        self.b.order_history[4878801646].position_id = 12345
        with self.assertRaisesRegex(RuntimeError, 'identifier mismatch'): self.runner.step(True)
        self.b.order_history[4878801646].position_id = 0
        second = deal(12345, entry=0, symbol=self.b.symbol, order=4878801646, volume=.005)
        self.b.deals[4878801646].append(second)
        with self.assertRaisesRegex(RuntimeError, 'ambiguous'): self.runner.step(True)
        self.assertFalse(self.b.sent)

    def test_partial_entry_deals_and_duplicate_rows_are_counted_once(self):
        self.stalled_pair()
        entry = self.b.deals[4878801646][0]
        entry.volume = .004
        second = deal(4878801646, entry=0, volume=.006, symbol=self.b.symbol, ticket=99901)
        self.b.deals[4878801646].extend([second, second])
        self.runner.step(True)
        self.advance()
        self.assertEqual(len(self.b.orders), 2)
        self.assertAlmostEqual(self.runner.state['daily_net']['2026-10-15'], -3.07)

    def test_conflicting_duplicate_deal_rows_fail_closed(self):
        self.stalled_pair()
        duplicate = deal(4878801646, entry=0, volume=.004, symbol=self.b.symbol)
        self.b.deals[4878801646].append(duplicate)
        with self.assertRaisesRegex(RuntimeError, 'conflicting'): self.runner.step(True)
        self.assertFalse(self.b.sent)

    def test_recovered_current_day_loss_gate_still_blocks_new_orders(self):
        self.stalled_pair()
        today = datetime.now(BKK)
        self.runner.state['daily_net'] = {today.date().isoformat(): -19}
        for records in self.b.deals.values():
            for d in records: d.time_msc = int(today.timestamp() * 1000)
        self.runner.step(True)
        self.advance()
        self.assertAlmostEqual(self.runner.state['daily_net'][today.date().isoformat()], -21.01)
        self.assertFalse(self.b.sent)

    def test_off_cancels_only_scalping_and_trails_target_positions(self):
        foreign = position(90, magic=234001)
        foreign.symbol = self.b.symbol
        owned = position()
        owned.symbol = self.b.symbol
        self.b.positions = [owned, foreign]
        self.b.orders = [NS(ticket=91, magic=234001, symbol=self.b.symbol),
                         NS(ticket=92, magic=MAGIC, symbol=self.b.symbol)]
        self.runner.step(False)
        self.b.tick.bid, self.b.tick.ask = 101, 101.13
        self.advance(False)
        self.assertEqual([o.ticket for o in self.b.orders], [91])
        self.assertAlmostEqual(owned.sl, 100.8)
        self.assertEqual(foreign.sl, 99)
        self.assertFalse(any(r.get('order') == 91 or r.get('position') == 90 for r in self.b.sent))

    def test_production_wrapper_drains_source_even_if_stale_env_says_on(self):
        tree = ast.parse(Path('demo_portfolio.py').read_text(encoding='utf-8'))
        function = next(n for n in tree.body if isinstance(n, ast.AsyncFunctionDef)
                        and n.name == 'demo_scalping456_tick_job')
        runner = NS(step=Mock(), state={'known_positions': {}})
        cfg = NS(BOT_PROFILE=PROFILE, PROFILE_DIR=str(self.directory.parent / PROFILE),
                 DEMO_PORTFOLIO_ACTIVE={'SCALPING456': True})
        namespace = {'config': cfg, '_scalping456_runner': runner}
        exec(compile(ast.Module(body=[function], type_ignores=[]), '<wrapper>', 'exec'), namespace)
        with patch.dict('sys.modules', {'trailing': NS(position_sid={})}):
            asyncio.run(namespace['demo_scalping456_tick_job']())
            runner.step.assert_called_once_with(False)
            runner.step.reset_mock()
            cfg.BOT_PROFILE, cfg.PROFILE_DIR = ENTRY_PROFILE, str(self.directory)
            asyncio.run(namespace['demo_scalping456_tick_job']())
            runner.step.assert_called_once_with(True)
            cfg.PROFILE_DIR = str(self.directory.parent / PROFILE)
            with self.assertRaisesRegex(RuntimeError, 'directory mismatch'):
                asyncio.run(namespace['demo_scalping456_tick_job']())


class RiskSizingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.directory = Path(self.temp.name) / ENTRY_PROFILE
        self.directory.mkdir()
        self.b = Broker(self.directory)
        self.b.info.point = self.b.info.trade_tick_size = .001
        self.b.account.equity = 1000
        self.now = 0.
        self.runner = ForwardScalper(self.b, self.directory, clock=lambda: self.now)

    def tearDown(self):
        self.runner.close()
        self.temp.cleanup()

    def advance(self, seconds=1.):
        self.now += seconds
        self.b.tick.time_msc += round(seconds * 1000)
        self.runner.step(True)

    def arm(self):
        self.runner.step(True)
        self.advance()

    def test_default_one_percent_equity_each_leg_and_status(self):
        self.assertEqual(Params().risk_percent, 1)
        self.b.account.balance = 999999
        self.arm()
        self.assertEqual([r['volume'] for r in self.b.sent], [.1, .1])
        for r in self.b.sent:
            side = self.b.ORDER_TYPE_BUY if r['type'] == 4 else self.b.ORDER_TYPE_SELL
            self.assertAlmostEqual(-self.b.order_calc_profit(side, self.b.symbol, r['volume'], r['price'], r['sl']), 10)
        self.assertIn('risk 1% equity per NEW order', status_text(self.directory, True))
        self.assertIn('pair may risk 2%', status_text(self.directory, True))

    def test_floor_to_broker_step_never_round_up(self):
        self.b.account.equity = 2456.78
        self.arm()
        self.assertEqual([r['volume'] for r in self.b.sent], [.24, .24])

    def test_actual_sl_distance_changes_lot_not_risk_budget(self):
        self.runner.params = Params(initial_stop=2.)
        self.arm()
        self.assertEqual([r['volume'] for r in self.b.sent], [.05, .05])

    def test_buy_sell_calculated_independently_in_account_currency(self):
        native = self.b.order_calc_profit
        self.b.order_calc_profit = lambda side, *args: native(side, *args) * (2 if side == 1 else 1)
        self.arm()
        self.assertEqual([r['volume'] for r in self.b.sent], [.1, .05])

    def test_broker_maximum_can_reduce_but_not_increase_risk(self):
        self.b.info.volume_max = .05
        self.arm()
        self.assertEqual([r['volume'] for r in self.b.sent], [.05, .05])

    def test_minimum_lot_above_budget_skips_instead_of_rounding_up(self):
        self.b.account.equity = 50
        self.runner.step(True)
        with self.assertRaisesRegex(RuntimeError, 'minimum lot'): self.advance()
        self.assertFalse(self.b.sent)

    def test_invalid_equity_or_profit_never_falls_back_to_fixed_lot(self):
        self.runner.step(True)
        for value in (0, -1, float('nan'), float('inf'), None):
            with self.subTest(equity=value):
                self.b.account.equity = value
                with self.assertRaises(RuntimeError): self.advance()
                self.assertFalse(self.b.sent)
        self.b.account.equity = 1000
        for value in (None, 0, 1, float('nan'), float('inf')):
            with self.subTest(profit=value):
                self.b.order_calc_profit = lambda *args: value
                with self.assertRaises(RuntimeError): self.advance()
                self.assertFalse(self.b.sent)

    def test_second_leg_sizing_failure_cannot_submit_first_leg(self):
        native = self.b.order_calc_profit
        self.b.order_calc_profit = lambda side, *args: native(side, *args) if side == 0 else None
        self.runner.step(True)
        with self.assertRaises(RuntimeError): self.advance()
        self.assertFalse(self.b.sent)

    def test_equity_drop_before_second_send_cancels_partial_pair_and_retries(self):
        def reduce_equity(r):
            if r['action'] == self.b.TRADE_ACTION_PENDING: self.b.account.equity = 100
            return 'continue'
        self.b.failure = reduce_equity
        self.arm()
        self.assertEqual([r['action'] for r in self.b.sent], [5, 8])
        self.assertFalse(self.b.orders)
        self.assertEqual(self.runner.state['phase'], 'cooldown')
        self.b.failure = None
        self.b.account.equity = 1000
        self.advance(31)
        self.assertEqual(len(self.b.orders), 2)
        self.assertEqual([r['volume'] for r in self.b.sent if r['action'] == 5], [.1, .1, .1])

    def test_late_profit_api_failure_cancels_acknowledged_first_leg(self):
        native = self.b.order_calc_profit
        calls = []
        def failure_on_second_send(*args):
            calls.append(args)
            return None if len(calls) == 6 else native(*args)
        self.b.order_calc_profit = failure_on_second_send
        self.arm()
        self.assertEqual([r['action'] for r in self.b.sent], [5, 8])
        self.assertFalse(self.b.orders)
        self.assertEqual(self.runner.state['phase'], 'cooldown')

    def test_variable_lot_zero_magic_cancel_history_uses_original_ack(self):
        self.arm()
        for r in self.b.sent:
            self.assertEqual(r['volume'], .1)
        for o in self.b.orders:
            self.b.order_history[o.ticket] = NS(ticket=o.ticket, magic=0, symbol=self.b.symbol,
                                                type=o.type, state=2, position_id=0, volume_initial=.1)
        self.b.orders = []
        self.advance()
        self.assertEqual(len(self.b.orders), 2)
        self.assertEqual(self.runner.state['cycles'], 2)

    def test_direct_oversized_request_and_invalid_volume_are_blocked(self):
        request = {'action':5, 'magic':MAGIC, 'symbol':self.b.symbol, 'type':4,
                   'price':101., 'sl':100., 'volume':1.}
        self.assertFalse(self.runner._send(request))
        request['volume'] = .105
        with self.assertRaises(RuntimeError): self.runner._send(request)
        self.assertFalse(self.b.sent)

    def test_invalid_risk_percent_and_legacy_fixed_mode(self):
        for value in (-1, 101, float('nan'), float('inf')):
            with self.assertRaises(ValueError): Params(risk_percent=value)
        self.runner.params = Params(risk_percent=0)
        self.arm()
        self.assertEqual([r['volume'] for r in self.b.sent], [.01, .01])

    def test_profit_api_uses_timeout_protected_worker_wrapper(self):
        import mt5_worker as worker
        args = (0, 'XAUUSDm', .1, 4146., 4145.)
        with patch.object(worker, '_call', return_value=-10.) as call:
            self.assertEqual(worker.order_calc_profit(*args), -10.)
            call.assert_called_once_with(worker._mt5.order_calc_profit, *args)


if __name__ == '__main__':
    unittest.main()
