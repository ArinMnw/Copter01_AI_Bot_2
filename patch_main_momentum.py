import re

def patch_main():
    with open("main.py", "r", encoding="utf-8") as f:
        content = f.read()
        
    # 1. Update import in main.py
    if "check_momentum_stall_exit" not in content:
        content = content.replace(
            "check_smart_cutloss, check_atr_trailing,",
            "check_smart_cutloss, check_atr_trailing, check_momentum_stall_exit,"
        )
        
    # 2. Add the call right after check_smart_cutloss
    if "await check_momentum_stall_exit(app)" not in content:
        content = content.replace(
            'await check_smart_cutloss(app); _lap("smart_cutloss")',
            'await check_smart_cutloss(app); _lap("smart_cutloss")\n            await check_momentum_stall_exit(app); _lap("momentum_stall")'
        )
        
    with open("main.py", "w", encoding="utf-8") as f:
        f.write(content)

if __name__ == "__main__":
    patch_main()
