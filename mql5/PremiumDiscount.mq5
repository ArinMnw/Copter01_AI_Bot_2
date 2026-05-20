//+------------------------------------------------------------------+
//|                                       PremiumDiscount.mq5         |
//|  Premium & Discount Zone Indicator                                 |
//|                                                                    |
//|  อ่าน H / L ล่าสุดจาก labels ของ HHLLStrategy.mq5 (prefix HHLL_L_) |
//|  แล้วตี zone:                                                       |
//|    H               = swing high ล่าสุด (HH หรือ LH ตัวใหม่สุด)      |
//|    L               = swing low  ล่าสุด (HL หรือ LL ตัวใหม่สุด)      |
//|    EQ              = (H + L) / 2   (Equilibrium / midpoint)        |
//|    Premium zone    = EQ → H  (โซนบน — แพง, เหมาะ SELL)              |
//|    Discount zone   = L → EQ  (โซนล่าง — ถูก, เหมาะ BUY)            |
//|                                                                    |
//|  หมายเหตุ: ต้องแนบ HHLLStrategy.mq5 บน chart เดียวกันก่อน          |
//+------------------------------------------------------------------+
#property copyright "Copter01 AI Bot"
#property version   "1.00"
#property indicator_chart_window
#property indicator_plots 0

//--- Inputs
input bool            InpShowEQ         = true;             // Show Equilibrium (EQ) Line
input bool            InpShowHL         = true;             // Show H / L Boundary Lines
input bool            InpShowLabels     = true;             // Show Text Labels (PREMIUM/DISCOUNT/EQ)
input bool            InpExtendRight    = true;             // Extend lines to Right
input int             InpExtendBars     = 20;               // Extra bars to extend right (when InpExtendRight=true)
input color           InpPremiumColor   = clrTomato;        // Premium Label Color
input color           InpDiscountColor  = clrLimeGreen;     // Discount Label Color
input color           InpEQColor        = clrGold;          // Equilibrium Line
input color           InpHColor         = clrTomato;        // H Boundary
input color           InpLColor         = clrLimeGreen;     // L Boundary
input ENUM_LINE_STYLE InpLineStyle      = STYLE_SOLID;      // Line Style (H/L/EQ)
input int             InpLineWidth      = 1;                // Line Width
input int             InpLabelFontSize  = 9;                // Label Font Size
input int             InpRefreshSec     = 5;                // Refresh Interval (sec)
input string          InpHHLLPrefix     = "HHLL_L_";        // HHLLStrategy Label Prefix

//--- Object prefix
const string PFX = "PD_";

//--- State
string          g_last_sig    = "";
ENUM_TIMEFRAMES g_last_period = PERIOD_CURRENT;

//+------------------------------------------------------------------+
int OnInit()
  {
   EventSetTimer(MathMax(1, InpRefreshSec));
   g_last_period = (ENUM_TIMEFRAMES)_Period;
   Refresh();
   return INIT_SUCCEEDED;
  }

void OnDeinit(const int reason)
  {
   EventKillTimer();
   ObjectsDeleteAll(0, PFX);
   Comment("");
   ChartRedraw();
  }

void OnTimer() { Refresh(); }

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
   if(prev_calculated == 0) Refresh();
   return rates_total;
  }

void OnChartEvent(const int id, const long &lparam,
                  const double &dparam, const string &sparam)
  {
   if(id == CHARTEVENT_CHART_CHANGE)
     {
      ENUM_TIMEFRAMES cur = (ENUM_TIMEFRAMES)_Period;
      if(cur != g_last_period)
        {
         g_last_period = cur;
         g_last_sig    = "";
         Refresh();
        }
     }
  }

//+------------------------------------------------------------------+
// หา H / L ล่าสุดจาก labels ของ HHLLStrategy.mq5
//   H = newest among HH/LH (max time)
//   L = newest among HL/LL (max time)
// return true ถ้าพบทั้ง H และ L
//+------------------------------------------------------------------+
bool FindLatestHL(double &h_price, datetime &h_time,
                  double &l_price, datetime &l_time)
  {
   h_price = 0; l_price = 0; h_time = 0; l_time = 0;
   int prefix_len = StringLen(InpHHLLPrefix);
   int total = ObjectsTotal(0);

   for(int i = 0; i < total; i++)
     {
      string nm = ObjectName(0, i);
      if(StringFind(nm, InpHHLLPrefix) != 0) continue;

      string   txt = ObjectGetString(0,  nm, OBJPROP_TEXT);
      datetime t   = (datetime)ObjectGetInteger(0, nm, OBJPROP_TIME, 0);
      double   p   = ObjectGetDouble(0,  nm, OBJPROP_PRICE, 0);

      if(txt == "HH" || txt == "LH")
        {
         if(t > h_time) { h_time = t; h_price = p; }
        }
      else if(txt == "HL" || txt == "LL")
        {
         if(t > l_time) { l_time = t; l_price = p; }
        }
     }
   return (h_price > 0 && l_price > 0);
  }

