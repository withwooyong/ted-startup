"""엑셀 거래내역 import — parser + service + router 3계층 테스트.

실제 KIS 체결내역 엑셀 샘플을 확보하지 못한 상태라 fixture 를 openpyxl 로 직접
작성해 테스트. 컬럼 alias 가 실 파일과 어긋나면 `_COLUMN_ALIASES` 를 보정해야 함.
"""
from __future__ import annotations

import io
from collections.abc import AsyncIterator
from datetime import date
from decimal import Decimal

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI
from openpyxl import Workbook
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapter.out.persistence.models import BrokerageAccount, Stock
from app.adapter.out.persistence.repositories import (
    BrokerageAccountRepository,
    PortfolioTransactionRepository,
    StockRepository,
)
from app.adapter.web._deps import get_session as prod_get_session
from app.application.service.excel_import_service import (
    AccountNotFoundForImportError,
    ExcelImportService,
    ParsedTxRow,
    TooManyRowsError,
    UnsupportedExcelFormatError,
    parse_kis_transaction_xlsx,
)
from app.config.settings import get_settings
from app.main import create_app

# -----------------------------------------------------------------------------
# Fixture helpers
# -----------------------------------------------------------------------------


def _make_xlsx(
    *,
    columns: list[str],
    rows: list[list[object]],
    sheet_name: str = "체결내역",
) -> bytes:
    wb = Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = sheet_name
    ws.append(columns)
    for r in rows:
        ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


_KIS_COLUMNS = ["체결일자", "종목코드", "종목명", "매매구분", "체결수량", "체결단가"]


async def _seed_account(session: AsyncSession, alias: str = "excel-acc") -> BrokerageAccount:
    return await BrokerageAccountRepository(session).add(
        BrokerageAccount(
            account_alias=alias,
            broker_code="manual",
            connection_type="manual",
            environment="mock",
        )
    )


# -----------------------------------------------------------------------------
# Parser unit tests (외부 I/O 없이 바이트스트림만 왕복)
# -----------------------------------------------------------------------------


def test_parser_happy_path_returns_parsed_rows() -> None:
    xlsx = _make_xlsx(
        columns=_KIS_COLUMNS,
        rows=[
            ["2026-04-01", "005930", "삼성전자", "매수", 10, 72000],
            ["20260402", "000660", "SK하이닉스", "매도", 5, "150,000"],
        ],
    )
    rows, errors = parse_kis_transaction_xlsx(io.BytesIO(xlsx))
    assert errors == []
    assert len(rows) == 2
    r1, r2 = rows
    assert r1 == ParsedTxRow(
        executed_at=date(2026, 4, 1),
        stock_code="005930",
        stock_name="삼성전자",
        transaction_type="BUY",
        quantity=10,
        price=Decimal("72000.00"),
        row_number=2,
    )
    assert r2.transaction_type == "SELL"
    assert r2.price == Decimal("150000.00")  # 쉼표 포함 문자열 파싱
    assert r2.stock_code == "000660"


def test_parser_preserves_leading_zero_stock_code() -> None:
    # pandas 가 숫자로 읽어도 선행 0 을 복구 — KIS 구코드 "000000" 형태 대응
    xlsx = _make_xlsx(
        columns=_KIS_COLUMNS,
        rows=[["2026-04-01", 5930, "삼성전자(숫자입력)", "매수", 1, 100]],
    )
    rows, errors = parse_kis_transaction_xlsx(io.BytesIO(xlsx))
    assert errors == []
    assert rows[0].stock_code == "005930"


def test_parser_collects_per_row_errors_without_aborting() -> None:
    xlsx = _make_xlsx(
        columns=_KIS_COLUMNS,
        rows=[
            ["2026-04-01", "005930", "삼성전자", "매수", 10, 72000],  # OK
            ["2026-04-01", "005930", "삼성전자", "기타", 10, 72000],  # 매매구분 불명
            ["2026-04-01", "005930", "삼성전자", "매수", -5, 72000],  # 수량 음수
        ],
    )
    rows, errors = parse_kis_transaction_xlsx(io.BytesIO(xlsx))
    assert len(rows) == 1
    assert {e.row for e in errors} == {3, 4}
    assert "기타" in errors[0].reason


def test_parser_raises_on_missing_required_column() -> None:
    xlsx = _make_xlsx(
        columns=["체결일자", "종목코드"],  # 필수 대부분 누락
        rows=[["2026-04-01", "005930"]],
    )
    with pytest.raises(UnsupportedExcelFormatError, match="필수 컬럼 누락"):
        parse_kis_transaction_xlsx(io.BytesIO(xlsx))


def test_parser_accepts_column_aliases() -> None:
    # 다른 alias 조합 — KIS 섹션별 차이 대응
    xlsx = _make_xlsx(
        columns=["거래일자", "상품번호", "상품명", "거래구분", "거래수량", "거래단가"],
        rows=[["2026-04-01", "005930", "삼성전자", "매도", 3, 70000]],
    )
    rows, errors = parse_kis_transaction_xlsx(io.BytesIO(xlsx))
    assert errors == []
    assert rows[0].transaction_type == "SELL"


