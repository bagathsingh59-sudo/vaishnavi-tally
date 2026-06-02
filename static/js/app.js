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
    F1: "/", F2: "/clients", F4: "/mis", F5: "/payments", F6: "/receipts",
    F7: "/journal", F8: "/daybook", F9: "/ledgers", F12: "/reports",
  };
  if (routes[e.key]) {
    e.preventDefault();
    window.location.href = routes[e.key];
  }
});

// ── Live ledger balance (Cur Bal) beside a ledger <select class="bal"> ──
async function loadBal(sel) {
  const hint = sel.parentElement.querySelector(".balhint");
  if (!hint) return;
  if (!sel.value) { hint.textContent = ""; return; }
  try {
    const r = await fetch("/api/ledger/" + sel.value + "/balance");
    const d = await r.json();
    hint.textContent = "Cur Bal: " + d.formatted;
    hint.style.color = d.type === "Dr" ? "#d33" : "#1e8e3e";
  } catch (e) { hint.textContent = ""; }
}
function attachBalances() {
  document.querySelectorAll("select.bal").forEach((sel) => {
    if (sel.dataset.wired) return;
    sel.dataset.wired = "1";
    sel.addEventListener("change", () => loadBal(sel));
    if (sel.value) loadBal(sel);
  });
}
document.addEventListener("DOMContentLoaded", attachBalances);

// Dynamic row tables (journal / multi-row). Clone last row.
function addRow(tableId) {
  const tbody = document.querySelector("#" + tableId + " tbody");
  const rows = tbody.querySelectorAll("tr");
  const clone = rows[rows.length - 1].cloneNode(true);
  clone.querySelectorAll("input, select").forEach((el) => {
    if (el.type === "number") el.value = "";
    else if (el.tagName === "SELECT") { el.selectedIndex = 0; el.dataset.wired = ""; }
    else el.value = "";
  });
  clone.querySelectorAll(".balhint").forEach((h) => (h.textContent = ""));
  tbody.appendChild(clone);
  attachBalances();
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

// ── Auto-balance a journal row: fill this line so total Dr = total Cr ──
async function balanceRow(btn) {
  const tr = btn.closest("tr");
  let otherDr = 0, otherCr = 0;
  document.querySelectorAll('#jrnTable input[name="debit[]"]').forEach((i) => {
    if (!tr.contains(i)) otherDr += parseFloat(i.value || 0);
  });
  document.querySelectorAll('#jrnTable input[name="credit[]"]').forEach((i) => {
    if (!tr.contains(i)) otherCr += parseFloat(i.value || 0);
  });
  const drIn = tr.querySelector('input[name="debit[]"]');
  const crIn = tr.querySelector('input[name="credit[]"]');
  const diff = otherCr - otherDr; // >0 => this row needs a debit
  let thisDr = 0, thisCr = 0;
  if (diff >= 0) { thisDr = diff; drIn.value = diff ? diff.toFixed(2) : ""; crIn.value = ""; }
  else { thisCr = -diff; crIn.value = (-diff).toFixed(2); drIn.value = ""; }
  recalcJournal();

  // Show the projected balance for this ledger after the entry
  const sel = tr.querySelector("select.bal");
  const hint = tr.querySelector(".balhint");
  if (sel && sel.value && hint) {
    try {
      const r = await fetch("/api/ledger/" + sel.value + "/balance");
      const d = await r.json();
      const cur = d.type === "Dr" ? d.balance : -d.balance;
      const proj = cur + thisDr - thisCr;
      const amt = "₹" + Math.abs(proj).toLocaleString("en-IN", { minimumFractionDigits: 2 });
      if (Math.abs(proj) < 0.01) { hint.textContent = "After this: settled (₹0.00)"; hint.style.color = "#1e8e3e"; }
      else if (proj < 0) { hint.textContent = "After this: " + amt + " Cr (excess held)"; hint.style.color = "#1e8e3e"; }
      else { hint.textContent = "After this: " + amt + " Dr (receivable)"; hint.style.color = "#d33"; }
    } catch (e) {}
  }
}

// ── Floating Calculator ──────────────────────────────────────────────
(function () {
  const panel = document.getElementById("calcPanel");
  const toggle = document.getElementById("calcToggle");
  const disp = document.getElementById("calcDisplay");
  if (!panel || !toggle || !disp) return;
  let expr = "";

  function render() { disp.value = expr === "" ? "0" : expr; }
  function press(k) {
    if (k === "C") expr = "";
    else if (k === "back") expr = expr.slice(0, -1);
    else if (k === "=") {
      try {
        const safe = expr.replace(/[^0-9.+\-*/()%]/g, "").replace(/%/g, "/100");
        if (safe) { expr = String(Function('"use strict";return (' + safe + ')')()); }
      } catch (e) { expr = "Error"; }
    } else expr += k;
    render();
  }

  toggle.addEventListener("click", () => {
    panel.style.display = panel.style.display === "block" ? "none" : "block";
  });
  document.getElementById("calcClose").addEventListener("click", () => panel.style.display = "none");
  panel.querySelectorAll(".ck").forEach((b) =>
    b.addEventListener("click", () => press(b.dataset.k)));

  // Alt+C toggles, keyboard input when panel open
  document.addEventListener("keydown", (e) => {
    if (e.altKey && e.key.toLowerCase() === "c") {
      e.preventDefault();
      panel.style.display = panel.style.display === "block" ? "none" : "block";
      return;
    }
    if (panel.style.display !== "block") return;
    if ("0123456789+-*/.%".includes(e.key)) { press(e.key); }
    else if (e.key === "Enter") { e.preventDefault(); press("="); }
    else if (e.key === "Backspace") { press("back"); }
    else if (e.key === "Escape") { panel.style.display = "none"; }
  });

  // Draggable by header
  const head = document.getElementById("calcHead");
  let drag = false, ox = 0, oy = 0;
  head.addEventListener("mousedown", (e) => {
    drag = true; ox = e.clientX - panel.offsetLeft; oy = e.clientY - panel.offsetTop;
    panel.style.bottom = "auto"; panel.style.right = "auto";
  });
  document.addEventListener("mousemove", (e) => {
    if (!drag) return;
    panel.style.left = (e.clientX - ox) + "px";
    panel.style.top = (e.clientY - oy) + "px";
  });
  document.addEventListener("mouseup", () => drag = false);
})();
