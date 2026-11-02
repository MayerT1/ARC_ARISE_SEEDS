# SEEDS kickoff site

Source: `Site/kickoff_site/` in the repository. Published by `.github/workflows/pages.yml` at
`https://mayert1.github.io/ARC_ARISE_SEEDS/kickoff/` on every push to `main`.

| What | Where to change it |
|---|---|
| Event details, outcomes, agenda, roles, exercises, pre-work, links | `site.json` (edit on GitHub; the site updates about a minute after you commit) |
| Agenda only, edited as a spreadsheet | Publish a Google Sheet with the columns of `templates/agenda.csv` (File > Share > Publish to web > CSV) and put the URL in `site.json` → `agenda_csv_url` |
| Slides, PDFs, handouts, notes, media | Drop them into the Drive folder `Kickoff_Event`; they appear on the site automatically |
| RSVPs and GitHub usernames | Google Sheet behind `apps_script_rsvp.gs` |

## Connect the Drive folder (once, about 10 minutes)

1. **Folders.** Inside `Kickoff_Event`, make one subfolder per section. A number prefix sets the order and is hidden on the site:
   `01_Agenda`, `02_Slides`, `03_Exercises`, `04_Readings`, `05_Notes & outputs`, `06_Media`.
   A new subfolder becomes a new section; a new file shows up in its section.
2. **Share.** Share `Kickoff_Event` as *Anyone with the link: Viewer*. The site can only list what the public link can see. If your Workspace blocks public links, use a personal Drive folder or put files in `Site/kickoff_site/files/` and set `repo_path` instead.
3. **Folder id.** Open the folder in Drive. The id is the last part of the URL: `drive.google.com/drive/folders/<THIS_PART>`. Put it in `site.json` → `materials.drive_root_folder_id`.
4. **API key.** This lets the site list files as cards with previews. Without it, the site shows Google's plain folder view, which still updates live.
   - In the Google Cloud console, pick a project (e.g. servir-sco-assets): APIs & Services > Library > enable **Google Drive API**.
   - Credentials > Create credentials > API key.
   - Restrict the key: *Application restrictions* = Websites, add `https://mayert1.github.io/*` (and `http://localhost:*` for local tests). *API restrictions* = Google Drive API.
   - Put the key in `site.json` → `materials.drive_api_key`. A key restricted to your site and to read-only Drive listing is safe to publish; it can only read files that are already public.

## RSVPs

Deploy `apps_script_rsvp.gs` (steps at the top of the file) and put the web-app URL in `site.json` → `rsvp.endpoint`.
The `github` column in the sheet is the list of people to add under the repository's Settings > Collaborators.
Until it is connected, the form offers copy-ready text and a pre-filled GitHub issue.

## Sections that are not on Drive

Any entry in `materials.sections` can point to:
- `drive_folder`: a specific Drive folder id
- `repo_path`: a folder in this repository, for example `Site/kickoff_site/files/slides` (drop files there and push)
- `links`: a list of `{ "name": ..., "url": ... }`

Moving off Drive later means changing those entries, not the site.
