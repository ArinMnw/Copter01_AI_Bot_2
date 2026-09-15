//+------------------------------------------------------------------+
//|                                          CheckM1DataGaps.mq5      |
//|  Script ตรวจสอบว่า M1 history ของ symbol ปัจจุบัน (บน broker/account |
//|  ที่ terminal นี้ login อยู่) มีช่วงที่ข้อมูลขาดหาย (gap) ในช่วงเวลา   |
//|  ที่กำหนดหรือไม่ — ใช้ตรวจสอบว่าความต่างของ pivot ระหว่าง MQL5/Python  |
//|  กับ TradingView มาจาก data gap ของ broker จริงหรือเปล่า             |
//|                                                                     |
//|  วิธีใช้: ลาก script นี้ไปวางบนชาร์ตของ symbol ที่ต้องการเช็ค          |
//|  (เช่น XAUUSD.iux) แล้วตั้งค่า InpStartTime/InpEndTime เป็นเวลา       |
//|  MT5 server time ตรงๆ (เวลาที่เห็นบนแท่งกราฟ/Journal ปกติ ไม่ต้อง      |
//|  แปลง timezone ใดๆ)                                                 |
//+------------------------------------------------------------------+
#property copyright "Copter01 AI Bot"
#property script_show_inputs

input datetime InpStartTime           = D'2026.08.06 03:00:00'; // เริ่ม (MT5 server time)
input datetime InpEndTime             = D'2026.08.06 05:00:00'; // สิ้นสุด (MT5 server time)
input int      InpGapThresholdSeconds = 120;  // ถือว่าเป็น gap ถ้าห่างกันเกินกี่วินาที (default 120 = ขาดอย่างน้อย 1 แท่ง)
input bool     InpDumpAllBars         = true; // เขียนแท่งทุกแท่งลงไฟล์ CSV ด้วยไหม (ไม่ใช่แค่สรุป gap)

