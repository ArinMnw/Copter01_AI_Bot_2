//+------------------------------------------------------------------+
//|                                                   HHLL_Lib.mqh   |
//|  พอร์ต pivot HH/HL/LH/LL logic จาก HHLLStrategy.mq5 มาเป็น library  |
//|  ใช้ร่วมกันใน EA/indicator หลายตัว (#include "HHLL_Lib.mqh")        |
//+------------------------------------------------------------------+
#ifndef __HHLL_LIB_MQH__
#define __HHLL_LIB_MQH__

struct HHLLZZPt
  {
   double   price;
   datetime t;
   int      idx;   // ตำแหน่งใน array ต้นทาง (ascending, 0 = เก่าสุด)
   int      dir;   // +1 = pivot high, -1 = pivot low
  };

//+------------------------------------------------------------------+
bool HHLL_IsPH(const double &high[], const int i, const int lb, const int rb, const int n)
  {
   if(i - lb < 0 || i + rb >= n)
      return(false);
   double h = high[i];
   for(int j = i - lb; j < i; j++)
      if(high[j] >= h) return(false);
   for(int j = i + 1; j <= i + rb; j++)
      if(high[j] > h) return(false);
   return(true);
  }

bool HHLL_IsPL(const double &low[], const int i, const int lb, const int rb, const int n)
  {
   if(i - lb < 0 || i + rb >= n)
      return(false);
   double l = low[i];
   for(int j = i - lb; j < i; j++)
      if(low[j] <= l) return(false);
   for(int j = i + 1; j <= i + rb; j++)
      if(low[j] < l) return(false);
   return(true);
  }

//+------------------------------------------------------------------+
// สร้าง zigzag จาก high/low/time (ascending, 0=เก่าสุด) ช่วง [fromIdx, n)
// fromIdx ใช้จำกัดขอบเขตการสแกน (กันสแกนย้อนหลังทั้งประวัติทุกครั้งที่ recalculate — ช้ามาก/ค้าง)
int HHLL_BuildZZ(const double &high[], const double &low[], const datetime &time[],
                  const int n, const int left, const int right, HHLLZZPt &zz[],
                  const int fromIdx = 0)
  {
   ArrayResize(zz, MathMax(n - fromIdx, 0));
   int cnt = 0;
   int startI = MathMax(left, fromIdx);
   for(int i = startI; i < n - right; i++)
     {
      bool ph = HHLL_IsPH(high, i, left, right, n);
      bool pl = HHLL_IsPL(low, i, left, right, n);
      if(!ph && !pl)
         continue;

      if(ph && pl)
        {
         if(cnt > 0 && zz[cnt - 1].dir == 1)
            ph = false;
         else
            pl = false;
        }

      double p = ph ? high[i] : low[i];
      int    d = ph ? 1 : -1;

      if(cnt > 0 && zz[cnt - 1].dir == d)
        {
         if(d == 1 && p < zz[cnt - 1].price)
            continue;
         if(d == -1 && p > zz[cnt - 1].price)
            continue;
        }

      if(cnt > 0)
        {
         if(d == -1 && p > zz[cnt - 1].price)
            continue;
         if(d == 1 && p < zz[cnt - 1].price)
            continue;
        }

      zz[cnt].price = p;
      zz[cnt].t     = time[i];
      zz[cnt].idx   = i;
      zz[cnt].dir   = d;
      cnt++;
     }
   ArrayResize(zz, cnt);
   return(cnt);
  }

//+------------------------------------------------------------------+
// จัดประเภทจุด zigzag ลำดับที่ k เป็น "HH" | "HL" | "LH" | "LL" | ""
string HHLL_ClassifyPt(const HHLLZZPt &zz[], const int k)
  {
   if(k < 4)
      return("");

   double a   = zz[k].price;
   int    ad  = zz[k].dir;
   int    opp = -ad;

   double b = 0, c = 0, d = 0, e = 0;
   int step = 0, need = opp;
   for(int j = k - 1; j >= 0 && step < 4; j--)
     {
      if(zz[j].dir != need)
         continue;
      switch(step)
        {
         case 0: b = zz[j].price; need = ad;  break;
         case 1: c = zz[j].price; need = opp; break;
         case 2: d = zz[j].price; need = ad;  break;
         case 3: e = zz[j].price;             break;
        }
      step++;
     }
   if(step < 4)
      return("");

   bool is_hh = (a > b) && (a > c) && (c > b) && (c > d);
   bool is_ll = (a < b) && (a < c) && (c < b) && (c < d);
   bool is_hl = ((a >= c && b > c && b > d && d > c && d > e) ||
                 (a < b && a > c && b < d));
   bool is_lh = ((a <= c && b < c && b < d && d < c && d < e) ||
                 (a > b && a < c && b > d));

   if(is_hh) return("HH");
   if(is_ll) return("LL");
   if(is_hl) return("HL");
   if(is_lh) return("LH");
   return("");
  }

