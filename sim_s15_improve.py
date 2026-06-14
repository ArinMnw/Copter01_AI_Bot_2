"""Sim: S15 ก่อน/หลัง trend filter + cooldown — ใช้ rates จริงจาก MT5"""
import glob, re, os, sys
from datetime import datetime, timedelta
import MetaTrader5 as mt5
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import config
from config import SYMBOL

mt5.initialize()

TF_MAP = {"M1": mt5.TIMEFRAME_M1, "M5": mt5.TIMEFRAME_M5, "M15": mt5.TIMEFRAME_M15,
          "M30": mt5.TIMEFRAME_M30, "H1": mt5.TIMEFRAME_H1}

def _ema(values, period):
    if not values: return None
    k = 2.0/(period+1.0); e = values[0]
    for v in values[1:]: e = v*k + e*(1.0-k)
    return e

log_dir = 'logs'
def log_files():
    from log_sources import bot_log_files
    return bot_log_files()

def fld(line, key):
    m = re.search(rf'{key}=([^|\s]+)', line); return m.group(1).strip() if m else None

# parse S15 closed orders
orders = {}; seen = set()
for path in log_files():
    try:
        for line in open(path, encoding='utf-8', errors='replace'):
            m = re.match(r'^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]\s+(\S+)', line)
            if not m: continue
            ts, kind = m.group(1), m.group(2)
            tk = fld(line,'ticket')
            if not tk or fld(line,'sid')!='15':
                if kind=='POSITION_CLOSED' and tk in orders: pass
                else: continue
            if kind=='ORDER_CREATED':
                orders[tk]={'ts':ts,'side':fld(line,'signal'),'tf':fld(line,'tf'),
                            'entry':float(fld(line,'entry') or 0),'profit':None}
            elif kind=='POSITION_CLOSED' and tk in orders and tk not in seen and 'XAUUSD' in line:
                seen.add(tk); orders[tk]['profit']=float(fld(line,'profit') or 0)
    except: pass

closed = [v for v in orders.values() if v['profit'] is not None and v['tf'] in TF_MAP]
print(f"S15 closed orders (TF supported): {len(closed)}")

BKK_OFFSET = 1  # fetch +1h ตาม timezone rule
ema_period = 50
neutral_atr_mult = 0.1
cooldown_bars = 15

def calc_atr_simple(rates, period=14):
    trs=[]
    for i in range(1,len(rates)):
        h=rates[i]['high']; l=rates[i]['low']; pc=rates[i-1]['close']
        trs.append(max(h-l, abs(h-pc), abs(l-pc)))
    if len(trs)<period: return sum(trs)/len(trs) if trs else 0
    atr=sum(trs[:period])/period
    for i in range(period,len(trs)): atr=(trs[i]+(period-1)*atr)/period
    return atr

# replay with cooldown state
last_fire={}
kept=[]; blocked_trend=0; blocked_cd=0
for o in sorted(closed, key=lambda x:x['ts']):
    tf=o['tf']; side=o['side']; entry=o['entry']
    dt = datetime.strptime(o['ts'],'%Y-%m-%d %H:%M:%S') + timedelta(hours=BKK_OFFSET)
    rates = mt5.copy_rates_from(SYMBOL, TF_MAP[tf], dt, ema_period*3+5)
    if rates is None or len(rates) < ema_period+5:
        kept.append(o); continue
    closes=[float(r['close']) for r in rates]
    cur_close=closes[-1]
    ema=_ema(closes[-(ema_period*3):], ema_period)
    atr=calc_atr_simple(rates)
    band=atr*neutral_atr_mult
    # trend filter
    allow = True
    if ema is not None:
        if side=='BUY' and cur_close < ema-band: allow=False
        elif side=='SELL' and cur_close > ema+band: allow=False
    if not allow:
        blocked_trend+=1; continue
    # cooldown
    bar_time=int(rates[-1]['time'])
    tf_secs={'M1':60,'M5':300,'M15':900,'M30':1800,'H1':3600}[tf]
    key=(tf,side,round(entry,1))
    if bar_time - last_fire.get(key,0) < cooldown_bars*tf_secs:
        blocked_cd+=1; continue
    last_fire[key]=bar_time
    kept.append(o)

old_pl=sum(o['profit'] for o in closed)
new_pl=sum(o['profit'] for o in kept)
old_win=sum(1 for o in closed if o['profit']>0)
new_win=sum(1 for o in kept if o['profit']>0)

print()
print("="*60)
print("  S15: ก่อน vs หลัง (trend filter + cooldown)")
print("="*60)
print(f"  {'':20} {'BEFORE':>12} {'AFTER':>12}")
print(f"  {'Orders':20} {len(closed):>12} {len(kept):>12}")
print(f"  {'P/L':20} {old_pl:>12.2f} {new_pl:>12.2f}")
print(f"  {'Win rate':20} {100*old_win/len(closed):>11.0f}% {100*new_win/max(1,len(kept)):>11.0f}%")
print(f"  {'Blocked by trend':20} {'':>12} {blocked_trend:>12}")
print(f"  {'Blocked by cooldown':20} {'':>12} {blocked_cd:>12}")
print(f"\n  DIFF: {new_pl-old_pl:+.2f} USD")
print()
# kept orders detail
print("  เหลือ orders:")
for o in kept:
    print(f"    {o['ts']} {o['side']:4} {o['tf']:4} entry={o['entry']} P/L={o['profit']:.2f}")

mt5.shutdown()
