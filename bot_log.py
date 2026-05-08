import logging
import MetaTrader5 as mt5
import os
import re
from datetime import datetime, timedelta, timezone


TZ_OFFSET = 7
LOG_DIR = "logs"
BOT_LOG_FILE = os.path.join(LOG_DIR, "bot.log")
SYSTEM_LOG_DIR = os.path.join(LOG_DIR, "system")
SYSTEM_LOG_FILE = os.path.join(SYSTEM_LOG_DIR, "system.log")
DEBUG_LOG_DIR = os.path.join(LOG_DIR, "debug")
LOG_RETENTION_DAYS = 7

_TS_LINE_RE = re.compile(r"^\[?(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})")
_MONTHLY_LOG_RE = re.compile(r"^bot-\d{4}-\d{2}\.log$")
_ERROR_MONTHLY_LOG_RE = re.compile(r"^error-\d{4}-\d{2}\.log$")


def _now_bkk() -> datetime:
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
                return dt
    except Exception:
        pass
    server_tz = getattr(locals().get("_config", None), "MT5_SERVER_TZ", 1) if "_config" in locals() else 1
    return datetime.now(timezone.utc) + timedelta(hours=TZ_OFFSET - server_tz)


def _sanitize(value) -> str:
    if value is None:
        return "-"
    text = str(value)
    return " | ".join(part.strip() for part in text.splitlines() if part.strip()) or "-"


def _ensure_log_dir() -> None:
    os.makedirs(LOG_DIR, exist_ok=True)
    os.makedirs(SYSTEM_LOG_DIR, exist_ok=True)
    os.makedirs(DEBUG_LOG_DIR, exist_ok=True)


def get_monthly_bot_log_file(year: int, month: int) -> str:
    return os.path.join(LOG_DIR, f"bot-{year:04d}-{month:02d}.log")


def get_monthly_bot_log_file_for_dt(dt: datetime) -> str:
    return get_monthly_bot_log_file(dt.year, dt.month)


def get_monthly_error_log_file_for_dt(dt: datetime) -> str:
    return os.path.join(LOG_DIR, f"error-{dt.year:04d}-{dt.month:02d}.log")


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
        file_handler = logging.FileHandler(SYSTEM_LOG_FILE, encoding="utf-8")
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
        monthly_bot_log = get_monthly_bot_log_file_for_dt(now_dt)
        for path in (BOT_LOG_FILE, monthly_bot_log):
            with open(path, "a", encoding="utf-8") as f:
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
    """ลบบรรทัด log ที่เก่าเกิน retention_days ออกจากไฟล์ใน LOG_DIR
    ถ้าเป็น monthly log (bot-YYYY-MM.log) และไม่มีบรรทัดเหลือ จะลบทั้งไฟล์
    """
    _ensure_log_dir()
    cutoff = _now_bkk().replace(tzinfo=None) - timedelta(days=retention_days)
    summary: dict = {"trimmed": [], "deleted": [], "skipped": [], "retention_days": retention_days}
    try:
        entries = os.listdir(LOG_DIR)
    except FileNotFoundError:
        return summary

    for name in entries:
        if not name.endswith(".log"):
            continue
        path = os.path.join(LOG_DIR, name)
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

        if (_MONTHLY_LOG_RE.match(name) or _ERROR_MONTHLY_LOG_RE.match(name)) and not kept:
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
