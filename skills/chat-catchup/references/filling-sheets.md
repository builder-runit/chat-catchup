# Filling the user's name into a sheet

A sheet is shared by the whole club. A name typed in the wrong cell takes someone else's slot or signs the user up for something they did not choose, and everyone can see it. So: go slowly, type in exactly one cell, and check the result.

> Status: the reading side of this was tested live. The editing steps follow how Google Sheets normally behaves but have not been run against a live edit, so verify each step on screen the first time.

## Checklist before you touch anything

All of these must be true. If any is not, do not edit; report it in the digest instead.

- `actions.fill_sheets` allows it (`ask` and the user said yes, or `auto` and the case is clear).
- The sheet really is a sign-up or assignment for something the user should do. Check the chat message that shared it, not just the sheet.
- The target row is not in `uncertain_rows` from `read_sheet.js`. If it is, look at the row on screen and use the cell you can see, or skip it and report it in the digest.
- The slot is empty **right now** (re-read the sheet just before typing: other people edit at the same time).
- The user is not already listed for it (`listed_in_name_column`, `matches`) and `state fills --url <link>` shows no earlier fill for that cell.
- It does not clash with `me.availability_notes`, and the sheet's own rules allow it ("max 2 per team", "seniors only").
- You can edit: the sheet is not in "Viewing" mode.

## Steps

1. Open the editor on the right tab: `https://docs.google.com/spreadsheets/d/<id>/edit#gid=<gid>`. Take a screenshot. Confirm you are in edit mode (there is no "View only" badge, and the cursor can select cells).
2. Go to the cell by address. Click the **Name Box** (the small box at the top left that shows the selected cell, such as `A1`), type the address from the scan (for example `D5`), press Enter. Zoom into the Name Box and the formula bar. The Name Box must show that address and the cell must be empty.
3. Type the user's `sign_up_as` text.
4. **Press Delete once, then Enter.** Sheets autocompletes from other values in the column, and Enter accepts the suggestion. Typing "Sam" in a column that contains "Sam T." would put "Sam T." in the cell. Delete removes the suggested tail first.
5. Wait about three seconds, then run `read_sheet.js` again for that tab. Confirm the cell holds exactly the text, and that the cells next to it did not change.
6. Record it: `catchup.py state log-fill --url <link> --tab "<tab>" --cell D5 --value "Alex R."`

If the text is wrong and you typed it, fix your own mistake: select that cell and press Delete, then redo steps 2 to 5 once. Tell the user what happened. Never clear or change a cell you did not write.

## Things that mean stop

- A message such as "You are trying to edit a protected cell or object": stop, do not look for a way around it, report it.
- A dropdown cell (data validation) that does not include the user's name: do not force text in. Report it.
- Merged cells, filtered views or hidden rows that make the address unclear: report it, do not guess.
- The tab or layout is different from what the scan saw: re-scan before doing anything.

## Undo

The digest says what was filled in. To undo: clear that one cell, or use File > Version history in the sheet. Tell the user this once, in the digest.
