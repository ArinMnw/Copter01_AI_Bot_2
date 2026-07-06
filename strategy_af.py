"""
strategy_af.py - AF Ambfix strategy wrappers.

This module keeps AF milestone and full-ladder leg definitions in one place so
the demo portfolio runner and verification scripts use the same cfg/filter/
inverse rules as the backtest research.
"""

import itertools
import re
from pathlib import Path

import config

from strategy84 import S84_DEFAULTS, _detect_closed as _detect_s84_closed, _in_session as _in_s84_session
from strategy86 import S86_DEFAULTS, _detect_closed as _detect_s86_closed, _in_session as _in_s86_session


ROOT = Path(__file__).resolve().parent
OVERLAY_CFG = {
    "RISK_PCT": 0.5,
    "DD_CONTROL": "circuit_breaker",
    "CONSEC_LOSS_TRIGGER": 3,
    "REDUCED_RISK_PCT": 0.35,
    "COOLDOWN_TRADES": 10,
}


def _grid_s84():
    return (
        ["M15", "M30"],
        [48, 72],
        [0.25, 0.35],
        [0.8, 1.0],
        [0.06, 0.12],
        [0.03, 0.08],
        [True, False],
        [0.06, 0.12],
        [0.25, 0.35],
        ["mid", "rr"],
        ["revisit", "follow"],
        [0.20, 0.35],
        [0.9, 1.2],
    )


def _grid_s86():
    return (
        ["M15", "M30"],
        [48, 72],
        [1.6, 2.2],
        [0.06, 0.12],
        [0.08, 0.14],
        [0.20, 0.35],
        [True, False],
        [12, 16],
        [0.6, 1.0],
        ["swing", "zone"],
        [0.20, 0.35],
        ["old", "rr"],
        [1.0, 1.3],
    )


def _make_s84(vals):
    (
        tf, lb, refwick, wickbody, eattol, fail, opposite, minbody,
        minrange, target, mode, slmult, rr,
    ) = vals
    cfg = dict(S84_DEFAULTS)
    cfg.update(OVERLAY_CFG)
    cfg.update({
        "ENTRY_TF": tf,
        "LOOKBACK": lb,
        "REF_MIN_WICK_ATR": refwick,
        "REF_WICK_BODY_MULT": wickbody,
        "EAT_TOL_ATR": eattol,
        "CLOSE_FAIL_ATR": fail,
        "REQUIRE_OPPOSITE_CLOSE": opposite,
        "MIN_BODY_ATR": minbody,
        "MIN_RANGE_ATR": minrange,
        "TARGET_MODE": target,
        "MODE": mode,
        "SL_ATR_MULT": slmult,
        "TP_RR": rr,
    })
    return cfg


def _make_s86(vals):
    (
        tf, lb, impulse, ztol, body, ratio, trend, tlb, tmin,
        slmode, slmult, tpmode, rr,
    ) = vals
    cfg = dict(S86_DEFAULTS)
    cfg.update(OVERLAY_CFG)
    cfg.update({
        "ENTRY_TF": tf,
        "LOOKBACK": lb,
        "IMPULSE_MIN_ATR": impulse,
        "ZONE_TOL_ATR": ztol,
        "CONFIRM_BODY_ATR": body,
        "CONFIRM_BODY_RATIO": ratio,
        "REQUIRE_TREND": trend,
        "TREND_LOOKBACK": tlb,
        "TREND_MIN_ATR": tmin,
        "SL_MODE": slmode,
        "SL_ATR_MULT": slmult,
        "TP_MODE": tpmode,
        "TP_RR": rr,
    })
    return cfg


def _atr_series(bars, period):
    trs = []
    out = []
    atr = None
    for i, b in enumerate(bars):
        h = float(b["high"])
        l = float(b["low"])
        if i == 0:
            tr = h - l
        else:
            pc = float(bars[i - 1]["close"])
            tr = max(h - l, abs(h - pc), abs(l - pc))
        trs.append(tr)
        if i + 1 < period:
            out.append(sum(trs) / len(trs))
        elif i + 1 == period:
            atr = sum(trs[-period:]) / period
            out.append(atr)
        else:
            atr = (atr * (period - 1) + tr) / period
            out.append(atr)
    return out


