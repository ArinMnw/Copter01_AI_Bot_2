# Bot 36 Order Matching Report (Grouped)

รายงานแยกตามกลุ่ม Pattern (ATR แยกต่างหาก, ออเดอร์ที่มีมากกว่า 2 pattern แยกต่างหาก)

## ATR Group

| Order | Patterns | Type | Bot Pattern | Spec Entry | Bot Entry | Entry Diff | Spec SL | Bot SL | SL Diff | Spec TP | Bot TP | TP Diff | P&L |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | ATR D1 | SELL | Naiya | 5590.00 | 5541.52 | **48.48** | 5604.00 | 5605.48 | **1.48** | 3058.00 | 5221.71 | **2163.71** | **63962.00** |
| 5 | ATR D1/Fibo H1 | SELL | Fibo | 5417.00 | 5412.48 | **4.52** | 5435.00 | 5447.45 | **12.45** | 3058.00 | 5345.45 | **2287.45** | **13406.00** |
| 10 | ATR D1 | SELL | Fibo/ATR | 4887.00 | 4799.28 | **87.72** | 4891.00 | 4823.93 | **67.07** | 3850.00 | 4745.11 | **895.11** | **-4930.00** |
| 14 | ATR D1/Div H1 | SELL | Fibo/FollowDiv | 4769.00 | 4704.55 | **64.45** | 4775.00 | 4747.82 | **27.18** | 4100.00 | 4533.05 | **433.05** | **34300.00** |
| 17 | ATR H1 | BUY | Naiya | 4462.00 | 4463.72 | **1.72** | 4454.00 | 4428.57 | **25.43** | 4568.00 | 4639.47 | **71.47** | **-7030.00** |
| 19 | ATR D1/ราคาลงไป W1 H1 | SELL | Naiya | 4590.00 | 4565.22 | **24.78** | 4598.00 | 4707.81 | **109.81** | 4093.00 | 3852.28 | **240.72** | **0.00** |
| 23 | ATR D1/FVG D1/Div H1 | SELL | Naiya | 4380.00 | 4312.05 | **67.95** | 4387.00 | 4518.15 | **131.15** | 3971.00 | 3281.55 | **689.45** | **0.00** |
| 25 | ATR D1 | BUY | Fibo/ATR | 3961.00 | 4023.77 | **62.77** | 3953.00 | 3978.80 | **25.80** | 4089.00 | 4135.70 | **46.70** | **-8994.00** |
| 28 | ATR H1 | SELL | Fibo | 4063.00 | 4029.48 | **33.52** | 4065.00 | 4081.91 | **16.91** | 3971.00 | 3834.15 | **136.85** | **-10486.00** |
| 32 | Doji H1/ATR H1 | BUY | Fibo | 4072.00 | 4098.21 | **26.21** | 4070.00 | 4062.32 | **7.68** | 4120.00 | 4198.85 | **78.85** | **-7178.00** |
| 33 | ATR H1 | SELL | FVG/Fibo | 4096.00 | 4062.98 | **33.02** | 4100.00 | 4109.80 | **9.80** | 3963.00 | 3869.95 | **93.05** | **-9364.00** |
| 35 | ATR H1/กินไส้ D1 | BUY | Fibo/ATR | 3964.00 | 4126.56 | **162.56** | 3959.00 | 4105.80 | **146.80** | 4147.00 | 4166.17 | **19.17** | **-4152.00** |
| 36 | ATR H1/Div H1/Fibo M30 | SELL | Fibo | 4160.00 | 4134.69 | **25.31** | 4168.00 | 4174.38 | **6.38** | 3923.00 | 3990.33 | **67.33** | **-7938.00** |

**Group P&L:** 51596.00

## Pattern: ไม่มีท่า H1 Group

| Order | Patterns | Type | Bot Pattern | Spec Entry | Bot Entry | Entry Diff | Spec SL | Bot SL | SL Diff | Spec TP | Bot TP | TP Diff | P&L |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2 | ไม่มีท่า H1 | BUY | Inst_Gap | 4658.00 | 4664.34 | **6.34** | 4648.00 | 4580.71 | **67.29** | 5407.00 | 5082.50 | **324.50** | **83632.00** |

