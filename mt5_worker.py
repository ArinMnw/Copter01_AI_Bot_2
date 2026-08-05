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

── MT5_WORKER_MODE = "subprocess" (opt-in, ต่อ profile ผ่าน profile.env) ──────
โหมด thread เดิม (default) มีข้อจำกัดที่แก้ไม่ได้: ถ้า _mt5.* call จริงค้างอยู่ที่
native/IPC layer (เช่น terminal หน่วง) Python ยกเลิก call ที่กำลังรันอยู่ใน thread
ไม่ได้เลย (fut.result(timeout=...) แค่เลิกรอฝั่งนี้ — worker thread ยังค้างถือ
_mt5_lock อยู่จริง บล็อก call ถัดไปทุกตัวเป็นโดมิโน จนต้อง os._exit(1) รอ
supervisor restart ทั้ง process ถึงจะหลุด)

โหมด subprocess แก้ตรงจุดนี้: read ทั้งหมดส่งไปรันใน child process แยกต่างหาก
(เรียก mt5.initialize() ของตัวเองอีกชุด แนบเข้า terminal เดียวกัน — ทดสอบแล้วว่า
2 process initialize() พร้อมกันกับ terminal เดียวกันปลอดภัย ไม่รบกวนกัน) ถ้า
child ค้างจริง เรา `terminate()`/`kill()` ที่ตัว OS process ได้จริง (ต่างจาก thread
ที่ฆ่าไม่ได้) แล้ว spawn ตัวใหม่ทันที โดยไม่ต้อง restart main.py ทั้งตัว (ไม่ต้อง
re-login/restore state ใหม่) — ผลกระทบตอนเกิด wedge น้อยกว่าเดิมมาก

trade/connection (order_send/initialize/login/shutdown/last_error) ไม่แตะเลย
ยังรันตรงบน thread ผู้เรียกเหมือนเดิมทั้ง 2 โหมด (เหตุผลเดิม — ดูด้านบน)

MT5 result object (TradePosition/SymbolInfo/AccountInfo/...) เป็น C-extension
type ส่งผ่าน multiprocessing Queue ตรงๆไม่ได้ (pickle ไม่ได้) — แปลงเป็น dict
ด้วย `_asdict()` ฝั่ง child ก่อนส่งกลับ แล้วห่อด้วย `_MT5Obj` proxy ฝั่ง parent
ให้ attribute access (`pos.ticket`) ยังใช้ได้เหมือนเดิมทุกจุดเรียกในโค้ดเดิม
โดยไม่ต้องแก้ scanner.py/trailing.py/ฯลฯ เลยสักจุด
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

# ── สถานะให้ watchdog เช็คว่า worker แข็งค้างอยู่ไหม (อัปเดตโดย worker/subprocess ฝั่งเรียกเอง) ──
current_call_name: str = ""          # ฟังก์ชันที่ worker กำลังรันอยู่ตอนนี้ (ว่าง = ไม่มี call ค้าง)
current_call_started_ts: float = 0.0  # เวลาที่เริ่มรัน call ปัจจุบัน

_WORKER_MODE: str = "thread"   # "thread" (default) หรือ "subprocess" — ตั้งครั้งเดียวตอน start_worker()


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


def _resolve_worker_mode() -> str:
    try:
        import config
        mode = str(getattr(config, "MT5_WORKER_MODE", "thread") or "thread").strip().lower()
    except Exception:
        mode = "thread"
    return mode if mode in ("thread", "subprocess") else "thread"


def start_worker() -> None:
    """เริ่ม worker (idempotent — เรียกซ้ำได้ไม่เป็นไร) เลือกโหมดจาก
    config.MT5_WORKER_MODE (deferred import กัน circular import — config.py
    เอง import mt5_worker ตอน module-level)"""
    global _worker_thread, _WORKER_MODE
    with _start_lock:
        if _worker_thread is not None or _sub_proc is not None:
            return
        _WORKER_MODE = _resolve_worker_mode()
        if _WORKER_MODE == "subprocess":
            _start_subprocess_worker()
            return
        _worker_thread = threading.Thread(target=_worker_loop, name="MT5Worker", daemon=True)
        _worker_thread.start()


