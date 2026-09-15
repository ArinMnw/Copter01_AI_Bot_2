//+------------------------------------------------------------------+
//|                                          Stochastic_Preset.mq5    |
//|  Stochastic Oscillator ธรรมดา (iStochastic) แต่มาพร้อม default/     |
//|  level/สี ตามที่ตั้งไว้แล้ว %K=5, %D=3, Slowing=3                    |
//|  Level 15=-, 50=-, 85=Sell (เส้น level สีแดง)                       |
//|  เส้นหลัก (%K) และเส้นสัญญาณ (%D) สีดำทั้งคู่                         |
//+------------------------------------------------------------------+
#property copyright "Copter01 AI Bot"
#property link       ""
#property version    "1.00"
#property indicator_separate_window
#property indicator_buffers 2
#property indicator_plots   2
#property indicator_minimum 0
#property indicator_maximum 100

#property indicator_label1  "%K"
#property indicator_type1   DRAW_LINE
#property indicator_color1  clrBlack
#property indicator_style1  STYLE_SOLID
#property indicator_width1  1

#property indicator_label2  "%D"
#property indicator_type2   DRAW_LINE
#property indicator_color2  clrBlack
#property indicator_style2  STYLE_DOT
#property indicator_width2  1

// Level 15 = ขอบล่าง (oversold), 50 = เส้นกลาง, 85 = Sell zone (overbought)
#property indicator_level1     15.0
#property indicator_level2     50.0
#property indicator_level3     85.0
#property indicator_levelcolor clrRed
#property indicator_levelstyle STYLE_DOT
#property indicator_levelwidth 1

input int              InpKPeriod  = 5;              // %K period
input int              InpDPeriod  = 3;              // %D period
input int              InpSlowing  = 3;               // Slowing
input ENUM_MA_METHOD    InpMAMethod = MODE_SMA;         // MA method
input ENUM_STO_PRICE    InpPriceField = STO_LOWHIGH;    // Price field

double MainBuffer[];
double SignalBuffer[];
int    g_handle;

//+------------------------------------------------------------------+
int OnInit()
  {
   SetIndexBuffer(0, MainBuffer, INDICATOR_DATA);
   SetIndexBuffer(1, SignalBuffer, INDICATOR_DATA);
   ArraySetAsSeries(MainBuffer, true);
   ArraySetAsSeries(SignalBuffer, true);

   IndicatorSetString(INDICATOR_SHORTNAME,
      StringFormat("Stochastic Preset(%d,%d,%d)", InpKPeriod, InpDPeriod, InpSlowing));
   IndicatorSetInteger(INDICATOR_DIGITS, 2);

   g_handle = iStochastic(_Symbol, _Period, InpKPeriod, InpDPeriod, InpSlowing,
                           InpMAMethod, InpPriceField);
   if(g_handle == INVALID_HANDLE)
     {
      Print("Stochastic_Preset: iStochastic handle failed, err=", GetLastError());
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

   if(CopyBuffer(g_handle, 0, 0, rates_total, MainBuffer) <= 0)
      return(0);
   if(CopyBuffer(g_handle, 1, 0, rates_total, SignalBuffer) <= 0)
      return(0);

   return(rates_total);
  }
//+------------------------------------------------------------------+
