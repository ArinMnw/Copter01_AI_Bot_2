import pandas as pd; df = pd.read_parquet('strategy/s20.14.1/data/D1.parquet'); df = df.set_index('time'); print(df.loc['2026-02-06':'2026-02-28', ['open', 'high', 'low', 'close']])
