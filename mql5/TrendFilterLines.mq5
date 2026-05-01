//+------------------------------------------------------------------+
//|                                            TrendFilterLines.mq5  |
//|  Reads trend_state.txt / trend_state_<symbol>.txt and draws      |
//|  SLOPED trend lines through 2 swing points, with ray to right,   |
//|  for each TF where Per-TF is ticked in the bot.                  |
//|  Also renders a TREND summary panel at the bottom-right corner.  |
//|                                                                   |
//|  File location: <Terminal>\Common\Files\trend_state*.txt         |
//|  Format per line:                                                 |
//|    tf,trend,strength,                                             |
//|    sh_time,sh_price,prev_sh_time,prev_sh_price,                   |
//|    sl_time,sl_price,prev_sl_time,prev_sl_price,                   |
//|    break_flag,per_tf_on                                           |
//|                                                                   |
//|  Drawing rule:                                                    |
//|    BULL / BEAR / SIDEWAY → 2 lines (resistance + support)        |
//|    UNKNOWN               → skip                                   |
//|    strong = solid + thick, weak = dashed + thin                   |
//+------------------------------------------------------------------+
#property copyright   "Copter01 AI Bot"
#property link        ""
#property version     "2.10"
#property indicator_chart_window
#property indicator_plots 0

input string InpFileName        = "trend_state.txt"; // Shared file under Common\Files
input int    InpRefreshSec      = 5;                 // Refresh interval (seconds)
input bool   InpOnlyPerTfOn     = true;              // Draw only TFs with per_tf_on=1
input bool   InpOnlyChartTf     = true;              // Draw only the TF matching this chart
input color  InpBullColor       = clrLime;           // Bull trend color
input color  InpBearColor       = clrRed;            // Bear trend color
input color  InpSidewayColor    = clrGray;           // Sideway / unknown color
input int    InpStrongWidth     = 2;                 // Width for strong trend
input int    InpWeakWidth       = 1;                 // Width for weak trend
input bool   InpShowLabels      = true;              // Show TF label at right edge
input int    InpLabelFontSize   = 9;                 // Label font size

// === Panel (summary box at bottom-right) ===
input bool   InpShowPanel        = true;             // Show trend summary panel
input int    InpPanelXOffset     = 10;               // Panel X offset from right (px)
input int    InpPanelYOffset     = 20;               // Panel Y offset from bottom (px)
input int    InpPanelFontSize    = 10;               // Panel font size
input string InpPanelFont        = "Consolas";       // Panel font (monospace recommended)
input color  InpPanelHeaderColor = clrWhite;         // Panel header color

string g_prefix = "TFL_";
datetime g_last_refresh = 0;

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

struct TFRow
  {
   string   tf;
   string   trend;
   string   strength;
   datetime sh_time;
   double   sh_price;
   datetime psh_time;
   double   psh_price;
   datetime sl_time;
   double   sl_price;
   datetime psl_time;
   double   psl_price;
   string   break_flag;
   int      per_tf_on;
  };

//+------------------------------------------------------------------+
int OnInit()
  {
   EventSetTimer(MathMax(1, InpRefreshSec));
   RefreshLines();
   return(INIT_SUCCEEDED);
  }

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   EventKillTimer();
   ObjectsDeleteAll(0, g_prefix);
   Comment("");
   ChartRedraw();
  }

