# Comparison: 36_order_spec.md vs Bot Generated Trades

This report lists all discrepancies between the specifications in `36_order_spec.md` and the actual simulated bot trades.

### Order 1 - ❌ No Match
- **Pattern Mismatch:** User='ATR 1D', Bot='Naiya'
- **TF Mismatch:** User=D1, Bot=M30
- **Entry Price Diff:** User=5590.0, Bot=5541.52 (Diff: 48.48)
- **TP Price Diff:** User=3058.0, Bot=5221.71 (Diff: 2163.71)

### Order 2 - ✅ Matched
- **TF Mismatch:** User=H1, Bot=M30
- **Entry Price Diff:** User=4658.0, Bot=4702.08 (Diff: 44.08)
- **TP Price Diff:** User=5407.0, Bot=4958.49 (Diff: 448.51)
- **Time Diff:** User=2026-02-06 07:00, Bot=2026-02-06 01:00 (Diff: -6.0 Hrs)

### Order 3 - ✅ Matched
- **TF Mismatch:** User=H1, Bot=M30
- **Entry Price Diff:** User=5116.0, Bot=5087.15 (Diff: 28.85)
- **SL Price Diff:** User=5128.0, Bot=5147.03 (Diff: 19.03)
- **TP Price Diff:** User=4849.0, Bot=4964.55 (Diff: 115.55)

### Order 4 - ✅ Matched
- **TF Mismatch:** User=H1, Bot=M15
- **Entry Price Diff:** User=4849.0, Bot=4877.98 (Diff: 28.98)
- **SL Price Diff:** User=4833.0, Bot=4841.9 (Diff: 8.9)
- **TP Price Diff:** User=5407.0, Bot=4977.15 (Diff: 429.85)

### Order 5 - ✅ Matched
- **TF Mismatch:** User=D1, Bot=M30
- **SL Price Diff:** User=5435.0, Bot=5460.42 (Diff: 25.42)
- **TP Price Diff:** User=3058.0, Bot=5158.99 (Diff: 2100.99)
- **Time Diff:** User=2026-03-02 15:00, Bot=2026-03-02 14:30 (Diff: -0.5 Hrs)

### Order 6 - ✅ Matched
- **TF Mismatch:** User=D1, Bot=M15
- **Entry Price Diff:** User=5238.0, Bot=5195.01 (Diff: 42.99)
- **SL Price Diff:** User=5249.0, Bot=5231.18 (Diff: 17.82)
- **TP Price Diff:** User=4405.0, Bot=5069.21 (Diff: 664.21)
- **Time Diff:** User=2026-03-10 22:00, Bot=2026-03-10 21:45 (Diff: -0.25 Hrs)

### Order 7 - ✅ Matched
- **TF Mismatch:** User=H1, Bot=M30
- **Entry Price Diff:** User=4607.0, Bot=4818.27 (Diff: 211.27)
- **SL Price Diff:** User=4601.0, Bot=4756.31 (Diff: 155.31)
- **TP Price Diff:** User=4879.0, Bot=5128.07 (Diff: 249.07)
- **Time Diff:** User=2026-04-07 21:00, Bot=2026-04-08 02:30 (Diff: 5.5 Hrs)

### Order 8 - ✅ Matched
- **Entry Price Diff:** User=4644.0, Bot=4715.97 (Diff: 71.97)
- **SL Price Diff:** User=4639.0, Bot=4684.81 (Diff: 45.81)
- **TP Price Diff:** User=4879.0, Bot=4852.65 (Diff: 26.35)
- **Time Diff:** User=2026-04-13 05:00, Bot=2026-04-13 05:15 (Diff: 0.25 Hrs)

### Order 9 - ✅ Matched
- **Entry Price Diff:** User=4772.0, Bot=4792.8 (Diff: 20.8)
- **SL Price Diff:** User=4765.0, Bot=4754.55 (Diff: 10.45)
- **TP Price Diff:** User=4879.0, Bot=4895.09 (Diff: 16.09)

### Order 10 - ✅ Matched
- **TF Mismatch:** User=D1, Bot=M15
- **Entry Price Diff:** User=4887.0, Bot=4799.28 (Diff: 87.72)
- **SL Price Diff:** User=4891.0, Bot=4823.93 (Diff: 67.07)
- **TP Price Diff:** User=3850.0, Bot=4745.11 (Diff: 895.11)
- **Time Diff:** User=2026-04-17 20:00, Bot=2026-04-17 06:30 (Diff: -13.5 Hrs)

### Order 13 - ✅ Matched
- **TF Mismatch:** User=H1, Bot=M30
- **Entry Price Diff:** User=4747.0, Bot=4724.17 (Diff: 22.83)
- **SL Price Diff:** User=4752.0, Bot=4760.07 (Diff: 8.07)
- **TP Price Diff:** User=4665.0, Bot=4647.35 (Diff: 17.65)

