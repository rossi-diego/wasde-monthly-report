// frontend/charts.js — Chart.js builders consuming the FastAPI endpoints

const API = window.location.origin;

const CHART_DEFAULTS = {
  color: "#f9fafb",
  borderColor: "#10b981",
  grid: { color: "#1f2937" },
  ticks: { color: "#9ca3af" },
};

const instances = {};

function destroyChart(id) {
  if (instances[id]) {
    instances[id].destroy();
    delete instances[id];
  }
}

function fmt(n, decimals = 0) {
  if (n == null) return "—";
  return Number(n).toLocaleString("en-US", { maximumFractionDigits: decimals });
}

// ── Helpers ────────────────────────────────────────────────────────────

async function apiFetch(path) {
  const res = await fetch(API + path);
  if (!res.ok) throw new Error(`API error ${res.status}: ${path}`);
  return res.json();
}

function lineChart(canvasId, labels, datasets, yLabel = "") {
  destroyChart(canvasId);
  const ctx = document.getElementById(canvasId).getContext("2d");
  instances[canvasId] = new Chart(ctx, {
    type: "line",
    data: { labels, datasets },
    options: {
      responsive: true,
      plugins: { legend: { labels: { color: CHART_DEFAULTS.color } } },
      scales: {
        x: { grid: CHART_DEFAULTS.grid, ticks: CHART_DEFAULTS.ticks },
        y: {
          grid: CHART_DEFAULTS.grid,
          ticks: CHART_DEFAULTS.ticks,
          title: { display: !!yLabel, text: yLabel, color: CHART_DEFAULTS.ticks.color },
        },
      },
    },
  });
}

function barChart(canvasId, labels, data, yLabel = "", horizontal = false) {
  destroyChart(canvasId);
  const ctx = document.getElementById(canvasId).getContext("2d");
  instances[canvasId] = new Chart(ctx, {
    type: "bar",
    data: {
      labels,
      datasets: [{
        data,
        backgroundColor: "#10b981aa",
        borderColor: "#10b981",
        borderWidth: 1,
      }],
    },
    options: {
      indexAxis: horizontal ? "y" : "x",
      responsive: true,
      plugins: { legend: { display: false } },
      scales: {
        x: { grid: CHART_DEFAULTS.grid, ticks: CHART_DEFAULTS.ticks },
        y: {
          grid: CHART_DEFAULTS.grid,
          ticks: CHART_DEFAULTS.ticks,
          title: { display: !!yLabel, text: yLabel, color: CHART_DEFAULTS.ticks.color },
        },
      },
    },
  });
}

// ── Section loaders ────────────────────────────────────────────────────

async function loadSupplyDemand() {
  const commodity = document.getElementById("filter-commodity").value;
  const country = document.getElementById("filter-country").value;
  const year = document.getElementById("filter-year").value;

  try {
    const data = await apiFetch(
      `/v1/supply-demand/?commodity=${encodeURIComponent(commodity)}&country=${encodeURIComponent(country)}&marketing_year=${year}`
    );

    // Latest row → metric cards
    if (data.length > 0) {
      const latest = data[0];
      document.getElementById("val-production").textContent = fmt(latest.production);
      document.getElementById("val-ending-stocks").textContent = fmt(latest.ending_stocks);
      document.getElementById("val-exports").textContent = fmt(latest.exports);
      document.getElementById("val-stu").textContent =
        latest.stock_to_use_pct != null ? fmt(latest.stock_to_use_pct, 1) + "%" : "—";
      document.getElementById("last-update").textContent =
        "Last report: " + latest.report_date;
    }

    // Ending stocks history
    const history = await apiFetch(
      `/v1/supply-demand/?commodity=${encodeURIComponent(commodity)}&country=${encodeURIComponent(country)}`
    );
    const byYear = {};
    history.forEach(r => {
      if (!byYear[r.marketing_year]) byYear[r.marketing_year] = {};
      byYear[r.marketing_year][r.report_date] = r.ending_stocks;
    });
    const years = Object.keys(byYear).sort().slice(-5);
    const allDates = [...new Set(history.map(r => r.report_date))].sort();
    const colors = ["#10b981", "#3b82f6", "#f59e0b", "#ef4444", "#8b5cf6"];
    lineChart(
      "chart-ending-stocks",
      allDates,
      years.map((yr, i) => ({
        label: yr,
        data: allDates.map(d => byYear[yr]?.[d] ?? null),
        borderColor: colors[i],
        backgroundColor: "transparent",
        tension: 0.3,
        spanGaps: true,
      })),
      "1000 MT"
    );
  } catch (e) {
    console.error("Supply/demand load error:", e);
  }
}

async function loadStockToUse() {
  const commodity = document.getElementById("filter-commodity").value;
  const country = document.getElementById("filter-country").value;
  try {
    const data = await apiFetch(
      `/v1/supply-demand/stock-to-use?commodity=${encodeURIComponent(commodity)}&country=${encodeURIComponent(country)}`
    );
    const byYear = {};
    data.forEach(r => {
      if (!byYear[r.marketing_year]) byYear[r.marketing_year] = {};
      byYear[r.marketing_year][r.report_date] = r.stock_to_use_pct;
    });
    const years = Object.keys(byYear).sort().slice(-5);
    const allDates = [...new Set(data.map(r => r.report_date))].sort();
    const colors = ["#10b981", "#3b82f6", "#f59e0b", "#ef4444", "#8b5cf6"];
    lineChart(
      "chart-stu",
      allDates,
      years.map((yr, i) => ({
        label: yr,
        data: allDates.map(d => byYear[yr]?.[d] ?? null),
        borderColor: colors[i],
        backgroundColor: "transparent",
        tension: 0.3,
        spanGaps: true,
      })),
      "% Stock-to-Use"
    );
  } catch (e) {
    console.error("STU load error:", e);
  }
}

