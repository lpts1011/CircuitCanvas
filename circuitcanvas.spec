# PyInstaller recipe: a macOS .app on macOS, a CircuitCanvas folder with CircuitCanvas.exe on Windows.
#
#     pyinstaller --noconfirm circuitcanvas.spec
import re
import sys
from pathlib import Path

ROOT = Path(SPECPATH)  # noqa: F821 - defined by PyInstaller
VERSION = re.search(
    r'__version__ = "([^"]+)"', (ROOT / "src/circuitcanvas/__init__.py").read_text()
).group(1)
ICON = str(
    ROOT / "assets/icon" / ("CircuitCanvas.icns" if sys.platform == "darwin" else "CircuitCanvas.ico")
)

# Examples and the window icon live inside the package and are read with importlib.resources.
datas = [
    ("src/circuitcanvas/examples/*.json", "circuitcanvas/examples"),
    ("src/circuitcanvas/resources/*.png", "circuitcanvas/resources"),
]
hiddenimports = ["circuitcanvas.examples", "circuitcanvas.resources"]

a = Analysis(  # noqa: F821
    ["run_circuitcanvas.py"],
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
pyz = PYZ(a.pure)  # noqa: F821
exe = EXE(  # noqa: F821
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="CircuitCanvas",
    icon=ICON,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    # UPX is off: compressed Qt libraries are slow to start and can be flagged by antivirus.
    upx=False,
    console=False,
)
coll = COLLECT(  # noqa: F821
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="CircuitCanvas",
)
# BUNDLE does nothing outside macOS.
app = BUNDLE(  # noqa: F821
    coll,
    name="CircuitCanvas.app",
    icon=ICON,
    bundle_identifier="com.peichili.circuitcanvas",
    version=VERSION,
    info_plist={
        "NSHighResolutionCapable": True,
        "CFBundleShortVersionString": VERSION,
        "CFBundleVersion": VERSION,
        "NSHumanReadableCopyright": "MIT License",
        # Double-clicking a saved .circuitcanvas file in Finder opens it in the app.
        "CFBundleDocumentTypes": [
            {
                "CFBundleTypeName": "CircuitCanvas circuit",
                "CFBundleTypeRole": "Editor",
                "LSHandlerRank": "Owner",
                "LSItemContentTypes": ["com.peichili.circuitcanvas.circuit"],
            }
        ],
        "UTExportedTypeDeclarations": [
            {
                "UTTypeIdentifier": "com.peichili.circuitcanvas.circuit",
                "UTTypeDescription": "CircuitCanvas circuit",
                "UTTypeConformsTo": ["public.json"],
                "UTTypeTagSpecification": {"public.filename-extension": ["circuitcanvas"]},
            }
        ],
    },
)
