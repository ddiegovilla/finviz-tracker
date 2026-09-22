import os
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files

root = Path(SPECPATH).parent
signing_identity = os.environ.get("FINVIZ_DEVELOPER_ID") or None
icon = root / "packaging" / "Finviz Tracker.icns"
if not icon.exists():
    icon = root / "build" / "Finviz Tracker.icns"
analysis = Analysis(
    [str(root / "packaging" / "macos_entry.py")],
    pathex=[str(root)],
    datas=[(str(root / "frontend"), "frontend"), (str(root / "config"), "config"),
           (str(root / "scripts/collect_macos_diagnostics.sh"), ".")]
          + collect_data_files("tzdata"),
    runtime_hooks=[str(root / "packaging/runtime_startup.py")],
    hiddenimports=["webview.platforms.cocoa"],
    excludes=["pytest", "playwright", "tkinter", "PyQt5", "PyQt6", "PySide6"],
)
archive = PYZ(analysis.pure)
executable = EXE(archive, analysis.scripts, [], exclude_binaries=True,
                 name="Finviz Tracker", console=False, target_arch="arm64",
                 codesign_identity=signing_identity)
collection = COLLECT(executable, analysis.binaries, analysis.datas, name="Finviz Tracker")
app = BUNDLE(collection, name="Finviz Tracker.app", icon=str(icon) if icon.exists() else None,
             bundle_identifier="local.finviz.tracker",
             info_plist={"CFBundleDisplayName": "Finviz Tracker", "CFBundleShortVersionString": "1.0.1",
                         "CFBundleVersion": "3", "NSHighResolutionCapable": True,
                         "LSMinimumSystemVersion": "14.0",
                         "NSAppTransportSecurity": {"NSAllowsLocalNetworking": True}})
