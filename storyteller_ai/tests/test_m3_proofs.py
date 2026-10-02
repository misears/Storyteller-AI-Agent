from backend.rules.compatibility import validate_ruleset_mix
from backend.rules.registry import RulesetRegistry
from backend.services.document_store import DocumentStore
from backend.services.pack_importer import PackImporter


def test_import_proof_creates_d20_pack_without_bundling_source_text(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    monkeypatch.setenv("STORYTELLER_DATA_DIR", str(data_dir))
    store = DocumentStore()
    document_id = store.add_document(
        "srd-proof.pdf", "D&D SRD 5.2 proof fixture", "d20 test fixture", b"pdf",
    )
    importer = PackImporter(store)
    job = importer.start([document_id])
    importer.answer(job.id, {"manifest": {
        "id": "dnd-srd-5-2-proof", "name": "D20 SRD Proof",
        "dice": {"kind": "sum_vs_target", "default_expression": "1d20+{modifier}"},
    }})
    assert importer.validate(job.id).status == "validated"
    assert importer.commit(job.id).status == "committed"
    pack = RulesetRegistry([("local", data_dir / "packs" / "rulesets")]).get("dnd-srd-5-2-proof")
    assert pack.dice.kind == "sum_vs_target"
    assert "d20 test fixture" not in (data_dir / "packs" / "rulesets" / "dnd-srd-5-2-proof" / "ruleset.yaml").read_text()


def test_cross_genre_ruleset_mix_uses_family_or_outcome_ladder():
    registry = RulesetRegistry()

    same_family = validate_ruleset_mix(registry, ["vtm-revised", "demon-the-fallen"])
    different_family = validate_ruleset_mix(registry, ["vtm-revised", "pbta-generic"])

    assert same_family["comparison"] == "direct"
    assert different_family["comparison"] == "outcome_ladder"