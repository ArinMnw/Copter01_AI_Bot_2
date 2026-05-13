//+------------------------------------------------------------------+
//|                                               SwingHLLevels.mq5  |
//|  Pivot swing levels inspired by TradingView                      |
//|  "Swing Points and Liquidity - By Leviathan"                     |
//+------------------------------------------------------------------+
#property copyright "Copter01 AI Bot"
#property version   "2.00"
#property indicator_chart_window
#property indicator_plots 0

input int    InpLookbackBars       = 2000;
input int    InpPivotRight         = 10;
input int    InpPivotLeft          = 15;
input bool   InpShowSwingLines     = true;
input bool   InpShowBubbles        = false;
input bool   InpExtendUntilFilled  = true;
input bool   InpHideFilled         = false;
input int    InpRefreshSec         = 5;
input color  InpHighLineColor      = clrTomato;
input color  InpLowLineColor       = clrDeepSkyBlue;
input color  InpHighBubbleColor    = clrTomato;
input color  InpLowBubbleColor     = clrDeepSkyBlue;
input ENUM_LINE_STYLE InpLineStyle = STYLE_DOT;
input int    InpLineWidth          = 1;

string g_prefix = "SHLTV_";
string g_last_signature = "";
ENUM_TIMEFRAMES g_last_period = PERIOD_CURRENT;

int OnInit()
  {
   EventSetTimer(MathMax(1, InpRefreshSec));
   g_last_period = (ENUM_TIMEFRAMES)_Period;
   RefreshLevels();
   return(INIT_SUCCEEDED);
  }

void OnDeinit(const int reason)
  {
   EventKillTimer();
   ObjectsDeleteAll(0, g_prefix);
   ChartRedraw();
  }

void OnTimer()
  {
   RefreshLevels();
  }

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
   return(rates_total);
  }

void OnChartEvent(const int id, const long &lparam,
                  const double &dparam, const string &sparam)
  {
   if(id == CHARTEVENT_CHART_CHANGE)
     {
      g_last_signature = "";
      g_last_period = (ENUM_TIMEFRAMES)_Period;
      RefreshLevels();
     }
  }

bool IsPivotHigh(MqlRates &rates[], const int idx, const int left, const int right)
  {
   if(idx - left < 0 || idx + right >= ArraySize(rates))
      return false;

   double center = rates[idx].high;
   for(int j = idx - left; j < idx; ++j)
      if(rates[j].high >= center)
         return false;
   for(int j = idx + 1; j <= idx + right; ++j)
      if(rates[j].high > center)
         return false;
   return true;
  }

bool IsPivotLow(MqlRates &rates[], const int idx, const int left, const int right)
  {
   if(idx - left < 0 || idx + right >= ArraySize(rates))
      return false;

   double center = rates[idx].low;
   for(int j = idx - left; j < idx; ++j)
      if(rates[j].low <= center)
         return false;
   for(int j = idx + 1; j <= idx + right; ++j)
      if(rates[j].low < center)
         return false;
   return true;
  }

int FindTouchIndex(MqlRates &rates[], const int pivot_idx, const double level)
  {
   for(int i = pivot_idx + 1; i < ArraySize(rates); ++i)
      if(rates[i].high >= level && rates[i].low <= level)
         return i;
   return -1;
  }

void DrawLineObject(const string name,
                    const datetime t1,
                    const datetime t2,
                    const double price,
                    const color clr)
  {
   if(!InpShowSwingLines)
     {
      ObjectDelete(0, name);
      return;
     }

   if(ObjectFind(0, name) < 0)
      ObjectCreate(0, name, OBJ_TREND, 0, t1, price, t2, price);

   ObjectSetInteger(0, name, OBJPROP_TIME, 0, t1);
   ObjectSetDouble(0, name, OBJPROP_PRICE, 0, price);
   ObjectSetInteger(0, name, OBJPROP_TIME, 1, t2);
   ObjectSetDouble(0, name, OBJPROP_PRICE, 1, price);
   ObjectSetInteger(0, name, OBJPROP_COLOR, clr);
   ObjectSetInteger(0, name, OBJPROP_STYLE, InpLineStyle);
   ObjectSetInteger(0, name, OBJPROP_WIDTH, InpLineWidth);
   ObjectSetInteger(0, name, OBJPROP_RAY_RIGHT, false);
   ObjectSetInteger(0, name, OBJPROP_RAY_LEFT, false);
   ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, name, OBJPROP_HIDDEN, true);
   ObjectSetInteger(0, name, OBJPROP_BACK, true);
  }

void DrawBubbleObject(const string name,
                      const datetime t1,
                      const double price,
                      const color clr)
  {
   if(!InpShowBubbles)
     {
      ObjectDelete(0, name);
      return;
     }

   if(ObjectFind(0, name) < 0)
      ObjectCreate(0, name, OBJ_ARROW, 0, t1, price);

   ObjectSetInteger(0, name, OBJPROP_TIME, 0, t1);
   ObjectSetDouble(0, name, OBJPROP_PRICE, 0, price);
   ObjectSetInteger(0, name, OBJPROP_ARROWCODE, 108);
   ObjectSetInteger(0, name, OBJPROP_COLOR, clr);
   ObjectSetInteger(0, name, OBJPROP_WIDTH, 1);
   ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, name, OBJPROP_HIDDEN, true);
  }

