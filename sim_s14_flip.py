"""
sim_s14_flip.py — จำลอง S14 พร้อม Flip Logic (ไม่มี filter)
เมื่อ signal ตรงข้ามมาบน TF เดิมขณะอยู่ใน trade → ปิดตัวเก่า เปิดใหม่ทันที
ตั้งแต่ 24-05-2026 ถึงปัจจุบัน ทุก TF
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')

import MetaTrader5 as mt5
from datetime import datetime, timezone, timedelta
import config
from strategy14 import strategy_14

# ─── Config ───────────────────────────────────────────────────────────────────
SYMBOL        = config.SYMBOL
SINCE         = datetime(2026, 5, 24, 0, 0, 0, tzinfo=timezone.utc)
VOLUME        = 0.01
PRICE_TO_USD  = 100 * VOLUME   # XAUUSD: price_diff × 100 × lot = USD

S14_LOOKBACK  = int(getattr(config, 'S14_REVERSAL_LOOKBACK', 50))
S14_PERIOD    = int(getattr(config, 'S14_RSI_PERIOD', 14))
WINDOW_NEEDED = S14_LOOKBACK + S14_PERIOD + 15
TP_EXTRA      = 300

UTC    = timezone.utc
TZ_OFF = getattr(config, 'TZ_OFFSET', 7)
SRV_TZ = getattr(config, 'MT5_SERVER_TZ', 0)

TF_MAP = {
    'M1':  mt5.TIMEFRAME_M1,
    'M5':  mt5.TIMEFRAME_M5,
    'M15': mt5.TIMEFRAME_M15,
    'M30': mt5.TIMEFRAME_M30,
    'H1':  mt5.TIMEFRAME_H1,
    'H4':  mt5.TIMEFRAME_H4,
}
TF_EXTRA_BARS = {'M1': 2000, 'M5': 500, 'M15': 300, 'M30': 200, 'H1': 150, 'H4': 100}

# ─── Helpers ──────────────────────────────────────────────────────────────────
def to_bkk(ts: int) -> datetime:
    return datetime.fromtimestamp(ts, tz=UTC) + timedelta(hours=TZ_OFF - SRV_TZ)

def pnl_calc(signal: str, entry: float, close: float) -> float:
    diff = (close - entry) if signal == 'BUY' else (entry - close)
    return round(diff * PRICE_TO_USD, 2)


# ─── Backtest per TF (with flip logic) ───────────────────────────────────────
def backtest_tf(tf_name: str, tf_val: int) -> list:
    """
    Flip rule:
    - ถ้า in_trade BUY และ signal ใหม่เป็น SELL → ปิด BUY ที่ราคา close ของแท่งนั้น
      แล้วเปิด SELL ทันที (market order จำลอง)
    - และกลับกัน
    """
    extra = TF_EXTRA_BARS.get(tf_name, 200)
    rates = mt5.copy_rates_from_pos(SYMBOL, tf_val, 0, 5000 + extra)
    if rates is None or len(rates) == 0:
        return []

    bars = [{'time': int(r['time']), 'open': float(r['open']),
             'high': float(r['high']), 'low': float(r['low']),
             'close': float(r['close'])} for r in rates]

    since_ts  = int(SINCE.timestamp())
    start_idx = None
    for i, b in enumerate(bars):
        if b['time'] >= since_ts and i >= WINDOW_NEEDED + TP_EXTRA:
            start_idx = i
            break
    if start_idx is None:
        return []

    trades   = []
    in_trade = None  # {'signal','entry','sl','tp','entry_time','pattern'}

    for i in range(start_idx, len(bars)):
        b  = bars[i]
        bt = to_bkk(b['time'])
        h, l, c = b['high'], b['low'], b['close']

        # ── ตรวจ SL/TP exit ก่อน (ก่อนตรวจ signal ใหม่) ──
        if in_trade:
            sig = in_trade['signal']
            if sig == 'BUY':
                if l <= in_trade['sl']:
                    trades.append({**in_trade, 'close_type': 'SL',
                                   'close_price': in_trade['sl'], 'close_time': bt,
                                   'pnl': pnl_calc('BUY', in_trade['entry'], in_trade['sl'])})
                    in_trade = None
                elif h >= in_trade['tp']:
                    trades.append({**in_trade, 'close_type': 'TP',
                                   'close_price': in_trade['tp'], 'close_time': bt,
                                   'pnl': pnl_calc('BUY', in_trade['entry'], in_trade['tp'])})
                    in_trade = None
            else:  # SELL
                if h >= in_trade['sl']:
                    trades.append({**in_trade, 'close_type': 'SL',
                                   'close_price': in_trade['sl'], 'close_time': bt,
                                   'pnl': pnl_calc('SELL', in_trade['entry'], in_trade['sl'])})
                    in_trade = None
                elif l <= in_trade['tp']:
                    trades.append({**in_trade, 'close_type': 'TP',
                                   'close_price': in_trade['tp'], 'close_time': bt,
                                   'pnl': pnl_calc('SELL', in_trade['entry'], in_trade['tp'])})
                    in_trade = None

        # ── ดึง signal ──
        tp_start = max(0, i - WINDOW_NEEDED - TP_EXTRA + 1)
        result   = strategy_14(bars[tp_start:i + 1], tf=tf_name)

        sig    = result.get('signal', 'WAIT')
        orders = (result.get('orders', [result]) if sig == 'MULTI'
                  else ([result] if sig in ('BUY', 'SELL') else []))

        new_trade = None
        for ord_ in orders:
            s  = ord_.get('signal')
            e  = ord_.get('entry')
            sl = ord_.get('sl')
            tp = ord_.get('tp')
            if not (s in ('BUY', 'SELL') and e and sl and tp):
                continue
            new_trade = {'signal': s, 'entry': e, 'sl': sl, 'tp': tp,
                         'entry_time': bt, 'pattern': ord_.get('sub_pattern', '?')}
            break

        if new_trade is None:
            continue  # ไม่มี signal ใหม่

        # ── Flip logic ──
        if in_trade and in_trade['signal'] != new_trade['signal']:
            # ปิดตัวเก่าที่ราคา close ของแท่งนี้ (market order จำลอง)
            flip_pnl = pnl_calc(in_trade['signal'], in_trade['entry'], c)
            trades.append({**in_trade, 'close_type': 'FLIP',
                           'close_price': c, 'close_time': bt, 'pnl': flip_pnl})
            in_trade = None

        # เปิด trade ใหม่ (ถ้าไม่มี trade อยู่แล้วฝั่งเดียวกัน)
        if in_trade is None:
            in_trade = new_trade

    # ── trade ที่เปิดค้างอยู่ → ปิดที่ last bar close ──
    if in_trade and bars:
        lc = bars[-1]['close']
        lt = to_bkk(bars[-1]['time'])
        trades.append({**in_trade, 'close_type': 'OPEN',
                       'close_price': lc, 'close_time': lt,
                       'pnl': pnl_calc(in_trade['signal'], in_trade['entry'], lc)})

    return trades


# ─── Main ─────────────────────────────────────────────────────────────────────
def main():
    if not mt5.initialize():
        print('MT5 init failed:', mt5.last_error())
        return

    print(f'Symbol : {SYMBOL}')
    print(f'Since  : {SINCE.strftime("%d-%m-%Y")}  Volume: {VOLUME} lot')
    print(f'Filters: ไม่มี (raw)   Flip: ✓ (ปิดตัวเก่าเมื่อ signal ตรงข้ามมา)')
    print('=' * 70)

    grand_total  = 0.0
    summary_rows = []

    for tf_name, tf_val in TF_MAP.items():
        trades = backtest_tf(tf_name, tf_val)

        tp_cnt   = sum(1 for t in trades if t['close_type'] == 'TP')
        sl_cnt   = sum(1 for t in trades if t['close_type'] == 'SL')
        flip_cnt = sum(1 for t in trades if t['close_type'] == 'FLIP')
        op_cnt   = sum(1 for t in trades if t['close_type'] == 'OPEN')
        total    = sum(t['pnl'] for t in trades)
        wr       = tp_cnt / (tp_cnt + sl_cnt) * 100 if (tp_cnt + sl_cnt) > 0 else 0
        grand_total += total

        summary_rows.append((tf_name, len(trades), tp_cnt, sl_cnt, flip_cnt, op_cnt, wr, total))

        if not trades:
            print(f'\n{tf_name}: ไม่พบ signal')
            continue

        print(f'\n── {tf_name} ─────────────────────────────────────────────')
        print(f'   trades={len(trades)}  TP={tp_cnt}  SL={sl_cnt}  FLIP={flip_cnt}  OPEN={op_cnt}  WR={wr:.0f}%')
        print(f'   P&L: {"+" if total>=0 else ""}{total:.2f} USD')

        for t in trades:
            dt    = t['entry_time'].strftime('%d-%m %H:%M')
            ct    = t['close_time'].strftime('%H:%M') if t['close_type'] != 'OPEN' else 'OPEN'
            pnl_s = f'{"+" if t["pnl"]>=0 else ""}{t["pnl"]:.2f}'
            ctype = t['close_type']
            icon  = '🎯' if ctype=='TP' else ('🛑' if ctype=='SL' else ('↔️' if ctype=='FLIP' else '⏳'))
            print(f'   {dt} {t["signal"]:<4} E={t["entry"]:.2f} SL={t["sl"]:.2f} TP={t["tp"]:.2f}'
                  f' → {icon}{ctype:<4} @ {t.get("close_price",0):.2f}'
                  f' [{ct}]  {pnl_s} USD  [{t["pattern"]}]')

    print('\n' + '=' * 70)
    print(f'GRAND TOTAL: {"+" if grand_total>=0 else ""}{grand_total:.2f} USD  '
          f'(volume={VOLUME} lot each TF)')

    print('\n── สรุปตาม TF ──────────────────────────────────────────────────────')
    print(f'{"TF":<6} {"Trades":>7} {"TP":>5} {"SL":>5} {"FLIP":>5} {"WR%":>6} {"P&L":>10}')
    print('-' * 52)
    for row in summary_rows:
        tf_name, n, tp, sl, flip, op, wr, pnl = row
        print(f'{tf_name:<6} {n:>7} {tp:>5} {sl:>5} {flip:>5} {wr:>5.0f}% {pnl:>+10.2f}')
    print('-' * 52)
    tp_tot   = sum(r[2] for r in summary_rows)
    sl_tot   = sum(r[3] for r in summary_rows)
    flip_tot = sum(r[4] for r in summary_rows)
    n_tot    = sum(r[1] for r in summary_rows)
    print(f'{"TOTAL":<6} {n_tot:>7} {tp_tot:>5} {sl_tot:>5} {flip_tot:>5} {"":>6} {grand_total:>+10.2f}')

    print('\n── เปรียบเทียบกับ raw (ไม่มี flip) ─────────────────────────────────')
    print(f'  Raw (sim_s14_backtest):  52 trades  +124.63 USD')
    print(f'  Flip (sim_s14_flip):     {n_tot} trades  {"+" if grand_total>=0 else ""}{grand_total:.2f} USD')

    mt5.shutdown()


if __name__ == '__main__':
    main()
