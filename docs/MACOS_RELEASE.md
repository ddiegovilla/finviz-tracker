# macOS release paths

## Format decision

| Format | Fit for Finviz Tracker |
| --- | --- |
| DMG | **Primary.** One file opens in Finder with the app and an Applications shortcut. It preserves the signed bundle, executable modes, and symlinks. It can later be Developer ID signed, notarized, and stapled. |
| ZIP | Keep as a fallback for transfers and automated inspection. `ditto` preserves the bundle, but Finder extraction gives less installation guidance. A ZIP itself cannot be signed or stapled. |
| PKG | Unnecessary for a single drag-install app. It adds an installer flow and would later need a separate Developer ID Installer certificate. |
| Bare `.app` or custom installer | Easier to damage or obscure the bundle during transfer; no benefit here. |

The DMG contains only `Finviz Tracker.app` and an `Applications` shortcut, laid out
in a Finder icon window on a volume named **Finviz Tracker**. No custom background
or installer code is needed. The DMG changes the installation experience, **not**
macOS trust policy. Apple documents DMG creation, signing, and notarization as the
standard path for directly distributed apps. See [Apple's packaging guide](https://developer.apple.com/documentation/xcode/packaging-mac-software-for-distribution).

## Path 1: private test build (available now)

On a native Apple Silicon Mac, run:

```bash
./scripts/build_macos.sh
```

With `FINVIZ_DEVELOPER_ID` unset, the app is ad-hoc signed. The command builds
version **1.0.1 (3)**, checks arm64, permissions, Info.plist, resources, symlinks,
all native dependencies and signature, then creates and verifies both containers:

```text
dist/Finviz Tracker.app
dist/Finviz Tracker-macOS-arm64.dmg
dist/Finviz Tracker-macOS-arm64.dmg.sha256
dist/Finviz Tracker-macOS-arm64.zip
dist/Finviz Tracker-macOS-arm64.zip.sha256
```

Send the DMG as the primary file. Give the recipient its SHA-256 through a trusted
channel (the sidecar is convenient for transfer checks, but a hash sent alongside
a tampered file does not establish authenticity). The [short recipient guide](MACOS_RECIPIENT_GUIDE.md)
starts with Finder and offers Apple's **Open Anyway** flow when available.

The recipient's WhatsApp copy had `com.apple.quarantine: 0087;...;WhatsApp;` and
`spctl` reported **“File created by an AppSandbox, exec/open not allowed.”** Its
signature passed, and removing quarantine from that one verified app allowed it to
run on the M1 Mac. That identifies hard quarantine from the transfer path, not an
arm64, dependency, or bundle defect. Apple documents a hard-quarantine error and
a [Developer Technical Support discussion](https://developer.apple.com/forums/thread/767612)
shows the same sandbox-created denial on a Developer ID-signed app, even after a
notarization ticket was stapled. A DMG or notarization alone cannot promise to
correct a hard-quarantine flag assigned by the receiving app. Prefer a trusted
direct browser download over a WhatsApp file transfer for the next recipient test.
There is no legitimate app-side or build-side switch that reliably prevents a
third-party transfer app from assigning quarantine. The app never removes its own
quarantine attribute.

## Path 2: professional direct distribution (future)

This path requires Apple Developer Program membership, a **Developer ID
Application** signing certificate, and Apple's notarization service. It is not
available with an ad-hoc signature. The optional signing branch below is prepared
but cannot be validated until a real certificate and notary credentials exist.
Increment `CFBundleVersion` in `packaging/Finviz Tracker.spec` for the next release.

1. Install and unlock the Developer ID Application certificate in Keychain. Check
   that it appears in `security find-identity -v -p codesigning`.
2. Build with its exact identity. PyInstaller uses it to sign the executable and
   collected native code with hardened runtime; the release script signs the outer
   app and DMG, then runs the same bundle, archive, and image audits.

   ```bash
   export FINVIZ_DEVELOPER_ID='Developer ID Application: YOUR NAME (TEAMID)'
   ./scripts/build_macos.sh
   codesign --verify --deep --strict --verbose=2 'dist/Finviz Tracker.app'
   codesign -dv --verbose=4 'dist/Finviz Tracker.app'
   codesign --verify --verbose=2 'dist/Finviz Tracker-macOS-arm64.dmg'
   ```

3. Run the signed app on a clean test Mac. If hardened runtime blocks a required
   operation, diagnose that exact denial and add only the necessary entitlement to
   the executable signing configuration. No exception entitlement is assumed now.
   Apple recommends signing nested code from the inside out and avoiding `--deep`
   when manually **signing** complex bundles; `--deep` remains appropriate for
   **verification**. See [Apple's signing guidance](https://developer.apple.com/documentation/xcode/creating-distribution-signed-code-for-the-mac/)
   and [hardened runtime guidance](https://developer.apple.com/documentation/security/hardened-runtime).
4. With Xcode installed and its license accepted, create a `notarytool` Keychain
   profile once using App Store Connect API credentials. Keep the `.p8` private:

   ```bash
   xcrun notarytool store-credentials finviz-notary \
     --key '/private/path/AuthKey_KEYID.p8' --key-id KEYID --issuer ISSUER_ID
   ```

5. Submit the **signed DMG**, inspect the result, staple, and validate. Do not
   distribute if the submission is rejected. Keep the printed submission ID; use
   `xcrun notarytool log SUBMISSION_ID --keychain-profile finviz-notary` to inspect
   any rejection or warning. The DMG is the outermost container:

   ```bash
   xcrun notarytool submit 'dist/Finviz Tracker-macOS-arm64.dmg' \
     --keychain-profile finviz-notary --wait
   xcrun stapler staple 'dist/Finviz Tracker-macOS-arm64.dmg'
   xcrun stapler validate 'dist/Finviz Tracker-macOS-arm64.dmg'
   hdiutil verify 'dist/Finviz Tracker-macOS-arm64.dmg'
   ```

6. Stapling changes the DMG's bytes: regenerate its checksum **after** stapling.
   Mount and drag-install that final DMG on another Mac, launch from Applications,
   and inspect Gatekeeper's decision there. Test through the actual download channel.

   ```bash
   (cd dist && shasum -a 256 'Finviz Tracker-macOS-arm64.dmg' > 'Finviz Tracker-macOS-arm64.dmg.sha256')
   spctl --assess --type execute --verbose=4 '/Applications/Finviz Tracker.app'
   ```

Apple documents `notarytool`, stapling, and testing the distributed container in
its [notarization workflow](https://developer.apple.com/documentation/security/customizing-the-notarization-workflow).
For a professional release, distribute the notarized DMG. The build also emits a
ZIP, but do not present that ZIP as stapled: a ZIP cannot carry a stapled ticket.
If a ZIP becomes necessary, staple the app first, recreate and reverify the ZIP,
and regenerate its checksum.

Developer ID signing and notarization address ordinary Gatekeeper publisher and
notarization checks. They do not authorize us to alter WhatsApp's sandbox or
guarantee that macOS will run a file it has marked **hard quarantined**. Preserve
quarantine in the release artifact and test each real transfer channel.

## Release verification

Run these after a private build; none initiates a Finviz scan:

```bash
.venv-build/bin/python scripts/check_macos_bundle.py 'dist/Finviz Tracker.app'
.venv-build/bin/python scripts/check_macos_zip.py 'dist/Finviz Tracker.app' 'dist/Finviz Tracker-macOS-arm64.zip'
.venv-build/bin/python scripts/check_macos_dmg.py 'dist/Finviz Tracker.app' 'dist/Finviz Tracker-macOS-arm64.dmg'
.venv/bin/python scripts/check_macos_app.py --no-scan
(cd dist && shasum -a 256 -c 'Finviz Tracker-macOS-arm64.dmg.sha256')
(cd dist && shasum -a 256 -c 'Finviz Tracker-macOS-arm64.zip.sha256')
```

The app checker tests the built app, a fresh ZIP extraction, and a DMG copy to an
isolated Applications-style directory. It verifies the native window, preserved
Application Support history, clean backend shutdown, and no repository or external
native-library dependency. A separate direct launch from `/Applications` was also
tested on the build Mac when no older app occupied that path. These local tests do
not simulate WhatsApp's hard quarantine; the recipient's real M1 test supplies that
evidence.
