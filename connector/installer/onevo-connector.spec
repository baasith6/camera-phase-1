# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for ONEVO Local Connector (one-file Windows x64).
# Invoked by installer/build.ps1 Ã¢â‚¬â€ do not run manually unless debugging.

import sys
from pathlib import Path

block_cipher = None
root = Path(SPECPATH).resolve().parent  # connector/
app_dir = root / "app"
launcher = root / "onevo_launcher.py"
icon_file = root / "installer" / "assets" / "onevo.ico"

a = Analysis(
    [str(launcher)],
    pathex=[str(root)],
    binaries=[],
    datas=[(str(icon_file), "assets")],
    hiddenimports=[
        "uvicorn.logging",
        "uvicorn.loops",
        "uvicorn.loops.auto",
        "uvicorn.protocols",
        "uvicorn.protocols.http",
        "uvicorn.protocols.http.auto",
        "uvicorn.lifespan",
        "uvicorn.lifespan.on",
        "fastapi",
        "multipart",
        "cv2",
        "numpy",
        "onvif",
        "zeep",
        "wsdiscovery",
        "pystray",
        "pystray._win32",
        "PIL",
        "PIL.Image",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "torch", "torchvision", "torchaudio", "tensorflow", "keras",
        "onnx", "onnxruntime", "pandas", "matplotlib", "sklearn", "scipy",
        "IPython", "jupyter", "notebook",
        "tkinter", "_tkinter", "tcl", "tk",
        "gi", "pystray._gtk", "pystray._xorg", "pystray._appindicator",
        "websockets",
    ],
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
    icon=str(icon_file),
)
