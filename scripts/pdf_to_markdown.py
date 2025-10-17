#!/usr/bin/env python3
"""
Convert selected chapters from a PDF into a "rich" Markdown file.

This script:
 - Loads a PDF via PyMuPDF (fitz)
 - Heuristically finds where "Chapter 4", "Chapter 5", "Chapter 6" start
   (case-insensitive). If chapters can't be found automatically you can
   pass explicit start pages via CLI.
 - For each chapter range it:
    - Extracts text blocks and uses font size heuristics to map big text to
      Markdown headings (#, ##, ###).
    - Marks bold text when the font name/span indicates bold.
    - Extracts embedded images and writes them to an images/ subfolder,
      embedding Markdown image links close to the page they appear on.
 - Produces a single Markdown file with chapter sections.

Requirements:
  pip install pymupdf Pillow

Usage:
  python scripts/pdf_to_markdown.py \
    --input eurocontrol-ernip-part-4-v2.8.pdf \
    --output doc/ch4-6.md

If automatic detection fails for your copy of the PDF you can also pass
chapter start pages manually:
  --chapter-starts 45 78 123
(where the three numbers are the page numbers (1-based) where chapters 4,5,6 start).
"""

import argparse
import fitz  # PyMuPDF
import os
import re
import io
from PIL import Image

CHAPTER_RE = re.compile(r'\bchapter\s*(\d+)\b', re.I)

def find_chapter_pages(doc, target_chapters=(4, 5, 6)):
    """
    Scan the PDF and try to find first page index (0-based) for each requested chapter.
    Returns dict: chapter_number -> page_index
    """
    found = {}
    for pno in range(doc.page_count):
        text = doc.load_page(pno).get_text("text")
        if not text:
            continue
        for m in CHAPTER_RE.finditer(text):
            try:
                num = int(m.group(1))
            except Exception:
                continue
            if num in target_chapters and num not in found:
                found[num] = pno
                if len(found) == len(target_chapters):
                    return found
    return found

def compute_size_levels(spans):
    """
    Given a list of numeric font sizes (floats), create a mapping size -> level (1..4)
    Larger fonts map to smaller heading numbers (# => 1). We'll map top sizes to
    heading levels, and the rest are treated as normal text.
    """
    uniq = sorted(set(spans), reverse=True)
    if not uniq:
        return {}
    # pick top 3 sizes as headings
    top = uniq[:3]
    mapping = {}
    for i, s in enumerate(top):
        mapping[s] = i + 1  # 1 => H1, 2 => H2 ...
    return mapping

def sanitize_filename(s):
    # keep filesystem-safe
    return re.sub(r'[^A-Za-z0-9._-]', '_', s)

def save_image_xref(doc, page, xref, images_dir, base_name, count):
    """
    Extract image by xref from doc and save to images_dir.
    Returns markdown image path (relative) and img filename.
    """
    pix = fitz.Pixmap(doc, xref)
    if pix.n < 5:  # RGB or grayscale
        img_ext = "png"
        img_data = pix.tobytes("png")
    else:
        # CMYK: convert to RGB via PIL
        img_ext = "png"
        img = Image.frombytes("CMYK", [pix.width, pix.height], pix.samples)
        buf = io.BytesIO()
        img.convert("RGB").save(buf, format="PNG")
        img_data = buf.getvalue()
    fname = f"{base_name}_img_{count}.{img_ext}"
    fpath = os.path.join(images_dir, fname)
    with open(fpath, "wb") as f:
        f.write(img_data)
    pix = None
    return fpath, fname

def page_to_markdown(doc, page, images_dir, image_base, img_counter_start=1):
    """
    Convert a single page to markdown text. Returns (md_text, last_img_counter)
    """
    md_lines = []
    d = page.get_text("dict")  # structured blocks
    # collect sizes for this page to compute levels
    sizes = []
    for block in d.get("blocks", []):
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                sizes.append(round(span.get("size", 0), 1))
    size_map = compute_size_levels(sizes)

    img_counter = img_counter_start

    for block in d.get("blocks", []):
        # text blocks
        if block.get("type") == 0:
            # block has lines -> spans
            # build block text, mapping spans to markup where possible
            block_lines = []
            for line in block.get("lines", []):
                line_text_parts = []
                # find largest span size in the line to categorize
                line_sizes = [round(s.get("size", 0), 1) for s in sum([l.get("spans", []) for l in [line]], [])]  # odd but safe
                # process spans
                for span in line.get("spans", []):
                    text = span.get("text", "")
                    if not text.strip():
                        line_text_parts.append(text)
                        continue
                    fsize = round(span.get("size", 0), 1)
                    fontname = span.get("font", "")
                    # simple bold heuristic
                    is_bold = "Bold" in fontname or "Bd" in fontname or span.get("flags", 0) & 2
                    if is_bold:
                        text = f"**{text}**"
                    # add
                    line_text_parts.append(text)
                line_text = "".join(line_text_parts).strip()
                if line_text:
                    # heading detection by span size
                    # prefer mapping based on the largest span in the line
                    line_span_sizes = [round(s.get("size", 0), 1) for s in line.get("spans", []) if s.get("text", "").strip()]
                    lvl = None
                    if line_span_sizes:
                        maximum = max(line_span_sizes)
                        if maximum in size_map:
                            lvl = size_map[maximum]
                    if lvl:
                        md = "#" * lvl + " " + line_text
                    else:
                        md = line_text
                    block_lines.append(md)
            if block_lines:
                md_lines.extend(block_lines)
                md_lines.append("")  # blank line after block
        # image blocks
        elif block.get("type") == 1:
            # image block - we have to extract images by xref from the page
            # get image references
            images = page.get_images(full=True)
            if images:
                # save all images for the page (avoid duplicates by xref)
                saved = []
                for img in images:
                    xref = img[0]
                    if xref in saved:
                        continue
                    fpath, fname = save_image_xref(doc, page, xref, images_dir, image_base, img_counter)
                    rel = os.path.relpath(fpath, os.path.dirname(images_dir))
                    md_lines.append(f"![{fname}]({os.path.join('images', fname)})")
                    img_counter += 1
                    saved.append(xref)
                md_lines.append("")
    return "\n".join(md_lines), img_counter

