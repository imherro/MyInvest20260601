(function () {
  const body = document.body;
  const apiPath = body.dataset.apiPath;
  const page = body.dataset.page;
  const statusEl = document.querySelector("[data-refresh-status]");
  const tableState = new Map();
  const forbiddenKeyRe =
    /(^|_)(amount|market_value|profit_amount|total_amount|total_asset|share_count|shares|quantity|qty|available_qty|available_quantity|trade_amount|account|full_account|order|fill|deal|cost_price|raw_cost_price|current_price|qmt_timetag)($|_)/i;
  const localPathRe = /(?:[A-Za-z]:(?!\/\/)[\\/]|\\\\|\/Users\/|\/home\/)/;
  const forbiddenTextRe =
    /(total asset|market value|profit amount|trade amount|share count|available quantity|full account|order id|fill record|deal record)/i;

  function text(value, fallback = "n/a") {
    if (value === null || value === undefined || value === "") return fallback;
    return String(value);
  }

  function pct(value) {
    if (value === null || value === undefined || value === "") return "";
    const num = Number(value);
    return Number.isFinite(num) ? `${num.toFixed(2)}%` : text(value, "");
  }

  function pp(value) {
    if (value === null || value === undefined || value === "") return "";
    const num = Number(value);
    return Number.isFinite(num) ? `${num.toFixed(2)}pp` : text(value, "");
  }

  function range(min, max, unit = "%") {
    if (min === null || min === undefined) return "";
    const left = Number(min);
    const right = Number(max);
    if (!Number.isFinite(left)) return "";
    if (!Number.isFinite(right) || right === left) return `${left.toFixed(2)}${unit}`;
    return `${left.toFixed(2)}-${right.toFixed(2)}${unit}`;
  }

  function yesNo(value) {
    return value ? "yes" : "no";
  }

  function assertRatioOnly(value, path = "$") {
    if (Array.isArray(value)) {
      value.forEach((item, index) => assertRatioOnly(item, `${path}[${index}]`));
      return;
    }
    if (value && typeof value === "object") {
      Object.entries(value).forEach(([key, item]) => {
        if (forbiddenKeyRe.test(String(key))) {
          throw new Error(`ratio-only blocked key ${path}.${key}`);
        }
        assertRatioOnly(item, `${path}.${key}`);
      });
      return;
    }
    if (typeof value === "string" && (localPathRe.test(value) || forbiddenTextRe.test(value))) {
      throw new Error(`ratio-only blocked text ${path}`);
    }
  }

  function setBind(name, value) {
    document.querySelectorAll(`[data-bind="${name}"]`).forEach((node) => {
      node.textContent = text(value);
    });
  }

  function setStatusCard(name, status) {
    document.querySelectorAll(`[data-status-card="${name}"]`).forEach((node) => {
      node.classList.remove("ok", "warn", "fail");
      if (status) node.classList.add(status);
    });
  }

  function cellObject(cell) {
    if (cell && typeof cell === "object" && Object.prototype.hasOwnProperty.call(cell, "value")) {
      return { value: text(cell.value, ""), className: cell.className || "" };
    }
    return { value: text(cell, ""), className: "" };
  }

  function rowSearchText(item) {
    return item.cells.map((cell) => cell.value).join(" ").toLowerCase();
  }

  function defaultDetails(row) {
    return Object.entries(row || {})
      .filter(([, value]) => value !== null && value !== undefined && typeof value !== "object")
      .map(([key, value]) => `${key}: ${value}`)
      .join(" | ");
  }

  function setRows(id, rows, cells, detailFactory = defaultDetails) {
    const tbody = document.getElementById(id);
    if (!tbody) return;
    const existing = tableState.get(id) || {};
    tableState.set(id, {
      rows: (rows || []).map((row, index) => ({
        key: `${id}-${index}`,
        row,
        cells: cells(row).map(cellObject),
        detail: detailFactory(row),
      })),
      page: 1,
      pageSize: Number(tbody.closest("table")?.dataset.pageSize || 10),
      query: existing.query || "",
      sortIndex: existing.sortIndex,
      sortType: existing.sortType || "text",
      sortDirection: existing.sortDirection || "asc",
      expanded: existing.expanded || new Set(),
    });
    renderTable(id);
  }

  function filteredRows(state) {
    const query = (state.query || "").trim().toLowerCase();
    let rows = state.rows.filter((item) => !query || rowSearchText(item).includes(query));
    if (state.sortIndex !== undefined) {
      rows = rows.slice().sort((left, right) => {
        const leftText = left.cells[state.sortIndex]?.value || "";
        const rightText = right.cells[state.sortIndex]?.value || "";
        const leftValue = state.sortType === "number" ? parseFloat(leftText) || 0 : leftText;
        const rightValue = state.sortType === "number" ? parseFloat(rightText) || 0 : rightText;
        if (leftValue < rightValue) return state.sortDirection === "asc" ? -1 : 1;
        if (leftValue > rightValue) return state.sortDirection === "asc" ? 1 : -1;
        return 0;
      });
    }
    return rows;
  }

  function renderTable(id) {
    const tbody = document.getElementById(id);
    const state = tableState.get(id);
    if (!tbody || !state) return;
    const table = tbody.closest("table");
    const rows = filteredRows(state);
    const totalPages = Math.max(1, Math.ceil(rows.length / state.pageSize));
    state.page = Math.min(Math.max(1, state.page), totalPages);
    const start = (state.page - 1) * state.pageSize;
    const visibleRows = rows.slice(start, start + state.pageSize);
    tbody.replaceChildren();
    visibleRows.forEach((item) => {
      const tr = document.createElement("tr");
      tr.className = "expandable-row";
      tr.title = "Click to expand details";
      tr.addEventListener("click", () => {
        if (state.expanded.has(item.key)) state.expanded.delete(item.key);
        else state.expanded.add(item.key);
        renderTable(id);
      });
      item.cells.forEach((cell) => {
        const td = document.createElement("td");
        td.textContent = cell.value;
        if (cell.className) td.className = cell.className;
        tr.appendChild(td);
      });
      tbody.appendChild(tr);
      if (state.expanded.has(item.key)) {
        const detailRow = document.createElement("tr");
        detailRow.className = "detail-row";
        const detailCell = document.createElement("td");
        detailCell.colSpan = Math.max(1, item.cells.length);
        detailCell.textContent = item.detail || "No additional details.";
        detailRow.appendChild(detailCell);
        tbody.appendChild(detailRow);
      }
    });
    renderPagination(table, id, rows.length, totalPages);
  }

  function renderPagination(table, id, totalRows, totalPages) {
    if (!table) return;
    let controls = document.querySelector(`[data-pagination-for="${id}"]`);
    if (!controls) {
      controls = document.createElement("div");
      controls.className = "pagination";
      controls.dataset.paginationFor = id;
      table.insertAdjacentElement("afterend", controls);
    }
    const state = tableState.get(id);
    controls.replaceChildren();
    const prev = document.createElement("button");
    prev.type = "button";
    prev.textContent = "Prev";
    prev.disabled = state.page <= 1;
    prev.addEventListener("click", () => {
      state.page -= 1;
      renderTable(id);
    });
    const next = document.createElement("button");
    next.type = "button";
    next.textContent = "Next";
    next.disabled = state.page >= totalPages;
    next.addEventListener("click", () => {
      state.page += 1;
      renderTable(id);
    });
    const info = document.createElement("span");
    info.textContent = `Page ${state.page}/${totalPages} - ${totalRows} rows`;
    controls.append(prev, info, next);
  }

  function renderGapChart(buckets) {
    const chart = document.getElementById("bucketGapChart");
    if (!chart) return;
    chart.replaceChildren();
    const rows = buckets || [];
    const maxGap = Math.max(1, ...rows.map((row) => Math.abs(Number(row.gap_pct) || 0)));
    rows.forEach((row) => {
      const value = Number(row.gap_pct) || 0;
      const wrapper = document.createElement("div");
      wrapper.className = "gap-row";
      const label = document.createElement("div");
      label.textContent = text(row.bucket, "");
      const track = document.createElement("div");
      track.className = "gap-track";
      const bar = document.createElement("div");
      bar.className = `gap-bar ${value >= 0 ? "positive" : "negative"}`;
      bar.style.width = `${Math.min(50, (Math.abs(value) / maxGap) * 50)}%`;
      const number = document.createElement("div");
      number.className = "num";
      number.textContent = pp(value);
      track.appendChild(bar);
      wrapper.append(label, track, number);
      chart.appendChild(wrapper);
    });
  }

  function renderDashboard(data) {
    const plan = data.action_plan || {};
    const market = data.market_score || {};
    const marketPosition = data.market_position || {};
    const portfolio = data.portfolio || {};
    const target = data.target_allocation || {};
    const intraday = data.intraday_rules || {};
    const checks = data.system_check || {};
    const projectCheck = (checks.checks || []).find((item) => item.check_name === "project_check_current_only") || {};
    setBind("action_generated_at", plan.generated_at);
    setBind("market_state", market.state);
    setBind("market_position_score", marketPosition.score);
    setBind("market_position_label", marketPosition.label);
    setBind("market_position_source", marketPosition.source);
    setBind("equity_current", pct(portfolio.equity_pct));
    setBind("equity_target", range(target.equity_min_pct, target.equity_max_pct));
    setBind("cash_current", pct(portfolio.cash_short_pct));
    setBind("cash_target", range(target.cash_min_pct, target.cash_max_pct));
    setBind("research_first_status", (checks.research_first_gate || {}).status);
    setBind("intraday_status", `${text(intraday.status)} / stale ${yesNo(intraday.stale_flag)} / degraded ${yesNo(intraday.degraded_flag)}`);
    setBind("project_check_status", projectCheck.status);
    setStatusCard("research-first", (checks.research_first_gate || {}).status === "ok" ? "ok" : "fail");
    setStatusCard("intraday", intraday.stale_flag || intraday.degraded_flag ? "warn" : "ok");
    setStatusCard("project-check", projectCheck.status === "ok" ? "ok" : "fail");
    renderGapChart((target || {}).buckets || []);
    setRows(
      "moduleRows",
      ((data.latest_index || {}).modules || []),
      (row) => [
        row.module,
        row.generated_at,
        row.basis_trade_date,
        row.sha256 ? row.sha256.slice(0, 8) : "",
        "current",
      ],
      (row) => `source: ${row.path || ""} | sha256: ${row.sha256 || ""}`,
    );
  }

  function renderActionPlan(data) {
    const plan = data.action_plan || {};
    setBind("plan_status", plan.status);
    setBind("plan_market", plan.market_state);
    setBind("plan_generated", plan.generated_at);
    setBind("plan_basis", plan.basis_trade_date);
    setRows(
      "actionRows",
      plan.actions || [],
      (row) => [
        row.sequence,
        row.action_type,
        row.bucket,
        row.name || row.code,
        { value: pct(row.current_position_pct), className: "num" },
        { value: range(row.target_range_min_pct, row.target_range_max_pct), className: "num" },
        { value: range(row.suggested_change_min_pp, row.suggested_change_max_pp, "pp"), className: "num" },
        yesNo(row.requires_manual_confirmation),
        row.reason,
      ],
      (row) =>
        `code: ${row.code || ""} | type: ${row.subject_type || ""} | reason: ${row.reason || ""} | manual confirmation: ${yesNo(row.requires_manual_confirmation)}`,
    );
  }

  function renderTargetAllocation(data) {
    const target = data.target_allocation || {};
    setBind("target_equity", range(target.equity_min_pct, target.equity_max_pct));
    setBind("target_cash", range(target.cash_min_pct, target.cash_max_pct));
    setBind("target_generated", target.generated_at);
    setBind("target_basis", target.basis_trade_date);
    setRows(
      "targetRows",
      target.buckets || [],
      (row) => [
        row.bucket,
        { value: pct(row.actual_pct), className: "num" },
        { value: pct(row.target_pct), className: "num" },
        { value: pp(row.gap_pct), className: "num" },
      ],
      (row) => `bucket: ${row.bucket || ""} | actual: ${pct(row.actual_pct)} | target: ${pct(row.target_pct)} | gap: ${pp(row.gap_pct)}`,
    );
  }

  function renderSubjectGap(data) {
    const rows = data.rows || [];
    const summary = data.summary || {};
    setBind("subject_gap_count", summary.subject_count ?? rows.length);
    setBind("subject_stale_count", summary.stale_count ?? 0);
    setBind("subject_green_count", summary.green_count ?? 0);
    setBind("subject_yellow_count", summary.yellow_count ?? 0);
    setBind("subject_red_count", summary.red_count ?? 0);
    setBind("subject_unknown_count", summary.unknown_count ?? 0);
    setRows(
      "subjectGapRows",
      rows,
      (row) => [
        row.code,
        row.name,
        row.bucket,
        { value: pct(row.position_pct), className: "num" },
        { value: pct(row.actual_pct), className: "num" },
        { value: pct(row.target_pct), className: "num" },
        { value: pp(row.gap_pct), className: "num" },
        row.gap_status,
        yesNo(row.staleness_flag),
        row.last_update_timestamp,
      ],
      (row) => {
        const sources = Object.values(row.source_paths || {}).join(" | ");
        return `basis: ${row.basis_trade_date || ""} | staleness: ${row.staleness_reason || ""} | subject type: ${row.subject_type || ""} | sources: ${sources || "none"}`;
      },
    );
  }

  function renderResearchFirst(data) {
    const gate = data.gate || {};
    const items = data.items || [];
    setBind("research_first_gate", gate.status);
    setBind("research_first_count", items.length);
    setStatusCard("research-first-page", gate.status === "ok" ? "ok" : "fail");
    setRows(
      "researchFirstRows",
      items,
      (row) => [
        row.code,
        row.name,
        yesNo(row.missing_profile),
        yesNo(row.missing_valuation),
        yesNo(row.missing_liquidity),
        yesNo(row.missing_theme_binding),
        row.allowed_conclusion,
        row.blocking_reason,
      ],
      (row) => `blocking reason: ${row.blocking_reason || ""}`,
    );
  }

  function renderPortfolio(data) {
    const portfolio = data.portfolio || {};
    setBind("portfolio_count", (portfolio.positions || []).length);
    setBind("portfolio_equity", pct(portfolio.equity_pct));
    setBind("portfolio_cash", pct(portfolio.cash_short_pct));
    setBind("portfolio_generated", portfolio.generated_at);
    setRows(
      "portfolioRows",
      portfolio.positions || [],
      (row) => [
        row.bucket,
        { value: pct(row.position_pct), className: "num" },
        row.code,
        row.name,
        yesNo(row.reference_only_flag),
      ],
      (row) => `code: ${row.code || ""} | name: ${row.name || ""} | bucket: ${row.bucket || ""} | reference only: ${yesNo(row.reference_only_flag)}`,
    );
  }

  function renderIntradayRules(data) {
    const rules = data.intraday_rules || {};
    setBind("intraday_risk_mode", rules.risk_mode);
    setBind("intraday_status", rules.status);
    setBind("intraday_stale", yesNo(rules.stale_flag));
    setBind("intraday_degraded", yesNo(rules.degraded_flag));
    setRows(
      "intradayRows",
      rules.buckets || [],
      (row) => [
        row.bucket,
        { value: pct(row.actual_pct), className: "num" },
        { value: pct(row.target_pct), className: "num" },
        { value: pp(row.gap_pct), className: "num" },
      ],
      (row) => `bucket: ${row.bucket || ""} | actual: ${pct(row.actual_pct)} | target: ${pct(row.target_pct)} | gap: ${pp(row.gap_pct)}`,
    );
    setRows(
      "disabledTriggerRows",
      rules.disabled_triggers || [],
      (row) => [row.subject, row.trigger_condition, row.action_after_trigger],
      (row) => `trigger: ${row.trigger_condition || ""} | after trigger: ${row.action_after_trigger || ""}`,
    );
  }

  function renderSystemChecks(data) {
    setBind("system_status", data.status);
    setBind("sensitive_status", (data.sensitive_scan || {}).status);
    setBind("sensitive_summary", (data.sensitive_scan || {}).summary);
    setBind("research_gate_status", (data.research_first_gate || {}).status);
    setBind("allocation_status", (data.allocation_consistency || {}).status);
    setRows("checkRows", data.checks || [], (row) => [row.check_name, row.status, row.message, row.generated_at]);
    setRows("countRows", Object.entries(data.counts || {}).map(([table, count]) => ({ table, count })), (row) => [
      row.table,
      { value: row.count, className: "num" },
    ]);
  }

  function renderDecisionLog(data) {
    setRows("decisionRows", data.entries || [], (row) => [row.entry_time, row.summary], (row) => row.ratio_only_text || row.summary || "");
  }

  const renderers = {
    dashboard: renderDashboard,
    "action-plan": renderActionPlan,
    "target-allocation": renderTargetAllocation,
    "subjects-gap": renderSubjectGap,
    "research-first": renderResearchFirst,
    portfolio: renderPortfolio,
    "intraday-rules": renderIntradayRules,
    "system-checks": renderSystemChecks,
    "decision-log": renderDecisionLog,
  };

  async function refresh() {
    if (!apiPath || !renderers[page]) return;
    try {
      updateRefreshStatus("refreshing...");
      const response = await fetch(apiPath, { cache: "no-store" });
      const payload = await response.json();
      assertRatioOnly(payload);
      if (!response.ok || payload.ok === false) {
        throw new Error(payload.detail || "API refresh failed");
      }
      renderers[page](payload.data);
      updateRefreshStatus(`updated ${new Date().toLocaleTimeString()}`);
    } catch (error) {
      updateRefreshStatus(error.message || "refresh failed", false);
    }
  }

  function updateRefreshStatus(message, ok = true) {
    if (!statusEl) return;
    statusEl.textContent = message;
    statusEl.className = ok ? "refresh-status" : "refresh-status warn";
  }

  function setupSearch() {
    document.querySelectorAll("[data-table-search]").forEach((input) => {
      if (!input.nextElementSibling || input.nextElementSibling.dataset.clearSearch !== input.dataset.tableSearch) {
        const clear = document.createElement("button");
        clear.type = "button";
        clear.textContent = "Clear";
        clear.dataset.clearSearch = input.dataset.tableSearch;
        input.insertAdjacentElement("afterend", clear);
        clear.addEventListener("click", () => {
          input.value = "";
          updateSearchState(input);
        });
      }
      input.addEventListener("input", () => {
        updateSearchState(input);
      });
      input.addEventListener("keydown", (event) => {
        if (event.key === "Escape") {
          input.value = "";
          updateSearchState(input);
        }
      });
    });
  }

  function updateSearchState(input) {
    const id = input.dataset.tableSearch;
    const bodyId = id.replace("Table", "Rows");
    const state = tableState.get(bodyId) || tableState.get(id);
    if (!state) return;
    state.query = input.value;
    state.page = 1;
    renderTable(bodyId);
  }

  function setupSort() {
    document.querySelectorAll("th[data-sort]").forEach((header) => {
      header.addEventListener("click", () => {
        const table = header.closest("table");
        const tbody = table?.tBodies?.[0];
        if (!tbody) return;
        const state = tableState.get(tbody.id);
        if (!state) return;
        if (state.sortIndex === header.cellIndex) {
          state.sortDirection = state.sortDirection === "asc" ? "desc" : "asc";
        } else {
          state.sortIndex = header.cellIndex;
          state.sortDirection = "asc";
        }
        state.sortType = header.dataset.sort || "text";
        state.page = 1;
        renderTable(tbody.id);
      });
    });
  }

  document.addEventListener("DOMContentLoaded", () => {
    document.querySelector("[data-refresh]")?.addEventListener("click", refresh);
    setupSearch();
    setupSort();
    refresh();
    window.setInterval(refresh, 60000);
  });
})();
