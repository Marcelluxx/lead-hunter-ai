import unittest

from src.security.presentation import (
    build_keyword_card_html,
    build_phase_card_html,
    escape_dynamic_html,
    normalize_console_text,
    normalize_log_message,
)


class PresentationSecurityTests(unittest.TestCase):
    def test_escapes_dynamic_values_in_keyword_card(self):
        payload = '<img src=x onerror="alert(1)">'

        rendered = build_keyword_card_html(payload, "<svg/onload=1>", "done", payload)

        self.assertNotIn(payload, rendered)
        self.assertNotIn("<svg/onload=1>", rendered)
        self.assertIn("&lt;img", rendered)
        self.assertIn("&lt;svg", rendered)

    def test_escapes_every_dynamic_phase_value(self):
        rendered = build_phase_card_html("<svg>", "</span><script>x</script>", '1" onmouseover="x')

        self.assertNotIn("<script>", rendered)
        self.assertNotIn("<svg>", rendered)
        self.assertIn("&lt;script&gt;", rendered)
        self.assertIn("&quot;", rendered)

    def test_normalizes_control_characters_and_bounds_log_messages(self):
        self.assertEqual(normalize_log_message("ok\x00\x1fbad"), "okbad")
        self.assertEqual(normalize_log_message("abcdef", max_length=3), "abc")

    def test_escape_dynamic_html_escapes_quotes(self):
        self.assertEqual(escape_dynamic_html('"quoted"'), "&quot;quoted&quot;")

    def test_console_text_degrades_unencodable_characters(self):
        self.assertEqual(normalize_console_text("phase 🔍", encoding="cp1252"), "phase ?")


if __name__ == "__main__":
    unittest.main()
