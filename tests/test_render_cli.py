import json
import subprocess
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

import helpers
from chatcatchup import render

DIGEST = json.loads((helpers.EXAMPLES / "sample-digest.json").read_text(encoding="utf-8"))
CLI = str(helpers.SCRIPTS / "catchup.py")

try:
    import docx  # noqa: F401
    HAVE_DOCX = True
except ImportError:
    HAVE_DOCX = False


class RenderTests(unittest.TestCase):
    def md(self, digest=DIGEST):
        return render.blocks_to_md(render.build_blocks(digest))

    def test_sections_appear_in_reading_order(self):
        text = self.md()
        order = ["The short version", "What you need to do", "Decisions only you can make", "Sign-ups",
                 "Coming up", "Replies", "Chat by chat", "Couldn't check", "Notes"]
        positions = [text.index(f"## {h}") for h in order]
        self.assertEqual(positions, sorted(positions))

    def test_empty_sections_are_left_out(self):
        text = self.md({"title": "Quiet week", "tldr": ["Nothing to do."]})
        self.assertIn("# Quiet week", text)
        self.assertNotIn("What you need to do", text)
        self.assertNotIn("Sign-ups", text)

    def test_actions_are_checkboxes_sorted_by_date_and_done_last(self):
        lines = [l for l in self.md().splitlines() if l.startswith(("- [ ]", "- [x]"))]
        self.assertTrue(lines[0].startswith("- [ ] Turn in signed permission slip"))
        self.assertTrue(lines[-1].startswith("- [x] Sign up sheet"))
        undated = next(i for i, l in enumerate(lines) if "scouting rubric" in l)
        dated = max(i for i, l in enumerate(lines) if "due 2026-12-06" in l)
        self.assertGreater(undated, dated)  # no date -> after dated items

    def test_signup_statuses_are_in_plain_words(self):
        text = self.md()
        self.assertIn("Filled in for you: Auto routine coding", text)
        self.assertIn("Waiting for your OK: Auto routine testing", text)
        self.assertIn("You're already on it: Pit crew practice", text)

    def test_unsafe_links_are_never_rendered(self):
        bad = {"action_items": [{"task": "Click me", "link": "javascript:alert(1)"}, {"task": "File", "link": "file:///etc/passwd"}]}
        text = self.md(bad)
        self.assertNotIn("javascript:", text)
        self.assertNotIn("file://", text)
        self.assertIn("Click me", text)

    def test_tolerates_sloppy_input(self):
        text = self.md({"action_items": ["not a dict", {"task": None}], "tldr": [None, "ok"], "spaces": [{"name": "X", "unread": 3}]})
        self.assertIn("X (3 new)", text)

    def test_write_outputs_never_overwrites_an_earlier_digest(self):
        with tempfile.TemporaryDirectory() as tmp:
            first = render.write_outputs(DIGEST, tmp, ["md"], today=date(2026, 11, 23))
            second = render.write_outputs(DIGEST, tmp, ["md"], today=date(2026, 11, 23))
            self.assertTrue(first["written"][0].endswith("Chat Catch-up 2026-11-23.md"))
            self.assertTrue(second["written"][0].endswith("Chat Catch-up 2026-11-23 (2).md"))
            self.assertEqual(len(list(Path(tmp).iterdir())), 2)

    def test_write_outputs_creates_missing_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "a" / "b"
            self.assertEqual(len(render.write_outputs(DIGEST, target, ["md"])["written"]), 1)

    @unittest.skipUnless(HAVE_DOCX, "python-docx not installed")
    def test_docx_is_written_with_working_links(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = render.write_outputs(DIGEST, tmp, ["docx"], today=date(2026, 11, 23))
            path = Path(result["written"][0])
            document = docx.Document(str(path))
            text = "\n".join(p.text for p in document.paragraphs)
            self.assertIn("What you need to do", text)
            self.assertIn("☐ Turn in signed permission slip", text)
            self.assertIn("☑ Sign up sheet", text)
            targets = [r.target_ref for r in document.part.rels.values() if r.is_external]
            self.assertIn("https://docs.google.com/spreadsheets/d/EXAMPLE_FEES/edit", targets)

    @unittest.skipIf(HAVE_DOCX, "only meaningful when python-docx is missing")
    def test_missing_python_docx_is_a_warning_not_a_crash(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = render.write_outputs(DIGEST, tmp, ["md", "docx"])
            self.assertEqual(len(result["written"]), 1)
            self.assertIn("python-docx", result["warnings"][0])


class CliTests(helpers.IsolatedHome):
    def run_cli(self, *args, stdin=None, ok=True):
        proc = subprocess.run([sys.executable, CLI, *args], input=stdin, capture_output=True, text=True,
                              env={**__import__("os").environ})
        if ok:
            self.assertEqual(proc.returncode, 0, proc.stderr)
            return json.loads(proc.stdout)
        self.assertEqual(proc.returncode, 1)
        return proc.stderr

    def test_setup_interview_answers_flow_into_scan(self):
        self.run_cli("config", "init", "--name", "Alex", "--role", "student", "--grade", "10th",
                     "--skill", "CAD", "--interest", "programming", "--avoid", "outreach",
                     "--goals", "join drive team", "--fill-sheets", "ask", "--digest-detail", "short",
                     "--folder", str(self.home / "out"))
        shown = self.run_cli("config", "show")["config"]
        self.assertEqual((shown["me"]["role"], shown["me"]["avoid"], shown["digest_detail"]), ("student", ["outreach"], "short"))
        self.assertTrue(self.run_cli("doctor")["ok"])
        sheet = helpers.EXAMPLES / "sample-signup-sheet.tsv"
        result = self.run_cli("sheet-scan", "--file", str(sheet))
        self.assertEqual([s["cell"] for s in result["open_slots"]][:2], ["D5", "D7"])   # programming first
        self.assertEqual([b["cell"] for b in result["blocked_slots"]], ["D10"])         # outreach never offered

    def test_empty_profile_gets_a_hint(self):
        self.run_cli("config", "init", "--name", "Alex", "--folder", str(self.home / "out"))
        self.assertTrue(any("profile is empty" in h for h in self.run_cli("doctor")["hints"]))

    def test_full_first_run_flow(self):
        self.assertFalse(self.run_cli("doctor")["ok"])
        self.run_cli("config", "init", "--name", "Alex", "--name", "Al", "--sign-up-as", "Alex R.",
                     "--team", "Programming", "--folder", str(self.home / "out"))
        report = self.run_cli("doctor")
        self.assertTrue(report["ok"], report)
        self.run_cli("config", "set", "actions.fill_sheets", "auto")
        self.assertEqual(self.run_cli("config", "show")["config"]["actions"]["fill_sheets"], "auto")

        since = self.run_cli("state", "since", "--space", "Programming")
        self.assertEqual(since["source"], "lookback")
        self.run_cli("state", "mark", "--space", "Programming", "--time", "2026-11-22T10:00:00Z")
        self.assertEqual(self.run_cli("state", "since", "--space", "Programming")["since"], "2026-11-22T10:00:00Z")

        messages = self.home / "messages.json"
        messages.write_text(json.dumps([{"text": "Sign up https://docs.google.com/spreadsheets/d/S1/edit#gid=0", "space": "Programming"}]))
        found = self.run_cli("links", "--messages", str(messages))
        self.assertEqual(found["links"][0]["kind"], "gsheet")

        scan = self.run_cli("sheet-scan", "--file", str(helpers.EXAMPLES / "sample-signup-sheet.tsv"), "--tab", "Sheet1")
        self.assertEqual(scan["tab"], "Sheet1")
        self.assertIn("D5", [s["cell"] for s in scan["open_slots"]])
        self.assertTrue(scan["listed_in_name_column"])  # "Al"/"Alex" ... Alex R. is on D8

        digest = self.home / "digest.json"
        digest.write_text(json.dumps(DIGEST))
        written = self.run_cli("render", "--input", str(digest), "--formats", "md")
        self.assertTrue(Path(written["written"][0]).read_text().startswith("# Chat Catch-up"))
        self.assertTrue(written["written"][0].startswith(str(self.home / "out")))

    def test_errors_are_one_plain_sentence(self):
        message = self.run_cli("state", "since", "--space", "X", ok=False)
        self.assertIn("config init", message)
        self.assertNotIn("Traceback", message)

    def test_sheet_scan_works_without_settings_if_given_a_name(self):
        scan = self.run_cli("sheet-scan", "--name", "Alex R.", stdin=(helpers.EXAMPLES / "sample-signup-sheet.tsv").read_text())
        self.assertTrue(scan["listed_in_name_column"])


if __name__ == "__main__":
    unittest.main()
