# macOS portability and launch diagnostics

## Confirmed recipient result

The recipient's M1 MacBook Air on macOS Tahoe 26.6.2 received a ZIP whose SHA-256
passed. Its extracted app had `com.apple.quarantine: 0087;...;WhatsApp;`.
Direct execution returned `zsh: operation not permitted`; `spctl` said **“File
created by an AppSandbox, exec/open not allowed.”** `codesign --verify` passed.
Removing quarantine from that *one verified app bundle* made the same app launch.
This proves that the recipient's arm64 binary, bundled dependencies, and app data
path work on that M1 Mac. The blocking issue was hard quarantine from the WhatsApp
transfer, not a build or archive integrity failure. Apple's [hard-quarantine error](https://developer.apple.com/documentation/security/errseccsfilehardquarantined)
and [Developer Technical Support discussion](https://developer.apple.com/forums/thread/767612)
describe this sandbox-created denial. Developer ID notarization addresses ordinary
Gatekeeper trust, but is not a promise to overcome this flag.

An earlier diagnostic command assumed the app had been copied to `/Applications`.
Its “No such file or directory” result identified that wrong path. The ZIP itself
contains `Finviz Tracker.app/Contents/Resources/collect_macos_diagnostics.sh`.
The script's mode is 644 and it is invoked with `/bin/bash`; the main executable's
mode is 755. The ZIP's top-level app name is exactly `Finviz Tracker.app`. Finder
may rename a copy if that name already exists in the destination folder.

## Current build checks

Version **1.0.1 (3)** targets arm64 and macOS 14+. The release script checks
Info.plist, all 71 native binaries and their dependencies, permissions, signature,
fresh ZIP extraction, and a mounted DMG. The DMG contains the same signed app and
an Applications shortcut. A no-scan launch check has passed from the built app,
a fresh ZIP extraction, a DMG copy into an isolated Applications-style directory,
and the real `/Applications/Finviz Tracker.app` path on the build Mac. Saved history
was preserved. The recipient's M1 result provides the separate macOS 26.6.2 runtime
evidence. See [release checks](MACOS_RELEASE.md#release-verification).

The private build is ad-hoc signed. `codesign` integrity verification can pass
while `spctl` rejects distribution. Neither ZIP nor DMG removes quarantine or
provides a Developer ID publisher identity. See the [short installation guide](MACOS_RECIPIENT_GUIDE.md)
for the supported Open Anyway flow and narrowly scoped advanced fallback.

## Compare the exact copies before diagnosing

Quit Finviz Tracker first. Use Finder → Applications to replace an older app with
the newly verified copy. Leave `~/Library/Application Support/Finviz Tracker/`
untouched; it contains saved history. The following commands report the build and
quarantine on a Downloads extraction and on the installed app. Change
`DOWNLOADS_APP` if Finder gave the extracted app a different name or directory.

```bash
DOWNLOADS_APP="$HOME/Downloads/Finviz Tracker.app"
for APP in "$DOWNLOADS_APP" "/Applications/Finviz Tracker.app"; do
  echo "--- $APP ---"
  if [[ -d "$APP" ]]; then
    /usr/libexec/PlistBuddy -c 'Print :CFBundleVersion' "$APP/Contents/Info.plist"
    xattr -p com.apple.quarantine "$APP" 2>&1
    xattr -p com.apple.quarantine "$APP/Contents/MacOS/Finviz Tracker" 2>&1
    codesign --verify --deep --strict "$APP"
  else
    echo 'App does not exist at this path'
  fi
done
```

Build `3` is the current release. A missing quarantine attribute reports “No such
xattr.” To inspect a previously extracted app elsewhere in Downloads, locate it
first with:

```bash
find "$HOME/Downloads" -maxdepth 3 -type d -name 'Finviz Tracker*.app' -print
```

Launch specifically from Applications with Finder, or use:

```bash
open "/Applications/Finviz Tracker.app"
```

## Collect a focused report from the app that actually exists

Set `APP` to the real path. The first example is a manual ZIP extraction in a fresh
Downloads subdirectory; for an installed app, use `/Applications/Finviz Tracker.app`.
The bundled script collects OS, signature, quarantine, LaunchServices, and recent
startup diagnostics without changing security settings or collecting the database.

```bash
APP="$HOME/Downloads/Finviz-Tracker-diagnostic-extract/Finviz Tracker.app"
ls -ld "$APP" "$APP/Contents/MacOS/Finviz Tracker" "$APP/Contents/Resources/collect_macos_diagnostics.sh"
sw_vers
uname -m
file "$APP/Contents/MacOS/Finviz Tracker"
codesign --verify --deep --strict --verbose=2 "$APP"
spctl --assess --type execute --verbose=4 "$APP"
xattr -p com.apple.quarantine "$APP"
if [[ -f "$APP/Contents/Resources/collect_macos_diagnostics.sh" ]]; then
  /bin/bash "$APP/Contents/Resources/collect_macos_diagnostics.sh" "$APP" --launch
fi
```

If the bundled script cannot run, capture the main executable directly. `--verify`
tests the packaged window and exits without a Finviz scan:

```bash
"$APP/Contents/MacOS/Finviz Tracker" --verify > "$HOME/Downloads/finviz-stdout.log" 2> "$HOME/Downloads/finviz-stderr.log"
echo "Direct launch exit: $?"
cat "$HOME/Downloads/finviz-stdout.log" "$HOME/Downloads/finviz-stderr.log"
```

The diagnostic report is written under
`~/Library/Application Support/Finviz Tracker/logs/`. Review usernames and paths
before sharing it. Do not send `session.json`, the history database, or the entire
Application Support folder. A failure before Python starts may produce no startup
log; `spctl`, LaunchServices, and direct stderr then supply the relevant evidence.
