from __future__ import annotations

import glob
import json
import os
import pathlib
import urllib.error
import urllib.request
from typing import Any

from .auth import DEFAULT_AUTH_PATH, auth_headers
from .models import ResetCredit


DEFAULT_USAGE_URL = "https://chatgpt.com/backend-api/wham/usage"
DEFAULT_RESET_CREDITS_URL = "https://chatgpt.com/backend-api/wham/rate-limit-reset-credits"


def fetch_json(auth_path: pathlib.Path, url: str, timeout: float) -> dict[str, Any]:
    request = urllib.request.Request(url, headers=auth_headers(auth_path))
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read())
    except urllib.error.HTTPError as exc:
        body = exc.read(500).decode("utf-8", errors="replace")
        raise RuntimeError(f"{url} returned HTTP {exc.code}: {body}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"{url} request failed: {exc}") from exc

    if not isinstance(data, dict):
        raise RuntimeError(f"{url} returned non-object JSON")
    return data


def fetch_usage(
    auth_path: pathlib.Path = DEFAULT_AUTH_PATH,
    url: str = DEFAULT_USAGE_URL,
    timeout: float = 20.0,
) -> dict[str, Any]:
    return fetch_json(auth_path, url, timeout)


def fetch_reset_credits(
    auth_path: pathlib.Path = DEFAULT_AUTH_PATH,
    url: str = DEFAULT_RESET_CREDITS_URL,
    timeout: float = 20.0,
) -> dict[str, Any]:
    return fetch_json(auth_path, url, timeout)


def merge_status(usage: dict[str, Any], reset_credits: dict[str, Any] | None) -> dict[str, Any]:
    merged = dict(usage)
    if isinstance(reset_credits, dict):
        merged["_rate_limit_reset_credits_detail"] = reset_credits
        if not isinstance(merged.get("rate_limit_reset_credits"), dict):
            merged["rate_limit_reset_credits"] = {
                "available_count": reset_credits.get("available_count"),
            }
    return merged


def reset_credit_objects(payload: dict[str, Any]) -> list[ResetCredit]:
    credits = payload.get("credits")
    if not isinstance(credits, list):
        return []
    return [ResetCredit.from_payload(item) for item in credits if isinstance(item, dict)]


def newest_session_rate_limits() -> dict[str, Any] | None:
    session_glob = str(pathlib.Path.home() / ".codex" / "sessions" / "**" / "*.jsonl")
    newest: tuple[float, dict[str, Any]] | None = None

    for file_name in glob.iglob(session_glob, recursive=True):
        try:
            mtime = os.path.getmtime(file_name)
            with open(file_name, "r", encoding="utf-8") as handle:
                for line in handle:
                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    rate_limits = _extract_rate_limits(event)
                    if isinstance(rate_limits, dict) and (newest is None or mtime >= newest[0]):
                        newest = (mtime, rate_limits)
        except OSError:
            continue
    return newest[1] if newest else None


def normalize_log_rate_limits(rate_limits: dict[str, Any]) -> dict[str, Any]:
    return {
        "plan_type": rate_limits.get("plan_type"),
        "rate_limit": {
            "limit_reached": rate_limits.get("rate_limit_reached_type") is not None,
            "primary_window": _log_window(rate_limits.get("primary")),
            "secondary_window": _log_window(rate_limits.get("secondary")),
        },
        "rate_limit_reset_credits": rate_limits.get("credits"),
        "_source": "local session log fallback",
    }


def _extract_rate_limits(event: dict[str, Any]) -> Any:
    rate_limits = event.get("rate_limits")
    if isinstance(rate_limits, dict):
        return rate_limits
    payload = event.get("payload")
    if isinstance(payload, dict):
        return payload.get("rate_limits")
    return None


def _log_window(source: Any) -> dict[str, Any] | None:
    if not isinstance(source, dict):
        return None
    return {
        "used_percent": source.get("used_percent"),
        "reset_at": source.get("resets_at"),
        "limit_window_seconds": _minutes_to_seconds(source.get("window_minutes")),
    }


def _minutes_to_seconds(value: Any) -> int | None:
    try:
        return int(value) * 60
    except (TypeError, ValueError):
        return None

