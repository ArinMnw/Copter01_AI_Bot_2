//+------------------------------------------------------------------+
//|                                                    DumpGeno.mq5   |
//|  Script: เรียก GenoSmartSignal ด้วย iCustom (ค่า default) แล้ว dump  |
//|  ค่า buffer จริงของ H1 และ M5 ออก CSV ใน MQL5\Files เพื่อเทียบกับ    |
//|  Python (mq5_strategy/indi1/compare_geno_buffers.py)               |
//|  วิธีใช้: ลาก script นี้ไปวางบนชาร์ตของ symbol ที่ต้องการ (เช่น      |
//|  XAUUSDm) แล้วรอข้อความ "DumpGeno done" ใน Experts log              |
//+------------------------------------------------------------------+
#property script_show_inputs
#property strict

input int InpBars = 1200;   // จำนวนแท่งล่าสุดที่ dump ต่อ TF

#define NBUF 10
struct BufArr { double v[]; };
int g_idx[NBUF] = {6, 7, 10, 11, 12, 13, 14, 15, 18, 19};
string g_nm[NBUF] = {"fl1", "fl1c", "fl2", "fl2c", "buy2", "sell2", "ker", "kerc", "swl", "swh"};

string Cell(const double v)
{
   if(v == EMPTY_VALUE || !MathIsValidNumber(v)) return "";
   return DoubleToString(v, 5);
}

bool DumpTF(const ENUM_TIMEFRAMES tf, const string tfname)
{
   int h = iCustom(_Symbol, tf, "GenoSmartSignal");
   if(h == INVALID_HANDLE) { Print("DumpGeno: iCustom failed ", tfname, " err=", GetLastError()); return false; }
   // รอให้ indicator คำนวณเสร็จ
   int need = Bars(_Symbol, tf), tries = 0;
   while(BarsCalculated(h) < need - 1 && tries < 120 && !IsStopped()) { Sleep(500); tries++; }
   int n = MathMin(InpBars, BarsCalculated(h) - 2);
   if(n < 50) { Print("DumpGeno: BarsCalculated too small for ", tfname); IndicatorRelease(h); return false; }

   MqlRates rt[];
   ArraySetAsSeries(rt, false);
   if(CopyRates(_Symbol, tf, 0, n, rt) != n) { Print("DumpGeno: CopyRates failed"); IndicatorRelease(h); return false; }
   BufArr buf[NBUF];
   for(int b = 0; b < NBUF; b++)
   {
      ArraySetAsSeries(buf[b].v, false);
      if(CopyBuffer(h, g_idx[b], 0, n, buf[b].v) != n) { Print("DumpGeno: CopyBuffer ", g_nm[b], " failed err=", GetLastError()); IndicatorRelease(h); return false; }
   }
   string fn = "geno_dump_" + tfname + ".csv";
   int f = FileOpen(fn, FILE_WRITE | FILE_CSV | FILE_ANSI, ',');
   if(f == INVALID_HANDLE) { Print("DumpGeno: FileOpen failed ", fn); IndicatorRelease(h); return false; }
   FileWrite(f, "time", "open", "high", "low", "close", "fl1", "fl1c", "fl2", "fl2c", "buy2", "sell2", "ker", "kerc", "swl", "swh");
   for(int i = 0; i < n; i++)
      FileWrite(f, (long)rt[i].time, DoubleToString(rt[i].open, 5), DoubleToString(rt[i].high, 5), DoubleToString(rt[i].low, 5), DoubleToString(rt[i].close, 5),
                Cell(buf[0].v[i]), Cell(buf[1].v[i]), Cell(buf[2].v[i]), Cell(buf[3].v[i]), Cell(buf[4].v[i]),
                Cell(buf[5].v[i]), Cell(buf[6].v[i]), Cell(buf[7].v[i]), Cell(buf[8].v[i]), Cell(buf[9].v[i]));
   FileClose(f);
   IndicatorRelease(h);
   PrintFormat("DumpGeno: %s wrote %d rows -> MQL5\\Files\\%s (BarsCalculated ok)", tfname, n, fn);
   return true;
}

void OnStart()
{
   bool a = DumpTF(PERIOD_H1, "H1");
   bool b = DumpTF(PERIOD_M5, "M5");
   Print("DumpGeno done: H1=", a, " M5=", b, " symbol=", _Symbol);
   Alert("DumpGeno done: H1=", a, " M5=", b);
}
//+------------------------------------------------------------------+
