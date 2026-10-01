from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine

from ..services.app_paths import get_data_dir, get_frontend_dir


def create_campaign_engine() -> Engine:
    database_path = get_data_dir() / "campaigns.db"
    database_path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{database_path.as_posix()}")

    @event.listens_for(engine, "connect")
    def configure_sqlite(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    return engine


def upgrade_database() -> None:
    config = Config()
    config.set_main_option(
        "script_location", str(get_frontend_dir().parent / "backend" / "persistence" / "migrations")
    )
    engine = create_campaign_engine()
    try:
        with engine.begin() as connection:
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
    finally:
        engine.dispose()