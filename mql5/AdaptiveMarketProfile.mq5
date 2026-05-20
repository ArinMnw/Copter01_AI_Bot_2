//+------------------------------------------------------------------+
//|                                   AdaptiveMarketProfile.mq5     |
//|              Converted from Pine Script by Julien_Eche           |
//+------------------------------------------------------------------+
#property copyright "Converted from Pine Script by Julien_Eche"
#property version   "1.00"
#property indicator_chart_window
#property indicator_buffers 4
#property indicator_plots   4

//--- Inputs
input bool             useAdaptive         = true;              // Automatic detection of optimal trend channel period
input int              pI                  = 200;              // Manual channel period (bars)
input double           devMultiplier       = 2.0;              // Deviation Multiplier
// --- Channel Lines ---
input color            regColor            = clrGray;          // Channel Lines Color
input int              regLineWidth        = 1;                // Channel Lines Width
input color            regFillColor        = C'144,148,151';   // Channel Fill
// --- Mid Line ---
input color            regLineColor        = clrGray;          // Mid Line Color
// --- Most Active Lines ---
input int              numActivityLines    = 2;                // Show Most Active Lines (1-5)
// --- Profile ---
input bool             showLabels          = false;            // Show Labels
input string           activityMethod      = "Volume";         // Calculation method: Touches / Volume
input int              nFills              = 23;               // Number of Profile Sections (2-25)
// --- Active Lines ---
input int              actLineWidth        = 1;                // Active Line Width (1-5)
// --- Trend Panel ---
input bool             showTrendPanel      = true;             // Show All-TF Trend Panel
input ENUM_BASE_CORNER panelCorner         = CORNER_RIGHT_UPPER; // Panel corner
input int              panelXOffset        = 10;               // Panel X offset (px)
input int              panelYOffset        = 20;               // Panel Y offset (px)
input int              panelFontSize       = 10;               // Panel font size
input string           panelFont           = "Consolas";       // Panel font
input color            panelBullColor      = clrLime;          // Bull color
input color            panelBearColor      = clrRed;           // Bear color
input color            panelSideColor      = clrGray;          // Sideway color
input color            panelHeaderColor    = clrWhite;         // Header color
// --- Trend Thresholds ---
input double           threshStrong        = 0.7;              // Pearson r → Strong trend
input double           threshSideway       = 0.3;              // Pearson r < this → Sideway

// Hardcoded (ซ่อนจากเมนู)
#define uL              false
#define regLineStyle    STYLE_SOLID
#define regLineStyleOpt STYLE_DASH
#define actLineStyle    STYLE_SOLID
#define regLineWidthOpt 1
#define customColor     C'0,187,255'
#define showRegLine          false
#define showProfile          false
#define showMostActiveLines  false

//--- Output buffers (readable via CopyBuffer / iCustom)
// Buffer 0: Slope        → + = uptrend, - = downtrend
// Buffer 1: PriceMid     → close - midline  (+ = above mid = bull bias, - = bear bias)
// Buffer 2: Pearson      → 0–1, trend strength
// Buffer 3: StdDev       → residual std dev (สูง = volatile/sideways, ต่ำ = tight trend)
double BufSlope[];
double BufPriceMid[];
double BufPearson[];
double BufStdDev[];

//--- Object name prefix
#define PREFIX      "AMP_"
#define PANEL_PFX   "AMPP_"

//--- Adaptive periods to test (matching Pine Script)
int PERIODS[] = {50,60,70,80,90,100,115,130,145,160,180,200,220,250,280,310,340,370,400};

//--- All-TF panel: TF list
string            PANEL_TF_NAMES[] = {"M1","M5","M15","M30","H1","H4","H12","D1"};
ENUM_TIMEFRAMES   PANEL_TF_ENUMS[] = {PERIOD_M1,PERIOD_M5,PERIOD_M15,PERIOD_M30,
                                       PERIOD_H1,PERIOD_H4,PERIOD_H12,PERIOD_D1};

//--- Per-TF trend result
struct TFTrendInfo
{
    string trend;     // "BULL" | "BEAR" | "SIDEWAY"
    string strength;  // "strong" | "weak" | "-"
    double pearson;
    double slope;
    bool   ok;
};

