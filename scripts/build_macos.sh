#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ "$(uname -s)" != Darwin || "$(uname -m)" != arm64 ]]; then
  echo "Build on an Apple Silicon Mac with native arm64 Python 3.12+." >&2
  exit 1
fi
if [[ -z "${DEVELOPER_DIR:-}" && -d /Library/Developer/CommandLineTools ]]; then
  export DEVELOPER_DIR=/Library/Developer/CommandLineTools
fi
if [[ -z "${PYTHON_BIN:-}" && -x /Library/Frameworks/Python.framework/Versions/3.13/bin/python3 ]]; then
  PYTHON_BIN=/Library/Frameworks/Python.framework/Versions/3.13/bin/python3
fi
if [[ ! -x .venv-build/bin/python ]]; then
  "${PYTHON_BIN:-python3}" -m venv .venv-build
fi
.venv-build/bin/python -c 'import platform, sys; assert platform.machine() == "arm64" and sys.version_info >= (3,12), "Native arm64 Python 3.12+ required"'
.venv-build/bin/python -m pip install -r requirements-build.txt
.venv-build/bin/python scripts/macos_icon.py
export PYINSTALLER_CONFIG_DIR="$PWD/build/pyinstaller-cache"
if [[ -n "${FINVIZ_DEVELOPER_ID:-}" ]]; then
  export PYINSTALLER_STRICT_BUNDLE_CODESIGN_ERROR=1
fi
.venv-build/bin/python -m PyInstaller --noconfirm --clean --workpath build/macos --distpath dist "packaging/Finviz Tracker.spec"
chmod 755 "dist/Finviz Tracker.app/Contents/MacOS/Finviz Tracker"
if [[ -n "${FINVIZ_DEVELOPER_ID:-}" ]]; then
  codesign --force --options runtime --timestamp --sign "$FINVIZ_DEVELOPER_ID" "dist/Finviz Tracker.app"
else
  codesign --force --deep --sign - "dist/Finviz Tracker.app"
fi
.venv-build/bin/python scripts/check_macos_bundle.py "dist/Finviz Tracker.app"
codesign --verify --deep --strict "dist/Finviz Tracker.app"
ditto -c -k --sequesterRsrc --keepParent "dist/Finviz Tracker.app" "dist/Finviz Tracker-macOS-arm64.zip"
.venv-build/bin/python scripts/check_macos_zip.py "dist/Finviz Tracker.app" "dist/Finviz Tracker-macOS-arm64.zip"
./scripts/create_macos_dmg.sh "dist/Finviz Tracker.app" "dist/Finviz Tracker-macOS-arm64.dmg"
if [[ -n "${FINVIZ_DEVELOPER_ID:-}" ]]; then
  codesign --force --timestamp --identifier local.finviz.tracker.dmg --sign "$FINVIZ_DEVELOPER_ID" "dist/Finviz Tracker-macOS-arm64.dmg"
  codesign --verify --verbose=2 "dist/Finviz Tracker-macOS-arm64.dmg"
fi
.venv-build/bin/python scripts/check_macos_dmg.py "dist/Finviz Tracker.app" "dist/Finviz Tracker-macOS-arm64.dmg"
(cd dist && shasum -a 256 "Finviz Tracker-macOS-arm64.zip" > "Finviz Tracker-macOS-arm64.zip.sha256")
(cd dist && shasum -a 256 "Finviz Tracker-macOS-arm64.dmg" > "Finviz Tracker-macOS-arm64.dmg.sha256")
echo "Built: $PWD/dist/Finviz Tracker.app"
if [[ -n "${FINVIZ_DEVELOPER_ID:-}" ]]; then
  echo "Developer ID-signed DMG (not yet notarized): $PWD/dist/Finviz Tracker-macOS-arm64.dmg"
else
  echo "Private test DMG (ad-hoc signed app): $PWD/dist/Finviz Tracker-macOS-arm64.dmg"
fi
echo "ZIP fallback: $PWD/dist/Finviz Tracker-macOS-arm64.zip"
