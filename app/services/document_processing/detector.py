"""File type detection and business document classification."""
import os
from typing import Tuple, Dict, Any


SUPPORTED_EXTENSIONS = {
    ".pdf": "pdf",
    ".docx": "docx",
    ".doc": "doc",
    ".pptx": "pptx",
    ".ppt": "ppt",
    ".xlsx": "xlsx",
    ".xls": "xls",
    ".csv": "csv",
    ".tsv": "csv",
    ".txt": "text",
    ".md": "markdown",
    ".json": "json",
    ".html": "html",
    ".htm": "html",
    ".rtf": "text",
    ".png": "image",
    ".jpg": "image",
    ".jpeg": "image",
    ".webp": "image",
    ".tiff": "image",
    ".tif": "image",
    ".bmp": "image",
    ".gif": "image",
}


def detect_file_type(filename: str, file_bytes: bytes) -> str:
    """Detect format from file extension and magic byte signatures."""
    ext = os.path.splitext(filename.lower())[1]

    # Magic byte checks
    if file_bytes.startswith(b"%PDF"):
        return "pdf"
    if file_bytes.startswith(b"\x50\x4B\x03\x04"):  # ZIP-based (DOCX, PPTX, XLSX)
        if ext in (".docx", ".pptx", ".xlsx"):
            return SUPPORTED_EXTENSIONS[ext]
        return "docx"  # fallback default for Office Open XML
    if (
        file_bytes.startswith(b"\x89PNG\r\n\x1a\n")
        or file_bytes.startswith(b"\xFF\xD8\xFF")
        or file_bytes.startswith(b"GIF87a")
        or file_bytes.startswith(b"GIF89a")
        or file_bytes.startswith(b"BM")
        or file_bytes.startswith(b"II*\x00")
        or file_bytes.startswith(b"MM\x00*")
        or (file_bytes[:4] == b"RIFF" and file_bytes[8:12] == b"WEBP")
    ):
        return "image"

    return SUPPORTED_EXTENSIONS.get(ext, "unknown")


def classify_document_category(filename: str, sample_text: str = "") -> str:
    """Classify business document category from filename and content keywords."""
    combined = (filename + " " + sample_text[:1000]).lower().replace("_", " ").replace("-", " ")

    if any(w in combined for w in ["pricing", "price", "rate card", "quotation", "cost", "tier", "subscription fee"]):
        return "pricing"
    if any(w in combined for w in ["case study", "customer story", "success story", "roi", "results achieved"]):
        return "case_study"
    if any(w in combined for w in ["playbook", "battlecard", "objection", "competitor", "talk track"]):
        return "sales_playbook"
    if any(w in combined for w in ["agreement", "contract", "msa", "terms of service", "sla", "nda", "dpa"]):
        return "contract"
    if any(w in combined for w in ["deck", "presentation", "overview", "pitch", "slides"]):
        return "sales_deck"
    if any(w in combined for w in ["brochure", "datasheet", "feature matrix", "product sheet", "spec sheet"]):
        return "product_brochure"
    if any(w in combined for w in ["faq", "frequently asked questions", "q&a"]):
        return "faq"

    return "general"
