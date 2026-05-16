# Session Handoff

> Last updated: 2026-05-16 (KST) — **Phase F-4 ted-run 풀 파이프라인 완료** (Agent tool 사용, 메모리 정책 미정착 시점). 25 endpoint **20/25 (80%)** 도달. ADR § 48 신규 / plan doc § 11~15 누적 / 메타 4종 갱신. 한글 커밋 + 사용자 push 명시 시 push.
> Branch: `master`
> Latest commit: `598b3c5` (Phase H plan doc 신규)
> **본 세션 commit: 1건 (push 완료)** + Phase F-4 마무리 commit 1건 (push 대기)
> **미커밋 변경**: Phase F-4 의 production 13 파일 + test 11 파일 (Step 0a~0e) + 메타 4종 (STATUS/HANDOFF/CHANGELOG/plan doc) + ADR § 48 + 메모리 3건 (`feedback_recommendation_over_question` update / `feedback_plan_doc_per_chunk` 신규 / MEMORY.md index) + `.env.prod` 10 신규 env

## Current Status

**Phase F-4 ✅ 완료** — ka10027/30/31/32/23 5 ranking endpoint 통합. Migration 018 + ranking_snapshot + JSONB payload + 15 라우터 + 5 cron (19:30/35/40/45/50 KST mon-fri). 사용자 D-1~D-14 일괄 + G-1/G-2/G-3 추가 확정. R1 sonnet 8.0 + opus 5.5 D → fix 10건 → R2 sonnet 9.2 PASS + opus 8.6 B+ CONDITIONAL / inherit 5건.

운영 적용 후 **5-17 (월) 19:30 첫 cron 발화** — ka10027 → 5분 chain → 19:50 ka10023.

### 본 chunk ted-run 13-task 진행표 (모두 ✅)

| Step | 결과 | 모델 |
|------|------|------|
| 0a F-3 정착 + endpoint-18 reference | ✅ | (메인) |
| 0b Migration 018 + Repository test | ✅ (27 케이스) | (메인) |
| 0c Adapter rkinfo + _records test | ✅ (41 케이스) | (메인) |
| 0d DTO + Service test | ✅ (30 케이스) | (메인) |
| 0e Router + Batch + Scheduler + Integration test | ✅ (40 케이스) | sonnet sub-agent |
| 0f pytest collection red 확인 | ✅ (3 collection error 의도) | (메인) |
| **1 구현 — green 도달** | ✅ (1424 PASS) | **opus sub-agent** |
| 2a R1 sonnet python-reviewer | ✅ (8.0/10) | sonnet sub-agent |
| 2b R1 opus 적대적 | ✅ (5.5/10 D) | opus sub-agent |
| 2 fix R1 | ✅ (10 fix) | opus sub-agent |
| 2a R2 sonnet | ✅ (9.2 PASS) | sonnet sub-agent |
| 2b R2 opus 적대적 | ✅ (8.6 B+ CONDITIONAL) | opus sub-agent |
| 3 Verification 5관문 | ✅ (ruff + mypy 103 + pytest 1424 + cov 85% + 런타임) | (메인) |
| 4 E2E | ⚪ 자동 생략 (UI 0) | — |
| **5 Ship** | ✅ ADR § 48 + plan doc § 11~15 + 메타 4종 + 한글 커밋 | (메인) |

> **메모리 정책 미정착** 인지: 본 chunk 는 Agent tool 로 진행. 메모리 신규 `feedback_plan_doc_per_chunk` 정착 후 **다음 chunk (Phase G / D-2 / H) 부터 ted-run skill 명시 호출**.

## Completed This Session

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | Phase H plan doc 신규 (`phase-h-integration.md` 10 § / 280줄) | `598b3c5` (push 완료) | 3 (plan doc + STATUS + HANDOFF) |
| 2 | Phase F-4 ted-run 풀 파이프라인 (Step 0a~0e TDD red 138 케이스) | (미커밋, Step 1 일괄) | 11 test |
| 3 | Phase F-4 Step 1 (opus) 구현 — 13 production 파일 | (미커밋, 본 chunk 일괄) | 13 production |
| 4 | Phase F-4 Step 2 fix R1 (사용자 G-1/G-2/G-3) — 10 fix / +~570/-49 | 동일 | 13 파일 |
| 5 | Phase F-4 Step 2 R2 — sonnet PASS + opus B+ CONDITIONAL | (변경 0) | — |
| 6 | ADR § 48 신규 (9 sub-§) | 동일 | ADR-0001 |
| 7 | plan doc § 11~15 누적 갱신 (`phase-f-4-rankings.md`) | 동일 | plan doc |
| 8 | STATUS.md 갱신 (60% → 80%) | 동일 | STATUS |
| 9 | HANDOFF.md rewrite (본 문서) | 동일 | HANDOFF |
| 10 | CHANGELOG.md prepend | 동일 | CHANGELOG |
| 11 | 메모리 정책 update 2건 | (메모리만) | `feedback_recommendation_over_question.md` update + `feedback_plan_doc_per_chunk.md` 신규 + MEMORY.md index |

## In Progress / Pending