//+------------------------------------------------------------------+
//| Adjust/unadjust for log scale                                    |
//+------------------------------------------------------------------+
double Adj(double p)   { return uL ? MathLog(MathMax(p, 1e-10)) : p; }
double UnAdj(double p) { return uL ? MathExp(p) : p; }

//+------------------------------------------------------------------+
//| Linear regression: returns slope, intercept, stdDev, Pearson r  |
//| Arrays set as series: [0]=current, [len-1]=oldest               |
//+------------------------------------------------------------------+
bool CalcReg(const double &close[], int len, int total,
             double &slope, double &intercept, double &stdDev, double &pearson)
{
    if(len < 2 || len > total) return false;

    // x: 0=oldest bar in window, len-1=current bar
    // close[j] with series → close[0]=current → x = len-1-j
    double sumX=0, sumXX=0, sumXY=0, sumY=0, sumYY=0;
    double n = (double)len;

    for(int j=0; j<len; j++)
    {
        double x   = (double)(len - 1 - j);   // 0=oldest, len-1=newest
        double val = Adj(close[j]);
        sumX  += x;
        sumXX += x * x;
        sumXY += x * val;
        sumY  += val;
        sumYY += val * val;
    }

    double denom = n * sumXX - sumX * sumX;
    if(denom == 0.0) return false;

    slope     = (n * sumXY - sumX * sumY) / denom;
    intercept = (sumY - slope * sumX) / n;

    // Pearson r
    double xAvg = sumX / n;
    double yAvg = sumY / n;
    double varX = sumXX / n - xAvg * xAvg;
    double varY = sumYY / n - yAvg * yAvg;
    pearson = (varX > 0 && varY > 0)
              ? ((sumXY / n) - xAvg * yAvg) / MathSqrt(varX * varY)
              : 0.0;
    pearson = MathAbs(pearson); // Pine's r is always positive (|r(i, price)|)

    // StdDev of residuals
    double sumRes = 0.0;
    for(int j=0; j<len; j++)
    {
        double x   = (double)(len - 1 - j);
        double fit = intercept + slope * x;
        double res = Adj(close[j]) - fit;
        sumRes += res * res;
    }
    stdDev = MathSqrt(sumRes / (len - 1));

    return true;
}

//+------------------------------------------------------------------+
//| Interpolate value along a sloped line                            |
//+------------------------------------------------------------------+
// ตรงกับ Pine: calcLineValue(startY, endY, pos, totalBars) => startY + (endY-startY)*pos/totalBars
// pos รับ double ได้ (ใช้ +0.5 สำหรับ midpoint ของ section)
double LineVal(double startY, double endY, double pos, int totalBars)
{
    if(totalBars <= 0) return startY;
    return UnAdj(Adj(startY) + (Adj(endY) - Adj(startY)) * pos / (double)totalBars);
}



int GetRValue(color c) { return (int)(c & 0xFF); }
int GetGValue(color c) { return (int)((c >> 8) & 0xFF); }
int GetBValue(color c) { return (int)((c >> 16) & 0xFF); }

//+------------------------------------------------------------------+
//| Format number (K/M suffix)                                       |
//+------------------------------------------------------------------+
string FormatNum(double n)
{
    if(n >= 1000000) return DoubleToString(n / 1000000.0, 2) + "M";
    if(n >= 1000)    return DoubleToString(n / 1000.0, 2) + "K";
    return DoubleToString(n, 0);
}

//+------------------------------------------------------------------+
//| Delete all AMP objects                                           |
//+------------------------------------------------------------------+
void DeleteAll() { ObjectsDeleteAll(0, PREFIX); }

