# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

pyside_dir = Path(SPECPATH) / '.venv' / 'Lib' / 'site-packages' / 'PySide6'
runtime_dlls = ['MSVCP140.dll', 'MSVCP140_1.dll', 'MSVCP140_2.dll',
                'VCRUNTIME140.dll', 'VCRUNTIME140_1.dll']

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[(str(pyside_dir / dll), '.') for dll in runtime_dlls],
    datas=[('data', 'data'), ('map', 'map'), ('ui/icons', 'ui/icons')],
    hiddenimports=['PySide6.QtWebEngineCore', 'PySide6.QtWebEngineWidgets'],
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
    a.binaries,
    a.datas,
    [],
    name='PyGeoTrack',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
