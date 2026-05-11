//+------------------------------------------------------------------+
//|                                               SwingHLLevels.mq5  |
//|  Draw latest swing high / swing low for selected TFs using the   |
//|  same 2-candle swing logic as strategy4.py, extending each line  |
//|  to the right for about N bars of that TF.                       |
//+------------------------------------------------------------------+
#property copyright "Copter01 AI Bot"
#property link      ""
#property version   "1.00"
#property indicator_chart_window
#property indicator_plots 0

input string InpFileName         = "trend_state.txt"; // Shared file under Common\Files
input int    InpLookback         = 100;          // Swing lookback
input int    InpExtendBars       = 5;            // Extend to right in TF bars
input int    InpRefreshSec       = 5;            // Refresh interval (seconds)
input bool   InpOnlyPerTfOn      = true;         // Draw only TFs opened in bot (per_tf_on=1)
input bool   InpShowLabels       = true;         // Show labels
input int    InpLabelFontSize    = 9;            // Label font size
input color  InpHighColor        = clrTomato;    // Swing High color
input color  InpLowColor         = clrDeepSkyBlue; // Swing Low color
input ENUM_LINE_STYLE InpLineStyle = STYLE_DASH; // Line style
input int    InpLineWidth        = 2;            // Line width

input bool   InpShowM1           = true;
input bool   InpShowM5           = true;
input bool   InpShowM15          = true;
input bool   InpShowM30          = true;
input bool   InpShowH1           = true;
input bool   InpShowH4           = true;
input bool   InpShowH12          = true;
input bool   InpShowD1           = true;

string g_prefix = "SHL_";

struct TFSpec
  {
   string name;
   ENUM_TIMEFRAMES period;
   bool enabled;
   int per_tf_on;
  };

struct SwingPoint
  {
   bool found;
   datetime time;
   double price;
  };

//+------------------------------------------------------------------+
int OnInit()
  {
   EventSetTimer(MathMax(1, InpRefreshSec));
   RefreshLevels();
   return(INIT_SUCCEEDED);
  }

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   EventKillTimer();
   ObjectsDeleteAll(0, g_prefix);
   ChartRedraw();
  }

//+------------------------------------------------------------------+
void OnTimer()
  {
   RefreshLevels();
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
   return(rates_total);
  }

//+------------------------------------------------------------------+
void OnChartEvent(const int id, const long &lparam,
                  const double &dparam, const string &sparam)
  {
   if(id == CHARTEVENT_CHART_CHANGE)
      RefreshLevels();
  }

//+------------------------------------------------------------------+
string ChartTfName()
  {
   switch(_Period)
     {
      case PERIOD_M1:  return "M1";
      case PERIOD_M5:  return "M5";
      case PERIOD_M15: return "M15";
      case PERIOD_M30: return "M30";
      case PERIOD_H1:  return "H1";
      case PERIOD_H4:  return "H4";
      case PERIOD_H12: return "H12";
      case PERIOD_D1:  return "D1";
     }
  return "";
  }

//+------------------------------------------------------------------+
string ResolveTrendFileName()
  {
   string symbol_file = "trend_state_" + _Symbol + ".txt";
   if(InpFileName == "" || InpFileName == "trend_state.txt")
     {
      if(FileIsExist(symbol_file, FILE_COMMON))
         return symbol_file;
      return "trend_state.txt";
     }
   return InpFileName;
  }

//+------------------------------------------------------------------+
int SplitCsv(const string line, string &parts[])
  {
   return StringSplit(line, (ushort)',', parts);
  }

//+------------------------------------------------------------------+
void ApplyPerTfOnFromFile(TFSpec &specs[])
  {
   for(int i = 0; i < ArraySize(specs); ++i)
      specs[i].per_tf_on = -1;

   string file_name = ResolveTrendFileName();
   int handle = FileOpen(file_name, FILE_READ|FILE_TXT|FILE_ANSI|FILE_COMMON);
   if(handle == INVALID_HANDLE)
      return;

   while(!FileIsEnding(handle))
     {
      string line = FileReadString(handle);
      if(line == "" || StringGetCharacter(line, 0) == '#')
         continue;

      string p[];
      int n = SplitCsv(line, p);
      if(n < 13)
         continue;

      string tf_name = p[0];
      int per_tf_on = (int)StringToInteger(p[12]);
      for(int i = 0; i < ArraySize(specs); ++i)
        {
         if(specs[i].name == tf_name)
           {
            specs[i].per_tf_on = per_tf_on;
            break;
           }
        }
     }

   FileClose(handle);
  }

