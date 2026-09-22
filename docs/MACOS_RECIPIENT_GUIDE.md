# Install Finviz Tracker on an Apple Silicon Mac

This is a **private test build** (version 1.0.1, build 3). It is ad-hoc signed, not
Developer ID signed or notarized. Receive it only from someone you trust. The primary
release file is `Finviz Tracker-macOS-arm64.dmg`; the `.zip` is a fallback.

## Normal install

1. Download the DMG. A direct download opened with Safari is preferable to sending
   the file through WhatsApp, which marked a previous copy with hard quarantine.
2. Quit any open Finviz Tracker with Command-Q. In Finder → Applications, move an old
   `Finviz Tracker.app` to the Trash. Leave `~/Library/Application Support/Finviz Tracker/`
   alone; that folder contains your saved history.
3. Double-click the DMG, then drag **Finviz Tracker.app** onto its **Applications**
   shortcut. Eject the Finviz Tracker disk image.
4. Open Finder → Applications and double-click **Finviz Tracker** there. To check
   that this is the installed copy, choose File → Get Info and confirm **Where:
   Applications** and **Version: 1.0.1**.

If macOS blocks this private build, try to open the app once, then open **System
Settings → Privacy & Security** and use **Open Anyway**, if offered. Authenticate
and confirm. Apple says this option appears after a blocked open and may be
available for about an hour. It may be unavailable on managed Macs or for a hard
quarantine denial. See [Apple's instructions](https://support.apple.com/en-us/102445).

## Advanced troubleshooting: hard quarantine

Use this section only for the exact release received from a trusted sender. Verify
the DMG's SHA-256 against the value the sender supplied through a trusted channel
before changing any quarantine attribute. If you also received the `.sha256` file,
run this from Terminal:

```bash
cd ~/Downloads
shasum -a 256 -c "Finviz Tracker-macOS-arm64.dmg.sha256"
```

Check the installed app's path, build, signature, and quarantine. If you extracted
the ZIP in Downloads, set `DOWNLOADS_APP` to the actual extracted path to compare
it with the installed copy. The example below uses the default Finder extraction.

```bash
DOWNLOADS_APP="$HOME/Downloads/Finviz Tracker.app"
for APP in "$DOWNLOADS_APP" "/Applications/Finviz Tracker.app"; do
  echo "--- $APP ---"
  if [[ -d "$APP" ]]; then
    /usr/libexec/PlistBuddy -c 'Print :CFBundleVersion' "$APP/Contents/Info.plist"
    xattr -p com.apple.quarantine "$APP" 2>&1
    xattr -p com.apple.quarantine "$APP/Contents/MacOS/Finviz Tracker" 2>&1
  else
    echo 'App does not exist at this path'
  fi
done
codesign --verify --deep --strict --verbose=2 "/Applications/Finviz Tracker.app"
spctl --assess --type execute --verbose=4 "/Applications/Finviz Tracker.app"
```

If the checksum and signature pass, **Open Anyway** is unavailable, and the installed
copy specifically remains blocked by hard quarantine, the following command removes
quarantine from that one app bundle. It does not alter Gatekeeper's global settings.
Open the installed app again from Finder → Applications afterward.

```bash
xattr -dr com.apple.quarantine "/Applications/Finviz Tracker.app"
codesign --verify --deep --strict --verbose=2 "/Applications/Finviz Tracker.app"
open "/Applications/Finviz Tracker.app"
```

Do not run this against all of Downloads, another app, or an unverified file. Do not
disable Gatekeeper globally. An ad-hoc signature verifies bundle integrity but does
not establish a trusted publisher identity. If the block remains, send the exact
`spctl` output and the [recipient diagnostics](MACOS_PORTABILITY.md) to the sender.
