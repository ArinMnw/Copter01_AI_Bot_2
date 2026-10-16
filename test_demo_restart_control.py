"""No live broker/processes: cooperative restart and strategy import regressions."""

import asyncio
import importlib
import json
import os
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

import demo_restart_control as control
import mt5_worker as worker


class RestartControlTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.directory = Path(self.temp.name) / control.PROFILE
        self.directory.mkdir()
        self.request = {"profile": control.PROFILE, "pid": os.getpid(),
                        "created_epoch": time.time(), "request_id": "test-2459"}
        self.app = NS(running=True, post_stop=None, post_shutdown=None, stop_running=Mock())
        self.scheduler = Mock(running=True)
        self.broker = NS(stop_worker=Mock(return_value=True))
        self.save, self.log = Mock(), Mock()

    def tearDown(self):
        self.temp.cleanup()

    def write_request(self, **overrides):
        request = dict(self.request, **overrides)
        (self.directory / control.REQUEST).write_text(json.dumps(request), encoding="utf-8")

    def install(self, profile=control.PROFILE):
        return control.install_restart_control(self.app, self.scheduler, self.broker,
                                               self.directory, profile, self.save, self.log)

    def check(self):
        asyncio.run(self.scheduler.add_job.call_args.args[0]())

    def test_request_requires_exact_profile_pid_and_fresh_time(self):
        self.write_request()
        self.assertEqual(control.read_request(self.directory, control.PROFILE), self.request)
        self.assertIsNone(control.read_request(self.directory, "other-profile"))
        for fields in ({"pid": 0}, {"profile": "other-profile"}, {"created_epoch": time.time()-121},
                       {"created_epoch": time.time()+10}, {"created_epoch": float("nan")},
                       {"request_id": ""}, {"request_id": "x"*65}):
            self.write_request(**fields)
            self.assertIsNone(control.read_request(self.directory, control.PROFILE), fields)

    def test_bad_request_never_stops_bot(self):
        self.install()
        (self.directory / control.REQUEST).write_text("{broken", encoding="utf-8")
        self.check()
        self.app.stop_running.assert_not_called()
        self.scheduler.pause.assert_not_called()

    def test_other_profiles_have_no_hooks_or_restart_job(self):
        self.assertFalse(self.install("demo-iux-2101182461"))
        self.scheduler.add_job.assert_not_called()
        self.assertIsNone(self.app.post_stop)

    def test_7129_request_and_ack_cannot_cross_profile_boundaries(self):
        target = 'demo-exness-434237129'
        directory = self.directory.parent / target
        directory.mkdir()
        request = dict(self.request, profile=target)
        (directory / control.REQUEST).write_text(json.dumps(request), encoding='utf-8')
        self.assertEqual(control.read_request(directory, target), request)
        self.assertIsNone(control.read_request(directory, control.PROFILE))
        self.assertIsNone(control.read_request(self.directory, target))
        self.assertTrue(control.install_restart_control(self.app, self.scheduler, self.broker,
                                                       directory, target, self.save, self.log))
        self.check()
        asyncio.run(self.app.post_shutdown(self.app))
        ack = json.loads((directory / control.ACK).read_text(encoding='utf-8'))
        self.assertEqual(ack['profile'], target)
        self.assertTrue(ack['worker_stopped'])

    def test_live_request_pauses_once_and_ack_follows_worker_exit(self):
        self.write_request()
        self.install()
        self.assertEqual(self.scheduler.add_job.call_args.kwargs["max_instances"], 1)
        self.check()
        self.check()
        self.scheduler.pause.assert_called_once()
        self.app.stop_running.assert_called_once()
        self.assertFalse((self.directory / control.ACK).exists())
        asyncio.run(self.app.post_stop(self.app))
        self.scheduler.shutdown.assert_called_once_with(wait=False)
        asyncio.run(self.app.post_shutdown(self.app))
        self.broker.stop_worker.assert_called_once()
        ack = json.loads((self.directory / control.ACK).read_text(encoding="utf-8"))
        self.assertEqual(ack["request_id"], self.request["request_id"])
        self.assertTrue(ack["worker_stopped"])

    def test_startup_cannot_be_stopped_before_application_running(self):
        self.write_request()
        self.install()
        self.app.running = False
        self.check()
        self.app.stop_running.assert_not_called()

    def test_failed_worker_shutdown_is_not_a_success_ack(self):
        self.write_request()
        self.install()
        self.check()
        self.broker.stop_worker.return_value = False
        asyncio.run(self.app.post_shutdown(self.app))
        self.assertFalse(json.loads((self.directory/control.ACK).read_text(encoding="utf-8"))["worker_stopped"])

    def test_save_failure_cannot_leave_paused_bot_or_live_worker(self):
        self.write_request()
        self.install()
        self.save.side_effect = OSError("disk failure")
        with self.assertRaises(OSError):
            self.check()
        self.app.stop_running.assert_called_once()
        with self.assertRaises(OSError):
            asyncio.run(self.app.post_shutdown(self.app))
        self.broker.stop_worker.assert_called_once()

    def test_ordinary_clean_shutdown_also_stops_reader_without_restart_ack(self):
        self.install()
        asyncio.run(self.app.post_stop(self.app))
        asyncio.run(self.app.post_shutdown(self.app))
        self.broker.stop_worker.assert_called_once()
        self.assertFalse((self.directory/control.ACK).exists())

    def test_telegram_queue_and_news_tasks_are_joined_before_loop_close(self):
        self.install()

        async def exercise():
            queue = asyncio.Queue()
            bot_task = asyncio.create_task(queue.get())
            news_task = asyncio.create_task(asyncio.sleep(3600))
            self.app.bot = NS(_worker_task=bot_task)
            self.app.bot_data = {"news_fetch_task": news_task}
            await asyncio.sleep(0)
            await self.app.post_stop(self.app)
            self.assertTrue(bot_task.cancelled())
            self.assertTrue(news_task.cancelled())

        asyncio.run(exercise())


