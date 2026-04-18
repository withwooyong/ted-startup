"""Repository 공용 헬퍼."""
from __future__ import annotations

from typing import Any


def rowcount_of(result: Any) -> int:
    """SQLAlchemy 2.0 async execute 결과에서 rowcount 안전 추출.

    반환형 `Result[Any]` 에는 .rowcount 가 없어 mypy attr-defined 에러가 난다.
    런타임은 INSERT/UPDATE/DELETE 시 CursorResult 를 반환하므로 getattr 로 우회.
    """
    try:
        return int(getattr(result, "rowcount", 0) or 0)
    except (TypeError, ValueError):
        return 0
