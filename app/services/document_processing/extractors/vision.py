"""Level 3: Multimodal Vision Extractor for complex layouts, pricing tables, and infographics.

Invoked as a fallback when deterministic extraction and OCR yield insufficient quality (< 0.65).
Actually sends base64 image data payload to vision-capable multimodal LLMs (Gemini, Claude, GPT-4o).
"""
import io
import base64
import logging
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from app.services.llm_gateway import LLMGateway
from app.services.document_processing.extractors.native import evaluate_text_quality

logger = logging.getLogger(__name__)


async def extract_vision_document(
    file_bytes: bytes,
    mime_type: str = "image/png",
    db: Optional[Session] = None,
    tenant_id: str = "",
    prompt_context: Optional[str] = None,
) -> Dict[str, Any]:
    """Extract structured content and tables from document image using Multimodal Vision."""
    if not file_bytes or not db or not tenant_id:
        return {
            "text": "",
            "tables": [],
            "pages": [],
            "total_pages": 0,
            "quality_score": 0.0,
            "method": "vision_skipped",
        }

    # If payload is PDF, rasterize first page to PNG for vision processing
    final_bytes = file_bytes
    final_mime = mime_type
    if mime_type == "application/pdf" or file_bytes.startswith(b"%PDF"):
        try:
            import fitz
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            if len(doc) > 0:
                pix = doc[0].get_pixmap(dpi=200)
                final_bytes = pix.tobytes("png")
                final_mime = "image/png"
            doc.close()
        except Exception as e:
            logger.warning(f"Could not rasterize PDF for vision: {e}")

    b64_data = base64.b64encode(final_bytes).decode("utf-8")

    prompt = (
        "You are an enterprise document extraction system. "
        "Analyze this document image with rigorous precision.\n"
        "1. Extract all text content, headings, and bullet points verbatim.\n"
        "2. Convert any tables, pricing grids, or comparison matrices into clean Markdown tables.\n"
        "3. Accurately preserve all figures, currencies, product names, dates, and SLA terms.\n"
        "4. Do not invent or hallucinate information. If text is unreadable, note [UNREADABLE].\n"
        "Output the reconstructed document text and markdown tables directly without conversational preamble or commentary."
    )
    if prompt_context:
        prompt += f"\nAdditional Document Context: {prompt_context}"

    try:
        llm = LLMGateway(db, tenant_id)
        # Pass actual multimodal image payload via kwargs to LLMGateway -> AI Gateway -> Adapter
        content = await llm.complete(
            prompt=prompt,
            model="gemini-2.5-flash",
            provider="gemini",
            images=[{"mime_type": final_mime, "data": b64_data}],
        )
        content_clean = (content or "").strip()
        quality = evaluate_text_quality(content_clean)

        return {
            "text": content_clean,
            "tables": [],
            "pages": [{"page_num": 1, "text": content_clean, "quality_score": quality, "needs_ocr": False}],
            "total_pages": 1 if content_clean else 0,
            "quality_score": quality,
            "method": "vision_multimodal",
        }
    except Exception as e:
        logger.error(f"Multimodal vision extraction failed: {e}")
        return {
            "text": "",
            "tables": [],
            "pages": [],
            "total_pages": 0,
            "quality_score": 0.0,
            "method": "vision_failed",
            "error": str(e),
        }
