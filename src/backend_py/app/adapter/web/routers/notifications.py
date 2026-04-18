"""/api/notifications/preferences 조회/수정."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapter.out.persistence.repositories import NotificationPreferenceRepository
from app.adapter.web._deps import get_session, require_admin_key
from app.adapter.web._schemas import (
    NotificationPreferenceResponse,
    NotificationPreferenceUpdateRequest,
)

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("/preferences", response_model=NotificationPreferenceResponse)
async def get_preferences(
    session: AsyncSession = Depends(get_session),
) -> NotificationPreferenceResponse:
    pref = await NotificationPreferenceRepository(session).get_or_create()
    return NotificationPreferenceResponse.model_validate(pref)


@router.put(
    "/preferences",
    response_model=NotificationPreferenceResponse,
    dependencies=[Depends(require_admin_key)],
)
async def update_preferences(
    body: NotificationPreferenceUpdateRequest,
    session: AsyncSession = Depends(get_session),
) -> NotificationPreferenceResponse:
    repo = NotificationPreferenceRepository(session)
    pref = await repo.get_or_create()
    pref.daily_summary_enabled = body.daily_summary_enabled
    pref.urgent_alert_enabled = body.urgent_alert_enabled
    pref.batch_failure_enabled = body.batch_failure_enabled
    pref.weekly_report_enabled = body.weekly_report_enabled
    pref.min_score = body.min_score
    pref.signal_types = list(body.signal_types)
    pref = await repo.save(pref)
    return NotificationPreferenceResponse.model_validate(pref)
