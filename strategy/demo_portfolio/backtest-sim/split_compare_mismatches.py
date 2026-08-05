"""
split_compare_mismatches.py — แยก row ที่ Matched=False ออกจาก {portfolio}_compare.csv
เป็น 2 ไฟล์ตามฝั่งที่มีข้อมูล:
  - {portfolio}_mt5_not_match.csv      : MT5 มี order แต่ backtest ไม่มีคู่ (MT5_Open_Time ไม่ว่าง)
  - {portfolio}_backtest_not_match.csv : backtest มี trade แต่ MT5 ไม่มีคู่ (SIM_Open_Time ไม่ว่าง)

รัน: python split_compare_mismatches.py --portfolio LTS_AVENGERS_ULTRA_SAFE
     python split_compare_mismatches.py --portfolio LTS_AVENGERS_HIGH_RISK
"""
import argparse
import csv
import os

EXCEL_LTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "excel", "lts"))


def split(portfolio_name, in_dir=EXCEL_LTS_DIR, out_dir=EXCEL_LTS_DIR):
    compare_path = os.path.join(in_dir, f"{portfolio_name}_compare.csv")
    if not os.path.exists(compare_path):
        print(f"❌ Not found: {compare_path}")
        return

    with open(compare_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)

    mt5_rows = []
    backtest_rows = []
    for row in rows:
        if row.get("Matched") == "True":
            continue
        mt5_open = (row.get("MT5_Open_Time") or "").strip()
        sim_open = (row.get("SIM_Open_Time") or "").strip()
        if mt5_open and not sim_open:
            mt5_rows.append(row)
        elif sim_open and not mt5_open:
            backtest_rows.append(row)
        # แถวที่ทั้งคู่ว่างหรือทั้งคู่มีข้อมูลพร้อมกันแต่ Matched=False ไม่ควรเกิดขึ้นตามโครงสร้าง
        # compare.csv ปัจจุบัน (ข้ามไปเงียบๆ ถ้าเจอ กันสคริปต์พัง)

    mt5_out = os.path.join(out_dir, f"{portfolio_name}_mt5_not_match.csv")
    with open(mt5_out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(mt5_rows)
    print(f"Saved: {mt5_out} ({len(mt5_rows)} rows)")

    bt_out = os.path.join(out_dir, f"{portfolio_name}_backtest_not_match.csv")
    with open(bt_out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(backtest_rows)
    print(f"Saved: {bt_out} ({len(backtest_rows)} rows)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--portfolio", required=True, help="e.g. LTS_AVENGERS_ULTRA_SAFE or LTS_AVENGERS_HIGH_RISK")
    args = ap.parse_args()
    split(args.portfolio)


if __name__ == "__main__":
    main()
