import importlib
import asyncio
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory


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


def test_empty_data_dir_migrates_campaign_database(tmp_path, monkeypatch):
    from backend.main import app
    from backend.persistence.db import create_campaign_engine
    from backend.services.app_paths import get_frontend_dir

    monkeypatch.setenv("STORYTELLER_DATA_DIR", str(tmp_path))
    monkeypatch.setattr("backend.main.launch_browser_when_ready", lambda: None)

    async def start_app():
        async with app.router.lifespan_context(app):
            pass

    asyncio.run(start_app())
    assert (tmp_path / "campaigns.db").is_file()

    config = Config()
    config.set_main_option(
        "script_location", str(get_frontend_dir().parent / "backend" / "persistence" / "migrations")
    )
    head_revision = ScriptDirectory.from_config(config).get_current_head()
    engine = create_campaign_engine()
    try:
        with engine.connect() as connection:
            assert connection.exec_driver_sql("SELECT version_num FROM alembic_version").scalar() == head_revision
            assert connection.exec_driver_sql("PRAGMA journal_mode").scalar() == "wal"
            assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar() == 1
    finally:
        engine.dispose()