//+------------------------------------------------------------------+
bool InBody(const double price, const MqlRates &bar)
  {
   double body_low = MathMin(bar.open, bar.close);
   double body_high = MathMax(bar.open, bar.close);
   return (body_low <= price && price <= body_high);
  }

//+------------------------------------------------------------------+
int TfSeconds(const ENUM_TIMEFRAMES tf)
  {
   return PeriodSeconds(tf);
  }

//+------------------------------------------------------------------+
bool ShouldShowTf(const TFSpec &spec, const string chart_tf)
  {
   if(!spec.enabled)
      return false;
   if(InpOnlyPerTfOn && spec.per_tf_on == 0)
      return false;
   if(chart_tf == "")
      return false;
   if(spec.name != chart_tf)
      return false;
   return true;
  }

//+------------------------------------------------------------------+
SwingPoint FindPrevSwingHigh(MqlRates &rates[], const int lookback)
  {
   SwingPoint out;
   out.found = false;

   int total = ArraySize(rates);
   if(total < 6)
      return out;

   int use_n = MathMin(lookback, total);
   int start = total - use_n;
   int end_exclusive = total - 3;
   if(end_exclusive - start < 3)
      return out;

   for(int i = end_exclusive - 2; i >= start + 1; --i)
     {
      bool bull_i = (rates[i].close > rates[i].open);
      bool bull_next = (rates[i + 1].close > rates[i + 1].open);
      if(!bull_i)
         continue;
      if(bull_next)
         continue;

      double swing_h = MathMax(rates[i].high, rates[i + 1].high);

      if(i - 1 >= start)
        {
         MqlRates prev_bar = rates[i - 1];
         bool prev_bull = (prev_bar.close > prev_bar.open);
         if(!prev_bull && InBody(swing_h, prev_bar))
            continue;
        }

      bool invalidated = false;
      for(int j = i + 2; j < end_exclusive; ++j)
        {
         if(rates[j].high >= swing_h)
           {
            invalidated = true;
            break;
           }
        }
      if(invalidated)
         continue;

      int max_idx = (rates[i].high >= rates[i + 1].high) ? i : (i + 1);
      out.found = true;
      out.time = rates[max_idx].time;
      out.price = swing_h;
      return out;
     }
   return out;
  }

//+------------------------------------------------------------------+
SwingPoint FindPrevSwingLow(MqlRates &rates[], const int lookback)
  {
   SwingPoint out;
   out.found = false;

   int total = ArraySize(rates);
   if(total < 6)
      return out;

   int use_n = MathMin(lookback, total);
   int start = total - use_n;
   int end_exclusive = total - 3;
   if(end_exclusive - start < 3)
      return out;

   for(int i = end_exclusive - 2; i >= start + 1; --i)
     {
      bool bull_i = (rates[i].close > rates[i].open);
      bool bull_next = (rates[i + 1].close > rates[i + 1].open);
      if(bull_i)
         continue;
      if(!bull_next)
         continue;

      double swing_l = MathMin(rates[i].low, rates[i + 1].low);

      if(i - 1 >= start)
        {
         MqlRates prev_bar = rates[i - 1];
         bool prev_bull = (prev_bar.close > prev_bar.open);
         if(prev_bull && InBody(swing_l, prev_bar))
            continue;
        }

      bool invalidated = false;
      for(int j = i + 2; j < end_exclusive; ++j)
        {
         if(rates[j].low <= swing_l)
           {
            invalidated = true;
            break;
           }
        }
      if(invalidated)
         continue;

      int min_idx = (rates[i].low <= rates[i + 1].low) ? i : (i + 1);
      out.found = true;
      out.time = rates[min_idx].time;
      out.price = swing_l;
      return out;
     }
   return out;
  }

