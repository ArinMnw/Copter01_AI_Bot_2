import os
import shutil
import sys

# Reconfigure stdout to use utf-8 if possible
try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

def parse_env(profile_dir):
    env_path = os.path.join(profile_dir, "profile.env")
    data = {}
    if not os.path.exists(env_path):
        return data
    try:
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                data[k.strip()] = v.strip()
    except Exception:
        pass
    return data

def get_dir_size(path):
    try:
        return sum(os.path.getsize(os.path.join(r, f)) for r, d, fs in os.walk(path) for f in fs)
    except Exception:
        return 0

def cleanup_mt5_folder(mt5_path, profile_name, profile_dir):
    if not os.path.exists(mt5_path):
        return 0
        
    bytes_freed = 0
    env_data = parse_env(profile_dir)
    active_login = env_data.get("MT5_LOGIN", "")
    active_server = env_data.get("MT5_SERVER", "")
    
    # Identify which symbols to keep
    # AF (2461) and Main (2459) check/trade BTCUSD, others only trade XAUUSD.
    is_btc_needed = (profile_name in ["demo-iux-2101182461", "demo-iux-2101182459"])
    keep_symbols = ["xauusd"]
    if is_btc_needed:
        keep_symbols.append("btcusd")
        
    print(f"  [Config] Login={active_login}, Server={active_server}, KeepSymbols={keep_symbols}")
    
    # 1. Delete executables that are not needed for running the bot
    files_to_delete = ["MetaEditor64.exe", "metatester64.exe"]
    for file_name in files_to_delete:
        file_path = os.path.join(mt5_path, file_name)
        if os.path.exists(file_path):
            try:
                size = os.path.getsize(file_path)
                os.remove(file_path)
                bytes_freed += size
                print(f"  [Deleted File] {file_name} ({size/1024/1024:.1f} MB)")
            except Exception as e:
                print(f"  [Error deleting] {file_name}: {e}")
                
    # 2. Delete terminal backup files (terminal64.exe.bak*)
    try:
        for entry in os.scandir(mt5_path):
            if entry.is_file() and entry.name.startswith("terminal64.exe.bak"):
                try:
                    size = entry.stat().st_size
                    os.remove(entry.path)
                    bytes_freed += size
                    print(f"  [Deleted File] {entry.name} ({size/1024/1024:.1f} MB)")
                except Exception as e:
                    print(f"  [Error deleting] {entry.name}: {e}")
    except Exception:
        pass

    # 3. Delete Tester folder
    tester_path = os.path.join(mt5_path, "Tester")
    if os.path.exists(tester_path):
        try:
            size = get_dir_size(tester_path)
            shutil.rmtree(tester_path)
            bytes_freed += size
            print(f"  [Deleted Folder] Tester/ ({size/1024/1024:.1f} MB)")
        except Exception as e:
            print(f"  [Error deleting] Tester/: {e}")
            
    # 4. Clean up bases history and ticks
    bases_dir = os.path.join(mt5_path, "bases")
    if os.path.exists(bases_dir):
        try:
            for server in os.listdir(bases_dir):
                server_dir = os.path.join(bases_dir, server)
                if not os.path.isdir(server_dir):
                    continue
                
                server_lower = server.lower()
                
                # Check if it is a mismatched broker server folder
                # For example, if active server is Exness, delete IUXMarkets-Demo folder.
                # If active server is IUX, delete Exness folders.
                # We always keep 'default', 'custom', 'signals' etc.
                is_ignored_name = server_lower in ["default", "custom", "signals"]
                is_active_broker = False
                
                if active_server:
                    active_srv_lower = active_server.lower()
                    # Exness-MT5Trail7 maps to Exness-MT5Trial7 folder, so we check substring match
                    if active_srv_lower.replace("trail", "trial") in server_lower.replace("trail", "trial") or server_lower.replace("trail", "trial") in active_srv_lower.replace("trail", "trial"):
                        is_active_broker = True
                    elif "exness" in active_srv_lower and "exness" in server_lower:
                        is_active_broker = True
                    elif "iux" in active_srv_lower and "iux" in server_lower:
                        is_active_broker = True
                
                if not is_ignored_name and not is_active_broker and active_server:
                    # This is a mismatched broker database (e.g. IUX folder in Exness profile)! Delete it entirely!
                    try:
                        size = get_dir_size(server_dir)
                        shutil.rmtree(server_dir)
                        bytes_freed += size
                        print(f"  [Deleted Mismatched Broker Bases] bases/{server}/ ({size/1024/1024:.1f} MB)")
                        continue
                    except Exception as e:
                        print(f"  [Error deleting broker bases] {server}: {e}")
                
                # If it is 'Default' folder, delete history and trades entirely
                if server_lower == "default":
                    for sub in ["history", "trades", "ticks"]:
                        sub_path = os.path.join(server_dir, sub)
                        if os.path.exists(sub_path):
                            try:
                                size = get_dir_size(sub_path)
                                shutil.rmtree(sub_path)
                                bytes_freed += size
                                print(f"  [Deleted Default Data] bases/Default/{sub}/ ({size/1024/1024:.1f} MB)")
                            except Exception as e:
                                print(f"  [Error deleting default {sub}] : {e}")
                    continue
                
                # Active broker cleanup (history & ticks of unused symbols)
                hist_dir = os.path.join(server_dir, "history")
                if os.path.exists(hist_dir):
                    for sym in os.listdir(hist_dir):
                        sym_lower = sym.lower()
                        if not any(k in sym_lower for k in keep_symbols):
                            sym_path = os.path.join(hist_dir, sym)
                            try:
                                size = get_dir_size(sym_path)
                                shutil.rmtree(sym_path)
                                bytes_freed += size
                                print(f"  [Deleted History] bases/{server}/history/{sym} ({size/1024/1024:.1f} MB)")
                            except Exception as e:
                                print(f"  [Error deleting history] {sym}: {e}")
                                
                ticks_dir = os.path.join(server_dir, "ticks")
                if os.path.exists(ticks_dir):
                    for sym in os.listdir(ticks_dir):
                        sym_lower = sym.lower()
                        if not any(k in sym_lower for k in keep_symbols):
                            sym_path = os.path.join(ticks_dir, sym)
                            try:
                                size = get_dir_size(sym_path)
                                shutil.rmtree(sym_path)
                                bytes_freed += size
                                print(f"  [Deleted Ticks] bases/{server}/ticks/{sym} ({size/1024/1024:.1f} MB)")
                            except Exception as e:
                                print(f"  [Error deleting ticks] {sym}: {e}")
                                
                # Trades cleanup of other accounts
                # Delete any account subdirectory inside trades/ that is NOT the active_login
                trades_dir = os.path.join(server_dir, "trades")
                if os.path.exists(trades_dir):
                    for acc in os.listdir(trades_dir):
                        if active_login and acc != active_login:
                            acc_path = os.path.join(trades_dir, acc)
                            if os.path.isdir(acc_path):
                                try:
                                    size = get_dir_size(acc_path)
                                    shutil.rmtree(acc_path)
                                    bytes_freed += size
                                    print(f"  [Deleted Other Account Trades] bases/{server}/trades/{acc} ({size/1024/1024:.1f} MB)")
                                except Exception as e:
                                    print(f"  [Error deleting other account trades] {acc}: {e}")
        except Exception:
            pass
            
    return bytes_freed

def main():
    run_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(run_dir)
    
    profile_roots = [
        os.path.join(project_root, "profiles", "demo"),
        os.path.join(project_root, "profiles", "real")
    ]
    total_freed = 0
    
    print("Starting MT5 profiles disk cleanup...")
    for root in profile_roots:
        if not os.path.exists(root):
            continue
        for p in os.listdir(root):
            p_path = os.path.join(root, p)
            if os.path.isdir(p_path):
                mt5_path = os.path.join(p_path, "mt5")
                if os.path.exists(mt5_path):
                    print(f"\\n==========================================")
                    print(f"Profile: {p}")
                    print(f"==========================================")
                    freed = cleanup_mt5_folder(mt5_path, p, p_path)
                    total_freed += freed
                    print(f"-> Freed: {freed/1024/1024:.1f} MB")
                    
    print(f"\\nCleanup complete! Total disk space freed: {total_freed/1024/1024:.1f} MB ({total_freed/1024/1024/1024:.2f} GB)")

if __name__ == "__main__":
    main()
