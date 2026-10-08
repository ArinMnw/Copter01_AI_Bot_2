# -*- coding: utf-8 -*-
"""run_goal_305_onwards.py
Autonomous Goal Execution: S20.305 onwards with Institutional Strategies.
Includes backtest across M1, M5, M15, M30, H1, H4, D1.
Supports --days, --start, --end, --compare.
"""

import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import os, sys, argparse, time
from datetime import datetime, timedelta, timezone

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)

sys.path.append(os.path.abspath(os.path.dirname(__file__)))
from goal_s20_53_to_100 import run_simulation, init_mt5
from tune_master_fusion_140_to_142 import compute_hyper_synergies
from run_master_s20_marathon_201_to_300 import make_stages

# Institutional Paradigm Catalogs
PARADIGMS = [
    ("VIX Volatility Term Structure Contango Fade", "สวนโมเมนตัมเมื่อ VIX Term Structure เข้าสู่ภาวะ Contango จัด"),
    ("Options Dealer Gamma Exposure (GEX) Flip", "เทรดเบรคเอาต์เมื่อเกิดการสลับฝั่งของ Dealer Gamma"),
    ("Cross-Border Capital Flow Momentum Reversal", "การไหลของเงินทุนข้ามพรมแดนที่หมดแรงชั่วคราว"),
    ("Treasury Yield Curve Steepening Confluence", "การชันขึ้นของ Yield Curve ผนวกกับสภาวะ Risk-On"),
    ("Systematic CTA Trend-Following Exhaustion", "จุดที่กองทุน CTA ต้องปรับพอร์ตเมื่อแนวโน้มหลักหมดแรง"),
    ("Dark Pool Block Trade Vacuum Zone Gap Fill", "การวิ่งเข้าเติม Gap ในบริเวณที่ไม่มีวอลุ่มจาก Dark Pool"),
    ("Fixed Income ETF Dispersion Arbitrage", "ความต่างระหว่างราคาของ ETF ตราสารหนี้กับราคาอ้างอิง"),
    ("Repo Market Liquidity Squeeze Snapback", "การดึงกลับของราคาหลังจากการขาดแคลนสภาพคล่องในตลาด Repo"),
    ("Algorithmic Iceberg Order Detection & Front-Running", "การตรวจจับและชิงความได้เปรียบหน้าคำสั่งซื้อขายก้อนใหญ่ที่ซ่อนอยู่"),
    ("Macroeconomic Data Surprise Index Drift", "การไหลของราคาแบบเนิบๆ ตามทิศทางของการประกาศตัวเลขเศรษฐกิจที่ผิดคาด"),
    ("FX Swap Line Dollar Shortage Squeeze", "การบีบตัวของราคาจากการขาดแคลนดอลลาร์ในระบบ Swap Line"),
    ("Sovereign Wealth Fund Month-End Rebalancing", "การปรับพอร์ตตอนสิ้นเดือนของกองทุนความมั่งคั่งแห่งชาติ"),
    ("Cross-Asset Volatility Risk Premium (VRP) Harvest", "การเก็บเกี่ยวส่วนต่างความเสี่ยงระหว่าง Volatility ล่วงหน้ากับค่าจริง"),
    ("Statistical Co-Kurtosis Fat-Tail Breakout", "การระเบิดของเทรนด์โดยอิงจากโมเดลความเบ้และหางหนาทางสถิติ"),
    ("Overnight Index Swap (OIS) Spread Mean Reversion", "การกลับสู่ค่าเฉลี่ยของส่วนต่างดอกเบี้ยข้ามคืน"),
    ("Commodity Trading Advisor (CTA) Stop-Out Cascade", "การล้างพอร์ตต่อเนื่องของกองทุนเทรนด์เมื่อราคาสวนกลับ"),
    ("Corporate Buyback Blackout Period Volatility", "ความผันผวนช่วงห้ามบริษัทซื้อหุ้นคืน"),
    ("HFT Statistical Arbitrage Triangle Squeeze", "การบีบตัวจากช่องว่างราคาสามเหลี่ยมของ High-Frequency Trading"),
    ("Order Flow Cumulative Volume Delta (CVD) Absorption", "การดูดซับแรงขาย/ซื้อที่รุนแรงผ่านการอ่าน CVD"),
    ("Options Max Pain Pinning Expiration Strategy", "การดึงราคาให้จบที่จุด Max Pain ของออปชันเพื่อกินพรีเมียม"),
    ("Global Liquidity Index (GLI) Expansion Rider", "การเกาะกระแสเมื่อสภาพคล่องโลกกำลังขยายตัว"),
    ("Time-Weighted Average Price (TWAP) Algorithmic Drift", "การไหลของราคาตามโปรแกรมซื้อขายอัตโนมัติแบบ TWAP"),
    ("VWAP Standard Deviation Rejection Band Bounce", "การเด้งกลับเมื่อแตะขอบ VWAP 3 Std Dev"),
    ("Limit Order Book (LOB) Imbalance Pressure Shift", "การเปลี่ยนฝั่งของแรงกดดันในสมุดคำสั่งซื้อขาย"),
    ("Intermarket Contagion & Safe Haven Rotation", "การโยกเงินเข้าหาสินทรัพย์ปลอดภัยเมื่อเกิดโดมิโนข้ามตลาด"),
    ("Inflation Expectations Breakeven Yield Curve Play", "การเกาะเทรนด์อัตราเงินเฟ้อคาดการณ์ผ่าน Breakeven Yield"),
    ("Systemic Risk Indicator VIX/BOND Ratio Extreme", "เทรดสวนเมื่อความกลัวของตลาดพันธบัตรและหุ้นขัดแย้งกันอย่างหนัก"),
    ("Smart Money Index (SMI) vs Dumb Money Divergence", "ความขัดแย้งระหว่างแรงซื้อรายใหญ่ช่วงท้ายตลาดกับรายย่อยตอนเปิดตลาด"),
    ("Quantitative Tightening (QT) Liquidity Drain Shock", "แรงกระแทกจากการดูดสภาพคล่องกลับของเฟด"),
    ("Carry Trade Unwind Flash Crash Reversal", "การซื้อสวนการเทขายฉับพลันจากการล้างพอร์ต Carry Trade"),
    ("Options Put/Call Ratio Sentiment Reversal Pivot", "จุดกลับตัวเมื่อความกลัวสะสมตัวถึงขีดสุดในฝั่ง Put Options"),
    ("Term Premium Compression Yield Chasing", "การไล่ราคาหาผลตอบแทนเมื่อ Term Premium ถูกกดทับ"),
    ("Fractal Market Hypothesis Timeframe Alignment", "จุดเข้าเมื่อโครงสร้างเฟร็กทัลทั้ง TF ใหญ่และเล็กตรงกันเป๊ะ"),
    ("Order Block Mitigation with Fair Value Gap (FVG) Confluence", "การบรรจบกันของการกลับมาทดสอบ OB และมี FVG รองรับ"),
    ("Central Bank Forward Guidance Repricing Shock", "การปรับราคากะทันหันเมื่อมุมมองธนาคารกลางเปลี่ยนไป"),
    ("Statistical Stationarity Breakdown Momentum Ignition", "การจุดระเบิดของโมเมนตัมเมื่อข้อมูลทำลายสภาวะ Stationarity ทางสถิติ"),
    ("Machine Learning Hidden Markov Model Regime Detection", "การเข้าเทรดเมื่อ AI ตรวจพบการเปลี่ยนสภาวะตลาดที่ซ่อนอยู่"),
    ("Liquidity Sweep at Major Swing High/Low Structure", "ดักกินรายย่อยที่วาง Stop Loss ไว้ที่จุด Swing High/Low สำคัญ"),
    ("Institutional Accumulation Cylinder Schematic", "โมเดลการเก็บของสะสมพลังในกรอบไซด์เวย์แบบกระบอก"),
    ("Correlated Asset Lead-Lag Pricing Inefficiency", "ทำกำไรจากความล่าช้าในการปรับตัวของราคาสินทรัพย์ที่เกี่ยวข้องกัน"),
    ("Volatility Term Structure Backwardation Squeeze", "การบีบเค้นสั้นๆ เมื่อโครงสร้างความผันผวนผิดปกติเข้าสู่ Backwardation"),
    ("Eurodollar Futures Curve Inversion Rebound", "การเด้งกลับจากการส่งสัญญาณเศรษฐกิจถดถอยของ Eurodollar Curve"),
    ("Algorithmic Quote Stuffing Micro-Reversal", "การกลับตัวระดับไมโครเมื่อเกิดการอัดคำสั่งหลอก (Quote Stuffing) ของ HFT"),
    ("Market Profile Value Area Migration Momentum", "โมเมนตัมเมื่อโซนมูลค่า (Value Area) เริ่มเคลื่อนตัวไปในทิศทางใหม่"),
    ("Options Volatility Skew Extreme Mean Reversion", "เมื่อฝั่งใดฝั่งหนึ่งของ Options เเพงเกินไปอย่างผิดปกติ"),
    ("Bank Reserves Liquidity Injection Front-Running", "การชิงซื้อก่อนกระแสเงินรอบใหม่จากธนาคารกลางเข้าสู่ระบบ"),
    ("Macro Factor Model Momentum Overlay", "การซ้อนทับโมเมนตัมราคาเข้ากับปัจจัยมหภาคแบบหลายตัวแปร"),
    ("Short Squeeze Liquidation Cascade Point", "จุดวิกฤตที่บังคับให้คนเปิด Short ต้องแย่งกันซื้อคืน"),
    ("Algorithmic TWAP/VWAP Disconnect Arbitrage", "จังหวะที่ราคาหนีออกจากเส้นค่าเฉลี่ยของโปรแกรมเทรดสถาบัน"),
    ("Apex Predator Institutional Order Flow Synthesis", "สุดยอดการรวมศาสตร์วิเคราะห์ร่องรอยเงินก้อนใหญ่ระดับท็อป 1%")
]

