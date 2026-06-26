from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from .asar import AsarFile, get_file, iter_file_paths, read_asar, replace_file


DEFAULT_MACOS_ASAR = Path("/Applications/Codex.app/Contents/Resources/app.asar")
MENU_CHUNK_PATH = "webview/assets/app-initial~app-main~automations-page-jUgL0rhh.js"
MENU_CHUNK_MARKER = "composer.mode.rateLimit.resetsAvailable"
MENU_CHUNK_COMPONENT_MARKERS = ("onRateLimitResetClick", "h>0?")
PATCH_MARKER = "reset-credit-expiry"
PATCH_STARTS = (
    "(()=>{const __codexResetCreditEndpoint=",
    "(()=>{const __codexResetCredits=",
)


@dataclass(frozen=True)
class PatchResult:
    asar_path: Path
    backup_path: Path | None
    changed: bool
    dry_run: bool


@dataclass(frozen=True)
class MenuNeedle:
    text: str
    credit_count: str
    compact: str
    jsx: str
    item: str
    classnames: str


def patch_usage_menu(
    asar_path: Path,
    backup_path: Path | None = None,
    dry_run: bool = False,
) -> PatchResult:
    archive = read_asar(asar_path)
    menu_chunk_path = find_menu_chunk_path(archive)
    chunk = get_file(archive, menu_chunk_path).decode("utf-8")
    patched = patch_menu_chunk(chunk)
    changed = patched != chunk

    if not changed or dry_run:
        return PatchResult(asar_path=asar_path, backup_path=None, changed=changed, dry_run=dry_run)

    backup = backup_path or asar_path.with_suffix(asar_path.suffix + ".bak")
    if not backup.exists():
        shutil.copy2(asar_path, backup)

    asar_path.write_bytes(replace_file(archive, menu_chunk_path, patched.encode("utf-8")))
    return PatchResult(asar_path=asar_path, backup_path=backup, changed=True, dry_run=False)


def find_menu_chunk_path(archive: AsarFile) -> str:
    try:
        chunk = get_file(archive, MENU_CHUNK_PATH)
    except KeyError:
        chunk = b""
    if _is_menu_chunk(chunk):
        return MENU_CHUNK_PATH

    matches = []
    for path in iter_file_paths(archive):
        if not path.startswith("webview/assets/") or not path.endswith(".js"):
            continue
        content = get_file(archive, path)
        if _is_menu_chunk(content):
            matches.append(path)

    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise KeyError(f"could not find Codex usage menu chunk containing {MENU_CHUNK_MARKER!r}")
    raise ValueError(f"found multiple candidate Codex usage menu chunks: {', '.join(matches)}")


def _is_menu_chunk(content: bytes) -> bool:
    if PATCH_MARKER.encode("utf-8") in content:
        return True
    if MENU_CHUNK_MARKER.encode("utf-8") not in content:
        return False
    return all(marker.encode("utf-8") in content for marker in MENU_CHUNK_COMPONENT_MARKERS)


def patch_menu_chunk(chunk: str) -> str:
    if PATCH_MARKER in chunk:
        needle = _needle_for_chunk(chunk)
        if needle is None:
            raise ValueError("found previous patch marker but could not identify Codex usage reset menu item shape")
        span = _existing_patch_span(chunk)
        if span is None:
            raise ValueError("found previous patch marker but could not locate patch block")
        start, end = span
        replacement = _reset_credit_js(needle)
        return chunk[:start] + replacement + chunk[end:]

    for needle in _reset_row_needles():
        if needle.text in chunk:
            return chunk.replace(needle.text, needle.text + "," + _reset_credit_js(needle), 1)
    raise ValueError("could not find Codex usage reset menu item in app chunk")


def _existing_patch_span(chunk: str) -> tuple[int, int] | None:
    start = _existing_patch_start(chunk)
    if start != -1:
        end = chunk.find("})()", start)
        if end == -1:
            raise ValueError("found previous patch marker but patch block is malformed")
        return start, end + 4

    marker = chunk.find(PATCH_MARKER)
    start = chunk.rfind(",[", 0, marker)
    end = chunk.find("))]}", marker)
    if start == -1 or end == -1:
        return None
    return start + 1, end + 2


def _existing_patch_start(chunk: str) -> int:
    starts = [index for prefix in PATCH_STARTS if (index := chunk.find(prefix)) != -1]
    return min(starts) if starts else -1


def _needle_for_chunk(chunk: str) -> MenuNeedle | None:
    for needle in _reset_row_needles():
        if needle.text in chunk:
            return needle
    return None


