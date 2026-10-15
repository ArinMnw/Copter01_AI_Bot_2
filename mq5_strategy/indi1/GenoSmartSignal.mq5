//+------------------------------------------------------------------+
//|                                          GenoSmartSignal.mq5      |
//|  Indicator — ported จาก Pine v5 "Geno Smart signal V2.3 Update    |
//|  Orderblocks"                                                     |
//|                                                                   |
//|  ส่วนประกอบ: Smart Trail (+Fib fill) / ZigZag HH-LL /              |
//|  Follow Line (BB+ATR) Buy/Sell / Follow Line MA-type Smart Buy/    |
//|  Sell / Kernel Regression / Auto Lot Calculator (กล่อง Risk/Target |
//|  + ตาราง) / Orderblocks (Fractal + FVG)                            |
//|                                                                   |
//|  ข้อแตกต่างจาก Pine ต้นฉบับ:                                        |
//|  1) ไม่ repaint — ประมวลผลเฉพาะแท่งที่ปิดสนิทแล้ว แท่งที่กำลังวิ่ง     |
//|     จะไม่มีสัญญาณ/เส้น (Pine จะ repaint ตามราคาสด)                  |
//|  2) Follow Line MA-type รองรับเฉพาะ "Use Current Chart Resolution" |
//|     (ไม่มี request.security ข้าม TF)                                |
//|  3) ตัดส่วน Support/Resistance (enableSR ปิดเป็น default ใน Pine)   |
//|     และ Parabolic SAR (ไม่ได้แสดงผล) ออก                            |
//|  4) ประมวลผลย้อนหลัง InpCalcBars แท่งเท่านั้น (กันช้า) — state ของ    |
//|     OB/ZigZag จึงเริ่มนับจากแท่งนั้น                                 |
//|  5) ตาราง Pine -> OBJ_LABEL มุมขวาบน, Volume ของ VWMA = tick volume |
//+------------------------------------------------------------------+
#property copyright "Copter01 AI Bot"
#property link      ""
#property version   "1.00"
#property indicator_chart_window
#property indicator_buffers 20
#property indicator_plots   11

#define PFX "GENO_"

//--- enums
enum ENUM_G_TRAIL   { G_TRAIL_MOD = 0,   // modified
                      G_TRAIL_UNMOD = 1  // unmodified
                    };
enum ENUM_G_LBL     { G_LBL_HHLL = 0,    // HHLL
                      G_LBL_HL = 1       // HL
                    };
enum ENUM_G_NAME    { G_NAME_SHORT = 0,  // Short
                      G_NAME_LONG = 1    // Long
                    };
enum ENUM_G_MA      { G_MA_RMA, G_MA_SMA, G_MA_EMA, G_MA_WMA, G_MA_VWMA, G_MA_SMMA,
                      G_MA_KMA, G_MA_TMA, G_MA_HULL, G_MA_DEMA, G_MA_TEMA, G_MA_CTI };
enum ENUM_G_KFILT   { G_K_NONE = 0,      // No Filter
                      G_K_SMOOTH = 1,    // Smooth
                      G_K_ZLAG = 2       // Zero Lag
                    };
enum ENUM_G_KTYPE   { G_K_RQ = 0,        // Rational Quadratic
                      G_K_GAUSS = 1,     // Gaussian
                      G_K_PERIODIC = 2,  // Periodic
                      G_K_LOCPER = 3     // Locally Periodic
                    };
enum ENUM_G_FRAC    { G_FRAC_3 = 3,      // 3
                      G_FRAC_5 = 5       // 5
                    };
enum ENUM_G_OBTYPE  { G_OB_CLOSE = 0,    // Close
                      G_OB_HL = 1        // HL
                    };
enum ENUM_G_OBH     { G_OBH_BODY = 0,    // Body
                      G_OBH_WICK = 1     // Wick
                    };

//--- inputs
input group "=== Smart Trail ==="
input bool           InpShowSmartTrail = true;      // Smart Trail
input ENUM_G_TRAIL   InpTrailType      = G_TRAIL_MOD; // Trail type
input int            InpATRPeriod      = 200;       // ATR Period
input double         InpATRFactor      = 4.2;       // ATR Factor
input int            InpSmoothing      = 4;         // Smoothing

input group "=== Trade / Lot Calculator ==="
input string         InpAccCur         = "USD";     // Account Currency
input int            InpQty            = 100;       // Units/Lot (XAUUSD = 100)
input double         InpBal            = 10000.0;   // Balance
input double         InpRiskPct        = 1.0;       // Risk %
input double         InpRR             = 2.5;       // R:R
input int            InpSLBufTicks     = 100;       // SL buffer (ticks)
input int            InpBoxExtend      = 10;        // Box Length (bars)
input color          InpRiskBoxCol     = C'239,83,80';  // Risk Zone
input color          InpTargetBoxCol   = C'38,166,154'; // Target Zone
input int            InpBoxAlpha       = 60;        // Box alpha (0-255)
input bool           InpShowEntry      = true;      // Show Entry Line
input bool           InpShowDash       = true;      // Show table
input int            InpDashY          = 40;        // Table Y offset

input group "=== ZigZag ==="
input int            InpZzLen          = 13;        // Level ZigZag
input color          InpColorUp        = C'0,250,75';  // Trend Color (High)
input color          InpColorDn        = C'202,70,70'; // Trend Color (Low)
input bool           InpShowLabel      = true;      // Label
input bool           InpShowLine       = true;      // Line
input ENUM_G_LBL     InpDisplayLabel   = G_LBL_HHLL; // Label text
input ENUM_G_NAME    InpNameHL         = G_NAME_SHORT; // Label name
input int            InpZzFont         = 9;         // Label font size
input ENUM_LINE_STYLE InpZzStyle       = STYLE_DASH; // Line style
input int            InpZzWidth        = 1;         // Line width

input group "=== Follow Line (BB + ATR) ==="
input int            InpBB1Period      = 21;        // BB Period
input double         InpBB1Dev         = 1.0;       // BB Deviations
input bool           InpUseATR1        = true;      // ATR Filter
input int            InpATR1           = 5;         // ATR Period
input bool           InpHide1          = false;     // Hide Labels

input group "=== Follow Line (MA type) ==="
input ENUM_G_MA      InpMAType         = G_MA_EMA;  // Type of MA
input int            InpMALen          = 21;        // Period
input double         InpBB2Dev         = 1.0;       // Deviations
input int            InpATR2           = 5;         // ATR Period
input bool           InpHide2          = false;     // Hide Labels

input group "=== Kernel Regression ==="
input ENUM_G_KFILT   InpKFilter        = G_K_SMOOTH; // Filter
input ENUM_G_KTYPE   InpKType          = G_K_RQ;    // Kernel type
input int            InpKH             = 8;         // Lookback Window
input double         InpKR             = 1.0;       // Weighting
input int            InpKX             = 20;        // Level
input int            InpKLag           = 2;         // Lag

