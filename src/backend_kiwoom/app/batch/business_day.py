"""KST 영업일 helper — cron 발화 시점에서 직전 영업일 결정.

phase-c-cron-shift-to-morning § 3.3 — cron 시간을 NXT 마감 (20:00) 후 다음 영업일 새벽 06:00
으로 이동한 결과, 발화 시점의 `date.today()` 가 그날 거래 시작 전 (06:00 < 09:00 정규시장 개장)
이라 빈 응답 발생. fire_*_job 이 `execute(base_date=previous_kst_business_day(today))` 명시 전달.

공휴일 (mon-fri 안의 공휴일) 무시 — 키움 API 빈 응답 → success 0 / UPSERT idempotent →
운영 영향 0. sentinel 빈 row fix (72dbe69) 가 자연 처리. 공휴일 추적은 별도 chunk.
"""

from __future__ import annotations

from datetime import date, timedelta


def previous_kst_business_day(today: date) -> date:
    """직전 KST 영업일 (mon-fri) 을 반환.

    요일별 분기:
    - Monday   → today - 3d (last Friday)
    - Saturday → today - 1d (Friday — Weekly cron sat 발화용)
    - Sunday   → today - 2d (Friday — 안전망)
    - Tue~Fri  → today - 1d (전일)

    공휴일 무시 — 캘린더 외부 의존성 0. 빈 응답은 sentinel break + UPSERT idempotent 로 처리.
    """
    weekday = today.weekday()  # Mon=0, Tue=1, ..., Sat=5, Sun=6
    if weekday == 0:  # Monday
        return today - timedelta(days=3)
    if weekday == 6:  # Sunday — 안전망
        return today - timedelta(days=2)
    return today - timedelta(days=1)
