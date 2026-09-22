import { distribution, escapeHTML, filterStocks, sortStocks } from "./logic.js";
import { desktop, initializeDesktop, timeoutSignal } from "./desktop.js";

const element = selector => document.querySelector(selector);
const escape = escapeHTML;
const dataMode = element('meta[name="finviz-data-mode"]')?.content || "api";
let staticDataPromise;
const initialFilters = () => ({ search: "", sectors: [], industries: [], names: [], counts: [], mode: "all" });
const state = { data: null, filters: initialFilters(), sort: "match_count", direction: "desc", page: 1, pageSize: 50, date: "", request: 0, detailRequest: 0, loading: false, error: false };
const dialog = element("#ticker-dialog");
const formatDate = (value, options = {}) => new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", ...options }).format(new Date(`${value}T12:00:00`));
const stocks = () => state.data?.snapshot?.stocks || [];
const filterCount = () => state.data?.snapshot?.run.filter_count || 7;
const filterNames = () => (state.data?.snapshot?.filters || []).map(filter => filter.filter_name);

function navigate() {
  const view = location.hash === "#screener" ? "screener" : "dashboard";
  element("#dashboard-view").hidden = view !== "dashboard";
  element("#screener-view").hidden = view !== "screener";
  document.querySelectorAll("[data-nav]").forEach(link => {
    if (link.dataset.nav === view) link.setAttribute("aria-current", "page");
    else link.removeAttribute("aria-current");
  });
  document.title = `${view === "dashboard" ? "Dashboard" : "Screener"} · Overlap`;
}

function notify(message, error = false) {
  const notice = element("#notice");
  notice.hidden = !message;
  notice.setAttribute("role", error ? "alert" : "status");
  notice.textContent = message;
}

async function fetchJSON(url) {
  if (dataMode === "static") {
    staticDataPromise ||= fetch("./site-data.json", { cache: "no-store", signal: timeoutSignal() }).then(async response => {
      if (!response.ok) throw new Error("Published scan data is unavailable.");
      return response.json();
    });
    const bundle = await staticDataPromise;
    const request = new URL(url, location.href);
    const date = request.searchParams.get("date") || bundle.latest_date || "";
    if (request.pathname.endsWith("/api/overview")) {
      const overview = bundle.overviews[date];
      if (!overview) throw new Error("That scan date is not available.");
      return overview;
    }
    if (request.pathname.endsWith("/api/ticker")) {
      const ticker = (request.searchParams.get("ticker") || "").toUpperCase();
      const detail = bundle.tickers[date]?.[ticker];
      if (!detail) throw new Error(`No collected observations for ${ticker}`);
      return detail;
    }
    throw new Error("Unknown data request.");
  }
  const response = await fetch(url, { signal: timeoutSignal() });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "Unable to read saved scans.");
  return data;
}

async function loadData(quiet = false) {
  if (quiet && (state.loading || dialog.open || document.hidden || document.activeElement.closest("#app") || document.querySelector(".filter-dropdown[open]"))) return;
  const request = ++state.request;
  state.loading = true;
  if (!quiet) {
    element("#refresh").disabled = true;
    element("#refresh").textContent = "Refreshing…";
    element("#app").setAttribute("aria-busy", "true");
  }
  try {
    const data = await fetchJSON(`/api/overview${state.date ? `?date=${encodeURIComponent(state.date)}` : ""}`);
    if (request !== state.request) return;
    const changed = JSON.stringify(data) !== JSON.stringify(state.data);
    state.data = data;
    if (changed || !quiet || state.error) render();
    state.error = false;
    element("#loading").hidden = true;
    element("#app").hidden = false;
  } catch (error) {
    if (request !== state.request) return;
    state.error = true;
    notify(dataMode === "static" ? `${error.message} Reload the page and try again.` : `${error.message} Check that the local server is running, then use Refresh data.`, true);
    element("#loading").hidden = true;
  } finally {
    if (request === state.request) {
      state.loading = false;
      element("#refresh").disabled = false;
      element("#refresh").innerHTML = '<span aria-hidden="true">↻</span> Refresh data';
      element("#app").removeAttribute("aria-busy");
    }
  }
}

