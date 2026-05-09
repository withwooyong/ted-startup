# `KIWOOM_CREDENTIAL_MASTER_KEY` 운영 가이드

> **출처**: ADR-0001 § 2.4 (자격증명 보안 — Fernet 대칭 + 마스터키 fail-fast) / § 3.4 (회전 자동화 지연)
> **대상 독자**: backend_kiwoom 운영자 / 신규 입문자

---

## 1. 한 줄 요약

> DB 가 유출되더라도 키움 `appkey`/`secretkey` 가 평문 노출되지 않게 하는 **암호화 키**. DB 와 키를 서로 다른 신뢰 경계에 두기 위함 — 둘 다 동시에 털려야 자격증명이 노출됨.

---

## 2. 무엇이 아닌가 (혼동 주의)

| 변수 | 정체 | Phase C 사용? |
|------|------|----------|
| **`KIWOOM_CREDENTIAL_MASTER_KEY`** | Fernet 32B base64 — DB BYTEA 자격증명 암복호화 키 | ✅ 필수 |
| `KIWOOM_ACCOUNT_NO` | 키움 **계좌번호** (8자리 숫자) | ❌ Phase D 이후 (주문/잔고) |
| `KIWOOM_APPKEY` | 키움이 발급한 **API 앱키** (개발자 등록 시 받음) | ✅ register 시 1회 |
| `KIWOOM_SECRETKEY` | 키움이 발급한 **API 시크릿키** | ✅ register 시 1회 |

**마스터키는 키움 서버에 보내지 않습니다**. 100% 로컬 — DB 의 BYTEA 컬럼 암복호화 전용.

---

## 3. 왜 필요한가 — Defense in Depth

```
┌───────────────────────────────────────────────────┐
│  키움 OpenAPI                                     │
│  ↑ appkey + secretkey 로 토큰 발급                │
│  │                                                │
│  TokenManager (메모리, 즉시 폐기)                 │
│  ↑ Fernet.decrypt(ciphertext, MASTER_KEY)         │
│  │                                                │
│  PostgreSQL kiwoom.kiwoom_credential              │
│  • appkey_cipher    BYTEA  ← 암호화 상태          │
│  • secretkey_cipher BYTEA  ← 암호화 상태          │
└───────────────────────────────────────────────────┘
       ▲                                ▲
       │                                │
       │ DB 백업 / pg_dump 유출        │ env / secret manager
       │ (BYTEA → 의미 없는 바이트)    │ 마스터키 보관 (DB 외부)
       │                                │
       └─── 둘 다 동시 유출 ───────────┘
            만 평문 복원 가능
```

---

## 4. 위험 시나리오 비교

| 사고 | 평문 저장 (구식) | Fernet 암호화 (현 방식) |
|------|-----------------|----------------------|
| DB 백업 파일 S3 misconfig | appkey/secretkey 즉시 노출 | BYTEA 만 노출 → 의미 없음 |
| `pg_dump` 결과 git 실수 커밋 | 동일 | 동일 — ciphertext 만 |
| DB 호스트 read-only 침해 | 평문 노출 | ciphertext 만 |
| DBA 권한자 내부 위협 | 즉시 모든 자격증명 열람 | 마스터키 추가 획득 필요 (권한 분리) |
| 운영자 SELECT 결과 슬랙 공유 실수 | 평문 슬랙 노출 | `\x4f7256...` 의미 없는 바이트 |

---

## 5. 생성 방법

```bash
cd src/backend_kiwoom
uv run python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

**출력 형식**: 44자 URL-safe base64 (예: `IagxdiiY0O5pEOBP4rfV2F1O_eq6pQo1n6G8vGZZeIk=`)

> ⚠️ 위 예시 키를 그대로 쓰지 말 것 — 본인이 새로 생성한 값을 사용해야 함.

---

## 6. `.env.prod` 적용 예시

```bash
# DB 연결
KIWOOM_DATABASE_URL=postgresql+asyncpg://kiwoom:kiwoom@localhost:5433/kiwoom_db

# 자격증명 보안 (본 가이드 핵심)
KIWOOM_CREDENTIAL_MASTER_KEY=<위 명령으로 새로 생성한 키>

# 키움 자격증명 (register_credential.py 1회 실행 시에만 필요)
KIWOOM_APPKEY=<운영 appkey>
KIWOOM_SECRETKEY=<운영 secretkey>

