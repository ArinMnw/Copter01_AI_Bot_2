import logging
import MetaTrader5 as mt5
import os
import re
import time
from datetime import datetime, timedelta, timezone


TZ_OFFSET = 7
LOG_DIR       = "logs"
OLD_LOG_DIR   = os.path.join(LOG_DIR, "old_logs")   # archived monthly logs
BOT_LOG_FILE  = os.path.join(LOG_DIR, "bot.log")
SYSTEM_LOG_DIR  = os.path.join(LOG_DIR, "system")
SYSTEM_LOG_FILE = os.path.join(SYSTEM_LOG_DIR, "system.log")
DEBUG_LOG_DIR   = os.path.join(LOG_DIR, "debug")
LOG_RETENTION_DAYS = 15
_MAX_BOT_LOG_BYTES = 100 * 1024 * 1024  # 100 MB

_TS_LINE_RE          = re.compile(r"^\[?(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})")
_MONTHLY_LOG_RE      = re.compile(r"^bot-\d{4}-\d{2}\.log$")
_ERROR_MONTHLY_LOG_RE = re.compile(r"^error-\d{4}-\d{2}\.log$")
_SYSTEM_MONTHLY_LOG_RE = re.compile(r"^system-\d{4}-\d{2}\.log$")

# ── Rotation state ─────────────────────────────────────────────
_last_bot_log_month: tuple = (0, 0)   # (year, month) ที่ bot.log ถูกเขียนล่าสุด

# ── _now_bkk() throttle ─────────────────────────────────────────
# log_event()/log_error() เรียก _now_bkk() ทุกบรรทัด (หลายร้อยครั้ง/รอบ scan)
# ถ้าเรียก mt5.symbol_info_tick() สดทุกครั้ง แล้ว MT5 IPC ค้าง/หน่วง จะลาก
# event loop ค้างไปด้วย (เหมือน MT5 blocking call อื่นๆ ที่ทำให้ supervisor restart วนลูป)
# จึง cache offset ไว้ แล้ว refresh จาก MT5 แค่เป็นช่วงๆ พอ
_NOW_BKK_REFRESH_SEC = 15.0
_now_bkk_cache_offset: timedelta = None
_now_bkk_cache_at: float = 0.0


def _now_bkk() -> datetime:
    global _now_bkk_cache_offset, _now_bkk_cache_at

    nowt = time.monotonic()
    if _now_bkk_cache_offset is not None and (nowt - _now_bkk_cache_at) < _NOW_BKK_REFRESH_SEC:
        return datetime.now(timezone.utc) + _now_bkk_cache_offset

    try:
        import config as _config
        symbols = []
        current_symbol = getattr(_config, "SYMBOL", "")
        if current_symbol:
            symbols.append(current_symbol)
        for sym in getattr(_config, "SYMBOL_CONFIG", {}).keys():
            if sym not in symbols:
                symbols.append(sym)

        best_ts = None
        for sym in symbols:
            try:
                tick = mt5.symbol_info_tick(sym)
            except Exception:
                tick = None
            ts = int(getattr(tick, "time", 0) or 0) if tick else 0
            if ts > 0 and (best_ts is None or ts > best_ts):
                best_ts = ts

        if best_ts is not None:
            dt = _config.mt5_ts_to_bkk(best_ts)
            if dt is not None:
                _now_bkk_cache_offset = dt - datetime.now(timezone.utc)
                _now_bkk_cache_at = nowt
                return dt
    except Exception:
        pass

    server_tz = getattr(locals().get("_config", None), "MT5_SERVER_TZ", 1) if "_config" in locals() else 1
    fallback_offset = timedelta(hours=TZ_OFFSET - server_tz)
    _now_bkk_cache_offset = fallback_offset
    _now_bkk_cache_at = nowt
    return datetime.now(timezone.utc) + fallback_offset


def _sanitize(value) -> str:
    if value is None:
        return "-"
    text = str(value)
    return " | ".join(part.strip() for part in text.splitlines() if part.strip()) or "-"


def _ensure_log_dir() -> None:
    os.makedirs(LOG_DIR, exist_ok=True)
    os.makedirs(OLD_LOG_DIR, exist_ok=True)
    os.makedirs(SYSTEM_LOG_DIR, exist_ok=True)
    os.makedirs(DEBUG_LOG_DIR, exist_ok=True)


