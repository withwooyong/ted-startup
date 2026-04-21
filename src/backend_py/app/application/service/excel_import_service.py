"""엑셀 거래내역 import — KIS 홈페이지 체결내역 xlsx 포맷 MVP.

파서 + 서비스 두 책임을 한 모듈에 묶어 외부 의존(pandas+openpyxl)과 도메인
(PortfolioTransaction) 사이 접착 코드를 단일 파일로 유지.

설계 문서: docs/kis-real-account-sync-plan.md (§ 5 PR 1)
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import IO, Any

import pandas as pd
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapter.out.persistence.models import (
    PortfolioTransaction,
)
from app.adapter.out.persistence.repositories import (
    BrokerageAccountRepository,
    PortfolioTransactionRepository,
    StockRepository,
)

logger = structlog.get_logger(__name__)

MAX_ROWS = 10_000
DEFAULT_MARKET_TYPE = "KOSPI"


# ---------------------------------------------------------------------------
# DTO
# ---------------------------------------------------------------------------


@dataclass(slots=True, frozen=True)
class ParsedTxRow:
    executed_at: date
    stock_code: str
    stock_name: str
    transaction_type: str  # "BUY" | "SELL"
    quantity: int
    price: Decimal
    row_number: int  # 엑셀 원본 1-index (헤더 제외)


@dataclass(slots=True, frozen=True)
class RowError:
    row: int
    reason: str


@dataclass(slots=True)
class ImportResult:
    total_rows: int
    imported: int
    skipped_duplicates: int
    stock_created_count: int
    errors: list[RowError]


class ExcelImportError(Exception):
    """파서·서비스 공통 최상위 예외."""


class UnsupportedExcelFormatError(ExcelImportError):
    """필수 컬럼이 누락됐거나 포맷을 인식할 수 없음."""


class TooManyRowsError(ExcelImportError):
    pass


class AccountNotFoundForImportError(ExcelImportError):
    pass


# ---------------------------------------------------------------------------
# Parser — 컬럼 alias 매칭 + 값 정규화
# ---------------------------------------------------------------------------

# KIS 체결내역 엑셀은 버전·섹션 별로 미묘하게 다른 컬럼명을 사용. 실 파일 샘플이
# 확보되지 않은 상태라 알려진 보편 후보를 alias 로 받아 유연하게 매칭.
_COLUMN_ALIASES: dict[str, tuple[str, ...]] = {
    "executed_at": ("체결일자", "거래일자", "거래일", "주문일자", "일자"),
    "stock_code": ("종목코드", "종목번호", "상품번호", "코드"),
    "stock_name": ("종목명", "상품명"),
    "transaction_type": ("매매구분", "거래구분", "구분", "주문구분"),
    "quantity": ("체결수량", "거래수량", "수량", "주문수량"),
    "price": ("체결단가", "거래단가", "단가", "주문단가", "체결가"),
}

_BUY_LABELS = {"매수", "현금매수", "신용매수", "BUY", "buy"}
_SELL_LABELS = {"매도", "현금매도", "신용매도", "SELL", "sell"}


def _resolve_columns(df_columns: list[str]) -> dict[str, str]:
    """엑셀의 실제 컬럼명 집합에서 alias 매칭으로 표준 키를 찾는다.

    Returns:
        {standard_key: actual_column_name} — 필수 키가 누락되면 UnsupportedExcelFormatError.
    """
    normalized = {str(c).strip(): str(c) for c in df_columns}
    resolved: dict[str, str] = {}
    missing: list[str] = []
    for std_key, aliases in _COLUMN_ALIASES.items():
        for alias in aliases:
            if alias in normalized:
                resolved[std_key] = normalized[alias]
                break
        else:
            missing.append(std_key)
    if missing:
        raise UnsupportedExcelFormatError(f"필수 컬럼 누락: {missing}. 지원 alias: {dict(_COLUMN_ALIASES)}")
    return resolved


def _parse_date(val: Any) -> date:
    if isinstance(val, date):
        return val
    if isinstance(val, pd.Timestamp):
        return val.date()
    s = str(val).strip().replace("-", "").replace("/", "").replace(".", "")
    if len(s) != 8 or not s.isdigit():
        raise ValueError(f"날짜 포맷 인식 불가: {val!r}")
    return date(int(s[:4]), int(s[4:6]), int(s[6:8]))


def _parse_code(val: Any) -> str:
    # 선행 0 보존 — pandas 가 숫자로 읽어들이는 케이스 방어
    if isinstance(val, float) and not pd.isna(val):
        val = int(val)
    s = str(val).strip()
    if not s:
        raise ValueError("종목코드 비어있음")
    # 숫자 6자리 미만이면 zfill
    if s.isdigit():
        return s.zfill(6)
    return s


def _parse_tx_type(val: Any) -> str:
    s = str(val).strip()
    if s in _BUY_LABELS:
        return "BUY"
    if s in _SELL_LABELS:
        return "SELL"
    raise ValueError(f"매매구분 '{s}' 지원 안 함")


def _parse_int(val: Any) -> int:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        raise ValueError("수량 비어있음")
    s = str(val).strip().replace(",", "")
    if not s:
        raise ValueError("수량 비어있음")
    n = int(Decimal(s))
    if n <= 0:
        raise ValueError(f"수량은 양수여야 함: {n}")
    return n


def _parse_price(val: Any) -> Decimal:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        raise ValueError("단가 비어있음")
    s = str(val).strip().replace(",", "")
    if not s:
        raise ValueError("단가 비어있음")
    try:
        d = Decimal(s).quantize(Decimal("0.01"))
    except InvalidOperation as exc:
        raise ValueError(f"단가 파싱 실패: {val!r}") from exc
    if d < 0:
        raise ValueError(f"단가는 0 이상이어야 함: {d}")
    return d


def parse_kis_transaction_xlsx(
    stream: IO[bytes],
) -> tuple[list[ParsedTxRow], list[RowError]]:
    """xlsx 바이너리 스트림 → 파싱된 행 + 행별 오류 리스트.

    라이브러리 제약:
    - `pandas.read_excel(engine='openpyxl')` 사용. openpyxl `read_only=True` 는
      pandas 3.x 에서 자동 설정되어 zip bomb 위험 완화.
    - 파일 포맷 자체 에러(시트 없음 등) 는 `UnsupportedExcelFormatError` 로 래핑.
    """
    try:
        df = pd.read_excel(stream, engine="openpyxl", dtype=str)
    except Exception as exc:  # openpyxl 의 다양한 내부 예외 flat 처리
        raise UnsupportedExcelFormatError(f"엑셀 파일을 읽을 수 없음: {exc}") from exc

    if df.empty:
        return [], []
    if len(df) > MAX_ROWS:
        raise TooManyRowsError(f"행 수가 한계({MAX_ROWS}) 초과: {len(df)}")

    col = _resolve_columns(list(df.columns))
    rows: list[ParsedTxRow] = []
    errors: list[RowError] = []

    for pos, (_, raw) in enumerate(df.iterrows(), start=2):  # pandas 0-index + 헤더 1줄
        try:
            rows.append(
                ParsedTxRow(
                    executed_at=_parse_date(raw[col["executed_at"]]),
                    stock_code=_parse_code(raw[col["stock_code"]]),
                    stock_name=str(raw[col["stock_name"]]).strip(),
                    transaction_type=_parse_tx_type(raw[col["transaction_type"]]),
                    quantity=_parse_int(raw[col["quantity"]]),
                    price=_parse_price(raw[col["price"]]),
                    row_number=pos,
                )
            )
        except (ValueError, TypeError, KeyError) as exc:
            errors.append(RowError(row=pos, reason=str(exc)))
    return rows, errors


# ---------------------------------------------------------------------------
# Service — stock 자동 생성 + 중복 스킵 + 벌크 insert
# ---------------------------------------------------------------------------


class ExcelImportService:
    """Application service — 파서 출력을 domain 으로 변환·저장.

    중복 판단 기준: `(account_id, stock_id, executed_at, transaction_type,
    quantity, price)` 완전 일치. 같은 날 동일 종목·수량·단가 거래는 합쳐질 수
    있으나 MVP 허용.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._account_repo = BrokerageAccountRepository(session)
        self._stock_repo = StockRepository(session)
        self._tx_repo = PortfolioTransactionRepository(session)

    async def import_from_xlsx(self, *, account_id: int, file_bytes: bytes) -> ImportResult:
        account = await self._account_repo.get(account_id)
        if account is None:
            raise AccountNotFoundForImportError(f"account_id={account_id} 없음")

        parsed_rows, parse_errors = parse_kis_transaction_xlsx(io.BytesIO(file_bytes))
        total = len(parsed_rows) + len(parse_errors)
        imported = 0
        duplicates = 0
        stock_created = 0
        errors: list[RowError] = list(parse_errors)

        for row in parsed_rows:
            try:
                stock = await self._stock_repo.find_by_code(row.stock_code)
                if stock is None:
                    stock = await self._stock_repo.upsert_by_code(
                        stock_code=row.stock_code,
                        stock_name=row.stock_name or row.stock_code,
                        market_type=DEFAULT_MARKET_TYPE,
                    )
                    stock_created += 1

                if await self._is_duplicate(
                    account_id=account_id,
                    stock_id=stock.id,
                    executed_at=row.executed_at,
                    transaction_type=row.transaction_type,
                    quantity=row.quantity,
                    price=row.price,
                ):
                    duplicates += 1
                    continue

                tx = PortfolioTransaction(
                    account_id=account_id,
                    stock_id=stock.id,
                    transaction_type=row.transaction_type,
                    quantity=row.quantity,
                    price=row.price,
                    executed_at=row.executed_at,
                    source="excel_import",
                    memo=None,
                )
                await self._tx_repo.add(tx)
                imported += 1
            except (ValueError, TypeError) as exc:
                # 순수 데이터 문제 (예: price quantize 실패) 는 해당 행만 스킵.
                # SQLAlchemyError 는 세션이 오염되므로 잡지 않고 request 레벨에서 롤백 유도.
                logger.warning(
                    "엑셀 import row 데이터 오류",
                    row=row.row_number,
                    reason=str(exc),
                )
                errors.append(RowError(row=row.row_number, reason=str(exc)))

        return ImportResult(
            total_rows=total,
            imported=imported,
            skipped_duplicates=duplicates,
            stock_created_count=stock_created,
            errors=errors,
        )

    async def _is_duplicate(
        self,
        *,
        account_id: int,
        stock_id: int,
        executed_at: date,
        transaction_type: str,
        quantity: int,
        price: Decimal,
    ) -> bool:
        stmt = select(PortfolioTransaction.id).where(
            PortfolioTransaction.account_id == account_id,
            PortfolioTransaction.stock_id == stock_id,
            PortfolioTransaction.executed_at == executed_at,
            PortfolioTransaction.transaction_type == transaction_type,
            PortfolioTransaction.quantity == quantity,
            PortfolioTransaction.price == price,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none() is not None
