# AI Agent Team 파이프라인 사용설명서

> **목적**: 요구사항 한 줄 → 기획 → 설계 → 개발 → 검증 → 배포까지, 16개 AI 전문가 에이전트가 자동으로 처리하는 파이프라인을 학습하고 다른 프로젝트에도 재사용할 수 있게 한다.
>
> **대상**: 소규모 스타트업 팀에서 기획/디자인/개발(FE/BE/앱)/보안/DevOps/운영 역할을 겸하는 모든 구성원.
>
> **원본 설계**: `docs/design/ai-agent-team-master.md` (4112줄) — 이 가이드는 실전 운영 요약본.

---

## 📑 목차

1. [5분 요약 — 이 플랫폼이 하는 일](#1-5분-요약)
2. [필수 준비물](#2-필수-준비물)
3. [새 프로젝트에 적용하는 3단계](#3-새-프로젝트에-적용하는-3단계)
4. [개발 플로우 마스터하기 (5 Phase)](#4-개발-플로우-마스터하기)
5. [슬래시 커맨드 치트시트](#5-슬래시-커맨드-치트시트)
6. [병렬 작업 패턴 (Agent Teams)](#6-병렬-작업-패턴)
7. [Compaction 방어 — 세션 끊겨도 안전](#7-compaction-방어)
8. [자주 겪는 문제 & 해결](#8-자주-겪는-문제--해결)
9. [체크리스트 — 다른 프로젝트 이식](#9-체크리스트--다른-프로젝트-이식)

---

## 1. 5분 요약

### 무엇을?
**"MVP 만들어줘"** 한 줄로 4~6주 내 런칭 가능한 웹/앱 서비스의 **기획서, 디자인, 코드, 테스트, 배포 스크립트**까지 일괄 생성.

### 어떻게?
16명의 AI 전문가가 순차·병렬로 분업:
```
[요구사항] → 사업분석 → PM → 기획/디자인/DB(병렬) → 백엔드/프론트(병렬) → QA/보안/리뷰(병렬) → DevOps → [배포]
```

### 왜 쓸까?
- **1인~소규모 팀**: 모든 직군을 겸할 때 AI가 전문성을 보완
- **학습 목적**: SDLC 전 과정을 한 번에 경험
- **반복 적용**: 다음 프로젝트에 `init-agent-team` 한 줄로 동일 구조 복제

---

## 2. 필수 준비물

### 환경
| 항목 | 버전 / 값 |
|------|-----------|
| Claude Code | 최신 (Opus 4.7 권장, 단일 운영) |
| 구독 | Max / Team / Enterprise (1M 컨텍스트 + Opus 단일 운영 전제) |
| `.claude/settings.json` env | `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`<br>`CLAUDE_AUTOCOMPACT_PCT_OVERRIDE=90` |
| `.claude/settings.local.json` | 개인 오버라이드용 (gitignored). 예: `{"includeCoAuthoredBy": true}` |
| Git | `init`, worktree 지원, GitHub CLI (`gh`) |
| 기본 스택 (본 프로젝트) | Python 3.12 + FastAPI, Next.js 16, Node 20+, PostgreSQL 16, Docker |
| 패키지 매니저 | `uv` (Python), `npm` (Node) |

> 📌 **스택 변경 시**: Scaffolding 생성기(`/init-agent-team`)는 본 프로젝트가 Java→Python 이전(Phase 1~9)을 거치며 진화했다. 다른 스택(Kotlin/Go/Rust 등)에 적용하려면 `agents/08-backend/AGENT.md` · `agents/09-frontend/AGENT.md` 를 팀 컨벤션으로 교체. 언어별 reviewer 에이전트 매핑은 §8 참조.

### 문서
- **반드시 숙지**: `docs/design/ai-agent-team-master.md` 목차 + Part I
- **참조**: 이 가이드 (`PIPELINE-GUIDE.md`)

### 모델 운용 전략 (구독 유형별)

**A. Claude Code Max / Team / Enterprise 구독자 — 권장**
- **Opus 4.7 단일 운영** (모든 Phase 기본값)
- 근거: 비용 고정 → 품질 최대화가 합리적. Phase별 분기 관리 비용이 오히려 손해
- 리밋 도달 시: Sonnet 4.6 자동 fallback → statusline으로 실시간 인지
- 실전 효과: Sprint 3에서 Opus 4.7이 N+1 쿼리 17,500건 등 HIGH 이슈 7건 포착 (Sonnet이면 표면 리뷰로 놓쳤을 가능성)

**B. API 종량제 / 비용 민감 사용자**
- 전체 파이프라인 1회 실행: $40~80 (Agent Teams 포함)
- Selective Loading 적용 시: $15~30 수준
- **핵심 절감 레버**: Phase 1~3은 Sonnet 4.6, Phase 4 검증만 Opus 4.7

| 단계 | Max 구독자 | 비용 민감 |
|------|-----------|-----------|
| Phase 1 Discovery | Opus 4.7 | Sonnet 4.6 |
| Phase 2 Design | Opus 4.7 | Sonnet 4.6 |
| Phase 3 Build | Opus 4.7 | Sonnet 4.6 (코드 생성만 Opus 선택적) |
| Phase 4 Verify | Opus 4.7 | Opus 4.7 (공통, 정확도 최우선) |
| Phase 5 Ship | Opus 4.7 | Sonnet 4.6 |

> 💡 **이 프로젝트(ted-startup)는 Max $200 구독 기준 Opus 4.7 단일 운영**.

---

## 3. 새 프로젝트에 적용하는 3단계

### Step 1: 디렉토리 생성 (5분)
```bash
mkdir my-new-project && cd my-new-project
git init
```

### Step 2: Scaffolding 자동 생성 (5분)
Claude Code 세션에서:
```
/init-agent-team my-new-project
```

이 한 줄이 아래를 전부 생성:
- `CLAUDE.md` (오케스트레이션 규칙)
- `agents/XX-이름/AGENT.md` 16개 (페르소나)
- `agents/_shared/` (통신 프로토콜)
- `.claude/commands/` 7개 (슬래시 커맨드)
- `pipeline/` (state, decisions, artifacts, contracts)
- `.claude/settings.json`, `.gitignore`

### Step 3: 요구사항 입력 + 실행 (자동)
```
/kickoff 반려동물 병원 진료기록 공유 SaaS를 4주 내 런칭
```
→ Phase 1부터 Phase 5까지 자동 진행, 3번의 인간 승인 게이트에서 멈춤.

---

## 4. 개발 플로우 마스터하기

### 전체 흐름도

```
┌─ Phase 1: Discovery ─┐   ┌─ Phase 2: Design ─┐   ┌─ Phase 3: Build ─┐   ┌─ Phase 4: Verify ─┐   ┌─ Phase 5: Ship ─┐
│ 01-biz-analyst       │   │ 03-planning       │   │ 08-backend    │   │ 11-qa              │   │ 12-devops        │
│ 02-pm                │   │ 06-design         │   │ 09-frontend   │   │ 08-backend(review) │   │ 04-marketing     │
│ 04-marketing         │ → │ 07-db             │ → │ 10-app        │ → │ 13-security        │ → │ (analytics)      │
│ 05-crm               │   │ (병렬 가능)       │   │ (병렬 가능)   │   │ (병렬 가능)        │   │                  │
└──────────────────────┘   └───────────────────┘   └───────────────┘   └────────────────────┘   └──────────────────┘
         🔴 승인 #1                🔴 승인 #2                                 🔴 승인 #3
       (Discovery 검토)          (설계 검토)                               (배포 직전 검토)
```

### Phase 1: Discovery (발견)

**목표**: 사용자의 모호한 요구사항 → 구조화된 명세.

| 에이전트 | 입력 | 출력 |
|---------|------|------|
| 01-biz-analyst | `pipeline/artifacts/00-input/user-request.md` | `01-requirements/requirements.md` (MoSCoW, US-001~) |
| 02-pm | requirements.md | `02-prd/prd.md`, `roadmap.md`, `sprint-plan.md` |
| 04-marketing | prd.md | `gtm-strategy.md`, `competitor-analysis.md` |
| 05-crm | prd.md | `customer-journey.md`, `notification-scenarios.md` |

**병렬화**: 02-pm 완료 후 03-marketing + 05-crm + 03-planning 3개 병렬 → **3배 속도**

**인간 승인 #1**: 00-advisor가 Decision Brief 자동 생성 → 사용자가 go/no-go 결정.

### Phase 2: Design (설계)

**목표**: PRD → 기능명세 + 화면 + 데이터 모델.

| 에이전트 | 출력 |
|---------|------|
| 03-planning | `03-design-spec/feature-spec.md`, `screen-flow.mermaid` |
| 06-design | `06-design-system/design-tokens.json`, `component-spec.md` |
| 07-db | `04-db-schema/erd.mermaid`, `ddl.sql`, `indexes.md`, `query-strategy.md` |

**병렬화**: 06-design(UI) + 07-db(데이터) 독립 → **2배 속도**, 충돌 위험 낮음.

**인간 승인 #2**: 설계 요약 + 기술 판단 근거 확인 후 진행.

### Phase 3: Build (구현) — Agent Teams 병렬

**이 프로젝트의 실전 사례 참조**: `pipeline/artifacts/06-code/summary.md`

**핵심 원리**: Contract-First Design
- 변경 금지 파일: `05-api-spec/openapi.yaml`, `04-db-schema/ddl.sql`, `06-design-system/design-tokens.json`
- 각 에이전트는 git worktree에서 격리 작업
- 충돌 발생 시 Team Lead가 계약 업데이트 후 재시작

**팀 구성 예시**:
```
Team Lead:    Build Orchestrator
Teammate 1:   08-backend    (src/backend/)        branch: feat/backend
Teammate 2:   09-frontend   (src/frontend/)       branch: feat/frontend
Teammate 3:   11-qa         (tests/)              branch: feat/tests
```

**코드 생성 3-Pass 전략** (128K Output 활용):
1. **Scaffolding Pass** (1회, 대규모): Entity, Repository, UseCase, DTO, Controller 스켈레톤 일괄 생성
2. **Domain Pass** (도메인당 1회): 비즈니스 로직 구현
3. **Integration Pass** (1회): Security, 예외 핸들러, Docker, 통합 테스트

### Phase 4: Verify (검증) — Agent Teams 병렬

**Full Context Mode**: 소스코드 전체를 1M 컨텍스트에 로드해서 크로스 파일 분석.

| 에이전트 | 체크 대상 |
|---------|-----------|
| 11-qa | 단위(70%) / 통합(20%) / E2E(10%) / 성능(P95<200ms) |
| 08-backend(review) | SOLID, N+1, 트랜잭션, 에러 핸들링 |
| 13-security | OWASP Top 10, 의존성 취약점, 비밀정보 |

**Critical 이슈 0건** 달성 전까지 배포 차단.

**인간 승인 #3**: 리스크 리포트 검토 후 최종 GO.

### Phase 5: Ship (배포)

| 에이전트 | 출력 |
|---------|------|
| 12-devops | `infra/terraform/`, `.github/workflows/`, `Dockerfile`, `runbook.md` |
| 04-marketing (analytics mode) | `11-analytics/launch-report.md` |

---

## 5. 슬래시 커맨드 치트시트

| 커맨드 | 실행 내용 | 언제 쓰나 |
|--------|----------|-----------|
| `/init-agent-team [name]` | 전체 Scaffolding 생성 | 새 프로젝트 시작 |
| `/kickoff [요구사항]` | Phase 1~5 전체 실행 | 처음부터 끝까지 |
| `/plan [요구사항]` | Phase 1만 | 요구사항 분석부터 다시 |
| `/design` | Phase 2만 | PRD 확정 후 설계만 |
| `/develop` | Phase 3만 | 설계 확정 후 구현만 |
| `/test` | Phase 4만 | 구현 완료 후 검증 |
| `/review` | 코드리뷰 + 보안 | 커밋 전 마지막 체크 |
| `/deploy` | Phase 5만 | 검증 통과 후 배포 |

### 실전 팁
- **중간에 끼어들기**: Phase 3 Sprint 2 끝났는데 한 기능만 추가? → `/develop` 후 프롬프트에서 "기능 X만 추가" 명시.
- **에이전트 수동 호출**: 특정 역할만 필요하면 `agents/XX-name/AGENT.md`를 Read로 로드 후 작업.

---

## 6. 병렬 작업 패턴

### 기본 (Sequential)
```
Agent 1 완료 → Agent 2 시작 → Agent 3 시작
총 시간 = A1 + A2 + A3
```

### 병렬 (Agent Teams + worktree)
```
Agent 1, 2, 3 동시 시작 (각자 worktree)
총 시간 = max(A1, A2, A3)
```

### Claude Code에서 실행 방법

**방법 A — Task 도구의 Agent 호출**:
```
한 메시지에 여러 Agent tool use 블록 → 병렬 실행
```

**방법 B — 격리 모드**:
```yaml
Agent 호출 시:
  isolation: "worktree"   # 별도 git worktree에서 작업
  name: "backend-team"    # SendMessage로 지속 통신 가능
```

**방법 C — Agent Teams 실험 기능**:
```bash
# settings.json
"env": {"CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"}
```

### 충돌 방지 3중 방어
1. **Contract-First**: API/DB 스키마 고정 후 구현 시작
2. **파일 소유권**: Backend = `src/backend/`, Frontend = `src/frontend/`
3. **통신 규칙**: 계약 변경 시 Team Lead 경유

---

## 7. Compaction 방어

Claude Code는 1M 토큰 초과 시 **대화 히스토리를 자동 요약**(Compaction)한다. 하지만 **파일은 건드리지 않는다**. 이 원리로 핵심 정보를 파일로 영속화.

### 필수 영속 파일
| 파일 | 역할 |
|------|------|
| `CLAUDE.md` | 매 턴 재로드 → 파이프라인 규칙 영구 보존 |
| `pipeline/state/current-state.json` | 현재 Phase/Stage/Agent 기록 |
| `pipeline/decisions/decision-registry.md` | 모든 의사결정 누적 |
| `pipeline/artifacts/XX/summary.md` | 각 단계 산출물 요약 |

### Compaction 후 복구 절차
```
1. pipeline/state/current-state.json 읽기
2. pipeline/decisions/decision-registry.md 읽기
3. 현재 단계에 필요한 산출물 로드
4. 작업 계속
```

### 3계층 컨텍스트 관리
- **Layer 1 (Metadata)**: 제목/경로만 — 5~50 토큰/산출물
- **Layer 2 (Summary)**: 요약본 `summary.md` — 500 토큰/산출물
- **Layer 3 (Full)**: 원본 전체 — Phase 4 검증 시에만

---

## 8. 자주 겪는 문제 & 해결

### Q1. 슬래시 커맨드를 실행했는데 에이전트가 안 움직여요
- `.claude/settings.json`의 `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` 확인
- `agents/XX-name/AGENT.md`가 실제로 존재하는지 확인
- `pipeline/artifacts/00-input/user-request.md`가 비어있지 않은지 확인

### Q2. 중간에 세션이 끊겼어요
- `pipeline/state/current-state.json` + `pipeline/decisions/decision-registry.md` 읽고 그 지점부터 재시작
- `/handoff` 스킬로 매 세션 종료 시 HANDOFF.md 생성해두면 안전

### Q3. 코드리뷰 결과 CRITICAL이 너무 많아요
- `/review` → 언어별 reviewer 에이전트가 자동 스캔 (아래 매핑 표)
- Phase 4의 Verify 게이트는 Critical 0건이 필수 조건
- 배치 크기가 크면 도메인별로 나눠서 리뷰

**언어별 reviewer 에이전트 매핑** (`everything-claude-code` 플러그인):

| 프로젝트 언어 | 리뷰어 에이전트 | 이 프로젝트 사용 여부 |
|---|---|---|
| Python | `everything-claude-code:python-reviewer` | ✅ 백엔드 |
| TypeScript / React | `everything-claude-code:typescript-reviewer` | ✅ 프론트엔드 |
| Kotlin / Android / Spring | `everything-claude-code:kotlin-reviewer` | 이전 스택 참고 |
| Java / Spring Boot | `everything-claude-code:java-reviewer` | Phase 1~9 이전 스택 |
| Go / Rust / C++ | `everything-claude-code:go-reviewer` 등 | — |

**병렬 리뷰 실전 패턴** (본 프로젝트 PR #12~#16 에서 검증):
- 풀스택 PR 은 python-reviewer + typescript-reviewer 를 **단일 메시지에 동시** Agent 호출
- 각 리뷰어에게 리뷰 대상 파일 경로를 명시, "기존 코드 이슈 vs 이번 변경 이슈" 구분 요청
- ~4분 내 양쪽 리뷰 완료 → HIGH 즉시 반영, MEDIUM 은 ROI 판단, 스킵 시 사유 기록

### Q4. 1인 프로젝트인데 팀 공유 구조가 필요한가요?
- `pipeline/` 디렉토리 커밋을 권장: Compaction 방어 + 팀원 합류 대비
- `.gitignore`에서 `pipeline/` 제거 → 전원이 동일 파이프라인 컨텍스트 공유

### Q5. 비용이 너무 많이 나와요
**API 종량제 사용자 한정** (Max/Team/Enterprise 구독자는 고정 비용이므로 해당 없음):
- Phase 1~3: Sonnet 4.6 사용 (Opus 대비 40~80% 절감)
- Phase 4 검증만 Opus 4.7 (정확도 최우선)
- Selective Loading 강제: 매 단계 Layer 2 요약본 사용
- 1회 실행당 $15~30 수준 가능

> Max 구독자는 Opus 4.7 단일 운영 권장 — 섹션 2 "모델 운용 전략" 참조.

### Q6. Opus 리밋이 걸리면 어떻게 되나요?
- Claude Code가 자동으로 Sonnet 4.6으로 fallback (수동 개입 불필요)
- `~/.claude/settings.json`의 `statusLine`에서 현재 모델 실시간 표시
- 5시간 세션 리밋 리셋 후 자동 복귀
- Fallback 중에도 작업은 중단 없이 지속 — 품질만 일시 저하

---

## 9. 체크리스트 — 다른 프로젝트 이식

### 이식 순서
1. [ ] 새 디렉토리 생성 + `git init`
2. [ ] `/init-agent-team [project-name]` 실행
3. [ ] `.claude/settings.json` 확인 (env, permissions)
4. [ ] `CLAUDE.md`의 "프로젝트 개요" 섹션을 내 프로젝트에 맞게 수정
5. [ ] 기술 스택 변경 시 `agents/08-backend/AGENT.md`, `agents/09-frontend/AGENT.md` 수정
6. [ ] 컨벤션 변경 시 `conventions/presets/` 확인 (네이버/토스/카카오 대신 팀 컨벤션)
7. [ ] `/kickoff [요구사항]` 실행
8. [ ] 3개 인간 승인 게이트 통과
9. [ ] 마지막에 `/handoff` 스킬로 HANDOFF.md 생성

### 재사용 가능 자산
- ✅ `.claude/commands/` 7개 커맨드 (프로젝트 무관)
- ✅ `agents/` 16개 페르소나 (스택 무관 구조)
- ✅ `agents/_shared/context-protocol.md` (통신 규격)
- ✅ `pipeline/` 구조 (빈 템플릿)

### 프로젝트별 수정 필요
- ⚠️ `CLAUDE.md` — 프로젝트 개요, 기술스택, 현재 상태
- ⚠️ `agents/08-backend/AGENT.md` — 스택이 Java 아니면
- ⚠️ `agents/09-frontend/AGENT.md` — 스택이 Next.js 아니면
- ⚠️ `conventions/` — 팀 컨벤션 반영

---

## 📚 더 깊이 알고 싶다면

- `docs/design/ai-agent-team-master.md` Part III (부록 F): Agent Teams 병렬화 상세 설계
- `docs/design/ai-agent-team-master.md` Part II: 1M 컨텍스트 활용 최적화
- `docs/design/ai-agent-team-master.md` 부록 D: Compaction 방어 영속화 아키텍처
- `docs/design/ai-agent-team-master.md` 부록 E: 128K Output 하이브리드 전략

---

## 💡 이 프로젝트(ted-startup)의 실전 학습 포인트

### 🆕 frontend-lint 게이트 — 대칭 설계 (PR #(예정), 2026-04-22)

| 상황 | 교훈 | 참고 |
|------|------|------|
| 큰 UI refactor 앞 CI 안전망 | 3~4일 규모 UI 작업 착수 전 30분 PR 로 lint/type 게이트 선행. 백엔드 `backend-lint`(PR #22) 도입 직후 PR #23·#24·#25 가 게이트 덕에 안전하게 쌓인 것과 같은 레버리지 | `.github/workflows/ci.yml` `frontend-lint` |
| CI job 대칭 패턴 | backend-lint/test 쌍과 동일하게 frontend-lint/build 쌍 구성. `needs: [X-lint]` 로 풀 빌드 앞단에서 빠른 실패 | `frontend-build` needs |
| eslint + tsc 별도 스텝 | CI 로그에서 lint vs type 에러 즉시 구분. `next build` 는 둘 다 포함하지만 `// @ts-ignore` 우회 가능 → 독립 `tsc --noEmit` 스텝이 더 엄격 | `type-check` script |

### KisAuthError 4xx/5xx 분리 (PR #24, 2026-04-22)

| 상황 | 교훈 | 참고 |
|------|------|------|
| 외부 API 오류 일괄 502 매핑 | "credential 거부(401/403)" 와 "업스트림 장애(5xx/네트워크)" 는 사용자 조치가 다름 → 예외 타입으로 분리해 4xx/5xx 각각 매핑. 서브클래스 패턴(`KisCredentialRejectedError(KisAuthError)`)으로 타입 계층 + 도메인 계층 각각 2쌍 | `portfolio.py` `_credential_error_to_http` |
| HTTP 401 vs 400 선택 | "우리 서버 auth 실패" = 401, "우리 서버는 요청을 이해했지만 업스트림이 사용자 credential 거부" = **400** 이 적절. 401 은 FE 가 우리 admin API 인증 실패로 오해 유도 | 리뷰어 판단 — 422 도 semantics 불일치 |
| 예외 메시지에 원 응답 body 포함 금지 | Adapter 예외가 UseCase·Router 를 거쳐 `HTTPException.detail` 로 사용자 노출 → PR #20 로깅 마스킹 파이프라인 우회. `body=` 는 DEBUG 로그로만 분리 | `kis_client.py` raise 지점 4곳 |
| 서브클래스 catch 순서 | `except KisCredentialRejectedError` 를 `except KisClientError` **앞** 에 둬야 서브클래스가 먼저 잡힘. 세 UseCase 모두 동일 패턴 적용 일관성 | `portfolio_service.py` `except` 블록 3곳 |
| 테스트: 서브클래스 오탐 방지 | `pytest.raises(KisAuthError)` 는 서브클래스도 매칭하므로 "base 타입만" 을 검증하려면 `exc_info.value` 에 `isinstance` 로 명시 negative 단언 | `test_token_500_raises_base_auth_error_not_rejection` |

### Hexagonal + Sync UseCase mock/real 분리 (PR #23, 2026-04-22)

| 상황 | 교훈 | 참고 |
|------|------|------|
| infra DTO re-export 역방향 의존 | Application layer 가 DTO 를 소유해야 Hexagonal 경계 정합. repository 가 application/dto 를 import 해서 반환하는 방향이 올바름 | `app/application/dto/credential.py` |
| Optional 파라미터 RuntimeError 퇴화 | `kis_client \| None` + `credential_repo \| None` 묶음 → 런타임 검증 패턴은 타입 안전성 없음. 분기별 UseCase 클래스로 분리해 컴파일 타임 강제 | `SyncPortfolioFromKis(Mock\|Real)UseCase` |
| 공통 헬퍼 파라미터 타입 좁히기 | 모듈 헬퍼가 여러 UseCase 에서 호출될 때 분기 식별자(`connection_type`) 를 `str` 로 열어두면 임의 값이 DTO 에 흘러듬. `Literal[...]` 로 좁히고 caller 가 리터럴을 명시 전달 | `KisConnectionType = Literal[...]` |
| 테스트 의미 회귀 감지 | 단일 UseCase → 분리 시 기존 테스트가 "다른 이유로 PASS" 하는 함정. 예: `test_sync_kis_rest_real_requires_real_environment` 가 `UnsupportedConnectionError` 로 먼저 실패해 환경 검증을 실제론 테스트 안 함. 분리 후 real UseCase 로 전환하고 `get_decrypted` monkeypatch AssertionError 로 **순서** 까지 단언 | `test_portfolio.py` |

### CI lint/type 게이트 (PR #22, 2026-04-22)

| 상황 | 교훈 | 참고 |
|------|------|------|
| ruff format 미도입 레포 | CI 게이트 추가 PR 시작 시 98 파일 포매팅 부채 존재 가능성 확인 → `format .` 을 같은 PR 에 묶어 한 번에 정리 | `backend-lint` job |
| pre-existing mypy 부채 | `app/` 범위로만 strict 게이트. tests/scripts 는 mock 다량으로 ROI 낮음 → 향후 확대 후보 | mypy `[tool.mypy]` 전역 strict |
| lint job 을 test 앞에 | `backend-test` 가 `needs: [backend-lint]` — 1~2초 내 빠르게 실패 신호 제공, 불필요한 testcontainers 기동 회피 | `.github/workflows/ci.yml` |
| 리스트 컴프리헨션 내 narrowing | `dict.get()` 두 번 호출해도 mypy 는 narrowing 불가 → `for` 루프로 풀어 로컬 변수 1회 바인딩 | `signals.py` L86 |

### 🆕 KIS sync 시리즈 (PR #12~#16, 2026-04, Python 스택)

| 상황 | 교훈 | 참고 |
|------|------|------|
| 다단계 외부 API 연동 (6 PR) | `docs/*-plan.md` 설계서 선행 + 사용자 승인 → PR 단위로 위험 낮은 것부터 진입 | `docs/kis-real-account-sync-plan.md` |
| 외부 호출 0 단계적 해제 | PR 1(엑셀) → PR 2(어댑터 분기) → PR 3(저장소) → PR 4(등록 API/UI) → PR 5(실 호출 개시) 로 **신뢰 빌드업** | — |
| 민감 자격증명 저장 | Fernet 대칭암호화 + Key 회전 대비 `key_version` 필드 + `DO $$` downgrade 가드 | PR #14 |
| 예외 계층 래핑 | `InvalidToken` → `DecryptionFailedError` 로 래핑해 스택트레이스에 bytes/plaintext 노출 차단 | PR #14 |
| 마스킹 뷰 | **비례 길이** 마스킹 (`(len - 4)` 불릿 + tail 4) — 고정 4개 불릿은 짧은 값 노출 비율 과다 | PR #15 |
| HTTP 시맨틱 501 vs 503 | "미구현 기능" 은 501, "일시 장애" 는 503 — 재시도 루프 유발 방지 | PR #13 |
| `python -O` 대응 | 프로덕션 코드의 `assert` 전면 금지 → `if not X: raise RuntimeError(...)` | PR #15 |
| 요청 스코프 팩토리 DI | 계좌별 credential 이 달라 프로세스 공유 불가 → `Callable[[Creds], Client]` 팩토리 주입 | PR #16 |
| smoke 마커 CI skip | `@pytest.mark.requires_kis_real_account` + pyproject `addopts = [..., "-m", "not ..."]` | PR #16 |
| 예외 매퍼 네이밍 | `_raise_for_*` = 내부 raise, `_*_to_http` = return (caller 가 raise) — 이름과 동작 일치 | PR #16 |
| FE dead code 제거 | `adminCall` 이 !ok 를 throw → 응답 `ok: true` 리터럴로 좁혀 타입 계약 강제 | PR #16 |

### Sprint 1~3 (Java 스택 이전 시대, 참고용 보존)

| 상황 | 교훈 | 기록 위치 |
|------|------|-----------|
| 코드리뷰 CRITICAL 발견 | 반영 → 커밋 순서 엄수 | 의사결정 D-3.5, D-3.11 |
| N+1 쿼리 17,500건 | 일자별 벌크 조회로 전환 | Sprint 4 계획 Task 1 |
| Testcontainers 컨텍스트 충돌 | 싱글톤 패턴으로 해결 | 의사결정 D-3.10 |
| Hexagonal 경계 위반 | Config → Service 위임 | 의사결정 D-3.12 |
| 1인 → 팀 확장 가정 | pipeline/ 커밋 대상화 | 세션 2026-04-17 |

### 공통 워크플로우 (검증됨)

본 프로젝트에서 반복적으로 증명된 SDLC 루틴:

1. **설계 승인 루프**: 복잡 과제는 `docs/*-plan.md` 선행 작성 + 열린 질문 명시 → 사용자 결정 → 착수
2. **`/ted-run` 파이프라인**: 구현 → 병렬 리뷰(언어별 reviewer) → 빌드검증 → 핸드오프/커밋/PR
3. **Feature branch + Squash Merge**: `feature/<topic>` → push → `gh pr create` → CI 4/4 PASS 확인 → `gh pr merge --squash --delete-branch`
4. **CI 필수 통과 게이트**: Backend Test / Frontend Build / Docker Build / E2E (gitignore·문서 단독 변경 시 e2e skip path filter 가능)
5. **매 세션 마감 `/handoff`**: `HANDOFF.md` 에 당일 결정·미커밋·다음 액션·알려진 부채 명시 → 차기 세션 Compaction 안전망
6. **커밋 메시지 한글 + Co-Authored-By**: `.claude/settings.local.json` 에 `includeCoAuthoredBy: true` 로 자동 부여

**이 가이드를 업데이트할 타이밍**:
- 신규 PR 시리즈 완료 시 실전 교훈 추가 (위 표 형식 유지)
- 새 슬래시 커맨드 도입 시 치트시트 갱신 (§5)
- Compaction 방어 패턴 개선 시 §7 보강
- 스택 변경 시 §2 표 + §8 리뷰어 매핑 갱신