//+------------------------------------------------------------------+
void OnStart()
  {
   if(InpEndTime <= InpStartTime)
     {
      Print("CheckM1DataGaps: InpEndTime ต้องมากกว่า InpStartTime");
      return;
     }

   MqlRates rates[];
   ArraySetAsSeries(rates, false);
   int copied = CopyRates(_Symbol, PERIOD_M1, InpStartTime, InpEndTime, rates);
   if(copied <= 0)
     {
      PrintFormat("CheckM1DataGaps: ไม่พบข้อมูล M1 ในช่วงที่ระบุ (copied=%d, err=%d)", copied, GetLastError());
      return;
     }

   int expectedBars = (int)((InpEndTime - InpStartTime) / 60) + 1;
   int missingBars   = expectedBars - copied;
   double missingPct = 100.0 * missingBars / expectedBars;

   PrintFormat("=== CheckM1DataGaps: %s ===", _Symbol);
   PrintFormat("ช่วงที่ขอ: %s -> %s", TimeToString(InpStartTime, TIME_DATE | TIME_MINUTES | TIME_SECONDS),
               TimeToString(InpEndTime, TIME_DATE | TIME_MINUTES | TIME_SECONDS));
   PrintFormat("แท่งที่คาดหวัง (ทุกนาที): %d แท่ง | แท่งที่มีจริง: %d แท่ง | ขาดหายไป: %d แท่ง (%.1f%%)",
               expectedBars, copied, missingBars, missingPct);

   // --- เดินหา gap ระหว่างแท่งที่มีอยู่จริง ---
   int gapCount = 0;
   int gapBarsTotal = 0;
   for(int i = 1; i < copied; i++)
     {
      long diffSeconds = (long)(rates[i].time - rates[i-1].time);
      if(diffSeconds > InpGapThresholdSeconds)
        {
         gapCount++;
         int missingHere = (int)(diffSeconds / 60) - 1;
         gapBarsTotal += missingHere;
         PrintFormat("  GAP #%d: %s -> %s (ห่างกัน %d วินาที ~ ขาดไปประมาณ %d แท่ง)",
                     gapCount,
                     TimeToString(rates[i-1].time, TIME_DATE | TIME_MINUTES | TIME_SECONDS),
                     TimeToString(rates[i].time, TIME_DATE | TIME_MINUTES | TIME_SECONDS),
                     diffSeconds, missingHere);
        }
     }

   // --- เช็คขอบเขตต้น/ท้ายด้วย (ข้อมูลอาจขาดตรงต้นหรือท้ายช่วงที่ขอ ไม่ใช่แค่ตรงกลาง) ---
   long headGapSeconds = (long)(rates[0].time - InpStartTime);
   long tailGapSeconds = (long)(InpEndTime - rates[copied-1].time);
   if(headGapSeconds > InpGapThresholdSeconds)
      PrintFormat("  GAP ที่ต้นช่วง: ขอเริ่ม %s แต่แท่งแรกที่มีจริงคือ %s (ขาดไป ~%d แท่ง)",
                  TimeToString(InpStartTime, TIME_MINUTES | TIME_SECONDS),
                  TimeToString(rates[0].time, TIME_MINUTES | TIME_SECONDS), (int)(headGapSeconds / 60));
   if(tailGapSeconds > InpGapThresholdSeconds)
      PrintFormat("  GAP ที่ท้ายช่วง: แท่งสุดท้ายที่มีจริงคือ %s แต่ขอถึง %s (ขาดไป ~%d แท่ง)",
                  TimeToString(rates[copied-1].time, TIME_MINUTES | TIME_SECONDS),
                  TimeToString(InpEndTime, TIME_MINUTES | TIME_SECONDS), (int)(tailGapSeconds / 60));

   if(gapCount == 0 && headGapSeconds <= InpGapThresholdSeconds && tailGapSeconds <= InpGapThresholdSeconds)
      Print("  สรุป: ไม่พบ gap เลยในช่วงนี้ — ข้อมูลครบ");
   else
      PrintFormat("  สรุป: พบ gap รวม %d จุด (ไม่รวมขอบเขตต้น/ท้าย) ขาดไปรวมประมาณ %d แท่ง", gapCount, gapBarsTotal);

   // --- เขียนไฟล์ CSV สรุป (และ dump ทุกแท่งถ้าเปิด InpDumpAllBars) ---
   string fname = StringFormat("M1GapReport_%s_%s.csv", _Symbol,
                                TimeToString(InpStartTime, TIME_DATE));
   StringReplace(fname, ".", "-");
   StringReplace(fname, ":", "-");
   StringReplace(fname, " ", "_");
   int handle = FileOpen(fname, FILE_WRITE | FILE_CSV | FILE_ANSI, ',');
   if(handle != INVALID_HANDLE)
     {
      FileWrite(handle, "summary_expected", "summary_actual", "summary_missing", "summary_missing_pct");
      FileWrite(handle, expectedBars, copied, missingBars, DoubleToString(missingPct, 2));
      FileWrite(handle, "");
      FileWrite(handle, "gap_index", "before_time", "after_time", "gap_seconds", "missing_bars_est");
      int gi = 0;
      for(int i = 1; i < copied; i++)
        {
         long diffSeconds = (long)(rates[i].time - rates[i-1].time);
         if(diffSeconds > InpGapThresholdSeconds)
           {
            gi++;
            FileWrite(handle, gi, TimeToString(rates[i-1].time, TIME_DATE | TIME_MINUTES | TIME_SECONDS),
                      TimeToString(rates[i].time, TIME_DATE | TIME_MINUTES | TIME_SECONDS),
                      diffSeconds, (int)(diffSeconds / 60) - 1);
           }
        }
      if(InpDumpAllBars)
        {
         FileWrite(handle, "");
         FileWrite(handle, "bar_time", "open", "high", "low", "close", "tick_volume");
         for(int i = 0; i < copied; i++)
            FileWrite(handle, TimeToString(rates[i].time, TIME_DATE | TIME_MINUTES | TIME_SECONDS),
                      DoubleToString(rates[i].open, _Digits), DoubleToString(rates[i].high, _Digits),
                      DoubleToString(rates[i].low, _Digits), DoubleToString(rates[i].close, _Digits),
                      rates[i].tick_volume);
        }
      FileClose(handle);
      PrintFormat("เขียนรายงานเต็มลงไฟล์: MQL5/Files/%s", fname);
     }
   else
      PrintFormat("CheckM1DataGaps: เขียนไฟล์ %s ไม่สำเร็จ err=%d", fname, GetLastError());
  }
//+------------------------------------------------------------------+
