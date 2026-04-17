---
agent: 13-security
phase: 4-verify
stage: 09-security-audit
date: 2026-04-17
status: CONDITIONAL
---

# 보안 감사 보고서 — ted-startup (BEARWATCH)

## Summary

| 심각도 | 건수 |
|--------|------|
| Critical | 0 |
| High | 1 |
| Medium | 4 |
| Low | 3 |

**판정: CONDITIONAL** — Critical/BLOCK 없음. MVP 런칭 전 High 1건(프론트엔드 ADMIN API Key 번들 노출) 반드시 수정 필요. 그 외 Medium/Low는 배포 직후 패치 타임라인으로 처리 가능.

- 스택: Spring Boot 3.5.0 + Java 21 (Gradle, pom.xml 아님), Next.js 16.2.4 + React 19.2.4.
- MVP 특성: 전통적 사용자 로그인 없음. 관리자 엔드포인트만 `X-API-Key` 검증. PII는 종목코드/티커 수준으로 극소.
- 공개 엔드포인트: `GET /api/signals`, `GET /api/stocks/{code}`, `GET /api/backtest`, `GET /api/notifications/preferences`.
- 보호 엔드포인트: `POST /api/batch/collect`, `POST /api/signals/detect`, `POST /api/backtest/run`, `PUT /api/notifications/preferences`.

---

## OWASP Top 10 Walkthrough

| # | 항목 | 상태 | 요약 |
|---|------|------|------|
| A01 | Broken Access Control | PASS | 관리자 엔드포인트 4개 모두 `ApiKeyValidator.isValid()` 선제 체크. 읽기 전용 엔드포인트는 의도적으로 공개(인증 없음). |
| A02 | Cryptographic Failures | PASS (w/ note) | 토큰/키 평문 저장 없음(환경변수 주입). `MessageDigest.isEqual`로 timing-safe 비교. KRX만 HTTP(외부 제약). |
| A03 | Injection (SQL/XSS/cmd) | PASS | 모든 JPQL에 `@Param` 바인딩. 네이티브 쿼리/동적 SQL 조립 없음. 커맨드 실행 없음. |
| A04 | Insecure Design | FINDING (M) | Rate limiting/브루트포스 방어 미구현. API Key 30자 이상 강제 없음. |
| A05 | Security Misconfiguration | FINDING (M) | Actuator `health,info,metrics` 공개, `info` 미인증 노출 시 빌드 메타 유출 가능. 보안 헤더(X-Frame-Options, HSTS, CSP) 미설정. |
| A06 | Vulnerable Components | PASS | `npm audit`: 0 vulnerabilities. 백엔드는 자동 스캔 미연결 — 권고사항. |
| A07 | Identification & Auth Failures | FINDING (H) | `NEXT_PUBLIC_ADMIN_API_KEY` 사용으로 관리자 키가 브라우저 번들에 포함됨. 누구나 DevTools로 추출 가능. |
| A08 | Software & Data Integrity | PASS | 외부 의존성 pinning(구체 버전). CI 서명 검증 없음(MVP 허용). |
| A09 | Logging & Monitoring | FINDING (L) | 감사 로그 체계 없음. 인증 실패가 로그로 남지 않음. 텔레그램 chatId 평문 로깅. |
| A10 | SSRF | PASS | 외부 URL 모두 상수(KRX/Telegram). 사용자 입력으로 URL 조립 없음. |

---

## Findings

### HIGH-1. 관리자 API Key가 프론트엔드 번들에 노출됨

- 파일: `src/frontend/src/app/settings/page.tsx:24`, `src/frontend/src/lib/api/client.ts:47-58`
- 코드: `const ADMIN_API_KEY = process.env.NEXT_PUBLIC_ADMIN_API_KEY || '';`
- 재현: `NEXT_PUBLIC_` 프리픽스 환경변수는 Next.js가 **클라이언트 JS 번들에 인라인**함. 빌드 산출물(`.next/static/chunks/**`)에서 grep으로 즉시 추출 가능. 악의적 사용자가 `X-API-Key`를 탈취해 `/api/batch/collect`, `/api/signals/detect`, `/api/backtest/run`, `PUT /api/notifications/preferences`를 임의 호출 가능.
- 영향: 보호된 관리자 엔드포인트 4개 전부 무력화. 배치 남용으로 KRX 측 IP 차단 및 Telegram 메시지 스팸 유발 가능.
- 수정(택1):
  1. **권장**: 관리자 기능(설정 저장/배치 트리거)은 서버 액션 또는 Next.js Route Handler로 이동해 키를 서버 측에서만 참조. 클라이언트는 내부 세션 쿠키로만 승격.
  2. 차선: Basic Auth + nginx IP 화이트리스트로 라우팅 전단계 차단. 단, MVP 인프라에 역할 충돌.
- 사전 배포 필수: YES.

