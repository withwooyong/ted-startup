"""backfill_short summary label 회귀 (Phase F-3 D-6 / H-R2-1).

기존: label `alphanumeric_skipped:` (DTO field `total_skipped` 참조 — label-field mismatch)
변경: label `total_skipped:` (DTO field 와 일치)

설계 근거:
- 기존 backfill_short.py 라인 189: `f"alphanumeric_skipped:{result.total_skipped}"`
- field 명은 `total_skipped` 인데 label 이 `alphanumeric_skipped:` 로 표기 — 혼란 유발
- Phase F-3 에서 label 을 `total_skipped:` 로 통일 (DTO field 명 그대로)
- KOSCOM cross-check 파이프라인이 label 을 파싱하므로 변경 회귀 탐지 필수

본 테스트는 구현 전 의도적으로 실패 (red) — Step 1 구현 후 green 전환 대상.
현재 backfill_short.py 라인 189 에 `alphanumeric_skipped:` 가 남아 있어 assert 실패.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock

import pytest

from app.application.dto.short_selling import ShortSellingBulkResult

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_short_result(
    *,
    total_stocks: int = 10,
    total_skipped: int = 5,
    total_failed: int = 0,
) -> ShortSellingBulkResult:
    """summary label 검증용 ShortSellingBulkResult fixture."""
    return ShortSellingBulkResult(
        total_stocks=total_stocks,
        total_skipped=total_skipped,
    )


# ---------------------------------------------------------------------------
# summary label 회귀
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_summary_uses_total_skipped_label(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """summary 출력에 'total_skipped:' 라벨 등장. 'alphanumeric_skipped:' 0건.

    Phase F-3 H-R2-1: backfill_short.py 라인 189 label 변경.
    기존: `f"alphanumeric_skipped:{result.total_skipped}"`
    신규: `f"total_skipped:  {result.total_skipped}"`

    현재 구현이 'alphanumeric_skipped:' 를 출력 → assert 실패 = red.
    Step 1 에서 label 변경 후 green.
    """
    from scripts.backfill_short import async_main

    mock_result = _make_short_result(total_skipped=5, total_failed=0)
    mock_use_case = AsyncMock()
    mock_use_case.execute = AsyncMock(return_value=mock_result)

    @asynccontextmanager
    async def _mock_builder(*, alias: str):  # type: ignore[misc]
        yield mock_use_case

    monkeypatch.setattr("scripts.backfill_short._build_use_case", _mock_builder)

    await async_main(["--start", "2025-01-01", "--end", "2025-01-02", "--alias", "test"])

    captured = capsys.readouterr()
    # 신규 label 이 있어야 함
    assert "total_skipped:" in captured.out, (
        f"summary 에 'total_skipped:' 라벨 없음.\n실제 stdout:\n{captured.out}"
    )
    # 기존 label 은 사라져야 함 (label-field mismatch 제거)
    assert "alphanumeric_skipped:" not in captured.out, (
        f"'alphanumeric_skipped:' 라벨이 아직 남아 있음.\n실제 stdout:\n{captured.out}"
    )


@pytest.mark.asyncio
async def test_summary_total_skipped_value_shown(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """summary 출력에 total_skipped 값(5) 이 포함되는지 검증.

    label 변경과 함께 값도 올바르게 출력되어야 한다.
    """
    from scripts.backfill_short import async_main

    mock_result = _make_short_result(total_skipped=5, total_failed=0)
    mock_use_case = AsyncMock()
    mock_use_case.execute = AsyncMock(return_value=mock_result)

    @asynccontextmanager
    async def _mock_builder(*, alias: str):  # type: ignore[misc]
        yield mock_use_case

    monkeypatch.setattr("scripts.backfill_short._build_use_case", _mock_builder)

    await async_main(["--start", "2025-01-01", "--end", "2025-01-02", "--alias", "test"])

    captured = capsys.readouterr()
    assert "5" in captured.out, (
        f"total_skipped 값(5) 이 stdout 에 없음.\n실제 stdout:\n{captured.out}"
    )


@pytest.mark.asyncio
async def test_summary_exit_code_zero_when_no_failure(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """total_failed=0 → exit code 0 검증 (exit code 정책 유지 회귀).

    label 변경이 exit code 로직에 영향을 주지 않아야 한다.
    """
    from scripts.backfill_short import async_main

    mock_result = _make_short_result(total_skipped=3, total_failed=0)
    mock_use_case = AsyncMock()
    mock_use_case.execute = AsyncMock(return_value=mock_result)

    @asynccontextmanager
    async def _mock_builder(*, alias: str):  # type: ignore[misc]
        yield mock_use_case

    monkeypatch.setattr("scripts.backfill_short._build_use_case", _mock_builder)

    rc = await async_main(["--start", "2025-01-01", "--end", "2025-01-02", "--alias", "test"])

    assert rc == 0, f"total_failed=0 → exit code 0 기대, 실제={rc}"