function render() {
  const data = state.data;
  element("#app").dataset.runId = data.snapshot?.run.id ?? "";
  const dates = data.dates || [];
  element("#scan-date").innerHTML = dates.length ? `<option value="">Latest · ${escape(formatDate(dates[0]))}</option>${dates.map(day => `<option value="${escape(day)}">${escape(formatDate(day, { year: "numeric" }))}</option>`).join("")}` : '<option value="">No scans yet</option>';
  element("#scan-date").value = state.date;
  element("#scan-date").disabled = !dates.length;
  const notes = [];
  if (data.selected_date && data.selected_date !== data.today) notes.push(`Viewing the ${formatDate(data.selected_date, { year: "numeric" })} scan. These are saved observations, not today's results.`);
  if (data.snapshot?.run.status === "partial") notes.push("Incomplete scan: match counts are lower bounds. Unavailable filters are not counted as zero.");
  if (data.selected_attempt && data.selected_attempt.status !== "complete") notes.push(`Latest attempt for this date: ${data.selected_attempt.status}.${data.snapshot?.run.status === "complete" ? " Showing the earlier complete scan." : ""}`);
  notify(notes.join(" "));
  renderDashboard();
  renderFilterControls();
  renderScreener();
  navigate();
}

function strip(stock) {
  return `<div class="filter-strip" aria-hidden="true">${filterNames().map(name => `<span class="${stock.matched_filters.includes(name) ? "matched" : ""}"></span>`).join("")}</div>`;
}

function bars(items, category, total, scale = null) {
  const maximum = scale || Math.max(1, ...items.map(item => item.count || 0));
  return items.map(item => {
    const percentage = !total || item.count === null ? "" : item.count > 0 && item.count / total < .01 ? "<1%" : `${Math.round(item.count / total * 100)}%`;
    return `<button class="bar-row" data-drill="${category}" data-value="${escape(item.label)}" ${item.count === null ? "disabled" : ""} aria-label="${escape(item.label)}: ${item.count === null ? "unavailable" : `${item.count} stocks. Show in screener`}"><span class="bar-label">${escape(item.label)}</span><span class="bar-count">${item.count === null ? "Unavailable" : item.count}<small>${escape(percentage)}</small></span><span class="bar-track" aria-hidden="true"><span class="bar-fill" style="width:${(item.count || 0) / maximum * 100}%"></span></span></button>`;
  }).join("");
}

