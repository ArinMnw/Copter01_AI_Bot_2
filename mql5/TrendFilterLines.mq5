//+------------------------------------------------------------------+
//|                                            TrendFilterLines.mq5  |
//|  ต่อยอดจาก HHLLStrategy.mq5                                      |
//|                                                                   |
//|  Current chart TF : อ่าน labels HHLL_L_* ของ HHLLStrategy        |
//|                     (ต้องแนบ HHLLStrategy บน chart นี้)           |
//|  TF อื่นใน panel  : คำนวณเองด้วย CopyRates + BuildZZ             |
//|                     (InpPivotLeft/Right ควรตรงกับ HHLLStrategy)   |
//|                                                                   |
//|  เส้น  : วาดเฉพาะ TF ของ chart ปัจจุบัน (จาก HHLLStrategy labels)|
//|  Panel : แสดงทุก TF ที่เปิดไว้                                    |
//|                                                                   |
//|  Trend rule:                                                      |
//|    newest_high=HH AND newest_low=HL → BULL  (strong)             |
//|    newest_high=LH AND newest_low=LL → BEAR  (strong)             |
//|    otherwise                        → SIDEWAY (weak)             |
//+------------------------------------------------------------------+
#property copyright   "Copter01 AI Bot"
#property link        ""
#property version     "4.10"
#property indicator_chart_window
#property indicator_plots 0

// ── HHLLStrategy label prefix (สำหรับ current chart TF) ──
input string InpHHLLPrefix      = "HHLL_L_";   // HHLLStrategy label prefix

// ── Pivot (สำหรับ TF อื่นใน panel — ควรตรงกับ HHLLStrategy InpLeft/InpRight) ──
input int    InpPivotLeft       = 5;            // Left bars  (ตรงกับ HHLLStrategy InpLeft)
input int    InpPivotRight      = 5;            // Right bars (ตรงกับ HHLLStrategy InpRight)
input int    InpLookback        = 300;          // Bars ย้อนหลังต่อ TF (non-chart TFs)
input int    InpRefreshSec      = 5;            // Refresh interval (seconds)

// ── TF เปิด/ปิด (panel) ──
input bool   InpShowM1          = true;
input bool   InpShowM5          = true;
input bool   InpShowM15         = true;
input bool   InpShowM30         = true;
input bool   InpShowH1          = true;
input bool   InpShowH4          = true;
input bool   InpShowH12         = true;
input bool   InpShowD1          = true;

// ── สี / ความหนา ──
input color  InpBullColor       = clrLime;
input color  InpBearColor       = clrRed;
input color  InpSidewayColor    = clrGray;
input int    InpStrongWidth     = 2;
input int    InpWeakWidth       = 1;
input bool   InpShowLabels      = true;
input int    InpLabelFontSize   = 9;

// ── Panel ──
input bool   InpShowPanel       = true;
input int    InpPanelXOffset    = 10;
input int    InpPanelYOffset    = 20;
input int    InpPanelFontSize   = 10;
input string InpPanelFont       = "Consolas";
input color  InpPanelHeaderColor = clrWhite;

//+------------------------------------------------------------------+
const string g_prefix = "TFL_";
string       g_last_sig = "";

struct ZZPt
  {
   double   price;
   datetime t;
   int      dir;
  };

struct SwingPt
  {
   datetime t;
   double   price;
   string   label;
  };

struct TFInfo
  {
   ENUM_TIMEFRAMES period;
   string          name;
   string          trend;
   string          strength;
   SwingPt         h1, h2, l1, l2;
   bool            ok;
  };

//+------------------------------------------------------------------+
//| Pivot helpers — ported from HHLLStrategy.mq5                     |
//+------------------------------------------------------------------+
bool IsPH(MqlRates &r[], int i, int lb, int rb)
  {
   int n = ArraySize(r);
   if(i - lb < 0 || i + rb >= n) return false;
   double h = r[i].high;
   for(int j = i - lb; j < i;       j++) if(r[j].high >= h) return false;
   for(int j = i + 1;  j <= i + rb; j++) if(r[j].high >  h) return false;
   return true;
  }

bool IsPL(MqlRates &r[], int i, int lb, int rb)
  {
   int n = ArraySize(r);
   if(i - lb < 0 || i + rb >= n) return false;
   double l = r[i].low;
   for(int j = i - lb; j < i;       j++) if(r[j].low <=  l) return false;
   for(int j = i + 1;  j <= i + rb; j++) if(r[j].low <   l) return false;
   return true;
  }

