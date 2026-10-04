"""Level 1: Deterministic Native Document Extractors.

Supports:
- PDF: PyMuPDF (fitz) reading-order text + pdfplumber precision table extraction + per-page scan detection
- Word DOCX: python-docx with headings, bullets, and markdown tables
- PowerPoint PPTX: python-pptx with slides, bullets, and tables
- Excel XLSX & CSV/TSV: openpyxl / csv with sheet and table preservation
- Markdown, Text, HTML: structured text with encoding auto-detection
- Legacy Office (.doc, .ppt, .xls): informative fallback guidance
"""
import io
import re
import csv
from typing import Dict, Any, List, Optional


def evaluate_text_quality(text: str) -> float:
    """Calculate extraction quality score (0.0 to 1.0).

    Penalizes garbled symbols, unprintable characters, and low word density.
    """
    if not text or len(text.strip()) < 20:
        return 0.0

    cleaned = text.strip()
    words = re.findall(r"\b[a-zA-Z0-9]{2,}\b", cleaned)
    if not words:
        return 0.0

    # 1. Alphanumeric word char ratio vs non-whitespace chars
    alphanumeric_chars = sum(len(w) for w in words)
    total_non_ws = max(len(re.sub(r"\s+", "", cleaned)), 1)
    word_ratio = min(1.0, alphanumeric_chars / total_non_ws)

    # 2. Garbage / unprintable symbol ratio penalty
    weird_chars = len(re.findall(r"[\ufffd\x00-\x08\x0b\x0c\x0e-\x1f]", cleaned))
    weird_penalty = min(0.5, (weird_chars / max(len(cleaned), 1)) * 5.0)

    # 3. Word count adequacy
    density_boost = 0.1 if len(words) >= 20 else 0.0

    base_score = (word_ratio * 0.9) - weird_penalty + density_boost
    return max(0.0, min(1.0, round(base_score, 2)))


def _format_table_to_markdown(rows_data: List[List[Any]]) -> str:
    """Helper to convert 2D array of cells into a Markdown table."""
    if not rows_data:
        return ""
    # Filter empty rows
    clean_rows = []
    for row in rows_data:
        cells = [str(c).strip().replace("\n", " ") if c is not None else "" for c in row]
        if any(cells):
            clean_rows.append(cells)
    if not clean_rows:
        return ""

    # Normalize column count across all rows
    max_cols = max(len(r) for r in clean_rows)
    padded = [r + [""] * (max_cols - len(r)) for r in clean_rows]

    header = padded[0]
    md = "| " + " | ".join(header) + " |\n"
    md += "| " + " | ".join(["---"] * max_cols) + " |\n"
    for r in padded[1:]:
        md += "| " + " | ".join(r) + " |\n"
    return md


def extract_pdf(file_bytes: bytes) -> Dict[str, Any]:
    """Advanced PDF extraction: PyMuPDF for layout text + pdfplumber for tables.

    Tracks page-by-page content and flags image-only or low-quality pages for OCR.
    """
    pages = []
    all_runs = []
    all_tables = []
    method = "native_pymupdf"

    # Step 1: Extract tables per page via pdfplumber
    plumber_tables_by_page: Dict[int, List[Dict[str, Any]]] = {}
    try:
        import pdfplumber
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for idx, p in enumerate(pdf.pages):
                tables = p.extract_tables()
                if tables:
                    formatted_tables = []
                    for t_idx, t in enumerate(tables):
                        md_table = _format_table_to_markdown(t)
                        if md_table:
                            tbl_dict = {
                                "page_num": idx + 1,
                                "table_index": t_idx + 1,
                                "markdown": md_table,
                                "rows": t,
                            }
                            formatted_tables.append(tbl_dict)
                            all_tables.append(tbl_dict)
                    if formatted_tables:
                        plumber_tables_by_page[idx + 1] = formatted_tables
    except Exception:
        pass

    # Step 2: Extract text blocks per page via PyMuPDF (fitz)
    try:
        import fitz
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        for idx in range(len(doc)):
            page_num = idx + 1
            page = doc[idx]

            # Extract layout text blocks sorted in natural reading order
            blocks = page.get_text("blocks")
            # block format: (x0, y0, x1, y1, text, block_no, block_type)
            # block_type 0 is text, 1 is image
            text_blocks = [b[4].strip() for b in blocks if b[6] == 0 and b[4].strip()]
            page_text = "\n\n".join(text_blocks)

            # Append tables extracted on this page
            page_tables = plumber_tables_by_page.get(page_num, [])
            if page_tables:
                table_texts = [f"\n[Table {t['table_index']}]\n{t['markdown']}" for t in page_tables]
                page_text = f"{page_text}\n" + "\n".join(table_texts) if page_text else "\n".join(table_texts)

            page_quality = evaluate_text_quality(page_text)
            image_list = page.get_images(full=True)
            has_images = len(image_list) > 0

            # Needs OCR if text is virtually empty or very low quality and has images
            needs_ocr = (len(page_text.strip()) < 40 or page_quality < 0.50) and has_images

            pages.append({
                "page_num": page_num,
                "text": page_text,
                "quality_score": page_quality,
                "needs_ocr": needs_ocr,
                "has_images": has_images,
                "tables": page_tables,
            })
            if page_text:
                all_runs.append(f"--- Page {page_num} ---\n{page_text}")
        doc.close()
    except Exception:
        # Fallback to pypdf if fitz fails
        import pypdf
        method = "native_pypdf_fallback"
        reader = pypdf.PdfReader(io.BytesIO(file_bytes))
        for idx, page in enumerate(reader.pages):
            page_num = idx + 1
            page_text = (page.extract_text() or "").strip()
            page_quality = evaluate_text_quality(page_text)
            pages.append({
                "page_num": page_num,
                "text": page_text,
                "quality_score": page_quality,
                "needs_ocr": len(page_text) < 40,
                "has_images": False,
                "tables": [],
            })
            if page_text:
                all_runs.append(f"--- Page {page_num} ---\n{page_text}")

    full_text = "\n\n".join(all_runs)
    overall_quality = evaluate_text_quality(full_text)

    return {
        "text": full_text,
        "pages": pages,
        "tables": all_tables,
        "total_pages": len(pages),
        "quality_score": overall_quality,
        "method": method,
    }