function renderDashboard() {
  const data = state.data;
  const snapshot = data.snapshot;
  const selectedDate = data.selected_date;
  element("#dashboard-date").textContent = selectedDate ? formatDate(selectedDate, { weekday: "long", year: "numeric" }).toUpperCase() : "YOUR DAILY RESEARCH, TOGETHER";
  element("#screener-date").textContent = selectedDate ? `Saved scan · ${formatDate(selectedDate, { year: "numeric" })}` : "No saved scan";
  if (!snapshot) {
    element("#scan-context").textContent = "Waiting for a saved scan";
    element("#dashboard-content").innerHTML = desktop.enabled
      ? '<div class="panel data-empty"><h2>Your research starts with a scan</h2><p>Choose Run Scan above to collect all seven filters. To bring existing history, choose File → Import History before your first scan.</p></div>'
      : `<div class="panel data-empty"><h2>${data.selected_attempt ? "No usable snapshot for this date" : "Your research starts with a scan"}</h2><p>Run the existing scan command, then refresh this page. Previous observations are preserved.</p><code>python -m src.main</code></div>`;
    return;
  }
  const rows = stocks();
  const total = rows.length;
  const maximum = Math.max(0, ...rows.map(stock => stock.match_count));
  const leaders = rows.filter(stock => stock.match_count === maximum);
  const overlap = rows.filter(stock => stock.match_count >= 2).length;
  const sectors = distribution(rows, "sector");
  const industries = distribution(rows, "industry");
  const successful = snapshot.filters.filter(filter => filter.status === "success").length;
  const finished = snapshot.run.finished_timestamp;
  const time = finished ? new Intl.DateTimeFormat("en-US", { hour: "numeric", minute: "2-digit", timeZone: snapshot.run.timezone }).format(new Date(finished)) : "";
  element("#scan-context").innerHTML = `<strong><span class="status-dot" aria-hidden="true"></span>${successful} of ${filterCount()} filters collected</strong><br>Saved ${escape(time)} · ${escape(snapshot.run.timezone)}`;
  const metrics = [
    ["Unique stocks", total, "Across all collected filters"],
    ["Highest overlap", `${maximum}<small> / ${filterCount()}</small>`, `${leaders.length} ${leaders.length === 1 ? "stock shares" : "stocks share"} the highest count`],
    ["Multiple matches", overlap, `${total ? Math.round(overlap / total * 100) : 0}% matched two or more filters`],
    ["Sectors represented", sectors.length, `${industries.length} industries in this scan`],
  ];
  const countItems = Array.from({ length: filterCount() }, (_, position) => ({ label: position + 1, count: rows.filter(stock => stock.match_count === position + 1).length }));
  const maxBin = Math.max(1, ...countItems.map(item => item.count));
  const usage = snapshot.filters.map(filter => ({ label: filter.filter_name, count: filter.status === "success" ? filter.ticker_count : null }));
  element("#dashboard-content").innerHTML = `
    <div class="metrics">${metrics.map(([label, value, note]) => `<div class="metric"><p class="metric-label">${label}</p><strong class="metric-value">${value}</strong><p class="metric-note">${note}</p></div>`).join("")}</div>
    <div class="overview-grid">
      <section class="panel"><div class="panel-heading"><div><h2>Highest overlap</h2><p>The most filters matched in this scan</p></div><a class="text-button" href="#screener" data-action="view-all">View all <span aria-hidden="true">↗</span></a></div>
        <div class="leader-grid">${leaders.slice(0, 2).map(stock => `<article class="leader"><div class="leader-name"><button class="ticker-link" data-ticker="${escape(stock.ticker)}" aria-haspopup="dialog">${escape(stock.ticker)}</button><span class="leader-count">${stock.match_count}<small> / ${filterCount()}</small></span></div><p class="company-name">${escape(stock.company)}</p>${strip(stock)}<ul class="leader-filters">${stock.matched_filters.map(name => `<li>${escape(name)}</li>`).join("")}</ul></article>`).join("") || '<p class="muted">No stocks matched in this scan.</p>'}</div>
        <p class="panel-footnote">${leaders.length > 2 ? `Showing 2 of ${leaders.length} stocks tied at ${maximum} matches. ` : ""}Ranked by filter count only. No investment ratings.</p>
      </section>
      <section class="panel"><div class="panel-heading"><div><h2>Match distribution</h2><p>How many stocks matched each filter count</p></div></div>
        <div class="match-chart" role="group" aria-label="Stock counts by number of filters matched; bars start at zero">${countItems.map(item => `<button class="match-column" data-drill="counts" data-value="${item.label}" aria-label="${item.label} filters: ${item.count} stocks. Show in screener"><span class="match-value">${item.count}</span><span class="match-bar" style="height:${item.count / maxBin * 140}px" aria-hidden="true"></span><span class="match-label">${item.label}</span></button>`).join("")}</div><p class="axis-caption">Number of filters matched · Select a bar to explore</p>
      </section>
    </div>
    <div class="overview-grid">
      <section class="panel"><div class="panel-heading"><div><h2>Sector composition</h2><p>${sectors.length} sectors · Share of ${total} unique stocks</p></div></div><div class="distribution">${bars(sectors.slice(0, 6), "sectors", total)}</div>${sectors.length > 6 ? `<details><summary class="disclosure">Show all ${sectors.length} sectors</summary><div class="distribution">${bars(sectors.slice(6), "sectors", total, sectors[0].count)}</div></details>` : ""}<p class="panel-footnote">Bars compare stock counts; percentages show share of the scan.</p></section>
      <section class="panel"><div class="panel-heading"><div><h2>Filter coverage</h2><p>Stocks captured by each Finviz filter</p></div><span class="eyebrow">${successful} / ${filterCount()}</span></div><div class="distribution">${bars(usage, "names", total)}</div><p class="panel-footnote">A stock can appear in multiple filters. Percentages may exceed 100% in total.</p></section>
    </div>
    <section class="panel"><div class="panel-heading"><div><h2>Industry breakdown</h2><p>${industries.length} industries · Select an industry to explore its stocks</p></div></div><div class="industry-grid">${bars(industries.slice(0, 8), "industries", total)}</div>${industries.length > 8 ? `<details><summary class="disclosure">Show all ${industries.length} industries</summary><div class="industry-grid">${bars(industries.slice(8), "industries", total, industries[0].count)}</div></details>` : ""}</section>`;
}

