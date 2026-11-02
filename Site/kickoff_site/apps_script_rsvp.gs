/**
 * SEEDS kickoff RSVP collector (Google Apps Script web app) — collects names, orgs and GitHub usernames.
 *
 * Setup (5 minutes):
 *  1. In the Kickoff_Event Drive folder create a Google Sheet "Kickoff RSVPs". Extensions > Apps Script.
 *  2. Paste this file and save.
 *  3. Deploy > New deployment > Web app. Execute as: Me. Who has access: Anyone.
 *  4. Copy the /exec URL into docs/kickoff/site.json -> "rsvp": {"endpoint": "<URL>"} and push.
 * Each RSVP becomes a row. The "github" column is the list of usernames to add as repository collaborators.
 */
const SHEET = "rsvp";
const COLS = ["ts", "name", "org", "email", "github", "mode", "role", "note", "event"];

function sheet_() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let sh = ss.getSheetByName(SHEET);
  if (!sh) { sh = ss.insertSheet(SHEET); sh.appendRow(COLS); sh.setFrozenRows(1); }
  return sh;
}

function doPost(e) {
  const lock = LockService.getScriptLock();
  lock.waitLock(10000);
  try {
    const p = JSON.parse(e.postData.contents);
    if (!p.name || !p.email) return out_({ ok: false, error: "name and email required" });
    sheet_().appendRow(COLS.map((c) => String(p[c] || "").slice(0, 1000)));
    return out_({ ok: true });
  } finally {
    lock.releaseLock();
  }
}

function doGet() {
  return out_({ ok: true, info: "SEEDS kickoff RSVP endpoint" });  // RSVPs are never returned publicly
}

function out_(o) {
  return ContentService.createTextOutput(JSON.stringify(o)).setMimeType(ContentService.MimeType.JSON);
}
