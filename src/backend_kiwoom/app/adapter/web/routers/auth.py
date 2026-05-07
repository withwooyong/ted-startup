"""POST /api/kiwoom/auth/tokens — 토큰 강제 갱신 (admin only).

설계: endpoint-01-au10001.md § 7.1.

응답 정책 (적대적 리뷰 반영):
- 토큰 평문 절대 미반환 — `mask_token` 으로 tail 일부만 노출 (L1: 25% cap)
- `expires_at` minute precision — 초/마이크로초 절단으로 정확한 발급 시각 fingerprint 차단 (M5)
- 잘못된 alias / 자격증명 거부 / 비활성 → 일관된 4xx 매핑 (HTTPException detail 은 비식별 메시지만)
- KiwoomBusinessError detail 에 attacker-influenced `message` 미포함 (M1)
- admin guard 가 함수 진입 전 차단

α chunk 범위: POST (issue). DELETE / revoke-raw 는 β.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field

from app.adapter.out.kiwoom._exceptions import (
    KiwoomBusinessError,
    KiwoomCredentialRejectedError,
    KiwoomResponseValidationError,
    KiwoomUpstreamError,
)
from app.adapter.web._deps import get_token_manager, require_admin_key
from app.application.dto.kiwoom_auth import mask_token
from app.application.service.token_service import (
    AliasCapacityExceededError,
    CredentialInactiveError,
    CredentialNotFoundError,
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
