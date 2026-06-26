import unittest

from codex_reset_credits.formatting import format_duration, parse_iso_datetime
from codex_reset_credits.models import ResetCredit


class FormattingTests(unittest.TestCase):
    def test_format_duration_compacts_seconds(self) -> None:
        self.assertEqual(format_duration(65), "1m 5s")
        self.assertEqual(format_duration(90061), "1d 1h 1m 1s")

    def test_parse_iso_datetime_accepts_z_suffix(self) -> None:
        parsed = parse_iso_datetime("2026-07-18T00:31:22.905095Z")
        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertEqual(parsed.utcoffset().total_seconds(), 0)


class ResetCreditModelTests(unittest.TestCase):
    def test_category_detects_full_and_partial_titles(self) -> None:
        full = ResetCredit(None, "Full reset (Weekly + 5 hr)", "available", None, None, "codex_rate_limits")
        partial = ResetCredit(None, "Partial reset (5 hr)", "available", None, None, "codex_rate_limits_partial")

        self.assertEqual(full.category, "full")
        self.assertEqual(partial.category, "partial")


if __name__ == "__main__":
    unittest.main()
