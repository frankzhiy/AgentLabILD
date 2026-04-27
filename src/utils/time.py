"""Time helpers shared by validators and report builders."""

from __future__ import annotations

from datetime import datetime, timezone


def utc_now() -> datetime:
    """Return timezone-aware current UTC time.

    Keeping the default time source behind one helper makes later naive/aware
    policy changes a one-place modification.
    """

    return datetime.now(timezone.utc)


__all__ = ["utc_now"]