### MED-1. Rate Limiting / 브루트포스 방어 부재

- 파일: `src/backend/src/main/java/com/ted/signal/adapter/in/web/ApiKeyValidator.java` 및 모든 Controller.
- 재현: 공격자가 유효하지 않은 API Key로 초당 수천 회 `POST /api/batch/collect`를 시도해도 계정 잠금/지연이 없음. HIGH-1과 결합 시 키 탈취 후 DOS 효과 증폭.
- 수정: Bucket4j 또는 Spring Cloud Gateway에 `RateLimiter` 필터 추가. 엔드포인트별 한도 예) 관리자 1 rps, 공개 60 rpm per IP. `dependencies`에 `com.bucket4j:bucket4j-spring-boot-starter` 추가.
- 사전 배포 필수: NO (모니터링 병행 시 48시간 내 패치 허용).

### MED-2. Actuator `info` 엔드포인트 공개

- 파일: `src/backend/src/main/resources/application.yml:52-56`
- 재현: `application.yml`에 `management.endpoints.web.exposure.include: health,info,metrics`. 현재는 `info`에 빌드 메타가 없지만 향후 `info.app.version`, `info.git.commit` 추가 시 커밋 해시/버전 유출. `metrics` 전체 공개 시 JVM heap/스레드 수로 내부 구조 유출 가능.
- 수정: prod 프로필에서 `health`만 노출하거나 `management.server.port` 분리 + 방화벽 차단.
  ```yaml
  management:
    endpoints:
      web:
        exposure:
          include: health
    endpoint:
      health:
        show-details: never
  ```
- 사전 배포 필수: NO.

### MED-3. 보안 HTTP 헤더 미설정

- 파일: `src/backend/src/main/java/com/ted/signal/config/WebConfig.java` (CORS만 설정).
- 재현: 응답에 `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Strict-Transport-Security`, `Content-Security-Policy` 등 기본 보안 헤더 없음. 클릭재킹/MIME 스니핑 방어 부재.
- 수정: `spring-boot-starter-security` 의존성 추가가 MVP에는 과하므로, `OncePerRequestFilter`로 헤더만 추가:
  ```java
  response.setHeader("X-Content-Type-Options", "nosniff");
  response.setHeader("X-Frame-Options", "DENY");
  response.setHeader("Referrer-Policy", "strict-origin-when-cross-origin");
  ```
- 사전 배포 필수: NO.

### MED-4. Telegram HTML parse_mode 잠재 XSS

- 파일: `src/backend/src/main/java/com/ted/signal/application/service/TelegramNotificationService.java:73-76, 84`, `src/backend/src/main/java/com/ted/signal/adapter/out/external/TelegramClient.java:51-55`
- 재현: `sendMessage`의 `parse_mode=HTML` 사용 중이며 메시지 본문에 KRX에서 가져온 `stock.getStockName()`을 직접 concat. KRX 측이 종목명에 `<script>` 류를 내려줄 가능성은 낮지만, 업계 선례상 종목명에 HTML 엔티티(`&`, `<`, `>`)가 포함될 경우 Telegram이 메시지를 거부(400 Bad Request)해 알림 실패로 이어짐. 실질적 XSS는 아니지만 가용성(A09 Logging과 결합)에 영향.
- 수정: 메시지 조립 전 `org.springframework.web.util.HtmlUtils.htmlEscape(name)` 적용. 또는 `parse_mode`를 `MarkdownV2`로 변경 시 이스케이프 테이블이 더 엄격하므로 현 HTML 유지 + escape 권장.
- 사전 배포 필수: NO (KRX 실데이터에 HTML 특수문자 관측 시 즉시 패치).

### LOW-1. API Key 최소 길이 검증 없음

- 파일: `src/backend/src/main/java/com/ted/signal/adapter/in/web/ApiKeyValidator.java:18-27`
- 현재: 빈 키면 모두 거부(line 23)하나 `ADMIN_API_KEY=1`도 허용.
- 수정: 생성자에서 `adminApiKey.length() < 32` 시 `IllegalStateException`으로 부팅 실패 처리. 운영자 실수 방지.

### LOW-2. 인증 실패 이벤트 로깅 없음

- 파일: 모든 Controller의 `if (!apiKeyValidator.isValid(apiKey))` 분기.
- 현재: 401만 반환하고 로그 남기지 않음. 공격 패턴 탐지 불가.
- 수정: `log.warn("관리자 API 인증 실패 — endpoint={}, ip={}", endpoint, request.getRemoteAddr())` 추가. 프라이버시를 위해 IP는 마스킹.

### LOW-3. KRX 요청이 HTTP(평문)

