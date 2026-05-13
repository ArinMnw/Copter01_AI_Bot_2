//+------------------------------------------------------------------+
//| S12_RangeZone.mq5                                                |
//| Show S12 buy/sell zones from M5 using the same active range      |
//| logic as the Python backend.                                     |
//+------------------------------------------------------------------+
#property copyright "Copter01 Bot"
#property version   "1.02"
#property indicator_chart_window
#property indicator_plots 0

sinput int    InpLookback   = 100;               // Lookback Bars (match S12_LOOKBACK)
sinput int    InpZonePoints = 50;                // Zone Points (match S12_ZONE_POINTS)
sinput double InpPointScale = 1.0;               // Point Scale (1.0=XAUUSD, 4.0=BTCUSD)
sinput int    InpPivotLeft  = 15;                // Pivot Left (match SWING_PIVOT_LEFT)
sinput int    InpPivotRight = 10;                // Pivot Right (match SWING_PIVOT_RIGHT)
sinput color  InpBuyColor   = clrMediumSeaGreen; // BUY Zone Color
sinput color  InpSellColor  = clrTomato;         // SELL Zone Color
sinput int    InpExtendBars = 100;               // Extend Right (bars, M5 units)

#define PREFIX "S12_"

double g_last_buy_zone_bot = 0.0;
double g_last_buy_zone_top = 0.0;
double g_last_sell_zone_bot = 0.0;
double g_last_sell_zone_top = 0.0;
double g_last_swing_high = 0.0;
double g_last_swing_low = 0.0;
datetime g_last_t_start = 0;
datetime g_last_t_end = 0;
bool g_has_last_zone = false;

int OnInit()
{
   ChartSetInteger(0, CHART_EVENT_MOUSE_MOVE, true);
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   ObjectsDeleteAll(0, PREFIX);
   ChartRedraw(0);
}

int OnCalculate(const int rates_total,
                const int prev_calculated,
                const datetime &time[],
                const double   &open[],
                const double   &high[],
                const double   &low[],
                const double   &close[],
                const long     &tick_volume[],
                const long     &volume[],
                const int      &spread[])
{
   int need = InpLookback + MathMax(InpPivotLeft + InpPivotRight + 5, 5);

   double m5_high[], m5_low[], m5_close[];
   datetime m5_time[];
   ArraySetAsSeries(m5_high, false);
   ArraySetAsSeries(m5_low, false);
   ArraySetAsSeries(m5_close, false);
   ArraySetAsSeries(m5_time, false);

   if(CopyHigh(_Symbol, PERIOD_M5, 0, need, m5_high) < need) return rates_total;
   if(CopyLow(_Symbol, PERIOD_M5, 0, need, m5_low) < need) return rates_total;
   if(CopyClose(_Symbol, PERIOD_M5, 0, need, m5_close) < need) return rates_total;
   if(CopyTime(_Symbol, PERIOD_M5, 0, need, m5_time) < need) return rates_total;

   double pt = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   double zone_dist = InpZonePoints * pt * InpPointScale;

   double swing_high = 0.0;
   double swing_low = 0.0;
   if(!FindActiveS12Swing(m5_high, m5_low, m5_close, need, InpLookback, InpPivotLeft, InpPivotRight, swing_high, swing_low))
      return rates_total;

   double buy_zone_bot = swing_low;
   double buy_zone_top = swing_low + zone_dist;
   double sell_zone_bot = swing_high - zone_dist;
   double sell_zone_top = swing_high;

   datetime t_start = m5_time[need - InpLookback];
   datetime t_end = m5_time[need - 1] + (datetime)(60 * 5 * InpExtendBars);

   bool changed = (!g_has_last_zone ||
                   MathAbs(g_last_buy_zone_bot - buy_zone_bot) > (_Point * 0.1) ||
                   MathAbs(g_last_buy_zone_top - buy_zone_top) > (_Point * 0.1) ||
                   MathAbs(g_last_sell_zone_bot - sell_zone_bot) > (_Point * 0.1) ||
                   MathAbs(g_last_sell_zone_top - sell_zone_top) > (_Point * 0.1) ||
                   MathAbs(g_last_swing_high - swing_high) > (_Point * 0.1) ||
                   MathAbs(g_last_swing_low - swing_low) > (_Point * 0.1) ||
                   g_last_t_start != t_start ||
                   g_last_t_end != t_end);

   if(changed)
   {
      DrawRect(PREFIX + "BuyZone", t_start, buy_zone_bot, t_end, buy_zone_top, InpBuyColor);
      DrawRect(PREFIX + "SellZone", t_start, sell_zone_bot, t_end, sell_zone_top, InpSellColor);
      DrawHLine(PREFIX + "SwingHigh", swing_high, t_start, t_end, clrOrangeRed, STYLE_DASH);
      DrawHLine(PREFIX + "SwingLow", swing_low, t_start, t_end, clrDeepSkyBlue, STYLE_DASH);

      DrawLabel(PREFIX + "LblSellTop", t_end, sell_zone_top, StringFormat("Swing H %.2f", sell_zone_top), clrOrangeRed);
      DrawLabel(PREFIX + "LblSellBot", t_end, sell_zone_bot, StringFormat("SELL bot %.2f", sell_zone_bot), InpSellColor);
      DrawLabel(PREFIX + "LblBuyTop", t_end, buy_zone_top, StringFormat("BUY top %.2f", buy_zone_top), InpBuyColor);
      DrawLabel(PREFIX + "LblBuyBot", t_end, buy_zone_bot, StringFormat("Swing L %.2f", buy_zone_bot), clrDeepSkyBlue);

      g_last_buy_zone_bot = buy_zone_bot;
      g_last_buy_zone_top = buy_zone_top;
      g_last_sell_zone_bot = sell_zone_bot;
      g_last_sell_zone_top = sell_zone_top;
      g_last_swing_high = swing_high;
      g_last_swing_low = swing_low;
      g_last_t_start = t_start;
      g_last_t_end = t_end;
      g_has_last_zone = true;

      ChartRedraw(0);
   }
   return rates_total;
}

