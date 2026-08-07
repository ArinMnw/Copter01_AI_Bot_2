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
            
            # Check for S9X/S1XX format first: INVERSE_S95_M30, DIRECT_S101_M5
            # รองรับซีรีส์ใหม่ S99-S110 (2026-07: The Full Assembly)
            # + S202/S206 (2026-07-19: แชมป์สาย rollover ผ่าน dual-window validation)
            # + S218 (2026-07-20: regime-gated S206 — risk-adjusted, ต้อง lookback ≥620)
            # + S224 (2026-07-20: rollover ORB — แชมป์ตัวที่ 2, ratio 16.6)
            # + S165/S166/S172/S258/S294 (2026-07-28: 9-strategy evolution portfolio,
            #   คัดจาก S103-S302 campaign ผ่าน backtest 30-365 วัน — ดู LTS_EVOLUTION9)
            # + S303 (2026-07-20: ORB + HTF bias — subset ของ S224, ratio 23.0)
            m_s9x = re.match(r"^(DIRECT|INVERSE)_(S9[5-9]|S10[0-9]|S110|S165|S166|S172|S202|S206|S218|S224|S258|S294|S303|S304|S305|S311|S312|S322|S327|S332|S411|S413|S418|S286|S199|S293|S419)_(M5|M15|M30|H1|H4)", label)
            if m_s9x:
                n = i + 1
                key = f"{prefix}_{n}"
                mode = "inverse" if m_s9x.group(1) == "INVERSE" else "direct"
                family = m_s9x.group(2)
                tf_str = m_s9x.group(3)

                import importlib
                _num = family[1:]  # "95".."110"
                _mod = importlib.import_module(f"strategy{_num}")
                detect_fn = getattr(_mod, f"detect_s{_num}")
                    
                cfg = {"ENTRY_TF": tf_str}
                LTS_STRATEGIES[key] = {
                    "key": key,
                    "component_no": n,
                    "label": f"{key} {label}",
                    "short": key,
                    "portfolio_leg": True,
                    "formula": f"{mode.upper()} {label} x{weight}",
                    "leg_name": family,
                    "detect_fn": detect_fn,
                    "cfg": cfg,
                    "mode": mode,
                    "rd_min": None,
                    "rd_max": None,
                    "hour": None,
                    "family": family,
                    "cfg_idx": 0,
                    "weight": weight,
                    "is_s9x": True
                }
                legs.append(key)
                continue

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
weights_dir = os.path.join(_dir, "strategy", "lts", "optimized_weights")
_load_lts_weights(os.path.join(weights_dir, "lts44_optimized_weights.txt"), "LTS44")
_load_lts_weights(os.path.join(weights_dir, "lts890_optimized_weights.txt"), "LTS890")

# Expose a detect function for LTS (same wrapper as AF)
from strategy_af import apply_af_filters
import config

def detect_lts(name, bars):
    af_def = LTS_STRATEGIES[name]
    cfg = af_def["cfg"]
    fill_ts = int(bars[-1]["time"])
    
    pf_name = "LTS_AVENGERS_HIGH_RISK" if name.startswith("LTS_AVENGERS_HIGH_RISK") else ("LTS_AVENGERS_ULTRA_SAFE" if name.startswith("LTS_AVENGERS_ULTRA_SAFE") else name)
    also_backtest = config.DEMO_PORTFOLIO_CB_ENABLED.get(pf_name, False)
    
    if af_def.get("is_s9x"):
        # The backtest (run_s9x_generic) uses a lookback of 300 bars for S95-S111.
        # Slice to the last 300 to ensure identical PoC/min/max indicator calculations if also_backtest is enabled.
        rates_to_pass = bars[-300:] if also_backtest else bars
        # ต้องส่ง cfg= เสมอ — บาง strategy ใหม่ (S165/S166/S172 เป็นต้น) กำหนด cfg เป็น
        # positional argument จำเป็น ไม่มี default=None เหมือน S9x ตัวเก่า (เจอบั๊กจริง
        # 2026-07-28 ตอนเพิ่ม LTS_EVOLUTION9: TypeError missing 1 required argument 'cfg')
        # ปลอดภัยกับของเดิมด้วย เพราะทุกตัวใช้ pattern c=dict(DEFAULT_CFG); if cfg: c.update(cfg)
        res = af_def["detect_fn"](rates_to_pass, tf=cfg["ENTRY_TF"],
                                  dt_bkk=config.mt5_ts_to_bkk(fill_ts), cfg=cfg)
        if not res or res.get("signal") not in ("BUY", "SELL"):
            return res, None, "no_signal"
            
        sig = res["signal"]
        entry = float(res.get("entry", 0.0) or 0.0)
        sl = float(res.get("sl", 0.0) or 0.0)
        tp = float(res.get("tp", 0.0) or 0.0)
        risk_distance = abs(entry - sl)
        
        if af_def.get("mode") == "inverse":
            sig = "SELL" if sig == "BUY" else "BUY"
            sl, tp = tp, sl
            
        filtered = {
            "signal": sig,
            "entry": entry,
            "sl": sl,
            "tp": tp,
            "risk_distance": risk_distance,
            "fill_hour": int(config.mt5_ts_to_bkk(fill_ts).hour)
        }
        return res, filtered, ""
 
    fill_dt = config.mt5_ts_to_bkk(fill_ts)
    if also_backtest and not af_def.get("is_s9x"):
        # S84/S86 detect_fn drops the last bar internally (rates[:-1] and j = len(rates) - 2).
        # We append a duplicate candle to offset this, running detection on bars[-1] instead of bars[-2].
        rates_to_pass = list(bars) + [bars[-1]]
    else:
        rates_to_pass = bars
    res = af_def["detect_fn"](rates_to_pass, tf=cfg["ENTRY_TF"], dt_bkk=fill_dt, cfg=cfg)
    filtered, reason = apply_af_filters(res, af_def, fill_ts)
    return res, filtered, reason

