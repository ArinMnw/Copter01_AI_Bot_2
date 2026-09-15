//+------------------------------------------------------------------+
//|                                              backtest_S420.mq5    |
//|  วาดผล backtest ของ S420 (จาก backtest_s420.py --compare หรือรันปกติ) |
//|  ลงบนชาร์ตจริง — อ่านไฟล์ s420_trades_<TF>.csv (TF เลือกอัตโนมัติ    |
//|  ตาม timeframe ของชาร์ตที่ attach อยู่) จาก MQL5\Files แล้ววาด:      |
//|    - เส้น Entry สีขาว, TP สีเขียว (ประ), SL สีแดง (ประ) ต่อไม้ 1 ชุด |
//|      ลากจากแท่ง entry ไปถึงแท่ง exit จริง (ตาม exit_time ใน CSV —    |
//|      ไม่ใช่ fixed 5 แท่งอีกต่อไป) แต่ละเส้นมี label เลขไม้+ราคา       |
//|      กำกับ (เช่น "1. Entry 4450.00") และเส้น TP/SL ที่ตรงกับ         |
//|      outcome จริงจะมี P&L กำกับด้วย (เช่น "1. TP 4460.00  P&L=25.78")|
//|    - ลูกศร Buy/Sell (built-in order-arrow object) ที่จุดเข้าไม้      |
//|    - ปุ่ม Order/TP/SL มุมซ้ายบนของชาร์ต: Order = master ปิด/เปิดทุกไม้ |
//|      ทั้งหมด, TP = ปิด/เปิดไม้ที่ผลลัพธ์เป็น TP ทั้งชุด (เส้น Entry/   |
//|      TP/SL + ลูกศร ของไม้นั้นทั้งหมด), SL = เหมือนกันแต่กรองเฉพาะไม้    |
//|      ที่ผลลัพธ์เป็น SL — กรองตามผลไม้ ไม่ใช่ตามชนิดเส้น               |
//|  เช็คว่าไฟล์เปลี่ยนทุก InpRefreshSec วิ (timer) แล้ว redraw ให้เอง —  |
//|  รัน backtest_s420.py ใหม่ (สคริปต์ copy CSV ทับให้อัตโนมัติ) ไม่ต้อง|
//|  ถอด/ใส่ indicator ใหม่ก็เห็นผลอัปเดต                                |
//|                                                                    |
//|  CSV มีทั้งเวลา BKK แบบอ่านง่าย (entry_time/exit_time) และ raw MT5   |
//|  epoch ดิบ (entry_time_raw/exit_time_raw) — indicator ใช้คอลัมน์ raw |
//|  โดยตรงกับ iTime() เลย ไม่ต้องแปลง timezone/เดา offset ต่อ broker    |
//|  เอง (broker เดียวกัน raw epoch ตรงกับ chart เป๊ะเสมอไม่ว่า server    |
//|  จะตั้ง timezone อะไร — กันพลาดแบบที่เคยใส่ -1h/-6h ผิดมาก่อน)        |
//+------------------------------------------------------------------+
#property copyright "Copter01 AI Bot"
#property link       ""
#property version    "1.00"
#property indicator_chart_window
#property indicator_plots 0
#property strict

input int    InpBarsExtend   = 5;          // fallback: ใช้เมื่อหาแท่ง exit บนชาร์ตไม่เจอ (ประวัติไม่ถึง)
input color  InpColorEntry   = clrWhite;
input color  InpColorTP      = clrLime;
input color  InpColorSL      = clrRed;
input bool   InpShowLabel    = true;       // แสดง label เลขไม้/ราคา/P&L กำกับแต่ละเส้น
input int    InpRefreshSec   = 5;          // เช็คไฟล์เปลี่ยนทุกกี่วิ (0 = ปิด auto-refresh)
input string InpFileOverride = "";         // เว้นว่าง = auto เลือกจาก TF ของชาร์ตปัจจุบัน

#define OBJ_PREFIX "S420BT_"
#define BTN_PREFIX "S420BTN_"

datetime g_last_file_mtime = 0;
string   g_file_name = "";

