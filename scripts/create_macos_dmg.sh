#!/bin/bash
set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "Usage: $0 APP_PATH DMG_PATH" >&2
  exit 2
fi

APP="$(cd "$(dirname "$1")" && pwd)/$(basename "$1")"
DMG="$(cd "$(dirname "$2")" && pwd)/$(basename "$2")"
[[ -d "$APP" ]] || { echo "Missing app: $APP" >&2; exit 1; }

SCRATCH="$(mktemp -d "${TMPDIR:-/tmp}/finviz-dmg.XXXXXX")"
MOUNT="$SCRATCH/mount"
MOUNTED=0
cleanup() {
  if [[ "$MOUNTED" == 1 ]]; then hdiutil detach -quiet "$MOUNT" || true; fi
  rm -rf "$SCRATCH"
}
trap cleanup EXIT

mkdir "$SCRATCH/stage" "$MOUNT"
ditto "$APP" "$SCRATCH/stage/Finviz Tracker.app"
ln -s /Applications "$SCRATCH/stage/Applications"
hdiutil create -quiet -srcfolder "$SCRATCH/stage" -volname "Finviz Tracker" -format UDRW "$SCRATCH/layout.dmg"
hdiutil attach -quiet -readwrite -nobrowse -mountpoint "$MOUNT" "$SCRATCH/layout.dmg"
MOUNTED=1
osascript "$(dirname "$0")/../packaging/dmg_layout.applescript" "$MOUNT"
sync
hdiutil detach -quiet "$MOUNT"
MOUNTED=0
hdiutil convert -quiet "$SCRATCH/layout.dmg" -format UDZO -ov -o "$DMG"
hdiutil verify "$DMG"
