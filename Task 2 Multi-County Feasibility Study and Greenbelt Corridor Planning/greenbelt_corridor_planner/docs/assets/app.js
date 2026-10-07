/* SEEDS Greenbelt Corridor Planner — UI. Data: window.SEEDS_DATA (bundled preview) or ../data/*.json */
(async function () {
  "use strict";
  const E = window.SeedsEngine;
  const $ = (s) => document.querySelector(s);
  const el = (tag, attrs = {}, html = "") => {
    const n = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
    if (html) n.innerHTML = html;
    return n;
  };
  const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const fmt = (v, d = 1) => (v == null || !isFinite(v) ? "–" : Number(v).toLocaleString(undefined, { maximumFractionDigits: d, minimumFractionDigits: d }));

  // ---------------------------------------------------------------- data
  let DATA = window.SEEDS_DATA;
  if (!DATA) {
    const base = document.currentScript?.src ? new URL("../data/", document.currentScript.src) : "../data/";
    const [cells, config] = await Promise.all(
      ["cells.json", "config.json"].map((f) => fetch(new URL(f, base)).then((r) => r.json()))
    );
    DATA = { cells, config };
  }
  const C = DATA.cells, CFG = DATA.config;
  const N = C.h3.length;
  const idxOf = new Map(C.h3.map((h, i) => [h, i]));
  const center = C.h3.map((h) => h3.cellToLatLng(h));
  const area = C.h3.map((h) => h3.cellArea(h, "km2"));
  const nbrs = C.h3.map((h) =>
    Int32Array.from(h3.gridDisk(h, 1).filter((x) => x !== h && idxOf.has(x)).map((x) => idxOf.get(x)))
  );
  const critKeys = Object.keys(CFG.criteria).filter((k) => C.norm[k]);
  const hubs = (CFG.hubs || []).filter((h) => idxOf.has(h.cell)).map((h) => ({ ...h, idx: idxOf.get(h.cell) }));
  const hubById = Object.fromEntries(hubs.map((h) => [h.id, h]));
  if (C.meta?.demo) $("#demo-banner").hidden = false;

  // ---------------------------------------------------------------- state
  const firstScenario = Object.keys(CFG.scenarios)[0];
  const S = {
    scenario: firstScenario,
    weights: { ...CFG.scenarios[firstScenario].weights },
    view: "priority",
    county: "",
    hideProt: false,
    topOnly: false,
    mode: "network",
    hubsOn: new Set(hubs.filter((h) => h.type === "park").map((h) => h.id)),
    p2p: { from: null, to: null, clickNext: "from" },
    params: { ...CFG.corridor },
    opacity: 0.75,
  };
  let priority = new Float64Array(N), q80 = 1, corridor = { links: [], zone: new Set() };

  // ---------------------------------------------------------------- colour
  const RAMP = ["#f2efdc", "#d6e0a8", "#93c08a", "#4f9a7f", "#2a6e72", "#1b4462"];
  const rgb = RAMP.map((h) => [1, 3, 5].map((o) => parseInt(h.slice(o, o + 2), 16)));
  function ramp(t) {
    t = Math.min(1, Math.max(0, t)) * (rgb.length - 1);
    const i = Math.min(rgb.length - 2, Math.floor(t)), f = t - i, a = rgb[i], b = rgb[i + 1];
    return `rgb(${a.map((v, k) => Math.round(v + (b[k] - v) * f)).join(",")})`;
  }
  const tok = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

  // ---------------------------------------------------------------- map
  const map = L.map("map", { preferCanvas: true, zoomSnap: 0.25, attributionControl: true });
  const renderer = L.canvas({ padding: 0.4 });
  const BASEMAPS = {
    topo: ["https://basemap.nationalmap.gov/arcgis/rest/services/USGSTopo/MapServer/tile/{z}/{y}/{x}",
      { maxNativeZoom: 16, maxZoom: 18, attribution: "USGS The National Map" }],
    imagery: ["https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
      { maxZoom: 18, attribution: "Imagery © Esri, Maxar, Earthstar Geographics" }],
    osm: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png",
      { maxZoom: 18, attribution: "© OpenStreetMap contributors" }],
  };
  let baseLayer = null;
  function setBasemap(key) {
    if (baseLayer) map.removeLayer(baseLayer);
    baseLayer = BASEMAPS[key] ? L.tileLayer(BASEMAPS[key][0], { ...BASEMAPS[key][1], opacity: 0.85 }).addTo(map) : null;
  }

  // Earth Engine raster overlays (getMapId tile URLs written by the pipeline)
  map.createPane("ee").style.zIndex = 300;
  let eeLayer = null;
  const eeSel = $("#eelayer"), eeNote = $("#ee-note");
  (CFG.tiles || []).forEach((t) => eeSel.append(new Option(t.label, t.key)));
  if (!(CFG.tiles || []).length) eeSel.hidden = true;
  function setEE(key) {
    if (eeLayer) map.removeLayer(eeLayer);
    eeLayer = null;
    const t = (CFG.tiles || []).find((x) => x.key === key);
    $("#ee-op-row").hidden = !t;
    eeNote.hidden = !t;
    if (!t) return;
    eeLayer = L.tileLayer(t.url, { pane: "ee", maxZoom: 18, opacity: +$("#ee-opacity").value,
      attribution: "Google Earth Engine" }).addTo(map);
    const age = CFG.tiles_generated ? Math.round((Date.now() - Date.parse(CFG.tiles_generated)) / 36e5) : null;
    eeNote.textContent = `Tiles generated ${age != null ? age + " h ago" : ""}. If the layer is blank, the URLs have expired: run python -m seeds_cds tiles.`;
    let errs = 0;
    eeLayer.on("tileerror", () => { if (++errs === 4) eeNote.textContent = "Tiles failed to load. They have probably expired: run python -m seeds_cds tiles, then reload."; });
  }
  eeSel.addEventListener("change", () => setEE(eeSel.value));
  $("#ee-opacity").addEventListener("input", (e) => { $("#o-eeop").textContent = (+e.target.value).toFixed(2); eeLayer?.setOpacity(+e.target.value); });
  $("#o-eeop").textContent = "0.90";

  const hexLayer = L.layerGroup().addTo(map);
  const polys = C.h3.map((h, i) =>
    L.polygon(h3.cellToBoundary(h), { renderer, weight: 0.4, fillOpacity: S.opacity })
      .bindTooltip(() => tipHtml(i), { sticky: true, className: "cell-tip", direction: "top", offset: [0, -8] })
      .on("click", () => onCellClick(i))
      .addTo(hexLayer)
  );
  const outline = L.geoJSON(CFG.county_outline, { interactive: false, style: () => ({ weight: 1.6, fill: false }) }).addTo(map);
  const corrLayer = L.layerGroup().addTo(map);
  const hubLayer = L.layerGroup().addTo(map);
  hubs.forEach((h) => {
    L.circleMarker(center[h.idx], {
      radius: h.type === "park" ? 6 : 4.5, weight: 2, color: "#1d2a29",
      fillColor: h.type === "park" ? "#2e6a56" : "#ffffff", fillOpacity: 1,
    }).bindTooltip(`<b>${esc(h.name)}</b><br><span class="k">${h.type === "park" ? "Recreation hub" : "Gateway community"}</span>`,
      { className: "cell-tip", direction: "top", offset: [0, -6] })
      .on("click", () => onHubClick(h)).addTo(hubLayer);
  });
  map.fitBounds(outline.getBounds(), { padding: [12, 12] });

  // ---------------------------------------------------------------- UI build
  const groups = {};
  critKeys.forEach((k) => (groups[CFG.criteria[k].group] ||= []).push(k));
  const wBox = $("#weights");
  for (const [g, keys] of Object.entries(groups)) {
    const grp = el("div", { class: "grp" }, `<h4>${esc(g)}</h4>`);
    keys.forEach((k) => {
      const c = CFG.criteria[k];
      const row = el("div", { class: "wt", "data-k": k });
      row.innerHTML = `<label for="w-${k}"><span>${esc(c.label)}</span>
          <button class="eye" type="button" aria-pressed="false" title="Map this criterion" data-view="${k}">MAP</button></label>
        <output id="ow-${k}"></output>
        <input type="range" id="w-${k}" min="-100" max="100" step="5" aria-label="${esc(c.label)} weight">`;
      grp.append(row);
    });
    wBox.append(grp);
  }
  wBox.addEventListener("input", (e) => {
    if (e.target.type !== "range") return;
    const k = e.target.id.slice(2);
    S.weights[k] = +e.target.value;
    markCustom();
    syncWeightUI();
    schedule();
  });
  wBox.addEventListener("click", (e) => {
    const b = e.target.closest(".eye");
    if (!b) return;
    setView(S.view === b.dataset.view ? "priority" : b.dataset.view);
  });

  const scSel = $("#scenario");
  function fillScenarios(extra) {
    scSel.innerHTML = "";
    for (const [id, sc] of Object.entries(CFG.scenarios)) scSel.append(new Option(sc.label, id));
    if (extra) scSel.append(new Option(extra, "__custom"));
    scSel.value = extra ? "__custom" : S.scenario;
  }
  fillScenarios();
  scSel.addEventListener("change", () => {
    if (scSel.value === "__custom") return;
    S.scenario = scSel.value;
    S.weights = { ...CFG.scenarios[S.scenario].weights };
    fillScenarios();
    syncWeightUI();
    compute();
  });
  function markCustom(label = "Custom (edited)") {
    if (scSel.value !== "__custom") fillScenarios(label);
  }

  function syncWeightUI() {
    critKeys.forEach((k) => {
      const v = S.weights[k] || 0;
      $(`#w-${k}`).value = v;
      const o = $(`#ow-${k}`);
      o.textContent = (v > 0 ? "+" : "") + v;
      o.className = v > 0 ? "pos" : v < 0 ? "neg" : "zero";
      o.closest(".wt").classList.toggle("is-neg", v < 0);
    });
    document.querySelectorAll(".eye").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.view === S.view)));
  }

  // view select
  const viewSel = $("#view");
  viewSel.append(new Option("Composite priority", "priority"));
  critKeys.forEach((k) => viewSel.append(new Option(CFG.criteria[k].label, k)));
  viewSel.append(new Option("Protected land (%)", "__protected"));
  viewSel.addEventListener("change", () => setView(viewSel.value));
  function setView(v) {
    S.view = v;
    viewSel.value = v;
    syncWeightUI();
    restyle();
    legend();
  }

  // filters
  const cf = $("#county-filter");
  C.counties.forEach((c, i) => cf.append(new Option(`${c.name}, ${c.state}`, String(i))));
  cf.addEventListener("change", () => { S.county = cf.value; restyle(); });
  $("#hide-protected").addEventListener("change", (e) => { S.hideProt = e.target.checked; restyle(); });
  $("#top-only").addEventListener("change", (e) => { S.topOnly = e.target.checked; restyle(); });
  $("#opacity").addEventListener("input", (e) => { S.opacity = +e.target.value; $("#o-op").textContent = S.opacity.toFixed(2); restyle(); });
  $("#o-op").textContent = S.opacity.toFixed(2);
  const bm = $("#basemap");
  bm.value = window.SEEDS_PREVIEW ? "none" : "topo";
  bm.addEventListener("change", () => { setBasemap(bm.value); restyle(); });
  setBasemap(bm.value);

  // tabs
  const tabs = [...document.querySelectorAll('[role="tab"]')];
  function selectTab(id) {
    tabs.forEach((t) => {
      const on = t.id === id;
      t.setAttribute("aria-selected", String(on));
      document.getElementById(t.getAttribute("aria-controls")).hidden = !on;
    });
  }
  tabs.forEach((t) => t.addEventListener("click", () => selectTab(t.id)));
  $("#nav-method").addEventListener("click", (e) => { e.preventDefault(); selectTab("t-ai"); $("#method").scrollIntoView({ behavior: "smooth" }); });
  if (location.hash === "#method") selectTab("t-ai");

  // corridor controls
  document.querySelectorAll("#mode button").forEach((b) =>
    b.addEventListener("click", () => {
      S.mode = b.dataset.mode;
      document.querySelectorAll("#mode button").forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
      $("#network-ctl").hidden = S.mode !== "network";
      $("#p2p-ctl").hidden = S.mode !== "p2p";
      modeHint();
      runCorridors();
    })
  );
  function modeHint() {
    $("#mode-hint").textContent = S.mode === "network"
      ? "Links every selected hub with the cheapest set of least-cost paths (a minimum spanning tree)."
      : "Finds the single least-cost path between two hubs or two map points.";
  }
  modeHint();

  const hubList = $("#hub-list");
  for (const [type, title] of [["park", "Recreation hubs"], ["gateway", "Gateway communities"]]) {
    const h5 = el("h5", {}, `${title} <button type="button" data-all="${type}">all</button><button type="button" data-none="${type}">none</button>`);
    hubList.append(h5);
    hubs.filter((h) => h.type === type).forEach((h) => {
      const lab = el("label", { class: "chk" });
      lab.innerHTML = `<input type="checkbox" id="hub-${h.id}" value="${h.id}" ${S.hubsOn.has(h.id) ? "checked" : ""}> ${esc(h.name)}`;
      hubList.append(lab);
    });
  }
  hubList.addEventListener("change", (e) => {
    if (e.target.type !== "checkbox") return;
    e.target.checked ? S.hubsOn.add(e.target.value) : S.hubsOn.delete(e.target.value);
    runCorridors();
  });
  hubList.addEventListener("click", (e) => {
    const t = e.target.dataset.all || e.target.dataset.none;
    if (!t) return;
    hubs.filter((h) => h.type === t).forEach((h) => {
      e.target.dataset.all ? S.hubsOn.add(h.id) : S.hubsOn.delete(h.id);
      $(`#hub-${h.id}`).checked = S.hubsOn.has(h.id);
    });
    runCorridors();
  });

  const fromSel = $("#p2p-from"), toSel = $("#p2p-to");
  function fillP2P() {
    for (const [sel, key, ph] of [[fromSel, "from", "Start"], [toSel, "to", "End"]]) {
      sel.innerHTML = "";
      sel.append(new Option(`${ph}: choose a hub…`, ""));
      const cur = S.p2p[key];
      if (cur && cur.custom) sel.append(new Option(`${ph}: map point (${cur.label})`, "__pt"));
      hubs.forEach((h) => sel.append(new Option(`${ph}: ${h.name}`, h.id)));
      sel.value = cur ? (cur.custom ? "__pt" : cur.id) : "";
    }
  }
  S.p2p.from = hubById.fall_creek_falls || hubs[0] || null;
  S.p2p.to = hubById.monte_sano || hubs[1] || null;
  fillP2P();
  fromSel.addEventListener("change", () => { S.p2p.from = hubById[fromSel.value] || null; runCorridors(); });
  toSel.addEventListener("change", () => { S.p2p.to = hubById[toSel.value] || null; runCorridors(); });

  const paramUI = [["c-exp", "o-exp", "cost_exponent", (v) => v.toFixed(1)],
    ["c-disc", "o-disc", "protected_discount", (v) => `${Math.round(v * 100)}%`],
    ["c-bar", "o-bar", "development_barrier", (v) => (v >= 1 ? "off" : `${Math.round(v * 100)}th pct`)],
    ["c-ring", "o-ring", "zone_rings", (v) => String(v)]];
  paramUI.forEach(([i, o, k, f]) => {
    const inp = $("#" + i);
    inp.value = S.params[k];
    $("#" + o).textContent = f(+S.params[k]);
    inp.addEventListener("input", () => { S.params[k] = +inp.value; $("#" + o).textContent = f(+inp.value); scheduleCorr(); });
  });

  function onHubClick(h) {
    if (S.mode !== "p2p") return;
    S.p2p[S.p2p.clickNext] = h;
    S.p2p.clickNext = S.p2p.clickNext === "from" ? "to" : "from";
    fillP2P();
    runCorridors();
  }
  function onCellClick(i) {
    if (S.mode !== "p2p") return;
    const pt = { custom: true, idx: i, id: "__pt", name: `Map point in ${C.counties[C.county[i]].name}`, label: C.counties[C.county[i]].name };
    S.p2p[S.p2p.clickNext] = pt;
    S.p2p.clickNext = S.p2p.clickNext === "from" ? "to" : "from";
    status(S.p2p.clickNext === "to" ? "Start set. Click a second cell for the end." : null);
    fillP2P();
    runCorridors();
  }
  function status(msg) {
    const s = $("#status");
    s.hidden = !msg;
    s.textContent = msg || "";
  }

  // ---------------------------------------------------------------- compute
  let t1 = 0, t2 = 0;
  const schedule = () => { cancelAnimationFrame(t1); t1 = requestAnimationFrame(compute); };
  const scheduleCorr = () => { clearTimeout(t2); t2 = setTimeout(runCorridors, 60); };

  function compute() {
    priority = E.composite(C.norm, S.weights, N);
    const s = Float64Array.from(priority).sort();
    q80 = s[Math.floor(0.8 * (N - 1))];
    restyle();
    runCorridors();
  }

  function value(i) {
    if (S.view === "priority") return priority[i];
    if (S.view === "__protected") return C.protected[i] / 100;
    return C.norm[S.view][i] / 100;
  }

  function restyle() {
    const stroke = bm.value === "none" ? tok("--bg") : "#ffffff";
    for (let i = 0; i < N; i++) {
      const hide = (S.county !== "" && String(C.county[i]) !== S.county)
        || (S.hideProt && C.protected[i] > 50)
        || (S.topOnly && priority[i] < q80);
      polys[i].setStyle(hide
        ? { fillOpacity: 0, opacity: 0 }
        : { fillColor: ramp(value(i)), fillOpacity: S.opacity, color: stroke, opacity: Math.min(0.6, S.opacity), weight: 0.4 });
    }
    outline.setStyle({ color: bm.value === "imagery" ? "#ffffff" : tok("--ink"), opacity: 0.9 });
  }

  function ringZone(paths, k) {
    const zone = new Set(paths.flat());
    let frontier = [...zone];
    for (let r = 0; r < k; r++) {
      const nx = [];
      frontier.forEach((u) => nbrs[u].forEach((v) => { if (!zone.has(v)) { zone.add(v); nx.push(v); } }));
      frontier = nx;
    }
    return zone;
  }
  const pathKm = (p) => p.slice(1).reduce((s, v, j) => s + E.haversineKm(center[p[j]], center[v]), 0);
  const meanP = (cells) => (cells.length ? cells.reduce((s, i) => s + priority[i], 0) / cells.length : NaN);

  function runCorridors() {
    const cost = E.cellCost(priority, C.protected, C.norm.development, S.params);
    let links = [];
    if (S.mode === "network") {
      const sel = hubs.filter((h) => S.hubsOn.has(h.id));
      // several hubs can snap to one cell; keep the first
      const seen = new Set(), uniq = sel.filter((h) => !seen.has(h.idx) && seen.add(h.idx));
      links = uniq.length > 1 ? E.greenbelt(nbrs, cost, uniq) : [];
      links.forEach((l) => { l.fromName = hubById[l.from].name; l.toName = hubById[l.to].name; });
    } else if (S.p2p.from && S.p2p.to && S.p2p.from.idx !== S.p2p.to.idx) {
      const r = E.dijkstra(nbrs, cost, S.p2p.from.idx);
      const path = E.trace(r.prev, S.p2p.from.idx, S.p2p.to.idx);
      if (path.length) links = [{ fromName: S.p2p.from.name, toName: S.p2p.to.name, cost: r.dist[S.p2p.to.idx], path }];
    }
    links.forEach((l) => { l.km = pathKm(l.path); l.meanP = meanP(l.path); });
    corridor = { links, zone: ringZone(links.map((l) => l.path), S.params.zone_rings) };
    drawCorridors();
    corridorPanel();
    countyTable();
  }

  // ---------------------------------------------------------------- render
  function drawCorridors() {
    corrLayer.clearLayers();
    const acc = tok("--accent");
    corridor.zone.forEach((i) =>
      L.polygon(h3.cellToBoundary(C.h3[i]), { renderer, interactive: false, fill: false, color: acc, weight: 1.2, opacity: 0.75 }).addTo(corrLayer)
    );
    corridor.links.forEach((l) => {
      const ll = l.path.map((i) => center[i]);
      L.polyline(ll, { renderer, interactive: false, color: "#ffffff", weight: 7, opacity: 0.9 }).addTo(corrLayer);
      L.polyline(ll, { renderer, interactive: false, color: acc, weight: 3.5, opacity: 1 }).addTo(corrLayer);
    });
    hubLayer.bringToFront?.();
  }

  function candidates() {
    return [...corridor.zone].filter((i) => C.protected[i] < 50).sort((a, b) => priority[b] - priority[a]);
  }

  function corridorPanel() {
    const z = [...corridor.zone];
    const km = corridor.links.reduce((s, l) => s + l.km, 0);
    const zArea = z.reduce((s, i) => s + area[i], 0);
    const protArea = z.reduce((s, i) => s + area[i] * C.protected[i] / 100, 0);
    const cands = candidates();
    $("#corr-stats").innerHTML = [
      [fmt(km, 0) + " km", "Corridor length"],
      [String(corridor.links.length), corridor.links.length === 1 ? "Link" : "Links"],
      [fmt(zArea, 0) + " km²", "Corridor zone"],
      [zArea ? fmt(100 * protArea / zArea, 0) + "%" : "–", "Already protected"],
      [fmt(meanP(z), 2), "Mean priority in zone"],
      [String(cands.length), "Candidate cells"],
    ].map(([b, s]) => `<div class="stat"><b>${b}</b><span>${s}</span></div>`).join("");

    $("#links").innerHTML = corridor.links.length
      ? `<thead><tr><th>From → to</th><th class="n">km</th><th class="n">Prio</th></tr></thead><tbody>${corridor.links
        .map((l) => `<tr><td>${esc(l.fromName)} → ${esc(l.toName)}</td><td class="n">${fmt(l.km, 0)}</td><td class="n">${fmt(l.meanP, 2)}</td></tr>`).join("")}</tbody>`
      : `<tbody><tr><td>${S.mode === "network" ? "Select at least two hubs." : "Choose a start and an end."}</td></tr></tbody>`;

    $("#cands").innerHTML = cands.length
      ? `<thead><tr><th>County</th><th class="n">Prio</th><th class="n">Prot.</th><th></th></tr></thead><tbody>${cands.slice(0, 15)
        .map((i) => `<tr><td>${esc(C.counties[C.county[i]].name)}, ${C.counties[C.county[i]].state}</td><td class="n">${fmt(priority[i], 2)}</td><td class="n">${C.protected[i]}%</td><td><button class="btn" data-zoom="${i}" type="button">Zoom</button></td></tr>`).join("")}</tbody>`
      : "<tbody><tr><td>No unprotected cells in the corridor zone.</td></tr></tbody>";
  }
  $("#cands").addEventListener("click", (e) => {
    const i = e.target.dataset.zoom;
    if (i == null) return;
    map.flyTo(center[+i], 12, { duration: 0.6 });
    polys[+i].openTooltip(center[+i]);
  });

  function countyTable() {
    const agg = C.counties.map(() => ({ n: 0, sum: 0, top: 0, corr: 0 }));
    for (let i = 0; i < N; i++) {
      const a = agg[C.county[i]];
      a.n++; a.sum += priority[i]; if (priority[i] >= q80) a.top++; if (corridor.zone.has(i)) a.corr++;
    }
    const rows = C.counties.map((c, j) => ({ c, ...agg[j], mean: agg[j].sum / agg[j].n }))
      .sort((a, b) => b.mean - a.mean);
    $("#county-tbl").innerHTML = `<thead><tr><th>County</th><th>ARC</th><th class="n">Mean</th><th class="n">Top 20%</th><th class="n">Corridor</th></tr></thead><tbody>${rows
      .map((r) => `<tr><td>${esc(r.c.name)}, ${r.c.state}</td><td><span class="pill ${esc(r.c.arc_status)}">${esc(r.c.arc_status)}</span></td><td class="n">${fmt(r.mean, 2)}</td><td class="n">${fmt(100 * r.top / r.n, 0)}%</td><td class="n">${r.corr}</td></tr>`).join("")}</tbody>`;
  }

  function rawFmt(k, v) {
    if (v == null) return "no data";
    const u = CFG.criteria[k].unit;
    if (u === "%") return fmt(v * 100, 1) + "%";
    if (u === "km") return fmt(v, 1) + " km";
    if (u === "m") return fmt(v, 0) + " m";
    return fmt(v, 2);
  }
  function tipHtml(i) {
    const c = C.counties[C.county[i]];
    const top = E.contributions(C.norm, S.weights, i).slice(0, 5);
    const rows = top.map((t) => `<tr><td>${esc(CFG.criteria[t.key].label)}</td><td class="k">${rawFmt(t.key, C.raw[t.key]?.[i])}</td><td style="color:var(${t.v < 0 ? "--ochre" : "--forest"})">${t.v >= 0 ? "+" : ""}${fmt(t.v * 100, 0)}</td></tr>`).join("");
    const view = S.view !== "priority" && S.view !== "__protected"
      ? `<div><span class="k">${esc(CFG.criteria[S.view].label)}:</span> ${rawFmt(S.view, C.raw[S.view]?.[i])} · pct ${C.norm[S.view][i]}</div>` : "";
    return `<b>${esc(c.name)} Co., ${c.state}</b> <span class="pill ${esc(c.arc_status)}">${esc(c.arc_status)}</span>
      <div><span class="k">Priority</span> <b>${fmt(priority[i], 2)}</b> · <span class="k">protected</span> ${C.protected[i]}%${corridor.zone.has(i) ? ' · <span style="color:var(--accent)">in corridor</span>' : ""}</div>
      ${view}<table>${rows}</table>`;
  }

  function legend() {
    const title = S.view === "priority" ? "Composite priority"
      : S.view === "__protected" ? "Protected land" : CFG.criteria[S.view].label;
    const ticks = S.view === "priority" ? ["0 low", "0.5", "1 high"]
      : S.view === "__protected" ? ["0%", "50%", "100%"] : ["0 pct", "50", "100 pct"];
    $("#legend").innerHTML = `<div class="ttl">${esc(title)}</div>
      <div class="ramp" style="background:linear-gradient(90deg,${RAMP.join(",")})"></div>
      <div class="ticks">${ticks.map((t) => `<span>${t}</span>`).join("")}</div>
      <div class="keys"><span><i class="sw"></i>Corridor</span><span><i class="dot park"></i>Rec hub</span><span><i class="dot gate"></i>Gateway</span></div>`;
  }

  function aiPanel() {
    const ai = CFG.ai || {};
    $("#ai-stats").innerHTML = [
      [ai.auc != null ? fmt(ai.auc, 3) : "–", "Holdout AUC"],
      [ai.n_test ? String(ai.n_test) : "–", "Test samples"],
      [esc(CFG.protected_source || "–"), "Training labels"],
      [C.meta?.res != null ? `H3 r${C.meta.res}` : "–", `${N.toLocaleString()} cells`],
    ].map(([b, s]) => `<div class="stat"><b style="font-size:${b.length > 12 ? 15 : 22}px">${b}</b><span>${s}</span></div>`).join("");
    const imp = Object.entries(ai.importance || {});
    const mx = Math.max(...imp.map(([, v]) => v), 1e-9);
    $("#ai-imp").innerHTML = imp.length
      ? imp.map(([k, v]) => `<div class="barrow"><span>${esc(k.replace(/_/g, " "))}</span><i style="width:${(100 * v / mx).toFixed(1)}%"></i><span class="n">${fmt(100 * v, 0)}%</span></div>`).join("")
        + (ai.note ? `<p class="hint">${esc(ai.note)}</p>` : "")
      : '<p class="hint">Geo-AI model was not run for this build.</p>';
  }

  // ---------------------------------------------------------------- import / export
  function download(name, text, type) {
    const a = el("a", { href: URL.createObjectURL(new Blob([text], { type })), download: name });
    document.body.append(a); a.click(); a.remove();
  }
  const ring = (i) => { const b = h3.cellToBoundary(C.h3[i], true); return [[...b, b[0]]]; };
  $("#dl-cells").addEventListener("click", () => {
    const features = C.h3.map((h, i) => ({
      type: "Feature", geometry: { type: "Polygon", coordinates: ring(i) },
      properties: { h3: h, county: C.counties[C.county[i]].name, state: C.counties[C.county[i]].state,
        priority: +priority[i].toFixed(4), protected_pct: C.protected[i], in_corridor: corridor.zone.has(i) ? 1 : 0,
        ...Object.fromEntries(critKeys.map((k) => [`pct_${k}`, C.norm[k][i]])) },
    }));
    download("seeds_priority_cells.geojson", JSON.stringify({ type: "FeatureCollection", features, properties: { weights: S.weights } }), "application/geo+json");
  });
  $("#dl-corr").addEventListener("click", () => {
    const features = corridor.links.map((l) => ({
      type: "Feature", geometry: { type: "LineString", coordinates: l.path.map((i) => [center[i][1], center[i][0]]) },
      properties: { from: l.fromName, to: l.toName, km: +l.km.toFixed(2), mean_priority: +l.meanP.toFixed(4), cost: +l.cost.toFixed(4) },
    }));
    download("seeds_greenbelt_corridor.geojson", JSON.stringify({ type: "FeatureCollection", features, properties: { weights: S.weights, corridor: S.params } }), "application/geo+json");
  });
  $("#dl-cands").addEventListener("click", () => {
    const lines = ["h3,county,state,lat,lon,priority,protected_pct"].concat(
      candidates().map((i) => [C.h3[i], C.counties[C.county[i]].name, C.counties[C.county[i]].state,
        center[i][0].toFixed(5), center[i][1].toFixed(5), priority[i].toFixed(4), C.protected[i]].join(","))
    );
    download("seeds_corridor_candidates.csv", lines.join("\n"), "text/csv");
  });
  $("#export-weights").addEventListener("click", () =>
    download("seeds_weights.json", JSON.stringify({ scenario: scSel.options[scSel.selectedIndex].text, weights: S.weights,
      corridor: S.params, generated: new Date().toISOString() }, null, 2), "application/json"));
  $("#import-weights").addEventListener("change", async (e) => {
    const f = e.target.files[0];
    if (!f) return;
    try {
      const j = JSON.parse(await f.text());
      const w = j.weights || j;
      const known = Object.keys(w).filter((k) => critKeys.includes(k) && isFinite(+w[k]));
      const unknown = Object.keys(w).filter((k) => !critKeys.includes(k));
      if (!known.length) throw new Error("no recognized criterion keys");
      const mx = Math.max(...known.map((k) => Math.abs(+w[k])));
      S.weights = Object.fromEntries(known.map((k) => [k, Math.round((+w[k] / mx) * 100 / 5) * 5]));
      if (j.corridor) Object.assign(S.params, j.corridor);
      fillScenarios(`Imported: ${j.scenario || f.name}`);
      $("#weights-note").textContent = `Loaded ${known.length} weights from ${f.name}.` +
        (unknown.length ? ` Ignored unknown keys: ${unknown.join(", ")}.` : "");
      syncWeightUI();
      compute();
    } catch (err) {
      $("#weights-note").textContent = `Could not read ${f.name}: ${err.message}. Expected JSON like {"weights": {"forest_cover": 20, "development": -15}}.`;
    }
    e.target.value = "";
  });

  // theme changes re-read tokens
  window.matchMedia("(prefers-color-scheme: dark)").addEventListener?.("change", () => { restyle(); drawCorridors(); });
  new MutationObserver(() => { restyle(); drawCorridors(); }).observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });

  // ---------------------------------------------------------------- go
  syncWeightUI();
  legend();
  aiPanel();
  compute();
})();
