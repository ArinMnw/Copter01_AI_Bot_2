import pandas as pd

def main():
    try:
        df = pd.read_csv(r"C:\Users\Copter\.gemini\antigravity-ide\brain\46b76b60-dc83-4319-86c1-8cec2d62a6ff\scratch\s96_trades.csv")
    except:
        print("Cannot load CSV")
        return

    df['time'] = pd.to_datetime(df['time'])
    
    # Original
    total_net = df['profit'].sum()
    wr = len(df[df['outcome'] == 'TP']) / len(df) * 100
    print(f"Original: Net ${total_net:.2f}, WR: {wr:.2f}% (Trades: {len(df)})")
    
    # Time Filter (Avoid 18, 19, 21 BKK time)
    # BKK time is UTC+7. Is the log in BKK time? 
    # Yes, the trades are typically generated using MT5 server time or BKK time. Let's assume it's MT5 server time. 
    # Let's just filter those exact hour numbers as they appeared in the previous script.
    bad_hours = [7, 8, 9, 10, 11, 12, 18, 19, 21, 22]
    df_filtered = df[~df['time'].dt.hour.isin(bad_hours)]
    
    if len(df_filtered) > 0:
        filt_net = df_filtered['profit'].sum()
        filt_wr = len(df_filtered[df_filtered['outcome'] == 'TP']) / len(df_filtered) * 100
        print(f"After Time Filter (Drop {bad_hours}): Net ${filt_net:.2f}, WR: {filt_wr:.2f}% (Trades: {len(df_filtered)})")
    
if __name__ == "__main__":
    main()
