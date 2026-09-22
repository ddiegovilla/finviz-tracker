# Finviz Tracker for Apple Silicon

For version 1.0.1 (build 3), see the [recipient guide](MACOS_RECIPIENT_GUIDE.md),
[release paths](MACOS_RELEASE.md), and [portability diagnostics](MACOS_PORTABILITY.md).

## Build

On an Apple Silicon Mac, using native arm64 Python 3.12 or newer:

```bash
./scripts/build_macos.sh
```

The script creates an isolated `.venv-build` environment if needed, installs packaging dependencies,
converts the existing SVG favicon to an app icon, performs a clean PyInstaller build,
replaces previous generated outputs, and produces:

- `dist/Finviz Tracker.app`
- `dist/Finviz Tracker-macOS-arm64.dmg`
- `dist/Finviz Tracker-macOS-arm64.dmg.sha256`
- `dist/Finviz Tracker-macOS-arm64.zip`
- `dist/Finviz Tracker-macOS-arm64.zip.sha256`

Build artifacts and caches are under `build/` and `dist/`, never in user history.
The build machine needs internet access to install dependencies. Recipients do not
need Python, Terminal, Node, Chrome, or any package installation. Target: Apple Silicon,
macOS 14 or newer. Compatibility with other OS versions is not claimed.

For a portable build, prefer Python from python.org rather than a Homebrew interpreter
compiled for the newest macOS. The script prefers an installed python.org Python 3.13;
otherwise it uses `python3`. Set `PYTHON_BIN=/path/to/python3` before the first build to
choose another interpreter. The development `.venv` is not replaced. The actual bundled
Python and native libraries must support the advertised minimum OS; lowering only the
Info.plist version does not make newer binaries compatible.

PyInstaller bundles Python and dependencies. pywebview uses macOS's WKWebView, not a
bundled Chromium browser. The original local HTTP server and HTML/CSS/JS dashboard
remain in use. No cloud service or account is involved.

## Open and use

Double-click the app. A native window opens after a loopback-only server is ready on
an automatically selected port. The app has a Dock icon, native window controls,
standard Edit commands and Quit (Command-Q), plus File and View menus.

Choose **Run Scan** in the window or File menu. Progress names the current filter
and page; results refresh on completion. Only one desktop scan can run at a time.
Incomplete attempts retain successful filters and do not replace an earlier complete
daily snapshot. A failed scan never deletes previous history.

On opening, the app checks for a complete scan on today's date in the Mac's system
timezone. If missing, a nonmodal banner offers Run Scan. It does not silently use
the network or create fake days. If complete, existing results load immediately.
The Run Scan action is always available to collect another attempt.

Closing the window or choosing Quit stops the server. During a scan, quitting asks
for confirmation, interrupts at the next safe boundary, and saves completed filters.
An in-flight HTTP request can delay shutdown. No launchd job or background scheduler
is installed. Force Quit cannot export an interrupted JSON snapshot; committed SQLite
observations still survive.

## Persistent data and migration

All runtime data lives outside the read-only app bundle:

```text
~/Library/Application Support/Finviz Tracker/
  finviz_history.db
  latest-scan.json
  scans/YYYY-MM-DD/run-ID.json
  logs/app.log
  logs/startup.log
  debug/
  app.lock
  session.json   (private, temporary; removed on normal exit)
```

Use Finder → Go → Go to Folder to open this directory. Replacing/updating the app
does not remove it. Back up this folder with the app closed; it contains all collected
history, not just seven days. SQLite retains every run. The chart displays up to seven
collected dates, selecting the latest complete run for each date.

**Import before your first scan:** choose File → Import History and select the old
project's `data` folder. The app creates a consistent SQLite backup and copies dated
JSON snapshots without modifying the originals. If a destination database already
exists, import refuses to overwrite or merge it. Missing/corrupt source databases
produce a safe error. No personal scan database is bundled or sent to recipients.

In repository development mode, `python -m src.desktop` automatically imports
repository history on first launch only if no desktop database exists. A packaged
app never searches for the original repository; use the File menu for explicit import.

The original development commands remain available:

```bash
.venv/bin/python -m pip install -r requirements-desktop.txt
.venv/bin/python -m src.desktop
.venv/bin/python -m src.main scan --output data/latest-scan.json
.venv/bin/python -m src.web
```

The CLI and original browser server retain their repository-relative defaults.
They do not touch desktop history unless explicitly given its database with `--db`.
Avoid running the CLI against the desktop database while the app is open.

## Sharing and Gatekeeper

The primary private release is the DMG: it contains the app and an Applications
shortcut for a Finder drag install. The ZIP remains a verified fallback. Both
containers preserve bundle structure, modes, and symlinks. The private build is
ad-hoc signed and **not** notarized, so a downloaded copy may be blocked despite
passing `codesign` verification. A recipient's WhatsApp transfer was hard
quarantined; that same app launched on their M1 Mac after quarantine was removed.
The [recipient guide](MACOS_RECIPIENT_GUIDE.md) gives the normal Finder flow, Apple's
Open Anyway option, and a narrowly scoped advanced fallback for that verified case.
The [release guide](MACOS_RELEASE.md) explains what Developer ID and notarization
would change and why a DMG alone cannot prevent quarantine.

