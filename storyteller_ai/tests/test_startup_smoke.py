import importlib
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = REPO_ROOT / "backend"


def test_backend_sources_have_no_merge_markers():
    for path in BACKEND_DIR.rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        for line in source.splitlines():
            assert not line.startswith("<<<<<<< "), f"Unresolved merge marker in {path}"
            assert line.strip() != "=======", f"Unresolved merge marker in {path}"
            assert not line.startswith(">>>>>>> "), f"Unresolved merge marker in {path}"


def test_backend_python_files_compile():
    for path in BACKEND_DIR.rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        compile(source, str(path), "exec")


def test_backend_main_app_importable():
    module = importlib.import_module("backend.main")
    assert hasattr(module, "app")


def test_empty_test_data_dir_initializes_stores():
    from backend.services.app_paths import get_data_dir
    from backend.services.character_sheet_store import character_sheet_store
    from backend.services.document_store import document_store

    assert document_store.database_path == get_data_dir() / "storyteller.db"
    assert document_store.database_path.is_file()
    assert character_sheet_store.store_path == get_data_dir() / "character_sheets.json"
    assert character_sheet_store.list_templates()
