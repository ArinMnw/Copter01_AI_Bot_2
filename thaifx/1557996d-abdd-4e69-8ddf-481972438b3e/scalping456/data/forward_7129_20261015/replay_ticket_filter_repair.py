"""Offline only: replay captured 7129 history; never connect or send to MT5."""

import json
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace as NS

sys.path.insert(0, str(Path(__file__).resolve().parents[5]))
from demo_scalping456 import ENTRY_PROFILE, ForwardScalper, MAGIC
from test_demo_scalping456 import Broker


class CapturedBroker(Broker):
    def history_deals_get(self, *dates, position=None, ticket=None):
        if ticket is not None:
            return None  # observed native (-2, Terminal: Invalid params)
        return super().history_deals_get(*dates, position=position)


def replay(evidence):
    assert evidence['native_identity_verified']
    assert not evidence['own_positions'] and not evidence['own_pending']
    with tempfile.TemporaryDirectory() as task_dir:
        directory = Path(task_dir) / ENTRY_PROFILE
        directory.mkdir()
        broker = CapturedBroker(directory)
        broker.account = NS(**evidence['account'])
        broker.info = NS(**evidence['symbol_specs'])
        broker.tick = NS(**evidence['native_tick_samples'][-1])
        broker.order_history = {int(k): NS(**v[0]) for k, v in evidence['historical_orders'].items() if v}
        broker.deals = {int(k): [NS(**d) for d in v] for k, v in evidence['position_history'].items()}
        now = [0.0]
        runner = ForwardScalper(broker, directory, clock=lambda: now[0])
        runner.state = json.loads(json.dumps(evidence['strategy_state']))
        original_pnl = dict(runner.state['daily_net'])
        original_closed = dict(runner.state['closed_positions'])
        try:
            runner.step(True)
            # Deliberately simulated quote/time progression, NOT evidence of live freshness.
            broker.tick.time_msc += 500
            now[0] += .5
            runner.step(True)
            assert len(broker.sent) == len(broker.orders) == 2
            assert [r['type'] for r in broker.sent] == [4, 5]
            assert all(r['magic'] == MAGIC and r['symbol'] == 'XAUUSDm'
                       and r['sl'] > 0 and r['tp'] == 0 for r in broker.sent)
            assert runner.state['daily_net'] == original_pnl
            assert runner.state['closed_positions'] == original_closed
            assert not ({'4878801646', '4878801649'} & runner.state['known_orders'].keys())
            for request in broker.sent:
                side = broker.ORDER_TYPE_BUY if request['type'] == 4 else broker.ORDER_TYPE_SELL
                loss = -broker.order_calc_profit(side, request['symbol'], request['volume'],
                                                request['price'], request['sl'])
                assert 0 < loss <= broker.account.equity * .01 + 1e-9
            after = json.loads(json.dumps(runner.state))
            runner.close()
            runner = ForwardScalper(broker, directory, clock=lambda: now[0])
            runner.step(True)
            broker.tick.time_msc += 500
            now[0] += .5
            runner.step(True)
            assert len(broker.sent) == 2  # no duplicate pair after restart
            assert runner.state['daily_net'] == original_pnl
            return {'result': 'PASS_OFFLINE', 'live_order_sends': 0,
                    'simulated_quote_progression': True, 'fake_requests': broker.sent,
                    'state_after_fake_pair': after, 'restart_duplicate_requests': 0,
                    'closed_pnl_unchanged': True,
                    'risk_note': '1% per NEW order, not portfolio-wide; fees/gaps excluded',
                    'native_capture_utc': evidence['checked_utc']}
        finally:
            runner.close()


if __name__ == '__main__':
    capture = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).with_name(
        'repair_ticket_filter_native_20261016T174604.json')
    print(json.dumps(replay(json.loads(capture.read_text(encoding='utf-8'))), indent=2))
