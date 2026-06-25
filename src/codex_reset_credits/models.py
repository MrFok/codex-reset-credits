from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ResetCredit:
    id: str | None
    title: str
    status: str
    expires_at: str | None
    granted_at: str | None
    reset_type: str | None

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "ResetCredit":
        return cls(
            id=_optional_str(payload.get("id")),
            title=_optional_str(payload.get("title")) or "Reset credit",
            status=_optional_str(payload.get("status")) or "unknown",
            expires_at=_optional_str(payload.get("expires_at")),
            granted_at=_optional_str(payload.get("granted_at")),
            reset_type=_optional_str(payload.get("reset_type")),
        )

    @property
    def category(self) -> str:
        haystack = f"{self.title} {self.reset_type or ''}".lower()
        if "partial" in haystack:
            return "partial"
        if "full" in haystack or "weekly" in haystack:
            return "full"
        return self.reset_type or "unknown"

    def menu_label(self, index: int, duplicate_count: int) -> str:
        base = self.title.split(" (", 1)[0].strip() or "Reset credit"
        if duplicate_count > 1:
            return f"{base} {index}"
        return base


def _optional_str(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def duplicate_title_counts(credits: list[ResetCredit]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for credit in credits:
        counts[credit.title] = counts.get(credit.title, 0) + 1
    return counts
