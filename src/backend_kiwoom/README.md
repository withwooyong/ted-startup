# backend_kiwoom

키움 OpenAPI 25 endpoint 를 호출해 KRX/NXT OHLCV·시그널·순위·투자자별 매매 데이터를 PostgreSQL 에 적재하는 독립 백엔드.

> **상태**: Phase A (기반 인프라 — A1 chunk) 코드화. 실제 키움 API 호출은 A2 (예정).
>
> **참조**: `docs/plans/master.md` (25 endpoint 카탈로그), `docs/plans/endpoint-XX-{api_id}.md` (개별 계획서).

## 디렉토리

```
src/backend_kiwoom/
├ app/
│  ├ config/settings.py              Pydantic v2 BaseSettings
│  ├ security/kiwoom_credential_cipher.py  Fernet (key_version 회전)
│  ├ observability/logging.py        structlog + 자동 마스킹
│  ├ application/dto/                값 객체 (KiwoomCredentials 등)
│  └ adapter/out/persistence/        SQLAlchemy 2.0 async ORM
├ migrations/versions/               Alembic 마이그레이션
├ tests/                             pytest + testcontainers PG16
├ pyproject.toml
├ alembic.ini
├ Dockerfile
└ .env.example
```

## 로컬 실행

```bash
cd src/backend_kiwoom
uv sync --extra dev

# 마스터키 발급 (1회)
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# .env 의 KIWOOM_CREDENTIAL_MASTER_KEY 에 출력값 복사

# 마이그레이션 + 테스트
uv run alembic upgrade head
uv run pytest
```

## 보안 원칙 (Phase A)

- **자격증명 평문 저장 금지**: appkey/secretkey 는 Fernet 으로 암호화 후 BYTEA 저장
- **마스터키 미주입 시 fail-fast**: `KIWOOM_CREDENTIAL_MASTER_KEY` 빈 값이면 Cipher 초기화 차단
- **로그 마스킹**: structlog processor 가 `appkey`/`secretkey`/`token`/`authorization` 키 + JWT/40+hex 패턴 자동 치환
- **DB 분리**: `kiwoom` 스키마로 backend_py 와 격리

## Phase 진행

| Phase | 상태 | 산출물 |
|-------|------|--------|
| A1 (기반) | 🔄 진행 | Settings + Cipher + structlog + Migration 001 + Repository |
| A2 (인증) | ⏳ 대기 | KiwoomClient + KiwoomAuthClient (au10001/au10002) |
| A3 (sector) | ⏳ 대기 | KiwoomStkInfoClient (ka10101) + sector master |
| B~G | ⏳ 대기 | 22 endpoint (master.md § 5) |

상세 계획은 `docs/plans/master.md` 참조.
