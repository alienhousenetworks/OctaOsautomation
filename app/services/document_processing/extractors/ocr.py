"""Level 2: OCR Extractor for scanned documents and images.

Uses RapidOCR (ONNX-runtime, pure Python/pip, no system binary required)
with PyMuPDF page rasterization for scanned PDFs and PIL image enhancements.
"""
import io
import logging
from typing import Dict, Any, List, Optional
from PIL import Image

from app.services.document_processing.extractors.native import evaluate_text_quality

logger = logging.getLogger(__name__)

_RAPID_OCR_INSTANCE = None


def _get_rapid_ocr():
    """Lazy singleton initializer for RapidOCR engine."""
    global _RAPID_OCR_INSTANCE
    if _RAPID_OCR_INSTANCE is None:
        try:
            from rapidocr_onnxruntime import RapidOCR
            _RAPID_OCR_INSTANCE = RapidOCR()
        except Exception as e:
            logger.warning(f"Could not load RapidOCR: {e}")
    return _RAPID_OCR_INSTANCE


def _preprocess_image_bytes(file_bytes: bytes) -> bytes:
    """Enhance image for OCR (normalize color modes, upscale tiny images)."""
    try:
        img = Image.open(io.BytesIO(file_bytes))
        # Convert non-RGB/L modes
        if img.mode in ("RGBA", "P", "LA"):
            background = Image.new("RGB", img.size, (255, 255, 255))
            if img.mode == "RGBA":
                background.paste(img, mask=img.split()[3])
            else:
                background.paste(img.convert("RGB"))
            img = background
        elif img.mode != "RGB":
            img = img.convert("RGB")

        # Upscale small images to improve character detection
        w, h = img.size
        if w < 400 or h < 400:
            scale = max(400 / max(w, 1), 400 / max(h, 1))
            new_size = (int(w * scale), int(h * scale))
            img = img.resize(new_size, Image.Resampling.BICUBIC)

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()
    except Exception:
        return file_bytes


def extract_ocr_image(file_bytes: bytes) -> Dict[str, Any]:
    """Run OCR on image bytes (PNG, JPG, TIFF, WEBP, BMP, GIF)."""
    cleaned_bytes = _preprocess_image_bytes(file_bytes)
    ocr_engine = _get_rapid_ocr()

    lines = []
    method = "ocr_rapidocr"

    if ocr_engine:
        try:
            results, _ = ocr_engine(cleaned_bytes)
            if results:
                # result item: [box, text, score]
                for item in results:
                    txt = (item[1] or "").strip()
                    if txt:
                        lines.append(txt)
        except Exception as e:
            logger.warning(f"RapidOCR failed: {e}")
            ocr_engine = None

    # Fallback to pytesseract if RapidOCR was unavailable or returned nothing
    if not lines and not ocr_engine:
        try:
            import pytesseract
            img = Image.open(io.BytesIO(cleaned_bytes))
            txt = pytesseract.image_to_string(img)
            if txt.strip():
                lines = [txt.strip()]
                method = "ocr_tesseract"
        except Exception:
            pass

    full_text = "\n".join(lines).strip()
    quality = evaluate_text_quality(full_text)

    return {
        "text": full_text,
        "tables": [],
        "pages": [{"page_num": 1, "text": full_text, "quality_score": quality, "needs_ocr": False}],
        "total_pages": 1 if full_text else 0,
        "quality_score": quality,
        "method": method if full_text else "ocr_no_text_detected",
    }


def extract_ocr_pdf_pages(file_bytes: bytes, target_pages: Optional[List[int]] = None) -> Dict[str, Any]:
    """Rasterize PDF pages using PyMuPDF and perform high-resolution OCR."""
    pages = []
    all_runs = []

    try:
        import fitz
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        total_doc_pages = len(doc)
        pages_to_process = set(target_pages) if target_pages else set(range(1, total_doc_pages + 1))

        for idx in range(total_doc_pages):
            page_num = idx + 1
            if page_num not in pages_to_process:
                continue

            page = doc[idx]
            # Render page at 200 DPI for high OCR accuracy
            pix = page.get_pixmap(dpi=200)
            png_bytes = pix.tobytes("png")

            ocr_res = extract_ocr_image(png_bytes)
            page_text = ocr_res.get("text", "")
            page_q = ocr_res.get("quality_score", 0.0)

            pages.append({
                "page_num": page_num,
                "text": page_text,
                "quality_score": page_q,
                "needs_ocr": False,
                "has_images": True,
                "tables": [],
                "method": ocr_res.get("method", "ocr_rapidocr"),
            })
            if page_text:
                all_runs.append(f"--- Page {page_num} (OCR) ---\n{page_text}")
        doc.close()
    except Exception as e:
        logger.error(f"Failed to rasterize and OCR PDF pages: {e}")

    full_text = "\n\n".join(all_runs)
    quality = evaluate_text_quality(full_text)

    return {
        "text": full_text,
        "pages": pages,
        "tables": [],
        "total_pages": len(pages),
        "quality_score": quality,
        "method": "ocr_rasterized_pdf",
    }
