// PULSE frontend: plain JavaScript, no framework.
// Pages are switched by the part of the URL after "#", e.g. #/section/Business
// Each page function fetches JSON from the FastAPI backend and writes HTML.

const $ = (sel) => document.querySelector(sel);
const view = $("#view");

// ───────────── Saved settings (this browser only, no login) ─────────────
const store = {
  get(key, fallback) {
    try { return JSON.parse(localStorage.getItem("pulse." + key)) ?? fallback; } catch { return fallback; }
  },
  set(key, value) {
    try { localStorage.setItem("pulse." + key, JSON.stringify(value)); } catch { /* private mode */ }
  },
};
let interests = store.get("interests", []);
let country = store.get("country", "Nigeria");
let meta = null;

const COUNTRIES = ["Nigeria", "Ghana", "Kenya", "South Africa", "Egypt", "United Kingdom", "United States", "India", "Canada"];

// ───────────── Helpers ─────────────
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

async function api(path) {
  const res = await fetch("/api" + path);
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || res.statusText);
  return res.json();
}

function ago(ts) {
  if (!ts) return "";
  const m = Math.max(1, Math.round((Date.now() / 1000 - ts) / 60));
  if (m < 60) return `${m}m ago`;
  const h = Math.round(m / 60);
  return h < 24 ? `${h}h ago` : `${Math.round(h / 24)}d ago`;
}

const navLabel = (name) => (name === "HOME" ? country : name);

function kicker(a, extra = "") {
  const place = a.country && a.country !== "" ? a.country : "";
  let label = a.subcategory || a.category;
  if (extra && label.toLowerCase() === extra.toLowerCase()) label = "";   // avoid "AI · AI"
  const parts = [extra ? `<b>${esc(extra)}</b>` : "", esc(label), esc(place)].filter(Boolean);
  return `<p class="kicker">${parts.join(" · ")}</p>`;
}

function skeleton(rows = 4) {
  return Array.from({ length: rows }, () => `
    <div class="py-5 border-b border-rule flex gap-4">
      <div class="flex-1 space-y-2"><div class="shimmer h-3 w-24 rounded"></div><div class="shimmer h-5 w-4/5 rounded"></div><div class="shimmer h-3 w-3/5 rounded"></div></div>
      <div class="shimmer w-28 h-20 rounded"></div>
    </div>`).join("");
}

// One story as a row: text left, small picture right. Used almost everywhere.
function storyRow(a, opts = {}) {
  const img = a.image
    ? `<img class="thumb w-24 h-20 sm:w-32 sm:h-24 object-cover rounded shrink-0" src="${esc(a.image)}" alt="" loading="lazy" onerror="this.remove()">`
    : "";
  return `
  <article class="py-5 border-b border-rule fade-in" data-id="${esc(a.id || "")}">
    <div class="flex gap-4 sm:gap-5">
      <div class="flex-1 min-w-0">
        ${kicker(a, opts.because ? a.because : "")}
        <a href="${esc(a.link)}" target="_blank" rel="noopener" class="headline block font-serif text-[19px] sm:text-[21px] leading-snug mt-1.5">${esc(a.title)}</a>
        ${a.desc ? `<p class="text-[14px] text-muted mt-1.5 clamp-2">${esc(a.desc)}</p>` : ""}
        <div class="flex items-center gap-3 mt-2 text-xs text-muted">
          <span class="font-medium text-ink/80">${esc(a.source)}</span><span>${ago(a.published)}</span>
          ${a.id ? `<button class="quick ml-auto sm:ml-0 text-accent font-medium hover:underline" data-id="${esc(a.id)}">Quick read</button>` : ""}
        </div>
        <div class="summary hidden"></div>
      </div>
      ${img}
    </div>
  </article>`;
}

