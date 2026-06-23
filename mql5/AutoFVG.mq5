//+------------------------------------------------------------------+
//|                                                      AutoFVG.mq5 |
//|                                     Copyright 2026, Copter01 Bot |
//|                                                                  |
//|  เครื่องมือช่วยตีเส้น FVG (Fair Value Gap) อัตโนมัติ                 |
//|  โดยวิเคราะห์จาก Timeframe ระดับ D1 และ H4 พร้อมคัดเฉพาะ            |
//|  3 โซนล่าสุดที่ยังไม่ถูก Mitigation (ทะลวง)                          |
//+------------------------------------------------------------------+
#property copyright "Copter01 Bot"
#property version   "1.00"
#property indicator_chart_window
#property indicator_plots 0

//--- Inputs
input int    InpEngulfMinPoints = 5;               // Engulf Min Points (Default 5 pt = 0.5 pip)
input bool   InpShowD1          = true;            // Show D1 FVG
input bool   InpShowH4          = true;            // Show H4 FVG
input int    InpLookbackD1      = 100;             // D1 History Lookback
input int    InpLookbackH4      = 500;             // H4 History Lookback
input int    InpExtendBars      = 20;              // Extend Zone Right (Bars)
input color  InpBuyColor        = C'20, 50, 40';   // BUY FVG Color (Dark/Faded Green)
input color  InpSellColor       = C'60, 20, 20';   // SELL FVG Color (Dark/Faded Red)
input int    InpRefreshSec      = 60;              // Refresh Interval (Seconds)

//--- Prefix for chart objects
const string PFX = "AutoFVG_";

struct FVG_Zone
  {
   int      type;       // 1 = BUY, -1 = SELL
   datetime start_time;
   datetime end_time;   // 0 = active
   double   gap_top;
   double   gap_bot;
   string   tf_name;
  };

datetime g_last_calc = 0;

//+------------------------------------------------------------------+
//| Custom indicator initialization function                         |
//+------------------------------------------------------------------+
int OnInit()
  {
   EventSetTimer(MathMax(1, InpRefreshSec));
   RefreshFVGs();
   return(INIT_SUCCEEDED);
  }

//+------------------------------------------------------------------+
//| Custom indicator deinitialization function                       |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   EventKillTimer();
   ObjectsDeleteAll(0, PFX);
   ChartRedraw();
  }

//+------------------------------------------------------------------+
//| Timer function                                                   |
//+------------------------------------------------------------------+
void OnTimer()
  {
   RefreshFVGs();
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
   if(prev_calculated == 0 || TimeCurrent() - g_last_calc >= InpRefreshSec)
     {
      RefreshFVGs();
     }
   return(rates_total);
  }

//+------------------------------------------------------------------+
//| Main function to scan and draw FVGs                              |
//+------------------------------------------------------------------+
void RefreshFVGs()
  {
   ObjectsDeleteAll(0, PFX);
   
   if(InpShowD1) ScanAndDraw(PERIOD_D1, "D1", InpLookbackD1);
   if(InpShowH4) ScanAndDraw(PERIOD_H4, "H4", InpLookbackH4);
   
   g_last_calc = TimeCurrent();
   ChartRedraw();
  }