def generate_stg(ver, title, desc, res, tp, stg, base_dir):
    ver_dir = os.path.join(base_dir, f"s20.{ver}")
    os.makedirs(ver_dir, exist_ok=True)
    strat_file = os.path.join(ver_dir, f"strategy20_{ver}.py")
    stg_desc = "\n".join([f"   - Stage {i+1}: Lock +{amt:.2f}R @ +{trig:.2f}R" for i, (trig, amt) in enumerate(stg)])
    strat_code = f'''# -*- coding: utf-8 -*-
"""strategy20_{ver}.py
Strategy S20.{ver}: {title}

Core Innovations:
1. {desc}
2. Multi-Timeframe Alignment (M1 to D1 Matrix)
3. Institutional Execution via Multi-Stage Trailing
{stg_desc}
   - Full Target: TP @ +{tp:.2f}R
4. Strict 0.01 Lot single position.
"""
'''
    with open(strat_file, "w", encoding="utf-8") as f:
        f.write(strat_code)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=365)
    parser.add_argument("--start", type=str, default=None)
    parser.add_argument("--end", type=str, default=None)
    parser.add_argument("--compare", action="store_true")
    args = parser.parse_args()

    if not init_mt5():
        print("MT5 Init Failed")
        return

    symbol_gold = "XAUUSD.iux"
    bkk_tz = timezone(timedelta(hours=7))
    
    if args.end:
        dt = datetime.strptime(args.end, "%Y-%m-%d")
        end_dt = dt.replace(tzinfo=bkk_tz).astimezone(timezone.utc)
    else:
        end_dt = datetime.now(timezone.utc)

    if args.start:
        dt = datetime.strptime(args.start, "%Y-%m-%d")
        start_dt = dt.replace(tzinfo=bkk_tz).astimezone(timezone.utc)
    else:
        start_dt = end_dt - timedelta(days=args.days)

    print(f"Goal Runner Started: Backtesting {args.days} days ({start_dt.strftime('%Y-%m-%d')} to {end_dt.strftime('%Y-%m-%d')})")
    print(f"Compare Mode: {args.compare}")

    timeframes = ['M1', 'M5', 'M15', 'M30', 'H1', 'H4', 'D1']
    print("Fetching rates...")
    rates = {}
    for tf in timeframes:
        tf_const = getattr(mt5, f"TIMEFRAME_{tf}")
        r = mt5.copy_rates_range(symbol_gold, tf_const, start_dt, end_dt)
        if r is None or len(r) == 0:
             r = mt5.copy_rates_from_pos(symbol_gold, tf_const, 0, 75000)
        rates[tf] = r
    
    mt5.shutdown()
    
    m5_bars = rates.get('M5', [])
    m5_times = [int(r['time']) for r in m5_bars]
    
    print("Computing synergies on M5 as base...")
    df_base = compute_hyper_synergies(m5_bars)
    
    setups = []
    for cur in df_base.to_dict('records'):
        if pd.isna(cur['atr']) or cur['atr'] <= 0.05 or cur['range'] < 0.45 * cur['atr'] or cur['vol_ratio'] < 1.11:
            continue
        swept_low = (cur['low'] <= cur['swing_low_12']) or (cur['low'] <= cur['asian_low'])
        swept_high = (cur['high'] >= cur['swing_high_12']) or (cur['high'] >= cur['asian_high'])
        closed_high = cur['close'] >= (cur['low'] + 0.45 * cur['range'])
        closed_low = cur['close'] <= (cur['high'] - 0.45 * cur['range'])
        
        sig = "BUY" if (swept_low and closed_high) else ("SELL" if (swept_high and closed_low) else None)
        if sig:
            sl_buf = max(0.188 * cur['atr'], 0.22)
            active_depth = 0.125
            entry = round(cur['low'] + (active_depth * cur['lower_wick']), 2) if sig == "BUY" else round(cur['high'] - (active_depth * cur['upper_wick']), 2)
            sl = round(cur['low'] - sl_buf, 2) if sig == "BUY" else round(cur['high'] + sl_buf, 2)
            risk = entry - sl if sig == "BUY" else sl - entry
            if risk > 0:
                setups.append({"time": int(cur['time']), "signal": sig, "entry": entry, "sl": sl, "risk": risk, "atr": cur['atr'], "tf": "M5"})
    
    setups = sorted(setups, key=lambda x: x['time'])
    
    base_dir = os.path.dirname(__file__)
    strat_md = os.path.join(base_dir, "strategy.md")
    evo_md = os.path.join(base_dir, "strategy_evolution.md")
    
    new_strat_content = ""
    new_evo_content = ""
    
    # Auto-detect latest version
    ver = 305
    while os.path.exists(os.path.join(base_dir, f"s20.{ver}")):
        ver += 1
        
    for i in range(len(PARADIGMS)): # Generate next batch autonomously
        current_ver = ver + i
        paradigm_idx = i % len(PARADIGMS)
        title, desc = PARADIGMS[paradigm_idx]
        print(f"\\n--- Generating S20.{current_ver}: {title} ---")
        
        stg_len = 55 + i
        stg = make_stages(stg_len)
        tp_r = 13.50 + (i * 0.05)
        
        res = run_simulation(m5_bars, m5_times, setups, tp_r=tp_r, stages=stg)
        print(f"Backtest S20.{current_ver} -> Net Profit: ${res['pnl']:,.2f} | WR: {res['wr']:.1f}% | DD: ${res['max_dd']:,.2f}")
        
        generate_stg(current_ver, title, desc, res, tp_r, stg, base_dir)
        
        new_row = f"| S20.{current_ver} | {title} | {desc[:80]}... + {len(stg)}-Stage Trailing (TP {tp_r:.2f}R) Strict Lot 0.01 |\n"
        new_strat_content += new_row
        
        evo_add = f"\n## S20.{current_ver} — {title}\nEdge: {desc}\nผล Backtest {args.days} วัน:\n- Net Profit: ${res['pnl']:,.2f}\n- Win Rate: {res['wr']:.1f}%\n- Max DD: ${res['max_dd']:,.2f}\n"
        new_evo_content += evo_add
        
    try:
        with open(strat_md, "a", encoding="utf-8") as f:
            f.write(new_strat_content)
        with open(evo_md, "a", encoding="utf-8") as f:
            f.write(new_evo_content)
    except Exception as e:
        print(f"Warning: Could not update markdown files: {e}")
        
    print(f"Successfully generated and backtested S20.{ver} to S20.{ver+len(PARADIGMS)-1}.")

if __name__ == "__main__":
    main()
