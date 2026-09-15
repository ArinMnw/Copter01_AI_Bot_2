//+------------------------------------------------------------------+
//|                                          ZigZagPA_Indicator.mq5   |
//|  ตัวชี้วัด (ไม่เทรดจริง) ที่ port มาจาก Pine v3 "[STRATEGY][RS]      |
//|  ZigZag PA Strategy V4.1" — ใช้เทียบภาพกับ TradingView โดยตรง       |
//|  (วาดเส้น ZigZag + label pattern บนกราฟ MT5 เหมือน Pine plot)        |
//|                                                                     |
//|  ใช้ logic เดียวกับ ZigZagPA_EA.mq5 ทุกจุด (เรียก ZigZagPA_Lib.mqh   |
//|  ตัวเดียวกัน) ต่างกันแค่ตัวนี้ไม่ส่งคำสั่งเทรด วาดภาพอย่างเดียว        |
//|  ใช้สำหรับเทียบตำแหน่งจุด X,A,B,C,D และชื่อ pattern กับ TradingView   |
//|  แบบเห็นภาพตรงๆ แทนการอ่านตัวเลขจาก log ทีละบรรทัด                   |
//+------------------------------------------------------------------+
#property copyright "Copter01 AI Bot"
#property link       ""
#property version    "1.00"
#property indicator_chart_window
#property indicator_plots 0
#property indicator_buffers 0

#include "ZigZagPA_Lib.mqh"

input bool InpUseHA        = false; // Use Heikken Ashi Candles
input bool InpUseAltTF     = true;  // Use Alt Timeframe
input int  InpAltTFMinutes = 60;    // Alt Timeframe (นาที, ตรงกับ tf="60" ของ Pine)
input int  InpCalcBars     = 300;   // จำนวนแท่ง (บน Alt/Calc TF) ย้อนหลังที่จะวาด zigzag — ต้องมากพอให้ direction state
                                     // warm-up ก่อนถึงช่วงที่สนใจ (ค่าต่ำไปทำให้ pivot ต้นๆ ผิดเพี้ยนได้ ดู
                                     // ตรงกับ ZigZagPA_EA.mq5 ที่ใช้ 300 เป็น default เดียวกัน) ยิ่งมาก ยิ่งต้องใช้ M1 history เยอะ

input bool InpShowPatterns = true;  // Show Patterns (label ชื่อ pattern บนกราฟ)
input bool InpShowFib0000  = true;  // Display Fibonacci 0.000
input bool InpShowFib0236  = true;  // Display Fibonacci 0.236
input bool InpShowFib0382  = true;  // Display Fibonacci 0.382
input bool InpShowFib0500  = true;  // Display Fibonacci 0.500
input bool InpShowFib0618  = true;  // Display Fibonacci 0.618
input bool InpShowFib0764  = true;  // Display Fibonacci 0.764
input bool InpShowFib1000  = true;  // Display Fibonacci 1.000

string   g_Prefix     = "";
datetime g_LastBarTime = 0;

//+------------------------------------------------------------------+
int OnInit()
  {
   g_Prefix = "ZZPA_" + IntegerToString(ChartID()) + "_";
   ObjectsDeleteAll(0, g_Prefix);
   g_LastBarTime = 0;
   return(INIT_SUCCEEDED);
  }

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   ObjectsDeleteAll(0, g_Prefix);
  }

