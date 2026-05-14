"""DTO layer 공유 enum / 상수 (Phase F-3 D-1).

SkipReason — F-1/F-2 매직 스트링 → enum (R2 inherit § 46.8 #2).
"""
from __future__ import annotations

from enum import StrEnum


class SkipReason(StrEnum):
    """bulk loop / pre-filter 의 skip 사유 분류 (Phase F-3 D-2).

    값은 기존 매직 스트링 그대로 — 외부 시스템 (KOSCOM cross-check / log 분석)
    영향 0. StrEnum 이라 `outcome.error: str` 그대로 비교 호환.
    """

    ALPHANUMERIC_PRE_FILTER = "alphanumeric_pre_filter"
    """alphanumeric pre-filter 단계에서 제거 (CLI filter_alphanumeric=True 경로)."""

    SENTINEL_SKIP = "sentinel_skip"
    """bulk loop 안에서 SentinelStockCodeError catch (adapter 가드 발화)."""


__all__ = ["SkipReason"]
