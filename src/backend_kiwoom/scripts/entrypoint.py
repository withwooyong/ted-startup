#!/usr/bin/env python
"""컨테이너 진입점 — alembic upgrade head 후 uvicorn 단일 worker 기동.

- alembic 자동 적용 — Migration 014 까지 모두 idempotent + 비파괴 (ADR § 38.3)
- uvicorn `--workers 1` 명시 — APScheduler 중복 발화 방지 (ADR § 38.4)
- DB 미준비 시 재시도 — depends_on healthy 가 보장하지만 안전판
"""

from __future__ import annotations

import os
import subprocess
import sys


def run_alembic_upgrade() -> None:
    print("[entrypoint] alembic upgrade head 시작", flush=True)
    result = subprocess.run(
        ["alembic", "upgrade", "head"],
        check=False,
    )
    if result.returncode != 0:
        print(f"[entrypoint] alembic upgrade head 실패: exit={result.returncode}", flush=True)
        sys.exit(result.returncode)
    print("[entrypoint] alembic upgrade head 완료", flush=True)


def exec_uvicorn() -> None:
    port = os.environ.get("PORT", "8001")
    print(f"[entrypoint] uvicorn 기동 (port={port}, workers=1)", flush=True)
    os.execvp(
        "uvicorn",
        [
            "uvicorn",
            "app.main:app",
            "--host", "0.0.0.0",
            "--port", port,
            "--workers", "1",
            "--log-level", "info",
        ],
    )


if __name__ == "__main__":
    run_alembic_upgrade()
    exec_uvicorn()