def get_monthly_bot_log_file(year: int, month: int) -> str:
    """archive path สำหรับ bot log เดือนนั้น (อยู่ใน old_logs/)"""
    return os.path.join(OLD_LOG_DIR, f"bot-{year:04d}-{month:02d}.log")


def get_monthly_bot_log_file_for_dt(dt: datetime) -> str:
    return get_monthly_bot_log_file(dt.year, dt.month)


def get_monthly_error_log_file(year: int, month: int) -> str:
    """archive path สำหรับ error log เดือนนั้น (old_logs/ ถ้าไม่ใช่เดือนนี้)"""
    return os.path.join(OLD_LOG_DIR, f"error-{year:04d}-{month:02d}.log")


def get_monthly_error_log_file_for_dt(dt: datetime) -> str:
    """เขียน error log เดือนปัจจุบันที่ logs/ (ยังไม่ archived)"""
    return os.path.join(LOG_DIR, f"error-{dt.year:04d}-{dt.month:02d}.log")


def get_monthly_system_log_file(year: int, month: int) -> str:
    """archive path สำหรับ system log เดือนนั้น (อยู่ใน old_logs/)"""
    return os.path.join(OLD_LOG_DIR, f"system-{year:04d}-{month:02d}.log")


# ── Bot log rotation ───────────────────────────────────────────

def _rotate_bot_log(old_year: int, old_month: int) -> None:
    """rename bot.log → bot-YYYY-MM.log"""
    archive = get_monthly_bot_log_file(old_year, old_month)
    if os.path.exists(BOT_LOG_FILE) and not os.path.exists(archive):
        try:
            os.rename(BOT_LOG_FILE, archive)
        except OSError:
            pass


def _rotate_bot_log_if_needed(now_dt: datetime) -> None:
    """เช็คทุกครั้งที่เขียน log — ถ้าเดือนเปลี่ยน → rotate"""
    global _last_bot_log_month
    cur = (now_dt.year, now_dt.month)
    if _last_bot_log_month == (0, 0):
        _last_bot_log_month = cur
        return
    if cur == _last_bot_log_month:
        return
    # เดือนเปลี่ยน
    _rotate_bot_log(*_last_bot_log_month)
    _last_bot_log_month = cur


def _rotate_bot_log_by_size(now_dt: datetime) -> None:
    """ถ้า bot.log > 100 MB → rotate เป็น bot-YYYY-MM-DD-NN.log ใน old_logs/"""
    try:
        if not os.path.exists(BOT_LOG_FILE):
            return
        if os.path.getsize(BOT_LOG_FILE) < _MAX_BOT_LOG_BYTES:
            return
        date_str = now_dt.strftime("%Y-%m-%d")
        for seq in range(100):
            archive = os.path.join(OLD_LOG_DIR, f"bot-{date_str}-{seq:02d}.log")
            if not os.path.exists(archive):
                os.rename(BOT_LOG_FILE, archive)
                return
    except OSError:
        pass


def _safe_move_to_old(src: str, dst: str) -> None:
    """rename src → dst ถ้า src มีอยู่และ dst ยังไม่มี"""
    if os.path.exists(src) and not os.path.exists(dst):
        try:
            os.rename(src, dst)
        except OSError:
            pass


