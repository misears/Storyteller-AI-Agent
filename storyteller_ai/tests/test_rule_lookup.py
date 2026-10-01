from backend.services.document_store import DocumentStore


def test_scoped_lookup_returns_only_selected_pages(tmp_path, monkeypatch):
    monkeypatch.setenv("STORYTELLER_DATA_DIR", str(tmp_path / "data"))
    store = DocumentStore()
    first = store.add_document(
        "rules-a.pdf", "Rules A", "ignored", b"pdf",
        page_chunks=["combat rules and difficulty", "character creation"],
    )
    second = store.add_document(
        "rules-b.pdf", "Rules B", "other", b"pdf",
        page_chunks=["combat rules from another book"],
    )

    results = store.retrieve_scoped("difficulty", [first])

    assert [item["document_id"] for item in results] == [first]
    assert results[0]["page"] == 1
    assert store.retrieve_scoped("combat", [second])[0]["document_id"] == second
    assert store.retrieve_scoped("combat", [first])[0]["document_id"] == first