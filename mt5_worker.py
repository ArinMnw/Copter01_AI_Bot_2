"""mt5_worker.py — MT5 single-thread isolation layer

MetaTrader5 Python API ผูก connection กับ thread เดียวที่เรียก initialize()
เป็นครั้งแรก (thread affinity) — เรียก mt5.* จาก thread อื่นจะพัง (PR#20:
ThreadPoolExecutor หมุนเวียน thread ทำให้ order_send error -2 'Unnamed
arguments not allowed' ~18,236 ครั้ง ก่อน revert ใน PR#21)

โมดูลนี้แก้ปัญหานี้ทั้งระบบโดยไม่ละเมิด thread affinity: สร้าง worker thread
เดียวที่คงที่ตลอด process (ไม่หมุนเวียนแบบ ThreadPoolExecutor) แล้วรัน mt5.*
ทุกตัว "เฉพาะบน thread นี้เท่านั้น" ไม่ว่าผู้เรียกจะอยู่ thread ไหนก็ตาม

ผู้เรียก (event loop หรือ thread ไหนก็ได้) เรียกผ่าน wrapper function ในไฟล์นี้
แทน mt5.* ตรง — wrapper จะ block แบบมี timeout (CALL_TIMEOUT_DEFAULT) ถ้า
worker ไม่ตอบภายในเวลา ผู้เรียกจะได้ None กลับไปทันที (ตรงกับพฤติกรรม mt5.*
คืน None ตอน fail ที่โค้ดทั้งระบบเช็คอยู่แล้ว) แทนที่จะค้าง caller (และถ้า caller
คือ event loop หลัก ก็คือทั้งบอท) แบบไม่มีกำหนดเหมือนเดิม

ห้าม `import MetaTrader5` ตรงที่ไฟล์อื่นในโค้ด production — ให้
`import mt5_worker as mt5` แทนเสมอ (ทุก call site ถูก migrate มาใช้โมดูลนี้แล้ว)
"""
import queue
import threading
import time
from concurrent.futures import Future, TimeoutError as _FutTimeout

import MetaTrader5 as _mt5
from MetaTrader5 import *  # noqa: F401,F403 — ดึง constants (TRADE_ACTION_*, ORDER_TYPE_*, TIMEFRAME_*, DEAL_*, ...) เข้ามาตรงๆ ปลอดภัย เพราะเป็นแค่ค่าคงที่ ไม่ใช่การเรียก API

CALL_TIMEOUT_DEFAULT = 15.0   # วิ — ผู้เรียกแต่ละจุดรอ worker ตอบนานสุดเท่านี้
INIT_TIMEOUT          = 30.0  # initialize()/login() อาจช้ากว่าปกติตอน terminal เพิ่ง start

_q: "queue.Queue" = queue.Queue()
_worker_thread: "threading.Thread | None" = None
_start_lock = threading.Lock()

# ── สถานะให้ watchdog เช็คว่า worker แข็งค้างอยู่ไหม (อัปเดตโดย worker thread เอง) ──
current_call_name: str = ""          # ฟังก์ชันที่ worker กำลังรันอยู่ตอนนี้ (ว่าง = ไม่มี call ค้าง)
current_call_started_ts: float = 0.0  # เวลาที่เริ่มรัน call ปัจจุบัน


def _worker_loop() -> None:
    global current_call_name, current_call_started_ts
    while True:
        name, func, args, kwargs, fut = _q.get()
        if func is None:   # sentinel หยุด worker
            break
        current_call_name = name
        current_call_started_ts = time.time()
        try:
            result = func(*args, **kwargs)
            if not fut.cancelled():
                fut.set_result(result)
        except Exception as e:
            if not fut.cancelled():
                fut.set_exception(e)
        finally:
            current_call_name = ""
            current_call_started_ts = 0.0


def start_worker() -> None:
    """เริ่ม worker thread (idempotent — เรียกซ้ำได้ไม่เป็นไร)"""
    global _worker_thread
    with _start_lock:
        if _worker_thread is not None:
            return
        _worker_thread = threading.Thread(target=_worker_loop, name="MT5Worker", daemon=True)
        _worker_thread.start()


def _call(func, *args, _timeout: float = None, **kwargs):
    if _timeout is None:
        _timeout = CALL_TIMEOUT_DEFAULT   # อ่านค่าปัจจุบันตอนเรียก ไม่ bind ตอน def
    if _worker_thread is None:
        start_worker()
    fut: Future = Future()
    name = getattr(func, "__name__", str(func))
    _q.put((name, func, args, kwargs, fut))
    try:
        return fut.result(timeout=_timeout)
    except _FutTimeout:
        return None


def is_wedged(stale_after: float = 60.0) -> bool:
    """worker กำลังรัน call เดิมค้างนานเกิน stale_after วิ → ถือว่า wedged จริง
    (ไม่ใช่แค่ idle เฉยๆ — idle คือ current_call_name ว่างอยู่แล้ว)"""
    name = current_call_name
    if not name:
        return False
    return (time.time() - current_call_started_ts) > stale_after


def wedge_info() -> str:
    name = current_call_name
    if not name:
        return ""
    age = time.time() - current_call_started_ts
    return f"{name} (ค้าง {age:.0f}s)"


# ── Wrapped API — ชื่อตรงกับ mt5.* ของจริงทุกตัวที่ใช้ใน production ──────
def initialize(*a, **kw):           return _call(_mt5.initialize, *a, _timeout=INIT_TIMEOUT, **kw)
def login(*a, **kw):                return _call(_mt5.login, *a, _timeout=INIT_TIMEOUT, **kw)
def shutdown(*a, **kw):             return _call(_mt5.shutdown, *a, **kw)
def last_error(*a, **kw):           return _call(_mt5.last_error, *a, **kw)
def account_info(*a, **kw):         return _call(_mt5.account_info, *a, **kw)
def terminal_info(*a, **kw):        return _call(_mt5.terminal_info, *a, **kw)
def symbol_info(*a, **kw):          return _call(_mt5.symbol_info, *a, **kw)
def symbol_info_tick(*a, **kw):     return _call(_mt5.symbol_info_tick, *a, **kw)
def positions_get(*a, **kw):        return _call(_mt5.positions_get, *a, **kw)
def orders_get(*a, **kw):           return _call(_mt5.orders_get, *a, **kw)
def orders_total(*a, **kw):         return _call(_mt5.orders_total, *a, **kw)
def order_send(*a, **kw):           return _call(_mt5.order_send, *a, **kw)
def copy_rates_from(*a, **kw):      return _call(_mt5.copy_rates_from, *a, **kw)
def copy_rates_from_pos(*a, **kw):  return _call(_mt5.copy_rates_from_pos, *a, **kw)
def copy_rates_range(*a, **kw):     return _call(_mt5.copy_rates_range, *a, **kw)
def history_deals_get(*a, **kw):    return _call(_mt5.history_deals_get, *a, **kw)
def history_orders_get(*a, **kw):   return _call(_mt5.history_orders_get, *a, **kw)