function renderFilterControls() {
  const options = [
    ["sectors", "Sector", [...new Set(stocks().map(stock => stock.sector))].sort()],
    ["industries", "Industry", [...new Set(stocks().map(stock => stock.industry))].sort()],
    ["names", "Filters matched", filterNames()],
    ["counts", "Match count", Array.from({ length: filterCount() }, (_, position) => String(position + 1))],
  ];
  element("#filter-toolbar").innerHTML = options.map(([key, label, values]) => `<details class="filter-dropdown" data-group="${key}"><summary><span>${label}</span><span class="filter-badge" data-badge="${key}" hidden>0</span></summary><div class="filter-menu">${values.length > 10 ? `<label><span class="sr-only">Find ${label.toLowerCase()} options</span><input type="search" data-option-search="${key}" placeholder="Find ${label.toLowerCase()}…"></label>` : ""}<div class="filter-options" role="group" aria-label="${label}">${values.map(value => `<label data-option-label="${escape(value.toLocaleLowerCase())}"><input type="checkbox" data-filter="${key}" value="${escape(value)}" ${state.filters[key].includes(value) ? "checked" : ""}><span>${escape(value)}${key === "counts" ? ` / ${filterCount()}` : ""}</span></label>`).join("") || '<p class="muted">No options in this scan.</p>'}</div></div></details>`).join("");
  updateFilterFeedback();
}

function updateFilterFeedback() {
  const selections = [];
  for (const key of ["sectors", "industries", "names", "counts"]) {
    const badge = element(`[data-badge="${key}"]`);
    if (badge) { badge.textContent = state.filters[key].length; badge.hidden = !state.filters[key].length; }
    for (const value of state.filters[key]) selections.push(`<button class="filter-chip" data-remove="${key}" data-value="${escape(value)}" aria-label="Remove ${escape(value)} ${key === "counts" ? "matches" : "filter"}">${escape(value)}${key === "counts" ? " matches" : ""} <span aria-hidden="true">×</span></button>`);
  }
  element("#active-filters").innerHTML = selections.join("");
  element("#active-filters").hidden = !selections.length;
}

function renderScreener() {
  const filtered = sortStocks(filterStocks(stocks(), state.filters), state.sort, state.direction);
  const pageCount = Math.max(1, Math.ceil(filtered.length / state.pageSize));
  state.page = Math.min(state.page, pageCount);
  const start = (state.page - 1) * state.pageSize;
  const page = filtered.slice(start, start + state.pageSize);
  element("#result-count").innerHTML = `<strong>${filtered.length}</strong> of ${stocks().length} stocks${state.data?.snapshot?.run.status === "partial" ? " · Partial scan" : ""}`;
  element("#stock-rows").innerHTML = page.map(stock => `<tr><td><button class="ticker-link" data-ticker="${escape(stock.ticker)}" aria-haspopup="dialog">${escape(stock.ticker)}</button></td><td>${escape(stock.company)}</td><td>${escape(stock.sector)}</td><td>${escape(stock.industry)}</td><td><span class="count-pill ${stock.match_count >= 3 ? "high" : ""}">${stock.match_count} / ${filterCount()}</span></td><td><div class="cell-filters">${stock.matched_filters.map(name => `<span>${escape(name)}</span>`).join("")}</div></td></tr>`).join("");
  element("#table-empty").hidden = filtered.length !== 0;
  element("#table-empty h2").textContent = stocks().length ? "No stocks match these selections" : state.data?.snapshot ? "No stocks in this scan" : "No saved results for this date";
  element("#table-empty p").textContent = stocks().length ? "Try a broader search or remove a filter." : state.data?.snapshot ? "Choose another date to explore previously collected observations." : desktop.enabled ? "Choose Run Scan to collect your first results." : "Run the scan command, then refresh your saved data.";
  element('#table-empty [data-action="reset"]').hidden = !stocks().length;
  element("#stock-table").hidden = filtered.length === 0;
  element("#page-label").textContent = `${filtered.length ? start + 1 : 0}–${Math.min(start + state.pageSize, filtered.length)} of ${filtered.length}`;
  element("#previous").disabled = state.page <= 1;
  element("#next").disabled = state.page >= pageCount;
  document.querySelectorAll("[data-sort]").forEach(button => {
    const active = button.dataset.sort === state.sort;
    button.parentElement.setAttribute("aria-sort", active ? (state.direction === "asc" ? "ascending" : "descending") : "none");
    button.querySelector("span").textContent = active ? (state.direction === "asc" ? "↑" : "↓") : "↕";
  });
  updateFilterFeedback();
}

