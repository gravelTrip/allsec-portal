document.addEventListener("DOMContentLoaded", function () {
  const root = document.getElementById("dashboard-root");
  if (!root) {
    return;
  }

  const userId = root.dataset.userId || "anon";

  // --- Helpery localStorage dla kolejek drag&drop ---

  function saveOrder(container, storageKey, itemSelector) {
    if (!container) return;
    const items = Array.from(container.querySelectorAll(itemSelector));
    const ids = items
      .map((el) => el.dataset.id)
      .filter((id) => typeof id !== "undefined" && id !== null && id !== "");
    try {
      window.localStorage.setItem(storageKey, JSON.stringify(ids));
    } catch (e) {
      // brak localStorage / tryb prywatny – ignorujemy
    }
  }

  function applyOrder(container, storageKey, itemSelector) {
    if (!container) return;
    let stored = null;
    try {
      stored = window.localStorage.getItem(storageKey);
    } catch (e) {
      stored = null;
    }
    if (!stored) return;

    let ids;
    try {
      ids = JSON.parse(stored);
    } catch (e) {
      return;
    }
    if (!Array.isArray(ids)) return;

    const items = Array.from(container.querySelectorAll(itemSelector));
    const lookup = new Map();
    items.forEach((el) => {
      const id = el.dataset.id;
      if (id) {
        lookup.set(id, el);
      }
    });

    ids.forEach((id) => {
      const el = lookup.get(id);
      if (el) {
        container.appendChild(el);
      }
    });
  }

  // --- ZLECENIA: drag&drop + pamięć ---

  const ordersBody = document.getElementById("dashboard-orders-body");
  if (ordersBody) {
    const ordersStorageKey = `allsec_dashboard_orders_${userId}`;

    applyOrder(ordersBody, ordersStorageKey, "tr[data-id]");

    if (window.Sortable && typeof window.Sortable.create === "function") {
      window.Sortable.create(ordersBody, {
        animation: 150,
        onEnd: function () {
          saveOrder(ordersBody, ordersStorageKey, "tr[data-id]");
        },
      });
    }
  }

  // --- KONSERWACJE: drag&drop + pamięć per miesiąc ---

  const maintenanceCard = document.getElementById("dashboard-maintenance-card");
  const maintenanceList = document.getElementById("dashboard-maintenance-list");

  if (maintenanceCard && maintenanceList) {
    const year = maintenanceCard.dataset.year || "0000";
    const month = maintenanceCard.dataset.month || "00";
    const maintStorageKey = `allsec_dashboard_maintenance_${userId}_${year}_${month}`;

    applyOrder(maintenanceList, maintStorageKey, "li[data-id]");

    if (window.Sortable && typeof window.Sortable.create === "function") {
      window.Sortable.create(maintenanceList, {
        animation: 150,
        onEnd: function () {
          saveOrder(maintenanceList, maintStorageKey, "li[data-id]");
        },
      });
    }
  }

  // --- Pokazywanie pól dat dla time == 'range' ---

  const timeSelect = document.getElementById("dashboard-filter-time");
  const dateFromInput = document.querySelector("input[name='date_from']");
  const dateToInput = document.querySelector("input[name='date_to']");

  function updateDateRangeVisibility() {
    if (!timeSelect || !dateFromInput || !dateToInput) return;
    const show = timeSelect.value === "range";
    const fromGroup = dateFromInput.closest(".col-6");
    const toGroup = dateToInput.closest(".col-6");
    if (fromGroup) fromGroup.style.display = show ? "" : "none";
    if (toGroup) toGroup.style.display = show ? "" : "none";
  }

  updateDateRangeVisibility();
  if (timeSelect) {
    timeSelect.addEventListener("change", updateDateRangeVisibility);
  }

  // --- Filtry zleceń: pamiętanie ustawień + auto-submit + reset ---

  const filtersForm = document.getElementById("dashboard-orders-filters");

  function hasQueryFilters() {
    const params = new URLSearchParams(window.location.search);
    const filterNames = [
      "type",
      "assignee",
      "status",
      "time",
      "date_from",
      "date_to",
      "hide_completed",
    ];
    return filterNames.some((name) => params.has(name));
  }

  if (filtersForm) {
    const filtersStorageKey = `allsec_dashboard_filters_${userId}`;

    function saveFiltersToStorage() {
      const data = {};
      const typeField = filtersForm.querySelector("select[name='type']");
      const assigneeField = filtersForm.querySelector("select[name='assignee']");
      const statusField = filtersForm.querySelector("select[name='status']");
      const timeField = filtersForm.querySelector("select[name='time']");
      const dateFromField = filtersForm.querySelector("input[name='date_from']");
      const dateToField = filtersForm.querySelector("input[name='date_to']");
      const hideCheckbox = filtersForm.querySelector("input[name='hide_completed']");

      data.type = typeField ? typeField.value || "" : "";
      data.assignee = assigneeField ? assigneeField.value || "" : "";
      data.status = statusField ? statusField.value || "" : "";
      data.time = timeField ? timeField.value || "" : "";
      data.date_from = dateFromField ? dateFromField.value || "" : "";
      data.date_to = dateToField ? dateToField.value || "" : "";
      data.hide_completed = hideCheckbox ? !!hideCheckbox.checked : true;

      try {
        window.localStorage.setItem(filtersStorageKey, JSON.stringify(data));
      } catch (e) {
        // brak localStorage – ignorujemy
      }
    }

    function loadFiltersFromStorage() {
      let stored = null;
      try {
        stored = window.localStorage.getItem(filtersStorageKey);
      } catch (e) {
        stored = null;
      }
      if (!stored) return false;

      let data;
      try {
        data = JSON.parse(stored);
      } catch (e) {
        return false;
      }
      if (!data || typeof data !== "object") return false;

      const typeField = filtersForm.querySelector("select[name='type']");
      const assigneeField = filtersForm.querySelector("select[name='assignee']");
      const statusField = filtersForm.querySelector("select[name='status']");
      const timeField = filtersForm.querySelector("select[name='time']");
      const dateFromField = filtersForm.querySelector("input[name='date_from']");
      const dateToField = filtersForm.querySelector("input[name='date_to']");
      const hideCheckbox = filtersForm.querySelector("input[name='hide_completed']");

      if (typeField && "type" in data) typeField.value = data.type || "";
      if (assigneeField && "assignee" in data)
        assigneeField.value = data.assignee || "";
      if (statusField && "status" in data) statusField.value = data.status || "";
      if (timeField && "time" in data) timeField.value = data.time || "";
      if (dateFromField && "date_from" in data)
        dateFromField.value = data.date_from || "";
      if (dateToField && "date_to" in data)
        dateToField.value = data.date_to || "";
      if (hideCheckbox && "hide_completed" in data)
        hideCheckbox.checked = !!data.hide_completed;

      return true;
    }

    // Jeśli nie ma żadnych filtrów w URL, spróbuj wczytać z localStorage
    if (!hasQueryFilters()) {
      const loaded = loadFiltersFromStorage();
      if (loaded) {
        updateDateRangeVisibility();
        filtersForm.submit();
        return; // reszta JS wykona się po przeładowaniu strony
      }
    }

    // Auto-submit + zapisywanie filtrów po każdej zmianie
    const autoSubmitInputs = filtersForm.querySelectorAll(
      "select, input[type='checkbox'], input[type='date']"
    );
    autoSubmitInputs.forEach((el) => {
      el.addEventListener("change", function () {
        saveFiltersToStorage();
        filtersForm.submit();
      });
    });

    // Przycisk "Resetuj" – przywrócenie domyślnych wartości
    const resetButton = document.getElementById("dashboard-filters-reset");
    if (resetButton) {
      resetButton.addEventListener("click", function () {
        const typeField = filtersForm.querySelector("select[name='type']");
        const assigneeField = filtersForm.querySelector("select[name='assignee']");
        const statusField = filtersForm.querySelector("select[name='status']");
        const timeField = filtersForm.querySelector("select[name='time']");
        const dateFromField = filtersForm.querySelector("input[name='date_from']");
        const dateToField = filtersForm.querySelector("input[name='date_to']");
        const hideCheckbox = filtersForm.querySelector("input[name='hide_completed']");

        if (typeField) typeField.value = "";
        if (assigneeField) assigneeField.value = "";
        if (statusField) statusField.value = "";
        if (timeField) timeField.value = "week";
        if (dateFromField) dateFromField.value = "";
        if (dateToField) dateToField.value = "";
        if (hideCheckbox) hideCheckbox.checked = true;

        try {
          window.localStorage.removeItem(filtersStorageKey);
        } catch (e) {}

        updateDateRangeVisibility();

        filtersForm.submit();
      });
    }
  }
});
