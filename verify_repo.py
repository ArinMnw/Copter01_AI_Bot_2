from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent

DEFAULT_FILES = [
    "config.py",
    "scanner.py",
    "trailing.py",
    "mt5_utils.py",
    "notifications.py",
    "pending.py",
    "strategy1.py",
    "strategy2.py",
    "strategy3.py",
    "strategy4.py",
    "strategy5.py",
    "strategy8.py",
    "handlers/keyboard.py",
    "handlers/callback_handler.py",
]


def resolve_targets(args: list[str]) -> list[str]:
    if not args:
        return [str(ROOT / rel) for rel in DEFAULT_FILES if (ROOT / rel).exists()]

    targets: list[str] = []
    for raw in args:
        path = Path(raw)
        if not path.is_absolute():
            path = ROOT / path
        if path.exists() and path.is_file():
            targets.append(str(path))
    return targets


def run_step(title: str, command: list[str]) -> bool:
    print(f"\n== {title} ==")
    result = subprocess.run(command, cwd=ROOT)
    if result.returncode == 0:
        print("PASS")
        return True
    print(f"FAIL ({result.returncode})")
    return False


def main() -> int:
    targets = resolve_targets(sys.argv[1:])

    ok = True
    ok &= run_step("Mojibake Check", [sys.executable, str(ROOT / "check_mojibake.py")])

    if targets:
        ok &= run_step("Python Compile Check", [sys.executable, "-m", "py_compile", *targets])

    if ok:
        print("\nRepository verification passed.")
        return 0

    print("\nRepository verification failed.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