function resetFilters() {
  state.filters = initialFilters();
  state.page = 1;
  element("#search").value = "";
  element('input[name="filter-mode"][value="all"]').checked = true;
  renderFilterControls();
  renderScreener();
}

async function openDetail(ticker) {
  const request = ++state.detailRequest;
  element("#detail-content").innerHTML = `<h2 id="detail-title">${escape(ticker)}</h2><p class="detail-note" role="status">Loading collected history…</p>`;
  if (!dialog.open) dialog.showModal();
  try {
    const data = await fetchJSON(`/api/ticker?ticker=${encodeURIComponent(ticker)}&date=${encodeURIComponent(state.data.selected_date)}`);
    if (request !== state.detailRequest || !dialog.open) return;
    const current = data.current;
    const days = data.observations;
    const maximum = Math.max(data.filter_count || 7, ...days.map(day => day.filter_count));
    const currentCount = current ? current.match_count : data.current_absence_known ? 0 : "—";
    element("#detail-content").innerHTML = `
      <div class="detail-heading"><div><h2 id="detail-title">${escape(data.ticker)}</h2><p>${escape(data.company)}</p></div><div class="detail-count"><strong>${currentCount}<small> / ${data.filter_count || "—"}</small></strong><span>filters matched</span></div></div>
      <dl class="detail-metadata"><div><dt>Sector</dt><dd>${escape(data.sector)}</dd></div><div><dt>Industry</dt><dd>${escape(data.industry)}</dd></div></dl>
      <section class="detail-section"><h3>Matched filters</h3><p>${formatDate(data.selected_date, { year: "numeric" })}${data.snapshot_status !== "complete" ? " · Incomplete scan; counts are lower bounds" : ""}</p><div class="detail-tags">${(current?.matched_filters || []).map(name => `<span>${escape(name)}</span>`).join("") || `<p class="muted">${data.current_absence_known ? "No filters matched on this date." : "No confirmed matches; some filters are unavailable."}</p>`}</div></section>
      <section class="detail-section"><h3>Collected history</h3><p>${days.length} collected ${days.length === 1 ? "day" : "days"} of 7 · ${data.days_appeared} ${data.days_appeared === 1 ? "appearance" : "appearances"}</p>
        ${days.length ? `<div class="history-chart" role="img" aria-label="Filter matches on collected dates, scale zero to ${maximum}. ${days.map(day => `${formatDate(day.date)}: ${day.match_count} of ${day.filter_count}`).join("; ")}"><span class="history-axis top" aria-hidden="true">${maximum}</span><span class="history-axis bottom" aria-hidden="true">0</span>${days.map(day => `<div class="history-column" style="--bar-height:${day.match_count / maximum * 100}%" aria-hidden="true"><span class="history-number">${day.match_count}</span><div class="history-bar"></div></div>`).join("")}</div><div class="history-dates" aria-hidden="true">${days.map(day => `<span class="history-date">${formatDate(day.date)}</span>`).join("")}</div>
        <table class="history-table"><caption class="sr-only">Exact matched filters on each collected date</caption><thead><tr><th scope="col">Date</th><th scope="col">Matches</th><th scope="col">Filters Matched</th></tr></thead><tbody>${days.map(day => `<tr><td>${formatDate(day.date, { year: "2-digit" })}</td><td>${day.match_count} / ${day.filter_count}</td><td>${day.matched_filters.length ? escape(day.matched_filters.join(", ")) : "No filters matched"}</td></tr>`).join("")}</tbody></table>` : '<p class="detail-note">No complete daily scans are available yet.</p>'}
        ${days.length < 7 ? `<p class="detail-note">${days.length === 1 ? "One day collected so far." : `${days.length} days collected so far.`} More history will appear as you collect new daily scans. Missing days are never filled in.</p>` : ""}
        <p class="panel-footnote">One complete snapshot per collected date. A zero means the ticker was absent from that complete scan. Counts measure filter matches, not price performance.</p>
      </section>`;
  } catch (error) {
    if (request === state.detailRequest && dialog.open) element("#detail-content").innerHTML = `<h2 id="detail-title">${escape(ticker)}</h2><p class="detail-note" role="alert">${escape(error.message)}</p><button class="text-button" data-ticker="${escape(ticker)}">Try again</button>`;
  }
}