def extract_docx(file_bytes: bytes) -> Dict[str, Any]:
    """Deterministic DOCX extraction preserving headings, paragraphs, and markdown tables."""
    import docx

    doc = docx.Document(io.BytesIO(file_bytes))
    runs = []
    tables = []

    for p in doc.paragraphs:
        txt = p.text.strip()
        if not txt:
            continue
        style_name = (p.style.name or "").lower()
        if "heading 1" in style_name:
            runs.append(f"# {txt}")
        elif "heading 2" in style_name:
            runs.append(f"## {txt}")
        elif "heading 3" in style_name:
            runs.append(f"### {txt}")
        elif "title" in style_name:
            runs.append(f"# {txt}")
        else:
            runs.append(txt)

    for t_idx, table in enumerate(doc.tables):
        rows_data = []
        for row in table.rows:
            row_cells = [cell.text.strip().replace("\n", " ") for cell in row.cells]
            rows_data.append(row_cells)

        md_table = _format_table_to_markdown(rows_data)
        if md_table:
            tables.append({"table_index": t_idx + 1, "markdown": md_table, "rows": rows_data})
            runs.append(f"\n[Table {t_idx + 1}]\n{md_table}")

    full_text = "\n\n".join(runs)
    quality = evaluate_text_quality(full_text)

    return {
        "text": full_text,
        "tables": tables,
        "pages": [{"page_num": 1, "text": full_text, "quality_score": quality, "needs_ocr": False}],
        "total_pages": 1,
        "quality_score": quality,
        "method": "native_docx",
    }


def extract_pptx(file_bytes: bytes) -> Dict[str, Any]:
    """Deterministic PPTX extraction extracting slides, bullet points, and tables."""
    import pptx

    prs = pptx.Presentation(io.BytesIO(file_bytes))
    slides = []
    all_runs = []
    tables = []

    for s_idx, slide in enumerate(prs.slides):
        slide_num = s_idx + 1
        slide_text_runs = []

        # Title shape first if available
        if slide.shapes.title and slide.shapes.title.has_text_frame:
            title_text = slide.shapes.title.text_frame.text.strip()
            if title_text:
                slide_text_runs.append(f"## {title_text}")

        for shape in slide.shapes:
            if shape == slide.shapes.title:
                continue
            if shape.has_text_frame:
                for paragraph in shape.text_frame.paragraphs:
                    line = paragraph.text.strip()
                    if line:
                        slide_text_runs.append(f"- {line}" if not line.startswith("-") else line)
            elif shape.has_table:
                table = shape.table
                rows_data = []
                for row in table.rows:
                    row_cells = [cell.text.strip().replace("\n", " ") for cell in row.cells]
                    rows_data.append(row_cells)
                md_table = _format_table_to_markdown(rows_data)
                if md_table:
                    tables.append({"slide": slide_num, "markdown": md_table})
                    slide_text_runs.append(f"[Table]\n{md_table}")

        slide_content = "\n".join(slide_text_runs)
        slides.append({
            "page_num": slide_num,
            "text": slide_content,
            "quality_score": evaluate_text_quality(slide_content),
            "needs_ocr": len(slide_content.strip()) < 20,
        })
        if slide_content:
            all_runs.append(f"--- Slide {slide_num} ---\n{slide_content}")

    full_text = "\n\n".join(all_runs)
    quality = evaluate_text_quality(full_text)

    return {
        "text": full_text,
        "pages": slides,
        "tables": tables,
        "total_pages": len(slides),
        "quality_score": quality,
        "method": "native_pptx",
    }


