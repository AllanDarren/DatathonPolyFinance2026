"""Business errors shared by core/ and services/.

The API maps them to `{error: {code, message, details?}}` with `status`.
Messages are in French: they are shown to the user as is.
"""

from __future__ import annotations

from typing import Any


class AlphaForgeError(Exception):
    def __init__(self, code: str, message: str, status: int = 400, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code, self.message, self.status, self.details = code, message, status, details

    def to_dict(self) -> dict[str, Any]:
        err: dict[str, Any] = {"code": self.code, "message": self.message}
        if self.details:
            err["details"] = self.details
        return {"error": err}


class DataError(AlphaForgeError):
    """Starter data or snapshot is missing or invalid (server-side problem)."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__("DATA_UNAVAILABLE", message, status=500, details=details)
