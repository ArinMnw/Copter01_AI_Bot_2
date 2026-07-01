"""mt5_worker.py — MT5 single-thread isolation layer

MetaTrader5 Python API ผูก connection กับ thread เดียวที่เรียก initialize()
เป็นครั้งแรก (thread affinity) — เรียก mt5.* จาก thread อื่นจะพัง (PR#20:
ThreadPoolExecutor หมุนเวียน thread ทำให้ order_send error -2 'Unnamed
arguments not allowed' ~18,236 ครั้ง ก่อน revert ใน PR#21)

ROOT CAUSE จริงของ -2 'Unnamed arguments not allowed' (ยืนยันด้วย isolated
repro script นอก main.py ทั้งหมด ตัดทุกตัวแปรเรื่อง thread/lock/process ออกแล้ว
เหลือแค่ตัวแปรเดียว): **ไม่ใช่เรื่อง thread เลย** — เป็นเพราะ wrapper function
ใช้ `def order_send(*a, **kw): return _mt5.order_send(*a, **kw)` แล้วเรียก
`mt5.order_send(request_dict)` (ไม่มี keyword arg เลย) ทำให้ `**kw` เป็น `{}`
(dict ว่าง) แต่ Python ยังส่ง `**{}` ไปที่ C extension อยู่ — แค่มี keyword-dict
ใน calling convention (ต่อให้ว่าง) ก็ทำให้ MetaTrader5 C extension ปฏิเสธด้วย
error นี้ทันที 100% ไม่ว่าจะรันบน thread ไหนก็ตาม (สลับ thread เดิม ใส่ lock เดิม
ก็ยังพัง — พิสูจน์แล้วว่า thread ไม่ใช่ตัวแปร) ส่วน `func(*args)` (ไม่มี `**kwargs`
ในการเรียกเลย) ใช้ได้ปกติเสมอ

แก้ที่ `_call_direct`/`_call`: ถ้า kwargs ว่าง ให้เรียก `func(*args)` เฉยๆ
ไม่แตะ `**kwargs` ในการเรียกเลย (ดูจุดที่แก้ด้านล่าง)

ยังคงโครงสร้าง worker thread ไว้ (read ผ่าน worker thread เดียว, timeout-protected
กัน MT5 call ค้าง freeze event loop/STALL) เพราะเรื่องนี้เป็นปัญหาคนละเรื่องกับ -2
และยังจำเป็นอยู่ — order_send/initialize/login/shutdown/last_error เรียกตรงบน
thread ผู้เรียก (ไม่ผ่าน worker) เพราะ trade action ไม่ต้องการ timeout-cut กลางคัน

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
TRADE_LOCK_TIMEOUT    = 10.0  # วิ — trade/connection รอ _mt5_lock นานสุดเท่านี้ ถ้า worker ยึดอยู่ค้าง

_q: "queue.Queue" = queue.Queue()
_worker_thread: "threading.Thread | None" = None
_start_lock = threading.Lock()
_mt5_lock = threading.Lock()   # serialize ทุกการเรียก _mt5.* กัน 2 thread ชน MT5 IPC พร้อมกัน

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
            with _mt5_lock:
                result = func(*args, **kwargs) if kwargs else func(*args)
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


# ── Wrapped API (HYBRID routing) ─────────────────────────────────────────
# root cause ของ -2 'Unnamed arguments not allowed' ไม่ใช่เรื่อง thread (ดูหัวไฟล์)
# แต่โครงสร้าง 2 กลุ่มนี้ยังจำเป็นอยู่เพื่อกัน STALL (event loop ค้างจาก MT5 read ช้า):
#   • trade/connection (order_send, initialize, login, shutdown, last_error)
#     → เรียก _mt5.* ตรงบน thread ผู้เรียก ไม่ผ่าน worker — trade action ไม่ควรมี
#       timeout ตัดกลางคัน (order_send ที่ถูกตัดกลางคันจะไม่รู้ว่า broker fill ไปแล้ว
#       หรือยัง) last_error ต้องอยู่กลุ่มนี้เพราะต้องอ่านค่าจาก thread เดียวกับที่
#       เพิ่งเรียก order_send/initialize ถึงจะได้ค่าที่ถูกต้อง
#   • read ทั้งหมด → ผ่าน worker thread เดียวคงที่ (timeout-protected กัน STALL)
#   • ทุกการเรียก _mt5.* (ทั้ง 2 กลุ่ม) ถือ _mt5_lock ก่อน กัน 2 thread (main+worker)
#     เข้า MT5 IPC พร้อมกัน

def _call_direct(func, *args, **kwargs):
    """เรียก _mt5.* ตรงบน thread ผู้เรียก แต่ขอ _mt5_lock ก่อนกัน race กับ worker
    thread ที่อาจกำลังเรียก read อยู่พร้อมกัน รอ lock ได้ไม่เกิน TRADE_LOCK_TIMEOUT
    ถ้าหมดเวลา (worker ค้างยึด lock อยู่) → คืน None ทันที ไม่รอค้างไม่มีกำหนด
    (None ตรงกับ contract เดิมที่ caller เช็ค `if r is None`/`if not mt5.initialize()`
    อยู่แล้วทั่วระบบ)

    สำคัญ: ถ้า kwargs ว่าง ต้องเรียก func(*args) เฉยๆ ห้ามเรียก func(*args, **kwargs)
    แม้ kwargs={} ก็ตาม — MetaTrader5 C extension (อย่างน้อย order_send) ปฏิเสธด้วย
    error (-2, 'Unnamed arguments not allowed') ทันทีที่ calling convention มี
    keyword-dict ติดมาด้วย ต่อให้ว่างเปล่า (ดู root cause ในหัวไฟล์)"""
    if not _mt5_lock.acquire(timeout=TRADE_LOCK_TIMEOUT):
        return None
    try:
        return func(*args, **kwargs) if kwargs else func(*args)
    finally:
        _mt5_lock.release()


# trade/connection — รันตรงบน main thread (ห้ามย้ายไป worker เด็ดขาด)
def initialize(*a, **kw):           return _call_direct(_mt5.initialize, *a, **kw)
def login(*a, **kw):                return _call_direct(_mt5.login, *a, **kw)
def shutdown(*a, **kw):             return _call_direct(_mt5.shutdown, *a, **kw)
def last_error(*a, **kw):           return _call_direct(_mt5.last_error, *a, **kw)
def order_send(*a, **kw):           return _call_direct(_mt5.order_send, *a, **kw)

# read — ผ่าน worker thread (timeout กัน MT5 call ค้าง freeze event loop)
def account_info(*a, **kw):         return _call(_mt5.account_info, *a, **kw)
def terminal_info(*a, **kw):        return _call(_mt5.terminal_info, *a, **kw)
def symbol_info(*a, **kw):          return _call(_mt5.symbol_info, *a, **kw)
def symbol_info_tick(*a, **kw):     return _call(_mt5.symbol_info_tick, *a, **kw)
def symbols_get(*a, **kw):          return _call(_mt5.symbols_get, *a, **kw)
def symbol_select(*a, **kw):        return _call(_mt5.symbol_select, *a, **kw)
def positions_get(*a, **kw):        return _call(_mt5.positions_get, *a, **kw)
def orders_get(*a, **kw):           return _call(_mt5.orders_get, *a, **kw)
def orders_total(*a, **kw):         return _call(_mt5.orders_total, *a, **kw)
def copy_rates_from(*a, **kw):      return _call(_mt5.copy_rates_from, *a, **kw)
def copy_rates_from_pos(*a, **kw):  return _call(_mt5.copy_rates_from_pos, *a, **kw)
def copy_rates_range(*a, **kw):     return _call(_mt5.copy_rates_range, *a, **kw)
def history_deals_get(*a, **kw):    return _call(_mt5.history_deals_get, *a, **kw)
def history_orders_get(*a, **kw):   return _call(_mt5.history_orders_get, *a, **kw)
