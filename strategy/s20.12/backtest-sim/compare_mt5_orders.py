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
    sim_csv = os.path.join(os.path.dirname(__file__), "..", "excel", "s20_12_sim_trades.csv")
    if not os.path.exists(sim_csv):
        print(f"❌ ไม่พบไฟล์ {sim_csv}\nกรุณารัน backtest_S20_12_runner_mt5.py ก่อนครับ")
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

    if not config.mt5_initialize(mt5):
        print("❌ MT5 Initialize Failed")
        return

    resolved_symbol = config.SYMBOL

    # ใช้ naive UTC+7 แปลง BKK->UTC เพื่อกำหนดขอบเขต query เท่านั้น (MT5_SERVER_TZ ต่างจาก
    # BKK ไม่คงที่ + ห่างได้หลายชม.) แล้วบวก padding กว้างๆ กันเคส server tz ดันช่วงเวลาออกนอกขอบ
    start_utc = start_bkk.tz_localize(BKK).astimezone(timezone.utc) - timedelta(hours=6)
    end_utc = end_bkk.tz_localize(BKK).astimezone(timezone.utc) + timedelta(hours=6)

    print("📥 กำลังดึงประวัติการเทรดจาก MT5...")
    deals = mt5.history_deals_get(start_utc, end_utc)
    if deals is None or len(deals) == 0:
        print("⚠️ ไม่พบประวัติการเทรดใน MT5 ในช่วงเวลานี้")
        mt5.shutdown()
        return

    # Filter MT5 deals
    act_trades = []
    for d in deals:
        if d.symbol != resolved_symbol:
            continue
        # Only closed deals (OUT) to compare with sim closures
        if d.entry != mt5.DEAL_ENTRY_OUT:
            continue
        
        dt_bkk = config.mt5_ts_to_bkk(d.time)
        typ = "BUY" if d.type == mt5.DEAL_TYPE_SELL else "SELL" # DEAL_ENTRY_OUT for BUY is a SELL deal

        # S20.12 uses SID 20.12, so the original IN deal comment should contain "20.12"
        in_deals = mt5.history_deals_get(position=d.position_id)
        is_target_strat = False
        open_dt_bkk = None
        if in_deals:
            for ind in in_deals:
                if ind.entry == mt5.DEAL_ENTRY_IN and ind.comment and ("20.12" in str(ind.comment)):
                    is_target_strat = True
                    open_dt_bkk = config.mt5_ts_to_bkk(ind.time)
                    break
        if not is_target_strat:
             continue

        act_trades.append({
            "MT5_Open_Time": open_dt_bkk,
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

    # Merge logic — จับคู่เฉพาะเมื่อ open+close ตรงกันจริงระดับ ชม:นาที (ไม่สนวินาที) เท่านั้น
    # ถ้าไม่มี MT5 record ไหนตรงเป๊ะ ให้ปล่อยว่าง (ไม่ force-pair กับแถวที่ใกล้สุดแต่ไม่ใช่คู่จริง
    # เพราะจะหลอกตาว่า "จับคู่ได้" ทั้งที่เป็นออเดอร์คนละตัว)
    def _hhmm_match(a, b) -> bool:
        if a is None or b is None or pd.isna(a) or pd.isna(b):
            return False
        return (a.hour, a.minute) == (b.hour, b.minute)

    results = []
    matched_indices = set()
    for _, sim in df_sim.iterrows():
        sim_open = sim["Time (BKK)"]
        sim_close = sim["Close Time"]
        sim_type = sim["Type"]

        match = None
        if not df_act.empty:
            subset = df_act[(df_act["MT5_Type"] == sim_type) & (~df_act.index.isin(matched_indices))].copy()
            for idx, cand in subset.iterrows():
                cand_open = cand["MT5_Open_Time"].tz_localize(None) if cand["MT5_Open_Time"] is not None else None
                cand_close = cand["MT5_Close_Time"].tz_localize(None) if cand["MT5_Close_Time"] is not None else None
                if _hhmm_match(sim_open, cand_open) and _hhmm_match(sim_close, cand_close):
                    match = cand
                    matched_indices.add(idx)
                    break

        mt5_open = match["MT5_Open_Time"].tz_localize(None) if match is not None and match["MT5_Open_Time"] is not None else None
        mt5_close = match["MT5_Close_Time"].tz_localize(None) if match is not None else None

        res = {
            "SIM_Open_Time": sim["Time (BKK)"],
            "SIM_Close_Time": sim["Close Time"],
            "SIM_TF": sim["TF"],
            "SIM_Type": sim["Type"],
            "SIM_Entry": sim["Entry"],
            "SIM_P&L": sim["P&L"],
            "SIM_Reason": sim["Reason"],
            "MT5_Open_Time": mt5_open.strftime('%Y-%m-%d %H:%M:%S') if mt5_open is not None else None,
            "MT5_Close_Time": mt5_close.strftime('%Y-%m-%d %H:%M:%S') if mt5_close is not None else None,
            "MT5_Price": match["MT5_Price"] if match is not None else None,
            "MT5_P&L": match["MT5_P&L"] if match is not None else None,
            "MT5_Comment": match["MT5_Comment"] if match is not None else None,
            "MT5_Position_ID": match["MT5_Position_ID"] if match is not None else None,
            "Matched": match is not None
        }
        results.append(res)
        
    df_res = pd.DataFrame(results)
    
    out_dir = os.path.join(os.path.dirname(__file__), "..", "excel")
    os.makedirs(out_dir, exist_ok=True)
    out_file = os.path.join(out_dir, "compare_s20_12.csv")
    
    df_res.to_csv(out_file, index=False)
    print(f"🎉 สร้างไฟล์เปรียบเทียบเสร็จสมบูรณ์!\n📍 บันทึกไว้ที่: {out_file}")
    
    # Summary
    matched = df_res[df_res["Matched"] == True]
    print("-" * 40)
    print(f"สรุปการจับคู่:")
    print(f"ออเดอร์ SIM ทั้งหมด: {len(df_res)}")
    print(f"จับคู่กับ MT5 ได้: {len(matched)} ({len(matched)/len(df_res)*100:.2f}%)")
    print("-" * 40)

    mt5.shutdown()

if __name__ == "__main__":
    main()
