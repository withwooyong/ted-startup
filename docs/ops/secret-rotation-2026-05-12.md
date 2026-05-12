# Secret 회전 절차서 — 2026-05-12 대화 로그 노출 대응

> **CRITICAL** — 본 절차서는 사용자(Ted)가 직접 수행. Claude Code 는 검증 SQL 만 실행 가능.
> 근거: ADR § 38.8 #6 (secret 4건) + #7 (Docker Hub PAT)
> 작성: 2026-05-12 (KST) — § 38 Docker 배포 chunk 진단 시 대화 로그에 평문 노출 확인
>
> **실행 시점 (사용자 결정, 2026-05-12)**: **전체 개발 / 테스트 / 검증 종료 후** 일괄.
> `.env.prod` 편집 + Fernet 마스터키 교체 + DB 재암호화 + 컨테이너 재기동은 운영 영향이 크고 비가역. 개발 chunk 중간에 회전하면 후속 개발이 회전된 환경에 영향받음 → 디버깅 복잡도 ↑. 노출 위험은 존재하나 실제 침해 정황은 없음. 회전 시점이 오면 본 절차서를 그대로 따라 수행.

---

## 0. 배경 — 왜 회전해야 하는가

§ 38 Docker 컨테이너 배포 chunk 진행 중 다음 secret 들이 대화 로그에 **평문으로 영구 기록**됨:

| # | 항목 | 노출 경로 | 위험도 |
|---|------|----------|:------:|
| 1 | `KIWOOM_APPKEY` (또는 `KIWOOM_API_KEY`) | `docker compose exec env` / `.env.prod` cat | **CRITICAL** |
| 2 | `KIWOOM_SECRETKEY` (또는 `KIWOOM_API_SECRET`) | 동상 | **CRITICAL** |
| 3 | `KIWOOM_CREDENTIAL_MASTER_KEY` (Fernet 32B base64) | 동상 | **CRITICAL** |
| 4 | `KIWOOM_ACCOUNT_NO` (계좌번호) | 동상 | LOW (조회 외 권한 없음) |
| 5 | Docker Hub PAT (`dckr_pat_...`) | `~/.docker/config.json` 진단 시 base64 디코드 노출 | HIGH |

**왜 즉시 회전 — 대화 로그는 Anthropic 측 저장**: Claude Code 세션 로그는 사용자 환경 + Anthropic 서버 양쪽에 기록. 로그 삭제 요청을 해도 일정 기간 백업이 남을 수 있음. 침해 가능성 0% 가 아니므로 **노출된 secret 은 사용 가능한 상태로 두지 않음** 이 정책.

---

## 1. 회전 순서 (의존성)

```
[1단계] Docker Hub PAT          ← 가장 단순. 다른 의존성 0
[2단계] KIWOOM_APPKEY/SECRETKEY ← 키움증권 콘솔 발급
[3단계] Fernet 마스터키          ← KIWOOM_*KEY 회전 직후 (재암호화 동시 수행 효율적)
[4단계] KIWOOM_ACCOUNT_NO        ← 계좌 변경은 비즈니스 결정. 회전 = 신규 발급 (선택)
```

각 단계 완료 후 다음으로. 1단계 실패 시 2단계 이전 단계로 절대 진행 금지.

---

## 2. 사전 준비 (모두 회전 전 1회)

### 2.1 백업

```bash
# .env.prod 백업 (회전 후 비교 / 롤백)
cp .env.prod .env.prod.before-rotation-20260512

# DB 자격증명 row 백업
docker compose -f src/backend_kiwoom/docker-compose.yml exec -T kiwoom-db \
  pg_dump -U kiwoom -d kiwoom_db -t kiwoom.kiwoom_credential \
  > /tmp/kiwoom_credential.before-rotation-20260512.sql
```

### 2.2 컨테이너 정지 — Fernet 회전 단계까지 보류

```bash
# 회전 작업 중 cron 발화 방지 (특히 KRX rate limit 보호)
cd src/backend_kiwoom
docker compose stop kiwoom-app
```

> **5-12 화 오늘 회전 시 5-13 06:00 KST cron 첫 발화 영향 없음** — 회전 작업이 5-12 22:00 이전 종료되면 5-13 06:00 cron 정상 발화. 회전 시간 < 1시간 권장.

### 2.3 변수 정리