# -----------------------------------------------------------------------------
# Service integration tests (testcontainers DB 왕복)
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_service_imports_and_creates_missing_stock(session: AsyncSession) -> None:
    account = await _seed_account(session)
    # 삼성전자만 사전 등록 — SK하이닉스는 service 가 자동 생성해야 함
    samsung = await StockRepository(session).add(
        Stock(stock_code="005930", stock_name="삼성전자", market_type="KOSPI")
    )
    xlsx = _make_xlsx(
        columns=_KIS_COLUMNS,
        rows=[
            ["2026-04-01", "005930", "삼성전자", "매수", 10, 72000],
            ["2026-04-02", "000660", "SK하이닉스", "매수", 5, 150000],
        ],
    )

    result = await ExcelImportService(session).import_from_xlsx(
        account_id=account.id, file_bytes=xlsx
    )
    assert result.total_rows == 2
    assert result.imported == 2
    assert result.skipped_duplicates == 0
    assert result.stock_created_count == 1  # SK하이닉스만 신규

    txs = await PortfolioTransactionRepository(session).list_by_account(account.id)
    assert len(txs) == 2
    assert {t.stock_id for t in txs} == {
        samsung.id,
        (await StockRepository(session).find_by_code("000660")).id,  # type: ignore[union-attr]
    }


@pytest.mark.asyncio
async def test_service_skips_duplicates_on_repeated_import(session: AsyncSession) -> None:
    account = await _seed_account(session)
    xlsx = _make_xlsx(
        columns=_KIS_COLUMNS,
        rows=[["2026-04-01", "005930", "삼성전자", "매수", 10, 72000]],
    )
    first = await ExcelImportService(session).import_from_xlsx(
        account_id=account.id, file_bytes=xlsx
    )
    assert first.imported == 1 and first.skipped_duplicates == 0

    # 동일 파일 재업로드 → 1건 duplicate
    second = await ExcelImportService(session).import_from_xlsx(
        account_id=account.id, file_bytes=xlsx
    )
    assert second.imported == 0
    assert second.skipped_duplicates == 1


@pytest.mark.asyncio
async def test_service_raises_when_account_missing(session: AsyncSession) -> None:
    xlsx = _make_xlsx(columns=_KIS_COLUMNS, rows=[])
    with pytest.raises(AccountNotFoundForImportError):
        await ExcelImportService(session).import_from_xlsx(
            account_id=99_999, file_bytes=xlsx
        )


@pytest.mark.asyncio
async def test_service_raises_on_too_many_rows(session: AsyncSession) -> None:
    account = await _seed_account(session, alias="big")
    # MAX_ROWS(10_000) + 1 로 구성
    rows = [
        ["2026-04-01", "005930", "삼성전자", "매수", 1, 1]
        for _ in range(10_001)
    ]
    xlsx = _make_xlsx(columns=_KIS_COLUMNS, rows=rows)
    with pytest.raises(TooManyRowsError):
        await ExcelImportService(session).import_from_xlsx(
            account_id=account.id, file_bytes=xlsx
        )


# -----------------------------------------------------------------------------
# Router tests (FastAPI dependency_overrides 로 세션 주입)
# -----------------------------------------------------------------------------


@pytest_asyncio.fixture
async def app_with_session(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[FastAPI]:
    monkeypatch.setenv("ADMIN_API_KEY", "test-admin-key")
    get_settings.cache_clear()
    app = create_app()

    async def _override() -> AsyncIterator[AsyncSession]:
        yield session

    app.dependency_overrides[prod_get_session] = _override
    try:
        yield app
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()


@pytest_asyncio.fixture
async def client(app_with_session: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app_with_session)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"X-API-Key": "test-admin-key"},
    ) as c:
        yield c


@pytest.mark.asyncio
async def test_router_happy_path(
    session: AsyncSession, client: httpx.AsyncClient
) -> None:
    account = await _seed_account(session, alias="router-acc")
    xlsx = _make_xlsx(
        columns=_KIS_COLUMNS,
        rows=[["2026-04-01", "005930", "삼성전자", "매수", 10, 72000]],
    )
    resp = await client.post(
        f"/api/portfolio/accounts/{account.id}/import/excel",
        files={
            "file": (
                "trades.xlsx",
                xlsx,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["imported"] == 1
    assert body["skipped_duplicates"] == 0
    assert body["stock_created_count"] == 1


@pytest.mark.asyncio
async def test_router_rejects_non_xlsx_extension(
    session: AsyncSession, client: httpx.AsyncClient
) -> None:
    account = await _seed_account(session, alias="router-acc2")
    resp = await client.post(
        f"/api/portfolio/accounts/{account.id}/import/excel",
        files={"file": ("trades.csv", b"a,b,c", "text/csv")},
    )
    assert resp.status_code == 415
    assert "xlsx" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_router_returns_422_on_missing_columns(
    session: AsyncSession, client: httpx.AsyncClient
) -> None:
    account = await _seed_account(session, alias="router-acc3")
    xlsx = _make_xlsx(
        columns=["체결일자", "종목코드"],  # 필수 대부분 누락
        rows=[["2026-04-01", "005930"]],
    )
    resp = await client.post(
        f"/api/portfolio/accounts/{account.id}/import/excel",
        files={"file": ("bad.xlsx", xlsx, "application/octet-stream")},
    )
    assert resp.status_code == 422
    assert "필수 컬럼" in resp.json()["detail"]
