import glob
import os

files = glob.glob("profiles/**/run_supervised.bat", recursive=True)
print(f"Found {len(files)} files")

for f in files:
    norm_path = f.replace("\\", "/")
    parts = norm_path.split("/")
    prof_folder = [p for p in parts if "-" in p][0]

    lines = [
        "@echo off",
        "chcp 65001 >nul",
        r'cd /d "%~dp0..\..\..\.."',
        f"set BOT_PROFILE={prof_folder}",
        r"for /f \"delims=\" %%T in ('python get_profile_title.py %BOT_PROFILE%') do title %%T",
        "echo ==================================",
        f"echo   Copter Gold Bot - {prof_folder}",
        "echo   (auto-restart on crash / hang)",
        "echo ==================================",
        "python notify_start.py",
        r'powershell -ExecutionPolicy Bypass -NoProfile -File "%CD%\run_supervised.ps1" -Profile %BOT_PROFILE%',
        "pause",
        ""
    ]
    
    # fix batch escaping for for /f
    batch_lines = []
    for line in lines:
        if "for /f" in line:
            batch_lines.append("for /f \"delims=\" %%T in ('python get_profile_title.py %BOT_PROFILE%') do title %%T")
        else:
            batch_lines.append(line)

    with open(f, "w", encoding="utf-8", newline="\r\n") as fp:
        fp.write("\r\n".join(batch_lines))
    print(f"Updated: {f}")