async function loadRevisions() {
  const commodity = document.getElementById("filter-commodity").value;
  const year = document.getElementById("filter-year").value;
  const country = document.getElementById("filter-country").value;
  try {
    const data = await apiFetch(
      `/v1/supply-demand/revisions?commodity=${encodeURIComponent(commodity)}&marketing_year=${year}&country=${encodeURIComponent(country)}`
    );
    lineChart(
      "chart-revisions",
      data.map(r => r.report_date),
      [{
        label: "Ending Stocks",
        data: data.map(r => r.ending_stocks),
        borderColor: "#10b981",
        backgroundColor: "#10b98122",
        fill: true,
        tension: 0.2,
      }],
      "1000 MT"
    );
  } catch (e) {
    console.error("Revisions load error:", e);
  }
}

async function loadNOPA() {
  try {
    const data = await apiFetch("/v1/nopa/crush?months=36");
    const sorted = [...data].sort((a, b) => a.report_date.localeCompare(b.report_date));
    barChart(
      "chart-nopa",
      sorted.map(r => r.report_date),
      sorted.map(r => r.crush_million_bu),
      "Million Bushels"
    );
  } catch (e) {
    console.error("NOPA load error:", e);
  }
}

async function loadExports() {
  try {
    const data = await apiFetch("/v1/exports/pace");
    barChart(
      "chart-exports",
      data.map(r => r.commodity),
      data.map(r => r.pace_pct ?? 0),
      "% of USDA Target",
      true
    );
  } catch (e) {
    console.error("Export pace load error:", e);
  }
}

// ── Data Table ────────────────────────────────────────────────────────

const TABLE_COLS = [
  { key: "report_date", label: "Report Date" },
  { key: "commodity", label: "Commodity" },
  { key: "country", label: "Country" },
  { key: "marketing_year", label: "MY" },
  { key: "production", label: "Production" },
  { key: "beginning_stocks", label: "Beg. Stocks" },
  { key: "imports", label: "Imports" },
  { key: "domestic_total", label: "Dom. Use" },
  { key: "exports", label: "Exports" },
  { key: "ending_stocks", label: "End. Stocks" },
  { key: "stock_to_use_pct", label: "S/U %" },
];

let tableData = [];
let tableSortKey = "report_date";
let tableSortAsc = false;

function renderTable() {
  const head = document.getElementById("data-table-head");
  const body = document.getElementById("data-table-body");
  const status = document.getElementById("table-status");

  // Header
  head.innerHTML = `<tr>${TABLE_COLS.map(c =>
    `<th class="text-left py-2 px-2 border-b border-gray-800 text-gray-400 font-medium cursor-pointer hover:text-gray-200 whitespace-nowrap select-none"
         onclick="sortTable('${c.key}')">${c.label}${tableSortKey === c.key ? (tableSortAsc ? " ▲" : " ▼") : ""}</th>`
  ).join("")}</tr>`;

  // Sort
  const sorted = [...tableData].sort((a, b) => {
    const va = a[tableSortKey], vb = b[tableSortKey];
    if (va == null && vb == null) return 0;
    if (va == null) return 1;
    if (vb == null) return -1;
    if (typeof va === "string") return tableSortAsc ? va.localeCompare(vb) : vb.localeCompare(va);
    return tableSortAsc ? va - vb : vb - va;
  });

  // Rows
  body.innerHTML = sorted.map(row =>
    `<tr class="border-b border-gray-800/50 hover:bg-gray-800/30">${TABLE_COLS.map(c => {
      const v = row[c.key];
      const isNum = typeof v === "number";
      return `<td class="py-1.5 px-2 ${isNum ? "text-right tabular-nums" : ""} whitespace-nowrap">${
        v == null ? "—" : isNum ? fmt(v, c.key === "stock_to_use_pct" ? 1 : 0) : v
      }</td>`;
    }).join("")}</tr>`
  ).join("");

  status.textContent = `${sorted.length} rows`;
}

function sortTable(key) {
  if (tableSortKey === key) {
    tableSortAsc = !tableSortAsc;
  } else {
    tableSortKey = key;
    tableSortAsc = true;
  }
  renderTable();
}

async function loadTable() {
  const commodity = document.getElementById("filter-commodity").value;
  const country = document.getElementById("filter-country").value;
  try {
    tableData = await apiFetch(
      `/v1/supply-demand/?commodity=${encodeURIComponent(commodity)}&country=${encodeURIComponent(country)}`
    );
    renderTable();
  } catch (e) {
    console.error("Table load error:", e);
    document.getElementById("table-status").textContent = "Failed to load data";
  }
}

function downloadData(format) {
  const commodity = document.getElementById("filter-commodity").value;
  const country = document.getElementById("filter-country").value;
  const year = document.getElementById("filter-year").value;
  const url = `${API}/v1/supply-demand/download?commodity=${encodeURIComponent(commodity)}&country=${encodeURIComponent(country)}&marketing_year=${year}&format=${format}`;
  window.open(url, "_blank");
}

// ── Main ───────────────────────────────────────────────────────────────

async function loadAll() {
  await Promise.allSettled([
    loadSupplyDemand(),
    loadStockToUse(),
    loadRevisions(),
    loadNOPA(),
    loadExports(),
    loadTable(),
  ]);
}

document.addEventListener("DOMContentLoaded", loadAll);