// ปุ่มเปิด/ปิดการแสดงไม้ (มุมซ้ายบนของชาร์ต) — ค่าเริ่มต้นเปิดหมด
bool g_show_order = true;  // master: ปิด/เปิดทุกไม้ทั้งหมด (AND กับ tp/sl ด้านล่าง)
bool g_show_tp    = true;  // ไม้ที่ผลลัพธ์เป็น TP ทั้งชุด (Entry/TP/SL/ลูกศร)
bool g_show_sl    = true;  // ไม้ที่ผลลัพธ์เป็น SL ทั้งชุด (Entry/TP/SL/ลูกศร)

//+------------------------------------------------------------------+
string TFSuffix()
  {
   switch(_Period)
     {
      case PERIOD_M1:  return "M1";
      case PERIOD_M5:  return "M5";
      case PERIOD_M15: return "M15";
      case PERIOD_M30: return "M30";
      case PERIOD_H1:  return "H1";
     }
   return "M15";  // fallback เผื่อ chart เปิด TF ที่ backtest_s420.py ไม่รองรับ
  }

//+------------------------------------------------------------------+
void ClearObjects()
  {
   int total = ObjectsTotal(0, 0, -1);
   for(int i = total - 1; i >= 0; i--)
     {
      string name = ObjectName(0, i, 0, -1);
      if(StringFind(name, OBJ_PREFIX) == 0)
         ObjectDelete(0, name);
     }
  }

//+------------------------------------------------------------------+
// ปุ่ม toggle เปิด/ปิดเส้นแต่ละกลุ่ม มุมขวาบนของชาร์ต — สร้างครั้งเดียวใน
// OnInit() (ไม่ถูกลบทิ้งตอน LoadAndDraw()/ClearObjects() เพราะชื่อขึ้นต้น
// BTN_PREFIX คนละ prefix กับเส้น/label ของไม้ที่ถูกลบทิ้งทุกรอบ redraw)
void CreateButton(string name, int row, string label, bool state)
  {
   if(ObjectFind(0, name) < 0)
      ObjectCreate(0, name, OBJ_BUTTON, 0, 0, 0);
   ObjectSetInteger(0, name, OBJPROP_CORNER, CORNER_LEFT_UPPER);
   ObjectSetInteger(0, name, OBJPROP_XDISTANCE, 10);
   ObjectSetInteger(0, name, OBJPROP_YDISTANCE, 20 + row * 24);
   ObjectSetInteger(0, name, OBJPROP_XSIZE, 90);
   ObjectSetInteger(0, name, OBJPROP_YSIZE, 20);
   ObjectSetInteger(0, name, OBJPROP_CORNER, CORNER_LEFT_UPPER);
   ObjectSetInteger(0, name, OBJPROP_FONTSIZE, 8);
   ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, name, OBJPROP_HIDDEN, true);  // ไม่โชว์ใน object list (Ctrl+B) กันรก
   ObjectSetInteger(0, name, OBJPROP_ZORDER, 100);
   ObjectSetString(0, name, OBJPROP_TEXT, label + (state ? ": ON" : ": OFF"));
   ObjectSetInteger(0, name, OBJPROP_BGCOLOR, state ? clrDarkGreen : clrDarkSlateGray);
   ObjectSetInteger(0, name, OBJPROP_COLOR, clrWhite);
  }

void CreateButtons()
  {
   CreateButton(BTN_PREFIX + "ORDER", 0, "Order", g_show_order);
   CreateButton(BTN_PREFIX + "TP", 1, "TP", g_show_tp);
   CreateButton(BTN_PREFIX + "SL", 2, "SL", g_show_sl);
  }

