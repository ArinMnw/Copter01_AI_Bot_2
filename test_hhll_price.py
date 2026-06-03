"""ทดสอบ price violation check บน M30"""
import hhll_swing, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import MetaTrader5 as mt5
from datetime import datetime, timedelta
mt5.initialize()

hhll_swing.fetch_hhll('M30')
d = hhll_swing.get_hhll_data('M30')

def fmt(v):
    if not v: return 'None'
    ts = datetime.utcfromtimestamp(v['time']) + timedelta(hours=7)
    return f"price={v['price']:8.2f}  {ts.strftime('%H:%M %d-%m')}  label={v['label']}"

print("=== M30 HHLL ===")
print(f"  HH     : {fmt(d.get('hh'))}")
print(f"  HL     : {fmt(d.get('hl'))}")
print(f"  LH     : {fmt(d.get('lh'))}")
print(f"  LL     : {fmt(d.get('ll'))}")
print()
print("--- prev ---")
print(f"  prev_HH: {fmt(d.get('prev_hh'))}")
print(f"  prev_HL: {fmt(d.get('prev_hl'))}")
print(f"  prev_LH: {fmt(d.get('prev_lh'))}")
print(f"  prev_LL: {fmt(d.get('prev_ll'))}")
print()
print(f"Structure (latest): {d.get('structure')}")
print()

viol  = hhll_swing._check_price_violation('M30')
trend = hhll_swing.get_trend_from_structure('M30')
print(f"Price violation : {viol}")
print(f"Trend (label)   : {d.get('structure', [])[:2]}")
print(f"Trend (result)  : {trend}")

mt5.shutdown()