| Shell 변수 | 의미 | 회전 후 값 출처 |
|------------|------|----------------|
| `NEW_APPKEY` | 신규 키움 APPKEY | 키움증권 OpenAPI 콘솔 |
| `NEW_SECRETKEY` | 신규 키움 SECRETKEY | 동상 |
| `NEW_FERNET_KEY` | 신규 Fernet 마스터키 | `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |

> 본 절차서에는 **실제 값을 절대 기록하지 말 것**. 모든 값은 사용자 shell 환경변수 또는 .env.prod 파일에만 존재.

---

## 3. 단계별 회전

### 3.1 [1단계] Docker Hub PAT 회전

**소요 5분**. 키움 API 영향 없음.

#### Step 1 — 기존 PAT revoke

```
https://hub.docker.com/settings/security
```

→ 노출된 `dckr_pat_...` 항목 우측 메뉴 → **Delete** 클릭. 즉시 무효화 됨.

#### Step 2 — 신규 PAT 발급

같은 페이지 → **New Access Token**
- Description: `ted-mac-20260512`
- Permissions: **Read & Write** (이미지 push 필요 시) 또는 **Read** (pull 만)

발급 즉시 1회만 표시되므로 안전한 곳 (1Password 등 secret manager) 에 저장.

#### Step 3 — 로컬 적용

```bash
# 기존 자격 제거
docker logout

# 신규 PAT 으로 재로그인
docker login -u <docker-hub-username>
# Password: 발급된 dckr_pat_... 붙여넣기
```

> `~/.docker/config.json` 의 `auths` 또는 `credsStore` 에 새 자격이 저장됨. `credsStore = osxkeychain` 이면 Keychain 에 기록 (§ 38.6.1).

#### Step 4 — 검증

```bash
docker pull alpine:latest    # 정상 pull 동작
docker push <test-image>     # push 권한 필요 시
```

---

### 3.2 [2단계] KIWOOM_APPKEY / SECRETKEY 회전

**소요 15분**. 가장 중요. 회전 완료 전엔 컨테이너 기동 금지.

#### Step 1 — 기존 키 revoke

키움증권 OpenAPI 콘솔 (https://openapi.kiwoom.com) 로그인 → **앱 관리** → 노출된 앱 선택 → **앱 키 재발급** 또는 **앱 삭제**.

> 키움증권은 동시 다중 앱 발급 가능. **새 앱을 먼저 발급한 뒤 기존 앱을 삭제** 하면 cron 누락 없이 swap 가능. 그러나 노출 시점이 길어지므로 **노출된 앱 즉시 삭제 (또는 키 재발급) 후 새 앱 발급** 권장.

#### Step 2 — 신규 키 확보

신규 APPKEY/SECRETKEY 발급 완료 후, 콘솔에서 1회만 표시되는 SECRETKEY 를 안전한 곳에 즉시 저장.

#### Step 3 — `.env.prod` 갱신

```bash
# 편집기로 .env.prod 열고 아래 3 항목 교체
KIWOOM_APPKEY=<NEW_APPKEY>
KIWOOM_SECRETKEY=<NEW_SECRETKEY>
# KIWOOM_API_KEY / KIWOOM_API_SECRET 도 같은 값으로 (fallback 명명)
```

> 본 단계에서 **Fernet 마스터키는 아직 회전하지 않음**. 3.3 단계와 분리하면 DB 재암호화 횟수가 2배가 되므로 효율 ↓. 단, 3.2 단계 성공이 3.3 단계의 전제이므로 우선 3.2 만 완료.

#### Step 4 — DB 자격증명 재등록 (기존 Fernet 키로 신규 plaintext 암호화)

```bash
cd src/backend_kiwoom
uv run python scripts/register_credential.py --alias prod --env prod
# 환경변수 KIWOOM_APPKEY / KIWOOM_SECRETKEY 가 .env.prod 에서 load 됨
# DB 의 alias=prod row 가 신규 plaintext 로 upsert (Fernet 암호화는 기존 key_version=1)
```

#### Step 5 — 검증

```bash
docker compose -f src/backend_kiwoom/docker-compose.yml exec -T kiwoom-db \
  psql -U kiwoom -d kiwoom_db -c "
SELECT id, alias, env, key_version, length(appkey_cipher) AS appkey_len,
       updated_at AT TIME ZONE 'Asia/Seoul' AS updated_kst
