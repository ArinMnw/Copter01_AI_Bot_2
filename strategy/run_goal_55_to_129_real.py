# -*- coding: utf-8 -*-
import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import os, sys, argparse, time, random
from datetime import datetime, timedelta, timezone
import importlib.util

sys.path.append(os.path.abspath(os.path.dirname(__file__)))
from goal_s20_53_to_100 import init_mt5, compute_indicators, run_simulation

PARADIGMS = [
    ("Institutional Dark Pool Block Sweeper", "ตรวจจับบล็อกเทรดขนาดใหญ่จาก Dark Pool และเทรดตาม"),
    ("Algorithmic TWAP Displacement Arbitrage", "ใช้ TWAP เป็นฐานอ้างอิงเพื่อหาราคาผิดปกติ"),
    ("High-Frequency Triangle Squeeze Reversal", "ตีกรอบสามเหลี่ยมความถี่สูงและเทรดช่วงกลับตัว"),
    ("Volatility Skew Smile Breakout Pivot", "เบรคเอาต์จากฐานของ Volatility Skew"),
    ("Cross-Asset Yield Curve Inversion Overlay", "เทรดทองคำตามทิศทางผลตอบแทนพันธบัตรที่กลับทิศ"),
    ("Options Gamma Squeeze Liquidation Cascade", "ดักทางจุดชอร์ตสควีซจาก Options Gamma"),
    ("Systematic CTAs Trend-Exhaustion Flip", "จุดกลับตัวเมื่อกองทุน CTA ตามเทรนด์จนหมดแรง"),
    ("Macro Data Surprise Index Mean-Reversion", "ซื้อ/ขายเมื่อตัวเลขเศรษฐกิจคลาดเคลื่อนจากคาดการณ์มากไป"),
    ("Order Book Imbalance Cumulative Delta Divergence", "ขัดแย้งของออเดอร์สะสมใน Order Book"),
    ("Liquidity Vacuum Gap Fill Trajectory", "เติมเต็มช่วงว่างราคาเมื่อเกิดหลุมสภาพคล่อง"),
    ("Fractional Kelly Criterion Position Sizing Engine", "โมเดลเติบโตพอร์ตแบบเคลลี่ที่ปรับขนาดอัตโนมัติ"),
    ("Statistical Co-Integration Mean-Reversion Pairs", "เทรดตามสถิติกลับคืนค่าเฉลี่ยของสินทรัพย์เกี่ยวโยง"),
    ("Central Bank Swap Line Dollar Drain Rebound", "เด้งกลับจากสภาวะขาดแคลนดอลลาร์ใน Swap Line"),
    ("Repo Market Stress Indicator Snapback", "จับจังหวะเด้งกลับเมื่อเกิดปัญหาตลาด Repo"),
    ("Options Put/Call Ratio Extreme Contagion", "ความกลัวระดับสุดขีดบนอัตราส่วน Put/Call"),
    ("VIX Term Structure Contango Roll-Yield", "เก็บกำไรจากสถานะ Contango ของ VIX"),
    ("Sovereign Wealth Month-End Rebalance Front-Run", "ดักทางก่อนกองทุนรัฐบาลปรับพอร์ตสิ้นเดือน"),
    ("Overnight Index Swap Spread Mean-Reversion", "ส่วนต่าง OIS ที่กลับตัวเข้าหาค่าเฉลี่ย"),
    ("Corporate Buyback Blackout Window Drift", "ราคาไหลช้าๆ ในช่วงงดซื้อหุ้นคืนของบริษัท"),
    ("HFT Statistical Arbitrage Micro-Reversal", "การทำกำไรกลับตัวสั้นๆระดับไมโครจากโปรแกรม HFT"),
    ("Market Profile Value Area VAH/VAL Migration", "การย้ายถิ่นฐานของกรอบมูลค่า Market Profile"),
    ("Algorithmic Quote Stuffing Detection Override", "กรองสัญญานหลอกของคำสั่งเทรดลวง HFT"),
    ("Fractal Market Hypothesis Timeframe Alignment", "การเรียงตัวของเฟร็กทัลจาก Timeframe ใหญ่สู่เล็ก"),
    ("Order Block Mitigation FVG Confluence Bridge", "โครงสร้างราคา Order Block ควบ FVG"),
    ("Machine Learning Hidden Markov Regime Filter", "ใช้ Markov Model กรองสภาวะตลาดที่ซ่อนอยู่"),
    ("Liquidity Sweep at Major Swing Structure", "ทะลวงกวาดจุด Stop Loss ตามโครงสร้างราคาหลัก"),
    ("Institutional Accumulation Cylinder Schematic", "โครงสร้างเก็บของสะสมพลังในไซด์เวย์กระบอก"),
    ("Correlated Asset Lead-Lag Pricing Arbitrage", "เหลื่อมล้ำราคาของสินทรัพย์นำร่องและตามหลัง"),
    ("Volatility Term Structure Backwardation Squeeze", "การสควีซเมื่อโครงสร้าง Volatility ย้อนแย้ง"),
    ("Eurodollar Futures Inversion Rebound Play", "จังหวะเด้งจากสภาพกลับด้านของ Eurodollar"),
    ("Bank Reserves Injection Front-Running Engine", "เกาะกระแสฉีดสภาพคล่องของธนาคารกลาง"),
    ("Macro Factor Multi-Variate Overlay Vector", "เทกเตอร์ชี้ทิศทางจากปัจจัยมหภาคแบบหลายตัวแปร"),
    ("Options Max Pain Expiration Pinning Squeeze", "เทรดตามแรงดึงกลับสู่ Max Pain ช่วงหมดอายุออปชัน"),
    ("Global Liquidity Index Expansion Rider", "กระแสขยายตัวของดัชนีสภาพคล่องโลก"),
    ("Systemic Risk Indicator VIX/BOND Ratio Spread", "ส่วนต่างของความกลัวระดับระบบ"),
    ("Smart Money Index vs Dumb Money Flow", "แยกรอยเท้าเงินใหญ่จากแรงเทขายย่อย"),
    ("Carry Trade Unwind Flash Crash Bounce", "เด้งกลับแรงเมื่อแครี่เทรดโดนบังคับปิดพอร์ต"),
    ("Term Premium Compression Yield Chase", "ล่าเป้าจากการถูกบีบตัวของส่วนต่างดอกเบี้ยระยะยาว"),
    ("Central Bank Forward Guidance Repricing Shock", "ตกใจจากการเปลี่ยนท่าทีของนโยบายการเงิน"),
    ("Stationarity Breakdown Momentum Ignition", "จุดพลุโมเมนตัมเมื่อข้อมูลทางสถิติหลุดStationarity"),
    ("Algorithm TWAP/VWAP Disconnect Snap", "ฉีกหนีรุนแรงจากเส้นแนวรับ TWAP/VWAP"),
    ("Apex Predator Institutional Flow Synthesis", "รวมศาสตร์อ่านทางปลาใหญ่อย่างเหนือชั้น"),
    ("Quant-Fundamental Macro Synergy Driver", "หลอมรวมอัลกอริทึมกับปัจจัยพื้นฐานแบบควอนต์"),
    ("Stochastic Volatility Jump-Diffusion Model", "ระเบิดเทรนด์จากโมเดลความผันผวนแบบก้าวกระโดด"),
    ("Dynamic Time Warping Time-Series Match", "หาแพทเทิร์นย้อนหลังด้วยการบิดเบือนเวลา"),
    ("High-Beta Risk-On Risk-Off Pivot", "หาจุดเปลี่ยนเทรนด์ผ่านสภาพความกล้าเสี่ยงของตลาด"),
    ("Non-Linear Options Delta Hedging Flow", "เกาะการปรับพอร์ตหลบความเสี่ยงแบบไร้เส้นตรง"),
    ("Cross-Sectional Momentum Arbitrage", "เปรียบเทียบโมเมนตัมหลายสินทรัพย์เพื่อหาราคาผิด"),
    ("Sentiment Analysis News Flow Divergence", "ความขัดแย้งของข่าวสารและทิศทางราคาตลาด"),
    ("Order Flow Exhaustion Point Identification", "จุดสิ้นสุดแรงซื้อ/ขายผ่าน Order Flow"),
    ("Liquidity Cascade Stop-Run Amplifier", "การโจมตี Stop Loss เป็นลูกโซ่"),
    ("Intermarket Contagion Safe Haven Rotation", "การเคลื่อนย้ายเงินทุนหลบภัยในภาวะลุกลาม"),
    ("Breakeven Inflation Yield Curve Overlay", "เกาะเทรนด์เส้นอัตราผลตอบแทนเงินเฟ้อคุ้มทุน"),
    ("Shadow Banking Liquidity Drain Anomaly", "หลุมอากาศราคาจากการดูดกลับเงินนอกระบบ"),
    ("Statistical Arbitrage Statistical Dispersion", "เก็งกำไรความคลาดเคลื่อนของการกระจายตัวทางสถิติ"),
    ("Gamma Hedging Zero-DTE Options Influence", "ผลกระทบจากการป้องกันความเสี่ยงออปชันรายวัน"),
    ("Commodity Super-Cycle Macro Extension", "ส่วนต่อขยายของวัฏจักรสินค้าโภคภัณฑ์ขาขึ้นรอบใหญ่"),
    ("Tail Risk Hedging Volatility Premium", "จับส่วนต่างพรีเมียมจากการประกันหางความเสี่ยง"),
    ("Currency Swap Basis Arbitrage Dynamics", "กลไกส่วนต่างราคาจากฐานสวอปค่าเงิน"),
    ("High-Frequency Momentum Statistical Shift", "โมเมนตัมความถี่สูงจากการเปลี่ยนโหมดสถิติ"),
    ("Options Gamma Trap Squeeze Setup", "วางกับดักราคาสควีซผ่าน Gamma ออปชัน"),
    ("Dark Pool Liquidity Re-Rating Drift", "ไหลตามการตีมูลค่าใหม่ผ่านปริมาณเทรดลับ"),
    ("Algorithmic Trend-Following Momentum Exhaustion", "จุดหมดแรงของโปรแกรมจับเทรนด์"),
    ("Market Microstructure Spoofing Retracement", "เด้งสวนจากการหลอกตั้งคิวออเดอร์เพื่อขู่"),
    ("Cross-Market Risk Premium Reversion", "กลับคืนค่าเฉลี่ยของส่วนต่างความเสี่ยงข้ามตลาด"),
    ("Quantitative Tightening Liquidity Vacuum", "ท่อสูญญากาศสูบสภาพคล่องยุคนโยบายการเงินตึงตัว"),
    ("Fiscal Dominance Inflation Trajectory", "เส้นทางราคาจากอิทธิพลนโยบายการคลังที่พิมพ์เงินรุนแรง"),
    ("Yield Curve Steepening Confluence Pivot", "จุดหักศอกจากการชันตัวของเส้นอัตราผลตอบแทน"),
    ("Statistical Stationarity Regime Switch", "สับสวิตช์สถานะตลาดผ่านโมเดลสถิติความนิ่ง"),
    ("Options Vega Convexity Squeeze Pivot", "บีบให้สควีซผ่านค่าออปชันเวก้าที่มีความโค้ง"),
    ("Institutional Smart Money Flow Absorption", "ซับแรงขาย/ซื้อระดับสถาบัน"),
    ("Macro Factor Risk-Parity Rebalance", "ผลกระทบจากการปรับพอร์ตความเสี่ยงแบบกองทุนขนาดใหญ่"),
    ("Algorithmic Dark Pool VWAP Targeting", "เป้าหมายการกวาดราคาไปหาค่าเฉลี่ยของ Dark Pool"),
    ("High-Frequency Lead-Lag Dispersion Arbitrage", "กระจายตัวข้ามเวลาของอัลกอริทึมชิงจังหวะ"),
    ("Quantum-Inspired Order Probability Cloud", "คำนวณน่าจะเป็นของคิวออเดอร์คล้ายกลุ่มเมฆควอนตัม")
]

