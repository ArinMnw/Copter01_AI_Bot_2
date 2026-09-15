//+------------------------------------------------------------------+
//| CandlestickPatterns.mq5                                          |
//| Converted from Pine Script v6 "Candlestick Patterns Identified"  |
//| Original: (c) repo32, Mozilla Public License 2.0                 |
//| https://mozilla.org/MPL/2.0/                                     |
//+------------------------------------------------------------------+
#property copyright "Converted from Pine Script (MPL-2.0) by repo32"
#property link      "https://mozilla.org/MPL/2.0/"
#property version   "1.00"
#property indicator_chart_window
#property indicator_plots 0
#property strict

//--- inputs (mirrors the Pine Script inputs)
input int    InpTrend      = 5;             // Trend in Bars
input double InpDojiSize   = 0.05;           // Doji size

input color  InpBullColor  = clrLime;        // Bullish Arrow Color
input color  InpBearColor  = clrRed;         // Bearish Arrow Color
input color  InpDojiColor  = clrWhite;       // Other (i.e. Doji) Symbol Color
input color  InpBullText   = clrLime;        // Bullish Text Color
input color  InpBearText   = clrRed;         // Bearish Text Color
input color  InpDojiText   = clrWhite;       // Other (i.e. Doji) Text Color

input bool   InpShowLabels = true;           // Show pattern name labels
input int    InpFontSize   = 8;              // Label font size
input bool   InpAlertsOn   = true;           // Send alert on new confirmed pattern
input bool   InpPushNotif  = false;          // Also send push notification

#define OBJ_PREFIX "CP_"

//--- remembers the last bar we already alerted on, per pattern, so we only
//    alert ONCE per confirmed (closed) bar instead of on every tick/recalc
datetime g_lastAlertTime[15];

enum PatternId
{
   PID_DOJI = 0, PID_BEAR_HARAMI, PID_BULL_HARAMI, PID_BEAR_ENG, PID_BULL_ENG,
   PID_PIERCING, PID_BULL_BELT, PID_BULL_KICK, PID_BEAR_KICK, PID_HANGING_MAN,
   PID_EVENING_STAR, PID_MORNING_STAR, PID_SHOOTING_STAR, PID_HAMMER, PID_INV_HAMMER
};

//+------------------------------------------------------------------+
int OnInit()
{
   IndicatorSetString(INDICATOR_SHORTNAME, "Candlestick Patterns Identified");
   ArrayInitialize(g_lastAlertTime, 0);

   // Sweep any objects left behind by a previous run that never got a clean
   // OnDeinit (terminal crash, forced close, etc.) before drawing new ones.
   ObjectsDeleteAll(0, OBJ_PREFIX);
   ChartRedraw(0);
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   // Runs for every removal reason (manual delete, template change,
   // timeframe/symbol switch, recompile, chart close, ...).
   ObjectsDeleteAll(0, OBJ_PREFIX);
   ChartRedraw(0);
}

//+------------------------------------------------------------------+
//| Small helpers so pattern formulas below read like the Pine code  |
//+------------------------------------------------------------------+
double LowestLow(const double &low[], int shift, int len)
{
   double lo = low[shift];
   for(int k = 1; k < len; k++)
      if(low[shift - k] < lo) lo = low[shift - k];
   return lo;
}

//+------------------------------------------------------------------+
//| Draws one signal on a CLOSED bar and fires an alert exactly once |
//+------------------------------------------------------------------+
#define DOT_ARROW_CODE 159   // Wingdings small filled dot

