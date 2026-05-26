"""
test_s14_sim2.py — Simulate S14 (redesigned) on M1 bars 12:29-13:20 BKK
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import MetaTrader5 as mt5
from datetime import datetime, timezone, timedelta
import config
from strategy14 import strategy_14, _find_bear_reversals, _find_bull_reversals, _tp_from_window, _pivot_rsi_buy, _pivot_rsi_sell
from strategy9 import _calc_rsi_values
import hhll_swing

SYMBOL  = config.SYMBOL
TF_NAME = "M1"
TF_VAL  = mt5.TIMEFRAME_M1

S14_LOOKBACK  = int(getattr(config, "S14_REVERSAL_LOOKBACK", 50))
S14_PERIOD    = int(getattr(config, "S14_RSI_PERIOD", 14))
WINDOW_NEEDED = S14_LOOKBACK + S14_PERIOD + 10   # >= min_bars ของ strategy (RSI/signal)
TP_EXTRA      = 200                               # bars เพิ่มสำหรับ HHLL TP lookup

UTC = timezone.utc

def ts_to_bkk(ts: int) -> datetime:
    return datetime.fromtimestamp(ts, tz=UTC) + timedelta(hours=config.TZ_OFFSET - config.MT5_SERVER_TZ)

def main():
    if not mt5.initialize():
        print("MT5 init failed:", mt5.last_error())
        return

    print(f"Symbol : {SYMBOL}")
    print(f"Window : {WINDOW_NEEDED} bars lookback per tick")
    print(f"S14_LL_USE_HHLL = {getattr(config,'S14_LL_USE_HHLL',False)}")
    print(f"S14_ENGULF = {getattr(config,'S14_ENGULF',True)}  S14_SWEEP = {getattr(config,'S14_SWEEP',True)}")
    print("-" * 64)

    # ดึงข้อมูลรวม = 800 แท่ง (~13h ย้อนหลัง) ครอบคลุม lookback + test range
    total_fetch = 800
    rates_raw = mt5.copy_rates_from_pos(SYMBOL, TF_VAL, 0, total_fetch)
    if rates_raw is None or len(rates_raw) == 0:
        print("copy_rates_from_pos failed:", mt5.last_error())
        mt5.shutdown()
        return

    bars = [
        {"time": int(r["time"]), "open": float(r["open"]),
         "high": float(r["high"]), "low": float(r["low"]),
         "close": float(r["close"])}
        for r in rates_raw
    ]

    # scan HHLL ครั้งเดียว (เหมือน bot จริง)
    hhll_swing.fetch_hhll(TF_NAME, SYMBOL)

    # debug: แสดง range ของ bars ที่ดึงมา
    bkk_first = ts_to_bkk(bars[0]["time"])
    bkk_last  = ts_to_bkk(bars[-1]["time"])
    print(f"Bars   : {len(bars)} bars  [{bkk_first.strftime('%H:%M')} - {bkk_last.strftime('%H:%M')} BKK]")
    print("-" * 64)

    found_any = False

    for i in range(WINDOW_NEEDED, len(bars)):
        bkk = ts_to_bkk(bars[i]["time"])
        h, m = bkk.hour, bkk.minute

        # กรองเฉพาะช่วง 12:29 - 13:20 BKK
        in_range = (h == 12 and m >= 29) or (h == 13 and m <= 20)
        if not in_range:
            continue

        # ส่ง bars เพิ่มสำหรับ TP (HHLL) + WINDOW_NEEDED สำหรับ RSI/signal
        tp_start = max(0, i - WINDOW_NEEDED - TP_EXTRA + 1)
        full_win = bars[tp_start : i + 1]
        result = strategy_14(full_win, tf=TF_NAME)

        o = bars[i]["open"]
        hi = bars[i]["high"]
        lo = bars[i]["low"]
        c  = bars[i]["close"]
        clr = "G" if c >= o else "R"
        time_str = bkk.strftime("%H:%M")

        sig = result.get("signal", "WAIT")

        if sig in ("BUY", "SELL", "MULTI"):
            found_any = True
            print(f"*** {time_str} [{clr}] O={o:.2f} H={hi:.2f} L={lo:.2f} C={c:.2f}  --> {sig}")
            orders = result.get("orders", [result]) if sig == "MULTI" else [result]
            for ord_ in orders:
                sp  = ord_.get("sub_pattern", "?").upper()
                src = ord_.get("ref_source", "?")
                ref = ord_.get("ref_low", ord_.get("ref_high", "?"))
                rsi_ref = ord_.get("rsi_at_ref", "?")
                rsi_rej = ord_.get("rsi_at_rej", "?")
                print(f"     [{sp}] {ord_['signal']}  entry={ord_['entry']}  sl={ord_['sl']}  tp={ord_['tp']}")
                print(f"     ref={ref}  src={src}  RSI_ref={rsi_ref}  RSI_reject={rsi_rej}")
        else:
            # --- debug verbose ทุกแท่งในช่วงเวลา ---
            period   = int(getattr(config, "S14_RSI_PERIOD", 14))
            applied  = str(getattr(config, "S14_RSI_APPLIED_PRICE", "close"))
            lookback = int(getattr(config, "S14_REVERSAL_LOOKBACK", 50))
            inner_w  = list(full_win[-(lookback + period + 5):])
            rsi_vals = _calc_rsi_values(inner_w, period=period, applied_price=applied)

            cur_o_w  = float(inner_w[-1]["open"])
            cur_c_w  = float(inner_w[-1]["close"])
            cur_l_w  = float(inner_w[-1]["low"])
            cur_h_w  = float(inner_w[-1]["high"])
            cur_rsi  = rsi_vals[-1]
            rsi_str  = f"{cur_rsi:.1f}" if cur_rsi is not None else "None"

            print(f"\n{'-'*70}")
            print(f"  {time_str} [{clr}]  O={o:.2f} H={hi:.2f} L={lo:.2f} C={c:.2f}  RSI={rsi_str}")

            # BUY side (bear reversals)
            rev_bear = _find_bear_reversals(inner_w)
            if rev_bear:
                # กรอง reversal bars ที่ห่าง >= 2 แท่งก่อน
                rej_idx_b = len(inner_w) - 1
                valid_bear = [i for i in rev_bear if rej_idx_b - i >= 2]
                # LL bar = reversal bar ที่ low ต่ำสุดในบรรดา valid bars
                ll_rev = min(valid_bear, key=lambda i: float(inner_w[i]["low"])) if valid_bear else None

                # รายการ reversal bars ทั้งหมด (แสดง 5 ล่าสุด, * = LL bar)
                rev_list = [(ts_to_bkk(inner_w[j]["time"]).strftime("%H:%M"),
                             float(inner_w[j]["low"]),
                             rsi_vals[j],
                             j == ll_rev) for j in sorted(rev_bear)[-5:]]
                rev_str = "  ".join(f"{'*' if is_ll else ''}{t}(L={l:.2f} RSI={f'{r:.1f}' if r is not None else 'N'})" for t,l,r,is_ll in rev_list)
                print(f"  [BUY reversal bars ({len(rev_bear)})] {rev_str}")

                if ll_rev is None:
                    print(f"  [BUY] reversal bars ทั้งหมดอยู่ใกล้เกินไป (< 2 แท่ง)")
                    print(f"  [BUY result]  WAIT")
                else:
                    ref_low  = float(inner_w[ll_rev]["low"])
                    ref_rsi  = rsi_vals[ll_rev]
                    ref_t    = ts_to_bkk(inner_w[ll_rev]["time"]).strftime("%H:%M")
                    ref_type = "engulf" if float(inner_w[ll_rev]["close"]) < float(inner_w[ll_rev-1]["low"]) else "rejection"
                    # pivot RSI (ใช้แท่งแดงที่ใกล้ที่สุด)
                    ref_rsi_p = _pivot_rsi_buy(inner_w, rsi_vals, ll_rev)
                    rej_rsi_p = _pivot_rsi_buy(inner_w, rsi_vals, rej_idx_b)
                    ref_rsi_tag = "" if ref_rsi_p == ref_rsi else f"[pivot<-{ts_to_bkk(inner_w[ll_rev-1]['time']).strftime('%H:%M')}]"
                    rej_rsi_tag = "" if rej_rsi_p == cur_rsi else f"[pivot<-{ts_to_bkk(inner_w[rej_idx_b-1]['time']).strftime('%H:%M')}]"
                    print(f"  [BUY LL ref] {ref_t} L={ref_low:.2f} RSI={f'{ref_rsi_p:.1f}'}{ref_rsi_tag}  ({ref_type})")

                    # ตรวจเงื่อนไขทีละขั้น (c1 = True เสมอ เพราะกรองแล้ว)
                    c2 = cur_l_w < ref_low
                    c3 = (rej_rsi_p is not None and ref_rsi_p is not None and rej_rsi_p > ref_rsi_p)
                    c4 = (rej_rsi_p is not None and rej_rsi_p < 50.0)
                    engulf_ok = c2 and cur_c_w < ref_low
                    sweep_ok  = c2 and cur_o_w > ref_low and cur_c_w >= ref_low

                    print(f"  [BUY checks]")
                    print(f"    low < ref_low : {'PASS' if c2 else 'FAIL'}  ({cur_l_w:.2f} < {ref_low:.2f})")
                    if c2:
                        print(f"      --> Engulf? close < ref_low: {'PASS' if engulf_ok else 'FAIL'}  ({cur_c_w:.2f} < {ref_low:.2f})")
                        print(f"      --> Sweep?  open>ref & close>=ref: {'PASS' if sweep_ok else 'FAIL'}  (O={cur_o_w:.2f}>{ref_low:.2f}, C={cur_c_w:.2f}>={ref_low:.2f})")
                    if rej_rsi_p is not None and ref_rsi_p is not None:
                        print(f"    RSI div (>)   : {'PASS' if c3 else 'FAIL'}  (rej={rej_rsi_p:.1f}{rej_rsi_tag} > ref={ref_rsi_p:.1f}{ref_rsi_tag})")
                        print(f"    RSI < 50      : {'PASS' if c4 else 'FAIL'}  ({rej_rsi_p:.1f})")
                    else:
                        print(f"    RSI           : None")
                    overall = c2 and c3 and c4 and (engulf_ok or sweep_ok)
                    if overall:
                        atr_n = min(14, len(inner_w))
                        atr_  = sum(float(r["high"]) - float(r["low"]) for r in inner_w[-atr_n:]) / atr_n
                        from config import SL_BUFFER
                        sl_  = round(cur_l_w - SL_BUFFER(atr_), 2)
                        entry_ = round(cur_c_w, 2)
                        tp_  = _tp_from_window(inner_w, "BUY", entry_, sl_)
                        print(f"  [BUY result]  ** SIGNAL **  entry={entry_}  sl={sl_}  tp={tp_}" if tp_ else f"  [BUY result]  WAIT (TP=None — ไม่มี swing high ใน window ที่ให้ RR>=1:1)")
                    elif c2 and c3 and c4:
                        print(f"  [BUY result]  WAIT (engulf/sweep ไม่ผ่าน)")
                    else:
                        print(f"  [BUY result]  WAIT")
            else:
                print(f"  [BUY] ไม่มี reversal bars ในช่วง lookback")

            # SELL side (bull reversals)
            rev_bull = _find_bull_reversals(inner_w)
            if rev_bull:
                # กรอง reversal bars ที่ห่าง >= 2 แท่งก่อน
                rej_idx_s = len(inner_w) - 1
                valid_bull = [i for i in rev_bull if rej_idx_s - i >= 2]
                # most recent reversal bar ในบรรดา valid bars
                latest_bull = max(valid_bull) if valid_bull else None

                # รายการ reversal bars ทั้งหมด (แสดง 5 ล่าสุด, * = selected ref)
                rev_list = [(ts_to_bkk(inner_w[j]["time"]).strftime("%H:%M"),
                             float(inner_w[j]["high"]),
                             rsi_vals[j],
                             j == latest_bull) for j in sorted(rev_bull)[-5:]]
                rev_str = "  ".join(f"{'*' if is_lat else ''}{t}(H={h:.2f} RSI={f'{r:.1f}' if r is not None else 'N'})" for t,h,r,is_lat in rev_list)
                print(f"  [SELL reversal bars ({len(rev_bull)})] {rev_str}")

                if latest_bull is None:
                    print(f"  [SELL] reversal bars ทั้งหมดอยู่ใกล้เกินไป (< 2 แท่ง)")
                    print(f"  [SELL result] WAIT")
                else:
                    ref_high = float(inner_w[latest_bull]["high"])
                    ref_t    = ts_to_bkk(inner_w[latest_bull]["time"]).strftime("%H:%M")
                    ref_type = "engulf" if float(inner_w[latest_bull]["close"]) > float(inner_w[latest_bull-1]["high"]) else "rejection"
                    # pivot RSI (ใช้แท่งเขียวที่ใกล้ที่สุด)
                    ref_rsi_p = _pivot_rsi_sell(inner_w, rsi_vals, latest_bull)
                    rej_rsi_p = _pivot_rsi_sell(inner_w, rsi_vals, rej_idx_s)
                    ref_rsi_tag = "" if ref_rsi_p == rsi_vals[latest_bull] else f"[pivot<-{ts_to_bkk(inner_w[latest_bull-1]['time']).strftime('%H:%M')}]"
                    rej_rsi_tag = "" if rej_rsi_p == cur_rsi else f"[pivot<-{ts_to_bkk(inner_w[rej_idx_s-1]['time']).strftime('%H:%M')}]"
                    print(f"  [SELL ref] {ref_t} H={ref_high:.2f} RSI={ref_rsi_p:.1f}{ref_rsi_tag}  ({ref_type})")

                    # ตรวจเงื่อนไขทีละขั้น (c1s = True เสมอ เพราะกรองแล้ว)
                    c2s = cur_h_w > ref_high
                    c3s = (rej_rsi_p is not None and ref_rsi_p is not None and rej_rsi_p < ref_rsi_p)
                    c4s = (rej_rsi_p is not None and rej_rsi_p > 50.0)
                    engulf_s = c2s and cur_c_w > ref_high
                    sweep_s  = c2s and cur_o_w < ref_high and cur_c_w <= ref_high
                    print(f"  [SELL checks]")
                    print(f"    high > ref_h  : {'PASS' if c2s else 'FAIL'}  ({cur_h_w:.2f} > {ref_high:.2f})")
                    if c2s:
                        print(f"      --> Engulf? close > ref_high: {'PASS' if engulf_s else 'FAIL'}  ({cur_c_w:.2f} > {ref_high:.2f})")
                        print(f"      --> Sweep?  open<ref & close<=ref: {'PASS' if sweep_s else 'FAIL'}  (O={cur_o_w:.2f}<{ref_high:.2f}, C={cur_c_w:.2f}<={ref_high:.2f})")
                    if rej_rsi_p is not None and ref_rsi_p is not None:
                        print(f"    RSI div (<)   : {'PASS' if c3s else 'FAIL'}  (rej={rej_rsi_p:.1f}{rej_rsi_tag} < ref={ref_rsi_p:.1f}{ref_rsi_tag})")
                        print(f"    RSI > 50      : {'PASS' if c4s else 'FAIL'}  ({rej_rsi_p:.1f})")
                    overall_s = c2s and c3s and c4s and (engulf_s or sweep_s)
                    if overall_s:
                        atr_n = min(14, len(inner_w))
                        atr_  = sum(float(r["high"]) - float(r["low"]) for r in inner_w[-atr_n:]) / atr_n
                        from config import SL_BUFFER
                        sl_s  = round(cur_h_w + SL_BUFFER(atr_), 2)
                        entry_s = round(cur_c_w, 2)
                        tp_s  = _tp_from_window(inner_w, "SELL", entry_s, sl_s)
                        print(f"  [SELL result] ** SIGNAL **  entry={entry_s}  sl={sl_s}  tp={tp_s}" if tp_s else f"  [SELL result] WAIT (TP=None — ไม่มี swing low ใน window ที่ให้ RR>=1:1)")
                    elif c2s and c3s and c4s:
                        print(f"  [SELL result] WAIT (engulf/sweep ไม่ผ่าน)")
                    else:
                        print(f"  [SELL result] WAIT")
            else:
                print(f"  [SELL] ไม่มี reversal bars ในช่วง lookback")

    if not found_any:
        print("\n(ไม่พบ S14 signal ในช่วงเวลานี้)")

    mt5.shutdown()

if __name__ == "__main__":
    main()
