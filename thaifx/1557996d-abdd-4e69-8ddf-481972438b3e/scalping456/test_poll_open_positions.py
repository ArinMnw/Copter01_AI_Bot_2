"""Offline tests for the open-positions watcher (no network)."""

import json
import unittest

import poll_open_positions as pop


def page(updated, rows):
    payload = "5:" + json.dumps({"updated_at": updated, "rows": rows}) + "\n"
    return "<html><script>self.__next_f.push(" + json.dumps([1, payload]) + ")</script></html>"


ROW = {"ticket": 7, "symbol": "XAUUSD+", "trade_type": "buy", "volume": 10, "open_price": 4000.0,
       "current_price": 4001.0, "sl": 0, "tp": 0, "comment": "PipScalperEA V2 BUY STOP",
       "open_time": "2026-10-09T01:00:00+00:00", "profit": 100, "ignored_private_field": "x"}


class PollTests(unittest.TestCase):
    def test_parse_extracts_only_selected_fields_and_sync_time(self):
        updated, positions = pop.parse_page(page("2026-10-09T01:54:47+00:00", [ROW]))
        self.assertEqual(updated, "2026-10-09T01:54:47+00:00")
        self.assertEqual(len(positions), 1)
        self.assertNotIn("ignored_private_field", positions[0])
        self.assertEqual(positions[0]["sl"], 0)

    def test_signature_changes_with_sl_or_sync_time(self):
        a = pop.signature("t1", [ROW])
        self.assertEqual(a, pop.signature("t1", [dict(ROW)]))
        self.assertNotEqual(a, pop.signature("t2", [ROW]))
        self.assertNotEqual(a, pop.signature("t1", [dict(ROW, sl=3999.8)]))

    def test_interval_is_slow_when_stale_and_fast_after_a_recent_change(self):
        self.assertEqual(pop.next_interval(None, None, 100, 180, 15), 180)
        self.assertEqual(pop.next_interval("t", 90, 100, 180, 15), 15)
        self.assertEqual(pop.next_interval("t", 0, 1000, 180, 15), 180)

    def test_refuses_to_poll_too_fast(self):
        import sys
        old = sys.argv
        sys.argv = ["x", "--tag", "t", "--live-interval", "1"]
        try:
            with self.assertRaises(SystemExit):
                pop.main()
        finally:
            sys.argv = old


if __name__ == "__main__":
    unittest.main()
