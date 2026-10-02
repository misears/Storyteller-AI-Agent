from io import BytesIO
from typing import Any, Dict, List, Optional
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile

import fitz
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field

from ..services.character_sheet_store import (
    SheetConflictError, SheetValidationError, character_sheet_store,
)

router = APIRouter(prefix="/character-sheets", tags=["character-sheets"])


class CharacterSheetCreateRequest(BaseModel):
    template_key: str
    name: str
    session_id: Optional[str] = None
    fields: Dict[str, Any] = Field(default_factory=dict)


class CharacterSheetUpdateRequest(BaseModel):
    name: Optional[str] = None
    fields: Optional[Dict[str, Any]] = None
    expected_version: Optional[int] = None
    reason: str = "sheet update"


def _sheet_text_lines(sheet: Dict[str, Any]) -> List[str]:
    lines = [
        f"Character Sheet: {sheet.get('name', 'Untitled')}",
        f"Template: {sheet.get('template_key', '')}",
        f"Genre: {sheet.get('genre', '')}",
        f"Audience: {sheet.get('audience', '')}",
        f"Session ID: {sheet.get('session_id', '')}",
        "",
        "Details:",
    ]

    fields = sheet.get("fields", {})
    schema = sheet.get("field_schema", [])
    schema_labels = {item.get("name"): item.get("label", item.get("name")) for item in schema}

    for key, value in fields.items():
        label = schema_labels.get(key, key)
        lines.append(f"- {label}: {value}")

    return lines


def _build_pdf(sheet: Dict[str, Any]) -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    text = "\n".join(_sheet_text_lines(sheet))
    rect = fitz.Rect(40, 40, 560, 800)
    page.insert_textbox(rect, text, fontsize=11, fontname="helv", align=fitz.TEXT_ALIGN_LEFT)
    data = doc.tobytes()
    doc.close()
    return data


def _build_docx(sheet: Dict[str, Any]) -> bytes:
    paragraphs = [f"<w:p><w:r><w:t>{escape(line)}</w:t></w:r></w:p>" for line in _sheet_text_lines(sheet)]
    document_xml = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        "<w:document xmlns:wpc=\"http://schemas.microsoft.com/office/word/2010/wordprocessingCanvas\" "
        "xmlns:mc=\"http://schemas.openxmlformats.org/markup-compatibility/2006\" "
        "xmlns:o=\"urn:schemas-microsoft-com:office:office\" "
        "xmlns:r=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships\" "
        "xmlns:m=\"http://schemas.openxmlformats.org/officeDocument/2006/math\" "
        "xmlns:v=\"urn:schemas-microsoft-com:vml\" "
        "xmlns:wp14=\"http://schemas.microsoft.com/office/word/2010/wordprocessingDrawing\" "
        "xmlns:wp=\"http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing\" "
        "xmlns:w10=\"urn:schemas-microsoft-com:office:word\" "
        "xmlns:w=\"http://schemas.openxmlformats.org/wordprocessingml/2006/main\" "
        "xmlns:w14=\"http://schemas.microsoft.com/office/word/2010/wordml\" "
        "xmlns:wpg=\"http://schemas.microsoft.com/office/word/2010/wordprocessingGroup\" "
        "xmlns:wpi=\"http://schemas.microsoft.com/office/word/2010/wordprocessingInk\" "
        "xmlns:wne=\"http://schemas.microsoft.com/office/word/2006/wordml\" "
        "xmlns:wps=\"http://schemas.microsoft.com/office/word/2010/wordprocessingShape\" mc:Ignorable=\"w14 wp14\">"
        "<w:body>"
        f"{''.join(paragraphs)}"
        "<w:sectPr><w:pgSz w:w=\"12240\" w:h=\"15840\"/><w:pgMar w:top=\"1440\" w:right=\"1440\" w:bottom=\"1440\" w:left=\"1440\" w:header=\"708\" w:footer=\"708\" w:gutter=\"0\"/></w:sectPr>"
        "</w:body></w:document>"
    )

    content_types_xml = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        "<Types xmlns=\"http://schemas.openxmlformats.org/package/2006/content-types\">"
        "<Default Extension=\"rels\" ContentType=\"application/vnd.openxmlformats-package.relationships+xml\"/>"
        "<Default Extension=\"xml\" ContentType=\"application/xml\"/>"
        "<Override PartName=\"/word/document.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml\"/>"
        "</Types>"
    )

    rels_xml = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        "<Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\">"
        "<Relationship Id=\"rId1\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument\" Target=\"word/document.xml\"/>"
        "</Relationships>"
    )

    memory_file = BytesIO()
    with ZipFile(memory_file, "w", ZIP_DEFLATED) as docx:
        docx.writestr("[Content_Types].xml", content_types_xml)
        docx.writestr("_rels/.rels", rels_xml)
        docx.writestr("word/document.xml", document_xml)

    return memory_file.getvalue()


