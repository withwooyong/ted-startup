# Session Handoff

> Last updated: 2026-05-16 (KST) — **Phase G ted-run 풀 파이프라인 완료** (메모리 정책 `feedback_plan_doc_per_chunk` 정착 첫 chunk). 25 endpoint **23/25 (92%)** 도달. ADR § 49 신규 / plan doc § 11~15 누적 / 메타 4종 동시 갱신.
> Branch: `master`
> Latest commit: `e8c901d` (Phase G 3 endpoint 통합)
> **본 세션 commit: 1건** (Phase G + 메타 4종 일괄)
> **미푸시: 1건** (사용자 push 명시 요청 시 push — 글로벌 정책)

## Current Status

**Phase G ✅ 완료** — ka10058/10059/10131 3 endpoint 통합. Migration 019 + 3 테이블 (`investor_flow_daily` / `stock_investor_breakdown` / `frgn_orgn_consecutive`) + `KiwoomForeignClient` 신규 (`/api/dostk/frgnistt`) + 9 라우터 + 3 cron (20:00/20:30/21:00 KST mon-fri).

운영 적용 후 **5-18 (월) 20:00 KST 첫 cron 자연 발화** — ka10058 → 30분 후 20:30 ka10059 (3000 종목 60분 sync) → 21:00 ka10131.

### 본 chunk ted-run 11-task 진행표 (모두 ✅)

| Step | 결과 | 모델 |
|------|------|------|
| 0a 자산 점검 + Migration 019 골격 | ✅ head 018 확인 / F-3/F-4 helper 시그니처 | (메인) |
| 0b TDD red 작성 | ✅ 14 파일 / 4,829 라인 / ~185 케이스 / 13 collection error 의도된 red | **sonnet sub-agent** |
| 0c pytest collection red 확인 | ✅ 10 collected + 13 ImportError | (메인) |
| **1 구현 — green 도달** | ✅ 22 파일 / +~3,900 라인 / pytest 1596 PASS / mypy 114 / cov 85% | **opus sub-agent** |
| 2a R1 sonnet python-reviewer | ✅ 5.8/10 RETRY (CRITICAL 3 + HIGH 3 + MED 5 + LOW 4) | sonnet sub-agent |
| 2b R1 opus 적대적 | ✅ 4.5/10 운영 D (CRITICAL 8 + HIGH 7 / 적대적 시뮬 7 PASS + 1 N/A) | **opus sub-agent** |
| 2 fix R1 | ✅ 17 fix 일괄 (G-1) / 8 파일 +~700/-100 / pytest 1596 유지 | opus sub-agent |
| 2a R2 sonnet | ✅ 9.2/10 PASS / 17/17 fix 정확성 / 신규 결함 0 | sonnet sub-agent |
| 2b R2 opus 적대적 | ✅ 8.4/10 B+ CONDITIONAL / 적대적 시뮬 4.5/5 / inherit 5 | opus sub-agent |
| 3 Verification 5관문 | ✅ ruff + mypy 114 + pytest 1596 + cov 84% + scheduler smoke 20 schedulers | (메인) |
| 4 E2E | ⚪ 자동 생략 (UI 0) | — |
| **5 Ship** | ✅ ADR § 49 + plan doc § 11~15 + 메타 4종 + 한글 커밋 | (메인) |

> **메모리 정책 `feedback_plan_doc_per_chunk` 정착 첫 chunk** — plan doc 신규 (`phase-g-investor-flow.md` 485줄) → 결정 게이트 17건 사용자 확정 (AskUserQuestion Recommended 포함) → `/ted-run` skill **명시 호출** → 메타 4종 동시 commit. F-4 (Agent tool ad-hoc) 와 대조.

