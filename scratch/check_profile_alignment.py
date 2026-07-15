import os
import re

root_dir = "d:/Project/Copter01_AI_Bot_2"
demo_dir = os.path.join(root_dir, "profiles", "demo")

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

profiles = sorted([p for p in os.listdir(demo_dir) if os.path.isdir(os.path.join(demo_dir, p))])

print(f"{'Profile Name':<30} | {'Login':<12} | {'Server':<20} | {'MT5 Path':<40} | {'Portable':<8}")
print("-" * 120)
for p in profiles:
    env_path = os.path.join(demo_dir, p, "profile.env")
    env = parse_env_file(env_path)
    login = env.get("MT5_LOGIN", "N/A")
    server = env.get("MT5_SERVER", "N/A")
    rel_path = env.get("MT5_PATH", "mt5\\terminal64.exe")
    portable = env.get("MT5_PORTABLE", "true")
    
    # Check if the local mt5 path exists
    abs_path = os.path.join(demo_dir, p, rel_path)
    exists = "OK" if os.path.exists(abs_path) else "MISSING"
    
    print(f"{p:<30} | {login:<12} | {server:<20} | {rel_path:<30} ({exists}) | {portable:<8}")
