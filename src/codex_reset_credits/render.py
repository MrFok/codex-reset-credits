from __future__ import annotations

import json
from collections import Counter
from typing import Any

from .api import reset_credit_objects
from .formatting import format_duration, format_epoch, format_iso_datetime


def print_status(data: dict[str, Any], source: str) -> None:
    print(f"Source: {source}")
    if data.get("_source"):
        print(f"Fallback: {data['_source']}")
    if data.get("plan_type") is not None:
        print(f"Plan: {data['plan_type']}")
    if data.get("rate_limit_reached_type") is not None:
        print(f"Limit reached type: {data['rate_limit_reached_type']}")

    rate_limit = data.get("rate_limit")
    if isinstance(rate_limit, dict):
        print(f"Allowed: {rate_limit.get('allowed', 'unknown')}")
        print(f"Limit reached: {rate_limit.get('limit_reached', 'unknown')}")
        print_window("Primary", rate_limit.get("primary_window"))
        print_window("Secondary", rate_limit.get("secondary_window"))

    additional = data.get("additional_rate_limits")
    if isinstance(additional, list) and additional:
        print("\nAdditional rate limits:")
        for item in additional:
            if not isinstance(item, dict):
                continue
            name = item.get("limit_name") or item.get("metered_feature") or "unnamed"
            print(f"- {name}")
            nested = item.get("rate_limit")
            if isinstance(nested, dict):
                print_window("  Primary", nested.get("primary_window"))
                print_window("  Secondary", nested.get("secondary_window"))

    print_reset_credits(data)


def print_window(label: str, window: Any) -> None:
    if not isinstance(window, dict):
        print(f"{label}: not provided")
        return

    used = window.get("used_percent")
    limit_seconds = window.get("limit_window_seconds")
    window_text = format_duration(int(limit_seconds)) if limit_seconds else "unknown window"
    reset_at = window.get("reset_at") or window.get("resets_at") or window.get("resetsAt")
    print(f"{label}:")
    print(f"  used: {used if used is not None else 'unknown'}%")
    print(f"  window: {window_text}")
    print(f"  resets: {format_epoch(reset_at)}")


def print_reset_credits(data: dict[str, Any]) -> None:
    print("\nReset credits:")
    detail = data.get("_rate_limit_reset_credits_detail")
    if isinstance(detail, dict):
        available_count = detail.get("available_count")
        if available_count is not None:
            print(f"  available: {available_count}")
        credits = reset_credit_objects(detail)
        if not credits:
            print("  no individual credits returned")
            return
        for index, credit in enumerate(credits, start=1):
            print(f"  {index}. {credit.title} [{credit.status}]")
            if credit.reset_type:
                print(f"     type: {credit.reset_type}")
            print(f"     expires: {format_iso_datetime(credit.expires_at)}")
            if credit.granted_at:
                print(f"     granted: {format_iso_datetime(credit.granted_at)}")
        return

    reset_credits = data.get("rate_limit_reset_credits")
    if isinstance(reset_credits, dict):
        if "available_count" in reset_credits:
            print(f"  available: {reset_credits['available_count']}")
        expiry_fields = [
            (path, value)
            for path, value in find_expiry_fields(reset_credits)
            if path != "available_count"
        ]
        if expiry_fields:
            for path, value in expiry_fields:
                print(f"  {path}: {format_epoch(value)}")
        else:
            print("  expiry: not exposed by this endpoint")
    elif reset_credits is None:
        print("  not provided")
    else:
        print(f"  {reset_credits}")


def print_reset_types(reset_credits: dict[str, Any]) -> None:
    credits = reset_credit_objects(reset_credits)
    if not credits:
        print("No individual reset credits returned.")
        return

    counts = Counter((credit.reset_type or "unknown", credit.title, credit.status) for credit in credits)
    print("Reset credit types:")
    for (reset_type, title, status), count in sorted(counts.items()):
        print(f"- {reset_type}: {title} [{status}] x{count}")


def dumps_json(data: dict[str, Any]) -> str:
    return json.dumps(data, indent=2, sort_keys=True)


def find_expiry_fields(value: Any, path: str = "") -> list[tuple[str, Any]]:
    matches: list[tuple[str, Any]] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}" if path else key
            lowered = key.lower()
            if any(part in lowered for part in ("expire", "expiry", "expires", "reset_at", "resets_at", "resetsat")):
                matches.append((child_path, child))
            matches.extend(find_expiry_fields(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            matches.extend(find_expiry_fields(child, f"{path}[{index}]"))
    return matches