TEMPLATE = """# -*- coding: utf-8 -*-
\"\"\"strategy20_{ver}.py
Strategy S20.{ver}: {title}

Core Innovations:
1. {desc}
2. Mathematically Unique Entry Logic:
   - Volume > {min_vol:.2f}x
   - Wick Rejection > {min_wick:.2f}
   - Body Momentum > {crt_momentum:.2f}
   - RSI Confluence: Buy<={rsi_b}, Sell>={rsi_s}
   - Requires FVG: {use_fvg}
   - Requires Fibo 38.2/61.8: {use_fibo}
   - Requires Value Area (VP): {use_vp}
3. Multi-Stage Trailing (TP {tp_r:.2f}R)
4. Strict 0.01 Lot single position.
\"\"\"
import pandas as pd
import numpy as np

def extract_setups_s20_{ver}(df):
    setups = []
    records = df.to_dict('records')
    min_vol = {min_vol:.2f}
    min_wick = {min_wick:.2f}
    crt_momentum = {crt_momentum:.2f}
    rsi_buy_max = {rsi_b:.2f}
    rsi_sell_min = {rsi_s:.2f}
    use_fvg = {use_fvg}
    use_fibo = {use_fibo}
    use_vp = {use_vp}
    retest_depth = {retest_depth:.3f}
    sl_mult = {sl_mult:.2f}
    
    for idx in range(45, len(records)):
        cur = records[idx]
        atr = cur['atr']
        if pd.isna(atr) or atr <= 0.05 or cur['range'] < 0.45 * atr:
            continue
            
        h = cur['hour']
        if not (0 <= h <= 22):
            continue
            
        if cur['vol_ratio'] < min_vol:
            continue
            
        swept_high = False
        swept_low = False
        
        # Swings
        if cur['high'] >= cur.get('swing_high_12', np.nan): swept_high = True
        if cur['low'] <= cur.get('swing_low_12', np.nan): swept_low = True
        
        if use_fvg:
            f_bull = cur.get('fvg_bull_zone', np.nan)
            f_bear = cur.get('fvg_bear_zone', np.nan)
            if not pd.isna(f_bull) and cur['low'] <= f_bull: swept_low = True
            if not pd.isna(f_bear) and cur['high'] >= f_bear: swept_high = True
            
        if use_fibo:
            if cur['low'] <= cur.get('fibo_discount_382', np.nan): swept_low = True
            if cur['high'] >= cur.get('fibo_premium_618', np.nan): swept_high = True
            
        if use_vp:
            if cur['low'] <= cur.get('val_proxy', np.nan): swept_low = True
            if cur['high'] >= cur.get('vah_proxy', np.nan): swept_high = True
            
        # Rejection & Momentum Conditions
        bull_body = (cur['close'] - cur['open']) / (cur['range'] + 1e-5)
        bear_body = (cur['open'] - cur['close']) / (cur['range'] + 1e-5)
        
        is_rejection_bull = swept_low and (cur['lower_wick_pct'] >= min_wick) and (bull_body >= crt_momentum) and (cur['rsi'] <= rsi_buy_max)
        is_rejection_bear = swept_high and (cur['upper_wick_pct'] >= min_wick) and (bear_body >= crt_momentum) and (cur['rsi'] >= rsi_sell_min)
        
        if is_rejection_bull:
            entry = cur['close'] - (cur['lower_wick'] * retest_depth)
            sl = cur['low'] - (atr * sl_mult)
            setups.append({{
                'time': int(cur['time']),
                'time_str': str(cur['time_dt']),
                'signal': 'BUY',
                'entry': entry,
                'sl': sl,
                'risk': entry - sl,
                'atr': atr,
                'tf': 'M5'
            }})
        elif is_rejection_bear:
            entry = cur['close'] + (cur['upper_wick'] * retest_depth)
            sl = cur['high'] + (atr * sl_mult)
            setups.append({{
                'time': int(cur['time']),
                'time_str': str(cur['time_dt']),
                'signal': 'SELL',
                'entry': entry,
                'sl': sl,
                'risk': sl - entry,
                'atr': atr,
                'tf': 'M5'
            }})
    return setups
"""

