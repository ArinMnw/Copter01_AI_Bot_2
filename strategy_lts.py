import os
import re
from strategy_af import _cfg_for_ladder_leg, _filters_for_ladder_leg

LTS_PORTFOLIO_LEGS = {}
LTS_STRATEGIES = {}

def _load_lts_weights(filepath, prefix):
    if not os.path.exists(filepath):
        return
        
    legs = []
    with open(filepath, "r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            line = line.strip()
            if not line:
                continue
            parts = line.split(":")
            if len(parts) != 2:
                continue
                
            label = parts[0].strip()
            weight = float(parts[1].strip())
            
            # Label format: INVERSE_S84c4369_RD2.7-3.4_H12
            m = re.match(r"^(DIRECT|INVERSE)_S(\d+)c(\d+)_RD([a-zA-Z0-9.\-]+)_H(\d+)", label)
            if not m:
                continue
                
            n = i + 1
            key = f"{prefix}_{n}"
            
            # Extract for _cfg_for_ladder_leg compatibility
            leg_name = f"c{m.group(3)}" if m.group(2) == "84" else f"S86RUNc{m.group(3)}"
            family, cfg, detect_fn, cfg_idx = _cfg_for_ladder_leg(leg_name)
            
            mode = "inverse" if m.group(1) == "INVERSE" else "direct"
            
            rd_band = m.group(4)
            rd_min = rd_max = None
            if rd_band != "all":
                if "-" in rd_band:
                    rd_min, rd_max = map(float, rd_band.split("-"))
                elif "_" in rd_band:
                    rd_min, rd_max = map(float, rd_band.split("_"))
            
            hour = int(m.group(5))
            
            LTS_STRATEGIES[key] = {
                "key": key,
                "component_no": n,
                "label": f"{key} {label}",
                "short": key,
                "portfolio_leg": True,
                "formula": f"{mode.upper()} {label} x{weight}",
                "leg_name": leg_name,
                "detect_fn": detect_fn,
                "cfg": cfg,
                "mode": mode,
                "rd_min": rd_min,
                "rd_max": rd_max,
                "hour": hour,
                "family": family,
                "cfg_idx": cfg_idx,
                "weight": weight,
            }
            legs.append(key)
            
    LTS_PORTFOLIO_LEGS[prefix] = legs

# Load dynamically
_dir = os.path.dirname(__file__)
_load_lts_weights(os.path.join(_dir, "lts44_optimized_weights.txt"), "LTS44")
_load_lts_weights(os.path.join(_dir, "lts890_optimized_weights.txt"), "LTS890")

# Expose a detect function for LTS (same wrapper as AF)
from strategy_af import apply_af_filters
import config

def detect_lts(name, bars):
    af_def = LTS_STRATEGIES[name]
    cfg = af_def["cfg"]
    fill_ts = int(bars[-1]["time"])
    fill_dt = config.mt5_ts_to_bkk(fill_ts)
    res = af_def["detect_fn"](bars, tf=cfg["ENTRY_TF"], dt_bkk=fill_dt, cfg=cfg)
    filtered, reason = apply_af_filters(res, af_def, fill_ts)
    return res, filtered, reason

_load_lts_weights(os.path.join(_dir, "lts_optimized_weights.txt"), "LTS10K")
