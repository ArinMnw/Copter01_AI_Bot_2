import re

def patch_scanner():
    with open("scanner.py", "r", encoding="utf-8") as f:
        content = f.read()
        
    # Add import
    if "from mt5_utils import get_dynamic_volume" not in content:
        content = content.replace(
            "from mt5_utils import connect_mt5",
            "from mt5_utils import connect_mt5, get_dynamic_volume"
        )
        
    content = content.replace(
        'final_volume = round(get_volume() * result.get("quant_lot_multiplier", 1.0), 2)',
        'final_volume = round(get_dynamic_volume(tf_name, signal, get_volume()) * result.get("quant_lot_multiplier", 1.0), 2)'
    )
    
    with open("scanner.py", "w", encoding="utf-8") as f:
        f.write(content)
        
    print("Patched quant_lot_multiplier lines.")

if __name__ == "__main__":
    patch_scanner()
