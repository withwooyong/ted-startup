#!/usr/bin/env python3
"""컨테이너 진입점 — Alembic 마이그레이션 실행 후 Uvicorn 기동.

레거시 스키마(Java Flyway V1/V2 가 생성) 가 이미 있는 DB 로 연결되는 경우,
`alembic upgrade head` 는 `CREATE TABLE stock ...` 에서 실패한다.
Java V1 = Alembic 001, V2 = Alembic 002 로 스키마가 정확히 대응되므로 다음 로직:

  - alembic_version 없음 AND stock 존재
      → `alembic stamp 002_notification_preference` (V1+V2 완료 상태로 마킹)
      → `alembic upgrade head` (003/004/005 신규 적용)
  - 그 외(신규 DB 또는 이미 tracked)
      → `alembic upgrade head`

※ 이전 버전은 `stamp head` 를 써서 003/004/005 가 누락됐다. 2026-04-18 수정.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from sqlalchemy import create_engine, inspect

from app.config.settings import get_settings


def _run(cmd: list[str]) -> None:
    print(f"[entrypoint] exec: {' '.join(cmd)}", flush=True)
    result = subprocess.run(cmd, cwd=str(Path(__file__).resolve().parent.parent))
    if result.returncode != 0:
        sys.exit(result.returncode)


def main() -> None:
    settings = get_settings()
    sync_url = settings.database_url.replace("+asyncpg", "+psycopg2")
    engine = create_engine(sync_url, pool_pre_ping=True)
    try:
        insp = inspect(engine)
        tables = set(insp.get_table_names())
    finally:
        engine.dispose()

    has_alembic = "alembic_version" in tables
    has_stock = "stock" in tables

    if not has_alembic and has_stock:
        # Java Flyway V1(init_schema) + V2(notification_preference) 가 적용된 상태.
        # 해당 두 단계를 완료로 마킹한 뒤, 003 portfolio / 004 dart_corp_mapping /
        # 005 analysis_report 를 upgrade head 로 적용.
        print(
            "[entrypoint] 레거시 Java Flyway 스키마 감지 — alembic stamp 002 후 upgrade head",
            flush=True,
        )
        _run(["alembic", "stamp", "002_notification_preference"])
        _run(["alembic", "upgrade", "head"])
    else:
        _run(["alembic", "upgrade", "head"])

    # Docker 사설 대역에서만 X-Forwarded-* 신뢰. 운영 스택에선 Caddy 가 같은 브리지 네트워크에 있어
    # 172.16/12 안의 IP 로 접속. "*" 로 두면 실수로 포트 노출 시 X-Forwarded-For 스푸핑 가능.
    # 다른 런타임(Kubernetes 등)에선 FORWARDED_ALLOW_IPS 환경변수로 오버라이드.
    forwarded_allow = os.environ.get("FORWARDED_ALLOW_IPS", "127.0.0.1,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16")
    uvicorn_args = [
        "uvicorn",
        "app.main:app",
        "--host",
        "0.0.0.0",
        "--port",
        str(settings.port),
        "--proxy-headers",
        "--forwarded-allow-ips",
        forwarded_allow,
    ]
    print(f"[entrypoint] starting uvicorn: {' '.join(uvicorn_args)}", flush=True)
    os.execvp(uvicorn_args[0], uvicorn_args)


if __name__ == "__main__":
    main()
