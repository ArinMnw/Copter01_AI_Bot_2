//+------------------------------------------------------------------+
//|                         HHLLStrategy.mq5                         |
//|  Higher High / Higher Low / Lower High / Lower Low               |
//|  Ported from Pine Script "Higher High Lower Low Strategy"        |
//|  Original: (c) LonesomeThe (TradingView) - MPL 2.0             |
//+------------------------------------------------------------------+
#property copyright "Ported from Pine Script (c) LonesomeThe (MPL 2.0)"
#property link      "https://mozilla.org/MPL/2.0/"
#property version   "1.00"
#property indicator_chart_window
#property indicator_plots 0

//--- Inputs
input int             InpLeft        = 5;         // Left Bars
input int             InpRight       = 5;         // Right Bars
input color           InpBullLblClr  = clrLime;   // Label Color - Bull (HH / HL)
input color           InpBearLblClr  = clrRed;    // Label Color - Bear (LH / LL)
input int             InpRefreshSec  = 5;         // Refresh Interval (sec)
input int             InpLookback    = 500;       // Max Lookback Bars

//--- Object-name prefix (used for batch-delete)
const string PFX = "HHLL_";

//--- Signature of last drawn state (skip redraw when nothing changed)
string            g_last_sig    = "";
ENUM_TIMEFRAMES   g_last_period = PERIOD_CURRENT;

//--- Zigzag point (forward-indexed: rates[0]=oldest)
struct ZZPt
  {
   double   price;
   datetime t;
   int      dir;   // +1=pivot high, -1=pivot low
  };

//+------------------------------------------------------------------+
int OnInit()
  {
   EventSetTimer(MathMax(1, InpRefreshSec));
   Refresh();
   return INIT_SUCCEEDED;
  }

void OnDeinit(const int reason)
  {
   EventKillTimer();
   ObjectsDeleteAll(0, PFX);
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
         // Timeframe เปลี่ยน → force full redraw
         g_last_period = cur;
         g_last_sig    = "";
         Refresh();
        }
      // Scroll / zoom → object ผูก price/time อยู่แล้ว ไม่ต้อง Refresh
     }
  }

//+------------------------------------------------------------------+
// Pivot detection — forward-indexed rates[] (0=oldest)
//
// Left bars  : pivot HIGH must be STRICTLY GREATER (>=  blocks)
// Right bars : equal values allowed — use strict >  to block
//   (matches Pine Script pivothigh/pivotlow and SwingHLLevels.mq5)
//+------------------------------------------------------------------+
bool IsPH(MqlRates &r[], int i, int lb, int rb)
  {
   int n = ArraySize(r);
   if(i - lb < 0 || i + rb >= n) return false;
   double h = r[i].high;
   for(int j = i - lb; j < i;       j++) if(r[j].high >= h) return false; // left: strict >
   for(int j = i + 1;  j <= i + rb; j++) if(r[j].high >  h) return false; // right: >=
   return true;
  }

bool IsPL(MqlRates &r[], int i, int lb, int rb)
  {
   int n = ArraySize(r);
   if(i - lb < 0 || i + rb >= n) return false;
   double l = r[i].low;
   for(int j = i - lb; j < i;       j++) if(r[j].low <=  l) return false; // left: strict <
   for(int j = i + 1;  j <= i + rb; j++) if(r[j].low <   l) return false; // right: <=
   return true;
  }

//+------------------------------------------------------------------+
// Build zigzag (oldest→newest)
//   Filter 1/2 : consecutive same-direction → keep more extreme
//   Filter 3   : alternating but price is "wrong side" → skip
//     (Pine Script: hl==-1 and zz > valuewhen(zz,zz,1) → na)
//+------------------------------------------------------------------+
int BuildZZ(MqlRates &r[], int total, ZZPt &zz[], int max_out)
  {
   int cnt = 0;
   for(int i = InpLeft; i < total - InpRight; i++)
     {
      bool ph = IsPH(r, i, InpLeft, InpRight);
      bool pl = IsPL(r, i, InpLeft, InpRight);
      if(!ph && !pl) continue;

      // Both PH and PL at same bar — prefer continuation direction
      if(ph && pl)
        {
         if(cnt > 0 && zz[cnt-1].dir == 1) ph = false;
         else                               pl = false;
        }

      double p = ph ? r[i].high : r[i].low;
      int    d = ph ? 1 : -1;

      // Filter 1/2: consecutive same-direction → keep more extreme
      if(cnt > 0 && zz[cnt-1].dir == d)
        {
         if(d == 1  && p <= zz[cnt-1].price) continue; // lower high  → skip
         if(d == -1 && p >= zz[cnt-1].price) continue; // higher low  → skip
         cnt--;                                          // replace with more extreme
        }

      // Filter 3: direction alternated but price is on wrong side
      //   LOW  > previous HIGH → impossible/invalid → skip
      //   HIGH < previous LOW  → impossible/invalid → skip
      if(cnt > 0)
        {
         if(d == -1 && p > zz[cnt-1].price) continue;  // low above prev high
         if(d ==  1 && p < zz[cnt-1].price) continue;  // high below prev low
        }

      if(cnt >= max_out) break;
      zz[cnt].price = p;
      zz[cnt].t     = r[i].time;
      zz[cnt].dir   = d;
      cnt++;
     }
   return cnt;
  }

