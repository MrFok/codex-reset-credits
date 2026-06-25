from __future__ import annotations

import datetime as dt
from typing import Any


def local_tz() -> dt.tzinfo:
    return dt.datetime.now().astimezone().tzinfo or dt.timezone.utc


def format_duration(seconds: int) -> str:
    seconds = max(0, seconds)
    days, seconds = divmod(seconds, 86_400)
    hours, seconds = divmod(seconds, 3_600)
    minutes, seconds = divmod(seconds, 60)

    parts: list[str] = []
    if days:
        parts.append(f"{days}d")
    if hours or parts:
        parts.append(f"{hours}h")
    if minutes or parts:
        parts.append(f"{minutes}m")
    parts.append(f"{seconds}s")
    return " ".join(parts)


def parse_iso_datetime(value: Any) -> dt.datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def format_iso_datetime(value: Any) -> str:
    parsed = parse_iso_datetime(value)
    if parsed is None:
        return str(value) if value is not None else "not provided"

    local = parsed.astimezone(local_tz())
    utc = parsed.astimezone(dt.timezone.utc)
    remaining = local - dt.datetime.now(tz=local_tz())
    return (
        f"{local:%Y-%m-%d %H:%M:%S %Z} "
        f"(UTC {utc:%Y-%m-%d %H:%M:%S}, in {format_duration(int(remaining.total_seconds()))})"
    )


def format_epoch(value: Any) -> str:
    if value is None:
        return "not provided"
    try:
        seconds = int(value)
    except (TypeError, ValueError):
        return str(value)

    local = dt.datetime.fromtimestamp(seconds, tz=local_tz())
    utc = dt.datetime.fromtimestamp(seconds, tz=dt.timezone.utc)
    remaining = local - dt.datetime.now(tz=local_tz())
    return (
        f"{local:%Y-%m-%d %H:%M:%S %Z} "
        f"(UTC {utc:%Y-%m-%d %H:%M:%S}, in {format_duration(int(remaining.total_seconds()))})"
    )


