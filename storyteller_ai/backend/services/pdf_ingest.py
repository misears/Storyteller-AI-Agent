import io
import os
import shutil
import subprocess
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
        return False, _ocr_setup_guidance("the application's OCR packages are unavailable.")

    executable = _find_tesseract()
    if executable is None:
        return False, _ocr_setup_guidance("Tesseract is not installed or could not be found.")

    try:
        result = subprocess.run(
            [executable, "--list-langs"],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, _ocr_setup_guidance(f"Tesseract could not be checked: {exc}.")
    if result.returncode != 0:
        detail = result.stderr.strip() or "Tesseract could not read its language data."
        return False, _ocr_setup_guidance(detail)

    languages = _parse_languages(result.stdout)
    if "eng" not in languages:
        return False, _ocr_setup_guidance("English language data (eng.traineddata) is missing.")

    tesseract_module = getattr(pytesseract, "pytesseract", None)
    if tesseract_module is not None:
        tesseract_module.tesseract_cmd = executable
    return True, f"OCR is ready with English language data ({executable})."


def _find_tesseract() -> str | None:
    configured = os.getenv("TESSERACT_CMD", "").strip()
    if configured:
        if os.path.isfile(configured):
            return configured
        found = shutil.which(configured)
        if found:
            return found

    tesseract_module = getattr(pytesseract, "pytesseract", None)
    module_command = getattr(tesseract_module, "tesseract_cmd", "tesseract")
    if os.path.isfile(module_command):
        return module_command
    found = shutil.which(module_command)
    if found:
        return found

    if os.name == "nt":
        for root in (os.getenv("ProgramFiles", r"C:\Program Files"), os.getenv("LOCALAPPDATA", "")):
            if root:
                candidate = os.path.join(root, "Tesseract-OCR", "tesseract.exe")
                if os.path.isfile(candidate):
                    return candidate
    return None


def _parse_languages(output: str) -> set[str]:
    lines = output.splitlines()
    if not lines or not lines[0].lower().startswith("list of available languages"):
        return set()
    return {line.strip() for line in lines[1:] if line.strip()}


def _page_has_images(page: fitz.Page) -> bool:
    get_images = getattr(page, "get_images", None)
    return bool(get_images(full=True)) if get_images is not None else True


def _ocr_setup_guidance(problem: str) -> str:
    return (
        f"Scanned PDF OCR is unavailable: {problem} "
        "Install or repair Tesseract OCR with English (eng) language data, "
        "then restart Storyteller AI. On Windows, choose Repair OCR for Storyteller AI "
        "or follow https://github.com/UB-Mannheim/tesseract/wiki. "
        "Text-based PDFs can still be imported."
    )


def extract_text_from_pdf(stream: io.BytesIO) -> str:
    return "\n\n".join(extract_pages_from_pdf(stream))


def extract_pages_from_pdf(stream: io.BytesIO) -> List[str]:
    stream.seek(0)
    document = fitz.open(stream=stream, filetype="pdf")
    page_texts: List[str] = []
    ocr_status: tuple[bool, str] | None = None

    try:
        for page_number, page in enumerate(document, start=1):
            text = page.get_text("text").strip()
            if not text and _page_has_images(page):
                if ocr_status is None:
                    ocr_status = get_ocr_runtime_status()
                if not ocr_status[0]:
                    raise OCRUnavailableError(
                        f"Page {page_number} appears to be scanned. {ocr_status[1]}"
                    )
                text = _extract_page_text_with_ocr(page)
            page_texts.append(text)
    finally:
        document.close()

    return page_texts


def _extract_page_text_with_ocr(page: fitz.Page) -> str:
    if pytesseract is None or Image is None:
        raise OCRUnavailableError(_ocr_setup_guidance("OCR packages are unavailable."))

    pix = page.get_pixmap(dpi=300)
    image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    try:
        return pytesseract.image_to_string(image, lang="eng").strip()
    except Exception as exc:
        raise OCRUnavailableError(
            _ocr_setup_guidance(f"Tesseract could not process the scanned page: {exc}.")
        ) from exc


class OCRUnavailableError(RuntimeError):
    """Raised when a scanned PDF page cannot be read by the configured OCR engine."""