- 파일: `src/backend/src/main/java/com/ted/signal/adapter/out/external/KrxClient.java:33, 120`
- 현재: `http://data.krx.co.kr`로 통신. KRX가 HTTPS 강제가 아님(외부 제약).
- 영향: MITM으로 주가 데이터 변조 가능성. 금융 신호 왜곡 리스크. 다만 KRX 측 인프라 책임.
- 수정: `https://data.krx.co.kr` 시도 후 실패 시 fallback 로직. 또는 응답 행 수/합계 sanity check.

---

## Dependency Audit

### Frontend (npm)
```
prod 59, dev 372, total 466
vulnerabilities: info 0, low 0, moderate 0, high 0, critical 0
```
결과: CLEAN. Next.js 16.2.4 + React 19.2.4 최신 라인.

### Backend (Gradle)
- `build.gradle` 기준: Spring Boot 3.5.0(2024-05 릴리스, 2026-04 기준 보안 패치 누락 가능), PostgreSQL JDBC, Lombok, testcontainers.
- `build.gradle:3` — Spring Boot 3.5.0 고정. **3.5.x의 최신 패치(3.5.8 등)로 갱신 권장**. CVE DB와 교차 검증 필요.
- 자동 스캔 파이프라인 없음:
  - 권고: GitHub Dependabot 활성화(`dependabot.yml`) + `org.owasp.dependencycheck` Gradle 플러그인 추가.
- pom.xml 언급은 실제 리포 구조와 불일치(Gradle 사용).

---

## Secrets & Config Review

### Grep 결과
- 커밋된 소스에서 `xoxb|sk-|AIza|ghp_|Bearer ` 패턴 탐지: **0건** (package-lock.json 내 `queue-microtask` 패키지명 오탐만 존재).
- `application.yml:11-12, 46, 49-50` — 모든 민감값 `${ENV_VAR:}` 플레이스홀더. 기본값 비어있음.
- `application-local.yml:5` — `password: signal` 평문 존재. **로컬 전용이지만 git에 커밋됨** — 프로덕션 연결로 혼용 금지.
- `.gitignore:32` — `.env*` 제외됨. 프론트엔드 `.env` 파일 현재 없음(clean).

### 위험 요소
1. `NEXT_PUBLIC_ADMIN_API_KEY` 환경변수명 자체가 클라이언트 번들 포함임을 시사(HIGH-1과 동일 근거).
2. `TelegramClient:32` — 시작 시 `log.info("텔레그램 알림 활성화 (chatId: {})", chatId)`로 chatId 평문 로깅. chatId는 비밀 수준은 아니나 봇 공격면을 좁히려면 마스킹 권장.
3. `application-local.yml` DB 자격증명이 단순(`signal/signal`). 로컬 Docker 전용 범위 유지 필수.

---

## Verdict

**CONDITIONAL** — 배포 전 HIGH-1(프론트 API Key 번들 노출) 반드시 해결. 나머지는 계획된 후속 릴리스에 포함 가능.

근거:
- Critical/BLOCK 없음.
- HIGH-1은 "인증 체계 실질적 무력화"에 해당하나, MVP 특성(PII 없음, 종목 데이터만)상 유출 피해 범위가 제한적.
- 공개 엔드포인트의 데이터는 이미 KRX 공개정보이므로 읽기 노출 손실 0.
- 관리자 액션 오남용 리스크(배치 트리거 폭주, 설정 변조)는 HIGH-1 수정만으로 해소.

---

## Recommendations (우선순위 순)

### Pre-ship 필수
1. **[HIGH-1]** `NEXT_PUBLIC_ADMIN_API_KEY` 제거 → Next.js Server Action/Route Handler로 래핑해 키를 서버 측 환경변수(`ADMIN_API_KEY`)에서만 읽도록 변경. `settings/page.tsx`의 저장 로직은 fetch(`/api/admin/preferences`)로 변경하고, Route Handler가 백엔드로 중계.

### Ship+1 (48시간 내)
2. **[MED-1]** Rate limiting (Bucket4j) 도입 — 관리자 1 rps, 공개 60 rpm/IP.
3. **[MED-2]** Actuator 노출 축소 — prod는 `health`만, `show-details: never`.
4. **[MED-3]** 보안 응답 헤더 필터 추가.
5. **[LOW-2]** 관리자 401 이벤트 WARN 로깅 + IP 마스킹.

### Ship+7 (일주일 내)
6. **[MED-4]** Telegram 메시지 HTML escape(`HtmlUtils.htmlEscape`) 적용.
7. **[LOW-1]** API Key 최소 길이(32) 부팅 시 검증.
8. Spring Boot 3.5.0 → 3.5.x 최신 패치로 갱신.
9. GitHub Dependabot 활성화 + OWASP dependency-check Gradle 플러그인 추가.
10. **[LOW-3]** KRX HTTPS 우선 시도 로직 + 응답 sanity check.
11. TelegramClient 시작 로그에서 chatId 마스킹 (`***1234` 형태).