## Completed This Session

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | Phase G plan doc 신규 (`phase-g-investor-flow.md` 17 결정 게이트 + 10 § / 485줄 → 누적 갱신 후 ~800줄) | `e8c901d` | 1 plan doc |
| 2 | Phase G Step 0b TDD red 14 테스트 파일 / ~185 케이스 (sonnet sub-agent) | (commit 일괄) | 14 test |
| 3 | Phase G Step 1 구현 22 파일 (신규 16 + 갱신 6) / +~3,900 라인 (opus sub-agent) | 동일 | 22 production |
| 4 | Phase G Step 2 fix R1 17건 일괄 (G-1 즉시 / 8 파일 +~700/-100) | 동일 | 8 파일 (4 갱신) |
| 5 | Phase G Step 2 R2 — sonnet 9.2 PASS + opus 8.4 B+ CONDITIONAL | (변경 0) | — |
| 6 | ADR § 49 신규 (9 sub-§) | 동일 | ADR-0001 |
| 7 | plan doc § 11~15 누적 갱신 (`phase-g-investor-flow.md`) | 동일 | plan doc |
| 8 | STATUS.md § 0 / § 1 / § 2 / § 4 / § 5 / § 6 (80% → 92%) | 동일 | STATUS |
| 9 | HANDOFF.md rewrite (본 문서) | 동일 | HANDOFF |
| 10 | CHANGELOG.md prepend | 동일 | CHANGELOG |

## In Progress / Pending

| # | Task | Status | Notes |
|---|------|--------|-------|
| **1** | **5-17 (월) 19:30 F-4 첫 cron 자연 검증** | 운영 자동 | ka10027 → 5분 chain → 19:50 ka10023. 본 세션 전 chunk (F-4) 효과 |
| **2** | **5-18 (월) 20:00 Phase G 첫 cron 자연 검증** | 운영 자동 | 20:00 ka10058 → 20:30 ka10059 (3000 종목 60분 sync) → 21:00 ka10131. 운영 검증 8건 (ka10059 완주율 / inh-1 PG abort / 토큰 만료 / netslmt_qty 부호 / flu_rt 표기 / amt_qty_tp 반대 / tot_cont_days 합산 / `_NX` Length=6) |
| **3** | **inh-1 Bulk 트랜잭션 오염 fix** (Phase E/F-4/G 상속, D-12 옵션 A) | 🔄 5-25 (월) 별도 chunk | dry-run 5-18~5-22 (5거래일) 결과 후 SAVEPOINT (begin_nested) vs 단건당 별도 세션 결정. N-1 (NULL distinct) 통합 가능 |
| 4 | Phase G R2 inherit 5건 (inh-1~inh-5) | 분산 | inh-1 = D-12 chunk / inh-2 D-11 임계치 = Phase H / inh-3 N-1 = D-12 통합 / inh-4 N-2 = Phase H 품질 / inh-5 H-5 `_unwrap_client_rows` = type-safety chunk |
| **5** | **Phase D-2 ka10080 분봉 (마지막 endpoint)** | inh-1 직후 | 대용량 파티션 결정 동반. 25 endpoint 100% 도달 |
| **6** | **Phase H — 통합 (백테 view + 데이터 품질 + README/SPEC)** — _Grafana 분리_ | plan doc 작성됨 | 25 endpoint 100% 도달 후 진입 (D-2 선행). 결정 게이트 D-1~D-6 사용자 확정 필수 |
| 7 | (선택) Phase H' — Grafana 대시보드 | 사용자 마지막 chunk | Phase H view + alert 위에 시각화 |
| 8 | secret 회전 / .env.prod 정리 | 전체 개발 완료 후 | — |

## Key Decisions Made