| # | Task | Status | Notes |
|---|------|--------|-------|
| **1** | **Phase G — 투자자별 3종 (ka10058/10059/10131)** | **🔄 다음 chunk** | plan doc 신규 작성 필요. 메모리 정책 (`feedback_plan_doc_per_chunk` + ted-run skill 명시 호출) 정착. stock_daily_flow / investor_flow_daily / frgn_orgn_consecutive 도메인 |
| **2** | **5-17 (월) 19:30 자연 cron 검증** | 운영 자동 | ka10027 첫 발화 → 5분 chain → 19:50 ka10023. 응답 schema / row 수 / lookup miss / NXT / 23 필드 nested 검증 (운영 결정 § 6.6) |
| **3** | **inh-1 Bulk 트랜잭션 오염 fix** (Phase E 상속) | Phase G dry-run 후 | SAVEPOINT 또는 단건당 별도 세션 도입 |
| 4 | F-4 R2 inherit 4건 (inh-2~inh-5) | 분산 | docs chunk + Phase F-5 router polish + 운영 1주 후 regex + Phase H 잔여 MEDIUM |
| 5 | Phase D-2 ka10080 분봉 (마지막 endpoint) | 대기 | 대용량 파티션 결정 동반 |
| **6** | **Phase H — 통합 (백테 view + 데이터 품질 + README/SPEC)** — _Grafana 제외_ | plan doc 작성됨 (`phase-h-integration.md`) | 25 endpoint 100% 도달 후 진입 (G + D-2 선행). 결정 게이트 D-1~D-6 사용자 확정 필수 |
| 7 | (선택) Phase H' — Grafana 대시보드 | 사용자 마지막 chunk | Phase H view + alert 위에 시각화 |
| 8 | secret 회전 / .env.prod 정리 | 전체 개발 완료 후 | — |

## Key Decisions Made

1. **사용자 D-1~D-14 권고 default 일괄 채택** (2026-05-14) — Phase F-4 Step 0 진입
2. **사용자 G-1~G-3 확정** (2026-05-16) — Step 2 fix R1 진입
   - G-1 (a) 본 chunk 즉시 일괄 fix
   - G-2 (a) misfire 21600 통일
   - G-3 (b) 단건 모드 분리
3. **Migration 번호 정정**: plan doc § 5.1 "007" stale → 실제 head 017 → **018_ranking_snapshot**
4. **plan doc § 5.12 변형**: 6 파일 분할 → 통합 1 파일 `test_ranking_service.py` 채택
5. **메모리 정책 update 2건** (2026-05-16 사용자 명시 정정):
   - `feedback_recommendation_over_question`: 추천 자제 → 복잡 결정 게이트는 Recommended 포함
   - `feedback_plan_doc_per_chunk` (신규): 모든 chunk = plan doc + ted-run skill 명시 호출 + 누적 갱신 + 메타 4종 동시 commit
6. **chunk 분할 임계 (1,500줄) 초과** — 본 chunk ~2,070 라인. 사용자 G-1(a) 명시 확정 후 일괄 진행

## Known Issues (요약 — 상세 STATUS § 4)

| # | 항목 | 결정 |
|---|------|------|
| **39** | F-4 R2 inherit 5건 | ADR § 48.4 / § 48.8 |
| **40** | 5-17 (월) 19:30 첫 ranking cron 발화 검증 | 운영 자동 |
| **41** | Coverage dip 86.56% → 85.00% | 운영 1주 후 재평가 |

## Context for Next Session

### 다음 진입점 (Phase G)

```
"Phase G — 투자자별 3종 (ka10058/10059/10131) plan doc 신규 작성.
 메모리 정책 (feedback_plan_doc_per_chunk) 정착 첫 chunk.
 1) plan doc 신규 (§ 1~10) 작성
 2) 사용자 결정 게이트 수집 (D-1~D-N)
 3) /ted-run skill 명시 호출 → 풀 파이프라인 자동화"
```

### 메모리 정책 정착 우선순위 (다음 chunk 부터)

- **chunk = plan doc + ted-run 명시 호출** — Agent tool ad-hoc spawn 자제
- **복잡 결정 게이트는 Recommended 포함** — AskUserQuestion 추천 마크 사용
- **메타 4종 동시 commit** — STATUS + HANDOFF + CHANGELOG + plan doc

### 운영 검증 5-17 (월) — 본 chunk 효과 자동

| 시점 | endpoint | 검증 |
|------|----------|------|
| 19:30 | ka10027 | 응답 schema / row 수 / sort_tp = {1,3} |
| 19:35 | ka10030 | 23 필드 nested payload (D-9 opmr/af_mkrt/bf_mkrt) |
| 19:40 | ka10031 | 6 필드 단순 |
| 19:45 | ka10032 | now_rank/pred_rank 직접 응답 |
| 19:50 | ka10023 | sdnin_qty/sdnin_rt sort 분기 |

공통 검증: NXT `_NX` 보존 / lookup miss 비율 / errors_above_threshold 발화 0 (baseline 없음 — 운영 1주 후 임계치 결정 D-11)

---

_Phase F-4 ted-run 풀 파이프라인 완료. 25 endpoint **20/25 (80%)** 도달. 다음 chunk = Phase G (메모리 정책 `feedback_plan_doc_per_chunk` 정착 첫 chunk — ted-run skill 명시 호출)._