FROM kiwoom.kiwoom_credential WHERE alias='prod';"
# updated_kst 가 방금 실행 시각이어야 함 (회전 확인)
# key_version 은 여전히 1 (Fernet 키 회전은 다음 단계)
```

---

### 3.3 [3단계] Fernet 마스터키 회전 — DB 재암호화

**소요 20분**. KIWOOM_*KEY 회전 직후가 가장 효율적 (동일 plaintext 로 재암호화 1회).

> **주의**: 현재 cipher 코드 (`KiwoomCredentialCipher`) 는 단일 master_key 만 받음 (`_fernets[v]` 다중 버전 구조는 있으나 실제 회전 마이그레이션 스크립트 부재 — ADR § 3.4). 따라서 **plaintext (APPKEY/SECRETKEY) 를 다시 입력해서 신규 키로 재암호화** 하는 단순 경로 사용. DB row 1개라 부담 없음.

#### Step 1 — 신규 Fernet 키 생성

```bash
# 신규 키 (32-byte url-safe base64) 1회 출력 — 안전한 곳에 즉시 저장
uv run python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# 예: 'aBcDeF...32바이트base64...=' (44자 + padding)
```

#### Step 2 — `.env.prod` 갱신

```bash
# KIWOOM_CREDENTIAL_MASTER_KEY 만 신규 값으로 교체
KIWOOM_CREDENTIAL_MASTER_KEY=<NEW_FERNET_KEY>
```

#### Step 3 — DB row 재암호화

```bash
# .env.prod 가 신규 Fernet 키를 이미 반영하므로 register_credential 재호출만 하면 됨
cd src/backend_kiwoom
uv run python scripts/register_credential.py --alias prod --env prod
# 신규 Fernet 키로 plaintext 재암호화 → BYTEA 컬럼 갱신
```

#### Step 4 — 검증

```bash
docker compose -f src/backend_kiwoom/docker-compose.yml exec -T kiwoom-db \
  psql -U kiwoom -d kiwoom_db -c "
SELECT id, alias, key_version, length(appkey_cipher),
       updated_at AT TIME ZONE 'Asia/Seoul' AS updated_kst
FROM kiwoom.kiwoom_credential WHERE alias='prod';"
# updated_kst 가 방금 실행 시각 / length 가 ~140 (Fernet 토큰 길이는 plaintext 길이에 거의 비례)
```

#### Step 5 — 복호화 동작 확인 (선택)

```bash
# 신규 Fernet 키로 row 를 복호화할 수 있는지 검사 — 회전 정합성 최종 확인
uv run python -c "
import asyncio, os
from app.adapter.out.persistence.repositories.kiwoom_credential import KiwoomCredentialRepository
from app.adapter.out.persistence.session import get_sessionmaker, get_engine
from app.security.kiwoom_credential_cipher import KiwoomCredentialCipher
from app.config.settings import get_settings

async def main():
    cipher = KiwoomCredentialCipher(master_key=get_settings().kiwoom_credential_master_key)
    async with get_sessionmaker()() as session:
        repo = KiwoomCredentialRepository(session=session, cipher=cipher)
        creds = await repo.get_decrypted(alias='prod')
        # plaintext 출력 금지. 마스킹만.
        print('appkey_prefix:', creds.appkey[:4] + '****' if creds else 'NOT FOUND')
    await get_engine().dispose()

asyncio.run(main())
"
# 'appkey_prefix: ABCD****' 같은 마스킹 출력이면 복호화 OK
```

---

### 3.4 [4단계] KIWOOM_ACCOUNT_NO — LOW 위험

**소요 0~10분**. 계좌번호 자체로는 매매 권한 없음 (조회만). 계좌 변경은 비즈니스 결정.

#### 선택지 A — 변경 안 함

운영 영향 0. ADR § 38.8 #6 에서 위험도 LOW 명시. **권장 (현 시점)**.

#### 선택지 B — 계좌 분리 / 변경

키움증권 홈트레이딩 → **계좌 추가 개설** → 신규 계좌번호 사용. 기존 계좌는 자산 이체 후 휴면. `.env.prod` 의 `KIWOOM_ACCOUNT_NO` 만 교체하면 됨.

---

## 4. 회전 후 컨테이너 재기동 + 검증

### 4.1 컨테이너 재기동

```bash
cd src/backend_kiwoom
docker compose up -d kiwoom-app
docker compose ps                    # Up (healthy)
```

### 4.2 기동 로그 검증

```bash
docker compose logs --since 5m kiwoom-app 2>&1 | grep -E "scheduler 시작|alembic|MasterKey|ERROR"
# 8 scheduler 정상 시작 / alembic upgrade head 완료 / MasterKeyNotConfiguredError 없음 / ERROR 0
```

### 4.3 첫 cron 발화 검증 (5-13 06:30 KST 이후)

§ 38 다음 chunk 의 "(5-13 06:00 발화 직후) cron 발화 결과 즉시 검증" 절차 그대로 (HANDOFF.md § Context for Next Session 참조).

추가로 신규 자격증명이 정상 동작했는지:
```bash
docker compose logs --since 1h kiwoom-app 2>&1 | grep -E "au10001|토큰 발급|appkey"
# 토큰 발급 성공 로그가 있으면 신규 APPKEY/SECRETKEY 정상
```

---

## 5. 롤백 (회전 실패 시)

> **롤백 가능 시점**: 3단계 (Fernet 마스터키) 완료 전 까지.
> **3단계 완료 후엔 신규 Fernet 키로 DB 가 재암호화 되어** 기존 키 사용 불가. 그러나 사전 백업 (2.1) 이 있으면 SQL 복원 가능.

### 롤백 절차

```bash
# 1. .env.prod 복원
cp .env.prod.before-rotation-20260512 .env.prod

