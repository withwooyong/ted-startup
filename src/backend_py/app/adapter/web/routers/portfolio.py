"""/api/portfolio/* — 계좌·보유·거래·성과."""
from __future__ import annotations

from dataclasses import asdict
from datetime import date

from dateutil.relativedelta import relativedelta
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapter.out.external import KisClient
from app.adapter.out.persistence.repositories import (
    BrokerageAccountRepository,
    PortfolioHoldingRepository,
    PortfolioSnapshotRepository,
    PortfolioTransactionRepository,
    StockRepository,
)
from app.adapter.web._deps import get_kis_client, get_session, require_admin_key
from app.adapter.web._schemas import (
    AccountCreateRequest,
    AccountResponse,
    ExcelImportResponse,
    ExcelImportRowError,
    HoldingResponse,
    PerformanceResponse,
    SignalAlignmentResponse,
    SnapshotResponse,
    SyncResponse,
    TransactionCreateRequest,
    TransactionResponse,
)
from app.application.service.excel_import_service import (
    AccountNotFoundForImportError,
    ExcelImportError,
    ExcelImportService,
    TooManyRowsError,
    UnsupportedExcelFormatError,
)
from app.application.service.portfolio_service import (
    AccountAliasConflictError,
    AccountNotFoundError,
    ComputePerformanceUseCase,
    ComputeSnapshotUseCase,
    InsufficientHoldingError,
    InvalidRealEnvironmentError,
    PortfolioError,
    RecordTransactionUseCase,
    RegisterAccountUseCase,
    SignalAlignmentUseCase,
    StockNotFoundError,
    SyncError,
    SyncPortfolioFromKisUseCase,
    TransactionRecord,
    UnsupportedConnectionError,
)

router = APIRouter(
    prefix="/api/portfolio",
    tags=["portfolio"],
    dependencies=[Depends(require_admin_key)],
)


# ---------- Accounts ----------


@router.post("/accounts", response_model=AccountResponse, status_code=status.HTTP_201_CREATED)
async def create_account(
    body: AccountCreateRequest,
    session: AsyncSession = Depends(get_session),
) -> AccountResponse:
    try:
        account = await RegisterAccountUseCase(session).execute(
            account_alias=body.account_alias,
            broker_code=body.broker_code,
            connection_type=body.connection_type,
            environment=body.environment,
        )
    except AccountAliasConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except InvalidRealEnvironmentError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except PortfolioError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return AccountResponse.model_validate(account)


@router.get("/accounts", response_model=list[AccountResponse])
async def list_accounts(
    session: AsyncSession = Depends(get_session),
) -> list[AccountResponse]:
    accounts = await BrokerageAccountRepository(session).list_active()
    return [AccountResponse.model_validate(a) for a in accounts]


# ---------- Holdings / Transactions ----------


@router.post(
    "/accounts/{account_id}/transactions",
    response_model=TransactionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def record_transaction(
    account_id: int,
    body: TransactionCreateRequest,
    session: AsyncSession = Depends(get_session),
) -> TransactionResponse:
    stock = await StockRepository(session).find_by_code(body.stock_code)
    if stock is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"종목 없음: {body.stock_code}")

    try:
        tx = await RecordTransactionUseCase(session).execute(
            TransactionRecord(
                account_id=account_id,
                stock_id=stock.id,
                transaction_type=body.transaction_type,
                quantity=body.quantity,
                price=body.price,
                executed_at=body.executed_at,
                source="manual",
                memo=body.memo,
            )
        )
    except AccountNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except StockNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except InsufficientHoldingError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except PortfolioError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return TransactionResponse.model_validate(tx)


@router.get(
    "/accounts/{account_id}/holdings",
    response_model=list[HoldingResponse],
)
async def list_holdings(
    account_id: int,
    session: AsyncSession = Depends(get_session),
) -> list[HoldingResponse]:
    account = await BrokerageAccountRepository(session).get(account_id)
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="계좌 없음")

    holdings = await PortfolioHoldingRepository(session).list_by_account(account_id)
    if not holdings:
        return []
    stocks = await StockRepository(session).list_by_ids([h.stock_id for h in holdings])
    stock_map = {s.id: s for s in stocks}
    out: list[HoldingResponse] = []
    for h in holdings:
        s = stock_map.get(h.stock_id)
        out.append(
            HoldingResponse(
                account_id=h.account_id,
                stock_id=h.stock_id,
                stock_code=s.stock_code if s else None,
                stock_name=s.stock_name if s else None,
                quantity=h.quantity,
                avg_buy_price=h.avg_buy_price,
                first_bought_at=h.first_bought_at,
                last_transacted_at=h.last_transacted_at,
            )
        )
    return out


@router.get(
    "/accounts/{account_id}/transactions",
    response_model=list[TransactionResponse],
)
async def list_transactions(
    account_id: int,
    limit: int = 100,
    session: AsyncSession = Depends(get_session),
) -> list[TransactionResponse]:
    account = await BrokerageAccountRepository(session).get(account_id)
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="계좌 없음")
    limit = max(1, min(limit, 500))
    txs = await PortfolioTransactionRepository(session).list_by_account(account_id, limit=limit)
    return [TransactionResponse.model_validate(t) for t in txs]


