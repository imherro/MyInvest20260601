(function () {
  const forbiddenKeyRe =
    /(^|_)(amount|market_value|profit_amount|total_amount|total_asset|share_count|shares|quantity|qty|available_qty|available_quantity|trade_amount|account|full_account|order|fill|deal|cost_price|raw_cost_price|current_price|qmt_timetag)($|_)/i;
  const localPathRe = /(?:[A-Za-z]:(?!\/\/)[\\/]|\\\\|\/Users\/|\/home\/)/;

  function text(value, fallback = "n/a") {
    if (value === null || value === undefined || value === "") return fallback;
    return String(value);
  }

  function assertSafe(value, path = "$") {
    if (Array.isArray(value)) {
      value.forEach((item, index) => assertSafe(item, `${path}[${index}]`));
      return;
    }
    if (value && typeof value === "object") {
      Object.entries(value).forEach(([key, item]) => {
        if (forbiddenKeyRe.test(String(key))) throw new Error(`blocked key ${path}.${key}`);
        assertSafe(item, `${path}.${key}`);
      });
      return;
    }
    if (typeof value === "string" && localPathRe.test(value)) {
      throw new Error(`blocked path ${path}`);
    }
  }

  function setBind(name, value) {
    document.querySelectorAll(`[data-bind="${name}"]`).forEach((node) => {
      node.textContent = text(value);
      window.MyInvestStatusTone?.apply(node, value, "status-inline");
    });
  }

  function renderRows(rows) {
    const tbody = document.getElementById("auditBundleRows");
    if (!tbody) return;
    tbody.replaceChildren();
    (rows || []).forEach((row) => {
      const tr = document.createElement("tr");
      [row.label, row.status, row.api_path].forEach((value, index) => {
        const td = document.createElement("td");
        td.textContent = text(value, "");
        if (index === 1) window.MyInvestStatusTone?.apply(td, value, "status-cell");
        tr.appendChild(td);
      });
      tbody.appendChild(tr);
    });
  }

  function renderChart(rows) {
    const chart = document.getElementById("auditPreviewChart");
    if (!chart) return;
    chart.replaceChildren();
    const values = rows || [];
    const maxValue = Math.max(1, ...values.map((row) => Number(row.value) || 0));
    values.forEach((row) => {
      const wrapper = document.createElement("div");
      wrapper.className = "gap-row";
      const label = document.createElement("div");
      label.textContent = text(row.label, "");
      const track = document.createElement("div");
      track.className = "gap-track";
      const bar = document.createElement("div");
      bar.className = "gap-bar positive";
      bar.style.width = `${Math.max(2, Math.min(100, ((Number(row.value) || 0) / maxValue) * 100))}%`;
      const count = document.createElement("div");
      count.className = "num";
      count.textContent = text(row.value, "0");
      track.appendChild(bar);
      wrapper.append(label, track, count);
      chart.appendChild(wrapper);
    });
  }

  function renderBundle(bundle) {
    const summary = bundle.summary || {};
    setBind("audit_readonly", bundle.read_only ? "read-only" : "check");
    setBind("audit_section_count", summary.section_count ?? 0);
    setBind("audit_current_modules", summary.current_module_count ?? 0);
    setBind("audit_subjects", summary.subject_count ?? 0);
    renderRows(bundle.sections || []);
    renderChart(bundle.preview_chart || []);
  }

  async function refreshAudit() {
    const windowInput = document.querySelector("[data-audit-window]");
    const moduleInput = document.querySelector("[data-audit-module]");
    const selectedWindow = windowInput?.value || "current";
    const selectedModule = moduleInput?.value || "all";
    const url = `/api/audit/bundle?time_window=${encodeURIComponent(selectedWindow)}&module_filter=${encodeURIComponent(selectedModule)}`;
    const download = document.getElementById("auditDownloadLink");
    if (download) download.href = url;
    const response = await fetch(url, { cache: "no-store" });
    const payload = await response.json();
    assertSafe(payload);
    if (!response.ok || payload.ok === false) throw new Error(payload.detail || "Audit refresh failed");
    renderBundle(payload.data || {});
  }

  document.addEventListener("DOMContentLoaded", () => {
    document.querySelector("[data-audit-window]")?.addEventListener("change", refreshAudit);
    document.querySelector("[data-audit-module]")?.addEventListener("change", refreshAudit);
    refreshAudit().catch(() => {});
  });
})();