// Bigger lead story at the top of a section: picture left, text right.
function leadStory(a) {
  return `
  <article class="grid sm:grid-cols-5 gap-5 py-6 border-b border-ink/80 fade-in" data-id="${esc(a.id)}">
    ${a.image ? `<img class="thumb sm:col-span-3 w-full aspect-[16/10] object-cover rounded" src="${esc(a.image)}" alt="" onerror="this.remove()">` : ""}
    <div class="${a.image ? "sm:col-span-2" : "sm:col-span-5"} flex flex-col">
      ${kicker(a)}
      <a href="${esc(a.link)}" target="_blank" rel="noopener" class="headline font-serif text-[28px] leading-tight mt-2">${esc(a.title)}</a>
      ${a.desc ? `<p class="text-[15px] text-muted mt-3 clamp-3">${esc(a.desc)}</p>` : ""}
      <div class="flex items-center gap-3 mt-3 text-xs text-muted">
        <span class="font-medium text-ink/80">${esc(a.source)}</span><span>${ago(a.published)}</span>
        <button class="quick text-accent font-medium hover:underline" data-id="${esc(a.id)}">Quick read</button>
      </div>
      <div class="summary hidden"></div>
    </div>
  </article>`;
}

// "Quick read": fetch an AI summary only when asked (keeps everything fast + cheap).
document.addEventListener("click", async (e) => {
  const btn = e.target.closest(".quick");
  if (!btn) return;
  const box = btn.closest("article").querySelector(".summary");
  if (!box.classList.contains("hidden") && box.dataset.loaded) { box.classList.add("hidden"); btn.textContent = "Quick read"; return; }
  box.classList.remove("hidden");
  btn.textContent = "Hide";
  if (box.dataset.loaded) return;
  box.innerHTML = `<div class="mt-3 space-y-2"><div class="shimmer h-3 rounded"></div><div class="shimmer h-3 w-5/6 rounded"></div><div class="shimmer h-3 w-2/3 rounded"></div></div>`;
  try {
    const s = await api("/summary/" + btn.dataset.id);
    box.innerHTML = `
      <div class="mt-3 border-l-2 border-accent pl-4 fade-in">
        <p class="text-[15px] leading-relaxed">${esc(s.summary)}</p>
        ${s.why ? `<p class="text-[14px] text-muted mt-2"><span class="font-semibold text-ink">Why it matters:</span> ${esc(s.why)}</p>` : ""}
        <p class="text-[11px] text-muted mt-2">AI summary${s.by === "bart" ? " (offline model)" : ""}</p>
      </div>`;
    box.dataset.loaded = "1";
  } catch (err) {
    box.innerHTML = `<p class="mt-3 text-sm text-muted">Couldn't summarise this one. ${esc(err.message)}</p>`;
  }
});

// ───────────── Nav ─────────────
function drawNav(active) {
  const items = [["Today", "#/"], ...meta.nav.map((n) => [navLabel(n), "#/section/" + encodeURIComponent(n)])];
  $("#nav").innerHTML = items.map(([label, href]) => {
    const on = href === active;
    return `<a href="${href}" class="py-2.5 whitespace-nowrap border-b-2 ${on ? "border-accent text-ink" : "border-transparent text-muted hover:text-ink"}">${esc(label)}</a>`;
  }).join("");
}

// ───────────── Today (landing) ─────────────
function greeting() {
  const h = new Date().getHours();
  return h < 12 ? "Good morning." : h < 17 ? "Good afternoon." : "Good evening.";
}

