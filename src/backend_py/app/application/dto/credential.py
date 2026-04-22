"""자격증명 도메인 DTO — application layer.

`MaskedCredentialView` 는 repository 에서 마스킹 조립 결과로 반환되지만, 그 DTO 정의는
application layer 에 둔다. 이유:

- Hexagonal 원칙: application/web layer 가 infra(repository) 의 DTO 를 직접 참조하는
  의존 역전을 피하기 위해.
- UseCase 와 Router 가 같은 DTO 를 공유해야 하는데, 정의 위치는 가장 상위 레이어 = application.
- Repository(infra)가 application layer 의 DTO 를 import 해 반환하는 것은 허용되는 방향
  (infra → application 의존은 port 호출이므로 Hexagonal 에 합치).

설계: docs/kis-real-account-sync-plan.md § 3.2 (원래 repository 정의 → 2026-04-22 이동).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class MaskedCredentialView:
    """GET 응답용 마스킹된 자격증명 뷰.

    `app_secret` 은 어떤 경로로도 노출되지 않는다. `app_key`·`account_no` 는
    마지막 4자리만 남기고 나머지는 `•` 로 치환한 문자열.
    """

    account_id: int
    app_key_masked: str
    account_no_masked: str
    key_version: int
    created_at: datetime
    updated_at: datetime
