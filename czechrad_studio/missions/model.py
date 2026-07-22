"""Portable mission model shared by persistence and future clients."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Mission:
    """A user-managed collection of one or more daily CzechRad logs."""

    id: str
    name: str
    description: str
    status: str
    started_at_utc: datetime | None
    ended_at_utc: datetime | None
    created_at_utc: datetime
    updated_at_utc: datetime

