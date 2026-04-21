# ted-startup

AI Agent Team Platform — Claude Code 기반 멀티에이전트 SDLC 자동화 플랫폼.
요구사항 한 줄로 기획 → 설계 → 개발 → 테스트 → 배포까지 16개 AI 전문가 에이전트가 순차/병렬 처리한다.

---

> ## 🚨 **필독 — 시작하기 전에**
>
> 이 플랫폼을 **새 프로젝트에 이식**하거나 **파이프라인을 처음 사용**한다면 아래 문서 먼저 숙지:
>
> ### 📖 **[docs/PIPELINE-GUIDE.md](docs/PIPELINE-GUIDE.md)** — 파이프라인 실전 운영 가이드
>
> 5분 요약 · 3단계 이식 절차 · 5-Phase 플로우 · 병렬 작업 패턴 · Compaction 방어 · 실전 학습 포인트까지.
> 이 프로젝트(ted-startup)의 모든 SDLC 루틴이 응축된 단일 엔트리 포인트.

---

## 주요 기능

- **5-Phase 파이프라인**: Discovery → Design → Build → Verify → Ship (각 단계 사이에 인간 승인 게이트)
- **16개 전문 에이전트**: 메타(3) · 비즈니스(5) · 설계/개발(5) · 품질/운영(3)
- **품질 게이트**: `00-judge`가 5차원(완전성/일관성/정확성/명확성/실행가능성) 평가, 8.0 미만 시 재작업
- **도메인 서비스**: 주식 시세 수집(KRX) · 공시(DART) · 포트폴리오 · AI 분석 리포트

## Tech Stack

| 영역 | 스택 |
|------|------|
| Backend | FastAPI + Python 3.12 (Hexagonal), SQLAlchemy 2.0 async, Alembic |
| Frontend | Next.js 15 + TypeScript (App Router) |
| DB | PostgreSQL 16 |
| 배치 | APScheduler (KST 06:00 mon-fri) |
| 분석 | pandas, numpy, pandas-ta, vectorbt |
| 인증 | 카카오 OAuth 2.0 + Admin API Key |
| 패키지 | uv (백엔드) · npm (프론트) |

## Quickstart

```bash
# DB
docker compose up -d postgres

# 백엔드
cd src/backend_py
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload

# 프론트엔드
cd src/frontend
npm install
npm run dev
```

## 파이프라인 실행

```
/kickoff [요구사항]   # 전체 파이프라인
/plan   [요구사항]   # Phase 1 Discovery
/design              # Phase 2 Design
/develop             # Phase 3 Build
/test                # Phase 4 Verify
/review              # 코드리뷰 + 보안
/deploy              # Phase 5 Ship
```

산출물은 `pipeline/artifacts/XX-stage/` 에 누적되고, 상태는 `pipeline/state/current-state.json` 에서 추적한다.

## 디렉토리 구조

```
agents/           # 16개 에이전트 정의 (AGENT.md)
pipeline/         # 파이프라인 산출물 · 상태 · 의사결정 기록
src/backend_py/   # FastAPI 백엔드 (Hexagonal)
src/frontend/     # Next.js 프론트엔드
docs/             # 마스터 설계서 · 파이프라인 가이드
ops/              # Caddy 등 운영 설정
```

## 핵심 문서

- 🚨 **[docs/PIPELINE-GUIDE.md](docs/PIPELINE-GUIDE.md)** — **신규 프로젝트 진행 시 가장 먼저 읽을 문서**. 5-Phase 플로우·이식 절차·실전 교훈 응축
- [docs/design/ai-agent-team-master.md](docs/design/ai-agent-team-master.md) — 마스터 설계서 (4112줄, 깊은 이해용)
- [CLAUDE.md](CLAUDE.md) — Claude Code 작업 규칙 (매 턴 자동 로드)
- [HANDOFF.md](HANDOFF.md) — 직전 세션 상태·다음 액션
- [CHANGELOG.md](CHANGELOG.md) — 변경 이력

## 컨벤션

- 백엔드: PEP 8 + `ruff` + `mypy --strict`, 120자, 4-space
- 프론트: 토스 스타일, 2-space, Server Component 기본, `any` 금지
- 커밋 메시지: 한글