// เดินทุก object ของไม้ (ขึ้นต้น OBJ_PREFIX) แล้วซ่อน/โชว์ทั้งชุดของไม้นั้นตาม
// ผลลัพธ์จริง (TP/SL) ที่ฝังอยู่ใน object name เอง (ดู DrawTrade — tag มีคำว่า
// "_TP_"/"_SL_" กำกับผลไม้อยู่แล้ว) ไม่ใช่กรองตามชนิดเส้น — object ทุกชิ้นของ
// ไม้เดียวกัน (Entry/TP/SL/ลูกศร/label) จะโชว์หรือซ่อนพร้อมกันหมดเสมอ
// g_show_order เป็น master, AND กับ g_show_tp/g_show_sl ตามผลไม้นั้นอีกชั้น
// ด้วย OBJPROP_TIMEFRAMES (0 = ซ่อนทุก TF, OBJ_ALL_PERIODS = โชว์ปกติ) ไม่ลบ
// object ทิ้งจริง แค่ซ่อนไว้ — เร็วกว่า/กันปัญหา state หายตอน toggle ถี่ๆ
void ApplyVisibility()
  {
   int total = ObjectsTotal(0, 0, -1);
   int prefLen = StringLen(OBJ_PREFIX);
   for(int i = 0; i < total; i++)
     {
      string name = ObjectName(0, i, 0, -1);
      if(StringFind(name, OBJ_PREFIX) != 0)
         continue;
      // ดึง outcome token ตรงตำแหน่ง ("_" ตัวที่ 1 และ 2 หลัง prefix+idx) แทน
      // การหา "_TP_"/"_SL_" แบบ substring ทั่วทั้งชื่อ — object ชนิด label ของ
      // เส้น TP ("..._SL_TP_LBL" สำหรับไม้ผลลัพธ์ SL) มีคำว่า "_TP_" ปนอยู่ด้วย
      // จากส่วนต่อท้าย "_LBL" ทำให้ substring search แบบเดิมจับผิดกลุ่ม (เช่น
      // label ราคา TP ของไม้ที่ออก SL ไม่ยอมหายไปตอนกดปิดปุ่ม SL)
      bool outcome_show = true;
      int u1 = StringFind(name, "_", prefLen);
      int u2 = (u1 >= 0) ? StringFind(name, "_", u1 + 1) : -1;
      if(u2 > u1)
        {
         string outcome_tok = StringSubstr(name, u1 + 1, u2 - u1 - 1);
         if(outcome_tok == "TP")
            outcome_show = g_show_tp;
         else if(outcome_tok == "SL")
            outcome_show = g_show_sl;
        }
      bool show = g_show_order && outcome_show;
      ObjectSetInteger(0, name, OBJPROP_TIMEFRAMES, show ? (long)OBJ_ALL_PERIODS : 0);
     }
   ChartRedraw(0);
  }

//+------------------------------------------------------------------+
// วาดเส้น 1 เส้น (entry/tp/sl) พร้อม label "N. <kind> <price>" ต่อท้ายด้วย
// "  P&L=<profit>" เฉพาะเส้นที่ตรงกับ outcome จริง (is_exit_line=true)
void DrawLevelLine(string tag, string kind, datetime t1, datetime t2, double price,
                    color clr, int width, bool dashed, int idx,
                    bool is_exit_line, double profit)
  {
   string name = tag + kind;
   ObjectCreate(0, name, OBJ_TREND, 0, t1, price, t2, price);
   ObjectSetInteger(0, name, OBJPROP_COLOR, clr);
   ObjectSetInteger(0, name, OBJPROP_WIDTH, width);
   if(dashed)
      ObjectSetInteger(0, name, OBJPROP_STYLE, STYLE_DASH);
   ObjectSetInteger(0, name, OBJPROP_RAY_RIGHT, false);
   ObjectSetInteger(0, name, OBJPROP_RAY_LEFT, false);
   ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);

   if(!InpShowLabel)
      return;
   string txt = StringFormat("%d. %s %.2f", idx, kind, price);
   if(is_exit_line)
      txt += StringFormat("  P&L=%.2f", profit);
   string name_lbl = name + "_LBL";
   ObjectCreate(0, name_lbl, OBJ_TEXT, 0, t2, price);
   ObjectSetString(0, name_lbl, OBJPROP_TEXT, txt);
   ObjectSetInteger(0, name_lbl, OBJPROP_COLOR, is_exit_line ? (profit >= 0.0 ? clrLime : clrRed) : clr);
   ObjectSetInteger(0, name_lbl, OBJPROP_FONTSIZE, 8);
   ObjectSetInteger(0, name_lbl, OBJPROP_ANCHOR, ANCHOR_LEFT);
   ObjectSetInteger(0, name_lbl, OBJPROP_SELECTABLE, false);
  }

