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
| Git | `init`, worktree 지원 |
| 기본 스택 | Java 21, Node 20+, PostgreSQL 16, Docker |

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
- `/review` → java-reviewer, typescript-reviewer 에이전트가 자동 스캔
- Phase 4의 Verify 게이트는 Critical 0건이 필수 조건
- 배치 크기가 크면 도메인별로 나눠서 리뷰

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

Sprint 1~3에서 체득한 패턴:

| 상황 | 교훈 | 기록 위치 |
|------|------|-----------|
| 코드리뷰 CRITICAL 발견 | 반영 → 커밋 순서 엄수 | 의사결정 D-3.5, D-3.11 |
| N+1 쿼리 17,500건 | 일자별 벌크 조회로 전환 | Sprint 4 계획 Task 1 |
| Testcontainers 컨텍스트 충돌 | 싱글톤 패턴으로 해결 | 의사결정 D-3.10 |
| Hexagonal 경계 위반 | Config → Service 위임 | 의사결정 D-3.12 |
| 1인 → 팀 확장 가정 | pipeline/ 커밋 대상화 | 이 세션(2026-04-17) |

**이 가이드를 업데이트할 타이밍**:
- 신규 스프린트 완료 시 실전 교훈 추가
- 새 슬래시 커맨드 도입 시 치트시트 갱신
- Compaction 방어 패턴 개선 시 섹션 7 보강
