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

print(f"{'Profile Name':<25} | {'Portfolio':<25} | {'Phase 3 (DynLot)':<18} | {'Phase 4 (CutLoss)':<18}")
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
    state_dyn = {}
    state_cut = {}
    if os.path.exists(state_path):
        try:
            with open(state_path, "r", encoding="utf-8") as f:
                state_data = json.load(f)
                state_dyn = state_data.get("dynamic_lot_enabled", {})
                state_cut = state_data.get("smart_cutloss_enabled", {})
        except Exception:
            pass
            
    for pf in pfs:
        # Phase 3: DYNAMIC_LOT_ENABLED
        env_dyn_key = f"DYNAMIC_LOT_ENABLED_{pf}"
        dyn_enabled = False
        if env_dyn_key in env:
            dyn_enabled = env[env_dyn_key].lower() == "true"
        elif pf in state_dyn:
            dyn_enabled = state_dyn[pf]
        else:
            # Default from config.py is False
            dyn_enabled = False
            
        # Phase 4: SMART_CUTLOSS_ENABLED
        env_cut_key = f"SMART_CUTLOSS_ENABLED_{pf}"
        cut_enabled = False
        if env_cut_key in env:
            cut_enabled = env[env_cut_key].lower() == "true"
        elif pf in state_cut:
            cut_enabled = state_cut[pf]
        else:
            # Default is True for P15/P16, False otherwise
            cut_enabled = pf in ("P15", "P16")
            
        dyn_str = "ON" if dyn_enabled else "OFF"
        cut_str = "ON" if cut_enabled else "OFF"
        
        print(f"{p:<25} | {pf:<25} | {dyn_str:<18} | {cut_str:<18}")
