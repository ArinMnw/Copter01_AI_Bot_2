"""
pybootstrap.py — auto re-exec ไป interpreter ที่มี MetaTrader5 ครบ

ปัญหา: `python` บน PATH อาจไปชี้ venv ของเครื่องมืออื่น (เช่น hermes-agent)
ที่ไม่มี MetaTrader5 ติดตั้งไว้ ขณะที่ `py -3`/`py` ชี้ไป interpreter ตัวจริง
ของบอท — ใช้ฟังก์ชันนี้ที่บรรทัดแรกๆ ของ CLI script ใดๆ ที่ต้องใช้ MT5
ก่อน import config/mt5_worker เพื่อให้รันด้วย `python script.py ...` ตรงๆ ได้
โดยไม่ต้องจำว่าต้องพิมพ์ `py -3` เอง

Usage:
    import pybootstrap; pybootstrap.ensure_mt5()
    import config   # ปลอดภัยแล้ว
"""
import os
import sys
import subprocess

_REEXEC_ENV = "_PYBOOTSTRAP_REEXEC"


def ensure_mt5():
    if os.environ.get(_REEXEC_ENV) == "1":
        return
    try:
        import MetaTrader5  # noqa: F401
        return
    except ModuleNotFoundError:
        pass

    main_file = os.path.abspath(sys.modules["__main__"].__file__)
    env = dict(os.environ, **{_REEXEC_ENV: "1"})
    for exe, extra_args in [("py", ["-3"]), ("py", [])]:
        try:
            probe = subprocess.run(
                [exe, *extra_args, "-c", "import MetaTrader5, sys; print(sys.executable)"],
                capture_output=True, text=True,
            )
        except (OSError, FileNotFoundError):
            continue
        real_exe = probe.stdout.strip()
        if probe.returncode == 0 and os.path.isfile(real_exe):
            # ใช้ subprocess.run แทน os.execve — os.execve segfault บน Windows
            # กับบาง interpreter build (พบกับ uv-managed venv python)
            result = subprocess.run([real_exe, main_file, *sys.argv[1:]], env=env)
            sys.exit(result.returncode)

    print("ERROR: ไม่พบ Python interpreter ที่มี MetaTrader5 ติดตั้งไว้ "
          "(ลองรันด้วย 'py -3 ...' ตรงๆ)")
    sys.exit(1)
