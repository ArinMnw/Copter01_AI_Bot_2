"""
notify_start.py — ส่ง + pin ข้อความ Telegram เมื่อ run_supervised.bat เริ่มทำงาน

รันจาก bat ก่อน PS1 ขึ้น ดังนั้นใช้ requests ยิง HTTP API ตรงแทน async bot
"""

import os
import sys
import requests
from datetime import datetime

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

_root = os.path.dirname(os.path.abspath(__file__))


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


_load_profile_env()

TOKEN   = os.getenv("TELEGRAM_TOKEN", "8731980788:AAHJ1_L3F44ZZbxR3yrPQhtZQzxgQE0d5s0")
CHAT_ID = os.getenv("MY_USER_ID",     "8666020453")
PROFILE = os.getenv("BOT_PROFILE",    "")
SERVER  = os.getenv("MT5_SERVER",     "")
LOGIN   = os.getenv("MT5_LOGIN",      "")
NOW     = datetime.now().strftime("%d/%m/%Y %H:%M")

profile_line = f"👤 Profile: `{PROFILE}`\n" if PROFILE else ""
account_line = f"🏦 {SERVER} : {LOGIN}\n" if SERVER or LOGIN else ""
msg = (
    f"🚀 *Bot เริ่มทำงาน*\n"
    f"━━━━━━━━━━━━━━━━━\n"
    f"{profile_line}"
    f"{account_line}"
    f"🕐 เวลา: `{NOW}`"
)

try:
    resp = requests.post(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"},
        timeout=10,
    )
    if resp.ok:
        msg_id = resp.json()["result"]["message_id"]
        requests.post(
            f"https://api.telegram.org/bot{TOKEN}/pinChatMessage",
            json={"chat_id": CHAT_ID, "message_id": msg_id, "disable_notification": True},
            timeout=10,
        )
        print(f"  ✅ Telegram: แจ้งเริ่มบอทแล้ว (msg_id={msg_id})")
    else:
        print(f"  ⚠️  Telegram ตอบ: {resp.status_code} {resp.text[:120]}")
except Exception as e:
    print(f"  ⚠️  ส่ง Telegram ไม่ได้: {e}")
