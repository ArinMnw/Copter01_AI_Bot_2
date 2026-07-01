import os
import sys
import pandas as pd
from datetime import datetime, timedelta, timezone
import MetaTrader5 as mt5

# Adjust path to import config if needed
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
import config

BKK = timezone(timedelta(hours=7))

def main():
    sim_csv = os.path.join(os.path.dirname(__file__), "..", "excel", "s20_6_sim_trades.csv")
    if not os.path.exists(sim_csv):
        print(f"❌ ไม่พบไฟล์ {sim_csv}\nกรุณารัน backtest_S20_6_runner_mt5.py ก่อนครับ")
        return

    print("📊 กำลังโหลดข้อมูลออเดอร์จำลอง (SIM)...")
    df_sim = pd.read_csv(sim_csv)
    if df_sim.empty:
        print("❌ ไฟล์ SIM ไม่มีข้อมูลออเดอร์")
        return

    # Parse BKK times to UTC for MT5
    df_sim["Time (BKK)"] = pd.to_datetime(df_sim["Time (BKK)"])
    df_sim["Close Time"] = pd.to_datetime(df_sim["Close Time"])
    
    start_bkk = df_sim["Time (BKK)"].min() - timedelta(hours=1)
    end_bkk = df_sim["Close Time"].max() + timedelta(hours=1)

    print(f"🕒 ช่วงเวลา SIM: {start_bkk} ถึง {end_bkk}")

    if not mt5.initialize():
        print("❌ MT5 Initialize Failed")
        return

    start_utc = start_bkk.tz_localize(BKK).astimezone(timezone.utc)
    end_utc = end_bkk.tz_localize(BKK).astimezone(timezone.utc)

    print("📥 กำลังดึงประวัติการเทรดจาก MT5...")
    deals = mt5.history_deals_get(start_utc, end_utc)
    if deals is None or len(deals) == 0:
        print("⚠️ ไม่พบประวัติการเทรดใน MT5 ในช่วงเวลานี้")
        mt5.shutdown()
        return

    # Filter MT5 deals
    act_trades = []
    for d in deals:
        if d.symbol != config.SYMBOL:
            continue
        # Only closed deals (OUT) to compare with sim closures
        if d.entry != mt5.DEAL_ENTRY_OUT:
            continue
        
        dt_bkk = datetime.fromtimestamp(d.time, tz=timezone.utc).astimezone(BKK)
        typ = "BUY" if d.type == mt5.DEAL_TYPE_SELL else "SELL" # DEAL_ENTRY_OUT for BUY is a SELL deal
        
        # S20.6 uses SID 20.6, so the original IN deal comment should contain "20.6"
        in_deals = mt5.history_deals_get(position=d.position_id)
        is_s20_6 = False
        if in_deals:
            for ind in in_deals:
                if ind.entry == mt5.DEAL_ENTRY_IN and ind.comment and ("20.6" in str(ind.comment)):
                    is_s20_6 = True
                    break
        if not is_s20_6:
             continue
        
        act_trades.append({
            "MT5_Close_Time": dt_bkk,
            "MT5_Type": typ,
            "MT5_Price": d.price,
            "MT5_Volume": d.volume,
            "MT5_P&L": d.profit + d.commission + d.swap,
            "MT5_Comment": d.comment,
            "MT5_Position_ID": d.position_id
        })

    df_act = pd.DataFrame(act_trades)
    print(f"✅ พบประวัติการปิดออเดอร์ใน MT5: {len(df_act)} รายการ")

    # Merge logic (Simple time-based matching)
    # We will iterate SIM trades and find the closest MT5 trade within +/- 5 minutes
    
    results = []
    matched_indices = set()
    for _, sim in df_sim.iterrows():
        sim_close = sim["Close Time"]
        sim_type = sim["Type"]
        
        match = None
        if not df_act.empty:
            # Filter by type
            subset = df_act[(df_act["MT5_Type"] == sim_type) & (~df_act.index.isin(matched_indices))].copy()
            if not subset.empty:
                subset["time_diff"] = (subset["MT5_Close_Time"].dt.tz_localize(None) - sim_close).abs()
                subset = subset[subset["time_diff"] <= timedelta(minutes=15)]
                if not subset.empty:
                    # Get closest
                    match_idx = subset["time_diff"].idxmin()
                    match = subset.loc[match_idx]
                    matched_indices.add(match_idx)
        
        res = {
            "SIM_Open_Time": sim["Time (BKK)"],
            "SIM_Close_Time": sim["Close Time"],
            "SIM_TF": sim["TF"],
            "SIM_Type": sim["Type"],
            "SIM_Entry": sim["Entry"],
            "SIM_P&L": sim["P&L"],
            "SIM_Reason": sim["Reason"],
            "MT5_Close_Time": match["MT5_Close_Time"].strftime('%Y-%m-%d %H:%M:%S') if match is not None else None,
            "MT5_Price": match["MT5_Price"] if match is not None else None,
            "MT5_P&L": match["MT5_P&L"] if match is not None else None,
            "MT5_Comment": match["MT5_Comment"] if match is not None else None,
            "MT5_Position_ID": match["MT5_Position_ID"] if match is not None else None,
            "Matched": "YES" if match is not None else "NO"
        }
        results.append(res)
        
    df_res = pd.DataFrame(results)
    
    out_dir = os.path.join(os.path.dirname(__file__), "..", "excel")
    os.makedirs(out_dir, exist_ok=True)
    out_file = os.path.join(out_dir, "compare_s20_6.csv")
    
    df_res.to_csv(out_file, index=False)
    print(f"🎉 สร้างไฟล์เปรียบเทียบเสร็จสมบูรณ์!\n📍 บันทึกไว้ที่: {out_file}")
    
    # Summary
    matched = df_res[df_res["Matched"] == "YES"]
    print("-" * 40)
    print(f"สรุปการจับคู่:")
    print(f"ออเดอร์ SIM ทั้งหมด: {len(df_res)}")
    print(f"จับคู่กับ MT5 ได้: {len(matched)} ({len(matched)/len(df_res)*100:.2f}%)")
    print("-" * 40)

    mt5.shutdown()

if __name__ == "__main__":
    main()
