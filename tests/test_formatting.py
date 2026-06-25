import unittest

from codex_reset_credits.formatting import format_duration, parse_iso_datetime


class FormattingTests(unittest.TestCase):
    def test_format_duration_compacts_seconds(self) -> None:
        self.assertEqual(format_duration(65), "1m 5s")
        self.assertEqual(format_duration(90061), "1d 1h 1m 1s")

    def test_parse_iso_datetime_accepts_z_suffix(self) -> None:
        parsed = parse_iso_datetime("2026-07-18T00:31:22.905095Z")
        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertEqual(parsed.utcoffset().total_seconds(), 0)


if __name__ == "__main__":
    unittest.main()
