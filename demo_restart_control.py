"""Cooperative restart for the two Scalping456 demo profiles; no trade actions."""

import asyncio
import json
import math
import os
import time
from pathlib import Path
from demo_scalping456 import TARGETS


PROFILE = "demo-iux-2101182459"
REQUEST = "bot_restart_request.json"
ACK = "bot_restart_ack.json"


def read_request(directory, profile, pid=None, now=None):
    directory = Path(directory)
    if profile not in TARGETS or directory.name != profile:
        return None
    try:
        path = directory / REQUEST
        if path.stat().st_size > 2048:
            return None
        request = json.loads(path.read_text(encoding="utf-8-sig"))
        created = float(request["created_epoch"])
        age = (time.time() if now is None else now) - created
        if (request["profile"] != profile or request["pid"] != (os.getpid() if pid is None else pid)
                or not math.isfinite(created) or not -5 <= age <= 120
                or not isinstance(request["request_id"], str) or not 1 <= len(request["request_id"]) <= 64):
            return None
        return request
    except (OSError, ValueError, TypeError, KeyError):
        return None


def write_ack(directory, request, worker_stopped):
    path = Path(directory) / ACK
    tmp = path.with_suffix(f".json.{os.getpid()}.tmp")
    payload = {"profile": request["profile"], "pid": os.getpid(), "request_id": request["request_id"],
               "worker_stopped": bool(worker_stopped), "ack_epoch": time.time()}
    with tmp.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, allow_nan=False)
        handle.write("\n")
    os.replace(tmp, path)


def install_restart_control(app, scheduler, broker, directory, profile, save_state, log):
    """Pause jobs, let Telegram shut down, then join the reader before exit."""
    if profile not in TARGETS or Path(directory).name != profile:
        return False
    accepted = None
    previous_stop, previous_shutdown = app.post_stop, app.post_shutdown

    async def check_request():
        nonlocal accepted
        if accepted is not None or not app.running:
            return
        request = read_request(directory, profile)
        if request is None:
            return
        accepted = request
        scheduler.pause()
        try:
            save_state()
            log("RESTART_REQUEST", "Cooperative demo restart accepted", request_id=request["request_id"])
        finally:
            app.stop_running()

    async def post_stop(application):
        # APScheduler cancels its outstanding jobs on shutdown. Yield so their
        # cancellations run before stopping the shared reader in post_shutdown.
        if scheduler.running:
            scheduler.shutdown(wait=False)
            await asyncio.sleep(0)
            await asyncio.sleep(0)
        try:
            if previous_stop is not None:
                await previous_stop(application)
        finally:
            # These two tasks are created outside Application.create_task(), so
            # Telegram's stop() does not await/cancel them for us.
            bot_task = getattr(getattr(application, "bot", None), "_worker_task", None)
            news_task = (getattr(application, "bot_data", {}) or {}).get("news_fetch_task")
            owned = [task for task in (bot_task, news_task)
                     if isinstance(task, asyncio.Task) and task is not asyncio.current_task()]
            for task in owned:
                task.cancel()
            if owned:
                await asyncio.gather(*owned, return_exceptions=True)

    async def post_shutdown(application):
        try:
            if previous_shutdown is not None:
                await previous_shutdown(application)
        finally:
            try:
                save_state()
            finally:
                stopped = broker.stop_worker()
                try:
                    log("MT5_WORKER_STOP", "Reader shutdown complete", worker_stopped=stopped)
                finally:
                    if accepted is not None:
                        write_ack(directory, accepted, stopped)

    app.post_stop, app.post_shutdown = post_stop, post_shutdown
    scheduler.add_job(check_request, "interval", seconds=1, id="demo_restart_control_job",
                      max_instances=1, coalesce=True, misfire_grace_time=3)
    return True