//+------------------------------------------------------------------+
void DrawLevel(const string name,
               const datetime t1,
               const datetime t2,
               const double price,
               const color clr,
               const string label)
  {
   string lbl_name = name + "_lbl";
   if(t1 <= 0 || t2 <= 0 || price <= 0 || t2 <= t1)
     {
      ObjectDelete(0, name);
      ObjectDelete(0, lbl_name);
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

   if(InpShowLabels)
     {
      if(ObjectFind(0, lbl_name) < 0)
         ObjectCreate(0, lbl_name, OBJ_TEXT, 0, t2, price);
      ObjectSetInteger(0, lbl_name, OBJPROP_TIME, t2);
      ObjectSetDouble(0, lbl_name, OBJPROP_PRICE, price);
      ObjectSetString(0, lbl_name, OBJPROP_TEXT, label);
      ObjectSetInteger(0, lbl_name, OBJPROP_COLOR, clr);
      ObjectSetInteger(0, lbl_name, OBJPROP_FONTSIZE, InpLabelFontSize);
      ObjectSetInteger(0, lbl_name, OBJPROP_ANCHOR, ANCHOR_LEFT);
      ObjectSetInteger(0, lbl_name, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, lbl_name, OBJPROP_HIDDEN, true);
     }
   else
     {
      ObjectDelete(0, lbl_name);
     }
  }

//+------------------------------------------------------------------+
void RefreshLevels()
  {
   string chart_tf = ChartTfName();
   if(chart_tf == "")
     {
      ObjectsDeleteAll(0, g_prefix);
      ChartRedraw();
      return;
     }
   TFSpec specs[8];

   specs[0].name = "M1";  specs[0].period = PERIOD_M1;  specs[0].enabled = InpShowM1;
   specs[1].name = "M5";  specs[1].period = PERIOD_M5;  specs[1].enabled = InpShowM5;
   specs[2].name = "M15"; specs[2].period = PERIOD_M15; specs[2].enabled = InpShowM15;
   specs[3].name = "M30"; specs[3].period = PERIOD_M30; specs[3].enabled = InpShowM30;
   specs[4].name = "H1";  specs[4].period = PERIOD_H1;  specs[4].enabled = InpShowH1;
   specs[5].name = "H4";  specs[5].period = PERIOD_H4;  specs[5].enabled = InpShowH4;
   specs[6].name = "H12"; specs[6].period = PERIOD_H12; specs[6].enabled = InpShowH12;
   specs[7].name = "D1";  specs[7].period = PERIOD_D1;  specs[7].enabled = InpShowD1;
   ApplyPerTfOnFromFile(specs);

   for(int k = 0; k < ArraySize(specs); ++k)
     {
      string base = g_prefix + specs[k].name + "_";
      if(!ShouldShowTf(specs[k], chart_tf))
        {
         ObjectDelete(0, base + "H");
         ObjectDelete(0, base + "H_lbl");
         ObjectDelete(0, base + "L");
         ObjectDelete(0, base + "L_lbl");
         continue;
        }

      MqlRates rates[];
      int copied = CopyRates(_Symbol, specs[k].period, 0, InpLookback + 10, rates);
      if(copied <= 0)
        {
         ObjectDelete(0, base + "H");
         ObjectDelete(0, base + "H_lbl");
         ObjectDelete(0, base + "L");
         ObjectDelete(0, base + "L_lbl");
         continue;
        }

      SwingPoint sh = FindPrevSwingHigh(rates, InpLookback);
      SwingPoint sl = FindPrevSwingLow(rates, InpLookback);
      int tf_sec = TfSeconds(specs[k].period);

      if(sh.found)
        {
         datetime end_h = sh.time + (datetime)(tf_sec * MathMax(1, InpExtendBars));
         DrawLevel(base + "H", sh.time, end_h, sh.price, InpHighColor,
                   "[" + specs[k].name + "] H " + DoubleToString(sh.price, _Digits));
        }
      else
        {
         ObjectDelete(0, base + "H");
         ObjectDelete(0, base + "H_lbl");
        }

      if(sl.found)
        {
         datetime end_l = sl.time + (datetime)(tf_sec * MathMax(1, InpExtendBars));
         DrawLevel(base + "L", sl.time, end_l, sl.price, InpLowColor,
                   "[" + specs[k].name + "] L " + DoubleToString(sl.price, _Digits));
        }
      else
        {
         ObjectDelete(0, base + "L");
         ObjectDelete(0, base + "L_lbl");
        }
     }

   ChartRedraw();
  }
//+------------------------------------------------------------------+
