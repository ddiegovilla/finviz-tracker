import assert from "node:assert/strict";
import test from "node:test";
import { filterStocks, sortStocks, distribution, escapeHTML } from "../frontend/logic.js";

const records = [
  { ticker: "TESTA", company: "Alpha Test", sector: "Energy", industry: "Oil", match_count: 2, matched_filters: ["Momentum", "Fortaleza"] },
  { ticker: "TESTB", company: "Beta Test", sector: "Technology", industry: "Software", match_count: 1, matched_filters: ["Momentum"] },
  { ticker: "TESTC", company: "Gamma Test", sector: "Healthcare", industry: "Biotechnology", match_count: 1, matched_filters: ["Fortaleza"] },
];
const filters = { search: "", sectors: [], industries: [], names: [], counts: [], mode: "all" };

test("categories combine with AND; choices within sector combine with OR", () => {
  const criteria = { ...filters, sectors: ["Energy", "Technology"], names: ["Momentum", "Fortaleza"] };
  assert.deepEqual(filterStocks(records, criteria).map(stock => stock.ticker), ["TESTA"]);
  assert.deepEqual(filterStocks(records, { ...criteria, mode: "any" }).map(stock => stock.ticker), ["TESTA", "TESTB"]);
});
test("industry, count and company search combine with other selections", () => {
  assert.deepEqual(filterStocks(records, { ...filters, industries: ["Oil", "Software"], counts: ["1"], search: " bEtA " }).map(stock => stock.ticker), ["TESTB"]);
  assert.equal(filterStocks(records, { ...filters, search: "no match" }).length, 0);
});
test("sort is deterministic and never mutates source", () => {
  assert.deepEqual(sortStocks([...records].reverse()).map(stock => stock.ticker), ["TESTA", "TESTB", "TESTC"]);
  assert.deepEqual(sortStocks(records, "ticker", "desc").map(stock => stock.ticker), ["TESTC", "TESTB", "TESTA"]);
  assert.equal(records[0].ticker, "TESTA");
});
test("distributions count stocks once; source strings cannot inject markup", () => {
  assert.equal(distribution(records, "match_count")[0].count, 2);
  assert.equal(escapeHTML('<img onerror="test">'), "&lt;img onerror=&quot;test&quot;&gt;");
});
