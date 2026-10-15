//+------------------------------------------------------------------+
//|                                                  Indi1_EA.mq5     |
//|  EA เทรดตามสัญญาณของ indicator GenoSmartSignal                    |
//|                                                                   |
//|  "3 เส้นเขียว" = Trend Line BB (Follow Line BB) + Trend Line MA   |
//|  (Follow Line MA) + Line 2 (Kernel) เป็นสีเขียวพร้อมกัน            |
//|  ฝั่ง Sell = แดงทั้ง 3 เส้น                                        |
//|                                                                   |
//|  กฎเข้า (Buy; Sell สลับด้าน):                                      |
//|   1) HTF (H1): แท่งที่ปิดล่าสุด 2 แท่งติดกัน 3 เส้นเขียวทั้งคู่       |
//|   2) LTF (M5): แท่ง T = "เกิด" 3 เส้นเขียวพร้อมกัน (แท่งก่อนหน้า     |
//|      ยังไม่ครบ) หรือเกิด Smart Buy                                 |
//|   3) แท่ง T+1 ปิดแล้ว 3 เส้นยังเขียว (หรือ Smart Buy ของ T ยังอยู่   |
//|      = Trend Line MA ยังเขียว) -> เข้า market ทันที                  |
//|   SL = swing ZigZag ล่าสุดของ LTF -/+ buffer, TP = RR x ระยะ SL,   |
//|   lot จาก Risk % ของ Balance (ตรรกะเดียวกับ Auto Lot ของ indicator) |
//|  Fibo breakeven: fib 50% ของ entry->TP, ถ้าแท่ง LTF ปิดเลย 50%      |
//|   -> เลื่อน SL ไป entry +/- 50 จุด                                  |
//|  เจอสัญญาณ HTF แล้วเข้าได้ 3 ไม้ (InpMaxEntriesPerH1) จนกว่า HTF จะ   |
//|  หายแล้วเกิดใหม่; ไม้ที่ 2-3 ต้องรอสัญญาณ LTF ใหม่ของแต่ละไม้           |
//|                                                                   |
//|  ถือหลายไม้พร้อมกันได้ (InpConcurrent) ไม่กลับด้านเมื่อสัญญาณตรงข้าม  |
//|  การติดตั้ง: คอมไพล์ GenoSmartSignal.mq5 ไว้ใน MQL5\Indicators ก่อน  |
//|  indicator ใช้ค่า default (Balance 10000 / Risk 1% / RR 2.5)       |
//+------------------------------------------------------------------+
#property copyright "Copter01 AI Bot"
#property version   "2.00"
#property tester_indicator "GenoSmartSignal.ex5"

#include <Trade\Trade.mqh>

input group "=== Timeframes ==="
input ENUM_TIMEFRAMES InpHTF         = PERIOD_H1;   // TF ใหญ่ (กรองทิศ)
input ENUM_TIMEFRAMES InpLTF         = PERIOD_M5;   // TF เล็ก (จังหวะเข้า)

input group "=== Direction ==="
input bool            InpAllowBuy    = true;        // เปิดฝั่ง Buy
input bool            InpAllowSell   = true;        // เปิดฝั่ง Sell
input int             InpMaxEntriesPerH1 = 3;       // เจอสัญญาณ HTF แล้วเข้าได้กี่ไม้ จนกว่าจะเกิดสัญญาณ HTF ใหม่ (0 = ไม่จำกัด)
input bool            InpConcurrent  = true;        // ถือหลายไม้พร้อมกันได้ (ไม้ใหม่ต้องรอสัญญาณ LTF ใหม่)
input int             InpMaxSpread   = 0;           // Spread สูงสุด (points, 0 = ไม่จำกัด)

input group "=== Risk (ทุนเริ่ม 10000, Risk 1%, R:R 2.5) ==="
input double          InpRiskPct     = 1.0;         // Risk % ต่อไม้ (ของ Balance)
input double          InpRR          = 2.5;         // R:R (TP = RR x ระยะ SL)
input int             InpSLBufTicks  = 100;         // buffer SL จาก swing (ticks)
input int             InpMinSLPoints = 0;           // ระยะ SL ขั้นต่ำ (points, 0 = ไม่จำกัด)

input group "=== Fibo breakeven ==="
input bool            InpUseBE       = true;        // เลื่อน SL เมื่อปิดเลย fibo 50%
input double          InpBEFib       = 0.5;         // ระดับ fibo ของ entry->TP
input int             InpBELockPts   = 50;          // SL ไปที่ entry +/- กี่ points

input group "=== General ==="
input long            InpMagic       = 20261014;    // Magic number
input int             InpSlippage    = 30;          // Slippage (points)
input string          InpComment     = "Indi1";     // Comment

CTrade   g_trade;
int      g_hL = INVALID_HANDLE, g_hH = INVALID_HANDLE;
datetime g_lastBar = 0;
int      g_cntBuy = 0, g_cntSell = 0;   // จำนวนไม้ที่เข้าไปแล้วในสัญญาณ HTF รอบนี้ (ไม่เก็บข้ามการรีสตาร์ท EA)