int BuildZZ(MqlRates &r[], int total, ZZPt &zz[], int max_out, int lb, int rb)
  {
   int cnt = 0;
   for(int i = lb; i < total - rb; i++)
     {
      bool ph = IsPH(r, i, lb, rb);
      bool pl = IsPL(r, i, lb, rb);
      if(!ph && !pl) continue;
      if(ph && pl)
        {
         if(cnt > 0 && zz[cnt-1].dir == 1) ph = false;
         else                               pl = false;
        }
      double p = ph ? r[i].high : r[i].low;
      int    d = ph ? 1 : -1;
      if(cnt > 0 && zz[cnt-1].dir == d)
        {
         if(d ==  1 && p <  zz[cnt-1].price) continue;
         if(d == -1 && p >  zz[cnt-1].price) continue;
        }
      if(cnt > 0)
        {
         if(d == -1 && p > zz[cnt-1].price) continue;
         if(d ==  1 && p < zz[cnt-1].price) continue;
        }
      if(cnt >= max_out) break;
      zz[cnt].price = p; zz[cnt].t = r[i].time; zz[cnt].dir = d;
      cnt++;
     }
   return cnt;
  }

string ClassifyPt(ZZPt &zz[], int k)
  {
   if(k < 4) return "";
   double a = zz[k].price; int ad = zz[k].dir; int opp = -ad;
   double b=0, c=0, d=0, e=0; int step=0, need=opp;
   for(int j = k-1; j >= 0 && step < 4; j--)
     {
      if(zz[j].dir != need) continue;
      switch(step)
        {
         case 0: b=zz[j].price; need=ad;  break;
         case 1: c=zz[j].price; need=opp; break;
         case 2: d=zz[j].price; need=ad;  break;
         case 3: e=zz[j].price;           break;
        }
      step++;
     }
   if(step < 4) return "";
   bool is_hh = (a>b)&&(a>c)&&(c>b)&&(c>d);
   bool is_ll = (a<b)&&(a<c)&&(c<b)&&(c<d);
   bool is_hl = ((a>=c&&b>c&&b>d&&d>c&&d>e)||(a<b&&a>c&&b<d));
   bool is_lh = ((a<=c&&b<c&&b<d&&d<c&&d<e)||(a>b&&a<c&&b>d));
   if(is_hh) return "HH";
   if(is_ll) return "LL";
   if(is_hl) return "HL";
   if(is_lh) return "LH";
   return "";
  }

//+------------------------------------------------------------------+
//| อ่าน HHLLStrategy labels บน chart ปัจจุบัน → h1/h2/l1/l2         |
//| (ใช้กับ current chart TF เท่านั้น)                                |
//+------------------------------------------------------------------+
bool FindSwingFromLabels(SwingPt &h1, SwingPt &h2, SwingPt &l1, SwingPt &l2)
  {
   h1.t=0; h2.t=0; l1.t=0; l2.t=0;
   int total = ObjectsTotal(0);
   for(int i = 0; i < total; i++)
     {
      string nm = ObjectName(0, i);
      if(StringFind(nm, InpHHLLPrefix) != 0) continue;
      string   txt = ObjectGetString(0,  nm, OBJPROP_TEXT);
      datetime t   = (datetime)ObjectGetInteger(0, nm, OBJPROP_TIME,  0);
      double   p   = ObjectGetDouble(0,  nm, OBJPROP_PRICE, 0);
      if(t == 0 || p == 0) continue;

      if(txt == "HH" || txt == "LH")
        {
         if(t > h1.t) { h2=h1; h1.t=t; h1.price=p; h1.label=txt; }
         else if(t > h2.t && t != h1.t) { h2.t=t; h2.price=p; h2.label=txt; }
        }
      else if(txt == "HL" || txt == "LL")
        {
         if(t > l1.t) { l2=l1; l1.t=t; l1.price=p; l1.label=txt; }
         else if(t > l2.t && t != l1.t) { l2.t=t; l2.price=p; l2.label=txt; }
        }
     }
   return (h1.t > 0 && h2.t > 0 && l1.t > 0 && l2.t > 0);
  }