def detect_s84_af(rates, tf="", dt_bkk=None, cfg=None):
    cfg = cfg or S84_DEFAULTS
    min_start = int(cfg["LOOKBACK"]) + 90
    if rates is None or len(rates) < min_start + 2:
        return {"signal": "WAIT", "reason": "S84 AF: data not enough"}
    fill_dt = dt_bkk or config.mt5_ts_to_bkk(int(rates[-1]["time"]))
    if not _in_s84_session(fill_dt, cfg):
        return {"signal": "WAIT", "reason": "S84 AF: out of session"}
    j = len(rates) - 2
    atr14 = _atr_series(rates, 14)
    found = _detect_s84_closed(rates, j, cfg, atr_value=atr14[j])
    if found is None:
        return {"signal": "WAIT", "reason": "S84 AF: no setup"}
    return found


def detect_s86_af(rates, tf="", dt_bkk=None, cfg=None):
    cfg = cfg or S86_DEFAULTS
    min_start = int(cfg["LOOKBACK"]) + 120
    if rates is None or len(rates) < min_start + 2:
        return {"signal": "WAIT", "reason": "S86 AF: data not enough"}
    fill_dt = dt_bkk or config.mt5_ts_to_bkk(int(rates[-1]["time"]))
    if not _in_s86_session(fill_dt, cfg):
        return {"signal": "WAIT", "reason": "S86 AF: out of session"}
    j = len(rates) - 2
    atr14 = _atr_series(rates, 14)
    found = _detect_s86_closed(rates, j, cfg, atr_value=atr14[j])
    if found is None:
        return {"signal": "WAIT", "reason": "S86 AF: no setup"}
    return found


def _cfg_af22():
    cfg = dict(S84_DEFAULTS)
    cfg.update({
        "ENTRY_TF": "M30",
        "LOOKBACK": 48,
        "REF_MIN_WICK_ATR": 0.35,
        "REF_WICK_BODY_MULT": 1.0,
        "EAT_TOL_ATR": 0.12,
        "CLOSE_FAIL_ATR": 0.08,
        "REQUIRE_OPPOSITE_CLOSE": True,
        "MIN_BODY_ATR": 0.06,
        "MIN_RANGE_ATR": 0.25,
        "TARGET_MODE": "mid",
        "MODE": "revisit",
        "SL_ATR_MULT": 0.20,
        "TP_RR": 1.20,
    })
    return cfg


def _cfg_af34():
    cfg = dict(S84_DEFAULTS)
    cfg.update({
        "ENTRY_TF": "M15",
        "LOOKBACK": 48,
        "REF_MIN_WICK_ATR": 0.25,
        "REF_WICK_BODY_MULT": 1.0,
        "EAT_TOL_ATR": 0.12,
        "CLOSE_FAIL_ATR": 0.03,
        "REQUIRE_OPPOSITE_CLOSE": False,
        "MIN_BODY_ATR": 0.12,
        "MIN_RANGE_ATR": 0.35,
        "TARGET_MODE": "rr",
        "MODE": "revisit",
        "SL_ATR_MULT": 0.20,
        "TP_RR": 1.20,
    })
    return cfg


def _cfg_af47():
    cfg = dict(S86_DEFAULTS)
    cfg.update({
        "ENTRY_TF": "M30",
        "LOOKBACK": 72,
        "IMPULSE_MIN_ATR": 2.2,
        "ZONE_TOL_ATR": 0.06,
        "CONFIRM_BODY_ATR": 0.08,
        "CONFIRM_BODY_RATIO": 0.20,
        "REQUIRE_TREND": True,
        "TREND_LOOKBACK": 12,
        "TREND_MIN_ATR": 0.60,
        "SL_MODE": "swing",
        "TP_MODE": "rr",
        "SL_ATR_MULT": 0.20,
        "TP_RR": 1.30,
    })
    return cfg


