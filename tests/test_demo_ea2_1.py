import asyncio
import unittest
from types import SimpleNamespace as NS
from unittest.mock import patch

import config
import demo_ea2_1 as bridge
import demo_portfolio


class DemoEa21Test(unittest.TestCase):
    def test_authorized_min_lot_fallback(self):
        info = NS(volume_step=.01, volume_min=.01, volume_max=100)
        with patch.object(config, "EA2_1_RISK_PERCENT", .1), \
                patch.object(config, "EA2_1_MIN_LOT_FALLBACK", True), \
                patch.object(bridge.mt5, "order_calc_profit", return_value=-1200):
            self.assertEqual(bridge.risk_volume("BUY", "XAUUSDm", 4140, 4128,
                                               .01, NS(balance=9823.02), info), .01)
            self.assertEqual(bridge.risk_volume("SELL", "XAUUSDm", 4140, 4152,
                                               .54, NS(balance=650000), info), .54)
            self.assertEqual(bridge.risk_volume("BUY", "XAUUSDm", 4140, 4128,
                                               0, NS(balance=9823.02), info), 0)
            self.assertEqual(bridge.risk_volume("BUY", "XAUUSDm", 4140, 4128,
                                               .01, NS(balance=0), info), 0)
            info.volume_min = .1
            self.assertEqual(bridge.risk_volume("BUY", "XAUUSDm", 4140, 4128,
                                               .01, NS(balance=9823.02), info), 0)

    def test_fallback_does_not_bypass_missing_profit_data(self):
        info = NS(volume_step=.01, volume_min=.01, volume_max=100)
        with patch.object(config, "EA2_1_MIN_LOT_FALLBACK", True), \
                patch.object(bridge.mt5, "order_calc_profit", return_value=None):
            self.assertEqual(bridge.risk_volume("BUY", "XAUUSDm", 4140, 4128,
                                               .01, NS(balance=9823.02), info), 0)

    def test_demo_account_identity(self):
        with patch.object(config, "MT5_LOGIN", 2101182459):
            self.assertTrue(bridge.demo_account_allowed(NS(login=2101182459, trade_mode=0)))
            self.assertFalse(bridge.demo_account_allowed(NS(login=2101182459, trade_mode=2)))
            self.assertFalse(bridge.demo_account_allowed(NS(login=2101182461, trade_mode=0)))
            self.assertFalse(bridge.demo_account_allowed(None))

    def test_risk_budget_rounds_down(self):
        account = NS(balance=650000)
        info = NS(volume_step=.01, volume_min=.01, volume_max=100)
        with patch.object(config, "EA2_1_RISK_PERCENT", .1), \
                patch.object(bridge.mt5, "order_calc_profit", return_value=-1200):
            lot = bridge.risk_volume("BUY", "XAUUSD", 3000, 2988, 100, account, info)
            self.assertEqual(lot, .54)
            self.assertLessEqual(lot * 1200, 650)

    def test_minimum_lot_over_budget_is_rejected(self):
        info = NS(volume_step=.01, volume_min=.01, volume_max=100)
        with patch.object(config, "EA2_1_RISK_PERCENT", .1), \
                patch.object(bridge.mt5, "order_calc_profit", return_value=-1200):
            self.assertEqual(bridge.risk_volume("BUY", "XAUUSD", 3000, 2988,
                                               .01, NS(balance=100), info), 0)

    def test_registration_and_disabled_route(self):
        self.assertIn("EA2_1", demo_portfolio.PORTFOLIO_ORDER)
        self.assertEqual(demo_portfolio._portfolio_magic("EA2_1"), 550021)
        with patch.dict(config.DEMO_PORTFOLIO_ACTIVE, {"EA2_1": False}), \
                patch.object(bridge.mt5, "order_send") as send:
            asyncio.run(bridge.scan_ea2_1(None))
            send.assert_not_called()

    def test_exness_point_conversion_preserves_price_distances(self):
        from live_ea2_1 import _engine_cfg
        from ea_strategy_2_1 import DEFAULT_CFG
        mapping = {
            "SL_POINTS": 1200, "TP_POINTS": 5000,
            "BREAKEVEN_TRIGGER_POINTS": 75, "BREAKEVEN_LOCK_POINTS": 25,
            "TRAIL_TRIGGER_POINTS": 100, "TRAIL_DISTANCE_POINTS": 75,
            "TRAIL_STEP_POINTS": 5, "MIN_LEG_POINTS": 200,
            "OB_PREFER_DEEPER_MAX_POINTS": 300,
        }
        cfg = NS(**{f"EA2_1_{key}": value * 10 for key, value in mapping.items()})
        actual = _engine_cfg(cfg, .001)
        for key, original in mapping.items():
            self.assertEqual(DEFAULT_CFG[key], original)
            self.assertAlmostEqual(actual[key] * actual["POINT"], original * .01)

    def test_exness_10k_minimum_lot_keeps_point_one_percent_limit(self):
        info = NS(volume_step=.01, volume_min=.01, volume_max=100)
        with patch.object(config, "EA2_1_RISK_PERCENT", .1), \
                patch.object(bridge.mt5, "order_calc_profit", return_value=-1200):
            lot = bridge.risk_volume("BUY", "XAUUSDm", 4140, 4128,
                                     .01, NS(balance=10075.34), info)
            self.assertEqual(lot, 0)


if __name__ == "__main__":
    unittest.main()
