import codecs
import re

with codecs.open('config.py', 'r', 'utf-8') as f:
    content = f.read()

# 1. Add S20.14 configs after S20.13 configs
s20_13_block = 'S20_13_TARGET_TF_SELL = "D1"\n'
s20_14_block = """
S20_14_ENABLED        = False
S20_14_TF_ENABLED     = {"M1": True, "M5": True, "M15": True, "M30": True, "H1": True, "H4": True, "H12": False, "D1": False}
S20_14_COMPOUNDING_ENABLED = False
S20_14_RISK_PCT       = 2.0
S20_14_MAX_LOT        = 50.0
S20_14_ACTIVE_MODE    = 2.0
"""
if "S20_14_ENABLED" not in content:
    content = content.replace(s20_13_block, s20_13_block + s20_14_block)

# 2. Add to active_strategies
act_strat_13 = '    20.13: True,  # ท่าที่ 20.13: Quant Fuel (AllIn4s)\n'
act_strat_14 = '    20.14: False, # ท่าที่ 20.14: Full Trading (Price Action)\n'
if act_strat_14 not in content:
    content = content.replace(act_strat_13, act_strat_13 + act_strat_14)

# 3. Add to STRATEGY_NAMES
name_13 = '    20.13: "S20.13: Quant Fuel",\n'
name_14 = '    20.14: "S20.14: Full Trading",\n'
if name_14 not in content:
    content = content.replace(name_13, name_13 + name_14)

# 4. Add to skip sets
skip_vars = [
    "PENDING_LIMIT_GUARD_SKIP_SIDS", "NEWS_FILTER_SKIP_SIDS", "SL_GUARD_SKIP_SIDS", 
    "SL_GUARD_GROUP_SKIP_SIDS", "OPPOSITE_ORDER_SKIP_SIDS", "PDFIBOPLUS_SKIP_SIDS", 
    "SHARED_TP_SKIP_SIDS", "RSI_RECHECK_SKIP_SIDS", "FILL_TREND_RECHECK_SKIP_SIDS", 
    "PENDING_TREND_RECHECK_SKIP_SIDS", "ENTRY_CANDLE_QUALITY_SKIP_SIDS", "TRAIL_SL_SKIP_SIDS", 
    "SWEEP_FILTER_SKIP_SIDS", "TREND_FILTER_SKIP_SIDS"
]
for var in skip_vars:
    # Match the set line and add 20.14 if not there
    pattern = r"(" + var + r"\s*=\s*\{[^}]*)(20\.13\b)([^}]*\})"
    def repl(m):
        if "20.14" not in m.group(0):
            return m.group(1) + m.group(2) + ", 20.14" + m.group(3)
        return m.group(0)
    content = re.sub(pattern, repl, content)

# 5. save_runtime_state
save_pattern = r'("S20_12_SESSION_FILTER": S20_12_SESSION_FILTER,)'
save_repl = r'\1\n        "S20_14_ENABLED": S20_14_ENABLED,\n        "S20_14_TF_ENABLED": S20_14_TF_ENABLED,\n        "S20_14_COMPOUNDING_ENABLED": S20_14_COMPOUNDING_ENABLED,\n        "S20_14_RISK_PCT": S20_14_RISK_PCT,\n        "S20_14_MAX_LOT": S20_14_MAX_LOT,'
try:
    if "S20_14_ENABLED" not in content.split("def save_runtime_state():")[1][:2000]:
        content = re.sub(save_pattern, save_repl, content)
except Exception:
    pass

# 6. restore_runtime_state
restore_pattern = r'(global S20_12_ENABLED, S20_12_TF_ENABLED, S20_12_COMPOUNDING_ENABLED, S20_12_RISK_PCT, S20_12_MAX_LOT, S20_12_SESSION_FILTER)'
restore_repl = r'\1, S20_14_ENABLED, S20_14_TF_ENABLED, S20_14_COMPOUNDING_ENABLED, S20_14_RISK_PCT, S20_14_MAX_LOT'
content = re.sub(restore_pattern, restore_repl, content)

# 6b. actual assignments in restore
restore_assign = r'(S20_12_SESSION_FILTER = data\.get\("S20_12_SESSION_FILTER", S20_12_SESSION_FILTER\))'
restore_assign_repl = r'\1\n        S20_14_ENABLED = data.get("S20_14_ENABLED", S20_14_ENABLED)\n        S20_14_TF_ENABLED = data.get("S20_14_TF_ENABLED", S20_14_TF_ENABLED)\n        S20_14_COMPOUNDING_ENABLED = data.get("S20_14_COMPOUNDING_ENABLED", S20_14_COMPOUNDING_ENABLED)\n        S20_14_RISK_PCT = data.get("S20_14_RISK_PCT", S20_14_RISK_PCT)\n        S20_14_MAX_LOT = data.get("S20_14_MAX_LOT", S20_14_MAX_LOT)'
try:
    if "S20_14_ENABLED = data.get" not in content.split("def restore_runtime_state():")[1][:2000]:
        content = re.sub(restore_assign, restore_assign_repl, content)
except Exception:
    pass

with codecs.open('config.py', 'w', 'utf-8') as f:
    f.write(content)

print("config.py patched successfully.")
