# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_data_files

datas = collect_data_files("PySide6", include_py_files=True) + collect_data_files(
    "shiboken6", include_py_files=True
)


def exclude_conflicting_root_binaries(toc):
    filtered = []
    for entry in toc:
        destination = entry[0].replace("\\", "/")
        name = destination.rsplit("/", 1)[-1].lower()
        if "/" not in destination and name.startswith("icu") and name.endswith(".dll"):
            continue
        filtered.append(entry)
    return filtered


app = Analysis(
    ["src/remote_image_compare/app.py"],
    pathex=["src"],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
app.binaries = exclude_conflicting_root_binaries(app.binaries)
pyz = PYZ(app.pure)

exe = EXE(
    pyz,
    app.scripts,
    [],
    exclude_binaries=True,
    name="mulitImgViewer",
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
    app.binaries,
    app.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="mulitImgViewer",
)
