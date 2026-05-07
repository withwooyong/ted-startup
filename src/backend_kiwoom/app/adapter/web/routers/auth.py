"""POST/DELETE /api/kiwoom/auth/tokens — 토큰 발급/폐기 (admin only).

설계: endpoint-01-au10001.md § 7.1 + endpoint-02-au10002.md § 7.1.

응답 정책 (적대적 리뷰 반영):
- 토큰 평문 절대 미반환 — `mask_token` 으로 tail 일부만 노출 (L1: 25% cap)
- `expires_at` minute precision — 초/마이크로초 절단으로 정확한 발급 시각 fingerprint 차단 (M5)
- 잘못된 alias / 자격증명 거부 / 비활성 → 일관된 4xx 매핑 (HTTPException detail 은 비식별 메시지만)
- KiwoomBusinessError detail 에 attacker-influenced `message` 미포함 (M1)
- admin guard 가 함수 진입 전 차단

라우터 구성 (β):
- POST   /tokens               — 강제 갱신 (α)
- DELETE /tokens/{alias}       — 캐시 토큰 폐기
- POST   /tokens/revoke-raw    — 외부 토큰 명시 폐기 (운영 사고 대응)
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from pydantic import BaseModel, ConfigDict, Field

from app.adapter.out.kiwoom._exceptions import (
    KiwoomBusinessError,
    KiwoomCredentialRejectedError,
    KiwoomRateLimitedError,
    KiwoomResponseValidationError,
    KiwoomUpstreamError,
)
from app.adapter.web._deps import get_revoke_use_case, get_token_manager, require_admin_key
from app.application.dto.kiwoom_auth import mask_token
from app.application.service.token_service import (
    AliasCapacityExceededError,
    CredentialInactiveError,
    CredentialNotFoundError,
    RevokeKiwoomTokenUseCase,
    TokenManager,
)

router = APIRouter(
    prefix="/api/kiwoom/auth",
    tags=["kiwoom-auth"],
    dependencies=[Depends(require_admin_key)],
)


class IssueTokenResponse(BaseModel):
    """토큰 발급 응답. 평문 토큰은 절대 포함 안 됨. expires_at 분 단위 절단."""

    model_config = ConfigDict(frozen=True)

    alias: str
    token_masked: str = Field(description="토큰 마스킹 표현 (예: ••••abc123) — 평문 미포함")
    token_type: str
    expires_at: datetime = Field(description="토큰 만료 시각 (분 단위 절단, fingerprint 방어)")


@router.post(
    "/tokens",
    response_model=IssueTokenResponse,
    summary="토큰 강제 갱신 (admin)",
)
async def issue_token(
    alias: str = Query(..., min_length=1, max_length=50),
    manager: TokenManager = Depends(get_token_manager),
) -> IssueTokenResponse:
    """기존 캐시 무효화 후 새로 발급. 응답에 토큰 평문 없음."""
    manager.invalidate(alias=alias)
    try:
        token = await manager.get(alias=alias)
    except CredentialNotFoundError:
        # detail 에 alias 평문 미포함 — 라우터는 비식별 메시지만 반환
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="등록되지 않은 alias",
        ) from None
    except CredentialInactiveError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="비활성 자격증명",
        ) from None
    except AliasCapacityExceededError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="alias 한도 초과 — 운영 문의",
        ) from None
    except KiwoomCredentialRejectedError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="키움 자격증명 거부",
        ) from None
    except KiwoomRateLimitedError:
        # H-1 적대적 리뷰 — 429 매핑 (이전엔 fallback 500 떨어짐)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="키움 RPS 초과 — 잠시 후 재시도",
        ) from None
    except KiwoomBusinessError as exc:
        # api_id / return_code 만 노출 — message 는 attacker-influenced (M1)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"키움 비즈니스 오류 (api={exc.api_id} code={exc.return_code})",
        ) from None
    except KiwoomResponseValidationError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="키움 응답 형식 오류",
        ) from None
    except KiwoomUpstreamError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="키움 OpenAPI 호출 실패",
        ) from None

    # M5: expires_at 분 단위 절단 — 초/마이크로초 fingerprint 방어
    expires_at_truncated = token.expires_at.replace(second=0, microsecond=0)
    return IssueTokenResponse(
        alias=alias,
        token_masked=mask_token(token.token),
        token_type=token.token_type,
        expires_at=expires_at_truncated,
    )


# =============================================================================
# β chunk — DELETE /tokens/{alias} + POST /tokens/revoke-raw
# =============================================================================


class RevokeTokenResponse(BaseModel):
    """폐기 응답. revoked / reason / alias 만 — 토큰 평문 미포함.

    reason 은 도메인 enum 같은 짧은 식별자 (ok/cache-miss/already-expired/ok-raw).
    """

    model_config = ConfigDict(frozen=True)

    alias: str
    revoked: bool
    reason: str


class RevokeRawTokenRequest(BaseModel):
    """외부 토큰 명시 폐기 요청 — 운영 사고 대응.

    응답에 token 평문 미반환. body 는 라우터 함수 내에서만 보유.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    alias: Annotated[str, Field(min_length=1, max_length=50)]
    token: Annotated[str, Field(min_length=20, max_length=1000)]


