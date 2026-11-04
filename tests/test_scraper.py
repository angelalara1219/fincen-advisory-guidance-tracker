import tempfile
import unittest
from pathlib import Path

from fincen_tracker import scraper as s

FIX = Path(__file__).parent / "fixtures"


class ScraperTests(unittest.TestCase):
    def setUp(self):
        self.items = s.parse_advisories((FIX / "advisories.html").read_text(), "2026-11-04")
        self.terms = s.parse_key_terms((FIX / "key_terms.html").read_text())

    def test_numbers_normalize(self):
        self.assertEqual(s.normalize_number("FinCEN Advisory FIN-2026-A002"), "FIN-2026-A002")
        self.assertEqual(s.normalize_number("FinCEN-2023-Alert006"), "FIN-2023-Alert006")
        self.assertEqual(s.normalize_number("FIN-2026-ntc2"), "FIN-2026-NTC2")
        self.assertEqual(s.normalize_number("PDF Only"), "")

    def test_dates(self):
        self.assertEqual(s.parse_date("08/4/2025"), "2025-08-04")
        self.assertEqual(s.parse_date("12/2020"), "2020-12-01")
        self.assertEqual(s.parse_date("junk"), "")

    def test_parse_skips_old_and_spanish(self):
        numbers = [i.fincen_number for i in self.items]
        self.assertIn("FIN-2026-Alert010", numbers)
        self.assertNotIn("FIN-2023-Alert005", numbers)
        self.assertEqual(len([i for i in self.items if "Spanish" in i.title]), 0)
        self.assertEqual(len(self.items), 5)

    def test_types_and_titles(self):
        by_num = {i.fincen_number: i for i in self.items}
        self.assertEqual(by_num["FIN-2026-A002"].type, "Advisory")
        self.assertEqual(by_num["FIN-2025-NTC1"].type, "Notice")
        bulletin = [i for i in self.items if not i.fincen_number][0]
        self.assertEqual(bulletin.type, "Bulletin / Fact Sheet")
        self.assertEqual(bulletin.title, "FinCEN Whistleblower Bulletin: Iran")
        self.assertTrue(bulletin.link.startswith("https://www.fincen.gov/system/files/"))

    def test_key_terms(self):
        self.assertEqual(self.terms["FIN-2026-Alert010"], "FIN2026NEWTHING")
        self.assertEqual(self.terms["FIN-2023-Alert006"], "FIN-2023-TFHAMAS")
        self.assertNotIn("FIN-2025-A002", self.terms)  # related, not the source

    def test_merge_adds_new_and_matches_by_link(self):
        existing = [s.Item("2026-10-30", "FIN-2026-Alert009", "Alert", "Foreign agents", "",
                           "https://www.fincen.gov/x.pdf", "2026-11-01")]
        merged, added = s.merge(existing, self.items, self.terms)
        added_nums = {i.fincen_number for i in added}
        self.assertNotIn("FIN-2026-Alert009", added_nums)
        self.assertIn("FIN-2026-Alert010", added_nums)
        kiosk = [i for i in merged if i.fincen_number == "FIN-2025-NTC1"][0]
        self.assertEqual(kiosk.sar_key_term, "FIN-2025-CVCKIOSK")
        self.assertEqual(existing[0].first_seen, "2026-11-01")

    def test_csv_and_readme_roundtrip(self):
        merged, _ = s.merge([], self.items, self.terms)
        with tempfile.TemporaryDirectory() as d:
            csv_path, readme = Path(d) / "t.csv", Path(d) / "README.md"
            s.save_csv(merged, csv_path)
            self.assertEqual(len(s.load_csv(csv_path)), len(merged))
            readme.write_text("top\n<!-- LATEST:START -->\nold\n<!-- LATEST:END -->\nbottom\n")
            s.update_readme(merged, readme)
            text = readme.read_text()
            self.assertIn("FIN-2026-Alert010", text)
            self.assertNotIn("\nold\n", text)
            self.assertTrue(text.endswith("bottom\n"))


if __name__ == "__main__":
    unittest.main()
