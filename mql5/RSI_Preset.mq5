//+------------------------------------------------------------------+
//|                                                 RSI_Preset.mq5    |
//|  RSI ธรรมดา (iRSI) แต่มาพร้อม default/level/สี ตามที่ตั้งไว้แล้ว     |
//|  Period=14, Level 10=Buy, 50=TP, 90=- (เส้น level สีเขียว)          |
//|  เส้นหลัก RSI สีดำ                                                  |
//+------------------------------------------------------------------+
#property copyright "Copter01 AI Bot"
#property link       ""
#property version    "1.00"
#property indicator_separate_window
#property indicator_buffers 1
#property indicator_plots   1
#property indicator_minimum 0
#property indicator_maximum 100

#property indicator_label1  "RSI"
#property indicator_type1   DRAW_LINE
#property indicator_color1  clrBlack
#property indicator_style1  STYLE_SOLID
#property indicator_width1  1

// Level 10 = Buy zone, 50 = TP reference, 90 = ขอบบน (overbought)
#property indicator_level1     10.0
#property indicator_level2     50.0
#property indicator_level3     90.0
#property indicator_levelcolor clrGreen
#property indicator_levelstyle STYLE_DOT
#property indicator_levelwidth 1

input int                InpPeriod = 14;             // RSI Period
input ENUM_APPLIED_PRICE InpAppliedPrice = PRICE_CLOSE; // Applied Price

double RSIBuffer[];
int    g_handle;

//+------------------------------------------------------------------+
int OnInit()
  {
   SetIndexBuffer(0, RSIBuffer, INDICATOR_DATA);
   ArraySetAsSeries(RSIBuffer, true);
   PlotIndexSetString(0, PLOT_LABEL, "RSI(" + IntegerToString(InpPeriod) + ")");
   IndicatorSetString(INDICATOR_SHORTNAME, "RSI Preset(" + IntegerToString(InpPeriod) + ")");
   IndicatorSetInteger(INDICATOR_DIGITS, 2);

   g_handle = iRSI(_Symbol, _Period, InpPeriod, InpAppliedPrice);
   if(g_handle == INVALID_HANDLE)
     {
      Print("RSI_Preset: iRSI handle failed, err=", GetLastError());
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

   int copied = CopyBuffer(g_handle, 0, 0, rates_total, RSIBuffer);
   if(copied <= 0)
      return(0);

   return(rates_total);
  }
//+------------------------------------------------------------------+
