// Tally-style keyboard shortcuts
document.addEventListener("keydown", function (e) {
  const tag = (document.activeElement.tagName || "").toUpperCase();
  const typing = ["INPUT", "TEXTAREA", "SELECT"].includes(tag);

  // Ctrl+S => submit the primary form on the page
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "s") {
    e.preventDefault();
    const form = document.querySelector("form[data-primary]");
    if (form) form.submit();
    return;
  }
  if (typing) return;

  const routes = {
    F1: "/", F2: "/clients", F5: "/payments", F6: "/receipts",
    F7: "/journal", F8: "/daybook", F9: "/ledgers", F12: "/reports",
  };
  if (routes[e.key]) {
    e.preventDefault();
    window.location.href = routes[e.key];
  }
});

// Dynamic row tables (journal / multi-row). Clone last row.
function addRow(tableId) {
  const tbody = document.querySelector("#" + tableId + " tbody");
  const rows = tbody.querySelectorAll("tr");
  const clone = rows[rows.length - 1].cloneNode(true);
  clone.querySelectorAll("input, select").forEach((el) => {
    if (el.type === "number") el.value = "";
    else if (el.tagName === "SELECT") el.selectedIndex = 0;
    else el.value = "";
  });
  tbody.appendChild(clone);
  recalcJournal();
}

function removeRow(btn) {
  const tbody = btn.closest("tbody");
  if (tbody.querySelectorAll("tr").length > 1) {
    btn.closest("tr").remove();
    recalcJournal();
  }
}

// Live Dr/Cr balance check for journal
function recalcJournal() {
  let dr = 0, cr = 0;
  document.querySelectorAll('input[name="debit[]"]').forEach((i) => dr += parseFloat(i.value || 0));
  document.querySelectorAll('input[name="credit[]"]').forEach((i) => cr += parseFloat(i.value || 0));
  const el = document.getElementById("jrn-balance");
  if (!el) return;
  const diff = dr - cr;
  if (Math.abs(diff) < 0.01 && dr > 0) {
    el.textContent = "✓ Balanced — Dr ₹" + dr.toFixed(2) + " = Cr ₹" + cr.toFixed(2);
    el.style.color = "#1E8449";
  } else {
    el.textContent = "Difference: ₹" + Math.abs(diff).toFixed(2);
    el.style.color = "#C0392B";
  }
}
document.addEventListener("input", function (e) {
  if (e.target.name === "debit[]" || e.target.name === "credit[]") recalcJournal();
});
