# codex-reset-credits

Small Python CLI for checking when Codex rate-limit reset credits expire. It reads
the local Codex auth file, calls the ChatGPT backend endpoint that returns reset
credit details, and prints the dates in your local timezone.

It can also patch the Codex desktop app menu so the "Usage remaining" section
shows reset-credit expiry rows. That patcher is intentionally separate from the
API checker because it modifies Electron app assets.

## What it shows

- Current usage windows from `https://chatgpt.com/backend-api/wham/usage`
- Reset-credit count and individual expiry times from
  `https://chatgpt.com/backend-api/wham/rate-limit-reset-credits`
- Reset-credit title, status, grant time, and reset type when the endpoint
  exposes them
- Local session-log fallback for basic rate-limit windows when the live API is
  unavailable

## Install

Requires Python 3.10 or newer.

```bash
git clone https://github.com/MrFok/codex-reset-credits.git
cd codex-reset-credits
python3 -m pip install -e .
```

Then run:

```bash
codex-reset-credits status
```

Without installing:

```bash
PYTHONPATH=src python3 -m codex_reset_credits.cli status
```

## For Agents

Use a local virtual environment and keep the install editable so follow-up agents
can inspect and modify the package without guessing import paths:

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

If you cannot install packages in the current environment, run from source:

```bash
cd codex-reset-credits
PYTHONPATH=src python3 -m codex_reset_credits.cli status
PYTHONPATH=src python3 -m unittest discover -s tests
```

Do not print or log `~/.codex/auth.json`. The CLI reads the local
`tokens.access_token` and sends it only as an HTTP `Authorization` header.
Use `patch-app --dry-run` before modifying any Codex desktop `app.asar`.

## Auth

By default the CLI reads:

```text
~/.codex/auth.json
```

Override it with:

```bash
codex-reset-credits --auth /path/to/auth.json status
```

The tool uses the local Codex `access_token`; it does not print tokens.

## Windows support

The API checker should work on Windows if Codex stores the same auth file at:

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

## Commands

Print human-readable status:

```bash
codex-reset-credits status
```

Print raw JSON merged from the usage and reset-credit endpoints:

```bash
codex-reset-credits status --json
```

Show only known reset-credit types/titles:

```bash
codex-reset-credits types
```

The `types` command groups credits by category, endpoint `reset_type`, title, and
status. Current observed credits are `full` resets, but the classifier keeps
future `partial` reset credits separate if the endpoint starts returning them.

Patch the Codex desktop menu from the current live reset-credit data:

```bash
codex-reset-credits patch-app
```

Dry-run the patcher without writing:

```bash
codex-reset-credits patch-app --dry-run
```

Patch a non-default `app.asar`:

```bash
codex-reset-credits patch-app --asar /path/to/app.asar
```

The patcher creates a `.bak` file next to the original unless `--backup` is
provided. Restart Codex desktop after patching.

## Caveats

- These are private, undocumented backend endpoints. They may change.
- The app patcher edits a bundled Electron asset. App updates can replace it.
- Patching the installed app may affect code-signing validation. Keep the backup.