//+------------------------------------------------------------------+
// วาดเส้นแนวนอน segment (OBJ_TREND ใช้เป็น horizontal เพราะ p1==p2)
//+------------------------------------------------------------------+
void DrawHLine(const string nm, datetime t1, datetime t2,
               double price, color clr,
               ENUM_LINE_STYLE style, int width)
  {
   if(ObjectFind(0, nm) < 0)
      ObjectCreate(0, nm, OBJ_TREND, 0, t1, price, t2, price);
   ObjectSetInteger(0, nm, OBJPROP_TIME,  0, (long)t1);
   ObjectSetDouble (0, nm, OBJPROP_PRICE, 0, price);
   ObjectSetInteger(0, nm, OBJPROP_TIME,  1, (long)t2);
   ObjectSetDouble (0, nm, OBJPROP_PRICE, 1, price);
   ObjectSetInteger(0, nm, OBJPROP_COLOR, clr);
   ObjectSetInteger(0, nm, OBJPROP_STYLE, style);
   ObjectSetInteger(0, nm, OBJPROP_WIDTH, width);
   ObjectSetInteger(0, nm, OBJPROP_RAY_RIGHT, false);
   ObjectSetInteger(0, nm, OBJPROP_RAY_LEFT,  false);
   ObjectSetInteger(0, nm, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, nm, OBJPROP_HIDDEN,     true);
   ObjectSetInteger(0, nm, OBJPROP_BACK,       false);
  }

//+------------------------------------------------------------------+
// วาด text label
//+------------------------------------------------------------------+
void DrawText(const string nm, datetime t, double price,
              const string txt, color clr,
              ENUM_ANCHOR_POINT anchor = ANCHOR_LEFT)
  {
   if(ObjectFind(0, nm) < 0)
      ObjectCreate(0, nm, OBJ_TEXT, 0, t, price);
   ObjectSetInteger(0, nm, OBJPROP_TIME,  0, (long)t);
   ObjectSetDouble (0, nm, OBJPROP_PRICE, 0, price);
   ObjectSetString (0, nm, OBJPROP_TEXT, txt);
   ObjectSetInteger(0, nm, OBJPROP_COLOR, clr);
   ObjectSetInteger(0, nm, OBJPROP_FONTSIZE, InpLabelFontSize);
   ObjectSetInteger(0, nm, OBJPROP_ANCHOR, anchor);
   ObjectSetInteger(0, nm, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, nm, OBJPROP_HIDDEN,     true);
  }

//+------------------------------------------------------------------+
// Main refresh
//+------------------------------------------------------------------+
void Refresh()
  {
   double   h_price = 0, l_price = 0;
   datetime h_time  = 0, l_time  = 0;

   if(!FindLatestHL(h_price, h_time, l_price, l_time))
     {
      Comment("PremiumDiscount: ไม่พบ HHLL labels — แนบ HHLLStrategy.mq5 บน chart เดียวกันก่อน");
      ObjectsDeleteAll(0, PFX);
      g_last_sig = "";
      ChartRedraw();
      return;
     }

   if(h_price <= l_price)
     {
      Comment("PremiumDiscount: H (", DoubleToString(h_price, _Digits),
              ") <= L (", DoubleToString(l_price, _Digits), ") — invalid range");
      ObjectsDeleteAll(0, PFX);
      g_last_sig = "";
      ChartRedraw();
      return;
     }

   // --- Signature check (skip redraw when nothing changed) ---
   string sig = IntegerToString(_Period) + "|"
              + DoubleToString(h_price, _Digits) + "|" + IntegerToString((long)h_time) + "|"
              + DoubleToString(l_price, _Digits) + "|" + IntegerToString((long)l_time);
   if(sig == g_last_sig) return;
   g_last_sig = sig;

   ObjectsDeleteAll(0, PFX);

   // ── Compute zone boundaries ──────────────────────────────────────
   double   eq      = (h_price + l_price) / 2.0;
   datetime t_start = (h_time < l_time) ? h_time : l_time;       // older of two
   datetime t_end   = (datetime)SeriesInfoInteger(_Symbol, _Period, SERIES_LASTBAR_DATE);
   if(InpExtendRight)
      t_end += PeriodSeconds(_Period) * MathMax(0, InpExtendBars);
   if(t_end <= t_start)
      t_end = t_start + PeriodSeconds(_Period) * 10;

   // ── H / L boundary lines ────────────────────────────────────────
   if(InpShowHL)
     {
      DrawHLine(PFX+"H",  t_start, t_end, h_price, InpHColor, InpLineStyle, InpLineWidth);
      DrawHLine(PFX+"L",  t_start, t_end, l_price, InpLColor, InpLineStyle, InpLineWidth);
     }

   // ── Equilibrium line ────────────────────────────────────────────
   if(InpShowEQ)
      DrawHLine(PFX+"EQ", t_start, t_end, eq, InpEQColor, InpLineStyle, InpLineWidth);

   // ── Labels at right edge ────────────────────────────────────────
   if(InpShowLabels)
     {
      DrawText(PFX+"PREM_T", t_end, h_price,
               " PREMIUM " + DoubleToString(h_price, _Digits),
               InpPremiumColor, ANCHOR_LEFT);
      DrawText(PFX+"DISC_T", t_end, l_price,
               " DISCOUNT " + DoubleToString(l_price, _Digits),
               InpDiscountColor, ANCHOR_LEFT);
      DrawText(PFX+"EQ_T",   t_end, eq,
               " EQ " + DoubleToString(eq, _Digits),
               InpEQColor, ANCHOR_LEFT);
     }

   Comment("PremiumDiscount: H=", DoubleToString(h_price, _Digits),
           " EQ=", DoubleToString(eq, _Digits),
           " L=", DoubleToString(l_price, _Digits),
           " | range=", DoubleToString(h_price - l_price, _Digits));
   ChartRedraw();
  }
//+------------------------------------------------------------------+
