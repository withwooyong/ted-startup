"""KiwoomStkInfoClient — `/api/dostk/stkinfo` 계열 어댑터.

설계: endpoint-14-ka10101.md § 6.1.

α chunk 범위: ka10101 (sector 마스터). ka10099 / ka10100 / ka10001 등은 Phase B.

책임:
- KiwoomClient(공통 트랜스포트) 위임 — 토큰 / 재시도 / rate-limit / 페이지네이션
- mrkt_tp 사전 검증 (5개 유효값) — 잘못된 값은 호출 자체 차단
- 응답 row 파싱 (Pydantic) → KiwoomResponseValidationError 매핑
- 페이지네이션 결과 합치기

camelCase 키 유지 (키움 응답 그대로) — 영속화 단계에서 snake_case 매핑.
"""

from __future__ import annotations

from typing import Annotated, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.adapter.out.kiwoom._client import KiwoomClient
from app.adapter.out.kiwoom._exceptions import KiwoomResponseValidationError

VALID_MRKT_TP: Final[tuple[str, ...]] = ("0", "1", "2", "4", "7")
"""ka10101 mrkt_tp 유효값 (master.md § 11.3 - 다른 endpoint 와 의미 다름).

0: 코스피(거래소) / 1: 코스닥 / 2: KOSPI200 / 4: KOSPI100 / 7: KRX100
"""


class SectorListRequest(BaseModel):
    """ka10101 요청 본문."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    mrkt_tp: Literal["0", "1", "2", "4", "7"]


class SectorRow(BaseModel):
    """업종 row — camelCase 유지 (키움 응답 그대로)."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    marketCode: str  # 요청한 mrkt_tp 에코  # noqa: N815 — 키움 응답 키 그대로
    code: Annotated[str, Field(min_length=1, max_length=10)]
    name: Annotated[str, Field(min_length=1, max_length=100)]
    group: str = ""


class SectorListResponse(BaseModel):
    """ka10101 응답 본문.

    `list` 필드명이 builtin `list` 를 가리므로 attribute 는 `items` 로 노출,
    JSON 키는 alias 로 `list` 유지 (`populate_by_name=True` 로 양방향 허용).
    """

    model_config = ConfigDict(frozen=True, extra="ignore", populate_by_name=True)

    items: list[SectorRow] = Field(default_factory=list, alias="list")
    return_code: int = 0
    return_msg: str = ""


class KiwoomStkInfoClient:
    """`/api/dostk/stkinfo` 어댑터. KiwoomClient 위임."""

    API_ID = "ka10101"
    PATH = "/api/dostk/stkinfo"

    def __init__(self, kiwoom_client: KiwoomClient) -> None:
        self._client = kiwoom_client

    async def fetch_sectors(self, mrkt_tp: Literal["0", "1", "2", "4", "7"]) -> SectorListResponse:
        """단일 시장의 업종 리스트 조회 — 페이지네이션 자동 합쳐짐.

        시그니처 타입을 Literal 로 강제 — mypy strict 가 caller (라우터) 까지 검증 (M2 적대적 리뷰).
        런타임 가드도 belt-and-suspenders 로 유지.

        Raises:
            ValueError: mrkt_tp 가 유효값 외 (typing.Literal 우회 시 안전망).
            KiwoomCredentialRejectedError: 401/403.
            KiwoomBusinessError: 응답 return_code != 0.
            KiwoomUpstreamError: 5xx · 네트워크 · 파싱 실패.
            KiwoomResponseValidationError: 응답 row Pydantic 검증 실패.
            KiwoomMaxPagesExceededError: max_pages=20 도달.
        """
        # Literal 시그니처가 정적 보호 — 런타임 가드는 동적 caller (예: dict.get) 안전망
        if mrkt_tp not in VALID_MRKT_TP:
            raise ValueError(f"mrkt_tp 유효값 외: {mrkt_tp!r} (허용: {VALID_MRKT_TP})")

        # SectorListRequest 사용 — wire 직전 Pydantic 검증 (1차 리뷰 MEDIUM)
        request_body = SectorListRequest(mrkt_tp=mrkt_tp).model_dump()

        all_rows: list[SectorRow] = []
        return_code = 0
        return_msg = ""

        async for page in self._client.call_paginated(
            api_id=self.API_ID,
            endpoint=self.PATH,
            body=request_body,
            max_pages=20,
        ):
            # 변수 캡처 후 except 밖 raise — `__context__` 차단 (C-1 적대적 리뷰 패턴 일관)
            validation_failed = False
            parsed: SectorListResponse | None = None
            try:
                parsed = SectorListResponse.model_validate(page.body)
            except ValidationError:
                validation_failed = True

            if validation_failed:
                # except 밖 raise — Pydantic ValidationError 가 cause/context 에 박히지 않음
                raise KiwoomResponseValidationError(f"{self.API_ID} 응답 검증 실패")
            if parsed is None:  # pragma: no cover — validation_failed 와 mutex
                raise RuntimeError("unreachable: parsed None without validation_failed")
            all_rows.extend(parsed.items)
            return_code = parsed.return_code
            return_msg = parsed.return_msg

        return SectorListResponse(
            items=all_rows,
            return_code=return_code,
            return_msg=return_msg,
        )