//+------------------------------------------------------------------+
//| Create or update a TREND line object                             |
//+------------------------------------------------------------------+
void SetTrendLine(string name, datetime t1, double p1, datetime t2, double p2,
                  color clr, int width, ENUM_LINE_STYLE style,
                  bool rayRight=true, bool back=true)
{
    if(ObjectFind(0, name) < 0)
        ObjectCreate(0, name, OBJ_TREND, 0, t1, p1, t2, p2);
    else
    {
        ObjectSetInteger(0, name, OBJPROP_TIME,  0, t1);
        ObjectSetDouble(0,  name, OBJPROP_PRICE, 0, p1);
        ObjectSetInteger(0, name, OBJPROP_TIME,  1, t2);
        ObjectSetDouble(0,  name, OBJPROP_PRICE, 1, p2);
    }
    ObjectSetInteger(0, name, OBJPROP_COLOR,     clr);
    ObjectSetInteger(0, name, OBJPROP_WIDTH,     width);
    ObjectSetInteger(0, name, OBJPROP_STYLE,     style);
    ObjectSetInteger(0, name, OBJPROP_RAY_RIGHT, rayRight);
    ObjectSetInteger(0, name, OBJPROP_BACK,      back);
    ObjectSetInteger(0, name, OBJPROP_SELECTABLE,false);
}

//+------------------------------------------------------------------+
//| Compute AMP trend for one TF                                     |
//+------------------------------------------------------------------+
bool ComputeTFTrend(ENUM_TIMEFRAMES tf, TFTrendInfo &out)
{
    out.ok       = false;
    out.trend    = "—";
    out.strength = "-";
    out.pearson  = 0.0;
    out.slope    = 0.0;

    int maxPeriod = 410;
    double closes[];
    int copied = CopyClose(_Symbol, tf, 0, maxPeriod + 10, closes);
    if(copied < 52) return false;
    ArraySetAsSeries(closes, true);   // [0]=current, [copied-1]=oldest

    int    nP            = ArraySize(PERIODS);
    double bestPearson   = -1.0;
    double bestSlope     = 0.0;
    double bestIntercept = 0.0;
    double bestStdDev    = 0.0;
    int    bestPeriod    = 0;      // เซฟ period ที่ให้ pearson สูงสุด

    for(int p = 0; p < nP; p++)
    {
        int len = PERIODS[p];
        if(len >= copied) continue;
        double sl, ic, sd, pr;
        if(CalcReg(closes, len, copied, sl, ic, sd, pr) && pr > bestPearson)
        {
            bestPearson   = pr;
            bestSlope     = sl;
            bestIntercept = ic;
            bestStdDev    = sd;
            bestPeriod    = len;   // ← เซฟ period ที่ถูก
        }
    }
    if(bestPearson < 0 || bestPeriod < 2) return false;

    // midCurrent = ค่า midline ที่แท่งปัจจุบัน (x = bestPeriod-1)
    double currentClose = closes[0];
    double midCurrent   = bestIntercept + bestSlope * (double)(bestPeriod - 1);
    double priceMid     = currentClose - midCurrent;

    // Trend logic — ใช้ slope เป็น direction หลัก, pearson เป็น strength
    if(bestPearson < threshSideway)
    {
        out.trend    = "SIDEWAY";
        out.strength = "-";
    }
    else
    {
        string str = (bestPearson >= threshStrong) ? "strong" : "weak";
        if(bestSlope > 0)
            { out.trend = "BULL"; out.strength = str; }
        else
            { out.trend = "BEAR"; out.strength = str; }
    }

    out.pearson = bestPearson;
    out.slope   = bestSlope;
    out.ok      = true;
    return true;
}

//+------------------------------------------------------------------+
//| Delete all panel objects                                         |
//+------------------------------------------------------------------+
void DeletePanel()
{
    ObjectsDeleteAll(0, PANEL_PFX);
}

//+------------------------------------------------------------------+
//| Draw helper — one label                                          |
//+------------------------------------------------------------------+
void PanelLabel(string name, int x, int y, string text, color clr,
                int fontSize, string font, ENUM_BASE_CORNER corner)
{
    if(ObjectFind(0, name) < 0)
        ObjectCreate(0, name, OBJ_LABEL, 0, 0, 0);

    // Right-side corners: anchor ด้านขวาเพื่อให้ข้อความยื่นเข้ามาในจอ
    ENUM_ANCHOR_POINT anchor = (corner == CORNER_RIGHT_UPPER || corner == CORNER_RIGHT_LOWER)
                               ? ANCHOR_RIGHT_UPPER : ANCHOR_LEFT_UPPER;

    ObjectSetInteger(0, name, OBJPROP_CORNER,    corner);
    ObjectSetInteger(0, name, OBJPROP_ANCHOR,    anchor);
    ObjectSetInteger(0, name, OBJPROP_XDISTANCE, x);
    ObjectSetInteger(0, name, OBJPROP_YDISTANCE, y);
    ObjectSetString(0,  name, OBJPROP_TEXT,      text);
    ObjectSetInteger(0, name, OBJPROP_COLOR,     clr);
    ObjectSetInteger(0, name, OBJPROP_FONTSIZE,  fontSize);
    ObjectSetString(0,  name, OBJPROP_FONT,      font);
    ObjectSetInteger(0, name, OBJPROP_SELECTABLE,false);
}

