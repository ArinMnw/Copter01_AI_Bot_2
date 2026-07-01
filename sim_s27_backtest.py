"""
sim_s27_backtest.py — Backtest S27 (entry M1/M5 + HTF confirmation M15/H1/H4) จาก MT5 จริง
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ RESEARCH / BACKTEST-ONLY — strategy27.py ไม่ถูก wire เข้า scanner.py/trailing.py/
   main.py ใดๆ ทั้งสิ้น ไฟล์นี้ไม่แก้ S1-S26, ไม่แก้ bot_state.json, ไม่แตะ live trading

กัน look-ahead bias 2 ชั้น:
  1) ชั้น entry-TF เดิม (เหมือน sim_s21-26): แท่งกำลังวิ่งใช้ close=open ของแท่งถัดไป, entry
     เป็น MARKET ที่ open ของแท่งถัดจากแท่ง signal, แท่งเดียวกันแตะทั้ง TP/SL นับ SL (conservative)
  2) ชั้นข้าม timeframe (ใหม่ใน S27): HTF context (_htf_lookup) ใช้เฉพาะ "แท่ง HTF ที่ปิดสมบูรณ์
     แล้วก่อนเวลา entry-bar" เท่านั้น — ไม่มีทางเห็นแท่ง HTF ที่ "กำลังวิ่ง" ในช่วงเวลานั้น
     (bisect บน close_time ของ HTF series ที่ build จาก rates ที่ปิดแล้วทั้งหมด)

ตัวอย่าง:
  python sim_s27_backtest.py --days 30 --conf htf_trend --entrytf M1 --htftf M15
  python sim_s27_backtest.py --days 30 --conf htf_rsi --entrytf M5 --htftf H1 --csv
"""

import argparse
import bisect
import csv
import os
from datetime import datetime

import MetaTrader5 as mt5

import config
from strategy27 import S27_DEFAULTS, detect_s27

SYMBOL = config.SYMBOL
DEFAULT_SPREAD = 0.20
START_EQUITY = 1000.0
ASSUMED_LEVERAGE = 500.0
MAX_MARGIN_USAGE_PCT = 30.0
CONTRACT_OZ = 100.0
MIN_LOT = 0.01
LOT_STEP = 0.01

_TF_MAP = {
    "M1": mt5.TIMEFRAME_M1, "M5": mt5.TIMEFRAME_M5, "M15": mt5.TIMEFRAME_M15,
    "M30": mt5.TIMEFRAME_M30, "H1": mt5.TIMEFRAME_H1, "H4": mt5.TIMEFRAME_H4,
}
_PER_DAY = {"M1": 1440, "M5": 288, "M15": 96, "M30": 48, "H1": 24, "H4": 6}


def fetch_bars(symbol, tf_str, days, extra_bars=400):
    tf_val = _TF_MAP[tf_str]
    per_day = _PER_DAY[tf_str]
    count = min(days * per_day + extra_bars, 95000)
    rates = mt5.copy_rates_from_pos(symbol, tf_val, 0, count)
    if rates is None or len(rates) == 0:
        return None
    return rates


def _calc_atr_series(rates, period=14):
    """ATR ของแท่งที่ i คำนวณจากแท่ง 0..i (ไม่ lookahead)"""
    n = len(rates)
    trs = [0.0] * n
    for i in range(n):
        h = float(rates[i]["high"]); l = float(rates[i]["low"])
        if i == 0:
            trs[i] = h - l
        else:
            pc = float(rates[i - 1]["close"])
            trs[i] = max(h - l, abs(h - pc), abs(l - pc))
    out = [0.0] * n
    if n < period:
        run = 0.0
        for i in range(n):
            run += trs[i]
            out[i] = run / (i + 1)
        return out
    atr = sum(trs[:period]) / period
    for i in range(period):
        out[i] = atr
    for i in range(period, n):
        atr = (atr * (period - 1) + trs[i]) / period
        out[i] = atr
    return out


