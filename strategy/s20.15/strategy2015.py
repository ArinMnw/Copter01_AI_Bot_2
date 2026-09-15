import config

S2015_DEFAULTS = {}

def detect_s2015(window, tf_name, dt_bkk, cfg):
    if len(window) < 3:
        return {"signal": "WAIT", "reason": "not enough bars"}

    c1, c2, c3 = window[-3], window[-2], window[-1]
    
    o1, h1, l1, cl1 = float(c1["open"]), float(c1["high"]), float(c1["low"]), float(c1["close"])
    o2, h2, l2, cl2 = float(c2["open"]), float(c2["high"]), float(c2["low"]), float(c2["close"])
    o3, h3, l3, cl3 = float(c3["open"]), float(c3["high"]), float(c3["low"]), float(c3["close"])
    
    # BUY Logic
    is_c2_green = cl2 > o2
    is_c3_green = cl3 > o3
    
    if is_c2_green and is_c3_green:
        if l2 < l1:
            if cl3 > h2 and l3 >= o2:
                entry = l3
                sl = l2
                risk = entry - sl
                if risk > 0:
                    tp = entry + risk * 2.0
                    return {
                        "signal": "BUY",
                        "entry": round(entry, 5),
                        "sl": round(sl, 5),
                        "tp": round(tp, 5),
                        "order_type": "limit",
                        "pattern": "S2015 BUY",
                        "reason": "c2_green, l2<l1, c3_green, cl3>h2, l3>=o2",
                        "be_rr": None,
                        "cancel_bars": 1
                    }

    # SELL Logic
    is_c2_red = cl2 < o2
    is_c3_red = cl3 < o3
    
    if is_c2_red and is_c3_red:
        if h2 > h1:
            if cl3 < l2 and h3 <= o2:
                entry = h3
                sl = h2
                risk = sl - entry
                if risk > 0:
                    tp = entry - risk * 2.0
                    return {
                        "signal": "SELL",
                        "entry": round(entry, 5),
                        "sl": round(sl, 5),
                        "tp": round(tp, 5),
                        "order_type": "limit",
                        "pattern": "S2015 SELL",
                        "reason": "c2_red, h2>h1, c3_red, cl3<l2, h3<=o2",
                        "be_rr": None,
                        "cancel_bars": 1
                    }

    return {"signal": "WAIT", "reason": "no pattern"}