input group "=== Orderblocks ==="
input bool           InpShowFractals   = false;     // Show Fractal Points
input ENUM_G_FRAC    InpFractal        = G_FRAC_3;  // Filter 3/5 bar fractal
input ENUM_G_OBTYPE  InpObType         = G_OB_CLOSE; // Find OB after fractal break of
input bool           InpFilterFvg      = true;      // Only OB that follow with FVG
input int            InpFvgDist        = 1;         // Max bars between OB and FVG
input ENUM_G_OBH     InpObHeight       = G_OBH_WICK; // Line Height
input bool           InpDelLines       = true;      // Delete lines after fill
input ENUM_LINE_STYLE InpObStyle       = STYLE_SOLID; // OB Lines style
input int            InpObLen          = 100;       // Length of OB lines (bars)
input int            InpObWidth        = 2;         // OB Lines Width
input color          InpBearCol        = clrRed;    // Bear OB Line color
input color          InpBullCol        = clrBlue;   // Bull OB Line color

input group "=== General ==="
input int            InpCalcBars       = 5000;      // Bars to calculate (0 = all)
input int            InpDrawBars       = 1500;      // Bars to draw ZigZag/Fractal objects
input bool           InpAlerts         = false;     // Alert on new signal

//--- buffers
double bFillLA[], bFillLB[], bFillSA[], bFillSB[];
double bTrail[], bTrailC[];
double bFl1[], bFl1C[];
double bBuy1[], bSell1[];
double bFl2[], bFl2C[];
double bBuy2[], bSell2[];
double bKer[], bKerC[];
double bEntry[];
double bSwL[], bSwH[];  // swing low/high ล่าสุดของ ZigZag (ไม่วาด ใช้ให้ EA อ่าน)
double bSL[];     // SL ของไม้ล่าสุด (ไม่วาด ใช้ให้ EA อ่าน)

//--- internal series (index k = bar - g_base, closed bars only)
double o_[], h_[], l_[], c_[], v_[];
datetime tm_[];
double rng_[], wild_[], tUp_[], tDn_[], trend_[], trail_[], ex_[], f3_[];
double tr_[], atr1_[], atr8_[], atr2_[];
double tl1_[], it1_[], tl2_[], it2_[];
double ma_[], t1_[], t2_[], t3_[], t4_[], t5_[], t6_[];
double yd_[], ks_[], kw_[];

double G_NAN;
int    g_base = 0, g_done = 0, g_N = 0, g_drawFrom = 0;
bool   g_live = false;
datetime g_lastTime = 0;

//--- zigzag state
int      g_dir = 0, g_zsz = 0, g_zzSeq = 0;
int      zx[4];
double   zy[4];
bool     zhi[4];
string   g_lastZL = "", g_lastZT = "";
double   g_lsh, g_lsl;

//--- lot calc state
double   g_p1, g_p2;
int      g_entryK = -1;

//--- fractals / orderblocks
double   frHiV[], frLoV[];
datetime frHiT[], frLoT[];
struct OBLine { datetime t1, t2; double y1, y2; bool bear; bool dead; };
OBLine   g_ob[];

//+------------------------------------------------------------------+
//| helpers                                                           |
//+------------------------------------------------------------------+
bool   V(const double x) { return MathIsValidNumber(x); }
double Nz(const double x) { return V(x) ? x : 0.0; }
double B(const double x) { return V(x) ? x : EMPTY_VALUE; }
double Mx(const double a, const double b) { if(!V(a) || !V(b)) return G_NAN; return a > b ? a : b; }
double Mn(const double a, const double b) { if(!V(a) || !V(b)) return G_NAN; return a < b ? a : b; }

double Sma(const double &a[], const int k, const int len)
{
   if(len < 1 || k < len - 1) return G_NAN;
   double s = 0;
   for(int j = 0; j < len; j++) s += a[k - j];
   return s / len;
}

double Wma(const double &a[], const int k, const int len)
{
   if(len < 1 || k < len - 1) return G_NAN;
   double s = 0;
   for(int j = 0; j < len; j++) s += a[k - j] * (len - j);
   return s / (len * (len + 1) / 2.0);
}

double Stdev(const double &a[], const int k, const int len)
{
   if(k < len - 1) return G_NAN;
   double m = Sma(a, k, len), s = 0;
   for(int j = 0; j < len; j++) s += (a[k - j] - m) * (a[k - j] - m);
   return MathSqrt(s / len);
}

void Ema(const double &a[], double &out[], const int k, const int len)
{
   double al = 2.0 / (len + 1);
   if(k == 0 || !V(out[k - 1])) out[k] = a[k];
   else out[k] = al * a[k] + (1 - al) * out[k - 1];
}

void Rma(const double &a[], double &out[], const int k, const int len)
{
   double al = 1.0 / len;
   if(k == 0 || !V(out[k - 1])) out[k] = Sma(a, k, len);
   else out[k] = al * a[k] + (1 - al) * out[k - 1];
}

//+------------------------------------------------------------------+
//| MA types (Follow Line #2)                                         |
//+------------------------------------------------------------------+
void CalcMA(const int k)
{
   int L = InpMALen;
   double s = c_[k], r = G_NAN;
   switch(InpMAType)
   {
      case G_MA_RMA:  Rma(c_, t1_, k, L); r = t1_[k]; break;
      case G_MA_SMA:  r = Sma(c_, k, L); break;
      case G_MA_EMA:  Ema(c_, t1_, k, L); r = t1_[k]; break;
      case G_MA_WMA:  r = Wma(c_, k, L); break;
      case G_MA_VWMA:
      {
         if(k >= L - 1)
         {
            double sv = 0, sw = 0;
            for(int j = 0; j < L; j++) { sv += c_[k - j] * v_[k - j]; sw += v_[k - j]; }
            r = (sw != 0) ? sv / sw : G_NAN;
         }
         break;
      }
      case G_MA_SMMA:
         if(k == 0 || !V(t1_[k - 1])) t1_[k] = Sma(c_, k, L);
         else t1_[k] = (t1_[k - 1] * (L - 1) + s) / L;
         r = t1_[k];
         break;
      case G_MA_KMA:
      {
         t2_[k] = (k > 0) ? MathAbs(s - c_[k - 1]) : G_NAN;           // xvnoise
         double nsig = (k >= L) ? MathAbs(s - c_[k - L]) : G_NAN;
         double nnoise = 0;
         if(k >= L) { for(int j = 0; j < L; j++) nnoise += t2_[k - j]; } else nnoise = G_NAN;
         double ef = (nnoise != 0) ? nsig / nnoise : 0;
         double nsm = MathPow(ef * (0.666 - 0.0645) + 0.0645, 2);
         double prev = (k > 0) ? Nz(t1_[k - 1]) : 0.0;
         t1_[k] = prev + nsm * (s - prev);
         r = t1_[k];
         break;
      }
      case G_MA_TMA:  t1_[k] = Sma(c_, k, L); r = Sma(t1_, k, L); break;
      case G_MA_HULL:
      {
         double a = Wma(c_, k, (int)(L / 2)), b = Wma(c_, k, L);
         t1_[k] = 2 * a - b;
         r = Wma(t1_, k, (int)MathRound(MathSqrt(L)));
         break;
      }
      case G_MA_DEMA: Ema(c_, t1_, k, L); Ema(t1_, t2_, k, L); r = 2 * t1_[k] - t2_[k]; break;
      case G_MA_TEMA:
         Ema(c_, t1_, k, L); Ema(t1_, t2_, k, L); Ema(t2_, t3_, k, L);
         r = 3 * t1_[k] - 3 * t2_[k] + t3_[k];
         break;
      case G_MA_CTI:
      {
         // cd = 0 ตาม Pine -> bfr = i3 ของ EMA ซ้อน 6 ชั้น (เริ่มจาก 0 ไม่ seed)
         double di = (L - 1.0) / 2.0 + 1.0, c1 = 2.0 / (di + 1.0), c2 = 1.0 - c1;
         t1_[k] = c1 * s + c2 * (k > 0 ? Nz(t1_[k - 1]) : 0);
         t2_[k] = c1 * t1_[k] + c2 * (k > 0 ? Nz(t2_[k - 1]) : 0);
         t3_[k] = c1 * t2_[k] + c2 * (k > 0 ? Nz(t3_[k - 1]) : 0);
         t4_[k] = c1 * t3_[k] + c2 * (k > 0 ? Nz(t4_[k - 1]) : 0);
         t5_[k] = c1 * t4_[k] + c2 * (k > 0 ? Nz(t5_[k - 1]) : 0);
         t6_[k] = c1 * t5_[k] + c2 * (k > 0 ? Nz(t6_[k - 1]) : 0);
         r = t3_[k];
         break;
      }
   }
   ma_[k] = r;
}

