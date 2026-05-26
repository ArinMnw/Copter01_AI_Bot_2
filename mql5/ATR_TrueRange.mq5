//+------------------------------------------------------------------+
//|                                              ATR_TrueRange.mq5   |
//|               Converted from TradingView Pine Script v6          |
//|  Original: indicator("Average True Range", "ATR", overlay=false) |
//+------------------------------------------------------------------+
#property copyright   ""
#property link        ""
#property version     "1.01"
#property description "Average True Range — port from TradingView (RMA/SMA/EMA/WMA)"

#property indicator_separate_window
#property indicator_buffers 2
#property indicator_plots   1

#property indicator_label1 "ATR"
#property indicator_type1  DRAW_LINE
#property indicator_color1 C'183,28,28'   // #B71C1C (เหมือน TradingView)
#property indicator_style1 STYLE_SOLID
#property indicator_width1 1

//--- enum Smoothing (dropdown ใน MT5)
enum ENUM_SMOOTH
  {
   SMOOTH_RMA = 0,  // RMA  (Wilder's MA — default)
   SMOOTH_SMA = 1,  // SMA
   SMOOTH_EMA = 2,  // EMA
   SMOOTH_WMA = 3,  // WMA
  };

//--- Inputs
input int          InpLength    = 14;         // Length
input ENUM_SMOOTH  InpSmoothing = SMOOTH_RMA; // Smoothing

//--- Buffers
double ATRBuffer[];   // plot
double TRBuffer[];    // True Range (internal)

//+------------------------------------------------------------------+
int OnInit()
  {
   //--- ผูก buffer
   SetIndexBuffer(0, ATRBuffer, INDICATOR_DATA);
   SetIndexBuffer(1, TRBuffer,  INDICATOR_CALCULATIONS);

   //--- ป้องกันกราฟกระพริบ: บอก MT5 ว่าเส้นเริ่มจาก bar ไหน
   //    บาร์ก่อนหน้านี้จะเป็น EMPTY_VALUE (ไม่วาด) แทนที่จะเป็น 0
   PlotIndexSetInteger(0, PLOT_DRAW_BEGIN, InpLength);

   //--- EMPTY_VALUE = DBL_MAX → MT5 จะข้ามบาร์นั้น ไม่วาดเส้น
   PlotIndexSetDouble(0, PLOT_EMPTY_VALUE, EMPTY_VALUE);

   //--- ชื่อ indicator
   string sm_name;
   switch(InpSmoothing)
     {
      case SMOOTH_SMA: sm_name = "SMA"; break;
      case SMOOTH_EMA: sm_name = "EMA"; break;
      case SMOOTH_WMA: sm_name = "WMA"; break;
      default:         sm_name = "RMA"; break;
     }
   IndicatorSetString(INDICATOR_SHORTNAME,
                      "ATR(" + IntegerToString(InpLength) + ", " + sm_name + ")");
   IndicatorSetInteger(INDICATOR_DIGITS, _Digits + 1);

   return(INIT_SUCCEEDED);
  }

