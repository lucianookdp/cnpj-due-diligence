from datetime import datetime
from typing import ClassVar

from sqlalchemy import DateTime
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Maps every `Mapped[datetime]` column to TIMESTAMPTZ project-wide.

    Without this, a naive TIMESTAMP column silently stores tz-aware Python
    datetimes as the session's *local* wall-clock digits, not UTC — invisible
    against day/month-scale thresholds (cache TTL, QSA-churn window) but a
    real bug against a tight "is this due right now" comparison (the job
    queue's scheduled_for). Found via that exact failure.
    """

    type_annotation_map: ClassVar[dict] = {datetime: DateTime(timezone=True)}