## Security and limitations

- Binds only `127.0.0.1`; strict Host validation, a per-launch HttpOnly SameSite cookie,
  Origin validation and a CSRF token protect the desktop HTTP API.
- No general-purpose shell endpoint, arbitrary path API, or remote JS-to-Python API.
- Runtime configuration and frontend assets are bundled; certificates and timezone
  data are bundled too. Local timezone is detected using tzlocal.
- A process lock prevents a second desktop instance using the same history folder.
- File import is first-use migration, not a general merge tool.
- Finviz needs internet and can change its markup or block/rate-limit requests.
- No automatic scans when the application is closed; missed days cannot be recreated.
- Each recipient has independent history. There is no account, sync, or shared database.
- `packaging/Finviz Tracker.icns` can override the icon generated from the existing SVG.
- Intel Macs, Windows, notarization, and automatic updating are not included in v1.

## Verification commands (developer only)

```bash
.venv/bin/python -m pytest -q
node --test tests/test_frontend.mjs
.venv/bin/python scripts/check_macos_app.py --no-scan
open -n "dist/Finviz Tracker.app" --args --verify
```

Close an already-running copy before these checks. Verification loads the actual
native WKWebView, checks the dashboard/screener/history, writes
`logs/verification.json` and `logs/native-window.png` in Application Support, then
exits. `--verify-scan` clicks the actual Run Scan button and contacts real Finviz URLs;
it adds a real scan to your desktop history. No sample stock data is generated.
The optional `--import-history /path/to/data` flag performs the same non-overwriting
first-use migration as the File menu, for repeatable developer checks.

`scripts/check_macos_app.py --no-scan` launches the built app, a fresh ZIP extraction,
and a copy installed from the DMG into an isolated Applications-style directory. It
checks native windows, preserved history, closed local servers, and signatures.
Its combined report is saved to `data/packaging-test/verification.json`. Omit
`--no-scan` only when a real Finviz scan is specifically needed. The browser suite saves
its own report to `data/ui-review/verification.json`, including the 200% text-size check.

For the full existing browser regression suite against a normally running app:

```bash
.venv/bin/python scripts/check_dashboard.py --desktop-session "$HOME/Library/Application Support/Finviz Tracker/session.json"
```

The native check does not require Chrome or Playwright. The optional browser suite
requires the existing `requirements-browser.txt` and Chrome developer dependencies.
Never share `session.json`; it contains a short-lived local authentication token.

## Changed files

### Initial build 2 verification — September 17, 2026 (historical)

- Python: 55 tests passed. JavaScript: 4 tests passed.
- Packaged native WKWebView: actual Run Scan completed all seven filters, saving
  249 stocks as run 7. The six earlier runs were preserved, including partial attempts.
- Extracted the final ZIP outside the repository and launched that copy through
  macOS LaunchServices. The same run, 249 stocks, and two collected historical dates
  loaded without creating another scan or requiring Terminal/Python installation.
- Both verification launches stopped their loopback servers on exit. Bundle signature
  checks passed before/after use; SQLite integrity check returned `ok`.
- Full UI suite passed with zero browser JavaScript errors, including filters,
  sorting, ticker detail, two-day history, light/dark appearance, keyboard focus,
  empty/error recovery, narrow layouts, and 200% text size at a 320px viewport.
- Live Finviz counts changed mid-pagination during two earlier attempts. These were
  correctly recorded as partial; the existing integrity checks were not weakened.
  A subsequent scan succeeded. A changing live screener can still require retrying.
- This was local verification before the recipient's M1/macOS Tahoe 26.6.2 test.
  The [portability report](MACOS_PORTABILITY.md) records that later confirmed
  WhatsApp hard quarantine caused the recipient's launch denial.

### Implementation inventory

Added:

- `src/app_paths.py`, `src/desktop.py`, `src/desktop_scan.py`, `src/desktop_server.py`, `src/desktop_verify.py`
- `frontend/desktop.js`
- `packaging/macos_entry.py`, `packaging/Finviz Tracker.spec`
- `scripts/build_macos.sh`, `scripts/create_macos_dmg.sh`, `scripts/check_macos_dmg.py`,
  `scripts/macos_icon.py`, `scripts/check_macos_bundle.py`, `scripts/check_macos_app.py`
- `requirements-desktop.txt`, `requirements-build.txt`
- `tests/test_desktop.py`, `tests/test_desktop_scan.py`
- `docs/MACOS_APP.md`, `docs/MACOS_DESIGN_REVIEW.md`, `docs/MACOS_RECIPIENT_GUIDE.md`,
  `docs/MACOS_RELEASE.md`, `docs/MACOS_PORTABILITY.md`

Modified:

- `src/config.py`, `src/finviz_client.py`, `src/web.py`
- `frontend/app.js`, `frontend/index.html`, `frontend/styles.css`
- `scripts/check_dashboard.py`, `README.md`, `.gitignore`

No filter URLs, database schema, original tests, or stored repository scans were changed.