### Order 14 - ✅ Matched
- **TF Mismatch:** User=D1, Bot=H1
- **Entry Price Diff:** User=4769.0, Bot=4704.55 (Diff: 64.45)
- **SL Price Diff:** User=4775.0, Bot=4747.82 (Diff: 27.18)
- **TP Price Diff:** User=4100.0, Bot=4533.05 (Diff: 433.05)
- **Time Diff:** User=2026-05-12 07:00, Bot=2026-05-12 12:00 (Diff: 5.0 Hrs)

### Order 15 - ✅ Matched
- **Entry Price Diff:** User=4716.0, Bot=4707.84 (Diff: 8.16)
- **SL Price Diff:** User=4722.0, Bot=4754.67 (Diff: 32.67)
- **TP Price Diff:** User=4466.0, Bot=4626.44 (Diff: 160.44)

### Order 16 - ✅ Matched
- **TF Mismatch:** User=D1, Bot=H1
- **Entry Price Diff:** User=4587.0, Bot=4510.4 (Diff: 76.6)
- **SL Price Diff:** User=4596.0, Bot=4564.2 (Diff: 31.8)
- **TP Price Diff:** User=4456.0, Bot=4309.3 (Diff: 146.7)
- **Time Diff:** User=2026-05-19 20:00, Bot=2026-05-19 18:00 (Diff: -2.0 Hrs)

### Order 17 - ✅ Matched
- **TF Mismatch:** User=H1, Bot=M15
- **Entry Price Diff:** User=4462.0, Bot=4530.24 (Diff: 68.24)
- **SL Price Diff:** User=4454.0, Bot=4507.05 (Diff: 53.05)
- **TP Price Diff:** User=4568.0, Bot=4593.91 (Diff: 25.91)
- **Time Diff:** User=2026-05-20 07:00, Bot=2026-05-21 06:00 (Diff: 23.0 Hrs)

### Order 18 - ✅ Matched
- **Entry Price Diff:** User=4578.0, Bot=4536.73 (Diff: 41.27)
- **SL Price Diff:** User=4580.0, Bot=4567.88 (Diff: 12.12)
- **TP Price Diff:** User=4368.0, Bot=4451.94 (Diff: 83.94)
- **Time Diff:** User=2026-05-26 06:00, Bot=2026-05-26 05:00 (Diff: -1.0 Hrs)

### Order 19 - ✅ Matched
- **TF Mismatch:** User=D1, Bot=H1
- **Entry Price Diff:** User=4590.0, Bot=4517.29 (Diff: 72.71)
- **SL Price Diff:** User=4598.0, Bot=4569.13 (Diff: 28.87)
- **TP Price Diff:** User=4093.0, Bot=4329.94 (Diff: 236.94)
- **Time Diff:** User=2026-05-29 22:00, Bot=2026-05-29 03:00 (Diff: -19.0 Hrs)

### Order 20 - ✅ Matched
- **Entry Price Diff:** User=4539.0, Bot=4530.12 (Diff: 8.88)
- **TP Price Diff:** User=4282.0, Bot=4403.09 (Diff: 121.09)

### Order 21 - ✅ Matched
- **Entry Price Diff:** User=4514.0, Bot=4479.68 (Diff: 34.32)
- **SL Price Diff:** User=4519.0, Bot=4530.25 (Diff: 11.25)
- **TP Price Diff:** User=4282.0, Bot=4331.68 (Diff: 49.68)

### Order 22 - ✅ Matched
- **TF Mismatch:** User=D1, Bot=M30
- **Entry Price Diff:** User=4359.0, Bot=4335.84 (Diff: 23.16)
- **SL Price Diff:** User=4369.0, Bot=4359.8 (Diff: 9.2)
- **TP Price Diff:** User=4093.0, Bot=4216.02 (Diff: 123.02)
- **Time Diff:** User=2026-06-09 20:00, Bot=2026-06-09 15:30 (Diff: -4.5 Hrs)

### Order 23 - ✅ Matched
- **TF Mismatch:** User=D1, Bot=H1
- **Entry Price Diff:** User=4380.0, Bot=4266.04 (Diff: 113.96)
- **SL Price Diff:** User=4387.0, Bot=4337.73 (Diff: 49.27)
- **TP Price Diff:** User=3971.0, Bot=4002.06 (Diff: 31.06)

### Order 24 - ✅ Matched
- **Entry Price Diff:** User=4143.0, Bot=4119.92 (Diff: 23.08)
- **SL Price Diff:** User=4150.0, Bot=4162.9 (Diff: 12.9)
- **TP Price Diff:** User=4007.0, Bot=3905.01 (Diff: 101.99)
- **Time Diff:** User=2026-06-23 21:00, Bot=2026-06-23 15:00 (Diff: -6.0 Hrs)

### Order 25 - ✅ Matched
- **TF Mismatch:** User=D1, Bot=M30
- **Entry Price Diff:** User=3961.0, Bot=4023.77 (Diff: 62.77)
- **SL Price Diff:** User=3953.0, Bot=3978.8 (Diff: 25.8)
- **TP Price Diff:** User=4089.0, Bot=4135.7 (Diff: 46.7)
- **Time Diff:** User=2026-06-25 01:00, Bot=2026-06-25 21:30 (Diff: 20.5 Hrs)

