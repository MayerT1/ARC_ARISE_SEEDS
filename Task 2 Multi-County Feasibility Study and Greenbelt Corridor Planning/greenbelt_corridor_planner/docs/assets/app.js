/* SEEDS Greenbelt Corridor Planner — UI.
   Data: window.SEEDS_DATA (bundled preview) or ../data/{cells,config,network,padus,parcels}.json */
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
  const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const fmt = (v, d = 1) => (v == null || !isFinite(v) ? "–" : Number(v).toLocaleString(undefined, { maximumFractionDigits: d, minimumFractionDigits: d }));
  const tok = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

  // ---------------------------------------------------------------- data
  let DATA = window.SEEDS_DATA;
  if (!DATA) {
    const base = new URL("../data/", document.currentScript?.src || location.href);
    const get = (f, optional) => fetch(new URL(f, base)).then((r) => (r.ok ? r.json() : optional ? null : Promise.reject(f)))
      .catch((e) => (optional ? null : Promise.reject(e)));
    const [cells, config, network, padus, parcels] = await Promise.all([
      get("cells.json"), get("config.json"), get("network.json", true), get("padus.json", true), get("parcels.json", true)]);
    DATA = { cells, config, network, padus, parcels };
  }
  const C = DATA.cells, CFG = DATA.config, NET = DATA.network, PADUS = DATA.padus?.features || [];
  const WEB = CFG.web || {};
  const N = C.h3.length;
  const idxOf = new Map(C.h3.map((h, i) => [h, i]));
  const res = C.meta?.res ?? h3.getResolution(C.h3[0]);
  const center = C.h3.map((h) => h3.cellToLatLng(h));
  const hexNbrs = C.h3.map((h) => h3.gridDisk(h, 1).filter((x) => x !== h && idxOf.has(x)).map((x) => idxOf.get(x)));
  const critKeys = Object.keys(CFG.criteria).filter((k) => C.norm[k]);
  const hexOf = (lat, lon) => idxOf.get(h3.latLngToCell(lat, lon, res)) ?? -1;
  const hubs = (CFG.hubs || []).filter((h) => idxOf.has(h.cell)).map((h) => ({ ...h, hex: idxOf.get(h.cell) }));
  const hubById = Object.fromEntries(hubs.map((h) => [h.id, h]));
  if (C.meta?.demo) $("#demo-banner").hidden = false;
  if (WEB.repo) $("#nav-factsheet").href = `https://github.com/${WEB.repo}/blob/main/Task%202%20Multi-County%20Feasibility%20Study%20and%20Greenbelt%20Corridor%20Planning/greenbelt_corridor_planner/FACT_SHEET.md`;
  else $("#nav-factsheet").hidden = true;

  // network decode (lazy geometry)
  const G = E.buildGraph(center, hexNbrs, NET);
  const netGeom = NET ? new Array(NET.edges.u.length) : [];
  const geomOf = (i) => (netGeom[i] ||= E.decodePolyline(NET.edges.geom[i]));
  const netCls = (i) => NET.classes[NET.edges.cls[i]];
  const TRAILISH = new Set(["greenway", "trail"]);

  // ---------------------------------------------------------------- state
  const firstScenario = Object.keys(CFG.scenarios)[0];
  const P0 = CFG.corridor || {};
  const S = {
    scenario: firstScenario,
    weights: { ...CFG.scenarios[firstScenario].weights },
    view: "priority", county: "", hideProt: false, topOnly: false,
    mode: "network",
    hubsOn: new Set(hubs.filter((h) => h.type === "park").map((h) => h.id)),
    p2p: { from: null, to: null, clickNext: "from" },
    P: { ...P0, cost: { ...(P0.cost || {}) } },
    opacity: 0.6,
    layers: { trails: true, roads: true, walk: false, padus: true, parcels: false, planned: true, hexes: true, feedback: true },
  };
  let priority = new Float64Array(N), q80 = 1, lr = null;
  let corridor = { links: [], segs: [], zone: new Set(), gaps: [] };
  let parcelRows = [];

  // ---------------------------------------------------------------- colour
  const RAMP = ["#f2efdc", "#d6e0a8", "#93c08a", "#4f9a7f", "#2a6e72", "#1b4462"];
  const rgb = RAMP.map((h) => [1, 3, 5].map((o) => parseInt(h.slice(o, o + 2), 16)));
  function ramp(t) {
    t = Math.min(1, Math.max(0, t)) * (rgb.length - 1);
    const i = Math.min(rgb.length - 2, Math.floor(t)), f = t - i, a = rgb[i], b = rgb[i + 1];
    return `rgb(${a.map((v, k) => Math.round(v + (b[k] - v) * f)).join(",")})`;
  }
  const NET_STYLE = {
    greenway: () => ({ color: tok("--greenway"), weight: 3, opacity: 0.95 }),
    trail: () => ({ color: tok("--trail"), weight: 2.4, opacity: 0.95, dashArray: "5 3" }),
    sidewalk: () => ({ color: tok("--street"), weight: 1, opacity: 0.7 }),
    road_local: () => ({ color: tok("--street"), weight: 1, opacity: 0.55 }),
    road_collector: () => ({ color: tok("--street"), weight: 1.8, opacity: 0.7 }),
    road_arterial: () => ({ color: tok("--street"), weight: 2.6, opacity: 0.8 }),
  };

  // ---------------------------------------------------------------- map + panes
  const map = L.map("map", { preferCanvas: true, zoomSnap: 0.25, attributionControl: true });
  [["ee", 250], ["hex", 300], ["land", 350], ["net", 420], ["corr", 450], ["hubs", 600]].forEach(([n, z]) => (map.createPane(n).style.zIndex = z));
  const R = (pane) => L.canvas({ padding: 0.4, pane });
  const rHex = R("hex"), rLand = R("land"), rNet = R("net"), rCorr = R("corr");
  const BASEMAPS = {
    topo: ["https://basemap.nationalmap.gov/arcgis/rest/services/USGSTopo/MapServer/tile/{z}/{y}/{x}", { maxNativeZoom: 16, maxZoom: 19, attribution: "USGS The National Map" }],
    imagery: ["https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}", { maxZoom: 19, attribution: "Imagery © Esri, Maxar, Earthstar Geographics" }],
    osm: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png", { maxZoom: 19, attribution: "© OpenStreetMap contributors" }],
  };
  let baseLayer = null;
  function setBasemap(key) {
    if (baseLayer) map.removeLayer(baseLayer);
    baseLayer = BASEMAPS[key] ? L.tileLayer(BASEMAPS[key][0], { ...BASEMAPS[key][1], opacity: 0.85 }).addTo(map) : null;
  }

  // Earth Engine overlays
  let eeLayer = null;
  const eeSel = $("#eelayer"), eeNote = $("#ee-note");
  (CFG.tiles || []).forEach((t) => eeSel.append(new Option(t.label, t.key)));
  if (!(CFG.tiles || []).length) eeSel.hidden = true;
  function setEE(key) {
    if (eeLayer) map.removeLayer(eeLayer);
    eeLayer = null;
    const t = (CFG.tiles || []).find((x) => x.key === key);
    $("#ee-op-row").hidden = !t; eeNote.hidden = !t;
    if (!t) return;
    eeLayer = L.tileLayer(t.url, { pane: "ee", maxZoom: 19, opacity: +$("#ee-opacity").value, attribution: "Google Earth Engine" }).addTo(map);
    const age = CFG.tiles_generated ? Math.round((Date.now() - Date.parse(CFG.tiles_generated)) / 36e5) : null;
    eeNote.textContent = `Tiles generated ${age != null ? age + " h ago" : ""}. If the layer is blank the URLs have expired: run python -m seeds_cds tiles.`;
    let errs = 0;
    eeLayer.on("tileerror", () => { if (++errs === 4) eeNote.textContent = "Tiles failed to load. They have probably expired: run python -m seeds_cds tiles, then reload."; });
  }
  eeSel.addEventListener("change", () => setEE(eeSel.value));
  $("#ee-opacity").addEventListener("input", (e) => { $("#o-eeop").textContent = (+e.target.value).toFixed(2); eeLayer?.setOpacity(+e.target.value); });
  $("#o-eeop").textContent = "0.90";

  // hexes
  const hexLayer = L.layerGroup().addTo(map);
  const polys = C.h3.map((h, i) =>
    L.polygon(h3.cellToBoundary(h), { renderer: rHex, weight: 0.4, fillOpacity: S.opacity })
      .bindTooltip(() => tipHtml(i), { sticky: true, className: "cell-tip", direction: "top", offset: [0, -8] })
      .on("click", (ev) => onMapClick(ev.latlng, i))
      .addTo(hexLayer));
  const outline = L.geoJSON(CFG.county_outline, { interactive: false, pane: "net", style: () => ({ weight: 1.6, fill: false }) }).addTo(map);

  // existing network: trails always drawn, streets by view at zoom >= road_min_zoom
  const trailLayer = L.layerGroup().addTo(map), roadLayer = L.layerGroup().addTo(map);
  const plannedLayer = L.layerGroup().addTo(map), walkLayer = L.layerGroup(), padusLayer = L.layerGroup().addTo(map);
  const parcelLayer = L.layerGroup(), fbLayer = L.layerGroup().addTo(map);
  const edgeName = (i) => NET.names[NET.edges.name[i]] || "";
  const edgeSrc = (i) => (NET.sources[NET.edges.src[i]] || []).join(", ");
  function netTip(i) {
    const c = netCls(i), nm = edgeName(i);
    return `<b>${esc(nm || c.replace("_", " "))}</b><br><span class="k">${esc(c.replace("_", " "))} · ${fmt(NET.edges.km[i], 2)} km · ${esc(edgeSrc(i))}</span>`;
  }
  let roadBoxes = null;
  function drawTrails() {
    trailLayer.clearLayers();
    if (!NET || !S.layers.trails) return;
    for (let i = 0; i < NET.edges.u.length; i++) {
      const c = netCls(i);
      if (!TRAILISH.has(c)) continue;
      L.polyline(geomOf(i), { renderer: rNet, ...NET_STYLE[c]() })
        .bindTooltip(() => netTip(i), { sticky: true, className: "cell-tip" }).addTo(trailLayer);
    }
  }
  function drawRoads() {
    roadLayer.clearLayers();
    if (!NET || !S.layers.roads || map.getZoom() < (WEB.road_min_zoom ?? 12)) return;
    if (!roadBoxes) {
      roadBoxes = [];
      for (let i = 0; i < NET.edges.u.length; i++) {
        if (TRAILISH.has(netCls(i))) continue;
        const g = geomOf(i); let a = 90, b = 180, c = -90, d = -180;
        for (const [la, lo] of g) { if (la < a) a = la; if (lo < b) b = lo; if (la > c) c = la; if (lo > d) d = lo; }
        roadBoxes.push([i, a, b, c, d]);
      }
    }
    const bb = map.getBounds().pad(0.2), s = bb.getSouth(), w = bb.getWest(), n = bb.getNorth(), e = bb.getEast();
    for (const [i, a, b, c, d] of roadBoxes) {
      if (c < s || a > n || d < w || b > e) continue;
      L.polyline(geomOf(i), { renderer: rNet, ...NET_STYLE[netCls(i)]() })
        .bindTooltip(() => netTip(i), { sticky: true, className: "cell-tip" }).addTo(roadLayer);
    }
  }
  function drawPlanned() {
    plannedLayer.clearLayers();
    if (!NET?.planned?.length || !S.layers.planned) return;
    for (const p of NET.planned)
      L.polyline(E.decodePolyline(p.geom), { renderer: rNet, color: tok("--greenway"), weight: 3, opacity: 0.8, dashArray: "1 6" })
        .bindTooltip(`<b>${esc(p.name || "Planned trail")}</b><br><span class="k">planned · ${esc(p.source)}</span>`, { sticky: true, className: "cell-tip" })
        .addTo(plannedLayer);
  }
  function drawWalk() {
    walkLayer.clearLayers();
    for (const w of NET?.walkable || [])
      L.circleMarker([w.lat, w.lon], { renderer: rNet, radius: 3.5, weight: 1, color: tok("--ink"), fillColor: tok("--greenway"), fillOpacity: 0.9 })
        .bindTooltip(`<b>${esc(w.name || "Unnamed " + w.kind)}</b><br><span class="k">${esc(w.kind.replace("_", " "))}</span>`, { className: "cell-tip" })
        .addTo(walkLayer);
  }
  const padusName = (p) => p.Unit_Nm || p.Loc_Nm || "Protected area";
  function padusTip(p) {
    return `<b>${esc(padusName(p))}</b><br><span class="k">Owner</span> ${esc(p.Own_Name || p.Loc_Own || "–")} (${esc(p.Own_Type || "–")})<br>
      <span class="k">Manager</span> ${esc(p.Mang_Name || p.Loc_Mang || "–")}<br><span class="k">${esc(p.Category || "")} · GAP ${esc(p.GAP_Sts || "–")} · access ${esc(p.Pub_Access || "–")}${p.GIS_Acres ? " · " + fmt(p.GIS_Acres, 0) + " ac" : ""}</span>`;
  }
  function drawPadus() {
    padusLayer.clearLayers();
    if (!S.layers.padus) return;
    L.geoJSON({ type: "FeatureCollection", features: PADUS }, {
      renderer: rLand,
      style: (f) => ({ color: tok("--land"), weight: 1, fillColor: tok("--land"), fillOpacity: f.properties.Category === "Easement" ? 0.08 : 0.18, dashArray: f.properties.Category === "Easement" ? "4 3" : null }),
      onEachFeature: (f, l) => l.bindTooltip(() => padusTip(f.properties), { sticky: true, className: "cell-tip" }),
    }).addTo(padusLayer);
  }

  // hubs
  const hubLayer = L.layerGroup().addTo(map);
  hubs.forEach((h) => {
    L.circleMarker([h.lat, h.lon], { pane: "hubs", radius: h.type === "park" ? 6.5 : 4.5, weight: 2, color: "#1d2a29",
      fillColor: h.type === "park" ? "#2e6a56" : "#ffffff", fillOpacity: 1 })
      .bindTooltip(`<b>${esc(h.name)}</b><br><span class="k">${h.type === "park" ? "Recreation hub" : "Gateway community"}</span>`,
        { className: "cell-tip", direction: "top", offset: [0, -6] })
      .on("click", () => onHubClick(h)).addTo(hubLayer);
  });
  const corrLayer = L.layerGroup().addTo(map);
  map.fitBounds(outline.getBounds(), { padding: [12, 12] });
  // keep the map sized to its container (tabs, banner, window and panel changes never distort it)
  new ResizeObserver(() => map.invalidateSize({ pan: false })).observe(document.getElementById("map"));
  map.on("zoomend moveend", () => { drawRoads(); if (S.layers.parcels) scheduleParcelView(); layerHints(); });
  map.on("click", (ev) => { if (fbPicking) onMapClick(ev.latlng, hexOf(ev.latlng.lat, ev.latlng.lng)); });

  // ---------------------------------------------------------------- layer list
  const LAYERS = [
    ["hexes", "Priority hexes"], ["trails", "Existing trails & greenways"], ["roads", "Sidewalks & streets"],
    ["planned", "Planned trails"], ["walk", "Parks & walkable spaces"], ["padus", "Public & protected land"],
    ["parcels", "Parcels (live)"], ["feedback", "Feedback pins"],
  ];
  const layerList = $("#layer-list");
  LAYERS.forEach(([k, label]) => {
    const lab = el("label", { class: "chk" }, `<input type="checkbox" id="ly-${k}" ${S.layers[k] ? "checked" : ""}> ${esc(label)} <span class="k" id="lyh-${k}"></span>`);
    layerList.append(lab);
  });
  layerList.addEventListener("change", (e) => {
    const k = e.target.id.slice(3);
    S.layers[k] = e.target.checked;
    const lyr = { hexes: hexLayer, walk: walkLayer, parcels: parcelLayer, feedback: fbLayer }[k];
    if (lyr) e.target.checked ? lyr.addTo(map) : map.removeLayer(lyr);
    if (k === "trails") drawTrails();
    if (k === "roads") drawRoads();
    if (k === "planned") drawPlanned();
    if (k === "padus") drawPadus();
    if (k === "walk" && e.target.checked) drawWalk();
    if (k === "parcels" && e.target.checked) scheduleParcelView();
    layerHints();
  });
  function layerHints() {
    const z = map.getZoom();
    const set = (k, t) => { const n = $(`#lyh-${k}`); if (n) n.textContent = t; };
    set("roads", !NET ? "(no network)" : z < (WEB.road_min_zoom ?? 12) ? `(zoom ${WEB.road_min_zoom ?? 12}+)` : "");
    set("trails", !NET ? "(no network)" : "");
    set("planned", NET?.planned?.length ? "" : "(none loaded)");
    set("padus", PADUS.length ? "" : "(not exported)");
    const live = (CFG.parcels || []).filter((p) => p.url).length;
    set("parcels", !live && !DATA.parcels ? "(no sources yet)" : z < (WEB.parcel_min_zoom ?? 14) ? `(zoom ${WEB.parcel_min_zoom ?? 14}+)` : "");
    set("feedback", WEB.feedback_endpoint ? "" : "(not connected)");
  }
  $("#mapctl-toggle").addEventListener("click", (e) => {
    const b = $("#mapctl-body"); b.hidden = !b.hidden; e.target.setAttribute("aria-expanded", String(!b.hidden));
  });
  if (window.matchMedia("(max-width: 700px)").matches) { $("#mapctl-body").hidden = true; $("#mapctl-toggle").setAttribute("aria-expanded", "false"); }

  // ---------------------------------------------------------------- weights UI
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
    S.weights[e.target.id.slice(2)] = +e.target.value;
    markCustom(); syncWeightUI(); schedule();
  });
  wBox.addEventListener("click", (e) => {
    const b = e.target.closest(".eye");
    if (b) setView(S.view === b.dataset.view ? "priority" : b.dataset.view);
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
    fillScenarios(); syncWeightUI(); compute();
  });
  const markCustom = (label = "Custom (edited)") => { if (scSel.value !== "__custom") fillScenarios(label); };
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
  const viewSel = $("#view");
  viewSel.append(new Option("Hexes: composite priority", "priority"));
  critKeys.forEach((k) => viewSel.append(new Option("Hexes: " + CFG.criteria[k].label, k)));
  viewSel.append(new Option("Hexes: protected land (%)", "__protected"));
  viewSel.addEventListener("change", () => setView(viewSel.value));
  function setView(v) { S.view = v; viewSel.value = v; syncWeightUI(); restyle(); legend(); }

  const cf = $("#county-filter");
  C.counties.forEach((c, i) => cf.append(new Option(`${c.name}, ${c.state}`, String(i))));
  cf.addEventListener("change", () => { S.county = cf.value; restyle(); });
  $("#hide-protected").addEventListener("change", (e) => { S.hideProt = e.target.checked; restyle(); });
  $("#top-only").addEventListener("change", (e) => { S.topOnly = e.target.checked; restyle(); });
  $("#opacity").addEventListener("input", (e) => { S.opacity = +e.target.value; $("#o-op").textContent = S.opacity.toFixed(2); restyle(); });
  $("#opacity").value = S.opacity; $("#o-op").textContent = S.opacity.toFixed(2);
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
    document.querySelector(".panel").scrollTop = 0;
  }
  tabs.forEach((t) => t.addEventListener("click", () => selectTab(t.id)));
  $("#nav-method").addEventListener("click", (e) => { e.preventDefault(); selectTab("t-ai"); $("#method").scrollIntoView({ behavior: "smooth" }); });
  if (location.hash === "#method") selectTab("t-ai");
  if (location.hash === "#corridors") selectTab("t-corridor");
  if (location.hash === "#land") selectTab("t-land");

  // ---------------------------------------------------------------- corridor controls
  document.querySelectorAll("#mode button").forEach((b) => b.addEventListener("click", () => {
    S.mode = b.dataset.mode;
    document.querySelectorAll("#mode button").forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
    $("#network-ctl").hidden = S.mode !== "network";
    $("#p2p-ctl").hidden = S.mode !== "p2p";
    modeHint(); runCorridors();
  }));
  function modeHint() {
    $("#mode-hint").textContent = S.mode === "network"
      ? "Connects every selected hub with the cheapest set of routes (a minimum spanning tree), following existing trails wherever they exist."
      : "Finds the single cheapest route between two hubs or two map points.";
  }
  modeHint();
  const hubList = $("#hub-list");
  for (const [type, title] of [["park", "Recreation hubs"], ["gateway", "Gateway communities"]]) {
    hubList.append(el("h5", {}, `${title} <button type="button" data-all="${type}">all</button><button type="button" data-none="${type}">none</button>`));
    hubs.filter((h) => h.type === type).forEach((h) =>
      hubList.append(el("label", { class: "chk" }, `<input type="checkbox" id="hub-${h.id}" value="${h.id}" ${S.hubsOn.has(h.id) ? "checked" : ""}> ${esc(h.name)}`)));
  }
  hubList.addEventListener("change", (e) => {
    if (e.target.type !== "checkbox") return;
    e.target.checked ? S.hubsOn.add(e.target.value) : S.hubsOn.delete(e.target.value);
    scheduleCorr();
  });
  hubList.addEventListener("click", (e) => {
    const t = e.target.dataset.all || e.target.dataset.none;
    if (!t) return;
    hubs.filter((h) => h.type === t).forEach((h) => {
      e.target.dataset.all ? S.hubsOn.add(h.id) : S.hubsOn.delete(h.id);
      $(`#hub-${h.id}`).checked = S.hubsOn.has(h.id);
    });
    scheduleCorr();
  });
  const fromSel = $("#p2p-from"), toSel = $("#p2p-to");
  function fillP2P() {
    for (const [sel, key, ph] of [[fromSel, "from", "Start"], [toSel, "to", "End"]]) {
      sel.innerHTML = "";
      sel.append(new Option(`${ph}: choose a hub…`, ""));
      const cur = S.p2p[key];
      if (cur && cur.custom) sel.append(new Option(`${ph}: ${cur.name}`, "__pt"));
      hubs.forEach((h) => sel.append(new Option(`${ph}: ${h.name}`, h.id)));
      sel.value = cur ? (cur.custom ? "__pt" : cur.id) : "";
    }
  }
  S.p2p.from = hubById.fall_creek_falls || hubs[0] || null;
  S.p2p.to = hubById.monte_sano || hubs[1] || null;
  fillP2P();
  fromSel.addEventListener("change", () => { S.p2p.from = hubById[fromSel.value] || null; runCorridors(); });
  toSel.addEventListener("change", () => { S.p2p.to = hubById[toSel.value] || null; runCorridors(); });

  // routing cost sliders (ratios between related classes are kept from config)
  const C0 = { ...S.P.cost };
  const costUI = [
    ["c-trail", "o-trail", () => S.P.cost.trail, (v) => { S.P.cost.trail = v; S.P.cost.greenway = v * (C0.greenway / C0.trail); }, (v) => v.toFixed(2)],
    ["c-street", "o-street", () => S.P.cost.road_local, (v) => { const k = v / C0.road_local; ["sidewalk", "road_local", "road_collector", "road_arterial"].forEach((c) => (S.P.cost[c] = C0[c] * k)); }, (v) => v.toFixed(2)],
    ["c-new", "o-new", () => S.P.cost.new, (v) => { S.P.cost.new = v; }, (v) => v.toFixed(1)],
    ["c-disc", "o-disc", () => S.P.protected_discount, (v) => { S.P.protected_discount = v; }, (v) => `${Math.round(v * 100)}%`],
    ["c-bar", "o-bar", () => S.P.development_barrier, (v) => { S.P.development_barrier = v; }, (v) => (v >= 1 ? "off" : `${Math.round(v * 100)}th pct`)],
  ];
  costUI.forEach(([i, o, get, set, f]) => {
    const inp = $("#" + i);
    inp.value = get(); $("#" + o).textContent = f(+get());
    inp.addEventListener("input", () => { set(+inp.value); $("#" + o).textContent = f(+inp.value); costRatio(); scheduleCorr(); });
  });
  function costRatio() {
    const c = S.P.cost;
    $("#cost-ratio").textContent = `New trail costs ${fmt((c.new * 0.5) / c.trail, 0)}–${fmt((c.new * 2) / c.trail, 0)}× an existing trail per km (best to worst land), and quiet streets cost ${fmt(c.road_local / c.trail, 0)}×. Higher ratios hold routes to existing trails more tightly.`;
  }
  costRatio();

  function onHubClick(h) {
    if (fbPicking) return onMapClick(L.latLng(h.lat, h.lon), h.hex);
    if (S.mode !== "p2p") return;
    S.p2p[S.p2p.clickNext] = h;
    S.p2p.clickNext = S.p2p.clickNext === "from" ? "to" : "from";
    fillP2P(); runCorridors();
  }
  function onMapClick(latlng, i) {
    if (fbPicking) return openFeedback(latlng);
    if (S.mode !== "p2p" || i < 0) return;
    const cty = C.counties[C.county[i]].name;
    S.p2p[S.p2p.clickNext] = { custom: true, id: "__pt", name: `map point in ${cty} Co.`, lat: latlng.lat, lon: latlng.lng, hex: i };
    S.p2p.clickNext = S.p2p.clickNext === "from" ? "to" : "from";
    status(S.p2p.clickNext === "to" ? "Start set. Click a second point for the end." : null);
    fillP2P(); runCorridors();
  }
  function status(msg) { const s = $("#status"); s.hidden = !msg; s.textContent = msg || ""; }

  // ---------------------------------------------------------------- compute
  let t1 = 0, t2 = 0;
  const schedule = () => { cancelAnimationFrame(t1); t1 = requestAnimationFrame(compute); };
  const scheduleCorr = () => { clearTimeout(t2); t2 = setTimeout(runCorridors, 120); };
  function compute() {
    priority = E.composite(C.norm, S.weights, N);
    const s = Float64Array.from(priority).sort();
    q80 = s[Math.floor(0.8 * (N - 1))];
    restyle();
    scheduleCorr();
  }
  const value = (i) => (S.view === "priority" ? priority[i] : S.view === "__protected" ? C.protected[i] / 100 : C.norm[S.view][i] / 100);
  function restyle() {
    const stroke = bm.value === "none" ? tok("--bg") : "#ffffff";
    for (let i = 0; i < N; i++) {
      const hide = (S.county !== "" && String(C.county[i]) !== S.county) || (S.hideProt && C.protected[i] > 50) || (S.topOnly && priority[i] < q80);
      polys[i].setStyle(hide ? { fillOpacity: 0, opacity: 0 }
        : { fillColor: ramp(value(i)), fillOpacity: S.opacity, color: stroke, opacity: Math.min(0.5, S.opacity), weight: 0.4 });
    }
    outline.setStyle({ color: bm.value === "imagery" ? "#ffffff" : tok("--ink"), opacity: 0.9 });
  }

  // segments for one routed link, oriented along the route
  function linkSegments(L0) {
    const segs = [];
    const access = (hub, node) => {
      if (!hub || node < 0) return;
      const kind = node < G.H ? "new" : "walk";
      segs.push({ coords: [[hub.lat, hub.lon], [G.lat[node], G.lon[node]]], kind, cls: kind === "new" ? "new" : "access", name: "", km: E.haversineKm([hub.lat, hub.lon], [G.lat[node], G.lon[node]]), access: true });
    };
    access(L0.hubFrom, L0.start);
    for (const [e, frm] of L0.edges) {
      const to = G.a[e] === frm ? G.b[e] : G.a[e];
      if (G.t[e] === 0) {
        let c = geomOf(e);
        if (G.a[e] !== frm) c = c.slice().reverse();
        const cls = netCls(e);
        segs.push({ coords: c, kind: TRAILISH.has(cls) ? "trail" : "walk", cls, name: edgeName(e), km: G.km[e], edge: e });
      } else {
        segs.push({ coords: [[G.lat[frm], G.lon[frm]], [G.lat[to], G.lon[to]]], kind: "new", cls: "new", name: "", km: G.km[e], edge: e });
      }
    }
    const endSeg = [];
    if (L0.hubTo && L0.end >= 0) {
      const kind = L0.end < G.H ? "new" : "walk";
      endSeg.push({ coords: [[G.lat[L0.end], G.lon[L0.end]], [L0.hubTo.lat, L0.hubTo.lon]], kind, cls: kind === "new" ? "new" : "access", name: "", km: E.haversineKm([L0.hubTo.lat, L0.hubTo.lon], [G.lat[L0.end], G.lon[L0.end]]), access: true });
    }
    return segs.concat(endSeg);
  }
  function gapRuns(L0, segs) {
    const runs = []; let cur = null, prevName = "";
    for (const s of segs) {
      if (s.kind === "new") {
        if (!cur) cur = { coords: [], km: 0, after: prevName || (L0.hubFrom?.name ?? ""), link: `${L0.fromName} → ${L0.toName}` };
        cur.coords.push(...(cur.coords.length ? s.coords.slice(1) : s.coords));
        cur.km += s.km;
      } else {
        if (cur) { cur.before = s.name || s.cls.replace("_", " "); runs.push(cur); cur = null; }
        if (s.name) prevName = s.name;
      }
    }
    if (cur) { cur.before = L0.hubTo?.name ?? ""; runs.push(cur); }
    for (const r of runs) {
      const hx = new Set(r.coords.map(([a, b]) => hexOf(a, b)).filter((i) => i >= 0));
      r.meanP = hx.size ? [...hx].reduce((s, i) => s + priority[i], 0) / hx.size : NaN;
      const mid = r.coords[Math.floor(r.coords.length / 2)];
      const mi = hexOf(mid[0], mid[1]);
      r.county = mi >= 0 ? `${C.counties[C.county[mi]].name}, ${C.counties[C.county[mi]].state}` : "–";
      r.mid = mid;
    }
    return runs;
  }

  function ringZone(cells, k) {
    const zone = new Set(cells); let frontier = [...zone];
    for (let r = 0; r < k; r++) {
      const nx = [];
      frontier.forEach((u) => hexNbrs[u].forEach((v) => { if (!zone.has(v)) { zone.add(v); nx.push(v); } }));
      frontier = nx;
    }
    return zone;
  }

  async function runCorridors() {
    status("Routing…");
    await sleep(15);
    lr = E.landRes(priority, C.protected, C.norm.development, S.P);
    const cost = E.edgeCost(G, lr, S.P);
    let links = [];
    if (S.mode === "network") {
      const sel = hubs.filter((h) => S.hubsOn.has(h.id));
      links = sel.length > 1 ? E.greenbelt(G, sel, cost, lr, S.P) : [];
      links.forEach((l) => { l.fromName = hubById[l.from].name; l.toName = hubById[l.to].name; });
    } else if (S.p2p.from && S.p2p.to && !(S.p2p.from.lat === S.p2p.to.lat && S.p2p.from.lon === S.p2p.to.lon)) {
      const l = E.pointToPoint(G, S.p2p.from, S.p2p.to, cost, lr, S.P);
      if (l) { l.fromName = S.p2p.from.name; l.toName = S.p2p.to.name; links = [l]; }
    }
    const segs = [], gaps = [], cells = new Set();
    links.forEach((l) => {
      const ss = linkSegments(l);
      l.segs = ss;
      l.km = { trail: 0, walk: 0, new: 0 };
      ss.forEach((s) => { l.km[s.kind] += s.km; s.coords.forEach(([a, b]) => { const i = hexOf(a, b); if (i >= 0) cells.add(i); }); });
      l.total = l.km.trail + l.km.walk + l.km.new;
      segs.push(...ss);
      gaps.push(...gapRuns(l, ss));
    });
    gaps.sort((a, b) => b.km - a.km);
    corridor = { links, segs, gaps, zone: ringZone([...cells], S.P.zone_rings ?? 1) };
    parcelRows = [];
    $("#dl-parcels").disabled = true;
    drawCorridors(); corridorPanel(); landPanel(); countyTable();
    status(null);
  }

  // ---------------------------------------------------------------- render corridor
  function drawCorridors() {
    corrLayer.clearLayers();
    const acc = tok("--accent"), casing = tok("--casing");
    for (const s of corridor.segs) {
      const dash = s.kind === "new" ? "9 7" : s.kind === "walk" ? "2 6" : null;
      L.polyline(s.coords, { renderer: rCorr, interactive: false, color: casing, weight: s.kind === "trail" ? 9 : 7, opacity: 0.85, lineCap: "round" }).addTo(corrLayer);
      L.polyline(s.coords, { renderer: rCorr, color: acc, weight: s.kind === "trail" ? 5 : 4, opacity: 1, dashArray: dash, lineCap: s.kind === "walk" ? "round" : "butt" })
        .bindTooltip(`<b>${s.kind === "trail" ? "On existing trail" : s.kind === "walk" ? "On sidewalk / street" : "Gap: new connector needed"}</b><br><span class="k">${esc(s.name || s.cls.replace("_", " "))} · ${fmt(s.km, 2)} km</span>`, { sticky: true, className: "cell-tip" })
        .addTo(corrLayer);
    }
  }

  function corridorPanel() {
    const sum = corridor.links.reduce((a, l) => ({ trail: a.trail + l.km.trail, walk: a.walk + l.km.walk, new: a.new + l.km.new }), { trail: 0, walk: 0, new: 0 });
    const tot = sum.trail + sum.walk + sum.new;
    $("#corr-stats").innerHTML = [
      [fmt(tot, 0) + " km", "Corridor length"],
      [tot ? fmt((100 * sum.trail) / tot, 0) + "%" : "–", "On existing trails"],
      [fmt(sum.walk, 0) + " km", "On sidewalks & streets"],
      [fmt(sum.new, 0) + " km", "New connectors (gaps)"],
      [String(corridor.links.length), corridor.links.length === 1 ? "Link" : "Links"],
      [String(corridor.gaps.length), "Gaps to close"],
    ].map(([b, s]) => `<div class="stat"><b>${b}</b><span>${s}</span></div>`).join("");
    $("#corr-mix").innerHTML = tot ? ["trail", "walk", "new"].map((k) => `<i class="m-${k}" style="flex:${sum[k]}" title="${k}: ${fmt(sum[k], 1)} km"></i>`).join("") : "";
    $("#net-note").textContent = !NET ? "No trail network loaded. Routes use the hex grid only. Run python -m seeds_cds network."
      : `Routing over ${NET.edges.u.length.toLocaleString()} existing trail, sidewalk and street segments plus ${NET.gaps.u.length.toLocaleString()} candidate gap connectors.`;
    $("#links").innerHTML = corridor.links.length
      ? `<thead><tr><th>From → to</th><th class="n">km</th><th class="n">Trail</th><th class="n">New km</th></tr></thead><tbody>${corridor.links
        .map((l) => `<tr><td>${esc(l.fromName)} → ${esc(l.toName)}</td><td class="n">${fmt(l.total, 0)}</td><td class="n">${l.total ? fmt((100 * l.km.trail) / l.total, 0) : "–"}%</td><td class="n">${fmt(l.km.new, 1)}</td></tr>`).join("")}</tbody>`
      : `<tbody><tr><td>${S.mode === "network" ? "Select at least two hubs." : "Choose a start and an end."}</td></tr></tbody>`;
    $("#gaps").innerHTML = corridor.gaps.length
      ? `<thead><tr><th>Between</th><th>County</th><th class="n">km</th><th class="n">Prio</th><th></th></tr></thead><tbody>${corridor.gaps.slice(0, 40)
        .map((g, j) => `<tr><td>${esc(g.after || "start")} → ${esc(g.before || "end")}</td><td>${esc(g.county)}</td><td class="n">${fmt(g.km, 2)}</td><td class="n">${fmt(g.meanP, 2)}</td><td><button class="btn" type="button" data-gap="${j}">Zoom</button></td></tr>`).join("")}</tbody>`
      : "<tbody><tr><td>No gaps: the whole route uses existing trails and streets.</td></tr></tbody>";
  }
  $("#gaps").addEventListener("click", (e) => {
    const j = e.target.dataset.gap;
    if (j == null) return;
    const g = corridor.gaps[+j];
    map.fitBounds(L.latLngBounds(g.coords).pad(0.6), { maxZoom: 15 });
  });

  // ---------------------------------------------------------------- land: PAD-US + parcels
  const bboxOf = (geom) => {
    let a = 180, b = 90, c = -180, d = -90;
    const walk = (x) => (typeof x[0] === "number" ? (x[0] < a && (a = x[0]), x[1] < b && (b = x[1]), x[0] > c && (c = x[0]), x[1] > d && (d = x[1])) : x.forEach(walk));
    walk(geom.coordinates);
    return [a, b, c, d];
  };
  PADUS.forEach((f) => (f.bbox ||= bboxOf(f.geometry)));
  // corridor sample points with kind: [lat, lon, kmWeight, kind]
  function corridorSamples(step = 0.05) {
    const pts = [];
    for (const s of corridor.segs) for (const p of E.densify(s.coords, step)) pts.push([p[0], p[1], p[2], s.kind]);
    return pts;
  }
  function overlay(features, pts) {
    const out = new Map();
    for (const f of features) {
      const [a, b, c, d] = f.bbox || (f.bbox = bboxOf(f.geometry));
      const r = { trail: 0, walk: 0, new: 0 };
      let hit = false;
      for (const [la, lo, w, k] of pts) {
        if (lo < a || lo > c || la < b || la > d) continue;
        if (E.pointInGeometry([lo, la], f.geometry)) { r[k] += w; hit = true; }
      }
      if (hit) out.set(f, r);
    }
    return out;
  }
  let lastSamples = [];
  function landPanel() {
    lastSamples = corridorSamples();
    const tot = lastSamples.reduce((s, p) => s + p[2], 0);
    const pad = overlay(PADUS, lastSamples);
    let inPad = 0; const seen = new Set();
    // count each sample once even if PAD-US units overlap
    for (const [la, lo, w] of lastSamples) {
      if (PADUS.some((f) => { const [a, b, c, d] = f.bbox; return lo >= a && lo <= c && la >= b && la <= d && E.pointInGeometry([lo, la], f.geometry); })) inPad += w;
    }
    const rows = [...pad.entries()].map(([f, r]) => ({ p: f.properties, km: r.trail + r.walk + r.new, r })).sort((x, y) => y.km - x.km);
    $("#land-stats").innerHTML = [
      [fmt(tot, 0) + " km", "Corridor length"],
      [tot ? fmt((100 * inPad) / tot, 0) + "%" : "–", "Through public / protected land"],
      [String(rows.length), "Protected units crossed"],
      [fmt(corridor.gaps.reduce((s, g) => s + g.km, 0), 1) + " km", "Gap length to secure"],
    ].map(([b, s]) => `<div class="stat"><b>${b}</b><span>${s}</span></div>`).join("");
    $("#padus-tbl").innerHTML = rows.length
      ? `<thead><tr><th>Unit</th><th>Owner</th><th>Access</th><th class="n">km</th></tr></thead><tbody>${rows.slice(0, 30)
        .map((x) => `<tr><td>${esc(padusName(x.p))}<br><span class="k">${esc(x.p.Category || "")} · GAP ${esc(x.p.GAP_Sts || "–")}</span></td><td>${esc(x.p.Own_Name || x.p.Loc_Own || "–")}<br><span class="k">${esc(x.p.Mang_Name || "")}</span></td><td>${esc(x.p.Pub_Access || "–")}</td><td class="n">${fmt(x.km, 1)}</td></tr>`).join("")}</tbody>`
      : `<tbody><tr><td>${PADUS.length ? "The route does not cross PAD-US land." : "PAD-US ownership not exported yet. Rerun the pipeline."}</td></tr></tbody>`;
    const cands = [...corridor.zone].filter((i) => C.protected[i] < 50).sort((a, b) => priority[b] - priority[a]);
    $("#cands").innerHTML = cands.length
      ? `<thead><tr><th>County</th><th class="n">Prio</th><th class="n">Prot.</th><th></th></tr></thead><tbody>${cands.slice(0, 12)
        .map((i) => `<tr><td>${esc(C.counties[C.county[i]].name)}, ${C.counties[C.county[i]].state}</td><td class="n">${fmt(priority[i], 2)}</td><td class="n">${C.protected[i]}%</td><td><button class="btn" data-zoom="${i}" type="button">Zoom</button></td></tr>`).join("")}</tbody>`
      : "<tbody><tr><td>No unprotected cells near the corridor.</td></tr></tbody>";
    parcelNote();
    if (parcelRows.length) parcelTable();
  }
  $("#cands").addEventListener("click", (e) => {
    const i = e.target.dataset.zoom;
    if (i != null) { map.flyTo(center[+i], 13, { duration: 0.6 }); polys[+i].openTooltip(center[+i]); }
  });

  const liveParcelSrc = () => (CFG.parcels || []).filter((p) => p.url);
  function parcelNote() {
    const live = liveParcelSrc();
    $("#parcel-note").innerHTML = live.length
      ? `Queries ${live.length} county parcel service${live.length > 1 ? "s" : ""} live along the corridor. Owner names are classified as public, non-profit, utility or private.`
      : DATA.parcels
        ? "Using parcels exported by the pipeline (python -m seeds_cds parcels)."
        : "No county parcel services are connected yet. Public and protected ownership above comes from PAD-US. To add private parcels, put assessor service URLs in config/sources.yaml, or run python -m seeds_cds parcels with downloaded parcel files.";
    $("#parcel-run").disabled = !live.length && !DATA.parcels;
  }

  async function arcQuery(src, params) {
    const layer = await resolveLayer(src);
    const body = new URLSearchParams({ outFields: "*", returnGeometry: "true", outSR: "4326", inSR: "4326", f: "geojson", ...params });
    const r = await fetch(layer + "/query", { method: "POST", body });
    if (!r.ok) throw new Error(`${src.id}: HTTP ${r.status}`);
    const j = await r.json();
    if (j.error) throw new Error(`${src.id}: ${j.error.message || j.error.code}`);
    return j.features || [];
  }
  const layerCache = {};
  async function resolveLayer(src) {
    if (layerCache[src.id]) return layerCache[src.id];
    let url = src.url.replace(/\/$/, "");
    if (!/\/(MapServer|FeatureServer)\/\d+$/.test(url)) {
      const info = await (await fetch(url + "?f=json")).json();
      const pat = (src.layer_match || "parcel").toLowerCase();
      const L0 = (info.layers || []).find((l) => l.name.toLowerCase().includes(pat)) || (info.layers || [])[0];
      if (!L0) throw new Error(`${src.id}: no layers`);
      url += "/" + L0.id;
    }
    return (layerCache[src.id] = url);
  }
  const fips = (src) => (src.fips === "any" ? null : [].concat(src.fips || []));
  function toParcel(src, f) {
    const p = f.properties || {}, fl = E.detectFields(p, CFG.parcel_fields), g = (k) => (fl[k] ? p[fl[k]] : null);
    return { src: src.id, id: g("id"), owner: g("owner"), acres: +g("acres") || null, landuse: g("landuse"), value: g("value"),
      address: g("address"), cls: E.ownerClass(g("owner"), CFG.owner_classes), geometry: f.geometry, props: p };
  }
  $("#parcel-run").addEventListener("click", async () => {
    const btn = $("#parcel-run"); btn.disabled = true;
    const note = $("#parcel-note");
    try {
      let feats = [];
      if (liveParcelSrc().length) {
        const counties = new Set([...corridor.zone].map((i) => C.counties[C.county[i]].fips));
        const paths = [];
        for (const s of corridor.segs) for (let i = 0; i < s.coords.length; i += 150) paths.push(s.coords.slice(i, i + 151).map(([a, b]) => [b, a]));
        for (const src of liveParcelSrc()) {
          const fl = fips(src);
          if (fl && !fl.some((f) => counties.has(f))) continue;
          for (let i = 0; i < paths.length; i += 20) {
            note.textContent = `Querying ${src.label}… (${Math.min(i + 20, paths.length)}/${paths.length} pieces)`;
            const got = await arcQuery(src, { geometry: JSON.stringify({ paths: paths.slice(i, i + 20), spatialReference: { wkid: 4326 } }),
              geometryType: "esriGeometryPolyline", spatialRel: "esriSpatialRelIntersects", distance: "30", units: "esriSRUnit_Meter" });
            feats.push(...got.map((f) => toParcel(src, f)));
          }
        }
      } else if (DATA.parcels) {
        feats = DATA.parcels.features.map((f) => ({ src: f.properties.source, id: f.properties.parcel_id, owner: f.properties.owner,
          acres: f.properties.acres, landuse: f.properties.landuse, value: f.properties.value, address: f.properties.address,
          cls: f.properties.owner_class, geometry: f.geometry, props: f.properties }));
      }
      const uniq = new Map(feats.map((f) => [`${f.src}|${f.id}|${f.owner}|${JSON.stringify(f.geometry).length}`, f]));
      const ov = overlay([...uniq.values()], lastSamples);
      parcelRows = [...ov.entries()].map(([f, r]) => ({ ...f, km_trail: r.trail, km_walk: r.walk, km_new: r.new,
        screen: (f.cls === "Private" || f.cls === "Unknown") && r.new > 0 ? "Easement / acquisition candidate" : r.new > 0 ? "Coordinate with owner" : "On existing route" }))
        .sort((a, b) => (a.screen > b.screen ? 1 : a.screen < b.screen ? -1 : b.km_new - a.km_new));
      parcelNote();
      parcelTable();
      parcelLayer.clearLayers();
      parcelRows.forEach((r) => L.geoJSON(r.geometry, { renderer: rLand, style: { color: tok(r.km_new > 0 ? "--accent" : "--ink"), weight: 1.2, fillOpacity: 0.06 } })
        .bindTooltip(parcelTip(r), { sticky: true, className: "cell-tip" }).addTo(parcelLayer));
      if (!S.layers.parcels) { S.layers.parcels = true; $("#ly-parcels").checked = true; parcelLayer.addTo(map); }
      $("#dl-parcels").disabled = !parcelRows.length;
    } catch (err) {
      note.textContent = `Parcel query failed: ${err.message}. The service may block browser requests (CORS) or need a token; run python -m seeds_cds parcels instead.`;
    }
    btn.disabled = false;
  });
  const parcelTip = (r) => `<b>${esc(r.owner || "Owner not listed")}</b> <span class="pill">${esc(r.cls)}</span><br>
    <span class="k">Parcel</span> ${esc(r.id || "–")}${r.acres ? ` · ${fmt(r.acres, 1)} ac` : ""}<br>${r.address ? esc(r.address) + "<br>" : ""}
    ${r.km_new != null ? `<span class="k">Corridor here: ${fmt(r.km_trail + r.km_walk, 2)} km existing, ${fmt(r.km_new, 2)} km new</span>` : ""}`;
  function parcelTable() {
    $("#parcel-tbl").innerHTML = parcelRows.length
      ? `<thead><tr><th>Owner</th><th>Class</th><th class="n">Acres</th><th class="n">New km</th><th>Screen</th></tr></thead><tbody>${parcelRows.slice(0, 60)
        .map((r) => `<tr><td>${esc(r.owner || "–")}<br><span class="k">${esc(r.id || "")}</span></td><td>${esc(r.cls)}</td><td class="n">${fmt(r.acres, 1)}</td><td class="n">${fmt(r.km_new, 2)}</td><td>${esc(r.screen)}</td></tr>`).join("")}</tbody>`
      : "<tbody><tr><td>No parcels found along the corridor.</td></tr></tbody>";
  }
  // live parcel view (zoomed in)
  let tPV = 0;
  const scheduleParcelView = () => { clearTimeout(tPV); tPV = setTimeout(parcelView, 400); };
  async function parcelView() {
    if (!S.layers.parcels || parcelRows.length || map.getZoom() < (WEB.parcel_min_zoom ?? 14)) return;
    const b = map.getBounds();
    const env = [b.getWest(), b.getSouth(), b.getEast(), b.getNorth()].join(",");
    parcelLayer.clearLayers();
    for (const src of liveParcelSrc()) {
      try {
        const got = await arcQuery(src, { geometry: env, geometryType: "esriGeometryEnvelope", spatialRel: "esriSpatialRelIntersects", resultRecordCount: "2000" });
        got.map((f) => toParcel(src, f)).forEach((r) => L.geoJSON(r.geometry, { renderer: rLand, style: { color: tok("--ink"), weight: 0.8, fillOpacity: 0.03 } })
          .bindTooltip(parcelTip(r), { sticky: true, className: "cell-tip" }).addTo(parcelLayer));
      } catch (err) { status(`Parcels: ${err.message}`); setTimeout(() => status(null), 3500); }
    }
  }

  // ---------------------------------------------------------------- county table
  const trailKmByCounty = C.counties.map(() => 0);
  if (NET) for (let i = 0; i < NET.edges.u.length; i++) {
    if (!TRAILISH.has(netCls(i))) continue;
    const g = geomOf(i), m = g[Math.floor(g.length / 2)], h = hexOf(m[0], m[1]);
    if (h >= 0) trailKmByCounty[C.county[h]] += NET.edges.km[i];
  }
  function countyTable() {
    const agg = C.counties.map(() => ({ n: 0, sum: 0, top: 0 }));
    for (let i = 0; i < N; i++) { const a = agg[C.county[i]]; a.n++; a.sum += priority[i]; if (priority[i] >= q80) a.top++; }
    const rows = C.counties.map((c, j) => ({ c, ...agg[j], mean: agg[j].sum / agg[j].n, tk: trailKmByCounty[j] })).sort((a, b) => b.mean - a.mean);
    $("#county-tbl").innerHTML = `<thead><tr><th>County</th><th>ARC</th><th class="n">Mean</th><th class="n">Top 20%</th><th class="n">Trail km</th></tr></thead><tbody>${rows
      .map((r) => `<tr><td>${esc(r.c.name)}, ${r.c.state}</td><td><span class="pill ${esc(r.c.arc_status)}">${esc(r.c.arc_status)}</span></td><td class="n">${fmt(r.mean, 2)}</td><td class="n">${fmt((100 * r.top) / r.n, 0)}%</td><td class="n">${fmt(r.tk, 0)}</td></tr>`).join("")}</tbody>`;
  }

  // ---------------------------------------------------------------- tooltips + legend + data tab
  function rawFmt(k, v) {
    if (v == null) return "no data";
    const u = CFG.criteria[k].unit;
    if (u === "%") return fmt(v * 100, 1) + "%";
    if (u === "km") return fmt(v, 1) + " km";
    if (u === "m") return fmt(v, 0) + " m";
    if (u === "km/km2") return fmt(v, 2) + " km/km²";
    return fmt(v, 2);
  }
  function tipHtml(i) {
    const c = C.counties[C.county[i]];
    const top = E.contributions(C.norm, S.weights, i).slice(0, 5);
    const rows = top.map((t) => `<tr><td>${esc(CFG.criteria[t.key].label)}</td><td class="k">${rawFmt(t.key, C.raw[t.key]?.[i])}</td><td style="color:var(${t.v < 0 ? "--ochre" : "--forest"})">${t.v >= 0 ? "+" : ""}${fmt(t.v * 100, 0)}</td></tr>`).join("");
    const view = S.view !== "priority" && S.view !== "__protected"
      ? `<div><span class="k">${esc(CFG.criteria[S.view].label)}:</span> ${rawFmt(S.view, C.raw[S.view]?.[i])} · pct ${C.norm[S.view][i]}</div>` : "";
    return `<b>${esc(c.name)} Co., ${c.state}</b> <span class="pill ${esc(c.arc_status)}">${esc(c.arc_status)}</span>
      <div><span class="k">Priority</span> <b>${fmt(priority[i], 2)}</b> · <span class="k">protected</span> ${C.protected[i]}%${corridor.zone.has(i) ? ' · <span style="color:var(--accent)">near corridor</span>' : ""}</div>
      ${view}<table>${rows}</table>`;
  }
  function legend() {
    const title = S.view === "priority" ? "Composite priority" : S.view === "__protected" ? "Protected land" : CFG.criteria[S.view].label;
    const ticks = S.view === "priority" ? ["0 low", "0.5", "1 high"] : S.view === "__protected" ? ["0%", "50%", "100%"] : ["0 pct", "50", "100 pct"];
    $("#legend").innerHTML = `<div class="ttl">${esc(title)}</div>
      <div class="ramp" style="background:linear-gradient(90deg,${RAMP.join(",")})"></div>
      <div class="ticks">${ticks.map((t) => `<span>${t}</span>`).join("")}</div>
      <div class="keys">
        <span><i class="ln ln-trail"></i>Corridor on trail</span><span><i class="ln ln-walk"></i>on street</span><span><i class="ln ln-new"></i>gap (new)</span>
        <span><i class="ln ln-gw"></i>Greenway</span><span><i class="ln ln-tr"></i>Trail</span><span><i class="sq"></i>Public land</span>
        <span><i class="dot park"></i>Rec hub</span><span><i class="dot gate"></i>Gateway</span></div>`;
  }
  function dataPanel() {
    const ai = CFG.ai || {};
    $("#ai-stats").innerHTML = [
      [ai.auc != null ? fmt(ai.auc, 3) : "–", "Holdout AUC"],
      [ai.n_test ? String(ai.n_test) : "–", "Test samples"],
      [esc(CFG.protected_source || "–"), "Training labels"],
      [C.meta?.res != null ? `H3 r${C.meta.res}` : "–", `${N.toLocaleString()} cells`],
    ].map(([b, s]) => `<div class="stat"><b style="font-size:${String(b).length > 12 ? 15 : 22}px">${b}</b><span>${s}</span></div>`).join("");
    const imp = Object.entries(ai.importance || {}), mx = Math.max(...imp.map(([, v]) => v), 1e-9);
    $("#ai-imp").innerHTML = imp.length
      ? imp.map(([k, v]) => `<div class="barrow"><span>${esc(k.replace(/_/g, " "))}</span><i style="width:${((100 * v) / mx).toFixed(1)}%"></i><span class="n">${fmt(100 * v, 0)}%</span></div>`).join("") + (ai.note ? `<p class="hint">${esc(ai.note)}</p>` : "")
      : '<p class="hint">Geo-AI model was not run for this build.</p>';
    const kb = NET?.stats?.km_by_class || {};
    $("#net-tbl").innerHTML = NET
      ? `<thead><tr><th>Class</th><th class="n">km</th></tr></thead><tbody>${NET.classes.map((c) => `<tr><td>${esc(c.replace("_", " "))}</td><td class="n">${fmt(kb[c] || 0, 0)}</td></tr>`).join("")}
        <tr><td>Candidate gap connectors</td><td class="n">${NET.gaps.u.length.toLocaleString()}</td></tr><tr><td>Parks &amp; walkable spaces</td><td class="n">${(NET.walkable || []).length.toLocaleString()}</td></tr></tbody>`
      : "<tbody><tr><td>No network loaded.</td></tr></tbody>";
    const used = new Set(NET?.stats?.sources || []);
    $("#src-tbl").innerHTML = `<thead><tr><th>Source</th><th>Status</th></tr></thead><tbody>${(CFG.network_sources || [])
      .map((s) => `<tr><td>${esc(s.label)}<br><span class="k">${esc(s.owner || "")}</span></td><td>${used.has(s.id) ? "loaded" : esc(s.status || "")}</td></tr>`).join("")}
      ${(CFG.parcels || []).map((s) => `<tr><td>${esc(s.label)}<br><span class="k">parcels</span></td><td>${s.url ? "connected" : esc(s.status || "")}</td></tr>`).join("")}</tbody>`;
  }

  // ---------------------------------------------------------------- downloads
  function download(name, text, type) {
    const a = el("a", { href: URL.createObjectURL(new Blob([text], { type })), download: name });
    document.body.append(a); a.click(); a.remove();
  }
  const csvCell = (v) => (v == null ? "" : /[",\n]/.test(String(v)) ? `"${String(v).replace(/"/g, '""')}"` : String(v));
  const ring = (i) => { const b = h3.cellToBoundary(C.h3[i], true); return [[...b, b[0]]]; };
  $("#dl-cells").addEventListener("click", () => {
    const features = C.h3.map((h, i) => ({ type: "Feature", geometry: { type: "Polygon", coordinates: ring(i) },
      properties: { h3: h, county: C.counties[C.county[i]].name, state: C.counties[C.county[i]].state, priority: +priority[i].toFixed(4),
        protected_pct: C.protected[i], near_corridor: corridor.zone.has(i) ? 1 : 0, ...Object.fromEntries(critKeys.map((k) => [`pct_${k}`, C.norm[k][i]])) } }));
    download("seeds_priority_cells.geojson", JSON.stringify({ type: "FeatureCollection", features, properties: { weights: S.weights } }), "application/geo+json");
  });
  $("#dl-corr").addEventListener("click", () => {
    const features = corridor.links.flatMap((l) => l.segs.map((s) => ({ type: "Feature",
      geometry: { type: "LineString", coordinates: s.coords.map(([a, b]) => [b, a]) },
      properties: { from: l.fromName, to: l.toName, segment: s.kind, class: s.cls, name: s.name, km: +s.km.toFixed(3) } })));
    download("seeds_greenbelt_corridor.geojson", JSON.stringify({ type: "FeatureCollection", features, properties: { weights: S.weights, routing: S.P } }), "application/geo+json");
  });
  $("#dl-gaps").addEventListener("click", () => {
    const lines = ["link,from_feature,to_feature,county,km,mean_priority,mid_lat,mid_lon"].concat(corridor.gaps.map((g) =>
      [g.link, g.after, g.before, g.county, g.km.toFixed(3), g.meanP.toFixed(3), g.mid[0].toFixed(5), g.mid[1].toFixed(5)].map(csvCell).join(",")));
    download("seeds_corridor_gaps.csv", lines.join("\n"), "text/csv");
  });
  $("#dl-parcels").addEventListener("click", () => {
    const lines = ["source,parcel_id,owner,owner_class,acres,landuse,value,address,km_existing_trail,km_street,km_new,screen"].concat(parcelRows.map((r) =>
      [r.src, r.id, r.owner, r.cls, r.acres, r.landuse, r.value, r.address, r.km_trail.toFixed(3), r.km_walk.toFixed(3), r.km_new.toFixed(3), r.screen].map(csvCell).join(",")));
    download("seeds_corridor_parcels.csv", lines.join("\n"), "text/csv");
  });
  $("#export-weights").addEventListener("click", () =>
    download("seeds_weights.json", JSON.stringify({ scenario: scSel.options[scSel.selectedIndex].text, weights: S.weights, corridor: S.P, generated: new Date().toISOString() }, null, 2), "application/json"));
  $("#import-weights").addEventListener("change", async (e) => {
    const f = e.target.files[0];
    if (!f) return;
    try {
      const j = JSON.parse(await f.text()), w = j.weights || j;
      const known = Object.keys(w).filter((k) => critKeys.includes(k) && isFinite(+w[k]));
      const unknown = Object.keys(w).filter((k) => !critKeys.includes(k));
      if (!known.length) throw new Error("no recognized criterion keys");
      const mx = Math.max(...known.map((k) => Math.abs(+w[k])));
      S.weights = Object.fromEntries(known.map((k) => [k, Math.round(((+w[k] / mx) * 100) / 5) * 5]));
      if (j.corridor) { Object.assign(S.P, j.corridor); S.P.cost = { ...S.P.cost, ...(j.corridor.cost || {}) }; }
      fillScenarios(`Imported: ${j.scenario || f.name}`);
      $("#weights-note").textContent = `Loaded ${known.length} weights from ${f.name}.` + (unknown.length ? ` Ignored unknown keys: ${unknown.join(", ")}.` : "");
      syncWeightUI(); compute();
    } catch (err) {
      $("#weights-note").textContent = `Could not read ${f.name}: ${err.message}. Expected JSON like {"weights": {"forest_cover": 20, "development": -15}}.`;
    }
    e.target.value = "";
  });

  // ---------------------------------------------------------------- feedback
  let fbPicking = false, fbAt = null;
  $("#fb-start").addEventListener("click", () => {
    fbPicking = true;
    document.body.classList.add("picking");
    status("Click the map where your comment applies.");
  });
  function openFeedback(latlng) {
    fbPicking = false; document.body.classList.remove("picking"); status(null);
    fbAt = latlng;
    const i = hexOf(latlng.lat, latlng.lng);
    $("#fb-where").textContent = `${latlng.lat.toFixed(5)}, ${latlng.lng.toFixed(5)}${i >= 0 ? ` · ${C.counties[C.county[i]].name} Co., ${C.counties[C.county[i]].state}` : ""}`;
    $("#fb-result").hidden = true;
    $("#fb").hidden = false;
    $("#fb-text").focus();
  }
  $("#fb-cancel").addEventListener("click", () => { $("#fb").hidden = true; });
  $("#fb-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const payload = { ts: new Date().toISOString(), lat: +fbAt.lat.toFixed(6), lon: +fbAt.lng.toFixed(6),
      topic: $("#fb-topic").value, comment: $("#fb-text").value.trim(), name: $("#fb-name").value.trim(), org: $("#fb-org").value.trim(),
      scenario: scSel.options[scSel.selectedIndex].text, weights: S.weights, routing: S.P, zoom: map.getZoom(), data_generated: C.meta?.generated };
    const out = $("#fb-result");
    out.hidden = false;
    if (!payload.comment) { out.textContent = "Add a comment first."; return; }
    if (WEB.feedback_endpoint) {
      try {
        await fetch(WEB.feedback_endpoint, { method: "POST", mode: "no-cors", headers: { "Content-Type": "text/plain;charset=utf-8" }, body: JSON.stringify(payload) });
        out.textContent = "Thanks. Your feedback was sent to the planning team.";
        addPin(payload);
        $("#fb-text").value = "";
        setTimeout(() => { $("#fb").hidden = true; }, 1600);
      } catch (err) { out.textContent = `Could not send: ${err.message}. Try again or use the copy option below.`; fbFallback(payload, out); }
    } else fbFallback(payload, out);
  });
  function fbFallback(payload, out) {
    const text = `[${payload.topic}] ${payload.comment}\nLocation: ${payload.lat}, ${payload.lon} (zoom ${payload.zoom})\nScenario: ${payload.scenario}\nFrom: ${payload.name || "anonymous"} ${payload.org ? "(" + payload.org + ")" : ""}\nSettings: ${JSON.stringify({ weights: payload.weights, routing: payload.routing })}`;
    const issue = WEB.repo ? `https://github.com/${WEB.repo}/issues/new?title=${encodeURIComponent("Planner feedback: " + payload.topic)}&body=${encodeURIComponent(text)}` : null;
    out.innerHTML = `Feedback collection is not connected yet. Copy your comment and send it to the planning team${issue ? `, or <a href="${issue}" target="_blank" rel="noopener">open it as a GitHub issue</a>` : ""}.
      <textarea readonly rows="4" id="fb-copytext"></textarea><button class="btn" type="button" id="fb-copy">Copy</button>`;
    $("#fb-copytext").value = text;
    $("#fb-copy").addEventListener("click", async () => {
      try { await navigator.clipboard.writeText(text); $("#fb-copy").textContent = "Copied"; } catch { $("#fb-copytext").select(); }
    });
  }
  function addPin(p) {
    L.circleMarker([p.lat, p.lon], { pane: "hubs", radius: 6, weight: 2, color: tok("--ink"), fillColor: tok("--ochre"), fillOpacity: 1 })
      .bindTooltip(`<b>${esc(p.topic)}</b><br>${esc(p.comment)}<br><span class="k">${esc(p.name || "anonymous")}${p.org ? " · " + esc(p.org) : ""} · ${esc((p.ts || "").slice(0, 10))}</span>`, { className: "cell-tip", maxWidth: 280 })
      .addTo(fbLayer);
  }
  async function loadPins() {
    if (!WEB.feedback_endpoint) return;
    try {
      const r = await fetch(WEB.feedback_endpoint + (WEB.feedback_endpoint.includes("?") ? "&" : "?") + "action=list");
      const j = await r.json();
      (j.items || j || []).forEach(addPin);
    } catch { /* list is optional */ }
  }
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") { fbPicking = false; document.body.classList.remove("picking"); status(null); $("#fb").hidden = true; } });

  // theme changes re-read tokens
  const rerender = () => { restyle(); drawTrails(); drawRoads(); drawPlanned(); drawPadus(); drawCorridors(); };
  window.matchMedia("(prefers-color-scheme: dark)").addEventListener?.("change", rerender);
  new MutationObserver(rerender).observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });

  // ---------------------------------------------------------------- go
  syncWeightUI(); legend(); dataPanel(); layerHints();
  drawTrails(); drawRoads(); drawPlanned(); drawPadus();
  loadPins();
  compute();
})();
