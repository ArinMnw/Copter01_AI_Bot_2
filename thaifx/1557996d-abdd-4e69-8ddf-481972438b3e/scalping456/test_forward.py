"""Safety tests for the forward-holdout tooling (no network, no MT5)."""

import unittest

import numpy as np

import replay_forward


class ForwardTooling(unittest.TestCase):
    def test_join_rejects_overlapping_or_empty_caches(self):
        old = (np.array([1, 2, 3]), np.array([1, 1, 1]), np.array([2, 2, 2]))
        good = (np.array([4, 5]), np.array([1, 1]), np.array([2, 2]))
        overlap = (np.array([2, 5]), np.array([1, 1]), np.array([2, 2]))
        empty = (np.array([], dtype=np.int64), np.array([], dtype=np.int64), np.array([], dtype=np.int64))
        self.assertEqual(len(replay_forward.join(old, good, "t")[0]), 5)
        with self.assertRaises(RuntimeError):
            replay_forward.join(old, overlap, "t")
        with self.assertRaises(RuntimeError):
            replay_forward.join(old, empty, "t")

    def test_predictions_are_hashed_before_the_forward_ledger_is_read(self):
        text = (replay_forward.ROOT / "replay_forward.py").read_text(encoding="utf-8")
        self.assertLess(text.index("pre_score_manifest.json"), text.index("new_orders_*.jsonl"))

    def test_forward_tooling_never_writes_into_the_frozen_snapshot(self):
        for name in ("replay_forward.py", "fetch_forward_orders.py"):
            text = (replay_forward.ROOT / name).read_text(encoding="utf-8")
            self.assertNotIn('open("w"', text)
            self.assertNotIn("orders_35462.jsonl\").write", text)


if __name__ == "__main__":
    unittest.main()
