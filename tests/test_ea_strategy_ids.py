"""EA identifier migration and broker comment compatibility; no broker writes."""

import unittest
import os
from types import SimpleNamespace
from unittest.mock import patch

import config
import notifications
import trailing
import scanner  # Loads the EA adapters through their production paths.
from live_ea2 import _ea2_position
from live_ea2_1 import _own_position
from handlers import keyboard
from handlers.btn_order import _parse_comment
from mt5_utils import _build_order_comment, _sid_in_config_skip
from strategy_ids import normalize_sid, migrate_sid_metadata, sid_sort_key


class EaStrategyIdsTest(unittest.TestCase):
    def test_canonical_config_and_old_env_aliases(self):
        self.assertEqual(config.EA2_SID, "ea2")
        self.assertEqual(config.EA2_1_SID, "ea2.1")
        self.assertNotIn(435, config.active_strategies)
        self.assertNotIn(436, config.active_strategies)
        for token, expected in (("435", "ea2"), ("436", "ea2.1"),
                                ("EA2", "ea2"), ("EA2.1", "ea2.1"),
                                ("20.14", 20.14), ("2", 2)):
            self.assertEqual(config._sid_from_env_token(token), expected)
        for token, expected in (("ea2", "ea2"), ("435", "ea2"),
                                ("ea2.1", "ea2.1"), ("436", "ea2.1")):
            with patch.dict(config.active_strategies, {1: True, "ea2": False, "ea2.1": False}, clear=True), \
                    patch.dict(os.environ, {"ACTIVE_STRATEGIES": token}):
                config._apply_active_strategies_env_override()
                self.assertEqual([sid for sid, enabled in config.active_strategies.items() if enabled], [expected])

    def test_comments_across_order_fill_close_and_profit_views(self):
        for sid, tf in (("ea2", "M1"), ("ea2.1", "M5")):
            comment = _build_order_comment(tf, sid)
            self.assertEqual(comment, f"{tf}_{sid.upper()}")
            self.assertLessEqual(len(comment), 31)
            legacy = f"{tf}_S{435 if sid == 'ea2' else 436}_OB"
            for text in (comment, legacy, comment + "_OB"):
                self.assertEqual(trailing._parse_bot_comment(text), (tf, sid))
                self.assertEqual(notifications._parse_bot_comment(text), (tf, sid))
                self.assertEqual(keyboard._parse_comment_detail(text)[:2], (tf, sid))
                self.assertEqual(_parse_comment(text)[:2], (tf, sid))
                self.assertEqual(trailing._resolve_pos_sid(-987654, text), sid)
                owner = _ea2_position if sid == "ea2" else _own_position
                self.assertTrue(owner(SimpleNamespace(magic=0, comment=text), config))
        self.assertEqual(trailing._parse_bot_comment("M15_S20.14_OB"), ("M15", 20.14))
        self.assertEqual(_build_order_comment("M5", 2), "M5_S2")

    def test_state_migration_preserves_ticket_and_price(self):
        source = {"pending": {"123": {"sid": 435, "entry": 435.0}},
                  "positions": [{"sid": "436", "ticket": 436}]}
        migrated = migrate_sid_metadata(source)
        self.assertEqual(migrated["pending"]["123"], {"sid": "ea2", "entry": 435.0})
        self.assertEqual(migrated["positions"][0], {"sid": "ea2.1", "ticket": 436})
        self.assertEqual(source["pending"]["123"]["sid"], 435)
        self.assertEqual(sorted(["ea2.1", 2, "ea2", 20.14], key=sid_sort_key),
                         [2, 20.14, "ea2", "ea2.1"])
        self.assertTrue(_sid_in_config_skip(435, "RISK_PERCENT_SKIP_SIDS"))
        self.assertTrue(_sid_in_config_skip("ea2.1", "TRAIL_SL_SKIP_SIDS"))

    def test_dedicated_trailing_uses_string_sid(self):
        import asyncio
        for sid, function in (("ea2", trailing.check_ea2_trail),
                              ("ea2.1", trailing.check_ea2_1_trail)):
            position = SimpleNamespace(ticket=-987654, type=0, price_open=100.0,
                                       sl=98.0, magic=0, comment="")
            with patch.dict(config.active_strategies, {sid: True}), \
                    patch.dict(trailing.position_sid, {-987654: sid}), \
                    patch.object(trailing.mt5, "positions_get", return_value=[position]), \
                    patch.object(trailing.mt5, "symbol_info", return_value=SimpleNamespace(point=.01, digits=2)), \
                    patch.object(trailing.mt5, "symbol_info_tick", return_value=SimpleNamespace(bid=105.0, ask=105.2)), \
                    patch.object(trailing, "_modify_sl", return_value=False) as modify:
                asyncio.run(function(None))
                modify.assert_called_once()
                self.assertGreater(modify.call_args.args[1], position.sl)


if __name__ == "__main__":
    unittest.main()