//+------------------------------------------------------------------+
//| Kernel weights                                                    |
//+------------------------------------------------------------------+
void BuildKernelWeights()
{
   int n = InpKX + 2;      // Pine: for i = 0 to 1 + startAtBar
   ArrayResize(kw_, n);
   for(int i = 0; i < n; i++)
   {
      double w = 0, lb = InpKH, per = InpKLag;
      switch(InpKType)
      {
         case G_K_RQ:
            w = MathPow(1 + (MathPow(i, 2) / (MathPow(lb, 2) * 2 * InpKR)), -InpKR); break;
         case G_K_GAUSS:
            lb = InpKH - InpKLag;
            w = MathExp(-MathPow(i, 2) / (2 * MathPow(lb, 2))); break;
         case G_K_PERIODIC:
            w = MathExp(-2 * MathPow(MathSin(M_PI * i / per), 2) / MathPow(lb, 2)); break;
         case G_K_LOCPER:
            w = MathExp(-2 * MathPow(MathSin(M_PI * i / per), 2) / MathPow(lb, 2))
                * MathExp(-MathPow(i, 2) / (2 * MathPow(lb, 2))); break;
      }
      kw_[i] = w;
   }
}

void KernelStep(const int k)
{
   int n = ArraySize(kw_);
   yd_[k] = G_NAN; ks_[k] = G_NAN;
   if(k < n - 1) return;
   double sw = 0, sy = 0;
   for(int j = 0; j < n; j++) { sy += kw_[j] * c_[k - j]; sw += kw_[j]; }
   yd_[k] = sy / sw;
   if(k < 2 * (n - 1)) return;
   double sy2 = 0;
   for(int j = 0; j < n; j++) sy2 += kw_[j] * yd_[k - j];
   double yd2 = sy2 / sw;
   switch(InpKFilter)
   {
      case G_K_NONE:   ks_[k] = yd_[k]; break;
      case G_K_SMOOTH: ks_[k] = yd2; break;
      case G_K_ZLAG:   ks_[k] = yd_[k] + (yd_[k] - yd2); break;
   }
}

//+------------------------------------------------------------------+
//| ZigZag                                                            |
//+------------------------------------------------------------------+
void ZigStep(const int k)
{
   bool kh = false, kl = false;
   if(k >= InpZzLen - 1)
   {
      double mx = h_[k], mn = l_[k];
      for(int j = 1; j < InpZzLen; j++) { if(h_[k - j] > mx) mx = h_[k - j]; if(l_[k - j] < mn) mn = l_[k - j]; }
      kh = (h_[k] >= mx);
      kl = (l_[k] <= mn);
   }
   int prevDir = g_dir;
   if(kh && !kl) g_dir = 1;
   else if(kl && !kh) g_dir = -1;
   bool dirChanged = (g_dir != prevDir);

   if(kh || kl)
   {
      int ox0 = (g_zsz > 0) ? zx[0] : -1, ox1 = (g_zsz > 1) ? zx[1] : -1;
      double oy0 = (g_zsz > 0) ? zy[0] : 0, oy1 = (g_zsz > 1) ? zy[1] : 0;

      bool isHi = (g_dir == 1);
      double ny = isHi ? h_[k] : l_[k];
      bool doPush = false;
      if(dirChanged || g_zsz == 0) doPush = true;
      else if((g_dir == 1 && ny > zy[0]) || (g_dir == -1 && ny < zy[0]))
      {
         zx[0] = k; zy[0] = ny; zhi[0] = isHi;
      }
      if(doPush)
      {
         for(int j = 3; j > 0; j--) { zx[j] = zx[j - 1]; zy[j] = zy[j - 1]; zhi[j] = zhi[j - 1]; }
         zx[0] = k; zy[0] = ny; zhi[0] = isHi;
         if(g_zsz < 4) g_zsz++;
      }

      if(g_zsz >= 3)
      {
         bool boolOr  = (zx[0] != ox0 || zy[0] != oy0);
         bool boolAnd = (zx[1] == ox1 && zy[1] == oy1);
         if(boolOr)
         {
            if(boolAnd)
            {
               if(g_lastZL != "") ObjectDelete(0, g_lastZL);
               if(g_lastZT != "") ObjectDelete(0, g_lastZT);
               g_lastZL = ""; g_lastZT = "";
            }
            if(k >= g_drawFrom)
            {
               color col = zhi[0] ? InpColorUp : InpColorDn;
               g_zzSeq++;
               ObjectDelete(0, PFX + "ZT_" + IntegerToString(g_zzSeq - 200));
               ObjectDelete(0, PFX + "ZN_" + IntegerToString(g_zzSeq - 200));
               if(InpShowLabel)
               {
                  bool lg = (InpNameHL == G_NAME_LONG);
                  string base = zhi[0] ? (lg ? "HIGH" : "H") : (lg ? "LOW" : "L");
                  string txt = base;
                  if(InpDisplayLabel == G_LBL_HHLL && g_zsz >= 4)
                  {
                     string hiS = lg ? "HIGHER\n" : "H", loS = lg ? "LOWER\n" : "L", ds;
                     if(g_dir == 1) ds = (zy[0] > zy[2]) ? hiS : loS;
                     else           ds = (zy[0] < zy[2]) ? loS : hiS;
                     txt = ds + base;
                  }
                  string nm = PFX + "ZT_" + IntegerToString(g_zzSeq);
                  ObjectCreate(0, nm, OBJ_TEXT, 0, tm_[zx[0]], zy[0]);
                  ObjectSetString(0, nm, OBJPROP_TEXT, txt);
                  ObjectSetInteger(0, nm, OBJPROP_COLOR, col);
                  ObjectSetInteger(0, nm, OBJPROP_FONTSIZE, InpZzFont);
                  ObjectSetInteger(0, nm, OBJPROP_ANCHOR, zhi[0] ? ANCHOR_LOWER : ANCHOR_UPPER);
                  ObjectSetInteger(0, nm, OBJPROP_SELECTABLE, false);
                  g_lastZT = nm;
               }
               if(InpShowLine)
               {
                  string nl = PFX + "ZN_" + IntegerToString(g_zzSeq);
                  ObjectCreate(0, nl, OBJ_TREND, 0, tm_[zx[1]], zy[1], tm_[zx[0]], zy[0]);
                  ObjectSetInteger(0, nl, OBJPROP_COLOR, col);
                  ObjectSetInteger(0, nl, OBJPROP_STYLE, InpZzStyle);
                  ObjectSetInteger(0, nl, OBJPROP_WIDTH, InpZzWidth);
                  ObjectSetInteger(0, nl, OBJPROP_RAY_RIGHT, false);
                  ObjectSetInteger(0, nl, OBJPROP_SELECTABLE, false);
                  g_lastZL = nl;
               }
            }
         }
      }
   }
   if(g_zsz >= 2)
   {
      if(zhi[0]) g_lsh = zy[0];
      else       g_lsl = zy[0];
   }
}

