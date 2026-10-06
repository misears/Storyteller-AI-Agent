import io
import logging
from typing import Any, Dict, List, Literal

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from ..services.document_store import document_store
from ..services.pdf_ingest import OCRUnavailableError, extract_pages_from_pdf, get_ocr_runtime_status

router = APIRouter(prefix="/documents", tags=["documents"])
logger = logging.getLogger(__name__)
DocumentRole = Literal["core_rules", "supplement", "flavor", "chronicle", "reference"]


class DocumentResponse(BaseModel):
    document_id: str
    title: str
    size: int
    genres: List[str] = Field(default_factory=list)
    role: DocumentRole = "reference"
    page_count: int = 1


class DocumentListResponse(BaseModel):
    documents: List[DocumentResponse]


class DocumentUploadResult(BaseModel):
    document_id: str
    title: str
    size: int
    genres: List[str] = Field(default_factory=list)
    role: DocumentRole = "reference"


class DocumentUploadResponse(BaseModel):
    documents: List[DocumentUploadResult]


class RetrieveRequest(BaseModel):
    query: str


class RetrieveResponse(BaseModel):
    results: str


class ScopedRetrieveResult(BaseModel):
    document_id: str
    title: str
    page: int
    snippet: str


class ScopedRetrieveResponse(BaseModel):
    results: List[ScopedRetrieveResult]


class DeleteDocumentResponse(BaseModel):
    deleted: bool
    document_id: str


class UpdateDocumentGenresRequest(BaseModel):
    genres: List[str] = Field(default_factory=list)


class UpdateDocumentGenresResponse(BaseModel):
    updated: bool
    document_id: str
    genres: List[str] = Field(default_factory=list)


def _parse_genres_csv(raw_value: str) -> List[str]:
    if not raw_value:
        return []
    seen = set()
    parsed = []
    for item in raw_value.split(","):
        value = item.strip().lower()
        if not value or value in seen:
            continue
        seen.add(value)
        parsed.append(value)
    return parsed


@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(
    files: List[UploadFile] = File(...),
    genres: str = Form(default=""),
    role: DocumentRole = Form(default="reference"),
) -> Dict[str, Any]:
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded")

    parsed_genres = _parse_genres_csv(genres)

    ocr_active, ocr_detail = get_ocr_runtime_status()
    logger.info(
        "PDF upload request: files=%d ocr_active=%s detail=%s",
        len(files),
        ocr_active,
        ocr_detail,
    )

    documents = []
    for file in files:
        if file.content_type != "application/pdf" and not file.filename.lower().endswith(".pdf"):
            raise HTTPException(status_code=400, detail=f"Only PDF files are supported: {file.filename}")

        contents = await file.read()
        try:
            page_chunks = extract_pages_from_pdf(io.BytesIO(contents))
        except OCRUnavailableError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        text = "\n\n".join(page_chunks)
        document_id = document_store.add_document(
            document_id=file.filename,
            title=file.filename,
            text=text,
            pdf_bytes=contents,
            genres=parsed_genres,
            page_chunks=page_chunks,
            role=role,
        )
        documents.append(
            {
                "document_id": document_id,
                "title": file.filename,
                "size": len(text),
                "genres": parsed_genres,
                "role": role,
            }
        )

    return {"documents": documents}


@router.get("/list", response_model=DocumentListResponse)
def list_documents() -> DocumentListResponse:
    return {"documents": document_store.list_documents()}


class DocumentRoleRequest(BaseModel):
    role: DocumentRole


@router.put("/{document_id}/role")
def update_document_role(document_id: str, payload: DocumentRoleRequest):
    if not document_store.update_document_role(document_id, payload.role):
        raise HTTPException(status_code=404, detail="PDF not found")
    return {"document_id": document_id, "role": payload.role}


@router.get("/{document_id}/pages")
def document_pages(document_id: str, start_page: int = 1, count: int = 3):
    try:
        return {"pages": document_store.get_pages(document_id, start_page, count)}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/retrieve", response_model=RetrieveResponse)
def retrieve_documents(payload: RetrieveRequest) -> RetrieveResponse:
    results = document_store.retrieve(payload.query)
    return {"results": results}


@router.post("/retrieve-scoped", response_model=ScopedRetrieveResponse)
def retrieve_scoped_documents(query: str, document_ids: List[str]) -> ScopedRetrieveResponse:
    results = document_store.retrieve_scoped(query, document_ids)
    return {"results": results}


@router.delete("/{document_id}", response_model=DeleteDocumentResponse)
def delete_document(document_id: str) -> DeleteDocumentResponse:
    deleted = document_store.delete_document(document_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Document not found: {document_id}")
    return {"deleted": True, "document_id": document_id}


@router.put("/{document_id}/genres", response_model=UpdateDocumentGenresResponse)
def update_document_genres(
    document_id: str,
    payload: UpdateDocumentGenresRequest,
) -> UpdateDocumentGenresResponse:
    updated = document_store.update_document_genres(document_id, payload.genres)
    if not updated:
        raise HTTPException(status_code=404, detail=f"Document not found: {document_id}")
    return {"updated": True, "document_id": document_id, "genres": payload.genres}