class WorkerShutdownTests(unittest.TestCase):
    def setUp(self):
        self.patches = [patch.object(worker, "_worker_stopping", threading.Event()),
                        patch.object(worker, "_sub_start_lock", threading.Lock()),
                        patch.object(worker, "_sub_proc", None),
                        patch.object(worker, "_sub_req_q", None),
                        patch.object(worker, "_sub_resp_q", None),
                        patch.object(worker, "_worker_thread", None)]
        for item in self.patches:
            item.start()
            self.addCleanup(item.stop)

    def test_clean_reader_exit_precedes_queue_close(self):
        child, req, resp = Mock(), Mock(), Mock()
        child.is_alive.side_effect = [True, False, False]
        with patch.object(worker, "_sub_proc", child), patch.object(worker, "_sub_req_q", req), \
                patch.object(worker, "_sub_resp_q", resp):
            self.assertTrue(worker.stop_worker(.1))
        req.put.assert_called_once_with(None)
        child.join.assert_called_once_with(timeout=.1)
        child.kill.assert_not_called()
        child.close.assert_called_once()
        req.cancel_join_thread.assert_called_once()
        resp.close.assert_called_once()

    def test_blocked_native_reader_killed_and_joined_while_parent_alive(self):
        child, req = Mock(), Mock()
        child.is_alive.side_effect = [True, True, False]
        with patch.object(worker, "_sub_proc", child), patch.object(worker, "_sub_req_q", req):
            self.assertTrue(worker.stop_worker(.1))
        child.kill.assert_called_once()
        self.assertEqual(child.join.call_count, 2)

    def test_shutdown_latch_blocks_late_reads_trades_and_respawn(self):
        self.assertTrue(worker.stop_worker(.1))
        broker_call = Mock()
        self.assertIsNone(worker._call(broker_call))
        self.assertIsNone(worker._call_direct(broker_call))
        self.assertIsNone(worker._call_subprocess("positions_get", (), {}, .1))
        with patch.object(worker._mp, "Process") as process:
            worker.start_worker()
            worker._start_subprocess_worker()
            worker._restart_subprocess_worker()
            process.assert_not_called()
        broker_call.assert_not_called()
        self.assertTrue(worker.stop_worker(.1))

    def test_new_strategy_imports_cannot_connect_trade_or_spawn_worker(self):
        with patch.object(worker, "start_worker", side_effect=AssertionError("unexpected spawn")), \
                patch.object(worker, "initialize", side_effect=AssertionError("unexpected connection")), \
                patch.object(worker, "order_send", side_effect=AssertionError("unexpected trade")):
            for name in ("strategy_indi1_live", "demo_ea2_1", "demo_scalping456"):
                importlib.reload(importlib.import_module(name))


if __name__ == "__main__":
    unittest.main()