//+------------------------------------------------------------------+
//| Scan specific timeframe and draw Top 3 FVGs                      |
//+------------------------------------------------------------------+
void ScanAndDraw(ENUM_TIMEFRAMES tf, string tf_name, int lookback)
  {
   MqlRates rates[];
   ArraySetAsSeries(rates, false); // Index 0 is oldest
   int copied = CopyRates(_Symbol, tf, 0, lookback, rates);
   if(copied < 5) return;

   double engulf_gap = InpEngulfMinPoints * _Point;
   FVG_Zone fvgs[];
   int fvg_count = 0;

   // 1. Find all FVGs
   for(int i = 2; i < copied; i++)
     {
      double o0 = rates[i].open;
      double h0 = rates[i].high;
      double l0 = rates[i].low;
      double c0 = rates[i].close;
      datetime t0 = rates[i].time;

      double o1 = rates[i-1].open;
      double h1 = rates[i-1].high;
      double l1 = rates[i-1].low;
      double c1 = rates[i-1].close;
      datetime t1 = rates[i-1].time;

      double h2 = rates[i-2].high;
      double l2 = rates[i-2].low;

      bool bull1 = (c1 > o1);
      bool bear1 = (c1 < o1);

      // Mitigate existing FVGs
      for(int k = 0; k < fvg_count; k++)
        {
         if(fvgs[k].end_time == 0)
           {
            if(fvgs[k].type == 1 && c0 < fvgs[k].gap_bot)
               fvgs[k].end_time = t0;
            else if(fvgs[k].type == -1 && c0 > fvgs[k].gap_top)
               fvgs[k].end_time = t0;
           }
        }

      // Check for new BUY FVG
      if(bull1 && c1 > h2 + engulf_gap)
        {
         if(l0 > h2 + engulf_gap)
           {
            ArrayResize(fvgs, fvg_count + 1);
            fvgs[fvg_count].type = 1;
            fvgs[fvg_count].gap_bot = h2;
            fvgs[fvg_count].gap_top = l0;
            fvgs[fvg_count].start_time = t1;
            fvgs[fvg_count].end_time = 0;
            fvgs[fvg_count].tf_name = tf_name;
            fvg_count++;
           }
        }

      // Check for new SELL FVG
      if(bear1 && c1 < l2 - engulf_gap)
        {
         if(h0 < l2 - engulf_gap)
           {
            ArrayResize(fvgs, fvg_count + 1);
            fvgs[fvg_count].type = -1;
            fvgs[fvg_count].gap_bot = h0;
            fvgs[fvg_count].gap_top = l2;
            fvgs[fvg_count].start_time = t1;
            fvgs[fvg_count].end_time = 0;
            fvgs[fvg_count].tf_name = tf_name;
            fvg_count++;
           }
        }
     }

   // 2. Filter Active FVGs and group by type
   FVG_Zone active_buy[];
   FVG_Zone active_sell[];
   int b_count = 0;
   int s_count = 0;

   for(int i = 0; i < fvg_count; i++)
     {
      if(fvgs[i].end_time == 0) // Still active
        {
         if(fvgs[i].type == 1)
           {
            ArrayResize(active_buy, b_count + 1);
            active_buy[b_count] = fvgs[i];
            b_count++;
           }
         else if(fvgs[i].type == -1)
           {
            ArrayResize(active_sell, s_count + 1);
            active_sell[s_count] = fvgs[i];
            s_count++;
           }
        }
     }

   // 3. Draw Top 3 Recent BUY FVGs
   // Since we iterated from oldest to newest, the last elements in array are the most recent.
   int start_b = MathMax(0, b_count - 3);
   for(int i = start_b; i < b_count; i++)
     {
      DrawRect(active_buy[i], "BUY_" + IntegerToString(i));
     }

   // 4. Draw Top 3 Recent SELL FVGs
   int start_s = MathMax(0, s_count - 3);
   for(int i = start_s; i < s_count; i++)
     {
      DrawRect(active_sell[i], "SELL_" + IntegerToString(i));
     }
  }

//+------------------------------------------------------------------+
//| Draw Rectangle and Label                                         |
//+------------------------------------------------------------------+
void DrawRect(FVG_Zone &fvg, string id)
  {
   string nm = PFX + fvg.tf_name + "_" + id;
   
   datetime t_start = fvg.start_time;
   datetime t_end = TimeCurrent() + PeriodSeconds(_Period) * InpExtendBars;
   
   color clr = (fvg.type == 1) ? InpBuyColor : InpSellColor;

   // Create Rectangle
   if(ObjectFind(0, nm) < 0)
     {
      ObjectCreate(0, nm, OBJ_RECTANGLE, 0, t_start, fvg.gap_top, t_end, fvg.gap_bot);
     }
   
   ObjectSetInteger(0, nm, OBJPROP_TIME, 0, t_start);
   ObjectSetDouble(0, nm, OBJPROP_PRICE, 0, fvg.gap_top);
   ObjectSetInteger(0, nm, OBJPROP_TIME, 1, t_end);
   ObjectSetDouble(0, nm, OBJPROP_PRICE, 1, fvg.gap_bot);
   
   ObjectSetInteger(0, nm, OBJPROP_COLOR, clr);
   ObjectSetInteger(0, nm, OBJPROP_FILL, true);
   ObjectSetInteger(0, nm, OBJPROP_BACK, true);
   ObjectSetInteger(0, nm, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, nm, OBJPROP_HIDDEN, true);
   
   // Create Label
   string lbl_nm = nm + "_LBL";
   if(ObjectFind(0, lbl_nm) < 0)
     {
      ObjectCreate(0, lbl_nm, OBJ_TEXT, 0, t_start, fvg.gap_top);
     }
   
   ObjectSetInteger(0, lbl_nm, OBJPROP_TIME, 0, t_start);
   ObjectSetDouble(0, lbl_nm, OBJPROP_PRICE, 0, (fvg.gap_top + fvg.gap_bot)/2.0);
   string type_str = (fvg.type == 1) ? "BUY" : "SELL";
   ObjectSetString(0, lbl_nm, OBJPROP_TEXT, "  [" + fvg.tf_name + "] " + type_str);
   ObjectSetInteger(0, lbl_nm, OBJPROP_COLOR, clrWhite); // สีตัวอักษรสีขาวให้ตัดกับกล่อง
   ObjectSetInteger(0, lbl_nm, OBJPROP_FONTSIZE, 10);
   ObjectSetInteger(0, lbl_nm, OBJPROP_ANCHOR, ANCHOR_LEFT);
   ObjectSetInteger(0, lbl_nm, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, lbl_nm, OBJPROP_HIDDEN, true);
  }
//+------------------------------------------------------------------+
