"""
notify_start.py — ส่ง + pin ข้อความ Telegram เมื่อ run_supervised.bat เริ่มทำงาน

รันจาก bat ก่อน PS1 ขึ้น ดังนั้นใช้ requests ยิง HTTP API ตรงแทน async bot
"""

import os
import sys
from datetime import datetime, timedelta

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

_root = os.path.dirname(os.path.abspath(__file__))

def log_msg(text: str):
    print(text)
    # Write to global logs/notify_start.log
    global_log = os.path.join(_root, "logs", "notify_start.log")
    try:
        os.makedirs(os.path.dirname(global_log), exist_ok=True)
        with open(global_log, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {text}\n")
    except Exception:
        pass
        
    # Write to profile logs/notify_start.log if profile is set
    profile = os.getenv("BOT_PROFILE", "")
    if profile:
        profile_log = os.path.join(_root, "profiles", "demo", profile, "logs", "notify_start.log")
        try:
            os.makedirs(os.path.dirname(profile_log), exist_ok=True)
            with open(profile_log, "a", encoding="utf-8") as f:
                f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {text}\n")
        except Exception:
            pass

# Robust import check
try:
    import requests
except ImportError as e:
    log_msg(f"❌ ImportError: {e}. Please run: pip install requests")
    sys.exit(0) # Exit with 0 to allow bat script to continue starting the bot even if notify fails

def _load_profile_env() -> None:
    """อ่าน profile.env เพื่อดึง TELEGRAM_TOKEN / MY_USER_ID ก่อน PS1 โหลด env"""
    profile = os.getenv("BOT_PROFILE", "")
    if not profile:
        return
    candidates = [
        os.path.join(_root, "profiles", profile, "profile.env"),
        os.path.join(_root, "profiles", "demo", profile, "profile.env"),
        os.path.join(_root, "profiles", "real", profile, "profile.env"),
    ]
    for path in candidates:
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
            break

try:
    _load_profile_env()

    TOKEN   = os.getenv("TELEGRAM_TOKEN", "8731980788:AAHJ1_L3F44ZZbxR3yrPQhtZQzxgQE0d5s0")
    CHAT_ID = os.getenv("MY_USER_ID",     "8666020453")
    PROFILE = os.getenv("BOT_PROFILE",    "")
    SERVER  = os.getenv("MT5_SERVER",     "")
    LOGIN   = os.getenv("MT5_LOGIN",      "")
    NOW     = datetime.now().strftime("%d/%m/%Y %H:%M")
    S20_12_START = os.getenv("S20_12_START_NOT_BEFORE", "").strip()

    def _s20_12_custom_line() -> str:
        if PROFILE != "demo-iux-2101182459" or not S20_12_START:
            return ""
        try:
            start_dt = datetime.strptime(S20_12_START, "%d-%m-%Y %H:%M")
            first_cycle = start_dt + timedelta(seconds=1)
            start_label = start_dt.strftime("%d/%m/%Y %H:%M")
            cycle_label = first_cycle.strftime("%H:%M:%S")
        except ValueError:
            start_label = S20_12_START
            cycle_label = "-"
        return (
            "🎯 Custom: `459 S20.12 standalone`\n"
            f"⏳ Start gate: `{start_label}` (+2m)\n"
            f"🔁 First backtest cycle: `{cycle_label}`\n"
        )

    profile_line = f"👤 Profile: `{PROFILE}`\n" if PROFILE else ""
    account_line = f"🏦 {SERVER} : {LOGIN}\n" if SERVER or LOGIN else ""
    custom_line = _s20_12_custom_line()
    msg = (
        f"🚀 *Bot เริ่มทำงาน*\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"{profile_line}"
        f"{account_line}"
        f"{custom_line}"
        f"🕐 เวลา: `{NOW}`"
    )

    resp = requests.post(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"},
        timeout=10,
    )
    if resp.ok:
        msg_id = resp.json()["result"]["message_id"]
        r_pin = requests.post(
            f"https://api.telegram.org/bot{TOKEN}/pinChatMessage",
            json={"chat_id": CHAT_ID, "message_id": msg_id, "disable_notification": True},
            timeout=10,
        )
        if r_pin.ok:
            log_msg(f"  ✅ Telegram: แจ้งเริ่มบอทสำเร็จและทำการ Pin แล้ว (msg_id={msg_id})")
        else:
            log_msg(f"  ⚠️  Telegram: ส่งสำเร็จแต่ Pin ล้มเหลว: {r_pin.status_code} {r_pin.text}")
    else:
        log_msg(f"  ⚠️  Telegram: ส่งเริ่มบอทล้มเหลว: {resp.status_code} {resp.text[:150]}")

except Exception as e:
    log_msg(f"  ⚠️  ส่ง Telegram ไม่ได้: {e}")
