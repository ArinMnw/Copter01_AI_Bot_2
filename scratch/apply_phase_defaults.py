import os
import json

root_dir = "d:/Project/Copter01_AI_Bot_2"
demo_dir = os.path.join(root_dir, "profiles", "demo")

profiles = sorted([p for p in os.listdir(demo_dir) if os.path.isdir(os.path.join(demo_dir, p))])

for p in profiles:
    state_path = os.path.join(demo_dir, p, "bot_state.json")
    if not os.path.exists(state_path):
        continue
        
    try:
        with open(state_path, "r", encoding="utf-8") as f:
            state_data = json.load(f)
            
        changed = False
        
        # Keys to update
        keys_to_update = ["dynamic_lot_enabled", "smart_cutloss_enabled", "momentum_stall_exit_enabled"]
        for key in keys_to_update:
            if key not in state_data:
                state_data[key] = {}
                
            dict_val = state_data[key]
            
            # Update values for all standard portfolios
            all_portfolios = [
                "P13", "P16", "AF22", "AF34", "AF47", "LTS44", "LTS890", "LTS999",
                "LTS_AVENGERS_BASE", "LTS_AVENGERS_P34", "LTS_AVENGERS_HIGH_RISK",
                "LTS_AVENGERS_ULTRA_SAFE", "LTS_AVENGERS_HIGH_FREQ", "P18",
                "S101", "S102", "S105", "S106", "S111"
            ]
            
            for pf in all_portfolios:
                if key == "dynamic_lot_enabled":
                    default_val = pf.startswith("LTS")
                else: # smart_cutloss_enabled and momentum_stall_exit_enabled
                    default_val = pf.startswith("LTS") or pf in ("P15", "P16")
                    
                if dict_val.get(pf) != default_val:
                    dict_val[pf] = default_val
                    changed = True
                    
        if changed:
            with open(state_path, "w", encoding="utf-8") as f:
                json.dump(state_data, f, indent=2, ensure_ascii=False)
            print(f"Updated defaults in {p}/bot_state.json")
        else:
            print(f"No changes needed in {p}/bot_state.json")
            
    except Exception as e:
        print(f"Error processing {p}: {e}")
