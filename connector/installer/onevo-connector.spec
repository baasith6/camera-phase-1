# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for ONEVO Local Connector (one-file Windows x64).
# Invoked by installer/build.ps1 Ã¢â‚¬â€ do not run manually unless debugging.

import sys
from pathlib import Path

block_cipher = None
root = Path(SPECPATH).resolve().parent  # connector/
app_dir = root / "app"
launcher = root / "onevo_launcher.py"

a = Analysis(
    [str(launcher)],
    pathex=[str(root)],
    binaries=[],
    datas=[],
    hiddenimports=[
        "uvicorn.logging",
        "uvicorn.loops",
        "uvicorn.loops.auto",
        "uvicorn.protocols",
        "uvicorn.protocols.http",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.websockets",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.lifespan",
        "uvicorn.lifespan.on",
        "fastapi",
        "multipart",
        "cv2",
        "numpy",
        "onvif",
        "zeep",
        "wsdiscovery",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
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
    name="onevo-connector",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