//+------------------------------------------------------------------+
//| คำนวณ swing ด้วย CopyRates (สำหรับ TF ที่ไม่ใช่ chart ปัจจุบัน) |
//+------------------------------------------------------------------+
bool FindSwingFromRates(ENUM_TIMEFRAMES period,
                        SwingPt &h1, SwingPt &h2, SwingPt &l1, SwingPt &l2)
  {
   h1.t=0; h2.t=0; l1.t=0; l2.t=0;
   MqlRates rates[];
   int need   = InpLookback + InpPivotLeft + InpPivotRight + 10;
   int copied = CopyRates(_Symbol, period, 0, need, rates);
   if(copied < InpPivotLeft + InpPivotRight + 10) return false;
   int total = ArraySize(rates);
   ZZPt zz[]; ArrayResize(zz, total);
   int zz_n = BuildZZ(rates, total, zz, total, InpPivotLeft, InpPivotRight);
   if(zz_n < 5) return false;

   bool h1f=false, h2f=false, l1f=false, l2f=false;
   for(int k = zz_n-1; k >= 4; k--)
     {
      if(h2f && l2f) break;
      string lbl = ClassifyPt(zz, k);
      if(lbl == "") continue;
      if((lbl=="HH"||lbl=="LH") && !h2f)
        {
         if(!h1f) { h1.t=zz[k].t; h1.price=zz[k].price; h1.label=lbl; h1f=true; }
         else     { h2.t=zz[k].t; h2.price=zz[k].price; h2.label=lbl; h2f=true; }
        }
      if((lbl=="HL"||lbl=="LL") && !l2f)
        {
         if(!l1f) { l1.t=zz[k].t; l1.price=zz[k].price; l1.label=lbl; l1f=true; }
         else     { l2.t=zz[k].t; l2.price=zz[k].price; l2.label=lbl; l2f=true; }
        }
     }
   return (h1f && h2f && l1f && l2f);
  }

//+------------------------------------------------------------------+
void SetTrend(TFInfo &info)
  {
   if(info.h1.t == 0 || info.l1.t == 0)
     { info.trend="UNKNOWN"; info.strength="-"; return; }
   if(info.h1.label=="HH" && info.l1.label=="HL")
     { info.trend="BULL";    info.strength="strong"; }
   else if(info.h1.label=="LH" && info.l1.label=="LL")
     { info.trend="BEAR";    info.strength="strong"; }
   else
     { info.trend="SIDEWAY"; info.strength="weak"; }
  }

//+------------------------------------------------------------------+
color PickColor(const string trend)
  {
   if(trend=="BULL") return InpBullColor;
   if(trend=="BEAR") return InpBearColor;
   return InpSidewayColor;
  }
ENUM_LINE_STYLE PickStyle(const string s) { return s=="strong"?STYLE_SOLID:STYLE_DASH; }
int             PickWidth(const string s) { return s=="strong"?InpStrongWidth:InpWeakWidth; }

//+------------------------------------------------------------------+
void DrawTrend(const string name,
               datetime t1, double p1, datetime t2, double p2,
               color clr, ENUM_LINE_STYLE style, int width,
               const string label)
  {
   string lbl_name = name + "_lbl";
   if(t1<=0||t2<=0||p1<=0||p2<=0||t1==t2)
     { ObjectDelete(0,name); ObjectDelete(0,lbl_name); return; }
   if(ObjectFind(0,name)<0) ObjectCreate(0,name,OBJ_TREND,0,t1,p1,t2,p2);
   ObjectSetInteger(0,name,OBJPROP_TIME, 0,t1); ObjectSetDouble(0,name,OBJPROP_PRICE,0,p1);
   ObjectSetInteger(0,name,OBJPROP_TIME, 1,t2); ObjectSetDouble(0,name,OBJPROP_PRICE,1,p2);
   ObjectSetInteger(0,name,OBJPROP_COLOR,clr);  ObjectSetInteger(0,name,OBJPROP_STYLE,style);
   ObjectSetInteger(0,name,OBJPROP_WIDTH,width);
   ObjectSetInteger(0,name,OBJPROP_RAY_RIGHT,true); ObjectSetInteger(0,name,OBJPROP_RAY_LEFT,false);
   ObjectSetInteger(0,name,OBJPROP_BACK,true);
   ObjectSetInteger(0,name,OBJPROP_SELECTABLE,false); ObjectSetInteger(0,name,OBJPROP_HIDDEN,true);
   ObjectSetString (0,name,OBJPROP_TEXT,label);
   if(InpShowLabels)
     {
      datetime last_bar=(datetime)SeriesInfoInteger(_Symbol,_Period,SERIES_LASTBAR_DATE);
      datetime anchor=last_bar+PeriodSeconds(_Period)*3;
      double slope=(p2-p1)/(double)(t2-t1);
      double proj=p2+slope*(double)(anchor-t2);
      if(ObjectFind(0,lbl_name)<0) ObjectCreate(0,lbl_name,OBJ_TEXT,0,anchor,proj);
      ObjectSetInteger(0,lbl_name,OBJPROP_TIME,anchor); ObjectSetDouble(0,lbl_name,OBJPROP_PRICE,proj);
      ObjectSetString (0,lbl_name,OBJPROP_TEXT,label);  ObjectSetInteger(0,lbl_name,OBJPROP_COLOR,clr);
      ObjectSetInteger(0,lbl_name,OBJPROP_FONTSIZE,InpLabelFontSize);
      ObjectSetInteger(0,lbl_name,OBJPROP_ANCHOR,ANCHOR_LEFT);
      ObjectSetInteger(0,lbl_name,OBJPROP_SELECTABLE,false); ObjectSetInteger(0,lbl_name,OBJPROP_HIDDEN,true);
     }
   else ObjectDelete(0,lbl_name);
  }