AF_STRATEGIES = {
    "AF22": {
        "key": "AF22",
        "label": "AF22 $1000 Ambfix S84 c6017",
        "short": "AF22 $1000",
        "target_balance": 1000,
        "milestone": "avg >= $1000/day",
        "detect_fn": detect_s84_af,
        "cfg": _cfg_af22(),
        "mode": "direct",
        "rd_min": 5.0,
        "rd_max": 7.0,
        "hour": 14,
        "doc": "create_af22.md",
        "base": "af21_ambfix_c6017_dir_rdmin50_rd70_h10_daily.csv",
        "out_prefix": "af22_ambfix_c6017_dir_rdmin50_rd70_h14",
        "family": "s84",
        "cfg_idx": 6017,
        "weight": 244.089,
    },
    "AF34": {
        "key": "AF34",
        "label": "AF34 $1500 Ambfix S84 c889 inverse",
        "short": "AF34 $1500",
        "target_balance": 1500,
        "milestone": "avg >= $1500/day",
        "detect_fn": detect_s84_af,
        "cfg": _cfg_af34(),
        "mode": "inverse",
        "rd_min": 2.7,
        "rd_max": 3.4,
        "hour": 13,
        "doc": "create_af34.md",
        "base": "af33_ambfix_c889_dir_rdmin34_rd40_h13_daily.csv",
        "out_prefix": "af34_ambfix_c889_inv_rdmin27_rd34_h13",
        "family": "s84",
        "cfg_idx": 889,
        "weight": 273.830,
    },
    "AF47": {
        "key": "AF47",
        "label": "AF47 $2000 Ambfix S86RUN c7171",
        "short": "AF47 $2000",
        "target_balance": 2000,
        "milestone": "avg >= $2000/day",
        "detect_fn": detect_s86_af,
        "cfg": _cfg_af47(),
        "mode": "direct",
        "rd_min": None,
        "rd_max": None,
        "hour": 13,
        "doc": "create_af47.md",
        "base": "af46_ambfix_s86c7171_dir_all_h11_daily.csv",
        "out_prefix": "af47_ambfix_s86c7171_dir_all_h13",
        "family": "s86",
        "cfg_idx": 7171,
        "weight": 145.720,
    },
}


AF_MILESTONE_STRATEGIES = AF_STRATEGIES


def _formula_from_doc(n):
    text = (ROOT / f"create_af{n}.md").read_text(encoding="utf-8")
    matches = re.findall(rf"AF{n}\s*=\s*([^\n`]+)", text)
    if not matches:
        raise ValueError(f"Cannot find AF{n} formula")
    formula = matches[-1].strip()
    leg = formula.split("+", 1)[1].strip() if "+" in formula else formula
    m = re.search(r"x([0-9]+(?:\.[0-9]+)?)$", leg)
    if not m:
        raise ValueError(f"Cannot parse AF{n} weight from {leg}")
    return formula, leg[:m.start()].rstrip(), float(m.group(1))


def _old_s84_follow_cfg():
    cfg = dict(_make_s84(list(itertools.product(*_grid_s84()))[28]))
    cfg.update({
        "ENTRY_TF": "M15",
        "LOOKBACK": 48,
        "REF_MIN_WICK_ATR": 0.25,
        "REF_WICK_BODY_MULT": 0.8,
        "EAT_TOL_ATR": 0.06,
        "CLOSE_FAIL_ATR": 0.03,
        "REQUIRE_OPPOSITE_CLOSE": True,
        "MIN_BODY_ATR": 0.06,
        "MIN_RANGE_ATR": 0.35,
        "TARGET_MODE": "rr",
        "MODE": "follow",
        "SL_ATR_MULT": 0.20,
        "TP_RR": 0.90,
    })
    return cfg


def _cfg_for_ladder_leg(leg_name):
    if "S86RUN" in leg_name:
        cfg_idx = int(re.search(r"c([0-9]+)", leg_name).group(1))
        return "s86", _make_s86(list(itertools.product(*_grid_s86()))[cfg_idx]), detect_s86_af, cfg_idx
    if "c" in leg_name:
        cfg_idx = int(re.search(r"c([0-9]+)", leg_name).group(1))
        return "s84", _make_s84(list(itertools.product(*_grid_s84()))[cfg_idx]), detect_s84_af, cfg_idx
    return "s84", _old_s84_follow_cfg(), detect_s84_af, 28


def _filters_for_ladder_leg(leg_name):
    mode = "inverse" if "_INV_" in leg_name else "direct"
    rd_min = rd_max = None
    m = re.search(r"_RD([0-9.]+)_([0-9.]+)_H", leg_name)
    if m:
        rd_min = float(m.group(1))
        rd_max = float(m.group(2))
    hour = int(re.search(r"_H([0-9]+)", leg_name).group(1))
    return mode, rd_min, rd_max, hour