def _map_revoke_exception(exc: Exception) -> HTTPException:
    """폐기 예외 → HTTPException. detail 비식별화 + cause chain 차단.

    H-1 적대적 리뷰: KiwoomRateLimitedError 매핑 추가 (이전엔 fallback 500).
    H-2/M-5 적대적 리뷰: KiwoomCredentialRejectedError 매핑 — revoke_by_raw_token 의
    401 idempotent 변환 누락 시 fallback 500 방어.
    """
    if isinstance(exc, CredentialNotFoundError):
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="등록되지 않은 alias",
        )
    if isinstance(exc, KiwoomCredentialRejectedError):
        # 폐기 경로의 401/403 — 이미 만료/폐기된 토큰. UseCase 가 idempotent 변환 못 한 경우
        return HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="키움 자격증명 거부 또는 만료",
        )
    if isinstance(exc, KiwoomRateLimitedError):
        return HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="키움 RPS 초과 — 잠시 후 재시도",
        )
    if isinstance(exc, KiwoomBusinessError):
        return HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"키움 비즈니스 오류 (api={exc.api_id} code={exc.return_code})",
        )
    if isinstance(exc, KiwoomResponseValidationError):
        return HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="키움 응답 형식 오류",
        )
    if isinstance(exc, KiwoomUpstreamError):
        return HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="키움 OpenAPI 호출 실패",
        )
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="내부 오류",
    )


@router.delete(
    "/tokens/{alias}",
    response_model=RevokeTokenResponse,
    summary="alias 의 캐시 토큰을 키움 측에 폐기",
)
async def revoke_token_by_alias(
    alias: Annotated[str, Path(min_length=1, max_length=50)],
    use_case: RevokeKiwoomTokenUseCase = Depends(get_revoke_use_case),
) -> RevokeTokenResponse:
    """캐시 hit → 키움 폐기 + 캐시 무효화. 캐시 miss → 멱등 응답."""
    try:
        result = await use_case.revoke_by_alias(alias=alias)
    except (
        CredentialNotFoundError,
        KiwoomCredentialRejectedError,
        KiwoomRateLimitedError,
        KiwoomBusinessError,
        KiwoomResponseValidationError,
        KiwoomUpstreamError,
    ) as exc:
        raise _map_revoke_exception(exc) from None

    return RevokeTokenResponse(
        alias=result.alias,
        revoked=result.revoked,
        reason=result.reason,
    )


@router.post(
    "/tokens/revoke-raw",
    response_model=RevokeTokenResponse,
    summary="외부 노출된 토큰을 명시 폐기 (운영 사고 대응)",
)
async def revoke_raw_token(
    body: RevokeRawTokenRequest,
    use_case: RevokeKiwoomTokenUseCase = Depends(get_revoke_use_case),
) -> RevokeTokenResponse:
    """body 의 token 평문은 라우터에서만 보유 — 응답에 미반환."""
    try:
        result = await use_case.revoke_by_raw_token(alias=body.alias, raw_token=body.token)
    except (
        CredentialNotFoundError,
        KiwoomCredentialRejectedError,
        KiwoomRateLimitedError,
        KiwoomBusinessError,
        KiwoomResponseValidationError,
        KiwoomUpstreamError,
    ) as exc:
        raise _map_revoke_exception(exc) from None

    return RevokeTokenResponse(
        alias=result.alias,
        revoked=result.revoked,
        reason=result.reason,
    )
