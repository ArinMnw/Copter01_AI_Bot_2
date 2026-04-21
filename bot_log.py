import logging
import os
from datetime import datetime, timedelta, timezone


TZ_OFFSET = 7
LOG_DIR = "logs"
BOT_LOG_FILE = os.path.join(LOG_DIR, "bot.log")
SYSTEM_LOG_FILE = os.path.join(LOG_DIR, "system.log")


def _now_bkk() -> datetime:
    return datetime.now(timezone.utc) + timedelta(hours=TZ_OFFSET)


def _sanitize(value) -> str:
    if value is None:
        return "-"
    text = str(value)
    return " | ".join(part.strip() for part in text.splitlines() if part.strip()) or "-"


def _ensure_log_dir() -> None:
    os.makedirs(LOG_DIR, exist_ok=True)


def get_monthly_bot_log_file(year: int, month: int) -> str:
    return os.path.join(LOG_DIR, f"bot-{year:04d}-{month:02d}.log")


def get_monthly_bot_log_file_for_dt(dt: datetime) -> str:
    return get_monthly_bot_log_file(dt.year, dt.month)


def setup_python_logging() -> None:
    _ensure_log_dir()
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    system_path = os.path.abspath(SYSTEM_LOG_FILE)
    for handler in root.handlers:
        if isinstance(handler, logging.FileHandler) and getattr(handler, "baseFilename", "") == system_path:
            return
    file_handler = logging.FileHandler(SYSTEM_LOG_FILE, encoding="utf-8")
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root.addHandler(file_handler)


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
