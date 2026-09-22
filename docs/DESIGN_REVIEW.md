# Design review: Overlap

## Summary

**Overall: Good.** Overlap is a local, browser-based financial research tool for comparing objective Finviz filter matches. Its thesis is to make filter overlap immediately legible while retaining the provenance of each observation. A seven-position membership strip connects the highest-overlap cards to the exact filter names; the rest of the interface stays quiet.

The installed `apple-design` skill was used for design and review. The HIG lookup routed layout, navigation, typography, color, dark appearance, accessibility, tables, charting, search, selection controls, loading, and feedback. This is a web app: the review applies the principles and foundations, not native macOS menu-bar or window-chrome conventions.

## Design decisions

- **Navigation:** two persistent, labeled links, Dashboard and Screener. Ticker details use a temporary native HTML dialog. A separate History section would repeat the ticker-level workflow with the currently small dataset. `tab-bars.md › Best practices`: “Use a tab bar to support navigation, not to provide actions.”
- **Layout:** the date and data freshness accompany each view. Metrics lead, then highest overlap and distribution, then sector/filter/industry breakdowns. `layout.md › Best practices`: “Make essential information easy to find by giving it sufficient space.”
- **Typography:** system UI family, tabular numerals, regular/medium/semibold weights. Main title 36px, metrics 40px, panel titles 18px, main body 15–16px, table text 13px; small annotations 11–12px. Rem units preserve text scaling. `typography.md › Conveying hierarchy`: “Minimize the number of typefaces you use, even in a highly customized interface.”
- **Tables:** native HTML semantics, explicit column headers, ascending/descending sort state, modest alternating rows, full text wrapping, and horizontal scrolling. Column resizing is deferred because full text is available without truncation. `lists-and-tables.md › Desktop (macOS)` recommends sortable headings and considers alternating row colors.
- **Search and filtering:** a prominent ticker/company search, four grouped checkbox menus, visible selected chips, and a labeled ALL/ANY radio group. `searching.md › Best practices`: “Clearly display the current scope of a search.” `segmented-controls.md › Best practices` supports grouping closely related choices and showing selection state.
- **Appearance:** semantic CSS tokens follow `prefers-color-scheme`; there is no competing app-level appearance setting. `dark-mode.md › Best practices`: “Avoid offering an app-specific appearance setting.”
- **Materials and motion:** opaque content surfaces, restrained borders and shadows, a dimmed dialog backdrop, and one 160ms desktop panel entrance. No decorative gradients, background animation, or glass over charts. Reduced motion disables the entrance; reduced transparency makes the backdrop opaque.

Regular layout:

```text
Brand       Dashboard · Screener                   Date · Refresh
Daily overview                                      Scan status
Unique stocks | Highest overlap | Multiple matches | Sectors
Highest-overlap cards                   Match-count distribution
Sector composition                      Filter coverage
Industry breakdown, with progressive disclosure
```

Compact layout:

```text
Brand
Date · Refresh
Dashboard · Screener
Heading and scan status
Metrics (two columns, one when text needs more room)
Highest overlap → distributions → industries
Screener: stacked controls + horizontally scrollable table
Ticker detail: full-width dialog with its own vertical scroll
```

The design intentionally omits price sparklines, recommendation badges, gain/loss colors, and invented trends: those would suggest data or judgments the project does not contain. This is product-specific restraint, not a generic trading terminal theme.

## Tokens and measured contrast

Ratios below use WCAG relative luminance calculated from the actual CSS hex values, not screenshot estimates.

| Role | Light | Dark | Contrast against its surface, light / dark |
|---|---|---|---|
| Canvas | `#f5f6f8` | `#13161b` | Background |
| Surface | `#ffffff` | `#1c2027` | Background |
| Primary content | `#202631` | `#edf0f5` | 15.18:1 / 14.30:1 |
| Secondary content | `#606b7a` | `#a7b1bf` | 5.41:1 / 7.53:1 |
| Accent on selected surface | `#245bc4` on `#edf3ff` | `#91b6ff` on `#26354e` | 5.60:1 / 6.08:1 |
| Input boundary | `#8290a2` | `#738096` | 3.25:1 / 4.09:1 |

Secondary text also meets 4.5:1 on recessed surfaces: 4.78:1 light, 6.57:1 dark. Control and focus states have visible borders/outlines; data never relies on color alone. `accessibility.md › Vision` calls for sufficient text contrast, larger text, and information conveyed through more than color.

## Review findings and fixes

- **High — chart accuracy, fixed:** initial history bars used less vertical space than their labeled axis. They now share the exact plot height and a zero-to-filter-count domain. Expanded category lists share the same scale as their visible predecessors. Percentages below 1% read `<1%`, not `0%`. `charts.md › Axes` ties scale to the data and bar lower bounds to zero.
- **Critical — compact filter menus, fixed:** menus anchored to individual buttons could extend beyond the viewport. Compact menus now anchor inside the shared toolbar. Browser checks verify every menu's bounds at 390px.
- **Medium — control size and typography, fixed:** compact controls, chips, and ticker targets now reach 44px; the brand caption increased from 9px to 10px. At enlarged text sizes, header actions, metrics, and search controls wrap instead of overflowing. `accessibility.md › Mobility` recommends sufficiently sized controls and space around them.
- **Medium — refresh interruption, fixed:** polling defers while someone uses a control, open filter menu, or ticker dialog. A manual refresh keeps selection and sort state. `feedback.md › Best practices` favors status feedback integrated into the interface.
- **Low — density, fixed:** all ten sectors initially extended the dashboard unnecessarily. The leading six remain visible, with an explicit disclosure for the rest; all values stay accessible. This is the accessory removed in the second critique. `charting-data.md › Best practices`: “Keep a chart simple, letting people choose when they want additional details.”

## What works

- Clear hierarchy through spacing, type weight, and alignment rather than saturated cards.
- Exact counts and filter names alongside every chart; ticker history also has a full text table.
- AND across categories, OR within categories, and an explicit choice for matched-filter logic.
- Persistent navigation and date context, with partial/stale observations visibly distinguished.
- Native checkboxes, radios, select, disclosure controls, table semantics, and dialog behavior.
- Immediate loading shell, recoverable load errors, empty search results, and a truthful one-day history state. `loading.md › Best practices`: “Show something as soon as possible.”

## Validation and limits

Real-data browser checks cover the 206-stock saved scan, ALL/ANY combinations, search/reset, sorting, modal dismissal and focus restoration, system light/dark modes, responsive layouts down to 320px, 200% text sizing, and reduced motion. Captures are in `data/ui-review/`. Python tests cover read-only access, snapshot choice, partial/failed attempts, seven collected dates, genuine absence, and missing database behavior. The backend's original tests remain intact.

The automated browser pass uses desktop Chrome. Safari, Firefox, actual VoiceOver speech order, Switch Control, high-contrast hardware conditions, and touch devices still merit a manual pass. The implementation uses semantic controls and forced-color/reduced-motion styles, but this review does not claim assistive-technology certification. Historical multi-day tests use isolated test databases; no fabricated observations are added to the application database or screenshots.

## Reference set

Read from the installed skill's `references/hig/`: `designing-for-macos.md`, `layout.md`, `typography.md`, `color.md`, `accessibility.md`, `dark-mode.md`, `lists-and-tables.md`, `tab-bars.md`, `searching.md`, `segmented-controls.md`, `charting-data.md`, `charts.md`, `loading.md`, and `feedback.md`. The broader set follows the user's explicit coverage requirements. HIG wording is translated to HTML/CSS/JavaScript behavior; product-specific choices are design judgment.
