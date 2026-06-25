from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path

from .asar import get_file, read_asar, replace_file
from .models import ResetCredit, duplicate_title_counts


DEFAULT_MACOS_ASAR = Path("/Applications/Codex.app/Contents/Resources/app.asar")
MENU_CHUNK_PATH = "webview/assets/app-initial~app-main~automations-page-jUgL0rhh.js"
PATCH_MARKER = "reset-credit-expiry"


@dataclass(frozen=True)
class PatchResult:
    asar_path: Path
    backup_path: Path | None
    credit_count: int
    changed: bool
    dry_run: bool


def patch_usage_menu(
    asar_path: Path,
    credits: list[ResetCredit],
    backup_path: Path | None = None,
    dry_run: bool = False,
) -> PatchResult:
    archive = read_asar(asar_path)
    chunk = get_file(archive, MENU_CHUNK_PATH).decode("utf-8")
    patched = patch_menu_chunk(chunk, credits)
    changed = patched != chunk

    if not changed or dry_run:
        return PatchResult(asar_path=asar_path, backup_path=None, credit_count=len(credits), changed=changed, dry_run=dry_run)

    backup = backup_path or asar_path.with_suffix(asar_path.suffix + ".bak")
    if not backup.exists():
        shutil.copy2(asar_path, backup)

    asar_path.write_bytes(replace_file(archive, MENU_CHUNK_PATH, patched.encode("utf-8")))
    return PatchResult(asar_path=asar_path, backup_path=backup, credit_count=len(credits), changed=True, dry_run=False)


def patch_menu_chunk(chunk: str, credits: list[ResetCredit]) -> str:
    if PATCH_MARKER in chunk:
        start = chunk.find("(()=>{const __codexResetCredits=")
        if start == -1:
            raise ValueError("found previous patch marker but could not locate patch block")
        end = chunk.find("})()", start)
        if end == -1:
            raise ValueError("found previous patch marker but patch block is malformed")
        replacement = _reset_credit_js(credits)
        return chunk[:start] + replacement + chunk[end + 4 :]

    for needle in _reset_row_needles():
        if needle in chunk:
            return chunk.replace(needle, needle + "," + _reset_credit_js(credits), 1)
    raise ValueError("could not find Codex usage reset menu item in app chunk")


def _reset_credit_js(credits: list[ResetCredit]) -> str:
    duplicate_counts = duplicate_title_counts(credits)
    rows = [
        {
            "label": credit.menu_label(index, duplicate_counts[credit.title]),
            "title": credit.title,
            "status": credit.status,
            "expires_at": credit.expires_at,
            "reset_type": credit.reset_type,
            "category": credit.category,
        }
        for index, credit in enumerate(credits, start=1)
        if credit.expires_at
    ]
    rows_json = json.dumps(rows, separators=(",", ":"))
    return (
        f'(()=>{{const __codexResetCredits={rows_json};'
        '/* reset-credit-expiry */'
        'return __codexResetCredits.length?__codexResetCredits.map((e,t)=>(0,CV.jsx)(Xb.Item,{className:"text-base opacity-70",href:"#",onClick:e=>e.preventDefault(),children:(0,CV.jsxs)("span",{className:"flex items-center justify-between gap-3",children:[(0,CV.jsx)("span",{children:e.label||e.title||`Reset ${t+1}`}),(0,CV.jsx)("span",{className:"text-iconDefault",children:new Intl.DateTimeFormat(void 0,{month:"short",day:"numeric",hour:"numeric",minute:"2-digit"}).format(new Date(e.expires_at))})]})},`reset-credit-expiry-${t}`)):null})()'
    )


def _reset_row_needles() -> tuple[str, ...]:
    current = 'h>0?(0,CV.jsx)(Xb.Item,{RightIcon:Ib,className:$(x&&`pl-[calc(var(--padding-row-x)+1.25rem)] pr-[var(--padding-row-x)]`),onClick:c,children:(0,CV.jsx)(Z,{id:`composer.mode.rateLimit.resetsAvailable`,defaultMessage:`{availableRateLimitResetCount, plural, one {# reset available} other {# resets available}}`,description:`Menu item for opening available rate limit resets`,values:{availableRateLimitResetCount:h}})}):null'
    previous = 'h>0?(0,CV.jsx)(Xb.Item,{className:"text-base",href:"#",onClick:e=>{e.preventDefault(),c&&c()},children:(0,CV.jsxs)("span",{className:"text-iconDefault flex items-center justify-between gap-3",children:[(0,CV.jsxs)("span",{children:[h," reset",h===1?"":"s"," available"]}),(0,CV.jsx)(tH,{className:"icon-sm shrink-0"})]})}):null'
    return (current, previous)
