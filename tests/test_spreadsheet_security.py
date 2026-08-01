import os
import tempfile
import unittest

from openpyxl import load_workbook

from src.exporter import DataExporter
from src.security.spreadsheet import sanitize_spreadsheet_value


class SpreadsheetSecurityTests(unittest.TestCase):
    def test_neutralizes_formula_prefixes_and_leading_whitespace(self):
        payloads = [
            "=1+1",
            "+SUM(A1:A2)",
            "-2+3",
            "@SUM(A1:A2)",
            "  =HYPERLINK(\"https://example.test\")",
            "\t=cmd|' /C calc'!A0",
            "\r\n@malicious",
        ]

        for payload in payloads:
            with self.subTest(payload=payload):
                self.assertEqual(sanitize_spreadsheet_value(payload), f"'{payload}")

    def test_preserves_numbers_but_serializes_other_values_as_text(self):
        self.assertEqual(sanitize_spreadsheet_value(-42), -42)
        self.assertEqual(sanitize_spreadsheet_value(4.5), 4.5)
        self.assertEqual(sanitize_spreadsheet_value(None), "")
        self.assertEqual(sanitize_spreadsheet_value(True), "True")

    def test_exported_untrusted_cells_are_strings_not_formulas(self):
        lead = {
            "displayName": {"text": "=HYPERLINK(\"https://example.test\")"},
            "types": [],
            "formattedAddress": "+SUM(A1:A2)",
            "nationalPhoneNumber": "+39 0123",
            "rating": 4.5,
            "userRatingCount": 12,
            "competitor": "@malicious",
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "safe.xlsx")
            DataExporter.export_to_excel([lead], mode="no_website", filename=path)
            workbook = load_workbook(path, data_only=False)
            sheet = workbook["Leads"]

            for cell in sheet[2]:
                self.assertNotEqual(cell.data_type, "f")

            self.assertTrue(sheet["A2"].value.startswith("'="))
            self.assertTrue(sheet["E2"].value.startswith("'+"))
            self.assertEqual(sheet["F2"].value, 4.5)
            self.assertEqual(sheet["G2"].value, 12)
            self.assertTrue(sheet["H2"].value.startswith("'@"))


if __name__ == "__main__":
    unittest.main()
