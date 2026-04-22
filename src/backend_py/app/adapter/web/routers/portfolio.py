"""/api/portfolio/* — 계좌·보유·거래·성과."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import asdict
from datetime import date

from dateutil.relativedelta import relativedelta
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapter.out.external import KisClient, KisCredentials
from app.adapter.out.persistence.repositories import (
    BrokerageAccountCredentialRepository,
    BrokerageAccountRepository,
    PortfolioHoldingRepository,
    PortfolioSnapshotRepository,
    PortfolioTransactionRepository,
    StockRepository,
)
from app.adapter.web._deps import (
    get_credential_cipher,
    get_kis_client,
    get_kis_real_client_factory,
    get_session,
    require_admin_key,
)
from app.adapter.web._schemas import (
    AccountCreateRequest,
    AccountResponse,
    BrokerageCredentialRequest,
    BrokerageCredentialResponse,
    ExcelImportResponse,
    ExcelImportRowError,
    HoldingResponse,
    PerformanceResponse,
    SignalAlignmentResponse,
    SnapshotResponse,
    SyncResponse,
    TestConnectionResponse,
    TransactionCreateRequest,
    TransactionResponse,
)
from app.application.dto.credential import MaskedCredentialView
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
    BrokerageCredentialUseCase,
    ComputePerformanceUseCase,
    ComputeSnapshotUseCase,
    CredentialAlreadyExistsError,
    CredentialNotFoundError,
    CredentialRejectedError,
    InsufficientHoldingError,
    InvalidRealEnvironmentError,
    PortfolioError,
    RecordTransactionUseCase,
    RegisterAccountUseCase,
    SignalAlignmentUseCase,
    StockNotFoundError,
    SyncError,
    SyncPortfolioFromKisMockUseCase,
    SyncPortfolioFromKisRealUseCase,
    TestKisConnectionUseCase,
    TransactionRecord,
    UnsupportedConnectionError,
)
from app.security.credential_cipher import CredentialCipher, CredentialCipherError

logger = logging.getLogger(__name__)

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
    record = await ComputeSnapshotUseCase(session).execute(account_id=account_id, snapshot_date=snapshot_date)
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

    report = await ComputePerformanceUseCase(session).execute(account_id=account_id, start=start_d, end=end_d)
    return PerformanceResponse.model_validate(asdict(report))


@router.post(
    "/accounts/{account_id}/sync",
    response_model=SyncResponse,
)
async def sync_from_kis(
    account_id: int,
    session: AsyncSession = Depends(get_session),
    kis: KisClient = Depends(get_kis_client),
    cipher: CredentialCipher = Depends(get_credential_cipher),
    real_client_factory: Callable[[KisCredentials], KisClient] = Depends(get_kis_real_client_factory),
) -> SyncResponse:
    """KIS 잔고 동기화 — mock·real 2환경 동일 엔드포인트.

    계좌 `connection_type` 으로 분기해 **타입이 다른 두 UseCase** 중 하나를 실행:
      - kis_rest_mock → `SyncPortfolioFromKisMockUseCase` (kis_client 필수)
      - kis_rest_real → `SyncPortfolioFromKisRealUseCase` (credential_repo + factory 필수)
    credential 미등록 시 404, KIS 토큰 발급/잔고조회 실패 시 502.

    2026-04-22: 기존 단일 UseCase Optional 파라미터 퇴화 → mock/real 전용 UseCase 2개로 분리.
    """
    # connection_type 판별을 위해 account 선로드 — UseCase 내부에서도 재검증하므로 race 안전.
    account = await BrokerageAccountRepository(session).get(account_id)
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"account_id={account_id} 없음",
        )

    try:
        if account.connection_type == "kis_rest_mock":
            result = await SyncPortfolioFromKisMockUseCase(session, kis_client=kis).execute(account_id=account_id)
        elif account.connection_type == "kis_rest_real":
            credential_repo = BrokerageAccountCredentialRepository(session, cipher)
            result = await SyncPortfolioFromKisRealUseCase(
                session,
                credential_repo=credential_repo,
                real_client_factory=real_client_factory,
            ).execute(account_id=account_id)
        else:
            raise UnsupportedConnectionError(f"connection_type={account.connection_type} 는 동기화 비지원")
    except PortfolioError as exc:
        raise _credential_error_to_http(exc) from exc
    except CredentialCipherError as exc:
        raise _cipher_failure_as_http(account_id, exc) from exc
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
        result = await ExcelImportService(session).import_from_xlsx(account_id=account_id, file_bytes=payload)
    except AccountNotFoundForImportError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except UnsupportedExcelFormatError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except TooManyRowsError as exc:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=str(exc)) from exc
    except ExcelImportError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return ExcelImportResponse(
        account_id=account_id,
        total_rows=result.total_rows,
        imported=result.imported,
        skipped_duplicates=result.skipped_duplicates,
        stock_created_count=result.stock_created_count,
        errors=[ExcelImportRowError(row=e.row, reason=e.reason) for e in result.errors],
    )


# ---------- KIS 연결 테스트 (PR 5 — 3단계 온보딩 1단계) ----------


@router.post(
    "/accounts/{account_id}/test-connection",
    response_model=TestConnectionResponse,
)
async def test_kis_connection(
    account_id: int,
    session: AsyncSession = Depends(get_session),
    cipher: CredentialCipher = Depends(get_credential_cipher),
    real_client_factory: Callable[[KisCredentials], KisClient] = Depends(get_kis_real_client_factory),
) -> TestConnectionResponse:
    """실 KIS 자격증명으로 OAuth 토큰 발급만 시도하는 dry-run.

    잔고 조회 API 는 호출하지 않아 계좌 상태에 영향 0. 자격증명 등록 직후 "정말
    연결되는가" 검증용. 성공 시 200 `ok=true`, credential 미등록 404, KIS 업스트림
    실패 502, 계좌 설정 오류(비 `kis_rest_real`·non-real) 400/403.
    """
    uc = TestKisConnectionUseCase(session, cipher=cipher, real_client_factory=real_client_factory)
    try:
        result = await uc.execute(account_id=account_id)
    except PortfolioError as exc:
        raise _credential_error_to_http(exc) from exc
    except CredentialCipherError as exc:
        raise _cipher_failure_as_http(account_id, exc) from exc
    return TestConnectionResponse.model_validate(asdict(result))


# ---------- Brokerage Credentials (P15 / KIS sync PR 4 — 2단계 온보딩) ----------


def _credential_response(view: MaskedCredentialView) -> BrokerageCredentialResponse:
    """UseCase DTO → API 응답 매핑. `_Base(from_attributes=True)` 가 dataclass 읽기 지원."""
    return BrokerageCredentialResponse.model_validate(view)


def _credential_error_to_http(exc: PortfolioError) -> HTTPException:
    """credential·sync·연결테스트 도메인 예외 → HTTP 매핑 공통 처리.

    호출자는 반드시 반환된 `HTTPException` 을 `raise` 해야 한다. 함수 자체는 raise 하지
    않으며, mypy `no-implicit-optional` 로 반환값 누락은 컴파일 타임에 탐지된다.
    """
    if isinstance(exc, AccountNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, UnsupportedConnectionError):
        return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    if isinstance(exc, InvalidRealEnvironmentError):
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    if isinstance(exc, CredentialAlreadyExistsError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    if isinstance(exc, CredentialNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, CredentialRejectedError):
        # KIS 가 HTTP 401/403 으로 자격증명을 명시 거부 — 사용자가 Settings 에서
        # 재등록해야 해결. 업스트림 장애(502) 와 구분해 4xx 로 매핑.
        return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    if isinstance(exc, SyncError):
        # KIS 업스트림(토큰 발급/잔고 조회) 실패 — 업스트림 게이트웨이 오류.
        return HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


def _cipher_failure_as_http(account_id: int, exc: CredentialCipherError) -> HTTPException:
    """Fernet 복호화/키 버전 오류 → 500 으로 변환 + 운영 로그에 예외 타입만 남김.

    `DecryptionFailedError` / `UnknownKeyVersionError` 는 `PortfolioError` 계열이 아니라
    router 의 `except PortfolioError` 에서 잡히지 않고 FastAPI 기본 500 으로 전파된다.
    사용자 응답에는 내부 스택트레이스·메시지를 노출하지 않고, 로그에만 예외 타입 + account_id
    만 기록해 운영팀이 키 회전 상태를 점검할 수 있게 한다.
    """
    logger.error(
        "Credential cipher failure: account_id=%s exc_type=%s",
        account_id,
        type(exc).__name__,
    )
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="자격증명 복호화 실패 — 운영자에게 문의하세요",
    )


@router.post(
    "/accounts/{account_id}/credentials",
    response_model=BrokerageCredentialResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_credential(
    account_id: int,
    body: BrokerageCredentialRequest,
    session: AsyncSession = Depends(get_session),
    cipher: CredentialCipher = Depends(get_credential_cipher),
) -> BrokerageCredentialResponse:
    """실계정 자격증명 신규 등록. 이미 있으면 409 — 교체는 PUT 사용."""
    uc = BrokerageCredentialUseCase(session, cipher)
    try:
        view = await uc.create(
            account_id=account_id,
            credentials=KisCredentials(
                app_key=body.app_key,
                app_secret=body.app_secret,
                account_no=body.account_no,
            ),
        )
    except PortfolioError as exc:
        raise _credential_error_to_http(exc) from exc
    except CredentialCipherError as exc:
        raise _cipher_failure_as_http(account_id, exc) from exc
    return _credential_response(view)


@router.put(
    "/accounts/{account_id}/credentials",
    response_model=BrokerageCredentialResponse,
)
async def replace_credential(
    account_id: int,
    body: BrokerageCredentialRequest,
    session: AsyncSession = Depends(get_session),
    cipher: CredentialCipher = Depends(get_credential_cipher),
) -> BrokerageCredentialResponse:
    """기존 자격증명 교체. 존재하지 않으면 404 — 신규는 POST 사용."""
    uc = BrokerageCredentialUseCase(session, cipher)
    try:
        view = await uc.replace(
            account_id=account_id,
            credentials=KisCredentials(
                app_key=body.app_key,
                app_secret=body.app_secret,
                account_no=body.account_no,
            ),
        )
    except PortfolioError as exc:
        raise _credential_error_to_http(exc) from exc
    except CredentialCipherError as exc:
        raise _cipher_failure_as_http(account_id, exc) from exc
    return _credential_response(view)


@router.get(
    "/accounts/{account_id}/credentials",
    response_model=BrokerageCredentialResponse,
)
async def get_credential(
    account_id: int,
    session: AsyncSession = Depends(get_session),
    cipher: CredentialCipher = Depends(get_credential_cipher),
) -> BrokerageCredentialResponse:
    """마스킹된 자격증명 뷰. `app_secret` 은 어떤 경로로도 반환되지 않음."""
    uc = BrokerageCredentialUseCase(session, cipher)
    try:
        view = await uc.get_masked(account_id)
    except PortfolioError as exc:
        raise _credential_error_to_http(exc) from exc
    except CredentialCipherError as exc:
        raise _cipher_failure_as_http(account_id, exc) from exc
    return _credential_response(view)


@router.delete(
    "/accounts/{account_id}/credentials",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_credential(
    account_id: int,
    session: AsyncSession = Depends(get_session),
    cipher: CredentialCipher = Depends(get_credential_cipher),
) -> None:
    """자격증명 명시 삭제. 계좌는 유지, credential 레코드만 제거."""
    uc = BrokerageCredentialUseCase(session, cipher)
    try:
        await uc.delete(account_id)
    except PortfolioError as exc:
        raise _credential_error_to_http(exc) from exc
