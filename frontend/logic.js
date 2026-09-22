export function filterStocks(stocks, filters) {
  const query = filters.search.trim().toLocaleLowerCase();
  return stocks.filter(stock => {
    if (query && !`${stock.ticker} ${stock.company}`.toLocaleLowerCase().includes(query)) return false;
    if (filters.sectors.length && !filters.sectors.includes(stock.sector)) return false;
    if (filters.industries.length && !filters.industries.includes(stock.industry)) return false;
    if (filters.counts.length && !filters.counts.includes(String(stock.match_count))) return false;
    if (filters.names.length) {
      const matches = name => stock.matched_filters.includes(name);
      if (filters.mode === "all" ? !filters.names.every(matches) : !filters.names.some(matches)) return false;
    }
    return true;
  });
}

export function sortStocks(stocks, key = "match_count", direction = "desc") {
  return [...stocks].sort((first, second) => {
    const firstValue = key === "matched_filters" ? first[key].join(", ") : first[key];
    const secondValue = key === "matched_filters" ? second[key].join(", ") : second[key];
    const comparison = typeof firstValue === "number" ? firstValue - secondValue : firstValue.localeCompare(secondValue);
    return comparison ? comparison * (direction === "asc" ? 1 : -1) : first.ticker.localeCompare(second.ticker);
  });
}

export function distribution(stocks, key) {
  const counts = new Map();
  for (const stock of stocks) counts.set(stock[key], (counts.get(stock[key]) || 0) + 1);
  return [...counts].map(([label, count]) => ({ label, count })).sort((first, second) => second.count - first.count || String(first.label).localeCompare(String(second.label)));
}

export function escapeHTML(value) {
  return String(value ?? "").replace(/[&<>"']/g, character => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[character]);
}
