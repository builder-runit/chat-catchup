"""Runs scripts/browser/read_sheet.js under Node against saved page shapes.

The fixtures copy the structure of Google's "htmlview" pages, including the quirk that broke
cell addresses on a real sheet: a spacer cell ("freezebar-cell") between frozen and scrolling
columns, and hidden columns (letters jump from A to EM). Skipped when Node is not installed.
"""
import json
import shutil
import subprocess
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "skills" / "chat-catchup" / "scripts" / "browser" / "read_sheet.js"

HARNESS = r"""
const fs = require('fs');
const {pages, tab} = JSON.parse(fs.readFileSync(0, 'utf8'));
let src = fs.readFileSync(process.argv[1], 'utf8')
  .replace(/^const SHEET_ID = .*$/m, "const SHEET_ID = 'SHEET';")
  .replace(/^const TAB = .*$/m, `const TAB = ${JSON.stringify(tab)};`);
src = src.replace(/\nresult;\s*$/, '\nreturn result;');
const fetch = async url => ({status: pages[url] ? 200 : 404, headers: {get: () => 'text/html'}, text: async () => pages[url] || ''});
const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor;
new AsyncFunction('fetch', 'location', 'document', src)(fetch, {origin: 'https://docs.google.com'}, {querySelectorAll: () => []})
  .then(r => console.log(JSON.stringify(r)));
"""


def _page(tabs):
    items = "".join(f'items.push({{name: "{n}", pageUrl: "/tab/{g}", gid: "{g}"}});' for n, g in tabs)
    return f"<html><script>{items}</script></html>"


def _table(head_cells, rows):
    return "<html><table><thead><tr>" + head_cells + "</tr></thead><tbody>" + rows + "</tbody></table></html>"


FREEZE_TH = '<th class="freezebar-cell"></th>'
FREEZE_TD = '<td class="freezebar-cell"></td>'


def _th(letter, col):
    return f'<th id="1C{col}" style="width:80px">{letter}</th>'


def _row(n, cells):
    return f'<tr><th id="1R{n - 1}" class="row-header"><div class="row-header-wrapper">{n}</div></th>{cells}</tr>'


def _td(text="", cls="s0"):
    return f'<td class="{cls}">{text}</td>'


def run_reader(pages, tab=None):
    proc = subprocess.run(["node", "-e", HARNESS, str(SCRIPT)], input=json.dumps({"pages": pages, "tab": tab}),
                          capture_output=True, text=True, timeout=30)
    if proc.returncode != 0:
        raise AssertionError(proc.stderr)
    return json.loads(proc.stdout)


def grid_cells(result):
    """{'EM1': '5/26/2026', ...} from the A1 grid the reader returns."""
    lines = result["grid"].split("\n")
    letters = lines[0].split("\t")[1:]
    out = {}
    for line in lines[1:]:
        number, *cells = line.split("\t")
        for letter, value in zip(letters, cells):
            if value:
                out[f"{letter}{number}"] = value
    return out


@unittest.skipUnless(shutil.which("node"), "Node is not installed")
class ReadSheetFrozenColumnTests(unittest.TestCase):
    def frozen_sheet(self):
        # A frozen column A, hidden columns B..EL, then scrolling columns EM..ER (like a real club sheet).
        head = '<th class="row-header"></th>' + _th("A", 0) + FREEZE_TH + "".join(
            _th(letter, 142 + i) for i, letter in enumerate(["EM", "EN", "EO"]))
        rows = (
            _row(1, _td("", "s0") + FREEZE_TD + _td("5/26/2026", "s1") + _td("5/27/2026", "s1") + _td("5/28/2026", "s1"))
            # Row 2 has no cell before the freeze bar, like the real sheet.
            + _row(2, FREEZE_TD + _td("Tuesday", "s2") + _td("Wednesday", "s2") + _td("Thursday", "s2"))
            # A spacer row with no row number must be skipped.
            + '<tr><th class="freezebar-cell"></th>' + FREEZE_TD * 4 + "</tr>"
            + _row(3, _td("Robotics Event") + FREEZE_TD + _td("", "s4") + _td("Build day", "s4") + _td("", "s4"))
            # Row 4 is missing a scrolling cell: addresses cannot be trusted.
            + _row(4, _td("Time") + FREEZE_TD + _td("9am", "s6") + _td("noon", "s6"))
        )
        return {"/spreadsheets/d/SHEET/htmlview": _page([("Controls", "1")]), "/tab/1": _table(head, rows)}

    def test_freeze_bar_is_not_counted_as_a_column(self):
        result = run_reader(self.frozen_sheet(), "Controls")
        self.assertTrue(result["ok"])
        cells = grid_cells(result)
        # 5/26 sits in column EM. Counting the spacer used to push it to EN.
        self.assertEqual(cells["EM1"], "5/26/2026")
        self.assertEqual(cells["EO1"], "5/28/2026")
        self.assertEqual(cells["EM2"], "Tuesday")
        self.assertEqual(cells["EO2"], "Thursday")
        self.assertEqual(cells["A3"], "Robotics Event")
        self.assertEqual(cells["EN3"], "Build day")
        self.assertNotIn("ER1", cells)
        self.assertEqual(result["frozen_columns"], 1)

    def test_header_uses_real_letters(self):
        result = run_reader(self.frozen_sheet(), "Controls")
        self.assertEqual(result["grid"].split("\n")[0], "#\tA\tEM\tEN\tEO")

    def test_rows_with_missing_cells_are_flagged_not_trusted(self):
        result = run_reader(self.frozen_sheet(), "Controls")
        self.assertEqual(result["uncertain_rows"], [4])

    def test_sheet_without_frozen_columns(self):
        head = '<th class="row-header"></th>' + "".join(_th(letter, i) for i, letter in enumerate("ABC"))
        rows = _row(1, _td("Name") + _td("Role") + _td("Day")) + _row(2, _td("Alex") + _td("Build") + _td("Sat"))
        pages = {"/spreadsheets/d/SHEET/htmlview": _page([("Sign-ups", "7")]), "/tab/7": _table(head, rows)}
        result = run_reader(pages)
        cells = grid_cells(result)
        self.assertEqual(cells["A2"], "Alex")
        self.assertEqual(cells["C2"], "Sat")
        self.assertEqual(result["uncertain_rows"], [])
        self.assertEqual(result["frozen_columns"], 0)


if __name__ == "__main__":
    unittest.main()