//+------------------------------------------------------------------+
void DrawPanelLabel(const string name, const string text,
                    int x, int y, color clr,
                    ENUM_ANCHOR_POINT anchor=ANCHOR_RIGHT_LOWER)
  {
   if(ObjectFind(0,name)<0) ObjectCreate(0,name,OBJ_LABEL,0,0,0);
   ObjectSetInteger(0,name,OBJPROP_CORNER,    CORNER_RIGHT_LOWER);
   ObjectSetInteger(0,name,OBJPROP_ANCHOR,    anchor);
   ObjectSetInteger(0,name,OBJPROP_XDISTANCE, x);
   ObjectSetInteger(0,name,OBJPROP_YDISTANCE, y);
   ObjectSetString (0,name,OBJPROP_TEXT,      text);
   ObjectSetString (0,name,OBJPROP_FONT,      InpPanelFont);
   ObjectSetInteger(0,name,OBJPROP_FONTSIZE,  InpPanelFontSize);
   ObjectSetInteger(0,name,OBJPROP_COLOR,     clr);
   ObjectSetInteger(0,name,OBJPROP_SELECTABLE,false);
   ObjectSetInteger(0,name,OBJPROP_HIDDEN,    true);
   ObjectSetInteger(0,name,OBJPROP_BACK,      false);
  }

void DrawPanel(TFInfo &tfs[])
  {
   if(!InpShowPanel) return;
   int count=ArraySize(tfs);
   if(count==0) return;
   int lh=InpPanelFontSize+6;
   int x_ic=InpPanelXOffset;
   int x_tf=InpPanelXOffset+InpPanelFontSize*8;

   DrawPanelLabel(g_prefix+"PANEL_hdr","TREND FILTER",
                  x_tf,InpPanelYOffset+count*lh,InpPanelHeaderColor,ANCHOR_LEFT_LOWER);
   for(int k=0; k<count; k++)
     {
      color clr=PickColor(tfs[k].trend);
      string icon;
      if(tfs[k].trend=="BULL")    icon=(tfs[k].strength=="strong")?"🟢🟢":"🟢";
      else if(tfs[k].trend=="BEAR") icon=(tfs[k].strength=="strong")?"🔴🔴":"🔴";
      else if(tfs[k].trend=="SIDEWAY") icon="⚪";
      else icon="⚫";
      int y=InpPanelYOffset+(count-1-k)*lh;
      DrawPanelLabel(g_prefix+"PANEL_"+IntegerToString(k)+"_tf",
                     tfs[k].name,x_tf,y,clr,ANCHOR_LEFT_LOWER);
      DrawPanelLabel(g_prefix+"PANEL_"+IntegerToString(k)+"_ic",
                     icon,x_ic,y,clr,ANCHOR_RIGHT_LOWER);
     }
  }

string PeriodName(ENUM_TIMEFRAMES p)
  {
   switch(p)
     {
      case PERIOD_M1:  return "M1";  case PERIOD_M5:  return "M5";
      case PERIOD_M15: return "M15"; case PERIOD_M30: return "M30";
      case PERIOD_H1:  return "H1";  case PERIOD_H4:  return "H4";
      case PERIOD_H12: return "H12"; case PERIOD_D1:  return "D1";
     }
   return "??";
  }