def _ema_full(closes, period):
    n = len(closes)
    if n == 0:
        return []
    k = 2.0 / (period + 1.0)
    ema = closes[0]
    out = [ema]
    for i in range(1, n):
        ema = closes[i] * k + ema * (1.0 - k)
        out.append(ema)
    return out


def _rsi_series(closes, period=14):
    n = len(closes)
    out = [50.0] * n
    if n < period + 1:
        return out
    gains = [0.0] * n
    losses = [0.0] * n
    for i in range(1, n):
        diff = closes[i] - closes[i - 1]
        gains[i] = max(diff, 0.0)
        losses[i] = max(-diff, 0.0)
    avg_gain = sum(gains[1:period + 1]) / period
    avg_loss = sum(losses[1:period + 1]) / period
    for i in range(period + 1):
        out[i] = 50.0
    for i in range(period + 1, n):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        if avg_loss == 0:
            out[i] = 100.0
        else:
            rs = avg_gain / avg_loss
            out[i] = 100.0 - (100.0 / (1.0 + rs))
    return out


def _adx_series(rates, period=14):
    n = len(rates)
    out = [0.0] * n
    if n < period * 2 + 1:
        return out
    highs = [float(r["high"]) for r in rates]
    lows = [float(r["low"]) for r in rates]
    closes = [float(r["close"]) for r in rates]
    plus_dm = [0.0] * n
    minus_dm = [0.0] * n
    tr = [0.0] * n
    for i in range(1, n):
        up = highs[i] - highs[i - 1]
        down = lows[i - 1] - lows[i]
        plus_dm[i] = up if (up > down and up > 0) else 0.0
        minus_dm[i] = down if (down > up and down > 0) else 0.0
        tr[i] = max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1]))

    def _wilder_smooth(vals):
        sm = [0.0] * n
        sm[period] = sum(vals[1:period + 1])
        for i in range(period + 1, n):
            sm[i] = sm[i - 1] - sm[i - 1] / period + vals[i]
        return sm

    tr_sm = _wilder_smooth(tr)
    pdm_sm = _wilder_smooth(plus_dm)
    mdm_sm = _wilder_smooth(minus_dm)
    dx = [0.0] * n
    for i in range(period, n):
        if tr_sm[i] <= 0:
            continue
        pdi = 100.0 * pdm_sm[i] / tr_sm[i]
        mdi = 100.0 * mdm_sm[i] / tr_sm[i]
        denom = pdi + mdi
        dx[i] = 100.0 * abs(pdi - mdi) / denom if denom > 0 else 0.0
    start = period * 2
    if start >= n:
        return out
    adx = sum(dx[period:start]) / period
    out[start] = adx
    for i in range(start + 1, n):
        adx = (adx * (period - 1) + dx[i]) / period
        out[i] = adx
    return out


def build_htf_series(htf_bars, cfg):
    """
    Precompute ทุก indicator บน HTF bars ทั้งชุด (ไม่ lookahead เพราะแต่ละ index ใช้แท่ง
    0..i เท่านั้นภายในตัวมันเอง — สิ่งที่กัน lookahead จริงคือ `_htf_lookup` ด้านล่างที่
    บังคับเลือกแท่ง HTF "ปิดแล้วก่อนเวลา entry" เท่านั้น ไม่ใช่ index ล่าสุดของ array)
    """
    closes = [float(r["close"]) for r in htf_bars]
    ema_period = int(_cfg_get(cfg, "HTF_EMA_PERIOD"))
    slope_bars = int(_cfg_get(cfg, "HTF_SLOPE_BARS"))
    rsi_period = int(_cfg_get(cfg, "RSI_PERIOD"))
    adx_period = int(_cfg_get(cfg, "ADX_PERIOD"))
    lb = int(_cfg_get(cfg, "LEVEL_LOOKBACK"))

    ema = _ema_full(closes, ema_period)
    rsi = _rsi_series(closes, rsi_period)
    adx = _adx_series(htf_bars, adx_period)

    n = len(htf_bars)
    close_times = [int(r["time"]) + _tf_secs(_cfg_get(cfg, "HTF_TF")) for r in htf_bars]  # เวลาที่แท่งนี้ "ปิด" จริง

    level_high = [None] * n
    level_low = [None] * n
    highs = [float(r["high"]) for r in htf_bars]
    lows = [float(r["low"]) for r in htf_bars]
    for i in range(n):
        lo_idx = max(0, i - lb + 1)
        if i - lo_idx + 1 < lb:
            continue
        level_high[i] = max(highs[lo_idx:i + 1])
        level_low[i] = min(lows[lo_idx:i + 1])

    return {
        "close_times": close_times,
        "closes": closes,
        "ema": ema,
        "rsi": rsi,
        "adx": adx,
        "level_high": level_high,
        "level_low": level_low,
        "slope_bars": slope_bars,
    }


