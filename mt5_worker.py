"""mt5_worker.py — MT5 single-thread isolation layer

MetaTrader5 Python API ผูก connection กับ thread เดียวที่เรียก initialize()
เป็นครั้งแรก (thread affinity) — เรียก mt5.* จาก thread อื่นจะพัง (PR#20:
ThreadPoolExecutor หมุนเวียน thread ทำให้ order_send error -2 'Unnamed
arguments not allowed' ~18,236 ครั้ง ก่อน revert ใน PR#21)

โมดูลนี้ใช้ HYBRID routing (ดูเหตุผลจากหลักฐาน log จริงท้ายไฟล์ section "Wrapped
API"): พิสูจน์แล้วว่า order_send สำเร็จก็ต่อเมื่อรันบน main thread เท่านั้น (รันบน
worker/pool thread คืน -2 'Unnamed arguments not allowed' 100%) แต่คำสั่งอ่าน
ข้อมูลทนทุก thread จึงแบ่งเป็น 2 กลุ่ม:
  • order_send/initialize/login/shutdown/last_error → เรียก _mt5.* ตรงบน thread
    ผู้เรียก (ทุก call site คือ main/event loop)
  • read (copy_rates/symbol_info/positions_get/...) → ผ่าน worker thread เดียวที่
    คงที่ตลอด process (ไม่หมุนเวียนแบบ ThreadPoolExecutor)

read ที่ผ่าน worker: wrapper จะ block แบบมี timeout (CALL_TIMEOUT_DEFAULT) ถ้า
worker ไม่ตอบภายในเวลา ผู้เรียกจะได้ None กลับไปทันที (ตรงกับพฤติกรรม mt5.*
คืน None ตอน fail ที่โค้ดทั้งระบบเช็คอยู่แล้ว) แทนที่จะค้าง caller (และถ้า caller
คือ event loop หลัก ก็คือทั้งบอท) แบบไม่มีกำหนด — กัน MT5 read ค้าง freeze loop (STALL)

อัปเดต (รอบ 2 — หลักฐานจาก VPS จริงหลัง deploy hybrid): order_send ที่ย้ายมารัน
ตรงบน main thread แล้วยัง fail -2 ซ้ำ และ stall_trace.log จับได้ว่า main thread
ค้างอยู่ใน open_order (เส้นเดียวกับ order_send) นานเกิน 2 นาที — ทั้งที่ก่อนหน้านี้
พิสูจน์แล้วว่า order_send ไม่เคยค้าง สิ่งที่เปลี่ยนไปจาก Period 2 (PR#21 ที่ order_send
สำเร็จเป็นส่วนใหญ่) คือ hybrid มี "worker thread แยกที่ยังเรียก mt5.* (read) พร้อมๆ
กัน" ซึ่ง Period 2 ไม่มีเลย (ตอนนั้นทุกอย่างเดิน thread เดียวตามลำดับ ไม่มี concurrency)
สมมติฐานใหม่: MT5 IPC ไม่ thread-safe ต่อการเรียกพร้อมกันจาก 2 thread แม้แต่ละ
thread แยกกันเรียกได้ปกติ — order_send (main thread) ชนกับ read (worker thread)
พร้อมกันจึงพังหรือค้าง เพิ่ม `_mt5_lock` (threading.Lock) คลุมทุกการเรียก _mt5.*
ไม่ว่าจะมาจาก main thread (ตรง) หรือ worker thread (ผ่าน queue) เพื่อ serialize
ไม่ให้ 2 thread เข้า MT5 IPC พร้อมกันเด็ดขาด — ฝั่ง trade ใช้ `acquire(timeout=...)`
ไม่รอ lock แบบไม่มีกำหนด กัน main thread ค้างถ้า worker ดันไปค้างยึด lock อยู่ตอนนั้น

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


# ── Wrapped API (HYBRID routing) ─────────────────────────────────────────
# พิสูจน์จาก log จริง 3 ช่วง (PR#20 pool / PR#21 direct / PR#23 worker):
#   order_send สำเร็จ "ก็ต่อเมื่อรันบน main thread เท่านั้น" — รันบน thread อื่น
#   (pool ของ PR#20 หรือ worker ของ PR#23) คืน (-2,'Unnamed arguments not
#   allowed') 100% ทั้งที่ initialize() อยู่ thread เดียวกับ order_send แล้ว
#   ส่วนคำสั่ง "อ่านข้อมูล" (copy_rates/symbol_info/positions_get/...) ทนทุก
#   thread — ใน PR#23 อ่านผ่าน worker สำเร็จหมด (PATTERN_FOUND 10k+ ระหว่างที่
#   order_send พัง 100%) จึงคงไว้บน worker เพื่อกัน MT5 read ค้าง freeze loop (STALL)
#
# ดังนั้น:
#   • trade/connection (order_send, initialize, login, shutdown, last_error)
#     → เรียก _mt5.* "ตรง" บน thread ผู้เรียก ซึ่งทุก call site เป็น main/event
#       loop (ยืนยันแล้วว่าไม่มี call site ไหนอยู่ใน thread/executor แยก)
#       last_error อยู่กลุ่มนี้เพราะถูกใช้เฉพาะหลัง order_send/initialize เท่านั้น
#       ต้องอ่าน error จาก thread เดียวกับที่เพิ่งเรียก ถึงจะได้ค่าที่ถูกต้อง
#       order_send ไม่เคยปรากฏว่าค้างใน stall dump เลย → รันตรงไม่ทำให้ STALL กลับมา
#   • read ทั้งหมด → ผ่าน worker thread (timeout-protected, กัน STALL)
#   • ทุกการเรียก _mt5.* (ทั้ง 2 กลุ่ม) ต้องถือ _mt5_lock ก่อน กัน main thread
#     (trade) ชนกับ worker thread (read) เข้า MT5 IPC พร้อมกัน (ดูหัวไฟล์ "อัปเดต รอบ 2")

def _call_direct(func, *args, **kwargs):
    """เรียก _mt5.* ตรงบน thread ผู้เรียก แต่ขอ _mt5_lock ก่อนกัน race กับ worker
    thread ที่อาจกำลังเรียก read อยู่พร้อมกัน รอ lock ได้ไม่เกิน TRADE_LOCK_TIMEOUT
    ถ้าหมดเวลา (worker ค้างยึด lock อยู่) → คืน None ทันที ไม่รอค้างไม่มีกำหนด
    (None ตรงกับ contract เดิมที่ caller เช็ค `if r is None`/`if not mt5.initialize()`
    อยู่แล้วทั่วระบบ)"""
    if not _mt5_lock.acquire(timeout=TRADE_LOCK_TIMEOUT):
        return None
    try:
        return func(*args, **kwargs)
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
def positions_get(*a, **kw):        return _call(_mt5.positions_get, *a, **kw)
def orders_get(*a, **kw):           return _call(_mt5.orders_get, *a, **kw)
def orders_total(*a, **kw):         return _call(_mt5.orders_total, *a, **kw)
def copy_rates_from(*a, **kw):      return _call(_mt5.copy_rates_from, *a, **kw)
def copy_rates_from_pos(*a, **kw):  return _call(_mt5.copy_rates_from_pos, *a, **kw)
def copy_rates_range(*a, **kw):     return _call(_mt5.copy_rates_range, *a, **kw)
def history_deals_get(*a, **kw):    return _call(_mt5.history_deals_get, *a, **kw)
def history_orders_get(*a, **kw):   return _call(_mt5.history_orders_get, *a, **kw)
