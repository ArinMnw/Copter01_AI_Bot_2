"""
Render contact sheets for image-only All-in-4S PDFs.

Uses the manifest produced by research_allin4s_pdf_audit.py.
Skips exact duplicates and split _part PDFs when a full PDF exists in the same
folder, because the full PDF already covers those pages.
"""

from __future__ import annotations

import csv
import math
import re
import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(r"C:\Users\Copter\Downloads\อออิน4s")
MANIFEST = Path("tmp") / "allin4s_pdf_audit" / "allin4s_pdf_manifest.csv"
OUT_DIR = Path("tmp") / "allin4s_pdf_audit" / "contact_sheets"
RENDER_DIR = OUT_DIR / "_rendered_pages"
INDEX = OUT_DIR / "contact_sheet_index.md"

PDFTOPPM = Path(
    r"C:\Users\Copter\.cache\codex-runtimes\codex-primary-runtime"
    r"\dependencies\native\poppler\Library\bin\pdftoppm.exe"
)


def safe_slug(s: str) -> str:
    s = re.sub(r"[^\w.\-ก-๙]+", "_", s, flags=re.UNICODE).strip("_")
    return s[-110:] if len(s) > 110 else s


def is_split_part(rel_path: str, all_rels: set[str]) -> bool:
    p = Path(rel_path)
    stem = p.stem
    m = re.match(r"(.+)_part\d+$", stem, re.IGNORECASE)
    if not m:
        return False
    base = str(p.with_name(m.group(1) + p.suffix))
    return base in all_rels


def render_pdf(pdf_path: Path, out_prefix: Path, dpi: int = 55) -> list[Path]:
    out_prefix.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [str(PDFTOPPM), "-jpeg", "-r", str(dpi), str(pdf_path), str(out_prefix)],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=300,
    )
    return sorted(out_prefix.parent.glob(out_prefix.name + "-*.jpg"))


def make_sheets(images: list[Path], out_stem: Path, title: str, pages_per_sheet: int = 30) -> list[Path]:
    sheets: list[Path] = []
    if not images:
        return sheets
    font = ImageFont.load_default()
    for batch_idx in range(0, len(images), pages_per_sheet):
        batch = images[batch_idx:batch_idx + pages_per_sheet]
        thumbs = []
        for img_path in batch:
            img = Image.open(img_path).convert("RGB")
            img.thumbnail((260, 360))
            thumbs.append((img_path, img.copy()))
            img.close()
        cols = 5
        rows = math.ceil(len(thumbs) / cols)
        cell_w, cell_h = 300, 405
        header_h = 70
        sheet = Image.new("RGB", (cols * cell_w, rows * cell_h + header_h), "white")
        draw = ImageDraw.Draw(sheet)
        draw.text((10, 10), title[:180], fill="black", font=font)
        draw.text((10, 32), f"pages {batch_idx + 1}-{batch_idx + len(batch)} of {len(images)}", fill="black", font=font)
        for i, (img_path, img) in enumerate(thumbs):
            col = i % cols
            row = i // cols
            x = col * cell_w + (cell_w - img.width) // 2
            y = header_h + row * cell_h + 25
            sheet.paste(img, (x, y))
            page_no = batch_idx + i + 1
            draw.text((col * cell_w + 8, header_h + row * cell_h + 5), f"p{page_no}", fill="black", font=font)
        out_path = out_stem.with_name(f"{out_stem.name}_sheet{len(sheets) + 1:02d}.jpg")
        sheet.save(out_path, quality=82)
        sheets.append(out_path)
    return sheets


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    RENDER_DIR.mkdir(parents=True, exist_ok=True)
    rows = list(csv.DictReader(MANIFEST.open(encoding="utf-8")))
    all_rels = {r["rel_path"] for r in rows}
    targets = []
    for r in rows:
        if r["duplicate_of"]:
            continue
        if r["status"] not in {"image_only", "low_text_mostly_image"}:
            continue
        if is_split_part(r["rel_path"], all_rels):
            continue
        targets.append(r)

    lines = ["# All-in-4S Image PDF Contact Sheets", "", f"Targets: {len(targets)}", ""]
    for n, r in enumerate(targets, 1):
        rel = r["rel_path"]
        pages = int(r["pages"] or 0)
        slug = f"{int(r['idx']):03d}_{safe_slug(rel)}"
        pdf_path = ROOT / rel
        rendered_dir = RENDER_DIR / slug
        if rendered_dir.exists():
            shutil.rmtree(rendered_dir)
        rendered_dir.mkdir(parents=True, exist_ok=True)
        print(f"[{n}/{len(targets)}] render {rel} ({pages} pages)", flush=True)
        try:
            imgs = render_pdf(pdf_path, rendered_dir / "page")
            sheets = make_sheets(imgs, OUT_DIR / slug, rel)
            rel_sheets = [str(p).replace("\\", "/") for p in sheets]
            lines.append(f"## {r['idx']} - {rel}")
            lines.append(f"- pages: {pages}")
            lines.append(f"- status: `{r['status']}`")
            for s in rel_sheets:
                lines.append(f"- sheet: `{s}`")
            lines.append("")
        except Exception as exc:
            lines.append(f"## {r['idx']} - {rel}")
            lines.append(f"- ERROR: `{exc}`")
            lines.append("")
    INDEX.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    print(f"Wrote {INDEX}")


if __name__ == "__main__":
    main()