def extract_xlsx(file_bytes: bytes) -> Dict[str, Any]:
    """Deterministic Excel extraction converting sheets into markdown tables."""
    import openpyxl

    wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)
    sheets_output = []
    tables = []

    for sheet_name in wb.sheetnames:
        sheet = wb[sheet_name]
        rows = list(sheet.iter_rows(values_only=True))
        if not rows:
            continue

        clean_rows = []
        for row in rows:
            if any(cell is not None for cell in row):
                clean_rows.append([str(c) if c is not None else "" for c in row])

        if clean_rows:
            md_table = _format_table_to_markdown(clean_rows)
            if md_table:
                table_str = f"### Sheet: {sheet_name}\n\n{md_table}"
                tables.append({"sheet": sheet_name, "markdown": md_table})
                sheets_output.append(table_str)

    full_text = "\n\n".join(sheets_output)
    quality = evaluate_text_quality(full_text)

    return {
        "text": full_text,
        "tables": tables,
        "pages": [{"page_num": 1, "text": full_text, "quality_score": quality, "needs_ocr": False}],
        "total_pages": 1,
        "quality_score": quality,
        "method": "native_xlsx",
    }


def extract_csv(file_bytes: bytes) -> Dict[str, Any]:
    """Deterministic CSV/TSV extraction with dialect sniffing and markdown formatting."""
    text_content = ""
    for enc in ["utf-8", "utf-8-sig", "latin-1", "cp1252"]:
        try:
            text_content = file_bytes.decode(enc)
            break
        except UnicodeDecodeError:
            continue

    if not text_content.strip():
        return {"text": "", "tables": [], "pages": [], "quality_score": 0.0, "method": "native_csv"}

    delimiter = ","
    try:
        sample = text_content[:2048]
        sniffer = csv.Sniffer()
        dialect = sniffer.sniff(sample)
        delimiter = dialect.delimiter
    except Exception:
        if "\t" in text_content[:500]:
            delimiter = "\t"

    reader = csv.reader(io.StringIO(text_content), delimiter=delimiter)
    rows = list(reader)
    md_table = _format_table_to_markdown(rows)
    quality = evaluate_text_quality(md_table)

    return {
        "text": md_table,
        "tables": [{"table_index": 1, "markdown": md_table}],
        "pages": [{"page_num": 1, "text": md_table, "quality_score": quality, "needs_ocr": False}],
        "total_pages": 1,
        "quality_score": quality,
        "method": "native_csv",
    }


def extract_text_plain(file_bytes: bytes) -> Dict[str, Any]:
    """Plain text / Markdown / HTML extraction with multi-encoding fallback."""
    for enc in ["utf-8", "utf-8-sig", "latin-1", "cp1252", "utf-16"]:
        try:
            content = file_bytes.decode(enc)
            # Basic HTML cleanup if content contains HTML tags
            if "<html" in content.lower() or "<body" in content.lower():
                content = re.sub(r"<style[\s\S]*?</style>", "", content, flags=re.IGNORECASE)
                content = re.sub(r"<script[\s\S]*?</script>", "", content, flags=re.IGNORECASE)
                content = re.sub(r"<[^>]+>", " ", content)
                content = re.sub(r"\n\s*\n+", "\n\n", content).strip()

            quality = evaluate_text_quality(content)
            return {
                "text": content,
                "tables": [],
                "pages": [{"page_num": 1, "text": content, "quality_score": quality, "needs_ocr": False}],
                "total_pages": 1,
                "quality_score": quality,
                "method": "native_text",
            }
        except UnicodeDecodeError:
            continue

    return {"text": "", "tables": [], "pages": [], "quality_score": 0.0, "method": "native_text_failed"}


def extract_legacy_office(filename: str) -> Dict[str, Any]:
    """Clear guidance for legacy binary formats (.doc, .ppt, .xls)."""
    ext = filename.split(".")[-1].lower() if "." in filename else ""
    return {
        "text": (
            f"Note: '{filename}' is in legacy binary format (.{ext}). "
            f"Please convert or re-save as modern XML format (.{ext}x) for maximum fidelity extraction."
        ),
        "tables": [],
        "pages": [],
        "total_pages": 0,
        "quality_score": 0.1,
        "method": "legacy_office_warning",
    }
