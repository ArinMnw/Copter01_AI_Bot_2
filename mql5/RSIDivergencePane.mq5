//+------------------------------------------------------------------+
//|                                           RSIDivergencePane.mq5  |
//|  RSI Divergence indicator in separate pane for Strategy 9.      |
//+------------------------------------------------------------------+
#property copyright   "Copter01 AI Bot"
#property link        ""
#property version     "2.10"
#property indicator_separate_window
#property indicator_minimum 0
#property indicator_maximum 100
#property indicator_level1 30
#property indicator_level2 50
#property indicator_level3 70
#property indicator_levelcolor clrDimGray
#property indicator_levelstyle STYLE_DOT
#property indicator_buffers 5
#property indicator_plots 5

#property indicator_label1  "RSI"
#property indicator_type1   DRAW_LINE
#property indicator_color1  clrDeepSkyBlue
#property indicator_style1  STYLE_SOLID
#property indicator_width1  2

#property indicator_label2  "Regular Bullish"
#property indicator_type2   DRAW_ARROW
#property indicator_color2  clrLimeGreen
#property indicator_style2  STYLE_SOLID
#property indicator_width2  2

#property indicator_label3  "Hidden Bullish"
#property indicator_type3   DRAW_ARROW
#property indicator_color3  clrDarkGreen
#property indicator_style3  STYLE_SOLID
#property indicator_width3  1

#property indicator_label4  "Regular Bearish"
#property indicator_type4   DRAW_ARROW
#property indicator_color4  clrTomato
#property indicator_style4  STYLE_SOLID
#property indicator_width4  2

#property indicator_label5  "Hidden Bearish"
#property indicator_type5   DRAW_ARROW
#property indicator_color5  clrDarkRed
#property indicator_style5  STYLE_SOLID
#property indicator_width5  1

input int   InpRsiPeriod             = 14;            // ช่วงเวลา RSI
input ENUM_APPLIED_PRICE InpRsiSource = PRICE_CLOSE;  // ฐานข้อมูล RSI
input int   InpPivotLookbackRight    = 5;             // Pivot Lookback Right
input int   InpPivotLookbackLeft     = 5;             // Pivot Lookback Left
input int   InpLookbackRangeMax      = 60;            // Max of Lookback Range
input int   InpLookbackRangeMin      = 5;             // Min of Lookback Range
input bool  InpPlotBullish           = true;          // Plot Bullish
input bool  InpPlotHiddenBullish     = false;         // Plot Hidden Bullish
input bool  InpPlotBearish           = true;          // Plot Bearish
input bool  InpPlotHiddenBearish     = false;         // Plot Hidden Bearish
input color InpRsiColor              = clrDeepSkyBlue;
input int   InpRsiWidth              = 2;
input bool  InpDrawDivergenceLines   = true;          // Draw Bull/Bear lines
input int   InpLineWidth             = 2;             // Divergence line width
input ENUM_LINE_STYLE InpLineStyle   = STYLE_SOLID;   // Divergence line style

double g_rsi_buffer[];
double g_bull_buffer[];
double g_hidden_bull_buffer[];
double g_bear_buffer[];
double g_hidden_bear_buffer[];
int    g_rsi_handle = INVALID_HANDLE;
string g_obj_prefix = "RSIDivPane_";
string g_indicator_short_name = "RSI Divergence Indicator";

//+------------------------------------------------------------------+
bool IsPivotLow(const double &values[], const int index, const int left, const int right)
  {
   if(index - left < 0 || index + right >= ArraySize(values))
      return(false);

   const double center = values[index];
   if(center == EMPTY_VALUE)
      return(false);

   for(int i = index - left; i <= index + right; i++)
     {
      if(i == index)
         continue;
      if(values[i] == EMPTY_VALUE || center >= values[i])
         return(false);
     }
   return(true);
  }

//+------------------------------------------------------------------+
bool IsPivotHigh(const double &values[], const int index, const int left, const int right)
  {
   if(index - left < 0 || index + right >= ArraySize(values))
      return(false);

   const double center = values[index];
   if(center == EMPTY_VALUE)
      return(false);

   for(int i = index - left; i <= index + right; i++)
     {
      if(i == index)
         continue;
      if(values[i] == EMPTY_VALUE || center <= values[i])
         return(false);
     }
   return(true);
  }

//+------------------------------------------------------------------+
int FindPreviousPivot(const int &pivots[], const int pivot_count, const int current_index,
                      const int min_range, const int max_range)
  {
   for(int i = pivot_count - 1; i >= 0; i--)
     {
      const int prev_index = pivots[i];
      if(prev_index <= current_index)
         continue;
      const int gap = prev_index - current_index;
      if(gap >= min_range && gap <= max_range)
         return(prev_index);
     }
   return(-1);
  }