# ---------- Snapshot / Performance ----------


@router.post(
    "/accounts/{account_id}/snapshot",
    response_model=SnapshotResponse,
)
async def create_snapshot(
    account_id: int,
    asof: date | None = None,
    session: AsyncSession = Depends(get_session),
) -> SnapshotResponse:
    account = await BrokerageAccountRepository(session).get(account_id)
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="계좌 없음")
    snapshot_date = asof or date.today()
    record = await ComputeSnapshotUseCase(session).execute(
        account_id=account_id, snapshot_date=snapshot_date
    )
    return SnapshotResponse.model_validate(asdict(record))


@router.get(
    "/accounts/{account_id}/performance",
    response_model=PerformanceResponse,
)
async def get_performance(
    account_id: int,
    start: date | None = None,
    end: date | None = None,
    session: AsyncSession = Depends(get_session),
) -> PerformanceResponse:
    account = await BrokerageAccountRepository(session).get(account_id)
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="계좌 없음")

    today = date.today()
    end_d = end or today
    start_d = start or (end_d - relativedelta(months=3))
    if start_d > end_d:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="start 는 end 보다 미래일 수 없습니다")

    report = await ComputePerformanceUseCase(session).execute(
        account_id=account_id, start=start_d, end=end_d
    )
    return PerformanceResponse.model_validate(asdict(report))


@router.post(
    "/accounts/{account_id}/sync",
    response_model=SyncResponse,
)
async def sync_from_kis(
    account_id: int,
    session: AsyncSession = Depends(get_session),
    kis: KisClient = Depends(get_kis_client),
) -> SyncResponse:
    try:
        result = await SyncPortfolioFromKisUseCase(session, kis_client=kis).execute(
            account_id=account_id
        )
    except AccountNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except UnsupportedConnectionError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except InvalidRealEnvironmentError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except SyncError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    except PortfolioError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return SyncResponse.model_validate(asdict(result))


@router.get(
    "/accounts/{account_id}/signal-alignment",
    response_model=SignalAlignmentResponse,
)
async def get_signal_alignment(
    account_id: int,
    since: date | None = None,
    until: date | None = None,
    min_score: int = 60,
    session: AsyncSession = Depends(get_session),
) -> SignalAlignmentResponse:
    if not 0 <= min_score <= 100:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="min_score 는 0~100")
    today = date.today()
    end_d = until or today
    start_d = since or (end_d - relativedelta(days=30))
    try:
        report = await SignalAlignmentUseCase(session).execute(
            account_id=account_id, since=start_d, until=end_d, min_score=min_score
        )
    except AccountNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except PortfolioError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return SignalAlignmentResponse.model_validate(asdict(report))


@router.get(
    "/accounts/{account_id}/snapshots",
    response_model=list[SnapshotResponse],
)
async def list_snapshots(
    account_id: int,
    start: date | None = None,
    end: date | None = None,
    session: AsyncSession = Depends(get_session),
) -> list[SnapshotResponse]:
    account = await BrokerageAccountRepository(session).get(account_id)
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="계좌 없음")
    today = date.today()
    end_d = end or today
    start_d = start or (end_d - relativedelta(months=3))
    rows = await PortfolioSnapshotRepository(session).list_between(account_id, start_d, end_d)
    return [SnapshotResponse.model_validate(r) for r in rows]


# ---------- Excel Import (P10 온보딩 1단계) ----------

MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10MB — 설계서 § 4 검증 기준


@router.post(
    "/accounts/{account_id}/import/excel",
    response_model=ExcelImportResponse,
    status_code=status.HTTP_200_OK,
)
async def import_transactions_from_excel(
    account_id: int,
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
) -> ExcelImportResponse:
    """KIS 체결내역 엑셀(.xlsx) 업로드 → portfolio_transaction 에 `source='excel_import'` 로 적재.

    - 파일 확장자 `.xlsx` 만 허용 → 415
    - 파일 크기 > 10MB → 413
    - 행 수 > 10_000 → 413 (TooManyRowsError 경유)
    - 필수 컬럼 누락 → 422
    - 중복 행 (account·stock·date·type·qty·price) 은 skip, 응답에 카운트만 반영
    """
    filename = (file.filename or "").lower()
    if not filename.endswith(".xlsx"):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="xlsx 파일만 지원합니다.",
        )
    payload = await file.read()
    if len(payload) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"파일 크기가 한계({MAX_UPLOAD_BYTES} bytes)를 초과합니다.",
        )

    try:
        result = await ExcelImportService(session).import_from_xlsx(
            account_id=account_id, file_bytes=payload
        )
    except AccountNotFoundForImportError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except UnsupportedExcelFormatError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    except TooManyRowsError as exc:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=str(exc)
        ) from exc
    except ExcelImportError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc

    return ExcelImportResponse(
        account_id=account_id,
        total_rows=result.total_rows,
        imported=result.imported,
        skipped_duplicates=result.skipped_duplicates,
        stock_created_count=result.stock_created_count,
        errors=[ExcelImportRowError(row=e.row, reason=e.reason) for e in result.errors],
    )
