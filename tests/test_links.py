import unittest

import helpers  # noqa: F401  (sets up sys.path)
from chatcatchup import links

SHEET = "https://docs.google.com/spreadsheets/d/1AbC_dEf-123/edit#gid=456"


class ExtractTests(unittest.TestCase):
    def test_strips_sentence_punctuation(self):
        text = f"Sign up here: {SHEET}. Also see https://example.com/page, thanks!"
        self.assertEqual(links.extract_urls(text), [SHEET, "https://example.com/page"])

    def test_keeps_balanced_parentheses_but_drops_a_closing_one(self):
        self.assertEqual(links.extract_urls("(see https://example.com/a)"), ["https://example.com/a"])
        self.assertEqual(links.extract_urls("https://en.wikipedia.org/wiki/Foo_(bar)"), ["https://en.wikipedia.org/wiki/Foo_(bar)"])

    def test_handles_missing_text(self):
        self.assertEqual(links.extract_urls(""), [])
        self.assertEqual(links.extract_urls(None), [])

    def test_unwraps_google_redirects(self):
        wrapped = "https://www.google.com/url?q=https://docs.google.com/document/d/DOC1/edit&sa=D&source=chat"
        self.assertEqual(links.unwrap(wrapped), "https://docs.google.com/document/d/DOC1/edit")
        nested = "https://www.google.com/url?url=" + "https%3A%2F%2Fexample.com%2Fx"
        self.assertEqual(links.unwrap(nested), "https://example.com/x")
        self.assertEqual(links.unwrap("https://example.com/"), "https://example.com/")


class ClassifyTests(unittest.TestCase):
    def kind(self, url):
        return links.classify(url)["kind"]

    def test_google_files(self):
        sheet = links.classify(SHEET)
        self.assertEqual((sheet["kind"], sheet["id"], sheet["gid"], sheet["readable"]), ("gsheet", "1AbC_dEf-123", "456", True))
        self.assertEqual(self.kind("https://docs.google.com/spreadsheets/u/1/d/XYZ/edit?gid=7"), "gsheet")
        self.assertEqual(links.classify("https://docs.google.com/spreadsheets/d/XYZ/edit?gid=7")["gid"], "7")
        self.assertEqual(self.kind("https://docs.google.com/document/d/DOC1/edit?usp=sharing"), "gdoc")
        self.assertEqual(self.kind("https://docs.google.com/presentation/d/SLIDES/edit"), "gslides")
        self.assertEqual(self.kind("https://docs.google.com/forms/d/e/1FAIpQ/viewform"), "gform")
        self.assertEqual(self.kind("https://forms.gle/abc123"), "gform")

    def test_published_sheet_is_flagged(self):
        self.assertTrue(links.classify("https://docs.google.com/spreadsheets/d/e/2PACX-abc/pubhtml")["published"])

    def test_drive_calendar_meet_chat_sites(self):
        self.assertEqual(self.kind("https://drive.google.com/file/d/FILE1/view"), "gdrive_file")
        self.assertEqual(self.kind("https://drive.google.com/open?id=FILE2"), "gdrive_file")
        self.assertEqual(self.kind("https://drive.google.com/drive/folders/FOLD1"), "gdrive_folder")
        self.assertEqual(self.kind("https://drive.google.com/drive/u/0/folders/FOLD1"), "gdrive_folder")
        self.assertEqual(self.kind("https://calendar.google.com/calendar/u/0/r"), "gcalendar")
        self.assertEqual(self.kind("https://meet.google.com/abc-defg-hij"), "gmeet")
        self.assertEqual(self.kind("https://chat.google.com/room/AAAA"), "gchat")
        self.assertEqual(self.kind("https://mail.google.com/chat/u/0/#chat/space/AAAA"), "gchat")
        self.assertEqual(self.kind("https://sites.google.com/view/robotics"), "gsite")

    def test_everything_else_is_external_and_not_opened(self):
        info = links.classify("https://www.thebluealliance.com/event/2026casj")
        self.assertEqual((info["kind"], info["domain"], info["readable"]), ("external", "thebluealliance.com", False))

    def test_lookalike_hosts_are_not_google(self):
        self.assertEqual(self.kind("https://docs.google.com.evil.example/spreadsheets/d/X/edit"), "external")
        self.assertEqual(self.kind("https://evil.example/docs.google.com/spreadsheets/d/X/edit"), "external")


class CollectTests(unittest.TestCase):
    def test_dedupes_across_messages_and_keeps_every_source(self):
        messages = [
            {"text": f"Sign up: {SHEET}", "space": "Programming", "sender": "Sam", "time": "2026-11-22T10:00:00Z"},
            {"text": f"reminder {SHEET}", "space": "General", "sender": "Jo"},
        ]
        found = links.collect(messages)
        self.assertEqual(len(found), 1)
        self.assertEqual([s["space"] for s in found[0]["sources"]], ["Programming", "General"])

    def test_different_tabs_of_one_sheet_stay_separate(self):
        found = links.collect([{"text": "https://docs.google.com/spreadsheets/d/S1/edit#gid=1 https://docs.google.com/spreadsheets/d/S1/edit#gid=2"}])
        self.assertEqual(len(found), 2)

    def test_sheets_come_first_and_external_last(self):
        found = links.collect([{"text": "https://example.com/a https://meet.google.com/aaa-bbbb-ccc https://docs.google.com/document/d/D/edit " + SHEET}])
        self.assertEqual([f["kind"] for f in found], ["gsheet", "gdoc", "gmeet", "external"])

    def test_uses_real_hrefs_when_message_text_has_no_urls(self):
        found = links.collect([{"text": "Sign up here", "links": [SHEET], "space": "Build"}])
        self.assertEqual(found[0]["kind"], "gsheet")

    def test_ignores_junk_entries(self):
        self.assertEqual(links.collect([None, "text", {"text": None}]), [])


if __name__ == "__main__":
    unittest.main()
