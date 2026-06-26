from __future__ import annotations

import posixpath
import re
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
    "(()=>{const __codexResetCreditModule=",
    "(()=>{const __codexResetCredits=",
)
RESET_CREDITS_ROUTE = "/wham/rate-limit-reset-credits"


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


@dataclass(frozen=True)
class ResetCreditApiClient:
    module_path: str
    client_export: str


def patch_usage_menu(
    asar_path: Path,
    backup_path: Path | None = None,
    dry_run: bool = False,
) -> PatchResult:
    archive = read_asar(asar_path)
    menu_chunk_path = find_menu_chunk_path(archive)
    api_client = find_reset_credit_api_client(archive, menu_chunk_path)
    chunk = get_file(archive, menu_chunk_path).decode("utf-8")
    patched = patch_menu_chunk(chunk, api_client=api_client)
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


def find_reset_credit_api_client(archive: AsarFile, menu_chunk_path: str) -> ResetCreditApiClient:
    matches = []
    route = RESET_CREDITS_ROUTE.encode("utf-8")
    for path in iter_file_paths(archive):
        if not path.startswith("webview/assets/") or not path.endswith(".js"):
            continue
        content = get_file(archive, path)
        if route not in content or b"safeGet" not in content or b"export{" not in content:
            continue
        text = content.decode("utf-8", errors="replace")
        client_match = re.search(
            rf"\b([A-Za-z_$][\w$]*)\.safeGet\(`{re.escape(RESET_CREDITS_ROUTE)}`\)",
            text,
        )
        if client_match is None:
            continue
        client_name = client_match.group(1)
        export_match = re.search(rf"\b{re.escape(client_name)} as ([A-Za-z_$][\w$]*)\b", text)
        if export_match:
            matches.append(ResetCreditApiClient(_relative_module_path(menu_chunk_path, path), export_match.group(1)))

    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise KeyError(f"could not find Codex reset-credit API client containing {RESET_CREDITS_ROUTE!r}")
    paths = ", ".join(match.module_path for match in matches)
    raise ValueError(f"found multiple candidate Codex reset-credit API clients: {paths}")


def _relative_module_path(from_path: str, to_path: str) -> str:
    relative = posixpath.relpath(to_path, posixpath.dirname(from_path))
    if not relative.startswith("."):
        relative = f"./{relative}"
    return relative


def _is_menu_chunk(content: bytes) -> bool:
    if PATCH_MARKER.encode("utf-8") in content:
        return True
    if MENU_CHUNK_MARKER.encode("utf-8") not in content:
        return False
    return all(marker.encode("utf-8") in content for marker in MENU_CHUNK_COMPONENT_MARKERS)


def patch_menu_chunk(
    chunk: str,
    api_client: ResetCreditApiClient | None = None,
) -> str:
    api_client = api_client or ResetCreditApiClient("./reset-credit-api.js", "apiClient")
    if PATCH_MARKER in chunk:
        needle = _needle_for_chunk(chunk)
        if needle is None:
            raise ValueError("found previous patch marker but could not identify Codex usage reset menu item shape")
        span = _existing_patch_span(chunk)
        if span is None:
            raise ValueError("found previous patch marker but could not locate patch block")
        start, end = span
        replacement = _reset_credit_js(needle, api_client)
        return chunk[:start] + replacement + chunk[end:]

    for needle in _reset_row_needles():
        if needle.text in chunk:
            return chunk.replace(needle.text, needle.text + "," + _reset_credit_js(needle, api_client), 1)
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