document.addEventListener("click", event => {
  const target = event.target.closest("button, a");
  if (target?.dataset.ticker) openDetail(target.dataset.ticker);
  if (target?.dataset.action === "reset") resetFilters();
  if (target?.dataset.action === "view-all") { resetFilters(); state.sort = "match_count"; state.direction = "desc"; renderScreener(); }
  if (target?.dataset.drill) {
    resetFilters();
    state.filters[target.dataset.drill] = [target.dataset.value];
    renderFilterControls(); renderScreener();
    location.hash = "screener";
  }
  if (target?.dataset.sort) {
    state.direction = state.sort === target.dataset.sort ? (state.direction === "desc" ? "asc" : "desc") : target.dataset.sort === "match_count" ? "desc" : "asc";
    state.sort = target.dataset.sort; state.page = 1; renderScreener();
  }
  if (target?.dataset.remove) {
    state.filters[target.dataset.remove] = state.filters[target.dataset.remove].filter(value => value !== target.dataset.value);
    state.page = 1; renderFilterControls(); renderScreener(); element("#reset").focus();
  }
  document.querySelectorAll(".filter-dropdown[open]").forEach(dropdown => { if (!dropdown.contains(event.target)) dropdown.open = false; });
});
document.addEventListener("change", event => {
  if (event.target.dataset.filter) {
    const key = event.target.dataset.filter;
    state.filters[key] = [...document.querySelectorAll(`input[data-filter="${key}"]:checked`)].map(input => input.value);
    state.page = 1; renderScreener();
  }
  if (event.target.name === "filter-mode") { state.filters.mode = event.target.value; state.page = 1; renderScreener(); }
});
document.addEventListener("input", event => {
  if (event.target.dataset.optionSearch) {
    const query = event.target.value.toLocaleLowerCase();
    event.target.closest(".filter-menu").querySelectorAll("[data-option-label]").forEach(label => { label.hidden = !label.dataset.optionLabel.includes(query); });
  }
});
document.addEventListener("keydown", event => {
  if (event.key === "Escape" && !dialog.open) document.querySelectorAll(".filter-dropdown[open]").forEach(dropdown => { dropdown.open = false; dropdown.querySelector("summary").focus(); });
});
element("#search").addEventListener("input", event => { state.filters.search = event.target.value; state.page = 1; renderScreener(); });
element("#reset").addEventListener("click", resetFilters);
element("#scan-date").addEventListener("change", event => { state.date = event.target.value; state.page = 1; loadData(); });
element("#refresh").addEventListener("click", () => loadData());
element("#page-size").addEventListener("change", event => { state.pageSize = Number(event.target.value); state.page = 1; renderScreener(); });
element("#previous").addEventListener("click", () => { state.page -= 1; renderScreener(); element(".table-scroll").scrollTop = 0; });
element("#next").addEventListener("click", () => { state.page += 1; renderScreener(); element(".table-scroll").scrollTop = 0; });
element("#close-detail").addEventListener("click", () => dialog.close());
dialog.addEventListener("close", () => { state.detailRequest += 1; });
dialog.addEventListener("click", event => { if (event.target === dialog && event.clientX < dialog.getBoundingClientRect().left) dialog.close(); });
window.addEventListener("hashchange", navigate);
navigate();
if (dataMode === "api") {
  await initializeDesktop(async () => { state.date = ""; await loadData(); });
} else {
  document.querySelector("footer > span:last-child").textContent = "Published scans · Updates appear automatically";
}
loadData();
setInterval(() => loadData(true), 60000);
