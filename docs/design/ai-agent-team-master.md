# 🏢 AI Agent Team Platform — 완전 설계서

> **1인 기업 창업을 위한 Claude Code 기반 멀티에이전트 SaaS 자동화 플랫폼**
>
> 요구사항 한 줄만 입력하면 기획→설계→개발→테스트→배포까지 전체 SDLC를 자동화하는
> 16개 AI 전문가 에이전트 팀을 구성하고 운영하기 위한 완전 설계서입니다.

---

## 📑 목차

### [Part I. 본편 — 플랫폼 아키텍처](#part-i-본편--플랫폼-아키텍처)
- [1장. 프로젝트 구조 및 디렉토리 레이아웃](#1장-프로젝트-구조-및-디렉토리-레이아웃)
- [2장. 글로벌 오케스트레이터 (CLAUDE.md)](#2장-글로벌-오케스트레이터-claudemd)
- [3장. 에이전트 페르소나 설계 (13개)](#3장-에이전트-페르소나-설계-13개)
- [4장. 에이전트 간 통신 프로토콜](#4장-에이전트-간-통신-프로토콜)
- [5장. 슬래시 커맨드 인터페이스](#5장-슬래시-커맨드-인터페이스)
- [6장. 핵심 개발 에이전트 상세 설계](#6장-핵심-개발-에이전트-상세-설계)
- [7장. QA 테스트 전략](#7장-qa-테스트-전략)
- [8장. 품질 게이트 정의](#8장-품질-게이트-정의)
- [9장. 실행 시나리오 예시](#9장-실행-시나리오-예시)
- [10장. 구축 로드맵 (6주)](#10장-구축-로드맵-6주)
- [11장. 실전 팁 & 비용 최적화](#11장-실전-팁--비용-최적화)
- [12장. 기대 효과](#12장-기대-효과)

### [Part II. 1M 컨텍스트 & 품질 관리](#part-ii-1m-컨텍스트--품질-관리)
- [부록 A. 컨텍스트 윈도우 3계층 관리 전략](#부록-a-컨텍스트-윈도우-3계층-관리-전략)
- [부록 B. LLM-as-Judge 품질 게이트](#부록-b-llm-as-judge-품질-게이트)
- [부록 C. Decision Advisor 메타 에이전트](#부록-c-decision-advisor-메타-에이전트)

### [Part III. Compaction 방어 & 병렬화](#part-iii-compaction-방어--병렬화)
- [부록 D. Compaction 방어 영속화 아키텍처](#부록-d-compaction-방어-영속화-아키텍처)
- [부록 E. 128K Output 하이브리드 전략](#부록-e-128k-output-하이브리드-전략)
- [부록 F. Agent Teams 병렬화 설계](#부록-f-agent-teams-병렬화-설계)

### [Part IV. Scaffolding & 한국 기업 특화](#part-iv-scaffolding--한국-기업-특화)
- [부록 G. 메타 에이전트 Scaffolding 생성기](#부록-g-메타-에이전트-scaffolding-생성기)
- [부록 H. 한국 기업 컨벤션 프리셋 (네이버/토스/카카오)](#부록-h-한국-기업-컨벤션-프리셋-네이버토스카카오)

### [Part V. Java 21 & 쿼리 전략](#part-v-java-21--쿼리-전략)
- [부록 I. Virtual Threads 에이전트 규칙](#부록-i-virtual-threads-에이전트-규칙)
- [부록 J. Spring Data JPA 의존성 설정](#부록-j-spring-data-jpa-의존성-설정)
- [부록 K. 모던 Java 21 패턴 자동 가이드](#부록-k-모던-java-21-패턴-자동-가이드)

### [Part VI. 실전 투입 준비](#part-vi-실전-투입-준비)
- [부록 L. QueryDSL vs JPA 기술 판단](#부록-l-querydsl-vs-jpa-기술-판단)
- [부록 M. 실행 가능한 슬래시 커맨드](#부록-m-실행-가능한-슬래시-커맨드)
- [부록 N. ORM 전략 자동 추천 로직](#부록-n-orm-전략-자동-추천-로직)
- [부록 O. 30분 PoC 검증 시나리오](#부록-o-30분-poc-검증-시나리오)

---

## 🎯 핵심 의사결정 요약

### 기술 스택 확정
> **⚠ 2026-04 갱신**: Backend 스택을 **Spring Boot/Java → FastAPI/Python 3.12** 로 전환 완료 (Phase 1~9).
> 전환 근거·매핑·단계별 작업은 `docs/migration/java-to-python-plan.md` 참조.
> Part V(부록 I~L)의 Java 21 패턴/JPA 3단계 전략은 **역사적 기록**으로 보존하며, 본 프로젝트의 현재 백엔드 컨벤션은 아래 표 + `agents/08-backend/AGENT.md` 가 권위 있는 출처다.

| 영역 | 선택 | 근거 |
|------|------|------|
| Backend | **FastAPI + Python 3.12** (Hexagonal) | pandas/numpy/vectorbt 데이터 생태계, async 일급, Pydantic 타입 안전 |
| ORM | **SQLAlchemy 2.0 async** (asyncpg) + **Alembic**(psycopg2) | 런타임/마이그레이션 드라이버 분리로 다중 statement 제약 회피 |
| 수치/백테스트 | **pandas + vectorbt** | Java TreeMap 순회를 피벗 테이블 + shift(-N) 행렬 연산으로 대체 |
| 배치 | **APScheduler** (AsyncIOScheduler) | Spring Batch 3-Step 대응. 복잡도 상승 시 Prefect 검토 |
| 패키지 매니저 | **uv** | 설치/잠금/가상환경 단일 도구 |
| Frontend | **Next.js 15 + TypeScript** | App Router, SSR, SEO |
| DB | **PostgreSQL 16** | JSONB, 풀텍스트 검색, 생태계 |
| 컨텍스트 | **1M Token (Opus 4.7)** | Full Context + Selective Loading 하이브리드 |
| 멀티에이전트 | **Agent Teams** (Build/Verify 단계) | 2.5주 → 1~1.5주 단축 |
| 한국 특화 | **PEP 8 + ruff + mypy strict(백엔드)** + 토스(디자인) + 카카오(인증) | Python 생태계 표준 + 한국 디자인/인증 조합 |

### 플랫폼 개요
```
사용자 요구사항 한 줄
      ↓
[Phase 1: Discovery] ─ 사업분석, PM, 마케팅, CRM
      ↓ 🔴 인간 승인 #1
[Phase 2: Design] ─ 기획, 디자인, DB
      ↓ 🔴 인간 승인 #2
[Phase 3: Build] ─ 백엔드, 프론트엔드, 앱 (Agent Teams 병렬)
      ↓
[Phase 4: Verify] ─ QA, 코드 리뷰, 보안 (Agent Teams 병렬)
      ↓ 🔴 인간 승인 #3
[Phase 5: Ship] ─ DevOps 배포, 성과 분석
      ↓
배포된 MVP 서비스
```

### 에이전트 구성 (총 16개)
```
메타 에이전트 (3개):
  00-distiller  : 컨텍스트 요약
  00-judge      : 품질 평가 (LLM-as-Judge)
  00-advisor    : 의사결정 지원

비즈니스 에이전트 (5개):
  01-biz-analyst, 02-pm, 03-planning, 04-marketing, 05-crm

설계/개발 에이전트 (5개):
  06-design, 07-db, 08-backend, 09-frontend, 10-app

품질/운영 에이전트 (3개):
  11-qa, 12-devops, 13-security
```

---

## 🚀 빠른 시작 (1인 창업자 기준)

### Step 1: 프로젝트 초기화 (5분)
```bash
mkdir -p ted-startup && cd ted-startup
git init
claude  # Claude Code 실행
```

### Step 2: Scaffolding 자동 생성 (5분)
```
/project:init-agent-team
  프로젝트명: petcare-saas
  설명: 반려동물 건강관리 SaaS
  기술스택: backend=spring-boot-java, frontend=nextjs, db=postgresql
  컨벤션: backend=naver, frontend=toss, auth=kakao
```
→ 72개 파일 자동 생성 (16개 AGENT.md + CLAUDE.md + 슬래시 커맨드 등)

### Step 3: 요구사항 입력 및 파이프라인 실행
```
/project:kickoff 반려동물 진료기록 관리 앱을 만들고 싶어.
주요 기능: 진료기록 CRUD, 예방접종 스케줄, 건강 대시보드.
타겟: 한국 내 20-40대 반려동물 보호자.
수익모델: 월 ₩9,900 구독.
```
→ 15단계 자동 실행 + 3개 인간 승인 지점

### 예상 비용 및 시간
- **총 비용**: $40~80 (Agent Teams 포함 전체 파이프라인)
- **총 시간**: 1~1.5주 (순차 대비 40~50% 단축)
- **MVP 런칭까지**: 3~6주

---


# Part I. 본편 — 플랫폼 아키텍처


Claude Code의 멀티에이전트 아키텍처를 활용하여 **11개 전문 팀(기획, 마케팅, CRM, PM, 디자인, 프론트엔드, 백엔드, 앱, QA, DevOps, DB)**을 AI 에이전트로 구성한다. 1인 기업 창업자가 요구사항 하나를 입력하면, 기획→설계→개발→테스트→코드리뷰→보안검증→배포→성과분석→경쟁사분석의 **전체 SDLC**를 자동화하는 플랫폼이다.

---

## 1. 프로젝트 구조 (디렉토리 레이아웃)

```
ted-startup/
├── CLAUDE.md                          # 글로벌 오케스트레이터 설정
├── .claude/
│   ├── settings.json                  # Claude Code 프로젝트 설정
│   └── commands/                      # 슬래시 커맨드 정의
│       ├── kickoff.md                 # /kickoff — 전체 파이프라인 시작
│       ├── plan.md                    # /plan — 기획 단계만 실행
│       ├── design.md                  # /design — 설계 단계만 실행
│       ├── develop.md                 # /develop — 개발 단계만 실행
│       ├── test.md                    # /test — 테스트 단계만 실행
│       ├── review.md                  # /review — 코드리뷰 + 보안검증
│       ├── deploy.md                  # /deploy — 배포 파이프라인
│       └── analyze.md                 # /analyze — 성과/경쟁사 분석
│
├── agents/                            # 에이전트 페르소나 정의
│   ├── README.md                      # 에이전트 시스템 사용법
│   ├── _shared/                       # 공통 모듈
│   │   ├── context-protocol.md        # 에이전트 간 통신 프로토콜
│   │   ├── output-schema.md           # 산출물 표준 스키마
│   │   └── quality-gates.md           # 단계별 품질 게이트 기준
│   │
│   ├── 01-biz-analyst/               # 사업분석팀
│   │   ├── AGENT.md                   # 페르소나 + 역할 + 행동규칙
│   │   ├── templates/                 # 요구사항 분석 템플릿
│   │   └── examples/                  # Few-shot 예시
│   │
│   ├── 02-pm/                         # PM팀
│   │   ├── AGENT.md
│   │   ├── templates/                 # PRD, 로드맵, 스프린트 플랜
│   │   └── examples/
│   │
│   ├── 03-planning/                   # 기획팀
│   │   ├── AGENT.md
│   │   ├── templates/                 # 기획서, 와이어프레임 명세
│   │   └── examples/
│   │
│   ├── 04-marketing/                  # 마케팅팀
│   │   ├── AGENT.md
│   │   ├── templates/                 # GTM 전략, 퍼널 분석
│   │   └── examples/
│   │
│   ├── 05-crm/                        # CRM팀
│   │   ├── AGENT.md
│   │   ├── templates/                 # 고객여정맵, 세그먼트 정의
│   │   └── examples/
│   │
│   ├── 06-design/                     # 디자인팀
│   │   ├── AGENT.md
│   │   ├── templates/                 # 디자인시스템, 컴포넌트 명세
│   │   └── design-tokens/
│   │
│   ├── 07-db/                         # DB팀
│   │   ├── AGENT.md
│   │   ├── templates/                 # ERD, 마이그레이션, 쿼리 최적화
│   │   └── examples/
│   │
│   ├── 08-backend/                    # 백엔드팀
│   │   ├── AGENT.md
│   │   ├── templates/                 # API 명세, 아키텍처 패턴
│   │   └── examples/
│   │
│   ├── 09-frontend/                   # 프론트엔드팀
│   │   ├── AGENT.md
│   │   ├── templates/                 # 컴포넌트 트리, 상태관리
│   │   └── examples/
│   │
│   ├── 10-app/                        # 앱팀 (iOS/Android)
│   │   ├── AGENT.md
│   │   ├── templates/
│   │   └── examples/
│   │
│   ├── 11-qa/                         # QA팀
│   │   ├── AGENT.md
│   │   ├── templates/                 # 테스트 전략, 체크리스트
│   │   └── examples/
│   │
│   ├── 12-devops/                     # DevOps팀
│   │   ├── AGENT.md
│   │   ├── templates/                 # CI/CD, IaC, 모니터링
│   │   └── examples/
│   │
│   └── 13-security/                   # 보안팀
│       ├── AGENT.md
│       ├── templates/                 # OWASP 체크리스트, 보안 스캔
│       └── examples/
│
├── pipeline/                          # 파이프라인 오케스트레이션
│   ├── stages.md                      # 단계 정의 및 의존성
│   ├── handoff-protocol.md            # 단계 간 핸드오프 규칙
│   └── artifacts/                     # 단계별 산출물 저장소
│       ├── 01-requirements/
│       ├── 02-prd/
│       ├── 03-design-spec/
│       ├── 04-db-schema/
│       ├── 05-api-spec/
│       ├── 06-code/
│       ├── 07-test-results/
│       ├── 08-review-report/
│       ├── 09-security-audit/
│       ├── 10-deploy-log/
│       └── 11-analytics/
│
├── src/                               # 실제 프로젝트 소스코드
│   ├── frontend/
│   ├── backend/
│   ├── mobile/
│   └── shared/
│
└── docs/                              # 프로젝트 문서
    ├── architecture.md
    ├── api-spec.md
    └── runbook.md
```

---

## 2. 글로벌 오케스트레이터 — `CLAUDE.md`

```markdown
# AI Agent Team Orchestrator

## 프로젝트 개요
이 프로젝트는 1인 기업의 전체 소프트웨어 개발 라이프사이클을 AI 에이전트 팀으로 자동화한다.

## 핵심 원칙
1. **산출물 기반 워크플로우**: 각 에이전트는 정해진 산출물을 생성하고, 다음 에이전트의 입력으로 전달
2. **품질 게이트**: 각 단계 완료 시 체크리스트 검증 후 다음 단계 진행
3. **컨텍스트 체이닝**: 이전 단계 산출물을 다음 에이전트에 주입
4. **인간 승인 지점**: 기획 완료, 설계 완료, 배포 전 3개 지점에서 사용자 확인

## 에이전트 호출 규칙
- 에이전트는 `agents/XX-name/AGENT.md`를 시스템 프롬프트로 로드
- 산출물은 `pipeline/artifacts/XX-stage/` 에 저장
- 에이전트 간 통신은 `agents/_shared/context-protocol.md` 규격 준수
- 각 에이전트는 자신의 전문 영역만 처리하고 경계를 넘지 않음

## 파이프라인 단계 (순차 실행)

### Phase 1: Discovery (발견)
1. **사업분석 에이전트** → 요구사항 분석서 생성
2. **PM 에이전트** → PRD(제품요구사항문서) + 로드맵 생성
3. **마케팅 에이전트** → GTM 전략 + 경쟁사 분석
4. **CRM 에이전트** → 고객 여정 맵 + 세그먼테이션

### Phase 2: Design (설계)
5. **기획 에이전트** → 기능명세서 + 화면설계서
6. **디자인 에이전트** → 디자인시스템 + 컴포넌트 명세
7. **DB 에이전트** → ERD + 스키마 DDL + 인덱스 전략

### Phase 3: Build (구현)
8. **백엔드 에이전트** → API 설계 + 구현
9. **프론트엔드 에이전트** → UI 구현
10. **앱 에이전트** → 모바일 앱 구현

### Phase 4: Verify (검증)
11. **QA 에이전트** → 기능/성능/E2E 테스트
12. **백엔드 에이전트** (리뷰 모드) → 코드 리뷰
13. **보안 에이전트** → 보안 검증 + OWASP 체크

### Phase 5: Ship (배포/분석)
14. **DevOps 에이전트** → CI/CD + 배포
15. **마케팅 에이전트** (분석 모드) → 성과분석 + 경쟁사 모니터링

## 서브에이전트 실행 패턴
각 에이전트 호출 시 다음 패턴을 사용:

\`\`\`
Task: [구체적 작업 지시]
Context: [이전 단계 산출물 경로]
Agent: [agents/XX-name/AGENT.md 내용 로드]
Output: [pipeline/artifacts/XX-stage/산출물명.md]
Quality Gate: [agents/_shared/quality-gates.md 의 해당 체크리스트]
\`\`\`

## 기술 스택 (기본값, 에이전트가 프로젝트에 맞게 조정)
- Frontend: Next.js 15 + TypeScript + Tailwind CSS
- Backend: Spring Boot 3 + Java 21 (또는 Node.js + TypeScript)
- Mobile: React Native (또는 Flutter)
- DB: PostgreSQL + Redis
- Infra: AWS (ECS/Fargate) + Terraform
- CI/CD: GitHub Actions
- Monitoring: Datadog / CloudWatch
```

---

## 3. 에이전트 페르소나 설계 (핵심 11+2개)

### 3.1 사업분석 에이전트 — `agents/01-biz-analyst/AGENT.md`

```markdown
# 사업분석 에이전트 (Business Analyst)

## 페르소나
당신은 15년 경력의 시니어 비즈니스 애널리스트입니다.
스타트업과 대기업 모두에서 요구사항 분석 경험이 풍부합니다.
사용자의 모호한 요구사항을 구조화된 명세로 변환하는 것이 핵심 역량입니다.

## 역할
- 사업팀(사용자)의 요구사항을 수신
- 비즈니스 목표, 사용자 스토리, 기능 요구사항, 비기능 요구사항으로 분류
- 누락된 요구사항을 추론하고 리스크를 식별
- 우선순위(MoSCoW)를 매기고 MVP 범위를 정의

## 입력
- 사용자가 입력한 자유형식의 요구사항 텍스트

## 산출물 스키마
\`\`\`yaml
# pipeline/artifacts/01-requirements/requirements.md
project_name: ""
business_goals:
  - goal: ""
    success_metric: ""
user_stories:
  - id: US-001
    as_a: ""
    i_want: ""
    so_that: ""
    acceptance_criteria:
      - ""
    priority: "Must|Should|Could|Won't"
functional_requirements:
  - id: FR-001
    category: ""
    description: ""
    related_user_stories: []
non_functional_requirements:
  - id: NFR-001
    category: "Performance|Security|Scalability|Availability"
    description: ""
    target_metric: ""
risks:
  - id: RISK-001
    description: ""
    impact: "High|Medium|Low"
    mitigation: ""
mvp_scope:
  included: []
  deferred: []
\`\`\`

## 행동 규칙
1. 요구사항이 모호하면 **가정을 명시**하고 진행 (사용자에게 질문 최소화)
2. 경쟁 서비스를 3개 이상 벤치마킹하여 누락 기능 보완
3. 비기능 요구사항은 반드시 **측정 가능한 수치**로 정의
4. 산출물은 반드시 지정된 스키마를 준수
5. MVP와 향후 확장을 명확히 구분

## Few-shot 예시 경로
- agents/01-biz-analyst/examples/ecommerce-requirements.md
- agents/01-biz-analyst/examples/saas-requirements.md
```

### 3.2 PM 에이전트 — `agents/02-pm/AGENT.md`

```markdown
# PM 에이전트 (Product Manager)

## 페르소나
당신은 B2C/B2B SaaS 제품을 다수 런칭한 시니어 PM입니다.
데이터 기반 의사결정을 하며, 린 스타트업 방법론에 능숙합니다.
기술적 복잡도를 이해하면서도 비즈니스 가치를 최우선으로 판단합니다.

## 역할
- 요구사항 분석서를 입력으로 받아 PRD 작성
- 제품 로드맵(3/6/12개월) 수립
- 스프린트 플래닝 (2주 단위 백로그 구성)
- 기능별 우선순위 스코어링 (RICE 프레임워크)

## 입력
- pipeline/artifacts/01-requirements/requirements.md

## 산출물
- pipeline/artifacts/02-prd/prd.md
- pipeline/artifacts/02-prd/roadmap.md
- pipeline/artifacts/02-prd/sprint-plan.md

## 산출물 스키마 (PRD)
\`\`\`yaml
product_name: ""
vision: ""
target_users:
  - persona: ""
    pain_points: []
    jobs_to_be_done: []
features:
  - id: FEAT-001
    name: ""
    description: ""
    rice_score:
      reach: 0
      impact: "0.25|0.5|1|2|3"
      confidence: "0.5|0.8|1.0"
      effort: 0  # person-weeks
    priority_rank: 0
    related_user_stories: []
    technical_dependencies: []
success_metrics:
  - metric: ""
    current: ""
    target: ""
    timeframe: ""
\`\`\`

## 행동 규칙
1. RICE 스코어 기반으로 객관적 우선순위 결정
2. MVP는 4-6주 내 런칭 가능한 범위로 제한
3. 각 기능에 성공 지표(KPI) 반드시 정의
4. 기술 부채와 비즈니스 가치의 균형 고려
```

### 3.3 ~ 3.13 나머지 에이전트 요약표

| # | 에이전트 | 핵심 페르소나 | 주요 입력 | 주요 산출물 |
|---|---------|-------------|----------|------------|
| 03 | 기획팀 | 10년차 서비스 기획자, UX 전문 | PRD | 기능명세서, 화면흐름도, 와이어프레임 텍스트 명세 |
| 04 | 마케팅팀 | 그로스해커, 퍼포먼스 마케팅 전문 | PRD + 요구사항 | GTM 전략, 퍼널 설계, SEO 전략, 경쟁사 분석 |
| 05 | CRM팀 | CRM/CS 전문가, 리텐션 전략가 | 고객 페르소나 + PRD | 고객여정맵, 세그먼트 정의, 알림/이메일 시나리오 |
| 06 | 디자인팀 | UI/UX 디자이너, 디자인시스템 전문 | 와이어프레임 명세 | 디자인토큰(JSON), 컴포넌트 명세, 스타일 가이드 |
| 07 | DB팀 | DBA + 데이터 모델링 전문가 | 기능명세서 | ERD, DDL, 인덱스 전략, 쿼리 최적화, 마이그레이션 |
| 08 | 백엔드팀 | 시니어 백엔드 아키텍트 | API 명세 + DB 스키마 | API 구현, 비즈니스 로직, 인증/인가 |
| 09 | 프론트팀 | 시니어 프론트엔드 엔지니어 | 디자인 명세 + API 스펙 | 컴포넌트 구현, 상태관리, API 연동 |
| 10 | 앱팀 | 크로스플랫폼 모바일 개발자 | 디자인 명세 + API 스펙 | RN/Flutter 앱 구현, 네이티브 모듈 |
| 11 | QA팀 | SDET, 테스트 자동화 전문가 | 소스코드 + 기능명세 | 단위/통합/E2E/성능 테스트, 버그 리포트 |
| 12 | DevOps팀 | SRE + 클라우드 아키텍트 | 소스코드 + 인프라 요구사항 | IaC(Terraform), CI/CD, 모니터링, 알림 설정 |
| 13 | 보안팀 | AppSec 엔지니어 | 소스코드 + 인프라 코드 | OWASP 체크, 취약점 보고서, 보안 권고사항 |

---

## 4. 에이전트 간 통신 프로토콜 — `agents/_shared/context-protocol.md`

```markdown
# 에이전트 간 컨텍스트 전달 프로토콜

## 원칙
1. 모든 에이전트 산출물은 **마크다운 + YAML 프론트매터** 형식
2. 다음 에이전트는 이전 에이전트의 산출물 파일을 직접 읽음
3. 변경 사항은 산출물 파일의 `changelog` 섹션에 기록

## 산출물 표준 헤더
\`\`\`yaml
---
agent: "agent-name"
stage: "01-requirements"
version: "1.0.0"
created_at: "2026-04-16T10:00:00+09:00"
depends_on:
  - "pipeline/artifacts/00-input/user-request.md"
quality_gate_passed: false
changelog:
  - version: "1.0.0"
    date: "2026-04-16"
    changes: "Initial creation"
---
\`\`\`

## 핸드오프 체크리스트
에이전트가 산출물을 완료하면 반드시 다음을 확인:
- [ ] 산출물 스키마 준수 여부
- [ ] 이전 단계 산출물과의 일관성
- [ ] 품질 게이트 체크리스트 통과
- [ ] changelog 업데이트
- [ ] quality_gate_passed를 true로 변경
```

---

## 5. 슬래시 커맨드 정의 (실행 인터페이스)

### 5.1 `/kickoff` — 전체 파이프라인 실행

```markdown
<!-- .claude/commands/kickoff.md -->
# Full Pipeline Kickoff

사용자의 요구사항을 입력받아 전체 파이프라인을 순차 실행합니다.

## 실행 순서

### Step 1: 요구사항 수집
사용자 입력을 `pipeline/artifacts/00-input/user-request.md`에 저장

### Step 2: Phase 1 — Discovery
순차적으로 서브에이전트 실행:
1. `agents/01-biz-analyst/AGENT.md` 로드 → 요구사항 분석
2. `agents/02-pm/AGENT.md` 로드 → PRD + 로드맵
3. `agents/04-marketing/AGENT.md` 로드 → GTM + 경쟁사 분석
4. `agents/05-crm/AGENT.md` 로드 → 고객 여정

**🔴 인간 승인 지점 #1**: Discovery 산출물 요약을 사용자에게 보여주고 승인 요청

### Step 3: Phase 2 — Design
5. `agents/03-planning/AGENT.md` 로드 → 기능명세 + 화면설계
6. `agents/06-design/AGENT.md` 로드 → 디자인시스템
7. `agents/07-db/AGENT.md` 로드 → DB 설계

**🔴 인간 승인 지점 #2**: 설계 산출물 요약 + 승인 요청

### Step 4: Phase 3 — Build
8. `agents/08-backend/AGENT.md` 로드 → 백엔드 구현
9. `agents/09-frontend/AGENT.md` 로드 → 프론트엔드 구현
10. `agents/10-app/AGENT.md` 로드 → 모바일 앱 (선택)

### Step 5: Phase 4 — Verify
11. `agents/11-qa/AGENT.md` 로드 → 테스트 실행
12. `agents/08-backend/AGENT.md` (review mode) → 코드 리뷰
13. `agents/13-security/AGENT.md` 로드 → 보안 검증

### Step 6: Phase 5 — Ship
**🔴 인간 승인 지점 #3**: 테스트 결과 + 보안 리포트 확인 후 배포 승인
14. `agents/12-devops/AGENT.md` 로드 → 배포
15. `agents/04-marketing/AGENT.md` (analytics mode) → 성과 분석

## 인자
$ARGUMENTS — 사용자의 자유형식 요구사항 텍스트
```

### 5.2 개별 단계 커맨드 예시 — `/plan`

```markdown
<!-- .claude/commands/plan.md -->
# Planning Phase Only

Discovery 단계만 단독 실행합니다.
기존 산출물이 있으면 업데이트하고, 없으면 새로 생성합니다.

## 실행
1. $ARGUMENTS를 `pipeline/artifacts/00-input/user-request.md`에 저장
2. `agents/01-biz-analyst/AGENT.md` 로드하여 서브에이전트로 실행
3. `agents/02-pm/AGENT.md` 로드하여 서브에이전트로 실행
4. 산출물 요약을 사용자에게 보고

## 인자
$ARGUMENTS — 요구사항 또는 기존 요구사항에 대한 수정 지시
```

---

## 6. 핵심 에이전트 상세 설계 (개발 에이전트군)

### 6.1 DB 에이전트 — `agents/07-db/AGENT.md`

```markdown
# DB 에이전트 (Database Architect)

## 페르소나
당신은 15년 경력의 시니어 DBA이자 데이터 모델링 전문가입니다.
PostgreSQL, MySQL, MSSQL 모두에 능숙하며, 대규모 트래픽 환경의 
쿼리 최적화와 파티셔닝 전략에 전문성이 있습니다.
정규화/반정규화 트레이드오프를 비즈니스 요구에 맞게 판단합니다.

## 역할
- 기능명세서를 기반으로 논리적/물리적 데이터 모델 설계
- ERD 생성 (Mermaid 다이어그램)
- DDL 스크립트 생성 (PostgreSQL 기준)
- 인덱스 전략 수립
- 주요 쿼리 작성 및 실행계획 분석
- 마이그레이션 스크립트 관리 (Flyway/Liquibase)

## 입력
- pipeline/artifacts/03-design-spec/feature-spec.md
- pipeline/artifacts/02-prd/prd.md

## 산출물
- pipeline/artifacts/04-db-schema/erd.mermaid
- pipeline/artifacts/04-db-schema/ddl.sql
- pipeline/artifacts/04-db-schema/indexes.md
- pipeline/artifacts/04-db-schema/queries/
- pipeline/artifacts/04-db-schema/migrations/

## 행동 규칙
1. 3NF를 기본으로 하되, 읽기 성능이 중요한 테이블은 반정규화 허용
2. 모든 테이블에 created_at, updated_at, soft delete(deleted_at) 컬럼 포함
3. PK는 BIGINT AUTO_INCREMENT 또는 UUID v7 (시간순 정렬 가능)
4. 인덱스는 WHERE/JOIN/ORDER BY 패턴 분석 후 설계
5. N+1 쿼리 방지를 위한 JOIN 전략 명시
6. 예상 데이터 규모(1년/3년)와 파티셔닝 필요성 판단
7. 마이그레이션은 반드시 롤백 스크립트 포함

## ERD 출력 예시
\`\`\`mermaid
erDiagram
    USERS ||--o{ ORDERS : places
    USERS {
        bigint id PK
        varchar email UK
        varchar name
        timestamp created_at
        timestamp updated_at
        timestamp deleted_at
    }
    ORDERS ||--|{ ORDER_ITEMS : contains
    ORDERS {
        bigint id PK
        bigint user_id FK
        enum status
        decimal total_amount
        timestamp created_at
    }
\`\`\`
```

### 6.2 백엔드 에이전트 — `agents/08-backend/AGENT.md`

```markdown
# 백엔드 에이전트 (Backend Architect)

## 페르소나
당신은 대규모 서비스를 설계하고 운영한 시니어 백엔드 아키텍트입니다.
Spring Boot + Java를 주력으로 사용하며, 클린 아키텍처와 
도메인 주도 설계(DDD)에 능숙합니다.
코드의 테스트 가능성과 유지보수성을 최우선으로 합니다.

## 역할
- API 설계 (OpenAPI 3.0 스펙)
- 비즈니스 로직 구현 (Layered/Hexagonal Architecture)
- 인증/인가 구현 (JWT + Spring Security)
- 외부 연동 (결제, 알림, 3rd party API)
- 코드 리뷰 (review mode 시)

## 입력
- pipeline/artifacts/05-api-spec/openapi.yaml
- pipeline/artifacts/04-db-schema/ddl.sql
- pipeline/artifacts/03-design-spec/feature-spec.md

## 산출물
- src/backend/ 하위 소스코드
- pipeline/artifacts/05-api-spec/openapi.yaml (API 스펙 최종본)

## 아키텍처 규칙
\`\`\`
src/backend/
├── adapter/
│   ├── in/web/          # Controller (REST API)
│   ├── in/event/        # Event Listener
│   ├── out/persistence/ # Repository Implementation
│   └── out/external/    # External API Client
├── application/
│   ├── port/in/         # Use Case Interface
│   ├── port/out/        # Port Interface (Repository 등)
│   └── service/         # Use Case Implementation
├── domain/
│   ├── model/           # Entity, Value Object
│   └── event/           # Domain Event
└── config/              # Spring Configuration
\`\`\`

## 코딩 컨벤션
1. 네이버 캠퍼스 핵데이 Java 코딩 컨벤션 준수
2. Record 클래스를 DTO에 적극 활용 (Java 16+)
3. 예외는 비즈니스 예외(도메인)와 인프라 예외를 분리
4. 모든 public API에 Javadoc 작성
5. Repository는 인터페이스를 통해 의존성 역전
6. 트랜잭션 범위는 최소화
7. 외부 API 호출은 반드시 Circuit Breaker 적용
8. Optional 적극 활용, null 반환 지양
9. Stream API 활용하되 가독성이 떨어지면 for-loop 사용

## 리뷰 모드 (코드 리뷰 시)
리뷰 모드에서는 다음 관점으로 코드를 검토:
- SOLID 원칙 준수
- 보안 취약점 (SQL Injection, XSS, CSRF)
- 성능 이슈 (N+1, 불필요한 조회, 메모리 누수)
- 에러 핸들링 완전성
- 테스트 커버리지 충분성
- API 설계 일관성 (RESTful 원칙)
```

### 6.3 프론트엔드 에이전트 — `agents/09-frontend/AGENT.md`

```markdown
# 프론트엔드 에이전트 (Frontend Engineer)

## 페르소나
당신은 React/Next.js 생태계에 전문성을 가진 시니어 프론트엔드 엔지니어입니다.
성능 최적화, 접근성(a11y), SEO에 깊은 이해가 있습니다.
타입 안전성을 중시하며, 재사용 가능한 컴포넌트 설계에 능숙합니다.

## 역할
- 디자인 명세 기반 컴포넌트 구현
- 페이지 라우팅 및 레이아웃 구성
- 상태관리 설계 (서버 상태: TanStack Query, 클라이언트: Zustand)
- API 연동 레이어 구현
- 반응형 + 접근성 보장

## 입력
- pipeline/artifacts/03-design-spec/wireframe-spec.md
- pipeline/artifacts/06-design-system/design-tokens.json
- pipeline/artifacts/05-api-spec/openapi.yaml

## 산출물
- src/frontend/ 하위 소스코드

## 디렉토리 구조
\`\`\`
src/frontend/
├── app/                  # Next.js App Router
│   ├── (auth)/          # 인증 필요 라우트 그룹
│   ├── (public)/        # 공개 라우트 그룹
│   └── api/             # Route Handlers (BFF)
├── components/
│   ├── ui/              # 기본 UI 컴포넌트 (Button, Input 등)
│   ├── features/        # 기능별 컴포넌트
│   └── layouts/         # 레이아웃 컴포넌트
├── hooks/               # 커스텀 훅
├── lib/
│   ├── api/             # API 클라이언트 + 타입
│   └── utils/           # 유틸리티 함수
├── stores/              # Zustand 스토어
└── types/               # 글로벌 타입 정의
\`\`\`

## 코딩 컨벤션
1. 컴포넌트는 함수형 + TypeScript strict mode
2. Server Component를 기본으로, 상호작용 필요 시만 'use client'
3. 이미지는 next/image, 폰트는 next/font 사용
4. CSS는 Tailwind CSS + cn() 유틸리티
5. 폼은 react-hook-form + zod validation
6. API 호출은 TanStack Query의 useQuery/useMutation
7. 에러 바운더리 필수 적용
```

---

## 7. QA 에이전트 테스트 전략 — `agents/11-qa/AGENT.md` (핵심 발췌)

```markdown
# QA 에이전트 (Quality Assurance)

## 테스트 피라미드

### Layer 1: 단위 테스트 (70%)
- 백엔드: JUnit 5 + Mockito (Java)
- 프론트: Vitest + React Testing Library
- 커버리지 목표: 라인 80% 이상

### Layer 2: 통합 테스트 (20%)
- 백엔드: @SpringBootTest + Testcontainers (PostgreSQL, Redis)
- API: REST Assured 또는 MockMvc
- 프론트: MSW(Mock Service Worker) + Playwright Component Test

### Layer 3: E2E 테스트 (10%)
- Playwright (웹) / Detox (모바일)
- 핵심 사용자 시나리오 (Happy Path) 우선
- CI에서 병렬 실행

### 성능 테스트
- k6 스크립트 생성
- 시나리오: 동시 사용자 100/500/1000명
- 응답시간 P95 < 200ms, P99 < 500ms 목표

## 산출물
- pipeline/artifacts/07-test-results/unit-test-report.md
- pipeline/artifacts/07-test-results/integration-test-report.md
- pipeline/artifacts/07-test-results/e2e-test-report.md
- pipeline/artifacts/07-test-results/performance-report.md
- pipeline/artifacts/07-test-results/bug-report.md
```

---

## 8. 품질 게이트 정의 — `agents/_shared/quality-gates.md`

```markdown
# 단계별 품질 게이트

## Gate 1: Discovery 완료
- [ ] 비즈니스 목표 3개 이상 정의
- [ ] 사용자 스토리 10개 이상 작성
- [ ] MVP 범위 명확히 정의
- [ ] 경쟁사 3곳 이상 분석
- [ ] PRD에 성공 지표(KPI) 포함

## Gate 2: 설계 완료
- [ ] 모든 사용자 스토리에 대응하는 화면 설계 존재
- [ ] ERD가 기능명세의 모든 데이터 요구사항 커버
- [ ] API 엔드포인트가 모든 기능을 지원
- [ ] 디자인 토큰 정의 완료

## Gate 3: 구현 완료
- [ ] 모든 API 엔드포인트 구현 완료
- [ ] 프론트엔드 모든 페이지 구현 완료
- [ ] 컴파일/빌드 성공
- [ ] Lint 에러 0건

## Gate 4: 검증 완료
- [ ] 단위 테스트 커버리지 80% 이상
- [ ] E2E 핵심 시나리오 전체 통과
- [ ] 성능 테스트 목표치 달성
- [ ] 코드 리뷰 Critical 이슈 0건
- [ ] OWASP Top 10 보안 체크 통과
- [ ] 의존성 취약점 스캔 통과 (npm audit / OWASP Dependency Check)

## Gate 5: 배포 완료
- [ ] 스테이징 환경 배포 성공
- [ ] 헬스체크 통과
- [ ] 모니터링 + 알림 설정 확인
- [ ] 롤백 플랜 문서화
```

---

## 9. 실행 시나리오 예시

### 사용자 입력
```
/kickoff 반려동물 건강관리 SaaS를 만들고 싶어.
주요 기능: 진료 기록 관리, 예방접종 스케줄, 사료/간식 추천, 
수의사 상담 예약, 건강 대시보드.
타겟: 한국 내 20-40대 반려동물 보호자.
수익모델: 프리미엄 구독 + 수의사 매칭 수수료.
```

### 자동 실행 흐름

```
[1] 📋 사업분석 에이전트 실행
    → 요구사항 분석서 생성 (US-001 ~ US-025)
    → MVP 범위: 진료기록 + 예방접종 + 대시보드
    
[2] 📊 PM 에이전트 실행  
    → PRD 생성 (FEAT-001 ~ FEAT-015, RICE 스코어링)
    → 3개월 로드맵: Sprint 1-6
    → Sprint 1 백로그: 회원가입, 반려동물 프로필, 진료기록 CRUD

[3] 📈 마케팅 에이전트 실행
    → 경쟁사 분석: 핏펫, 펫닥, 포인핸드
    → GTM: 인스타그램 + 네이버 카페 타겟팅
    → SEO 키워드: "강아지 건강관리앱", "반려동물 진료기록"

[4] 💬 CRM 에이전트 실행
    → 고객 여정: 발견 → 가입 → 첫 기록 → 구독 전환
    → 온보딩 이메일 시퀀스 설계

🔴 [인간 승인 지점 #1] — 사용자에게 요약 보고 + 진행 확인

[5] 📝 기획 에이전트 실행
    → 15개 화면 기능명세서
    → 화면흐름도 (Mermaid)

[6] 🎨 디자인 에이전트 실행
    → 디자인 토큰 (primary: #4A90D9, font: Pretendard)
    → 컴포넌트 명세 23개

[7] 🗄️ DB 에이전트 실행
    → ERD: users, pets, medical_records, vaccinations, 
      appointments, subscriptions 등 12테이블
    → DDL + 인덱스 + 주요 쿼리 20개

🔴 [인간 승인 지점 #2] — 설계 검토 + 진행 확인

[8-10] 💻 개발 에이전트들 실행
    → Spring Boot API 32개 엔드포인트
    → Next.js 15개 페이지 + 45개 컴포넌트
    → (모바일은 v2로 연기)

[11-13] 🔍 검증 에이전트들 실행
    → 단위 테스트 187개, 커버리지 83%
    → E2E 시나리오 12개 통과
    → k6 성능: P95 145ms ✅
    → 코드 리뷰: Minor 8건, Critical 0건
    → 보안: XSS 차단 확인, CSRF 토큰 적용 확인

🔴 [인간 승인 지점 #3] — 배포 승인

[14] 🚀 DevOps 에이전트 실행
    → Terraform으로 AWS 인프라 프로비저닝
    → GitHub Actions CI/CD 파이프라인
    → Staging → Production 배포

[15] 📊 성과분석 에이전트 실행
    → 런칭 체크리스트 확인
    → 모니터링 대시보드 설정
    → 주간 리포트 자동화 설정
```

---

## 10. 구축 로드맵 (이 플랫폼 자체의 구축 계획)

### Phase 0: 기반 구축 (1주차)
- [ ] 디렉토리 구조 생성
- [ ] CLAUDE.md 오케스트레이터 작성
- [ ] context-protocol.md, quality-gates.md 작성
- [ ] 슬래시 커맨드 기본 틀 작성

### Phase 1: 핵심 에이전트 구축 (2-3주차)
- [ ] 사업분석 에이전트 AGENT.md + 템플릿 + 예시
- [ ] PM 에이전트 AGENT.md + 템플릿 + 예시
- [ ] DB 에이전트 AGENT.md + 템플릿 + 예시
- [ ] 백엔드 에이전트 AGENT.md + 템플릿 + 예시
- [ ] 프론트엔드 에이전트 AGENT.md + 템플릿 + 예시
- [ ] QA 에이전트 AGENT.md + 템플릿 + 예시

### Phase 2: 보조 에이전트 구축 (4주차)
- [ ] 기획 에이전트
- [ ] 마케팅 에이전트
- [ ] CRM 에이전트
- [ ] 디자인 에이전트
- [ ] 앱 에이전트
- [ ] DevOps 에이전트
- [ ] 보안 에이전트

### Phase 3: 통합 테스트 (5주차)
- [ ] /kickoff 전체 파이프라인 시험 실행
- [ ] 에이전트 간 산출물 연계 검증
- [ ] 품질 게이트 동작 확인
- [ ] 인간 승인 지점 UX 최적화
- [ ] 에이전트 프롬프트 튜닝 (Few-shot 추가)

### Phase 4: 최적화 (6주차)
- [ ] 에이전트 성능 벤치마크 (산출물 품질 측정)
- [ ] 1M 컨텍스트 활용 전략 최적화 (Full Context vs Selective 단계별 매핑)
- [ ] Compaction 동작 모니터링 및 핵심 정보 영속화 패턴 적용
- [ ] 병렬 실행 가능 구간 식별 및 적용 (Agent Teams 활용)
- [ ] 모델 전략 확정 (Max 구독자: Opus 4.7 단일 / API 종량제: 단계별 Opus 4.7 ↔ Sonnet 4.6 분기)

---

## 11. 실전 팁 & 주의사항

### 컨텍스트 윈도우 관리 (1M 토큰 기준)
- Opus 4.7 / Sonnet 4.6은 **1M 토큰** 컨텍스트 윈도우 지원 (Max/Team/Enterprise 자동 적용)
- 물리적 제약은 거의 없으나, **비용 최적화**를 위해 Selective Loading 권장
- Phase 4(Verify) 코드 리뷰/보안 검증은 **Full Context Mode** 활용 (전체 소스 원본 로드)
- Phase 1~3는 요약본 기반으로 입력 토큰 70% 절감 가능
- Compaction 기능이 1M 초과 시 자동 요약하지만, 핵심 정보는 파일로 영속화
- `pipeline/artifacts/`의 산출물 요약본(summary.md)은 비용 절감용으로 별도 관리

### 모델 전략 (구독 유형별 분기)

**Option A — Claude Code Max / Team / Enterprise 구독자 (이 프로젝트 기본값)**
- **Opus 4.7 단일 운영** — 모든 Phase에서 최고 품질 모델 사용
- 근거:
  - 월 고정 구독료 기준 → 모델 분기로 얻는 비용 이득 없음
  - Phase 1~3에서도 Opus가 Sonnet 대비 엣지 케이스/복합 제약 판단에서 우위
  - 분기 관리의 인지 비용이 오히려 손해
- 리밋 도달 시: Sonnet 4.6 자동 fallback (Claude Code 내장, statusline으로 인지)
- 실전 사례: Sprint 3 코드리뷰에서 Opus 4.7이 N+1 쿼리 17,500건 발견 — Sonnet 표면 리뷰로는 포착 난이도 높은 이슈

**Option B — API 종량제 / 비용 민감 사용자**
- Discovery/Design 단계: Sonnet 4.6 사용 ($3/$15 per 1M tokens — Opus 대비 40% 절감)
- 코드 생성/리뷰: Opus 4.7 사용 ($5/$25 per 1M tokens, 128K max output)
- Phase 4 검증: Opus 4.7 Full Context Mode (정확도 최우선, 공통)
- 반복적 테스트 실행은 실제 테스트 러너(Jest, Playwright, k6)에 위임
- 전체 파이프라인 예상 비용: $15~30 (Selective Loading 적용 시)

| 구분 | Option A (Max) | Option B (API) |
|------|--------------|---------------|
| Phase 1 Discovery | Opus 4.7 | Sonnet 4.6 |
| Phase 2 Design | Opus 4.7 | Sonnet 4.6 |
| Phase 3 Build | Opus 4.7 | Sonnet 4.6 (+ Opus 선택적) |
| Phase 4 Verify | Opus 4.7 | Opus 4.7 |
| Phase 5 Ship | Opus 4.7 | Sonnet 4.6 |
| Judge Agent | Opus 4.7 | Sonnet 4.6 |

### 에이전트 프롬프트 개선 사이클
```
1. 실행 → 2. 산출물 품질 평가 → 3. AGENT.md 수정 
→ 4. Few-shot 예시 추가 → 5. 재실행 → 반복
```

### 확장 가능한 구조
- 새 에이전트 추가: `agents/XX-name/AGENT.md` 생성 + 파이프라인에 등록
- 기술 스택 변경: 해당 에이전트의 AGENT.md만 수정
- 산출물 포맷 변경: `agents/_shared/output-schema.md` 업데이트

---

## 12. 기대 효과

| 항목 | 기존 (1인 수동) | AI 에이전트팀 활용 |
|------|---------------|-------------------|
| 요구사항→PRD | 3-5일 | 30분-1시간 |
| 설계 (DB+API+UI) | 1-2주 | 2-4시간 |
| MVP 개발 | 4-8주 | 1-2주 |
| 테스트 작성 | 1-2주 | 2-4시간 |
| 코드 리뷰 | 수동 (편향) | 자동 (다관점) |
| 보안 검증 | 외부 의뢰 | 자동 기본검증 |
| 총 MVP 런칭 | 3-4개월 | 3-6주 |

> ⚠️ **면책**: 위 수치는 이상적 시나리오이며, 실제로는 인간 검토/수정 시간이 추가됩니다.
> AI 생성물은 반드시 전문가(당신) 검토가 필요합니다.

---

# Part II. 1M 컨텍스트 & 품질 관리


# 부록 A. 컨텍스트 윈도우 관리 전략

## 문제 정의

Claude Code는 Opus 4.7 / Sonnet 4.6 기준 **1M(1,000,000) 토큰** 컨텍스트 윈도우를 지원한다 (Max/Team/Enterprise 사용자 기본 적용, 추가 비용 없음). 이전 200K 시절 대비 5배 확장되었으나, 멀티에이전트 파이프라인에서는 여전히 관리가 필요하다:

```
에이전트 페르소나 AGENT.md          ≈    2,000 토큰
이전 단계 산출물 (누적)             ≈  150,000 ~ 500,000+ 토큰
현재 작업 지시 + Few-shot 예시      ≈    5,000 토큰
코드 생성 출력 여유분 (128K max)    ≈  128,000 토큰
───────────────────────────────────────────
필요 총량                          ≈  285,000 ~ 635,000+ 토큰
```

**1M 컨텍스트에서도 관리가 필요한 이유:**
1. **대규모 프로젝트**: 전체 파이프라인 산출물 누적이 500K+ 토큰을 초과할 수 있음
2. **코드 생성 단계**: 생성된 소스코드 자체가 수십만 토큰을 차지 (50+ 파일 프로젝트)
3. **비용 효율**: 1M 토큰 전체를 매번 로드하면 Opus 기준 입력만 $5/회 → 불필요한 컨텍스트 제거로 비용 절감
4. **정확도**: Opus 4.7의 MRCR v2 점수가 78.3%로 최고 수준이지만, 컨텍스트가 작을수록 recall 정확도는 더 높아짐

> 💡 **1M 컨텍스트의 전략적 활용**: 200K 시절에는 "어떻게 컨텍스트 안에 넣을까"가 문제였다면, 1M 시대에는 **"비용 최적화와 정확도 극대화를 위해 얼마나 정제해서 넣을까"**가 핵심 과제다.

Phase 3(Build) 시점에서 이전 단계 산출물을 전부 원본으로 로드하면 ~300K 토큰으로, 1M 윈도우의 30%를 차지한다. 물리적으로는 가능하지만, **비용($1.50/회 입력)과 recall 정확도** 관점에서 선택적 로딩이 여전히 유리하다.

## 해결 전략: 3계층 컨텍스트 관리 (1M 시대 비용·정확도 최적화)

```
┌─────────────────────────────────────────────────┐
│  Layer 1: Context Distiller Agent (요약 에이전트)  │
│  - 각 단계 산출물의 압축 요약 자동 생성             │
│  - 비용 최적화: 불필요한 토큰 입력 80~90% 절감     │
│  - 정확도 향상: 핵심 정보만 주입 → recall 개선      │
├─────────────────────────────────────────────────┤
│  Layer 2: Selective Loader (선택적 로더)           │
│  - 에이전트별 의존성 매핑에 따라 필요 섹션만 로드     │
│  - 파일 단위가 아닌 섹션 단위 로딩                  │
│  - 1M 여유분을 코드 생성 + 출력에 최대한 활용       │
├─────────────────────────────────────────────────┤
│  Layer 3: Full Context Mode (전체 컨텍스트 모드)   │
│  - 1M 윈도우를 활용한 전체 산출물 원본 로드          │
│  - 코드 리뷰, 보안 검증 등 전체 맥락 필요 시 사용    │
│  - 비용보다 정확도가 중요한 Phase 4(Verify)에 적합   │
└─────────────────────────────────────────────────┘
```

> 💡 **1M 컨텍스트 활용 전략 핵심**: Phase 1~2(Discovery/Design)는 Layer 1+2로 비용 효율화, Phase 4(Verify)의 코드 리뷰/보안 검증은 Layer 3으로 전체 컨텍스트 활용. "항상 요약" 또는 "항상 전체 로드" 가 아닌, **단계별 최적 전략**을 적용한다.

### Layer 1: Context Distiller Agent

별도의 경량 에이전트를 두어, 각 단계 산출물이 완료될 때마다 자동으로 **구조화된 요약**을 생성한다.

```
agents/00-distiller/
├── AGENT.md
└── templates/
    └── summary-schema.md
```

#### `agents/00-distiller/AGENT.md`

```markdown
# Context Distiller Agent

## 페르소나
당신은 기술 문서 요약 전문가입니다. 
핵심 정보를 손실 없이 최소 토큰으로 압축하는 것이 임무입니다.

## 역할
각 에이전트의 산출물을 받아 3가지 수준의 요약을 생성:

### Level 1: Headline (1줄, ~50 토큰)
- 산출물의 핵심 결론 한 줄

### Level 2: Brief (~500 토큰)
- 핵심 의사결정 사항
- 주요 수치/제약조건
- 다음 단계에 영향을 주는 핵심 항목만

### Level 3: Structured Extract (~2,000 토큰)
- 섹션별 핵심 내용 추출
- 데이터 모델/API 목록은 이름+설명만 (상세 스키마 제외)
- 의존성 관계 그래프

## 요약 규칙
1. 원본의 **의사결정(decisions)**은 반드시 보존
2. **수치적 제약조건**(성능 목표, 데이터 규모 등)은 반드시 보존
3. **명명 규칙**(테이블명, API 경로, 컴포넌트명)은 목록으로 보존
4. 설명적 텍스트, 배경 설명, 근거는 생략 가능
5. Few-shot 예시는 제거

## 출력 형식
\`\`\`yaml
---
source: "pipeline/artifacts/04-db-schema/ddl.sql"
distilled_at: "2026-04-16T11:00:00+09:00"
compression_ratio: "92%"  # 원본 대비 절감률
---

# Level 1: Headline
12개 테이블, PostgreSQL, UUID v7 PK, soft delete 적용

# Level 2: Brief
- 핵심 엔티티: users, pets, medical_records, vaccinations, appointments
- 관계: users 1:N pets, pets 1:N medical_records
- 인덱스: 8개 복합 인덱스 (주요 조회 패턴 커버)
- 파티셔닝: medical_records 월별 파티션 (3년 후 예상 5천만건)
- 특이사항: vaccinations에 JSON 컬럼(vaccine_metadata) 사용

# Level 3: Structured Extract
## 테이블 목록
| 테이블 | 설명 | 주요 컬럼 | 관계 |
|--------|------|----------|------|
| users | 사용자 | email, name, phone | 1:N pets |
| pets | 반려동물 | name, species, breed, birth_date | N:1 users, 1:N medical_records |
| ... | ... | ... | ... |

## 인덱스 전략 요약
- idx_medical_records_pet_date: (pet_id, record_date DESC) — 진료기록 목록 조회
- ...

## 핵심 의사결정
- PK: UUID v7 선택 (시간순 정렬 + 분산 ID 생성)
- soft delete: deleted_at 컬럼 (법적 데이터 보존 요구사항)
- JSON 컬럼: vaccine_metadata (백신 종류별 스키마가 달라 유연성 필요)
\`\`\`
```

#### 요약 저장 구조

```
pipeline/artifacts/
├── 01-requirements/
│   ├── requirements.md          # 원본 (30,000 토큰)
│   └── requirements.summary.md  # 요약 (2,000 토큰) ← Distiller 생성
├── 04-db-schema/
│   ├── ddl.sql                  # 원본 (15,000 토큰)
│   ├── erd.mermaid              # 원본
│   └── db-schema.summary.md    # 요약 (2,000 토큰) ← Distiller 생성
```

### Layer 2: Selective Loader — 에이전트별 의존성 매핑

각 에이전트가 실제로 필요한 이전 산출물의 **수준(Level)**을 미리 매핑한다.

```markdown
<!-- pipeline/dependency-map.md -->

# 에이전트별 컨텍스트 로딩 맵

## 08-backend (백엔드 에이전트)
| 산출물 | 로딩 수준 | 이유 |
|--------|----------|------|
| 01-requirements | Level 2 (Brief) | 비즈니스 맥락만 필요 |
| 02-prd | Level 2 (Brief) | 기능 범위 확인용 |
| 03-design-spec | Level 3 (Extract) | API 경로와 화면흐름 필요 |
| 04-db-schema/ddl.sql | **원본 (Full)** | 테이블 정의 직접 참조 필수 |
| 05-api-spec | **원본 (Full)** | API 구현 대상 |
| 06-design-system | Level 1 (Headline) | 백엔드에는 거의 불필요 |

## 09-frontend (프론트엔드 에이전트)
| 산출물 | 로딩 수준 | 이유 |
|--------|----------|------|
| 01-requirements | Level 1 (Headline) | 최소 맥락만 |
| 02-prd | Level 2 (Brief) | 기능 범위 확인용 |
| 03-design-spec | **원본 (Full)** | 화면 구현 직접 참조 필수 |
| 04-db-schema | Level 1 (Headline) | 프론트에는 불필요 |
| 05-api-spec | **원본 (Full)** | API 연동 필수 |
| 06-design-system | **원본 (Full)** | 디자인 토큰 직접 참조 필수 |

## 11-qa (QA 에이전트)
| 산출물 | 로딩 수준 | 이유 |
|--------|----------|------|
| 01-requirements | Level 3 (Extract) | 인수 조건 참조 |
| 03-design-spec | Level 3 (Extract) | 테스트 시나리오 도출 |
| 05-api-spec | **원본 (Full)** | API 테스트 대상 |
| src/backend/** | **원본 (Full)** | 테스트 대상 코드 |
| src/frontend/** | Level 3 (Extract) | E2E 시나리오용 |
```

#### 토큰 절감 효과 시뮬레이션 (1M 컨텍스트 기준)

```
시나리오: 백엔드 에이전트가 Phase 3에서 코드 구현 시

[방식 A — 전체 원본 로드 (1M Full Context Mode)]
requirements.md        30,000 토큰
prd.md                 20,000 토큰
feature-spec.md        25,000 토큰
ddl.sql                15,000 토큰
openapi.yaml           12,000 토큰
design-tokens.json      3,000 토큰
AGENT.md                2,000 토큰
───────────────────────────────
합계                  107,000 토큰 (컨텍스트의 10.7%)
출력 여유             893,000 토큰 ✅ 충분
입력 비용             ~$0.54/회 (Opus $5/1M 입력)

→ 물리적으로 전혀 문제없음. 단, 15단계 × 평균 3회 호출 = 45회
→ 입력만 $24.30 (전체 원본 유지 시)

[방식 B — Selective Loading (비용 최적화)]
requirements.summary (L2)    500 토큰
prd.summary (L2)             500 토큰
feature-spec.summary (L3)  2,000 토큰
ddl.sql (원본)             15,000 토큰
openapi.yaml (원본)        12,000 토큰
design-tokens (L1)            50 토큰
AGENT.md                   2,000 토큰
───────────────────────────────
합계                      32,050 토큰 (컨텍스트의 3.2%)
출력 여유             967,950 토큰 ✅ 더 많은 여유
입력 비용             ~$0.16/회

→ 45회 기준 입력 비용 $7.20 (방식 A 대비 70% 절감)
→ 정확도도 핵심 컨텍스트만 집중하므로 오히려 향상

[방식 C — 하이브리드 (권장)]
Phase 1~3: Selective Loading (방식 B) — 비용 효율 우선
Phase 4:   Full Context (방식 A) — 코드 리뷰/보안 검증은 전체 맥락 필요
→ 예상 총 입력 비용: ~$12~15 (전체 파이프라인)
```

### Layer 3: Full Context Mode (1M 전체 활용)

1M 컨텍스트 윈도우의 가장 큰 장점은 **전체 원본을 한 번에 로드**할 수 있다는 것이다. 다음 상황에서는 요약 없이 원본 전체를 주입한다:

```markdown
<!-- CLAUDE.md 에 추가할 규칙 -->

## Full Context Mode 사용 조건

다음 에이전트/단계에서는 이전 산출물 원본을 전체 로드:

### 반드시 Full Context
- **코드 리뷰 에이전트**: 소스코드 전체 + API 스펙 + DB 스키마 원본
- **보안 검증 에이전트**: 소스코드 전체 + 인프라 코드 + 의존성 목록
- **QA E2E 테스트**: 기능명세 원본 + 소스코드 전체

### 선택적 Full Context (프로젝트 규모에 따라)
- **백엔드 에이전트**: 소규모 프로젝트(총 산출물 < 300K)면 전체 로드
- **프론트엔드 에이전트**: 디자인 시스템 + API 스펙은 항상 원본

### Selective Loading 유지 (비용 최적화)
- **사업분석/PM/마케팅/CRM**: 비코드 단계는 요약으로 충분
- **Distiller 에이전트 자체**: 원본 입력 → 요약 출력이므로 원본 필요

1M 컨텍스트 + Compaction 기능 활용:
- 세션이 길어져 1M에 근접하면 서버 측 Compaction이 자동으로
  이전 대화를 요약하여 공간 확보 (Opus 4.7/Sonnet 4.6 지원)
- 즉, 이론적으로 무한 길이 대화가 가능하나, Compaction 이후
  초기 컨텍스트 정확도가 떨어질 수 있으므로 핵심 정보는
  파일로 저장하여 참조하는 패턴 유지
```

### 보너스: 대규모 코드 생성 시 파일 분할 전략

```markdown
## 코드 생성 분할 규칙

한 번의 에이전트 실행에서 생성할 코드가 50개 파일 이상이면:

1. **도메인 단위 분할**: 기능 도메인별로 서브태스크 분리
   - Subtask 1: users 도메인 (Controller + Service + Repository + DTO)
   - Subtask 2: pets 도메인
   - Subtask 3: medical_records 도메인
   - ...

2. **레이어 단위 분할** (도메인이 적을 때):
   - Subtask 1: 전체 Entity + Repository
   - Subtask 2: 전체 Service + UseCase
   - Subtask 3: 전체 Controller + DTO

3. 각 서브태스크는 이전 서브태스크의 산출물을 컨텍스트로 받음
   (이미 생성된 코드 → 다음 코드의 참조용)
```

---

# 부록 B. LLM-as-Judge 기반 자동 품질 게이트 시스템

## 문제 정의

현재 `quality-gates.md`는 **체크리스트 기반**으로, 에이전트 자신이 자기 산출물을 "통과"로 마킹한다. 이는 두 가지 근본적 문제를 갖는다:

1. **자기 평가 편향**: 생성자가 자신의 산출물을 검증하면 맹점 발생
2. **이진 판단의 한계**: Pass/Fail만으로는 품질 수준의 미세 차이를 포착 불가

## 해결 아키텍처: 독립 Judge Agent + 정량 스코어링

```
┌──────────────────────────────────────────────────────────┐
│                    Quality Gate System                    │
│                                                          │
│  ┌────────────┐    ┌────────────┐    ┌────────────┐     │
│  │ Producer   │───▶│ Judge      │───▶│ Gate       │     │
│  │ Agent      │    │ Agent      │    │ Controller │     │
│  │ (산출물    │    │ (독립 평가) │    │ (통과/반려  │     │
│  │  생성)     │    │            │    │  /재시도)   │     │
│  └────────────┘    └────────────┘    └────────────┘     │
│        │                │                  │             │
│        ▼                ▼                  ▼             │
│   산출물 저장      평가 리포트 저장    파이프라인 제어     │
│                                                          │
│  판정 기준:                                              │
│  ├─ Score ≥ 8.0  → ✅ PASS (다음 단계 진행)              │
│  ├─ Score 6.0~7.9 → ⚠️ CONDITIONAL (경고 + 진행 가능)   │
│  ├─ Score 4.0~5.9 → 🔄 RETRY (피드백 반영 후 재생성)     │
│  └─ Score < 4.0  → 🔴 FAIL (인간 개입 필요)              │
└──────────────────────────────────────────────────────────┘
```

### Judge Agent 설계 — `agents/00-judge/AGENT.md`

```markdown
# Quality Judge Agent

## 페르소나
당신은 소프트웨어 품질 보증 수석 심사관입니다.
ISO 25010 품질 모델과 CMMI 성숙도 모델에 정통합니다.
편향 없이 객관적으로 산출물을 평가하며, 구체적인 개선 피드백을 제공합니다.

## 핵심 원칙
1. **산출물 생성 에이전트와 완전히 독립적으로 평가**
2. 점수는 반드시 구체적 근거와 함께 제시
3. 개선 피드백은 실행 가능한(actionable) 수준으로 작성
4. 이전 단계 산출물과의 **일관성**을 중점 검증

## 평가 차원 (Rubric)

### 공통 평가 기준 (모든 산출물)
| 차원 | 가중치 | 설명 |
|------|--------|------|
| 완전성(Completeness) | 25% | 요구되는 모든 섹션/항목이 존재하는가 |
| 일관성(Consistency) | 25% | 이전 단계 산출물과 모순이 없는가 |
| 정확성(Accuracy) | 20% | 기술적으로 올바른가 |
| 명확성(Clarity) | 15% | 다음 에이전트가 해석 가능한 수준인가 |
| 실행가능성(Actionability) | 15% | 이 산출물만으로 다음 작업을 수행할 수 있는가 |

### 단계별 추가 기준

#### 요구사항 (Stage 01)
- 사용자 스토리 커버리지: 모든 비즈니스 목표에 대응하는 스토리 존재?
- 인수 조건 명확성: 테스트 가능한 수준으로 작성?
- MVP 범위 합리성: 4-6주 내 구현 가능한 범위?

#### PRD (Stage 02)
- RICE 스코어 일관성: 스코어링이 논리적인가?
- KPI 측정가능성: 모든 지표가 측정 가능한가?
- 기술 의존성 식별: 누락된 의존성이 없는가?

#### DB 설계 (Stage 04)
- 정규화 수준: 적절한 정규화/반정규화 판단?
- 인덱스 전략: 주요 쿼리 패턴 커버?
- 확장성: 예상 데이터 규모에 대한 고려?
- 마이그레이션 안전성: 롤백 가능한 DDL?

#### 코드 (Stage 06)
- SOLID 원칙 준수
- 에러 핸들링 완전성
- 테스트 가능성 (의존성 주입, 모킹 용이성)
- 보안 기본 원칙 (입력 검증, 인증/인가)
- API 설계 RESTful 준수

## 평가 출력 스키마
\`\`\`yaml
---
judge: "quality-judge"
evaluated_artifact: "pipeline/artifacts/04-db-schema/ddl.sql"
evaluated_agent: "07-db"
evaluation_timestamp: "2026-04-16T12:00:00+09:00"
---

overall_score: 8.2  # 0.0 ~ 10.0
verdict: "PASS"     # PASS | CONDITIONAL | RETRY | FAIL

dimension_scores:
  completeness:
    score: 9.0
    evidence: "12개 테이블 모두 DDL 존재, 인덱스 8개 정의, 마이그레이션 포함"
    issues: []
  consistency:
    score: 7.5
    evidence: "기능명세의 '알림 설정' 기능에 대응하는 notification_preferences 테이블 누락"
    issues:
      - severity: "Major"
        description: "기능명세 FR-012(알림 설정 관리)에 대응하는 테이블이 없음"
        suggestion: "notification_preferences 테이블 추가 필요 (user_id FK, channel ENUM, enabled BOOLEAN)"
  accuracy:
    score: 8.5
    evidence: "PostgreSQL 문법 정확, 데이터 타입 적절"
    issues:
      - severity: "Minor"
        description: "vaccinations.vaccine_metadata JSONB 컬럼에 GIN 인덱스 미적용"
        suggestion: "CREATE INDEX idx_vacc_metadata ON vaccinations USING GIN(vaccine_metadata)"
  clarity:
    score: 8.0
    evidence: "테이블/컬럼 네이밍 일관적, 주석 포함"
    issues: []
  actionability:
    score: 8.5
    evidence: "DDL 스크립트 직접 실행 가능, 시드 데이터 포함"
    issues: []

blocking_issues:       # RETRY/FAIL 판정 시 반드시 해결해야 할 항목
  - "notification_preferences 테이블 누락 (consistency)"

improvement_suggestions:  # PASS여도 개선하면 좋을 항목
  - "JSONB 컬럼에 GIN 인덱스 추가"
  - "파티셔닝 전략을 DDL에 직접 포함 (현재 문서에만 기술)"

retry_instructions: null  # RETRY 판정 시 재생성 가이드
\`\`\`

## 크로스 체크 규칙 (일관성 검증 상세)

### 산출물 간 참조 무결성 체크
\`\`\`
requirements.user_stories[*].id 
  ⊆ prd.features[*].related_user_stories[*]
  → 모든 사용자 스토리가 PRD 기능에 매핑되어야 함

prd.features[*].id
  ⊆ design_spec.screens[*].related_features[*]
  → 모든 PRD 기능이 화면 설계에 반영되어야 함

design_spec.screens[*].data_requirements[*]
  ⊆ db_schema.tables[*]
  → 화면에서 필요한 모든 데이터가 DB 스키마에 존재해야 함

db_schema.tables[*]
  ⊆ api_spec.endpoints[*].request/response
  → 모든 테이블이 최소 1개 API를 통해 접근 가능해야 함
\`\`\`
```

### Gate Controller 로직

```markdown
<!-- pipeline/gate-controller.md -->

# Gate Controller — 파이프라인 흐름 제어

## 판정별 동작

### ✅ PASS (Score ≥ 8.0)
1. 산출물의 quality_gate_passed를 true로 변경
2. improvement_suggestions를 별도 파일로 저장 (추후 개선용)
3. 다음 단계 에이전트 자동 실행

### ⚠️ CONDITIONAL (Score 6.0~7.9)
1. 경고 메시지를 사용자에게 표시
2. blocking_issues가 없으면 진행 허용
3. improvement_suggestions를 다음 에이전트에 "참고사항"으로 전달
4. 사용자에게 "진행/수정 중 선택" 프롬프트

### 🔄 RETRY (Score 4.0~5.9)
1. blocking_issues와 retry_instructions를 원본 에이전트에 피드백으로 전달
2. 원본 에이전트 재실행 (최대 2회)
3. 재시도 시 Judge의 피드백을 추가 컨텍스트로 주입:
   
   ```
   ## 이전 평가 피드백 (반드시 반영할 것)
   - [Major] notification_preferences 테이블 누락
   - [Major] vaccinations.vaccine_metadata에 GIN 인덱스 필요
   
   위 피드백을 반영하여 산출물을 수정하세요.
   수정한 내용을 changelog에 기록하세요.
   ```

4. 2회 재시도 후에도 6.0 미만이면 FAIL로 승격

### 🔴 FAIL (Score < 4.0)
1. 파이프라인 중단
2. 전체 평가 리포트를 사용자에게 표시
3. 사용자가 직접 수정하거나, 에이전트 페르소나(AGENT.md) 수정 후 재실행

## 자동 재시도 흐름

\`\`\`
Producer Agent → 산출물 생성
       ↓
Judge Agent → 평가 (Score: 5.8, RETRY)
       ↓
Gate Controller → 피드백 주입 + Producer Agent 재실행
       ↓
Producer Agent → 수정된 산출물 생성 (v1.1)
       ↓
Judge Agent → 재평가 (Score: 8.3, PASS) ✅
       ↓
Gate Controller → 다음 단계 진행
\`\`\`
```

### 실행 비용 분석

```
Judge Agent 1회 실행 비용 (Option B / API 종량제 기준 — Sonnet 4.6 사용 시):
- 입력: 산출물 (~5,000 토큰) + Rubric (~2,000 토큰) + 이전 산출물 요약 (~2,000 토큰)
- 출력: 평가 리포트 (~1,500 토큰)
- 총: ~10,500 토큰 ≈ $0.05 (Sonnet 4.6: $3/$15 per 1M tokens)
- Option A (Max 구독) 적용 시: Opus 4.7 사용, 구독료에 포함 → 추가 비용 0

전체 파이프라인 Judge 비용:
- 15단계 × 1.3회 (평균 재시도 포함) ≈ 20회 × $0.05 = $1.00

→ 전체 파이프라인 비용의 ~3% 추가로 품질 보증 확보
→ 재시도로 인한 재생성 비용이 더 크므로,
   첫 생성 품질을 높이는 Few-shot 투자가 더 경제적

1M 컨텍스트 시대 Judge 최적화:
- API 종량제 기준: Judge Agent는 Sonnet 4.6으로 충분 (평가는 생성보다 가벼움)
- Max 구독자: Opus 4.7 그대로 사용 — 편향 없는 정밀 평가
- 단, 코드 리뷰 Judge는 Full Context Mode로 전체 소스 로드 가능
  → 200K 시절에는 불가능했던 "프로젝트 전체 맥락의 코드 리뷰"가 실현
```

---

# 부록 C. 의사결정 지원 메타 에이전트 (Decision Advisor)

## 문제 정의

3개의 인간 승인 지점에서 1인 창업자가 직면하는 의사결정 과제:

```
승인 지점 #1 (Discovery 완료):
  "이 MVP 범위가 맞나? 기능을 더 넣어야 하나 빼야 하나?"
  "경쟁사 대비 차별점이 충분한가?"
  "타겟 시장 규모가 사업성이 있는가?"

승인 지점 #2 (설계 완료):
  "이 기술 스택이 적절한가?"
  "DB 설계가 향후 확장에 문제없는가?"
  "API 설계가 모바일 앱까지 고려했는가?"

승인 지점 #3 (배포 전):
  "테스트 커버리지가 충분한가?"
  "보안 이슈가 런칭을 막을 수준인가?"
  "성능이 예상 트래픽을 감당하는가?"
```

**1인 창업자는 모든 도메인의 전문가가 아니다.** 기획/마케팅 산출물의 품질을 판단하기 어렵고, 빠르게 진행하고 싶은 편향에 빠지기 쉽다.

## 해결: Decision Advisor Meta-Agent

```
agents/00-advisor/
├── AGENT.md
├── templates/
│   ├── tradeoff-matrix.md
│   ├── risk-simulation.md
│   ├── decision-brief.md
│   └── go-nogo-checklist.md
└── examples/
    └── sample-decision-brief.md
```

### `agents/00-advisor/AGENT.md`

```markdown
# Decision Advisor Meta-Agent

## 페르소나
당신은 스타트업 전문 경영 컨설턴트이자 기술 고문입니다.
McKinsey 출신으로 구조화된 의사결정 프레임워크에 능숙하며,
YC/500 Startups 멘토로서 수백 개 스타트업의 의사결정을 도왔습니다.
기술과 비즈니스 양쪽 언어를 모두 구사합니다.

## 역할
인간 승인 지점에서 다음 보조 자료를 자동 생성:

1. **Decision Brief** — 1페이지 의사결정 요약
2. **Tradeoff Matrix** — 주요 선택지의 장단점 비교
3. **Risk Simulation** — 의사결정별 리스크 시나리오
4. **Go/No-Go Checklist** — 최종 체크리스트 + 권고

## 승인 지점별 보조 자료

### 승인 지점 #1: Discovery 완료

#### Decision Brief 구조
\`\`\`yaml
decision_brief:
  title: "MVP 범위 및 시장 진입 전략 승인"
  
  situation:
    one_liner: "반려동물 건강관리 SaaS, 월 ₩9,900 구독 모델"
    market_size: "국내 반려동물 가구 600만, 헬스케어 앱 시장 연 15% 성장"
    competitive_landscape: "핏펫(시리즈B), 펫닥(수의사 중심), 포인핸드(입양 특화)"
  
  key_decisions:
    - id: D-001
      question: "MVP에 수의사 매칭을 포함할 것인가?"
      options:
        - name: "포함"
          pros:
            - "핵심 수익원(매칭 수수료) 조기 검증"
            - "경쟁사 대비 차별점 확보"
          cons:
            - "개발 기간 2주 추가"
            - "수의사 온보딩이라는 콜드스타트 문제"
            - "법적 검토 필요 (원격진료 규제)"
          risk: "수의사 확보 실패 시 핵심 기능 무력화"
          effort: "3 person-weeks"
        - name: "v2로 연기"
          pros:
            - "MVP 4주 내 런칭 가능"
            - "기록 관리만으로 사용자 확보 후 수의사 매칭 추가"
          cons:
            - "초기 수익 모델이 구독만으로 제한"
            - "경쟁사가 먼저 매칭 시장 선점 리스크"
          risk: "구독 전환율이 낮으면 수익 모델 위기"
          effort: "0 (절감)"
      recommendation: "v2로 연기"
      reasoning: >
        수의사 매칭은 공급측(수의사) 확보가 핵심인데,
        사용자 기반이 없는 상태에서 수의사를 설득하기 어렵다.
        먼저 기록 관리로 사용자 10,000명 확보 후 매칭 추가가
        양면 시장(two-sided market) 구축의 정석이다.
    
    - id: D-002
      question: "웹 우선 vs 앱 우선?"
      options:
        - name: "웹(PWA) 우선"
          pros: ["빠른 개발", "SEO 유입", "앱스토어 심사 불필요"]
          cons: ["푸시 알림 제한(iOS)", "네이티브 경험 부족"]
        - name: "앱 우선"
          pros: ["푸시 알림", "카메라/갤러리 접근", "리텐션 높음"]
          cons: ["개발 기간 2배", "스토어 심사 리스크"]
      recommendation: "웹(PWA) 우선, 3개월 후 앱 출시"
      reasoning: >
        반려동물 진료 기록은 즉시성보다 정확성이 중요하므로
        웹으로 충분하다. PWA로 홈 화면 추가 + 기본 푸시를 활용하고,
        사용자 피드백 기반으로 앱 필요성을 검증한 후 투자한다.
  
  risk_simulation:
    best_case:
      description: "3개월 내 MAU 5,000, 유료 전환 8%"
      monthly_revenue: "₩3,960,000"
      probability: "20%"
    base_case:
      description: "6개월 내 MAU 2,000, 유료 전환 5%"
      monthly_revenue: "₩990,000"
      probability: "50%"
    worst_case:
      description: "6개월 내 MAU 500, 유료 전환 2%"
      monthly_revenue: "₩99,000"
      probability: "30%"
    break_even:
      monthly_cost: "₩500,000 (인프라 + API 비용)"
      required_subscribers: 51
      estimated_timeline: "4-8개월"
  
  go_nogo_checklist:
    must_have:
      - item: "MVP 기능 범위가 4-6주 내 구현 가능한가?"
        status: "✅ YES — 진료기록 + 예방접종 + 대시보드"
      - item: "타겟 사용자가 명확하고 도달 가능한가?"
        status: "✅ YES — 네이버 반려동물 카페, 인스타그램"
      - item: "수익 모델이 검증 가능한가?"
        status: "⚠️ PARTIAL — 구독만으로는 손익분기 늦을 수 있음"
    nice_to_have:
      - item: "경쟁사 대비 명확한 차별점"
        status: "⚠️ PARTIAL — 기능보다 UX 차별화 필요"
    
    overall_recommendation: "GO — 조건부 진행"
    conditions:
      - "수익 모델을 구독 + 제휴(사료/간식 추천 커미션)로 보완"
      - "런칭 3개월 시점에 MAU 1,000 미달 시 피벗 검토"
\`\`\`

### 승인 지점 #2: 설계 완료

#### Tradeoff Matrix 구조
\`\`\`yaml
tradeoff_matrix:
  title: "기술 아키텍처 의사결정"
  
  decisions:
    - question: "PostgreSQL vs MySQL"
      context: "현재 MySQL(yanadoo) 운영 경험 있음"
      matrix:
        | 기준 | PostgreSQL | MySQL |
        |------|-----------|-------|
        | JSONB 지원 | ✅ 네이티브 | ⚠️ JSON 타입 있으나 제한적 |
        | 파티셔닝 | ✅ 선언적 파티셔닝 | ⚠️ 수동 설정 |
        | 풀텍스트 검색 | ✅ tsvector | ⚠️ FULLTEXT (제한적) |
        | 운영 경험 | ⚠️ 새로 학습 | ✅ 기존 경험 활용 |
        | AWS 관리형 | ✅ Aurora PostgreSQL | ✅ Aurora MySQL |
        | 커뮤니티/생태계 | ✅ 확장 모듈 풍부 | ✅ 광범위한 호환성 |
      recommendation: "PostgreSQL"
      reasoning: >
        반려동물 건강 데이터의 유연한 스키마(백신 종류별 메타데이터)가
        필요하므로 JSONB 네이티브 지원이 결정적이다.
        MySQL 경험이 있으므로 SQL 기본기는 전이되며,
        PostgreSQL 특화 기능(Window Function, CTE 최적화)은
        DB 에이전트가 자동 생성하므로 학습 부담 최소화.

    - question: "모놀리스 vs 마이크로서비스"
      recommendation: "모듈러 모놀리스"
      reasoning: >
        1인 운영에서 마이크로서비스는 운영 오버헤드가 치명적.
        모듈러 모놀리스로 시작하여 도메인 경계를 명확히 하고,
        MAU 10만 이상 시 트래픽 핫스팟 서비스만 분리.
  
  architecture_risk_assessment:
    low_risk:
      - "Next.js + Spring Boot 조합은 검증된 스택"
      - "PostgreSQL은 반려동물 데이터 규모에 충분"
    medium_risk:
      - "Redis 캐시 레이어 없이 시작 → 트래픽 증가 시 성능 병목 가능"
      - "이미지 스토리지 전략 미정 (S3 vs CloudFront)"
    mitigation:
      - "Redis는 Sprint 3에서 추가 (캐시 레이어 선제 설계)"
      - "이미지는 S3 + CloudFront CDN으로 확정"
\`\`\`

### 승인 지점 #3: 배포 전

#### Go/No-Go 최종 체크리스트
\`\`\`yaml
deployment_readiness:
  title: "프로덕션 배포 준비도 평가"
  
  critical_gates:  # 하나라도 NO면 배포 불가
    - gate: "E2E 핵심 시나리오 전체 통과"
      status: "✅ 12/12 passed"
      detail: "회원가입→반려동물등록→진료기록→대시보드 전체 흐름 검증"
    
    - gate: "보안 Critical 이슈 0건"
      status: "✅ 0건"
      detail: "OWASP Top 10 체크 완료, SQL Injection/XSS 방어 확인"
    
    - gate: "성능 목표 달성 (P95 < 200ms)"
      status: "✅ P95: 145ms"
      detail: "k6 100 VU 시나리오, 5분간 지속 부하"
    
    - gate: "데이터 백업/복구 검증"
      status: "⚠️ 미검증"
      detail: "RDS 자동 백업은 설정했으나, 복구 테스트 미실행"
      action_required: "배포 전 복구 테스트 1회 실행 (예상 30분)"
  
  important_gates:  # NO여도 배포 가능하나 권고
    - gate: "모니터링 알림 설정"
      status: "✅ CloudWatch 알림 5개 설정"
    - gate: "롤백 플랜 문서화"
      status: "✅ blue-green 배포 전략 적용"
    - gate: "에러 트래킹 설정"
      status: "⚠️ Sentry 미설정"
      recommendation: "Sprint 2에서 추가 (런칭 임팩트 낮음)"
  
  risk_assessment:
    deployment_risk: "LOW"
    reasoning: >
      Critical 게이트 중 데이터 복구 테스트만 미완이며,
      이는 30분 내 해결 가능. 나머지 모든 게이트 통과.
    
    post_launch_risks:
      - risk: "예상 외 트래픽 스파이크"
        probability: "Low"
        mitigation: "ECS auto-scaling 설정 완료, 최대 4 인스턴스"
      - risk: "결제 연동 장애"
        probability: "N/A (v1에 결제 미포함)"
      - risk: "사용자 데이터 유실"
        probability: "Very Low"
        mitigation: "RDS 멀티AZ + 일일 스냅샷"
  
  overall_verdict: "GO — 조건부"
  conditions_before_deploy:
    - "RDS 복구 테스트 실행 (30분)"
  conditions_after_deploy:
    - "48시간 내 Sentry 설정"
    - "1주 내 부하 테스트 재실행 (500 VU)"
\`\`\`

## 실행 흐름 통합

```
Pipeline Stage 완료
       ↓
[Judge Agent] → 품질 평가 (Score 8.2, PASS)
       ↓
인간 승인 지점 도달?
  ├─ NO → 다음 Stage 자동 진행
  └─ YES ↓
       [Decision Advisor Agent] 실행
            ↓
       Decision Brief 생성
       Tradeoff Matrix 생성
       Risk Simulation 생성
       Go/No-Go Checklist 생성
            ↓
       사용자에게 종합 보고서 제시
            ↓
       ┌─────────────────────────────────────┐
       │  📊 Decision Brief                  │
       │  ─────────────────────              │
       │  핵심 의사결정 3개:                   │
       │  D-001: 수의사 매칭 → v2 연기 권고    │
       │  D-002: 웹 우선 출시 권고             │
       │  D-003: 구독+제휴 수익 모델 권고       │
       │                                     │
       │  리스크 시뮬레이션:                    │
       │  Best: ₩396만/월 (20%)              │
       │  Base: ₩99만/월 (50%)               │
       │  Worst: ₩9.9만/월 (30%)             │
       │                                     │
       │  종합 권고: GO (조건부)               │
       │                                     │
       │  [승인] [수정 요청] [중단]             │
       └─────────────────────────────────────┘
            ↓
       사용자 선택:
         ├─ 승인 → 다음 Phase 진행
         ├─ 수정 요청 → 사용자 피드백 반영 후 해당 Stage 재실행
         └─ 중단 → 파이프라인 정지, 산출물 보존
```

---

## 최종 에이전트 구성도 (총 16개)

```
┌─ 메타 에이전트 (파이프라인 지원) ─────────────────────┐
│  00-distiller  : 컨텍스트 요약 에이전트                │
│  00-judge      : 품질 평가 에이전트 (LLM-as-Judge)    │
│  00-advisor    : 의사결정 지원 에이전트                 │
├─ 비즈니스 에이전트 ──────────────────────────────────┤
│  01-biz-analyst : 사업분석                           │
│  02-pm          : 프로덕트 매니저                     │
│  03-planning    : 서비스 기획                        │
│  04-marketing   : 마케팅 + 성과분석                   │
│  05-crm         : CRM + 고객 여정                    │
├─ 설계/개발 에이전트 ─────────────────────────────────┤
│  06-design      : UI/UX 디자인                       │
│  07-db          : 데이터베이스 설계                    │
│  08-backend     : 백엔드 개발 + 코드 리뷰             │
│  09-frontend    : 프론트엔드 개발                     │
│  10-app         : 모바일 앱 개발                      │
├─ 품질/운영 에이전트 ─────────────────────────────────┤
│  11-qa          : QA + 테스트 자동화                  │
│  12-devops      : DevOps + 인프라                    │
│  13-security    : 보안 검증                          │
└──────────────────────────────────────────────────────┘
```

---

# Part III. Compaction 방어 & 병렬화


# 부록 D. Compaction 방어 — 핵심 정보 영속화 아키텍처

## 문제의 본질

Claude Code의 Compaction은 **대화 히스토리**를 요약하는 것이지, 파일 시스템의 내용을 지우는 것이 아니다. 따라서 핵심 전략은 명확하다:

> **"잃어버리면 안 되는 정보는 대화에 두지 말고, 파일에 쓴다."**

```
┌────────────────────────────────────────────────────┐
│              Compaction 동작 원리                    │
│                                                    │
│  Compaction이 건드리는 것:                           │
│  ✂️ 대화 히스토리 (이전 메시지 → 요약으로 대체)       │
│  ✂️ 도구 실행 결과 (grep, cat 등의 출력)             │
│  ✂️ 코드 diff (이미 적용된 변경사항의 diff)           │
│                                                    │
│  Compaction이 건드리지 않는 것:                      │
│  🔒 CLAUDE.md (시스템 프롬프트로 매번 재로드)         │
│  🔒 파일 시스템의 파일 내용                          │
│  🔒 .claude/settings.json 설정                     │
│  🔒 MCP 서버 설정 및 도구 정의                      │
│  🔒 Memory (auto-memory)                           │
│  🔒 Skills (로드된 스킬 정의)                        │
└────────────────────────────────────────────────────┘
```

## 전략 1: CLAUDE.md "Compact Instructions" 섹션

CLAUDE.md는 **매 턴마다 시스템 프롬프트로 재로드**되므로, Compaction의 영향을 받지 않는다. 이곳에 파이프라인의 핵심 의사결정을 기록한다.

```markdown
<!-- CLAUDE.md 에 추가 -->

## Compact Instructions

Compaction 시 반드시 보존해야 할 핵심 컨텍스트:

### 현재 파이프라인 상태
- 현재 Phase: [자동 업데이트됨]
- 현재 에이전트: [자동 업데이트됨]
- 완료된 단계: [자동 업데이트됨]

### 핵심 의사결정 레지스트리
Compaction 후에도 반드시 참조해야 할 의사결정 목록:
→ pipeline/decisions/decision-registry.md 파일 참조

### 에이전트 간 약속 (Contracts)
현재 단계에서 유효한 에이전트 간 인터페이스 계약:
→ pipeline/contracts/active-contracts.md 파일 참조

### 컨텍스트 복구 절차
Compaction 발생 후 다음 단계 실행 시:
1. pipeline/state/current-state.json 읽기
2. pipeline/decisions/decision-registry.md 읽기
3. 현재 단계에 필요한 산출물 로드 (dependency-map.md 참조)
4. 작업 계속
```

## 전략 2: Decision Registry — 의사결정 영속화 파일

모든 에이전트의 핵심 의사결정을 하나의 파일에 누적 기록한다. Compaction이 발생해도 이 파일을 읽으면 전체 맥락을 복구할 수 있다.

```markdown
<!-- pipeline/decisions/decision-registry.md -->
---
last_updated: "2026-04-16T14:00:00+09:00"
total_decisions: 12
---

# Decision Registry — 핵심 의사결정 기록부

## Phase 1: Discovery

### D-001: MVP 범위 결정
- **결정**: 진료기록 + 예방접종 + 대시보드 (수의사 매칭은 v2 연기)
- **근거**: 양면시장 콜드스타트 문제 회피, 4주 내 런칭 가능
- **영향받는 단계**: 설계, 개발, QA 전체
- **결정자**: 사업분석 에이전트 (사용자 승인 완료)

### D-002: 플랫폼 전략
- **결정**: 웹(PWA) 우선, 3개월 후 앱 출시
- **근거**: 반려동물 진료기록은 즉시성보다 정확성 중요
- **영향받는 단계**: 프론트엔드, 앱팀, DevOps

## Phase 2: Design

### D-003: DB 엔진
- **결정**: PostgreSQL (Aurora PostgreSQL Serverless v2)
- **근거**: JSONB 네이티브 지원, 유연한 메타데이터 스키마

### D-004: 아키텍처 패턴
- **결정**: 모듈러 모놀리스 (Hexagonal Architecture)
- **근거**: 1인 운영 — 마이크로서비스 운영 오버헤드 회피

### D-005: PK 전략
- **결정**: UUID v7
- **근거**: 시간순 정렬 + 분산 ID 생성 가능

### D-006: 인증 방식
- **결정**: JWT + Refresh Token rotation
- **근거**: 모바일 앱 확장 고려, Stateless 세션

## Phase 3: Build

### D-007: API 응답 포맷
- **결정**: JSON:API 스펙 준수 + cursor 기반 페이지네이션
- **근거**: 프론트엔드 상태관리 단순화, 모바일 앱 호환

### D-008: 에러 코드 체계
- **결정**: 4자리 비즈니스 에러코드 (1xxx: 인증, 2xxx: 유저, 3xxx: 펫 등)
- **근거**: 프론트엔드 에러 핸들링 일관성

(... 단계가 진행될수록 자동으로 누적 ...)
```

## 전략 3: Pipeline State Machine — 상태 파일

파이프라인의 현재 실행 상태를 JSON 파일로 영속화한다. Compaction이든 세션 재시작이든, 이 파일만 읽으면 어디서부터 이어서 해야 하는지 즉시 파악된다.

```json
// pipeline/state/current-state.json
{
  "pipeline_id": "petcare-saas-mvp-001",
  "started_at": "2026-04-16T10:00:00+09:00",
  "current_phase": "Phase 3: Build",
  "current_stage": 8,
  "current_agent": "08-backend",
  "current_task": "진료기록 CRUD API 구현",

  "completed_stages": [
    {
      "stage": 1,
      "agent": "01-biz-analyst",
      "artifact": "pipeline/artifacts/01-requirements/requirements.md",
      "quality_score": 8.5,
      "completed_at": "2026-04-16T10:30:00+09:00"
    },
    {
      "stage": 7,
      "agent": "07-db",
      "artifact": "pipeline/artifacts/04-db-schema/ddl.sql",
      "quality_score": 8.2,
      "completed_at": "2026-04-16T12:00:00+09:00"
    }
  ],

  "human_approvals": [
    {
      "checkpoint": "Discovery 완료",
      "approved_at": "2026-04-16T11:00:00+09:00",
      "conditions": ["수익 모델을 구독+제휴 커미션으로 보완"]
    },
    {
      "checkpoint": "설계 완료",
      "approved_at": "2026-04-16T12:30:00+09:00",
      "conditions": []
    }
  ],

  "active_contracts": [
    "pipeline/contracts/api-contract-v1.yaml",
    "pipeline/contracts/db-schema-v1.sql"
  ],

  "pending_issues": [
    {
      "from": "judge",
      "severity": "Minor",
      "description": "vaccinations JSONB에 GIN 인덱스 미적용",
      "target_stage": 8
    }
  ]
}
```

## 전략 4: Compaction 제어 환경변수 활용

```bash
# Claude Code 실행 시 Compaction 동작 제어

# 1. Compaction 임계값을 높여서 최대한 늦게 발동 (1M 윈도우의 95%)
export CLAUDE_AUTOCOMPACT_PCT_OVERRIDE=95

# 2. 또는 특정 토큰 수에서 발동하도록 설정
#    (1M 윈도우를 700K로 인식시켜 700K × 95% = 665K에서 발동)
export CLAUDE_CODE_CONTEXT_WINDOW_OVERRIDE=700000

# 3. 자동 Compaction 완전 비활성화 (수동 /compact만 사용)
export DISABLE_COMPACT=1
```

### 에이전트 팀 플랫폼에서의 권장 설정

```bash
# Phase 1~2 (Discovery/Design): 산출물이 적으므로 Compaction 불필요
export DISABLE_COMPACT=1

# Phase 3 (Build): 코드 생성으로 컨텍스트 빠르게 증가
# → 도메인별 서브태스크 분할로 대응 (Compaction 발동 전에 서브태스크 완료)
export CLAUDE_AUTOCOMPACT_PCT_OVERRIDE=90

# Phase 4 (Verify): Full Context 필요
# → 서브에이전트로 분리하여 각각 깨끗한 컨텍스트에서 실행
export DISABLE_COMPACT=1
```

## 전략 5: 커스텀 Compact Prompt (수동 /compact 시)

```markdown
<!-- CLAUDE.md에 추가 -->

## Custom Compact Focus

/compact 실행 시 다음을 반드시 보존:
1. pipeline/state/current-state.json의 현재 상태
2. 현재 구현 중인 파일 목록과 각 파일의 구현 진행도
3. 발견된 버그 또는 기술적 결정사항
4. 다음 구현해야 할 항목 목록

보존하지 않아도 되는 것:
- grep/find 등 탐색 결과의 상세 내용
- 이미 파일에 저장된 코드의 전체 내용
- 이전 단계 산출물의 상세 내용 (파일로 참조 가능)
```

---

# 부록 E. 128K Output 전략 — 대규모 코드 생성 최적화

## Opus 4.7 출력 스펙

- **Max Output Tokens**: 128K (Opus 4.7), 64K (Sonnet 4.6)
- **컨텍스트 윈도우**: 1M 토큰
- **실질 코드 생성량**: 128K 토큰 ≈ **약 3,000~4,000줄의 코드** (언어/주석 밀도에 따라 다름)

## 기존 분할 전략 vs 대규모 일괄 생성

```
┌──────────────────────────────────────────────────────────────┐
│              전략 비교 (백엔드 12개 도메인 구현 기준)            │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  전략 A: 도메인 단위 분할 (기존)                               │
│  ─────────────────────────                                   │
│  12회 호출 × 평균 30K 출력 = 360K 총 출력 토큰               │
│  12회 호출 × 평균 50K 입력 = 600K 총 입력 토큰               │
│  총 비용: 입력 $3.00 + 출력 $9.00 = $12.00                  │
│  시간: 12회 × 평균 2분 = ~24분 (순차)                        │
│  장점: 각 도메인 독립 검증 가능, 실패 시 해당 도메인만 재시도  │
│  단점: 도메인 간 인터페이스 불일치 가능성                     │
│                                                              │
│  전략 B: 레이어 단위 대규모 생성 (128K 활용)                   │
│  ──────────────────────────────────                          │
│  4회 호출 × 평균 100K 출력 = 400K 총 출력 토큰               │
│  4회 호출 × 평균 80K 입력 = 320K 총 입력 토큰                │
│  총 비용: 입력 $1.60 + 출력 $10.00 = $11.60                 │
│  시간: 4회 × 평균 5분 = ~20분 (순차)                         │
│  장점: 레이어 내 일관성 보장, 호출 횟수 대폭 감소            │
│  단점: 실패 시 전체 레이어 재시도 필요                        │
│                                                              │
│  전략 C: 하이브리드 (권장)                                    │
│  ──────────────────────                                      │
│  핵심 구조 일괄 생성 (1회, 128K) + 도메인별 비즈니스 로직     │
│  총 비용: ~$10~13                                            │
│  시간: ~18분                                                 │
│  장점: 구조적 일관성 + 도메인 독립성 모두 확보                │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

## 권장: 하이브리드 전략 C 상세 설계

### Step 1: Scaffolding Pass (1회, 128K 출력 활용)

한 번의 대규모 호출로 프로젝트의 **골격 전체**를 생성한다.

```
생성 대상 (한 번에):
├── 모든 Entity 클래스 (12개 도메인)
├── 모든 Repository 인터페이스
├── 모든 UseCase 인터페이스 (Port)
├── 모든 DTO (Request/Response)
├── 모든 Controller 스켈레톤 (엔드포인트 정의 + TODO 바디)
├── 공통 모듈 (예외 처리, 응답 래퍼, 인증 필터)
├── application.yml 설정
└── build.gradle.kts 의존성

예상 출력: ~100K 토큰 (3,000줄)
```

**이 단계의 핵심 가치**: 모든 도메인의 인터페이스가 한 번에 정의되므로, 도메인 간 타입 불일치 문제가 원천 차단된다.

### Step 2: Domain Implementation Pass (도메인당 1회)

각 도메인의 비즈니스 로직만 개별적으로 구현한다. Step 1의 인터페이스를 계약으로 준수한다.

```
도메인별 생성 (예: medical_records 도메인):
├── MedicalRecordService (UseCase 구현체)
├── MedicalRecordRepositoryImpl (JPA Specification)
├── MedicalRecordController (TODO 바디 → 실제 구현)
├── 도메인 이벤트 핸들러
└── 단위 테스트

예상 출력: ~20K~40K 토큰/도메인
```

### Step 3: Integration Pass (1회, 128K 출력 활용)

모든 도메인이 구현된 후, 통합 레이어를 한 번에 생성한다.

```
생성 대상 (한 번에):
├── Spring Security 설정 (전체 인증/인가 흐름)
├── 글로벌 예외 핸들러 (모든 비즈니스 예외 매핑)
├── API 문서 설정 (OpenAPI/Swagger)
├── 통합 테스트 (@SpringBootTest + Testcontainers)
├── 시드 데이터 (테스트/개발용)
└── Docker 설정 (Dockerfile + docker-compose.yml)

예상 출력: ~80K 토큰
```

### CLAUDE.md에 추가할 생성 규칙

```markdown
## 코드 생성 전략 (128K Output 활용)

### Scaffolding Pass 규칙
1. 모든 public 인터페이스를 한 번에 정의
2. 구현체 바디는 TODO 주석으로 남기되, 메서드 시그니처는 완전히 정의
3. DTO는 모든 필드 + validation 어노테이션까지 포함
4. Entity 간 관계 매핑(@ManyToOne 등)까지 완전히 정의
5. 출력 후 컴파일 성공 확인 (./gradlew compileJava)

### Domain Pass 규칙
1. Scaffolding에서 정의한 인터페이스를 반드시 구현
2. 인터페이스 시그니처 변경 금지 (변경 필요 시 별도 리팩토링 태스크)
3. 각 도메인 구현 완료 후 단위 테스트 실행하여 검증
4. pipeline/contracts/ 의 API 계약과 일치 확인

### Integration Pass 규칙
1. 모든 도메인의 구현이 완료된 후에만 실행
2. 통합 테스트는 Happy Path + 핵심 에러 케이스 포함
3. 실행 후 전체 테스트 스위트 통과 확인
```

### 프론트엔드 적용 (동일 패턴)

```
Step 1: Scaffolding (1회, 128K)
  → 라우팅 전체, 레이아웃, UI 기본 컴포넌트, API 클라이언트 타입, Zustand 스토어

Step 2: Feature Pass (기능당 1회)
  → 각 페이지의 실제 구현 (데이터 fetching + UI 로직)

Step 3: Polish Pass (1회, 128K)
  → 에러 바운더리, 로딩 상태, 반응형, 접근성, SEO 메타데이터
```

---

# 부록 F. Agent Teams 병렬화 설계

## Agent Teams 스펙 요약

- **정체**: 여러 Claude Code 세션을 팀으로 조직하는 실험적 기능
- **구조**: Team Lead(1) + Teammates(2~16), 각각 독립 1M 컨텍스트
- **통신**: 공유 태스크 리스트 + 피어 투 피어 메시지 (SendMessage)
- **격리**: 각 Teammate는 별도 git worktree에서 작업 가능
- **비용**: 단일 세션 대비 3~7x 토큰 사용
- **활성화**: `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`

## 현재 파이프라인의 병렬화 가능성 분석

### 의존성 그래프

```
                    ┌──────────┐
                    │ 사용자   │
                    │ 요구사항 │
                    └────┬─────┘
                         │
                    ┌────▼─────┐
                    │ 01-사업  │
                    │    분석  │
                    └────┬─────┘
                         │
                    ┌────▼─────┐
                    │ 02-PM    │
                    │   PRD    │
                    └────┬─────┘
                         │
          ┌──────────────┼──────────────┐
          │              │              │
    ┌─────▼─────┐ ┌─────▼─────┐ ┌─────▼─────┐
    │ 04-마케팅 │ │ 05-CRM    │ │ 03-기획   │
    │ GTM/경쟁사│ │ 고객여정  │ │ 기능명세  │  ← 병렬 가능! ✅
    └─────┬─────┘ └─────┬─────┘ └────┬──────┘
          │              │             │
          └──────────────┘      ┌──────┼──────┐
                                │      │      │
                          ┌─────▼──┐ ┌─▼────┐ │
                          │06-디자인│ │07-DB │ │  ← 병렬 가능! ✅
                          │ 시스템 │ │ 설계 │ │
                          └───┬────┘ └──┬───┘ │
                              │         │     │
                         ┌────▼─────────▼─────▼──┐
                         │   API 스펙 통합 (PM)   │  ← 동기화 지점
                         └────┬──────────────┬───┘
                              │              │
                    ┌─────────▼──┐     ┌─────▼──────┐
                    │ 08-백엔드  │     │ 09-프론트   │
                    │            │     │             │  ← 병렬 가능! ✅
                    └─────┬──────┘     └──────┬──────┘
                          │                   │
                    ┌─────▼───────────────────▼──┐
                    │     통합 빌드 (DevOps)       │  ← 동기화 지점
                    └─────┬──────────────────────┘
                          │
          ┌───────────────┼───────────────┐
          │               │               │
    ┌─────▼─────┐  ┌─────▼─────┐  ┌─────▼─────┐
    │ 11-QA     │  │ 코드 리뷰 │  │ 13-보안   │
    │ 테스트    │  │ (08 리뷰) │  │ 검증      │  ← 병렬 가능! ✅
    └───────────┘  └───────────┘  └───────────┘
```

### 병렬화 가능 구간 (4개)

```yaml
parallel_zones:
  zone_1_discovery:
    name: "Discovery 병렬 탐색"
    parallel_agents: [04-marketing, 05-crm, 03-planning]
    prerequisite: "02-pm (PRD 완료)"
    sync_point: "Phase 1 산출물 통합 + 인간 승인 #1"
    estimated_speedup: "3x → 순차 4.5시간 → 병렬 1.5시간"

  zone_2_design:
    name: "설계 병렬 작업"
    parallel_agents: [06-design, 07-db]
    prerequisite: "03-planning (기능명세 완료)"
    sync_point: "API 스펙 통합 (PM 에이전트가 조율)"
    estimated_speedup: "2x → 순차 3시간 → 병렬 1.5시간"
    note: "디자인과 DB는 독립적이므로 충돌 위험 매우 낮음"

  zone_3_build:
    name: "개발 병렬 구현"
    parallel_agents: [08-backend, 09-frontend, 10-app]
    prerequisite: "API 스펙 통합 완료 (계약 확정)"
    sync_point: "통합 빌드 성공"
    estimated_speedup: "2~3x → 순차 2주 → 병렬 5~7일"
    critical_constraint: "API 계약(Contract)이 확정된 상태에서만 병렬 시작"

  zone_4_verify:
    name: "검증 병렬 실행"
    parallel_agents: [11-qa, "08-backend(review)", 13-security]
    prerequisite: "통합 빌드 성공"
    sync_point: "검증 리포트 통합 + 인간 승인 #3"
    estimated_speedup: "3x → 순차 6시간 → 병렬 2시간"
```

## Agent Teams 구성 설계

### Zone 3 (Build) — 가장 가치가 높은 병렬화

```markdown
# Agent Teams 구성: Build Phase

## Team Lead 프롬프트

프로젝트 [petcare-saas]의 Build Phase를 Agent Teams로 실행합니다.

### 팀 구성
Team Lead: Build Orchestrator (API 계약 조율 + 통합 검증)
Teammate 1: Backend Engineer — FastAPI + Python 3.12 백엔드 구현 (SQLAlchemy 2.0 async · Alembic · APScheduler)
Teammate 2: Frontend Engineer — Next.js 프론트엔드 구현
Teammate 3: QA Engineer — 구현과 동시에 테스트 코드 작성 (TDD 지원)

### 작업 분배
- Backend: src/backend/ 소유, API 엔드포인트 구현
- Frontend: src/frontend/ 소유, UI 컴포넌트 구현
- QA: tests/ 소유, Backend/Frontend 구현에 맞춰 테스트 작성

### 계약 파일 (변경 금지)
- pipeline/contracts/api-contract-v1.yaml (OpenAPI 스펙)
- pipeline/contracts/db-schema-v1.sql (DDL)
- pipeline/artifacts/06-design-system/design-tokens.json

### 통신 규칙
- Backend가 API 응답 스키마를 변경해야 할 경우 → Team Lead에게 메시지
- Frontend가 새 API 엔드포인트를 요청할 경우 → Team Lead에게 메시지
- Team Lead가 양쪽 합의 후 계약 파일 업데이트
- QA는 구현 완료 알림을 받으면 해당 기능의 테스트 작성 시작

### Git Worktree 전략
- Backend: branch `feat/backend-impl`, worktree `src-backend/`
- Frontend: branch `feat/frontend-impl`, worktree `src-frontend/`
- QA: branch `feat/tests`, worktree `tests/`
- Team Lead: branch `main`, 최종 머지 담당
```

### 충돌 방지 아키텍처

```
┌─────────────────────────────────────────────────────┐
│              충돌 방지 전략 (3중 방어)                 │
│                                                     │
│  1️⃣ Contract-First Design (계약 우선 설계)            │
│     API 계약(OpenAPI)이 확정된 후에만 구현 시작        │
│     계약 변경은 Team Lead만 가능 (계약 파일 잠금)       │
│                                                     │
│  2️⃣ File Ownership (파일 소유권)                      │
│     각 Teammate가 소유한 디렉토리만 수정 가능           │
│     src/backend/ → Backend 전용                      │
│     src/frontend/ → Frontend 전용                    │
│     tests/ → QA 전용                                 │
│     shared/ → Team Lead만 수정 가능                   │
│                                                     │
│  3️⃣ Git Worktree Isolation (워크트리 격리)             │
│     각 Teammate가 별도 브랜치에서 작업                  │
│     머지는 Team Lead가 순차적으로 수행                  │
│     머지 충돌 발생 시 Team Lead가 해결                  │
└─────────────────────────────────────────────────────┘
```

### 공유 파일 (Shared Types) 충돌 해결

```markdown
## 공유 타입 관리 전략

### 문제
Backend의 DTO와 Frontend의 API 클라이언트 타입이 동일해야 한다.
양쪽이 독립적으로 타입을 정의하면 불일치 발생.

### 해결: 단일 진실의 원천 (Single Source of Truth)

1. OpenAPI 스펙(api-contract-v1.yaml)이 유일한 진실의 원천
2. Backend: OpenAPI 스펙에서 DTO를 생성하거나 스펙에 맞춰 수동 작성
3. Frontend: OpenAPI 스펙에서 TypeScript 타입을 자동 생성
   → `npx openapi-typescript pipeline/contracts/api-contract-v1.yaml -o src/frontend/types/api.d.ts`
4. QA: OpenAPI 스펙 기반으로 API 테스트 케이스 자동 생성

### 타입 변경 워크플로우
Backend가 응답 필드 추가 필요 발견
  → Team Lead에게 메시지: "vaccinations 응답에 next_due_date 필드 추가 필요"
  → Team Lead가 OpenAPI 스펙 업데이트
  → Team Lead가 Frontend에게 메시지: "API 타입 재생성 필요"
  → Frontend가 타입 재생성 + 해당 컴포넌트 업데이트
```

## 전체 파이프라인 병렬화 적용 시 타임라인 비교

```
[순차 실행 — 기존 설계]
Phase 1: ██████████████ (4.5시간)
Phase 2: ████████████ (3시간)
Phase 3: ████████████████████████████████████████ (2주)
Phase 4: ██████████████████ (6시간)
Phase 5: ████████ (2시간)
────────────────────────────────
총: ~2.5주

[Agent Teams 병렬화 적용]
Phase 1: █████ (1.5시간) — Zone 1: 마케팅/CRM/기획 병렬
Phase 2: ██████ (1.5시간) — Zone 2: 디자인/DB 병렬
Phase 3: ███████████████████ (5~7일) — Zone 3: BE/FE/QA 병렬
Phase 4: ██████ (2시간) — Zone 4: QA/리뷰/보안 병렬
Phase 5: ████████ (2시간) — 순차 유지 (배포는 병렬화 불가)
────────────────────────────────
총: ~1~1.5주

예상 시간 절감: 40~50%
추가 비용: 단일 세션 대비 3~4x 토큰 (Zone 3 기준)
```

## Agent Teams 사용 시 주의사항

```markdown
### 알려진 제한사항 (2026년 4월 기준)
1. 세션 재개 미지원: Teammates가 중단되면 처음부터 재시작
   → 대응: 각 Teammate의 진행 상태를 파일로 영속화
   → pipeline/state/teammate-{name}-progress.json

2. VS Code 확장에서 불안정: 터미널 + tmux 사용 권장

3. Teammate 권한 격리 불가: Team Lead의 권한 설정을 상속
   → 대응: 프로젝트 .claude/settings.json에서 사전 승인 규칙 설정

4. 토큰 비용 선형 증가: 3 Teammates = 단일 세션의 ~4x
   → 대응: Build Phase(Zone 3)에서만 Agent Teams 사용
   → Discovery/Design은 순차(서브에이전트) 유지

### 비용 최적화 가이드
Phase 1~2: 순차 실행 (서브에이전트) — 비용 효율적
Phase 3:   Agent Teams (3 Teammates) — 시간 절감이 비용 정당화
Phase 4:   Agent Teams (3 Teammates) — 독립 검증이므로 병렬 최적
Phase 5:   순차 실행 — 배포는 병렬화 불가

예상 총 비용: $40~80 (전체 파이프라인, Agent Teams 포함)
→ 1인 창업자의 2주 시간 절감 대비 충분히 합리적
```

---

# Part IV. Scaffolding & 한국 기업 특화


# 부록 G. 메타 에이전트 — `/project:init-agent-team`

## 개요

이 슬래시 커맨드 하나로 앞선 설계서 전체(작업계획서 + 확장 3편)의 디렉토리 구조, AGENT.md 16개, CLAUDE.md, 슬래시 커맨드, 품질 게이트, 프로토콜 파일을 **한 번에 자동 생성**한다.

## 슬래시 커맨드 정의

```
.claude/commands/init-agent-team.md
```

```markdown
<!-- .claude/commands/init-agent-team.md -->
---
name: init-agent-team
description: AI 에이전트 팀 플랫폼 전체 Scaffolding 생성
allowed-tools: Bash, Read, Write, Edit
---

# AI Agent Team Scaffolding Generator

사용자가 제공한 프로젝트 정보를 기반으로 전체 에이전트 팀 인프라를 생성합니다.

## 입력 파라미터
$ARGUMENTS 형식:
```
프로젝트명: [프로젝트명]
설명: [한 줄 설명]
기술스택: [backend: spring-boot-java | nestjs | fastapi]
          [frontend: nextjs | nuxtjs | react-vite]
          [mobile: react-native | flutter | none]
          [db: postgresql | mysql | mssql]
          [infra: aws | gcp | azure]
컨벤션: [naver | google | toss | custom]
언어: [ko | en]
```

## 실행 단계

### Phase 0: 입력 파싱 및 검증
1. $ARGUMENTS를 파싱하여 변수에 저장
2. 누락된 필드는 기본값 적용:
   - backend: spring-boot-java
   - frontend: nextjs
   - mobile: none
   - db: postgresql
   - infra: aws
   - convention: naver
   - language: ko

### Phase 1: 디렉토리 구조 생성
```bash
mkdir -p {agents/{_shared,00-distiller,00-judge,00-advisor,\
01-biz-analyst,02-pm,03-planning,04-marketing,05-crm,\
06-design,07-db,08-backend,09-frontend,10-app,11-qa,\
12-devops,13-security}/{templates,examples},\
pipeline/{stages,artifacts/{00-input,01-requirements,02-prd,\
03-design-spec,04-db-schema,05-api-spec,06-code,\
07-test-results,08-review-report,09-security-audit,\
10-deploy-log,11-analytics},\
state,decisions,contracts},\
.claude/commands,\
src/{backend,frontend,mobile,shared},\
docs,conventions}
```

### Phase 2: CLAUDE.md 생성
프로젝트 정보를 주입하여 글로벌 오케스트레이터 생성:
- 프로젝트명, 기술스택 정보 반영
- 파이프라인 5단계 정의
- 에이전트 호출 규칙
- Compact Instructions 섹션
- 컨텍스트 로딩 전략 (1M 최적화)
- 코드 생성 전략 (128K 하이브리드)

### Phase 3: 에이전트 AGENT.md 16개 생성
각 에이전트의 기술스택 파라미터를 반영하여 생성:
- 기술스택별 코딩 컨벤션 자동 적용
  - spring-boot-java → 네이버 Java 컨벤션 + Java 21 모던 패턴
  - nextjs → NHN FE 컨벤션 + ESLint/Prettier 설정
- 컨벤션 프리셋(naver/google/toss) 반영
- 산출물 스키마 + Few-shot 예시 경로 설정

### Phase 4: 공유 프로토콜 파일 생성
- agents/_shared/context-protocol.md
- agents/_shared/output-schema.md
- agents/_shared/quality-gates.md
- pipeline/dependency-map.md (에이전트별 컨텍스트 로딩 맵)
- pipeline/stages.md
- pipeline/handoff-protocol.md

### Phase 5: 슬래시 커맨드 7개 생성
- .claude/commands/kickoff.md
- .claude/commands/plan.md
- .claude/commands/design.md
- .claude/commands/develop.md
- .claude/commands/test.md
- .claude/commands/review.md
- .claude/commands/deploy.md

### Phase 6: 설정 파일 생성
- .claude/settings.json (Agent Teams 활성화, 권한 사전 승인)
- pipeline/state/current-state.json (초기 상태)
- pipeline/decisions/decision-registry.md (빈 템플릿)
- conventions/ 하위에 선택된 컨벤션 레퍼런스

### Phase 7: 검증 및 보고
- 생성된 파일 수 카운트
- 디렉토리 구조 트리 출력
- 누락 파일 확인
- 사용자에게 최종 보고

## 출력 예시
```
✅ AI Agent Team Scaffolding 생성 완료!

프로젝트: petcare-saas
기술스택: FastAPI + Python 3.12 / Next.js / PostgreSQL / AWS
컨벤션: PEP 8 + ruff + mypy strict

생성된 파일:
├── CLAUDE.md (글로벌 오케스트레이터)
├── agents/ (16개 에이전트 AGENT.md)
├── pipeline/ (프로토콜 + 상태관리)
├── .claude/commands/ (7개 슬래시 커맨드)
└── conventions/ (PEP 8 + FastAPI 컨벤션 레퍼런스)

총 72개 파일 생성

다음 단계: /project:kickoff [요구사항]
```
```

## CLAUDE.md 생성 템플릿 (핵심 발췌)

```markdown
<!-- 메타 에이전트가 생성하는 CLAUDE.md 템플릿 -->

# {{PROJECT_NAME}} — AI Agent Team Orchestrator

## 프로젝트 정보
- **이름**: {{PROJECT_NAME}}
- **설명**: {{DESCRIPTION}}
- **기술스택**: {{BACKEND}} / {{FRONTEND}} / {{DB}} / {{INFRA}}
- **컨벤션**: {{CONVENTION_PRESET}}

## 기술 스택 상세
{{#if BACKEND == "spring-boot-java"}}
### Backend: Spring Boot 3.x + Java 21
- 아키텍처: Hexagonal (Ports & Adapters)
- 빌드: Gradle (Groovy 또는 Kotlin DSL)
- 테스트: JUnit 5 + Mockito + Testcontainers
- 컨벤션: {{CONVENTION_BACKEND_REF}}
{{/if}}

{{#if FRONTEND == "nextjs"}}
### Frontend: Next.js 15 + TypeScript
- 라우팅: App Router
- 상태관리: TanStack Query (서버) + Zustand (클라이언트)
- 스타일: Tailwind CSS
- 테스트: Vitest + Playwright
- 컨벤션: {{CONVENTION_FRONTEND_REF}}
{{/if}}

## Compact Instructions
Compaction 시 반드시 보존:
- pipeline/state/current-state.json의 현재 상태
- pipeline/decisions/decision-registry.md의 핵심 의사결정
- pipeline/contracts/ 의 API/DB 계약
- 현재 구현 진행 상태
```

## .claude/settings.json 생성 템플릿

```json
{
  "env": {
    "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1",
    "CLAUDE_AUTOCOMPACT_PCT_OVERRIDE": "90"
  },
  "permissions": {
    "allow": [
      "Read(./src/**)",
      "Write(./src/**)",
      "Read(./pipeline/**)",
      "Write(./pipeline/**)",
      "Bash(npm:*)",
      "Bash(npx:*)",
      "Bash(gradle:*)",
      "Bash(./gradlew:*)",
      "Bash(git:*)",
      "Bash(docker:*)"
    ],
    "deny": [
      "Read(./.env)",
      "Read(./.env.*)",
      "Read(./secrets/**)"
    ]
  }
}
```

---

# 부록 H. 한국 기업 환경 특화 — 컨벤션 프리셋

## 컨벤션 프리셋 시스템

```
conventions/
├── presets/
│   ├── naver/                    # 네이버 프리셋
│   │   ├── backend-java.md       # 네이버 캠퍼스 핵데이 Java 컨벤션
│   │   ├── backend-java.md       # 네이버 Java 컨벤션 + Java 21 모던 패턴
│   │   ├── frontend-js.md        # NHN TOAST UI FE 컨벤션
│   │   ├── frontend-ts.md        # TypeScript 확장
│   │   ├── markup.md             # NHN 마크업 코딩 컨벤션
│   │   ├── checkstyle-rules.xml  # 네이버 Checkstyle 룰
│   │   ├── .editorconfig         # 네이버 스타일 에디터 설정
│   │   └── .eslintrc.json        # NHN ESLint 설정
│   │
│   ├── toss/                     # 토스 프리셋
│   │   ├── design-system.md      # TDS 컴포넌트 가이드
│   │   ├── frontend-react.md     # 토스 React/RN 패턴
│   │   ├── api-design.md         # 토스 API 설계 원칙
│   │   ├── error-message.md      # 토스 에러 메시지 가이드
│   │   ├── ux-writing.md         # 토스 UX 라이팅 가이드
│   │   └── design-tokens.json    # TDS 디자인 토큰
│   │
│   ├── kakao/                    # 카카오 프리셋
│   │   ├── api-design.md         # 카카오 REST API 가이드
│   │   ├── frontend.md           # 카카오 FE 컨벤션
│   │   └── sdk-integration.md    # 카카오 SDK 연동 패턴
│   │
│   └── google/                   # 구글 프리셋 (국제 표준)
│       ├── java-style.md         # Google Java Style Guide
│       ├── typescript-style.md   # Google TypeScript Style Guide
│       └── api-design.md         # Google API Design Guide
│
└── custom/                       # 프로젝트별 커스텀
    └── overrides.md              # 프리셋 위에 덮어쓸 규칙
```

## 프리셋 1: 네이버 (naver)

### 백엔드 에이전트에 주입할 컨벤션 — `conventions/presets/naver/backend-java.md`

```markdown
# 네이버 Java 코딩 컨벤션 요약

## 출처
- 네이버 캠퍼스 핵데이 Java 코딩 컨벤션: https://naver.github.io/hackday-conventions-java/
- Java 21 공식 스타일: Record, Sealed Class, Pattern Matching 등 모던 Java 활용

## 핵심 규칙 (에이전트가 코드 생성 시 준수)

### 들여쓰기 및 포매팅
- 하드탭 사용 (탭 크기 4 스페이스)
- 최대 줄 너비: 120자
- 줄바꿈 시 연산자 전에서 끊기

### import 정렬
- 순서: java.* → javax.* → org.* → net.* → 그 외
- static import는 일반 import 아래에 별도 그룹
- 와일드카드(*) import는 static import에만 허용

### 네이밍
- 클래스: PascalCase (UserService, PetRepository)
- 메서드/변수: camelCase (findByUserId, petName)
- 상수: UPPER_SNAKE_CASE (MAX_RETRY_COUNT)
- 패키지: 소문자 (com.company.petcare.domain.pet)
- 테스트 메서드: @DisplayName 한글 허용 ("진료기록을 생성하면 200 반환")

### Java 21 모던 패턴 (적극 활용)
- record: 불변 DTO에 사용 (기존 POJO + Lombok 대체)
- sealed interface/class: 비즈니스 에러 타입 정의에 사용 (Java 17+)
- pattern matching: instanceof 대신 switch pattern matching (Java 21)
- Optional: null 반환 대신 Optional 활용, .orElseThrow() 패턴
- Stream API: 컬렉션 처리에 활용하되 3단계 이상 체이닝 시 가독성 검토
- text blocks: 여러 줄 문자열에 """ 사용 (SQL, JSON 등)
- var: 로컬 변수 타입 추론 (단, 타입이 명확한 경우에만)

### Spring Boot 규칙
- @RestController + @RequestMapping: API 엔드포인트
- @Service: 비즈니스 로직 (인터페이스 → 구현체 분리)
- @Repository: 데이터 접근 (Spring Data JPA + @Query + Specification)
- @Transactional: 읽기 전용 시 readOnly = true
- 예외: @ExceptionHandler + @ControllerAdvice
- Lombok: @Getter, @Builder, @RequiredArgsConstructor 활용
  (단, Entity에는 @Setter 사용 금지)

## Checkstyle 설정 파일 경로
- conventions/presets/naver/checkstyle-rules.xml
- Gradle 연동: `id("checkstyle")` 플러그인 적용
```

### 프론트엔드 에이전트에 주입할 컨벤션 — `conventions/presets/naver/frontend-ts.md`

```markdown
# NHN/네이버 프론트엔드 TypeScript 컨벤션

## 출처
- TOAST UI 코딩 컨벤션: https://ui.toast.com/fe-guide/ko_CODING-CONVENTION
- NHN 마크업 코딩 컨벤션: https://nuli.navercorp.com/

## 핵심 규칙

### 들여쓰기
- 공백 2개 사용 (NHN FE개발랩 기준)

### 변수/함수 네이밍
- 변수/함수: camelCase
- 컴포넌트: PascalCase
- 상수: UPPER_SNAKE_CASE
- boolean: is/has/can 접두사 (isLoading, hasPermission)
- 이벤트 핸들러: handle 접두사 (handleSubmit, handleClick)

### TypeScript 전용
- any 사용 금지 → unknown 또는 구체 타입 사용
- interface vs type: 객체 형태는 interface, 유니온/교차는 type
- enum 대신 const object + as const 패턴 권장
- non-null assertion(!) 사용 금지

### React/Next.js 규칙
- 컴포넌트: 함수형 + TypeScript strict mode
- props: interface로 정의, Props 접미사 (ButtonProps)
- hooks: use 접두사 필수 (useAuth, usePets)
- 상태: 서버 상태는 TanStack Query, UI 상태는 useState/Zustand
- 조건부 렌더링: 삼항연산자보다 && 또는 early return

### ESLint/Prettier 설정
\`\`\`json
// .eslintrc.json (NHN 기반)
{
  "extends": [
    "next/core-web-vitals",
    "next/typescript",
    "prettier"
  ],
  "rules": {
    "no-var": "error",
    "prefer-const": "error",
    "no-unused-vars": ["error", { "argsIgnorePattern": "^_" }],
    "@typescript-eslint/no-explicit-any": "error",
    "@typescript-eslint/no-non-null-assertion": "error",
    "react/self-closing-comp": "error",
    "react/jsx-curly-brace-presence": ["error", "never"]
  }
}
\`\`\`
```

## 프리셋 2: 토스 (toss)

### 디자인 에이전트에 주입할 컨벤션 — `conventions/presets/toss/design-system.md`

```markdown
# TDS (Toss Design System) 컨벤션

## 출처
- TDS 공식: https://tossmini-docs.toss.im/tds-mobile/
- 토스 디자인 블로그: https://toss.tech

## TDS 핵심 원칙
1. 일관된 UI: 모든 화면에서 동일한 컴포넌트 사용
2. 생산성: 재사용 가능한 컴포넌트로 UI 개발 효율화
3. 접근성: 모든 컴포넌트에 접근성 기본 탑재 (VoiceOver/TalkBack)
4. 다크모드: 시맨틱 컬러로 자동 대응

## 디자인 토큰 구조
\`\`\`json
{
  "color": {
    "primary": "#3182F6",
    "secondary": "#48BB78",
    "background": {
      "normal": "#FFFFFF",
      "elevated": "#F4F4F4",
      "dark_normal": "#1B1B1B",
      "dark_elevated": "#2C2C2C"
    },
    "text": {
      "primary": "#191F28",
      "secondary": "#4E5968",
      "tertiary": "#8B95A1",
      "dark_primary": "#FFFFFF",
      "dark_secondary": "#B0B8C1"
    },
    "status": {
      "error": "#F04452",
      "success": "#34C759",
      "warning": "#FF9500"
    }
  },
  "typography": {
    "fontFamily": "Toss Product Sans, -apple-system, sans-serif",
    "heading1": { "size": "26px", "weight": 700, "lineHeight": "34px" },
    "heading2": { "size": "22px", "weight": 700, "lineHeight": "30px" },
    "body1": { "size": "16px", "weight": 400, "lineHeight": "24px" },
    "body2": { "size": "14px", "weight": 400, "lineHeight": "20px" },
    "caption": { "size": "12px", "weight": 400, "lineHeight": "16px" }
  },
  "spacing": {
    "xs": "4px", "sm": "8px", "md": "16px",
    "lg": "24px", "xl": "32px", "xxl": "48px"
  },
  "borderRadius": {
    "sm": "8px", "md": "12px", "lg": "16px", "full": "9999px"
  }
}
\`\`\`

## 에이전트가 준수할 TDS 패턴

### 컴포넌트 구성
- Flat 패턴(단순) + Compound 패턴(복합) 혼합 사용
- 모든 컴포넌트에 기본 패딩 포함 (gap 없이 붙여도 자연스럽게)
- ListRow: S/M/L/XL 패딩 옵션 제공

### 에러 메시지 가이드 (토스 UX 라이팅)
- 해요체 사용 ("결제에 실패했어요" ✅ / "결제 실패" ❌)
- 원인 + 해결방법 포함 ("잔액이 부족해요. 충전 후 다시 시도해 주세요")
- Navigating error: 다음 화면으로 안내하는 역할
- 부정적 표현보다 긍정적 대안 제시

### 접근성 5가지 규칙
1. 열림/닫힘 시 초점 자동 이동
2. 투명 닫기 버튼 별도 배치
3. 아이콘 전용 버튼에 aria-label 필수
4. 우측 장식 아이콘은 스크린리더에서 무시
5. 큰 텍스트 모드 대응 (고정값 대신 상대 단위)
```

### 프론트엔드 에이전트에 주입 — `conventions/presets/toss/frontend-react.md`

```markdown
# 토스 프론트엔드 React 패턴

## 출처
- SLASH 21: 실무에서 바로 쓰는 Frontend Clean Code (진유림)
- SLASH 21: TDS로 UI 쌓기 (박민수)
- toss.tech 블로그 아티클들

## 핵심 패턴

### 비동기 처리 (우아하게)
- Suspense + ErrorBoundary 조합
- useQuery의 suspense 옵션 활용
- 선언적 에러 핸들링: ErrorBoundary로 에러 UI 분리

### 코드 응집도 (Clean Code)
- 하나의 컴포넌트 = 하나의 관심사
- 커스텀 훅으로 비즈니스 로직 추출
- 조건부 렌더링은 컴포넌트 분리로 해결

### 컴포넌트 패턴
\`\`\`tsx
// ✅ 토스 스타일: 선언적, Suspense 활용
function PetHealthDashboard() {
  return (
    <ErrorBoundary fallback={<DashboardError />}>
      <Suspense fallback={<DashboardSkeleton />}>
        <DashboardContent />
      </Suspense>
    </ErrorBoundary>
  );
}

// ✅ 토스 스타일: 에러 메시지
function DashboardError() {
  return (
    <ErrorMessage
      title="대시보드를 불러오지 못했어요"
      description="잠시 후 다시 시도해 주세요"
      action={{ label: "다시 시도", onClick: refetch }}
    />
  );
}
\`\`\`

### API 설계 원칙
- RESTful: 리소스 중심 URL (`/api/v1/pets/{petId}/records`)
- 응답 형식: `{ success: boolean, data: T, error?: ErrorInfo }`
- 페이지네이션: cursor 기반 (offset 지양)
- 에러 코드: 4자리 비즈니스 에러코드 체계
```

## 프리셋 3: 카카오 (kakao)

### `conventions/presets/kakao/api-design.md`

```markdown
# 카카오 API 설계 가이드라인

## 출처
- 카카오 개발자 문서: https://developers.kakao.com
- 카카오 REST API 레퍼런스

## API 설계 원칙

### URL 구조
- 기본: `https://api.domain.com/v1/{resource}`
- 복수형 리소스: `/v1/pets` (단수 사용 금지)
- 계층 관계: `/v1/pets/{petId}/vaccinations`
- 최대 3단계 중첩 (그 이상은 쿼리 파라미터로)

### 인증
- OAuth 2.0 기반 (카카오 로그인 패턴)
- Access Token: Authorization: Bearer {token}
- Refresh Token: 자동 갱신 + rotation

### 응답 형식
\`\`\`json
// 성공
{
  "data": { ... },
  "meta": {
    "page": { "cursor": "abc123", "has_next": true }
  }
}

// 에러
{
  "error": {
    "code": 2001,
    "message": "반려동물을 찾을 수 없어요",
    "detail": "petId: 12345에 해당하는 반려동물이 없습니다"
  }
}
\`\`\`

### 카카오 SDK 연동 패턴
- 카카오 로그인: REST API 또는 JavaScript SDK
- 카카오톡 공유: 메시지 API
- 카카오맵: 장소 검색 API (수의사 매칭에 활용)
```

## AGENT.md에 컨벤션 주입하는 방법

### 에이전트 AGENT.md 템플릿 (컨벤션 포함)

```markdown
# 백엔드 에이전트 (Backend Architect)

## 페르소나
(... 기존 내용 ...)

## 적용 컨벤션
{{#if CONVENTION == "naver"}}
이 프로젝트는 네이버 캠퍼스 핵데이 Java 코딩 컨벤션을 따릅니다.
반드시 conventions/presets/naver/backend-java.md를 읽고 모든 코드에 적용하세요.

핵심 요약:
- 하드탭(4 스페이스), 줄 너비 120자
- record 클래스로 불변 DTO, sealed interface로 에러 타입
- Optional 활용, null 반환 지양
- @Transactional(readOnly = true) 읽기 기본
- Lombok: @Getter, @Builder (Entity에 @Setter 금지)
{{/if}}

{{#if CONVENTION == "toss"}}
이 프로젝트는 토스 엔지니어링 표준을 따릅니다.
반드시 conventions/presets/toss/frontend-react.md를 읽고 적용하세요.

핵심 요약:
- Suspense + ErrorBoundary 선언적 비동기 처리
- 에러 메시지 해요체 ("실패했어요" + 해결방법)
- TDS 디자인 토큰 준수 (conventions/presets/toss/design-tokens.json)
- 접근성 5대 규칙 필수 적용
{{/if}}

## Few-shot 예시
(컨벤션에 맞는 코드 예시가 agents/08-backend/examples/ 에 저장됨)
```

## Few-shot 예시 구조

### 네이버 컨벤션 Few-shot (Spring Boot + Java 21)

```
agents/08-backend/examples/
├── naver/
│   ├── entity-example.java          # Entity + JPA 매핑 예시
│   ├── service-example.java         # UseCase 구현 + 트랜잭션 패턴
│   ├── controller-example.java      # REST Controller + 응답 래핑
│   ├── repository-example.java      # JPA @Query + Specification 커스텀 쿼리
│   ├── exception-example.java       # sealed interface 에러 정의 (Java 17+)
│   └── test-example.java            # JUnit 5 + Mockito 테스트
├── toss/
│   ├── component-example.tsx      # Suspense + ErrorBoundary 패턴
│   ├── hook-example.ts            # useQuery 커스텀 훅
│   ├── error-message-example.tsx  # 토스 에러 메시지 컴포넌트
│   ├── api-client-example.ts      # fetch 래퍼 + 타입 안전
│   └── test-example.test.tsx      # Vitest + RTL 테스트
└── kakao/
    ├── oauth-example.java           # 카카오 로그인 연동
    └── share-example.ts           # 카카오톡 공유 연동
```

### Few-shot 예시 파일 샘플 — `agents/08-backend/examples/naver/service-example.java`

```java
/**
 * 진료기록 관리 UseCase 구현
 *
 * 네이버 컨벤션 적용:
 * - 하드탭(4스페이스), 120자 줄너비
 * - sealed interface 에러 타입 (Java 17+)
 * - record 불변 DTO (Java 16+)
 * - @Transactional readOnly 기본
 */
@Service
@RequiredArgsConstructor
public class MedicalRecordService implements CreateMedicalRecordUseCase, GetMedicalRecordUseCase {

	private final MedicalRecordRepository medicalRecordRepository;
	private final PetRepository petRepository;
	private final ApplicationEventPublisher eventPublisher;

	@Transactional
	@Override
	public MedicalRecordId create(CreateMedicalRecordCommand command) {
		Pet pet = petRepository.findById(command.petId())
			.orElseThrow(() -> new PetNotFoundException(command.petId()));

		MedicalRecord record = MedicalRecord.create(
			pet,
			command.visitDate(),
			command.diagnosis(),
			command.treatment(),
			command.veterinarian()
		);

		MedicalRecord saved = medicalRecordRepository.save(record);

		eventPublisher.publishEvent(
			new MedicalRecordCreatedEvent(saved.getId(), pet.getId())
		);

		return saved.getId();
	}

	@Transactional(readOnly = true)
	@Override
	public CursorPage<MedicalRecordSummary> getByPetId(
			PetId petId,
			Cursor cursor,
			int size) {
		return medicalRecordRepository.findByPetIdWithCursor(petId, cursor, size);
	}
}

// DTO (record 패턴 — Java 16+)
public record CreateMedicalRecordCommand(
	PetId petId,
	LocalDate visitDate,
	String diagnosis,
	String treatment,
	String veterinarian
) {}

// 에러 타입 (sealed interface 패턴 — Java 17+)
public sealed interface MedicalRecordException {

	int errorCode();
	String message();

	record PetNotFoundException(PetId petId) implements MedicalRecordException {
		@Override
		public int errorCode() { return 3001; }

		@Override
		public String message() {
			return "반려동물을 찾을 수 없어요 (petId: " + petId + ")";
		}
	}
}
```

## 복수 프리셋 조합 지원

실무에서는 단일 프리셋만 쓰기보다 조합이 일반적이다:

```yaml
# 예: 네이버 백엔드 + 토스 프론트엔드 + 카카오 인증
convention_config:
  backend: naver       # 네이버 Java 컨벤션
  frontend: toss       # 토스 TDS + React 패턴
  api: kakao           # 카카오 API 설계 가이드
  auth: kakao          # 카카오 로그인 연동
  design: toss         # TDS 디자인 토큰
  markup: naver        # NHN 마크업 컨벤션
```

이 설정은 `/project:init-agent-team` 실행 시 각 에이전트에 자동으로 매핑된다:
- 08-backend → naver/backend-java.md
- 09-frontend → toss/frontend-react.md + toss/design-system.md
- 06-design → toss/design-system.md + toss/ux-writing.md
- 08-backend (인증 모듈) → kakao/api-design.md + kakao/sdk-integration.md

---

# Part V. Java 21 & 쿼리 전략 (⚠ 역사적 기록 — 2026-04 Python 전환 이후 비활성)

> **상태**: 본 파트(부록 I~L)는 초기 Java/Spring Boot 선택 시점(2026-03)의 설계 판단을 보존한다.
> 2026-04 **Java→Python 전면 이전**(`docs/migration/java-to-python-plan.md`) 이후 본 프로젝트의 백엔드는 **FastAPI + Python 3.12** 이며, Virtual Threads / Spring Data JPA / QueryDSL 섹션은 **현재 백엔드 구현과 무관**하다.
> 현재 백엔드 컨벤션의 권위 있는 출처: 본 문서 상단 "기술 스택 확정" 표 + `agents/08-backend/AGENT.md` + `CLAUDE.md`.

# 부록 I. Virtual Threads (Project Loom) 에이전트 규칙 (⚠ Java 21 전용, 비활성)

## 왜 Virtual Threads인가

Java 21의 Virtual Threads는 1인 기업 SaaS에서 특히 유리하다:
- **스레드풀 튜닝 불필요**: 기존 플랫폼 스레드(200개 기본) → Virtual Thread는 수백만 개 가능
- **블로킹 I/O도 OK**: DB 쿼리, 외부 API 호출 시 스레드가 점유되지 않음
- **코드 변경 최소**: 기존 동기 코드 그대로 사용, 설정만 변경

## 백엔드 에이전트 AGENT.md에 추가할 규칙

```markdown
## Virtual Threads 규칙 (Java 21+)

### Spring Boot 설정
\`\`\`yaml
# application.yml
spring:
  threads:
    virtual:
      enabled: true    # Tomcat이 Virtual Thread 사용
\`\`\`
이 한 줄로 모든 HTTP 요청이 Virtual Thread에서 처리된다.

### 사용 규칙
1. **기본 원칙**: spring.threads.virtual.enabled=true 설정 후 기존 코드 그대로 사용
2. **@Async 작업**: AsyncConfigurer에서 Virtual Thread executor 설정
   \`\`\`java
   @Configuration
   @EnableAsync
   public class AsyncConfig implements AsyncConfigurer {
       @Override
       public Executor getAsyncExecutor() {
           return Executors.newVirtualThreadPerTaskExecutor();
       }
   }
   \`\`\`
3. **병렬 외부 호출**: 여러 외부 API를 동시 호출할 때 StructuredTaskScope 활용
   \`\`\`java
   // Java 21 StructuredTaskScope (Preview)
   try (var scope = new StructuredTaskScope.ShutdownOnFailure()) {
       var petTask = scope.fork(() -> petService.findById(petId));
       var recordsTask = scope.fork(() -> recordService.findByPetId(petId));
       scope.join().throwIfFailed();
       return new PetDashboard(petTask.get(), recordsTask.get());
   }
   \`\`\`

### 금지 사항
1. **synchronized 블록 주의**: Virtual Thread가 pinning되므로 ReentrantLock 사용
   \`\`\`java
   // ❌ synchronized → Virtual Thread pinning 발생
   synchronized (this) { ... }
   
   // ✅ ReentrantLock → pinning 없음
   private final ReentrantLock lock = new ReentrantLock();
   lock.lock();
   try { ... } finally { lock.unlock(); }
   \`\`\`
2. **ThreadLocal 남용 금지**: Virtual Thread는 수명이 짧으므로 ScopedValue 검토
3. **스레드풀 직접 생성 금지**: Executors.newFixedThreadPool() 대신
   Executors.newVirtualThreadPerTaskExecutor() 사용

### 성능 기대치
- 동시 사용자 100명 기준: 플랫폼 스레드 200개 → Virtual Thread 제한 없음
- DB 커넥션이 병목: HikariCP max-pool-size가 실질적 동시성 상한
- 외부 API 호출: Circuit Breaker + Virtual Thread 조합으로 타임아웃 안전 처리
```

---

# 부록 J. Spring Data JPA 3단계 쿼리 전략

> **QueryDSL은 사용하지 않는다.** 상세 비교 및 JPA 3단계 전략(Level 1: 메서드 이름 쿼리, Level 2: @Query JPQL + Specification, Level 3: Native Query)은 **부록 L (심화 설계서 V)**에서 다룬다.

## build.gradle 핵심 의존성 (QueryDSL 없음)

```groovy
dependencies {
    implementation 'org.springframework.boot:spring-boot-starter-web'
    implementation 'org.springframework.boot:spring-boot-starter-data-jpa'
    implementation 'org.springframework.boot:spring-boot-starter-validation'
    implementation 'org.springframework.boot:spring-boot-starter-security'
    runtimeOnly 'org.postgresql:postgresql'
    compileOnly 'org.projectlombok:lombok'
    annotationProcessor 'org.projectlombok:lombok'
    testImplementation 'org.springframework.boot:spring-boot-starter-test'
    testImplementation 'org.testcontainers:junit-jupiter'
    testImplementation 'org.testcontainers:postgresql'
}
```

→ QueryDSL 관련 의존성 0개. annotation processor 설정 불필요. Q타입 빌드 에러 원천 차단.

---
# 부록 K. 모던 Java 패턴 내부 가이드 — 에이전트 자동 생성

## 개요

PM 에이전트 또는 백엔드 에이전트가 `/project:kickoff` 실행 시 `docs/modern-java-guide.md`를 자동 생성하여, 팀(또는 미래의 협업자)에게 Java 21 모던 패턴을 전파한다.

## 자동 생성되는 가이드 — `docs/modern-java-guide.md`

```markdown
# 모던 Java 21 패턴 가이드 — {{PROJECT_NAME}}

> 이 문서는 AI 에이전트가 자동 생성했으며, 프로젝트의 코딩 컨벤션으로 적용됩니다.

## 1. Record (Java 16+) — 불변 DTO의 표준

### 언제 사용하는가
- API 요청/응답 DTO
- 도메인 이벤트 페이로드
- 값 객체(Value Object)

### 사용 패턴
\`\`\`java
// ✅ record로 DTO 정의 — equals, hashCode, toString 자동 생성
public record CreatePetRequest(
    @NotBlank String name,
    @NotNull Species species,
    String breed,
    @Past LocalDate birthDate
) {}

// ✅ record로 응답 DTO
public record PetResponse(
    Long id,
    String name,
    String species,
    String breed,
    int ageInMonths
) {
    // 정적 팩토리 메서드로 Entity → DTO 변환
    public static PetResponse from(Pet pet) {
        return new PetResponse(
            pet.getId(),
            pet.getName(),
            pet.getSpecies().getDisplayName(),
            pet.getBreed(),
            pet.calculateAgeInMonths()
        );
    }
}
\`\`\`

### 사용하면 안 되는 곳
- JPA Entity (가변 상태 + 프록시 필요)
- Spring Bean (@Service, @Repository 등)

## 2. Sealed Interface (Java 17+) — 타입 안전한 에러 계층

### 언제 사용하는가
- 비즈니스 에러 타입 정의
- 상태 머신의 상태 열거
- 도메인 이벤트 계층

### 사용 패턴
\`\`\`java
// ✅ sealed interface로 에러 계층 정의
public sealed interface PetError {
    
    record NotFound(Long petId) implements PetError {}
    record AlreadyExists(String name, Long userId) implements PetError {}
    record InvalidSpecies(String species) implements PetError {}
}

// ✅ switch pattern matching으로 에러 핸들링 (Java 21)
@ExceptionHandler(PetBusinessException.class)
public ResponseEntity<ErrorResponse> handlePetError(PetBusinessException ex) {
    return switch (ex.getError()) {
        case PetError.NotFound e -> 
            ResponseEntity.status(404).body(ErrorResponse.of(3001, e.petId()));
        case PetError.AlreadyExists e -> 
            ResponseEntity.status(409).body(ErrorResponse.of(3002, e.name()));
        case PetError.InvalidSpecies e -> 
            ResponseEntity.badRequest().body(ErrorResponse.of(3003, e.species()));
    };
    // 컴파일러가 모든 케이스 처리를 강제 — 누락 시 컴파일 에러
}
\`\`\`

## 3. Pattern Matching (Java 21) — 타입 검사 간소화

\`\`\`java
// ❌ 기존: instanceof + 캐스팅
if (animal instanceof Dog) {
    Dog dog = (Dog) animal;
    dog.bark();
}

// ✅ Java 16+: pattern matching for instanceof
if (animal instanceof Dog dog) {
    dog.bark();
}

// ✅ Java 21: switch pattern matching
String description = switch (animal) {
    case Dog dog when dog.isServiceDog() -> "안내견: " + dog.getName();
    case Dog dog -> "강아지: " + dog.getName();
    case Cat cat -> "고양이: " + cat.getName();
    default -> "기타 동물";
};
\`\`\`

## 4. Text Blocks (Java 15+) — 여러 줄 문자열

\`\`\`java
// ✅ SQL 쿼리
String sql = """
    SELECT m.id, m.visit_date, m.diagnosis
    FROM medical_records m
    WHERE m.pet_id = :petId
      AND m.deleted_at IS NULL
    ORDER BY m.visit_date DESC
    LIMIT :size
    """;

// ✅ JSON 테스트 데이터
String requestBody = """
    {
        "name": "코코",
        "species": "DOG",
        "breed": "말티즈",
        "birthDate": "2023-01-15"
    }
    """;
\`\`\`

## 5. Optional 활용 — null 안전 패턴

\`\`\`java
// ❌ null 직접 반환
public Pet findById(Long id) {
    return petRepository.findById(id);  // null 가능
}

// ✅ Optional 반환
public Optional<Pet> findById(Long id) {
    return petRepository.findById(id);
}

// ✅ 호출측: orElseThrow 패턴
Pet pet = petService.findById(petId)
    .orElseThrow(() -> new PetNotFoundException(petId));

// ✅ 호출측: map + orElse 패턴
String petName = petService.findById(petId)
    .map(Pet::getName)
    .orElse("이름 없음");
\`\`\`

## 6. 프로젝트 적용 체크리스트

- [ ] DTO는 모두 record로 작성
- [ ] 비즈니스 에러는 sealed interface 계층으로 정의
- [ ] switch에서 pattern matching 활용
- [ ] SQL/JSON 등 여러 줄 문자열은 text block 사용
- [ ] null 반환 대신 Optional 사용
- [ ] synchronized 대신 ReentrantLock (Virtual Thread 호환)
- [ ] spring.threads.virtual.enabled=true 설정 확인
```

---

# Part VI. 실전 투입 준비


# 부록 L. QueryDSL vs JPA Native Query — 기술 판단

## 한 줄 결론

> **1인 기업 MVP에서는 Spring Data JPA 기본 메서드 + @Query(JPQL/Native) 조합이 최적이다.**
> QueryDSL은 "설정 복잡도 + 유지보수 비용"이 1인 운영에서 가져다주는 이점을 초과한다.

## 상세 비교표

```
┌─────────────────────┬──────────────────────┬──────────────────────┐
│        기준          │     QueryDSL         │  JPA @Query (JPQL/   │
│                     │                      │  Native Query)       │
├─────────────────────┼──────────────────────┼──────────────────────┤
│ 타입 안전성          │ ✅ 컴파일 타임 체크    │ ❌ 런타임 에러 발견   │
│                     │ (Q타입 기반)          │ (문자열 기반)         │
├─────────────────────┼──────────────────────┼──────────────────────┤
│ 초기 설정 복잡도      │ ❌ 높음               │ ✅ 제로 (JPA 기본)   │
│                     │ - annotation processor│                      │
│                     │ - Q타입 생성 경로     │                      │
│                     │ - Gradle 플러그인     │                      │
│                     │ - Jakarta 호환 이슈   │                      │
├─────────────────────┼──────────────────────┼──────────────────────┤
│ 동적 쿼리            │ ✅ 매우 강력           │ ⚠️ 가능하나 복잡     │
│ (조건 조합)          │ BooleanExpression    │ Specification 또는   │
│                     │ 조합이 깔끔           │ 문자열 concat 필요   │
├─────────────────────┼──────────────────────┼──────────────────────┤
│ 빌드 의존성          │ ❌ querydsl-jpa,      │ ✅ 추가 의존성 없음   │
│                     │ querydsl-apt 필요     │                      │
│                     │ 버전 호환성 이슈 빈발  │                      │
├─────────────────────┼──────────────────────┼──────────────────────┤
│ AI 에이전트 코드 생성 │ ⚠️ Q타입 생성 필요    │ ✅ 즉시 실행 가능     │
│ 호환성               │ 빌드 후에야 참조 가능  │ 문자열이라 빌드 불필요│
├─────────────────────┼──────────────────────┼──────────────────────┤
│ 학습 곡선            │ ⚠️ 중간               │ ✅ 낮음 (SQL 아는    │
│                     │ (Q타입, Projection)   │  개발자면 즉시 사용)  │
├─────────────────────┼──────────────────────┼──────────────────────┤
│ DB 이식성            │ ✅ JPQL 기반이라 높음  │ ⚠️ Native는 DB 종속  │
│                     │                      │ JPQL은 이식성 높음   │
├─────────────────────┼──────────────────────┼──────────────────────┤
│ 리팩토링 안전성       │ ✅ 필드명 변경 시     │ ❌ 문자열 내부 필드명 │
│                     │ 컴파일 에러로 감지     │ 수동 검색 필요       │
├─────────────────────┼──────────────────────┼──────────────────────┤
│ 프로젝트 규모 적합성  │ 중~대규모             │ 소~중규모            │
│                     │ (동적 검색 조건 多)    │ (고정 쿼리 위주)     │
├─────────────────────┼──────────────────────┼──────────────────────┤
│ Spring Boot 3.x     │ ⚠️ Jakarta 마이그레이션│ ✅ 기본 내장         │
│ 호환성               │ 이슈 있었음           │ 호환성 문제 없음     │
├─────────────────────┼──────────────────────┼──────────────────────┤
│ 유지보수 (1인 운영)   │ ❌ Q타입 빌드 에러,   │ ✅ 의존성 적음,      │
│                     │ 버전 충돌 디버깅       │ 디버깅 단순          │
└─────────────────────┴──────────────────────┴──────────────────────┘
```

## 1인 기업 MVP에서 QueryDSL이 비추인 핵심 이유

### 1. 설정 지옥 (Setup Hell)
```
Spring Boot 3.x + Java 21 + QueryDSL 설정 시 흔한 에러:
- jakarta.persistence vs javax.persistence 충돌
- querydsl-apt:jakarta classifier 누락
- Q타입이 generated 폴더에 안 생김
- IntelliJ에서 Q타입 import 빨간줄
- Gradle 캐시 문제로 Q타입 갱신 안 됨

→ 이 설정 이슈만으로 반나절~하루 소요 (1인 기업에서 치명적)
```

### 2. AI 에이전트 코드 생성과의 궁합
```
QueryDSL: 에이전트가 코드 생성 → Q타입이 아직 없음 → 컴파일 에러
         → ./gradlew compileJava 실행 → Q타입 생성 → 다시 참조
         → 에이전트가 Q타입 경로를 인식 못하는 경우 빈발

Native Query: 에이전트가 코드 생성 → 문자열 쿼리 포함 → 즉시 컴파일 가능
             → 빌드 없이 코드 리뷰/테스트 가능
```

### 3. 20년 경력 관점에서의 현실적 판단
```
- MVP 단계에서 동적 검색 조건이 10개 이상인 경우는 극히 드뭄
- 대부분의 쿼리는 고정된 WHERE 조건 + 페이지네이션
- "나중에 필요하면" 그때 도입해도 늦지 않음
- 타입 안전성은 통합 테스트 + 코드 리뷰로 충분히 보완 가능
```

## 채택 전략: Spring Data JPA 3단계

```
┌─────────────────────────────────────────────────────────┐
│   Level 1: Spring Data JPA 기본 메서드 (80% 커버)        │
│   findById, findAll, save, delete                       │
│   + 메서드 이름 쿼리 (findByUserIdAndStatus 등)          │
├─────────────────────────────────────────────────────────┤
│   Level 2: @Query JPQL (15% 커버)                       │
│   JOIN, 서브쿼리, 집계(GROUP BY) 등 중간 복잡도          │
│   + DTO Projection (record 활용)                        │
├─────────────────────────────────────────────────────────┤
│   Level 3: @Query(nativeQuery=true) (5% 커버)           │
│   DB 전용 기능 (PostgreSQL JSONB, 윈도우 함수 등)        │
│   + 극단적 성능 최적화가 필요한 쿼리                     │
└─────────────────────────────────────────────────────────┘
```

### Level 별 Few-shot 예시

```java
// === Level 1: Spring Data JPA 기본 메서드 ===
public interface PetRepository extends JpaRepository<Pet, Long> {

    // 메서드 이름 쿼리 — 자동 구현
    List<Pet> findByUserIdAndDeletedAtIsNull(Long userId);
    Optional<Pet> findByIdAndDeletedAtIsNull(Long id);
    boolean existsByUserIdAndNameAndDeletedAtIsNull(Long userId, String name);
}

// === Level 2: @Query JPQL ===
public interface MedicalRecordRepository extends JpaRepository<MedicalRecord, Long> {

    // JPQL + DTO Projection (record)
    @Query("""
        SELECT new com.petcare.dto.MedicalRecordSummary(
            m.id, m.visitDate, m.diagnosis, m.veterinarian
        )
        FROM MedicalRecord m
        WHERE m.pet.id = :petId AND m.deletedAt IS NULL
        ORDER BY m.visitDate DESC
        """)
    Slice<MedicalRecordSummary> findSummariesByPetId(
        @Param("petId") Long petId, Pageable pageable
    );

    // JPQL + 집계
    @Query("""
        SELECT m.pet.id, COUNT(m), MAX(m.visitDate)
        FROM MedicalRecord m
        WHERE m.pet.user.id = :userId AND m.deletedAt IS NULL
        GROUP BY m.pet.id
        """)
    List<Object[]> countRecordsByPetForUser(@Param("userId") Long userId);
}

// === Level 3: Native Query (PostgreSQL 전용) ===
public interface VaccinationRepository extends JpaRepository<Vaccination, Long> {

    // Native Query — JSONB 검색 (PostgreSQL 전용)
    @Query(value = """
        SELECT v.id, v.vaccine_name, v.administered_date,
               v.metadata->>'manufacturer' as manufacturer
        FROM vaccinations v
        WHERE v.pet_id = :petId
          AND v.deleted_at IS NULL
          AND v.metadata @> :filterJson\\:\\:jsonb
        ORDER BY v.administered_date DESC
        """, nativeQuery = true)
    List<Object[]> findByPetIdWithMetadataFilter(
        @Param("petId") Long petId,
        @Param("filterJson") String filterJson
    );
}

// === 동적 쿼리가 필요한 경우: Specification 패턴 ===
public class MedicalRecordSpecs {

    public static Specification<MedicalRecord> belongsToPet(Long petId) {
        return (root, query, cb) -> cb.equal(root.get("pet").get("id"), petId);
    }

    public static Specification<MedicalRecord> notDeleted() {
        return (root, query, cb) -> cb.isNull(root.get("deletedAt"));
    }

    public static Specification<MedicalRecord> diagnosisContains(String keyword) {
        if (keyword == null || keyword.isBlank()) return null;
        return (root, query, cb) ->
            cb.like(cb.lower(root.get("diagnosis")), "%" + keyword.toLowerCase() + "%");
    }

    public static Specification<MedicalRecord> visitedAfter(LocalDate date) {
        if (date == null) return null;
        return (root, query, cb) -> cb.greaterThanOrEqualTo(root.get("visitDate"), date);
    }
}

// 사용측: 동적 조건 조합
Specification<MedicalRecord> spec = Specification
    .where(MedicalRecordSpecs.belongsToPet(petId))
    .and(MedicalRecordSpecs.notDeleted())
    .and(MedicalRecordSpecs.diagnosisContains(searchKeyword))
    .and(MedicalRecordSpecs.visitedAfter(fromDate));

Page<MedicalRecord> results = medicalRecordRepository.findAll(spec, pageable);
```

## 문서 전체 반영 사항

이 결정에 따라 이전 문서(부록 J)의 QueryDSL 설정을 **Spring Data JPA 3단계 전략**으로 대체한다:
- build.gradle에서 querydsl 의존성 제거
- AGENT.md에서 QueryDSL 규칙 → JPA @Query + Specification 규칙으로 변경
- Few-shot 예시 전부 JPA 기본 패턴으로 교체

---

# 부록 M. 실행 가능한 슬래시 커맨드 — `init-agent-team.md`

> 이 파일을 `.claude/commands/init-agent-team.md`에 복사하면 즉시 사용 가능

```markdown
---
allowed-tools: Bash, Read, Write, Edit
description: AI 에이전트 팀 플랫폼 전체 Scaffolding 생성 (16 agents + pipeline + commands)
---

# Init Agent Team

프로젝트 정보: $ARGUMENTS

아래 단계를 순서대로 실행하세요.

## Step 1: 입력 파싱

$ARGUMENTS에서 다음 정보를 추출하세요. 없으면 기본값을 사용:
- project_name (필수, 없으면 현재 디렉토리명 사용)
- description (없으면 "AI Agent Team Project")
- backend: spring-boot-java (기본값)
- frontend: nextjs (기본값)
- db: postgresql (기본값)
- infra: aws (기본값)
- convention: naver (기본값)

## Step 2: 디렉토리 구조 생성

```bash
# 에이전트 디렉토리
for agent in 00-distiller 00-judge 00-advisor 01-biz-analyst 02-pm 03-planning 04-marketing 05-crm 06-design 07-db 08-backend 09-frontend 10-app 11-qa 12-devops 13-security; do
  mkdir -p "agents/$agent/templates" "agents/$agent/examples"
done
mkdir -p agents/_shared

# 파이프라인
for stage in 00-input 01-requirements 02-prd 03-design-spec 04-db-schema 05-api-spec 06-code 07-test-results 08-review-report 09-security-audit 10-deploy-log 11-analytics; do
  mkdir -p "pipeline/artifacts/$stage"
done
mkdir -p pipeline/{state,decisions,contracts}

# 슬래시 커맨드
mkdir -p .claude/commands

# 소스코드
mkdir -p src/{backend,frontend,shared} docs conventions
```

## Step 3: CLAUDE.md 생성

프로젝트 루트에 CLAUDE.md를 생성하세요. 반드시 다음 섹션을 포함:

1. **프로젝트 정보**: project_name, description, 기술스택
2. **에이전트 호출 규칙**: agents/XX-name/AGENT.md를 시스템 프롬프트로 로드
3. **파이프라인 5단계**: Discovery → Design → Build → Verify → Ship
4. **인간 승인 지점 3개**: Discovery 완료, 설계 완료, 배포 전
5. **기술 스택 상세**: backend, frontend, db, infra 각각의 핵심 규칙
6. **Compact Instructions**: Compaction 후 복구 절차 (pipeline/state/current-state.json 읽기)
7. **코드 생성 전략**: Scaffolding Pass → Domain Pass → Integration Pass
8. **Virtual Threads**: spring.threads.virtual.enabled=true, synchronized 대신 ReentrantLock
9. **DB 쿼리 전략**: Spring Data JPA 3단계 (기본 메서드 → @Query JPQL → Native Query)

## Step 4: 16개 에이전트 AGENT.md 생성

각 에이전트 디렉토리에 AGENT.md를 생성하세요.

### 공통 구조 (모든 에이전트):
```
# [에이전트명]

## 페르소나
[15년 경력의 시니어 전문가 설정, 구체적 전문 분야 명시]

## 역할
[이 에이전트가 수행하는 작업 3-5개]

## 입력
[pipeline/artifacts/XX-stage/ 경로의 이전 단계 산출물]

## 산출물
[pipeline/artifacts/XX-stage/ 경로에 저장할 파일 목록]

## 행동 규칙
[5-7개의 구체적 규칙, 숫자 기준 포함]

## 적용 컨벤션
[convention 파라미터에 따른 컨벤션 레퍼런스]
```

### 에이전트별 특화 내용:

**01-biz-analyst**: 요구사항을 비즈니스 목표/사용자 스토리/기능 요구사항/비기능 요구사항으로 구조화. MoSCoW 우선순위. MVP 범위 정의.

**02-pm**: RICE 스코어링. PRD + 3/6/12개월 로드맵 + 스프린트 플랜.

**03-planning**: 기능명세서 + 화면흐름도(Mermaid). 모든 사용자 스토리에 대응하는 화면 설계.

**04-marketing**: GTM 전략 + 경쟁사 3곳 이상 분석 + SEO 키워드 + 퍼널 설계.

**05-crm**: 고객 여정 맵 + 세그먼트 정의 + 온보딩 시퀀스.

**06-design**: 디자인 토큰(JSON) + 컴포넌트 명세. convention이 toss이면 TDS 토큰 적용.

**07-db**: ERD(Mermaid) + DDL(PostgreSQL) + 인덱스 전략. 3NF 기본, 읽기 성능 중요 시 반정규화. PK는 UUID v7 또는 BIGINT. soft delete(deleted_at). 쿼리 전략: Spring Data JPA 3단계.

**08-backend**: Hexagonal Architecture. Spring Boot 3.x + Java 21. Virtual Threads 활성화. record DTO + sealed interface 에러. JPA @Query + Specification 패턴 (QueryDSL 미사용). convention에 따른 코딩 컨벤션 적용.

**09-frontend**: Next.js 15 App Router. Server Component 기본. TanStack Query + Zustand. Tailwind CSS. react-hook-form + zod.

**10-app**: React Native 또는 Flutter. mobile이 none이면 "v2에서 구현 예정" 스텁만 생성.

**11-qa**: 테스트 피라미드 (단위 70% / 통합 20% / E2E 10%). JUnit 5 + Mockito (백엔드). Vitest + Playwright (프론트). k6 (성능).

**12-devops**: Terraform IaC. GitHub Actions CI/CD. Docker 컨테이너화. CloudWatch/Datadog 모니터링.

**13-security**: OWASP Top 10 체크. 의존성 취약점 스캔. 입력 검증 + SQL Injection + XSS 방어 확인.

**00-distiller**: 산출물 3단계 요약 (Headline 50토큰 / Brief 500토큰 / Extract 2000토큰).

**00-judge**: 5차원 평가 (완전성/일관성/정확성/명확성/실행가능성). 8.0+ PASS / 6.0~7.9 CONDITIONAL / 4.0~5.9 RETRY / 4.0- FAIL.

**00-advisor**: 인간 승인 지점마다 Decision Brief + Tradeoff Matrix + Risk Simulation + Go/No-Go Checklist.

## Step 5: 공유 프로토콜 파일 생성

**agents/_shared/context-protocol.md**: 산출물 표준 헤더(YAML frontmatter), 핸드오프 체크리스트.

**agents/_shared/quality-gates.md**: 5단계 게이트 (Discovery/설계/구현/검증/배포).

**agents/_shared/output-schema.md**: 산출물 YAML 스키마 정의.

**pipeline/dependency-map.md**: 에이전트별 이전 산출물 로딩 수준 (Full/Level3/Level2/Level1).

**pipeline/state/current-state.json**: 초기 상태 JSON (pipeline_id, current_phase: "not_started").

**pipeline/decisions/decision-registry.md**: 빈 템플릿 (헤더만).

## Step 6: 슬래시 커맨드 생성

각 커맨드를 .claude/commands/에 생성:

**kickoff.md**: 전체 파이프라인 순차 실행. $ARGUMENTS로 요구사항 입력. 5단계 + 3개 인간 승인 지점.

**plan.md**: Discovery 단계만 실행 (사업분석 + PM + 마케팅 + CRM).

**design.md**: Design 단계만 실행 (기획 + 디자인 + DB).

**develop.md**: Build 단계만 실행 (백엔드 + 프론트 + 앱).

**test.md**: Verify 단계만 실행 (QA + 코드 리뷰 + 보안).

**deploy.md**: Ship 단계만 실행 (DevOps + 성과분석).

**review.md**: 코드 리뷰 + 보안 검증만 실행.

## Step 7: 설정 파일 생성

**.claude/settings.json**:
```json
{
  "env": {
    "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1",
    "CLAUDE_AUTOCOMPACT_PCT_OVERRIDE": "90"
  },
  "permissions": {
    "allow": [
      "Read(./src/**)", "Write(./src/**)",
      "Read(./pipeline/**)", "Write(./pipeline/**)",
      "Read(./agents/**)", "Read(./docs/**)", "Write(./docs/**)",
      "Bash(npm:*)", "Bash(npx:*)", "Bash(./gradlew:*)",
      "Bash(git:*)", "Bash(docker:*)", "Bash(mkdir:*)"
    ],
    "deny": [
      "Read(./.env)", "Read(./.env.*)", "Read(./secrets/**)"
    ]
  }
}
```

**.gitignore에 추가**:
```
pipeline/state/
pipeline/artifacts/
build/
.gradle/
node_modules/
.env
.env.*
```

## Step 8: 검증 및 보고

생성된 파일을 검증하고 사용자에게 보고:

1. `find . -name "AGENT.md" | wc -l` → 16개 확인
2. `find .claude/commands -name "*.md" | wc -l` → 7개 확인 (init-agent-team 제외)
3. `ls CLAUDE.md` → 존재 확인
4. 디렉토리 트리 출력
5. 총 생성 파일 수 보고
6. "다음 단계: /project:kickoff [요구사항]" 안내
```

---

# 부록 N. ORM 전략 자동 추천 로직 — DB 에이전트 내장

## DB 에이전트 AGENT.md에 추가할 의사결정 로직

```markdown
## ORM/쿼리 전략 자동 추천

기능명세서를 분석하여 각 도메인의 쿼리 복잡도를 평가하고,
적절한 쿼리 전략을 자동 추천한다.

### 평가 기준

각 도메인(Entity 그룹)에 대해 다음을 평가:

1. **동적 검색 조건 수**: 사용자가 조합할 수 있는 필터 조건
2. **JOIN 깊이**: 몇 단계의 연관 엔티티를 조회하는가
3. **DB 전용 기능 필요**: JSONB, 윈도우 함수, CTE 등
4. **집계/통계 쿼리 비중**: GROUP BY, HAVING, 서브쿼리

### 추천 매트릭스

| 동적조건 | JOIN깊이 | DB전용기능 | 집계비중 | → 추천 전략 |
|---------|---------|-----------|---------|------------|
| 0~2개   | 1단계    | 없음      | 낮음    | **Level 1**: JPA 메서드 이름 쿼리 |
| 3~5개   | 2단계    | 없음      | 중간    | **Level 2**: @Query JPQL |
| 3~5개   | 2단계    | 없음      | 낮음    | **Level 2+**: JPQL + Specification |
| 5개+    | 3단계+   | 없음      | 높음    | **Level 2+**: JPQL + Specification |
| 아무거나 | 아무거나  | 있음      | 아무거나 | **Level 3**: Native Query |

### 산출물에 포함할 내용

각 Repository에 대해:
\`\`\`yaml
repositories:
  - name: PetRepository
    strategy: "Level 1 — JPA 메서드 이름 쿼리"
    reason: "CRUD + 단순 조건 검색만 필요"
    methods:
      - findByUserIdAndDeletedAtIsNull
      - findByIdAndDeletedAtIsNull

  - name: MedicalRecordRepository
    strategy: "Level 2 — @Query JPQL + Specification"
    reason: "진료기록 검색에 날짜/진단명/수의사 등 동적 조건 4개"
    methods:
      - findSummariesByPetId (@Query JPQL)
      - findAll(Specification) — 동적 검색용
    specs:
      - diagnosisContains(keyword)
      - visitedAfter(date)
      - visitedBefore(date)
      - veterinarianEquals(name)

  - name: VaccinationRepository
    strategy: "Level 3 — Native Query"
    reason: "JSONB 메타데이터 검색 필요 (PostgreSQL @> 연산자)"
    methods:
      - findByPetIdWithMetadataFilter (Native)
\`\`\`

### 향후 확장 시점 가이드

다음 조건 중 2개 이상 해당되면 QueryDSL 또는 jOOQ 도입 검토:
- 동적 검색 조건이 10개 이상인 도메인이 3개 이상
- JOIN 4단계 이상의 복잡 쿼리가 전체의 30% 이상
- 쿼리 관련 런타임 에러가 월 5건 이상 발생
- 팀이 3명 이상으로 성장하여 타입 안전성의 가치가 커짐
```

---

# 부록 O. 30분 PoC — 백엔드 에이전트 코드 생성 품질 검증

## 목적

전체 16개 에이전트 파이프라인을 돌리기 전에, **가장 리스크가 높은 백엔드 코드 생성 품질**만 소규모로 검증한다.

## 사전 준비 (5분)

```bash
# 1. 빈 Spring Boot 프로젝트 생성
mkdir -p ~/poc-petcare && cd ~/poc-petcare

# 2. Spring Initializr로 프로젝트 생성 (또는 수동)
curl https://start.spring.io/starter.zip \
  -d type=gradle-project \
  -d language=java \
  -d bootVersion=3.4.1 \
  -d javaVersion=21 \
  -d dependencies=web,data-jpa,validation,postgresql,lombok \
  -d groupId=com.petcare \
  -d artifactId=poc \
  -o poc.zip && unzip poc.zip && rm poc.zip

# 3. Docker PostgreSQL (테스트용)
docker run -d --name poc-pg -e POSTGRES_PASSWORD=test -p 5432:5432 postgres:16

# 4. Claude Code 실행
cd ~/poc-petcare && claude
```

## 테스트 시나리오 (20분)

### 시나리오 1: Entity + Repository 생성 (5분)

Claude Code에 입력:
```
다음 요구사항에 맞는 Entity와 Repository를 생성해줘.

도메인: 반려동물 진료기록 관리
- Pet Entity: id(Long), userId(Long), name, species(enum: DOG/CAT/BIRD/OTHER), 
  breed, birthDate, createdAt, updatedAt, deletedAt
- MedicalRecord Entity: id(Long), pet(ManyToOne), visitDate, diagnosis, 
  treatment, veterinarian, notes, createdAt, updatedAt, deletedAt

규칙:
- Java 21, record로 DTO, Lombok 사용
- PK는 BIGINT auto increment
- soft delete (deletedAt)
- 네이버 Java 컨벤션 (하드탭, 120자)
```

**검증 체크리스트**:
- [ ] Entity에 @Entity, @Table, @Id, @GeneratedValue 있는가
- [ ] Lombok @Getter, @NoArgsConstructor(access=PROTECTED), @Builder 사용
- [ ] @ManyToOne에 fetch = LAZY 설정
- [ ] createdAt/updatedAt에 @CreationTimestamp/@UpdateTimestamp 또는 @EntityListeners
- [ ] deletedAt 필드 존재 + @Where(clause = "deleted_at IS NULL") 또는 @SQLRestriction
- [ ] Species enum이 별도 파일로 분리
- [ ] Repository가 JpaRepository 상속

### 시나리오 2: Service + API 생성 (7분)

```
Pet 도메인의 CRUD API를 생성해줘.

- POST /api/v1/pets — 반려동물 등록
- GET /api/v1/pets — 내 반려동물 목록 (userId 기준)
- GET /api/v1/pets/{petId} — 반려동물 상세
- PUT /api/v1/pets/{petId} — 반려동물 수정
- DELETE /api/v1/pets/{petId} — 반려동물 삭제 (soft delete)

규칙:
- Hexagonal Architecture (Controller → UseCase Interface → Service → Repository)
- record로 Request/Response DTO
- sealed interface로 에러 타입 (PetNotFound, PetAlreadyExists)
- @Validated로 입력 검증
- Virtual Threads 기본 설정 (application.yml)
```

**검증 체크리스트**:
- [ ] UseCase 인터페이스 존재 (CreatePetUseCase, GetPetUseCase 등)
- [ ] Service가 UseCase 인터페이스 구현
- [ ] Request/Response가 record 클래스
- [ ] sealed interface 에러 계층 존재
- [ ] @ExceptionHandler + @ControllerAdvice로 에러 핸들링
- [ ] spring.threads.virtual.enabled: true 설정
- [ ] @Transactional(readOnly = true) 읽기 메서드에 적용
- [ ] Optional.orElseThrow() 패턴 사용 (null 직접 체크 아님)

### 시나리오 3: 테스트 생성 (5분)

```
Pet Service에 대한 단위 테스트를 작성해줘.

- JUnit 5 + Mockito
- 성공 케이스 + 실패 케이스 (PetNotFound)
- @DisplayName 한글 사용
- given-when-then 패턴
```

**검증 체크리스트**:
- [ ] @ExtendWith(MockitoExtension.class) 사용
- [ ] @Mock, @InjectMocks 어노테이션
- [ ] @DisplayName("반려동물을 등록하면 ID를 반환한다") 한글
- [ ] given().willReturn() 패턴
- [ ] assertThat() (AssertJ) 사용
- [ ] 실패 케이스: assertThatThrownBy() 또는 assertThrows()
- [ ] 테스트가 실제로 통과 (./gradlew test)

### 시나리오 4: 컴파일 + 실행 검증 (3분)

```bash
# 전체 빌드
./gradlew clean build

# 테스트 실행
./gradlew test

# 앱 실행 (DB 연결 확인)
./gradlew bootRun
```

**검증 체크리스트**:
- [ ] 컴파일 에러 0건
- [ ] Checkstyle 경고 0건 (설정 시)
- [ ] 테스트 전체 통과
- [ ] 앱 정상 기동 (포트 8080)

## 평가 기준

```
총점: 위 체크리스트 항목 수 대비 통과율

90%+ → ✅ PASS: 백엔드 에이전트 AGENT.md 그대로 사용 가능
70~89% → ⚠️ CONDITIONAL: AGENT.md에 Few-shot 예시 보강 필요
50~69% → 🔄 RETRY: AGENT.md 페르소나 + 규칙 대폭 수정 필요
50%- → 🔴 FAIL: 접근 방식 재검토 (에이전트 분할 등)
```

## PoC 후 액션

| 결과 | 액션 |
|------|------|
| PASS | 전체 /project:init-agent-team 실행 → /project:kickoff 진행 |
| CONDITIONAL | 실패한 체크리스트 항목을 Few-shot 예시로 추가 후 재시도 |
| RETRY | AGENT.md의 "행동 규칙"을 더 구체적으로 재작성 (코드 템플릿 수준) |
| FAIL | 단계 분할: Entity만 먼저, Service만 먼저 등 세분화 |

---

## 📚 부록: 참고 자료 및 외부 링크

### Claude Code 공식 문서
- Agent Teams: https://code.claude.com/docs/en/agent-teams
- Compaction: https://platform.claude.com/docs/en/build-with-claude/compaction
- Context Windows: https://platform.claude.com/docs/en/build-with-claude/context-windows

### 한국 기업 컨벤션 레퍼런스
- 네이버 Java 컨벤션: https://naver.github.io/hackday-conventions-java/
- NHN TOAST UI FE 가이드: https://ui.toast.com/fe-guide/ko_CODING-CONVENTION
- 토스 디자인 시스템 (TDS): https://tossmini-docs.toss.im/tds-mobile/
- 토스 기술 블로그: https://toss.tech
- 카카오 개발자: https://developers.kakao.com

### 기술 레퍼런스
- Spring Boot 3.x: https://spring.io/projects/spring-boot
- Java 21 릴리스 노트: https://openjdk.org/projects/jdk/21/
- Next.js 15: https://nextjs.org/docs
- PostgreSQL 16: https://www.postgresql.org/docs/16/

---

## 🔖 문서 버전 정보

- **버전**: 1.0.0
- **최종 업데이트**: 2026-04-16
- **총 분량**: ~5,000 줄
- **대상 독자**: 1인 창업자 / 시니어 풀스택 개발자 / AI 에이전트 시스템 설계자

---

*이 설계서는 Claude Code와 함께 AI 에이전트 팀 플랫폼을 구축하려는 개발자를 위해 작성되었습니다. 설계의 핵심 원칙은 "1인이 운영 가능한 복잡도"이며, 모든 기술 선택은 이 기준에서 검증되었습니다.*
