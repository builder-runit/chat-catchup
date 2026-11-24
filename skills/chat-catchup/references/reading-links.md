# Reading the files linked in chats

`scripts/catchup.py links` tells you each link's `kind`. Open them in a browser tab that is already signed in to Google. Nothing here downloads a file or changes anything.

| kind | how to read it |
|---|---|
| `gsheet` | `scripts/browser/read_sheet.js` (below). Page text does not work for sheets. |
| `gdoc` | open `https://docs.google.com/document/d/<id>/mobilebasic`, then `get_page_text` |
| `gslides` | open the link, `get_page_text`; if empty, step through slides with screenshots |
| `gform` | open the link, `get_page_text` to read the questions. **Never submit.** |
| `gdrive_file`, `gdrive_folder` | open it only if the chat makes it relevant; read the page or list file names. Do not download. |
| `gcalendar`, `gmeet`, `gchat`, `gsite` | note that it exists (a meeting time, a site); no need to open |
| `external` | do not open on your own. Mention it in one line. |

> Status: the Sheets reader was tested live against a public sheet. The Docs, Slides and Forms rows follow Google's normal URL patterns but have not been verified in a live session. If one does not work, open the link normally and read the screen.

## Sheets

Why a script: Google Sheets draws its grid on a canvas, so `get_page_text` on a sheet returns almost nothing, and `/export?format=csv` is blocked from inside the page. `read_sheet.js` fetches the sheet's lightweight "htmlview" pages with the user's own sign-in and returns a grid with **real row numbers and column letters**. Those addresses are what make it safe to write into the correct cell later.

1. Open any `https://docs.google.com/` page in a tab (the sheet itself is fine).
2. Read `scripts/browser/read_sheet.js`, set `SHEET_ID` (the part after `/spreadsheets/d/`) and `TAB` (`null` for the first tab, a tab name, or a gid from the link's `#gid=`), and run it with `javascript_tool`.
3. The result is an object:
   - `tabs`: every tab's name and gid. If the sheet has several tabs, look at the ones that sound relevant (sign-ups, schedule, roster), not necessarily all.
   - `grid`: tab-separated text. The first line is `#<TAB>A<TAB>B...` and each row starts with its real row number. Empty rows are left out, which is why the numbers can skip.
   - `links`: addresses behind links inside cells.
   - `uncertain_rows`: row numbers where a cell was left out of Google's page, so the cells cannot be matched to column letters with certainty. Read those rows on screen, and never write into them without checking. `frozen_columns` is how many columns are frozen. Hidden columns are skipped, so letters can jump (A, then EM).
   - `truncated`: true if there were more than 500 rows. Re-run with a different tab or tell the user.
   - On failure, `ok: false` and `error`. `no_access_or_not_found` means the signed-in account cannot see the sheet.
4. Save `grid` to a file and run `scripts/catchup.py sheet-scan --file <that file> --url <link> --tab "<tab name>"`. See SKILL.md Step 3 for what to do with the result.

If `source` is `gviz-csv` the fallback path was used. It works but can read a text cell inside a mostly-numeric column as empty, so double-check anything important on screen before relying on it.

## Documents, slides, forms

Open in a **new tab**, read, close the tab. Read for: dates, deadlines, assignments by name, requirements ("bring", "wear", "complete before"), and links to other files. A one-paragraph summary per file is enough in the digest, plus the link.

For forms, the useful output is: what the form asks, who must fill it, and by when. Put the link in the digest as a to-do ("Fill in the travel form by Friday") and, if their settings make it obvious, suggested answers. The user submits it.

## Access problems

If a file shows "You need access", "Request access" or a sign-in page, record it under "Couldn't check" with its link and who shared it. Do not click Request access.