### Order 26 - ✅ Matched
- **TF Mismatch:** User=H1, Bot=M15
- **Entry Price Diff:** User=4051.0, Bot=4025.31 (Diff: 25.69)
- **SL Price Diff:** User=4054.0, Bot=4043.57 (Diff: 10.43)
- **TP Price Diff:** User=3962.0, Bot=3941.84 (Diff: 20.16)
- **Time Diff:** User=2026-06-29 20:00, Bot=2026-06-29 20:15 (Diff: 0.25 Hrs)

### Order 27 - ✅ Matched
- **TF Mismatch:** User=H1, Bot=M15
- **Entry Price Diff:** User=3975.0, Bot=4013.46 (Diff: 38.46)
- **SL Price Diff:** User=3971.0, Bot=3985.91 (Diff: 14.91)
- **TP Price Diff:** User=4052.0, Bot=4119.5 (Diff: 67.5)
- **Time Diff:** User=2026-06-30 12:00, Bot=2026-06-30 11:30 (Diff: -0.5 Hrs)

### Order 28 - ✅ Matched
- **TF Mismatch:** User=H1, Bot=M15
- **Entry Price Diff:** User=4063.0, Bot=4033.44 (Diff: 29.56)
- **SL Price Diff:** User=4065.0, Bot=4048.72 (Diff: 16.28)
- **TP Price Diff:** User=3971.0, Bot=3992.8 (Diff: 21.8)
- **Time Diff:** User=2026-06-30 21:00, Bot=2026-06-30 15:15 (Diff: -5.75 Hrs)

### Order 29 - ✅ Matched
- **TF Mismatch:** User=H1, Bot=M15
- **Entry Price Diff:** User=3974.0, Bot=4018.73 (Diff: 44.73)
- **SL Price Diff:** User=3969.0, Bot=3997.13 (Diff: 28.13)
- **TP Price Diff:** User=4087.0, Bot=4140.61 (Diff: 53.61)

### Order 30 - ✅ Matched
- **Entry Price Diff:** User=4177.0, Bot=4143.77 (Diff: 33.23)
- **TP Price Diff:** User=3952.0, Bot=4040.63 (Diff: 88.63)
- **Time Diff:** User=2026-07-07 20:00, Bot=2026-07-07 19:00 (Diff: -1.0 Hrs)

### Order 31 - ✅ Matched
- **TF Mismatch:** User=H12, Bot=M30
- **Entry Price Diff:** User=4023.0, Bot=4077.57 (Diff: 54.57)
- **SL Price Diff:** User=4020.0, Bot=4054.45 (Diff: 34.45)
- **TP Price Diff:** User=4137.0, Bot=4193.16 (Diff: 56.16)
- **Time Diff:** User=2026-07-08 22:00, Bot=2026-07-09 02:30 (Diff: 4.5 Hrs)

### Order 32 - ✅ Matched
- **TF Mismatch:** User=H1, Bot=M30
- **Entry Price Diff:** User=4072.0, Bot=4100.54 (Diff: 28.54)
- **TP Price Diff:** User=4120.0, Bot=4173.38 (Diff: 53.38)

### Order 33 - ❌ No Match
- **Pattern Mismatch:** User='ATR 1H', Bot='FVG/Fibo'
- **TF Mismatch:** User=H1, Bot=M30
- **Entry Price Diff:** User=4096.0, Bot=4053.04 (Diff: 42.96)
- **SL Price Diff:** User=4100.0, Bot=4084.24 (Diff: 15.76)
- **TP Price Diff:** User=3963.0, Bot=3908.78 (Diff: 54.22)

### Order 34 - ✅ Matched
- **TF Mismatch:** User=H1, Bot=M30
- **Entry Price Diff:** User=4038.0, Bot=4015.89 (Diff: 22.11)
- **SL Price Diff:** User=4045.0, Bot=4058.71 (Diff: 13.71)
- **TP Price Diff:** User=3966.0, Bot=3903.27 (Diff: 62.73)
- **Time Diff:** User=2026-07-16 19:00, Bot=2026-07-16 17:30 (Diff: -1.5 Hrs)

### Order 35 - ✅ Matched
- **TF Mismatch:** User=D1, Bot=M15
- **Entry Price Diff:** User=3964.0, Bot=4126.56 (Diff: 162.56)
- **SL Price Diff:** User=3959.0, Bot=4105.8 (Diff: 146.8)
- **TP Price Diff:** User=4147.0, Bot=4166.17 (Diff: 19.17)
- **Time Diff:** User=2026-07-22 22:00, Bot=2026-07-23 03:45 (Diff: 5.75 Hrs)

### Order 36 - ✅ Matched
- **Entry Price Diff:** User=4160.0, Bot=4134.69 (Diff: 25.31)
- **SL Price Diff:** User=4168.0, Bot=4174.38 (Diff: 6.38)
- **TP Price Diff:** User=3923.0, Bot=3990.33 (Diff: 67.33)
