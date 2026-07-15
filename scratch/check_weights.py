import os
import json

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

print(f"{'Profile Name':<30} | {'Active Portfolio(s)':<30} | {'Weight Enabled':<15} | {'Weight Scale':<12}")
print("-" * 95)

for p in profiles:
    env_path = os.path.join(demo_dir, p, "profile.env")
    env = parse_env_file(env_path)
    
    active_pf_str = env.get("DEMO_PORTFOLIO_ACTIVE", "NONE")
    if active_pf_str == "NONE" or not active_pf_str:
        continue
        
    pfs = [x.strip() for x in active_pf_str.split(",") if x.strip()]
    
    # Load bot_state.json if it exists
    state_path = os.path.join(demo_dir, p, "bot_state.json")
    state_weights = {}
    state_scales = {}
    if os.path.exists(state_path):
        try:
            with open(state_path, "r", encoding="utf-8") as f:
                state_data = json.load(f)
                state_weights = state_data.get("demo_portfolio_weight_enabled", {})
                state_scales = state_data.get("demo_portfolio_weight_scale", {})
        except Exception:
            pass
            
    for pf in pfs:
        # Resolve weight_enabled (env variable has highest precedence, then bot_state.json, then False)
        env_weight_key = f"DEMO_PORTFOLIO_WEIGHT_ENABLED_{pf}"
        env_scale_key = f"DEMO_PORTFOLIO_WEIGHT_SCALE_{pf}"
        
        weight_enabled = False
        if env_weight_key in env:
            weight_enabled = env[env_weight_key].lower() == "true"
        elif pf in state_weights:
            weight_enabled = state_weights[pf]
            
        weight_scale = 1.0
        if env_scale_key in env:
            try:
                weight_scale = float(env[env_scale_key])
            except ValueError:
                pass
        elif pf in state_scales:
            try:
                weight_scale = float(state_scales[pf])
            except ValueError:
                pass
                
        status_str = "ON" if weight_enabled else "OFF"
        print(f"{p:<30} | {pf:<30} | {status_str:<15} | {weight_scale:<12}")
