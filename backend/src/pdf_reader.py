from __future__ import annotations

from typing import Any, Dict, List

import fitz  # PyMuPDF
import numpy as np
import pdfplumber
from PIL import Image


def is_text_pdf(pdf_path: str, min_len: int = 30) -> bool:
    """Roughly judge whether PDF is text-based by checking first page text length."""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            if not pdf.pages:
                return False
            first_page = pdf.pages[0]
            text = (first_page.extract_text() or "").strip()
            return len(text) >= min_len
    except Exception:
        # If pdfplumber fails, treat as scanned to fall back to OCR.
        return False


def parse_text_pdf(pdf_path: str) -> Dict[str, Any]:
    """Parse text-based PDF using pdfplumber.

    Returns a dict with structure:
    {
        "pages": [
            {"text_lines": [...], "tables": [[...], ...]},
            ...
        ]
    }
    """
    pages_data: List[Dict[str, Any]] = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            raw_text = page.extract_text() or ""
            text_lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
            tables = page.extract_tables() or []
            pages_data.append({"text_lines": text_lines, "tables": tables})
    return {"pages": pages_data}


def _page_to_image(page: fitz.Page) -> Image.Image:
    """Render a single PDF page to a PIL Image for OCR."""
    # Use a zoom factor to get a reasonably high resolution image
    zoom = 2.0  # ~144 DPI
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat)

    mode = "RGBA" if pix.alpha else "RGB"
    image = Image.frombytes(mode, [pix.width, pix.height], pix.samples)
    if pix.alpha:
        image = image.convert("RGB")
    return image


def parse_scanned_pdf(pdf_path: str, ocr_engine) -> Dict[str, Any]:
    """Parse scanned PDF via PaddleOCR (line-level text extraction only)."""
    doc = fitz.open(pdf_path)
    pages_data: List[Dict[str, Any]] = []

    try:
        for page in doc:
            image = _page_to_image(page)
            np_img = np.array(image)

            ocr_result = ocr_engine.ocr(np_img)
            text_lines: List[str] = []

            for res in ocr_result:
                for line in res:
                    text = line[1][0]
                    if text:
                        text_lines.append(str(text).strip())

            pages_data.append({"text_lines": text_lines, "tables": []})
    finally:
        doc.close()

    return {"pages": pages_data}


def parse_pdf(pdf_path: str, ocr_engine=None, min_text_len: int = 30) -> Dict[str, Any]:
    """Parse a PDF and normalize into a unified structure.

    If it looks like a text PDF, use pdfplumber; otherwise, use OCR via the
    provided ocr_engine to parse as a scanned PDF.
    """
    if is_text_pdf(pdf_path, min_len=min_text_len):
        return parse_text_pdf(pdf_path)

    if ocr_engine is None:
        raise ValueError("ocr_engine must be provided when parsing scanned PDFs.")

    return parse_scanned_pdf(pdf_path, ocr_engine)