//+------------------------------------------------------------------+
//| Draw all-TF trend panel                                          |
//+------------------------------------------------------------------+
void DrawTrendPanel()
{
    if(!showTrendPanel) { DeletePanel(); return; }

    int nTF     = ArraySize(PANEL_TF_NAMES);
    int lineH   = panelFontSize + 6;
    int x0      = panelXOffset;
    int y0      = panelYOffset;

    // Header
    PanelLabel(PANEL_PFX+"hdr", x0, y0,
               "── AMP Trend ──", panelHeaderColor,
               panelFontSize, panelFont, panelCorner);

    for(int i = 0; i < nTF; i++)
    {
        int y = y0 + lineH * (i + 1);

        TFTrendInfo info;
        bool ok = ComputeTFTrend(PANEL_TF_ENUMS[i], info);

        string tfStr    = StringFormat("%-4s", PANEL_TF_NAMES[i]);
        string trendStr, rowText;
        color  rowColor;

        if(!ok)
        {
            rowText  = tfStr + "  —";
            rowColor = panelSideColor;
        }
        else if(info.trend == "BULL")
        {
            trendStr = (info.strength == "strong") ? "Bull ▲ str" : "Bull ▲ wk ";
            rowText  = tfStr + "  " + trendStr + StringFormat("  %.2f", info.pearson);
            rowColor = panelBullColor;
        }
        else if(info.trend == "BEAR")
        {
            trendStr = (info.strength == "strong") ? "Bear ▼ str" : "Bear ▼ wk ";
            rowText  = tfStr + "  " + trendStr + StringFormat("  %.2f", info.pearson);
            rowColor = panelBearColor;
        }
        else  // SIDEWAY
        {
            rowText  = tfStr + "  Sideway   " + StringFormat("  %.2f", info.pearson);
            rowColor = panelSideColor;
        }

        PanelLabel(PANEL_PFX + "row" + IntegerToString(i),
                   x0, y, rowText, rowColor,
                   panelFontSize, panelFont, panelCorner);
    }

    ChartRedraw(0);
}

//+------------------------------------------------------------------+
//| OnInit                                                           |
//+------------------------------------------------------------------+
int OnInit()
{
    SetIndexBuffer(0, BufSlope,    INDICATOR_DATA);
    SetIndexBuffer(1, BufPriceMid, INDICATOR_DATA);
    SetIndexBuffer(2, BufPearson,  INDICATOR_DATA);
    SetIndexBuffer(3, BufStdDev,   INDICATOR_DATA);

    PlotIndexSetInteger(0, PLOT_DRAW_TYPE, DRAW_NONE);
    PlotIndexSetInteger(1, PLOT_DRAW_TYPE, DRAW_NONE);
    PlotIndexSetInteger(2, PLOT_DRAW_TYPE, DRAW_NONE);
    PlotIndexSetInteger(3, PLOT_DRAW_TYPE, DRAW_NONE);

    PlotIndexSetString(0, PLOT_LABEL, "Slope");
    PlotIndexSetString(1, PLOT_LABEL, "PriceMid");
    PlotIndexSetString(2, PLOT_LABEL, "Pearson");
    PlotIndexSetString(3, PLOT_LABEL, "StdDev");

    return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| OnDeinit                                                         |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
    DeleteAll();
    DeletePanel();
    ChartRedraw(0);
}