//+------------------------------------------------------------------+
//| Orderblocks                                                       |
//+------------------------------------------------------------------+
void PushD(double &a[], const double v) { int n = ArraySize(a); ArrayResize(a, n + 1); a[n] = v; }
void PushT(datetime &a[], const datetime v) { int n = ArraySize(a); ArrayResize(a, n + 1); a[n] = v; }

void AddOB(const int bi, const bool bear)
{
   OBLine ob;
   ob.t1 = tm_[bi];
   ob.t2 = (datetime)(ob.t1 + (long)PeriodSeconds() * InpObLen);
   ob.bear = bear;
   ob.dead = false;
   if(bear)
   {
      ob.y1 = h_[bi];
      ob.y2 = (InpObHeight == G_OBH_BODY) ? o_[bi] : l_[bi];
   }
   else
   {
      ob.y1 = l_[bi];
      ob.y2 = (InpObHeight == G_OBH_BODY) ? o_[bi] : h_[bi];
   }
   int n = ArraySize(g_ob);
   ArrayResize(g_ob, n + 1);
   g_ob[n] = ob;
}

void OrderblockStep(const int k)
{
   bool f3 = (InpFractal == G_FRAC_3);
   //--- fractal detection
   bool fh = false, fl = false;
   if(f3 && k >= 3)
   {
      fh = h_[k] < h_[k - 1] && (h_[k - 2] < h_[k - 1] || (h_[k - 2] == h_[k - 1] && h_[k - 3] < h_[k - 2]));
      fl = l_[k] > l_[k - 1] && (l_[k - 2] > l_[k - 1] || (l_[k - 2] == l_[k - 1] && l_[k - 3] > l_[k - 2]));
   }
   else if(!f3 && k >= 4)
   {
      fh = h_[k] < h_[k - 2] && h_[k - 1] < h_[k - 2] && h_[k - 3] < h_[k - 2] && h_[k - 4] < h_[k - 2];
      fl = l_[k] > l_[k - 2] && l_[k - 1] > l_[k - 2] && l_[k - 3] > l_[k - 2] && l_[k - 4] > l_[k - 2];
   }
   int off = f3 ? 1 : 2;
   if(fh) { PushD(frHiV, h_[k - off]); PushT(frHiT, tm_[k - off]); }
   if(fl) { PushD(frLoV, l_[k - off]); PushT(frLoT, tm_[k - off]); }
   if(InpShowFractals && k >= g_drawFrom && (fh || fl))
   {
      if(fh)
      {
         string n1 = PFX + "FH_" + IntegerToString((long)tm_[k - off]);
         ObjectCreate(0, n1, OBJ_ARROW, 0, tm_[k - off], h_[k - off]);
         ObjectSetInteger(0, n1, OBJPROP_ARROWCODE, 234);
         ObjectSetInteger(0, n1, OBJPROP_COLOR, clrRed);
         ObjectSetInteger(0, n1, OBJPROP_ANCHOR, ANCHOR_BOTTOM);
         ObjectSetInteger(0, n1, OBJPROP_SELECTABLE, false);
      }
      if(fl)
      {
         string n2 = PFX + "FL_" + IntegerToString((long)tm_[k - off]);
         ObjectCreate(0, n2, OBJ_ARROW, 0, tm_[k - off], l_[k - off]);
         ObjectSetInteger(0, n2, OBJPROP_ARROWCODE, 233);
         ObjectSetInteger(0, n2, OBJPROP_COLOR, clrBlue);
         ObjectSetInteger(0, n2, OBJPROP_ANCHOR, ANCHOR_TOP);
         ObjectSetInteger(0, n2, OBJPROP_SELECTABLE, false);
      }
   }

   //--- bearish loop (fractal lows broken -> last bullish candle = bear OB)
   for(int fi = ArraySize(frLoV) - 1; fi >= 0; fi--)
   {
      double ref = (InpObType == G_OB_CLOSE) ? c_[k] : l_[k];
      if(ref < frLoV[fi])
      {
         int idx = 0, gapIndex = 0;
         double mx = l_[k];
         for(int j = 0; j <= 500; j++)
         {
            int b = k - j;
            if(b < 0) break;
            bool bg = (b >= 2) && (c_[b - 1] < l_[b - 2]) && (h_[b] < l_[b - 2]);
            if(tm_[b] < frLoT[fi]) break;
            if(c_[b] > o_[b] && h_[b] > mx) { idx = j; mx = h_[b]; }
            if(bg && h_[b] > mx) gapIndex = j + 2;
         }
         bool okFvg = InpFilterFvg ? (gapIndex > 0 && idx - gapIndex >= 0 && idx - gapIndex <= InpFvgDist) : true;
         if(idx != 0 && okFvg) AddOB(k - idx, true);
         ArrayRemove(frLoV, fi, 1);
         ArrayRemove(frLoT, fi, 1);
      }
   }
   //--- bullish loop (fractal highs broken -> last bearish candle = bull OB)
   for(int fi = ArraySize(frHiV) - 1; fi >= 0; fi--)
   {
      double ref = (InpObType == G_OB_CLOSE) ? c_[k] : h_[k];
      if(ref > frHiV[fi])
      {
         int idx = 0, gapIndex = 0;
         double mn = l_[k];
         for(int j = 0; j <= 500; j++)
         {
            int b = k - j;
            if(b < 0) break;
            bool bg = (b >= 2) && (c_[b - 1] > h_[b - 2]) && (l_[b] > h_[b - 2]);
            if(tm_[b] < frHiT[fi]) break;
            if(c_[b] < o_[b] && l_[b] < mn) { idx = j; mn = l_[b]; }
            if(bg) gapIndex = j + 2;
         }
         bool okFvg = InpFilterFvg ? (gapIndex > 0 && idx - gapIndex >= 0 && idx - gapIndex <= InpFvgDist) : true;
         if(idx != 0 && okFvg) AddOB(k - idx, false);
         ArrayRemove(frHiV, fi, 1);
         ArrayRemove(frHiT, fi, 1);
      }
   }
   //--- mitigation
   for(int i = ArraySize(g_ob) - 1; i >= 0; i--)
   {
      if(g_ob[i].dead) continue;
      if(g_ob[i].bear) { if(h_[k] >= g_ob[i].y1 && h_[k] >= g_ob[i].y2) g_ob[i].dead = true; }
      else             { if(l_[k] <= g_ob[i].y1 && l_[k] <= g_ob[i].y2) g_ob[i].dead = true; }
   }
}

