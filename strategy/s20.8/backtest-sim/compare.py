from pathlib import Path

import pandas as pd


EXCEL_DIR = Path(__file__).resolve().parents[1] / "excel"


# Load Actual
df_act = pd.read_csv(EXCEL_DIR / "mt5_actual_history_s20_8.csv")
# Keep only Out deals to represent closed trades.
df_act_out = df_act[df_act["Entry"] == "Out"].copy()
df_act_out["Time (BKK)"] = pd.to_datetime(df_act_out["Time (BKK)"])
df_act_out = df_act_out.sort_values("Time (BKK)").reset_index(drop=True)

# Load Sim
df_sim = pd.read_csv(EXCEL_DIR / "s20_8_trades.csv")
df_sim["exit_time"] = pd.to_datetime(df_sim["exit_time"])
df_sim = df_sim.sort_values("exit_time").reset_index(drop=True)

print(f"Total Sim Trades today: {len(df_sim)}")
print(f"Total Actual Trades (Out deals) today: {len(df_act_out)}")

print("\nActual Trades:")
print(
    df_act_out[["Order", "Time (BKK)", "Type", "Volume", "Profit", "Comment"]]
    .sort_values("Time (BKK)")
)
