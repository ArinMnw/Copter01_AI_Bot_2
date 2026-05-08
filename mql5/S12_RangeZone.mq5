//+------------------------------------------------------------------+
//|  S12_RangeZone.mq5                                               |
//|  แสดง BUY/SELL zone สำหรับท่าที่ 12 Range Trading               |
//|  ดึง M5 data เสมอ — attach ที่ TF ไหนก็แสดงถูก                  |
//+------------------------------------------------------------------+
#property copyright "Copter01 Bot"
#property version   "1.01"
#property indicator_chart_window
#property indicator_plots 0

sinput int    InpLookback   = 50;                // Lookback Bars (S12_LOOKBACK)
sinput int    InpZonePoints = 50;                // Zone Points (S12_ZONE_POINTS)
sinput double InpPointScale = 1.0;               // Point Scale (1.0=XAUUSD, 4.0=BTCUSD)
sinput color  InpBuyColor   = clrMediumSeaGreen; // BUY Zone Color
sinput color  InpSellColor  = clrTomato;         // SELL Zone Color
sinput int    InpExtendBars = 100;               // Extend Right (bars, M5 units)

#define PREFIX "S12_"

//+------------------------------------------------------------------+
int OnInit()
{
   // force recalc ทุก tick เพื่ออัปเดต zone ตาม M5
   ChartSetInteger(0, CHART_EVENT_MOUSE_MOVE, true);
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   ObjectsDeleteAll(0, PREFIX);
   ChartRedraw(0);
}

//+------------------------------------------------------------------+
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
   // ดึง M5 data เสมอ ไม่ว่าจะ attach ที่ TF ไหน
   int need = InpLookback + 5;
   double m5_high[], m5_low[];
   datetime m5_time[];
   ArraySetAsSeries(m5_high, true);
   ArraySetAsSeries(m5_low,  true);
   ArraySetAsSeries(m5_time, true);

   if(CopyHigh(_Symbol, PERIOD_M5, 0, need, m5_high) < need) return rates_total;
   if(CopyLow (_Symbol, PERIOD_M5, 0, need, m5_low)  < need) return rates_total;
   if(CopyTime(_Symbol, PERIOD_M5, 0, need, m5_time) < need) return rates_total;

   double pt        = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   double zone_dist = InpZonePoints * pt * InpPointScale;

   // หา swing high/low จาก lookback M5 bars (index 0 = แท่งล่าสุด)
   double swing_high = m5_high[0];
   double swing_low  = m5_low[0];
   for(int i = 1; i < InpLookback; i++)
   {
      if(m5_high[i] > swing_high) swing_high = m5_high[i];
      if(m5_low[i]  < swing_low)  swing_low  = m5_low[i];
   }

   double buy_zone_bot  = swing_low;
   double buy_zone_top  = swing_low  + zone_dist;
   double sell_zone_bot = swing_high - zone_dist;
   double sell_zone_top = swing_high;

   // t_start = เวลาแท่ง M5 แรกของ lookback, t_end = ยืดไปทางขวา
   datetime t_start = m5_time[InpLookback - 1];
   datetime t_end   = m5_time[0] + (datetime)(60 * 5 * InpExtendBars);

   // วาด zone rectangle
   DrawRect(PREFIX + "BuyZone",  t_start, buy_zone_bot,  t_end, buy_zone_top,  InpBuyColor);
   DrawRect(PREFIX + "SellZone", t_start, sell_zone_bot, t_end, sell_zone_top, InpSellColor);

   // เส้น swing boundary (dashed)
   DrawHLine(PREFIX + "SwingHigh", swing_high, t_start, t_end, clrOrangeRed,   STYLE_DASH);
   DrawHLine(PREFIX + "SwingLow",  swing_low,  t_start, t_end, clrDeepSkyBlue, STYLE_DASH);

   // Label ราคา
   DrawLabel(PREFIX + "LblSellTop", t_end, sell_zone_top, StringFormat("Swing H  %.2f", sell_zone_top), clrOrangeRed);
   DrawLabel(PREFIX + "LblSellBot", t_end, sell_zone_bot, StringFormat("SELL bot %.2f", sell_zone_bot), InpSellColor);
   DrawLabel(PREFIX + "LblBuyTop",  t_end, buy_zone_top,  StringFormat("BUY  top %.2f", buy_zone_top),  InpBuyColor);
   DrawLabel(PREFIX + "LblBuyBot",  t_end, buy_zone_bot,  StringFormat("Swing L  %.2f", buy_zone_bot),  clrDeepSkyBlue);

   ChartRedraw(0);
   return rates_total;
}

//+------------------------------------------------------------------+
void DrawRect(string name, datetime t1, double p1, datetime t2, double p2, color clr)
{
   if(ObjectFind(0, name) < 0)
      ObjectCreate(0, name, OBJ_RECTANGLE, 0, t1, p1, t2, p2);
   ObjectSetInteger(0, name, OBJPROP_TIME,  0, t1);
   ObjectSetDouble(0,  name, OBJPROP_PRICE, 0, p1);
   ObjectSetInteger(0, name, OBJPROP_TIME,  1, t2);
   ObjectSetDouble(0,  name, OBJPROP_PRICE, 1, p2);
   ObjectSetInteger(0, name, OBJPROP_COLOR, clr);
   ObjectSetInteger(0, name, OBJPROP_FILL,  true);
   ObjectSetInteger(0, name, OBJPROP_BACK,  true);
   ObjectSetInteger(0, name, OBJPROP_WIDTH, 1);
   ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, name, OBJPROP_HIDDEN, true);
}

//+------------------------------------------------------------------+
void DrawHLine(string name, double price, datetime t1, datetime t2, color clr, ENUM_LINE_STYLE style)
{
   if(ObjectFind(0, name) < 0)
      ObjectCreate(0, name, OBJ_TREND, 0, t1, price, t2, price);
   ObjectSetInteger(0, name, OBJPROP_TIME,  0, t1);
   ObjectSetDouble(0,  name, OBJPROP_PRICE, 0, price);
   ObjectSetInteger(0, name, OBJPROP_TIME,  1, t2);
   ObjectSetDouble(0,  name, OBJPROP_PRICE, 1, price);
   ObjectSetInteger(0, name, OBJPROP_COLOR, clr);
   ObjectSetInteger(0, name, OBJPROP_STYLE, style);
   ObjectSetInteger(0, name, OBJPROP_WIDTH, 1);
   ObjectSetInteger(0, name, OBJPROP_RAY_RIGHT, false);
   ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, name, OBJPROP_HIDDEN, true);
}

//+------------------------------------------------------------------+
void DrawLabel(string name, datetime t, double price, string text, color clr)
{
   if(ObjectFind(0, name) < 0)
      ObjectCreate(0, name, OBJ_TEXT, 0, t, price);
   ObjectSetInteger(0, name, OBJPROP_TIME,  t);
   ObjectSetDouble(0,  name, OBJPROP_PRICE, price);
   ObjectSetString(0,  name, OBJPROP_TEXT,  text);
   ObjectSetInteger(0, name, OBJPROP_COLOR, clr);
   ObjectSetInteger(0, name, OBJPROP_FONTSIZE, 8);
   ObjectSetString(0,  name, OBJPROP_FONT, "Consolas");
   ObjectSetInteger(0, name, OBJPROP_ANCHOR, ANCHOR_LEFT);
   ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, name, OBJPROP_HIDDEN, true);
}
//+------------------------------------------------------------------+