@router.get("/templates")
def list_templates(
    genre: Optional[str] = Query(default=None),
    audience: Optional[str] = Query(default=None),
):
    templates = character_sheet_store.list_templates(genre=genre, audience=audience)
    return {"templates": templates}


@router.get("/")
def list_sheets(session_id: Optional[str] = Query(default=None)):
    sheets = character_sheet_store.list_sheets(session_id=session_id)
    return {"sheets": sheets}


@router.post("/")
def create_sheet(payload: CharacterSheetCreateRequest):
    try:
        sheet = character_sheet_store.create_sheet(
            template_key=payload.template_key,
            name=payload.name,
            session_id=payload.session_id,
            fields=payload.fields,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return {"sheet": sheet}


@router.get("/{sheet_id}")
def get_sheet(sheet_id: str):
    try:
        sheet = character_sheet_store.get_sheet(sheet_id)
    except (KeyError, SheetValidationError) as exc:
        raise HTTPException(status_code=404, detail="Sheet not found") from exc
    return {"sheet": sheet}


@router.put("/{sheet_id}")
def update_sheet(sheet_id: str, payload: CharacterSheetUpdateRequest):
    try:
        sheet = character_sheet_store.update_sheet(
            sheet_id=sheet_id,
            name=payload.name,
            fields=payload.fields,
            expected_version=payload.expected_version,
            reason=payload.reason,
        )
    except SheetConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except SheetValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Sheet not found") from exc
    return {"sheet": sheet}


@router.get("/{sheet_id}/history")
def sheet_history(sheet_id: str):
    try:
        return {"history": character_sheet_store.list_history(sheet_id)}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Sheet not found") from exc


class SheetRevertRequest(BaseModel):
    expected_version: Optional[int] = None


@router.post("/{sheet_id}/history/{version}/revert")
def revert_sheet(sheet_id: str, version: int, payload: SheetRevertRequest = SheetRevertRequest()):
    try:
        sheet = character_sheet_store.revert_sheet(sheet_id, version, payload.expected_version)
    except SheetConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (KeyError, SheetValidationError) as exc:
        raise HTTPException(status_code=404, detail="Sheet or version not found") from exc
    return {"sheet": sheet}


@router.get("/{sheet_id}/export")
def export_sheet(sheet_id: str, format: str = Query(pattern="^(pdf|docx)$")):
    try:
        sheet = character_sheet_store.get_sheet(sheet_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Sheet not found") from exc

    safe_name = (sheet.get("name") or "character_sheet").strip().replace(" ", "_")
    safe_name = "".join(ch for ch in safe_name if ch.isalnum() or ch in {"_", "-"}) or "character_sheet"

    if format == "pdf":
        body = _build_pdf(sheet)
        media_type = "application/pdf"
    else:
        body = _build_docx(sheet)
        media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

    headers = {
        "Content-Disposition": f"attachment; filename={safe_name}.{format}",
    }
    return Response(content=body, media_type=media_type, headers=headers)
