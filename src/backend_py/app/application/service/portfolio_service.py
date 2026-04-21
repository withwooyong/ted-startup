"""포트폴리오 도메인 UseCase.

- RegisterAccountUseCase: 계좌 생성(alias 기준 idempotent).
- RecordTransactionUseCase: 매수/매도 거래 기록 + portfolio_holding 가중평균 갱신.
- ComputeSnapshotUseCase: 현재 보유 + 최신 시세로 일별 평가 스냅샷 산출·저장.
- ComputePerformanceUseCase: 기간 스냅샷 → 수익률/MDD/샤프(기본 252영업일·무위험=0).

수동 등록(P10)과 KIS 동기화(P11)는 모두 `RecordTransactionUseCase` 뒤에 얹힌다.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

import numpy as np
import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapter.out.external import (
    KisClient,
    KisClientError,
    KisCredentials,
    KisHoldingRow,
)
from app.adapter.out.persistence.models import (
    BrokerageAccount,
    PortfolioHolding,
    PortfolioSnapshot,
    PortfolioTransaction,
    Signal,
    Stock,
)
from app.adapter.out.persistence.models.portfolio import (
    VALID_BROKER_CODES,
    VALID_CONNECTION_TYPES,
    VALID_ENVIRONMENTS,
    VALID_SOURCES,
    VALID_TRANSACTION_TYPES,
)
from app.adapter.out.persistence.repositories import (
    BrokerageAccountCredentialRepository,
    BrokerageAccountRepository,
    PortfolioHoldingRepository,
    PortfolioSnapshotRepository,
    PortfolioTransactionRepository,
    SignalRepository,
    StockPriceRepository,
    StockRepository,
)
from app.adapter.out.persistence.repositories.brokerage_credential import (
    MaskedCredentialView as MaskedCredentialView,  # explicit re-export
)
from app.security.credential_cipher import CredentialCipher

logger = logging.getLogger(__name__)


# ---------- Errors ----------


class PortfolioError(Exception):
    """포트폴리오 도메인 공통 예외."""


class AccountAliasConflictError(PortfolioError):
    pass


class AccountNotFoundError(PortfolioError):
    pass


class StockNotFoundError(PortfolioError):
    pass


class InsufficientHoldingError(PortfolioError):
    pass


class InvalidRealEnvironmentError(PortfolioError):
    """connection_type 과 environment 매칭 위반 (예: kis_rest_real 인데 environment='mock')."""


class UnsupportedConnectionError(PortfolioError):
    """연결방식이 동기화를 지원하지 않을 때."""


class SyncError(PortfolioError):
    """외부 API 동기화 중 오류(업스트림 장애 포함)."""


class CredentialAlreadyExistsError(PortfolioError):
    """해당 계좌에 이미 credential 이 등록돼 있음. POST → 409 로 매핑."""


class CredentialNotFoundError(PortfolioError):
    """해당 계좌에 credential 이 없음. PUT·GET·DELETE·sync·test-connection → 404 로 매핑."""


# ---------- Type aliases ----------


# 실 KIS 호출용 KisClient 팩토리 — credential 을 받아 REAL 환경 인스턴스를 생성.
# 각 요청마다 새 클라이언트를 만들어야 한다 (계좌마다 credential 이 다르므로).
# 테스트는 dependency_override 로 MockTransport 주입한 factory 로 치환.
KisRealClientFactory = Callable[[KisCredentials], KisClient]


# ---------- DTOs ----------


@dataclass(slots=True)
class TransactionRecord:
    account_id: int
    stock_id: int
    transaction_type: str  # BUY | SELL
    quantity: int
    price: Decimal
    executed_at: date
    source: str  # manual | kis_sync
    memo: str | None = None


@dataclass(slots=True)
class SnapshotRecord:
    account_id: int
    snapshot_date: date
    total_value: Decimal
    total_cost: Decimal
    unrealized_pnl: Decimal
    realized_pnl: Decimal
    holdings_count: int


@dataclass(slots=True)
class PerformanceReport:
    account_id: int
    start_date: date
    end_date: date
    samples: int
    total_return_pct: Decimal | None
    max_drawdown_pct: Decimal | None
    sharpe_ratio: Decimal | None
    first_value: Decimal | None
    last_value: Decimal | None


@dataclass(slots=True)
class SyncResult:
    account_id: int
    connection_type: str
    fetched_count: int  # KIS 응답 보유 종목 수
    created_count: int  # 새로 보유로 추가된 종목 수
    updated_count: int  # 기존 보유 수량/평단가 갱신된 종목 수
    unchanged_count: int  # 변경 없음
    stock_created_count: int  # 신규 stock 마스터 upsert 수


@dataclass(slots=True)
class TestConnectionResult:
    """실 KIS 연결 테스트 결과 — OAuth 토큰 발급 성공 여부."""

    account_id: int
    environment: str
    ok: bool


@dataclass(slots=True)
class AlignedSignal:
    signal_date: date
    signal_type: str
    score: int
    grade: str


@dataclass(slots=True)
class AlignedHolding:
    stock_id: int
    stock_code: str
    stock_name: str
    quantity: int
    avg_buy_price: Decimal
    max_score: int
    hit_count: int
    signals: list[AlignedSignal]


@dataclass(slots=True)
class SignalAlignmentReport:
    account_id: int
    since: date
    until: date
    min_score: int
    total_holdings: int
    aligned_holdings: int
    items: list[AlignedHolding]


# ---------- Shared helpers ----------


async def _ensure_kis_real_account(account_repo: BrokerageAccountRepository, account_id: int) -> BrokerageAccount:
    """credential 등록·조회·연결테스트·실 sync 공통 전처리.

    계좌 존재 + `connection_type='kis_rest_real'` + `environment='real'` 보장.
    각 조건마다 명확한 도메인 예외로 구분해 router 에서 HTTP 의미론을 맞출 수 있게.
    """
    account = await account_repo.get(account_id)
    if account is None:
        raise AccountNotFoundError(f"account_id={account_id} 없음")
    if account.connection_type != "kis_rest_real":
        raise UnsupportedConnectionError(
            f"실계정 전용 기능 — connection_type='kis_rest_real' 필요 (현재 {account.connection_type})"
        )
    if account.environment != "real":
        raise InvalidRealEnvironmentError("kis_rest_real 계좌는 environment='real' 필수")
    return account


# ---------- UseCases ----------


class RegisterAccountUseCase:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = BrokerageAccountRepository(session)

    async def execute(
        self,
        *,
        account_alias: str,
        broker_code: str,
        connection_type: str,
        environment: str = "mock",
    ) -> BrokerageAccount:
        if broker_code not in VALID_BROKER_CODES:
            raise PortfolioError(f"broker_code 불가: {broker_code}")
        if connection_type not in VALID_CONNECTION_TYPES:
            raise PortfolioError(f"connection_type 불가: {connection_type}")
        if environment not in VALID_ENVIRONMENTS:
            raise PortfolioError(f"environment 불가: {environment}")

        # connection_type × environment 조합 검증 — 운영 실수 방지.
        # kis_rest_real 은 오직 environment='real' 과만, 나머지는 'mock' 과만 짝지어야 함.
        if connection_type == "kis_rest_real" and environment != "real":
            raise InvalidRealEnvironmentError("kis_rest_real 계좌는 environment='real' 필수")
        if connection_type != "kis_rest_real" and environment == "real":
            raise InvalidRealEnvironmentError("environment='real' 은 connection_type='kis_rest_real' 에서만 허용")

        existing = await self._repo.find_by_alias(account_alias)
        if existing is not None:
            raise AccountAliasConflictError(f"이미 존재하는 계좌 별칭: {account_alias}")

        account = BrokerageAccount(
            account_alias=account_alias,
            broker_code=broker_code,
            connection_type=connection_type,
            environment=environment,
        )
        return await self._repo.add(account)


class RecordTransactionUseCase:
    """매수/매도 거래 기록 + portfolio_holding 가중평균 갱신.

    - BUY: new_qty = qty + buy_qty / new_avg = (qty*avg + buy_qty*buy_price) / new_qty
    - SELL: new_qty = qty - sell_qty (0 이상 보장) / avg 는 불변
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._account_repo = BrokerageAccountRepository(session)
        self._holding_repo = PortfolioHoldingRepository(session)
        self._tx_repo = PortfolioTransactionRepository(session)
        self._stock_repo = StockRepository(session)

    async def execute(self, record: TransactionRecord) -> PortfolioTransaction:
        if record.transaction_type not in VALID_TRANSACTION_TYPES:
            raise PortfolioError(f"transaction_type 불가: {record.transaction_type}")
        if record.source not in VALID_SOURCES:
            raise PortfolioError(f"source 불가: {record.source}")
        if record.quantity <= 0:
            raise PortfolioError("quantity 는 양수여야 함")

        account = await self._account_repo.get(record.account_id)
        if account is None:
            raise AccountNotFoundError(f"account_id={record.account_id} 없음")
        stock = await self._stock_repo.get(record.stock_id)
        if stock is None:
            raise StockNotFoundError(f"stock_id={record.stock_id} 없음")

        tx = await self._tx_repo.add(
            PortfolioTransaction(
                account_id=record.account_id,
                stock_id=record.stock_id,
                transaction_type=record.transaction_type,
                quantity=record.quantity,
                price=record.price,
                executed_at=record.executed_at,
                source=record.source,
                memo=record.memo,
            )
        )
        await self._apply_holding(record)
        return tx

    async def _apply_holding(self, record: TransactionRecord) -> None:
        holding = await self._holding_repo.find_by_account_and_stock(record.account_id, record.stock_id)
        qty_delta = record.quantity if record.transaction_type == "BUY" else -record.quantity

        if holding is None:
            if record.transaction_type == "SELL":
                raise InsufficientHoldingError("보유 없음 상태에서 SELL 불가")
            holding = PortfolioHolding(
                account_id=record.account_id,
                stock_id=record.stock_id,
                quantity=record.quantity,
                avg_buy_price=record.price,
                first_bought_at=record.executed_at,
                last_transacted_at=record.executed_at,
            )
            await self._holding_repo.upsert(holding)
            return

        new_qty = holding.quantity + qty_delta
        if new_qty < 0:
            raise InsufficientHoldingError(f"잔고 부족: 보유 {holding.quantity} vs 매도 {record.quantity}")
        if record.transaction_type == "BUY":
            # 가중평균 평단가 갱신
            prev_cost = Decimal(holding.quantity) * holding.avg_buy_price
            add_cost = Decimal(record.quantity) * record.price
            holding.avg_buy_price = ((prev_cost + add_cost) / Decimal(new_qty)).quantize(Decimal("0.01"))
        holding.quantity = new_qty
        holding.last_transacted_at = record.executed_at
        await self._holding_repo.upsert(holding)