//+------------------------------------------------------------------+
int OnCalculate(const int      rates_total,
                const int      prev_calculated,
                const datetime &time[],
                const double   &open[],
                const double   &high[],
                const double   &low[],
                const double   &close[],
                const long     &tick_volume[],
                const long     &volume[],
                const int      &spread[])
  {
   //--- ต้องมีข้อมูลพอสำหรับ seed + TR bar แรก
   if(rates_total < InpLength + 1)
      return(0);

   //--- กำหนด start bar
   //    prev_calculated == 0 → โหลดครั้งแรก คำนวณทั้งหมด
   //    prev_calculated  > 0 → มีแค่บาร์ใหม่ คำนวณแค่ bar ล่าสุด
   int start = (prev_calculated <= 0) ? 1 : prev_calculated - 1;

   //--------------------------------------------------------------
   // Step 1: True Range
   //   TR = max(H-L, |H-prevC|, |L-prevC|)
   //   bar 0: ไม่มี prevClose → ใช้แค่ H-L
   //--------------------------------------------------------------
   if(prev_calculated <= 0)
      TRBuffer[0] = high[0] - low[0];

   for(int i = MathMax(start, 1); i < rates_total; i++)
     {
      double hl  = high[i] - low[i];
      double hpc = MathAbs(high[i] - close[i - 1]);
      double lpc = MathAbs(low[i]  - close[i - 1]);
      TRBuffer[i] = MathMax(hl, MathMax(hpc, lpc));
     }

   //--------------------------------------------------------------
   // Step 2: Smoothing
   //   ป้องกันกระพริบ: บาร์ก่อน seed ตั้งค่า EMPTY_VALUE ไว้
   //   MT5 จะไม่วาดจุดนั้น (เหมือน Pine: ไม่มีค่าก่อน length บาร์)
   //--------------------------------------------------------------
   int seed = InpLength - 1;   // bar แรกที่มีค่า ATR ได้

   // ถ้าเป็นการโหลดครั้งแรก: clear บาร์ก่อน seed ไม่ให้วาด
   if(prev_calculated <= 0)
     {
      for(int i = 0; i < seed; i++)
         ATRBuffer[i] = EMPTY_VALUE;
     }

   switch(InpSmoothing)
     {
      //------------------------------------------------------------
      // SMA: ค่าเฉลี่ยธรรมดา — ไม่ขึ้นกับบาร์ก่อน → ทำ incremental ได้
      //------------------------------------------------------------
      case SMOOTH_SMA:
        {
         int from = MathMax(start, seed);
         for(int i = from; i < rates_total; i++)
           {
            double s = 0.0;
            for(int j = 0; j < InpLength; j++)
               s += TRBuffer[i - j];
            ATRBuffer[i] = s / InpLength;
           }
         break;
        }

      //------------------------------------------------------------
      // EMA: alpha = 2/(length+1)
      //   seed ครั้งแรกด้วย SMA แล้ว incremental ต่อ
      //   ทุก tick ต่อมา: คำนวณแค่บาร์เดียว (start = rates_total-1)
      //------------------------------------------------------------
      case SMOOTH_EMA:
        {
         double alpha = 2.0 / (InpLength + 1);

         if(prev_calculated <= seed + 1)
           {
            // seed = SMA ของ InpLength bars แรก
            double s = 0.0;
            for(int j = 0; j < InpLength; j++)
               s += TRBuffer[seed - j];
            ATRBuffer[seed] = s / InpLength;

            // ต่อจาก seed ไปจนสุด (ทำครั้งเดียวตอนโหลด)
            for(int i = seed + 1; i < rates_total; i++)
               ATRBuffer[i] = alpha * TRBuffer[i] + (1.0 - alpha) * ATRBuffer[i - 1];
           }
         else
           {
            // incremental: ATRBuffer[start-1] มีค่าอยู่แล้ว → คำนวณแค่ 1 บาร์
            for(int i = start; i < rates_total; i++)
               ATRBuffer[i] = alpha * TRBuffer[i] + (1.0 - alpha) * ATRBuffer[i - 1];
           }
         break;
        }

      //------------------------------------------------------------
      // WMA: Weighted MA, น้ำหนัก = length, length-1, ..., 1
      //   ไม่ขึ้นกับบาร์ก่อน → ทำ incremental ได้
      //------------------------------------------------------------
      case SMOOTH_WMA:
        {
         int from = MathMax(start, seed);
         for(int i = from; i < rates_total; i++)
           {
            double ws = 0.0, denom = 0.0;
            for(int j = 0; j < InpLength; j++)
              {
               double w  = (double)(InpLength - j);
               ws    += TRBuffer[i - j] * w;
               denom += w;
              }
            ATRBuffer[i] = ws / denom;
           }
         break;
        }

      //------------------------------------------------------------
      // RMA (Wilder's MA): alpha = 1/length
      //   seed ครั้งแรกด้วย SMA แล้ว incremental ต่อ
      //------------------------------------------------------------
      default: // SMOOTH_RMA
        {
         double alpha = 1.0 / InpLength;

         if(prev_calculated <= seed + 1)
           {
            // seed = SMA ของ InpLength bars แรก
            double s = 0.0;
            for(int j = 0; j < InpLength; j++)
               s += TRBuffer[seed - j];
            ATRBuffer[seed] = s / InpLength;

            // ต่อจาก seed ไปจนสุด (ทำครั้งเดียวตอนโหลด)
            for(int i = seed + 1; i < rates_total; i++)
               ATRBuffer[i] = alpha * TRBuffer[i] + (1.0 - alpha) * ATRBuffer[i - 1];
           }
         else
           {
            // incremental: ATRBuffer[start-1] มีค่าอยู่แล้ว → คำนวณแค่ 1 บาร์
            for(int i = start; i < rates_total; i++)
               ATRBuffer[i] = alpha * TRBuffer[i] + (1.0 - alpha) * ATRBuffer[i - 1];
           }
         break;
        }
     }

   return(rates_total);
  }
//+------------------------------------------------------------------+
