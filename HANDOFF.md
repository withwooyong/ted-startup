# Session Handoff

> Last updated: 2026-04-23 08:10 KST (오전 세션 확장 — **Gate 3 실제 측정 완료 + /stocks/005930 Perf 미달 사후 수정 PR 까지 오픈**)
> Current branch: `feature/stocks-detail-cls-fix` (origin 푸시 완료)
> Latest commit: `5efff74` — fix(frontend): /stocks/005930 CLS 0.36→0.12 · Perf 80→92
> master 최신: `62a7361` (PR #34, Gate 3 인프라, 이번 세션에 머지)

## Current Status

Gate 3 증빙 인프라 PR #34 를 머지한 뒤, **prod docker 스택을 master 기준으로 재빌드 → caddy self-signed HTTPS 경유로 7 페이지 Lighthouse 모바일 측정 수행 → `/stocks/005930` Perf 80 미달 발견 → JSON audit 기반으로 CLS 진범 특정 → CSS-only 수정으로 Perf 92 달성** 까지 1-cycle 완결. 현재 PR 스택 2개 오픈(`#35`, `#36`) 으로 CI 대기 중, 미커밋 파일은 핸드오프 문서 2 종.

## Completed This Session (2026-04-23 오전 확장)

| # | 커밋/PR | 내용 | 파일 |
|---|---|---|---|
| 1 | `62a7361` / PR #34 merge | Gate 3 증빙 인프라 머지 완료 (`gh pr merge 34 --squash --delete-branch`) | — |
| 2 | `docker compose … up -d --build` | prod 스택 전체 재빌드 (backend+frontend 새 이미지, db/caddy 유지). healthcheck 전부 green. | — |
| 3 | Lighthouse 7페이지 1차 측정 | `LIGHTHOUSE_BASE_URL=https://localhost ./scripts/lighthouse-mobile.sh` — 6 페이지 목표 통과, `/stocks/005930` Perf 80 단일 미달 | `lighthouse-reports/*` (untracked) |
| 4 | `9815608` / PR #35 | Gate 3 1차 측정 결과 기록 + 스크립트 self-signed 지원 | `docs/lighthouse-scores.md` · `scripts/lighthouse-mobile.sh` |
| 5 | JSON audit 로 CLS 진범 특정 | `layout-shifts` 2 건 모두 footer / TBT 48ms (문제 없음) / CLS 0.362 (문제) → 초기 가설(recharts TBT) 반증 | `lighthouse-reports/stocks-005930.report.json` |
| 6 | `5efff74` / PR #36 | `/stocks/005930` CSS-only 수정: `useMediaQuery` 제거 → aspect CSS 이관 · `min-h-[calc(100dvh-8rem)]` 로 footer 고정 · 스켈레톤 세분화 | `src/frontend/src/app/stocks/[code]/page.tsx` · `docs/lighthouse-scores.md` |
| 7 | 프론트엔드 단일 서비스 재빌드 + 재측정 | CLS 0.362 → 0.123, Perf 80 → **92** 확인 | — |

### 주요 수치 비교

```
/stocks/005930  (mobile Lighthouse, prod docker 스택, caddy self-signed HTTPS)
                   Perf    A11y    BP     SEO    CLS      TBT     LCP
  Before (PR #35)  80      96      100    100    0.362    48ms    2553ms
  After  (PR #36)  92      96      100    100    0.123    119ms   2557ms
                   +12     =       =      =      −66%     변동성  =
  Layout shift      2 건 (footer × 2)   →    1 건 (header card 내부)
```

## In Progress / Pending

| # | 항목 | 상태 | 비고 |
|---|---|---|---|
| 1 | **PR #35 CI 완료 확인 후 머지** | 5/5 green 확인됨 | `gh pr merge 35 --squash --delete-branch`. |
| 2 | **PR #36 CI 완료 확인 후 머지** | e2e pending / 나머지 미보고 | #35 머지 후 base 가 master 로 자동 전환됨. CI 최종 green 후 머지. |
| 3 | **세션 마감 핸드오프 커밋** | 미커밋 | 현재 `CHANGELOG.md` + `HANDOFF.md` 수정분. 핸들오프 스킬 완료 후 사용자 승인 받아 커밋. |
| 4 | **TradingView Lightweight Charts 적용 작업** | 사용자 지정 다음 작업 | 후속 세션/현 세션 계속. recharts → TradingView 로 `/stocks/[code]` 차트 교체 (Phase D 에서 사용 중). 범위·설계 합의 필요. |
| 5 | 로그인 세션 기반 실데이터 재측정 (`/portfolio`, `/settings`) | 선택 | DevTools 수동 절차 (scores.md §측정 방법 B) — staging 환경 구성 시 lhci 자동화로 이관 |
| 6 | 실기기 점검 (Phase E3) | 선택 | iPhone SE/13, Galaxy S8, iPad mini |
| 7 | lhci 자동화 | 별도 스프린트 | staging + 로그인 세션 시드 준비 후 |
| 8 | 이전 세션 이월: 다른 서비스 DIP 확장 (Telegram/Krx/Dart) | 백엔드, 1~2h | PR #25 KIS leading example 복제 |
| 9 | 이전 세션 이월: DB 모델 `Mapped[str]` → `Literal` 좁히기 | 백엔드, 1h | Router exhaustive check |
| 10 | 이전 세션 이월: R-04/R-05/R-06 소규모 이슈 | 각 30분 | MOCK 401 재분류 / `/sync` 400 테스트 / `.git-blame-ignore-revs` |

미커밋 변경: **있음** (`HANDOFF.md` overwrite + `CHANGELOG.md` prepend). 세션 마감 시 `docs: 세션 마감 핸드오프 — 2026-04-23 Gate 3 측정/수정 완결` 로 커밋 예정.

## Key Decisions Made

### 측정 환경

1. **prod docker 스택 경유 측정 채택**: dev 서버(`uvicorn` + `yarn dev`) 대비 실제 배포 구성(번들 분할, caddy 압축) 이 반영되어 점수 신뢰도 ↑. self-signed 인증서 이슈는 chrome-flags `--ignore-certificate-errors` 로 해결 (스크립트 내장).
2. **PR 스택 구조 (#35 ← #36)**: #35 의 측정 결과 기록과 #36 의 Perf 수정을 분리 PR 로 운영. 이유: (a) 리뷰 초점 분리, (b) 1차 측정 기록을 "있는 그대로" 보존해 진단 서사 유지, (c) 사후 수정 작업의 투자 대비 효과를 독립 측정.

### /stocks/005930 진단

3. **초기 가설(recharts dynamic import for TBT) 반증**: 가설은 그럴듯했지만 JSON audit 확인 결과 **TBT = 48ms ("Good")** → dynamic import 로 얻을 이익 거의 없음. 실제 병목은 **CLS 0.362** (footer shift × 2). JSON 분석 없이 상용 가설만 좇았으면 잘못된 최적화에 시간 허비했을 것 — **"lighthouse JSON 먼저 읽고 수정 방향 결정"** 을 이번 세션 교훈으로 기록.
4. **CSS-only 수정 채택**: footer shift 는 스켈레톤 높이 부족 + `useMediaQuery` hydration 재배치가 원인. JS 런타임이 아니라 CSS 레이아웃 문제라 (a) `aspect-ratio` Tailwind 클래스, (b) `min-h-[calc(100dvh-8rem)]` 만으로 해결. JS 훅 삭제로 부가 이익(번들 소폭 감소 + hydration 경로 단순화).
5. **남은 CLS 0.123 (header card 내부) 은 닫음**: Gate 3 목표(Perf 85+) 통과 + "Needs Improvement" 범위(0.1~0.25) 중간 값 → 효용 낮음. 다음 차트 교체 작업(TradingView) 에서 header 카드 구조도 건드릴 가능성 있으니 그때 재측정으로 자연 해결 기대.

### Next.js 16 제약 확인

6. **`src/frontend/AGENTS.md` 명시**: "This is NOT the Next.js you know. … Read `node_modules/next/dist/docs/` before writing any code." 이번 세션은 CSS/Tailwind 변경만이라 해당 안 됨. TradingView 적용 시 dynamic import/Client Component 패턴이 Next.js 16 문법과 다를 수 있으니 **구현 전 `node_modules/next/dist/docs/` 먼저 확인** 규칙 세션간 이월.

## Known Issues

- **로컬 repo `credential.helper` 가 AWS CodeCommit helper 로 설정됨** → GitHub 푸시 실패. repo 단위로 `!gh auth git-credential` 로 overlay 해 해결 (이전 세션에 이미 해결). 이 저장소는 gh 토큰 우선 상태.
- **`.claude/scheduled_tasks.lock`** — ScheduleWakeup 사용 시 로컬에 생성되는 일시 파일. 세션 종료와 함께 삭제되므로 `.gitignore` 추가 불필요.
- **PR #36 CI e2e pending**: 머지 전 반드시 green 확인 필요.
- **로그인 의존 페이지 측정은 비로그인 셸 기준**: `/portfolio`, `/settings`, `/portfolio/1/alignment` 의 PR #35 기록 점수는 로그인 리다이렉트 상태의 점수. 실데이터 상태는 별도 측정 절차 필요 (scores.md §측정 방법 B).

## Context for Next Session

### 사용자의 원 목적 (본 세션 연속)
Gate 3 증빙을 실제 측정값으로 닫고, 결과에 따라 추가 최적화까지 끝내기. 본 세션에서 측정 + 수정 1-cycle 완주.

### 선택한 접근과 이유
- **측정 → 진단 → 최소 수정 → 재측정** 의 단계별 분할: 각 단계를 별 PR 로 분리해 의사결정 근거를 문서로 남김. "JSON 먼저 본다" 규칙이 이번 세션에서 가장 큰 가치 산출.
- **prod docker 스택 재빌드 + caddy 경유**: 배포 구성 반영된 점수 + 스크립트를 dev/prod 양쪽에 쓸 수 있게 확장.

### 사용자 선호/제약 (재확인)
- **한국어 커밋 메시지 + `Co-Authored-By: Claude Opus 4.7 (1M context)`** 유지 (글로벌 CLAUDE.md 규칙).
- **`git push` 는 명시 요청 시에만** (글로벌 CLAUDE.md). 본 세션도 명시 요청 확인 후 푸시.
- **Next.js 16 는 훈련 데이터와 다르다** (`src/frontend/AGENTS.md` 명시). 새 API/패턴 도입 전 `node_modules/next/dist/docs/` 확인 필수.

### 다음 세션에서 먼저 확인할 것 (사용자 명시 다음 작업)
1. **TradingView Lightweight Charts 적용 작업** — 사용자 요청. 현재 `src/frontend/src/app/stocks/[code]/page.tsx` 의 recharts `ComposedChart` 를 TradingView `lightweight-charts` 로 교체. Phase D 의 CSS aspect 는 유지(충돌 없음), `ReferenceDot` 으로 표시하던 signal 마커 재구현 필요. 예상 난이도: **중**. 착수 전 다음 사항 합의 필요:
   - (a) 적용 범위 — 종목상세만? 백테스트도 포함?
   - (b) 라이선스 — `lightweight-charts` Apache-2.0 OK, 옵션으로 "Advanced Charts" 는 별도 계약(스킵)
   - (c) Server/Client 경계 — SSR 시 차트 div 만 placeholder, hydration 후 마운트 (Next.js 16 dynamic import 패턴)
   - (d) recharts 의존성 유지/제거 — 다른 페이지(backtest, dashboard) 도 recharts 쓰므로 당장 제거 불가
2. PR #35 · #36 CI 최종 green 확인 후 순차 머지
3. 세션 마감 핸드오프 커밋

## Files Modified This Session

```
 CHANGELOG.md                                         | (prepend 이번 세션 #35/#36 2 엔트리 + #34 status 갱신)
 HANDOFF.md                                           | (overwrite)
 docs/lighthouse-scores.md                            |  28 ++--
 scripts/lighthouse-mobile.sh                         |   9 ++
 src/frontend/src/app/stocks/[code]/page.tsx          |  29 ++--
 — 추가로 untracked (gitignored):
   lighthouse-reports/*.{html,report.json,summary.md}
   /tmp/lh-smoke/*, /tmp/lh-after/*  (diagnostic dumps)
```