//+------------------------------------------------------------------+
// สำหรับ EA: เช็คว่าแท่งที่เพิ่งปิดล่าสุด (shift=1) เพิ่ง confirm pivot ใหม่หรือไม่
// คืน true + outLabel="HH"/"HL"/"LH"/"LL" ถ้าใช่ (ใช้ CopyRates ดึงเฉพาะแท่งที่ปิดแล้ว)
// หมายเหตุ: คืน true ทุก label ที่จัดประเภทได้ — ผู้เรียกเป็นคนกรองว่า label ไหนใช้ปิดฝั่งไหน
bool HHLL_CheckNewPivot(const string symbol, const ENUM_TIMEFRAMES period,
                         const int left, const int right, const int lookback,
                         string &outLabel)
  {
   outLabel = "";
   int copy_n = lookback + left + right + 5;
   MqlRates rates[];
   int copied = CopyRates(symbol, period, 1, copy_n, rates); // shift=1 กันแท่งที่ยังไม่ปิด
   if(copied < left + right + 10)
      return(false);

   double   high[], low[];
   datetime t[];
   ArrayResize(high, copied);
   ArrayResize(low,  copied);
   ArrayResize(t,    copied);
   for(int k = 0; k < copied; k++)
     {
      high[k] = rates[k].high;
      low[k]  = rates[k].low;
      t[k]    = rates[k].time;
     }

   int target = copied - 1 - right;
   if(target < left)
      return(false);

   bool isPH = HHLL_IsPH(high, target, left, right, copied);
   bool isPL = HHLL_IsPL(low,  target, left, right, copied);
   if(!isPH && !isPL)
      return(false);

   HHLLZZPt zz[];
   int zz_n = HHLL_BuildZZ(high, low, t, copied, left, right, zz);
   if(zz_n == 0 || zz[zz_n - 1].idx != target)
      return(false); // ถูก filter ออก (consecutive-extreme / wrong-side ตาม BuildZZ)

   outLabel = HHLL_ClassifyPt(zz, zz_n - 1);
   return(outLabel != "");
  }

//+------------------------------------------------------------------+
// สำหรับ indicator: build zigzag จาก array ของ OnCalculate ครั้งเดียว
// แล้วคืน isHH[]/isHL[]/isLH[]/isLL[] บอกว่าแท่งไหน (index ตรงกับ high[]/low[]/time[]) "ยืนยัน" pivot อะไร
//
// ⚠️ สำคัญ: flag ถูกวางไว้ที่บาร์ idx+right (บาร์ที่ "รู้แน่ชัด" ว่าเป็น pivot แล้ว)
// ไม่ใช่ที่บาร์ยอด/ก้นจริง (idx) — เพื่อไม่ให้ repaint/look-ahead ผิดจาก EA จริง
// ซึ่งต้องรอ right แท่งถัดไปปิดก่อนถึงจะยืนยัน pivot ได้เหมือนกัน (ดู HHLL_CheckNewPivot)
//
// ⚠️ lookback จำกัดขอบเขตสแกนไว้ที่ N แท่งล่าสุดเท่านั้น (ไม่ใช่ทั้งประวัติ) — สำคัญมาก
// เพราะฟังก์ชันนี้ถูกเรียกทุกครั้งที่ OnCalculate ทำงาน (แทบทุก tick) ถ้าสแกนทั้งประวัติ
// บนกราฟที่มีข้อมูลหลายแสนแท่ง จะทำให้ terminal ค้าง/หน่วงหนักมาก โดยเฉพาะตอนเปลี่ยน TF
void HHLL_MarkPivots(const double &high[], const double &low[], const datetime &time[],
                      const int n, const int left, const int right, const int lookback,
                      bool &isHH[], bool &isHL[], bool &isLH[], bool &isLL[])
  {
   ArrayResize(isHH, MathMax(n, 1));
   ArrayResize(isHL, MathMax(n, 1));
   ArrayResize(isLH, MathMax(n, 1));
   ArrayResize(isLL, MathMax(n, 1));
   ArrayInitialize(isHH, false);
   ArrayInitialize(isHL, false);
   ArrayInitialize(isLH, false);
   ArrayInitialize(isLL, false);

   if(n <= 0)
      return;

   int fromIdx = (lookback > 0) ? MathMax(0, n - (lookback + left + right)) : 0;

   HHLLZZPt zz[];
   int zz_n = HHLL_BuildZZ(high, low, time, n, left, right, zz, fromIdx);
   for(int k = 0; k < zz_n; k++)
     {
      string lbl = HHLL_ClassifyPt(zz, k);
      if(lbl == "")
         continue;

      int confirmIdx = zz[k].idx + right; // บาร์ที่ยืนยันได้จริง (มี right แท่งปิดแล้วหลังจุดยอด/ก้น)
      if(confirmIdx < 0 || confirmIdx >= n)
         continue;

      if(lbl == "HH")
         isHH[confirmIdx] = true;
      else if(lbl == "HL")
         isHL[confirmIdx] = true;
      else if(lbl == "LH")
         isLH[confirmIdx] = true;
      else if(lbl == "LL")
         isLL[confirmIdx] = true;
     }
  }

#endif
