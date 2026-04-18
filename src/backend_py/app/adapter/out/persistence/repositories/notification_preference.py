from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.adapter.out.persistence.models import NotificationPreference


class NotificationPreferenceRepository:
    """싱글 로우(id=1) 규약. get_or_create 가 표준 진입점."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_or_create(self) -> NotificationPreference:
        pref = await self._session.get(NotificationPreference, NotificationPreference.SINGLETON_ID)
        if pref is None:
            pref = NotificationPreference(id=NotificationPreference.SINGLETON_ID)
            self._session.add(pref)
            await self._session.flush()
        return pref

    async def save(self, pref: NotificationPreference) -> NotificationPreference:
        self._session.add(pref)
        await self._session.flush()
        return pref