def _reset_credit_js(needle: MenuNeedle, api_client: ResetCreditApiClient) -> str:
    return (
        f'(()=>{{const __codexResetCreditModule="{api_client.module_path}",'
        f'__codexResetCreditClientExport="{api_client.client_export}",'
        '__codexResetCreditRowsKey="__codexResetCreditRows",'
        '__codexResetCreditTimerKey="__codexResetCreditTimer",'
        '__codexResetCreditExpiryTimerKey="__codexResetCreditExpiryTimer",'
        '__codexResetCreditCacheKey="__codexResetCreditCache";'
        '/* reset-credit-expiry */'
        'function __codexResetCreditHide(row){row&&(row.style.display="none");let item=row?.closest?.("[data-codex-reset-credit-row]")||row?.parentElement;item&&(item.style.display="none")}'
        'function __codexResetCreditShow(row){row&&(row.style.display="");let item=row?.closest?.("[data-codex-reset-credit-row]")||row?.parentElement;item&&(item.style.display="")}'
        'function __codexResetCreditLabel(credit,index,titleCounts){let title=credit.title||"Reset credit",label=(title.split(" (",1)[0]||"Reset credit").trim();return titleCounts[title]>1?`${label} ${index+1}`:label}'
        'function __codexResetCreditFetch(){return import(new URL(__codexResetCreditModule,import.meta.url).href).then(module=>module[__codexResetCreditClientExport].safeGet("/wham/rate-limit-reset-credits"))}'
        'function __codexResetCreditCredits(response){return Array.isArray(response?.credits)?response.credits.filter(credit=>credit&&credit.expires_at):[]}'
        'function __codexResetCreditScheduleExpiry(credits){clearTimeout(window[__codexResetCreditExpiryTimerKey]);let expiresAt=credits.map(credit=>Date.parse(credit.expires_at)).filter(Number.isFinite).sort((left,right)=>left-right)[0];'
        'expiresAt&&(window[__codexResetCreditExpiryTimerKey]=setTimeout(()=>__codexResetCreditRefresh(!0),Math.max(6e4,Math.min(2147483647,expiresAt-Date.now()-3e5))))}'
        'function __codexResetCreditRender(response){let rows=(window[__codexResetCreditRowsKey]||[]).filter(Boolean),credits=__codexResetCreditCredits(response),titleCounts={};if(!rows.length)return;'
        'if(!credits.length){rows.forEach(__codexResetCreditHide);return}'
        'credits.forEach(credit=>{let title=credit.title||"Reset credit";titleCounts[title]=(titleCounts[title]||0)+1}),rows.forEach((row,index)=>{let credit=credits[index];'
        'if(!credit){__codexResetCreditHide(row);return}let label=row.querySelector("[data-codex-reset-credit-label]"),expiry=row.querySelector("[data-codex-reset-credit-expiry]");'
        'label&&(label.textContent=__codexResetCreditLabel(credit,index,titleCounts)),expiry&&(expiry.textContent=new Intl.DateTimeFormat(void 0,{month:"short",day:"numeric",hour:"numeric",minute:"2-digit"}).format(new Date(credit.expires_at))),__codexResetCreditShow(row)}),__codexResetCreditScheduleExpiry(credits)}'
        'function __codexResetCreditRefresh(force){let rows=(window[__codexResetCreditRowsKey]||[]).filter(Boolean),cachedResponse=window[__codexResetCreditCacheKey];'
        'if(!rows.length)return;if(cachedResponse&&!force){__codexResetCreditRender(cachedResponse);return}__codexResetCreditFetch().then(response=>{window[__codexResetCreditCacheKey]=response,__codexResetCreditRender(response)}).catch(()=>cachedResponse?__codexResetCreditRender(cachedResponse):rows.forEach(__codexResetCreditHide))}'
        'function __codexResetCreditSchedule(force,delay=100){clearTimeout(window[__codexResetCreditTimerKey]),window[__codexResetCreditTimerKey]=setTimeout(()=>__codexResetCreditRefresh(force),delay)}'
        'function __codexResetCreditInvalidate(){delete window[__codexResetCreditCacheKey],[1e3,3e3,1e4].forEach(delay=>setTimeout(()=>__codexResetCreditRefresh(!0),delay))}'
        'function __codexResetCreditBindNativeClick(item){let nativeResetItem=item?.previousElementSibling;nativeResetItem&&!nativeResetItem.__codexResetCreditClickBound&&(nativeResetItem.__codexResetCreditClickBound=!0,nativeResetItem.addEventListener("click",__codexResetCreditInvalidate,!0))}'
        'window.__codexResetCreditsRefresh=()=>__codexResetCreditRefresh(!0);'
        f'return Array.from({{length:{needle.credit_count}}},(unused,index)=>(0,{needle.jsx}.jsx)({needle.item},{{className:{needle.classnames}({needle.compact}&&`pl-[calc(var(--padding-row-x)+1.25rem)] pr-[var(--padding-row-x)]`),disabled:!0,style:{{display:"none"}},"data-codex-reset-credit-row":!0,children:(0,{needle.jsx}.jsxs)("span",{{className:"flex w-full items-center justify-between gap-4",style:{{display:"none"}},ref:row=>{{if(row){{(window[__codexResetCreditRowsKey]||(window[__codexResetCreditRowsKey]=[]))[index]=row;let item=row.closest?.("[data-codex-reset-credit-row]")||row.parentElement;__codexResetCreditBindNativeClick(item),window[__codexResetCreditCacheKey]&&__codexResetCreditRender(window[__codexResetCreditCacheKey]),__codexResetCreditSchedule(!1)}}}},children:[(0,{needle.jsx}.jsx)("span",{{"data-codex-reset-credit-label":!0,children:`Reset ${{index+1}}`}}),(0,{needle.jsx}.jsx)("span",{{"data-codex-reset-credit-expiry":!0,className:"text-token-input-placeholder-foreground whitespace-nowrap",children:""}})]}})}},`reset-credit-expiry-${{index}}`))}})()'
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
    current_updated = MenuNeedle(
        text='h>0?(0,mG.jsx)(qd.Item,{RightIcon:ca,className:H(x&&`pl-[calc(var(--padding-row-x)+1.25rem)] pr-[var(--padding-row-x)]`),onClick:c,children:(0,mG.jsx)(X,{id:`composer.mode.rateLimit.resetsAvailable`,defaultMessage:`{availableRateLimitResetCount, plural, one {# reset available} other {# resets available}}`,description:`Menu item for opening available rate limit resets`,values:{availableRateLimitResetCount:h}})}):null',
        credit_count="h",
        compact="x",
        jsx="mG",
        item="qd.Item",
        classnames="H",
    )
    return (current, previous, updated, current_updated)