void PlotSignal(PatternId pid, int i, const datetime &time[],
                 const double &high[], const double &low[],
                 bool below, color clr,
                 color textClr, string text, bool newBarOnly)
{
   double range  = high[i] - low[i];
   double offset = MathMax(range * 0.4, 10 * _Point);
   double price  = below ? (low[i] - offset) : (high[i] + offset);

   string name = OBJ_PREFIX + EnumToString(pid) + "_" + IntegerToString((long)time[i]);

   if(ObjectFind(0, name) < 0)
   {
      ObjectCreate(0, name, OBJ_ARROW, 0, time[i], price);
      ObjectSetInteger(0, name, OBJPROP_ARROWCODE, DOT_ARROW_CODE);
      ObjectSetInteger(0, name, OBJPROP_COLOR, clr);
      ObjectSetInteger(0, name, OBJPROP_WIDTH, 2);
      ObjectSetInteger(0, name, OBJPROP_ANCHOR, ANCHOR_CENTER);
      ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, name, OBJPROP_BACK, false);

      if(InpShowLabels)
      {
         // below==true means this is a bullish signal (dot sits below the bar)
         // -> its label goes UNDER the dot. Bearish/doji (below==false, dot
         // above the bar) -> label goes ABOVE the dot. Always horizontally centered.
         string tname = name + "_TXT";
         double tprice = below ? (price - offset * 0.6) : (price + offset * 0.6);
         ObjectCreate(0, tname, OBJ_TEXT, 0, time[i], tprice);
         ObjectSetString(0, tname, OBJPROP_TEXT, text);
         ObjectSetInteger(0, tname, OBJPROP_COLOR, textClr);
         ObjectSetInteger(0, tname, OBJPROP_FONTSIZE, InpFontSize);
         ObjectSetString(0, tname, OBJPROP_FONT, "Arial");
         ObjectSetInteger(0, tname, OBJPROP_ANCHOR, below ? ANCHOR_UPPER : ANCHOR_LOWER); // top-center (grows down) vs bottom-center (grows up), both centered
         ObjectSetInteger(0, tname, OBJPROP_SELECTABLE, false);
         ObjectSetInteger(0, tname, OBJPROP_BACK, false);
      }
   }

   // Alert only once per pattern per bar, and only for the bar that JUST closed
   // (newBarOnly = true means "this is the most recently closed bar this pass").
   if(InpAlertsOn && newBarOnly && g_lastAlertTime[pid] != time[i])
   {
      g_lastAlertTime[pid] = time[i];
      string msg = StringFormat("%s: %s detected on %s (closed bar)", _Symbol, text, TimeToString(time[i], TIME_DATE|TIME_MINUTES));
      Alert(msg);
      if(InpPushNotif) SendNotification(msg);
   }
}