def _reset_credit_js(needle: MenuNeedle) -> str:
    return (
        '(()=>{const __codexResetCreditEndpoint="/backend-api/wham/rate-limit-reset-credits",'
        '__codexResetCreditRowsKey="__codexResetCreditRows",'
        '__codexResetCreditTimerKey="__codexResetCreditTimer";'
        '/* reset-credit-expiry */'
        'function __codexResetCreditHide(e){e&&(e.style.display="none");let t=e?.closest?.("[data-codex-reset-credit-row]")||e?.parentElement;t&&(t.style.display="none")}'
        'function __codexResetCreditShow(e){e&&(e.style.display="");let t=e?.closest?.("[data-codex-reset-credit-row]")||e?.parentElement;t&&(t.style.display="")}'
        'function __codexResetCreditLabel(e,t,n){let r=e.title||"Reset credit",i=(r.split(" (",1)[0]||"Reset credit").trim();return n[r]>1?`${i} ${t+1}`:i}'
        'function __codexResetCreditRefresh(){let e=(window[__codexResetCreditRowsKey]||[]).filter(Boolean);'
        'if(!e.length)return;fetch(__codexResetCreditEndpoint,{credentials:"include"}).then(e=>e.ok?e.json():null).then(t=>{'
        'let n=Array.isArray(t?.credits)?t.credits.filter(e=>e&&e.expires_at):[],r={};'
        'n.forEach(e=>{let t=e.title||"Reset credit";r[t]=(r[t]||0)+1}),e.forEach((e,t)=>{let i=n[t];'
        'if(!i){__codexResetCreditHide(e);return}let c=e.querySelector("[data-codex-reset-credit-label]"),l=e.querySelector("[data-codex-reset-credit-expiry]");'
        'c&&(c.textContent=__codexResetCreditLabel(i,t,r)),l&&(l.textContent=new Intl.DateTimeFormat(void 0,{month:"short",day:"numeric",hour:"numeric",minute:"2-digit"}).format(new Date(i.expires_at))),__codexResetCreditShow(e)})}).catch(()=>e.forEach(__codexResetCreditHide))}'
        'function __codexResetCreditSchedule(){clearTimeout(window[__codexResetCreditTimerKey]),window[__codexResetCreditTimerKey]=setTimeout(__codexResetCreditRefresh,100)}'
        'window.__codexResetCreditsRefresh=__codexResetCreditRefresh,window.__codexResetCreditListeners||(window.__codexResetCreditListeners=!0,window.addEventListener("focus",__codexResetCreditSchedule),document.addEventListener("visibilitychange",__codexResetCreditSchedule)),[0,1e3,3e3,1e4].forEach(e=>setTimeout(__codexResetCreditSchedule,e));'
        f'return Array.from({{length:{needle.credit_count}}},(e,t)=>(0,{needle.jsx}.jsx)({needle.item},{{className:{needle.classnames}({needle.compact}&&`pl-[calc(var(--padding-row-x)+1.25rem)] pr-[var(--padding-row-x)]`),disabled:!0,style:{{display:"none"}},"data-codex-reset-credit-row":!0,children:(0,{needle.jsx}.jsxs)("span",{{className:"flex w-full items-center justify-between gap-4",style:{{display:"none"}},ref:e=>{{e&&((window[__codexResetCreditRowsKey]||(window[__codexResetCreditRowsKey]=[]))[t]=e,__codexResetCreditSchedule())}},children:[(0,{needle.jsx}.jsx)("span",{{"data-codex-reset-credit-label":!0,children:`Reset ${{t+1}}`}}),(0,{needle.jsx}.jsx)("span",{{"data-codex-reset-credit-expiry":!0,className:"text-token-input-placeholder-foreground whitespace-nowrap",children:""}})]}})}},`reset-credit-expiry-${{t}}`))}})()'
    )


def _reset_row_needles() -> tuple[MenuNeedle, ...]:
    current = MenuNeedle(
        text='h>0?(0,CV.jsx)(Xb.Item,{RightIcon:Ib,className:$(x&&`pl-[calc(var(--padding-row-x)+1.25rem)] pr-[var(--padding-row-x)]`),onClick:c,children:(0,CV.jsx)(Z,{id:`composer.mode.rateLimit.resetsAvailable`,defaultMessage:`{availableRateLimitResetCount, plural, one {# reset available} other {# resets available}}`,description:`Menu item for opening available rate limit resets`,values:{availableRateLimitResetCount:h}})}):null',
        credit_count="h",
        compact="x",
        jsx="CV",
        item="Xb.Item",
        classnames="$",
    )
    previous = MenuNeedle(
        text='h>0?(0,CV.jsx)(Xb.Item,{className:"text-base",href:"#",onClick:e=>{e.preventDefault(),c&&c()},children:(0,CV.jsxs)("span",{className:"text-iconDefault flex items-center justify-between gap-3",children:[(0,CV.jsxs)("span",{children:[h," reset",h===1?"":"s"," available"]}),(0,CV.jsx)(tH,{className:"icon-sm shrink-0"})]})}):null',
        credit_count="h",
        compact="x",
        jsx="CV",
        item="Xb.Item",
        classnames="$",
    )
    updated = MenuNeedle(
        text='y>0?(0,X.jsx)(m.Item,{RightIcon:C,className:n(D&&`pl-[calc(var(--padding-row-x)+1.25rem)] pr-[var(--padding-row-x)]`),onClick:d,children:(0,X.jsx)(o,{id:`composer.mode.rateLimit.resetsAvailable`,defaultMessage:`{availableRateLimitResetCount, plural, one {# reset available} other {# resets available}}`,description:`Menu item for opening available rate limit resets`,values:{availableRateLimitResetCount:y}})}):null',
        credit_count="y",
        compact="D",
        jsx="X",
        item="m.Item",
        classnames="n",
    )
    return (current, previous, updated)
