import re
from typing import Dict, List


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"\w+", text.lower()))


class DocumentStore:
    def __init__(self) -> None:
        self.documents: Dict[str, Dict[str, str]] = {}

    def add_document(self, document_id: str, title: str, text: str) -> None:
        self.documents[document_id] = {
            "title": title,
            "text": text,
        }

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
