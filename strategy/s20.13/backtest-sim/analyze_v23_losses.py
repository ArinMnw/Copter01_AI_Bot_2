import pandas as pd
import os

csv_path = r'd:\Project\Copter01_AI_Bot_2\strategy\s20.13\backtest-sim\s20_13_23_trades.csv'
if os.path.exists(csv_path):
    df = pd.read_csv(csv_path)
    losses = df[df['Result'] == 'LOSS']
    print(f"Total Trades: {len(df)}")
    print(f"Wins: {len(df[df['Result'] == 'WIN'])} | Losses: {len(losses)} | BE: {len(df[df['Result'] == 'BE'])}")
    print("\n--- Remaining 5 Losses in v23 ---")
    for idx, row in losses.iterrows():
        print(f"Time: {row['Time']} | Type: {row['Type']} | Entry: {row['Entry']:.2f} | SL: {row['SL']:.2f} | TP: {row['TP']:.2f} | PnL: ${row['PnL']:.2f}")
    
    total_loss_pnl = losses['PnL'].sum()
    print(f"\nTotal money lost in these 5 trades: ${total_loss_pnl:,.2f}")
    print(f"If we eliminate these 5 losses, Net Profit becomes: ${df['PnL'].sum() - total_loss_pnl:,.2f}")
else:
    print("CSV not found!")
