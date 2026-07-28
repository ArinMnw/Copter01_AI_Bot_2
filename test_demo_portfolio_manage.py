# -*- coding: utf-8 -*-
"""Mock-driven behaviour test for demo_portfolio._manage_open_positions.

Exercises the real function with a fake MT5 so we verify the live code path
(thresholds, SL placement, scoping) without touching a broker.
"""
import asyncio
import copy
import sys
import types

sys.path.insert(0, r"D:\Project\Copter01_AI_Bot_2")
import demo_portfolio as dp

ORDER_TYPE_BUY, ORDER_TYPE_SELL = 0, 1
TRADE_ACTION_SLTP, TRADE_RETCODE_DONE = 6, 10009


class Pos:
    def __init__(self, ticket, magic, ptype, price_open, tp, volume=0.01):
        self.ticket, self.magic, self.type = ticket, magic, ptype
        self.price_open, self.tp, self.volume = price_open, tp, volume
        self.sl = 0.0


class Tick:
    def __init__(self, bid, ask):
        self.bid, self.ask = bid, ask


def run_case(name, price, expect_be, expect_pyr, rules, positions, trades):
    sent, placed = [], []

    fake = types.SimpleNamespace(
        ORDER_TYPE_BUY=ORDER_TYPE_BUY, ORDER_TYPE_SELL=ORDER_TYPE_SELL,
        TRADE_ACTION_SLTP=TRADE_ACTION_SLTP, TRADE_RETCODE_DONE=TRADE_RETCODE_DONE,
        positions_get=lambda **k: positions,
        symbol_info_tick=lambda s: Tick(price, price),
        order_send=lambda req: (sent.append(req),
                                types.SimpleNamespace(retcode=TRADE_RETCODE_DONE))[1],
    )
    state = {"trades": copy.deepcopy(trades), "active": {}, "last_signal_ts": {},
             "last_raw_signal_ts": {}, "pending_lts_entries": {}}

    orig = (dp.mt5, dp._load_state, dp._save_state, dp._place_market_order,
            dp.MANAGED_PORTFOLIOS, dp.log_event, dp.log_error)
    dp.mt5 = fake
    dp._load_state = lambda: state
    dp._save_state = lambda s: None
    dp._place_market_order = lambda *a, **k: (placed.append((a, k)),
                                              {"success": True, "ticket": 999,
                                               "sl": a[1], "tp": a[2]})[1]
    dp.MANAGED_PORTFOLIOS = rules
    dp.log_event = lambda *a, **k: None
    dp.log_error = lambda *a, **k: print("   ERROR:", a)
    try:
        asyncio.run(dp._manage_open_positions(None, "LTS_ROLLOVER_ORB"))
    finally:
        (dp.mt5, dp._load_state, dp._save_state, dp._place_market_order,
         dp.MANAGED_PORTFOLIOS, dp.log_event, dp.log_error) = orig

    be_done = any(r.get("action") == TRADE_ACTION_SLTP for r in sent)
    pyr_done = bool(placed)
    ok = (be_done == expect_be) and (pyr_done == expect_pyr)
    print(f"{'PASS' if ok else 'FAIL'} {name}: BE={be_done}(want {expect_be}) "
          f"PYR={pyr_done}(want {expect_pyr})")
    if be_done:
        print(f"      SL moved to {sent[0]['sl']} (entry was 4000.0)")
    if pyr_done:
        print(f"      pyramid SL={placed[0][0][1]} TP={placed[0][0][2]} vol={placed[0][1]}")
    return ok


MAGIC = dp._portfolio_magic("LTS_ROLLOVER_ORB")
# entry 4000, SL 3990 -> risk 10.0
pos = [Pos(101, MAGIC, ORDER_TYPE_BUY, 4000.0, 4100.0)]
trades = [{"ticket": 101, "leg": "LTS_ROLLOVER_ORB_1", "sl": 3990.0, "success": True}]
both = {"LTS_ROLLOVER_ORB": {"be_rr": 1.0, "pyramid_r": 3.0, "pyramid_frac": 1.0}}

results = [
    run_case("below BE threshold (+0.5R)", 4005.0, False, False, both, pos, trades),
    run_case("at BE threshold (+1R)", 4010.0, True, False, both, pos, trades),
    run_case("at pyramid threshold (+3R)", 4030.0, True, True, both, pos, trades),
    run_case("wrong magic ignored", 4030.0, False, False, both,
             [Pos(101, 999999, ORDER_TYPE_BUY, 4000.0, 4100.0)], trades),
    run_case("unknown ticket ignored", 4030.0, False, False, both, pos,
             [{"ticket": 777, "leg": "x", "sl": 3990.0, "success": True}]),
    run_case("already done -> no repeat", 4030.0, False, False, both, pos,
             [{"ticket": 101, "leg": "L", "sl": 3990.0, "success": True,
               "be_done": True, "pyramid_done": True}]),
    run_case("pyramid disabled (default)", 4030.0, True, False,
             {"LTS_ROLLOVER_ORB": {"be_rr": 1.0, "pyramid_r": None}}, pos, trades),
]
# leg filtering: only S224 may pyramid, S202 in the same portfolio must not
live_rules = dp.MANAGED_PORTFOLIOS["LTS_ROLLOVER_ORB"]
s224_tr = [{"ticket": 101, "leg": "LTS_ROLLOVER_ORB_1",
            "label": "LTS_ROLLOVER_ORB_1 DIRECT_S224_M5", "sl": 3990.0, "success": True}]
s202_tr = [{"ticket": 101, "leg": "LTS_ROLLOVER_ORB_2",
            "label": "LTS_ROLLOVER_ORB_2 DIRECT_S202_M5", "sl": 3990.0, "success": True}]
results.append(run_case("LIVE CFG: S224 leg pyramids", 4030.0, True, True,
                        {"LTS_ROLLOVER_ORB": live_rules}, pos, s224_tr))
results.append(run_case("LIVE CFG: S202 leg must NOT pyramid", 4030.0, True, False,
                        {"LTS_ROLLOVER_ORB": live_rules}, pos, s202_tr))

# SELL side: entry 4000, SL 4010 -> risk 10; price 3970 = +3R
sell_pos = [Pos(202, MAGIC, ORDER_TYPE_SELL, 4000.0, 3900.0)]
sell_tr = [{"ticket": 202, "leg": "L", "sl": 4010.0, "success": True}]
results.append(run_case("SELL +3R", 3970.0, True, True, both, sell_pos, sell_tr))

print("\nRESULT:", "ALL PASS" if all(results) else "SOME FAILED")