//+------------------------------------------------------------------+
void OnTimer()
  {
   RefreshLines();
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
//| Chart event — refresh when user changes timeframe                 |
//+------------------------------------------------------------------+
void OnChartEvent(const int id, const long &lparam,
                  const double &dparam, const string &sparam)
  {
   if(id == CHARTEVENT_CHART_CHANGE)
      RefreshLines();
  }

//+------------------------------------------------------------------+
int SplitCsv(const string line, string &parts[])
  {
   return StringSplit(line, (ushort)',', parts);
  }

//+------------------------------------------------------------------+
//| Map chart's current period to the TF name used in the file       |
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
color PickColor(const string trend)
  {
   if(trend == "BULL") return InpBullColor;
   if(trend == "BEAR") return InpBearColor;
   return InpSidewayColor;
  }

//+------------------------------------------------------------------+
ENUM_LINE_STYLE PickStyle(const string strength)
  {
   if(strength == "strong") return STYLE_SOLID;
   if(strength == "weak")   return STYLE_DASH;
   return STYLE_DOT;
  }

//+------------------------------------------------------------------+
int PickWidth(const string strength)
  {
   if(strength == "strong") return InpStrongWidth;
   return InpWeakWidth;
  }

//+------------------------------------------------------------------+
//| Create or update one sloped trend line with ray to right          |
//| Writes a visible OBJ_TEXT label near the right edge of chart      |
//+------------------------------------------------------------------+
void DrawTrend(const string name,
               const datetime t1, const double p1,
               const datetime t2, const double p2,
               const color clr,
               const ENUM_LINE_STYLE style,
               const int width,
               const string label)
  {
   string lbl_name = name + "_lbl";
   if(t1 <= 0 || t2 <= 0 || p1 <= 0 || p2 <= 0 || t1 == t2)
     {
      ObjectDelete(0, name);
      ObjectDelete(0, lbl_name);
      return;
     }
   if(ObjectFind(0, name) < 0)
      ObjectCreate(0, name, OBJ_TREND, 0, t1, p1, t2, p2);
   ObjectSetInteger(0, name, OBJPROP_TIME,  0, t1);
   ObjectSetDouble (0, name, OBJPROP_PRICE, 0, p1);
   ObjectSetInteger(0, name, OBJPROP_TIME,  1, t2);
   ObjectSetDouble (0, name, OBJPROP_PRICE, 1, p2);
   ObjectSetInteger(0, name, OBJPROP_COLOR, clr);
   ObjectSetInteger(0, name, OBJPROP_STYLE, style);
   ObjectSetInteger(0, name, OBJPROP_WIDTH, width);
   ObjectSetInteger(0, name, OBJPROP_RAY_RIGHT, true);
   ObjectSetInteger(0, name, OBJPROP_RAY_LEFT,  false);
   ObjectSetInteger(0, name, OBJPROP_BACK, true);
   ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, name, OBJPROP_HIDDEN, true);
   ObjectSetString (0, name, OBJPROP_TEXT, label);

   // label at last bar + 3 bars, projected along trend slope
   if(InpShowLabels)
     {
      datetime last_bar = (datetime)SeriesInfoInteger(_Symbol, _Period, SERIES_LASTBAR_DATE);
      datetime anchor   = last_bar + PeriodSeconds(_Period) * 3;
      double slope = (p2 - p1) / (double)(t2 - t1);
      double proj  = p2 + slope * (double)(anchor - t2);
      if(ObjectFind(0, lbl_name) < 0)
         ObjectCreate(0, lbl_name, OBJ_TEXT, 0, anchor, proj);
      ObjectSetInteger(0, lbl_name, OBJPROP_TIME,  anchor);
      ObjectSetDouble (0, lbl_name, OBJPROP_PRICE, proj);
      ObjectSetString (0, lbl_name, OBJPROP_TEXT,  label);
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
//| Create/update a single OBJ_LABEL at the bottom-right corner       |
//+------------------------------------------------------------------+
void DrawPanelLabel(const string name, const string text,
                    const int x, const int y, const color clr,
                    const ENUM_ANCHOR_POINT anchor = ANCHOR_RIGHT_LOWER)
  {
   if(ObjectFind(0, name) < 0)
      ObjectCreate(0, name, OBJ_LABEL, 0, 0, 0);
   ObjectSetInteger(0, name, OBJPROP_CORNER,     CORNER_RIGHT_LOWER);
   ObjectSetInteger(0, name, OBJPROP_ANCHOR,     anchor);
   ObjectSetInteger(0, name, OBJPROP_XDISTANCE,  x);
   ObjectSetInteger(0, name, OBJPROP_YDISTANCE,  y);
   ObjectSetString (0, name, OBJPROP_TEXT,       text);
   ObjectSetString (0, name, OBJPROP_FONT,       InpPanelFont);
   ObjectSetInteger(0, name, OBJPROP_FONTSIZE,   InpPanelFontSize);
   ObjectSetInteger(0, name, OBJPROP_COLOR,      clr);
   ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, name, OBJPROP_HIDDEN,     true);
   ObjectSetInteger(0, name, OBJPROP_BACK,       false);
  }

//+------------------------------------------------------------------+
//| Render trend summary panel at bottom-right corner (2-column table)|
//|   - Ignores InpOnlyChartTf (panel is multi-TF summary by design)  |
//|   - Respects InpOnlyPerTfOn                                       |
//|   - Shows UNKNOWN rows too (panel only; lines still need swings)  |
//|   - Each row = 2 OBJ_LABEL (TF cell + icon cell) for alignment    |
//+------------------------------------------------------------------+
void DrawPanel(const TFRow &rows[])
  {
   if(!InpShowPanel) return;

   int visible[];
   ArrayResize(visible, 0);
   int total_rows = ArraySize(rows);
   for(int i = 0; i < total_rows; i++)
     {
      if(InpOnlyPerTfOn && rows[i].per_tf_on == 0) continue;
      int sz = ArraySize(visible);
      ArrayResize(visible, sz + 1);
      visible[sz] = i;
     }

   int count = ArraySize(visible);
   int lh    = InpPanelFontSize + 6;

   // Column X positions (measured from right edge, leftward)
   //   x_icon = right edge of Icon column (closest to chart right edge)
   //   x_tf   = left  edge of TF   column (furthest from right edge)
   //   gap between TF-right and Icon-left is built into the column width
   int x_icon = InpPanelXOffset;
   int x_tf   = InpPanelXOffset + InpPanelFontSize * 8;

   if(count == 0)
     {
      DrawPanelLabel(g_prefix + "PANEL_hdr",
                     "TREND FILTER",
                     x_tf, InpPanelYOffset + lh,
                     InpPanelHeaderColor, ANCHOR_LEFT_LOWER);
       DrawPanelLabel(g_prefix + "PANEL_empty",
                      "No Active TF",
                      x_tf, InpPanelYOffset,
                      InpSidewayColor, ANCHOR_LEFT_LOWER);
      return;
     }

   // Header at top (largest Y), left-aligned above TF column
   DrawPanelLabel(g_prefix + "PANEL_hdr",
                  "TREND FILTER",
                  x_tf, InpPanelYOffset + count * lh,
                  InpPanelHeaderColor, ANCHOR_LEFT_LOWER);

   // Rows: k=0 at top, k=count-1 at bottom (preserve file order = M1..D1)
   for(int k = 0; k < count; k++)
     {
      int idx = visible[k];
      color clr = PickColor(rows[idx].trend);

      string icon;
      if(rows[idx].trend == "BULL")
         icon = (rows[idx].strength == "strong") ? "🟢🟢" : "🟢";
      else if(rows[idx].trend == "BEAR")
         icon = (rows[idx].strength == "strong") ? "🔴🔴" : "🔴";
      else if(rows[idx].trend == "SIDEWAY")
         icon = "⚪";
      else // UNKNOWN
         icon = "⚫";

      string brk = "";
      if(rows[idx].break_flag == "break_up")        brk = "↑";
      else if(rows[idx].break_flag == "break_down") brk = "↓";

      int y = InpPanelYOffset + (count - 1 - k) * lh;

      // TF cell — LEFT-aligned at x_tf (all TFs share same left edge)
      DrawPanelLabel(g_prefix + "PANEL_" + IntegerToString(k) + "_tf",
                     rows[idx].tf, x_tf, y, clr, ANCHOR_LEFT_LOWER);
      // Icon cell — RIGHT-aligned at x_icon (icon + break marker share same right edge)
      DrawPanelLabel(g_prefix + "PANEL_" + IntegerToString(k) + "_ic",
                     icon + brk, x_icon, y, clr, ANCHOR_RIGHT_LOWER);
     }
  }

//+------------------------------------------------------------------+
//| Read file and redraw all lines + panel                            |
//+------------------------------------------------------------------+
void RefreshLines()
  {
   g_last_refresh = TimeCurrent();
   string file_name = ResolveTrendFileName();
   int handle = FileOpen(file_name, FILE_READ|FILE_TXT|FILE_ANSI|FILE_COMMON);
   if(handle == INVALID_HANDLE)
     {
      Comment("TrendFilterLines: cannot open Common\\Files\\", file_name,
              " — err=", GetLastError());
      return;
     }

   ObjectsDeleteAll(0, g_prefix);

   // Parse rows into array
   TFRow rows[];
   ArrayResize(rows, 0);
   while(!FileIsEnding(handle))
     {
      string line = FileReadString(handle);
      if(line == "" || StringGetCharacter(line, 0) == '#')
         continue;
      string p[];
      int n = SplitCsv(line, p);
      if(n < 13) continue;

      TFRow row;
      row.tf         = p[0];
      row.trend      = p[1];
      row.strength   = p[2];
      row.sh_time    = (datetime)StringToInteger(p[3]);
      row.sh_price   = StringToDouble(p[4]);
      row.psh_time   = (datetime)StringToInteger(p[5]);
      row.psh_price  = StringToDouble(p[6]);
      row.sl_time    = (datetime)StringToInteger(p[7]);
      row.sl_price   = StringToDouble(p[8]);
      row.psl_time   = (datetime)StringToInteger(p[9]);
      row.psl_price  = StringToDouble(p[10]);
      row.break_flag = p[11];
      row.per_tf_on  = (int)StringToInteger(p[12]);

      int sz = ArraySize(rows);
      ArrayResize(rows, sz + 1);
      rows[sz] = row;
     }
   FileClose(handle);

   // Draw trend lines (respects both filters)
   string chart_tf = ChartTfName();
   int drawn = 0;
   for(int i = 0; i < ArraySize(rows); i++)
     {
      if(InpOnlyPerTfOn && rows[i].per_tf_on == 0) continue;
      if(InpOnlyChartTf && chart_tf != "" && rows[i].tf != chart_tf) continue;
      if(rows[i].trend == "UNKNOWN") continue;

      color clr             = PickColor(rows[i].trend);
      ENUM_LINE_STYLE style = PickStyle(rows[i].strength);
      int width             = PickWidth(rows[i].strength);

      string tag_break = "";
      if(rows[i].break_flag == "break_up")   tag_break = " 🚀";
      if(rows[i].break_flag == "break_down") tag_break = " 💥";

      string kind_name;
      if(rows[i].trend == "BULL")      kind_name = "Bull";
      else if(rows[i].trend == "BEAR") kind_name = "Bear";
      else                             kind_name = "Range";

      string lbl_res = StringFormat("[%s] %s-%s resistance%s",
                                    rows[i].tf, kind_name, rows[i].strength, tag_break);
      string lbl_sup = StringFormat("[%s] %s-%s support%s",
                                    rows[i].tf, kind_name, rows[i].strength, tag_break);

      // resistance (high pair): prev_sh → sh
      DrawTrend(g_prefix + rows[i].tf + "_RES",
                rows[i].psh_time, rows[i].psh_price,
                rows[i].sh_time,  rows[i].sh_price,
                clr, style, width, lbl_res);
      // support (low pair): prev_sl → sl
      DrawTrend(g_prefix + rows[i].tf + "_SUP",
                rows[i].psl_time, rows[i].psl_price,
                rows[i].sl_time,  rows[i].sl_price,
                clr, style, width, lbl_sup);

      drawn++;
     }

   // Summary panel at bottom-right
   DrawPanel(rows);

   Comment("TrendFilterLines: ", drawn, " TF drawn | last refresh ",
           TimeToString(g_last_refresh, TIME_SECONDS));
   ChartRedraw();
  }
//+------------------------------------------------------------------+
