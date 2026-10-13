"use strict";

const $ = (id) => document.getElementById(id);
const form = $("form");
const letters = $("letters");
const results = $("results");
const status = $("status");

let view = "grouped";
let lastWords = [];
let timer = null;
let seq = 0;

// --- input hygiene: letters and '?' only, never digits ---------------------

letters.addEventListener("input", () => {
  const start = letters.selectionStart;
  const before = letters.value;
  const clean = before.toLowerCase().replace(/[^a-z?]/g, "");
  if (clean !== before) {
    letters.value = clean;
    const removed = before.length - clean.length;
    letters.setSelectionRange(start - removed, start - removed);
  }
  syncHead();
  schedule();
});

$("pattern").addEventListener("input", (e) => {
  e.target.value = e.target.value.toLowerCase().replace(/[^a-z.?]/g, "");
});

$("length").addEventListener("input", (e) => {
  e.target.value = e.target.value.replace(/[^0-9,\s]/g, "");
});

// --- controls -------------------------------------------------------------

document.querySelectorAll(".seg button").forEach((b) => {
  b.addEventListener("click", () => {
    document.querySelectorAll(".seg button").forEach((x) => x.classList.remove("on"));
    b.classList.add("on");
    view = b.dataset.view;
    solve();
  });
});

for (const id of ["length", "min", "max", "pattern", "limit", "exact"]) {
  $(id).addEventListener("input", () => { reflectDisabled(); schedule(); });
}

form.addEventListener("submit", (e) => { e.preventDefault(); solve(); });

$("copy").addEventListener("click", async () => {
  if (!lastWords.length) return;
  try {
    await navigator.clipboard.writeText(lastWords.join("\n"));
    flash(`Copied ${lastWords.length} words`);
  } catch {
    flash("Clipboard blocked by the browser", true);
  }
});

/** Grey out controls the solver will ignore, so the UI matches the CLI's precedence. */
function reflectDisabled() {
  const exact = $("exact").checked;
  const byLength = $("length").value.trim() !== "";
  $("length").closest(".ctl").classList.toggle("off", exact);
  for (const id of ["minWrap", "maxWrap"]) {
    $(id).classList.toggle("off", exact || byLength);
  }
}

/** Mirror the letters into the panel header, so a collapsed panel still shows
    what is being solved. */
function syncHead() {
  const v = letters.value;
  $("headRack").textContent = v ? [...v].join(" ") : "no letters yet";
}

function schedule() {
  clearTimeout(timer);
  timer = setTimeout(solve, 180);
}

function flash(msg, bad) {
  status.textContent = msg;
  status.classList.toggle("err", !!bad);
}

// --- solving --------------------------------------------------------------

async function solve() {
  const raw = letters.value.trim();
  results.innerHTML = "";
  lastWords = [];

  if (!raw) {
    flash("");
    results.innerHTML = '<p class="empty">Type the board letters to begin.</p>';
    return;
  }

  const body = {
    letters: raw,
    length: $("length").value.trim(),
    min: $("min").value.trim(),
    max: $("max").value.trim(),
    pattern: $("pattern").value.trim(),
    limit: $("limit").value.trim(),
    exact: $("exact").checked,
  };

  const mine = ++seq;
  flash("Solving…");

  let data;
  try {
    const res = await fetch("/api/solve", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    data = await res.json();
  } catch {
    flash("Lost contact with the local server. Is serve.py still running?", true);
    return;
  }

  if (mine !== seq) return; // a newer keystroke already won

  if (!data.ok) {
    flash(data.error, true);
    return;
  }

  render(data);
}

function render(data) {
  const { rack, groups, total, notes } = data;
  lastWords = groups.flatMap((g) => g.words);

  let summary = `${total.toLocaleString()} word${total === 1 ? "" : "s"} from `
    + `${rack.letters} letter${rack.letters === 1 ? "" : "s"}`;
  if (rack.wildcards) {
    summary += ` + ${rack.wildcards} wildcard${rack.wildcards === 1 ? "" : "s"}`;
  }
  if (data.truncated) summary += ` · showing ${lastWords.length.toLocaleString()}`;
  if (notes.length) summary += ` · ${notes.join(" · ")}`;
  flash(summary);

  if (!total) {
    results.innerHTML = '<p class="empty">No words match.</p>';
    return;
  }

  if (view === "count") {
    const rows = groups
      .map((g) => `<tr><td>${g.length} letters</td><td>${g.count.toLocaleString()}</td></tr>`)
      .join("");
    results.innerHTML =
      `<table class="counts">${rows}<tr><td>total</td><td>${total.toLocaleString()}</td></tr></table>`;
    return;
  }

  const frag = document.createDocumentFragment();

  if (view === "flat") {
    const box = document.createElement("div");
    box.className = "words flat";
    box.append(...lastWords.map(chip));
    frag.append(box);
  } else {
    for (const g of groups) {
      const sec = document.createElement("section");
      sec.className = "group";

      const h = document.createElement("h2");
      h.innerHTML = `<b>${g.length} letters</b> <i>${g.count.toLocaleString()}`
        + `${g.words.length < g.count ? `, showing ${g.words.length}` : ""}</i>`;

      const box = document.createElement("div");
      box.className = "words";
      box.append(...g.words.map(chip));

      sec.append(h, box);
      frag.append(sec);
    }
  }

  results.replaceChildren(frag);
}

function chip(word) {
  const el = document.createElement("span");
  el.textContent = word;
  return el;
}

// --- startup --------------------------------------------------------------

(function init() {
  /* Options start open on desktop, collapsed under the "md" width (768px). */
  if (window.matchMedia("(max-width: 767px)").matches) $("opts").open = false;
  syncHead();
  reflectDisabled();
  $("dictInfo").textContent =
    "Solves anagrams from the bundled word list. Handles wildcard [ ? * ] characters.";
  results.innerHTML = '<p class="empty">Type the board letters to begin.</p>';
})();