//+------------------------------------------------------------------+
// รวมแท่ง M1 ให้เป็นแท่งสังเคราะห์ขนาด barMinutes นาที ตัดแท่งสุดท้าย     |
// ทิ้งถ้ายังฟอร์มไม่เสร็จ (non-repaint, เหมือน EA คู่กัน)                 |
//+------------------------------------------------------------------+
bool BuildSyntheticBars(const int barMinutes, const int barsNeeded, MqlRates &out[])
  {
   if(barMinutes <= 0)
      return(false);

   int bucketSeconds = barMinutes * 60;
   int m1Needed = barMinutes * (barsNeeded + 3);

   MqlRates m1[];
   ArraySetAsSeries(m1, false);
   int copied = CopyRates(_Symbol, PERIOD_M1, 1, m1Needed, m1); // shift=1 ข้ามแท่ง M1 ที่กำลังฟอร์ม
   if(copied <= 1)
      return(false);

   // เตือน (ไม่ได้แก้ข้อมูล) ถ้าเจอ gap ใน M1 history ของ broker — pivot ที่คำนวณจาก
   // ช่วงที่ข้อมูลขาดหายอาจไม่แม่น ไม่ใช่บั๊กโค้ด แต่ควรรู้ตัวไว้ (ยืนยันจากการสืบสวนจริง
   // ที่เจอ gap 28/60 แท่งช่วง 03:30-04:30 น. วันที่ 6 ส.ค. 2026 ของ broker IUX)
   static datetime lastWarnedGapEnd = 0;
   for(int gi = 1; gi < copied; gi++)
     {
      long gapSeconds = (long)(m1[gi].time - m1[gi-1].time);
      if(gapSeconds > 120 && m1[gi].time > lastWarnedGapEnd)
        {
         PrintFormat("ZigZagPA WARNING: M1 data gap %s -> %s (~%d นาทีหาย) — pivot ช่วงนี้อาจไม่แม่น "
                     "(ข้อมูล broker ขาดหาย ไม่ใช่บั๊กโค้ด ดู CheckM1DataGaps.mq5 เพื่อตรวจสอบละเอียด)",
                     TimeToString(m1[gi-1].time, TIME_DATE | TIME_MINUTES | TIME_SECONDS),
                     TimeToString(m1[gi].time, TIME_DATE | TIME_MINUTES | TIME_SECONDS),
                     (int)(gapSeconds / 60));
         lastWarnedGapEnd = m1[gi].time;
        }
     }

   ArrayResize(out, 0);
   ArraySetAsSeries(out, false);

   for(int i = 0; i < copied; i++)
     {
      long bucketStartLong = (((long)m1[i].time) / bucketSeconds) * bucketSeconds;
      datetime bucketStart = (datetime)bucketStartLong;
      int n = ArraySize(out);
      if(n == 0 || out[n-1].time != bucketStart)
        {
         ArrayResize(out, n + 1);
         out[n].time  = bucketStart;
         out[n].open  = m1[i].open;
         out[n].high  = m1[i].high;
         out[n].low   = m1[i].low;
         out[n].close = m1[i].close;
        }
      else
        {
         out[n-1].high  = MathMax(out[n-1].high, m1[i].high);
         out[n-1].low   = MathMin(out[n-1].low, m1[i].low);
         out[n-1].close = m1[i].close;
        }
     }

   int total = ArraySize(out);
   if(total == 0)
      return(false);

   long nowBucket = ((long)TimeCurrent() / bucketSeconds) * bucketSeconds;
   if((long)out[total-1].time == nowBucket)
     {
      ArrayResize(out, total - 1);
      total--;
     }
   return(total > 0);
  }

//+------------------------------------------------------------------+
void DrawZZSegment(const datetime t1, const double p1, const datetime t2, const double p2)
  {
   string name = g_Prefix + "ZZ_" + IntegerToString(t2);
   ObjectCreate(0, name, OBJ_TREND, 0, t1, p1, t2, p2);
   ObjectSetInteger(0, name, OBJPROP_COLOR, clrWhite);
   ObjectSetInteger(0, name, OBJPROP_WIDTH, 2);
   ObjectSetInteger(0, name, OBJPROP_RAY_RIGHT, false);
   ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, name, OBJPROP_HIDDEN, true);
  }

//+------------------------------------------------------------------+
// Label ชื่อ pattern (เช่น "Anti Shark", "ABCD") พร้อมลูกศรกำกับ — เลียนแบบ
// Pine plotshape(style=shape.labeldown/labelup): Bear=ลูกศรลงสีแดงอยู่เหนือ
// แท่ง, Bull=ลูกศรขึ้นสีเขียวอยู่ใต้แท่ง
//+------------------------------------------------------------------+
void DrawPatternLabel(const datetime t, const double p, const string text, const bool isBull)
  {
   string base = g_Prefix + "PAT_" + IntegerToString(t) + "_" + (isBull ? "B" : "S") + "_" + text;
   color clr = isBull ? clrGreen : clrMaroon;

   string arrName = base + "_ARR";
   ObjectCreate(0, arrName, OBJ_ARROW, 0, t, p);
   ObjectSetInteger(0, arrName, OBJPROP_ARROWCODE, isBull ? 233 : 234); // 233=ลูกศรขึ้น, 234=ลูกศรลง
   ObjectSetInteger(0, arrName, OBJPROP_COLOR, clr);
   ObjectSetInteger(0, arrName, OBJPROP_WIDTH, 3);
   ObjectSetInteger(0, arrName, OBJPROP_ANCHOR, isBull ? ANCHOR_TOP : ANCHOR_BOTTOM);
   ObjectSetInteger(0, arrName, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, arrName, OBJPROP_HIDDEN, true);

   string txtName = base + "_TXT";
   ObjectCreate(0, txtName, OBJ_TEXT, 0, t, p);
   ObjectSetString(0, txtName, OBJPROP_TEXT, text);
   ObjectSetInteger(0, txtName, OBJPROP_COLOR, clr);
   ObjectSetInteger(0, txtName, OBJPROP_FONTSIZE, 8);
   ObjectSetInteger(0, txtName, OBJPROP_ANCHOR, isBull ? ANCHOR_TOP : ANCHOR_BOTTOM);
   ObjectSetInteger(0, txtName, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, txtName, OBJPROP_HIDDEN, true);
  }