class ComputeSnapshotUseCase:
    """지정 일자 기준 포트폴리오 평가 스냅샷 생성.

    - 현재 holding.quantity > 0 대상만 반영.
    - close_price 는 snapshot_date 이전/당일 가장 최근 값 사용(휴일 대비).
    - realized_pnl 은 기간 내 SELL 거래의 (sell_price - avg_buy_price) * qty 합산.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._holding_repo = PortfolioHoldingRepository(session)
        self._price_repo = StockPriceRepository(session)
        self._snapshot_repo = PortfolioSnapshotRepository(session)
        self._tx_repo = PortfolioTransactionRepository(session)

    async def execute(self, *, account_id: int, snapshot_date: date) -> SnapshotRecord:
        holdings = await self._holding_repo.list_by_account(account_id, only_active=True)
        total_value = Decimal("0")
        total_cost = Decimal("0")
        holdings_count = 0
        for h in holdings:
            price = await self._latest_close(h.stock_id, snapshot_date)
            if price is None:
                logger.warning(
                    "스냅샷 skip: 시세 부재 account=%d stock=%d asof=%s",
                    account_id,
                    h.stock_id,
                    snapshot_date,
                )
                continue
            value = Decimal(h.quantity) * price
            cost = Decimal(h.quantity) * h.avg_buy_price
            total_value += value
            total_cost += cost
            holdings_count += 1

        realized_pnl = await self._realized_pnl_to_date(account_id, snapshot_date)
        unrealized = (total_value - total_cost).quantize(Decimal("0.01"))

        record = SnapshotRecord(
            account_id=account_id,
            snapshot_date=snapshot_date,
            total_value=total_value.quantize(Decimal("0.01")),
            total_cost=total_cost.quantize(Decimal("0.01")),
            unrealized_pnl=unrealized,
            realized_pnl=realized_pnl,
            holdings_count=holdings_count,
        )
        await self._snapshot_repo.upsert(
            PortfolioSnapshot(
                account_id=record.account_id,
                snapshot_date=record.snapshot_date,
                total_value=record.total_value,
                total_cost=record.total_cost,
                unrealized_pnl=record.unrealized_pnl,
                realized_pnl=record.realized_pnl,
                holdings_count=record.holdings_count,
            )
        )
        return record

    async def _latest_close(self, stock_id: int, asof: date) -> Decimal | None:
        # 최근 30 영업일 이내에서 마지막 종가 (휴일·갭 커버)
        window_start = asof.replace(day=1)  # 간단히 월초부터; 부족하면 호출 측에서 조정
        rows = await self._price_repo.list_between(stock_id, window_start, asof)
        if not rows:
            return None
        latest = rows[-1]
        return Decimal(latest.close_price)

    async def _realized_pnl_to_date(self, account_id: int, asof: date) -> Decimal:
        """SELL 거래의 누적 실현손익 (sell_price - 현 avg_buy_price) * qty 근사.

        MVP: 현재 holding 의 avg 와 대조. 역사적 정확도(매도 시점의 avg) 는
        P13 리포트 단계에서 보강.
        """
        txs = await self._tx_repo.list_by_account(account_id, limit=10_000)
        holdings_map: dict[int, Decimal] = {}  # stock_id → 현 avg
        holding_rows = await self._holding_repo.list_by_account(account_id, only_active=False)
        for h in holding_rows:
            holdings_map[h.stock_id] = h.avg_buy_price

        realized = Decimal("0")
        for tx in txs:
            if tx.transaction_type != "SELL" or tx.executed_at > asof:
                continue
            avg = holdings_map.get(tx.stock_id, tx.price)
            realized += (tx.price - avg) * Decimal(tx.quantity)
        return realized.quantize(Decimal("0.01"))


class ComputePerformanceUseCase:
    """기간 스냅샷 시퀀스 → 수익률·MDD·샤프."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._snapshot_repo = PortfolioSnapshotRepository(session)

    async def execute(self, *, account_id: int, start: date, end: date) -> PerformanceReport:
        snaps = await self._snapshot_repo.list_between(account_id, start, end)
        if len(snaps) < 2:
            return PerformanceReport(
                account_id=account_id,
                start_date=start,
                end_date=end,
                samples=len(snaps),
                total_return_pct=None,
                max_drawdown_pct=None,
                sharpe_ratio=None,
                first_value=snaps[0].total_value if snaps else None,
                last_value=snaps[-1].total_value if snaps else None,
            )

        values = pd.Series(
            [float(s.total_value) for s in snaps],
            index=pd.DatetimeIndex([s.snapshot_date for s in snaps]),
            dtype="float64",
        )
        first, last = values.iloc[0], values.iloc[-1]
        total_return = (last / first - 1.0) * 100.0 if first > 0 else None

        running_max = values.cummax()
        drawdowns = (values - running_max) / running_max
        max_dd = float(drawdowns.min()) * 100.0 if not drawdowns.empty else None

        daily_returns = values.pct_change().dropna()
        if len(daily_returns) >= 2 and daily_returns.std(ddof=0) > 0:
            sharpe = (daily_returns.mean() / daily_returns.std(ddof=0)) * np.sqrt(252)
        else:
            sharpe = None

        def _q(val: float | None) -> Decimal | None:
            if val is None or pd.isna(val):
                return None
            return Decimal(str(round(val, 4)))

        return PerformanceReport(
            account_id=account_id,
            start_date=start,
            end_date=end,
            samples=len(snaps),
            total_return_pct=_q(total_return),
            max_drawdown_pct=_q(max_dd),
            sharpe_ratio=_q(float(sharpe) if sharpe is not None else None),
            first_value=Decimal(str(first)),
            last_value=Decimal(str(last)),
        )