void AppendKeepNames(string &keep_names[], const string base_name)
  {
   int pos = ArraySize(keep_names);
   ArrayResize(keep_names, pos + 1);
   keep_names[pos] = base_name + "_line";
   pos = ArraySize(keep_names);
   ArrayResize(keep_names, pos + 1);
   keep_names[pos] = base_name + "_bubble";
  }

bool NameInList(const string name, string &keep_names[])
  {
   for(int i = 0; i < ArraySize(keep_names); ++i)
      if(keep_names[i] == name)
         return true;
   return false;
  }

void CleanupUnusedObjects(string &keep_names[])
  {
   int total = ObjectsTotal(0);
   for(int i = total - 1; i >= 0; --i)
     {
      string name = ObjectName(0, i);
      if(StringFind(name, g_prefix) != 0)
         continue;
      if(!NameInList(name, keep_names))
         ObjectDelete(0, name);
     }
  }

datetime ResolveEndTime(MqlRates &rates[],
                        const int pivot_idx,
                        const int confirm_idx,
                        const int touch_idx)
  {
   if(InpHideFilled && touch_idx >= 0)
      return 0;

   if(InpExtendUntilFilled)
     {
      if(touch_idx >= 0)
         return rates[touch_idx].time;
      return rates[ArraySize(rates) - 1].time;
     }

   return rates[confirm_idx].time;
  }

void RefreshLevels()
  {
   if(g_last_period != (ENUM_TIMEFRAMES)_Period)
     {
      g_last_signature = "";
      g_last_period = (ENUM_TIMEFRAMES)_Period;
     }

   MqlRates rates[];
   int copied = CopyRates(_Symbol, (ENUM_TIMEFRAMES)_Period, 0,
                          InpLookbackBars + InpPivotLeft + InpPivotRight + 5,
                          rates);
   if(copied <= 0)
      return;

   int total = ArraySize(rates);
   if(total <= InpPivotLeft + InpPivotRight)
      return;

   int start = InpPivotLeft;
   int end_exclusive = total - InpPivotRight;
   string signature = IntegerToString((int)_Period) + "|";
   string keep_names[];
   ArrayResize(keep_names, 0);

   for(int i = start; i < end_exclusive; ++i)
     {
      if(IsPivotHigh(rates, i, InpPivotLeft, InpPivotRight))
        {
         int confirm_idx_h = i + InpPivotRight;
         int touch_idx_h = FindTouchIndex(rates, i, rates[i].high);
         datetime end_h = ResolveEndTime(rates, i, confirm_idx_h, touch_idx_h);
         if(end_h != 0)
           {
            string base_h = g_prefix + "H_" + IntegerToString((int)rates[i].time);
            signature += "H" + IntegerToString((int)rates[i].time) + ":" + DoubleToString(rates[i].high, _Digits) + ":" + IntegerToString((int)end_h) + "|";
            AppendKeepNames(keep_names, base_h);
           }
        }

      if(IsPivotLow(rates, i, InpPivotLeft, InpPivotRight))
        {
         int confirm_idx_l = i + InpPivotRight;
         int touch_idx_l = FindTouchIndex(rates, i, rates[i].low);
         datetime end_l = ResolveEndTime(rates, i, confirm_idx_l, touch_idx_l);
         if(end_l != 0)
           {
            string base_l = g_prefix + "L_" + IntegerToString((int)rates[i].time);
            signature += "L" + IntegerToString((int)rates[i].time) + ":" + DoubleToString(rates[i].low, _Digits) + ":" + IntegerToString((int)end_l) + "|";
            AppendKeepNames(keep_names, base_l);
           }
        }
     }

   if(g_last_signature == signature)
      return;

   g_last_signature = signature;

   for(int i = start; i < end_exclusive; ++i)
     {
      if(IsPivotHigh(rates, i, InpPivotLeft, InpPivotRight))
        {
         int confirm_idx_h = i + InpPivotRight;
         int touch_idx_h = FindTouchIndex(rates, i, rates[i].high);
         datetime end_h = ResolveEndTime(rates, i, confirm_idx_h, touch_idx_h);
         if(end_h != 0)
           {
            string base_h = g_prefix + "H_" + IntegerToString((int)rates[i].time);
            DrawLineObject(base_h + "_line", rates[i].time, end_h, rates[i].high, InpHighLineColor);
            DrawBubbleObject(base_h + "_bubble", rates[i].time, rates[i].high, InpHighBubbleColor);
           }
        }

      if(IsPivotLow(rates, i, InpPivotLeft, InpPivotRight))
        {
         int confirm_idx_l = i + InpPivotRight;
         int touch_idx_l = FindTouchIndex(rates, i, rates[i].low);
         datetime end_l = ResolveEndTime(rates, i, confirm_idx_l, touch_idx_l);
         if(end_l != 0)
           {
            string base_l = g_prefix + "L_" + IntegerToString((int)rates[i].time);
            DrawLineObject(base_l + "_line", rates[i].time, end_l, rates[i].low, InpLowLineColor);
            DrawBubbleObject(base_l + "_bubble", rates[i].time, rates[i].low, InpLowBubbleColor);
           }
        }
     }

   CleanupUnusedObjects(keep_names);
   ChartRedraw();
  }