def _check_bot_log_on_startup() -> None:
    """ตรวจ bot.log ตอน start — ถ้าเป็นเดือนก่อน → rotate ทันที"""
    global _last_bot_log_month
    now_dt = _now_bkk()
    cur = (now_dt.year, now_dt.month)
    if os.path.exists(BOT_LOG_FILE):
        try:
            last_line = None
            with open(BOT_LOG_FILE, "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    if line.strip():
                        last_line = line
            if last_line:
                ts = _parse_log_line_ts(last_line)
                if ts and (ts.year, ts.month) != cur:
                    _rotate_bot_log(ts.year, ts.month)
        except Exception:
            pass
    _last_bot_log_month = cur


def _check_system_log_on_startup() -> None:
    """ตรวจ system.log ตอน start — ถ้าเป็นเดือนก่อน → rotate ทันที
    ต้องเรียกก่อนสร้าง _MonthlyRotatingFileHandler เพื่อให้ไฟล์ถูก rotate ก่อน handler เปิด"""
    if not os.path.exists(SYSTEM_LOG_FILE):
        return
    now_dt = _now_bkk()
    cur = (now_dt.year, now_dt.month)
    try:
        last_line = None
        with open(SYSTEM_LOG_FILE, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                if line.strip():
                    last_line = line
        if last_line:
            ts = _parse_log_line_ts(last_line)
            if ts and (ts.year, ts.month) != cur:
                archive = get_monthly_system_log_file(ts.year, ts.month)
                if os.path.exists(SYSTEM_LOG_FILE) and not os.path.exists(archive):
                    os.rename(SYSTEM_LOG_FILE, archive)
    except Exception:
        pass


def _move_old_logs_on_startup() -> None:
    """ย้าย monthly log เก่าที่หลงเหลือใน logs/ และ system/ ไป old_logs/"""
    now_dt = _now_bkk()
    cur_ym = (now_dt.year, now_dt.month)

    # bot-YYYY-MM.log ใน logs/
    try:
        for name in os.listdir(LOG_DIR):
            if not _MONTHLY_LOG_RE.match(name):
                continue
            src = os.path.join(LOG_DIR, name)
            dst = os.path.join(OLD_LOG_DIR, name)
            _safe_move_to_old(src, dst)
    except Exception:
        pass

    # error-YYYY-MM.log ใน logs/ ที่ไม่ใช่เดือนนี้
    try:
        for name in os.listdir(LOG_DIR):
            if not _ERROR_MONTHLY_LOG_RE.match(name):
                continue
            # ดึง year/month จาก ชื่อไฟล์
            m = re.search(r"(\d{4})-(\d{2})\.log$", name)
            if not m:
                continue
            ym = (int(m.group(1)), int(m.group(2)))
            if ym == cur_ym:
                continue   # เดือนนี้ยังใช้งานอยู่
            src = os.path.join(LOG_DIR, name)
            dst = os.path.join(OLD_LOG_DIR, name)
            _safe_move_to_old(src, dst)
    except Exception:
        pass

    # system-YYYY-MM.log ใน system/
    try:
        for name in os.listdir(SYSTEM_LOG_DIR):
            if not _SYSTEM_MONTHLY_LOG_RE.match(name):
                continue
            src = os.path.join(SYSTEM_LOG_DIR, name)
            dst = os.path.join(OLD_LOG_DIR, name)
            _safe_move_to_old(src, dst)
    except Exception:
        pass


# ── System log rotation handler ────────────────────────────────

class _MonthlyRotatingFileHandler(logging.FileHandler):
    """FileHandler ที่ rotate ทุกต้นเดือน → system-YYYY-MM.log"""

    def __init__(self, filename: str, **kwargs):
        # ตั้งต้นด้วยเดือนปัจจุบันทันที เพื่อให้ emit() แรกตรวจ month-change ได้ถูกต้อง
        # (_check_system_log_on_startup ถูกเรียกก่อนแล้ว ดังนั้น file นี้เป็นเดือนปัจจุบัน)
        try:
            _now = _now_bkk()
            self._current_month: tuple = (_now.year, _now.month)
        except Exception:
            self._current_month = (0, 0)
        super().__init__(filename, mode="a", encoding="utf-8", **kwargs)

    def _archive_path(self, year: int, month: int) -> str:
        return get_monthly_system_log_file(year, month)

    def _do_rotate(self, old_year: int, old_month: int) -> None:
        archive = self._archive_path(old_year, old_month)
        try:
            self.close()
            if os.path.exists(self.baseFilename) and not os.path.exists(archive):
                os.rename(self.baseFilename, archive)
        except OSError:
            pass
        try:
            self.stream = self._open()
        except OSError:
            pass

    def emit(self, record: logging.LogRecord) -> None:
        try:
            now = _now_bkk()
            cur = (now.year, now.month)
            if self._current_month == (0, 0):
                # fallback ถ้า __init__ ไม่สามารถ get เวลาได้
                self._current_month = cur
            elif cur != self._current_month:
                self._do_rotate(*self._current_month)
                self._current_month = cur
        except Exception:
            pass
        super().emit(record)


def log_error(kind: str, message: str = "", **fields) -> None:
    """เขียน error ลง error-YYYY-MM.log แยกต่างหาก"""
    try:
        _ensure_log_dir()
        now_dt = _now_bkk()
        ts = now_dt.strftime("%Y-%m-%d %H:%M:%S")
        flat_fields = [f"{key}={_sanitize(value)}" for key, value in fields.items() if value is not None]
        line = f"[{ts}] {kind}"
        if message:
            line += f" | {_sanitize(message)}"
        if flat_fields:
            line += " | " + " | ".join(flat_fields)
        error_log = get_monthly_error_log_file_for_dt(now_dt)
        with open(error_log, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


class _ErrorLogHandler(logging.Handler):
    """Catch Python ERROR-level logs → เขียนลง error-YYYY-MM.log"""
    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            log_error("PYTHON_ERROR", msg)
        except Exception:
            pass


def setup_python_logging() -> None:
    _ensure_log_dir()
    _check_bot_log_on_startup()      # rotate bot.log ถ้าเป็นเดือนก่อน
    _check_system_log_on_startup()   # rotate system.log ถ้าเป็นเดือนก่อน (ก่อน handler เปิดไฟล์)
    _move_old_logs_on_startup()      # ย้าย monthly เก่าใน logs/ → old_logs/
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    system_path = os.path.abspath(SYSTEM_LOG_FILE)
    already_has_file = False
    already_has_error = False
    for handler in root.handlers:
        if isinstance(handler, logging.FileHandler) and getattr(handler, "baseFilename", "") == system_path:
            already_has_file = True
        if isinstance(handler, _ErrorLogHandler):
            already_has_error = True
    if not already_has_file:
        file_handler = _MonthlyRotatingFileHandler(SYSTEM_LOG_FILE)
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        root.addHandler(file_handler)
    if not already_has_error:
        error_handler = _ErrorLogHandler()
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(logging.Formatter("%(name)s | %(message)s"))
        root.addHandler(error_handler)


def log_event(kind: str, message: str = "", **fields) -> None:
    try:
        _ensure_log_dir()
        now_dt = _now_bkk()
        ts = now_dt.strftime("%Y-%m-%d %H:%M:%S")
        flat_fields = [f"{key}={_sanitize(value)}" for key, value in fields.items() if value is not None]
        line = f"[{ts}] {kind}"
        if message:
            line += f" | {_sanitize(message)}"
        if flat_fields:
            line += " | " + " | ".join(flat_fields)
        _rotate_bot_log_if_needed(now_dt)
        _rotate_bot_log_by_size(now_dt)
        with open(BOT_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def log_block(kind: str, text: str, **fields) -> None:
    log_event(kind, text, **fields)


def _parse_log_line_ts(line: str):
    m = _TS_LINE_RE.match(line)
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None


def cleanup_old_logs(retention_days: int = LOG_RETENTION_DAYS) -> dict:
    """ลบ archived monthly log ที่เก่าเกิน retention_days ออกจาก old_logs/
    (current logs: bot.log / system.log / error-YYYY-MM.log เดือนนี้ ไม่แตะ)
    """
    _ensure_log_dir()
    cutoff = _now_bkk().replace(tzinfo=None) - timedelta(days=retention_days)
    summary: dict = {"trimmed": [], "deleted": [], "skipped": [], "retention_days": retention_days}

    _IS_ARCHIVED = re.compile(r"^(bot|error|system)-\d{4}-\d{2}(-\d{2}-\d{2})?\.log$")

    try:
        entries = os.listdir(OLD_LOG_DIR)
    except FileNotFoundError:
        return summary

    for name in entries:
        if not name.endswith(".log") or not _IS_ARCHIVED.match(name):
            continue
        path = os.path.join(OLD_LOG_DIR, name)
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
        except OSError:
            summary["skipped"].append(name)
            continue

        kept: list[str] = []
        last_ts = None
        for line in lines:
            ts = _parse_log_line_ts(line)
            if ts is not None:
                last_ts = ts
            effective_ts = ts if ts is not None else last_ts
            if effective_ts is None or effective_ts >= cutoff:
                kept.append(line)

        if not kept:
            try:
                os.remove(path)
                summary["deleted"].append(name)
            except OSError:
                summary["skipped"].append(name)
            continue

        if len(kept) == len(lines):
            continue

        removed = len(lines) - len(kept)
        tmp_path = path + ".tmp"
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                f.writelines(kept)
            os.replace(tmp_path, path)
            summary["trimmed"].append((name, removed))
        except OSError:
            try:
                os.remove(tmp_path)
            except OSError:
                pass
            summary["skipped"].append(name)

    return summary