def _call(func, *args, _timeout: float = None, **kwargs):
    if _timeout is None:
        _timeout = CALL_TIMEOUT_DEFAULT   # อ่านค่าปัจจุบันตอนเรียก ไม่ bind ตอน def
    if _worker_thread is None and _sub_proc is None:
        start_worker()
    name = getattr(func, "__name__", str(func))
    if _WORKER_MODE == "subprocess":
        return _call_subprocess(name, args, kwargs, _timeout)
    fut: Future = Future()
    _q.put((name, func, args, kwargs, fut))
    try:
        return fut.result(timeout=_timeout)
    except _FutTimeout:
        return None


# ── Subprocess-mode internals ─────────────────────────────────────────────
import multiprocessing as _mp

_sub_proc = None            # type: "_mp.process.BaseProcess | None"
_sub_req_q = None           # type: "_mp.queues.Queue | None"
_sub_resp_q = None          # type: "_mp.queues.Queue | None"
_sub_start_lock = threading.Lock()
_sub_call_lock = threading.Lock()   # กันเรียกซ้อน (subprocess ประมวลผลทีละคำสั่งเหมือน thread เดิม)


class _MT5Obj:
    """proxy ห่อ dict (จาก _asdict() ของ TradePosition/SymbolInfo/AccountInfo/...)
    ให้ attribute access (`obj.ticket`) ใช้ได้เหมือน MT5 object ตัวจริง — ไม่ต้อง
    แก้ call site เดิมทั่วโค้ดที่อ่านผลจาก mt5_worker"""
    __slots__ = ("_d",)

    def __init__(self, d: dict):
        object.__setattr__(self, "_d", d)

    def __getattr__(self, name):
        try:
            return self._d[name]
        except KeyError:
            raise AttributeError(name)

    def __getitem__(self, key):
        return self._d[key]

    def _asdict(self) -> dict:
        return dict(self._d)

    def __repr__(self) -> str:
        return f"MT5Obj({self._d!r})"


def _to_picklable(value):
    """แปลงผลลัพธ์จาก _mt5.* ให้ pickle ผ่าน multiprocessing Queue ได้ — เรียกฝั่ง
    child เท่านั้น (numpy array ของ copy_rates_* pickle ได้เองอยู่แล้ว ไม่แตะ)"""
    if value is None:
        return None
    if hasattr(value, "_asdict"):
        try:
            return ("__mt5obj__", value._asdict())
        except Exception:
            return None
    if isinstance(value, tuple):
        return tuple(_to_picklable(v) for v in value)
    return value


def _from_picklable(value):
    """ฝั่ง parent: กลับ dict ที่ห่อไว้เป็น _MT5Obj ให้ attribute access ใช้ได้ปกติ"""
    if isinstance(value, tuple):
        if len(value) == 2 and value[0] == "__mt5obj__":
            return _MT5Obj(value[1])
        return tuple(_from_picklable(v) for v in value)
    return value


def _subprocess_entry(req_q, resp_q, init_kwargs: dict) -> None:
    """ฟังก์ชันหลักของ child process — import MetaTrader5 แยกชุดของตัวเอง
    (แนบเข้า terminal เดิมด้วย path/portable เดียวกับ parent) แล้ววนรอรับคำสั่ง
    อ่านทีละตัว ส่งผลกลับผ่าน resp_q เท่านั้น — ไม่ทำ trade action ใดๆ ทั้งสิ้น"""
    import MetaTrader5 as _mt5c
    try:
        _mt5c.initialize(**init_kwargs)
    except Exception:
        pass   # ปล่อยให้ call แรกที่ parent ส่งมา fail แทน — parent จัดการ retry/restart เอง
    while True:
        try:
            item = req_q.get()
        except (EOFError, OSError):
            break
        if item is None:   # sentinel หยุด process
            break
        req_id, name, args, kwargs = item
        try:
            func = getattr(_mt5c, name)
            result = func(*args, **kwargs) if kwargs else func(*args)
            resp_q.put((req_id, "ok", _to_picklable(result)))
        except Exception as e:
            resp_q.put((req_id, "err", f"{type(e).__name__}: {e}"))