//+------------------------------------------------------------------+
void DrawFibLine(const string tag, const datetime t1, const datetime t2, const double price, const color clr)
  {
   string name = g_Prefix + "FIB_" + tag;
   ObjectCreate(0, name, OBJ_TREND, 0, t1, price, t2, price);
   ObjectSetInteger(0, name, OBJPROP_COLOR, clr);
   ObjectSetInteger(0, name, OBJPROP_WIDTH, 1);
   ObjectSetInteger(0, name, OBJPROP_RAY_RIGHT, true);
   ObjectSetInteger(0, name, OBJPROP_STYLE, STYLE_DOT);
   ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, name, OBJPROP_HIDDEN, true);
   ObjectSetString(0, name, OBJPROP_TEXT, "Fib " + tag);
  }

//+------------------------------------------------------------------+
int OnCalculate(const int rates_total, const int prev_calculated, const datetime &time[],
                 const double &open[], const double &high[], const double &low[], const double &close[],
                 const long &tick_volume[], const long &volume[], const int &spread[])
  {
   if(rates_total <= 0)
      return(0);

   datetime barTime = time[rates_total-1];
   if(barTime == g_LastBarTime && prev_calculated > 0)
      return(rates_total); // รอแท่งใหม่ของ chart TF เท่านั้น (ไม่ recalculate ทุก tick)
   g_LastBarTime = barTime;

   ObjectsDeleteAll(0, g_Prefix);

   int baseMinutes = (int)(PeriodSeconds(_Period) / 60);
   if(baseMinutes <= 0)
      baseMinutes = 1;
   int barMinutes = InpUseAltTF ? InpAltTFMinutes : baseMinutes;

   MqlRates bars[];
   if(!BuildSyntheticBars(barMinutes, InpCalcBars + 10, bars))
     {
      int m1Available = Bars(_Symbol, PERIOD_M1);
      int m1Needed = barMinutes * (InpCalcBars + 10 + 3);
      Comment(StringFormat("ZigZagPA: ไม่พอข้อมูล M1 (มี %d แท่ง ต้องการ ~%d แท่ง) — เปิดชาร์ต M1 ของ %s ทิ้งไว้สักครู่ให้โหลดประวัติ แล้วลองใหม่ หรือลด InpCalcBars/InpAltTFMinutes",
                             m1Available, m1Needed, _Symbol));
      Print("ZigZagPA: BuildSyntheticBars ล้มเหลว — m1Available=", m1Available, " m1Needed(ประมาณ)=", m1Needed);
      return(rates_total);
     }

   int n = ArraySize(bars);
   if(n < 10)
     {
      Comment(StringFormat("ZigZagPA: ได้แท่งสังเคราะห์แค่ %d แท่ง (ต้องการอย่างน้อย 10) — รอข้อมูลโหลดเพิ่ม หรือลด InpCalcBars", n));
      Print("ZigZagPA: synthetic bars น้อยเกินไป n=", n);
      return(rates_total);
     }
   Comment(""); // เคลียร์ข้อความเตือนถ้าคำนวณสำเร็จ

   datetime tm[];
   double o[], h[], l[], cl[];
   ArrayResize(tm, n);
   ArrayResize(o, n);
   ArrayResize(h, n);
   ArrayResize(l, n);
   ArrayResize(cl, n);
   for(int i = 0; i < n; i++)
     {
      tm[i] = bars[i].time;
      o[i]  = bars[i].open;
      h[i]  = bars[i].high;
      l[i]  = bars[i].low;
      cl[i] = bars[i].close;
     }

   double uo[], uh[], ul[], uc[];
   if(InpUseHA)
      ZZPA_ComputeHeikinAshi(o, h, l, cl, uo, uh, ul, uc);
   else
     {
      ArrayCopy(uo, o);
      ArrayCopy(uh, h);
      ArrayCopy(ul, l);
      ArrayCopy(uc, cl);
     }

   bool isPivot[];
   double pivotVal[];
   ZZPA_ComputeZigZag(tm, uo, uh, ul, uc, isPivot, pivotVal);

   int pivotCount = 0;
   for(int k = 0; k < n; k++)
      if(isPivot[k])
         pivotCount++;
   Print("ZigZagPA: synthetic bars n=", n, " (", bars[0].time, " -> ", bars[n-1].time, ") pivotCount=", pivotCount);

   // วาดเส้น zigzag เชื่อมจุดหักมุมต่อเนื่อง + label pattern ที่จุด D ของแต่ละ pivot
   int prevIdx = -1;
   int lastPivotIdx = -1;
   for(int i = 0; i < n; i++)
     {
      if(!isPivot[i])
         continue;

      if(prevIdx >= 0)
         DrawZZSegment(bars[prevIdx].time, pivotVal[prevIdx], bars[i].time, pivotVal[i]);
      prevIdx = i;
      lastPivotIdx = i;

      if(InpShowPatterns)
        {
         double x, a, b, c, d;
         if(ZZPA_GetLastPivots(isPivot, pivotVal, i, x, a, b, c, d))
           {
            double xab, xad, abc, bcd;
            if(ZZPA_CalcRatios(x, a, b, c, d, xab, xad, abc, bcd))
              {
               string bullName = ZZPA_MatchedPatternName(1, xab, xad, abc, bcd, d, c);
               if(bullName != "")
                  DrawPatternLabel(bars[i].time, pivotVal[i], bullName, true);
               string bearName = ZZPA_MatchedPatternName(-1, xab, xad, abc, bcd, d, c);
               if(bearName != "")
                  DrawPatternLabel(bars[i].time, pivotVal[i], bearName, false);
               if(bullName != "" || bearName != "")
                  PrintFormat("ZigZagPA t=%s X=%.2f A=%.2f B=%.2f C=%.2f D=%.2f xab=%.4f xad=%.4f abc=%.4f bcd=%.4f bull=%s bear=%s",
                              TimeToString(bars[i].time, TIME_DATE|TIME_MINUTES), x, a, b, c, d,
                              xab, xad, abc, bcd, bullName, bearName);
              }
           }
        }
     }

   // Fibonacci: วาดเฉพาะขา C-D ล่าสุด (เหมือนที่ Pine plot สดตอนนี้) ลากยาวไปทางขวา
   if(lastPivotIdx >= 0)
     {
      double x, a, b, c, d;
      if(ZZPA_GetLastPivots(isPivot, pivotVal, lastPivotIdx, x, a, b, c, d))
        {
         datetime tStart = bars[lastPivotIdx].time;
         datetime tEnd   = time[rates_total-1];
         if(InpShowFib0000) DrawFibLine("0.000", tStart, tEnd, ZZPA_LastFib(0.000, d, c), clrBlack);
         if(InpShowFib0236) DrawFibLine("0.236", tStart, tEnd, ZZPA_LastFib(0.236, d, c), clrRed);
         if(InpShowFib0382) DrawFibLine("0.382", tStart, tEnd, ZZPA_LastFib(0.382, d, c), clrOlive);
         if(InpShowFib0500) DrawFibLine("0.500", tStart, tEnd, ZZPA_LastFib(0.500, d, c), clrLime);
         if(InpShowFib0618) DrawFibLine("0.618", tStart, tEnd, ZZPA_LastFib(0.618, d, c), clrTeal);
         if(InpShowFib0764) DrawFibLine("0.764", tStart, tEnd, ZZPA_LastFib(0.764, d, c), clrBlue);
         if(InpShowFib1000) DrawFibLine("1.000", tStart, tEnd, ZZPA_LastFib(1.000, d, c), clrBlack);
        }
     }

   return(rates_total);
  }
//+------------------------------------------------------------------+