//+------------------------------------------------------------------+
void ResetSignalBuffers(const int rates_total)
  {
   for(int i = 0; i < rates_total; i++)
     {
      g_bull_buffer[i] = EMPTY_VALUE;
      g_hidden_bull_buffer[i] = EMPTY_VALUE;
      g_bear_buffer[i] = EMPTY_VALUE;
     g_hidden_bear_buffer[i] = EMPTY_VALUE;
     }
  }

//+------------------------------------------------------------------+
int GetPaneWindow()
  {
   const int wnd = ChartWindowFind(0, g_indicator_short_name);
   return(wnd >= 0 ? wnd : 1);
  }

//+------------------------------------------------------------------+
void ClearDivergenceObjects()
  {
   const int total = ObjectsTotal(0, -1, -1);
   for(int i = total - 1; i >= 0; i--)
     {
      const string name = ObjectName(0, i, -1, -1);
      if(StringFind(name, g_obj_prefix) == 0)
         ObjectDelete(0, name);
     }
  }

//+------------------------------------------------------------------+
void DrawDivergenceLine(const string kind,
                        const int prev_index,
                        const int cur_index,
                        const datetime &time[],
                        const color clr,
                        const int width,
                        const ENUM_LINE_STYLE style)
  {
   if(!InpDrawDivergenceLines)
      return;
   if(prev_index < 0 || cur_index < 0)
      return;
   if(g_rsi_buffer[prev_index] == EMPTY_VALUE || g_rsi_buffer[cur_index] == EMPTY_VALUE)
      return;

   const int wnd = GetPaneWindow();
   const string name = g_obj_prefix + kind + "_" + IntegerToString(prev_index) + "_" + IntegerToString(cur_index);
   if(ObjectFind(0, name) < 0)
     {
      if(!ObjectCreate(0, name, OBJ_TREND, wnd, time[prev_index], g_rsi_buffer[prev_index], time[cur_index], g_rsi_buffer[cur_index]))
         return;
     }

   ObjectSetInteger(0, name, OBJPROP_TIME, 0, time[prev_index]);
   ObjectSetDouble(0, name, OBJPROP_PRICE, 0, g_rsi_buffer[prev_index]);
   ObjectSetInteger(0, name, OBJPROP_TIME, 1, time[cur_index]);
   ObjectSetDouble(0, name, OBJPROP_PRICE, 1, g_rsi_buffer[cur_index]);

   ObjectSetInteger(0, name, OBJPROP_COLOR, clr);
   ObjectSetInteger(0, name, OBJPROP_WIDTH, width);
   ObjectSetInteger(0, name, OBJPROP_STYLE, style);
   ObjectSetInteger(0, name, OBJPROP_RAY_RIGHT, false);
   ObjectSetInteger(0, name, OBJPROP_RAY_LEFT, false);
   ObjectSetInteger(0, name, OBJPROP_BACK, false);
   ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, name, OBJPROP_SELECTED, false);
   ObjectSetInteger(0, name, OBJPROP_HIDDEN, true);
  }