def _tf_secs(tf_str):
    return {"M1": 60, "M5": 300, "M15": 900, "M30": 1800, "H1": 3600, "H4": 14400}[tf_str]


def _cfg_get(cfg, key):
    return cfg[key] if (cfg and key in cfg) else S27_DEFAULTS[key]


def htf_lookup(series, entry_time):
    """หา index ของแท่ง HTF ที่ 'ปิดแล้วล่าสุดก่อน entry_time' (กัน look-ahead ข้าม TF)"""
    ct = series["close_times"]
    idx = bisect.bisect_right(ct, entry_time) - 1
    if idx < 0:
        return None
    slope_bars = series["slope_bars"]
    ema_now = series["ema"][idx]
    prev_idx = max(0, idx - slope_bars)
    ema_prev = series["ema"][prev_idx]
    return {
        "trend_up": ema_now > ema_prev,
        "trend_down": ema_now < ema_prev,
        "adx": series["adx"][idx],
        "rsi": series["rsi"][idx],
        "level_high": series["level_high"][idx],
        "level_low": series["level_low"][idx],
        "price": series["closes"][idx],
        "idx": idx,
    }


def replay(bars, htf_series, spread, cfg):
    ema_fast = int(cfg["EMA_FAST"])
    win_size = ema_fast + 30
    conf_type = cfg["CONFIRMATION_TYPE"]

    trades = []
    last_fire_idx = -10
    min_gap_bars = 2
    n = len(bars)
    start_j = win_size + 5
    for j in range(start_j, n - 1):
        if j - last_fire_idx < min_gap_bars:
            continue
        entry_bar = bars[j + 1]
        live = {
            "time": int(entry_bar["time"]),
            "open": float(entry_bar["open"]),
            "high": float(entry_bar["open"]),
            "low": float(entry_bar["open"]),
            "close": float(entry_bar["open"]),
        }
        lo = max(0, j + 1 - win_size)
        window = list(bars[lo:j + 1]) + [live]

        dt_bkk = config.mt5_ts_to_bkk(int(entry_bar["time"]))

        htf_ctx = None
        if conf_type != "none":
            htf_ctx = htf_lookup(htf_series, int(entry_bar["time"]))

        res = detect_s27(window, tf=cfg["ENTRY_TF"], dt_bkk=dt_bkk, cfg=cfg, htf_ctx=htf_ctx)
        sig = res.get("signal")
        if sig not in ("BUY", "SELL"):
            continue
        last_fire_idx = j

        entry, tp, sl = float(res["entry"]), float(res["tp"]), float(res["sl"])
        fill_idx = j + 1
        outcome, exit_price, exit_idx = "OPEN", None, None
        for m in range(fill_idx, n):
            hi, lw = float(bars[m]["high"]), float(bars[m]["low"])
            if sig == "BUY":
                if lw <= sl:
                    outcome, exit_price = "SL", sl
                elif hi >= tp:
                    outcome, exit_price = "TP", tp
            else:
                if hi >= sl:
                    outcome, exit_price = "SL", sl
                elif lw <= tp:
                    outcome, exit_price = "TP", tp
            if outcome != "OPEN":
                exit_idx = m
                break
        if outcome == "OPEN":
            continue

        risk_distance = abs(entry - sl)
        diff = (exit_price - entry) if sig == "BUY" else (entry - exit_price)
        trades.append({
            "signal": sig, "outcome": outcome,
            "signal_time_ts": int(entry_bar["time"]),
            "fill_time_ts": int(bars[fill_idx]["time"]),
            "exit_time_ts": int(bars[exit_idx]["time"]),
            "entry": round(entry, 2), "tp": round(tp, 2), "sl": round(sl, 2),
            "exit_price": round(exit_price, 2),
            "risk_distance": round(risk_distance, 4),
            "diff_usd_per_001lot": round(diff, 4),
            "spread": spread,
        })
    return trades


