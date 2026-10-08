/**
 * SEEDS Greenbelt Corridor Planner — feedback collector (Google Apps Script web app).
 *
 * Setup (5 minutes, no server):
 *  1. Create a Google Sheet (e.g. "SEEDS planner feedback"). Extensions > Apps Script.
 *  2. Paste this file, save.
 *  3. Deploy > New deployment > type "Web app".
 *       Execute as: Me        Who has access: Anyone
 *  4. Copy the web-app URL (ends in /exec) into config/seeds.yaml -> web.feedback_endpoint,
 *     rerun `python -m seeds_cds network` (or edit docs/data/config.json "web.feedback_endpoint"), push.
 *
 * The sheet gets one row per comment. Set column "show" to FALSE to hide a pin from the public map.
 * POST body: JSON sent by the planner (text/plain to avoid a CORS preflight).
 * GET ?action=list returns visible comments as JSON for the map's feedback pins.
 */
const SHEET = "feedback";
const COLS = ["ts", "lat", "lon", "topic", "comment", "name", "org", "scenario", "zoom",
              "weights", "routing", "data_generated", "show"];

function sheet_() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let sh = ss.getSheetByName(SHEET);
  if (!sh) {
    sh = ss.insertSheet(SHEET);
    sh.appendRow(COLS);
    sh.setFrozenRows(1);
  }
  return sh;
}

function doPost(e) {
  const lock = LockService.getScriptLock();
  lock.waitLock(10000);
  try {
    const p = JSON.parse(e.postData.contents);
    const comment = String(p.comment || "").slice(0, 4000);
    if (!comment || !isFinite(p.lat) || !isFinite(p.lon)) return json_({ ok: false, error: "missing comment or location" });
    sheet_().appendRow([
      p.ts || new Date().toISOString(), +p.lat, +p.lon, String(p.topic || "").slice(0, 80), comment,
      String(p.name || "").slice(0, 120), String(p.org || "").slice(0, 160), String(p.scenario || "").slice(0, 160),
      p.zoom || "", JSON.stringify(p.weights || {}), JSON.stringify(p.routing || {}), p.data_generated || "", true,
    ]);
    return json_({ ok: true });
  } finally {
    lock.releaseLock();
  }
}

function doGet(e) {
  if ((e.parameter.action || "") !== "list") return json_({ ok: true, info: "SEEDS feedback endpoint" });
  const rows = sheet_().getDataRange().getValues();
  const head = rows.shift();
  const ix = Object.fromEntries(head.map((h, i) => [h, i]));
  const items = rows
    .filter((r) => r[ix.show] !== false && String(r[ix.show]).toUpperCase() !== "FALSE")
    .map((r) => ({ ts: r[ix.ts], lat: r[ix.lat], lon: r[ix.lon], topic: r[ix.topic], comment: r[ix.comment],
                   name: r[ix.name], org: r[ix.org] }));
  return json_({ ok: true, items });
}

function json_(o) {
  return ContentService.createTextOutput(JSON.stringify(o)).setMimeType(ContentService.MimeType.JSON);
}