void DrawOB()
{
   ObjectsDeleteAll(0, PFX + "OB_");
   // compact: ทิ้งอันที่ตายแล้วถ้า delLines เปิด
   if(InpDelLines)
   {
      int w = 0, n = ArraySize(g_ob);
      for(int i = 0; i < n; i++) if(!g_ob[i].dead) g_ob[w++] = g_ob[i];
      ArrayResize(g_ob, w);
   }
   int n2 = ArraySize(g_ob), drawn = 0;
   for(int i = n2 - 1; i >= 0 && drawn < 100; i--)
   {
      OBLine ob = g_ob[i];
      color col = ob.bear ? InpBearCol : InpBullCol;
      for(int s = 0; s < 2; s++)
      {
         string nm = PFX + "OB_" + IntegerToString(i) + "_" + IntegerToString(s);
         double y = (s == 0) ? ob.y1 : ob.y2;
         ObjectCreate(0, nm, OBJ_TREND, 0, ob.t1, y, ob.t2, y);
         ObjectSetInteger(0, nm, OBJPROP_COLOR, col);
         ObjectSetInteger(0, nm, OBJPROP_STYLE, InpObStyle);
         ObjectSetInteger(0, nm, OBJPROP_WIDTH, InpObWidth);
         ObjectSetInteger(0, nm, OBJPROP_RAY_RIGHT, false);
         ObjectSetInteger(0, nm, OBJPROP_SELECTABLE, false);
      }
      drawn++;
   }
}

//+------------------------------------------------------------------+
//| Lot calculator drawing                                            |
//+------------------------------------------------------------------+
void Lbl(const string name, const string text, const int x, const int y, const color col)
{
   if(ObjectFind(0, name) < 0) ObjectCreate(0, name, OBJ_LABEL, 0, 0, 0);
   ObjectSetInteger(0, name, OBJPROP_CORNER, CORNER_RIGHT_UPPER);
   ObjectSetInteger(0, name, OBJPROP_ANCHOR, ANCHOR_RIGHT_UPPER);
   ObjectSetInteger(0, name, OBJPROP_XDISTANCE, x);
   ObjectSetInteger(0, name, OBJPROP_YDISTANCE, y);
   ObjectSetInteger(0, name, OBJPROP_COLOR, col);
   ObjectSetInteger(0, name, OBJPROP_FONTSIZE, 9);
   ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
   ObjectSetString(0, name, OBJPROP_FONT, "Consolas");
   ObjectSetString(0, name, OBJPROP_TEXT, text);
}

void DrawTrade()
{
   ObjectDelete(0, PFX + "RBOX");
   ObjectDelete(0, PFX + "TBOX");
   ObjectsDeleteAll(0, PFX + "TB_");
   if(!V(g_p1) || !V(g_p2) || g_entryK < 0) return;

   int digs = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   datetime t1 = tm_[g_entryK];
   datetime t2 = (datetime)(g_lastTime + (long)PeriodSeconds() * InpBoxExtend);
   double riskval = MathAbs(g_p1 - g_p2);
   double tv = (g_p1 > g_p2) ? g_p1 + riskval * MathAbs(InpRR) : g_p1 - riskval * MathAbs(InpRR);

   ObjectCreate(0, PFX + "RBOX", OBJ_RECTANGLE, 0, t1, g_p1, t2, g_p2);
   ObjectSetInteger(0, PFX + "RBOX", OBJPROP_COLOR, ColorToARGB(InpRiskBoxCol, (uchar)InpBoxAlpha));
   ObjectSetInteger(0, PFX + "RBOX", OBJPROP_FILL, true);
   ObjectSetInteger(0, PFX + "RBOX", OBJPROP_BACK, true);
   ObjectSetInteger(0, PFX + "RBOX", OBJPROP_SELECTABLE, false);
   ObjectCreate(0, PFX + "TBOX", OBJ_RECTANGLE, 0, t1, g_p1, t2, tv);
   ObjectSetInteger(0, PFX + "TBOX", OBJPROP_COLOR, ColorToARGB(InpTargetBoxCol, (uchar)InpBoxAlpha));
   ObjectSetInteger(0, PFX + "TBOX", OBJPROP_FILL, true);
   ObjectSetInteger(0, PFX + "TBOX", OBJPROP_BACK, true);
   ObjectSetInteger(0, PFX + "TBOX", OBJPROP_SELECTABLE, false);

   if(!InpShowDash) return;
   double risk = InpBal * MathAbs(InpRiskPct) / 100.0;
   double dp = (riskval > 0) ? risk / (riskval * InpQty) : 0;
   string prof = SymbolInfoString(_Symbol, SYMBOL_CURRENCY_PROFIT);
   if(prof != InpAccCur)
   {
      double vt = SymbolInfoDouble(InpAccCur + prof, SYMBOL_BID);
      if(vt > 0) dp *= vt;
   }
   double lots = NormalizeDouble(MathAbs(dp), 2);

   string nm[7] = {"Balance", "Risk", "$ Risk", "Entry", "Stop Loss", "Take Profit", "Lots"};
   string vl[7];
   vl[0] = DoubleToString(InpBal, 2) + " " + InpAccCur;
   vl[1] = DoubleToString(InpRiskPct, 2) + "%";
   vl[2] = DoubleToString(risk, 2);
   vl[3] = DoubleToString(g_p1, digs);
   vl[4] = DoubleToString(g_p2, digs);
   vl[5] = DoubleToString(tv, digs);
   vl[6] = DoubleToString(lots, 2);
   color vc[7] = {C'144,164,174', C'144,164,174', C'144,164,174', C'255,167,38', C'239,83,80', C'38,166,154', C'102,187,106'};
   for(int r = 0; r < 7; r++)
   {
      Lbl(PFX + "TB_N" + IntegerToString(r), nm[r], 140, InpDashY + r * 18, C'176,190,197');
      Lbl(PFX + "TB_V" + IntegerToString(r), vl[r], 10, InpDashY + r * 18, vc[r]);
   }
}