def simulate_equity(all_trades, risk_pct):
    ordered = sorted(all_trades, key=lambda t: t["fill_time_ts"])
    equity = START_EQUITY
    peak = equity
    max_dd_usd = 0.0
    max_dd_pct = 0.0
    out = []
    lots_used = []
    for t in ordered:
        risk_usd = equity * risk_pct / 100.0
        risk_distance = t["risk_distance"]
        if risk_distance <= 0:
            continue
        lot_oz = risk_usd / risk_distance
        lot = round(lot_oz * 0.01 / LOT_STEP) * LOT_STEP
        lot = max(MIN_LOT, lot)

        approx_price = t["entry"]
        max_margin_usd = equity * MAX_MARGIN_USAGE_PCT / 100.0
        max_lot_by_margin = (max_margin_usd * ASSUMED_LEVERAGE) / (CONTRACT_OZ * approx_price)
        max_lot_by_margin = max(MIN_LOT, round(max_lot_by_margin / LOT_STEP) * LOT_STEP)
        if lot > max_lot_by_margin:
            lot = max_lot_by_margin

        lot_001_units = lot / 0.01
        pnl = (t["diff_usd_per_001lot"] - t["spread"]) * lot_001_units
        equity += pnl
        peak = max(peak, equity)
        dd_usd = peak - equity
        dd_pct = (dd_usd / peak * 100.0) if peak > 0 else 0.0
        max_dd_usd = max(max_dd_usd, dd_usd)
        max_dd_pct = max(max_dd_pct, dd_pct)
        lots_used.append(lot)

        row = dict(t)
        row["lot"] = lot
        row["risk_usd"] = round(risk_usd, 2)
        row["pnl_usd"] = round(pnl, 2)
        row["equity_after"] = round(equity, 2)
        out.append(row)

    return out, {
        "final_equity": round(equity, 2),
        "max_dd_usd": round(max_dd_usd, 2),
        "max_dd_pct": round(max_dd_pct, 2),
        "lot_min": round(min(lots_used), 2) if lots_used else 0.0,
        "lot_max": round(max(lots_used), 2) if lots_used else 0.0,
    }


def daily_pnl(trades_with_pnl):
    by_day = {}
    for t in trades_with_pnl:
        day = config.mt5_ts_to_bkk(t["exit_time_ts"]).strftime("%Y-%m-%d")
        by_day[day] = by_day.get(day, 0.0) + t["pnl_usd"]
    return by_day