# ---------- Main conversion logic ----------

def extract_chapters_to_markdown(pdf_path, out_md, chapters=(4, 5, 6), chapter_starts_cli=None):
    doc = fitz.open(pdf_path)
    images_dir = os.path.join(os.path.dirname(out_md), "images")
    os.makedirs(images_dir, exist_ok=True)

    # find chapter starts
    if chapter_starts_cli:
        # expect list of integers (1-based)
        starts = {chap: p - 1 for chap, p in zip(chapters, chapter_starts_cli)}
    else:
        starts = find_chapter_pages(doc, target_chapters=chapters)
    # If some chapters not found, prompt fallback: try look for "4." at line start or "4 " etc.
    missing = [c for c in chapters if c not in starts]
    if missing:
        # try weaker search: search for "Chapter 4" or lines starting with "4. " or "4 " and "CHAPTER"
        for pno in range(doc.page_count):
            text = doc.load_page(pno).get_text("text")
            if not text:
                continue
            for c in missing[:]:
                pat = re.compile(r'(^|\n)\s*(chapter\s*%d\b|^%d[.\s])' % (c, c), re.I | re.M)
                if pat.search(text):
                    starts[c] = pno
                    missing.remove(c)
        # if still missing, we'll set them to None and try to infer from surrounding chapters later

    # create ordered list of chapter starts
    ordered = sorted(starts.items(), key=lambda kv: kv[0])  # by chapter number
    # Build ranges: each chapter from its start page to just before next start page
    ranges = []
    for i, (chap, start_pno) in enumerate(ordered):
        if start_pno is None:
            continue
        if i + 1 < len(ordered):
            next_start = ordered[i + 1][1]
            if next_start is None:
                end_pno = doc.page_count - 1
            else:
                end_pno = next_start - 1
        else:
            end_pno = doc.page_count - 1
        if start_pno > end_pno:
            continue
        ranges.append((chap, start_pno, end_pno))

    if not ranges:
        raise RuntimeError("Unable to determine chapter page ranges automatically. Try passing explicit --chapter-starts.")

    # Compose markdown
    with open(out_md, "w", encoding="utf-8") as outf:
        outf.write(f"# Extracted chapters: {', '.join(str(c) for c in chapters)}\n\n")
        for chap, start, end in ranges:
            outf.write(f"\n\n---\n\n")
            outf.write(f"# Chapter {chap}\n\n")
            outf.write(f"_Pages {start + 1}–{end + 1} extracted from PDF_\n\n")
            img_counter = 1
            for pno in range(start, end + 1):
                page = doc.load_page(pno)
                outf.write(f"<!-- page: {pno+1} -->\n\n")
                md_page, img_counter = page_to_markdown(doc, page, images_dir, f"chapter{chap}_p{pno+1}", img_counter_start=img_counter)
                outf.write(md_page)
                outf.write("\n\n")
            outf.write("\n\n")  # extra spacing at chapter end

    doc.close()
    print(f"Wrote markdown to {out_md}")
    print(f"Images (if any) in {images_dir}")

# ---------- CLI ----------

def main():
    p = argparse.ArgumentParser(description="Convert chapters to markdown.")
    p.add_argument("--input", "-i", required=True, help="Input PDF path")
    p.add_argument("--output", "-o", required=True, help="Output Markdown file path")
    p.add_argument("--chapters", nargs="+", type=int, default=[4, 5, 6], help="Chapter numbers to extract (default: 4 5 6)")
    p.add_argument("--chapter-starts", nargs="+", type=int, help="Explicit start pages (1-based) for the chapters in same order as --chapters")
    args = p.parse_args()

    if args.chapter_starts and len(args.chapter_starts) != len(args.chapters):
        p.error("--chapter-starts must have same count as --chapters")

    extract_chapters_to_markdown(args.input, args.output, chapters=tuple(args.chapters), chapter_starts_cli=args.chapter_starts)

if __name__ == "__main__":
    main()