class SignalAlignmentUseCase:
    """보유 종목 × 기간 시그널 교차 리포트.

    - 보유는 quantity > 0 인 holding 만 대상
    - 시그널은 min_score 이상 + (since ≤ signal_date ≤ until)
    - N+1 회피: stock_id IN (...) 단일 쿼리로 시그널 일괄 조회
    - 정렬: 종목별 max_score desc, 동률이면 hit_count desc
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._account_repo = BrokerageAccountRepository(session)
        self._holding_repo = PortfolioHoldingRepository(session)
        self._stock_repo = StockRepository(session)
        self._signal_repo = SignalRepository(session)

    async def execute(
        self,
        *,
        account_id: int,
        since: date,
        until: date,
        min_score: int = 60,
    ) -> SignalAlignmentReport:
        account = await self._account_repo.get(account_id)
        if account is None:
            raise AccountNotFoundError(f"account_id={account_id} 없음")
        if since > until:
            raise PortfolioError("since 는 until 보다 미래일 수 없습니다")

        holdings = await self._holding_repo.list_by_account(account_id, only_active=True)
        total = len(holdings)
        if not holdings:
            return SignalAlignmentReport(
                account_id=account_id,
                since=since,
                until=until,
                min_score=min_score,
                total_holdings=0,
                aligned_holdings=0,
                items=[],
            )

        stock_ids = [h.stock_id for h in holdings]
        stocks = await self._stock_repo.list_by_ids(stock_ids)
        stock_map: dict[int, Stock] = {s.id: s for s in stocks}

        signals = await self._signal_repo.list_by_stocks_between(stock_ids, since, until, min_score=min_score)
        # stock_id → [Signal...] 버킷
        bucket: dict[int, list[Signal]] = {}
        for sig in signals:
            bucket.setdefault(sig.stock_id, []).append(sig)

        items: list[AlignedHolding] = []
        for h in holdings:
            sigs = bucket.get(h.stock_id, [])
            if not sigs:
                continue
            s = stock_map.get(h.stock_id)
            items.append(
                AlignedHolding(
                    stock_id=h.stock_id,
                    stock_code=s.stock_code if s else "",
                    stock_name=s.stock_name if s else "",
                    quantity=h.quantity,
                    avg_buy_price=h.avg_buy_price,
                    max_score=max(sig.score for sig in sigs),
                    hit_count=len(sigs),
                    signals=[
                        AlignedSignal(
                            signal_date=sig.signal_date,
                            signal_type=sig.signal_type,
                            score=sig.score,
                            grade=sig.grade,
                        )
                        for sig in sigs
                    ],
                )
            )
        items.sort(key=lambda x: (x.max_score, x.hit_count), reverse=True)

        return SignalAlignmentReport(
            account_id=account_id,
            since=since,
            until=until,
            min_score=min_score,
            total_holdings=total,
            aligned_holdings=len(items),
            items=items,
        )


class SyncPortfolioFromKisUseCase:
    """KIS 잔고 → portfolio_holding 직접 동기화. mock + real 2 환경 지원.

    - connection_type='kis_rest_mock': 주입된 프로세스 공유 `kis_client` 사용 (MOCK).
    - connection_type='kis_rest_real': credential_repo 에서 Fernet 복호화 →
      real_client_factory 로 요청 스코프 KisClient(REAL) 생성 → async with 로 fetch_balance.
    - KIS 잔고 응답은 종목별 (수량, 평단가) 스냅샷 → 거래 이력 재구성 불가.
      따라서 holding 을 직접 upsert: 수량/평단가를 KIS 값으로 덮어쓰기.
    - 신규 종목은 stock 마스터에 KOSPI 기본값으로 등록 (실제 시장 구분은 DART 후속 보강).
    """

    DEFAULT_MARKET_TYPE = "KOSPI"  # KIS 는 시장구분을 반환하지 않음 — 기본값

    def __init__(
        self,
        session: AsyncSession,
        *,
        kis_client: KisClient | None = None,
        credential_repo: BrokerageAccountCredentialRepository | None = None,
        real_client_factory: KisRealClientFactory | None = None,
    ) -> None:
        self._session = session
        self._kis = kis_client
        self._credential_repo = credential_repo
        self._real_client_factory = real_client_factory
        self._account_repo = BrokerageAccountRepository(session)
        self._holding_repo = PortfolioHoldingRepository(session)
        self._stock_repo = StockRepository(session)

    async def execute(self, *, account_id: int, asof: date | None = None) -> SyncResult:
        account = await self._account_repo.get(account_id)
        if account is None:
            raise AccountNotFoundError(f"account_id={account_id} 없음")
        if account.connection_type not in ("kis_rest_mock", "kis_rest_real"):
            raise UnsupportedConnectionError(f"connection_type={account.connection_type} 는 동기화 비지원")

        # connection_type × environment 조합 검증을 분기 진입 전에 수행. 공통 규칙은
        # `_ensure_kis_real_account` 와 `_fetch_balance_mock` 에 집중돼 있고, execute
        # 에서는 호출만 위임 — 검증 책임이 여러 곳에 퍼지는 것을 방지.
        if account.connection_type == "kis_rest_real":
            await _ensure_kis_real_account(self._account_repo, account_id)
            rows = await self._fetch_balance_real(account_id)
        else:  # kis_rest_mock
            rows = await self._fetch_balance_mock(account.environment)

        today = asof or date.today()
        created = 0
        updated = 0
        unchanged = 0
        stock_created = 0

        for row in rows:
            if not row.stock_code:
                continue
            stock = await self._stock_repo.find_by_code(row.stock_code)
            if stock is None:
                stock = await self._stock_repo.upsert_by_code(
                    stock_code=row.stock_code,
                    stock_name=row.stock_name or row.stock_code,
                    market_type=self.DEFAULT_MARKET_TYPE,
                )
                stock_created += 1

            holding = await self._holding_repo.find_by_account_and_stock(account_id, stock.id)
            if holding is None:
                holding = PortfolioHolding(
                    account_id=account_id,
                    stock_id=stock.id,
                    quantity=row.quantity,
                    avg_buy_price=row.avg_buy_price,
                    first_bought_at=today,
                    last_transacted_at=today,
                )
                await self._holding_repo.upsert(holding)
                created += 1
                continue

            qty_changed = holding.quantity != row.quantity
            price_changed = holding.avg_buy_price != row.avg_buy_price
            if not (qty_changed or price_changed):
                unchanged += 1
                continue
            holding.quantity = row.quantity
            holding.avg_buy_price = row.avg_buy_price
            holding.last_transacted_at = today
            await self._holding_repo.upsert(holding)
            updated += 1

        return SyncResult(
            account_id=account_id,
            connection_type=account.connection_type,
            fetched_count=len(rows),
            created_count=created,
            updated_count=updated,
            unchanged_count=unchanged,
            stock_created_count=stock_created,
        )

    async def _fetch_balance_real(self, account_id: int) -> list[KisHoldingRow]:
        """kis_rest_real 분기 — DB credential 복호화 후 요청 스코프 REAL 클라이언트로 호출.

        계좌 environment='real' 검증은 execute() 진입 시 `_ensure_kis_real_account` 가
        이미 수행 — 여기선 credential 조회·외부 호출에만 집중.
        """
        if self._credential_repo is None or self._real_client_factory is None:
            # 호출자가 REAL 경로용 DI 를 주입하지 않았음. 라우터/테스트 배선 오류.
            raise RuntimeError("kis_rest_real 동기화는 credential_repo + real_client_factory 주입 필수")
        credentials = await self._credential_repo.get_decrypted(account_id)
        if credentials is None:
            raise CredentialNotFoundError(f"account_id={account_id} credential 미등록 — Settings 에서 등록 후 재시도")
        try:
            async with self._real_client_factory(credentials) as client:
                return await client.fetch_balance()
        except KisClientError as exc:
            raise SyncError(f"KIS 실계좌 잔고 조회 실패: {exc}") from exc

    async def _fetch_balance_mock(self, environment: str) -> list[KisHoldingRow]:
        """kis_rest_mock 분기 — 주입된 프로세스 공유 MOCK 클라이언트 사용."""
        if environment != "mock":
            raise InvalidRealEnvironmentError("kis_rest_mock 계좌는 environment='mock' 필수")
        if self._kis is None:
            raise RuntimeError("kis_rest_mock 동기화는 kis_client 주입 필수")
        try:
            return await self._kis.fetch_balance()
        except KisClientError as exc:
            raise SyncError(f"KIS 잔고 조회 실패: {exc}") from exc


# ---------- PR 5: 연결 테스트 (3단계 온보딩 1단계) ----------


class TestKisConnectionUseCase:
    """실 KIS 연결 테스트 — OAuth 토큰 발급만 시도하는 dry-run.

    자격증명 등록 직후 "정말 연결되는가" 를 사용자가 잔고 변경 없이 확인할 수 있게 함.
    - 대상 계좌: `kis_rest_real` + `environment='real'` + credential 등록됨
    - 호출: `/oauth2/tokenP` 1회. 잔고 API 는 호출하지 않음
    - 실패: `SyncError` (KIS 토큰 발급 실패) 또는 `CredentialNotFoundError`

    pytest 가 "Test*" 접두로 시작하는 클래스를 자동 수집 대상으로 판단해 경고를 내므로
    `__test__ = False` 로 명시 — 이 클래스는 도메인 UseCase 지 pytest 테스트가 아님.
    """

    __test__ = False  # pytest collection 제외

    def __init__(
        self,
        session: AsyncSession,
        *,
        cipher: CredentialCipher,
        real_client_factory: KisRealClientFactory,
    ) -> None:
        self._session = session
        self._account_repo = BrokerageAccountRepository(session)
        self._cred_repo = BrokerageAccountCredentialRepository(session, cipher)
        self._factory = real_client_factory

    async def execute(self, *, account_id: int) -> TestConnectionResult:
        await _ensure_kis_real_account(self._account_repo, account_id)
        credentials = await self._cred_repo.get_decrypted(account_id)
        if credentials is None:
            raise CredentialNotFoundError(f"account_id={account_id} credential 미등록 — Settings 에서 등록 필요")
        try:
            async with self._factory(credentials) as client:
                await client.test_connection()
        except KisClientError as exc:
            # 토큰 발급 실패 = KIS 업스트림 오류. 라우터에서 502 로 변환.
            raise SyncError(f"KIS 토큰 발급 실패: {exc}") from exc
        return TestConnectionResult(account_id=account_id, environment="real", ok=True)


# ---------- P15 — KIS 실계정 자격증명 CRUD (2단계 온보딩) ----------


class BrokerageCredentialUseCase:
    """KIS 실계정 자격증명 CRUD — 외부 호출 0.

    - 대상 계좌는 반드시 `connection_type='kis_rest_real'` + `environment='real'`.
    - 저장 시 `BrokerageAccountCredentialRepository.upsert` 로 Fernet 암호화.
    - GET 응답은 `app_key`/`account_no` 의 tail 4자리만 마스킹 노출, `app_secret` 은
      어떤 경로로도 plaintext 반환하지 않는다.
    - 실 sync 연결(PR 5) 전까지는 credential 은 저장·마스킹·삭제만 수행.

    설계: docs/kis-real-account-sync-plan.md § 3.4 2단계 + § 5 PR 4.
    """

    def __init__(self, session: AsyncSession, cipher: CredentialCipher) -> None:
        self._session = session
        self._account_repo = BrokerageAccountRepository(session)
        self._cred_repo = BrokerageAccountCredentialRepository(session, cipher)

    async def create(self, *, account_id: int, credentials: KisCredentials) -> MaskedCredentialView:
        """신규 등록 — 이미 존재하면 `CredentialAlreadyExistsError`. POST 매핑."""
        await self._ensure_real_account(account_id)
        existing = await self._cred_repo.find_row(account_id)
        if existing is not None:
            raise CredentialAlreadyExistsError(
                f"account_id={account_id} 에 이미 credential 이 등록돼 있음 — PUT 으로 교체"
            )
        await self._cred_repo.upsert(account_id, credentials)
        return self._require_view(await self._cred_repo.get_masked_view(account_id), account_id)

    async def replace(self, *, account_id: int, credentials: KisCredentials) -> MaskedCredentialView:
        """기존 교체 — 존재하지 않으면 `CredentialNotFoundError`. PUT 매핑."""
        await self._ensure_real_account(account_id)
        existing = await self._cred_repo.find_row(account_id)
        if existing is None:
            raise CredentialNotFoundError(f"account_id={account_id} credential 미등록 — POST 로 생성")
        await self._cred_repo.upsert(account_id, credentials)
        return self._require_view(await self._cred_repo.get_masked_view(account_id), account_id)

    @staticmethod
    def _require_view(view: MaskedCredentialView | None, account_id: int) -> MaskedCredentialView:
        """`upsert` 직후 조회이므로 항상 존재해야 함.

        `assert` 는 `python -O` 에서 제거돼 프로덕션에서 silent None 반환 위험이 있으므로
        명시적 예외로 대체. 도달 불가 케이스(동시 DELETE 등)는 500 으로 loud fail.
        """
        if view is None:
            raise RuntimeError(
                f"account_id={account_id}: upsert 직후 get_masked_view 가 None — "
                "DB flush 타이밍 이상 또는 동시 DELETE 레이스 가능성"
            )
        return view

    async def get_masked(self, account_id: int) -> MaskedCredentialView:
        """마스킹 뷰 반환. 없으면 `CredentialNotFoundError`."""
        await self._ensure_real_account(account_id)
        view = await self._cred_repo.get_masked_view(account_id)
        if view is None:
            raise CredentialNotFoundError(f"account_id={account_id} credential 미등록")
        return view

    async def delete(self, account_id: int) -> None:
        """명시 삭제. 레코드 없으면 `CredentialNotFoundError`."""
        await self._ensure_real_account(account_id)
        deleted = await self._cred_repo.delete(account_id)
        if not deleted:
            raise CredentialNotFoundError(f"account_id={account_id} credential 미등록")

    async def _ensure_real_account(self, account_id: int) -> BrokerageAccount:
        """대상 계좌 존재 + `kis_rest_real` + `environment='real'` 보장.

        공통 헬퍼 `_ensure_kis_real_account` 에 위임해 `TestKisConnectionUseCase`·
        `SyncPortfolioFromKisUseCase` 와 검증 규칙을 1곳에서 관리.
        """
        return await _ensure_kis_real_account(self._account_repo, account_id)
