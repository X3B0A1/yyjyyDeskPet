# -*- mode: python ; coding: utf-8 -*-
import sys
from pathlib import Path

project = Path(SPECPATH)
is_mac = sys.platform == "darwin"
name = "zgyyjyy桌宠"

a = Analysis(
    [str(project / "main.py")],
    pathex=[str(project)],
    binaries=[],
    datas=([(str(project / image), ".") for image in ("0.png", "c1.png", "c2.png")]
           + [(str(project / "presets"), "presets")]),
    hiddenimports=["pystray._darwin", "macos_pet"] if is_mac else ["pystray._win32"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

if is_mac:
    # A directory bundle avoids one-file extraction on every macOS launch.
    exe = EXE(
        pyz, a.scripts, [], exclude_binaries=True, name=name,
        console=False, argv_emulation=False,
    )
    collection = COLLECT(exe, a.binaries, a.datas, name=name)
    app = BUNDLE(
        collection, name=name + ".app",
        bundle_identifier="com.sylaidesk.pet",
        info_plist={
            "CFBundleDisplayName": name,
            "CFBundleShortVersionString": "1.2.1",
            "NSHighResolutionCapable": True,
            "LSUIElement": True,
        },
    )
else:
    exe = EXE(
        pyz, a.scripts, a.binaries, a.datas, [], name=name,
        console=False,
    )
