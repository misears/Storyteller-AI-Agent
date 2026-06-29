import io
import os
import shutil
from typing import List

import fitz  # PyMuPDF

try:
    import pytesseract
    from PIL import Image
except Exception:  # pragma: no cover - optional dependency fallback
    pytesseract = None
    Image = None

if pytesseract is not None:
    tesseract_cmd = os.getenv("TESSERACT_CMD", "").strip()
    if tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = tesseract_cmd


def get_ocr_runtime_status() -> tuple[bool, str]:
    if pytesseract is None or Image is None:
        return False, "python OCR dependencies unavailable"

    tesseract_cmd = getattr(pytesseract.pytesseract, "tesseract_cmd", "tesseract")
    if os.path.isabs(tesseract_cmd):
        executable_found = os.path.exists(tesseract_cmd)
    else:
        executable_found = shutil.which(tesseract_cmd) is not None

    if not executable_found:
        return False, f"tesseract executable not found ({tesseract_cmd})"

    return True, f"tesseract executable ready ({tesseract_cmd})"


def extract_text_from_pdf(stream: io.BytesIO) -> str:
    document = fitz.open(stream=stream, filetype="pdf")
    page_texts: List[str] = []

    try:
        for page in document:
            text = page.get_text("text").strip()
            if text:
                page_texts.append(text)
                continue

            # Fallback for scanned/image-only PDFs.
            ocr_text = _extract_page_text_with_ocr(page)
            if ocr_text:
                page_texts.append(ocr_text)
    finally:
        document.close()

    return "\n\n".join(page_texts)


def _extract_page_text_with_ocr(page: fitz.Page) -> str:
    if pytesseract is None or Image is None:
        return ""

    pix = page.get_pixmap(dpi=300)
    image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    return pytesseract.image_to_string(image).strip()