// buffer index ใน GenoSmartSignal
#define BUF_FL1    6    // Trend Line BB
#define BUF_FL1C   7
#define BUF_FL2    10   // Trend Line MA
#define BUF_FL2C   11
#define BUF_BUY2   12   // Smart Buy
#define BUF_SELL2  13   // Smart Sell
#define BUF_KER    14   // Line 2 (Kernel)
#define BUF_KERC   15
#define BUF_SWL    18   // swing low ล่าสุด
#define BUF_SWH    19   // swing high ล่าสุด

//+------------------------------------------------------------------+
int OnInit()
{
   g_hL = iCustom(_Symbol, InpLTF, "GenoSmartSignal");
   g_hH = iCustom(_Symbol, InpHTF, "GenoSmartSignal");
   if(g_hL == INVALID_HANDLE || g_hH == INVALID_HANDLE)
   {
      Print("iCustom GenoSmartSignal ล้มเหลว — ต้องคอมไพล์ indicator ไว้ใน MQL5\\Indicators ก่อน");
      return INIT_FAILED;
   }
   g_trade.SetExpertMagicNumber(InpMagic);
   g_trade.SetDeviationInPoints(InpSlippage);
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   if(g_hL != INVALID_HANDLE) IndicatorRelease(g_hL);
   if(g_hH != INVALID_HANDLE) IndicatorRelease(g_hH);
}

//+------------------------------------------------------------------+
double Buf(const int h, const int idx, const int shift)
{
   double a[1];
   if(CopyBuffer(h, idx, shift, 1, a) != 1) return EMPTY_VALUE;
   return a[0];
}

bool Has(const double v) { return v != EMPTY_VALUE && MathIsValidNumber(v); }

// เส้นเดียว: มีค่าและสี = green(index 0) / red(index 1)
bool LineIs(const int h, const int valIdx, const int colIdx, const int shift, const bool green)
{
   if(!Has(Buf(h, valIdx, shift))) return false;
   double c = Buf(h, colIdx, shift);
   if(!Has(c)) return false;
   return green ? (c < 0.5) : (c > 0.5);
}

// 3 เส้น (BB, MA, Line2) สีเดียวกันพร้อมกัน
bool All3(const int h, const int shift, const bool green)
{
   return LineIs(h, BUF_FL1, BUF_FL1C, shift, green)
       && LineIs(h, BUF_FL2, BUF_FL2C, shift, green)
       && LineIs(h, BUF_KER, BUF_KERC, shift, green);
}

bool SmartSig(const int shift, const bool buy)
{
   return Has(Buf(g_hL, buy ? BUF_BUY2 : BUF_SELL2, shift));
}

int CountPositions()
{
   int n = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong t = PositionGetTicket(i);
      if(t == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;
      n++;
   }
   return n;
}

double CalcLot(const double slDist)
{
   double vmin = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double vmax = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double vstep = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   double tickSize = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   double tickVal  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE_LOSS);
   if(tickSize <= 0 || tickVal <= 0 || slDist <= 0) return 0;
   double risk = AccountInfoDouble(ACCOUNT_BALANCE) * InpRiskPct / 100.0;
   double lot = risk / (slDist / tickSize * tickVal);
   lot = MathFloor(lot / vstep) * vstep;
   if(lot < vmin) return 0;           // ไม่พอขั้นต่ำ = ไม่เข้า (ไม่ฝืนเกิน risk)
   return MathMin(lot, vmax);
}

bool OpenTrade(const bool isBuy)
{
   double swing = Buf(g_hL, isBuy ? BUF_SWL : BUF_SWH, 1);
   if(!Has(swing)) { Print("ข้าม: ยังไม่มี swing ZigZag"); return false; }
   double pt = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   int digs = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   double buf = InpSLBufTicks * SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   double sl = isBuy ? swing - buf : swing + buf;

   MqlTick tk;
   if(!SymbolInfoTick(_Symbol, tk)) return false;
   double entry = isBuy ? tk.ask : tk.bid;
   double dist = MathAbs(entry - sl);

   if(isBuy ? sl >= entry : sl <= entry) { Print("ข้าม: SL อยู่ผิดฝั่ง sl=", sl, " entry=", entry); return false; }
   if(InpMinSLPoints > 0 && dist < InpMinSLPoints * pt) { Print("ข้าม: SL แคบกว่า MinSL"); return false; }
   long stops = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL);
   if(dist < stops * pt) { Print("ข้าม: SL ใกล้เกิน stops level"); return false; }
   if(InpMaxSpread > 0 && SymbolInfoInteger(_Symbol, SYMBOL_SPREAD) > InpMaxSpread) { Print("ข้าม: spread สูง"); return false; }

   double tp = isBuy ? entry + dist * InpRR : entry - dist * InpRR;
   double lot = CalcLot(dist);
   if(lot <= 0) { Print("ข้าม: lot คำนวณได้ต่ำกว่าขั้นต่ำ"); return false; }

   sl = NormalizeDouble(sl, digs);
   tp = NormalizeDouble(tp, digs);
   bool ok = isBuy ? g_trade.Buy(lot, _Symbol, 0, sl, tp, InpComment)
                   : g_trade.Sell(lot, _Symbol, 0, sl, tp, InpComment);
   if(!ok) Print("เปิดออเดอร์ไม่สำเร็จ retcode=", g_trade.ResultRetcode(), " ", g_trade.ResultRetcodeDescription());
   return ok;
}