def summarize(trades_with_pnl, equity_stats, risk_pct, days):
    if not trades_with_pnl:
        return None
    wins = [t for t in trades_with_pnl if t["pnl_usd"] > 0]
    losses = [t for t in trades_with_pnl if t["pnl_usd"] <= 0]
    total_pnl = sum(t["pnl_usd"] for t in trades_with_pnl)
    by_day = daily_pnl(trades_with_pnl)
    n_days_with_trades = len(by_day)
    span_days = max(days, 1)
    avg_per_day_all_span = total_pnl / span_days
    avg_per_day_active = (total_pnl / n_days_with_trades) if n_days_with_trades else 0.0
    trades_per_active_day = (len(trades_with_pnl) / n_days_with_trades) if n_days_with_trades else 0.0
    days_hit_1000 = sum(1 for v in by_day.values() if v >= 1000.0)
    max_consec_loss = consec = 0
    for t in trades_with_pnl:
        consec = consec + 1 if t["pnl_usd"] <= 0 else 0
        max_consec_loss = max(max_consec_loss, consec)

    r_multiples = [t["pnl_usd"] / t["risk_usd"] for t in trades_with_pnl if t.get("risk_usd")]
    avg_r = round(sum(r_multiples) / len(r_multiples), 3) if r_multiples else 0.0

    pf_gain = sum(t["pnl_usd"] for t in wins) if wins else 0.0
    pf_loss = abs(sum(t["pnl_usd"] for t in losses)) if losses else 0.0
    profit_factor = round(pf_gain / pf_loss, 2) if pf_loss > 0 else (round(pf_gain, 2) if pf_gain > 0 else 0.0)

    return {
        "trades": len(trades_with_pnl),
        "wins": len(wins),
        "losses": len(losses),
        "wr": round(100.0 * len(wins) / len(trades_with_pnl), 1),
        "total_pnl": round(total_pnl, 2),
        "avg_per_day_span": round(avg_per_day_all_span, 2),
        "avg_per_day_active": round(avg_per_day_active, 2),
        "trades_per_active_day": round(trades_per_active_day, 1),
        "n_days_with_trades": n_days_with_trades,
        "span_days": span_days,
        "days_hit_1000": days_hit_1000,
        "max_consec_loss": max_consec_loss,
        "risk_pct": risk_pct,
        "avg_r_multiple": avg_r,
        "profit_factor": profit_factor,
        **equity_stats,
    }


def fmt_summary(s):
    if s is None:
        return "no trades"
    return (
        f"n={s['trades']:>5} WR={s['wr']:>5.1f}% | total P/L=${s['total_pnl']:>9.2f} | "
        f"avg/day(span {s['span_days']}d)=${s['avg_per_day_span']:>8.2f} | "
        f"trades/day(active)={s['trades_per_active_day']:>6.1f} | "
        f"days>=$1000: {s['days_hit_1000']}/{s['n_days_with_trades']} | "
        f"maxDD=${s['max_dd_usd']:>8.2f} ({s['max_dd_pct']:.1f}%) | "
        f"lot={s['lot_min']}-{s['lot_max']} | risk={s['risk_pct']}% | "
        f"avgR={s['avg_r_multiple']:.3f} | PF={s['profit_factor']:.2f} | "
        f"final_equity=${s['final_equity']:.2f} | maxLossStreak={s['max_consec_loss']}"
    )


def append_summary_csv(label, s, cfg, risk_pct):
    path = os.path.join(os.path.dirname(__file__), "s27_backtest_summary.csv")
    is_new = not os.path.exists(path)
    fields = [
        "timestamp", "label", "entry_tf", "confirmation_type", "htf_tf", "trades", "wr",
        "total_pnl", "avg_per_day_span", "avg_per_day_active", "trades_per_active_day",
        "n_days_with_trades", "span_days", "days_hit_1000", "max_dd_usd", "max_dd_pct",
        "lot_min", "lot_max", "risk_pct", "final_equity", "max_consec_loss",
        "avg_r_multiple", "profit_factor",
        "ema_fast", "pullback_touch_atr", "sl_atr_mult", "tp_rr",
        "htf_ema_period", "htf_slope_bars", "adx_min_threshold", "rsi_threshold",
        "level_lookback", "level_zone_pct",
    ]
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        if is_new:
            w.writeheader()
        row = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "label": label,
            "entry_tf": cfg["ENTRY_TF"],
            "confirmation_type": cfg["CONFIRMATION_TYPE"],
            "htf_tf": cfg["HTF_TF"],
            **{k: s[k] for k in (
                "trades", "wr", "total_pnl", "avg_per_day_span", "avg_per_day_active",
                "trades_per_active_day", "n_days_with_trades", "span_days", "days_hit_1000",
                "max_dd_usd", "max_dd_pct", "lot_min", "lot_max", "risk_pct", "final_equity",
                "max_consec_loss", "avg_r_multiple", "profit_factor",
            )},
            "ema_fast": cfg["EMA_FAST"],
            "pullback_touch_atr": cfg["PULLBACK_TOUCH_ATR"],
            "sl_atr_mult": cfg["SL_ATR_MULT"],
            "tp_rr": cfg["TP_RR"],
            "htf_ema_period": cfg["HTF_EMA_PERIOD"],
            "htf_slope_bars": cfg["HTF_SLOPE_BARS"],
            "adx_min_threshold": cfg["ADX_MIN_THRESHOLD"],
            "rsi_threshold": cfg["RSI_THRESHOLD"],
            "level_lookback": cfg["LEVEL_LOOKBACK"],
            "level_zone_pct": cfg["LEVEL_ZONE_PCT"],
        }
        w.writerow(row)
    print(f"  -> appended to {path}")


