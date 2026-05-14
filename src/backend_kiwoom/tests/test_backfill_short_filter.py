"""Phase F-2 TDD — backfill_short.py CLI filter_alphanumeric smoke test.

Red intent:
- UseCase.execute 가 filter_alphanumeric=True 를 받지 않음 → AssertionError
- summary stdout 에 alphanumeric_skipped 라인 없음 → AssertionError

설계: phase-f-2-backfill-alphanumeric-guard.md § 4 #7 + #8
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock

import pytest

from app.application.dto.short_selling import ShortSellingBulkResult

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_short_result(*, total_stocks: int = 10, total_skipped: int = 5, total_failed: int = 0) -> ShortSellingBulkResult:
    """Phase F-2 신규 필드 total_skipped 포함 fixture.

    Red intent: ShortSellingBulkResult 에 total_skipped 필드가 없으므로
    TypeError 로 실패 예정.
    """
    return ShortSellingBulkResult(
        total_stocks=total_stocks,
        total_skipped=total_skipped,  # F-2 신규 필드 — 현재 없음 → TypeError red
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_backfill_short_passes_filter_alphanumeric_true(capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    """CLI 가 UseCase.execute 에 filter_alphanumeric=True 를 전달하는지 검증.

    Red: filter_alphanumeric 파라미터 미전달 → call_kwargs 에 키 없음 → assert 실패.
    """
    from scripts.backfill_short import async_main

    mock_result = _make_short_result(total_skipped=5, total_failed=0)
    mock_use_case = AsyncMock()
    mock_use_case.execute = AsyncMock(return_value=mock_result)

    @asynccontextmanager
    async def _mock_builder(alias: str):  # type: ignore[misc]
        yield mock_use_case

    monkeypatch.setattr("scripts.backfill_short._build_use_case", _mock_builder)

    rc = await async_main(["--start", "2025-01-01", "--end", "2025-01-02", "--alias", "test"])

    assert rc == 0
    mock_use_case.execute.assert_called_once()
    call_kwargs = mock_use_case.execute.call_args.kwargs
    # Red: filter_alphanumeric 파라미터 현재 미전달 → KeyError/AssertionError
    assert call_kwargs.get("filter_alphanumeric") is True, (
        f"filter_alphanumeric=True 가 UseCase.execute 에 전달되지 않음. "
        f"실제 kwargs: {call_kwargs}"
    )


@pytest.mark.asyncio
async def test_backfill_short_summary_includes_total_skipped(capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    """CLI summary stdout 에 total_skipped: 5 라인이 포함되는지 검증.

    Phase F-3 D-6 (H-R2-1): label `alphanumeric_skipped:` → `total_skipped:` 통일
    (DTO field 명과 일치). 기존 F-2 테스트의 label 단언을 신규 label 로 갱신.
    """
    from scripts.backfill_short import async_main

    mock_result = _make_short_result(total_skipped=5, total_failed=0)
    mock_use_case = AsyncMock()
    mock_use_case.execute = AsyncMock(return_value=mock_result)

    @asynccontextmanager
    async def _mock_builder(alias: str):  # type: ignore[misc]
        yield mock_use_case

    monkeypatch.setattr("scripts.backfill_short._build_use_case", _mock_builder)

    await async_main(["--start", "2025-01-01", "--end", "2025-01-02", "--alias", "test"])

    captured = capsys.readouterr()
    assert "total_skipped" in captured.out, (
        f"summary 에 total_skipped 라인 없음.\n실제 stdout:\n{captured.out}"
    )
    assert "5" in captured.out, (
        f"total_skipped 값(5) 이 stdout 에 없음.\n실제 stdout:\n{captured.out}"
    )


@pytest.mark.asyncio
async def test_backfill_short_exit_code_zero_when_no_failure(capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    """total_failed=0 → exit code 0 검증 (§ 4 #9 — exit code 정책 유지)."""
    from scripts.backfill_short import async_main

    mock_result = _make_short_result(total_skipped=5, total_failed=0)
    mock_use_case = AsyncMock()
    mock_use_case.execute = AsyncMock(return_value=mock_result)

    @asynccontextmanager
    async def _mock_builder(alias: str):  # type: ignore[misc]
        yield mock_use_case

    monkeypatch.setattr("scripts.backfill_short._build_use_case", _mock_builder)

    rc = await async_main(["--start", "2025-01-01", "--end", "2025-01-02", "--alias", "test"])

    assert rc == 0
