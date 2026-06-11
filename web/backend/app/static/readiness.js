(function () {
  const forbiddenKeyRe =
    /(^|_)(amount|market_value|profit_amount|total_amount|total_asset|share_count|shares|quantity|qty|available_qty|available_quantity|trade_amount|account|full_account|order|fill|deal|cost_price|raw_cost_price|current_price|qmt_timetag)($|_)/i;
  const localPathRe = /(?:[A-Za-z]:(?!\/\/)[\\/]|\\\\|\/Users\/|\/home\/)/;
  const statusEl = document.querySelector("[data-refresh-status]");
  let activeView = "summary";
  let latestChecks = [];

  function text(value, fallback = "n/a") {
    if (value === null || value === undefined || value === "") return fallback;
    return String(value);
  }

  function yesNo(value) {
    return value ? "yes" : "no";
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
    });
  }

  function statusClass(status) {
    if (status === "ok") return "ok";
    if (status === "degraded") return "warn";
    return "fail";
  }

  function applyStatusTone(cell, value) {
    window.MyInvestStatusTone?.apply(cell, value, "status-cell");
  }

  function applyBooleanTone(cell, value, positiveWhenTrue = true) {
    cell.classList.remove(
      "status-cell",
      "status-tone-ok",
      "status-tone-warn",
      "status-tone-bad",
      "status-tone-info",
      "status-tone-neutral",
    );
    cell.classList.add("status-cell", value === positiveWhenTrue ? "status-tone-ok" : "status-tone-bad");
  }

  function setStatusCard(name, state) {
    document.querySelectorAll(`[data-status-card="${name}"]`).forEach((node) => {
      node.classList.remove("ok", "warn", "fail");
      node.classList.add(state);
    });
  }

  function updateRefreshStatus(message, ok = true) {
    if (!statusEl) return;
    statusEl.textContent = message;
    statusEl.className = ok ? "refresh-status" : "refresh-status warn";
  }

  function renderSummary(readiness) {
    const summary = readiness.summary || {};
    setBind("readiness_status", readiness.status);
    setBind("readiness_check_count", summary.check_count ?? 0);
    setBind("readiness_web_smoke", readiness.web_smoke_compatible ? "compatible" : "blocked");
    setBind("readiness_fail_closed", yesNo(readiness.fail_closed));
    setBind("readiness_checked_at", readiness.checked_at);
    setStatusCard("readiness-status", statusClass(readiness.status));
    setStatusCard("readiness-checks", "ok");
    setStatusCard("readiness-smoke", readiness.web_smoke_compatible ? "ok" : "fail");
    setStatusCard("readiness-fail-closed", readiness.fail_closed ? "fail" : "ok");
  }

  function renderChecks(checks) {
    latestChecks = checks || [];
    renderFilteredChecks();
  }

  function renderFilteredChecks() {
    const tbody = document.getElementById("readinessCheckRows");
    if (!tbody) return;
    const query = (document.querySelector('[data-table-search="readinessCheckTable"]')?.value || "").toLowerCase();
    tbody.replaceChildren();
    latestChecks
      .filter((check) => !query || JSON.stringify(check).toLowerCase().includes(query))
      .forEach((check) => {
        const source = check.source || {};
        const tr = document.createElement("tr");
        [
          check.label || check.name,
          check.status,
          yesNo(check.web_smoke_compatible),
          (check.degraded_reasons || []).join(", ") || "none",
          source.api_path || source.service || source.provider || "readiness",
        ].forEach((value, index) => {
          const td = document.createElement("td");
          td.textContent = text(value, "");
          if (index === 1) applyStatusTone(td, value);
          if (index === 2) applyBooleanTone(td, check.web_smoke_compatible);
          tr.appendChild(td);
        });
        tbody.appendChild(tr);
      });
  }

  function renderSafety(safety) {
    const tbody = document.getElementById("readinessSafetyRows");
    if (!tbody) return;
    const rows = [
      ["read_only", safety.read_only],
      ["ratio_only", safety.ratio_only],
      ["current_only", safety.current_only],
      ["research_first", safety.research_first],
      ["get_only", safety.get_only],
      ["no_validation_execution", safety.no_validation_commands],
      ["no_file_writes", safety.no_file_writes],
      ["no_sqlite_writes", safety.no_sqlite_writes],
    ];
    tbody.replaceChildren();
    rows.forEach(([name, value]) => {
      const tr = document.createElement("tr");
      const nameCell = document.createElement("td");
      const valueCell = document.createElement("td");
      nameCell.textContent = name;
      valueCell.textContent = yesNo(value);
      applyBooleanTone(valueCell, value);
      tr.append(nameCell, valueCell);
      tbody.appendChild(tr);
    });
  }

  function renderReasons(reasons) {
    const list = document.getElementById("readinessReasonRows");
    if (!list) return;
    list.replaceChildren();
    const values = reasons && reasons.length ? reasons : ["none"];
    values.forEach((reason) => {
      const item = document.createElement("li");
      item.textContent = text(reason, "");
      list.appendChild(item);
    });
  }

  function renderReadiness(readiness) {
    renderSummary(readiness);
    renderChecks(readiness.checks || []);
    renderSafety(readiness.safety || {});
    renderReasons(readiness.degraded_reasons || []);
  }

  async function refreshReadiness(view = activeView) {
    activeView = view === "checks" ? "checks" : "summary";
    document.querySelectorAll("[data-readiness-view]").forEach((button) => {
      button.setAttribute("aria-pressed", button.dataset.readinessView === activeView ? "true" : "false");
    });
    const url = activeView === "checks" ? "/api/readiness/checks" : "/api/readiness/summary";
    try {
      updateRefreshStatus("refreshing...");
      const response = await fetch(url, { cache: "no-store" });
      const payload = await response.json();
      assertSafe(payload);
      if (!response.ok || payload.ok === false) throw new Error(payload.detail || "Readiness refresh failed");
      renderReadiness(payload.data || {});
      updateRefreshStatus(`updated ${new Date().toLocaleTimeString()}`);
    } catch (error) {
      updateRefreshStatus(error.message || "readiness refresh failed", false);
    }
  }

  document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll("[data-readiness-view]").forEach((button) => {
      button.addEventListener("click", () => refreshReadiness(button.dataset.readinessView));
    });
    document.querySelector("[data-refresh]")?.addEventListener("click", () => refreshReadiness(activeView));
    document.querySelector('[data-table-search="readinessCheckTable"]')?.addEventListener("input", renderFilteredChecks);
    refreshReadiness("summary");
  });
})();
