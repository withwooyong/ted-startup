---
artifact: runbook
phase: 05-ship
agent: 12-devops
updated: 2026-04-18
---

# 운영 런북 (Operational Runbook)

단일 VPS/홈서버에서 docker compose 로 운영하는 1인 MVP 스택 기준.
공매도 커버링 시그널 탐지 서비스 — Caddy + 백엔드 + 프론트 + Postgres 4 컨테이너.

- 저장소: `github.com/withwooyong/ted-startup`
- Compose 파일: `docker-compose.prod.yml` (repo 루트)
- 환경변수: `.env.prod` (git 제외, 권한 600)
- 외부 노출: `80/tcp`, `443/tcp`, `443/udp` (Caddy만 — HTTP/2 + HTTP/3)
- 내부망 전용: backend:8080, frontend:3000, db:5432

---

## 1. 사전 준비 (Prerequisites)

- Linux 서버 (Ubuntu 22.04/24.04 권장), vCPU 2+ / RAM 4GB+ / 디스크 20GB+
- Docker Engine 24+ 와 Docker Compose v2 설치
- 아웃바운드 HTTPS 허용 (텔레그램 API, KRX API 호출용, Let's Encrypt ACME)
- 인바운드 `80/tcp`, `443/tcp`, `443/udp` 개방 (Caddy TLS + ACME HTTP-01 challenge + HTTP/3)
- (실도메인 사용 시) 도메인의 A 레코드가 서버 공인 IP 를 가리키도록 DNS 설정

---

## 2. 초기 배포 (First Deploy)

### 2.1 소스 체크아웃

```bash
git clone https://github.com/withwooyong/ted-startup.git
cd ted-startup
```

### 2.2 시크릿 파일 생성

```bash
cp .env.prod.example .env.prod
# 에디터로 열어 모든 CHANGE_ME_* 값 교체
vi .env.prod
chmod 600 .env.prod          # 운영자만 읽기/쓰기
```

필수 시크릿:

- `POSTGRES_PASSWORD` — `openssl rand -base64 24`
- `ADMIN_API_KEY` — `openssl rand -hex 32`
- `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`
- `KRX_AUTH_KEY`

TLS / 도메인 설정 (Caddy):

- `DOMAIN` — 기본값 `localhost` (Caddy internal CA 로 self-signed). 실 도메인(예: `signal.example.com`) 입력 시 Let's Encrypt 자동 발급
- `ACME_EMAIL` — Let's Encrypt 만료 경고 수신용 이메일 (실도메인 운영 시만 필수)

`.env.prod` 추가 예시 (기본값이 있으므로 생략해도 로컬은 동작):

```env
# --- TLS / Domain ---
DOMAIN=localhost
ACME_EMAIL=
```

### 2.3 스택 기동

```bash
# 이미지 빌드 + 기동 (첫 실행은 5~10분 소요)
docker compose --env-file .env.prod -f docker-compose.prod.yml up -d --build

# 전체 컨테이너 상태 확인
docker compose -f docker-compose.prod.yml ps
```

기대 상태:

- `ted-signal-db` → `healthy`
- `ted-signal-backend` → `healthy` (기동에 60초 내외 소요)
- `ted-signal-frontend` → `running`
- `ted-signal-caddy` → `healthy` (TLS 인증서 발급 완료 후)

> **첫 기동 시 TLS 발급 지연**: 실도메인 모드에서는 Let's Encrypt ACME challenge 로 최대 1~2분 소요. `docker compose logs -f caddy` 로 `certificate obtained successfully` 확인.

### 2.4 DB 스키마 초기화 확인

현재 Flyway 미도입 상태이므로, **Postgres 볼륨이 비어 있을 때만** `/docker-entrypoint-initdb.d/` 로 마운트된 V1/V2 SQL 이 자동 실행된다.

```bash
docker compose -f docker-compose.prod.yml exec db \
  psql -U signal -d signal_db -c "\dt"
```

주요 테이블(`short_interest_daily`, `signal`, `notification_preference` 등)이 보이면 정상.

> 이후 마이그레이션(V3+)은 자동 적용되지 않음 — 아래 "스키마 변경" 섹션 참조.

### 2.5 스모크 테스트

로컬(`DOMAIN=localhost`) 모드에서는 Caddy 가 internal CA 로 self-signed 인증서를 발급하므로 `curl -k` 또는 `--cacert` 옵션이 필요하다. 실도메인 + Let's Encrypt 모드에서는 `-k` 없이 정상 검증된다.

```bash
# 0) 관리자 키를 현재 셸에 로드 (test #5 에서 사용)
export ADMIN_API_KEY=$(grep '^ADMIN_API_KEY=' .env.prod | cut -d= -f2-)

# localhost 모드용 curl 옵션 (실도메인 시 -k 제거)
CURL_OPTS="-fsSk"
BASE="https://localhost"

# 1) 프론트엔드 루트 (Caddy TLS 종단 → frontend SSR)
curl $CURL_OPTS "$BASE/" | head -c 200

# 2) HTTP → HTTPS 자동 리다이렉트 확인 (Caddy 기본 동작)
curl -sSI http://localhost/ | head -n 1   # HTTP/1.1 308 Permanent Redirect

# 3) 백엔드 actuator/health (내부망 전용 — 컨테이너 내부에서)
docker compose -f docker-compose.prod.yml exec backend \
  curl -fsS http://localhost:8080/actuator/health

# 4) 시그널 조회 API (HTTPS)
curl $CURL_OPTS "$BASE/api/signals" | head -c 500

# 5) 알림 설정 조회 (공개, proxy.ts 경유)
curl $CURL_OPTS "$BASE/api/notifications/preferences"

# 6) 알림 설정 업데이트 (ADMIN_API_KEY 필요, HTTPS 로 전송)
#    - PUT 전용 엔드포인트 (GET 은 405)
#    - signalTypes 유효값: RAPID_DECLINE, TREND_REVERSAL, SHORT_SQUEEZE (1~3개)
#    - minScore: 0~100
curl $CURL_OPTS -X PUT \
     -H "Content-Type: application/json" \
     -H "X-Admin-Api-Key: $ADMIN_API_KEY" \
     -d '{
       "dailySummaryEnabled": true,
       "urgentAlertEnabled": true,
       "batchFailureEnabled": true,
       "weeklyReportEnabled": true,
       "minScore": 60,
       "signalTypes": ["RAPID_DECLINE", "TREND_REVERSAL", "SHORT_SQUEEZE"]
     }' \
     "$BASE/api/admin/notifications/preferences"

# 7) Prometheus 메트릭 (내부망 전용, 운영자 접근)
docker compose -f docker-compose.prod.yml exec backend \
  curl -fsS http://localhost:8080/actuator/prometheus | head -n 30
```

모두 2xx 응답이면 배포 완료. TLS 경로 검증이 포함된 풀 스모크.

> **보안 포인트**: `ADMIN_API_KEY` 가 HTTP 평문으로 노출되던 이전 구조 대비, 이제 Caddy 가 TLS 종단을 담당해 브라우저 → Caddy 구간이 암호화된다. Caddy → frontend / frontend → backend 구간은 내부 docker 네트워크라 외부에서 접근 불가.

---

## 3. 일상 운영

### 3.1 로그 확인

```bash
# 전체 스택 최근 200줄
docker compose -f docker-compose.prod.yml logs --tail=200

# 특정 서비스 실시간 추적
docker compose -f docker-compose.prod.yml logs -f backend
docker compose -f docker-compose.prod.yml logs -f frontend
```

### 3.2 헬스체크 확인

```bash
docker inspect --format='{{.State.Health.Status}}' ted-signal-backend
docker inspect --format='{{.State.Health.Status}}' ted-signal-db
```

### 3.3 재기동

```bash
# 설정만 바뀐 경우
docker compose -f docker-compose.prod.yml restart backend

# .env.prod 수정 후 재적용
docker compose --env-file .env.prod -f docker-compose.prod.yml up -d
```

---

## 4. 업데이트 배포 (Rolling Update — 단일 노드)

1인 운영이라 무중단 배포는 없음. **짧은 다운타임(≤30초) 허용.**

```bash
git pull origin master

# 재빌드 + 재기동
docker compose --env-file .env.prod -f docker-compose.prod.yml up -d --build

# 이전 이미지 정리 (디스크 확보)
docker image prune -f
```

---

## 5. 롤백 (Rollback)

### 5.1 직전 커밋으로 되돌리기

```bash
# 1) 컨테이너 중지
docker compose -f docker-compose.prod.yml down

# 2) 이전 커밋으로 체크아웃 (예: 배포 전 태그/커밋)
git checkout <prev-commit-sha>

# 3) 이전 소스 기반 재빌드
docker compose --env-file .env.prod -f docker-compose.prod.yml up -d --build
```

### 5.2 특정 이미지 태그로 되돌리기 (CI 에서 SHA 태그 사용 시)

```bash
# .env.prod 의 IMAGE_TAG 를 이전 SHA 로 수정 후
docker compose --env-file .env.prod -f docker-compose.prod.yml up -d
```

### 5.3 DB 마이그레이션 롤백

V2 이후의 스키마 변경은 자동 롤백이 없다. **사전 백업 필수.**

```bash
# 복구 (마이그레이션 적용 직전 덤프로 되돌리기)
docker compose -f docker-compose.prod.yml exec -T db \
  psql -U signal -d signal_db < backups/pre_v2_$(date +%Y%m%d).sql
```

---

## 6. DB 백업 전략

### 6.1 수동 백업

```bash
mkdir -p backups
docker compose -f docker-compose.prod.yml exec -T db \
  pg_dump -U signal -d signal_db --clean --if-exists \
  > backups/signal_$(date +%Y%m%d_%H%M).sql
```

### 6.2 cron 자동 백업 (호스트 crontab)

```cron
# 매일 03:00 덤프, 14일치 보관
0 3 * * * cd /home/ubuntu/ted-startup && \
  docker compose -f docker-compose.prod.yml exec -T db \
    pg_dump -U signal -d signal_db --clean --if-exists \
  | gzip > backups/signal_$(date +\%Y\%m\%d).sql.gz && \
  find backups/ -name 'signal_*.sql.gz' -mtime +14 -delete
```

> **MVP 제약**: 오프사이트 백업 미구축. 월 1회 `backups/` 디렉토리를 개인 NAS/S3 로 수동 복사 권장.

### 6.3 복원

```bash
gunzip -c backups/signal_20260401.sql.gz | \
  docker compose -f docker-compose.prod.yml exec -T db \
    psql -U signal -d signal_db
```

---

## 7. 스키마 변경 (Flyway 미도입 상태)

V2 이후 신규 마이그레이션 SQL 을 추가하려면:

1. `src/backend/src/main/resources/db/migration/V3__<desc>.sql` 생성
2. 배포 전 **백업 먼저** (위 6.1)
3. 수동 적용:
   ```bash
   docker compose -f docker-compose.prod.yml exec -T db \
     psql -U signal -d signal_db < src/backend/src/main/resources/db/migration/V3__xxx.sql
   ```
4. 애플리케이션 재기동

**Followup**: Flyway 도입 (`build.gradle` 에 `org.flywaydb:flyway-core` + `flyway-database-postgresql` 추가) → 부팅 시 자동 적용으로 전환.

---

## 8. 비밀값 관리

| 원칙 | 실행 |
|------|------|
| `.env.prod` 절대 커밋 금지 | `.gitignore` 에 등록 (`.env.prod`, `.env.prod.local`) |
| 파일 권한 600 | `chmod 600 .env.prod` (운영자 외 접근 차단) |
| 시크릿 순환 | 분기별 1회 `ADMIN_API_KEY`, DB password 재발급 |
| 백업 파일 권한 | `chmod 600 backups/*.sql*` |
| 서버 접근 | SSH 키 전용, root 로그인 비활성 |

---

## 9. 모니터링 & 알림

### 9.1 현재 (MVP)

- `docker logs` 수동 확인
- `/actuator/health` 엔드포인트 헬스체크
- `/actuator/prometheus` 메트릭 노출 (내부망 — JVM/HTTP 요청/배치 메트릭)
- Caddy `access log` stdout 출력 (TLS 연결, 4xx/5xx 카운트)
- 장애 감지는 **텔레그램 알림 실패 시 운영자 직접 인지** (스케줄 작업이 조용히 죽을 경우 리스크)

**Prometheus 메트릭 샘플 조회**:

```bash
# 컨테이너 내부에서 직접 (운영자)
docker compose -f docker-compose.prod.yml exec backend \
  curl -fsS http://localhost:8080/actuator/prometheus | grep -E '^(jvm_memory|http_server_requests_seconds_count|spring_batch)'
```

### 9.2 권장 보강 (v1.1)

- **Prometheus + Grafana** 컨테이너 추가 → `/actuator/prometheus` 스크랩, 대시보드 구성
- **Uptime Kuma** 컨테이너 추가 → 공개 `https://$DOMAIN/` 엔드포인트 5분 간격 외부 체크
- **Grafana Loki** + Promtail 로 컨테이너 로그 중앙집중화 (단일 노드라 경량)

---

## 10. 알려진 제약 (MVP 의도적)

| 항목 | 현재 | 미래 |
|------|------|------|
| 무중단 배포 | 없음 (짧은 다운타임 허용) | ECS Rolling Update |
| HA/Failover | 단일 노드 SPOF | Multi-AZ Aurora + ECS |
| 자동 백업 오프사이트 | 없음 | S3 lifecycle + Glacier |
| 시크릿 관리 | `.env.prod` 파일 | AWS Secrets Manager |
| 로그 보존 | Docker 기본 (로테이션 미설정) | CloudWatch Logs 30일 |
| 레지스트리 | 없음 (로컬 build) | ECR |
| TLS 인증서 | Caddy 자동 관리 (`caddy-data` 볼륨) | ACM + ALB |

---

## 11. v1.1 AWS 이관 로드맵

1. **컨테이너 레지스트리** — ECR 생성 → CI 에 `aws ecr get-login-password` 스텝 추가, 이미지 푸시
2. **DB** — Aurora PostgreSQL Serverless v2 (ACU 0.5~2) 로 마이그레이션, `pg_dump`/`pg_restore` 로 데이터 이관, Secrets Manager 에 접속정보 저장
3. **컴퓨트** — ECS Fargate Service 2개 (backend/frontend), 각각 Target Group + ALB, 헬스체크는 기존 `/actuator/health`, `/` 그대로 사용
4. **CDN & 엣지** — CloudFront → ALB + `public/` 정적 S3 오리진, 커스텀 도메인 + ACM 인증서
5. **관측 & 시크릿** — CloudWatch Logs (retention 30d), CloudWatch Alarms (5xx/p99), Secrets Manager 로 `ADMIN_API_KEY`/`TELEGRAM_*`/`KRX_AUTH_KEY` 이관

---

## 12. 빠른 레퍼런스

```bash
# 상태
docker compose -f docker-compose.prod.yml ps

# 로그
docker compose -f docker-compose.prod.yml logs -f --tail=100

# 백업
docker compose -f docker-compose.prod.yml exec -T db pg_dump -U signal signal_db > backup.sql

# 안전한 중지 (볼륨 보존)
docker compose -f docker-compose.prod.yml down

# 완전 제거 (⚠ 볼륨까지 삭제 — DB 데이터 유실)
docker compose -f docker-compose.prod.yml down -v
```