1. **사용자 D-1~D-17 권고 default 일괄 채택** (2026-05-16) — Phase G ted-run 진입 시
2. **메모리 정책 `feedback_plan_doc_per_chunk` 정착 첫 chunk** — plan doc 신규 → /ted-run skill 명시 호출 → 메타 4종 동시 commit. F-4 (Agent tool ad-hoc) 와 대조
3. **G-1/G-2/G-3 패턴 미러** (F-4 정착 그대로): G-1 즉시 일괄 fix / G-2 misfire 21600 통일 / G-3 단건 모드 분리
4. **D-12 옵션 A 채택** — inh-1 트랜잭션 오염 mitigate 본 chunk 미구현 (docstring 정정만), 5-25 별도 chunk 로 분리
5. **`amt_qty_tp` 의미 반대** (ka10059 1=금액/2=수량 vs ka10131 0=금액/1=수량) — D-15 별도 enum 분리 (컴파일 타임 가드)
6. **`InvestorMarketType` 신규 enum** — D-17 (vs F-4 `RankingMarketType` 재사용 X) — 의미 분리 (`000` 미지원)
7. **chunk 분할 임계 초과** — F-4 (~2,070) 대비 본 chunk +120% (~4,600 라인 production). 사용자 D-1(a) 통합 1 chunk 명시 확정 후 진행. `feedback_chunk_split_for_pipelines` 임계 1,500줄 크게 초과 — **backend_kiwoom 최대 chunk**

## Known Issues (요약 — 상세 STATUS § 4)

| # | 항목 | 결정 |
|---|------|------|
| **40** | 5-17 (월) 19:30 첫 F-4 ranking cron 발화 검증 | 운영 자동 |
| **41** | Coverage dip 누적 86.56% → 84% (F-4 -1.56%p + Phase G -1.0%p) | 운영 1주 후 재평가 |
| **42** | Phase G R2 inherit 5건 | ADR § 49.4 / § 49.8 |
| **43** | 5-18 (월) 20:00 첫 Phase G cron 발화 검증 | 운영 자동 |

## Context for Next Session

### 다음 진입점 (5-25 inh-1 D-12 chunk)

```
"5-18~5-22 (5거래일) Phase G dry-run 결과 분석 + inh-1 (D-12) 별도 chunk 진입.
 ka10059 60분 sync PG abort 발화 빈도 측정 결과로
 SAVEPOINT (begin_nested) vs 단건당 별도 세션 결정.
 N-1 (stock_investor_breakdown UNIQUE NULL distinct) Migration 020 통합 가능.
 1) dry-run 결과 SQL 조회 (5-18~5-22 ka10059 outcomes.error 통계)
 2) D-12 별도 chunk plan doc 신규 작성
 3) /ted-run skill 명시 호출"
```

### 메모리 정책 정착 (본 chunk 가 첫 적용)

- **chunk = plan doc + /ted-run skill 명시 호출** — Agent tool ad-hoc spawn 자제 ✅ 본 chunk 적용
- **복잡 결정 게이트는 Recommended 포함** — AskUserQuestion 추천 마크 ✅ 본 chunk D-1/D-7/D-12 적용
- **메타 4종 동시 commit** — STATUS + HANDOFF + CHANGELOG + plan doc + ADR ✅ 본 chunk 적용

### 운영 검증 5-17 (월) + 5-18 (월)

| 시점 | endpoint | 검증 |
|------|----------|------|
| 5-17 19:30 | ka10027 | F-4 첫 발화 |
| 5-17 19:35 | ka10030 | 23 필드 nested payload (F-4 D-9) |
| 5-17 19:40 | ka10031 | 6 필드 단순 |
| 5-17 19:45 | ka10032 | now_rank/pred_rank |
| 5-17 19:50 | ka10023 | sdnin_qty/sdnin_rt |
| **5-18 20:00** | **ka10058** | **Phase G 첫 발화 / netslmt_qty 부호 / 12 invsr_tp 분포** |
| **5-18 20:30** | **ka10059** | **3000 종목 60분 sync 완주율 / flu_rt "+698"→6.98 / orgn 합산 / inh-1 PG abort** |
| **5-18 21:00** | **ka10131** | **amt_qty_tp 반대 의미 / tot_cont_days 합산 / `_NX` Length=6** |

공통 검증: lookup miss 비율 / errors_above_threshold 발화 0 (baseline 없음 — 운영 1주 후 임계치 D-11 검토)

---

_Phase G ted-run 풀 파이프라인 완료. 25 endpoint **23/25 (92%)** 도달. 본 chunk = **backend_kiwoom 최대 chunk** (~4,600 production + 4,829 test 라인). 다음 = 5-18 dry-run 결과 후 5-25 (월) inh-1 (D-12) 별도 chunk._
