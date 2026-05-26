"""
sim_s14_backtest.py — จำลอง S14 (Sweep RSI) ทุก TF ตั้งแต่ 24-05-2026
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')

import MetaTrader5 as mt5
from datetime import datetime, timezone, timedelta
import config
from strategy14 import strategy_14

SYMBOL       = config.SYMBOL
SINCE        = datetime(2026, 5, 24, 0, 0, 0, tzinfo=timezone.utc)
VOLUME       = 0.01     # lot size สำหรับคำนวณ P&L
# XAUUSD: 1 pip (0.01) = $1.00 per 1 lot → 0.01 lot = $0.01 per pip
# price diff 1.0 = 100 pips × $0.01 = $1.00 per 0.01 lot ✓
PRICE_TO_USD = 100 * VOLUME   # price_diff × PRICE_TO_USD = profit USD

S14_LOOKBACK  = int(getattr(config, 'S14_REVERSAL_LOOKBACK', 50))
S14_PERIOD    = int(getattr(config, 'S14_RSI_PERIOD', 14))
WINDOW_NEEDED = S14_LOOKBACK + S14_PERIOD + 15
TP_EXTRA      = 300

UTC = timezone.utc
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

# ดึง bars มากกว่า SINCE เพื่อให้ได้ lookback ก่อนเริ่ม
TF_EXTRA_BARS = {
    'M1': 2000, 'M5': 500, 'M15': 300,
    'M30': 200, 'H1': 150, 'H4': 100,
}

def to_bkk(ts: int) -> datetime:
    return datetime.fromtimestamp(ts, tz=UTC) + timedelta(hours=TZ_OFF - SRV_TZ)

def profit(price_diff: float) -> float:
    return round(price_diff * PRICE_TO_USD, 2)

def backtest_tf(tf_name: str, tf_val: int) -> list:
    extra = TF_EXTRA_BARS.get(tf_name, 200)
    total = 5000 + extra

    # ดึง bars จาก MT5 โดยเริ่ม from_pos=0 (newest first internally)
    rates = mt5.copy_rates_from_pos(SYMBOL, tf_val, 0, total)
    if rates is None or len(rates) == 0:
        return []

    bars = [
        {'time': int(r['time']), 'open': float(r['open']),
         'high': float(r['high']), 'low': float(r['low']),
         'close': float(r['close'])}
        for r in rates
    ]

    since_ts = int(SINCE.timestamp())

    # หา start_idx = bar แรกที่ >= SINCE และ >= WINDOW_NEEDED
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
        b    = bars[i]
        bt   = to_bkk(b['time'])

        # ── ตรวจ exit ก่อน (ใช้ high/low ของแท่งปัจจุบัน) ──
        if in_trade:
            sig = in_trade['signal']
            h, l = b['high'], b['low']
            if sig == 'BUY':
                if l <= in_trade['sl']:
                    pnl = profit(in_trade['sl'] - in_trade['entry'])
                    trades.append({**in_trade, 'close_type': 'SL',
                                   'close_price': in_trade['sl'], 'close_time': bt, 'pnl': pnl})
                    in_trade = None
                elif h >= in_trade['tp']:
                    pnl = profit(in_trade['tp'] - in_trade['entry'])
                    trades.append({**in_trade, 'close_type': 'TP',
                                   'close_price': in_trade['tp'], 'close_time': bt, 'pnl': pnl})
                    in_trade = None
            else:  # SELL
                if h >= in_trade['sl']:
                    pnl = profit(in_trade['entry'] - in_trade['sl'])
                    trades.append({**in_trade, 'close_type': 'SL',
                                   'close_price': in_trade['sl'], 'close_time': bt, 'pnl': pnl})
                    in_trade = None
                elif l <= in_trade['tp']:
                    pnl = profit(in_trade['entry'] - in_trade['tp'])
                    trades.append({**in_trade, 'close_type': 'TP',
                                   'close_price': in_trade['tp'], 'close_time': bt, 'pnl': pnl})
                    in_trade = None

        # ── ถ้ายังอยู่ใน trade → ข้ามการหา signal ใหม่ ──
        if in_trade:
            continue

        # ── รัน strategy_14 ──
        tp_start = max(0, i - WINDOW_NEEDED - TP_EXTRA + 1)
        full_win  = bars[tp_start:i + 1]
        result    = strategy_14(full_win, tf=tf_name)

        sig = result.get('signal', 'WAIT')
        orders = result.get('orders', [result]) if sig == 'MULTI' else ([result] if sig in ('BUY', 'SELL') else [])

        for ord_ in orders:
            s = ord_.get('signal')
            e = ord_.get('entry')
            sl = ord_.get('sl')
            tp = ord_.get('tp')
            if s in ('BUY', 'SELL') and e and sl and tp:
                in_trade = {
                    'signal': s, 'entry': e, 'sl': sl, 'tp': tp,
                    'entry_time': bt,
                    'pattern': ord_.get('sub_pattern', '?'),
                }
                break

    # ── trade ที่ยังเปิดอยู่ → ปิดที่ last close ──
    if in_trade and bars:
        lc  = bars[-1]['close']
        lt  = to_bkk(bars[-1]['time'])
        sig = in_trade['signal']
        pnl = profit(lc - in_trade['entry']) if sig == 'BUY' else profit(in_trade['entry'] - lc)
        trades.append({**in_trade, 'close_type': 'OPEN', 'close_price': lc, 'close_time': lt, 'pnl': pnl})

    return trades


def main():
    if not mt5.initialize():
        print('MT5 init failed:', mt5.last_error())
        return

    print(f'Symbol : {SYMBOL}')
    print(f'Since  : {SINCE.strftime("%d-%m-%Y")}  Volume: {VOLUME} lot')
    print(f'S14 settings: lookback={S14_LOOKBACK}  rsi_period={S14_PERIOD}')
    print(f'  ENGULF={getattr(config,"S14_ENGULF",True)}  SWEEP={getattr(config,"S14_SWEEP",True)}')
    print('=' * 65)

    grand_total = 0.0
    all_trades  = []

    for tf_name, tf_val in TF_MAP.items():
        trades = backtest_tf(tf_name, tf_val)
        all_trades.extend([(tf_name, t) for t in trades])

        if not trades:
            print(f'\n{tf_name}: ไม่พบ signal')
            continue

        tp_cnt  = sum(1 for t in trades if t['close_type'] == 'TP')
        sl_cnt  = sum(1 for t in trades if t['close_type'] == 'SL')
        op_cnt  = sum(1 for t in trades if t['close_type'] == 'OPEN')
        total   = sum(t['pnl'] for t in trades)
        wr      = tp_cnt / (tp_cnt + sl_cnt) * 100 if (tp_cnt + sl_cnt) > 0 else 0
        grand_total += total

        print(f'\n── {tf_name} ─────────────────────────────────────────')
        print(f'   trades={len(trades)}  TP={tp_cnt}  SL={sl_cnt}  OPEN={op_cnt}  WR={wr:.0f}%')
        print(f'   P&L total: {"+" if total>=0 else ""}{total:.2f} USD')

        # แสดง trade list
        for t in trades:
            dt  = t['entry_time'].strftime('%d-%m %H:%M')
            ct  = t['close_time'].strftime('%H:%M') if t['close_type'] != 'OPEN' else 'OPEN'
            pnl_s = f'{"+" if t["pnl"]>=0 else ""}{t["pnl"]:.2f}'
            print(f'   {dt} {t["signal"]:<4} E={t["entry"]:.2f} SL={t["sl"]:.2f} TP={t["tp"]:.2f} '
                  f'→ {t["close_type"]:<4} @ {t.get("close_price", 0):.2f} [{ct}]  {pnl_s} USD  [{t["pattern"]}]')

    print('\n' + '=' * 65)
    print(f'GRAND TOTAL: {"+" if grand_total>=0 else ""}{grand_total:.2f} USD  (ทุก TF รวมกัน, volume={VOLUME} lot each)')

    # สรุปแบบตาราง
    print('\n── สรุปตาม TF ─────────────────────────────────────────────')
    print(f'{"TF":<6} {"Trades":>7} {"TP":>5} {"SL":>5} {"WR%":>6} {"P&L":>10}')
    print('-' * 45)
    for tf_name in TF_MAP:
        tf_trades = [t for n, t in all_trades if n == tf_name]
        if not tf_trades:
            print(f'{tf_name:<6} {"0":>7}')
            continue
        tp = sum(1 for t in tf_trades if t['close_type'] == 'TP')
        sl = sum(1 for t in tf_trades if t['close_type'] == 'SL')
        wr = tp / (tp + sl) * 100 if (tp + sl) > 0 else 0
        pnl = sum(t['pnl'] for t in tf_trades)
        print(f'{tf_name:<6} {len(tf_trades):>7} {tp:>5} {sl:>5} {wr:>5.0f}% {pnl:>+10.2f}')
    print('-' * 45)
    print(f'{"TOTAL":<6} {len(all_trades):>7} '
          f'{sum(1 for _,t in all_trades if t["close_type"]=="TP"):>5} '
          f'{sum(1 for _,t in all_trades if t["close_type"]=="SL"):>5} '
          f'{"":>6} {grand_total:>+10.2f}')

    mt5.shutdown()

if __name__ == '__main__':
    main()