**Group P&L:** 83632.00

## Pattern: Fibo H1 + Div H1 Group

| Order | Patterns | Type | Bot Pattern | Spec Entry | Bot Entry | Entry Diff | Spec SL | Bot SL | SL Diff | Spec TP | Bot TP | TP Diff | P&L |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 3 | Fibo H1/Div H1 | SELL | Fibo | 5116.00 | 5091.10 | **24.90** | 5128.00 | 5163.42 | **35.42** | 4849.00 | 4905.90 | **56.90** | **37040.00** |

**Group P&L:** 37040.00

## Pattern: Fibo H1 Group

| Order | Patterns | Type | Bot Pattern | Spec Entry | Bot Entry | Entry Diff | Spec SL | Bot SL | SL Diff | Spec TP | Bot TP | TP Diff | P&L |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 4 | Fibo H1 | BUY | FVG/Fibo | 4849.00 | 4875.27 | **26.27** | 4833.00 | 4799.23 | **33.77** | 5407.00 | 5135.54 | **271.46** | **52054.00** |

**Group P&L:** 52054.00

## Pattern: Fibo M30 + FVG D1 Group

| Order | Patterns | Type | Bot Pattern | Spec Entry | Bot Entry | Entry Diff | Spec SL | Bot SL | SL Diff | Spec TP | Bot TP | TP Diff | P&L |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 6 | Fibo M30/FVG D1 | SELL | Fibo | 5238.00 | 5195.01 | **42.99** | 5249.00 | 5231.18 | **17.82** | 4405.00 | 5069.21 | **664.21** | **25160.00** |

**Group P&L:** 25160.00

## Pattern: นัยยะ H1 Group

| Order | Patterns | Type | Bot Pattern | Spec Entry | Bot Entry | Entry Diff | Spec SL | Bot SL | SL Diff | Spec TP | Bot TP | TP Diff | P&L |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 7 | นัยยะ H1 | BUY | Naiya | 4607.00 | 4653.47 | **46.47** | 4601.00 | 4602.55 | **1.55** | 4879.00 | 4908.09 | **29.09** | **-10184.00** |

**Group P&L:** -10184.00

## Pattern: Fibo  3 M15 + 1 H1 Group

| Order | Patterns | Type | Bot Pattern | Spec Entry | Bot Entry | Entry Diff | Spec SL | Bot SL | SL Diff | Spec TP | Bot TP | TP Diff | P&L |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 8 | Fibo  3 M15/1 H1 | BUY | Fibo | 4644.00 | 4715.97 | **71.97** | 4639.00 | 4684.81 | **45.81** | 4879.00 | 4852.65 | **26.35** | **27336.00** |

**Group P&L:** 27336.00

## Pattern: ไม่ทราบแน่ชัด H1 Group

| Order | Patterns | Type | Bot Pattern | Spec Entry | Bot Entry | Entry Diff | Spec SL | Bot SL | SL Diff | Spec TP | Bot TP | TP Diff | P&L |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 9 | ไม่ทราบแน่ชัด H1 | BUY | Fibo | 4772.00 | 4792.80 | **20.80** | 4765.00 | 4754.55 | **10.45** | 4879.00 | 4895.09 | **16.09** | **-7650.00** |

**Group P&L:** -7650.00

## Pattern: นัยยะ H1 + Doji H1 Group

| Order | Patterns | Type | Bot Pattern | Spec Entry | Bot Entry | Entry Diff | Spec SL | Bot SL | SL Diff | Spec TP | Bot TP | TP Diff | P&L |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 11 | นัยยะ H1/Doji H1 | SELL | Naiya | 4739.00 | 4720.45 | **18.55** | 4745.00 | 4770.47 | **25.47** | 4557.00 | 4470.36 | **86.64** | **-10004.00** |

**Group P&L:** -10004.00

## Pattern: Fibo M15 Group

