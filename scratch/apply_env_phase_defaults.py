import os

root_dir = "d:/Project/Copter01_AI_Bot_2"
demo_dir = os.path.join(root_dir, "profiles", "demo")

profiles = sorted([p for p in os.listdir(demo_dir) if os.path.isdir(os.path.join(demo_dir, p))])

for p in profiles:
    env_path = os.path.join(demo_dir, p, "profile.env")
    if not os.path.exists(env_path):
        continue
        
    try:
        with open(env_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
            
        # Parse active portfolios
        active_pf = ""
        for line in lines:
            if line.strip().startswith("DEMO_PORTFOLIO_ACTIVE="):
                active_pf = line.split("=", 1)[1].strip()
                break
                
        if not active_pf or active_pf == "NONE":
            continue
            
        pfs = [x.strip() for x in active_pf.split(",") if x.strip()]
        
        changed = False
        new_lines = []
        for line in lines:
            updated_line = line
            for pf in pfs:
                if pf.startswith("LTS"):
                    # Change LTS portfolio settings to true
                    if line.strip().startswith(f"DYNAMIC_LOT_ENABLED_{pf}="):
                        updated_line = f"DYNAMIC_LOT_ENABLED_{pf}=true\n"
                        changed = True
                    elif line.strip().startswith(f"SMART_CUTLOSS_ENABLED_{pf}="):
                        updated_line = f"SMART_CUTLOSS_ENABLED_{pf}=true\n"
                        changed = True
                    elif line.strip().startswith(f"MOMENTUM_STALL_EXIT_ENABLED_{pf}="):
                        updated_line = f"MOMENTUM_STALL_EXIT_ENABLED_{pf}=true\n"
                        changed = True
            new_lines.append(updated_line)
            
        if changed:
            with open(env_path, "w", encoding="utf-8") as f:
                f.writelines(new_lines)
            print(f"Updated profile.env for {p} to enable Phase 3 & 4")
        else:
            print(f"No env changes needed for {p}")
            
    except Exception as e:
        print(f"Error processing {p}: {e}")
