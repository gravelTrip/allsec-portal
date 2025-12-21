document.addEventListener("DOMContentLoaded", () => {
  // =========================
  // Filters (Dashboard + Workorder list)
  // =========================
  function setupFilterForm({
    formId,
    storageKey,
    appliedOnceKey,
    keys,
    defaults,
    timeSelectId,
    resetBtnId,
  }) {
    const form = document.getElementById(formId);
    if (!form) return;

    const timeSelect =
      document.getElementById(timeSelectId) || form.querySelector("select[name='time']");
    const fromInput = form.querySelector("input[name='date_from']");
    const toInput = form.querySelector("input[name='date_to']");
    const resetBtn = document.getElementById(resetBtnId);

    function updateDateRangeVisibility() {
      if (!timeSelect || !fromInput || !toInput) return;

      const isRange = timeSelect.value === "range";
      const fromCol = fromInput.closest(".col-6");
      const toCol = toInput.closest(".col-6");

      if (fromCol) fromCol.style.display = isRange ? "" : "none";
      if (toCol) toCol.style.display = isRange ? "" : "none";

      fromInput.disabled = !isRange;
      toInput.disabled = !isRange;

      if (!isRange) {
        fromInput.value = "";
        toInput.value = "";
      }
    }

    function saveFilters() {
      const data = {};
      keys.forEach((k) => {
        const el = form.querySelector(`[name="${k}"]`);
        if (!el) return;

        if (el.type === "checkbox") {
          data[k] = el.checked ? "1" : "";
        } else {
          data[k] = el.value;
        }
      });

      localStorage.setItem(storageKey, JSON.stringify(data));
    }

    // 1) Jeśli URL nie ma filtrów, a w localStorage są => zastosuj raz i przeładuj
    const urlParams = new URLSearchParams(window.location.search);
    const hasAnyFilterInUrl = keys.some((k) => {
      const v = urlParams.get(k);
      return v !== null && v !== "";
    });

    if (!hasAnyFilterInUrl && !sessionStorage.getItem(appliedOnceKey)) {
      try {
        const saved = JSON.parse(localStorage.getItem(storageKey) || "{}");
        let shouldSubmit = false;

        keys.forEach((k) => {
          const el = form.querySelector(`[name="${k}"]`);
          if (!el) return;

          const savedVal = saved[k];
          if (savedVal === undefined) return;

          if (el.type === "checkbox") {
            const desired = savedVal === "1";
            if (el.checked !== desired) {
              el.checked = desired;
              shouldSubmit = true;
            }
          } else {
            if (savedVal !== "" && el.value !== savedVal) {
              el.value = savedVal;
              shouldSubmit = true;
            }
          }
        });

        updateDateRangeVisibility();

        if (shouldSubmit) {
          sessionStorage.setItem(appliedOnceKey, "1");
          form.submit();
          return;
        }
      } catch (_) {
        // ignore
      }
    } else {
      sessionStorage.removeItem(appliedOnceKey);
    }

    // 2) Auto-submit na zmianę + zapis do localStorage
    const autoSubmitInputs = form.querySelectorAll("select, input[type='checkbox']");
    autoSubmitInputs.forEach((el) => {
      el.addEventListener("change", () => {
        updateDateRangeVisibility();
        saveFilters();
        form.submit();
      });
    });

    // date inputs: zapis (submit leci przez zmianę time=range lub ręczne przeładowanie)
    if (fromInput) fromInput.addEventListener("change", saveFilters);
    if (toInput) toInput.addEventListener("change", saveFilters);

    // 3) Reset
    if (resetBtn) {
      resetBtn.addEventListener("click", () => {
        keys.forEach((k) => {
          const el = form.querySelector(`[name="${k}"]`);
          if (!el) return;

          const defVal = defaults[k];

          if (el.type === "checkbox") {
            el.checked = defVal === "1";
          } else if (defVal !== undefined) {
            el.value = defVal;
          } else {
            el.value = "";
          }
        });

        updateDateRangeVisibility();
        saveFilters();
        form.submit();
      });
    }

    updateDateRangeVisibility();
    form.addEventListener("submit", saveFilters);
  }

  // Dashboard filters
  setupFilterForm({
    formId: "dashboard-orders-filters",
    storageKey: "dashboardOrdersFilters",
    appliedOnceKey: "dashboardFiltersApplied",
    keys: ["type", "assignee", "status", "time", "date_from", "date_to", "hide_completed"],
    defaults: {
      type: "",
      assignee: "",
      status: "",
      time: "week",
      date_from: "",
      date_to: "",
      hide_completed: "1",
    },
    timeSelectId: "dashboard-filter-time",
    resetBtnId: "dashboard-filters-reset",
  });

  // Workorder list filters
  setupFilterForm({
    formId: "workorder-list-filters",
    storageKey: "workorderListFilters",
    appliedOnceKey: "workorderListFiltersApplied",
    keys: ["site", "assignee", "status", "time", "date_from", "date_to", "hide_completed"],
    defaults: {
      site: "",
      assignee: "",
      status: "",
      time: "all",
      date_from: "",
      date_to: "",
      hide_completed: "1",
    },
    timeSelectId: "workorder-list-filter-time",
    resetBtnId: "workorder-list-filters-reset",
  });

  // =========================
  // Dashboard: Sortable + order persistence
  // =========================
  const isDashboard = () => !!document.getElementById("dashboard-root");

  function applySavedOrder(container, key, selector) {
    try {
      const raw = localStorage.getItem(key);
      if (!raw) return;
      const ids = JSON.parse(raw);
      if (!Array.isArray(ids) || !ids.length) return;

      const map = new Map();
      Array.from(container.querySelectorAll(selector)).forEach((el) => {
        const id = el.dataset.id;
        if (id) map.set(String(id), el);
      });

      ids.forEach((id) => {
        const el = map.get(String(id));
        if (el) container.appendChild(el);
      });
    } catch (_) {}
  }

  function saveOrder(container, key, selector) {
    try {
      const ids = Array.from(container.querySelectorAll(selector))
        .map((el) => el.dataset.id)
        .filter(Boolean);
      localStorage.setItem(key, JSON.stringify(ids));
    } catch (_) {}
  }

  let ordersSortable = null;
  let maintenanceSortable = null;

  function initDashboardSortables() {
    if (!isDashboard()) return;
    if (typeof window.Sortable === "undefined") return;

    const root = document.getElementById("dashboard-root");
    const userId = (root && root.dataset.userId) ? root.dataset.userId : "0";

    // Zlecenia (tabela)
    const ordersBody = document.getElementById("dashboard-orders-body");
    if (ordersBody) {
      const key = `dashboard:ordersOrder:${userId}`;
      const draggableSel = "tr[data-id]";

      // destroy previous instance
      if (ordersSortable) {
        ordersSortable.destroy();
        ordersSortable = null;
      }

      applySavedOrder(ordersBody, key, draggableSel);

      ordersSortable = new Sortable(ordersBody, {
        animation: 150,
        draggable: draggableSel,
        handle: ".drag-handle",
        filter: "a,button,form,input,select,textarea,label",
        preventOnFilter: false,
        onEnd: () => saveOrder(ordersBody, key, draggableSel),
      });
    }

    // Konserwacje (lista po prawej)
    const maintenanceList = document.getElementById("dashboard-maintenance-list");
    if (maintenanceList) {
      const maintCard = document.getElementById("dashboard-maintenance-card");
      let suffix = "";

      if (maintCard) {
        const y = maintCard.dataset.year || "";
        const m = maintCard.dataset.month || "";
        if (y && m) suffix = `:${y}-${m}`;
      }

      const key = `dashboard:maintenanceOrder:${userId}${suffix}`;
      const draggableSel = "li[data-id]";

      // destroy previous instance
      if (maintenanceSortable) {
        maintenanceSortable.destroy();
        maintenanceSortable = null;
      }

      applySavedOrder(maintenanceList, key, draggableSel);

      maintenanceSortable = new Sortable(maintenanceList, {
        animation: 150,
        draggable: draggableSel,
        handle: ".drag-handle",
        filter: "a,button,form,input,select,textarea,label",
        preventOnFilter: false,
        onEnd: () => saveOrder(maintenanceList, key, draggableSel),
      });
    }
  }

  initDashboardSortables();

  // =========================
  // Dashboard: soft refresh KPI + tabela zleceń po nowym powiadomieniu
  // =========================
  let dashRefreshTimer = null;
  let lastDashRefreshAt = 0;

  async function refreshDashboardOrdersAndKpi() {
    if (!isDashboard()) return;
    if (document.hidden) return;

    // throttle (max co 2 sekundy)
    const now = Date.now();
    if (now - lastDashRefreshAt < 2000) return;
    lastDashRefreshAt = now;

    const ordersBody = document.getElementById("dashboard-orders-body");
    const kpi = document.getElementById("dashboard-kpi"); // jeśli nie ma ID, to po prostu nie odświeży KPI
    if (!ordersBody && !kpi) return;

    try {
      const resp = await fetch(window.location.href, {
        headers: { "X-Requested-With": "XMLHttpRequest" },
        credentials: "same-origin",
        cache: "no-store",
      });
      if (!resp.ok) return;

      const html = await resp.text();
      const doc = new DOMParser().parseFromString(html, "text/html");

      const newOrdersBody = doc.getElementById("dashboard-orders-body");
      if (ordersBody && newOrdersBody) {
        ordersBody.innerHTML = newOrdersBody.innerHTML;
      }

      const newKpi = doc.getElementById("dashboard-kpi");
      if (kpi && newKpi) {
        kpi.innerHTML = newKpi.innerHTML;
      }

      // po podmianie DOM -> re-init sortable (i re-apply kolejności z localStorage)
      initDashboardSortables();
    } catch (_) {}
  }

  // Event jest emitowany w base.html, gdy unread_count wzrasta
  document.addEventListener("woNotif:new", () => {
    if (!isDashboard()) return;
    clearTimeout(dashRefreshTimer);
    dashRefreshTimer = setTimeout(refreshDashboardOrdersAndKpi, 400);
  });
});
