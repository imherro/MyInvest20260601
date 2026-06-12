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
  const DEFAULT_PAGE_SIZE = 100;
  const statusToneClassNames = [
    "status-cell",
    "status-inline",
    "status-tone-ok",
    "status-tone-warn",
    "status-tone-bad",
    "status-tone-info",
    "status-tone-neutral",
  ];
  const statusVariantClassNames = ["ok", "warn", "bad", "info", "neutral", "fail"];
  const exactStatusTones = new Map([
    ["ok", "ok"],
    ["pass", "ok"],
    ["passed", "ok"],
    ["green", "ok"],
    ["clean", "ok"],
    ["current", "ok"],
    ["matched", "ok"],
    ["logged", "ok"],
    ["confirmed", "ok"],
    ["completed", "ok"],
    ["available", "ok"],
    ["active", "ok"],
    ["ready", "ok"],
    ["healthy", "ok"],
    ["success", "ok"],
    ["present", "ok"],
    ["compatible", "ok"],
    ["allowed", "ok"],
    ["fresh", "ok"],
    ["near_target", "ok"],
    ["normal", "ok"],
    ["safe", "ok"],
    ["prompt copied", "ok"],
    ["通过", "ok"],
    ["正常", "ok"],
    ["确认", "ok"],
    ["已确认", "ok"],
    ["已完成", "ok"],
    ["可用", "ok"],
    ["合格", "ok"],
    ["watch", "warn"],
    ["watch-only", "warn"],
    ["warn", "warn"],
    ["warning", "warn"],
    ["yellow", "warn"],
    ["degraded", "warn"],
    ["review", "warn"],
    ["pending", "warn"],
    ["stale", "warn"],
    ["attention", "warn"],
    ["manual", "warn"],
    ["running", "warn"],
    ["paused", "warn"],
    ["pause_new", "warn"],
    ["reduce", "warn"],
    ["trim", "warn"],
    ["inactive", "warn"],
    ["prompt", "warn"],
    ["waiting", "warn"],
    ["unknown", "neutral"],
    ["n/a", "neutral"],
    ["neutral", "neutral"],
    ["hold", "neutral"],
    ["maintain", "neutral"],
    ["planned", "neutral"],
    ["check", "neutral"],
    ["germination", "info"],
    ["launch", "info"],
    ["confirmation", "info"],
    ["info", "info"],
    ["fail", "bad"],
    ["failed", "bad"],
    ["red", "bad"],
    ["blocked", "bad"],
    ["research_first", "bad"],
    ["researchfirst", "bad"],
    ["missing", "bad"],
    ["mismatch", "bad"],
    ["unavailable", "bad"],
    ["dirty", "bad"],
    ["error", "bad"],
    ["invalid", "bad"],
    ["forbidden", "bad"],
    ["conflict", "bad"],
    ["incompatible", "bad"],
    ["copy failed", "bad"],
    ["极弱", "bad"],
    ["风险收缩", "bad"],
  ]);
  const badStatusFragments = [
    "failed",
    "blocked",
    "research_first",
    "researchfirst",
    "missing",
    "mismatch",
    "unavailable",
    "dirty",
    "error",
    "invalid",
    "forbidden",
    "conflict",
    "incompatible",
    "replay_failed",
    "not_allowed",
    "risk_off",
    "risk contraction",
    "extreme weakness",
    "very weak",
    "critical",
    "decline",
    "极弱",
    "风险收缩",
    "高位拥挤",
    "拥挤",
    "泡沫",
  ];
  const warnStatusFragments = [
    "watch",
    "warn",
    "yellow",
    "degraded",
    "pending",
    "stale",
    "review",
    "attention",
    "manual",
    "running",
    "prompt",
    "alert",
    "overweight",
    "underweight",
    "above_target",
    "below_target",
    "off_target",
    "partial",
    "repair",
    "divergence",
    "cautious",
    "risk",
    "weak",
    "pause",
    "reduce",
    "偏弱",
    "弱势",
    "收缩",
    "偏贵",
    "修复",
    "观察",
    "预警",
  ];
  const okStatusFragments = ["safe", "healthy", "success", "allowed", "reasonable", "低估", "合理", "强势", "较强"];

  function text(value, fallback = "n/a") {
    if (value === null || value === undefined || value === "") return fallback;
    return String(value);
  }

  const hoverTitleMap = new Map([
    ["Research Dashboard", "研究总览"],
    ["Read-only current state from latest_index.modules.", "只读当前状态，来源为 latest_index.modules 当前索引。"],
    ["Read-only assistant suite from current modules and history facts.", "只读助手套件，来源为当前模块和历史事实。"],
    ["Read-only daily command center from current modules and history facts.", "只读每日指挥台，来源为当前模块和历史事实。"],
    ["Read-only history workspace from temp/history_db.", "只读历史工作区，来源为 temp/history_db。"],
    ["Read-only market history from temp/history_db.", "只读市场历史，来源为 temp/history_db。"],
    ["Read-only position history from temp/history_db.", "只读仓位历史，来源为 temp/history_db。"],
    ["Read-only action history from temp/history_db.", "只读操作历史，来源为 temp/history_db。"],
    ["Read-only security history from temp/history_db.", "只读标的历史，来源为 temp/history_db。"],
    ["Read-only valuation history from temp/history_db.", "只读估值历史，来源为 temp/history_db。"],
    ["History DB quality checks.", "历史库质量检查。"],
    ["History DB artifact and normalized coverage.", "历史库文件与标准化覆盖情况。"],
    ["Local whitelisted tools. Script buttons run only fixed repo commands.", "本地白名单工具，脚本按钮只运行固定仓库命令。"],
    ["Action Plan", "操作计划"],
    ["Target Allocation", "目标仓位"],
    ["ResearchFirst Gate", "ResearchFirst 闸门"],
    ["Subject Research Status / 标的研究状态中心", "标的研究状态中心"],
    ["Data Freshness & Gap Center", "数据新鲜度与缺口中心"],
    ["Theme Research Center", "主题研究中心"],
    ["Bucket Explorer", "仓位桶浏览"],
    ["Bucket Allocation Drilldown", "仓位桶配置下钻"],
    ["Subject Allocation Drilldown", "标的配置下钻"],
    ["Portfolio Ratio Snapshot", "组合比例快照"],
    ["Intraday Rules", "盘中规则"],
    ["Decision Log", "决策日志"],
    ["Decision Timeline", "决策时间线"],
    ["Historical Metrics", "历史指标"],
    ["Workbench Audit", "工作台审计"],
    ["Workbench Readiness", "工作台就绪状态"],
    ["Workbench Settings", "工作台设置"],
    ["Workbench Preferences", "工作台偏好"],
    ["History", "历史库"],
    ["History Coverage", "历史覆盖"],
    ["History Quality", "历史质量"],
    ["History Gap Dashboard", "历史缺口看板"],
    ["Tools", "工具"],
    ["Market History", "市场历史"],
    ["Action History", "操作历史"],
    ["Position History", "仓位历史"],
    ["Security History", "标的历史"],
    ["Valuation History", "估值历史"],
    ["System Checks", "系统检查"],
    ["Dashboard", "总览"],
    ["Manager", "基金经理"],
    ["Researcher", "研究员"],
    ["Trader", "操盘手"],
    ["System", "系统"],
    ["System Workbench", "系统工作台"],
    ["Tool Registry", "工具注册表"],
    ["Audit Export", "审计导出"],
    ["System Tools", "系统工具"],
    ["Refresh", "刷新当前页面数据"],
    ["Clear", "清空筛选"],
    ["Prev", "上一页"],
    ["Next", "下一页"],
    ["Download JSON", "下载 JSON 数据"],
    ["Export Review Package", "导出当前只读评审包"],
    ["History Tools", "打开历史库与审计工具"],
    ["Copy Prompt", "复制提示词"],
    ["Run", "运行固定白名单工具"],
    ["Run log", "运行日志"],
    ["Codex prompt", "Codex 提示词"],
    ["Click to expand details", "点击展开详情"],
    ["No additional details.", "没有更多详情。"],
    ["Market Position", "市场仓位"],
    ["Action Plan Summary", "操作计划摘要"],
    ["Allocation Summary", "配置摘要"],
    ["Bucket Gap", "仓位桶偏离"],
    ["Subject Research Status", "标的研究状态"],
    ["Subject Gap Summary", "标的缺口摘要"],
    ["Quick Links", "快捷入口"],
    ["System Status", "系统状态"],
    ["Mode", "模式"],
    ["Sections", "分区数量"],
    ["Modules", "模块数量"],
    ["Subjects", "标的数量"],
    ["Score", "分数"],
    ["Label", "标签"],
    ["Equity Target", "权益目标"],
    ["Cash Target", "现金目标"],
    ["Generated", "生成时间"],
    ["Actions", "动作数量"],
    ["ResearchFirst", "研究优先"],
    ["Manual Review", "人工复核"],
    ["Equity Current", "当前权益比例"],
    ["Cash Current", "当前现金比例"],
    ["Pass", "通过"],
    ["Blocked", "阻断"],
    ["511360 Gate", "511360 检查"],
    ["Current-only", "只使用当前索引指向的数据"],
    ["Ratio-only", "只展示比例和百分点，隐藏敏感字段"],
    ["Local read-only", "本地只读页面，不自动交易"],
    ["Current", "当前"],
    ["All", "全部"],
    ["Other", "其他"],
    ["Preview", "预览"],
    ["Bundle Sections", "审计包分区"],
    ["Section", "分区"],
    ["Status", "状态"],
    ["API", "接口"],
    ["Title", "标题"],
    ["Group", "分组"],
    ["Category", "类别"],
    ["When to Use", "使用时机"],
    ["Impact", "影响"],
    ["Description", "说明"],
    ["Command", "命令"],
  ]);

  const hoverSelector = [
    "h1",
    "h2",
    "h3",
    ".subtle",
    ".metric span",
    ".metric strong",
    ".summary-line span",
    ".summary-line strong",
    ".status",
    ".status-cell",
    ".status-inline",
    "th",
    "button",
    "a.button-link",
    "a.nav-trigger",
    "nav a",
    "label",
    "select",
    "input",
    ".refresh-status",
    ".footer-boundary span",
    ".tool-result-label",
    ".pagination span",
  ].join(",");

  function normalizeHoverText(value) {
    return text(value, "").replace(/\s+/g, " ").trim();
  }

  function hasChinese(value) {
    return /[\u3400-\u9fff]/.test(text(value, ""));
  }

  function hoverTitleFor(value) {
    const normalized = normalizeHoverText(value);
    if (!normalized) return "";
    if (hoverTitleMap.has(normalized)) return hoverTitleMap.get(normalized);
    if (/^updated\b/i.test(normalized)) return "最近刷新时间";
    if (/^refreshing/i.test(normalized)) return "正在刷新数据";
    if (/^Page \d+\/\d+ - \d+ rows$/i.test(normalized)) return "当前页码和总行数";
    return "";
  }

  function decorateChineseHover(root = document) {
    root.querySelectorAll(hoverSelector).forEach((node) => {
      const existingTitle = node.getAttribute("title") || "";
      if (hasChinese(existingTitle) && !node.matches(".refresh-status")) return;
      const candidate = normalizeHoverText(
        node.textContent || node.getAttribute("aria-label") || node.getAttribute("placeholder") || existingTitle,
      );
      const title = hoverTitleFor(candidate || existingTitle);
      if (title) node.setAttribute("title", title);
    });
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

  function isAllowedSafetyKey(path, key) {
    return false;
  }

  function assertRatioOnly(value, path = "$") {
    if (Array.isArray(value)) {
      value.forEach((item, index) => assertRatioOnly(item, `${path}[${index}]`));
      return;
    }
    if (value && typeof value === "object") {
      Object.entries(value).forEach(([key, item]) => {
        if (forbiddenKeyRe.test(String(key)) && !isAllowedSafetyKey(path, key)) {
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
      applyStatusTone(node, value, "status-inline");
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

  function normalizedStatusValue(value) {
    return text(value, "").trim().replace(/\s+/g, " ").toLowerCase();
  }

  function statusTone(value) {
    const normalized = normalizedStatusValue(value);
    if (!normalized || normalized.length > 64) return "";
    if (/^[+-]?\d+(\.\d+)?(%|pp)?$/.test(normalized)) return "";
    if (exactStatusTones.has(normalized)) return exactStatusTones.get(normalized);
    if (badStatusFragments.some((fragment) => normalized.includes(fragment))) return "bad";
    if (warnStatusFragments.some((fragment) => normalized.includes(fragment))) return "warn";
    if (okStatusFragments.some((fragment) => normalized.includes(fragment))) return "ok";
    return "";
  }

  function applyStatusTone(node, value, baseClass = "") {
    if (!node?.classList) return "";
    const tone = statusTone(value);
    node.classList.remove(...statusToneClassNames);
    if (node.classList.contains("status")) node.classList.remove(...statusVariantClassNames);
    if (!tone) return "";
    if (baseClass) node.classList.add(baseClass);
    node.classList.add(`status-tone-${tone}`);
    if (node.classList.contains("status")) node.classList.add(tone);
    return tone;
  }

  function pageSizeFor(table, rows, noPagination) {
    if (noPagination) return Math.max(1, (rows || []).length);
    return DEFAULT_PAGE_SIZE;
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
    const table = tbody.closest("table");
    const noPagination = table?.dataset.noPagination === "true";
    tableState.set(id, {
      rows: (rows || []).map((row, index) => ({
        key: `${id}-${index}`,
        row,
        cells: cells(row).map(cellObject),
        detail: detailFactory(row),
      })),
      page: 1,
      pageSize: pageSizeFor(table, rows, noPagination),
      noPagination,
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

  function removePagination(id) {
    document.querySelector(`[data-pagination-for="${id}"]`)?.remove();
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
    const visibleRows = state.noPagination ? rows : rows.slice(start, start + state.pageSize);
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
        applyStatusTone(td, cell.value, "status-cell");
        tr.appendChild(td);
      });
      tbody.appendChild(tr);
      if (state.expanded.has(item.key)) {
        const detailRow = document.createElement("tr");
        detailRow.className = "detail-row";
        const detailCell = document.createElement("td");
        detailCell.colSpan = Math.max(1, item.cells.length);
        if (item.detail && typeof item.detail === "object" && item.detail.nodeType) {
          detailCell.appendChild(item.detail.cloneNode(true));
        } else {
          detailCell.textContent = item.detail || "No additional details.";
        }
        detailRow.appendChild(detailCell);
        tbody.appendChild(detailRow);
      }
    });
    if (state.noPagination) {
      removePagination(id);
      decorateChineseHover(table || tbody);
      return;
    }
    renderPagination(table, id, rows.length, totalPages);
    decorateChineseHover(table || tbody);
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

  function decorateExistingStatusTone() {
    document.querySelectorAll("td").forEach((cell) => {
      applyStatusTone(cell, cell.textContent, "status-cell");
    });
    document.querySelectorAll(".status").forEach((node) => {
      applyStatusTone(node, node.textContent);
    });
    document.querySelectorAll("[data-bind]").forEach((node) => {
      if (!node.closest("td")) applyStatusTone(node, node.textContent, "status-inline");
    });
    document.querySelectorAll(".metric strong, .summary-line strong").forEach((node) => {
      if (!node.hasAttribute("data-bind")) applyStatusTone(node, node.textContent, "status-inline");
    });
  }

  window.MyInvestStatusTone = {
    apply: applyStatusTone,
    tone: statusTone,
  };

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

  function renderDashboardAnalytics(analytics) {
    const metrics = analytics.metrics || {};
    const gates = analytics.gates || {};
    const windowInfo = analytics.window || {};
    setBind("dashboard_analytics_modules", metrics.current_module_count ?? 0);
    setBind("dashboard_analytics_subjects", metrics.subject_count ?? 0);
    setBind("dashboard_analytics_actions", metrics.action_count ?? 0);
    setBind("dashboard_analytics_research_first", metrics.research_first_count ?? 0);
    setBind("dashboard_analytics_large_gaps", metrics.large_gap_count ?? 0);
    setBind("dashboard_analytics_history_entries", metrics.history_entry_count ?? 0);
    const selector = document.querySelector("[data-dashboard-window]");
    if (selector && windowInfo.selected) selector.value = windowInfo.selected;
    setRows(
      "dashboardAnalyticsRows",
      Object.entries(gates).map(([name, status]) => ({ name, status })),
      (row) => [row.name, row.status],
      (row) => `gate: ${row.name || ""} | status: ${row.status || ""}`,
    );
  }

  function renderWorkbenchIntegration(integration) {
    const modules = integration.modules || [];
    const links = document.getElementById("workbenchModuleLinks");
    if (links) {
      links.replaceChildren();
      modules.forEach((item) => {
        const link = document.createElement("a");
        link.className = "button-link";
        link.href = text(item.href, "#");
        link.textContent = text(item.label, "");
        links.appendChild(link);
      });
    }
    setRows(
      "workbenchIntegrationRows",
      modules,
      (row) => [row.label, row.status, row.api_path],
      (row) => `module: ${row.name || ""} | status: ${row.status || ""} | api: ${row.api_path || ""}`,
    );
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
    renderDashboardAnalytics(data.analytics_summary || {});
    renderWorkbenchIntegration(data.workbench_integration || {});
    renderDashboardQuickLinks(data.quick_links || []);
  }

  function renderActionPlan(data) {
    const plan = data.action_plan || {};
    setBind("plan_status", plan.status);
    setBind("plan_market", plan.market_state);
    setBind("plan_market_score", plan.market_score);
    setBind("plan_generated", plan.generated_at);
    setBind("plan_basis", plan.basis_trade_date);
    setBind("plan_market_basis", plan.market_basis_trade_date);
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
        themeCoverage(row),
      ],
      createThemeDetails,
    );
  }

  function themeCoverage(row) {
    return [
      `ETF ${(row.associated_etfs || []).length}`,
      `Stock ${(row.associated_stocks || []).length}`,
      `Routes ${(row.leaders || []).length}`,
      `Conflict ${(row.conflicts || []).length}`,
    ].join(" / ");
  }

  function createThemeDetails(row) {
    const panel = document.createElement("div");
    panel.className = "theme-detail-panel";
    const meta = document.createElement("div");
    meta.className = "theme-detail-meta";
    meta.textContent = `data quality: ${row.data_quality_status || "unknown"} | status: ${row.status || "unknown"} | stage: ${row.stage || "unknown"}`;
    panel.appendChild(meta);
    appendThemeDetailSection(panel, "ETFs", row.associated_etfs || [], themeSubjectLine);
    appendThemeDetailSection(panel, "Stocks", row.associated_stocks || [], themeSubjectLine);
    appendThemeDetailSection(panel, "Leaders / Routes", row.leaders || [], themeLeaderLine);
    appendThemeDetailSection(panel, "Conflicts", row.conflicts || [], themeConflictLine);
    return panel;
  }

  function appendThemeDetailSection(panel, title, items, formatter) {
    const section = document.createElement("div");
    section.className = "theme-detail-section";
    const heading = document.createElement("div");
    heading.className = "theme-detail-heading";
    heading.textContent = `${title} (${items.length})`;
    const list = document.createElement("div");
    list.className = "theme-detail-list";
    if (!items.length) {
      const empty = document.createElement("div");
      empty.className = "theme-detail-empty";
      empty.textContent = "none";
      list.appendChild(empty);
    } else {
      items.forEach((item) => {
        const itemRow = document.createElement("div");
        itemRow.className = "theme-detail-item";
        const content = formatter(item);
        if (content && typeof content === "object" && content.nodeType) itemRow.appendChild(content);
        else itemRow.textContent = content;
        list.appendChild(itemRow);
      });
    }
    section.append(heading, list);
    panel.appendChild(section);
  }

  function themeSubjectLine(item) {
    const identity = [item.code, item.name].filter(Boolean).join(" ");
    return themeDetailLine(identity || "unknown", [
      ["profile", themeGateLabel(item.profile_status)],
      ["valuation", themeGateLabel(item.valuation_status)],
      ["liquidity", themeGateLabel(item.liquidity_status)],
      ["action", themeActionLabel(item.gate_conclusion)],
    ]);
  }

  function themeGateLabel(value) {
    const status = String(value || "unknown").toLowerCase();
    if (["pass", "present", "ok", "completed"].includes(status)) return "ok";
    if (["missing", "unknown", "blocked", "research_first"].includes(status)) return status;
    return status || "unknown";
  }

  function themeActionLabel(value) {
    const status = String(value || "unknown").toLowerCase();
    if (status === "watch") return "watch-only";
    if (status === "research_first") return "ResearchFirst";
    return status || "unknown";
  }

  function themeLeaderLine(item) {
    const identity = [item.type, item.code, item.name].filter(Boolean).join(" ");
    return themeDetailLine(identity || "unknown", [["route", item.route || "unknown"]]);
  }

  function themeConflictLine(item) {
    return themeDetailLine(item.type || "conflict", [["detail", item.detail || "unknown"]]);
  }

  function themeDetailLine(identity, badges) {
    const wrapper = document.createElement("div");
    wrapper.className = "theme-detail-line";
    const identityNode = document.createElement("strong");
    identityNode.className = "theme-detail-identity";
    identityNode.textContent = identity;
    wrapper.appendChild(identityNode);
    (badges || []).forEach(([label, value]) => wrapper.appendChild(themeStateBadge(label, value)));
    return wrapper;
  }

  function themeStateBadge(label, value) {
    const badge = document.createElement("span");
    const status = String(value || "unknown");
    badge.className = `state-badge ${themeStateClass(status)}`;
    badge.textContent = `${label} ${status}`;
    return badge;
  }

  function themeStateClass(value) {
    const status = String(value || "unknown").toLowerCase();
    if (["ok", "pass", "present", "completed", "fresh", "allowed"].includes(status)) return "ok";
    if (status.includes("missing") || status.includes("unknown") || status.includes("blocked") || status.includes("not")) return "bad";
    if (status.includes("researchfirst") || status.includes("research_first")) return "bad";
    if (status.includes("watch")) return "warn";
    return "neutral";
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

  function renderEnvironment(data) {
    const git = data.git || {};
    const paths = data.paths || {};
    const web = data.web || {};
    const checks = data.checks || {};
    setBind("env_readonly", data.readonly ? "read-only" : "check");
    setBind("env_current_only", data.current_only ? "current-only" : "check");
    setBind("env_ratio_only", data.ratio_only ? "ratio-only" : "check");
    setBind("env_branch", git.branch || git.current_branch);
    setBind("env_commit", text(git.commit || git.current_commit).slice(0, 12));
    setBind("env_baseline", git.baseline_tag);
    setBind("env_is_worktree", yesNo(git.is_worktree));
    setBind("env_main_repo", git.main_repo_path);
    setBind("env_dirty_status", git.dirty_status || (git.dirty ? "dirty" : "clean"));
    setBind("env_project_root", paths.project_root);
    setBind("env_temp_dir", paths.temp_dir);
    setBind("env_web_db_path", paths.web_db_path);
    setBind("env_web_runtime_dir", paths.web_runtime_dir);
    setBind("env_web_exports_dir", paths.web_exports_dir);
    setBind("env_candidate_exports_dir", paths.candidate_exports_dir);
    setBind("env_history_exports_dir", paths.history_exports_dir);
    setBind("env_default_host", web.default_host);
    setBind("env_default_port", web.default_port);
    setBind("env_phase10_port", web.phase10_recommended_port);
    setBind("env_current_host", web.current_host);
    setBind("env_current_port", web.current_port);
    setBind("env_lan_mode", web.lan_mode_enabled ? "enabled" : "disabled");
    setStatusCard("env-readonly", data.readonly ? "ok" : "fail");
    setStatusCard("env-current-only", data.current_only ? "ok" : "fail");
    setStatusCard("env-ratio-only", data.ratio_only ? "ok" : "fail");
    setRows(
      "environmentCheckRows",
      Object.entries(checks).map(([name, status]) => ({ name, status })),
      (row) => [row.name, row.status],
      (row) => `check: ${row.name || ""} | status: ${row.status || ""}`,
    );
  }

  function renderUserPreferences(data) {
    const preferences = data.preferences || {};
    const profile = preferences.profile || {};
    const display = preferences.display || {};
    const dashboard = preferences.dashboard || {};
    const tables = preferences.tables || {};
    const safety = preferences.safety || {};
    const sources = preferences.sources || {};
    setBind("pref_readonly", safety.read_only ? "read-only" : "check");
    setBind("pref_ratio_only", safety.ratio_only ? "ratio-only" : "check");
    setBind("pref_current_only", safety.current_only ? "current-only" : "check");
    setBind("pref_user_id", preferences.user_id);
    setBind("pref_scope", preferences.scope);
    setBind("pref_label", profile.label);
    setBind("pref_role", profile.role);
    setBind("pref_editable", yesNo(profile.editable));
    setBind("pref_language", display.language);
    setBind("pref_theme", display.theme);
    setBind("pref_density", display.density);
    setBind("pref_number_format", display.number_format);
    setBind("pref_basis_date", display.show_basis_date ? "visible" : "hidden");
    setBind("pref_generated_at_visible", display.show_generated_at ? "visible" : "hidden");
    setBind("pref_landing", dashboard.landing_page);
    setBind("pref_refresh", dashboard.refresh_seconds);
    setBind("pref_show_research_first", dashboard.show_research_first ? "visible" : "hidden");
    setBind("pref_show_allocation_gap", dashboard.show_allocation_gap ? "visible" : "hidden");
    setBind("pref_show_history_gap", dashboard.show_history_gap ? "visible" : "hidden");
    setBind("pref_database_service", yesNo(safety.uses_database_service));
    setBind("pref_trading_disabled", safety.trading_disabled ? "disabled" : "check");
    setBind("pref_qmt_write", safety.qmt_write_disabled ? "disabled" : "check");
    setBind("pref_research_write", safety.research_write_disabled ? "disabled" : "check");
    setBind("pref_database_write", safety.database_write_disabled ? "disabled" : "check");
    setStatusCard("pref-readonly", safety.read_only ? "ok" : "fail");
    setStatusCard("pref-ratio-only", safety.ratio_only ? "ok" : "fail");
    setStatusCard("pref-current-only", safety.current_only ? "ok" : "fail");
    setRows(
      "preferenceRows",
      Object.entries(tables).map(([name, state]) => ({ name, state })),
      (row) => [row.name, row.state],
      (row) => `option: ${row.name || ""} | state: ${text(row.state, "")}`,
    );
    setRows(
      "preferenceSourceRows",
      Object.entries(sources).map(([name, value]) => ({ name, value })),
      (row) => [row.name, row.value],
      (row) => `field: ${row.name || ""} | value: ${text(row.value, "")}`,
    );
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

  function updateHistoricalMetricsSummary(summary, rows) {
    setBind("historical_entity_count", summary.entity_count ?? rows.length);
    setBind("historical_bucket_count", summary.bucket_count ?? 0);
    setBind("historical_subject_count", summary.subject_count ?? 0);
    setBind("historical_theme_count", summary.theme_count ?? 0);
    setBind("historical_red_gap_count", summary.red_gap_count ?? 0);
    setBind("historical_decision_event_count", summary.decision_event_count ?? 0);
  }

  function renderHistoricalMetrics(data) {
    const rows = data.entities || [];
    const summary = data.summary || {};
    updateHistoricalMetricsSummary(summary, rows);
    renderHistoricalMetricsChart((data.aggregations || {}).buckets || []);
    setRows(
      "historicalMetricRows",
      rows,
      (row) => [
        row.label || row.entity_id,
        row.entity_type,
        row.status,
        { value: pct(row.actual_pct), className: "num" },
        { value: pct(row.target_pct), className: "num" },
        { value: pp(row.gap_pct), className: "num" },
        row.trend_indicator,
        { value: row.point_count, className: "num" },
        row.latest_timestamp,
      ],
      (row) => {
        const links = Object.values(row.review_links || {}).join(" | ");
        return `id: ${row.entity_id || ""} | bucket: ${row.bucket || ""} | status: ${row.status || ""} | delta: ${pp(row.gap_delta_pp)} | links: ${links || "none"}`;
      },
    );
  }

  function renderHistoricalMetricsChart(buckets) {
    const chart = document.getElementById("historicalMetricsChart");
    const tooltip = document.getElementById("historicalMetricsTooltip");
    if (!chart) return;
    chart.replaceChildren();
    const maxGap = Math.max(1, ...((buckets || []).map((row) => Math.abs(Number(row.gap_pct) || 0))));
    (buckets || []).forEach((row) => {
      const status = ["green", "yellow", "red"].includes(row.status) ? row.status : "unknown";
      const wrapper = document.createElement("div");
      wrapper.className = "historical-chart-row";
      wrapper.dataset.tooltip = `bucket: ${row.bucket || row.label || ""} | actual: ${pct(row.actual_pct)} | target: ${pct(row.target_pct)} | gap: ${pp(row.gap_pct)} | trend: ${row.trend_indicator || ""} | source points: ${row.point_count || 0}`;
      const label = document.createElement("div");
      label.textContent = row.bucket || row.label || "";
      const track = document.createElement("div");
      track.className = "historical-track";
      track.tabIndex = 0;
      track.title = wrapper.dataset.tooltip;
      const bar = document.createElement("div");
      bar.className = `historical-bar ${status}`;
      bar.style.width = `${Math.max(2, Math.min(100, (Math.abs(Number(row.gap_pct) || 0) / maxGap) * 100))}%`;
      const gap = document.createElement("div");
      gap.className = "num";
      gap.textContent = pp(row.gap_pct);
      track.appendChild(bar);
      wrapper.append(label, track, gap);
      const showTooltip = () => {
        if (tooltip) tooltip.textContent = wrapper.dataset.tooltip || "";
      };
      track.addEventListener("mouseenter", showTooltip);
      track.addEventListener("focus", showTooltip);
      chart.appendChild(wrapper);
    });
  }

  const toolState = {
    tools: [],
    groups: [],
    query: "",
    group: "",
  };

  function statusText(value) {
    if (value === "passed") return "PASS";
    if (value === "failed") return "FAIL";
    if (value === "prompt") return "PROMPT";
    if (value === "running") return "RUNNING";
    return text(value, "waiting");
  }

  function renderTools(data) {
    const summary = data.summary || {};
    toolState.tools = data.tools || [];
    toolState.groups = data.groups || [];
    setBind("tool_count", summary.tool_count);
    renderToolCategoryFilter();
    const filter = document.querySelector("[data-tool-filter]");
    if (filter && filter.value && !toolState.group) {
      toolState.group = filter.value;
    }
    renderToolRows();
  }

  function renderDecisionAssistant(data) {
    const today = data.today || {};
    setBind("assistant_market_score", today.market_score ?? "n/a");
    setBind("assistant_system_status", today.system_status || "unknown");
  }

  function renderAssistantFeature(data) {
    if (!data) return;
  }

  function renderToolCategoryFilter() {
    const filter = document.querySelector("[data-tool-filter]");
    if (!filter || filter.dataset.loaded === "true") return;
    (toolState.groups || []).forEach((group) => {
      const option = document.createElement("option");
      option.value = group;
      option.textContent = group;
      filter.appendChild(option);
    });
    filter.dataset.loaded = "true";
  }

  function filteredTools() {
    const query = (toolState.query || "").trim().toLowerCase();
    return (toolState.tools || []).slice().sort((left, right) => {
      const leftGroup = (toolState.groups || []).indexOf(left.group);
      const rightGroup = (toolState.groups || []).indexOf(right.group);
      const groupDiff = (leftGroup < 0 ? 999 : leftGroup) - (rightGroup < 0 ? 999 : rightGroup);
      if (groupDiff !== 0) return groupDiff;
      return (Number(left.sequence) || 999) - (Number(right.sequence) || 999);
    }).filter((tool) => {
      if (toolState.group && tool.group !== toolState.group) return false;
      if (!query) return true;
      return [tool.title, tool.group, tool.category, tool.when_to_use, tool.impact, tool.description, tool.command_display]
        .map((item) => text(item, "").toLowerCase())
        .join(" ")
        .includes(query);
    });
  }

  function renderToolRows() {
    const tbody = document.getElementById("toolRows");
    if (!tbody) return;
    tbody.replaceChildren();
    let currentGroup = "";
    filteredTools().forEach((tool) => {
      if (tool.group !== currentGroup) {
        currentGroup = tool.group || "";
        const groupRow = document.createElement("tr");
        groupRow.className = "tool-group-row";
        const groupCell = document.createElement("td");
        groupCell.colSpan = 8;
        groupCell.textContent = currentGroup || "Other";
        groupRow.appendChild(groupCell);
        tbody.appendChild(groupRow);
      }
      const tr = document.createElement("tr");
      tr.dataset.toolRow = tool.id || "";
      const title = document.createElement("td");
      title.textContent = tool.title || tool.id;
      const group = document.createElement("td");
      group.textContent = tool.group || "";
      const category = document.createElement("td");
      category.textContent = tool.category || "";
      const whenToUse = document.createElement("td");
      whenToUse.textContent = tool.when_to_use || "";
      const impact = document.createElement("td");
      impact.className = "tool-impact";
      impact.textContent = tool.impact || "";
      const description = document.createElement("td");
      description.textContent = tool.description || "";
      const command = document.createElement("td");
      command.textContent = tool.command_display || (tool.kind === "prompt" ? "Codex prompt" : "");
      const action = document.createElement("td");
      action.className = "tool-actions";
      const button = document.createElement("button");
      button.type = "button";
      button.textContent = tool.kind === "prompt" ? "Copy Prompt" : "Run";
      button.addEventListener("click", () => {
        if (tool.kind === "prompt") copyToolPrompt(tool, button);
        else runTool(tool, button);
      });
      action.appendChild(button);
      tr.append(title, group, category, whenToUse, impact, description, command, action);
      tbody.appendChild(tr);
      const resultRow = document.createElement("tr");
      resultRow.className = "tool-result-row";
      resultRow.dataset.toolOutputRow = tool.id || "";
      resultRow.hidden = true;
      const resultCell = document.createElement("td");
      resultCell.colSpan = 8;
      const resultLabel = document.createElement("div");
      resultLabel.className = "tool-result-label";
      resultLabel.textContent = "Run log";
      const resultOutput = document.createElement("pre");
      resultOutput.className = "tool-output tool-output-inline";
      resultCell.append(resultLabel, resultOutput);
      resultRow.appendChild(resultCell);
      tbody.appendChild(resultRow);
    });
    decorateChineseHover(tbody.closest("table") || tbody);
  }

  async function copyToolPrompt(tool, button) {
    const prompt = tool.prompt || "";
    try {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(prompt);
      } else {
        const area = document.createElement("textarea");
        area.value = prompt;
        document.body.appendChild(area);
        area.select();
        document.execCommand("copy");
        area.remove();
      }
      setBind("tool_selected", tool.title || tool.id);
      setBind("tool_status", "PROMPT COPIED");
      setBind("tool_last_run", new Date().toLocaleTimeString());
      showToolOutput(prompt, button);
    } catch (error) {
      setBind("tool_selected", tool.title || tool.id);
      setBind("tool_status", "COPY FAILED");
      showToolOutput(error.message || "Copy failed", button);
    }
  }

  async function runTool(tool, button) {
    setBind("tool_selected", tool.title || tool.id);
    setBind("tool_status", "RUNNING");
    setBind("tool_last_run", new Date().toLocaleTimeString());
    showToolOutput(`Running ${tool.title || tool.id}...`, button);
    button.disabled = true;
    try {
      const response = await fetch(`/ops/run/${encodeURIComponent(tool.id)}`, {
        method: "POST",
        cache: "no-store",
      });
      const payload = await response.json();
      assertRatioOnly(payload);
      if (!response.ok || payload.ok === false) {
        throw new Error(payload.detail || "Tool run failed");
      }
      const result = payload.data || {};
      setBind("tool_status", statusText(result.status));
      setBind("tool_last_run", new Date().toLocaleTimeString());
      showToolOutput(formatToolResult(result), button);
    } catch (error) {
      setBind("tool_status", "FAIL");
      showToolOutput(error.message || "Tool run failed", button);
    } finally {
      button.disabled = false;
    }
  }

  function formatToolResult(result) {
    const lines = [];
    lines.push(`status: ${statusText(result.status)}`);
    if (result.message) lines.push(`message: ${result.message}`);
    (result.steps || []).forEach((step) => {
      lines.push("");
      lines.push(`[${statusText(step.status)}] ${step.name || "step"} (${step.duration_seconds || 0}s)`);
      lines.push(`exit: ${step.exit_code === null || step.exit_code === undefined ? "n/a" : step.exit_code}`);
      if (step.stdout) {
        lines.push("stdout:");
        lines.push(step.stdout);
      }
      if (step.stderr) {
        lines.push("stderr:");
        lines.push(step.stderr);
      }
    });
    if (result.prompt) {
      lines.push("");
      lines.push(result.prompt);
    }
    return lines.join("\n");
  }

  function showToolOutput(value, button) {
    const row = button?.closest("tr");
    const outputRow = row?.nextElementSibling?.classList?.contains("tool-result-row")
      ? row.nextElementSibling
      : null;
    const output = outputRow?.querySelector(".tool-output") || document.getElementById("toolOutput");
    if (!output) return;
    if (outputRow) outputRow.hidden = false;
    else output.hidden = false;
    output.textContent = value || "";
    if (outputRow) outputRow.scrollIntoView({ block: "nearest", behavior: "smooth" });
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
    environment: renderEnvironment,
    preferences: renderUserPreferences,
    "decision-log": renderDecisionLog,
    "decision-timeline": renderDecisionTimeline,
    "historical-metrics": renderHistoricalMetrics,
    assistant: renderDecisionAssistant,
    "assistant-risk-center": renderAssistantFeature,
    "assistant-research-tasks": renderAssistantFeature,
    "assistant-preferences": renderAssistantFeature,
    "assistant-scenarios": renderAssistantFeature,
    "assistant-history-visuals": renderAssistantFeature,
    "assistant-review-score": renderAssistantFeature,
    "assistant-premarket": renderAssistantFeature,
    "assistant-search": renderAssistantFeature,
    "assistant-security-center": renderAssistantFeature,
    "assistant-weekly-safety": renderAssistantFeature,
    tools: renderTools,
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
      const data = Object.prototype.hasOwnProperty.call(payload, "data") ? payload.data : payload;
      renderers[page](data);
      decorateExistingStatusTone();
      decorateChineseHover();
      updateRefreshStatus(`updated ${new Date().toLocaleTimeString()}`);
    } catch (error) {
      updateRefreshStatus(error.message || "refresh failed", false);
    }
  }

  function updateRefreshStatus(message, ok = true) {
    if (!statusEl) return;
    statusEl.textContent = message;
    statusEl.className = ok ? "refresh-status" : "refresh-status warn";
    statusEl.title = hoverTitleFor(message) || (ok ? "刷新状态" : "刷新失败");
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

  function setupToolFilters() {
    document.querySelector("[data-tool-search]")?.addEventListener("input", (event) => {
      toolState.query = event.target.value || "";
      renderToolRows();
    });
    document.querySelector("[data-tool-filter]")?.addEventListener("change", (event) => {
      toolState.group = event.target.value || "";
      const url = new URL(window.location.href);
      if (toolState.group) url.searchParams.set("group", toolState.group);
      else url.searchParams.delete("group");
      window.history.replaceState({}, "", url);
      renderToolRows();
    });
  }

  function setupDashboardWindow() {
    const selector = document.querySelector("[data-dashboard-window]");
    if (!selector) return;
    selector.addEventListener("change", async () => {
      try {
        updateRefreshStatus("refreshing analytics...");
        const response = await fetch(`/api/dashboard/summary?time_window=${encodeURIComponent(selector.value)}`, {
          cache: "no-store",
        });
        const payload = await response.json();
        assertRatioOnly(payload);
        if (!response.ok || payload.ok === false) {
          throw new Error(payload.detail || "Analytics refresh failed");
        }
        renderDashboardAnalytics(payload.data || {});
        decorateChineseHover();
        updateRefreshStatus(`updated ${new Date().toLocaleTimeString()}`);
      } catch (error) {
        updateRefreshStatus(error.message || "analytics refresh failed", false);
      }
    });
  }

  document.addEventListener("DOMContentLoaded", () => {
    document.querySelector("[data-refresh]")?.addEventListener("click", refresh);
    setupSearch();
    setupFilters();
    setupSort();
    setupDashboardWindow();
    setupToolFilters();
    decorateExistingStatusTone();
    decorateChineseHover();
    refresh();
    window.setInterval(refresh, 60000);
  });
})();
