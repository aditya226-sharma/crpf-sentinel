"""VAJRA OSINT sync-state tracking.

The poller must not re-submit records it has already pushed into the main
pipeline. Each record is uniquely identified by its source citation chain
(entity_name + source_url + fetched_at); ``last_seen_at`` records when the
poller last saw that citation, and ``pushed_at`` marks the moment it was
forwarded to the ingestion endpoint.
"""

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, String

from app.database.base import Base


class OsintSyncState(Base):
    __tablename__ = "osint_sync_state"

    citation_key = Column(String(512), primary_key=True)
    entity_name = Column(String(256), nullable=False, index=True)
    source_url = Column(String(2048), nullable=False)
    fetched_at = Column(String(64), nullable=False)
    pushed_at = Column(DateTime(timezone=True), nullable=True)
    last_seen_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )