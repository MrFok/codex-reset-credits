# codex-reset-credits

did you know your reset credits have expiration dates? 

see your Codex usage windows and reset-credit expiration times from the command
line.

why aren't they shown natively? no clue, but until it's addressed you can use this

![Codex reset credits demo](public/demo_img.png)

`codex-reset-credits` is a small CLI utility and Codex desktop patcher for
checking how many Codex reset credits are available, when each credit expires,
and when the current usage windows reset. It can also patch the Codex desktop
"Usage remaining" menu to show those reset-credit expiry rows in the app.

## Features

- Shows Codex usage-window reset times in your local timezone.
- Shows available reset credits and individual expiry times.
- Prints raw JSON for debugging or automation.
- Groups reset credits by known type/title/status.

## Requirements

- Python 3.10 or newer
- A local Codex auth file at `~/.codex/auth.json` (you should already have this)

Run Codex desktop or Codex CLI login first if that auth file does not exist.

## Installation

```bash
git clone https://github.com/MrFok/codex-reset-credits.git
cd codex-reset-credits
python3 -m pip install -e .
```

To run without installing:

```bash
git clone https://github.com/MrFok/codex-reset-credits.git
cd codex-reset-credits
PYTHONPATH=src python3 -m codex_reset_credits.cli status
```

## Quick Start

```bash
codex-reset-credits status
```

Example commands:

```bash
codex-reset-credits status
codex-reset-credits status --json
codex-reset-credits types
codex-reset-credits patch-status
codex-reset-credits ensure-patched --dry-run
codex-reset-credits patch-app --dry-run
```

## Commands

### `status`

Print a human-readable summary of usage windows and reset credits.

```bash
codex-reset-credits status
```

Print the merged raw API response:

```bash
codex-reset-credits status --json
```

Use local session logs only:

```bash
codex-reset-credits status --no-api
```

### `types`

Show the reset-credit categories returned by the endpoint.

```bash
codex-reset-credits types
```

The command groups credits by category, endpoint `reset_type`, title, and
status. Current observed credits are `full` resets, but the classifier keeps
future `partial` reset credits separate if the endpoint starts returning them.

### `patch-app`

Patch the Codex desktop app menu to show live reset-credit expiry rows.

```bash
codex-reset-credits patch-app
```

The patch installs a live in-app fetcher. When Codex renders the usage menu, the
injected rows reuse Codex desktop's authenticated API client to request
`/wham/rate-limit-reset-credits` and populate from the current response. When
available at patch time, the command also bakes the current reset-credit
response as a fallback so rows can render before the live in-app request
finishes.

The in-app fetcher caches the last successful reset-credit response so the rows
render immediately on later menu opens. It refreshes on first load, shortly
before the earliest credit expiry, and after the native reset-credit menu item is
clicked.

Always dry-run first:

```bash
codex-reset-credits patch-app --dry-run
```

### `patch-status`

Run the read-only patch status command to check whether the Codex desktop app
bundle currently contains the reset-credit menu patch:

```bash
codex-reset-credits patch-status
```

The command is read-only. It reports whether the target `app.asar` exists,
whether the patch marker is present, the bundle hash, the bundle modification
time, whether `ensure-patched` would update it, and whether a low-level
`patch-app --dry-run` would update it.

### `ensure-patched`

Run the idempotent one-shot repair command to reapply the Codex desktop app
patch only when the target bundle is unpatched or stale:

```bash
codex-reset-credits ensure-patched
```

Use this after Codex desktop updates, since updates can replace the patched
`app.asar` with a fresh bundle. If the patch is already present, the command
does not rewrite the app bundle. If it applies the patch, fully quit and reopen
Codex desktop so the running app loads the updated ASAR.

Preview without writing:

```bash
codex-reset-credits ensure-patched --dry-run
```

Patch a non-default `app.asar`:

```bash
codex-reset-credits patch-app --asar /path/to/app.asar
```

The patcher creates a `.bak` file next to the original unless `--backup` is
provided. Restart Codex desktop after patching.

## Auth

By default the CLI reads `~/.codex/auth.json`. Override it with:

```bash
codex-reset-credits --auth /path/to/auth.json status
```

The tool reads `tokens.access_token` and sends it as an HTTP `Authorization`
header. It does not print tokens.

## Windows support

The API checker should work on Windows if Codex stores auth at:

```text
%USERPROFILE%\.codex\auth.json
```

Use PowerShell like:

```powershell
py -m pip install -e .
codex-reset-credits status
```

The app patcher is macOS-first because the default Codex app bundle path is
macOS-specific:

```text
/Applications/Codex.app/Contents/Resources/app.asar
```

On Windows, the API checker is the portable part. The patcher may work if you
pass the correct `app.asar` path with `--asar`, but the Windows Codex desktop
install path and signing/update behavior still need verification.

## For Agents

Use a local virtual environment and keep the install editable:

```bash
git clone https://github.com/MrFok/codex-reset-credits.git
cd codex-reset-credits
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -U pip
python -m pip install -e .
codex-reset-credits --help
codex-reset-credits status
```

If package installation is not available:

```bash
cd codex-reset-credits
PYTHONPATH=src python3 -m codex_reset_credits.cli status
PYTHONPATH=src python3 -m unittest discover -s tests
```

Do not print or log `~/.codex/auth.json`. `patch-app` may read live
reset-credit data at install time to bake a fallback response, but it must not
print tokens. Use `patch-app --dry-run` before modifying any Codex desktop
`app.asar`.

## Notes

- This uses private, undocumented ChatGPT backend endpoints. They may change.
- The app patcher edits a bundled Electron asset. App updates can replace it.
- Patching the installed app may affect code-signing validation. Keep the backup.
- If Codex is offline or the reset-credit endpoint fails, the patched app hides
  the extra reset-credit rows instead of showing stale data.