def _build_mt5_init_kwargs() -> dict:
    """อ่าน path/portable/timeout จาก config ของ profile ปัจจุบัน (deferred import
    กัน circular import — เหมือน _resolve_worker_mode ด้านบน)"""
    try:
        import config
        kw = {"timeout": int(getattr(config, "MT5_TIMEOUT_MS", 120000) or 120000)}
        mt5_path = str(getattr(config, "MT5_PATH", "") or "").strip()
        if mt5_path:
            kw["path"] = mt5_path
            kw["portable"] = bool(getattr(config, "MT5_PORTABLE", True))
        return kw
    except Exception:
        return {}


def _start_subprocess_worker() -> None:
    global _sub_proc, _sub_req_q, _sub_resp_q
    with _sub_start_lock:
        if _sub_proc is not None and _sub_proc.is_alive():
            return
        _sub_req_q = _mp.Queue()
        _sub_resp_q = _mp.Queue()
        init_kwargs = _build_mt5_init_kwargs()
        _sub_proc = _mp.Process(
            target=_subprocess_entry,
            args=(_sub_req_q, _sub_resp_q, init_kwargs),
            name="MT5WorkerProc",
            daemon=True,
        )
        _sub_proc.start()


def _restart_subprocess_worker() -> None:
    """kill child เดิมทิ้ง (ถ้ายังไม่ตาย) แล้ว spawn ใหม่ — เรียกตอนตรวจพบว่า
    child ค้างจริง (timeout ที่ _call_subprocess) ทำได้เพราะเป็น process จริง
    ต่างจาก thread เดิมที่ terminate ไม่ได้"""
    global _sub_proc, _sub_req_q, _sub_resp_q, current_call_name, current_call_started_ts
    with _sub_start_lock:
        old = _sub_proc
        _sub_proc = None
        if old is not None:
            try:
                old.kill()
                old.join(timeout=3)
            except Exception:
                pass
        current_call_name = ""
        current_call_started_ts = 0.0
    _start_subprocess_worker()


_sub_req_id = 0
_sub_req_id_lock = threading.Lock()


def _call_subprocess(name: str, args: tuple, kwargs: dict, timeout: float):
    global current_call_name, current_call_started_ts, _sub_req_id
    if _sub_proc is None or not _sub_proc.is_alive():
        _start_subprocess_worker()
    with _sub_call_lock:   # ทีละคำสั่งต่อรอบ (เหมือน thread-worker เดิม — ไม่ pipeline)
        with _sub_req_id_lock:
            _sub_req_id += 1
            req_id = _sub_req_id
        current_call_name = name
        current_call_started_ts = time.time()
        try:
            _sub_req_q.put((req_id, name, args, kwargs))
        except Exception:
            # queue พัง (เช่น child ตายกลางคัน) → restart แล้วคืน None ตาม contract เดิม
            _restart_subprocess_worker()
            current_call_name = ""
            current_call_started_ts = 0.0
            return None
        try:
            resp_req_id, status, payload = _sub_resp_q.get(timeout=timeout)
        except queue.Empty:
            # child ค้างจริงที่ native call — kill ทิ้งแล้ว spawn ใหม่ทันที (ต่างจาก
            # thread เดิมที่ทำแบบนี้ไม่ได้ ต้องรอ os._exit(1) + supervisor restart ทั้ง process)
            _restart_subprocess_worker()
            return None
        finally:
            current_call_name = ""
            current_call_started_ts = 0.0
        if status == "err":
            # ยึด contract เดิม (worker thread เดิมก็ raise exception กลับผู้เรียกเหมือนกัน)
            raise RuntimeError(str(payload))
        return _from_picklable(payload)


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