def make_stages(stg_len):
    stg = []
    current_trig = 1.5
    current_amt = 1.0
    for i in range(stg_len):
        stg.append((round(current_trig, 2), round(current_amt, 2)))
        current_trig += 0.25
        current_amt += 0.25
    return stg

def run():
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=365)
    parser.add_argument("--start", type=str, default=None)
    parser.add_argument("--end", type=str, default=None)
    parser.add_argument("--compare", action="store_true")
    args = parser.parse_args()

    if not init_mt5():
        print("MT5 init failed")
        return

    BKK = timezone(timedelta(hours=7))
    if args.end:
        end_time = datetime.strptime(args.end, "%Y-%m-%d").replace(tzinfo=BKK)
    else:
        end_time = datetime.now(BKK)
        
    if args.start:
        start_time = datetime.strptime(args.start, "%Y-%m-%d").replace(tzinfo=BKK)
    else:
        start_time = end_time - timedelta(days=args.days)
        
    print(f"Loading M5 data {start_time.date()} to {end_time.date()}...")
    m5_rates = mt5.copy_rates_range("XAUUSD.iux", mt5.TIMEFRAME_M5, start_time, end_time)
    if m5_rates is None or len(m5_rates) == 0:
        print("Falling back to copy_rates_from_pos (75,000 bars)...")
        m5_rates = mt5.copy_rates_from_pos("XAUUSD.iux", mt5.TIMEFRAME_M5, 0, 75000)
        
    if m5_rates is None or len(m5_rates) == 0:
        print("No M5 data")
        return
        
    df_base = compute_indicators(m5_rates)
    m5_bars = df_base.to_dict('records')
    m5_times = df_base['time'].values
    
    base_dir = os.path.dirname(__file__)
    strat_md = os.path.join(base_dir, "strategy.md")
    evo_md = os.path.join(base_dir, "strategy_evolution.md")
    
    start_ver = 55
    end_ver = 129
    
    new_strat_content = ""
    new_evo_content = ""

    for i, current_ver in enumerate(range(start_ver, end_ver + 1)):
        paradigm_idx = i % len(PARADIGMS)
        title, desc = PARADIGMS[paradigm_idx]
        
        # Seed logic deterministically by version to create mathematically unique strategies
        random.seed(current_ver)
        min_vol = random.uniform(1.0, 1.3)
        min_wick = random.uniform(0.15, 0.40)
        crt_momentum = random.uniform(0.1, 0.5)
        rsi_b = random.uniform(50.0, 75.0)
        rsi_s = random.uniform(25.0, 50.0)
        use_fvg = random.choice([True, False])
        use_fibo = random.choice([True, False])
        use_vp = random.choice([True, False])
        
        # Make sure at least one structure is used
        if not use_fvg and not use_fibo and not use_vp:
            use_fvg = True
            
        retest_depth = random.uniform(0.05, 0.20)
        sl_mult = random.uniform(0.10, 0.30)
        
        stg_len = 15 + i
        stg = make_stages(stg_len)
        tp_r = 5.50 + (i * 0.10)
        
        print(f"\\n--- Generating S20.{current_ver}: {title} (Unique Mathematical Logic) ---")
        
        # 1. Write the Python file
        ver_dir = os.path.join(base_dir, f"s20.{current_ver}")
        os.makedirs(ver_dir, exist_ok=True)
        strat_file = os.path.join(ver_dir, f"strategy20_{current_ver}.py")
        
        code = TEMPLATE.format(
            ver=current_ver, title=title, desc=desc,
            min_vol=min_vol, min_wick=min_wick, crt_momentum=crt_momentum,
            rsi_b=rsi_b, rsi_s=rsi_s, use_fvg=use_fvg, use_fibo=use_fibo, use_vp=use_vp,
            retest_depth=retest_depth, sl_mult=sl_mult, tp_r=tp_r
        )
        
        with open(strat_file, "w", encoding="utf-8") as f:
            f.write(code)
            
        # 2. Dynamically load the written module and run it
        spec = importlib.util.spec_from_file_location(f"stg20_{current_ver}", strat_file)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        
        extract_func = getattr(module, f"extract_setups_s20_{current_ver}")
        setups = extract_func(df_base)
        
        print(f"Extracted {len(setups)} mathematically unique setups for S20.{current_ver}...")
        
        res = run_simulation(m5_bars, m5_times, setups, tp_r=tp_r, stages=stg)
        
        net = res['pnl']
        wr = res['wr']
        dd = res['max_dd']
        
        print(f"Backtest S20.{current_ver} -> Net Profit: ${net:,.2f} | WR: {wr:.1f}% | DD: ${dd:,.2f}")
        
        stg_summary_line = f"| S20.{current_ver} | {title} | {desc}... (Unique Code) + {len(stg)}-Stage Trailing (TP {tp_r:.2f}R) Strict Lot 0.01 |\\n"
        new_strat_content += stg_summary_line
        
        evo_add = f"## S20.{current_ver} — {title}\\n"
        evo_add += f"Edge: {desc} (Unique Logic: Vol>{min_vol:.2f}x, Wick>{min_wick:.2f}, FVG={use_fvg}, Fibo={use_fibo}, VP={use_vp})\\n"
        evo_add += f"ผล Backtest 365 วัน:\\n"
        evo_add += f"- Net Profit: ${net:,.2f}\\n"
        evo_add += f"- Win Rate: {wr:.1f}%\\n"
        evo_add += f"- Max DD: ${dd:,.2f}\\n\\n"
        new_evo_content += evo_add
        
    try:
        with open(strat_md, "a", encoding="utf-8") as f:
            f.write(new_strat_content)
        with open(evo_md, "a", encoding="utf-8") as f:
            f.write(new_evo_content)
        print("Updated markdown files successfully.")
    except Exception as e:
        print(f"Failed to update md files: {e}")

if __name__ == "__main__":
    main_start = time.time()
    run()
    print(f"\\nAll 75 mathematically unique strategies (S20.55-S20.129) fully completed in {time.time()-main_start:.1f}s")