//+------------------------------------------------------------------+
void RefreshLines()
  {
   ENUM_TIMEFRAMES all_periods[] = {PERIOD_M1,PERIOD_M5,PERIOD_M15,PERIOD_M30,
                                    PERIOD_H1,PERIOD_H4,PERIOD_H12,PERIOD_D1};
   bool all_active[]             = {InpShowM1,InpShowM5,InpShowM15,InpShowM30,
                                    InpShowH1,InpShowH4,InpShowH12,InpShowD1};

   ENUM_TIMEFRAMES chart_period = (ENUM_TIMEFRAMES)_Period;

   TFInfo tfs[];
   ArrayResize(tfs, 0);
   for(int i = 0; i < ArraySize(all_periods); i++)
     {
      if(!all_active[i]) continue;
      int sz=ArraySize(tfs); ArrayResize(tfs,sz+1);
      tfs[sz].period=all_periods[i];
      tfs[sz].name=PeriodName(all_periods[i]);
      tfs[sz].ok=false; tfs[sz].trend="UNKNOWN"; tfs[sz].strength="-";

      if(all_periods[i] == chart_period)
        {
         // ── current chart TF: อ่านจาก HHLLStrategy labels ──
         tfs[sz].ok = FindSwingFromLabels(tfs[sz].h1, tfs[sz].h2,
                                          tfs[sz].l1, tfs[sz].l2);
        }
      else
        {
         // ── TF อื่น: คำนวณเองด้วย CopyRates + BuildZZ ──
         tfs[sz].ok = FindSwingFromRates(all_periods[i],
                                         tfs[sz].h1, tfs[sz].h2,
                                         tfs[sz].l1, tfs[sz].l2);
        }
      SetTrend(tfs[sz]);
     }

   // Signature check
   int count=ArraySize(tfs);
   string sig="";
   for(int i=0; i<count; i++)
      sig+=StringFormat("%s:%s:%s|%d|%d||",
                        tfs[i].name,tfs[i].trend,tfs[i].strength,
                        (long)tfs[i].h1.t,(long)tfs[i].l1.t);
   if(sig==g_last_sig) return;
   g_last_sig=sig;

   ObjectsDeleteAll(0, g_prefix);

   // ── เส้น: เฉพาะ chart TF (จาก HHLLStrategy labels) ──
   for(int i=0; i<count; i++)
     {
      if(tfs[i].period != chart_period) continue;
      if(!tfs[i].ok || tfs[i].trend=="UNKNOWN") continue;
      color           clr   = PickColor(tfs[i].trend);
      ENUM_LINE_STYLE style = PickStyle(tfs[i].strength);
      int             width = PickWidth(tfs[i].strength);
      string kind=(tfs[i].trend=="BULL")?"Bull":(tfs[i].trend=="BEAR")?"Bear":"Range";
      DrawTrend(g_prefix+"RES",
                tfs[i].h2.t,tfs[i].h2.price,tfs[i].h1.t,tfs[i].h1.price,
                clr,style,width,
                StringFormat("[%s] %s-%s resistance",tfs[i].name,kind,tfs[i].strength));
      DrawTrend(g_prefix+"SUP",
                tfs[i].l2.t,tfs[i].l2.price,tfs[i].l1.t,tfs[i].l1.price,
                clr,style,width,
                StringFormat("[%s] %s-%s support",tfs[i].name,kind,tfs[i].strength));
      break;
     }

   // ── Panel: ทุก TF ──
   DrawPanel(tfs);
   Comment(""); ChartRedraw();
  }

//+------------------------------------------------------------------+
int OnInit()
  {
   EventSetTimer(MathMax(1,InpRefreshSec));
   RefreshLines();
   return INIT_SUCCEEDED;
  }

void OnDeinit(const int reason)
  {
   EventKillTimer();
   ObjectsDeleteAll(0,g_prefix);
   Comment(""); ChartRedraw();
  }

void OnTimer() { RefreshLines(); }

int OnCalculate(const int rates_total,const int prev_calculated,
                const datetime &time[],const double &open[],
                const double &high[],const double &low[],
                const double &close[],const long &tick_volume[],
                const long &volume[],const int &spread[])
  { return rates_total; }

void OnChartEvent(const int id,const long &lparam,
                  const double &dparam,const string &sparam)
  { if(id==CHARTEVENT_CHART_CHANGE) RefreshLines(); }
//+------------------------------------------------------------------+
