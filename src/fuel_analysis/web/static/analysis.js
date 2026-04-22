/* Analysis page: fetches /api/analysis for the selected range and renders
 * metric chips + a set of Chart.js canvases.
 *
 * Responsive: Chart.js canvases are sized by their CSS container, and
 * maintainAspectRatio is false so they fit the grid on mobile.
 */

(function () {
  const picker = document.querySelector("[data-range-picker]");
  if (!picker) return;

  const button = picker.querySelector("[data-range-button]");
  const label = picker.querySelector("[data-range-label]");
  const menu = picker.querySelector("[data-range-menu]");
  const customForm = picker.querySelector("[data-range-custom]");

  const cssVar = (name) =>
    getComputedStyle(document.documentElement).getPropertyValue(name).trim();

  const palette = {
    ink: cssVar("--ink") || "#e8eaf0",
    dim: cssVar("--ink-muted") || "#6d7588",
    accent: cssVar("--accent") || "#7aa2ff",
    success: cssVar("--success") || "#4ade80",
    danger: cssVar("--danger") || "#f47171",
    e5: cssVar("--fuel-e5") || "#f59e0b",
    e10: cssVar("--fuel-e10") || "#22d3ee",
    border: cssVar("--border") || "#262b38",
  };

  // Chart.js global defaults — mobile-friendly.
  if (window.Chart) {
    Chart.defaults.color = palette.dim;
    Chart.defaults.borderColor = palette.border;
    Chart.defaults.font.family = getComputedStyle(document.body).fontFamily;
    Chart.defaults.font.size = 11;
    Chart.defaults.maintainAspectRatio = false;
    Chart.defaults.plugins.legend.labels.boxWidth = 10;
    Chart.defaults.plugins.legend.labels.boxHeight = 10;
    Chart.defaults.plugins.legend.position = "bottom";
  }

  const charts = {};
  function ensureChart(key, config) {
    const canvas = document.querySelector(`canvas[data-chart="${key}"]`);
    if (!canvas) return null;
    if (charts[key]) {
      charts[key].destroy();
    }
    charts[key] = new Chart(canvas.getContext("2d"), config);
    return charts[key];
  }

  function setMetric(name, value) {
    const el = document.querySelector(`[data-metric="${name}"]`);
    if (!el) return;
    if (value === null || value === undefined) {
      el.textContent = "—";
    } else {
      el.textContent = value;
    }
  }

  function formatL(v) { return (Number(v) || 0).toFixed(1) + " L"; }
  function formatEur(v) { return (Number(v) || 0).toFixed(2) + " €"; }
  function formatL100(v) { return (Number(v) || 0).toFixed(2) + " L/100km"; }

  function renderMetrics(metrics) {
    setMetric("total_liters", formatL(metrics.total_liters));
    setMetric("total_eur", formatEur(metrics.total_eur));
    setMetric(
      "avg_price_per_liter",
      metrics.avg_price_per_liter ? metrics.avg_price_per_liter.toFixed(3) + " €/L" : "—",
    );
    setMetric("entries", String(metrics.entries));
    setMetric(
      "avg_l_per_100km",
      metrics.avg_l_per_100km === null ? null : formatL100(metrics.avg_l_per_100km),
    );
    setMetric(
      "avg_cost_per_100km",
      metrics.avg_cost_per_100km === null ? null : formatEur(metrics.avg_cost_per_100km) + "/100km",
    );
  }

  function renderPriceTrend(series) {
    ensureChart("price_trend", {
      type: "line",
      data: {
        labels: series.map((p) => p.month),
        datasets: [{
          label: "Avg €/L",
          data: series.map((p) => p.avg_price_per_liter),
          borderColor: palette.accent,
          backgroundColor: palette.accent + "33",
          tension: 0.25,
          fill: true,
          pointRadius: 3,
        }],
      },
      options: {
        scales: { y: { ticks: { callback: (v) => v.toFixed(2) } } },
        plugins: { legend: { display: false } },
      },
    });
  }

  function renderMonthlyBar(key, series, color, label, unit) {
    ensureChart(key, {
      type: "bar",
      data: {
        labels: series.map((p) => p.month),
        datasets: [{
          label,
          data: series.map((p) => p.value),
          backgroundColor: color,
          borderRadius: 4,
        }],
      },
      options: {
        scales: {
          y: {
            ticks: {
              callback: (v) => (Number(v) || 0).toFixed(unit === "€" ? 0 : 0) + " " + unit,
            },
          },
        },
        plugins: { legend: { display: false } },
      },
    });
  }

  function renderConsumption(series) {
    ensureChart("consumption", {
      type: "line",
      data: {
        labels: series.map((p) => p.datetime.slice(0, 10)),
        datasets: [{
          label: "L/100km",
          data: series.map((p) => p.liters_per_100km),
          borderColor: palette.success,
          backgroundColor: palette.success + "22",
          pointBackgroundColor: series.map((p) =>
            p.quality === "exact" ? palette.success : palette.e5,
          ),
          pointRadius: 4,
          tension: 0.2,
          fill: true,
        }],
      },
      options: {
        scales: { y: { ticks: { callback: (v) => v.toFixed(1) } } },
        plugins: { legend: { display: false } },
      },
    });
  }

  function renderFuelTypes(series) {
    const colorFor = (ft) =>
      ft === "E5" ? palette.e5 : ft === "E10" ? palette.e10 : palette.accent;
    ensureChart("fuel_types", {
      type: "doughnut",
      data: {
        labels: series.map((p) => p.fuel_type),
        datasets: [{
          data: series.map((p) => p.total_liters),
          backgroundColor: series.map((p) => colorFor(p.fuel_type)),
          borderWidth: 0,
        }],
      },
      options: {
        cutout: "62%",
        plugins: {
          tooltip: {
            callbacks: { label: (ctx) => `${ctx.label}: ${ctx.parsed.toFixed(1)} L` },
          },
        },
      },
    });
  }

  function renderCountries(series) {
    ensureChart("countries", {
      type: "bar",
      data: {
        labels: series.map((p) => p.country),
        datasets: [{
          label: "Avg €/L",
          data: series.map((p) => p.avg_price_per_liter),
          backgroundColor: palette.accent,
          borderRadius: 4,
        }],
      },
      options: {
        indexAxis: "y",
        scales: { x: { ticks: { callback: (v) => v.toFixed(2) } } },
        plugins: { legend: { display: false } },
      },
    });
  }

  async function loadRange(range, start, end) {
    const qs = new URLSearchParams({ range });
    if (range === "custom" && start && end) {
      qs.set("start", start);
      qs.set("end", end);
    }
    const res = await fetch("/api/analysis?" + qs.toString());
    if (!res.ok) {
      console.error("Failed to load analysis", res.status);
      return;
    }
    const data = await res.json();
    label.textContent = data.range_label;
    renderMetrics(data.metrics);
    renderPriceTrend(data.charts.price_trend);
    renderMonthlyBar("monthly_liters", data.charts.monthly_liters, palette.accent, "Liters", "L");
    renderMonthlyBar("monthly_spending", data.charts.monthly_spending, palette.success, "€", "€");
    renderConsumption(data.charts.consumption_series);
    renderFuelTypes(data.charts.fuel_type_summary);
    renderCountries(data.charts.country_breakdown);
  }

  function toggleMenu(open) {
    const willOpen = typeof open === "boolean" ? open : menu.hidden;
    menu.hidden = !willOpen;
    button.setAttribute("aria-expanded", String(willOpen));
  }

  button.addEventListener("click", () => toggleMenu());

  document.addEventListener("click", (event) => {
    if (!picker.contains(event.target)) toggleMenu(false);
  });

  menu.querySelectorAll("[data-range]").forEach((li) => {
    li.addEventListener("click", () => {
      const range = li.getAttribute("data-range");
      if (range === "custom") {
        customForm.hidden = false;
        toggleMenu(false);
        return;
      }
      customForm.hidden = true;
      toggleMenu(false);
      loadRange(range);
    });
  });

  customForm.addEventListener("submit", (event) => {
    event.preventDefault();
    const start = customForm.elements.start.value;
    const end = customForm.elements.end.value;
    if (start && end) {
      toggleMenu(false);
      loadRange("custom", start, end);
    }
  });

  // Initial load.
  loadRange("month");
})();
