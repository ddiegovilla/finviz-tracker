#!/bin/bash
set -u
APP="${1:-/Applications/Finviz Tracker.app}"
LOGS="$HOME/Library/Application Support/Finviz Tracker/logs"
mkdir -p "$LOGS"
REPORT="$LOGS/portability-$(date +%Y%m%d-%H%M%S).log"
{
  date -u
  sw_vers
  uname -m
  plutil -lint "$APP/Contents/Info.plist"
  plutil -p "$APP/Contents/Info.plist"
  EXECUTABLE=$(/usr/libexec/PlistBuddy -c 'Print :CFBundleExecutable' "$APP/Contents/Info.plist")
  file "$APP/Contents/MacOS/$EXECUTABLE"
  stat -f '%Sp %OLp %N' "$APP/Contents/MacOS/$EXECUTABLE"
  ls -la "$APP/Contents/MacOS" "$APP/Contents/Frameworks"
  xattr -lr "$APP"
  codesign -dv --verbose=4 "$APP"
  codesign --verify --deep --strict --verbose=4 "$APP"
  echo "codesign verification exit: $?"
  spctl --assess --type execute --verbose=4 "$APP"
  echo "Gatekeeper exit: $? (rejection is expected for an unnotarized ad-hoc build)"
  if command -v syspolicy_check >/dev/null; then
    syspolicy_check distribution "$APP"
  fi
  if [[ "${2:-}" == --launch ]]; then
    open -n --stdout "$LOGS/launcher-stdout.log" --stderr "$LOGS/launcher-stderr.log" "$APP"
    echo "LaunchServices exit: $?"
    sleep 3
  fi
  /usr/bin/log show --last 5m --style compact --predicate '(eventMessage CONTAINS[c] "Finviz") OR (process == "Finviz Tracker")'
  for LOG in startup.log app.log launcher-stderr.log; do
    echo "--- $LOG ---"
    if [[ -f "$LOGS/$LOG" ]]; then tail -100 "$LOGS/$LOG"; fi
  done
  find "$HOME/Library/Logs/DiagnosticReports" -maxdepth 1 -iname '*Finviz*' -mtime -2 -print
} > "$REPORT" 2>&1
echo "Diagnostics saved to: $REPORT"
echo "Review usernames and paths before sharing. No database or session credentials are collected."