//+------------------------------------------------------------------+
// ไล่แท่งจริงบนชาร์ตทีละแท่งจาก entry ไปทางขวา หาแท่งแรกที่ high/low แตะ
// tp หรือ sl จริง (ใช้ราคาจริงจากชาร์ต ไม่ใช่ exit_time ที่ backtest คำนวณ
// มา ซึ่งอาจไม่ตรงกับแท่งจริงเป๊ะเพราะ convention fill/exit ต่างกันเล็กน้อย)
// คืน bar index ที่เจอ (-1 ถ้าไล่จนสุด limit แล้วไม่เจอ) ผ่าน out_hit_tp/out_hit_sl
int FindExitBar(int entry_bar, string direction, double sl, double tp,
                 string outcome, bool &out_hit_tp, bool &out_hit_sl)
  {
   bool isBuy = (direction == "BUY");
   int limit = 2000;  // กันไล่ไม่มีที่สิ้นสุดถ้าไม่เคยแตะเลย (เช่น TF เปลี่ยนทำให้ราคาเพี้ยน)
   int oldest = (int)MathMax(0, entry_bar - limit);
   for(int b = entry_bar - 1; b >= oldest; b--)  // index น้อยกว่า = เวลาใหม่กว่า (ทางขวา)
     {
      double h = iHigh(_Symbol, _Period, b);
      double l = iLow(_Symbol, _Period, b);
      bool touchTP = isBuy ? (h >= tp) : (l <= tp);
      bool touchSL = isBuy ? (l <= sl) : (h >= sl);
      if(!touchTP && !touchSL)
         continue;
      if(touchTP && touchSL)
        {
         // แตะทั้งคู่ในแท่งเดียว (gap/แท่งผันผวนแรง) — ไม่รู้ลำดับจริงภายในแท่ง
         // ยึดตามผลที่ backtest ตัดสินมาแล้ว (outcome จาก CSV) แทนการเดา
         out_hit_tp = (outcome == "TP");
         out_hit_sl = (outcome == "SL");
        }
      else
        {
         out_hit_tp = touchTP;
         out_hit_sl = touchSL;
        }
      return b;
     }
   return -1;
  }

//+------------------------------------------------------------------+
void DrawTrade(int idx, datetime signal_t, datetime entry_t, datetime exit_t, string direction,
               double entry, double sl, double tp, string outcome, double profit)
  {
   int entry_bar = iBarShift(_Symbol, _Period, entry_t, false);
   if(entry_bar < 0)
      return;  // ไม่มีแท่งในช่วงเวลานี้บนชาร์ต (ประวัติไม่ถึง หรือ TF ไม่ตรง)

   // เส้นเริ่มจากแท่งที่ pattern match/วาง order จริง (signal_t) ไม่ใช่แท่ง fill
   // (entry_t) — ถ้าหาแท่ง signal บนชาร์ตไม่เจอ (ประวัติไม่ถึง) fallback ไปแท่ง
   // fill แทน — ราคาที่ตรวจ TP/SL ยังคงเริ่มนับจากแท่ง fill จริงเสมอ (entry_bar)
   // เพราะ TP/SL เป็นไปไม่ได้ที่จะโดนก่อนไม้ fill จริง
   int signal_bar = iBarShift(_Symbol, _Period, signal_t, false);
   datetime t1 = (signal_bar >= 0) ? iTime(_Symbol, _Period, signal_bar) : iTime(_Symbol, _Period, entry_bar);

   // หาแท่งที่ราคาจริงบนชาร์ตแตะ TP/SL ก่อน (แม่นกว่า exit_time ที่ backtest
   // คำนวณมา) ถ้าไล่ไม่เจอเลย (เช่น ประวัติชาร์ตไม่ยาวพอ) ค่อย fallback ไปใช้
   // exit_time จาก CSV แล้วสุดท้ายค่อย fallback เป็น InpBarsExtend แท่ง
   bool hitTP = false, hitSL = false;
   int hit_bar = FindExitBar(entry_bar, direction, sl, tp, outcome, hitTP, hitSL);
   datetime t2;
   if(hit_bar >= 0)
      t2 = iTime(_Symbol, _Period, hit_bar);
   else
     {
      hitTP = (outcome == "TP");
      hitSL = (outcome == "SL");
      int exit_bar = iBarShift(_Symbol, _Period, exit_t, false);
      if(exit_bar >= 0 && exit_bar < entry_bar)
         t2 = iTime(_Symbol, _Period, exit_bar);
      else
        {
         int end_bar = (int)MathMax(0, entry_bar - InpBarsExtend);
         t2 = iTime(_Symbol, _Period, end_bar);
         if(t2 <= t1)
            t2 = t1 + PeriodSeconds(_Period) * InpBarsExtend;
        }
     }

   // outcome ฝังอยู่ใน tag เอง ("_TP_"/"_SL_") เพื่อให้ ApplyVisibility() ซ่อน/
   // โชว์ object ทุกชิ้นของไม้นี้ (Entry/TP/SL/ลูกศร/label) พร้อมกันตามผลจริง
   string tag = OBJ_PREFIX + IntegerToString(idx) + "_" + outcome + "_";

   DrawLevelLine(tag, "Entry", t1, t2, entry, InpColorEntry, 2, false, idx, false, profit);
   DrawLevelLine(tag, "TP", t1, t2, tp, InpColorTP, hitTP ? 2 : 1, !hitTP, idx, hitTP, profit);
   DrawLevelLine(tag, "SL", t1, t2, sl, InpColorSL, hitSL ? 2 : 1, !hitSL, idx, hitSL, profit);

   ObjectSetString(0, tag + "Entry", OBJPROP_TOOLTIP, StringFormat("S420 #%d %s entry=%.2f outcome=%s P&L=%.2f",
                   idx, direction, entry, outcome, profit));

   // ลูกศรเข้าไม้ (built-in order-arrow object เหมือนไม้จริงบนชาร์ต MT5) — วางที่
   // แท่ง fill จริง (entry_bar) เสมอ ไม่ใช่แท่ง signal (t1) เพราะลูกศรควรบอก
   // "ไม้เข้าจริงตรงนี้" แยกจากเส้นระดับที่ลากยาวย้อนไปถึงจุด pattern match
   bool isBuy = (direction == "BUY");
   string name_arrow = tag + "ARROW";
   ObjectCreate(0, name_arrow, isBuy ? OBJ_ARROW_BUY : OBJ_ARROW_SELL, 0, iTime(_Symbol, _Period, entry_bar), entry);
   ObjectSetInteger(0, name_arrow, OBJPROP_COLOR, isBuy ? clrDodgerBlue : clrOrange);
   ObjectSetInteger(0, name_arrow, OBJPROP_WIDTH, 2);
   ObjectSetInteger(0, name_arrow, OBJPROP_SELECTABLE, false);
  }