def run_backtest(cfg, days, spread, label, save_csv=False, verbose=True, mt5_already_init=False):
    if not mt5_already_init and not mt5.initialize():
        print(f"MT5 initialize ล้มเหลว: {mt5.last_error()}")
        return None

    symbol = config.SYMBOL
    entry_bars = fetch_bars(symbol, cfg["ENTRY_TF"], days, extra_bars=max(300, int(cfg["EMA_FAST"]) + 60))
    if entry_bars is None:
        if verbose:
            print("! ดึงข้อมูล entry TF ไม่ได้")
        return None

    htf_series = None
    if cfg["CONFIRMATION_TYPE"] != "none":
        htf_extra = max(int(cfg["HTF_EMA_PERIOD"]), int(cfg["LEVEL_LOOKBACK"]), int(cfg["ADX_PERIOD"]) * 2 + 5) + 60
        htf_bars = fetch_bars(symbol, cfg["HTF_TF"], days, extra_bars=htf_extra)
        if htf_bars is None:
            if verbose:
                print("! ดึงข้อมูล HTF ไม่ได้")
            return None
        htf_series = build_htf_series(htf_bars, cfg)

    if verbose:
        t0 = config.mt5_ts_to_bkk(int(entry_bars[0]["time"])).strftime("%Y-%m-%d %H:%M")
        t1 = config.mt5_ts_to_bkk(int(entry_bars[-1]["time"])).strftime("%Y-%m-%d %H:%M")
        print(f"  {cfg['ENTRY_TF']}: {len(entry_bars)} bars ({t0} -> {t1} BKK) | conf={cfg['CONFIRMATION_TYPE']} htf={cfg['HTF_TF']}")

    raw = replay(entry_bars, htf_series, spread, cfg)
    if verbose:
        print(f"    signals(after fill+SL/TP resolved): {len(raw)}")

    trades_with_pnl, equity_stats = simulate_equity(raw, cfg["RISK_PCT"])
    s = summarize(trades_with_pnl, equity_stats, cfg["RISK_PCT"], days)
    if verbose:
        print("-" * 120)
        print(fmt_summary(s) if s else "no trades")

    if s:
        append_summary_csv(label, s, cfg, cfg["RISK_PCT"])

    if save_csv and trades_with_pnl:
        out_dir = os.path.join("excel_reports", "backtest_compare", "s27")
        os.makedirs(out_dir, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M")
        path = os.path.join(out_dir, f"sim_s27_{label}_{stamp}.csv")
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(trades_with_pnl[0].keys()))
            w.writeheader()
            w.writerows(trades_with_pnl)
        if verbose:
            print(f"CSV: {path}")

    if not mt5_already_init:
        mt5.shutdown()

    return s, trades_with_pnl


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--spread", type=float, default=DEFAULT_SPREAD)
    ap.add_argument("--risk", type=float, default=S27_DEFAULTS["RISK_PCT"])
    ap.add_argument("--entrytf", default=None, choices=["M1", "M5"])
    ap.add_argument("--conf", default=None, choices=["none", "htf_trend", "htf_rsi", "htf_level"])
    ap.add_argument("--htftf", default=None, choices=["M15", "H1", "H4"])
    ap.add_argument("--emafast", type=int, default=None)
    ap.add_argument("--touchatr", type=float, default=None)
    ap.add_argument("--slmult", type=float, default=None)
    ap.add_argument("--rr", type=float, default=None)
    ap.add_argument("--htfema", type=int, default=None)
    ap.add_argument("--htfslope", type=int, default=None)
    ap.add_argument("--adxmin", type=float, default=None)
    ap.add_argument("--rsithr", type=float, default=None)
    ap.add_argument("--levellb", type=int, default=None)
    ap.add_argument("--levelzone", type=float, default=None)
    ap.add_argument("--nosession", action="store_true")
    ap.add_argument("--session", default=None)
    ap.add_argument("--label", default="baseline")
    ap.add_argument("--csv", action="store_true")
    args = ap.parse_args()

    cfg = dict(S27_DEFAULTS)
    cfg["RISK_PCT"] = args.risk
    if args.entrytf is not None:
        cfg["ENTRY_TF"] = args.entrytf
    if args.conf is not None:
        cfg["CONFIRMATION_TYPE"] = args.conf
    if args.htftf is not None:
        cfg["HTF_TF"] = args.htftf
    if args.emafast is not None:
        cfg["EMA_FAST"] = args.emafast
    if args.touchatr is not None:
        cfg["PULLBACK_TOUCH_ATR"] = args.touchatr
    if args.slmult is not None:
        cfg["SL_ATR_MULT"] = args.slmult
    if args.rr is not None:
        cfg["TP_RR"] = args.rr
    if args.htfema is not None:
        cfg["HTF_EMA_PERIOD"] = args.htfema
    if args.htfslope is not None:
        cfg["HTF_SLOPE_BARS"] = args.htfslope
    if args.adxmin is not None:
        cfg["ADX_MIN_THRESHOLD"] = args.adxmin
    if args.rsithr is not None:
        cfg["RSI_THRESHOLD"] = args.rsithr
    if args.levellb is not None:
        cfg["LEVEL_LOOKBACK"] = args.levellb
    if args.levelzone is not None:
        cfg["LEVEL_ZONE_PCT"] = args.levelzone
    if args.nosession:
        cfg["SESSION_FILTER"] = False
    if args.session is not None:
        start_s, end_s = args.session.split("-")
        cfg["SESSIONS"] = [(start_s, end_s)]

    print(f"S27 backtest | Symbol={config.SYMBOL} | days={args.days} | spread=${args.spread:.2f} | "
          f"risk={cfg['RISK_PCT']}%/trade | entry_tf={cfg['ENTRY_TF']} conf={cfg['CONFIRMATION_TYPE']} "
          f"htf={cfg['HTF_TF']} | start_equity=${START_EQUITY:.0f}")
    print(f"cfg: ema_fast={cfg['EMA_FAST']} touch_atr={cfg['PULLBACK_TOUCH_ATR']} sl_mult={cfg['SL_ATR_MULT']} "
          f"rr={cfg['TP_RR']} htf_ema={cfg['HTF_EMA_PERIOD']} htf_slope={cfg['HTF_SLOPE_BARS']} "
          f"adx_min={cfg['ADX_MIN_THRESHOLD']} rsi_thr={cfg['RSI_THRESHOLD']} level_lb={cfg['LEVEL_LOOKBACK']} "
          f"level_zone={cfg['LEVEL_ZONE_PCT']} session_filter={cfg['SESSION_FILTER']}")

    run_backtest(cfg, args.days, args.spread, args.label, save_csv=args.csv, verbose=True)


if __name__ == "__main__":
    main()
