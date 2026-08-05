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
            
        active_pf = ""
        insert_idx = -1
        for i, line in enumerate(lines):
            if line.strip().startswith("DEMO_PORTFOLIO_ACTIVE="):
                active_pf = line.split("=", 1)[1].strip()
                insert_idx = i
                break
                
        if not active_pf or active_pf == "NONE":
            continue
            
        pfs = [x.strip() for x in active_pf.split(",") if x.strip()]
        
        # Keys to ensure are true
        keys_to_set = []
        for pf in pfs:
            keys_to_set.append(f"DYNAMIC_LOT_ENABLED_{pf}")
            keys_to_set.append(f"SMART_CUTLOSS_ENABLED_{pf}")
            keys_to_set.append(f"MOMENTUM_STALL_EXIT_ENABLED_{pf}")
            keys_to_set.append(f"DEMO_PORTFOLIO_CB_ENABLED_{pf}")
            
        new_lines = []
        added = set()
        
        # Update existing lines
        for line in lines:
            updated = False
            for k in keys_to_set:
                if line.strip().startswith(f"{k}="):
                    new_lines.append(f"{k}=true\n")
                    added.add(k)
                    updated = True
                    break
            if not updated:
                new_lines.append(line)
                
        # Inject missing lines right after DEMO_PORTFOLIO_ACTIVE if not found
        missing = [k for k in keys_to_set if k not in added]
        if missing and insert_idx != -1:
            inject_lines = [f"{k}=true\n" for k in missing]
            new_lines = new_lines[:insert_idx+1] + inject_lines + new_lines[insert_idx+1:]
            
        with open(env_path, "w", encoding="utf-8") as f:
            f.writelines(new_lines)
            
        print(f"Enabled Phase 3 & 4 for {p} ({active_pf})")
            
    except Exception as e:
        print(f"Error processing {p}: {e}")
