# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AI Agent Team Platform — Claude Code 기반 멀티에이전트 SDLC 자동화 플랫폼.
요구사항 한 줄 입력으로 기획→설계→개발→테스트→배포까지 16개 AI 전문가 에이전트가 순차/병렬로 처리하는 구조.

**목적**: 소규모 스타트업 팀에서 모든 구성원이 기획/디자인/개발(FE/BE/앱)/보안/DevOps/운영 역할을 겸할 수 있도록 AI 에이전트가 전문성을 보완. 팀 공유를 전제로 `pipeline/` 디렉토리는 커밋 대상.

- **Repository**: github.com/withwooyong/ted-startup
- **기본 브랜치**: master
- **현재 상태**: Java→Python 전면 이전 완료 (Phase 1~9). FastAPI + SQLAlchemy 2.0 async 스택. §11 포트폴리오·AI 분석 리포트 도메인(P10~P15) 착수 대기.

## 핵심 참조 문서

- 사용설명서: `docs/PIPELINE-GUIDE.md` — 실전 운영 요약, 다른 프로젝트 이식 가이드 (여기부터 읽기)
- 마스터 설계서: `docs/design/ai-agent-team-master.md` — 모든 아키텍처/기술 판단의 권위 있는 출처
- Scaffolding 생성기: `.claude/commands/init-agent-team.md` — 에이전트/파이프라인 구조 자동 생성

## Getting Started

**초기 프로젝트 구조 생성** (아직 안 했다면):
```
/init-agent-team
```
이 명령이 16개 에이전트 AGENT.md, 파이프라인 디렉토리, 7개 슬래시 커맨드, 공유 프로토콜을 일괄 생성한다.

**파이프라인 실행** (scaffolding 생성 후):
```
/kickoff [요구사항 텍스트]     # 전체 파이프라인
/plan [요구사항]               # Phase 1: Discovery만
/design                        # Phase 2: Design만
/develop                       # Phase 3: Build만
/test                          # Phase 4: Verify만
/review                        # 코드 리뷰 + 보안 검증
/deploy                        # Phase 5: Ship만
```

## Tech Stack

| 영역 | 선택 |
|------|------|
| Backend | FastAPI + Python 3.12 (Hexagonal Architecture, `src/backend_py/`) |
| ORM | SQLAlchemy 2.0 (async, asyncpg 런타임) + Alembic (psycopg2 마이그레이션) |
| 수치/분석 | pandas, numpy, pandas-ta, vectorbt |
| 배치 | APScheduler (AsyncIOScheduler + CronTrigger, KST 06:00 mon-fri) |
| Frontend | Next.js 15 + TypeScript (App Router) |
| DB | PostgreSQL 16 |
| 인증 | 카카오 OAuth 2.0 + Admin API Key(`hmac.compare_digest`) |
| 컨벤션 | PEP 8 + ruff + mypy strict (백엔드) + 토스(디자인) + 카카오(인증) |
| 패키지 매니저 | uv |

## Pipeline (5 Phases)

```
Phase 1: Discovery — biz-analyst → pm → marketing → crm
   🔴 인간 승인 #1
Phase 2: Design — planning → design → db
   🔴 인간 승인 #2
Phase 3: Build — backend + frontend + app (Agent Teams 병렬)
Phase 4: Verify — qa + code-review + security (Agent Teams 병렬)
   🔴 인간 승인 #3
Phase 5: Ship — devops → analytics
```

- 산출물: `pipeline/artifacts/XX-stage/`
- 파이프라인 상태: `pipeline/state/current-state.json`
- 의사결정 기록: `pipeline/decisions/decision-registry.md`

## Agent Architecture (16 agents)

- **메타 (3)**: 00-distiller(요약), 00-judge(품질평가), 00-advisor(의사결정 지원)
- **비즈니스 (5)**: 01-biz-analyst, 02-pm, 03-planning, 04-marketing, 05-crm
- **설계/개발 (5)**: 06-design, 07-db, 08-backend, 09-frontend, 10-app
- **품질/운영 (3)**: 11-qa, 12-devops, 13-security

