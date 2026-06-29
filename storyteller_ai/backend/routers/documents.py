import io
from typing import Any, Dict, List

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from ..services.document_store import document_store
from ..services.pdf_ingest import extract_text_from_pdf

router = APIRouter(prefix="/documents", tags=["documents"])


class DocumentResponse(BaseModel):
    document_id: str
    title: str
    size: int


class DocumentListResponse(BaseModel):
    documents: List[DocumentResponse]


class DocumentUploadResult(BaseModel):
    document_id: str
    title: str
    size: int


class DocumentUploadResponse(BaseModel):
    documents: List[DocumentUploadResult]


class RetrieveRequest(BaseModel):
    query: str


class RetrieveResponse(BaseModel):
    results: str


class DeleteDocumentResponse(BaseModel):
    deleted: bool
    document_id: str


@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(files: List[UploadFile] = File(...)) -> Dict[str, Any]:
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded")

    documents = []
    for file in files:
        if file.content_type != "application/pdf" and not file.filename.lower().endswith(".pdf"):
            raise HTTPException(status_code=400, detail=f"Only PDF files are supported: {file.filename}")

        contents = await file.read()
        text = extract_text_from_pdf(io.BytesIO(contents))
        document_id = document_store.add_document(
            document_id=file.filename,
            title=file.filename,
            text=text,
            pdf_bytes=contents,
        )
        documents.append({"document_id": document_id, "title": file.filename, "size": len(text)})

    return {"documents": documents}


@router.get("/list", response_model=DocumentListResponse)
def list_documents() -> DocumentListResponse:
    return {"documents": document_store.list_documents()}


@router.post("/retrieve", response_model=RetrieveResponse)
def retrieve_documents(payload: RetrieveRequest) -> RetrieveResponse:
    results = document_store.retrieve(payload.query)
    return {"results": results}


@router.delete("/{document_id}", response_model=DeleteDocumentResponse)
def delete_document(document_id: str) -> DeleteDocumentResponse:
    deleted = document_store.delete_document(document_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Document not found: {document_id}")
    return {"deleted": True, "document_id": document_id}