# 2. DB row 복원 (3단계 이미 진행한 경우)
docker compose -f src/backend_kiwoom/docker-compose.yml exec -T kiwoom-db \
  psql -U kiwoom -d kiwoom_db -c "DELETE FROM kiwoom.kiwoom_credential WHERE alias='prod';"
docker compose -f src/backend_kiwoom/docker-compose.yml exec -T kiwoom-db \
  psql -U kiwoom -d kiwoom_db < /tmp/kiwoom_credential.before-rotation-20260512.sql

# 3. 컨테이너 재기동
docker compose up -d kiwoom-app
```

> **롤백은 노출 secret 을 다시 사용하게 됨** — 회전 실패 원인 즉시 해소 후 재시도 권장.

---

## 6. 완료 체크리스트

회전 작업 종료 후 사용자가 직접 확인:

- [ ] Docker Hub PAT — 기존 `dckr_pat_...` 삭제 / 신규 PAT 발급 / `docker pull alpine` 성공
- [ ] KIWOOM_APPKEY/SECRETKEY — 키움 콘솔에서 기존 앱 revoke / 신규 발급 / .env.prod 갱신 / DB upsert 성공 (updated_at 최신)
- [ ] Fernet 마스터키 — 신규 키 생성 / .env.prod 갱신 / DB 재암호화 성공 / 복호화 마스킹 출력 정상
- [ ] (선택) ACCOUNT_NO — 변경 결정 (B 선택지 진행 시)
- [ ] 컨테이너 재기동 — kiwoom-app Up (healthy) / 8 scheduler 시작 / ERROR 0
- [ ] 백업 파일 정리 — `.env.prod.before-rotation-20260512` / `/tmp/kiwoom_credential.before-rotation-20260512.sql` 회전 완료 24h 후 안전한 곳으로 이동 또는 삭제 (구 plaintext 포함)
- [ ] ADR / STATUS / HANDOFF 갱신 — § 38.8 #6 / #7 항목 해소 표시 (회전 후 별도 chunk 또는 다음 세션)

---

## 7. 보안 권고 — 재발 방지

1. **`docker compose exec env`, `cat .env.prod`, `~/.docker/config.json` 출력 금지** — Claude Code 세션 중 절대 실행하지 않음. 진단이 필요하면 변수명만 확인 (`env | cut -d= -f1`).
2. **secret 변수명에 의존하지 말고 마스킹 helper 사용** — `mask_appkey()` 가 이미 코드에 있음 (`app/application/dto/kiwoom_auth.py`).
3. **`.env.prod` 파일 자체 권한** — `chmod 600 .env.prod` / git ignore 확인.
4. **장기 — secret manager 도입** — AWS Secrets Manager / HashiCorp Vault / 1Password Connect. 운영 규모 ↑ 시.

---

## 부록 A — 의존성 다이어그램

```
┌───────────────────────┐
│  Docker Hub PAT       │  ← 독립
└───────────────────────┘
┌───────────────────────┐    ┌──────────────────────────┐
│  KIWOOM_APPKEY        │ ←  │  키움 OpenAPI 콘솔        │
│  KIWOOM_SECRETKEY     │    │  앱 발급 / revoke         │
└───────────────────────┘    └──────────────────────────┘
        │ plaintext
        ▼
┌───────────────────────┐    ┌──────────────────────────┐
│  Fernet 마스터키       │ →  │  kiwoom.kiwoom_credential │
│  (KIWOOM_CRED_..._KEY)│    │  appkey_cipher BYTEA      │
└───────────────────────┘    │  secretkey_cipher BYTEA   │
                             └──────────────────────────┘
        │
        ▼
┌───────────────────────┐
│  KIWOOM_ACCOUNT_NO    │  ← 독립 (조회 only)
└───────────────────────┘
```

## 부록 B — 참조

- ADR § 2.4 자격증명 보안 — Fernet 대칭 + 마스터키 fail-fast
- ADR § 3.4 마스터키 회전 자동화 (#4 지연 — 본 chunk 가 첫 실제 회전 시도)
- ADR § 38.8 #6/#7 follow-up — 본 절차서의 발생 원인
- `src/backend_kiwoom/scripts/register_credential.py` — 자격증명 등록/갱신 admin 도구
- `src/backend_kiwoom/app/security/kiwoom_credential_cipher.py` — Fernet wrapper
