document.addEventListener("DOMContentLoaded", function () {
  const root = document.getElementById("dashboard-root");
  if (!root) {
    return;
  }

  const userId = root.dataset.userId || "anon";

  // --- Helpery localStorage ---

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

    // Przy pierwszym wejściu spróbuj odtworzyć kolejność
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

  // --- Auto-submit filtrów po zmianie ---

  const filtersForm = document.getElementById("dashboard-orders-filters");
  if (filtersForm) {
    const autoSubmitInputs = filtersForm.querySelectorAll(
      "select, input[type='checkbox'], input[type='date']"
    );
    autoSubmitInputs.forEach((el) => {
      el.addEventListener("change", function () {
        filtersForm.submit();
      });
    });
  }
});