//+------------------------------------------------------------------+
// Classify zigzag point k as "HH" | "HL" | "LH" | "LL" | ""
// Mirrors Pine Script findprevious() + _hh/_ll/_hl/_lh conditions
//+------------------------------------------------------------------+
string ClassifyPt(ZZPt &zz[], int k)
  {
   if(k < 4) return "";

   double a  = zz[k].price;
   int    ad = zz[k].dir;   // +1=high, -1=low
   int    opp = -ad;

   // b = prev opposite, c = prev same, d = prev opposite, e = prev same
   double b = 0, c = 0, d = 0, e = 0;
   int step = 0, need = opp;
   for(int j = k - 1; j >= 0 && step < 4; j--)
     {
      if(zz[j].dir != need) continue;
      switch(step)
        {
         case 0: b = zz[j].price; need = ad;  break;
         case 1: c = zz[j].price; need = opp; break;
         case 2: d = zz[j].price; need = ad;  break;
         case 3: e = zz[j].price;              break;
        }
      step++;
     }
   if(step < 4) return "";

   // Pine Script classification (ported directly)
   bool is_hh = (a > b) && (a > c) && (c > b) && (c > d);
   bool is_ll = (a < b) && (a < c) && (c < b) && (c < d);
   bool is_hl = ((a >= c && b > c && b > d && d > c && d > e) ||
                 (a <  b && a > c && b < d));
   bool is_lh = ((a <= c && b < c && b < d && d < c && d < e) ||
                 (a >  b && a < c && b > d));

   if(is_hh) return "HH";
   if(is_ll) return "LL";
   if(is_hl) return "HL";
   if(is_lh) return "LH";
   return "";
  }

//+------------------------------------------------------------------+
// Object helpers
//+------------------------------------------------------------------+
void SetLabel(const string nm, datetime t, double price,
              const string txt, color clr, bool above)
  {
   if(ObjectFind(0, nm) < 0) ObjectCreate(0, nm, OBJ_TEXT, 0, t, price);
   ObjectSetInteger(0, nm, OBJPROP_TIME,  0, (long)t);
   ObjectSetDouble(0,  nm, OBJPROP_PRICE, 0, price);
   ObjectSetString(0,  nm, OBJPROP_TEXT,  txt);
   ObjectSetInteger(0, nm, OBJPROP_COLOR, clr);
   ObjectSetInteger(0, nm, OBJPROP_FONTSIZE, 9);
   ObjectSetInteger(0, nm, OBJPROP_ANCHOR, above ? ANCHOR_LOWER : ANCHOR_UPPER);
   ObjectSetInteger(0, nm, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, nm, OBJPROP_HIDDEN, true);
  }

//+------------------------------------------------------------------+
// Keep-list helpers — track which objects are still active
//+------------------------------------------------------------------+
void AppendName(string &keep[], const string nm)
  {
   int pos = ArraySize(keep);
   ArrayResize(keep, pos + 1);
   keep[pos] = nm;
  }

// Delete objects with PFX that are NOT in keep[] (no full clear → no flicker)
void CleanupStale(string &keep[])
  {
   int ksz = ArraySize(keep);
   int total = ObjectsTotal(0);
   for(int i = total - 1; i >= 0; i--)
     {
      string nm = ObjectName(0, i);
      if(StringFind(nm, PFX) != 0) continue;   // not our object
      bool found = false;
      for(int j = 0; j < ksz; j++)
         if(keep[j] == nm) { found = true; break; }
      if(!found) ObjectDelete(0, nm);
     }
  }

//+------------------------------------------------------------------+
// Main refresh — signature check first, then upsert + cleanup
// ถ้า zigzag ไม่เปลี่ยน → return ทันที ไม่แตะ object เลย = ไม่กระพริบ
//+------------------------------------------------------------------+
void Refresh()
  {
   int copy_n = InpLookback + InpLeft + InpRight + 5;
   MqlRates rates[];
   int copied = CopyRates(_Symbol, PERIOD_CURRENT, 0, copy_n, rates);
   if(copied < InpLeft + InpRight + 10) return;
   int total = ArraySize(rates);

   // Build zigzag
   ZZPt zz[];
   ArrayResize(zz, total);
   int zz_n = BuildZZ(rates, total, zz, total);
   if(zz_n < 5) return;

   // --- Signature check ---
   // คำนวณ fingerprint จาก classified labels เท่านั้น
   // ถ้าเหมือนเดิม → ข้อมูลไม่เปลี่ยน → return ทันที ไม่ repaint
   string sig = IntegerToString(_Period) + "|";
   for(int k = 0; k < zz_n; k++)
     {
      string lbl = ClassifyPt(zz, k);
      if(lbl == "") continue;
      sig += lbl + IntegerToString((long)zz[k].t)
           + DoubleToString(zz[k].price, _Digits) + "|";
     }
   if(sig == g_last_sig) return;   // ไม่มีอะไรเปลี่ยน → ออกเลย
   g_last_sig = sig;

   // Names of all objects drawn this round (for CleanupStale)
   string keep[];
   ArrayResize(keep, 0);

   //------------------------------------------------------------------
   // Draw HH/HL/LH/LL labels only — SR lines feature removed
   //------------------------------------------------------------------
   for(int k = 0; k < zz_n; k++)
     {
      string lbl   = ClassifyPt(zz, k);
      if(lbl == "") continue;

      bool   hh    = (lbl == "HH"), hl = (lbl == "HL");
      double price = zz[k].price;
      datetime t   = zz[k].t;
      bool   above = (zz[k].dir == 1);

      color  lbl_clr = (hh || hl) ? InpBullLblClr : InpBearLblClr;
      string nm      = PFX+"L_"+IntegerToString((long)t);
      SetLabel(nm, t, price, lbl, lbl_clr, above);
      AppendName(keep, nm);
     }

   // Remove objects that are no longer needed (no full-clear = no flicker)
   CleanupStale(keep);
   ChartRedraw();
  }
//+------------------------------------------------------------------+
