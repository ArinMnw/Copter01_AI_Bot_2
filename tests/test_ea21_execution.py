import copy
import asyncio
import sys
import unittest
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch, Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "mq5_strategy" / "ea2.1"))
import live_ea2_1 as live
from ea_strategy_2_1 import make_entry_filter
import demo_ea2_1 as bridge
import demo_portfolio as portfolio


class ExecutionTest(unittest.TestCase):
    def setUp(self):
        self.bars = [dict(time=1700000100 + i * 300, open=9, high=12, low=8, close=11)
                     for i in range(512)]
        self.state = dict(version=2, symbol="XAUUSDm", last_bar_time=self.bars[-2]["time"],
                          trend=1, awaiting_confirm=True, bos_count=0, entry_done_cycle=False,
                          ref_high=10, ref_low=1, last_bear_ob_high=1000, last_bull_ob_low=1,
                          swing_highs=[], swing_lows=[], order_blocks=[])
        self.mt5 = NS(symbol_info_tick=lambda s: NS(ask=11.01, bid=11),
                      symbol_info=lambda s: NS(point=.01, digits=2, volume_min=.01,
                         volume_max=100, volume_step=.01, trade_tick_size=.01, trade_tick_value=1),
                      account_info=lambda: NS(balance=10000), positions_get=lambda **kw: [])
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(live, "_load_state", side_effect=lambda *a: copy.deepcopy(self.state)))
        def save(path, payload):
            self.state = copy.deepcopy(payload)
        self.stack.enter_context(patch.object(live, "_atomic_save", side_effect=save))
        self.stack.enter_context(patch.object(live, "make_entry_filter", return_value=lambda *a: True))

    def detect(self):
        return live.detect_ea2_1(self.bars, tf="M5", mt5=self.mt5, cfg=NS(),
                                  symbol="XAUUSDm", htf_rates=self.bars[-200:], defer_execution=True)

    def attempt(self, token):
        live.mark_execution_attempt(NS(), "XAUUSDm", token, volume=.08, broker_time=1700153400)

    def ack(self, token, **kw):
        live.acknowledge_execution(NS(), "XAUUSDm", token, **kw)

    def test_success_commits_cycle_only_after_broker_ack(self):
        signal = self.detect()
        token = signal["execution_token"]
        self.assertFalse(self.state["entry_done_cycle"])
        self.assertEqual(self.state["ea21_last_accepted_time"], 0)
        self.attempt(token)
        self.assertEqual(self.detect()["signal"], "WAIT")
        self.ack(token, success=True, ticket=123)
        self.assertTrue(self.state["entry_done_cycle"])
        self.assertEqual(self.state["ea21_last_accepted_time"], self.bars[-1]["time"])
        self.assertEqual(self.detect()["signal"], "WAIT")

    def test_rejection_retries_same_token_without_consuming_cycle(self):
        token = self.detect()["execution_token"]
        self.attempt(token)
        with patch.object(live.time, "time", return_value=100):
            self.ack(token, success=False)
            self.assertEqual(self.detect()["signal"], "WAIT")
        with patch.object(live.time, "time", return_value=116):
            retry = self.detect()
        self.assertEqual(retry["signal"], "BUY")
        self.assertEqual(retry["execution_token"], token)
        self.assertFalse(self.state["entry_done_cycle"])

    def test_unknown_send_survives_reload_and_does_not_retry(self):
        token = self.detect()["execution_token"]
        self.attempt(token)
        self.ack(token, success=False, uncertain=True)
        self.bars.append(dict(self.bars[-1], time=self.bars[-1]["time"] + 300))
        self.assertEqual(self.detect()["signal"], "WAIT")
        self.assertEqual(self.state["ea21_execution_intent"]["status"], "unknown")

    def test_unsent_intent_expires_on_next_bar(self):
        self.detect()
        self.bars.append(dict(self.bars[-1], time=self.bars[-1]["time"] + 300))
        self.assertEqual(self.detect()["signal"], "WAIT")
        self.assertNotIn("ea21_execution_intent", self.state)

    def test_wrong_token_cannot_commit(self):
        self.detect()
        with self.assertRaises(RuntimeError):
            self.ack("wrong", success=True)
        self.assertFalse(self.state["entry_done_cycle"])

    def test_state_write_failure_prevents_send(self):
        token = self.detect()["execution_token"]
        with patch.object(live, "_atomic_save", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                self.attempt(token)


class BrokerBoundaryTest(unittest.TestCase):
    def place(self, first, fresh, cap=250):
        info = NS(point=.001, digits=3, trade_stops_level=0)
        mt = NS(symbol_info_tick=Mock(side_effect=[first, fresh]), symbol_info=lambda s: info,
                order_calc_margin=lambda *a: 10, account_info=lambda: NS(margin_free=10000),
                order_send=Mock(return_value=NS(retcode=10009, order=123)),
                ORDER_TYPE_BUY=0, ORDER_TYPE_SELL=1, TRADE_ACTION_DEAL=1,
                ORDER_TIME_GTC=0, ORDER_FILLING_FOK=0, TRADE_RETCODE_DONE=10009)
        with patch.object(portfolio, "mt5", mt), patch.object(portfolio, "_demo_symbol", return_value="XAUUSDm"):
            result = portfolio._place_market_order("BUY", 3988, 4050, "M5_EA2.1", 550021,
                                                  volume=.08, original_entry=4000,
                                                  max_spread_points=cap)
        return result, mt.order_send

    def test_spread_widening_prevents_broker_send(self):
        result, send = self.place(NS(ask=4000, bid=3999.8), NS(ask=4001, bid=4000.7))
        self.assertFalse(result["success"])
        send.assert_not_called()

    def test_fresh_price_keeps_sl_tp_distances(self):
        result, send = self.place(NS(ask=4000, bid=3999.8), NS(ask=4001, bid=4000.8))
        self.assertTrue(result["success"])
        request = send.call_args.args[0]
        self.assertEqual(request["price"], 4001)
        self.assertEqual(request["sl"], 3989)
        self.assertEqual(request["tp"], 4051)

    def test_invalid_final_quote_never_reaches_broker(self):
        result, send = self.place(NS(ask=4000, bid=3999.8), NS(ask=float("nan"), bid=4000))
        self.assertFalse(result["success"])
        send.assert_not_called()

    def test_other_portfolios_do_not_opt_into_extra_quote(self):
        result, send = self.place(NS(ask=4000, bid=3999.8), None, cap=None)
        self.assertTrue(result["success"])
        self.assertEqual(send.call_args.args[0]["price"], 4000)

    def test_unknown_without_broker_evidence_blocks_resend(self):
        intent = dict(status="unknown", token="t", broker_time=1700000000,
                      event=dict(signal="BUY"))
        with patch.object(bridge, "execution_intent", return_value=intent), \
                patch.object(bridge.mt5, "positions_get", return_value=[]), \
                patch.object(bridge.mt5, "history_deals_get", return_value=[]), \
                patch.object(bridge, "acknowledge_execution") as ack:
            self.assertFalse(bridge.reconcile_execution("XAUUSDm"))
            ack.assert_not_called()

    def test_closed_deal_resolves_unknown_after_restart(self):
        intent = dict(status="inflight", token="t", broker_time=1700000000,
                      event=dict(signal="BUY"))
        deal = NS(magic=550021, symbol="XAUUSDm", type=0, entry=0,
                  time=1700000001, position_id=123)
        with patch.object(bridge, "execution_intent", return_value=intent), \
                patch.object(bridge.mt5, "positions_get", return_value=[]), \
                patch.object(bridge.mt5, "history_deals_get", return_value=[deal]), \
                patch.object(bridge, "log_event"), \
                patch.object(bridge, "acknowledge_execution") as ack:
            self.assertTrue(bridge.reconcile_execution("XAUUSDm"))
            self.assertTrue(ack.call_args.kwargs["success"])


class BridgeIntegrationTest(unittest.TestCase):
    def run_scan(self, result):
        import trailing
        account = NS(login=123, trade_mode=0, balance=10000)
        signal = dict(signal="BUY", volume=.08, execution_token="t", reason="setup")
        with ExitStack() as stack:
            for target, name, value in [
                (bridge.config, "MT5_LOGIN", 123),
                (bridge.config, "auto_active", True),
                (bridge.config, "DEMO_PORTFOLIO_ACTIVE", {"EA2_1": True}),
                (bridge.config, "active_strategies", {}),
            ]:
                stack.enter_context(patch.object(target, name, value))
            for target, name, value in [
                (bridge, "reconcile_execution", True),
                (bridge, "detect_ea2_1", signal),
                (bridge, "risk_volume", .08),
                (bridge.mt5, "account_info", account),
                (bridge.mt5, "copy_rates_from_pos", []),
                (bridge.mt5, "symbol_info", NS(point=.001, digits=3, trade_stops_level=0)),
                (bridge.mt5, "symbol_info_tick", NS(ask=4000, bid=3999.8, time=1700000000)),
                (bridge.mt5, "order_calc_profit", -96),
                (portfolio, "_demo_symbol", "XAUUSDm"),
                (portfolio, "_demo_market_open", (True, "open")),
                (portfolio, "_load_state", {"trades": []}),
            ]:
                stack.enter_context(patch.object(target, name, return_value=value))
            stack.enter_context(patch.object(bridge, "log_event"))
            stack.enter_context(patch.object(portfolio, "_save_state"))
            stack.enter_context(patch.object(bridge.config, "save_runtime_state"))
            for name in ("position_sid", "position_tf", "position_pattern"):
                stack.enter_context(patch.object(trailing, name, {}))
            mark = stack.enter_context(patch.object(bridge, "mark_execution_attempt"))
            ack = stack.enter_context(patch.object(bridge, "acknowledge_execution"))
            place = stack.enter_context(patch.object(portfolio, "_place_market_order"))
            place.side_effect = result if isinstance(result, Exception) else None
            place.return_value = result
            if isinstance(result, Exception):
                with self.assertRaises(RuntimeError):
                    asyncio.run(bridge.scan_ea2_1(None))
            else:
                asyncio.run(bridge.scan_ea2_1(None))
            mark.assert_called_once()
            return ack.call_args, place.call_args

    def test_explicit_rejection_is_retryable(self):
        ack, place = self.run_scan(dict(success=False, error="reject"))
        self.assertFalse(ack.kwargs["success"])
        self.assertFalse(ack.kwargs["uncertain"])
        self.assertIn("max_spread_points", place.kwargs)

    def test_success_acknowledges_broker_ticket(self):
        ack, _ = self.run_scan(dict(success=True, ticket=123))
        self.assertTrue(ack.kwargs["success"])
        self.assertEqual(ack.kwargs["ticket"], 123)

    def test_broker_timeout_is_not_blindly_retried(self):
        ack, _ = self.run_scan(dict(success=False, uncertain=True))
        self.assertTrue(ack.kwargs["uncertain"])

    def test_exception_preserves_unknown_outcome(self):
        ack, _ = self.run_scan(RuntimeError("IPC failed"))
        self.assertFalse(ack.kwargs["success"])
        self.assertTrue(ack.kwargs["uncertain"])


class EmaWindowTest(unittest.TestCase):
    def test_all_causal_windows_match_research_history(self):
        import math
        rows = [dict(time=1700000100 + i * 900,
                     close=4000 + 8 * math.sin(i / 11)) for i in range(450)]
        cfg = dict(COOLDOWN_BARS=0)
        full = make_entry_filter(rows, decision_bar_seconds=300, cfg=cfg)
        for idx in range(199, len(rows)):
            raw = rows[idx]["time"] + 600
            for buy in (False, True):
                rolling = make_entry_filter(rows[idx-199:idx+1], decision_bar_seconds=300, cfg=cfg)
                self.assertEqual(full(buy, 0, raw), rolling(buy, 0, raw))

    def test_live_window_and_long_history_have_same_decision(self):
        rows = [dict(time=1700000100 + i * 900, close=4000 + i * .1) for i in range(400)]
        raw = rows[-1]["time"] + 600
        for buy in (False, True):
            full = make_entry_filter(rows, decision_bar_seconds=300)
            live_filter = make_entry_filter(rows[-200:], decision_bar_seconds=300)
            self.assertEqual(full(buy, 0, raw), live_filter(buy, 0, raw))
        self.assertTrue(make_entry_filter(rows, decision_bar_seconds=300)(True, 0, raw))

    def test_future_bars_cannot_change_past_decision(self):
        rows = [dict(time=1700000100 + i * 900, close=4000 + i * .1) for i in range(400)]
        future = [dict(time=rows[-1]["time"] + 900, close=1)]
        raw = rows[-1]["time"] + 600
        self.assertEqual(make_entry_filter(rows, decision_bar_seconds=300)(True, 0, raw),
                         make_entry_filter(rows + future, decision_bar_seconds=300)(True, 0, raw))


if __name__ == "__main__":
    unittest.main()
