import json
import re
from pathlib import Path
from typing import Dict, List


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"\w+", text.lower()))


class DocumentStore:
    def __init__(self) -> None:
        self.base_dir = Path(__file__).resolve().parent.parent
        self.data_dir = self.base_dir / "data"
        self.document_dir = self.data_dir / "documents"
        self.metadata_path = self.data_dir / "documents.json"
        self.document_dir.mkdir(parents=True, exist_ok=True)
        self.documents: Dict[str, Dict[str, str]] = {}
        self._load_documents()

    def _normalize_id(self, filename: str) -> str:
        safe = re.sub(r"[^\w\-. ]", "_", filename).strip()
        if not safe:
            safe = "document"

        candidate = safe
        counter = 1
        while candidate in self.documents or (self.document_dir / candidate).exists():
            candidate = f"{safe}-{counter}"
            counter += 1

        return candidate

    def _load_documents(self) -> None:
        if not self.metadata_path.exists():
            return

        try:
            data = json.loads(self.metadata_path.read_text(encoding="utf-8"))
            for document_id, document in data.get("documents", {}).items():
                self.documents[document_id] = document
        except (json.JSONDecodeError, OSError):
            self.documents = {}

    def _save_metadata(self) -> None:
        payload = {"documents": self.documents}
        self.metadata_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    def add_document(self, document_id: str, title: str, text: str, pdf_bytes: bytes) -> str:
        document_id = self._normalize_id(document_id)
        pdf_path = self.document_dir / document_id
        pdf_path.write_bytes(pdf_bytes)
        self.documents[document_id] = {
            "title": title,
            "text": text,
            "path": str(pdf_path.relative_to(self.base_dir)),
        }
        self._save_metadata()
        return document_id

    def list_documents(self) -> List[Dict[str, str]]:
        return [
            {
                "document_id": document_id,
                "title": document["title"],
                "size": len(document["text"]),
            }
            for document_id, document in self.documents.items()
        ]

    def retrieve(self, query: str, limit: int = 3) -> str:
        if not query.strip() or not self.documents:
            return ""

        query_tokens = _tokenize(query)
        scores: List[tuple[int, Dict[str, str]]] = []

        for document in self.documents.values():
            document_tokens = _tokenize(document["text"])
            score = len(query_tokens.intersection(document_tokens))
            scores.append((score, document))

        scores.sort(key=lambda item: item[0], reverse=True)
        top_docs = [doc for score, doc in scores if score > 0][:limit]

        if not top_docs:
            return ""

        return "\n\n".join(
            f"{doc['title']}\n{doc['text'][:1200]}"
            for doc in top_docs
        )


document_store = DocumentStore()
