import io
from types import SimpleNamespace

import pytest

from backend.services import pdf_ingest


class _FakePage:
    def __init__(self, text: str):
        self._text = text

    def get_text(self, mode: str) -> str:
        assert mode == "text"
        return self._text

    def get_pixmap(self, dpi: int):
        assert dpi == 300
        return _FakePixmap()


class _FakePixmap:
    width = 1
    height = 1
    samples = b"\x00\x00\x00"


class _FakeDocument:
    def __init__(self, pages):
        self._pages = pages
        self.closed = False

    def __iter__(self):
        return iter(self._pages)

    def close(self):
        self.closed = True


def test_extract_text_prefers_embedded_text(monkeypatch):
    fake_doc = _FakeDocument([_FakePage("Embedded text")])

    monkeypatch.setattr(pdf_ingest.fitz, "open", lambda stream, filetype: fake_doc)
    monkeypatch.setattr(pdf_ingest, "pytesseract", None)
    monkeypatch.setattr(pdf_ingest, "Image", None)

    text = pdf_ingest.extract_text_from_pdf(io.BytesIO(b"pdf"))

    assert text == "Embedded text"
    assert fake_doc.closed is True


def test_extract_text_falls_back_to_ocr(monkeypatch):
    fake_doc = _FakeDocument([_FakePage("   ")])

    monkeypatch.setattr(pdf_ingest.fitz, "open", lambda stream, filetype: fake_doc)

    class _FakeImageModule:
        @staticmethod
        def frombytes(mode, size, samples):
            assert mode == "RGB"
            assert size == [1, 1]
            assert samples == b"\x00\x00\x00"
            return "image"

    class _FakeTesseract:
        @staticmethod
        def image_to_string(image, lang):
            assert image == "image"
            assert lang == "eng"
            return "OCR text"

    monkeypatch.setattr(pdf_ingest, "Image", _FakeImageModule)
    monkeypatch.setattr(pdf_ingest, "pytesseract", _FakeTesseract)
    monkeypatch.setattr(pdf_ingest, "get_ocr_runtime_status", lambda: (True, "ready"))

    text = pdf_ingest.extract_text_from_pdf(io.BytesIO(b"pdf"))

    assert text == "OCR text"
    assert fake_doc.closed is True


def test_scanned_pdf_requires_working_ocr(monkeypatch):
    fake_doc = _FakeDocument([_FakePage("  ")])
    monkeypatch.setattr(pdf_ingest.fitz, "open", lambda stream, filetype: fake_doc)
    monkeypatch.setattr(
        pdf_ingest,
        "get_ocr_runtime_status",
        lambda: (False, "Install Tesseract with English language data."),
    )

    with pytest.raises(pdf_ingest.OCRUnavailableError, match="Page 1.*Install Tesseract"):
        pdf_ingest.extract_pages_from_pdf(io.BytesIO(b"pdf"))
    assert fake_doc.closed is True


def test_ocr_status_requires_english_language_data(monkeypatch):
    monkeypatch.setattr(
        pdf_ingest,
        "pytesseract",
        SimpleNamespace(pytesseract=SimpleNamespace(tesseract_cmd="tesseract")),
    )
    monkeypatch.setattr(pdf_ingest, "Image", object())
    monkeypatch.setattr(pdf_ingest, "_find_tesseract", lambda: "tesseract.exe")
    monkeypatch.setattr(
        pdf_ingest.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0,
            stdout='List of available languages in "tessdata" (1):\nfra\n',
            stderr="",
        ),
    )

    active, detail = pdf_ingest.get_ocr_runtime_status()

    assert active is False
    assert "eng.traineddata) is missing" in detail


def test_pages_without_text_keep_their_original_page_numbers(monkeypatch):
    fake_doc = _FakeDocument([_FakePage("first"), _FakePage("  "), _FakePage("third")])
    monkeypatch.setattr(pdf_ingest.fitz, "open", lambda stream, filetype: fake_doc)
    monkeypatch.setattr(pdf_ingest, "get_ocr_runtime_status", lambda: (True, "ready"))
    monkeypatch.setattr(pdf_ingest, "_extract_page_text_with_ocr", lambda page: "")

    pages = pdf_ingest.extract_pages_from_pdf(io.BytesIO(b"pdf"))

    assert pages == ["first", "", "third"]