| Order | Patterns | Type | Bot Pattern | Spec Entry | Bot Entry | Entry Diff | Spec SL | Bot SL | SL Diff | Spec TP | Bot TP | TP Diff | P&L |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 12 | Fibo M15 | SELL | Fibo | 4656.00 | 4625.83 | **30.17** | 4662.00 | 4647.65 | **14.35** | 4506.00 | 4506.71 | **0.71** | **23824.00** |

**Group P&L:** 23824.00

## Pattern: Doji Fibo H1 Group

| Order | Patterns | Type | Bot Pattern | Spec Entry | Bot Entry | Entry Diff | Spec SL | Bot SL | SL Diff | Spec TP | Bot TP | TP Diff | P&L |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 13 | Doji Fibo H1 | SELL | Fibo | 4747.00 | 4723.39 | **23.61** | 4752.00 | 4775.29 | **23.29** | 4665.00 | 4614.06 | **50.94** | **21866.00** |

**Group P&L:** 21866.00

## Pattern: นัยยะDoji H1 Group

| Order | Patterns | Type | Bot Pattern | Spec Entry | Bot Entry | Entry Diff | Spec SL | Bot SL | SL Diff | Spec TP | Bot TP | TP Diff | P&L |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 15 | นัยยะDoji H1 | SELL | Fibo | 4716.00 | 4707.84 | **8.16** | 4722.00 | 4752.43 | **30.43** | 4466.00 | 4626.44 | **160.44** | **16280.00** |

**Group P&L:** 16280.00

## Pattern: FVG D1 + กินไส้ H1 Group

| Order | Patterns | Type | Bot Pattern | Spec Entry | Bot Entry | Entry Diff | Spec SL | Bot SL | SL Diff | Spec TP | Bot TP | TP Diff | P&L |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 16 | FVG D1/กินไส้ H1 | SELL | FVG/Fibo | 4587.00 | 4510.40 | **76.60** | 4596.00 | 4564.20 | **31.80** | 4456.00 | 4309.30 | **146.70** | **-10760.00** |

**Group P&L:** -10760.00

## Pattern: กินไส้ H1 + Div H1 Group

| Order | Patterns | Type | Bot Pattern | Spec Entry | Bot Entry | Entry Diff | Spec SL | Bot SL | SL Diff | Spec TP | Bot TP | TP Diff | P&L |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 18 | กินไส้ H1/Div H1 | SELL | FVG/Fibo | 4578.00 | 4536.73 | **41.27** | 4580.00 | 4567.88 | **12.12** | 4368.00 | 4451.94 | **83.94** | **16958.00** |

**Group P&L:** 16958.00

## Pattern: Fibo  3 M30 + 1 H1 Group

| Order | Patterns | Type | Bot Pattern | Spec Entry | Bot Entry | Entry Diff | Spec SL | Bot SL | SL Diff | Spec TP | Bot TP | TP Diff | P&L |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 20 | Fibo  3 M30/1 H1 | SELL | Fibo | 4539.00 | 4530.12 | **8.88** | 4551.00 | 4551.88 | **0.88** | 4282.00 | 4403.09 | **121.09** | **25406.00** |

**Group P&L:** 25406.00

## Pattern: นัยยะ  Doji H1 Group

| Order | Patterns | Type | Bot Pattern | Spec Entry | Bot Entry | Entry Diff | Spec SL | Bot SL | SL Diff | Spec TP | Bot TP | TP Diff | P&L |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 21 | นัยยะ  Doji H1 | SELL | FVG/Fibo | 4514.00 | 4479.68 | **34.32** | 4519.00 | 4530.25 | **11.25** | 4282.00 | 4331.68 | **49.68** | **29600.00** |

**Group P&L:** 29600.00

## Pattern: นัยยะ D1 + FVG D1 Group

| Order | Patterns | Type | Bot Pattern | Spec Entry | Bot Entry | Entry Diff | Spec SL | Bot SL | SL Diff | Spec TP | Bot TP | TP Diff | P&L |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 22 | นัยยะ D1/FVG D1 | SELL | Naiya | 4359.00 | 4335.84 | **23.16** | 4369.00 | 4359.80 | **9.20** | 4093.00 | 4216.02 | **123.02** | **-4792.00** |

