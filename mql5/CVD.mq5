//+------------------------------------------------------------------+
//|                                                          CVD.mq5 |
//|                                      Copyright 2024, Antigravity |
//|                                             https://www.mql5.com |
//+------------------------------------------------------------------+
#property copyright "Copyright 2024, Antigravity"
#property link      "https://www.mql5.com"
#property version   "1.00"
#property indicator_separate_window
#property indicator_buffers 5
#property indicator_plots 1

//--- plot CVD
#property indicator_label1  "CVD Open;CVD High;CVD Low;CVD Close"
#property indicator_type1   DRAW_COLOR_CANDLES
#property indicator_color1  clrTeal, clrRed
#property indicator_style1  STYLE_SOLID
#property indicator_width1  1

//--- Zero line
#property indicator_level1  0.0
#property indicator_levelcolor clrGray
#property indicator_levelstyle STYLE_DOT

//--- enums
enum ENUM_ANCHOR_PERIOD
  {
   ANCHOR_NONE,   // None (Continuous)
   ANCHOR_1H,     // 1 Hour
   ANCHOR_4H,     // 4 Hours
   ANCHOR_1D,     // 1 Day
   ANCHOR_1W,     // 1 Week
   ANCHOR_1M,     // 1 Month
   ANCHOR_1Y      // 1 Year
  };

enum ENUM_DATA_AGGREGATION
  {
   AGG_TIME,      // Time (Lower Timeframe)
   AGG_TICKS      // 1 Tick (More accurate, but slower)
  };

//--- input parameters
input ENUM_ANCHOR_PERIOD    InpAnchorPeriod    = ANCHOR_1D;       // Anchor Period
input ENUM_DATA_AGGREGATION InpAggregation     = AGG_TIME;        // Data Aggregation
input ENUM_TIMEFRAMES       InpLowerTimeframe  = PERIOD_M1;       // Timeframe (for Time aggregation)
input ENUM_APPLIED_VOLUME   InpVolumeType      = VOLUME_TICK;     // Volume Type
input int                   InpMaxBars         = 5000;            // Max historical bars to calculate (0 = all)

//--- indicator buffers
double         BufferOpen[];
double         BufferHigh[];
double         BufferLow[];
double         BufferClose[];
double         BufferColor[];

//+------------------------------------------------------------------+
//| Custom indicator initialization function                         |
//+------------------------------------------------------------------+
int OnInit()
  {
//--- indicator buffers mapping
   SetIndexBuffer(0, BufferOpen, INDICATOR_DATA);
   SetIndexBuffer(1, BufferHigh, INDICATOR_DATA);
   SetIndexBuffer(2, BufferLow, INDICATOR_DATA);
   SetIndexBuffer(3, BufferClose, INDICATOR_DATA);
   SetIndexBuffer(4, BufferColor, INDICATOR_COLOR_INDEX);

   PlotIndexSetDouble(0, PLOT_EMPTY_VALUE, EMPTY_VALUE);

//--- Set formatting
   IndicatorSetInteger(INDICATOR_DIGITS, 2);

//--- name for DataWindow and indicator subwindow label
   string short_name = "CVD(" + EnumToString(InpAnchorPeriod) + ")";
   IndicatorSetString(INDICATOR_SHORTNAME, short_name);

   return(INIT_SUCCEEDED);
  }

//+------------------------------------------------------------------+
//| Check if a new anchor period has started                         |
//+------------------------------------------------------------------+
bool IsNewAnchor(datetime time_prev, datetime time_curr, ENUM_ANCHOR_PERIOD anchor)
  {
   if(anchor == ANCHOR_NONE) return false;
   
   MqlDateTime dt_prev, dt_curr;
   TimeToStruct(time_prev, dt_prev);
   TimeToStruct(time_curr, dt_curr);
   
   if(anchor == ANCHOR_1Y)
     {
      return (dt_prev.year != dt_curr.year);
     }
   else if(anchor == ANCHOR_1M)
     {
      return (dt_prev.mon != dt_curr.mon || dt_prev.year != dt_curr.year);
     }
   else if(anchor == ANCHOR_1W)
     {
      int days_prev = (int)(time_prev / 86400);
      int days_curr = (int)(time_curr / 86400);
      // epoch start 1970-01-01 was Thursday (day 0)
      // shift +3 makes Monday the start of the week
      int week_prev = (days_prev + 3) / 7;
      int week_curr = (days_curr + 3) / 7;
      return (week_prev != week_curr);
     }
   else if(anchor == ANCHOR_1D)
     {
      return (dt_prev.day_of_year != dt_curr.day_of_year || dt_prev.year != dt_curr.year);
     }
   else if(anchor == ANCHOR_4H)
     {
      return (time_prev / 14400 != time_curr / 14400);
     }
   else if(anchor == ANCHOR_1H)
     {
      return (time_prev / 3600 != time_curr / 3600);
     }
     
   return false;
  }