//+------------------------------------------------------------------+
void ResizeAll(const int n)
{
   ArrayResize(o_, n); ArrayResize(h_, n); ArrayResize(l_, n); ArrayResize(c_, n);
   ArrayResize(v_, n); ArrayResize(tm_, n);
   ArrayResize(rng_, n); ArrayResize(wild_, n); ArrayResize(tUp_, n); ArrayResize(tDn_, n);
   ArrayResize(trend_, n); ArrayResize(trail_, n); ArrayResize(ex_, n); ArrayResize(f3_, n);
   ArrayResize(tr_, n); ArrayResize(atr1_, n); ArrayResize(atr8_, n); ArrayResize(atr2_, n);
   ArrayResize(tl1_, n); ArrayResize(it1_, n); ArrayResize(tl2_, n); ArrayResize(it2_, n);
   ArrayResize(ma_, n); ArrayResize(t1_, n); ArrayResize(t2_, n); ArrayResize(t3_, n);
   ArrayResize(t4_, n); ArrayResize(t5_, n); ArrayResize(t6_, n);
   ArrayResize(yd_, n); ArrayResize(ks_, n);
}

void ResetState()
{
   g_done = 0; g_dir = 0; g_zsz = 0; g_zzSeq = 0;
   g_lastZL = ""; g_lastZT = "";
   g_lsh = G_NAN; g_lsl = G_NAN;
   g_p1 = G_NAN; g_p2 = G_NAN; g_entryK = -1;
   ArrayResize(frHiV, 0); ArrayResize(frLoV, 0);
   ArrayResize(frHiT, 0); ArrayResize(frLoT, 0);
   ArrayResize(g_ob, 0);
   ObjectsDeleteAll(0, PFX);
   ArrayInitialize(bFillLA, EMPTY_VALUE); ArrayInitialize(bFillLB, EMPTY_VALUE);
   ArrayInitialize(bFillSA, EMPTY_VALUE); ArrayInitialize(bFillSB, EMPTY_VALUE);
   ArrayInitialize(bTrail, EMPTY_VALUE);  ArrayInitialize(bFl1, EMPTY_VALUE);
   ArrayInitialize(bBuy1, EMPTY_VALUE);   ArrayInitialize(bSell1, EMPTY_VALUE);
   ArrayInitialize(bFl2, EMPTY_VALUE);    ArrayInitialize(bBuy2, EMPTY_VALUE);
   ArrayInitialize(bSell2, EMPTY_VALUE);  ArrayInitialize(bKer, EMPTY_VALUE);
   ArrayInitialize(bEntry, EMPTY_VALUE);
   ArrayInitialize(bSL, EMPTY_VALUE);
   ArrayInitialize(bSwL, EMPTY_VALUE); ArrayInitialize(bSwH, EMPTY_VALUE);
}