**Group P&L:** -4792.00

## Pattern: แนวต้าน H1 + นัยยะ H1 Group

| Order | Patterns | Type | Bot Pattern | Spec Entry | Bot Entry | Entry Diff | Spec SL | Bot SL | SL Diff | Spec TP | Bot TP | TP Diff | P&L |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 24 | แนวต้าน H1/นัยยะ H1 | SELL | Naiya | 4143.00 | 4119.92 | **23.08** | 4150.00 | 4162.90 | **12.90** | 4007.00 | 3905.01 | **101.99** | **-8596.00** |

**Group P&L:** -8596.00

## Pattern: MA12 H1 Group

| Order | Patterns | Type | Bot Pattern | Spec Entry | Bot Entry | Entry Diff | Spec SL | Bot SL | SL Diff | Spec TP | Bot TP | TP Diff | P&L |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 26 | MA12 H1 | SELL | FVG/Fibo | 4051.00 | 4025.34 | **25.66** | 4054.00 | 4069.83 | **15.83** | 3962.00 | 3880.67 | **81.33** | **-8898.00** |

**Group P&L:** -8898.00

## Pattern: ไม่ทราบ H1 Group

| Order | Patterns | Type | Bot Pattern | Spec Entry | Bot Entry | Entry Diff | Spec SL | Bot SL | SL Diff | Spec TP | Bot TP | TP Diff | P&L |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 27 | ไม่ทราบ H1 | BUY | FVG/Fibo | 3975.00 | 4011.53 | **36.53** | 3971.00 | 3957.60 | **13.40** | 4052.00 | 4189.04 | **137.04** | **35502.00** |

**Group P&L:** 35502.00

## Pattern: Follow Div ไม่แน่ใจ TF H1 Group

| Order | Patterns | Type | Bot Pattern | Spec Entry | Bot Entry | Entry Diff | Spec SL | Bot SL | SL Diff | Spec TP | Bot TP | TP Diff | P&L |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 29 | Follow Div ไม่แน่ใจ TF H1 | BUY | FVG/Fibo | 3974.00 | 4021.03 | **47.03** | 3969.00 | 3979.77 | **10.77** | 4087.00 | 4149.11 | **62.11** | **25616.00** |

**Group P&L:** 25616.00

## Pattern: ราคากินไส้ ไม่แน่ใจ TF H1 Group

| Order | Patterns | Type | Bot Pattern | Spec Entry | Bot Entry | Entry Diff | Spec SL | Bot SL | SL Diff | Spec TP | Bot TP | TP Diff | P&L |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 30 | ราคากินไส้ ไม่แน่ใจ TF H1 | SELL | FVG/Fibo | 4177.00 | 4143.77 | **33.23** | 4180.00 | 4184.18 | **4.18** | 3952.00 | 4040.63 | **88.63** | **20628.00** |

**Group P&L:** 20628.00

## Pattern: นัยยะ H12 Group

| Order | Patterns | Type | Bot Pattern | Spec Entry | Bot Entry | Entry Diff | Spec SL | Bot SL | SL Diff | Spec TP | Bot TP | TP Diff | P&L |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 31 | นัยยะ H12 | BUY | Naiya | 4023.00 | 4077.57 | **54.57** | 4020.00 | 4054.45 | **34.45** | 4137.00 | 4193.16 | **56.16** | **-4624.00** |

**Group P&L:** -4624.00

## Pattern: FVG H1 Group

| Order | Patterns | Type | Bot Pattern | Spec Entry | Bot Entry | Entry Diff | Spec SL | Bot SL | SL Diff | Spec TP | Bot TP | TP Diff | P&L |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 34 | FVG H1 | SELL | FVG/Fibo | 4038.00 | 4010.49 | **27.51** | 4045.00 | 4051.83 | **6.83** | 3966.00 | 3836.71 | **129.29** | **-8268.00** |

**Group P&L:** -8268.00

