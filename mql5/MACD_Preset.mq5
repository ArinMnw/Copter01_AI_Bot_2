//+------------------------------------------------------------------+
//|                                                MACD_Preset.mq5    |
//|  MACD ธรรมดา (iMACD) แต่มาพร้อม default/สี ตามที่ตั้งไว้แล้ว          |
//|  Fast=12, Slow=26, Signal=1, ไม่มี level                            |
//|  เส้นหลัก (MACD) สีม่วง, เส้นสัญญาณ (Signal) สีแดง                    |
//+------------------------------------------------------------------+
#property copyright "Copter01 AI Bot"
#property link       ""
#property version    "1.00"
#property indicator_separate_window
#property indicator_buffers 2
#property indicator_plots   2

#property indicator_label1  "MACD"
#property indicator_type1   DRAW_LINE
#property indicator_color1  clrPurple
#property indicator_style1  STYLE_SOLID
#property indicator_width1  1

#property indicator_label2  "Signal"
#property indicator_type2   DRAW_LINE
#property indicator_color2  clrRed
#property indicator_style2  STYLE_SOLID
#property indicator_width2  1

input int                InpFastEMA   = 12;         // Fast EMA period
input int                InpSlowEMA   = 26;         // Slow EMA period
input int                InpSignalEMA = 1;           // Signal period
input ENUM_APPLIED_PRICE InpAppliedPrice = PRICE_CLOSE; // Applied Price

double MacdBuffer[];
double SignalBuffer[];
int    g_handle;

//+------------------------------------------------------------------+
int OnInit()
  {
   SetIndexBuffer(0, MacdBuffer, INDICATOR_DATA);
   SetIndexBuffer(1, SignalBuffer, INDICATOR_DATA);
   ArraySetAsSeries(MacdBuffer, true);
   ArraySetAsSeries(SignalBuffer, true);

   IndicatorSetString(INDICATOR_SHORTNAME,
      StringFormat("MACD Preset(%d,%d,%d)", InpFastEMA, InpSlowEMA, InpSignalEMA));
   IndicatorSetInteger(INDICATOR_DIGITS, _Digits);

   g_handle = iMACD(_Symbol, _Period, InpFastEMA, InpSlowEMA, InpSignalEMA, InpAppliedPrice);
   if(g_handle == INVALID_HANDLE)
     {
      Print("MACD_Preset: iMACD handle failed, err=", GetLastError());
      return(INIT_FAILED);
     }
   return(INIT_SUCCEEDED);
  }

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   if(g_handle != INVALID_HANDLE)
      IndicatorRelease(g_handle);
  }

//+------------------------------------------------------------------+
int OnCalculate(const int rates_total,
                 const int prev_calculated,
                 const datetime &time[],
                 const double &open[],
                 const double &high[],
                 const double &low[],
                 const double &close[],
                 const long &tick_volume[],
                 const long &volume[],
                 const int &spread[])
  {
   if(BarsCalculated(g_handle) < rates_total)
      return(0);

   if(CopyBuffer(g_handle, 0, 0, rates_total, MacdBuffer) <= 0)
      return(0);
   if(CopyBuffer(g_handle, 1, 0, rates_total, SignalBuffer) <= 0)
      return(0);

   return(rates_total);
  }
//+------------------------------------------------------------------+
