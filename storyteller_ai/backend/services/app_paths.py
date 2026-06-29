from pathlib import Path
import sys


def is_frozen() -> bool:
    return getattr(sys, "frozen", False)


def get_app_root() -> Path:
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def get_frontend_dir() -> Path:
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS")) / "frontend"
    return get_app_root() / "frontend"


def get_data_dir() -> Path:
    if is_frozen():
        return get_app_root() / "data"
    return get_app_root() / "backend" / "data"
