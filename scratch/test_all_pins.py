import os
import requests
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

root_dir = "d:/Project/Copter01_AI_Bot_2"
demo_dir = os.path.join(root_dir, "profiles", "demo")
real_dir = os.path.join(root_dir, "profiles", "real")

def parse_env_file(env_path):
    data = {}
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                data[k.strip()] = v.strip().strip('"').strip("'")
    return data

profiles = []
# 1. Main profile (root .env if exists)
root_env = parse_env_file(os.path.join(root_dir, ".env"))
if root_env:
    profiles.append(("Main (Root .env)", root_env))

# 2. Demo profiles
for name in sorted(os.listdir(demo_dir)):
    full_path = os.path.join(demo_dir, name)
    if os.path.isdir(full_path):
        env = parse_env_file(os.path.join(full_path, "profile.env"))
        if env:
            profiles.append((f"Demo: {name}", env))

# 3. Real profiles
for name in sorted(os.listdir(real_dir)):
    full_path = os.path.join(real_dir, name)
    if os.path.isdir(full_path):
        env = parse_env_file(os.path.join(full_path, "profile.env"))
        if env:
            profiles.append((f"Real: {name}", env))

print(f"Testing Telegram Send & Pin for {len(profiles)} profiles...\n")

for label, env in profiles:
    token = env.get("TELEGRAM_TOKEN")
    chat_id = env.get("MY_USER_ID")
    
    if not token or not chat_id:
        print(f"❌ {label}: Missing token or chat_id in env.")
        continue
        
    print(f"--- Testing {label} ---")
    print(f"  Token: {token[:15]}... | Chat ID: {chat_id}")
    
    # 1. Send Message
    msg = f"🔔 Test start notification for {label}"
    send_url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        r_send = requests.post(send_url, json={"chat_id": chat_id, "text": msg}, timeout=8)
        if not r_send.ok:
            print(f"  ❌ Send Message FAILED: {r_send.status_code} {r_send.text}")
            continue
        
        msg_id = r_send.json()["result"]["message_id"]
        print(f"  ✅ Send Message OK: msg_id={msg_id}")
        
        # 2. Pin Message
        pin_url = f"https://api.telegram.org/bot{token}/pinChatMessage"
        r_pin = requests.post(pin_url, json={"chat_id": chat_id, "message_id": msg_id, "disable_notification": True}, timeout=8)
        if r_pin.ok:
            print(f"  ✅ Pin Message OK")
        else:
            print(f"  ❌ Pin Message FAILED: {r_pin.status_code} {r_pin.text}")
            
    except Exception as e:
        print(f"  ❌ Request error: {e}")
    print()
