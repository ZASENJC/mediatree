# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules

SPEC_DIR = Path(SPECPATH).resolve()
ROOT = SPEC_DIR.parents[1]

hiddenimports = []
for package in (
    "aiosqlite",
    "fastapi",
    "httpx",
    "PIL",
    "pydantic",
    "pydantic_settings",
    "starlette",
    "uvicorn",
):
    hiddenimports += collect_submodules(package)

hiddenimports += [
    "charset_normalizer",
    "fontTools",
    "multipart",
    "watchfiles",
]

datas = [
    (str(ROOT / "backend" / "app"), "base/app"),
    (str(ROOT / "frontend" / "dist"), "base/frontend/dist"),
    (str(ROOT / "VERSION"), "base"),
]

if (ROOT / "backend" / "requirements.txt").exists():
    datas.append((str(ROOT / "backend" / "requirements.txt"), "base"))
if (ROOT / "backend" / "constraints.txt").exists():
    datas.append((str(ROOT / "backend" / "constraints.txt"), "base"))
if (ROOT / "packaging" / "windows" / "bin").exists():
    datas.append((str(ROOT / "packaging" / "windows" / "bin"), "base/bin"))

a = Analysis(
    [str(ROOT / "backend" / "app" / "windows_entry.py")],
    pathex=[str(ROOT / "backend")],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="mediatree-server",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="mediatree-server",
)
