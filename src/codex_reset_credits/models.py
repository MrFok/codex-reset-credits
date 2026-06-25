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


def _optional_str(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None

