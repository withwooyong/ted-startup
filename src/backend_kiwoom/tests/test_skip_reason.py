"""SkipReason enum 값 안정성 회귀 (Phase F-3 D-2).

외부 시스템 (KOSCOM cross-check / log 분석) 이 매직 스트링 그대로 의존하므로
SkipReason.*.value 가 기존 string 과 정확히 일치해야 한다.

본 테스트는 구현 전 의도적으로 실패 (red) — Step 1 에서 _shared.py 생성 후 green 전환 대상.
"""

from app.application.dto._shared import SkipReason  # type: ignore[import]  # Step 1 에서 생성


def test_skip_reason_alphanumeric_pre_filter_value_stable() -> None:
    """SkipReason.ALPHANUMERIC_PRE_FILTER.value = "alphanumeric_pre_filter" 고정.

    외부 시스템 log 분석이 이 값에 의존 — 변경 시 cross-check 파이프라인 파손.
    """
    assert SkipReason.ALPHANUMERIC_PRE_FILTER.value == "alphanumeric_pre_filter"


def test_skip_reason_sentinel_skip_value_stable() -> None:
    """SkipReason.SENTINEL_SKIP.value = "sentinel_skip" 고정.

    외부 시스템 log 분석이 이 값에 의존 — 변경 시 cross-check 파이프라인 파손.
    """
    assert SkipReason.SENTINEL_SKIP.value == "sentinel_skip"


def test_skip_reason_is_str_enum() -> None:
    """StrEnum 이라 string 비교 호환 — outcome.error: str 그대로 비교 가능.

    StrEnum 을 사용하므로 SkipReason.SENTINEL_SKIP == "sentinel_skip" 은 True.
    outcome.error 타입을 str 로 유지한 채 enum 상수와 직접 비교 가능.
    """
    assert SkipReason.SENTINEL_SKIP == "sentinel_skip"
    assert SkipReason.ALPHANUMERIC_PRE_FILTER == "alphanumeric_pre_filter"


def test_skip_reason_members_count_stable() -> None:
    """Phase F-3 도입 시점 2 members. 추후 확장 시 본 회귀가 detect.

    신규 SkipReason 값을 추가할 때 이 테스트가 실패하여 의도적 확장임을 명시하도록 요구.
    """
    assert len(list(SkipReason)) == 2