//+------------------------------------------------------------------+
//| Custom indicator iteration function                              |
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
   int start = prev_calculated - 1;
   bool is_first_run = false;
   
   // Force recalculation if lower timeframe data was downloaded in the background
   static datetime last_first_m1 = 0;
   if(InpAggregation == AGG_TIME)
     {
      datetime req_start = time[0];
      if(InpMaxBars > 0 && rates_total > InpMaxBars) req_start = time[rates_total - InpMaxBars];
      
      datetime temp[];
      CopyTime(_Symbol, InpLowerTimeframe, req_start, time[rates_total-1], temp);
      
      datetime current_first_m1 = (datetime)SeriesInfoInteger(_Symbol, InpLowerTimeframe, SERIES_FIRSTDATE);
      if(current_first_m1 != last_first_m1 && current_first_m1 > 0)
        {
         last_first_m1 = current_first_m1;
         start = -1; // Force full recalculation
        }
     }
   
   if(start < 0)
     {
      start = 0;
      is_first_run = true;
      if(InpMaxBars > 0 && rates_total > InpMaxBars)
        {
         start = rates_total - InpMaxBars;
         // Roll back to the start of the anchor period to prevent baseline corruption
         if(InpAnchorPeriod != ANCHOR_NONE)
           {
            while(start > 0)
              {
               if(IsNewAnchor(time[start-1], time[start], InpAnchorPeriod)) break;
               start--;
              }
           }
        }
      ArrayInitialize(BufferOpen, EMPTY_VALUE);
      ArrayInitialize(BufferHigh, EMPTY_VALUE);
      ArrayInitialize(BufferLow, EMPTY_VALUE);
      ArrayInitialize(BufferClose, EMPTY_VALUE);
      ArrayInitialize(BufferColor, 0.0);
     }
     
   for(int i = start; i < rates_total; i++)
     {
      double base_delta = 0.0;
      
      // We only look at previous bar if we are not at the very first bar of the chart,
      // AND we are not at the very first bar of our limited calculation window during the first run.
      if(i > 0 && !(is_first_run && i == start))
        {
         bool reset = IsNewAnchor(time[i-1], time[i], InpAnchorPeriod);
         if(!reset)
           {
            base_delta = BufferClose[i-1];
           }
        }
        
      double current_delta = base_delta;
      double candle_open = current_delta;
      double candle_high = current_delta;
      double candle_low = current_delta;
      
      datetime bar_start_time = time[i];
      datetime bar_end_time;
      if(i < rates_total - 1)
         bar_end_time = time[i+1];
      else
         bar_end_time = time[i] + PeriodSeconds(_Period);
         
      if(InpAggregation == AGG_TIME)
        {
         MqlRates rates[];
         int count = CopyRates(_Symbol, InpLowerTimeframe, bar_start_time, bar_end_time - 1, rates);
         if(count > 0)
           {
            for(int j = 0; j < count; j++)
              {
               double vol = (InpVolumeType == VOLUME_TICK) ? (double)rates[j].tick_volume : (double)rates[j].real_volume;
               double bar_delta = 0;
               // Estimate volume delta based on candle direction
               if(rates[j].close > rates[j].open) bar_delta = vol;
               else if(rates[j].close < rates[j].open) bar_delta = -vol;
               
               current_delta += bar_delta;
               if(current_delta > candle_high) candle_high = current_delta;
               if(current_delta < candle_low) candle_low = current_delta;
              }
           }
         else
           {
            // Fallback to current timeframe if lower timeframe data is missing
            double vol = (InpVolumeType == VOLUME_TICK) ? (double)tick_volume[i] : (double)volume[i];
            double bar_delta = 0;
            if(close[i] > open[i]) bar_delta = vol;
            else if(close[i] < open[i]) bar_delta = -vol;
            
            current_delta += bar_delta;
            if(current_delta > candle_high) candle_high = current_delta;
            if(current_delta < candle_low) candle_low = current_delta;
           }
        }
      else
        {
         MqlTick ticks[];
         long t_start = (long)bar_start_time * 1000;
         long t_end = (long)bar_end_time * 1000 - 1;
         int count = CopyTicksRange(_Symbol, ticks, COPY_TICKS_ALL, t_start, t_end);
         if(count > 0)
           {
            double current_prev_price = open[i];
            for(int j = 0; j < count; j++)
              {
               double vol = (InpVolumeType == VOLUME_TICK) ? 1.0 : (double)ticks[j].volume_real;
               if(vol == 0.0 && InpVolumeType == VOLUME_REAL) vol = (double)ticks[j].volume;
               
               double tick_delta = 0;
               if((ticks[j].flags & TICK_FLAG_BUY) == TICK_FLAG_BUY)
                 {
                  tick_delta = vol;
                 }
               else if((ticks[j].flags & TICK_FLAG_SELL) == TICK_FLAG_SELL)
                 {
                  tick_delta = -vol;
                 }
               else
                 {
                  // Infer trade direction from price change
                  double price = (ticks[j].last > 0.0) ? ticks[j].last : ticks[j].bid;
                  if(price > current_prev_price) tick_delta = vol;
                  else if(price < current_prev_price) tick_delta = -vol;
                  current_prev_price = price;
                 }
                 
               current_delta += tick_delta;
               if(current_delta > candle_high) candle_high = current_delta;
               if(current_delta < candle_low) candle_low = current_delta;
              }
           }
         else
           {
            // Fallback to current timeframe
            double vol = (InpVolumeType == VOLUME_TICK) ? (double)tick_volume[i] : (double)volume[i];
            double bar_delta = 0;
            if(close[i] > open[i]) bar_delta = vol;
            else if(close[i] < open[i]) bar_delta = -vol;
            
            current_delta += bar_delta;
            if(current_delta > candle_high) candle_high = current_delta;
            if(current_delta < candle_low) candle_low = current_delta;
           }
        }
        
      BufferOpen[i] = candle_open;
      BufferHigh[i] = candle_high;
      BufferLow[i]  = candle_low;
      BufferClose[i] = current_delta;
      
      BufferColor[i] = (current_delta >= candle_open) ? 0 : 1; // 0: Teal, 1: Red
     }
     
   //--- Highlight current value on the top right
   if(rates_total > 0)
     {
      double current_val = BufferClose[rates_total - 1];
      
      // Get the subwindow index securely using the indicator's short name
      string short_name = "CVD(" + EnumToString(InpAnchorPeriod) + ")";
      int current_subwindow = ChartWindowFind(0, short_name);
      
      if(current_subwindow >= 0)
        {
         string obj_name = "CVD_Label_Value_Right";
         if(ObjectFind(0, obj_name) != current_subwindow)
           {
            ObjectDelete(0, obj_name);
            ObjectCreate(0, obj_name, OBJ_LABEL, current_subwindow, 0, 0);
            ObjectSetInteger(0, obj_name, OBJPROP_CORNER, CORNER_RIGHT_UPPER);
            ObjectSetInteger(0, obj_name, OBJPROP_ANCHOR, ANCHOR_RIGHT_UPPER);
            ObjectSetInteger(0, obj_name, OBJPROP_XDISTANCE, 15);
            ObjectSetInteger(0, obj_name, OBJPROP_YDISTANCE, 15);
            ObjectSetInteger(0, obj_name, OBJPROP_SELECTABLE, false);
            ObjectSetInteger(0, obj_name, OBJPROP_HIDDEN, true);
            ObjectSetString(0, obj_name, OBJPROP_FONT, "Arial");
            ObjectSetInteger(0, obj_name, OBJPROP_FONTSIZE, 12);
            ObjectSetInteger(0, obj_name, OBJPROP_BACK, false);
           }
         
         string text_val = "CVD: " + DoubleToString(current_val / 1000.0, 1) + "k";
         ObjectSetString(0, obj_name, OBJPROP_TEXT, text_val);
         color tag_color = (BufferColor[rates_total - 1] == 0.0) ? clrTeal : clrRed;
         ObjectSetInteger(0, obj_name, OBJPROP_COLOR, tag_color);
         ChartRedraw(0);
        }
     }
     
   return(rates_total);
  }

//+------------------------------------------------------------------+
//| Custom indicator deinitialization function                       |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   ObjectDelete(0, "CVD_CurrentValue");
   ObjectDelete(0, "CVD_Label_Value_Right");
  }
//+------------------------------------------------------------------+
