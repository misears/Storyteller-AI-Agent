import io

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
        def image_to_string(image):
            assert image == "image"
            return "OCR text"

    monkeypatch.setattr(pdf_ingest, "Image", _FakeImageModule)
    monkeypatch.setattr(pdf_ingest, "pytesseract", _FakeTesseract)

    text = pdf_ingest.extract_text_from_pdf(io.BytesIO(b"pdf"))

    assert text == "OCR text"
    assert fake_doc.closed is True