//+------------------------------------------------------------------+
// อ่าน field ถัดไปจากไฟล์ CSV ที่เปิดด้วย FILE_CSV — คืน "" ถ้าจบไฟล์/แถว
string ReadField(int handle)
  {
   if(FileIsEnding(handle))
      return "";
   return FileReadString(handle);
  }

//+------------------------------------------------------------------+
bool LoadAndDraw()
  {
   string fname = (InpFileOverride != "") ? InpFileOverride : ("s420_trades_" + TFSuffix() + ".csv");
   g_file_name = fname;

   if(!FileIsExist(fname, 0))
     {
      Comment("backtest_S420: ไม่พบไฟล์ " + fname + " ใน MQL5\\Files "
              "(รัน backtest_s420.py --tf " + TFSuffix() + " ก่อน — สคริปต์จะ copy CSV มาที่นี่ให้อัตโนมัติ)");
      Print("backtest_S420: ไม่พบไฟล์ ", fname);
      return false;
     }

   int handle = FileOpen(fname, FILE_READ | FILE_CSV | FILE_ANSI, ',');
   if(handle == INVALID_HANDLE)
     {
      Print("backtest_S420: เปิดไฟล์ไม่สำเร็จ ", fname, " err=", GetLastError());
      return false;
     }

   ClearObjects();
   Comment("");

   // ข้าม header แถวแรก — backtest_s420.py เขียน 15 คอลัมน์เสมอ
   // (entry_time,exit_time,direction,entry,sl,tp,outcome,profit,pattern,reason,
   //  entry_time_raw,exit_time_raw,signal_time,signal_time_raw,tf) — ใช้
   //  entry_time_raw/exit_time_raw/signal_time_raw (raw MT5 epoch ดิบจาก broker
   //  เดียวกัน) แทนการแปลง BKK string เอง เพราะ raw epoch จาก broker เดียวกัน
   //  ตรงกับ iTime() ของ terminal นี้เป๊ะเสมอ ไม่ต้องเดา/hardcode offset ต่อ
   //  broker เลย (กันพลาดแบบ -1h/-6h ที่เจอมาก่อน) signal_time_raw = แท่งที่
   //  pattern match/วาง pending order จริง (ใช้เป็นจุดเริ่มลากเส้น ต่างจาก
   //  entry_time_raw ที่เป็นแท่ง fill จริง) คอลัมน์ tf ท้ายสุดไม่ได้ใช้ (เลือก
   //  TF จาก _Period ของชาร์ตเองอยู่แล้ว) แต่ต้องอ่านทิ้งให้ครบทุกคอลัมน์
   for(int c = 0; c < 15 && !FileIsEnding(handle); c++)
      FileReadString(handle);

   int count = 0;
   while(!FileIsEnding(handle))
     {
      string entry_time_s = ReadField(handle);
      if(entry_time_s == "" && FileIsEnding(handle))
         break;
      string exit_time_s  = ReadField(handle);
      string direction    = ReadField(handle);
      double entry         = StringToDouble(ReadField(handle));
      double sl            = StringToDouble(ReadField(handle));
      double tp            = StringToDouble(ReadField(handle));
      string outcome       = ReadField(handle);
      double profit         = StringToDouble(ReadField(handle));
      string pattern       = ReadField(handle);
      string reason        = ReadField(handle);
      datetime entry_t     = (datetime)StringToInteger(ReadField(handle));  // entry_time_raw
      datetime exit_t      = (datetime)StringToInteger(ReadField(handle));  // exit_time_raw
      ReadField(handle);  // signal_time (string อ่านง่าย) — อ่านทิ้ง ใช้ raw แทน
      datetime signal_t    = (datetime)StringToInteger(ReadField(handle));  // signal_time_raw
      ReadField(handle);  // คอลัมน์ tf ท้ายสุด — อ่านทิ้ง

      DrawTrade(count, signal_t, entry_t, exit_t, direction, entry, sl, tp, outcome, profit);
      count++;
     }
   FileClose(handle);

   g_last_file_mtime = (datetime)FileGetInteger(fname, FILE_MODIFY_DATE);
   Print("backtest_S420: วาดไม้จาก ", fname, " จำนวน ", count, " ไม้ (TF=", TFSuffix(), ")");
   ApplyVisibility();  // ไม้ใหม่ทุกตัวต้องเคารพสถานะปุ่ม toggle ปัจจุบันด้วย
   ChartRedraw(0);
   return true;
  }