bool IsPivotHigh(const double &arr[], const int total, const int idx, const int left, const int right)
{
   if(idx - left < 0 || idx + right >= total)
      return false;

   double center = arr[idx];
   for(int j = idx - left; j < idx; j++)
      if(arr[j] >= center)
         return false;
   for(int j = idx + 1; j <= idx + right; j++)
      if(arr[j] > center)
         return false;
   return true;
}

bool IsPivotLow(const double &arr[], const int total, const int idx, const int left, const int right)
{
   if(idx - left < 0 || idx + right >= total)
      return false;

   double center = arr[idx];
   for(int j = idx - left; j < idx; j++)
      if(arr[j] <= center)
         return false;
   for(int j = idx + 1; j <= idx + right; j++)
      if(arr[j] < center)
         return false;
   return true;
}

bool FindActiveS12Swing(const double &m5_high[], const double &m5_low[], const double &m5_close[],
                        const int total, const int lookback, const int left, const int right,
                        double &swing_high, double &swing_low)
{
   int n = MathMin(MathMax(1, lookback), total);
   int start = total - n;
   double raw_high = m5_high[start];
   double raw_low = m5_low[start];
   for(int i = start + 1; i < total; i++)
   {
      if(m5_high[i] > raw_high) raw_high = m5_high[i];
      if(m5_low[i] < raw_low) raw_low = m5_low[i];
   }

   bool found_high = false;
   bool found_low = false;
   for(int i = total - right - 1; i >= start; i--)
   {
      if(!found_high && IsPivotHigh(m5_high, total, i, left, right))
      {
         swing_high = m5_high[i];
         found_high = true;
      }
      if(!found_low && IsPivotLow(m5_low, total, i, left, right))
      {
         swing_low = m5_low[i];
         found_low = true;
      }
      if(found_high && found_low)
         break;
   }

   if(!found_high)
      swing_high = raw_high;
   if(!found_low)
      swing_low = raw_low;

   if(total >= 2)
   {
      double last_closed = m5_close[total - 2];
      if(last_closed > swing_high)
         swing_high = raw_high;
      if(last_closed < swing_low)
         swing_low = raw_low;
   }
   return true;
}

void DrawRect(string name, datetime t1, double p1, datetime t2, double p2, color clr)
{
   if(ObjectFind(0, name) < 0)
      ObjectCreate(0, name, OBJ_RECTANGLE, 0, t1, p1, t2, p2);
   ObjectSetInteger(0, name, OBJPROP_TIME, 0, t1);
   ObjectSetDouble(0, name, OBJPROP_PRICE, 0, p1);
   ObjectSetInteger(0, name, OBJPROP_TIME, 1, t2);
   ObjectSetDouble(0, name, OBJPROP_PRICE, 1, p2);
   ObjectSetInteger(0, name, OBJPROP_COLOR, clr);
   ObjectSetInteger(0, name, OBJPROP_FILL, true);
   ObjectSetInteger(0, name, OBJPROP_BACK, true);
   ObjectSetInteger(0, name, OBJPROP_WIDTH, 1);
   ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, name, OBJPROP_HIDDEN, true);
}

void DrawHLine(string name, double price, datetime t1, datetime t2, color clr, ENUM_LINE_STYLE style)
{
   if(ObjectFind(0, name) < 0)
      ObjectCreate(0, name, OBJ_TREND, 0, t1, price, t2, price);
   ObjectSetInteger(0, name, OBJPROP_TIME, 0, t1);
   ObjectSetDouble(0, name, OBJPROP_PRICE, 0, price);
   ObjectSetInteger(0, name, OBJPROP_TIME, 1, t2);
   ObjectSetDouble(0, name, OBJPROP_PRICE, 1, price);
   ObjectSetInteger(0, name, OBJPROP_COLOR, clr);
   ObjectSetInteger(0, name, OBJPROP_STYLE, style);
   ObjectSetInteger(0, name, OBJPROP_WIDTH, 1);
   ObjectSetInteger(0, name, OBJPROP_RAY_RIGHT, false);
   ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, name, OBJPROP_HIDDEN, true);
}

void DrawLabel(string name, datetime t, double price, string text, color clr)
{
   if(ObjectFind(0, name) < 0)
      ObjectCreate(0, name, OBJ_TEXT, 0, t, price);
   ObjectSetInteger(0, name, OBJPROP_TIME, t);
   ObjectSetDouble(0, name, OBJPROP_PRICE, price);
   ObjectSetString(0, name, OBJPROP_TEXT, text);
   ObjectSetInteger(0, name, OBJPROP_COLOR, clr);
   ObjectSetInteger(0, name, OBJPROP_FONTSIZE, 8);
   ObjectSetString(0, name, OBJPROP_FONT, "Consolas");
   ObjectSetInteger(0, name, OBJPROP_ANCHOR, ANCHOR_LEFT);
   ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, name, OBJPROP_HIDDEN, true);
}
//+------------------------------------------------------------------+
