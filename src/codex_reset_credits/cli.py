from __future__ import annotations

import argparse
import pathlib
import sys
from datetime import datetime

from .api import (
    DEFAULT_RESET_CREDITS_URL,
    DEFAULT_USAGE_URL,
    fetch_reset_credits,
    fetch_usage,
    merge_status,
    newest_session_rate_limits,
    normalize_log_rate_limits,
)
from .app_patch import DEFAULT_MACOS_ASAR, ensure_usage_menu_patched, get_patch_status, patch_usage_menu
from .auth import DEFAULT_AUTH_PATH
from .render import dumps_json, print_reset_types, print_status


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Show Codex reset-credit expiration times.")
    parser.add_argument("--auth", type=pathlib.Path, default=DEFAULT_AUTH_PATH)
    parser.add_argument("--usage-url", default=DEFAULT_USAGE_URL)
    parser.add_argument("--reset-credits-url", default=DEFAULT_RESET_CREDITS_URL)
    parser.add_argument("--timeout", type=float, default=20.0)

    subparsers = parser.add_subparsers(dest="command")

    status_parser = subparsers.add_parser("status", help="print Codex usage and reset-credit expirations")
    status_parser.add_argument("--json", action="store_true", help="print merged raw JSON")
    status_parser.add_argument("--no-api", action="store_true", help="use local session logs only")

    types_parser = subparsers.add_parser("types", help="print reset-credit types returned by the endpoint")
    types_parser.add_argument("--json", action="store_true", help="print raw reset-credit JSON")

    patch_parser = subparsers.add_parser("patch-app", help="patch Codex desktop menu with reset-credit expirations")
    patch_parser.add_argument("--asar", type=pathlib.Path, default=DEFAULT_MACOS_ASAR)
    patch_parser.add_argument("--backup", type=pathlib.Path)
    patch_parser.add_argument("--dry-run", action="store_true")

    patch_status_parser = subparsers.add_parser(
        "patch-status",
        help="report whether the Codex desktop ASAR is patched",
    )
    patch_status_parser.add_argument("--asar", type=pathlib.Path, default=DEFAULT_MACOS_ASAR)

    ensure_parser = subparsers.add_parser(
        "ensure-patched",
        help="patch Codex desktop only when the ASAR is unpatched",
    )
    ensure_parser.add_argument("--asar", type=pathlib.Path, default=DEFAULT_MACOS_ASAR)
    ensure_parser.add_argument("--backup", type=pathlib.Path)
    ensure_parser.add_argument("--dry-run", action="store_true")

    args = parser.parse_args(argv)
    command = args.command or "status"

    if command == "status":
        return _status(args)
    if command == "types":
        return _types(args)
    if command == "patch-app":
        return _patch_app(args)
    if command == "patch-status":
        return _patch_status(args)
    if command == "ensure-patched":
        return _ensure_patched(args)
    parser.error(f"unknown command: {command}")
    return 2


def _status(args: argparse.Namespace) -> int:
    source = args.usage_url
    try:
        if args.no_api:
            raise RuntimeError("live endpoint skipped")
        usage = fetch_usage(args.auth, args.usage_url, args.timeout)
        try:
            reset_credits = fetch_reset_credits(args.auth, args.reset_credits_url, args.timeout)
        except Exception as exc:
            reset_credits = {"_error": str(exc)}
        data = merge_status(usage, reset_credits)
    except Exception as exc:
        fallback = newest_session_rate_limits()
        if fallback is None:
            print(f"Could not fetch live usage: {exc}", file=sys.stderr)
            print("No local session rate-limit events found.", file=sys.stderr)
            return 1
        data = normalize_log_rate_limits(fallback)
        source = "local Codex session logs"
        print(f"Live usage unavailable: {exc}", file=sys.stderr)

    if args.json:
        print(dumps_json(data))
    else:
        print_status(data, source)
    return 0


def _types(args: argparse.Namespace) -> int:
    reset_credits = fetch_reset_credits(args.auth, args.reset_credits_url, args.timeout)
    if args.json:
        print(dumps_json(reset_credits))
    else:
        print_reset_types(reset_credits)
    return 0


def _patch_app(args: argparse.Namespace) -> int:
    reset_credit_fallback = None
    try:
        reset_credit_fallback = fetch_reset_credits(args.auth, args.reset_credits_url, args.timeout)
    except Exception as exc:
        print(f"reset-credit fallback unavailable: {exc}", file=sys.stderr)

    result = patch_usage_menu(
        args.asar,
        backup_path=args.backup,
        dry_run=args.dry_run,
        reset_credit_fallback=reset_credit_fallback,
    )

    action = "would update" if result.dry_run and result.changed else "updated"
    if not result.changed:
        action = "already up to date"
    print(f"{action}: {result.asar_path}")
    print("reset credits rendered: live in Codex desktop")
    if reset_credit_fallback:
        credits = reset_credit_fallback.get("credits")
        print(f"fallback credits baked: {len(credits) if isinstance(credits, list) else 0}")
    if result.backup_path:
        print(f"backup: {result.backup_path}")
    if result.dry_run:
        print("dry run: no files written")
    return 0


def _patch_status(args: argparse.Namespace) -> int:
    status = get_patch_status(args.asar)
    print(f"asar: {status.asar_path}")
    print(f"exists: {_yes_no(status.exists)}")
    print(f"patched: {_yes_no(status.patched)}")
    print(f"current patch: {_yes_no(status.current)}")
    if status.sha256:
        print(f"sha256: {status.sha256}")
    if status.mtime is not None:
        print(f"mtime: {_format_timestamp(status.mtime)}")
    print(f"ensure-patched would update: {_yes_no(status.exists and not status.current)}")
    print(f"patch-app dry-run would update: {_format_optional_bool(status.would_update)}")
    if status.error:
        print(f"status error: {status.error}", file=sys.stderr)
    return 0 if status.exists else 1


def _ensure_patched(args: argparse.Namespace) -> int:
    status = get_patch_status(args.asar)
    if not status.exists:
        print(f"asar not found: {args.asar}", file=sys.stderr)
        return 1

    if status.current:
        print(f"already patched: {args.asar}")
        print("restart Codex required: no")
        if args.dry_run:
            print("dry run: no files written")
        return 0

    reset_credit_fallback = None
    try:
        reset_credit_fallback = fetch_reset_credits(args.auth, args.reset_credits_url, args.timeout)
    except Exception as exc:
        print(f"reset-credit fallback unavailable: {exc}", file=sys.stderr)

    result = ensure_usage_menu_patched(
        args.asar,
        backup_path=args.backup,
        dry_run=args.dry_run,
        reset_credit_fallback=reset_credit_fallback,
    )

    action = "would update" if result.dry_run and result.changed else "updated"
    if not result.changed:
        action = "already patched"
    print(f"{action}: {result.asar_path}")
    if reset_credit_fallback:
        credits = reset_credit_fallback.get("credits")
        print(f"fallback credits baked: {len(credits) if isinstance(credits, list) else 0}")
    if result.backup_path:
        print(f"backup: {result.backup_path}")
    if result.dry_run:
        print("dry run: no files written")
    print(f"restart Codex required: {_yes_no(result.changed and not result.dry_run)}")
    return 0


def _yes_no(value: bool) -> str:
    return "yes" if value else "no"


def _format_optional_bool(value: bool | None) -> str:
    if value is None:
        return "unknown"
    return _yes_no(value)


def _format_timestamp(value: float) -> str:
    return datetime.fromtimestamp(value).isoformat(timespec="seconds")


if __name__ == "__main__":
    raise SystemExit(main())
