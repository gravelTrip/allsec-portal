document.addEventListener("DOMContentLoaded", () => {
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

    const timeSelect = document.getElementById(timeSelectId) || form.querySelector("select[name='time']");
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
      } catch (e) {
        // ignore
      }
    } else {
      // po przeładowaniu usuń flagę
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

    // na start
    updateDateRangeVisibility();

    // zapis również przy submit (fallback)
    form.addEventListener("submit", saveFilters);
  }

  // Dashboard
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

  // Workorder list
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
});
