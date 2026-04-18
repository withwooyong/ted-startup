#!/usr/bin/env python3
"""컨테이너 진입점 — Alembic 마이그레이션 실행 후 Uvicorn 기동.

레거시 스키마(Java Hibernate 가 생성) 가 이미 있는 DB 로 연결되는 경우,
`alembic upgrade head` 는 `CREATE TABLE stock ...` 에서 실패한다.
이 스크립트는 다음 로직으로 안전 전환한다:

  - alembic_version 없음 AND stock 존재  → `alembic stamp head` (현 상태를 최신으로 인식)
  - 그 외(신규 DB 또는 이미 tracked)    → `alembic upgrade head`
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
        print(
            "[entrypoint] 레거시 스키마 감지(Java Hibernate) — alembic stamp head 로 버전 테이블만 생성",
            flush=True,
        )
        _run(["alembic", "stamp", "head"])
    else:
        _run(["alembic", "upgrade", "head"])

    uvicorn_args = [
        "uvicorn",
        "app.main:app",
        "--host",
        "0.0.0.0",
        "--port",
        str(settings.port),
        "--proxy-headers",
        "--forwarded-allow-ips",
        "*",
    ]
    print(f"[entrypoint] starting uvicorn: {' '.join(uvicorn_args)}", flush=True)
    os.execvp(uvicorn_args[0], uvicorn_args)


if __name__ == "__main__":
    main()
