import pandas as pd
from datetime import datetime, timedelta

def main():
    try:
        df = pd.read_csv(r"C:\Users\Copter\.gemini\antigravity-ide\brain\46b76b60-dc83-4319-86c1-8cec2d62a6ff\scratch\s96_trades.csv")
    except:
        print("Cannot load CSV")
        return

    df['time'] = pd.to_datetime(df['time'])
    df['exit_time'] = pd.to_datetime(df['exit_time'])

    total_trades = len(df)
    total_losses = len(df[df['outcome'] == 'SL'])
    total_wins = len(df[df['outcome'] == 'TP'])

    print(f"Total Trades: {total_trades}")
    print(f"Wins: {total_wins}, Losses: {total_losses}")
    print("---")

    # Time of day analysis
    losses_by_hour = df[df['outcome'] == 'SL']['time'].dt.hour.value_counts().sort_index()
    wins_by_hour = df[df['outcome'] == 'TP']['time'].dt.hour.value_counts().sort_index()

    print("Losses by Hour:")
    for h, count in losses_by_hour.items():
        w = wins_by_hour.get(h, 0)
        win_rate = w / (w + count) * 100 if (w + count) > 0 else 0
        if count > w:
            print(f"Hour {h:02d}: {count} losses, {w} wins (WR: {win_rate:.1f}%) <--- BAD HOUR")
        else:
            print(f"Hour {h:02d}: {count} losses, {w} wins (WR: {win_rate:.1f}%)")

    # Consecutive loss analysis (same direction within N hours)
    cooldown_hours = 4
    blocked_count = 0
    saved_loss = 0
    blocked_win = 0

    df_sorted = df.sort_values('time')
    last_trade_time = {}

    for _, row in df_sorted.iterrows():
        d = row['dir']
        t = row['time']
        if d in last_trade_time:
            if t - last_trade_time[d] < timedelta(hours=cooldown_hours):
                blocked_count += 1
                if row['outcome'] == 'SL':
                    saved_loss += 1
                else:
                    blocked_win += 1
                continue # don't update last_trade_time so we block the cluster
        last_trade_time[d] = t

    print("\n--- Consecutive Trades Cooldown Filter ---")
    print(f"If we block same-direction trades for {cooldown_hours} hours after an entry:")
    print(f"Total Blocked: {blocked_count}")
    print(f"Avoided SLs: {saved_loss}")
    print(f"Missed TPs: {blocked_win}")
    
    # Calculate net profit improvement
    # Avg SL loss is around 15, Avg TP win is around 30 (based on 1:2 RR)
    # Actually let's sum it
    
if __name__ == "__main__":
    main()
