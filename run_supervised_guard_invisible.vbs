' run_supervised_guard_invisible.vbs
' ใช้แทนการเรียก powershell.exe -WindowStyle Hidden ตรงๆ จาก Scheduled Task —
' แม้ตั้ง WindowStyle Hidden แล้ว บางเครื่อง (โดยเฉพาะ Windows 11 ที่ตั้ง Windows
' Terminal เป็น default terminal) ยังเห็นหน้าต่างกระพริบสั้นๆ ตอน powershell.exe
' เริ่มโหลด ก่อนที่ Hidden style จะมีผล — wscript.exe ไม่มี console/window ของ
' ตัวเองเลย แล้วสั่งรันผ่าน WshShell.Run windowStyle=0 จะไม่กระพริบเลยแม้แต่นิดเดียว
Dim objShell, profileArg, cmd

Set objShell = CreateObject("WScript.Shell")

profileArg = ""
If WScript.Arguments.Count > 0 Then
    profileArg = " -Profile " & WScript.Arguments(0)
End If

cmd = "powershell.exe -ExecutionPolicy Bypass -NoProfile -WindowStyle Hidden -File ""D:\Project\Copter01_AI_Bot_2\run_supervised_guard.ps1""" & profileArg

' 0 = ซ่อนหน้าต่างสนิท, True = รอให้จบก่อนค่อยจบ vbs (กันซ้อนกันเองถ้า task ยิงถี่)
objShell.Run cmd, 0, True