//+------------------------------------------------------------------+
//| one closed bar                                                    |
//+------------------------------------------------------------------+
void Step(const int k)
{
   int i = g_base + k;

   //=== true range / ATRs
   tr_[k] = (k == 0) ? h_[k] - l_[k]
            : MathMax(h_[k] - l_[k], MathMax(MathAbs(h_[k] - c_[k - 1]), MathAbs(l_[k] - c_[k - 1])));
   Rma(tr_, atr1_, k, InpATR1);
   Rma(tr_, atr8_, k, 8);
   Rma(tr_, atr2_, k, InpATR2);

   //=== Smart Trail
   rng_[k] = h_[k] - l_[k];
   if(k == 0)
   {
      wild_[k] = G_NAN; tUp_[k] = G_NAN; tDn_[k] = G_NAN;
      trend_[k] = 1; trail_[k] = G_NAN; ex_[k] = G_NAN; f3_[k] = G_NAN;
   }
   else
   {
      double smaR = (k >= InpATRPeriod - 1) ? Sma(rng_, k, InpATRPeriod) : 0.0;
      double hilo = MathMin(rng_[k], 1.5 * smaR);
      double hr = (l_[k] <= h_[k - 1]) ? h_[k] - c_[k - 1] : h_[k] - c_[k - 1] - 0.5 * (l_[k] - h_[k - 1]);
      double lr = (h_[k] >= l_[k - 1]) ? c_[k - 1] - l_[k] : c_[k - 1] - l_[k] - 0.5 * (l_[k - 1] - h_[k]);
      double trs = (InpTrailType == G_TRAIL_MOD) ? MathMax(hilo, MathMax(hr, lr)) : tr_[k];
      double pw = Nz(wild_[k - 1]);
      wild_[k] = pw + (trs - pw) / InpATRPeriod;
      double loss = InpATRFactor * wild_[k];
      double up = c_[k] - loss, dn = c_[k] + loss;
      tUp_[k] = (c_[k - 1] > tUp_[k - 1]) ? Mx(up, tUp_[k - 1]) : up;
      tDn_[k] = (c_[k - 1] < tDn_[k - 1]) ? Mn(dn, tDn_[k - 1]) : dn;
      trend_[k] = (c_[k] > tDn_[k - 1]) ? 1 : (c_[k] < tUp_[k - 1]) ? -1 : trend_[k - 1];
      trail_[k] = (trend_[k] == 1) ? tUp_[k] : tDn_[k];
      if(trend_[k - 1] <= 0 && trend_[k] > 0)       ex_[k] = h_[k];
      else if(trend_[k - 1] >= 0 && trend_[k] < 0)  ex_[k] = l_[k];
      else if(trend_[k] == 1)                       ex_[k] = Mx(ex_[k - 1], h_[k]);
      else                                          ex_[k] = Mn(ex_[k - 1], l_[k]);
      f3_[k] = ex_[k] + (trail_[k] - ex_[k]) * 88.6 / 100.0;
   }
   {
      double sU = Sma(trail_, k, InpSmoothing), sL = Sma(f3_, k, InpSmoothing);
      bool ok = InpShowSmartTrail && V(sU) && V(sL);
      bool lg = (trend_[k] == 1);
      bFillLA[i] = (ok && lg)  ? sU : EMPTY_VALUE;
      bFillLB[i] = (ok && lg)  ? sL : EMPTY_VALUE;
      bFillSA[i] = (ok && !lg) ? sU : EMPTY_VALUE;
      bFillSB[i] = (ok && !lg) ? sL : EMPTY_VALUE;
      bTrail[i]  = (InpShowSmartTrail && V(sU)) ? sU : EMPTY_VALUE;
      bTrailC[i] = lg ? 0 : 1;
   }

   //=== ZigZag (+ lastSwing)
   ZigStep(k);
   bSwL[i] = B(g_lsl);
   bSwH[i] = B(g_lsh);

   //=== Follow Line #1 (BB + ATR)
   {
      double m = Sma(c_, k, InpBB1Period), sd = Stdev(c_, k, InpBB1Period);
      double bu = m + sd * InpBB1Dev, bl = m - sd * InpBB1Dev;
      int sig = (c_[k] > bu) ? 1 : (c_[k] < bl) ? -1 : 0;
      double pv = (k > 0) ? tl1_[k - 1] : G_NAN, tl = G_NAN;
      if(sig == 1)       { tl = InpUseATR1 ? l_[k] - atr1_[k] : l_[k]; if(tl < pv) tl = pv; }
      else if(sig == -1) { tl = InpUseATR1 ? h_[k] + atr1_[k] : h_[k]; if(tl > pv) tl = pv; }
      else               tl = pv;
      tl1_[k] = tl;
      double it = (k > 0) ? it1_[k - 1] : G_NAN;
      if(tl > pv) it = 1;
      if(tl < pv) it = -1;
      it1_[k] = it;
      bool buy1 = (k > 0 && it1_[k - 1] == -1 && it == 1);
      bool sell1 = (k > 0 && it1_[k - 1] == 1 && it == -1);
      bFl1[i]  = B(tl);
      bFl1C[i] = (it > 0) ? 0 : 1;
      bBuy1[i]  = (buy1 && !InpHide1 && V(atr8_[k]))  ? tl - atr8_[k] : EMPTY_VALUE;
      bSell1[i] = (sell1 && !InpHide1 && V(atr8_[k])) ? tl + atr8_[k] : EMPTY_VALUE;
      if(g_live && InpAlerts && k == g_N - 1 && (buy1 || sell1))
         Alert(_Symbol, " ", EnumToString(Period()), (buy1 ? " buy1" : " sell1"));
   }

   //=== Follow Line #2 (MA type)
   bool buy2 = false, sell2 = false;
   {
      CalcMA(k);
      double sd = Stdev(c_, k, InpMALen);
      double bu = ma_[k] + sd * InpBB2Dev, bl = ma_[k] - sd * InpBB2Dev;
      int sig = (c_[k] > bu) ? 1 : (c_[k] < bl) ? -1 : 0;
      double v = atr2_[k];
      double pv = (k > 0) ? tl2_[k - 1] : G_NAN, tl = G_NAN;
      if(sig == 1)       { tl = l_[k] - v; if(tl < pv) tl = pv; }
      else if(sig == -1) { tl = h_[k] + v; if(tl > pv) tl = pv; }
      else               tl = pv;
      tl2_[k] = tl;
      double it = (k > 0) ? it2_[k - 1] : G_NAN;
      if(tl > pv) it = 1;
      if(tl < pv) it = -1;
      it2_[k] = it;
      buy2  = (k > 0 && it2_[k - 1] == -1 && it == 1);
      sell2 = (k > 0 && it2_[k - 1] == 1 && it == -1);
      bFl2[i]  = B(tl);
      bFl2C[i] = (it > 0) ? 0 : 1;
      bBuy2[i]  = (buy2 && !InpHide2 && V(v))  ? tl - v : EMPTY_VALUE;
      bSell2[i] = (sell2 && !InpHide2 && V(v)) ? tl + v : EMPTY_VALUE;
      if(g_live && InpAlerts && k == g_N - 1 && (buy2 || sell2))
         Alert(_Symbol, " ", EnumToString(Period()), (buy2 ? " Smart Buy" : " Smart Sell"));
   }

   //=== Kernel regression
   KernelStep(k);
   bKer[i]  = B(ks_[k]);
   bKerC[i] = (k > 0 && V(ks_[k]) && V(ks_[k - 1]) && ks_[k] > ks_[k - 1]) ? 0 : 1;

   //=== Auto lot calculator (entry/SL จาก Smart Buy/Sell + swing ล่าสุด)
   double slBuf = InpSLBufTicks * SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(buy2 && V(g_lsl))  { g_p1 = c_[k]; g_p2 = g_lsl - slBuf; g_entryK = k; }
   if(sell2 && V(g_lsh)) { g_p1 = c_[k]; g_p2 = g_lsh + slBuf; g_entryK = k; }
   bEntry[i] = (InpShowEntry && V(g_p1)) ? g_p1 : EMPTY_VALUE;
   bSL[i] = V(g_p2) ? g_p2 : EMPTY_VALUE;

   //=== Orderblocks
   OrderblockStep(k);
}

