import unittest

import helpers
from chatcatchup import sheets

SAMPLE = (helpers.EXAMPLES / "sample-signup-sheet.tsv").read_text(encoding="utf-8")


class GridTests(unittest.TestCase):
    def test_column_letters(self):
        self.assertEqual([sheets.col_letters(i) for i in (0, 25, 26, 51, 52, 701, 702)], ["A", "Z", "AA", "AZ", "BA", "ZZ", "AAA"])

    def test_a1_grid_keeps_real_row_numbers(self):
        grid = sheets.parse_grid(SAMPLE)
        self.assertEqual(grid.letters, list("ABCDE"))
        self.assertEqual([n for n, _ in grid.rows], [1, 3, 4, 5, 6, 7, 8, 9, 10])  # row 2 was empty, so it is absent

    def test_csv_rows_are_numbered_from_one(self):
        grid = sheets.parse_grid('Name,Task\n"Smith, Jo",Wiring\n,\nAlex,"Line one\nline two"\n')
        self.assertEqual([n for n, _ in grid.rows], [1, 2, 3, 4])
        self.assertEqual(grid.rows[1][1], ["Smith, Jo", "Wiring"])
        self.assertEqual(grid.rows[3][1][1], "Line one\nline two")

    def test_short_rows_are_padded(self):
        grid = sheets.parse_grid("#\tA\tB\tC\n1\tx\n")
        self.assertEqual(grid.rows, [(1, ["x", "", ""])])


class ScanTests(unittest.TestCase):
    def scan(self, **kw):
        kw.setdefault("names", ["Alex", "Alex R."])
        return sheets.scan(SAMPLE, **kw)

    def test_finds_header_and_name_column(self):
        result = self.scan()
        self.assertEqual(result["header_row"], 3)
        self.assertEqual(result["name_columns"], [{"column": "D", "header": "Name"}])

    def test_open_slots_have_exact_cell_addresses_and_context(self):
        result = self.scan()
        cells = [s["cell"] for s in result["open_slots"]]
        self.assertEqual(cells, ["D5", "D7", "D9", "D10"])
        first = result["open_slots"][0]
        self.assertEqual(first["context"]["Task"], "Auto routine coding")
        self.assertEqual(first["context"]["Subteam"], "Programming")
        self.assertNotIn("Name", first["context"])
        self.assertEqual(result["open_slot_count"], 4)

    def test_avoided_kinds_are_blocked_and_never_offered(self):
        result = sheets.scan(SAMPLE, ["Alex"], avoid=["outreach", "wiring"])
        self.assertEqual([s["cell"] for s in result["open_slots"]], ["D5", "D7"])
        self.assertEqual(result["open_slot_count"], 2)
        blocked = {b["cell"]: b["blocked_by"] for b in result["blocked_slots"]}
        self.assertEqual(blocked, {"D9": ["wiring"], "D10": ["outreach"]})

    def test_wanted_kinds_are_listed_first_and_marked(self):
        result = sheets.scan(SAMPLE, ["Alex"], interests=["outreach"])
        self.assertEqual([s["cell"] for s in result["open_slots"]], ["D10", "D5", "D7", "D9"])
        self.assertEqual(result["open_slots"][0]["matches_interest"], ["outreach"])
        self.assertNotIn("matches_interest", result["open_slots"][1])

    def test_without_preferences_nothing_is_blocked_or_reordered(self):
        result = sheets.scan(SAMPLE, ["Alex"])
        self.assertEqual(result["blocked_slots"], [])
        self.assertEqual([s["cell"] for s in result["open_slots"]], ["D5", "D7", "D9", "D10"])

    def test_slot_with_nothing_describing_it_is_not_a_slot(self):
        text = "#\tA\tB\n1\tTask\tName\n2\tWiring\t\n3\t\t\n"
        self.assertEqual([s["cell"] for s in sheets.scan(text, ["Alex"])["open_slots"]], ["B2"])

    def test_notices_when_you_are_already_listed(self):
        result = self.scan()
        self.assertTrue(result["listed_in_name_column"])
        match = next(m for m in result["matches"] if m["cell"] == "D8")
        self.assertEqual(match["matched"], {"name": ["Alex", "Alex R."]})  # both aliases hit this cell
        self.assertEqual(match["context"]["Task"], "Pit crew practice")

    def test_not_listed_when_name_is_absent(self):
        result = self.scan(names=["Priya"])
        self.assertFalse(result["listed_in_name_column"])
        self.assertEqual(result["matches"], [])

    def test_name_matching_is_whole_word_and_case_insensitive(self):
        text = "#\tA\tB\n1\tTask\tName\n2\tWiring\tAlexandra\n3\tTesting\tALEX\n"
        cells = [m["cell"] for m in sheets.scan(text, ["Alex"])["matches"]]
        self.assertEqual(cells, ["B3"])  # not "Alexandra"

    def test_team_keywords_flag_relevant_rows(self):
        result = self.scan(teams=["Programming"])
        team_cells = [m["cell"] for m in result["matches"] if "team" in m["matched"]]
        self.assertEqual(team_cells, ["C5", "C7"])

    def test_email_matches(self):
        text = "#\tA\tB\n1\tTask\tEmail\n2\tWiring\talex@example.com\n"
        result = sheets.scan(text, ["Nobody"], emails=["Alex@Example.com"])
        self.assertEqual(result["matches"][0]["matched"], {"email": ["Alex@Example.com"]})

    def test_append_slot_points_below_the_last_name(self):
        text = "#\tA\n1\tName\n2\tJo\n3\tSam\n"
        self.assertEqual(sheets.scan(text, ["Alex"])["append_slots"], [{"column": "A", "header": "Name", "next_empty_cell": "A4"}])

    def test_a_title_in_a_one_column_sheet_is_not_mistaken_for_the_header(self):
        text = "#\tA\n1\tFall Sign-ups\n2\tName\n3\tJo\n"
        result = sheets.scan(text, ["Alex"])
        self.assertEqual(result["header_row"], 2)
        self.assertEqual(result["append_slots"][0]["next_empty_cell"], "A4")

    def test_grid_layouts_get_an_honest_note_instead_of_guesses(self):
        text = "#\tA\tB\tC\n1\tRole\tMon\tTue\n2\tDriver\tJo\t\n"
        result = sheets.scan(text, ["Alex"])
        self.assertEqual(result["name_columns"], [])
        self.assertEqual(result["open_slots"], [])
        self.assertTrue(any("grid" in n for n in result["notes"]))

    def test_max_slots_caps_output_but_not_the_count(self):
        text = "#\tA\tB\n1\tTask\tName\n" + "".join(f"{i}\tjob {i}\t\n" for i in range(2, 30))
        result = sheets.scan(text, ["Alex"], max_slots=5)
        self.assertEqual(len(result["open_slots"]), 5)
        self.assertEqual(result["open_slot_count"], 28)

    def test_empty_sheet(self):
        self.assertIn("empty", sheets.scan("", ["Alex"])["notes"][0])

    def test_scan_never_edits_input(self):
        before = SAMPLE
        self.scan()
        self.assertEqual(before, SAMPLE)


if __name__ == "__main__":
    unittest.main()
