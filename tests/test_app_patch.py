import unittest

from codex_reset_credits.app_patch import _reset_row_needles, patch_menu_chunk
from codex_reset_credits.models import ResetCredit


class AppPatchTests(unittest.TestCase):
    def test_patch_menu_chunk_inserts_expression(self) -> None:
        patched = patch_menu_chunk("[" + _needle() + "]", [_credit()])

        self.assertIn("reset-credit-expiry", patched)
        self.assertIn("(()=>{const __codexResetCredits=", patched)
        self.assertIn("Full reset", patched)

    def test_patch_menu_chunk_replaces_existing_patch(self) -> None:
        first = patch_menu_chunk("[" + _needle() + "]", [_credit("First")])
        second = patch_menu_chunk(first, [_credit("Second")])

        self.assertIn("Second", second)
        self.assertNotIn("First", second)
        self.assertEqual(second.count("reset-credit-expiry"), 2)


def _needle() -> str:
    return _reset_row_needles()[0]


def _credit(title: str = "Full reset") -> ResetCredit:
    return ResetCredit(
        id="credit_1",
        title=title,
        status="available",
        expires_at="2026-07-18T00:31:22.905095Z",
        granted_at=None,
        reset_type="full",
    )


if __name__ == "__main__":
    unittest.main()