//+------------------------------------------------------------------+
//| Evaluate every pattern for one CLOSED bar index i                |
//| i is in "series" convention here: i=0 is the bar being tested,   |
//| i=1 is one bar back, i=2 two bars back, i=trend is trend bars    |
//| back -- exactly matching Pine's close[1], open[trend], etc.      |
//+------------------------------------------------------------------+
void EvaluateBar(int shift, const datetime &time[],
                  const double &open[], const double &high[],
                  const double &low[], const double &close[],
                  bool newBarOnly)
{
   // shift: index into the *series-style* accessor below, resolved via idx()
   // We work directly with the shift value assuming arrays are indexed as
   // series (element 0 = most recent), see call site for array preparation.
   #define O(n) open[shift + (n)]
   #define H(n) high[shift + (n)]
   #define L(n) low[shift + (n)]
   #define C(n) close[shift + (n)]

   int trend = InpTrend;

   //--- Doji
   bool doji = MathAbs(O(0) - C(0)) <= (H(0) - L(0)) * InpDojiSize;
   if(doji)
      PlotSignal(PID_DOJI, shift, time, high, low, false, InpDojiColor, InpDojiText, "Doji", newBarOnly);

   //--- Bearish Harami
   bool bearHarami = C(1) > O(1) && O(0) > C(0) && O(0) <= C(1) && O(1) <= C(0) &&
                      (O(0) - C(0)) < (C(1) - O(1)) && O(trend) < O(0);
   if(bearHarami)
      PlotSignal(PID_BEAR_HARAMI, shift, time, high, low, false, InpBearColor, InpBearText, "Bearish Harami", newBarOnly);

   //--- Bullish Harami
   bool bullHarami = O(1) > C(1) && C(0) > O(0) && C(0) <= O(1) && C(1) <= O(0) &&
                      (C(0) - O(0)) < (O(1) - C(1)) && O(trend) > O(0);
   if(bullHarami)
      PlotSignal(PID_BULL_HARAMI, shift, time, high, low, true, InpBullColor, InpBullText, "Bullish Harami", newBarOnly);

   //--- Bearish Engulfing
   bool bearEng = C(1) > O(1) && O(0) > C(0) && O(0) >= C(1) && O(1) >= C(0) &&
                   (O(0) - C(0)) > (C(1) - O(1)) && O(trend) < O(0);
   if(bearEng)
      PlotSignal(PID_BEAR_ENG, shift, time, high, low, false, InpBearColor, InpBearText, "Bearish Engulfing", newBarOnly);

   //--- Bullish Engulfing
   bool bullEng = O(1) > C(1) && C(0) > O(0) && C(0) >= O(1) && C(1) >= O(0) &&
                   (C(0) - O(0)) > (O(1) - C(1)) && O(trend) > O(0);
   if(bullEng)
      PlotSignal(PID_BULL_ENG, shift, time, high, low, true, InpBullColor, InpBullText, "Bullish Engulfing", newBarOnly);

   //--- Piercing Line
   bool piercing = C(1) < O(1) && O(0) < L(1) && C(0) > (C(1) + ((O(1) - C(1)) / 2.0)) &&
                    C(0) < O(1) && O(trend) > O(0);
   if(piercing)
      PlotSignal(PID_PIERCING, shift, time, high, low, true, InpBullColor, InpBullText, "Piercing Line", newBarOnly);

   //--- Bullish Belt (needs lowest low of the 10 bars ending one bar back)
   double lower = LowestLow(low, shift + 1, 10);
   bool bullBelt = L(0) == O(0) && O(0) < lower && O(0) < C(0) &&
                    C(0) > (((H(1) - L(1)) / 2.0) + L(1)) && O(trend) > O(0);
   if(bullBelt)
      PlotSignal(PID_BULL_BELT, shift, time, high, low, true, InpBullColor, InpBullText, "Bullish Belt", newBarOnly);

   //--- Bullish Kicker
   bool bullKick = O(1) > C(1) && O(0) >= O(1) && C(0) > O(0) && O(trend) > O(0);
   if(bullKick)
      PlotSignal(PID_BULL_KICK, shift, time, high, low, true, InpBullColor, InpBullText, "Bullish Kicker", newBarOnly);

   //--- Bearish Kicker
   bool bearKick = O(1) < C(1) && O(0) <= O(1) && C(0) <= O(0) && O(trend) < O(0);
   if(bearKick)
      PlotSignal(PID_BEAR_KICK, shift, time, high, low, false, InpBearColor, InpBearText, "Bearish Kicker", newBarOnly);

   //--- Hanging Man (needs shift+2 -> guard is done by caller's loop bounds)
   bool hangingMan = (H(0) - L(0) > 4 * MathAbs(O(0) - C(0))) &&
                       ((C(0) - L(0)) / (0.001 + H(0) - L(0)) >= 0.75) &&
                       ((O(0) - L(0)) / (0.001 + H(0) - L(0)) >= 0.75) &&
                       O(trend) < O(0) && H(1) < O(0) && H(2) < O(0);
   if(hangingMan)
      PlotSignal(PID_HANGING_MAN, shift, time, high, low, false, InpBearColor, InpBearText, "Hanging Man", newBarOnly);

   //--- Evening Star
   bool eveningStar = C(2) > O(2) && MathMin(O(1), C(1)) > C(2) &&
                        O(0) < MathMin(O(1), C(1)) && C(0) < O(0);
   if(eveningStar)
      PlotSignal(PID_EVENING_STAR, shift, time, high, low, false, InpBearColor, InpBearText, "Evening Star", newBarOnly);

   //--- Morning Star
   bool morningStar = C(2) < O(2) && MathMax(O(1), C(1)) < C(2) &&
                        O(0) > MathMax(O(1), C(1)) && C(0) > O(0);
   if(morningStar)
      PlotSignal(PID_MORNING_STAR, shift, time, high, low, true, InpBullColor, InpBullText, "Morning Star", newBarOnly);

   //--- Shooting Star
   bool shootingStar = O(1) < C(1) && O(0) > C(1) &&
                          (H(0) - MathMax(O(0), C(0))) >= MathAbs(O(0) - C(0)) * 3 &&
                          (MathMin(C(0), O(0)) - L(0)) <= MathAbs(O(0) - C(0));
   if(shootingStar)
      PlotSignal(PID_SHOOTING_STAR, shift, time, high, low, false, InpBearColor, InpBearText, "Shooting Star", newBarOnly);

   //--- Hammer
   bool hammer = (H(0) - L(0) > 3 * MathAbs(O(0) - C(0))) &&
                   ((C(0) - L(0)) / (0.001 + H(0) - L(0)) > 0.6) &&
                   ((O(0) - L(0)) / (0.001 + H(0) - L(0)) > 0.6);
   if(hammer)
      PlotSignal(PID_HAMMER, shift, time, high, low, true, InpDojiColor, InpDojiText, "H", newBarOnly);

   //--- Inverted Hammer
   bool invHammer = (H(0) - L(0) > 3 * MathAbs(O(0) - C(0))) &&
                      ((H(0) - C(0)) / (0.001 + H(0) - L(0)) > 0.6) &&
                      ((H(0) - O(0)) / (0.001 + H(0) - L(0)) > 0.6);
   if(invHammer)
      PlotSignal(PID_INV_HAMMER, shift, time, high, low, true, InpDojiColor, InpDojiText, "IH", newBarOnly);

   #undef O
   #undef H
   #undef L
   #undef C
}