def _build_ladder_leg(n):
    formula, leg_name, weight = _formula_from_doc(n)
    family, cfg, detect_fn, cfg_idx = _cfg_for_ladder_leg(leg_name)
    mode, rd_min, rd_max, hour = _filters_for_ladder_leg(leg_name)
    return {
        "key": f"AF{n}",
        "component_no": n,
        "label": f"AF{n} {leg_name}",
        "short": f"AF{n}",
        "portfolio_leg": True,
        "formula": formula,
        "leg_name": leg_name,
        "detect_fn": detect_fn,
        "cfg": cfg,
        "mode": mode,
        "rd_min": rd_min,
        "rd_max": rd_max,
        "hour": hour,
        "doc": f"create_af{n}.md",
        "family": family,
        "cfg_idx": cfg_idx,
        "weight": weight,
    }


AF_LADDER_LEGS = {f"AF{n}": _build_ladder_leg(n) for n in range(1, 48)}
AF_PORTFOLIO_LEGS = {
    "AF22": [f"AF{n}" for n in range(1, 23)],
    "AF34": [f"AF{n}" for n in range(1, 35)],
    "AF47": [f"AF{n}" for n in range(1, 48)],
}


def af_min_gap_seconds(af_def):
    cfg = af_def["cfg"]
    tf = cfg["ENTRY_TF"]
    tf_secs = {"M5": 300, "M15": 900, "M30": 1800, "H1": 3600}
    return int(cfg.get("MIN_GAP_BARS", 1)) * tf_secs[tf]


def af_raw_cooldown_active(last_raw_ts, entry_ts, af_def, bars=None):
    if last_raw_ts is None:
        return False
    if bars is not None:
        ts_to_idx = {int(b["time"]): i for i, b in enumerate(bars)}
        last_idx = ts_to_idx.get(int(last_raw_ts))
        entry_idx = ts_to_idx.get(int(entry_ts))
        if last_idx is not None and entry_idx is not None:
            return entry_idx - last_idx < int(af_def["cfg"].get("MIN_GAP_BARS", 1))
    return int(entry_ts) - int(last_raw_ts) < af_min_gap_seconds(af_def)


def apply_af_filters(res, af_def, fill_ts):
    sig = res.get("signal")
    if sig not in ("BUY", "SELL"):
        return None, "no_signal"

    fill_dt = config.mt5_ts_to_bkk(int(fill_ts))
    hour = int(fill_dt.hour)
    if hour != int(af_def["hour"]):
        return None, f"hour {hour} != {af_def['hour']}"

    entry = float(res.get("entry", 0.0) or 0.0)
    sl = float(res.get("sl", 0.0) or 0.0)
    tp = float(res.get("tp", 0.0) or 0.0)
    risk_distance = abs(entry - sl)
    rd_min = af_def.get("rd_min")
    rd_max = af_def.get("rd_max")
    if rd_min is not None and risk_distance < float(rd_min):
        return None, f"risk_distance {risk_distance:.2f} < {float(rd_min):.2f}"
    if rd_max is not None and risk_distance > float(rd_max):
        return None, f"risk_distance {risk_distance:.2f} > {float(rd_max):.2f}"

    if af_def.get("mode") == "inverse":
        sig = "SELL" if sig == "BUY" else "BUY"
        sl, tp = tp, sl

    return {
        "signal": sig,
        "entry": entry,
        "sl": sl,
        "tp": tp,
        "risk_distance": risk_distance,
        "fill_hour": hour,
    }, ""


def detect_af(name, bars):
    af_def = AF_STRATEGIES[name]
    cfg = af_def["cfg"]
    fill_ts = int(bars[-1]["time"])
    fill_dt = config.mt5_ts_to_bkk(fill_ts)
    res = af_def["detect_fn"](bars, tf=cfg["ENTRY_TF"], dt_bkk=fill_dt, cfg=cfg)
    filtered, reason = apply_af_filters(res, af_def, fill_ts)
    return res, filtered, reason


def detect_af22(bars):
    return detect_af("AF22", bars)


def detect_af34(bars):
    return detect_af("AF34", bars)


def detect_af47(bars):
    return detect_af("AF47", bars)