async function pageToday() {
  drawNav("#/");
  view.innerHTML = `
    <section class="grid lg:grid-cols-12 gap-8 pt-10 pb-10 border-b border-ink/80">
      <div class="lg:col-span-7">
        <p class="kicker">World Temperature</p>
        <h1 class="font-serif text-[44px] sm:text-[56px] leading-[1.02] tracking-tight mt-3">${greeting()}<br><span class="italic text-muted">What's going on in the world today?</span></h1>
        <p class="text-sm text-muted mt-4">Read from ${esc(country)}, with ${esc(country)} first, then how it shows up in the world, then everywhere else.</p>
      </div>
      <div class="lg:col-span-5 flex flex-col justify-end">
        <div id="gauge" class="bg-card border border-rule rounded-2xl p-5">
          <div class="flex items-baseline justify-between">
            <span class="kicker">Today's reading</span>
            <span id="gaugeMood" class="font-serif text-xl text-muted italic">Not taken yet</span>
          </div>
          <div class="relative mt-4 h-2.5 rounded-full scale opacity-30" id="gaugeBar">
            <div id="gaugeDot" class="hidden absolute -top-[5px] w-5 h-5 rounded-full bg-ink border-[3px] border-card shadow transition-all duration-700" style="left:0%"></div>
          </div>
          <div class="flex justify-between text-[11px] text-muted mt-2"><span>Calm</span><span>Normal churn</span><span>Boiling</span></div>
          <button id="takeTemp" class="mt-5 w-full py-3 rounded-full bg-ink text-paper text-sm font-medium hover:bg-accent transition">Take the world's temperature</button>
        </div>
      </div>
    </section>
    <section id="briefing"></section>

    <section class="pt-8">
      <div class="flex items-baseline justify-between"><h2 class="font-serif text-2xl">Three stories shaping today</h2><span class="text-xs text-muted">from different corners of the world</span></div>
      <div id="top" class="grid md:grid-cols-3 gap-0 md:gap-8 mt-4 border-t border-rule">${skeleton(1)}</div>
    </section>

    <section class="grid lg:grid-cols-12 gap-10 pt-10">
      <div class="lg:col-span-8">
        <div class="flex items-baseline justify-between border-b border-ink/80 pb-2">
          <h2 class="font-serif text-2xl">This might interest you today</h2>
          <button class="text-xs text-accent font-medium hover:underline" onclick="openPicker()">Edit interests</button>
        </div>
        <div id="thin"></div>
        <div id="forYou">${skeleton(4)}</div>
      </div>
      <aside class="lg:col-span-4">
        <div class="lg:sticky lg:top-32">
          <div class="flex items-baseline justify-between border-b border-ink/80 pb-2">
            <h2 class="font-serif text-2xl">${esc(country)} now</h2>
            <a href="#/section/HOME" class="text-xs text-accent font-medium hover:underline">All →</a>
          </div>
          <ol id="homeNow" class="divide-y divide-rule"></ol>
        </div>
      </aside>
    </section>`;

  $("#takeTemp").onclick = () => loadBriefing(false);

  const qs = new URLSearchParams({ country });
  interests.forEach((i) => qs.append("i", i));
  let d;
  try { d = await api("/home?" + qs); } catch (err) { $("#forYou").innerHTML = errorBox(err); return; }

  $("#top").innerHTML = d.top.map((a, n) => `
    <article class="py-5 md:border-r md:last:border-r-0 border-rule md:pr-8 border-b md:border-b-0 fade-in" data-id="${esc(a.id)}">
      <div class="flex items-start gap-4">
        <span class="font-serif text-4xl text-accent leading-none">0${n + 1}</span>
        ${a.image ? `<img class="thumb w-20 h-20 object-cover rounded-full ml-auto" src="${esc(a.image)}" alt="" onerror="this.remove()">` : ""}
      </div>
      <div class="mt-3">${kicker(a)}</div>
      <a href="${esc(a.link)}" target="_blank" rel="noopener" class="headline block font-serif text-[22px] leading-snug mt-1.5">${esc(a.title)}</a>
      <p class="text-[14px] text-muted mt-2 clamp-3">${esc(a.desc)}</p>
      <div class="flex items-center gap-3 mt-2 text-xs text-muted"><span class="font-medium text-ink/80">${esc(a.source)}</span><span>${ago(a.published)}</span>
        <button class="quick text-accent font-medium hover:underline" data-id="${esc(a.id)}">Quick read</button></div>
      <div class="summary hidden"></div>
    </article>`).join("") || `<p class="py-6 text-muted">Gathering today's headlines…</p>`;

  $("#homeNow").innerHTML = d.home_now.map((a, n) => `
    <li class="py-3.5 flex gap-3">
      <span class="font-serif text-lg text-muted w-5 shrink-0">${n + 1}</span>
      <div><a href="${esc(a.link)}" target="_blank" rel="noopener" class="headline font-serif text-[17px] leading-snug">${esc(a.title)}</a>
      <p class="text-xs text-muted mt-1">${esc(a.source)} · ${ago(a.published)}</p></div>
    </li>`).join("") || `<li class="py-4 text-sm text-muted">Nothing from ${esc(country)} yet.</li>`;

  const fy = d.for_you;
  if (!fy) {
    $("#forYou").innerHTML = `
      <div class="py-8 text-center">
        <p class="font-serif text-xl">Tell PULSE what you care about.</p>
        <p class="text-sm text-muted mt-1">AI, marine life, Nollywood, anything at all.</p>
        <button onclick="openPicker()" class="mt-4 px-5 py-2.5 rounded-full bg-accent text-white text-sm">Pick interests</button>
      </div>`;
    return;
  }
  $("#thin").innerHTML = fy.thin.map((t) => `
    <div class="mt-4 bg-card border border-rule rounded-xl px-4 py-3 text-sm">
      <span class="font-medium">Not much on ${esc(t.interest)} today${t.found ? ` (${t.found} story)` : ""}.</span>
      ${t.suggest.length ? `<span class="text-muted">Try </span>${t.suggest.map((s) => `<button class="text-accent hover:underline" onclick="addInterest(${esc(JSON.stringify(s))})">${esc(s)}</button>`).join('<span class="text-muted">, </span>')}<span class="text-muted">, or </span>` : `<span class="text-muted">You can </span>`}
      <a class="text-accent hover:underline" href="#/search?q=${encodeURIComponent(t.interest)}">search the web for it →</a>
    </div>`).join("");
  $("#forYou").innerHTML =
    fy.matched.map((a) => storyRow(a, { because: true })).join("") +
    (fy.more.length ? `<p class="kicker pt-8 pb-1">More from today</p>` + fy.more.map((a) => storyRow(a)).join("") : "");
}

