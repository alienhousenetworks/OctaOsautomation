"""Master Cascading Document Processing Pipeline.

Orchestrates:
1. File Type & Category Detection
2. Level 1: Deterministic Native Extraction (PDF, DOCX, PPTX, XLSX, CSV/TSV, Text, HTML)
3. Quality Gate Check with per-page scan escalation
4. Level 2: Targeted OCR Rasterization for scanned PDF pages & images (RapidOCR)
5. Level 3: Multimodal Vision Fallback for complex layouts/tables
6. Untrusted Data Boundary Sanitization (Prompt injection defense)
7. Semantic, heading-aware & page-aware chunking
8. Web content processing endpoint for crawled pages
"""
import re
import hashlib
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from app.services.document_processing.detector import detect_file_type, classify_document_category
from app.services.document_processing.extractors.native import (
    extract_pdf,
    extract_docx,
    extract_pptx,
    extract_xlsx,
    extract_csv,
    extract_text_plain,
    extract_legacy_office,
    evaluate_text_quality,
)
from app.services.document_processing.extractors.ocr import extract_ocr_image, extract_ocr_pdf_pages
from app.services.document_processing.extractors.vision import extract_vision_document
from app.services.document_processing.sanitizer import sanitize_untrusted_text


def chunk_document_content(
    text: str,
    chunk_size: int = 1000,
    overlap: int = 150,
    source_url: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Hierarchical chunking preserving table markdown blocks, section headings, and page boundaries."""
    if not text:
        return []

    # Parse sections demarcated by Page markers, markdown headings, or horizontal rules
    sections = re.split(r"\n(?=--- Page \d+ ---|#{1,4}\s|\n\[Table)", text)
    chunks = []
    chunk_index = 1
    current_page = 1
    current_section = "General"

    for sec in sections:
        sec = sec.strip()
        if not sec:
            continue

        # If section is purely a page delimiter, update current_page and advance
        page_only = re.fullmatch(r"^---\s*Page\s+(\d+)\s*---$", sec)
        if page_only:
            current_page = int(page_only.group(1))
            continue

        # Detect embedded page header
        page_match = re.search(r"---\s*Page\s+(\d+)\s*---", sec)
        if page_match:
            current_page = int(page_match.group(1))

        # Detect section title
        heading_match = re.search(r"#{1,4}\s+([^\n]+)", sec)
        if heading_match:
            current_section = heading_match.group(1).strip()

        # If section is small enough, keep as single chunk
        if len(sec) <= chunk_size:
            chunk_hash = hashlib.sha256(sec.encode("utf-8")).hexdigest()[:16]
            chunks.append({
                "chunk_index": chunk_index,
                "text": sec,
                "token_estimate": len(sec.split()),
                "page_start": current_page,
                "page_end": current_page,
                "section_title": current_section,
                "source_url": source_url,
                "content_hash": chunk_hash,
            })
            chunk_index += 1
        else:
            # Sub-chunk by paragraphs or table blocks
            paragraphs = sec.split("\n\n")
            buf = ""
            for p in paragraphs:
                if len(buf) + len(p) < chunk_size:
                    buf = f"{buf}\n\n{p}".strip() if buf else p
                else:
                    if buf:
                        chunk_hash = hashlib.sha256(buf.encode("utf-8")).hexdigest()[:16]
                        chunks.append({
                            "chunk_index": chunk_index,
                            "text": buf,
                            "token_estimate": len(buf.split()),
                            "page_start": current_page,
                            "page_end": current_page,
                            "section_title": current_section,
                            "source_url": source_url,
                            "content_hash": chunk_hash,
                        })
                        chunk_index += 1
                    buf = p
            if buf:
                chunk_hash = hashlib.sha256(buf.encode("utf-8")).hexdigest()[:16]
                chunks.append({
                    "chunk_index": chunk_index,
                    "text": buf,
                    "token_estimate": len(buf.split()),
                    "page_start": current_page,
                    "page_end": current_page,
                    "section_title": current_section,
                    "source_url": source_url,
                    "content_hash": chunk_hash,
                })
                chunk_index += 1

    return chunks


class DocumentProcessingPipeline:
    def __init__(self, db: Session, tenant_id: str):
        self.db = db
        self.tenant_id = tenant_id

    async def process_document(
        self,
        filename: str,
        file_bytes: bytes,
        department: str = "General",
        doc_type_override: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Process document through the cascading ingestion pipeline."""
        # 1. Detection
        file_type = detect_file_type(filename, file_bytes)
        category = doc_type_override or classify_document_category(filename)

        raw_result = {"text": "", "tables": [], "pages": [], "quality_score": 0.0, "method": "none"}

        # 2. Level 1: Deterministic Native Extraction
        if file_type == "pdf":
            raw_result = extract_pdf(file_bytes)
        elif file_type == "docx":
            raw_result = extract_docx(file_bytes)
        elif file_type == "pptx":
            raw_result = extract_pptx(file_bytes)
        elif file_type == "xlsx":
            raw_result = extract_xlsx(file_bytes)
        elif file_type == "csv":
            raw_result = extract_csv(file_bytes)
        elif file_type in ("text", "markdown", "json", "html"):
            raw_result = extract_text_plain(file_bytes)
        elif file_type in ("doc", "ppt", "xls"):
            raw_result = extract_legacy_office(filename)
        elif file_type == "image":
            raw_result = extract_ocr_image(file_bytes)

        # 3. Quality Gate & Targeted Level 2 OCR
        pages = raw_result.get("pages", [])
        overall_quality = raw_result.get("quality_score", 0.0)

        # If PDF has individual pages that need OCR (scanned pages, images of tables)
        if file_type == "pdf" and pages:
            pages_needing_ocr = [p["page_num"] for p in pages if p.get("needs_ocr")]
            if pages_needing_ocr:
                ocr_pdf_res = extract_ocr_pdf_pages(file_bytes, target_pages=pages_needing_ocr)
                ocr_pages_map = {p["page_num"]: p for p in ocr_pdf_res.get("pages", [])}

                # Merge OCR text into target pages
                updated_runs = []
                for p in pages:
                    p_num = p["page_num"]
                    if p_num in ocr_pages_map and ocr_pages_map[p_num]["text"]:
                        p["text"] = ocr_pages_map[p_num]["text"]
                        p["quality_score"] = ocr_pages_map[p_num]["quality_score"]
                        p["method"] = "ocr_rasterized_pdf"
                    if p.get("text"):
                        updated_runs.append(f"--- Page {p_num} ---\n{p['text']}")

                reconstructed_text = "\n\n".join(updated_runs)
                raw_result["text"] = reconstructed_text
                raw_result["quality_score"] = evaluate_text_quality(reconstructed_text)
                raw_result["method"] = "hybrid_native_with_ocr"
                overall_quality = raw_result["quality_score"]

        # Level 2 Fallback for stand-alone image or wholly scanned document
        if overall_quality < 0.65 and file_type in ("image", "pdf") and not pages:
            ocr_result = extract_ocr_image(file_bytes)
            if ocr_result.get("quality_score", 0.0) > overall_quality:
                raw_result = ocr_result
                overall_quality = ocr_result["quality_score"]

        # 4. Level 3 Fallback: Multimodal Vision
        if overall_quality < 0.65 and file_type in ("image", "pdf"):
            mime = "image/png"
            if filename.lower().endswith((".jpg", ".jpeg")):
                mime = "image/jpeg"
            elif filename.lower().endswith(".webp"):
                mime = "image/webp"
            elif filename.lower().endswith(".pdf"):
                mime = "application/pdf"

            vision_result = await extract_vision_document(
                file_bytes=file_bytes,
                mime_type=mime,
                db=self.db,
                tenant_id=self.tenant_id,
                prompt_context=f"Document: {filename}, Department: {department}, Category: {category}",
            )
            if vision_result.get("quality_score", 0.0) > overall_quality:
                raw_result = vision_result
                overall_quality = vision_result["quality_score"]

        # 5. Untrusted Data Boundary: Sanitize prompt injection directives
        sanitized_text = sanitize_untrusted_text(raw_result.get("text", ""))

        # 6. Semantic Chunking with section & page awareness
        chunks = chunk_document_content(sanitized_text)

        return {
            "filename": filename,
            "file_type": file_type,
            "category": category,
            "department": department,
            "text": sanitized_text,
            "tables": raw_result.get("tables", []),
            "pages": raw_result.get("pages", []),
            "quality_score": overall_quality,
            "extraction_method": raw_result.get("method", "unknown"),
            "chunks": chunks,
            "total_chunks": len(chunks),
        }

    def process_web_content(
        self,
        url: str,
        content: str,
        title: Optional[str] = None,
        department: str = "General",
        category: str = "Website",
    ) -> Dict[str, Any]:
        """Process crawled web page into sanitized structured knowledge."""
        # Sanitize untrusted web content
        sanitized_text = sanitize_untrusted_text(content or "")

        # Compute content hash for change detection
        content_hash = hashlib.sha256(sanitized_text.encode("utf-8")).hexdigest()

        # Chunk with source_url metadata attached
        chunks = chunk_document_content(sanitized_text, source_url=url)
        quality = evaluate_text_quality(sanitized_text)

        doc_title = title or url

        return {
            "title": doc_title,
            "url": url,
            "content": sanitized_text,
            "content_hash": content_hash,
            "quality_score": quality,
            "department": department,
            "category": category,
            "extraction_method": "firecrawl_web",
            "chunks": chunks,
            "total_chunks": len(chunks),
        }
