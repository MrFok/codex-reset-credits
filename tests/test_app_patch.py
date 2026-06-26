import unittest
from pathlib import Path

from codex_reset_credits.asar import AsarFile, iter_file_paths
from codex_reset_credits.app_patch import _reset_row_needles, find_menu_chunk_path, patch_menu_chunk


class AppPatchTests(unittest.TestCase):
    def test_find_menu_chunk_path_uses_current_hashed_asset(self) -> None:
        archive = _archive_with_files(
            {
                "webview/assets/app-initial~app-main~automations-page-newhash.js": (
                    b"abc composer.mode.rateLimit.resetsAvailable onRateLimitResetClick h>0? def"
                ),
                "webview/assets/other.js": b"abc",
            }
        )

        self.assertEqual(
            find_menu_chunk_path(archive),
            "webview/assets/app-initial~app-main~automations-page-newhash.js",
        )

    def test_find_menu_chunk_path_ignores_translation_assets(self) -> None:
        archive = _archive_with_files(
            {
                "webview/assets/fr-FR.js": b"composer.mode.rateLimit.resetsAvailable",
                "webview/assets/app-initial~app-main~thread.js": (
                    b"composer.mode.rateLimit.resetsAvailable onRateLimitResetClick h>0?"
                ),
            }
        )

        self.assertEqual(find_menu_chunk_path(archive), "webview/assets/app-initial~app-main~thread.js")

    def test_iter_file_paths_skips_metadata_without_payload(self) -> None:
        archive = _archive_with_files({"webview/assets/app.js": b"console.log(1)"})
        archive.header["files"]["webview"]["files"]["assets"]["files"]["virtual.js"] = {"size": 10}

        self.assertEqual(list(iter_file_paths(archive)), ["webview/assets/app.js"])

    def test_patch_menu_chunk_inserts_expression(self) -> None:
        patched = patch_menu_chunk("[" + _needle() + "]")

        self.assertIn("reset-credit-expiry", patched)
        self.assertIn("/backend-api/wham/rate-limit-reset-credits", patched)
        self.assertIn('credentials:"include"', patched)
        self.assertIn('style:{display:"none"}', patched)
        self.assertIn('window.addEventListener("focus"', patched)
        self.assertIn('document.addEventListener("visibilitychange"', patched)
        self.assertIn("[0,1e3,3e3,1e4]", patched)
        self.assertNotIn("2026-07-18T00:31:22.905095Z", patched)

    def test_patch_menu_chunk_supports_updated_bundle_symbols(self) -> None:
        patched = patch_menu_chunk("[" + _needle(2) + "]")

        self.assertIn("Array.from({length:y}", patched)
        self.assertIn("(0,X.jsx)(m.Item", patched)
        self.assertIn("className:n(D&&", patched)

    def test_patch_menu_chunk_hides_rows_when_refresh_fails(self) -> None:
        patched = patch_menu_chunk("[" + _needle() + "]")

        self.assertIn("catch(()=>e.forEach(__codexResetCreditHide))", patched)

    def test_patch_menu_chunk_replaces_existing_patch(self) -> None:
        first = patch_menu_chunk("[" + _needle() + "]")
        second = patch_menu_chunk(first)

        self.assertEqual(second.count("(()=>{const __codexResetCreditEndpoint="), 1)

    def test_patch_menu_chunk_replaces_static_snapshot_patch(self) -> None:
        static_patch = (
            '(()=>{const __codexResetCredits=[{"title":"Full reset",'
            '"expires_at":"2026-07-18T00:31:22.905095Z"}];'
            "/* reset-credit-expiry */return __codexResetCredits})()"
        )

        patched = patch_menu_chunk("[" + _needle() + "," + static_patch + "]")

        self.assertIn("/backend-api/wham/rate-limit-reset-credits", patched)
        self.assertNotIn("__codexResetCredits=[", patched)
        self.assertNotIn("2026-07-18T00:31:22.905095Z", patched)

    def test_patch_menu_chunk_replaces_legacy_manual_snapshot_patch(self) -> None:
        legacy_patch = (
            '["2026-07-12T01:30:38.263724Z"].slice(0,h).map((e,t)=>'
            '(0,CV.jsx)(Xb.Item,{children:(0,CV.jsx)("span",{children:e})},'
            "`reset-credit-expiry-${t}`))"
        )

        patched = patch_menu_chunk("[" + _needle() + "," + legacy_patch + "]}):null")

        self.assertIn("/backend-api/wham/rate-limit-reset-credits", patched)
        self.assertNotIn("2026-07-12T01:30:38.263724Z", patched)

    def test_patch_menu_chunk_keeps_different_credit_titles_dynamic(self) -> None:
        patched = patch_menu_chunk("[" + _needle() + "]")

        self.assertIn('e.title||"Reset credit"', patched)
        self.assertIn('n[r]>1?`${i} ${t+1}`:i', patched)


def _needle(index: int = 0) -> str:
    return _reset_row_needles()[index].text


def _archive_with_files(files: dict[str, bytes]) -> AsarFile:
    header: dict[str, object] = {"files": {}}
    raw = b""
    for path, content in files.items():
        node = header
        parts = path.split("/")
        for part in parts[:-1]:
            children = node.setdefault("files", {})
            node = children.setdefault(part, {"files": {}})
        children = node.setdefault("files", {})
        children[parts[-1]] = {"offset": str(len(raw)), "size": len(content)}
        raw += content
    return AsarFile(Path("test.asar"), 0, 0, 0, header, 0, raw)


if __name__ == "__main__":
    unittest.main()