# 환경
KIWOOM_DEFAULT_ENV=prod
NXT_COLLECTION_ENABLED=true
```

> 한번 등록되면 `KIWOOM_APPKEY` / `KIWOOM_SECRETKEY` 는 **삭제해도 됨** — 이후 모든 호출은 DB ciphertext + master_key 만 사용.

---

## 7. 보관 원칙

| 항목 | 권고 |
|------|------|
| 저장 위치 | 1Password / AWS Secrets Manager / `.env.prod` (gitignore 필수) |
| Git 격리 | `.env.prod` 는 절대 커밋 금지 — `.gitignore` 확인 |
| 쉘 history | `set +o history` 후 export, 또는 `set -a; source .env.prod; set +a` |
| 환경 분리 | local / dev / prod 각각 다른 키 (한 키 노출 시 다른 환경 보호) |
| 백업 위치 | DB 와 **다른 신뢰 경계** (예: 키는 1Password, DB 는 RDS) |

---

## 8. 회전 정책 (ADR § 3.4 — 자동화 지연 중)

`KiwoomCredentialCipher` 는 다중 버전 구조를 이미 지원:

```python
# 회전 시
cipher._fernets[2] = Fernet(new_key)  # v2 추가
cipher._current_version = 2           # 신규 encrypt 는 v2
# v1 으로 암호화된 기존 row 도 decrypt 가능 (key_version 컬럼으로 분기)
```

운영 회전 절차 (수동 — 자동화는 미구현):

1. 신규 키 생성 → secret manager 에 v2 추가
2. lifespan 시작 시 cipher 에 v1 + v2 둘 다 등록
3. `register_credential.py` 재실행 → 모든 alias 가 v2 로 재암호화 (upsert 자동)
4. v1 rows 가 사라지면 v1 키 폐기

> 회전 자동화 스크립트 (`scripts/rotate_master_key.py`) 는 Phase B 후반 또는 운영 자격증명 발급 후 결정 (ADR § 3.4).

---

## 9. 분실 시 복구

> ⚠️ **마스터키 분실 = DB 의 자격증명 ciphertext 영구 복호화 불가**

복구 절차:
1. 신규 마스터키 생성 (5번 명령)
2. `.env.prod` 에 신규 키 적용
3. `register_credential.py` **재실행** (운영 키움 appkey/secretkey 다시 채워서) → DB 의 row upsert (신규 키로 재암호화)

**자격증명 자체가 분실된 건 아님** — 재등록만 하면 즉시 복구. 단 키움 측 appkey/secretkey 가 사용자 손에 있어야 함.

---

## 10. 코드 위치

| 파일 | 역할 |
|------|------|
| `app/security/kiwoom_credential_cipher.py:50-60` | Cipher 초기화 + 빈 키 fail-fast (`MasterKeyNotConfiguredError`) |
| `app/security/kiwoom_credential_cipher.py:66-72` | `encrypt()` — plaintext → (BYTEA, key_version) |
| `app/security/kiwoom_credential_cipher.py:74-81` | `decrypt()` — `key_version` 분기 + `InvalidToken` 예외 |
| `app/adapter/out/persistence/repositories/kiwoom_credential.py:46-81` | `upsert()` — encrypt → BYTEA INSERT/UPDATE |
| `app/adapter/out/persistence/repositories/kiwoom_credential.py:87-100` | `get_decrypted()` — BYTEA → 평문 (메모리만) |
| `app/main.py` (lifespan) | 앱 기동 시 master_key 검증 — 빈값이면 즉시 종료 |
| `app/config/settings.py` | `kiwoom_credential_master_key: str` Field — env: `KIWOOM_CREDENTIAL_MASTER_KEY` |

---

## 11. 트러블슈팅

| 증상 | 원인 | 조치 |
|------|------|------|
| `MasterKeyNotConfiguredError` | env 빈 값 | `.env.prod` 또는 export 확인 |
| `MasterKeyNotConfiguredError: 형식 오류` | 32B base64 가 아님 | `Fernet.generate_key()` 출력 그대로 사용 |
| `DecryptionFailedError: Fernet 복호화 실패` | 다른 키로 암호화된 row | 마스터키가 변경됨 → 9번 분실 시 복구 절차 |
| `UnknownKeyVersionError: key_version=2` | 회전 중 v2 등록 안 됨 | cipher 인스턴스에 v2 추가 (8번 회전 절차 2단계) |

---

## 12. 대안 비교

| 옵션 | 장점 | 단점 | 채택? |
|------|------|------|-------|
| 평문 저장 | 단순 | DB 유출 = 자격증명 유출 | ❌ |
| **Fernet 대칭** | DB 유출 ≠ 자격증명 유출. 키 회전 가능 | 마스터키 분실 시 재등록 필요 | ✅ 채택 |
| KMS / HSM | 마스터키도 외부 격리 | 추가 인프라 비용 + 운영 복잡도 | 향후 운영 확장 시 |

backend_kiwoom 은 단일 머신 + 단일 운영자 기준 **MVP 적정선**으로 Fernet 채택. 운영 확장 시 KMS 마이그레이션 가능 (`_fernets[v]` 다중 버전 구조 호환).