//+------------------------------------------------------------------+
//| OnCalculate                                                      |
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
    if(rates_total < 52) return 0;

    // Redraw only on new bar or first run
    static datetime lastBarTime = 0;
    if(time[rates_total - 1] == lastBarTime && prev_calculated > 0) return rates_total;
    lastBarTime = time[rates_total - 1];

    // Set arrays as series (index 0 = current bar)
    ArraySetAsSeries(close,       true);
    ArraySetAsSeries(high,        true);
    ArraySetAsSeries(low,         true);
    ArraySetAsSeries(tick_volume, true);
    ArraySetAsSeries(time,        true);

    DeleteAll();

    //--- Step 1: Find optimal period ---
    int    finalPeriod    = MathMin(pI, rates_total - 1);
    double bestPearson    = -2.0;
    double bestSlope      = 0.0;
    double bestIntercept  = 0.0;
    double bestStdDev     = 0.0;

    if(useAdaptive)
    {
        int nP = ArraySize(PERIODS);
        for(int p = 0; p < nP; p++)
        {
            int len = PERIODS[p];
            if(len >= rates_total) continue;
            double sl, ic, sd, pr;
            if(CalcReg(close, len, rates_total, sl, ic, sd, pr) && pr > bestPearson)
            {
                bestPearson   = pr;
                finalPeriod   = len;
                bestSlope     = sl;
                bestIntercept = ic;
                bestStdDev    = sd;
            }
        }
        // fallback หาก adaptive ไม่ได้ผล
        if(bestPearson < -1.0)
        {
            finalPeriod = MathMin(200, rates_total - 1);
            CalcReg(close, finalPeriod, rates_total, bestSlope, bestIntercept, bestStdDev, bestPearson);
        }
    }
    else
    {
        CalcReg(close, finalPeriod, rates_total, bestSlope, bestIntercept, bestStdDev, bestPearson);
    }

    int lI = finalPeriod;
    if(lI < 2) return rates_total;

    //--- Step 2: Channel endpoints (oldest→newest) ---
    // x=0 → oldest bar (lI-1 bars ago), x=lI-1 → current bar (0 bars ago)
    double sP = UnAdj(bestIntercept);                         // oldest bar
    double eP = UnAdj(bestIntercept + bestSlope * (lI - 1)); // current bar

    // Compute max deviation for sD
    double sumRes = 0.0;
    for(int j = 0; j < lI; j++)
    {
        double x   = (double)(lI - 1 - j);
        double fit = bestIntercept + bestSlope * x;
        double res = Adj(close[j]) - fit;
        sumRes += res * res;
    }
    double sD = MathSqrt(sumRes / (lI - 1));

    //--- Output buffers (current bar = rates_total-1 in non-series index) ---
    BufSlope   [rates_total - 1] = bestSlope;
    BufPriceMid[rates_total - 1] = close[0] - eP;
    BufPearson [rates_total - 1] = bestPearson;
    BufStdDev  [rates_total - 1] = sD;

    // Upper/lower endpoints
    double dev = devMultiplier * sD;
    double uSP = UnAdj(Adj(sP) + dev);   // upper at oldest
    double uEP = UnAdj(Adj(eP) + dev);   // upper at current
    double lSP = UnAdj(Adj(sP) - dev);   // lower at oldest
    double lEP = UnAdj(Adj(eP) - dev);   // lower at current

    // Bar indices (series: [0]=current)
    // startBar in original array (non-series) = rates_total - lI
    // newest = time[0], oldest = time[lI-1]
    datetime t_newest = time[0];
    datetime t_oldest = time[lI - 1];

    //--- Step 3: Draw channel lines ---
    // Upper
    SetTrendLine(PREFIX+"Upper", t_oldest, uSP, t_newest, uEP,
                 regColor, regLineWidth, regLineStyle, true, true);
    // Lower
    SetTrendLine(PREFIX+"Lower", t_oldest, lSP, t_newest, lEP,
                 regColor, regLineWidth, regLineStyle, true, true);

    // Channel fill: ปิด

    // Mid line
    if(showRegLine)
        SetTrendLine(PREFIX+"Mid", t_oldest, sP, t_newest, eP,
                     regLineColor, regLineWidthOpt, regLineStyleOpt, true, true);

    // All-TF trend panel — วาดก่อน Step 4 เพื่อไม่โดน early return ข้าม
    DrawTrendPanel();

    // Pearson r label
    string pearsonName = PREFIX + "Pearson";
    ObjectCreate(0, pearsonName, OBJ_TEXT, 0, t_oldest, lSP);
    ObjectSetString(0,  pearsonName, OBJPROP_TEXT,      DoubleToString(bestPearson, 3));
    ObjectSetInteger(0, pearsonName, OBJPROP_COLOR,     clrGray);
    ObjectSetInteger(0, pearsonName, OBJPROP_FONTSIZE,  9);
    ObjectSetInteger(0, pearsonName, OBJPROP_SELECTABLE,false);

    //--- Step 4: Profile — count touches/volume per section ---
    double counts[];
    ArrayResize(counts, nFills);
    ArrayInitialize(counts, 0.0);

    for(int sec = 0; sec < nFills; sec++)
    {
        // section boundaries at oldest and newest
        double y1_top = LineVal(lSP, uSP, sec,     nFills);
        double y1_bot = LineVal(lSP, uSP, sec + 1, nFills);
        double y2_top = LineVal(lEP, uEP, sec,     nFills);
        double y2_bot = LineVal(lEP, uEP, sec + 1, nFills);
        double y1_mid = (y1_top + y1_bot) / 2.0;
        double y2_mid = (y2_top + y2_bot) / 2.0;

        double cnt = 0.0;
        for(int j = 0; j < lI; j++)
        {
            // j=0=newest, j=lI-1=oldest → barPos (0=oldest, lI-1=newest) = lI-1-j
            int barPos = lI - 1 - j;
            double lineVal = LineVal(y1_mid, y2_mid, barPos, lI);
            if(low[j] <= lineVal && high[j] >= lineVal)
            {
                cnt += (activityMethod == "Touches") ? 1.0 : (double)tick_volume[j];
            }
        }
        counts[sec] = cnt;
    }

    // Max count
    double maxCount = 0.0;
    for(int i = 0; i < nFills; i++) if(counts[i] > maxCount) maxCount = counts[i];
    if(maxCount <= 0.0) { ChartRedraw(0); return rates_total; }

    // Sort indices descending by count
    int sortedIdx[];
    ArrayResize(sortedIdx, nFills);
    for(int i = 0; i < nFills; i++) sortedIdx[i] = i;
    for(int i = 0; i < nFills - 1; i++)
        for(int j = i + 1; j < nFills; j++)
            if(counts[sortedIdx[j]] > counts[sortedIdx[i]])
            { int tmp = sortedIdx[i]; sortedIdx[i] = sortedIdx[j]; sortedIdx[j] = tmp; }

    // Activity slope — ใช้ midpoint ของ section ที่ active ที่สุด (ตรงกับ Pine: index + 0.5)
    int topSec = sortedIdx[0];
    double actY1 = LineVal(lSP, uSP, topSec + 0.5, nFills);   // midpoint at oldest
    double actY2 = LineVal(lEP, uEP, topSec + 0.5, nFills);   // midpoint at newest
    double actSlope = (lI > 1) ? (Adj(actY2) - Adj(actY1)) / (double)(lI - 1) : 0.0;

    //--- Step 5: Draw most active lines ---
    if(showMostActiveLines)
    {
        double minThresh = maxCount * 0.1;
        int displayed = 0;
        int profileLen = (int)MathRound((double)lI / 5.0);

        for(int idx = 0; idx < nFills && displayed < numActivityLines; idx++)
        {
            int sec    = sortedIdx[idx];
            double cnt = counts[sec];
            if(cnt < minThresh) continue;

            double aY1 = LineVal(lSP, uSP, sec, nFills);   // at oldest
            double aY2 = LineVal(lEP, uEP, sec, nFills);   // at newest

            double pct = cnt / maxCount;
            color  lc  = customColor;

            // Start x: shift right based on profile ratio (if showProfile)
            int    lineLen  = showProfile ? (int)MathRound(pct * profileLen) : 0;
            int    startPos = lineLen;  // bars from oldest end
            double startY   = UnAdj(Adj(aY1) + actSlope * startPos);

            datetime tStart = (startPos < lI) ? time[lI - 1 - startPos] : t_oldest;

            string aName = PREFIX + "ActLine_" + IntegerToString(displayed);
            SetTrendLine(aName, tStart, startY, t_newest, aY2,
                         lc, actLineWidth, actLineStyle, true, false);

            // Label
            if(showLabels)
            {
                string lblName = PREFIX + "ActLbl_" + IntegerToString(displayed);
                datetime tLbl  = t_newest + (long)PeriodSeconds() * 5;
                ObjectCreate(0, lblName, OBJ_TEXT, 0, tLbl, aY2);
                ObjectSetString(0,  lblName, OBJPROP_TEXT,       FormatNum(cnt));
                ObjectSetInteger(0, lblName, OBJPROP_COLOR,      lc);
                ObjectSetInteger(0, lblName, OBJPROP_FONTSIZE,   8);
                ObjectSetInteger(0, lblName, OBJPROP_SELECTABLE, false);
            }
            displayed++;
        }
    }

    //--- Step 6: Draw profile fills (OBJ_CHANNEL = parallelogram ตามความชัน channel) ---
    if(showProfile)
    {
        int maxProfileBars       = 25;
        int effectiveProfileBars = MathMax(numActivityLines,
                                   MathMin(nFills,
                                   MathMax(maxProfileBars - (numActivityLines - 2), 2)));
        int profileLen = (int)MathRound((double)lI / 5.0);

        for(int idx = 0; idx < effectiveProfileBars; idx++)
        {
            int    sec   = sortedIdx[idx];
            double cnt   = counts[sec];
            double pct   = cnt / maxCount;
            color  pFill = customColor;
            int    lineLen = (int)MathRound(pct * profileLen);

            // Top/bottom ของ section ที่ oldest bar (ตรงกับ Pine: y1_top, y1_bottom)
            double y1_top = LineVal(lSP, uSP, (double)sec,       nFills);
            double y1_bot = LineVal(lSP, uSP, (double)(sec + 1), nFills);

            // End point = oldest + lineLen bars toward newest (series: oldest=time[lI-1])
            int endSeries = MathMax(0, lI - 1 - lineLen);
            datetime tEnd = time[endSeries];

            // End Y = ขยับตามความชัน actSlope × lineLen (ตรงกับ Pine)
            double y_top_end = UnAdj(Adj(y1_top) + actSlope * lineLen);
            double y_bot_end = UnAdj(Adj(y1_bot) + actSlope * lineLen);

            // OBJ_CHANNEL: base = midpoint line, P3 = top ที่ oldest (กำหนด half-width)
            // เพราะ top/bot symmetric รอบ mid → OBJ_CHANNEL สร้าง parallelogram ถูกต้อง
            double mid_start = (y1_top + y1_bot) / 2.0;
            double mid_end   = (y_top_end + y_bot_end) / 2.0;

            string rName = PREFIX + "Prof_" + IntegerToString(idx);
            if(ObjectFind(0, rName) < 0)
                ObjectCreate(0, rName, OBJ_CHANNEL, 0,
                             t_oldest, mid_start, tEnd, mid_end, t_oldest, y1_top);
            else
            {
                ObjectSetInteger(0, rName, OBJPROP_TIME,  0, t_oldest);
                ObjectSetDouble(0,  rName, OBJPROP_PRICE, 0, mid_start);
                ObjectSetInteger(0, rName, OBJPROP_TIME,  1, tEnd);
                ObjectSetDouble(0,  rName, OBJPROP_PRICE, 1, mid_end);
                ObjectSetInteger(0, rName, OBJPROP_TIME,  2, t_oldest);
                ObjectSetDouble(0,  rName, OBJPROP_PRICE, 2, y1_top);
            }
            ObjectSetInteger(0, rName, OBJPROP_COLOR,     pFill);
            ObjectSetInteger(0, rName, OBJPROP_FILL,      true);
            ObjectSetInteger(0, rName, OBJPROP_BACK,      true);
            ObjectSetInteger(0, rName, OBJPROP_RAY_RIGHT, false);
            ObjectSetInteger(0, rName, OBJPROP_SELECTABLE,false);
        }
    }

    ChartRedraw(0);
    return rates_total;
}

