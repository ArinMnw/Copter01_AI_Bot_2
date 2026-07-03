"""
Audit and extract all PDFs in the local All-in-4S folder.

This is a research helper, not live trading code.
Outputs:
- tmp/allin4s_pdf_manifest.csv
- tmp/allin4s_pdf_text/*.txt
- tmp/allin4s_pdf_audit.md
"""

from __future__ import annotations

import csv
import hashlib
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

try:
    from pypdf import PdfReader
except Exception as exc:  # pragma: no cover
    PdfReader = None
    IMPORT_ERROR = exc
else:
    IMPORT_ERROR = None


ROOT = Path(r"C:\Users\Copter\Downloads\อออิน4s")
OUT_DIR = Path("tmp") / "allin4s_pdf_audit"
TEXT_DIR = OUT_DIR / "text"
MANIFEST = OUT_DIR / "allin4s_pdf_manifest.csv"
REPORT = OUT_DIR / "allin4s_pdf_audit.md"

PDFINFO = Path(
    r"C:\Users\Copter\.cache\codex-runtimes\codex-primary-runtime"
    r"\dependencies\native\poppler\Library\bin\pdfinfo.exe"
)


@dataclass
class PdfRow:
    idx: int
    rel_path: str
    size_mb: float
    pages: int | None
    sha256: str
    duplicate_of: str
    text_chars: int
    thai_chars: int
    status: str
    text_file: str
    error: str


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def pdf_pages_pdfinfo(path: Path) -> int | None:
    if not PDFINFO.exists():
        return None
    try:
        cp = subprocess.run(
            [str(PDFINFO), str(path)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
    except Exception:
        return None
    m = re.search(r"^Pages:\s+(\d+)\s*$", cp.stdout, re.MULTILINE)
    return int(m.group(1)) if m else None


def safe_text_name(idx: int, rel_path: str) -> str:
    stem = re.sub(r"[^\w.\-ก-๙]+", "_", rel_path, flags=re.UNICODE).strip("_")
    if len(stem) > 120:
        stem = stem[-120:]
    return f"{idx:03d}_{stem}.txt"


def extract_text(path: Path) -> tuple[int | None, str, str]:
    if PdfReader is None:
        return None, "", f"pypdf import failed: {IMPORT_ERROR}"
    try:
        reader = PdfReader(str(path), strict=False)
        pages = len(reader.pages)
        chunks: list[str] = []
        for i, page in enumerate(reader.pages, 1):
            try:
                text = page.extract_text() or ""
            except Exception as exc:
                chunks.append(f"\n[PAGE {i} EXTRACT_ERROR: {exc}]\n")
                continue
            if text.strip():
                chunks.append(f"\n\n--- PAGE {i} ---\n{text}")
        return pages, "".join(chunks).strip(), ""
    except Exception as exc:
        return None, "", str(exc)


def compact_title(rel_path: str) -> str:
    name = rel_path.replace("\\", "/")
    if len(name) <= 80:
        return name
    return "..." + name[-77:]


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="backslashreplace")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    TEXT_DIR.mkdir(parents=True, exist_ok=True)
    pdfs = sorted(ROOT.rglob("*.pdf"), key=lambda p: str(p).casefold())
    seen_hash: dict[str, str] = {}
    rows: list[PdfRow] = []

    for idx, path in enumerate(pdfs, 1):
        rel_path = str(path.relative_to(ROOT))
        size_mb = round(path.stat().st_size / (1024 * 1024), 3)
        print(f"[{idx}/{len(pdfs)}] {rel_path} ({size_mb} MB)", flush=True)
        error = ""
        sha = ""
        pages = pdf_pages_pdfinfo(path)
        text = ""
        try:
            sha = sha256_file(path)
        except Exception as exc:
            error = f"hash_error: {exc}"
        duplicate_of = seen_hash.get(sha, "") if sha else ""
        if sha and not duplicate_of:
            seen_hash[sha] = rel_path

        extracted_pages, text, extract_error = extract_text(path)
        if extracted_pages is not None:
            pages = extracted_pages
        if extract_error:
            error = (error + " | " + extract_error).strip(" |")

        text_chars = len(text)
        thai_chars = sum(1 for ch in text if "\u0e00" <= ch <= "\u0e7f")
        if error:
            status = "error"
        elif duplicate_of:
            status = "duplicate_text_extracted" if text_chars else "duplicate_image_only"
        elif text_chars >= 200:
            status = "text_extracted"
        elif text_chars > 0:
            status = "low_text_mostly_image"
        else:
            status = "image_only"

        text_file = ""
        if text_chars:
            text_name = safe_text_name(idx, rel_path)
            text_path = TEXT_DIR / text_name
            text_path.write_text(text, encoding="utf-8", newline="\n")
            text_file = str(text_path)

        rows.append(
            PdfRow(
                idx=idx,
                rel_path=rel_path,
                size_mb=size_mb,
                pages=pages,
                sha256=sha,
                duplicate_of=duplicate_of,
                text_chars=text_chars,
                thai_chars=thai_chars,
                status=status,
                text_file=text_file,
                error=error,
            )
        )

    with MANIFEST.open("w", newline="", encoding="utf-8") as f:
        fields = list(PdfRow.__dataclass_fields__.keys())
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in rows:
            w.writerow(row.__dict__)

    total_pages = sum(row.pages or 0 for row in rows)
    by_status: dict[str, int] = {}
    for row in rows:
        by_status[row.status] = by_status.get(row.status, 0) + 1

    lines = [
        "# All-in-4S PDF Audit",
        "",
        f"Root: `{ROOT}`",
        f"PDF files: {len(rows)}",
        f"Total pages counted: {total_pages}",
        "",
        "## Status Counts",
        "",
    ]
    for status, count in sorted(by_status.items()):
        lines.append(f"- `{status}`: {count}")
    lines += [
        "",
        "## Files",
        "",
        "| # | Status | Pages | MB | Text chars | Thai chars | File | Duplicate of |",
        "|---:|---|---:|---:|---:|---:|---|---|",
    ]
    for row in rows:
        dup = compact_title(row.duplicate_of) if row.duplicate_of else ""
        lines.append(
            f"| {row.idx} | {row.status} | {row.pages or ''} | {row.size_mb:.3f} | "
            f"{row.text_chars} | {row.thai_chars} | {compact_title(row.rel_path)} | {dup} |"
        )
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(f"\nWrote {MANIFEST}")
    print(f"Wrote {REPORT}")
    print(f"Wrote extracted text files under {TEXT_DIR}")


if __name__ == "__main__":
    main()
