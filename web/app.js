"use strict";

const $ = (id) => document.getElementById(id);
const form = $("form");
const letters = $("letters");
const results = $("results");
const status = $("status");

let view = "grouped";
/* Lengths the reader has collapsed. Results re-render on every keystroke,
   so without this a closed group would spring open again as you type. */
const collapsed = new Set();
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

$("clear").addEventListener("click", () => {
  letters.value = "";
  $("clear").hidden = true;
  letters.focus();
  syncHead();
  solve();
});

$("pattern").addEventListener("input", (e) => {
  e.target.value = e.target.value.toLowerCase().replace(/[^a-z.?]/g, "");
});

$("exclude").addEventListener("input", (e) => {
  e.target.value = e.target.value.toLowerCase().replace(/[^a-z]/g, "");
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

for (const id of ["length", "min", "max", "pattern", "exclude", "limit", "exact"]) {
  $(id).addEventListener("input", () => { reflectDisabled(); schedule(); });
}

form.addEventListener("submit", (e) => { e.preventDefault(); solve(); });

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
    what is being solved. Also hides the clear button when there is nothing to
    clear, since syncHead() already runs on every change to the field. */
function syncHead() {
  const v = letters.value;
  $("clear").hidden = !v;
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
  $("copyHint").hidden = true;
  lastWords = [];

  if (!raw) {
    flash("");
    results.innerHTML = '<p class="empty">{{msg_prompt}}</p>';
    return;
  }

  const body = {
    letters: raw,
    length: $("length").value.trim(),
    min: $("min").value.trim(),
    max: $("max").value.trim(),
    pattern: $("pattern").value.trim(),
    exclude: $("exclude").value.trim(),
    limit: $("limit").value.trim(),
    exact: $("exact").checked,
  };

  const mine = ++seq;
  flash("Solving…");

  // The standalone build inlines solver.js, which defines LOCAL_SOLVE; the
  // served page has no such thing and posts to the Python solver instead.
  let data;
  if (window.LOCAL_SOLVE) {
    await window.LOCAL_READY;
    try {
      data = window.LOCAL_SOLVE(body);
    } catch (exc) {
      flash(exc.message, true);
      return;
    }
  } else {
    try {
      const res = await fetch("/api/solve", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      data = await res.json();
    } catch {
      flash("Lost contact with the local server. Is server.py still running?", true);
      return;
    }
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
  $("copyHint").hidden = true;
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
    results.innerHTML = '<p class="empty">{{msg_no_match}}</p>';
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

  $("copyHint").hidden = false;   // past the empty and Counts cases: chips follow
  const frag = document.createDocumentFragment();

  if (view === "flat") {
    const box = document.createElement("div");
    box.className = "words flat";
    box.append(...lastWords.map(chip));
    frag.append(box);
  } else {
    for (const g of groups) {
      const sec = document.createElement("details");
      sec.className = "group";
      sec.open = !collapsed.has(g.length);
      sec.addEventListener("toggle", () => {
        if (sec.open) collapsed.delete(g.length);
        else collapsed.add(g.length);
      });

      const h = document.createElement("summary");
      h.innerHTML = `<b>${g.length} letters</b> <i>${g.count.toLocaleString()}`
        + `${g.words.length < g.count ? `, showing ${g.words.length}` : ""}</i>`
        + `<span class="rule"></span><span class="chev">&#9662;</span>`;

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
  const el = document.createElement("button");
  el.type = "button";
  el.className = "word";
  el.textContent = word;
  return el;
}

// --- copying a single word ------------------------------------------------

/* Both from ui.py, so the CSS transition and the timer below stay in step. */
/* Quoted so this file is valid JS before rendering as well as after. */
const TOAST_MS = +"{{toast_ms}}", TOAST_FADE_MS = +"{{toast_fade_ms}}";

/* One listener for the whole board: there can be thousands of chips. */
results.addEventListener("click", (e) => {
  const el = e.target.closest(".word");
  if (el) copyWord(el.textContent);
});

async function copyWord(word) {
  try {
    await navigator.clipboard.writeText(word);
  } catch {
    if (!legacyCopy(word)) {
      flash("{{msg_copy_failed}}", true);
      return;
    }
  }
  toast(word);
}

function legacyCopy(text) {
  const ta = document.createElement("textarea");
  ta.value = text;
  ta.style.position = "fixed";
  ta.style.opacity = "0";
  document.body.append(ta);
  ta.select();
  let ok = false;
  try { ok = document.execCommand("copy"); } catch {}
  ta.remove();
  return ok;
}

/* Android-style: a new toast wipes out whatever is on screen at once, rather
   than queueing behind it or crossfading with it. */
function toast(word) {
  const host = $("toasts");
  for (const old of host.querySelectorAll(".toast")) {
    clearTimeout(old.dismiss);
    old.remove();
  }

  const el = document.createElement("div");
  el.className = "toast";
  el.append(code(word), document.createTextNode("{{toast_copied_suffix}}"));
  host.append(el);

  // Two frames, so the browser paints the off-screen state before it animates.
  requestAnimationFrame(() => requestAnimationFrame(() => el.classList.add("show")));

  el.dismiss = setTimeout(() => {
    el.classList.remove("show");
    el.dismiss = setTimeout(() => el.remove(), TOAST_FADE_MS + 80);
  }, TOAST_MS);
}

function code(word) {
  const el = document.createElement("code");
  el.textContent = word;
  return el;
}

// --- startup --------------------------------------------------------------

(function init() {
  /* Options start open on desktop, collapsed under the "md" width (768px). */
  if (window.matchMedia("(max-width: 767px)").matches) $("opts").open = false;
  syncHead();
  reflectDisabled();
  results.innerHTML = '<p class="empty">{{msg_prompt}}</p>';

  if (window.LOCAL_SOLVE) {
    /* Offline build: say so while the embedded dictionary is decoding, then
       report it where the server would have reported the word count. */
    flash("{{msg_loading_dict}}");
    window.LOCAL_READY.then(({ words, ms }) => {
      flash(words.toLocaleString() + " words · ready in " + ms + " ms");
      if (letters.value) solve();
    });
  }
})();
