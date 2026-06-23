import os

header = """# [แนบเนื้อหาไฟล์ .md ของคุณตรงนี้]

---
### INSTRUCTIONS FOR THE MODEL (CRITICAL) ###
[คำสั่งห้ามย่อ]: คุณต้องอ่านเนื้อหาในไฟล์ .md ด้านบนทั้งหมดอย่างครบถ้วน 100% ห้ามทำการสรุปแบบย่อ (No Summarization) และห้ามตัดทอนข้อความใดๆ ทิ้งเด็ดขาด
[การประมวลผลข้อมูล]: ให้ใช้วิธีแจกแจงแบบ "หัวข้อต่อหัวข้อ" ตามโครงสร้างเดิมของไฟล์ด้านบน หากในเอกสารมีทั้งหมด X หัวข้อ คุณต้องรายงานกลับมาให้ครบทั้ง X หัวข้อ
[เทคนิคการสกัดข้อมูล]: ห้ามข้ามเนื้อหาที่อยู่ส่วนกลางและส่วนท้ายของเอกสาร จงใช้ความละเอียดสูงสุดในการถอดรายละเอียด (Economy of expression with highest information density)
[การทบทวนตัวเอง]: ก่อนที่คุณจะแสดงคำตอบเสร็จสิ้น ให้ตรวจสอบตัวเองอีกครั้ง (Double-check) ว่ามีประเด็นไหนตกหล่นไปจากไฟล์ต้นฉบับหรือไม่ หากมีให้นำกลับมาเขียนเพิ่มให้สมบูรณ์ก่อนส่งคำตอบ

"""

for root, dirs, files in os.walk('d:/Project/Copter01_AI_Bot_2/docs/allin4s'):
    for file in files:
        if file.endswith('.md'):
            file_path = os.path.join(root, file)
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                if content.startswith(header):
                    content = content.replace(header, '', 1)
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(content)
            except Exception as e:
                pass
