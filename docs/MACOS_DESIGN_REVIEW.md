# Design review: Finviz Tracker desktop

## Summary

Good. A quiet research application: filter overlap and collected history remain the
main content. The native shell reuses the dashboard instead of adding a second visual
language. Reviewed source and an actual WKWebView dark-mode snapshot; native automated
checks exercised loading, Run Scan, dashboard, screener, and ticker history. A full
VoiceOver audit and testing on another physical Mac remain outstanding.

## What works

- `windows.md › Best practices`: “Avoid creating custom window UI.” The app uses a
  standard, resizable macOS window, traffic-light controls, Dock presence, and Quit.
- `the-menu-bar.md › Best practices`: “Support the default system-defined menus and
  their ordering.” File contains Run Scan and Import History; View exposes navigation
  and saved-data refresh. The native Edit menu retains familiar text commands.
- `loading.md › Best practices`: “Let people do other things in your app or game while
  they wait for content to load.” Scans run off the UI thread; existing data remains
  browsable while textual progress identifies filters and pagination.
- `feedback.md › Best practices`: “Consider integrating status feedback into your
  interface.” A nonmodal daily-collection strip offers the first scan and explains
  success/failure without an alert on every launch.
- `accessibility.md › Vision`: “Convey information with more than color alone.” The
  action has a text label, visible disabled state, and a polite live status region.
  Repeated identical progress messages are not continually re-announced.
- `layout.md › Best practices`: Related scan actions and feedback are grouped without
  adding another navigation destination. Existing typography, semantic light/dark
  colors, table semantics, reduced-motion handling, and dialog focus behavior remain.

## Improvements made

- Critical: the new scan strip overflowed at 200% text size in a narrow window. The
  action and status now wrap into separate rows instead of forcing horizontal overflow.
  The full UI regression suite passed this check at 320px with 200% text on September
  17, 2026, against the final packaged backend, alongside light/dark and focus checks.

- High: pywebview's eval-based JavaScript helper conflicted with the existing strict
  CSP. Native menu actions now use direct `run_js`; unsafe-eval was not enabled.
- High: using this machine's Homebrew Python would silently require macOS 26. The
  build now uses a separate portable Python environment and verifies every bundled
  Mach-O minimum version and architecture against the declared support level.
- Medium: Refresh Saved Data and Run Scan are separate, explicitly labeled actions.
  Empty-state copy no longer asks desktop users to run terminal commands.
- Medium: importing history is explicit in packaged builds and refuses overwriting
  existing history. The recipient's first launch does not contain somebody else's data.

## Remaining limitations

- Medium: a request already in flight can delay confirmed shutdown; cancellation is
  cooperative and never intentionally discards committed filter observations.
- Low: the app retains the existing Overlap dashboard identity under the Finviz
  Tracker application name, rather than redesigning a working interface.
- Actual contrast colors were retained from the existing dashboard review. The new
  muted text uses the same palette; no new low-contrast palette or motion was added.
