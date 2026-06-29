# PyInstaller spec for Storyteller AI
# Build with: pyinstaller StorytellerAI.spec

from pathlib import Path
import os

from PyInstaller.building.build_main import Analysis, EXE, PYZ
from PyInstaller.utils.hooks import collect_submodules

block_cipher = None
project_root = Path(os.getcwd()).resolve()
frontend_dir = project_root / "frontend"
backend_dir = project_root / "backend"

hiddenimports = []
hiddenimports += collect_submodules("fastapi")
hiddenimports += collect_submodules("starlette")
hiddenimports += collect_submodules("uvicorn")
hiddenimports += collect_submodules("pydantic")
hiddenimports += collect_submodules("httpx")
hiddenimports += collect_submodules("fitz")
hiddenimports += collect_submodules("openai")
hiddenimports += collect_submodules("anthropic")

# Keep the bundled frontend next to the extracted executable resources.
datas = [
    (str(frontend_dir), "frontend"),
]

a = Analysis(
    [str(project_root / "desktop_entry.py")],
    pathex=[str(project_root)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="StorytellerAI",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
)
