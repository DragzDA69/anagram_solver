"use strict";

/* The solver, in the browser. Only the standalone build loads this file: the
   served page posts to /api/solve and gets the Python solver instead.

   app.js checks for window.LOCAL_SOLVE and uses it when it is there, so both
   pages run the same markup, stylesheet and UI code, and this is the only
   piece that differs. solveLocally() therefore returns exactly what
   /api/solve returns.

   A direct port of main.py. */

const MAX_SHOW = 3000;   // cap the render; '????????????' would return 151k

let WORDS = null, MASK = null, LEN = null, LONGEST = 0;

/* ---- dictionary: decode the front-coded list ---------------------------- */
/* Each line is <shared-prefix-length as one char><the rest of the word>. */
function decode() {
  const raw = document.getElementById("wl").textContent;
  const lines = raw.split("\n");
  const n = lines.length;
  const words = new Array(n);
  const mask = new Int32Array(n);
  const len = new Uint8Array(n);
  let prev = "", longest = 0;
  for (let i = 0; i < n; i++) {
    const line = lines[i];
    prev = prev.slice(0, line.charCodeAt(0) - 48) + line.slice(1);
    words[i] = prev;
    let m = 0;
    for (let j = 0; j < prev.length; j++) m |= 1 << (prev.charCodeAt(j) - 97);
    mask[i] = m;
    len[i] = prev.length;
    if (prev.length > longest) longest = prev.length;
  }
  WORDS = words; MASK = mask; LEN = len; LONGEST = longest;
}

function popcount(n) {
  n = n - ((n >> 1) & 0x55555555);
  n = (n & 0x33333333) + ((n >> 2) & 0x33333333);
  return (((n + (n >> 4)) & 0x0f0f0f0f) * 0x01010101) >> 24;
}

/* ---- the solver: same rules as main.py ---------------------------------- */
function parseRack(raw) {
  const rack = new Int32Array(26);
  let wild = 0;
  for (const ch of raw.toLowerCase()) {
    if (ch === "?") wild++;
    else if (ch >= "a" && ch <= "z") rack[ch.charCodeAt(0) - 97]++;
    else if (" ,.-_".includes(ch)) continue;
    else throw new Error("Invalid character in letters: '" + ch + "' (use a-z and ?)");
  }
  return { rack, wild };
}

function solveRack(rack, wild, wanted) {
  let rackMask = 0;
  for (let i = 0; i < 26; i++) if (rack[i]) rackMask |= 1 << i;
  const unavailable = ~rackMask;
  const seen = new Int32Array(26);
  const found = new Map();

  for (let i = 0; i < WORDS.length; i++) {
    const L = LEN[i];
    if (!wanted.has(L)) continue;
    if (popcount(MASK[i] & unavailable) > wild) continue;

    const w = WORDS[i];
    let deficit = 0;
    for (let j = 0; j < L; j++) {
      const c = w.charCodeAt(j) - 97;
      if (++seen[c] > rack[c]) deficit++;
    }
    for (let j = 0; j < L; j++) seen[w.charCodeAt(j) - 97] = 0;
    if (deficit > wild) continue;

    let bucket = found.get(L);
    if (!bucket) found.set(L, bucket = []);
    bucket.push(w);
  }
  return found;
}

/* Which lengths to search; mirrors choose_lengths() in main.py. */
function chooseLengths(opts, tiles) {
  const notes = [];
  if (opts.exact) {
    if (tiles > LONGEST) return { set: new Set(), notes: ["no word is " + tiles + " letters long"] };
    return { set: new Set([tiles]), notes };
  }
  if (opts.length) {
    const parts = opts.length.replace(/\s+/g, ",").split(",").filter(Boolean);
    const wanted = [];
    for (const p of parts) {
      if (!/^\d+$/.test(p)) throw new Error("Invalid length value: '" + opts.length + "' (expected e.g. 4,5,7)");
      wanted.push(parseInt(p, 10));
    }
    const over = wanted.filter((n) => n > tiles);
    if (over.length) notes.push(over.join(", ") + " exceeds the " + tiles + " tiles available");
    return { set: new Set(wanted.filter((n) => n >= 1 && n <= tiles)), notes };
  }
  const upper = Math.min(opts.max || tiles, tiles, LONGEST);
  const set = new Set();
  for (let n = Math.max(opts.min, 1); n <= upper; n++) set.add(n);
  return { set, notes };
}

/* ---- the seam: the same answer /api/solve would have given -------------- */
window.LOCAL_SOLVE = function (body) {
  const asInt = (v, dflt) => {
    const raw = String(v || "").trim();
    if (!raw) return dflt;
    const n = parseInt(raw, 10);
    if (Number.isNaN(n)) throw new Error("must be a whole number");
    return n;
  };

  const { rack, wild } = parseRack(String(body.letters || ""));
  const tiles = rack.reduce((a, b) => a + b, 0) + wild;
  if (!tiles) throw new Error("No letters given.");

  const lengths = chooseLengths({
    exact: !!body.exact,
    length: String(body.length || "").trim(),
    min: asInt(body.min, 4),
    max: asInt(body.max, 0),
  }, tiles);

  let found = solveRack(rack, wild, lengths.set);
  let notes = lengths.notes.slice();

  const pattern = String(body.pattern || "").trim();
  if (pattern) {
    let re;
    try {
      re = new RegExp("^" + pattern.toLowerCase().replace(/[?.]/g, ".") + "$");
    } catch {
      throw new Error("Invalid pattern.");
    }
    for (const [L, words] of [...found]) {
      const kept = words.filter((w) => re.test(w));
      if (kept.length) found.set(L, kept); else found.delete(L);
    }
  }

  /* By letter, not by count: a board letter that is not really in play makes
     any word using it wrong, however many of it the rack seems to hold. */
  const banned = new Set(String(body.exclude || "").toLowerCase().replace(/[^a-z]/g, ""));
  if (banned.size) {
    for (const [L, words] of [...found]) {
      const kept = words.filter((w) => ![...w].some((c) => banned.has(c)));
      if (kept.length) found.set(L, kept); else found.delete(L);
    }
    notes.push("excluding " + [...banned].sort().join(", "));
  }

  const limit = asInt(body.limit, 0);
  let total = 0;
  for (const words of found.values()) total += words.length;

  const groups = [];
  let shown = 0, truncated = false;
  for (const L of [...found.keys()].sort((a, b) => b - a)) {
    const words = found.get(L);
    let take = limit > 0 ? words.slice(0, limit) : words;
    if (shown + take.length > MAX_SHOW) {
      take = take.slice(0, MAX_SHOW - shown);
      truncated = true;
    }
    shown += take.length;
    groups.push({ length: L, count: words.length, words: take });
    if (truncated) break;
  }
  if (truncated) notes.push("output capped at " + MAX_SHOW.toLocaleString());

  return {
    ok: true,
    rack: { letters: tiles - wild, wildcards: wild, tiles: tiles },
    groups: groups,
    total: total,
    truncated: truncated,
    notes: notes,
    dictSize: WORDS.length,
  };
};

/* Decoded after first paint so the page is visible straight away; app.js
   waits on this before its first solve. */
window.LOCAL_READY = new Promise((resolve) => {
  setTimeout(() => {
    const t0 = performance.now();
    decode();
    resolve({ words: WORDS.length, ms: Math.round(performance.now() - t0) });
  }, 0);
});
