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
      filters: existing.filters || {},
      expanded: existing.expanded || new Set(),
    });
    renderTable(id);
  }

  function filteredRows(state) {
    const query = (state.query || "").trim().toLowerCase();
    let rows = state.rows.filter((item) => !query || rowSearchText(item).includes(query));
    Object.entries(state.filters || {}).forEach(([key, value]) => {
      if (!value) return;
      rows = rows.filter((item) => text(item.row?.[key], "").toLowerCase() === String(value).toLowerCase());
    });
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

  function renderDashboardQuickLinks(links) {
    const container = document.getElementById("dashboardQuickLinks");
    if (!container) return;
    container.replaceChildren();
    (links || []).forEach((item) => {
      const link = document.createElement("a");
      link.className = "button-link";
      link.href = text(item.href, "#");
      link.textContent = text(item.label, "");
      container.appendChild(link);
    });
  }

  function renderDashboard(data) {
    const system = data.system_status || {};
    const market = data.market_position || {};
    const action = data.action_plan_summary || {};
    const allocation = data.allocation_summary || {};
    const subjectStatus = data.subject_status_summary || {};
    const subjectGap = data.subject_gap_summary || {};
    const cashGate = subjectStatus.cash_equivalent_gate || {};
    setBind("dashboard_system_status", system.status);
    setBind("dashboard_project_check", system.project_check_status);
    setBind("dashboard_research_first", system.research_first_gate_status);
    setBind("dashboard_allocation_status", system.allocation_consistency_status);
    setBind("dashboard_intraday_status", system.intraday_status);
    setBind("dashboard_intraday_stale", yesNo(system.intraday_stale_flag));
    setBind("dashboard_intraday_degraded", yesNo(system.intraday_degraded_flag));
    setBind("dashboard_market_score", market.score);
    setBind("dashboard_market_label", market.label);
    setBind("dashboard_market_equity_target", range(market.equity_target_min_pct, market.equity_target_max_pct));
    setBind("dashboard_market_cash_target", range(market.cash_target_min_pct, market.cash_target_max_pct));
    setBind("dashboard_action_generated", action.generated_at);
    setBind("dashboard_action_count", action.action_count);
    setBind("dashboard_action_research_first", action.research_first_count);
    setBind("dashboard_action_manual", action.manual_confirmation_required_count);
    setBind("dashboard_equity_current", pct(allocation.equity_current_pct));
    setBind("dashboard_equity_target", range(allocation.equity_target_min_pct, allocation.equity_target_max_pct));
    setBind("dashboard_cash_current", pct(allocation.cash_short_current_pct));
    setBind("dashboard_cash_target", range(allocation.cash_short_target_min_pct, allocation.cash_short_target_max_pct));
    setBind("dashboard_subject_count", subjectStatus.subject_count);
    setBind("dashboard_subject_pass", subjectStatus.pass_count);
    setBind("dashboard_subject_research_first", subjectStatus.research_first_count);
    setBind("dashboard_subject_blocked", subjectStatus.blocked_count);
    setBind("dashboard_cash_gate", cashGate.research_first_status || cashGate.gate_conclusion);
    setBind("dashboard_gap_green", subjectGap.green_count);
    setBind("dashboard_gap_yellow", subjectGap.yellow_count);
    setBind("dashboard_gap_red", subjectGap.red_count);
    setBind("dashboard_gap_unknown", subjectGap.unknown_count);
    setBind("dashboard_gap_stale", subjectGap.stale_count);
    setStatusCard("system", system.status === "ok" ? "ok" : "fail");
    setStatusCard("research-first", system.research_first_gate_status === "ok" ? "ok" : "fail");
    setStatusCard("intraday", system.intraday_stale_flag || system.intraday_degraded_flag ? "warn" : "ok");
    renderGapChart(allocation.bucket_gaps || []);
    renderDashboardQuickLinks(data.quick_links || []);
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
    renderSubjectGapChart(rows);
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

  function renderSubjectGapChart(rows) {
    const chart = document.getElementById("subjectGapChart");
    const tooltip = document.getElementById("subjectGapTooltip");
    if (!chart) return;
    chart.replaceChildren();
    const buckets = new Map();
    (rows || []).forEach((row) => {
      if (!row.bucket || buckets.has(row.bucket)) return;
      buckets.set(row.bucket, row);
    });
    Array.from(buckets.values()).forEach((row) => {
      const actual = Math.max(0, Math.min(100, Number(row.actual_pct) || 0));
      const target = Math.max(0, Math.min(100, Number(row.target_pct) || 0));
      const status = ["green", "yellow", "red"].includes(row.gap_status) ? row.gap_status : "unknown";
      const wrapper = document.createElement("div");
      wrapper.className = "subject-gap-chart-row";
      wrapper.dataset.gapStatus = status;
      wrapper.dataset.tooltip = `bucket: ${row.bucket || ""} | actual: ${pct(row.actual_pct)} | target: ${pct(row.target_pct)} | gap: ${pp(row.gap_pct)} | stale: ${yesNo(row.staleness_flag)} | last update: ${row.last_update_timestamp || ""}`;

      const label = document.createElement("div");
      label.textContent = row.bucket || "";
      const track = document.createElement("div");
      track.className = "subject-gap-track";
      track.tabIndex = 0;
      track.title = wrapper.dataset.tooltip;
      const actualBar = document.createElement("div");
      actualBar.className = `subject-gap-actual ${status}`;
      actualBar.style.width = `${actual}%`;
      const targetMarker = document.createElement("div");
      targetMarker.className = "subject-gap-target";
      targetMarker.style.left = `${target}%`;
      const gap = document.createElement("div");
      gap.className = "num";
      gap.textContent = pp(row.gap_pct);
      track.append(actualBar, targetMarker);
      wrapper.append(label, track, gap);
      const showTooltip = () => {
        if (tooltip) tooltip.textContent = wrapper.dataset.tooltip || "";
      };
      track.addEventListener("mouseenter", showTooltip);
      track.addEventListener("focus", showTooltip);
      chart.appendChild(wrapper);
    });
  }

  function renderHistoryGapDashboard(data) {
    const rows = data.buckets || [];
    const summary = data.summary || {};
    setBind("history_gap_bucket_count", summary.bucket_count ?? rows.length);
    setBind("history_gap_green_count", summary.green_count ?? 0);
    setBind("history_gap_yellow_count", summary.yellow_count ?? 0);
    setBind("history_gap_red_count", summary.red_count ?? 0);
    setBind("history_gap_alert_count", summary.alert_count ?? 0);
    setBind("history_gap_source_count", summary.history_source_count ?? 0);
    renderHistoryGapChart(rows);
    setRows(
      "historyGapRows",
      rows,
      (row) => [
        row.bucket,
        { value: pct(row.actual_pct), className: "num" },
        { value: pct(row.target_pct), className: "num" },
        { value: pp(row.gap_pct), className: "num" },
        row.gap_status,
        row.alert_status,
        row.last_update_timestamp,
        { value: row.history_point_count, className: "num" },
      ],
      (row) => {
        const points = (row.timeline || [])
          .map((item) => `${item.source_kind || ""}: ${pp(item.gap_pct)} ${item.status || ""}`.trim())
          .join(" | ");
        return `timeline: ${points || "none"} | source count: ${row.source_count ?? 0}`;
      },
    );
    setRows(
      "historyEntryRows",
      data.history_entries || [],
      (row) => [
        row.source_id,
        row.export_kind,
        row.generated_at,
        row.status,
        yesNo(row.matched),
        { value: row.diff_count, className: "num" },
        { value: row.replay_failed, className: "num" },
      ],
      (row) =>
        `format: ${row.source_format || ""} | unsupported fields: ${row.unsupported_field_count ?? 0} | official allowed: ${yesNo(row.official_allowed)}`,
    );
  }

  function renderHistoryGapChart(rows) {
    const chart = document.getElementById("historyGapChart");
    const tooltip = document.getElementById("historyGapTooltip");
    if (!chart) return;
    chart.replaceChildren();
    const maxGap = Math.max(1, ...((rows || []).map((row) => Math.abs(Number(row.gap_pct) || 0))));
    (rows || []).forEach((row) => {
      const gap = Number(row.gap_pct) || 0;
      const status = ["green", "yellow", "red"].includes(row.gap_status) ? row.gap_status : "unknown";
      const wrapper = document.createElement("div");
      wrapper.className = "history-gap-chart-row";
      wrapper.dataset.gapStatus = status;
      wrapper.dataset.tooltip = `bucket: ${row.bucket || ""} | actual: ${pct(row.actual_pct)} | target: ${pct(row.target_pct)} | gap: ${pp(row.gap_pct)} | alert: ${row.alert_status || ""} | last update: ${row.last_update_timestamp || ""}`;

      const label = document.createElement("div");
      label.textContent = row.bucket || "";
      const track = document.createElement("div");
      track.className = "history-gap-track";
      track.tabIndex = 0;
      track.title = wrapper.dataset.tooltip;
      const bar = document.createElement("div");
      bar.className = `history-gap-bar ${status}`;
      bar.style.width = `${Math.max(2, Math.min(100, (Math.abs(gap) / maxGap) * 100))}%`;
      const value = document.createElement("div");
      value.className = "num";
      value.textContent = pp(row.gap_pct);
      track.appendChild(bar);
      wrapper.append(label, track, value);
      const showTooltip = () => {
        if (tooltip) tooltip.textContent = wrapper.dataset.tooltip || "";
      };
      track.addEventListener("mouseenter", showTooltip);
      track.addEventListener("focus", showTooltip);
      chart.appendChild(wrapper);
    });
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

  function renderSubjectStatus(data) {
    const subjects = data.subjects || [];
    const summary = data.summary || {};
    setBind("subject_count", summary.subject_count ?? subjects.length);
    setBind("subject_pass_count", summary.pass_count ?? 0);
    setBind("subject_research_first_count", summary.research_first_count ?? 0);
    setBind("subject_blocked_count", summary.blocked_count ?? 0);
    setRows(
      "subjectsRows",
      subjects,
      (row) => [
        row.code,
        row.name,
        row.subject_type,
        row.bucket,
        row.profile_status,
        row.valuation_status,
        row.liquidity_status,
        row.research_first_status,
        row.gate_conclusion,
        row.blocking_reason,
      ],
      (row) => {
        const sources = Object.values(row.source_paths || {}).join(" | ");
        const missing = [
          row.missing_profile ? "profile" : "",
          row.missing_valuation ? "valuation" : "",
          row.missing_liquidity ? "liquidity" : "",
          row.missing_theme_binding ? "theme_binding" : "",
        ]
          .filter(Boolean)
          .join(", ");
        return `generated: ${row.generated_at || ""} | basis: ${row.basis_trade_date || ""} | missing: ${missing || "none"} | sources: ${sources || "none"}`;
      },
    );
  }

  function renderThemes(data) {
    const themes = data.themes || [];
    const summary = data.summary || {};
    setBind("theme_count", summary.theme_count ?? themes.length);
    setBind("theme_confirmed_count", summary.confirmed_count ?? 0);
    setBind("theme_watch_count", summary.watch_count ?? 0);
    setBind("theme_research_first_count", summary.research_first_count ?? 0);
    setBind("theme_stale_count", summary.stale_count ?? 0);
    setBind("theme_conflict_count", summary.conflict_count ?? 0);
    setRows(
      "themesRows",
      themes,
      (row) => [
        row.theme_name,
        row.strategic_rating,
        row.tactical_rating,
        row.stage,
        row.status,
        row.basis_trade_date,
        row.generated_at,
        { value: (row.associated_etfs || []).length, className: "num" },
        { value: (row.associated_stocks || []).length, className: "num" },
        { value: (row.leaders || []).length, className: "num" },
        { value: (row.conflicts || []).length, className: "num" },
      ],
      (row) => {
        const etfs = (row.associated_etfs || []).map((item) => `${item.code || ""} ${item.name || ""}`.trim()).join("; ");
        const stocks = (row.associated_stocks || []).map((item) => `${item.code || ""} ${item.name || ""}`.trim()).join("; ");
        const leaders = (row.leaders || []).map((item) => `${item.type || ""} ${item.code || ""} ${item.route || ""}`.trim()).join("; ");
        const conflicts = (row.conflicts || []).map((item) => `${item.type || ""}: ${item.detail || ""}`).join("; ");
        return `data quality: ${row.data_quality_status || ""} | ETFs: ${etfs || "none"} | stocks: ${stocks || "none"} | leaders: ${leaders || "none"} | conflicts: ${conflicts || "none"}`;
      },
    );
  }

  function renderBuckets(data) {
    const buckets = data.buckets || [];
    const summary = data.summary || {};
    setBind("bucket_count", summary.bucket_count ?? buckets.length);
    setBind("bucket_overweight_count", summary.overweight_count ?? 0);
    setBind("bucket_underweight_count", summary.underweight_count ?? 0);
    setBind("bucket_research_first_count", summary.research_first_count ?? 0);
    setBind("bucket_blocked_count", summary.blocked_count ?? 0);
    setRows(
      "bucketRows",
      buckets,
      (row) => [
        row.bucket,
        { value: pct(row.actual_pct), className: "num" },
        { value: pct(row.target_pct), className: "num" },
        { value: pp(row.gap_pct), className: "num" },
        row.gap_status,
        { value: row.subject_count, className: "num" },
        { value: row.pass_count, className: "num" },
        { value: row.research_first_count, className: "num" },
        { value: row.stale_count, className: "num" },
      ],
      (row) => {
        const notes = (row.risk_notes || []).join(" | ");
        return `risk notes: ${notes || "none"} | blocked: ${row.blocked_count ?? 0}`;
      },
    );
    const subjects = buckets.flatMap((bucket) => bucket.subjects || []);
    setRows(
      "bucketSubjectRows",
      subjects,
      (row) => [
        row.code,
        row.name,
        row.subject_type,
        row.bucket,
        { value: pct(row.position_pct), className: "num" },
        row.profile_status,
        row.valuation_status,
        row.liquidity_status,
        row.research_first_status,
        row.gate_conclusion,
        row.blocking_reason,
      ],
      (row) => {
        const sources = Object.values(row.source_paths || {}).join(" | ");
        return `stale: ${yesNo(row.staleness_flag)} | sources: ${sources || "none"} | blocking: ${row.blocking_reason || "none"}`;
      },
    );
  }

  function renderBucketDrilldown(data) {
    const buckets = data.buckets || [];
    const summary = data.summary || {};
    setBind("bucket_drilldown_count", summary.bucket_count ?? buckets.length);
    setBind("bucket_drilldown_subjects", summary.subject_count ?? 0);
    setBind("bucket_drilldown_green", summary.green_count ?? 0);
    setBind("bucket_drilldown_yellow", summary.yellow_count ?? 0);
    setBind("bucket_drilldown_red", summary.red_count ?? 0);
    setBind("bucket_drilldown_generated", data.generated_at);
    renderBucketDrilldownChart(buckets);
    setRows(
      "bucketDrilldownRows",
      buckets,
      (row) => [
        row.bucket,
        { value: pct(row.actual_pct), className: "num" },
        { value: pct(row.target_pct), className: "num" },
        { value: pp(row.gap_pct), className: "num" },
        row.gap_status,
        { value: row.subject_count, className: "num" },
        row.generated_at,
      ],
      (row) => {
        const counts = Object.entries(row.research_first_counts || {})
          .map(([key, value]) => `${key}: ${value}`)
          .join(", ");
        const subjects = (row.subjects || [])
          .slice(0, 6)
          .map((item) => `${item.code || ""} ${item.name || ""}`.trim())
          .join("; ");
        const links = Object.values(row.review_links || {}).join(" | ");
        return `basis: ${row.basis_trade_date || ""} | position total: ${pct(row.position_pct_total)} | gate counts: ${counts || "none"} | subjects: ${subjects || "none"} | links: ${links || "none"}`;
      },
    );
  }

  function renderBucketDrilldownChart(buckets) {
    const chart = document.getElementById("bucketDrilldownChart");
    const tooltip = document.getElementById("bucketDrilldownTooltip");
    if (!chart) return;
    chart.replaceChildren();
    (buckets || []).forEach((row) => {
      const actual = Math.max(0, Math.min(100, Number(row.actual_pct) || 0));
      const target = Math.max(0, Math.min(100, Number(row.target_pct) || 0));
      const status = ["green", "yellow", "red"].includes(row.gap_status) ? row.gap_status : "unknown";
      const wrapper = document.createElement("div");
      wrapper.className = "drilldown-chart-row";
      wrapper.dataset.tooltip = `bucket: ${row.bucket || ""} | actual: ${pct(row.actual_pct)} | target: ${pct(row.target_pct)} | gap: ${pp(row.gap_pct)} | subjects: ${row.subject_count || 0}`;
      const label = document.createElement("div");
      label.textContent = row.bucket || "";
      const track = document.createElement("div");
      track.className = "drilldown-track";
      track.tabIndex = 0;
      track.title = wrapper.dataset.tooltip;
      const actualBar = document.createElement("div");
      actualBar.className = `drilldown-actual ${status}`;
      actualBar.style.width = `${actual}%`;
      const targetMarker = document.createElement("div");
      targetMarker.className = "drilldown-target";
      targetMarker.style.left = `${target}%`;
      const gap = document.createElement("div");
      gap.className = "num";
      gap.textContent = pp(row.gap_pct);
      track.append(actualBar, targetMarker);
      wrapper.append(label, track, gap);
      const showTooltip = () => {
        if (tooltip) tooltip.textContent = wrapper.dataset.tooltip || "";
      };
      track.addEventListener("mouseenter", showTooltip);
      track.addEventListener("focus", showTooltip);
      chart.appendChild(wrapper);
    });
  }

  function renderSubjectDrilldown(data) {
    const subjects = data.subjects || [];
    const summary = data.summary || {};
    setBind("subject_drilldown_count", summary.subject_count ?? subjects.length);
    setBind("subject_drilldown_pass", summary.pass_count ?? 0);
    setBind("subject_drilldown_research_first", summary.research_first_count ?? 0);
    setBind("subject_drilldown_blocked", summary.blocked_count ?? 0);
    setBind("subject_drilldown_stale", summary.stale_count ?? 0);
    setBind("subject_drilldown_generated", data.generated_at);
    setRows(
      "subjectDrilldownRows",
      subjects,
      (row) => [
        row.code,
        row.name,
        row.bucket,
        { value: pct(row.position_pct), className: "num" },
        { value: pct(row.bucket_actual_pct), className: "num" },
        { value: pct(row.bucket_target_pct), className: "num" },
        { value: pp(row.bucket_gap_pct), className: "num" },
        row.research_first_status,
        row.gate_conclusion,
        { value: row.theme_count, className: "num" },
      ],
      (row) => {
        const themes = (row.themes || [])
          .map((item) => `${item.theme_name || ""} ${item.status || ""} ${item.tactical_rating || ""}`.trim())
          .join("; ");
        const links = Object.values(row.review_links || {}).join(" | ");
        return `profile: ${row.profile_status || ""} | valuation: ${row.valuation_status || ""} | liquidity: ${row.liquidity_status || ""} | gap status: ${row.gap_status || ""} | stale: ${yesNo(row.staleness_flag)} | updated: ${row.last_update_timestamp || ""} | themes: ${themes || "none"} | reason: ${row.blocking_reason || "none"} | links: ${links || "none"}`;
      },
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

  function renderDecisionTimeline(data) {
    const events = data.events || [];
    const summary = data.summary || {};
    setBind("decision_timeline_count", summary.event_count ?? events.length);
    setBind("decision_timeline_decision_logs", summary.decision_log_count ?? 0);
    setBind("decision_timeline_history", summary.history_snapshot_count ?? 0);
    setBind("decision_timeline_action_plans", summary.action_plan_count ?? 0);
    setBind("decision_timeline_targets", summary.target_allocation_count ?? 0);
    setBind("decision_timeline_generated", data.generated_at);
    renderDecisionTimelineChart(events);
    setRows(
      "decisionTimelineRows",
      events,
      (row) => [
        row.timestamp,
        row.event_type,
        row.status,
        row.summary || row.title,
        Object.keys(row.review_links || {}).join(", "),
      ],
      (row) => {
        const details = Object.entries(row.details || {})
          .filter(([, value]) => value !== null && value !== undefined && typeof value !== "object")
          .map(([key, value]) => `${key}: ${value}`)
          .join(" | ");
        const links = Object.values(row.review_links || {}).join(" | ");
        return `title: ${row.title || ""} | basis: ${row.basis_trade_date || ""} | details: ${details || "none"} | links: ${links || "none"}`;
      },
    );
  }

  function renderDecisionTimelineChart(events) {
    const chart = document.getElementById("decisionTimelineChart");
    const tooltip = document.getElementById("decisionTimelineTooltip");
    if (!chart) return;
    chart.replaceChildren();
    (events || []).slice(0, 30).forEach((row) => {
      const wrapper = document.createElement("div");
      const eventType = String(row.event_type || "unknown").replace(/[^a-z0-9_-]/gi, "");
      wrapper.className = `timeline-chart-row ${eventType}`;
      wrapper.tabIndex = 0;
      wrapper.dataset.tooltip = `${row.timestamp || ""} | ${row.event_type || ""} | ${row.status || ""} | ${row.summary || row.title || ""}`;
      wrapper.title = wrapper.dataset.tooltip;
      const timestamp = document.createElement("div");
      timestamp.textContent = row.timestamp || "";
      const type = document.createElement("div");
      type.textContent = row.event_type || "";
      const summary = document.createElement("div");
      summary.textContent = row.summary || row.title || "";
      wrapper.append(timestamp, type, summary);
      const showTooltip = () => {
        if (tooltip) tooltip.textContent = wrapper.dataset.tooltip || "";
      };
      wrapper.addEventListener("mouseenter", showTooltip);
      wrapper.addEventListener("focus", showTooltip);
      chart.appendChild(wrapper);
    });
  }

  const renderers = {
    dashboard: renderDashboard,
    "action-plan": renderActionPlan,
    "target-allocation": renderTargetAllocation,
    "subjects-gap": renderSubjectGap,
    "history-gap-dashboard": renderHistoryGapDashboard,
    "research-first": renderResearchFirst,
    subjects: renderSubjectStatus,
    themes: renderThemes,
    buckets: renderBuckets,
    "buckets-drilldown": renderBucketDrilldown,
    "subjects-drilldown": renderSubjectDrilldown,
    portfolio: renderPortfolio,
    "intraday-rules": renderIntradayRules,
    "system-checks": renderSystemChecks,
    "decision-log": renderDecisionLog,
    "decision-timeline": renderDecisionTimeline,
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

  function setupFilters() {
    document.querySelectorAll("[data-table-filter]").forEach((input) => {
      input.addEventListener("change", () => {
        const id = input.dataset.tableFilter;
        const bodyId = id.replace("Table", "Rows");
        const state = tableState.get(bodyId) || tableState.get(id);
        if (!state) return;
        state.filters = state.filters || {};
        state.filters[input.dataset.filterKey] = input.value;
        state.page = 1;
        renderTable(bodyId);
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
    setupFilters();
    setupSort();
    refresh();
    window.setInterval(refresh, 60000);
  });
})();
