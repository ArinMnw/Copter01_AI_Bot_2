"""
get_profile_title.py — คำนวณ Window Title สำหรับ CMD / Powershell
โดยอ่านค่าจาก profile.env และ bot_state.json แบบไดนามิก (ไม่ Hardcode)
"""

import os
import sys
import json

def get_profile_title(profile_name: str) -> str:
    if not profile_name:
        return "Copter Gold Bot (Supervised)"
        
    root = os.path.dirname(os.path.abspath(__file__))
    
    # ค้นหาไดเรกทอรีของโปรไฟล์
    candidates = [
        os.path.join(root, "profiles", profile_name),
        os.path.join(root, "profiles", "demo", profile_name),
        os.path.join(root, "profiles", "real", profile_name),
        profile_name,
    ]
    
    profile_dir = None
    for c in candidates:
        if os.path.isdir(c):
            profile_dir = c
            break
            
    if not profile_dir:
        return f"Copter Gold Bot ({profile_name})"
        
    env_path = os.path.join(profile_dir, "profile.env")
    state_path = os.path.join(profile_dir, "bot_state.json")
    
    env = {}
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip().strip('"').strip("'")
                    
    prof_folder = os.path.basename(os.path.abspath(profile_dir))
    parts = prof_folder.split("-")
    
    mode = parts[0].capitalize() if len(parts) > 0 else "Demo"
    broker = parts[1].upper() if len(parts) > 1 else "IUX"
    login = env.get("MT5_LOGIN", parts[2] if len(parts) > 2 else "")
    
    dp_active = env.get("DEMO_PORTFOLIO_ACTIVE", "")
    if not dp_active or dp_active.upper() in ("NONE", "NULL"):
        if os.path.exists(state_path):
            try:
                with open(state_path, "r", encoding="utf-8") as f:
                    state = json.load(f)
                    act_dp = [k for k, v in state.get("demo_portfolio_active", {}).items() if v]
                    if act_dp:
                        dp_active = ",".join(act_dp)
                    else:
                        act_s = [k for k, v in state.get("active_strategies", {}).items() if v]
                        if len(act_s) > 1:
                            dp_active = "MULTI"
                        elif len(act_s) == 1:
                            dp_active = f"S{act_s[0]}"
            except Exception:
                pass
                
    if dp_active == "LTS_AVENGERS_HIGH_RISK":
        strat_tag = "LTS_AHR"
    elif dp_active == "LTS_AVENGERS_ULTRA_SAFE":
        strat_tag = "LTS_AUS"
    elif "," in dp_active and all(x.startswith("AF") for x in dp_active.split(",")):
        strat_tag = "AF"
    elif dp_active and dp_active.upper() not in ("NONE", "NULL"):
        strat_tag = dp_active
    else:
        strat_tag = ""
        
    tag_str = f"<{strat_tag}> " if strat_tag else ""
    return f"{tag_str}{login} {broker} {mode} Copter Gold Bot (Supervised)"

if __name__ == "__main__":
    prof = sys.argv[1] if len(sys.argv) > 1 else os.getenv("BOT_PROFILE", "")
    print(get_profile_title(prof))
