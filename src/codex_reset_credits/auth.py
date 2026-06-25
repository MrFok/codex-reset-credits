from __future__ import annotations

import json
import pathlib
from typing import Any


DEFAULT_AUTH_PATH = pathlib.Path.home() / ".codex" / "auth.json"


def load_tokens(path: pathlib.Path = DEFAULT_AUTH_PATH) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise SystemExit(f"auth file not found: {path}") from None
    except json.JSONDecodeError as exc:
        raise SystemExit(f"auth file is not valid JSON: {path}: {exc}") from None

    tokens = data.get("tokens")
    if not isinstance(tokens, dict):
        raise SystemExit(f"auth file does not contain tokens: {path}")
    return tokens


def auth_headers(path: pathlib.Path = DEFAULT_AUTH_PATH) -> dict[str, str]:
    tokens = load_tokens(path)
    access_token = tokens.get("access_token")
    if not access_token:
        raise SystemExit(f"auth file is missing tokens.access_token: {path}")

    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {access_token}",
        "User-Agent": "codex-reset-credits/0.1",
    }
    account_id = tokens.get("account_id")
    if account_id:
        headers["OpenAI-Account-ID"] = str(account_id)
        headers["x-oai-account-id"] = str(account_id)
    return headers

