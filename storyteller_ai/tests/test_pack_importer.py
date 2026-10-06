from backend.services.document_store import DocumentStore
from backend.services.pack_importer import PackImporter
import pytest
import sqlite3


def test_import_job_is_resumable_validated_and_committed(tmp_path, monkeypatch):
    monkeypatch.setenv("STORYTELLER_DATA_DIR", str(tmp_path / "data"))
    store = DocumentStore()
    document_id = store.add_document("core.pdf", "Core Rules", "rules", b"pdf", page_chunks=["rules"])
    importer = PackImporter(store)

    job = importer.start([document_id])
    assert importer.get(job.id).status == "classified"
    importer.answer(job.id, {"manifest": {"name": "Verified Imported Rules"}})
    validated = importer.validate(job.id)
    assert validated.status == "validated"
    committed = importer.commit(job.id)

    assert committed.status == "committed"
    assert (tmp_path / "data" / "packs" / "rulesets" / job.draft["manifest"]["id"] / "ruleset.yaml").is_file()


def test_extend_import_bumps_pack_version(tmp_path, monkeypatch):
    monkeypatch.setenv("STORYTELLER_DATA_DIR", str(tmp_path / "data"))
    store = DocumentStore()
    document_id = store.add_document("supplement.pdf", "Supplement", "rules", b"pdf")
    importer = PackImporter(store)

    job = importer.start([document_id], mode="extend", target_pack_id="freeform")

    assert job.draft["manifest"]["id"] == "freeform"
    assert job.draft["manifest"]["version"] == "1.0.1"
    assert job.draft["manifest"]["name"] == "Freeform Storytelling"
    assert "player intent" in job.draft["manifest"]["prompt_digest"]


def test_pdf_roles_persist_and_non_rules_cannot_become_rulesets(tmp_path, monkeypatch):
    monkeypatch.setenv("STORYTELLER_DATA_DIR", str(tmp_path / "data"))
    store = DocumentStore()
    scenario = store.add_document("story.pdf", "A published chronicle", "Scene one", b"pdf", page_chunks=["Scene one", "Scene two"], role="chronicle")
    flavor = store.add_document("flavor.pdf", "Setting flavor", "lore", b"pdf", role="flavor")
    supplement = store.add_document("extra.pdf", "More rules", "rules", b"pdf", role="supplement")
    importer = PackImporter(store)
    for document_id in [scenario, flavor]:
        with pytest.raises(ValueError, match="Only core-rules"):
            importer.start([document_id])
    with pytest.raises(ValueError, match="base ruleset"):
        importer.start([supplement])
    assert importer.start([supplement], "extend", "freeform").classification[supplement] == "supplement"
    assert store.get_pages(scenario, 2)[0]["text"] == "Scene two"
    with pytest.raises(ValueError):
        store.get_pages(scenario, 3)
    assert store.update_document_role(flavor, "reference")
    reloaded = DocumentStore()
    assert next(item for item in reloaded.list_documents() if item["document_id"] == flavor)["role"] == "reference"
    assert reloaded.rules_document_ids([scenario, flavor, supplement]) == [supplement]


def test_legacy_documents_gain_reference_role_without_losing_content(tmp_path, monkeypatch):
    data = tmp_path / "data"
    data.mkdir()
    monkeypatch.setenv("STORYTELLER_DATA_DIR", str(data))
    with sqlite3.connect(data / "storyteller.db") as connection:
        connection.execute("CREATE TABLE documents (document_id TEXT PRIMARY KEY, title TEXT, text TEXT, path TEXT, created_at TEXT)")
        connection.execute("INSERT INTO documents VALUES ('old.pdf', 'Old reference', 'Preserved notes', '', '2020-01-01')")
    store = DocumentStore()
    assert store.list_documents()[0]["role"] == "reference"
    assert store.get_pages("old.pdf")[0]["text"] == "Preserved notes"