_load_lts_weights(os.path.join(weights_dir, "lts_optimized_weights.txt"), "LTS999")
_load_lts_weights(os.path.join(weights_dir, "lts_avengers_weights.txt"), "LTS_AVENGERS_BASE")
_load_lts_weights(os.path.join(weights_dir, "lts_avengers_p34_weights.txt"), "LTS_AVENGERS_P34")
_load_lts_weights(os.path.join(weights_dir, "lts_avengers_high_risk_weights.txt"), "LTS_AVENGERS_HIGH_RISK")
_load_lts_weights(os.path.join(weights_dir, "lts_avengers_ultra_safe_weights.txt"), "LTS_AVENGERS_ULTRA_SAFE")
_load_lts_weights(os.path.join(weights_dir, "lts_avengers_high_freq_weights.txt"), "LTS_AVENGERS_HIGH_FREQ")
# LTS_ROLLOVER (2026-07-19): S206 rollover drive + S202 kurt-VR — paper-forward
# เท่านั้น จนกว่าจะกดเปิดใน Telegram (DEMO_PORTFOLIO_ACTIVE เริ่ม False เสมอ)
_load_lts_weights(os.path.join(weights_dir, "lts_rollover_weights.txt"), "LTS_ROLLOVER")
# LTS_ROLLOVER_SAFE (2026-07-20): S218 (regime-gated drive) + S202 — conservative
# variant, PF สูงกว่า/DD ต่ำกว่า LTS_ROLLOVER, เลือกอันใดอันหนึ่ง (S218 subset ของ S206)
_load_lts_weights(os.path.join(weights_dir, "lts_rollover_safe_weights.txt"), "LTS_ROLLOVER_SAFE")
# LTS_ROLLOVER_ORB (2026-07-20): S224 (rollover ORB) + S202 v2 — return/DD สูงสุด
# ที่แคมเปญทำได้ (94.0) และไม่ทับเวลากันเลย (04-06 vs 12-23).
# ⚠️ S224 ทับไม้กับ S206 บางส่วน — ห้ามเปิดพอร์ตนี้พร้อม LTS_ROLLOVER
_load_lts_weights(os.path.join(weights_dir, "lts_rollover_orb_weights.txt"), "LTS_ROLLOVER_ORB")
# LTS_ROLLOVER_HTF (2026-07-20): S303 (ORB + HTF-bias) + S202 v2 — return/DD สูงสุด
# ที่แคมเปญทำได้ (120.3 บน 2026-H1) ⚠️ S303 เป็น subset ของ S224 และ S224 ทับ S206
# บางส่วน — เปิดได้ทีละพอร์ตเดียวในกลุ่ม LTS_ROLLOVER*
_load_lts_weights(os.path.join(weights_dir, "lts_rollover_htf_weights.txt"), "LTS_ROLLOVER_HTF")
# LTS_ROLLOVER_HTF_MAX (2026-07-20): S304 (rolling-range drive + HTF bias) + S202 v2
# — กำไรสูงสุด (+1,253.71 บน 2026-H1) แลก DD สูงกว่า HTF (19.26 vs 9.24)
# ⚠️ S304 ทับ S206 เกือบสนิท (30/31) — เปิดได้ทีละพอร์ตเดียวในกลุ่ม LTS_ROLLOVER*
_load_lts_weights(os.path.join(weights_dir, "lts_rollover_htfmax_weights.txt"), "LTS_ROLLOVER_HTF_MAX")
# LTS_EVOLUTION9 (2026-07-28): 9 กลยุทธ์คัดจากแคมเปญ S103-S302 หลัง backtest 30-365 วัน
# (S206, S258, S294, S172, S165, S166, S104, S105, S106) — ตัด S111/S173/S176 ออกเพราะ
# DD ที่ 365d เกือบเท่า/เกิน net เอง — paper-forward เท่านั้นจนกว่าจะกดเปิดใน Telegram
# (DEMO_PORTFOLIO_ACTIVE เริ่ม False เสมอ) — S105/S106 ใช้ cfg เดียวกับพอร์ต S105/S106
# เดิมทุกประการ (_CFG_V/_CFG_W ใน demo_portfolio.py = strategy105/106.DEFAULT_CFG ตรงๆ)
_load_lts_weights(os.path.join(weights_dir, "lts_evolution9_weights.txt"), "LTS_EVOLUTION9")
# LTS_WINRATE5 (2026-07-28): เป้าหมาย win rate สูง (ต่างจาก LTS_EVOLUTION9 ที่เน้น RR/return-DD)
# คัดจากแคมเปญ S99-S111 (ICT-SMC liquidity reversal) — S99/S100/S101/S102/S105 ทุกตัว WR
# ที่ 365 วันยัง >=53% และรวมพอร์ตแล้ว WR ไม่เคยหลุดต่ำกว่า 55% ในทุกช่วง 30-365 วัน — S102 มี
# ช่วง 60-90d ติดลบเล็กน้อยเมื่อดูเดี่ยวๆ (n เล็ก) แต่พอรวมพอร์ตแล้ว net ยังบวกตลอด — paper-forward
# เท่านั้นจนกว่าจะกดเปิดใน Telegram (DEMO_PORTFOLIO_ACTIVE เริ่ม False เสมอ)
_load_lts_weights(os.path.join(weights_dir, "lts_winrate5_weights.txt"), "LTS_WINRATE5")
# LTS_SCREEN13 (2026-08-06): 13 กลยุทธ์ที่ผ่านเกณฑ์คัดกรอง dual-window (บวกทั้ง 2026-H1
# และ 2025-H2 walk-forward, combined return/DD>=10) จากแคมเปญ confluence-scoring +
# statistical-gate แต่ยังไม่เคยเข้าพอร์ตไหนมาก่อน — S305 (rollover drive ablation),
# S311/S312/S322/S327/S332 (สาย distribution-shift/self-excitation/volume-coupling),
# S411/S413 (สาย robust-shape/gap-response — เคยตกตอนทดสอบรวมกับ baseline S409-lineage
# ใน strategy_evolution.md แต่ยังไม่เคยทดสอบกับพอร์ตชุดนี้), S418 (FVG-only confluence,
# พิสูจน์แล้วว่าช่วย P13/P16 ตอนทดสอบรวมพอร์ต), S286/S199/S293 (คัดจาก DD% ต่ำ 6m ก่อน
# แล้วเพิ่งทดสอบ WF ทีหลัง — จาก 11 ตัวที่ DD% ต่ำ มีแค่ 3 ตัวนี้ผ่าน WF จริง อีก 7 ตัว
# net ติดลบทันทีที่ WF พิสูจน์ว่าเป็น overfit ล้วนๆ), S419 (Orochi Auction Market Theory —
# prior-session fixed value area, SESSION_ANCHOR_HOUR=20, ratio 12.58 เดี่ยวๆ) —
# combined backtest (2025-07-18 ถึง 2026-07-18): net $12,380.23 / DD $398.27 /
# ratio 31.09, dual_pos ทั้งสองหน้าต่าง (WF เดี่ยวๆ ก็ทะลุ 10 แล้ว ratio 10.28)
# ตัดสาย S306 ออกเพราะทับเวลากับ S305 เกือบสนิท (33/33 คู่ overlap) — เช็ค overlap ของ
# S286/S199/S293 กับ 9 ตัวเดิมแล้ว ทุกคู่ต่ำกว่า 1% ไม่มีปัญหาซ้ำซ้อน — ⚠️ S419↔S418
# ทับเวลากันสูง (75% ของไม้ S419 มีไม้ S418 เปิดอยู่พร้อมกัน เพราะทั้งคู่เป็น M5 ความถี่สูง
# ไม่กรอง session เหมือนกัน) ทำให้ ratio รวมลดจาก 39.60 (12 ตัว) เหลือ 31.09 (13 ตัว)
# แม้ net เพิ่มขึ้นก็ตาม — ยังคงสูงกว่าเกณฑ์มาก แค่ต้องรู้ว่า DD จะโตไวกว่าตัวอื่นเพราะ
# overlap นี้ — paper-forward เท่านั้นจนกว่าจะกดเปิดใน Telegram
# (DEMO_PORTFOLIO_ACTIVE เริ่ม False เสมอ)
_load_lts_weights(os.path.join(weights_dir, "lts_screen9_weights.txt"), "LTS_SCREEN13")
