"""Parser safety and causal parity for the two diagnostic-driven candidates."""

import json
import unittest

import numpy as np

from extract_public_metadata import hydration_records, objects
from replay_vantage_trial28 import reference_trial
from replay_vector import replay_candidate
from snapshot_public_schema import public_scripts
from strategy_scalping456 import Scalping456Config
from test_candle_grid_replay import censor


class PathPublicTrialTests(unittest.TestCase):
    def test_public_scripts_only_observed_first_party_javascript(self):
        html = '<script src="/_next/static/a.js"></script><script src="/_next/static/a.js"></script>'
        html += '<script src="https://elsewhere.test/_next/static/a.js"></script><script src="/private/api"></script>'
        html += '<script src="/_next/static/image.png"></script><script>inline()</script>'
        self.assertEqual(public_scripts(html), ["https://thaifxbook.com/_next/static/a.js"])

    def test_hydration_fragment_reassembly_is_json_not_execution(self):
        data = {"stats": {"ea_trade_count": 1}, "rows": [{"ticket": 2}]}
        record = "a:" + json.dumps(data) + "\nb:I[1,2]\nc:T5,text\n"
        html = "<script>self.__next_f.push(" + json.dumps([1, record[:10]]) + ")</script>"
        html += "<script>self.__next_f.push(" + json.dumps([1, record[10:]]) + ")</script>"
        self.assertEqual(hydration_records(html), [("a", data)])
        self.assertEqual([obj["ticket"] for obj in objects(data) if "ticket" in obj], [2])

    def test_distance280_actual_configuration_parity_and_future_prefix(self):
        rng = np.random.default_rng(456)
        times = 1788739200000 + np.arange(30000, dtype=np.int64) * 1000
        bids = np.round(1000 + np.cumsum(rng.normal(0, .3, len(times))), 3)
        asks = bids + .585
        for fill in ("level", "quote"):
            config = Scalping456Config.fixedvol20_trial(entry_reversal_points=300, trailing_activation_points=0,
                                                      trailing_distance_points=280, stop_fill_mode=fill)
            actual = replay_candidate(times, bids, asks, config, chunk_size=37)
            self.assertEqual(actual, reference_trial(times, bids, asks, config))
            prefix = replay_candidate(times[:10100], bids[:10100], asks[:10100], config)
            self.assertEqual(prefix, censor(actual, int(times[10100])))


if __name__ == "__main__":
    unittest.main()