//+------------------------------------------------------------------+
//| Fibo 50% ของ entry->TP: แท่ง LTF ปิดเลยระดับ -> SL = entry +/- lock |
//+------------------------------------------------------------------+
void ManageBreakeven(const ulong ticket)
{
   if(!InpUseBE || !PositionSelectByTicket(ticket)) return;
   datetime opened = (datetime)PositionGetInteger(POSITION_TIME);
   if(iTime(_Symbol, InpLTF, 1) + PeriodSeconds(InpLTF) <= opened) return;   // ใช้เฉพาะแท่งที่ปิดหลังเข้าไม้ (รวมแท่งที่เข้า)

   bool isBuy = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY);
   double entry = PositionGetDouble(POSITION_PRICE_OPEN);
   double tp = PositionGetDouble(POSITION_TP), sl = PositionGetDouble(POSITION_SL);
   if(tp <= 0) return;
   double level = entry + (tp - entry) * InpBEFib;
   double cls = iClose(_Symbol, InpLTF, 1);
   double pt = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   int digs = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);

   double newSL;
   if(isBuy)
   {
      if(cls <= level) return;
      newSL = NormalizeDouble(entry + InpBELockPts * pt, digs);
      if(sl > 0 && newSL <= sl) return;
      if(newSL >= SymbolInfoDouble(_Symbol, SYMBOL_BID)) return;
   }
   else
   {
      if(cls >= level) return;
      newSL = NormalizeDouble(entry - InpBELockPts * pt, digs);
      if(sl > 0 && newSL >= sl) return;
      if(newSL <= SymbolInfoDouble(_Symbol, SYMBOL_ASK)) return;
   }
   g_trade.PositionModify(ticket, newSL, tp);
}

//+------------------------------------------------------------------+
//| เรียกครั้งเดียวต่อแท่ง LTF ใหม่                                    |
//+------------------------------------------------------------------+
void OnNewBar()
{
   // สัญญาณ HTF (2 แท่งล่าสุดครบ 3 เส้น) หายเมื่อไหร่ = รีเซ็ตโควตาไม้ของฝั่งนั้น
   bool htfBuy  = All3(g_hH, 1, true)  && All3(g_hH, 2, true);
   bool htfSell = All3(g_hH, 1, false) && All3(g_hH, 2, false);
   if(!htfBuy)  g_cntBuy = 0;
   if(!htfSell) g_cntSell = 0;

   // Fibo breakeven ของทุกไม้ที่ถืออยู่
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong t = PositionGetTicket(i);
      if(t == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;
      ManageBreakeven(t);
   }
   if(!InpConcurrent && CountPositions() > 0) return;

   for(int side = 0; side < 2; side++)
   {
      bool buy = (side == 0);
      if(buy && !InpAllowBuy) continue;
      if(!buy && !InpAllowSell) continue;

      // 1) HTF: 2 แท่งที่ปิดล่าสุดสีเดียวกันครบ 3 เส้น
      if(!(buy ? htfBuy : htfSell)) continue;
      int used = buy ? g_cntBuy : g_cntSell;
      if(InpMaxEntriesPerH1 > 0 && used >= InpMaxEntriesPerH1) continue;

      // 2) LTF แท่ง T = shift 2: เพิ่งครบ 3 เส้นพร้อมกัน หรือเกิด Smart signal
      bool smartT = SmartSig(2, buy);
      bool newAll3 = All3(g_hL, 2, buy) && !All3(g_hL, 3, buy);
      if(!(newAll3 || smartT)) continue;

      // 3) แท่ง T+1 = shift 1 ปิดแล้วยังอยู่
      bool stillAll3 = All3(g_hL, 1, buy);
      bool stillSmart = smartT && LineIs(g_hL, BUF_FL2, BUF_FL2C, 1, buy);
      if(!(stillAll3 || stillSmart)) continue;

      if(OpenTrade(buy))
      {
         if(buy) g_cntBuy++; else g_cntSell++;
      }
      return;
   }
}

void OnTick()
{
   datetime t = iTime(_Symbol, InpLTF, 0);
   if(t == g_lastBar) return;
   if(BarsCalculated(g_hL) < 100 || BarsCalculated(g_hH) < 100) return;
   g_lastBar = t;
   OnNewBar();
}
//+------------------------------------------------------------------+
