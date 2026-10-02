from backend.services.document_store import DocumentStore
from backend.services.pack_importer import PackImporter


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