//+------------------------------------------------------------------+
//| Custom indicator iteration function                               |
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
   // Need up to `trend` bars back plus 2 more for the star patterns.
   int lookback = InpTrend + 2;
   if(rates_total < lookback + 2)
      return(rates_total);

   // --- Series-style local copies so shift math (O(0), O(1), O(trend)...) ---
   // matches Pine's close[1]/open[trend] directly: element 0 = most recent bar.
   double sOpen[], sHigh[], sLow[], sClose[];
   datetime sTime[];
   ArraySetAsSeries(sOpen, true);
   ArraySetAsSeries(sHigh, true);
   ArraySetAsSeries(sLow, true);
   ArraySetAsSeries(sClose, true);
   ArraySetAsSeries(sTime, true);
   ArrayCopy(sOpen, open);
   ArrayCopy(sHigh, high);
   ArrayCopy(sLow, low);
   ArrayCopy(sClose, close);
   ArrayCopy(sTime, time);

   // rates_total-1 (series index 0) is the CURRENTLY FORMING bar -- never
   // evaluate it, otherwise signals would repaint/disappear as the bar moves.
   // The most recently CLOSED bar is series index 1.
   int oldestShift = rates_total - 1 - lookback; // furthest back we can safely look
   int newestShift = 1;                          // most recent closed bar

   // Only bars not yet processed need a fresh look (prev_calculated already
   // covers everything except the last closed bar and the forming one).
   int startShift = (prev_calculated <= 1) ? oldestShift : newestShift;
   if(startShift > oldestShift) startShift = oldestShift; // safety on first run

   for(int shift = startShift; shift >= newestShift; shift--)
   {
      bool isNewestClosedBar = (shift == newestShift);
      EvaluateBar(shift, sTime, sOpen, sHigh, sLow, sClose, isNewestClosedBar);
   }

   return(rates_total);
}
//+------------------------------------------------------------------+
