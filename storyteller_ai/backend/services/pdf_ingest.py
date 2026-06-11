import fitz  # PyMuPDF
import io


def extract_text_from_pdf(stream: io.BytesIO) -> str:
    document = fitz.open(stream=stream, filetype="pdf")
    pages = [page.get_text("text") for page in document]
    document.close()
    return "\n\n".join(pages)
