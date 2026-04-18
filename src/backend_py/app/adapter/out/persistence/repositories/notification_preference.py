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
            # server_default(예: updated_at NOW()) 값을 파이썬 측에 반영
            await self._session.refresh(pref)
        return pref

    async def save(self, pref: NotificationPreference) -> NotificationPreference:
        self._session.add(pref)
        await self._session.flush()
        # onupdate=func.now() 로 갱신된 updated_at 을 파이썬 속성에 동기화.
        # 이 단계가 없으면 이후 Pydantic model_validate 중 MissingGreenlet 발생.
        await self._session.refresh(pref)
        return pref