에이전트 간 통신은 `agents/_shared/context-protocol.md` 규격 (마크다운 + YAML 프론트매터).

### 에이전트 호출 규칙
1. 각 에이전트는 `agents/XX-name/AGENT.md`를 시스템 프롬프트로 로드
2. 산출물은 `pipeline/artifacts/XX-stage/`에 저장
3. 각 에이전트는 자신의 전문 영역만 처리하고 경계를 넘지 않음

### 컨텍스트 관리 (1M Token)
- Phase 1~3: 산출물 요약본(summary.md) 사용 (Selective Loading)
- Phase 4: 소스코드 전체 원본 로드 (Full Context Mode)

### 코드 생성 전략 (128K Output)
1. **Scaffolding Pass** (1회) — SQLAlchemy 모델, Repository, UseCase Protocol, Pydantic DTO, FastAPI Router 스켈레톤 일괄 생성
2. **Domain Pass** (도메인당 1회) — 비즈니스 로직 개별 구현 (pandas 벡터화 우선)
3. **Integration Pass** (1회) — 인증 의존성, 예외 핸들러(RequestValidationError → 400), testcontainers 통합 테스트, Docker + entrypoint

## Quality Gates

00-judge가 각 Phase 완료 시 5차원 평가 (완전성/일관성/정확성/명확성/실행가능성):
- Score >= 8.0 → PASS
- Score 6.0~7.9 → CONDITIONAL
- Score < 6.0 → RETRY 또는 FAIL

## Key Design Decisions

- Java→Python 전면 이전 (Phase 1~9 완료, 2026-04): 사전-운영 단계에서 big-bang 재작성 채택
- 동시성: asyncio 일급 (Virtual Thread 개념 없음). CPU 바운드는 `run_in_executor` 로 분리
- 상호배제: `asyncio.Lock` (KRX 2초 rate limit 직렬화)
- DTO: Pydantic v2 `BaseModel` (Java record 대체)
- 에러 타입: Python `Exception` 계층 + FastAPI Exception Handler
- 백테스트: vectorbt + pandas 피벗 테이블 + shift(-N) 행렬 연산
- Alembic 마이그레이션은 동기 psycopg2, 앱 런타임은 asyncpg (다중 statement 제약 회피)
- MVP는 4~6주 내 런칭 가능한 범위로 제한
- 앱은 v1에서 PWA로 대체 권장

## Backend Conventions (Python 3.12 + FastAPI)

- PEP 8 준수, 4스페이스 들여쓰기, 줄 너비 120자
- `ruff`(lint + format) + `mypy --strict` 적용
- `None` 반환 지양, `Optional[T]` 또는 명시적 예외
- DB 트랜잭션: `async with session.begin():` 컨텍스트 매니저, 읽기는 `session.execute(select(...))`
- DTO/스키마: Pydantic v2 `BaseModel` (요청/응답 둘 다)
- Repository: async 메서드, `session.refresh()` 로 server_default 동기화
- 외부 I/O: httpx AsyncClient + tenacity 재시도 + 2초 rate limit (KRX)
- 로깅: structlog JSON, 비밀키 값은 절대 로그에 노출 금지
- 테스트: pytest + pytest-asyncio + testcontainers-python PG16

## Frontend Conventions (토스 + NHN)

- 공백 2개 들여쓰기
- Server Component 기본, `'use client'`는 필요 시만
- Suspense + ErrorBoundary 선언적 비동기
- 상태관리: TanStack Query (서버) + Zustand (클라이언트)
- 폼: react-hook-form + zod
- `any` 타입 사용 금지

## Compaction Recovery

Compaction 발생 시 복구 순서:
1. `pipeline/state/current-state.json` 읽기
2. `pipeline/decisions/decision-registry.md` 읽기
3. 현재 단계에 필요한 산출물 로드