//+------------------------------------------------------------------+
int OnInit()
  {
   IndicatorSetString(INDICATOR_SHORTNAME, "backtest_S420 (" + TFSuffix() + ")");
   CreateButtons();
   LoadAndDraw();
   if(InpRefreshSec > 0)
      EventSetTimer(InpRefreshSec);
   return(INIT_SUCCEEDED);
  }

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   EventKillTimer();
   ClearObjects();
   ObjectDelete(0, BTN_PREFIX + "ORDER");
   ObjectDelete(0, BTN_PREFIX + "TP");
   ObjectDelete(0, BTN_PREFIX + "SL");
   Comment("");
  }

//+------------------------------------------------------------------+
void OnChartEvent(const int id, const long &lparam, const double &dparam, const string &sparam)
  {
   if(id != CHARTEVENT_OBJECT_CLICK)
      return;
   bool changed = false;
   if(sparam == BTN_PREFIX + "ORDER")
     {
      g_show_order = !g_show_order;
      CreateButton(BTN_PREFIX + "ORDER", 0, "Order", g_show_order);
      changed = true;
     }
   else if(sparam == BTN_PREFIX + "TP")
     {
      g_show_tp = !g_show_tp;
      CreateButton(BTN_PREFIX + "TP", 1, "TP", g_show_tp);
      changed = true;
     }
   else if(sparam == BTN_PREFIX + "SL")
     {
      g_show_sl = !g_show_sl;
      CreateButton(BTN_PREFIX + "SL", 2, "SL", g_show_sl);
      changed = true;
     }
   if(changed)
     {
      ObjectSetInteger(0, sparam, OBJPROP_STATE, false);  // กันปุ่มค้างสถานะ "กดอยู่"
      ApplyVisibility();
     }
  }

//+------------------------------------------------------------------+
void OnTimer()
  {
   string fname = (InpFileOverride != "") ? InpFileOverride : ("s420_trades_" + TFSuffix() + ".csv");
   if(!FileIsExist(fname, 0))
      return;
   datetime mtime = (datetime)FileGetInteger(fname, FILE_MODIFY_DATE);
   if(mtime != g_last_file_mtime)
      LoadAndDraw();
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
