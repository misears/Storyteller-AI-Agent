import io
from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel
from typing import Any, Dict

from ..services.document_store import document_store
from ..services.pdf_ingest import extract_text_from_pdf

router = APIRouter(prefix="/documents", tags=["documents"])


class DocumentResponse(BaseModel):
    document_id: str
    title: str
    size: int


class DocumentListResponse(BaseModel):
    documents: list[DocumentResponse]


class RetrieveRequest(BaseModel):
    query: str


class RetrieveResponse(BaseModel):
    results: str


@router.post("/upload")
async def upload_document(file: UploadFile = File(...)) -> Dict[str, Any]:
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    contents = await file.read()
    text = extract_text_from_pdf(io.BytesIO(contents))
    document_id = file.filename
    document_store.add_document(document_id=document_id, title=file.filename, text=text)
    return {"document_id": document_id, "title": file.filename, "size": len(text)}


@router.get("/list", response_model=DocumentListResponse)
def list_documents() -> DocumentListResponse:
    return {"documents": document_store.list_documents()}


@router.post("/retrieve", response_model=RetrieveResponse)
def retrieve_documents(payload: RetrieveRequest) -> RetrieveResponse:
    results = document_store.retrieve(payload.query)
    return {"results": results}