// ───────────── World Temperature briefing ─────────────
async function loadBriefing(force) {
  const btn = $("#takeTemp");
  btn.disabled = true;
  btn.textContent = "Reading the world…";
  $("#briefing").innerHTML = `<div class="py-8 grid md:grid-cols-2 gap-8">${skeleton(2)}${skeleton(2)}</div>`;
  let b;
  try {
    b = await api(`/briefing?country=${encodeURIComponent(country)}${force ? "&refresh=1" : ""}`);
  } catch (err) { b = { error: err.message }; }
  btn.disabled = false;
  if (b.error) {
    btn.textContent = "Try again";
    $("#briefing").innerHTML = `<div class="py-6">${errorBox({ message: b.error })}</div>`;
    return;
  }
  btn.textContent = "Refresh reading";
  btn.onclick = () => loadBriefing(true);
  $("#gaugeBar").classList.remove("opacity-30");
  $("#gaugeDot").classList.remove("hidden");
  requestAnimationFrame(() => ($("#gaugeDot").style.left = `calc(${b.temperature}% - 10px)`));
  $("#gaugeMood").textContent = `${b.mood} · ${b.temperature}°`;
  $("#gaugeMood").classList.remove("text-muted");

  const block = (title, items, note = "") => items.length ? `
    <div class="fade-in">
      <h3 class="kicker !text-ink border-b border-rule pb-2">${esc(title)}</h3>
      <ul class="mt-3 space-y-3">${items.map((it) => `
        <li class="text-[15px] leading-relaxed">${esc(it.text)}
          ${it.sources.map((s) => `<a href="${esc(s.link)}" target="_blank" rel="noopener" class="ml-1 text-[11px] text-accent hover:underline whitespace-nowrap">${esc(s.source)}</a>`).join("")}
        </li>`).join("")}</ul>
    </div>` : note ? `<div><h3 class="kicker !text-ink border-b border-rule pb-2">${esc(title)}</h3><p class="mt-3 text-sm text-muted">${esc(note)}</p></div>` : "";

  $("#briefing").innerHTML = `
    <div class="py-10 border-b border-ink/80">
      <p class="font-serif text-[26px] sm:text-[30px] leading-snug max-w-4xl">${esc(b.headline)}</p>
      <div class="grid md:grid-cols-2 gap-x-12 gap-y-10 mt-8">
        ${block(`${b.country} today`, b.home)}
        ${block(`${b.country} in the world`, b.home_world, `No notable ${b.country} stories abroad in today's feeds.`)}
        ${block("The wider world", b.world)}
        ${block("What to watch", b.expect)}
      </div>
      <div class="mt-10 bg-card border border-rule rounded-2xl p-6">
        <p class="kicker"><b>What it means for you</b></p>
        <p class="font-serif text-[19px] leading-relaxed mt-2">${esc(b.meaning)}</p>
      </div>
      <p class="text-[11px] text-muted mt-4">Written by AI from ${b.story_count} stories across regions · ${new Date(b.generated_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</p>
    </div>`;
}

// ───────────── Category / region sections ─────────────
async function pageSection(name, chip) {
  drawNav("#/section/" + encodeURIComponent(name));
  const title = navLabel(name);
  view.innerHTML = `
    <div class="pt-8 pb-4 border-b border-ink/80">
      <h1 class="font-serif text-[44px] leading-none tracking-tight">${esc(title)}</h1>
      <div id="chips" class="flex gap-2 overflow-x-auto no-scrollbar mt-5"></div>
    </div>
    <div id="list">${skeleton(5)}</div>
    <div id="explore"></div>`;
  let d;
  try {
    const qs = new URLSearchParams({ country });
    if (chip) qs.set("chip", chip);
    d = await api(`/section/${encodeURIComponent(name)}?${qs}`);
  } catch (err) { $("#list").innerHTML = errorBox(err); return; }

  const base = "#/section/" + encodeURIComponent(name);
  $("#chips").innerHTML = [["All", base], ...d.chips.map((c) => [c, base + "?chip=" + encodeURIComponent(c)])]
    .map(([label, href]) => {
      const on = (label === "All" && !chip) || label === chip;
      return `<a href="${href}" class="shrink-0 px-3.5 py-1.5 rounded-full text-[13px] border ${on ? "bg-ink text-paper border-ink" : "border-rule text-muted hover:text-ink hover:border-ink/40"}">${esc(label)}</a>`;
    }).join("");

  const items = d.items;
  const leadIdx = items.findIndex((a) => a.image);
  const lead = leadIdx >= 0 && leadIdx < 4 ? items.splice(leadIdx, 1)[0] : null;
  $("#list").innerHTML = (lead ? leadStory(lead) : "") + items.map((a) => storyRow(a)).join("");

  const topic = chip || (name === "HOME" ? country : name);
  if (items.length + (lead ? 1 : 0) < 3) {
    $("#list").insertAdjacentHTML("afterbegin", `<div class="mt-5 bg-card border border-rule rounded-xl px-4 py-3 text-sm">Very little on <b>${esc(topic)}</b> in today's feeds. Try another subcategory, or search the web below.</div>`);
  }
  $("#explore").innerHTML = exploreBox(name === "HOME" ? `${country} ${chip || "news"}` : `${topic} news`);
}

function exploreBox(query) {
  return `
    <div class="mt-10 bg-card border border-rule rounded-2xl p-6 flex flex-col sm:flex-row sm:items-center gap-4">
      <div class="flex-1"><p class="font-serif text-xl">Want more?</p><p class="text-sm text-muted">Search BBC, CNN, Al Jazeera and Nigerian outlets first, then the wider web.</p></div>
      <a href="#/search?q=${encodeURIComponent(query)}" class="px-5 py-2.5 rounded-full bg-ink text-paper text-sm text-center hover:bg-accent transition">Explore “${esc(query)}”</a>
    </div>`;
}

// ───────────── Search ─────────────
async function pageSearch(q, deep) {
  drawNav("");
  view.innerHTML = `
    <div class="pt-8 pb-5 border-b border-ink/80">
      <p class="kicker">${deep ? "Across the web" : "From the main outlets"}</p>
      <form id="bigSearch" class="mt-2 flex gap-2">
        <input name="q" value="${esc(q)}" placeholder="Search any topic: coral reefs, Lagos tech, AFCON…" class="flex-1 bg-transparent font-serif text-[30px] sm:text-[40px] leading-tight focus:outline-none placeholder:text-muted/50" autofocus>
      </form>
    </div>
    <div id="results">${q ? skeleton(4) : ""}</div>
    <div id="more"></div>`;
  $("#bigSearch").onsubmit = (e) => { e.preventDefault(); location.hash = "#/search?q=" + encodeURIComponent(e.target.q.value); };
  if (!q) return;
  let d;
  try { d = await api(`/search?q=${encodeURIComponent(q)}${deep ? "&deep=1" : ""}`); } catch (err) { $("#results").innerHTML = errorBox(err); return; }
  const note = d.note ? `<div class="mt-5 bg-card border border-rule rounded-xl px-4 py-3 text-sm">${esc(d.note)}</div>` : "";
  $("#results").innerHTML = note + d.results.map((a) => storyRow({ ...a, category: a.source })).join("");
  $("#more").innerHTML = deep ? "" : `
    <div class="mt-8 text-center">
      <a href="#/search?q=${encodeURIComponent(q)}&deep=1" class="inline-block px-6 py-3 rounded-full border border-ink text-sm hover:bg-ink hover:text-paper transition">Explore more across the web</a>
      <p class="text-xs text-muted mt-2">Digs deeper beyond the main outlets. Takes a few seconds.</p>
    </div>`;
}

function errorBox(err) {
  return `<div class="my-6 bg-card border border-rule rounded-xl px-4 py-3 text-sm">Something went wrong: ${esc(err.message)}. <button class="text-accent hover:underline" onclick="route()">Try again</button></div>`;
}

// ───────────── Interest picker ─────────────
let draft = [];

function openPicker() {
  draft = [...interests];
  $("#countrySelect").innerHTML = [...new Set([country, ...COUNTRIES])].map((c) => `<option ${c === country ? "selected" : ""}>${esc(c)}</option>`).join("");
  drawPicker();
  $("#picker").classList.remove("hidden");
}
window.openPicker = openPicker;

function drawPicker() {
  $("#presetGrid").innerHTML = meta.presets.map((p) => {
    const pos = draft.indexOf(p);
    const on = pos >= 0;
    return `<button data-p="${esc(p)}" class="preset relative text-left px-4 py-3 rounded-xl border text-sm transition ${on ? "bg-ink text-paper border-ink" : "bg-card border-rule hover:border-ink/40"}">
      ${esc(p)}${on ? `<span class="absolute top-2 right-2 w-5 h-5 rounded-full bg-accent text-white text-[11px] grid place-items-center">${pos + 1}</span>` : ""}</button>`;
  }).join("");
  const custom = draft.filter((d) => !meta.presets.includes(d));
  $("#chosen").innerHTML = custom.map((c) => `
    <span class="inline-flex items-center gap-2 pl-3 pr-1 py-1 rounded-full bg-ink text-paper text-sm">
      <span class="text-accent text-xs">${draft.indexOf(c) + 1}</span>${esc(c)}
      <button data-rm="${esc(c)}" class="w-5 h-5 rounded-full hover:bg-paper/20" aria-label="Remove">×</button></span>`).join("");
}

$("#presetGrid").onclick = (e) => {
  const b = e.target.closest(".preset");
  if (!b) return;
  const p = b.dataset.p;
  draft = draft.includes(p) ? draft.filter((x) => x !== p) : [...draft, p];
  drawPicker();
};
$("#chosen").onclick = (e) => {
  const b = e.target.closest("[data-rm]");
  if (b) { draft = draft.filter((x) => x !== b.dataset.rm); drawPicker(); }
};
$("#customForm").onsubmit = (e) => {
  e.preventDefault();
  const v = $("#customInput").value.trim();
  if (v && !draft.some((d) => d.toLowerCase() === v.toLowerCase())) draft.push(v);
  $("#customInput").value = "";
  drawPicker();
};
$("#savePicker").onclick = () => {
  interests = draft;
  country = $("#countrySelect").value;
  store.set("interests", interests);
  store.set("country", country);
  store.set("onboarded", true);
  $("#picker").classList.add("hidden");
  route();
};
$("#picker").addEventListener("click", (e) => { if (e.target === $("#picker").firstElementChild) $("#picker").classList.add("hidden"); });

window.addInterest = (name) => {
  if (!interests.includes(name)) interests = [...interests, name];
  store.set("interests", interests);
  route();
};

// ───────────── Router ─────────────
function route() {
  const [path, query = ""] = location.hash.replace(/^#/, "").split("?");
  const params = new URLSearchParams(query);
  window.scrollTo(0, 0);
  const parts = path.split("/").filter(Boolean);
  if (parts[0] === "section" && parts[1]) return pageSection(decodeURIComponent(parts[1]), params.get("chip"));
  if (parts[0] === "search") return pageSearch(params.get("q") || "", params.get("deep") === "1");
  return pageToday();
}

$("#searchForm").onsubmit = (e) => {
  e.preventDefault();
  const q = $("#searchInput").value.trim();
  if (q) location.hash = "#/search?q=" + encodeURIComponent(q);
};
$("#openPicker").onclick = openPicker;
$("#dateline").textContent = new Date().toLocaleDateString(undefined, { weekday: "long", day: "numeric", month: "long", year: "numeric" });

(async function start() {
  meta = await api("/meta");
  window.addEventListener("hashchange", route);
  route();
  if (!store.get("onboarded", false)) openPicker();
})();
