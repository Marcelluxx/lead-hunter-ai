import os
import tempfile
import unittest
from dataclasses import replace

from openpyxl import load_workbook

from src.application.export_policy import ExportPolicyError
from src.domain.provenance import DataSource, FieldProvenance, VerifiedLead
from src.domain.contacts import ContactExtractionMethod, ContactPoint
from src.exporter import DataExporter
from src.security.spreadsheet import sanitize_spreadsheet_value
from datetime import datetime, timezone


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
        provenance = FieldProvenance(
            source=DataSource.OFFICIAL_WEBSITE,
            source_url="https://example.test",
            collected_at=datetime.now(timezone.utc),
            evidence_sha256="a" * 64,
        )
        lead = VerifiedLead(
            business_name="=HYPERLINK(\"https://example.test\")",
            category="+SUM(A1:A2)",
            website="https://example.test",
            contacts=(
                replace(ContactPoint.from_email(
                    "info@example.test",
                    source_url="https://example.test",
                    collected_at=provenance.collected_at,
                    extraction_method=ContactExtractionMethod.MAILTO,
                    evidence_sha256="a" * 64,
                ), display_value="@malicious"),
            ),
            provenance={
                "business_name": provenance,
                "category": FieldProvenance(
                    source=DataSource.USER_INPUT,
                    source_url=None,
                    collected_at=datetime.now(timezone.utc),
                ),
                "website": provenance,
                "extracted_email": provenance,
            },
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "safe.xlsx")
            DataExporter.export_to_excel(
                [lead],
                mode="with_website",
                filename=path,
                suppression_checker=lambda _: False,
            )
            workbook = load_workbook(path, data_only=False)
            sheet = workbook["Leads"]

            for cell in sheet[2]:
                self.assertNotEqual(cell.data_type, "f")

            self.assertTrue(sheet["A2"].value.startswith("'="))
            self.assertTrue(sheet["B2"].value.startswith("'+"))
            self.assertTrue(sheet["D2"].value.startswith("'@"))

    def test_no_website_provider_results_fail_closed(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "forbidden.xlsx")
            with self.assertRaises(ExportPolicyError):
                DataExporter.export_to_excel(
                    [{"displayName": {"text": "Provider content"}}],
                    mode="no_website",
                    filename=path,
                )
            self.assertFalse(os.path.exists(path))


if __name__ == "__main__":
    unittest.main()
