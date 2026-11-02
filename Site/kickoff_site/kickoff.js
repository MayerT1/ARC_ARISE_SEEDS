/* SEEDS kickoff site. All content comes from site.json (edit on GitHub) plus live folders:
   - Google Drive folders (listed with a Drive API key, or embedded folder view without one)
   - folders in this repository (GitHub contents API)
   - plain links. */
(async function () {
  "use strict";
  const $ = (s) => document.querySelector(s);
  const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const REPO = { owner: "MayerT1", repo: "ARC_ARISE_SEEDS", branch: "main" };
  const SITE_DIR = "Site/kickoff_site";   // this site's folder in the repository

  let S;
  try {
    S = await (await fetch("site.json", { cache: "no-cache" })).json();
  } catch (e) {
    document.querySelector("main").insertAdjacentHTML("afterbegin", `<p class="note" style="padding:16px">Could not load site.json: ${esc(e.message)}</p>`);
    return;
  }

  // ---------------------------------------------------------------- event
  const ev = S.event || {};
  document.title = ev.title || document.title;
  $("#ev-title").textContent = ev.title || "";
  $("#ev-subtitle").textContent = ev.subtitle || "";
  $("#ev-when").textContent = ev.when || "To be confirmed";
  $("#ev-status").textContent = ev.when_status || "";
  $("#ev-time").textContent = ev.default_times || "To be confirmed";
  $("#ev-where").textContent = ev.where || "To be confirmed";
  $("#ev-join").innerHTML = ev.join_link ? `<a href="${esc(ev.join_link)}" target="_blank" rel="noopener">Join remotely</a>` : "";
  $("#ev-hosts").textContent = ev.hosts || "";
  $("#foot-updated").textContent = ev.updated ? `Updated ${ev.updated}` : "";

  // ---------------------------------------------------------------- outcomes
  const outcomes = Object.fromEntries((S.outcomes || []).map((o) => [o.id, o]));
  $("#outcomes-list").innerHTML = (S.outcomes || []).map((o) =>
    `<li><span class="oid">${esc(o.id)}</span><b>${esc(o.title)}</b><p>${esc(o.text)}</p></li>`).join("");
  const tags = (ids) => (ids || []).map((id) => `<span class="tag" title="${esc(outcomes[id]?.title || "")}">${esc(id)}</span>`).join(" ");

  // ---------------------------------------------------------------- agenda (site.json or a published Google Sheet CSV)
  function parseCSV(text) {
    const rows = []; let row = [], cell = "", q = false;
    for (let i = 0; i < text.length; i++) {
      const c = text[i];
      if (q) { if (c === '"' && text[i + 1] === '"') { cell += '"'; i++; } else if (c === '"') q = false; else cell += c; }
      else if (c === '"') q = true;
      else if (c === ",") { row.push(cell); cell = ""; }
      else if (c === "\n" || c === "\r") { if (c === "\r" && text[i + 1] === "\n") i++; row.push(cell); rows.push(row); row = []; cell = ""; }
      else cell += c;
    }
    if (cell || row.length) { row.push(cell); rows.push(row); }
    const [head, ...body] = rows.filter((r) => r.some((x) => x.trim()));
    return body.map((r) => Object.fromEntries(head.map((h, i) => [h.trim().toLowerCase(), (r[i] || "").trim()])));
  }
  let agenda = S.agenda || [];
  if (S.agenda_csv_url) {
    try {
      const rows = parseCSV(await (await fetch(S.agenda_csv_url, { cache: "no-cache" })).text());
      if (rows.length) {
        agenda = rows.map((r) => ({ ...r, outcomes: (r.outcomes || "").split(/[\s,;]+/).filter(Boolean) }));
        $("#agenda-note").textContent += " Live from the agenda sheet.";
      }
    } catch { /* keep site.json agenda */ }
  }
  const exById = Object.fromEntries((S.exercises || []).map((x) => [x.id, x]));
  $("#agenda-tbl").innerHTML = `<thead><tr><th>Time</th><th>Session</th><th>Lead</th><th>Type</th><th>Builds</th></tr></thead><tbody>${agenda.map((a) => {
    const ex = a.exercise && exById[a.exercise];
    return `<tr class="k-${esc((a.format || "").replace(/\s/g, "-"))}">
      <td class="t"><b>${esc(a.start)}</b>${a.end ? `–${esc(a.end)}` : ""}</td>
      <td class="s"><b>${esc(a.title)}</b>${a.detail ? `<p>${esc(a.detail)}</p>` : ""}${ex ? `<a href="#ex-${esc(ex.id)}" data-open="${esc(ex.id)}">Exercise ${esc(ex.id)}: ${esc(ex.title)}</a>` : ""}</td>
      <td class="who">${esc(a.lead)}</td>
      <td><span class="fmt ${esc((a.format || "").replace(/\s/g, "-"))}">${esc(a.format)}</span></td>
      <td>${tags(a.outcomes)}</td></tr>`;
  }).join("")}</tbody>`;
  document.addEventListener("click", (e) => {
    const id = e.target.closest("[data-open]")?.dataset.open;
    if (id) { const d = document.getElementById(`ex-${id}`); if (d) d.open = true; }
  });

  // ---------------------------------------------------------------- roles
  $("#roles-grid").innerHTML = (S.partners || []).map((p) => `<article class="role">
    <div><div class="ab">${esc(p.short)}</div><div class="nm">${esc(p.org)}</div></div>
    <div class="rl">${esc(p.role)}</div>
    <ul>${(p.tasks || []).map((t) => `<li>${esc(t)}</li>`).join("")}</ul></article>`).join("");

  // ---------------------------------------------------------------- exercises
  const list = (arr, tag = "ul") => (arr && arr.length ? `<${tag}>${arr.map((x) => `<li>${esc(x)}</li>`).join("")}</${tag}>` : "");
  $("#ex-list").innerHTML = (S.exercises || []).map((x) => `<details class="ex" id="ex-${esc(x.id)}">
    <summary><span class="eid">${esc(x.id)}</span><span class="et">${esc(x.title)} <span class="chev">›</span></span>
      <span class="em">${x.minutes ? `${esc(x.minutes)} min` : ""} ${tags(x.outcomes)}</span>
      <p class="ep">${esc(x.purpose)}</p></summary>
    <div class="body">
      <div class="steps"><h4>Steps</h4>${list(x.steps, "ol")}</div>
      <div><h4>Lead</h4><p>${esc(x.lead || "")}</p></div>
      <div><h4>Materials</h4>${list(x.materials)}</div>
      <div><h4>Output</h4><p>${esc(x.output)}</p></div>
      ${x.metrics ? `<div><h4>Planning metrics practiced</h4>${list(x.metrics)}</div>` : ""}
      ${x.digital ? `<div><h4>Digital version</h4><p>${esc(x.digital)}</p></div>` : ""}
    </div></details>`).join("");
  if (location.hash.startsWith("#ex-")) { const d = document.getElementById(location.hash.slice(1)); if (d) d.open = true; }
  window.addEventListener("beforeprint", () => document.querySelectorAll("details.ex").forEach((d) => (d.open = true)));

  // ---------------------------------------------------------------- materials
  const M = S.materials || {};
  const KEY = M.drive_api_key || "";
  const strip = (name) => name.replace(/^\s*\d+[\s._-]+/, "");             // "01_Slides" -> "Slides"
  const kindOf = (mime = "", name = "") => {
    const n = name.toLowerCase();
    if (mime.includes("folder")) return ["folder", "dir"];
    if (mime.includes("pdf") || n.endsWith(".pdf")) return ["pdf", "pdf"];
    if (mime.includes("presentation") || /\.(pptx?|key)$/.test(n)) return ["slides", "ppt"];
    if (mime.includes("spreadsheet") || /\.(xlsx?|csv)$/.test(n)) return ["sheet", "xls"];
    if (mime.includes("document") || mime.includes("word") || /\.(docx?|md|txt)$/.test(n)) return ["doc", "doc"];
    if (mime.startsWith("image") || /\.(png|jpe?g|gif|svg|webp)$/.test(n)) return ["img", "img"];
    if (mime.startsWith("video") || /\.(mp4|mov|webm)$/.test(n)) return ["video", "vid"];
    if (mime.includes("shortcut") || mime.includes("link")) return ["", "lnk"];
    return ["", "file"];
  };
  const driveView = (f) => {
    const m = f.mimeType || "";
    if (m === "application/vnd.google-apps.presentation") return `https://docs.google.com/presentation/d/${f.id}/embed`;
    if (m === "application/vnd.google-apps.document") return `https://docs.google.com/document/d/${f.id}/preview`;
    if (m === "application/vnd.google-apps.spreadsheet") return `https://docs.google.com/spreadsheets/d/${f.id}/preview`;
    if (m.includes("folder")) return null;
    return `https://drive.google.com/file/d/${f.id}/preview`;
  };
  const fileCard = ({ name, kind, label, meta, open, preview }) => `<div class="file">
    <span class="ic ${kind}">${esc(label)}</span>
    <span class="fn">${esc(name)}</span>
    <span class="fm">${meta ? `<span>${esc(meta)}</span>` : ""}${preview ? `<button type="button" data-preview="${esc(preview)}" data-title="${esc(name)}" data-open-url="${esc(open)}">Preview</button>` : ""}${open ? `<a href="${esc(open)}" target="_blank" rel="noopener">Open</a>` : ""}</span></div>`;
  const fmtDate = (s) => (s ? new Date(s).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" }) : "");

  async function driveList(folderId) {
    const q = encodeURIComponent(`'${folderId}' in parents and trashed = false`);
    const fields = encodeURIComponent("nextPageToken,files(id,name,mimeType,modifiedTime,webViewLink,shortcutDetails)");
    let out = [], token = "";
    do {
      const url = `https://www.googleapis.com/drive/v3/files?q=${q}&fields=${fields}&orderBy=folder,name&pageSize=200&supportsAllDrives=true&includeItemsFromAllDrives=true&key=${encodeURIComponent(KEY)}${token ? `&pageToken=${token}` : ""}`;
      const r = await fetch(url);
      const j = await r.json();
      if (j.error) throw new Error(j.error.message || `Drive error ${j.error.code}`);
      out = out.concat(j.files || []);
      token = j.nextPageToken || "";
    } while (token);
    return out;
  }
  const driveCards = (files) => files.map((f) => {
    const [kind, label] = kindOf(f.mimeType, f.name);
    const open = f.webViewLink || (kind === "folder" ? `https://drive.google.com/drive/folders/${f.id}` : `https://drive.google.com/file/d/${f.id}/view`);
    return fileCard({ name: kind === "folder" ? strip(f.name) : f.name.replace(/\.[a-z0-9]{2,4}$/i, ""), kind, label,
      meta: fmtDate(f.modifiedTime), open, preview: driveView(f) });
  }).join("");
  const embedFolder = (id) => `<iframe class="embed" src="https://drive.google.com/embeddedfolderview?id=${encodeURIComponent(id)}#list" title="Drive folder" loading="lazy"></iframe>`;

  async function repoList(path) {
    const url = `https://api.github.com/repos/${REPO.owner}/${REPO.repo}/contents/${path.split("/").map(encodeURIComponent).join("/")}?ref=${REPO.branch}`;
    const r = await fetch(url, { headers: { Accept: "application/vnd.github+json" } });
    if (!r.ok) throw new Error(`GitHub ${r.status}`);
    const items = (await r.json()).filter((x) => !x.name.startsWith("."));
    return items.map((x) => {
      const [kind, label] = kindOf(x.type === "dir" ? "folder" : "", x.name);
      // files inside this site's own folder are served by Pages next to the page itself
      const pages = path.startsWith(SITE_DIR + "/") || path === SITE_DIR
        ? (path === SITE_DIR ? "" : path.slice(SITE_DIR.length + 1) + "/") + x.name : null;
      const open = x.type === "dir" ? x.html_url : pages || x.download_url || x.html_url;
      return fileCard({ name: x.type === "dir" ? strip(x.name) : x.name.replace(/\.[a-z0-9]{2,4}$/i, ""), kind, label, meta: "",
        open, preview: kind === "pdf" || kind === "img" ? open : null });
    }).join("");
  }

  const matBox = $("#mat-sections");
  const section = (title, html, extra = "") => `<div class="mat"><h3>${esc(title)} ${extra}</h3>${html}</div>`;
  const blocks = [], cfgBlocks = [];
  // 1) sections configured in site.json (shown after the Drive sections)
  for (const s of M.sections || []) {
    if (!s.drive_folder && !s.repo_path && !(s.links || []).length) continue;  // empty placeholder
    let html = "";
    try {
      if (s.drive_folder) html = KEY ? `<div class="files">${driveCards(await driveList(s.drive_folder)) || ""}</div>` : embedFolder(s.drive_folder);
      else if (s.repo_path) html = `<div class="files">${await repoList(s.repo_path)}</div>`;
    } catch (e) { html = `<p class="empty">Could not list this folder: ${esc(e.message)}</p>`; }
    const links = (s.links || []).map((l) => {
      const [kind, label] = kindOf("", l.url);
      return fileCard({ name: l.name, kind, label, meta: "", open: l.url, preview: kind === "pdf" ? l.url : null });
    }).join("");
    if (links) html += `<div class="files">${links}</div>`;
    if (!html.replace(/<[^>]+>/g, "").trim() && !html.includes("iframe")) html = `<p class="empty">Nothing here yet.</p>`;
    cfgBlocks.push(section(s.title, html, s.drive_folder ? `<a href="https://drive.google.com/drive/folders/${esc(s.drive_folder)}" target="_blank" rel="noopener">Open folder</a>` : ""));
  }
  // 2) every subfolder of the Drive root becomes a section automatically
  let note = "";
  if (M.drive_root_folder_id) {
    const rootLink = `<a href="https://drive.google.com/drive/folders/${esc(M.drive_root_folder_id)}" target="_blank" rel="noopener">Open the event folder</a>`;
    if (KEY && M.auto_sections_from_drive !== false) {
      try {
        const items = await driveList(M.drive_root_folder_id);
        const folders = items.filter((f) => f.mimeType === "application/vnd.google-apps.folder");
        const loose = items.filter((f) => f.mimeType !== "application/vnd.google-apps.folder");
        const taken = new Set((M.sections || []).map((s) => s.drive_folder).filter(Boolean));
        for (const f of folders) {
          if (taken.has(f.id)) continue;
          const files = await driveList(f.id);
          blocks.push(section(strip(f.name), files.length ? `<div class="files">${driveCards(files)}</div>` : `<p class="empty">Nothing here yet.</p>`,
            `<a href="https://drive.google.com/drive/folders/${esc(f.id)}" target="_blank" rel="noopener">Open folder</a>`));
        }
        if (loose.length) blocks.push(section("Other files", `<div class="files">${driveCards(loose)}</div>`));
        note = `Live from the shared Drive folder. Add a file or a new subfolder there and it appears here on the next page load. ${rootLink}`;
      } catch (e) {
        note = `The Drive folder could not be listed (${esc(e.message)}). Showing the folder view instead. ${rootLink}`;
        blocks.unshift(section("Event folder", embedFolder(M.drive_root_folder_id)));
      }
    } else {
      blocks.unshift(section("Event folder", embedFolder(M.drive_root_folder_id), rootLink));
      note = "Live view of the shared Drive folder.";
    }
  } else {
    note = "Slides, handouts and notes will appear here once the shared folder is connected.";
  }
  $("#mat-note").innerHTML = note;
  matBox.innerHTML = blocks.concat(cfgBlocks).join("");

  // preview dialog
  const dlg = $("#viewer");
  matBox.addEventListener("click", (e) => {
    const b = e.target.closest("[data-preview]");
    if (!b) return;
    $("#viewer-title").textContent = b.dataset.title;
    $("#viewer-open").href = b.dataset.openUrl || b.dataset.preview;
    $("#viewer-frame").src = b.dataset.preview;
    dlg.showModal ? dlg.showModal() : dlg.setAttribute("open", "");
  });
  $("#viewer-close").addEventListener("click", () => { $("#viewer-frame").src = "about:blank"; dlg.close(); });
  dlg.addEventListener("close", () => { $("#viewer-frame").src = "about:blank"; });

  // ---------------------------------------------------------------- pre-work + links
  $("#prework-list").innerHTML = (S.prework || []).map((p) => `<li>${esc(p)}</li>`).join("");
  $("#links-list").innerHTML = (S.links || []).map((l) => `<li><a href="${esc(l.url)}" target="_blank" rel="noopener">${esc(l.label)}</a></li>`).join("");

  // ---------------------------------------------------------------- RSVP
  const R = S.rsvp || {};
  $("#r-org").innerHTML = `<option value="">Choose…</option>` + (R.orgs || []).map((o) => `<option>${esc(o)}</option>`).join("");
  $("#rsvp-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const f = e.target, msg = $("#rsvp-msg"), fb = $("#rsvp-fallback");
    const data = Object.fromEntries(new FormData(f).entries());
    data.github = (data.github || "").trim().replace(/^@/, "").replace(/^https?:\/\/github\.com\//i, "").replace(/\/$/, "");
    if (!data.name || !data.org || !data.email) { msg.textContent = "Add your name, organization and email."; return; }
    if (data.github && !/^[a-z\d](?:[a-z\d]|-(?=[a-z\d])){0,38}$/i.test(data.github)) { msg.textContent = "That GitHub username doesn't look right: letters, numbers and single hyphens only."; return; }
    data.ts = new Date().toISOString();
    data.event = ev.title;
    if (R.endpoint) {
      try {
        await fetch(R.endpoint, { method: "POST", mode: "no-cors", headers: { "Content-Type": "text/plain;charset=utf-8" }, body: JSON.stringify(data) });
        msg.textContent = `Thanks, ${data.name.split(" ")[0]}. Your RSVP was sent.`;
        f.reset(); fb.hidden = true;
        return;
      } catch (err) { msg.textContent = `Could not send (${err.message}). Use the option below.`; }
    } else {
      msg.textContent = "RSVPs are not connected yet. Use one of the options below.";
    }
    const text = `SEEDS kickoff RSVP\nName: ${data.name}\nOrganization: ${data.org}\nEmail: ${data.email}\nGitHub: ${data.github || "(none yet)"}\nAttending: ${data.mode}\nRole: ${data.role || ""}\nNotes: ${data.note || ""}`;
    const issue = `https://github.com/${REPO.owner}/${REPO.repo}/issues/new?title=${encodeURIComponent(`Kickoff RSVP: ${data.name} (${data.org})`)}&labels=rsvp&body=${encodeURIComponent(text)}`;
    fb.hidden = false;
    fb.innerHTML = `<p class="note">Copy this and send it to the organizers, or <a href="${issue}" target="_blank" rel="noopener">post it as a GitHub issue</a> (needs a GitHub account).</p>
      <textarea rows="7" readonly id="rsvp-copytext"></textarea><div class="row"><button class="btn" type="button" id="rsvp-copy">Copy</button></div>`;
    $("#rsvp-copytext").value = text;
    $("#rsvp-copy").addEventListener("click", async () => {
      try { await navigator.clipboard.writeText(text); $("#rsvp-copy").textContent = "Copied"; } catch { $("#rsvp-copytext").select(); }
    });
  });
})();