//+------------------------------------------------------------------+
int OnInit()
  {
   SetIndexBuffer(0, g_rsi_buffer, INDICATOR_DATA);
   SetIndexBuffer(1, g_bull_buffer, INDICATOR_DATA);
   SetIndexBuffer(2, g_hidden_bull_buffer, INDICATOR_DATA);
   SetIndexBuffer(3, g_bear_buffer, INDICATOR_DATA);
   SetIndexBuffer(4, g_hidden_bear_buffer, INDICATOR_DATA);

   ArraySetAsSeries(g_rsi_buffer, true);
   ArraySetAsSeries(g_bull_buffer, true);
   ArraySetAsSeries(g_hidden_bull_buffer, true);
   ArraySetAsSeries(g_bear_buffer, true);
   ArraySetAsSeries(g_hidden_bear_buffer, true);

   PlotIndexSetInteger(0, PLOT_LINE_COLOR, InpRsiColor);
   PlotIndexSetInteger(0, PLOT_LINE_WIDTH, InpRsiWidth);
   PlotIndexSetString(0, PLOT_LABEL, "RSI");
   PlotIndexSetDouble(0, PLOT_EMPTY_VALUE, EMPTY_VALUE);

   PlotIndexSetInteger(1, PLOT_ARROW, 241);
   PlotIndexSetInteger(2, PLOT_ARROW, 241);
   PlotIndexSetInteger(3, PLOT_ARROW, 242);
   PlotIndexSetInteger(4, PLOT_ARROW, 242);

   PlotIndexSetDouble(1, PLOT_EMPTY_VALUE, EMPTY_VALUE);
   PlotIndexSetDouble(2, PLOT_EMPTY_VALUE, EMPTY_VALUE);
   PlotIndexSetDouble(3, PLOT_EMPTY_VALUE, EMPTY_VALUE);
   PlotIndexSetDouble(4, PLOT_EMPTY_VALUE, EMPTY_VALUE);

   IndicatorSetString(
      INDICATOR_SHORTNAME,
      g_indicator_short_name
   );

   g_rsi_handle = iRSI(_Symbol, _Period, InpRsiPeriod, InpRsiSource);
   if(g_rsi_handle == INVALID_HANDLE)
     {
      Print("RSIDivergencePane: failed to create iRSI handle. err=", GetLastError());
      return(INIT_FAILED);
     }

   return(INIT_SUCCEEDED);
  }

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   ClearDivergenceObjects();
   if(g_rsi_handle != INVALID_HANDLE)
      IndicatorRelease(g_rsi_handle);
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
   if(rates_total <= InpRsiPeriod + InpPivotLookbackLeft + InpPivotLookbackRight + 5)
      return(0);

   if(CopyBuffer(g_rsi_handle, 0, 0, rates_total, g_rsi_buffer) <= 0)
     {
      Print("RSIDivergencePane: CopyBuffer failed. err=", GetLastError());
      return(prev_calculated);
     }

   ResetSignalBuffers(rates_total);

   static int low_pivots[2048];
   static int high_pivots[2048];
   int low_count = 0;
   int high_count = 0;

   for(int i = rates_total - 1; i >= 0; i--)
     {
      if(IsPivotLow(g_rsi_buffer, i, InpPivotLookbackLeft, InpPivotLookbackRight))
        {
         if(low_count < ArraySize(low_pivots))
            low_pivots[low_count++] = i;
        }
      if(IsPivotHigh(g_rsi_buffer, i, InpPivotLookbackLeft, InpPivotLookbackRight))
        {
         if(high_count < ArraySize(high_pivots))
            high_pivots[high_count++] = i;
        }
     }

   if(InpPlotBullish || InpPlotHiddenBullish)
     {
      for(int i = 1; i < low_count; i++)
        {
         const int cur = low_pivots[i];
         const int prev = FindPreviousPivot(low_pivots, i, cur, InpLookbackRangeMin, InpLookbackRangeMax);
         if(prev < 0)
            continue;

         const bool regular_bull = low[cur] < low[prev] && g_rsi_buffer[cur] > g_rsi_buffer[prev];
         const bool hidden_bull  = low[cur] > low[prev] && g_rsi_buffer[cur] < g_rsi_buffer[prev];

         if(InpPlotBullish && regular_bull)
           {
            g_bull_buffer[cur] = g_rsi_buffer[cur] - 3.0;
            DrawDivergenceLine("reg_bull", prev, cur, time, clrLimeGreen, InpLineWidth, InpLineStyle);
           }
         if(InpPlotHiddenBullish && hidden_bull)
           {
            g_hidden_bull_buffer[cur] = g_rsi_buffer[cur] - 6.0;
            DrawDivergenceLine("hid_bull", prev, cur, time, clrDarkGreen, (int)MathMax(1, InpLineWidth - 1), InpLineStyle);
           }
        }
     }

   if(InpPlotBearish || InpPlotHiddenBearish)
     {
      for(int i = 1; i < high_count; i++)
        {
         const int cur = high_pivots[i];
         const int prev = FindPreviousPivot(high_pivots, i, cur, InpLookbackRangeMin, InpLookbackRangeMax);
         if(prev < 0)
            continue;

         const bool regular_bear = high[cur] > high[prev] && g_rsi_buffer[cur] < g_rsi_buffer[prev];
         const bool hidden_bear  = high[cur] < high[prev] && g_rsi_buffer[cur] > g_rsi_buffer[prev];

         if(InpPlotBearish && regular_bear)
           {
            g_bear_buffer[cur] = g_rsi_buffer[cur] + 3.0;
            DrawDivergenceLine("reg_bear", prev, cur, time, clrTomato, InpLineWidth, InpLineStyle);
           }
         if(InpPlotHiddenBearish && hidden_bear)
           {
            g_hidden_bear_buffer[cur] = g_rsi_buffer[cur] + 6.0;
            DrawDivergenceLine("hid_bear", prev, cur, time, clrDarkRed, (int)MathMax(1, InpLineWidth - 1), InpLineStyle);
           }
        }
     }

   return(rates_total);
  }
//+------------------------------------------------------------------+
