import sys
import datetime

raw = '''2. ไม่มีท่า | 06-02-2026 07:00 | Buy 4658 | SL 4648 | TP 5407
3. Fibo 1H/Div | 11-02-2026 18:00 | Sell 5116 | SL 5128 | TP 4849
4. Fibo 1H | 17-02-2026 21:00 | Buy 4849 | SL 4833 | TP 5407
5. ATR 1D/Fibo 1H | 02-03-2026 15:00 | Sell 5417 | SL 5435 | TP 3058
6. Fibo 30M/FVG 1D | 10-03-2026 22:00 | Sell 5238 | SL 5249 | TP 4405
7. นัยยะ 1H | 07-04-2026 21:00 | Buy 4607 | SL 4601 | TP 4879
8. Fibo 15M 3/1 | 13-04-2026 05:00 | Buy 4644 | SL 4639 | TP 4879
9.ไม่ทราบแน่ชัด | 17-04-2026 08:00 | Buy 4772 | SL 4765 | TP 4879
10. ATR 1D | 17-04-2026 20:00 | Sell 4887 | SL 4891 | TP 3850 
11. นัยยะ 1H/Doji | 23-04-2026 22:00 | Sell 4739 | SL 4745 | TP 4557
12. Fibo 15M | 01-05-2026 21:00 | Sell 4656 | SL 4762 | TP 4506
13. Doji Fibo | 08-05-2026 21:00 | Sell 4747 | SL 4752 | TP 4665
14. ATR 1D/Div | 12-05-2026 07:00 | Sell 4769 | SL 4775 | TP 4100
15. นัยยะDoji 1H | 14-05-2026 14:00 | Sell 4716 | SL 4722 | TP 4466
16. FVG 1D/กินไส้ | 19-05-2026 20:00 | Sell 4587 | SL 4596 | TP 4456
17. ATR 1H | 20-05-2026 07:00 | Buy 4462 | SL 4454 | TP 4568
18. กินไส้/Div | 26-05-2026 06:00 | Sell 4578 | SL 4580 | TP 4368
19. ATR 1D/ราคาลงไป W1 | 29-05-2026 22:00 | Sell 4590 | SL 4598 | TP 4093
20. Fibo 30M 3/1 | 02-06-2026 14:00 | Sell 4539 | SL 4551 | TP 4282
21. นัยยะ 1H Doji | 04-06-2026 18:00 | Sell 4514 | SL 4519 | TP 4282
22. นัยยะ 1D/FVG 1D | 09-06-2026 20:00 | Sell 4359 | SL 4369 | TP 4093
23. ATR 1D/FVG 1D/Div | 18-06-2026 00:00 | Sell 4380 | SL 4387 | TP 3971
24. แนวต้าน/นัยยะ 1H | 23-06-2026 21:00 | Sell 4143 | SL 4150 | TP 4007
25. ATR 1D | 25-06-2026 01:00 | Buy 3961 | SL 3953 | TP 4089
26. MA12 | 29-06-2026 20:00 | Sell 4051 | SL 4054 | TP 3962
27. ไม่ทราบ | 30-06-2026 12:00 | Buy 3975 | SL 3971 | TP 4052
28. ATR 1H | 30-06-2026 21:00 | Sell 4063 | SL 4065 | TP 3971
29. Follow Div ไม่แน่ใจ TF | 01-07-2026 15:00 | Buy 3974 | SL 3969 | TP 4087
30. ราคากินไส้ ไม่แน่ใจ TF | 07-07-2026 20:00 | Sell 4177 | SL 4180 | TP 4952
31. นัยยะ 12H | 08-07-2026 22:00 | Buy 4023 | SL 4020 | TP 4137
32. Doji/ATR 1H | 10-07-2026 21:00 | Buy 4072 | SL 4070 | TP 4120
33. ATR 1H | 14-07-2026 22:00 | Sell 4096 | SL 4100 | TP 3963
34. FVG 1H | 16-07-2026 19:00 | Sell 4038 | SL 4045 | TP 3966
35. ATR 1H / กินไส้ D1 | 22-07-2026 22:00 | Buy 3964 | SL 3959 | TP 4147
36. ATR 1H/Div/Fibo 30M | 22-07-2026 22:00 | Sell 4160 | SL 4168 | TP 3923'''

lines = raw.strip().split('\n')
out_md = []
for i, line in enumerate(lines):
    # Some lines might be malformed, e.g. 11 and 12 lack some pipes
    line = line.replace(' 23-04-2026 22:00 Sell 4739', ' | 23-04-2026 22:00 | Sell 4739')
    line = line.replace(' 01-05-2026 21:00 Sell 4656', ' | 01-05-2026 21:00 | Sell 4656')
    parts = [p.strip() for p in line.split('|')]
    name = parts[0].split('.', 1)[1].strip()
    
    date_str = parts[1]
    # parse DD-MM-YYYY HH:MM
    dt = datetime.datetime.strptime(date_str, '%d-%m-%Y %H:%M')
    formatted_date = dt.strftime('%Y-%m-%d %H:%M')
    
    order_type = 'LONG' if 'Buy' in parts[2] else 'SHORT'
    entry = parts[2].replace('Buy ', '').replace('Sell ', '').strip()
    sl = parts[3].replace('SL ', '').strip()
    tp = parts[4].replace('TP ', '').strip()
    
    out_md.append(f"{i+1}. **Order {i+1} [{order_type}]:** \"{name}\" — 🕒 **เวลา:** {formatted_date} | 💰 **Entry:** {entry} | 🛑 **SL:** {sl} | 🎯 **TP:** {tp}")

with open('formatted_orders.txt', 'w', encoding='utf-8') as f:
    f.write('\n'.join(out_md))
print("Done writing to formatted_orders.txt")
