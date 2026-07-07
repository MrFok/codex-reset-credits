import unittest
from pathlib import Path

from codex_reset_credits.asar import AsarFile, iter_file_paths
from codex_reset_credits.app_patch import (
    ResetCreditApiClient,
    _reset_row_needles,
    find_menu_chunk_path,
    find_reset_credit_api_client,
    patch_menu_chunk,
)


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

    def test_find_menu_chunk_path_supports_short_reset_message_marker(self) -> None:
        archive = _archive_with_files(
            {
                "webview/assets/fr-FR.js": b"resetsAvailable availableRateLimitResetCount",
                "webview/assets/app-initial~app-main~thread.js": (
                    b"resetsAvailable availableRateLimitResetCount onRateLimitResetClick C>0?"
                ),
            }
        )

        self.assertEqual(find_menu_chunk_path(archive), "webview/assets/app-initial~app-main~thread.js")

    def test_find_menu_chunk_path_uses_fallback_when_old_marker_lacks_old_shape(self) -> None:
        archive = _archive_with_files(
            {
                "webview/assets/app-initial~app-main~thread.js": (
                    b"composer.mode.rateLimit.resetsAvailable availableRateLimitResetCount onRateLimitResetClick C>0?"
                ),
            }
        )

        self.assertEqual(find_menu_chunk_path(archive), "webview/assets/app-initial~app-main~thread.js")

    def test_iter_file_paths_skips_metadata_without_payload(self) -> None:
        archive = _archive_with_files({"webview/assets/app.js": b"console.log(1)"})
        archive.header["files"]["webview"]["files"]["assets"]["files"]["virtual.js"] = {"size": 10}

        self.assertEqual(list(iter_file_paths(archive)), ["webview/assets/app.js"])

    def test_find_reset_credit_api_client_uses_exported_codex_client(self) -> None:
        archive = _archive_with_files(
            {
                "webview/assets/menu.js": b"composer.mode.rateLimit.resetsAvailable onRateLimitResetClick h>0?",
                "webview/assets/api-hash.js": (
                    b"function RSt(){return HM.safeGet(`/wham/rate-limit-reset-credits`)}"
                    b"export{HM as PA,LSt as Sc};"
                ),
            }
        )

        self.assertEqual(
            find_reset_credit_api_client(archive, "webview/assets/menu.js"),
            ResetCreditApiClient("./api-hash.js", "PA"),
        )

    def test_patch_menu_chunk_inserts_expression(self) -> None:
        patched = patch_menu_chunk("[" + _needle() + "]")

        self.assertIn("reset-credit-expiry", patched)
        self.assertIn('import(new URL(__codexResetCreditModule,import.meta.url).href)', patched)
        self.assertIn('.safeGet("/wham/rate-limit-reset-credits")', patched)
        self.assertIn("https://chatgpt.com/backend-api/wham/rate-limit-reset-credits", patched)
        self.assertIn('credentials:"include"', patched)
        self.assertIn("__codexResetCreditsLastError", patched)
        self.assertIn('style:{display:"none"}', patched)
        self.assertIn("__codexResetCreditCacheKey", patched)
        self.assertIn("__codexResetCreditScheduleExpiry", patched)
        self.assertIn("__codexResetCreditBindNativeClick", patched)
        self.assertIn("__codexResetCreditInvalidate", patched)
        self.assertNotIn('window.addEventListener("focus"', patched)
        self.assertNotIn('document.addEventListener("visibilitychange"', patched)
        self.assertNotIn("[0,1e3,3e3,1e4]", patched)
        self.assertIn("rows.forEach((row,index)=>{let credit=credits[index];", patched)
        self.assertIn("__codexResetCreditRender(response)", patched)
        self.assertNotIn("response.forEach", patched)
        self.assertNotIn("2026-07-18T00:31:22.905095Z", patched)

    def test_patch_menu_chunk_supports_updated_bundle_symbols(self) -> None:
        patched = patch_menu_chunk("[" + _needle(2) + "]")

        self.assertIn("Array.from({length:y}", patched)
        self.assertIn("(0,X.jsx)(m.Item", patched)
        self.assertIn("className:n(D&&", patched)

    def test_patch_menu_chunk_supports_current_bundle_symbols(self) -> None:
        patched = patch_menu_chunk("[" + _needle(3) + "]")

        self.assertIn("Array.from({length:h}", patched)
        self.assertIn("(0,mG.jsx)(qd.Item", patched)
        self.assertIn("className:H(x&&", patched)

    def test_patch_menu_chunk_supports_remote_conversation_bundle_symbols(self) -> None:
        patched = patch_menu_chunk("[" + _needle(4) + "]")

        self.assertIn("Array.from({length:h}", patched)
        self.assertIn("(0,Q.jsx)(k.Item", patched)
        self.assertIn("className:q(x&&", patched)

    def test_patch_menu_chunk_supports_thread_shell_bundle_symbols(self) -> None:
        patched = patch_menu_chunk("[" + _needle(5) + "]")

        self.assertIn("Array.from({length:C}", patched)
        self.assertIn("(0,X.jsx)(b.Item", patched)
        self.assertIn("className:h(A&&", patched)

    def test_patch_menu_chunk_supports_keyboard_shortcuts_bundle_symbols(self) -> None:
        patched = patch_menu_chunk("[" + _needle(6) + "]")

        self.assertIn("Array.from({length:h}", patched)
        self.assertIn("(0,K.jsx)(F.Item", patched)
        self.assertIn("className:L(x&&", patched)

    def test_patch_menu_chunk_hides_rows_when_refresh_fails(self) -> None:
        patched = patch_menu_chunk("[" + _needle() + "]")

        self.assertIn("catch(error=>{window.__codexResetCreditsLastError=String(error?.message||error)", patched)
        self.assertIn("cachedResponse?__codexResetCreditRender(cachedResponse):rows.forEach(__codexResetCreditHide)", patched)

    def test_patch_menu_chunk_replaces_existing_patch(self) -> None:
        first = patch_menu_chunk("[" + _needle() + "]")
        second = patch_menu_chunk(first)

        self.assertEqual(second.count("(()=>{const __codexResetCreditModule="), 1)

    def test_patch_menu_chunk_replaces_static_snapshot_patch(self) -> None:
        static_patch = (
            '(()=>{const __codexResetCredits=[{"title":"Full reset",'
            '"expires_at":"2026-07-18T00:31:22.905095Z"}];'
            "/* reset-credit-expiry */return __codexResetCredits})()"
        )

        patched = patch_menu_chunk("[" + _needle() + "," + static_patch + "]")

        self.assertIn('.safeGet("/wham/rate-limit-reset-credits")', patched)
        self.assertNotIn("__codexResetCredits=[", patched)
        self.assertNotIn("2026-07-18T00:31:22.905095Z", patched)

    def test_patch_menu_chunk_replaces_legacy_manual_snapshot_patch(self) -> None:
        legacy_patch = (
            '["2026-07-12T01:30:38.263724Z"].slice(0,h).map((e,t)=>'
            '(0,CV.jsx)(Xb.Item,{children:(0,CV.jsx)("span",{children:e})},'
            "`reset-credit-expiry-${t}`))"
        )

        patched = patch_menu_chunk("[" + _needle() + "," + legacy_patch + "]}):null")

        self.assertIn('.safeGet("/wham/rate-limit-reset-credits")', patched)
        self.assertNotIn("2026-07-12T01:30:38.263724Z", patched)

    def test_patch_menu_chunk_keeps_different_credit_titles_dynamic(self) -> None:
        patched = patch_menu_chunk("[" + _needle() + "]")

        self.assertIn('credit.title||"Reset credit"', patched)
        self.assertIn('titleCounts[title]>1?`${label} ${index+1}`:label', patched)


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
