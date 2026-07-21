import json
import re
import sqlite3
from typing import Dict, List

from .app_paths import get_data_dir


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"\w+", text.lower()))


def _normalize_genres(genres: List[str] | None) -> List[str]:
    if not genres:
        return []

    normalized = []
    seen = set()
    for genre in genres:
        value = genre.strip().lower()
        if not value or value in seen:
            continue
        seen.add(value)
        normalized.append(value)
    return normalized


def _parse_genre_tags(raw_value: str) -> List[str]:
    if not raw_value:
        return []
    try:
        parsed = json.loads(raw_value)
    except json.JSONDecodeError:
        return []

    if not isinstance(parsed, list):
        return []

    return _normalize_genres([str(item) for item in parsed])


class DocumentStore:
    def __init__(self) -> None:
        self.base_dir = get_data_dir().parent
        self.data_dir = get_data_dir()
        self.document_dir = self.data_dir / "documents"
        self.metadata_path = self.data_dir / "documents.json"
        self.database_path = self.data_dir / "storyteller.db"
        self.document_dir.mkdir(parents=True, exist_ok=True)
        self._init_db()
        self._migrate_legacy_json()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _init_db(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS documents (
                    document_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    text TEXT NOT NULL,
                    path TEXT NOT NULL,
                    genre_tags TEXT NOT NULL DEFAULT '[]',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

            columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(documents)").fetchall()
            }
            if "genre_tags" not in columns:
                connection.execute(
                    "ALTER TABLE documents ADD COLUMN genre_tags TEXT NOT NULL DEFAULT '[]'"
                )
            connection.commit()

    def _document_exists(self, document_id: str) -> bool:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT 1 FROM documents WHERE document_id = ? LIMIT 1",
                (document_id,),
            ).fetchone()
        return row is not None

    def _normalize_id(self, filename: str) -> str:
        safe = re.sub(r"[^\w\-. ]", "_", filename).strip()
        if not safe:
            safe = "document"

        candidate = safe
        counter = 1
        while self._document_exists(candidate) or (self.document_dir / candidate).exists():
            candidate = f"{safe}-{counter}"
            counter += 1

        return candidate

    def _migrate_legacy_json(self) -> None:
        if not self.metadata_path.exists():
            return

        try:
            data = json.loads(self.metadata_path.read_text(encoding="utf-8"))
            documents = data.get("documents", {})
        except (json.JSONDecodeError, OSError):
            documents = {}

        if not documents:
            return

        with self._connect() as connection:
            for document_id, document in documents.items():
                connection.execute(
                    """
                    INSERT OR IGNORE INTO documents (document_id, title, text, path, genre_tags)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        document_id,
                        document.get("title", document_id),
                        document.get("text", ""),
                        document.get("path", ""),
                        json.dumps(_normalize_genres(document.get("genres", []))),
                    ),
                )
            connection.commit()

    def add_document(
        self,
        document_id: str,
        title: str,
        text: str,
        pdf_bytes: bytes,
        genres: List[str] | None = None,
    ) -> str:
        document_id = self._normalize_id(document_id)
        pdf_path = self.document_dir / document_id
        pdf_path.write_bytes(pdf_bytes)
        normalized_genres = _normalize_genres(genres)

        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO documents (document_id, title, text, path, genre_tags)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    document_id,
                    title,
                    text,
                    str(pdf_path.relative_to(self.base_dir)),
                    json.dumps(normalized_genres),
                ),
            )
            connection.commit()

        return document_id

    def list_documents(self) -> List[Dict[str, str]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT document_id, title, text, genre_tags FROM documents ORDER BY created_at DESC, document_id DESC"
            ).fetchall()

        return [
            {
                "document_id": row["document_id"],
                "title": row["title"],
                "size": len(row["text"]),
                "genres": _parse_genre_tags(row["genre_tags"]),
            }
            for row in rows
        ]

    def update_document_genres(self, document_id: str, genres: List[str] | None) -> bool:
        normalized_genres = _normalize_genres(genres)
        with self._connect() as connection:
            result = connection.execute(
                "UPDATE documents SET genre_tags = ? WHERE document_id = ?",
                (json.dumps(normalized_genres), document_id),
            )
            connection.commit()
            return result.rowcount > 0

    def delete_document(self, document_id: str) -> bool:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT path FROM documents WHERE document_id = ?",
                (document_id,),
            ).fetchone()

            if row is None:
                return False

            path_value = row["path"]
            pdf_path = self.base_dir / path_value if path_value else None
            if pdf_path and pdf_path.exists() and pdf_path.is_file():
                pdf_path.unlink()

            connection.execute(
                "DELETE FROM documents WHERE document_id = ?",
                (document_id,),
            )
            connection.commit()

        return True

    def retrieve(self, query: str, limit: int = 3) -> str:
        if not query.strip():
            return ""

        with self._connect() as connection:
            rows = connection.execute("SELECT title, text FROM documents").fetchall()

        if not rows:
            return ""

        query_tokens = _tokenize(query)
        scores: List[tuple[int, Dict[str, str]]] = []

        for row in rows:
            document = {"title": row["title"], "text": row["text"]}
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