//+------------------------------------------------------------------+
int OnInit()
{
   G_NAN = MathSqrt(-1.0);

   SetIndexBuffer(0, bFillLA, INDICATOR_DATA);
   SetIndexBuffer(1, bFillLB, INDICATOR_DATA);
   SetIndexBuffer(2, bFillSA, INDICATOR_DATA);
   SetIndexBuffer(3, bFillSB, INDICATOR_DATA);
   SetIndexBuffer(4, bTrail,  INDICATOR_DATA);
   SetIndexBuffer(5, bTrailC, INDICATOR_COLOR_INDEX);
   SetIndexBuffer(6, bFl1,    INDICATOR_DATA);
   SetIndexBuffer(7, bFl1C,   INDICATOR_COLOR_INDEX);
   SetIndexBuffer(8, bBuy1,   INDICATOR_DATA);
   SetIndexBuffer(9, bSell1,  INDICATOR_DATA);
   SetIndexBuffer(10, bFl2,   INDICATOR_DATA);
   SetIndexBuffer(11, bFl2C,  INDICATOR_COLOR_INDEX);
   SetIndexBuffer(12, bBuy2,  INDICATOR_DATA);
   SetIndexBuffer(13, bSell2, INDICATOR_DATA);
   SetIndexBuffer(14, bKer,   INDICATOR_DATA);
   SetIndexBuffer(15, bKerC,  INDICATOR_COLOR_INDEX);
   SetIndexBuffer(16, bEntry, INDICATOR_DATA);
   SetIndexBuffer(17, bSL,    INDICATOR_CALCULATIONS);
   SetIndexBuffer(18, bSwL,   INDICATOR_CALCULATIONS);
   SetIndexBuffer(19, bSwH,   INDICATOR_CALCULATIONS);

   // plot 0: fill long, plot 1: fill short
   PlotIndexSetInteger(0, PLOT_DRAW_TYPE, DRAW_FILLING);
   PlotIndexSetInteger(0, PLOT_LINE_COLOR, 0, C'33,87,249');
   PlotIndexSetInteger(0, PLOT_LINE_COLOR, 1, C'33,87,249');
   PlotIndexSetString(0, PLOT_LABEL, "Trail Fill Long");
   PlotIndexSetInteger(1, PLOT_DRAW_TYPE, DRAW_FILLING);
   PlotIndexSetInteger(1, PLOT_LINE_COLOR, 0, C'255,17,0');
   PlotIndexSetInteger(1, PLOT_LINE_COLOR, 1, C'255,17,0');
   PlotIndexSetString(1, PLOT_LABEL, "Trail Fill Short");
   // plot 2: smart trail line
   PlotIndexSetInteger(2, PLOT_DRAW_TYPE, DRAW_COLOR_LINE);
   PlotIndexSetInteger(2, PLOT_COLOR_INDEXES, 2);
   PlotIndexSetInteger(2, PLOT_LINE_COLOR, 0, C'33,87,249');
   PlotIndexSetInteger(2, PLOT_LINE_COLOR, 1, C'255,17,0');
   PlotIndexSetString(2, PLOT_LABEL, "Smart Trail");
   // plot 3: follow line 1
   PlotIndexSetInteger(3, PLOT_DRAW_TYPE, DRAW_COLOR_LINE);
   PlotIndexSetInteger(3, PLOT_COLOR_INDEXES, 2);
   PlotIndexSetInteger(3, PLOT_LINE_COLOR, 0, C'2,248,27');
   PlotIndexSetInteger(3, PLOT_LINE_COLOR, 1, clrRed);
   PlotIndexSetInteger(3, PLOT_LINE_WIDTH, 2);
   PlotIndexSetString(3, PLOT_LABEL, "Trend Line (BB)");
   // plot 4,5: buy1/sell1
   PlotIndexSetInteger(4, PLOT_DRAW_TYPE, DRAW_ARROW);
   PlotIndexSetInteger(4, PLOT_ARROW, 233);
   PlotIndexSetInteger(4, PLOT_LINE_COLOR, clrTeal);
   PlotIndexSetInteger(4, PLOT_LINE_WIDTH, 2);
   PlotIndexSetString(4, PLOT_LABEL, "Buy");
   PlotIndexSetInteger(5, PLOT_DRAW_TYPE, DRAW_ARROW);
   PlotIndexSetInteger(5, PLOT_ARROW, 234);
   PlotIndexSetInteger(5, PLOT_LINE_COLOR, clrRed);
   PlotIndexSetInteger(5, PLOT_LINE_WIDTH, 2);
   PlotIndexSetString(5, PLOT_LABEL, "Sell");
   // plot 6: follow line 2
   PlotIndexSetInteger(6, PLOT_DRAW_TYPE, DRAW_COLOR_LINE);
   PlotIndexSetInteger(6, PLOT_COLOR_INDEXES, 2);
   PlotIndexSetInteger(6, PLOT_LINE_COLOR, 0, C'1,248,43');
   PlotIndexSetInteger(6, PLOT_LINE_COLOR, 1, clrRed);
   PlotIndexSetInteger(6, PLOT_LINE_WIDTH, 2);
   PlotIndexSetString(6, PLOT_LABEL, "Trend Line (MA)");
   // plot 7,8: smart buy/sell
   PlotIndexSetInteger(7, PLOT_DRAW_TYPE, DRAW_ARROW);
   PlotIndexSetInteger(7, PLOT_ARROW, 233);
   PlotIndexSetInteger(7, PLOT_LINE_COLOR, clrAqua);
   PlotIndexSetInteger(7, PLOT_LINE_WIDTH, 3);
   PlotIndexSetString(7, PLOT_LABEL, "Smart Buy");
   PlotIndexSetInteger(8, PLOT_DRAW_TYPE, DRAW_ARROW);
   PlotIndexSetInteger(8, PLOT_ARROW, 234);
   PlotIndexSetInteger(8, PLOT_LINE_COLOR, clrMagenta);
   PlotIndexSetInteger(8, PLOT_LINE_WIDTH, 3);
   PlotIndexSetString(8, PLOT_LABEL, "Smart Sell");
   // plot 9: kernel
   PlotIndexSetInteger(9, PLOT_DRAW_TYPE, DRAW_COLOR_LINE);
   PlotIndexSetInteger(9, PLOT_COLOR_INDEXES, 2);
   PlotIndexSetInteger(9, PLOT_LINE_COLOR, 0, C'9,255,95');
   PlotIndexSetInteger(9, PLOT_LINE_COLOR, 1, clrRed);
   PlotIndexSetInteger(9, PLOT_LINE_WIDTH, 2);
   PlotIndexSetString(9, PLOT_LABEL, "Kernel");
   // plot 10: entry
   PlotIndexSetInteger(10, PLOT_DRAW_TYPE, DRAW_LINE);
   PlotIndexSetInteger(10, PLOT_LINE_COLOR, C'255,167,38');
   PlotIndexSetString(10, PLOT_LABEL, "Entry");

   for(int p = 0; p < 11; p++) PlotIndexSetDouble(p, PLOT_EMPTY_VALUE, EMPTY_VALUE);

   BuildKernelWeights();
   IndicatorSetString(INDICATOR_SHORTNAME, "Geno Smart Signal");
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   ObjectsDeleteAll(0, PFX);
}

int OnCalculate(const int rates_total, const int prev_calculated,
                const datetime &time[], const double &open[], const double &high[],
                const double &low[], const double &close[], const long &tick_volume[],
                const long &volume[], const int &spread[])
{
   if(rates_total < 50) return 0;
   if(prev_calculated == 0)
   {
      g_base = (InpCalcBars > 0) ? MathMax(0, rates_total - InpCalcBars) : 0;
      ResetState();
   }
   g_live = (prev_calculated > 0);

   int n = rates_total - 1 - g_base;       // จำนวนแท่งที่ปิดแล้ว
   if(n != g_N || ArraySize(c_) != n)
   {
      g_N = n;
      ResizeAll(n);
   }
   g_drawFrom = MathMax(0, n - InpDrawBars);

   bool advanced = (g_done < n);
   for(int k = g_done; k < n; k++)
   {
      int i = g_base + k;
      o_[k] = open[i]; h_[k] = high[i]; l_[k] = low[i]; c_[k] = close[i];
      v_[k] = (double)tick_volume[i]; tm_[k] = time[i];
      Step(k);
   }
   g_done = n;

   // แท่งที่กำลังวิ่ง = ไม่แสดงสัญญาณ (non-repaint)
   int f = rates_total - 1;
   bFillLA[f] = EMPTY_VALUE; bFillLB[f] = EMPTY_VALUE; bFillSA[f] = EMPTY_VALUE; bFillSB[f] = EMPTY_VALUE;
   bTrail[f] = EMPTY_VALUE; bFl1[f] = EMPTY_VALUE; bBuy1[f] = EMPTY_VALUE; bSell1[f] = EMPTY_VALUE;
   bFl2[f] = EMPTY_VALUE; bBuy2[f] = EMPTY_VALUE; bSell2[f] = EMPTY_VALUE; bKer[f] = EMPTY_VALUE;
   bEntry[f] = EMPTY_VALUE; bSL[f] = EMPTY_VALUE; bSwL[f] = EMPTY_VALUE; bSwH[f] = EMPTY_VALUE;

   if(advanced || prev_calculated == 0)
   {
      g_lastTime = time[rates_total - 1];
      DrawOB();
      DrawTrade();
   }
   return rates_total;
}
//+------------------------------------------------------------------+
