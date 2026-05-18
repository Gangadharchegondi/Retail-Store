"""Audit logging helpers for order and payment lifecycle events."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from backend.models import AuditEvent


def record_audit_event(
    db: Session,
    event_type: str,
    message: str,
    user_id: int | None = None,
    order_id: int | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Persist a lightweight audit event in the current DB transaction."""
    payload = None
    if metadata:
        payload = json.dumps(metadata, default=str)

    db.add(
        AuditEvent(
            user_id=user_id,
            order_id=order_id,
            event_type=event_type,
            message=message,
            metadata_json=payload,
        )
    )
