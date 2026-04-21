from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
TEXT_EXTENSIONS = {
    ".py",
    ".md",
    ".txt",
    ".json",
    ".yml",
    ".yaml",
    ".ini",
    ".cfg",
    ".toml",
    ".bat",
}
SKIP_DIRS = {
    ".git",
    "__pycache__",
    ".claude",
    "logs",
}
SKIP_FILES = {
    "check_mojibake.py",
}
SUSPICIOUS_FRAGMENTS = [
    "\u0e40\u0e18",   # "เธ"
    "\u0e40\u0e19\u0e3f",  # one common broken sequence containing baht sign
    "\u0e42\u009d",   # broken emoji/text fragment
    "\u0e42\u009c",   # broken emoji/text fragment
    "\u0e50\u009f",   # broken emoji/text fragment
    "\ufffd",         # replacement char
]


def should_check(path: Path) -> bool:
    if path.suffix.lower() not in TEXT_EXTENSIONS:
        return False
    if any(part in SKIP_DIRS for part in path.parts):
        return False
    if path.name in SKIP_FILES:
        return False
    return path.is_file()


def find_issues(path: Path) -> list[tuple[int, str]]:
    issues: list[tuple[int, str]] = []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        issues.append((0, f"<read error: {exc}>"))
        return issues

    for lineno, line in enumerate(text.splitlines(), start=1):
        if any(fragment in line for fragment in SUSPICIOUS_FRAGMENTS):
            issues.append((lineno, line.strip()))
    return issues


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    found = False
    for path in sorted(ROOT.rglob("*")):
        if not should_check(path):
            continue
        issues = find_issues(path)
        if not issues:
            continue
        found = True
        print(path.relative_to(ROOT))
        for lineno, line in issues[:20]:
            print(f"  L{lineno}: {line[:160]}")

    if found:
        print("\nMojibake check found suspicious text.")
        return 1

    print("Mojibake check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
