from PyInstaller.utils.hooks import collect_data_files, collect_submodules

hiddenimports = collect_submodules("pyqtgraph")
datas = collect_data_files("pyqtgraph") + [("examples", "examples")]

a = Analysis(
    ["src/circuitcanvas/app.py"],
    pathex=["src"],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="CircuitCanvas",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="CircuitCanvas",
)
app = BUNDLE(
    coll,
    name="CircuitCanvas.app",
    icon=None,
    bundle_identifier="com.peichili.circuitcanvas",
    info_plist={
        "NSHighResolutionCapable": True,
        "CFBundleShortVersionString": "0.1.0",
    },
)
