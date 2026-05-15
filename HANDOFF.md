# Session Handoff

> Last updated: 2026-05-15 (KST) — **Phase H plan doc `phase-h-integration.md` 신규 작성** (사용자 요청 "H 통합 (백테 view / 데이터 품질) 까지, Grafana 는 분리"). Phase F-4 ted-run 풀 파이프라인은 여전히 **Step 0d 완료 / Step 0e 진입 직전** 미진행 상태.
> Branch: `master`
> Latest commit: `f4673e6` (HANDOFF.md push 완료 finalize — F-3 결과)
> **본 세션 commit: 0건** (Phase H plan doc + STATUS.md/HANDOFF.md 갱신만, 사용자 명시 push 요청 시까지 미커밋)
> **미푸시: 0건** (origin/master 와 동일)
> **미커밋 변경**: 8+ 파일 (tests/ 7 + Phase H plan doc 신규 + STATUS.md + HANDOFF.md)

## Current Status

Phase F-4 (5 ranking endpoint 통합 ka10027/30/31/32/23) **ted-run 풀 파이프라인 진행 중**. 사용자 D-1~D-14 권고 default 일괄 채택 후 진입. Step 0 (TDD red) 의 0a~0d 완료, 0e (Router + Batch + Integration) 미진입 상태로 세션 종료. **다음 세션 = Step 0e 부터 재개**.

### Phase F-4 진행 단계 (ted-run 13-task 진행표)

| # | Step | 상태 | 모델 | 본 세션 산출 |
|---|------|------|------|--------------|
| 0a | F-3 정착 + endpoint-18 reference 정독 | ✅ 완료 | (메인) | 패턴 + Migration 번호 정정 (007→018) 확정 |
| 0b | Migration 018 + ORM + Repository 테스트 | ✅ 완료 | (메인) | `test_migration_018.py` (9) + `test_ranking_snapshot_repository.py` (14) + `test_stock_repository.py` +4 (find_by_codes) |
| 0c | Adapter + _records 테스트 | ✅ 완료 | (메인) | `test_rkinfo_client.py` (25) + `test_records_ranking.py` (16) |
| 0d | DTO + Service 테스트 | ✅ 완료 | (메인) | `test_ranking_dto.py` (8) + `test_ranking_service.py` (22, 통합) |
| **0e** | **Router + Batch + Integration 테스트** | **🔄 다음 세션 진입점** | sonnet | `test_rankings_router.py` + `test_ranking_jobs.py` + `test_scheduler_phase_f_4.py` + `tests/integration/test_ranking_snapshot_e2e.py` (~35 케이스) |
| 0f | red 확인 (pytest -x) | ⏳ 대기 | (메인) | collection error / FAILED 의도된 red 검증 |
| 1 | 구현 — green 도달 | ⏳ 대기 | **opus** | Migration 018 + 11 production 파일 |
| 2a R1 | 1차 리뷰 | ⏳ 대기 | sonnet | python-reviewer |
| 2b R1 | 적대적 리뷰 | ⏳ 대기 | **opus** | security-review (force, F-3 관행) |
| 2 fix R1 | HIGH/MEDIUM 수정 | ⏳ 대기 | opus | |
| 2 R2 | 재리뷰 | ⏳ 대기 | sonnet+opus | |
| 3 | Verification 5관문 | ⏳ 대기 | sonnet+opus+haiku | alembic up + ruff + mypy + pytest + cov + 런타임 |
| 5 | Ship — ADR § 48 + 메타 3종 + 커밋 | ⏳ 대기 | (메인) | HANDOFF + CHANGELOG + STATUS + ADR + 한글 커밋 |

> Step 4 E2E ⚪ 자동 생략 (백엔드 전용 + 계약 분류).
> Step 3-4 보안 스캔 ⚪ 자동 생략 (계약 분류 — 신규 인증 로직 0).

### 본 세션 TDD red 누적

| 파일 | 케이스 수 | 위치 |
|------|----------|------|
| `test_migration_018.py` | 9 | `src/backend_kiwoom/tests/` |
| `test_ranking_snapshot_repository.py` | 14 | 동 |
| `test_stock_repository.py` (갱신) | +4 (find_by_codes) | 동 |
| `test_rkinfo_client.py` | 25 | 동 |
| `test_records_ranking.py` | 16 | 동 |
| `test_ranking_dto.py` | 8 | 동 |
| `test_ranking_service.py` (통합) | 22 | 동 |
| **소계** | **98** | — |

> Step 0e 작성 시 +35 케이스 추가 예정 (router 15 + batch 5 + integration 8 + scheduler 갱신 7).

## Completed This Session

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | Step 0a — F-3 정착 + endpoint-18 reference + 19~22 응답 schema 정독 | (미커밋) | — (분석만) |
| 2 | Step 0b — Migration 018 + Repository + find_by_codes 테스트 작성 | (미커밋) | 3 파일 (2 신규 + 1 갱신) |
| 3 | Step 0c — Adapter rkinfo + _records 테스트 작성 | (미커밋) | 2 파일 신규 |
| 4 | Step 0d — DTO + Service 통합 테스트 작성 | (미커밋) | 2 파일 신규 |
| 5 | TaskCreate 13개 — Phase F-4 ted-run 진행표 가시화 | (메모리만) | — |

> **커밋 0건의 의도**: Step 0 TDD red 단계 완료까지는 _테스트만 작성_ + _구현 0_ 이라 red 검증 (Step 0f) 후 Step 1 구현 단계에서 일괄 커밋 (F-1/F-2/F-3 패턴 일관).

## In Progress / Pending

| # | Task | Status | Notes |
|---|------|--------|-------|
| **1** | **Phase F-4 Step 0e — Router + Batch + Integration 테스트** | **🔄 다음 세션 1순위** | ~35 케이스. 작성 대상: `tests/test_rankings_router.py` (15 endpoint × 1-2 admin 회귀) + `tests/test_ranking_jobs.py` (5 cron fire/misfire/errors_above_threshold 알람) + `tests/test_scheduler_phase_f_4.py` (5 cron 등록 검증) + `tests/integration/test_ranking_snapshot_e2e.py` (testcontainers PG16 JSONB GIN 검증) |
| **2** | **Phase F-4 Step 0f → Step 1 (구현)** | 0e 완료 후 | red 확인 → opus 구현. 11 production 파일 (Migration 018 + ORM + Repository + Adapter rkinfo + _records 갱신 + DTO + Service + Router + Batch + DI + main.py) |
| **3** | **Phase F-4 Step 2~Step 5** | 1 완료 후 | 이중 리뷰 (sonnet+opus) + Verification 5관문 + Ship (ADR § 48 + 메타 3종 + 한글 커밋) |
| 4 | 5-15 (금) 06:00 + 07:30 + 08:00 자연 cron 검증 | 운영 검증 (코드 0) | F-1 + F-2 + F-3 효과 동시 검증. **F-4 코드와 무관 — 병행 진행** |
| 5 | F-3 R2 inherit 5건 (ADR § 47.8) | Phase F-4 합류 또는 별도 | inh-1 router DTO breaking consumer 식별 (F-4 ranking router 진입 시) / inh-2 coverage 설정 / inh-3 SkipReason 위치 / inh-4 lending progress log / inh-5 ruff (해소됨) |
| 6 | (5-19 이후) § 36.5 1주 모니터 측정 | § 43 효과 정량화 | 12 scheduler elapsed / catch-up 빈도 |
| 7 | Phase D-2 ka10080 분봉 (마지막 endpoint) | 대기 | 대용량 파티션 결정 동반 |
| 8 | Phase G (투자자별 3종 — ka10058/59/10131) | 대기 | plan doc 미작성. Phase H 진입 전 작성 필요 |
| **9** | **Phase H — 통합 (백테 view + 데이터 품질 + README/SPEC.md)** — Grafana 제외 | **plan doc 작성됨** (`phase-h-integration.md` 2026-05-15) | 25 endpoint 100% 도달 후 진입. 결정 게이트 D-1~D-6 (view 전략 / 알람 채널 / SPEC 범위 / cron / retention / backfill view) 사용자 확정 필수 |
| 10 | (선택) Phase H' — Grafana 대시보드 | 사용자 마지막 chunk 분리 요청 | Phase H 완료 후 사용자 재요청 시 plan doc 작성 |
| 11 | secret 회전 / .env.prod 정리 | 전체 개발 완료 후 | — |

## Key Decisions Made

1. **D-1~D-14 권고 default 일괄 채택** (사용자, 2026-05-14)
   - D-1 통합 1 chunk (옵션 A) — 견적 ~2,500줄 임계 초과 동의 (메모리 `feedback_chunk_split_for_pipelines` 명시 합의)
   - D-2 ranking_snapshot 단일 테이블 + JSONB payload + ranking_type 컬럼
   - D-3 운영 default mrkt_tp = {001, 101} (KOSPI + KOSDAQ)
   - D-4 운영 default stex_tp = 3 (통합)
   - D-5 ka10027 운영 default sort_tp = {1, 3} (UP_RATE + DOWN_RATE)
   - D-6 cron 19:30/35/40/45/50 KST mon-fri (5분 chain sequential)
   - D-7 snapshot_time 초 단위 (HH:MM:SS)
   - D-8 stock lookup miss → stock_id=NULL + stock_code_raw 보관 (alert 후속)
   - D-9 ka10030 23 필드 nested payload ({opmr, af_mkrt, bf_mkrt} 분리)
   - D-10 SkipReason.STOCK_LOOKUP_MISS 추가 안 함 (lookup miss 는 skip 이 아님)
   - D-11 errors_above_threshold 임계치 도입 안 함 (운영 1주 모니터 후)
   - D-12 primary_metric NUMERIC(20, 4)
   - D-13 GIN index payload 1개
   - D-14 5 endpoint scheduler chain sequential (asyncio.gather 아님)

2. **Migration 번호 정정**: plan doc `phase-f-4-rankings.md` 의 "007_ranking_snapshot" 은 **stale** — 실제 head 가 `017_ka10001_numeric_precision` 이라 신규 = **018_ranking_snapshot**. Step 5 (Ship) 에서 ADR § 48 + plan doc 정정 일괄 처리.

3. **plan doc § 5.12 변형 — 통합 1 파일 채택**: 6 파일 분할 (test_ingest_flu_rt_use_case.py 등) 권고 → **통합 1 파일** `test_ranking_service.py` 로 작성. 5 endpoint 가 같은 service module + 같은 client + 같은 repository 공유라 maintainability 우수. ADR § 48 D-1 변형 결정 기록 예정.

4. **cron 충돌 검증 — 19:30/35/40/45/50 충돌 0**: plan doc § 6.2 / § 10 의 "ka10014 19:45 충돌" 우려는 _Phase E 이전 stale_. ka10014 가 07:30 로 이동 완료 (`app/scheduler.py:984-1175`). 19:30 ranking chain 진입 가능.

5. **자동 분류 — 계약 변경 (contract)**: Migration 018 + 15 router + 5 DTO + 5 cron. "admin"/"credential" 키워드 매칭되나 _신규 보안 로직 0_. 사용자 메모리 `feedback_keep_existing_workflow` 정책으로 2b 적대적 리뷰 **강제 실행** (F-3 관행 유지).

6. **find_by_codes bulk 메서드 신규 필요**: `StockRepository.find_by_code` 단건만 존재. ka10027 sync 호출당 ~150 종목 → 단건 N번 비효율. Step 1 구현에서 신규 추가.

## Known Issues

| # | 항목 | 출처 | 결정 |
|---|------|------|------|
| 13 | 일간 cron 실측 | dry-run § 20.4 | 5-19 이후 |
| 20 | NXT 우선주 sentinel 빈 row 1 | § 32.3 | LOW |
| 22 | `.env.prod` 정리 | § 38.6.2' | 개발 완료 후 |
| 23 | secret 회전 | § 38.8 #6/#7 | 개발 완료 후 |
| ~~24~~ | ~~Mac 절전 컨테이너 중단~~ | § 38.8 #1 / § 42~44 | 🔄 부분 해소 / 5-15 자연 cron 검증 대기 |
| 30 | 2b 2R M-1 cross-scheduler catch-up race | § 43 plan § 5 H-6 | 운영 위반 시 별도 chunk |
| ~~32~~ | ~~F-2 R2 inherit 7건~~ | ADR § 46.8 | ✅ 해소 (Phase F-3, ADR § 47) |
| 33 | Phase F-4 chunk 크기 ~2,500줄 임계 초과 | 견적 | ✅ 사용자 명시 합의 (옵션 A 통합 1 chunk) |
| 34 | F-3 R2 inherit 5건 | ADR § 47.8 | Phase F-4 합류 가능 (특히 inh-1 router DTO breaking 식별) |
| **35** | **Phase F-4 plan doc Migration 번호 stale (007 → 018)** | 본 세션 발견 | ✅ 정정 결정 (Step 5 Ship 에서 plan doc + ADR § 48 일괄) |
| **36** | **Phase F-4 plan doc § 5.12 12 파일 분할 → 통합 1 파일 변형** | 본 세션 결정 | ADR § 48 D-1 변형 기록 |
| **37** | **`StockRepository.find_by_codes` bulk 메서드 부재** | 본 세션 발견 | Step 1 구현에서 신규 추가. 테스트는 작성됨 (4 케이스 red) |

## Context for Next Session

### 다음 세션 진입점 (즉시 재개 가능)

```
"Phase F-4 Step 0e 진행. test_rankings_router.py + test_ranking_jobs.py +
 test_scheduler_phase_f_4.py + tests/integration/test_ranking_snapshot_e2e.py
 작성 (~35 케이스 red)."
```

### Step 0e 작성 가이드라인 (다음 세션이 즉시 참조)

1. **test_rankings_router.py** (~15 케이스):
   - 5 endpoint × 3 라우터 = 15 endpoint
   - 각 endpoint POST 단건 + POST sync bulk = admin 인증 회귀 (`require_admin_key`)
   - GET snapshot (admin 무관, DB only)
   - Pydantic validation (Literal["000","001","101"] 등)
   - reference 패턴: `app/adapter/web/routers/short_selling.py` + `tests/test_fundamental_router.py`

2. **test_ranking_jobs.py** (~10 케이스):
   - 5 cron — `fire_flu_rt_sync` / `fire_today_volume_sync` / `fire_pred_volume_sync` / `fire_trde_prica_sync` / `fire_volume_sdnin_sync`
   - 각 cron 의 trading day 가드 (is_trading_day)
   - BulkUseCase 호출 검증
   - errors_above_threshold tuple → `logger.error` (F-3 D-3 패턴 미러)
   - reference: `tests/test_short_selling_use_case_sentinel.py` 일부 + `app/batch/short_selling_job.py` 패턴

3. **test_scheduler_phase_f_4.py** (~7 케이스):
   - 5 cron 등록 (`scheduler.add_job` × 5)
   - CronTrigger(day_of_week="mon-fri", hour=19, minute=30/35/40/45/50)
   - misfire_grace_time 검증
   - reference: `tests/test_scheduler_phase_e.py` 1:1

4. **tests/integration/test_ranking_snapshot_e2e.py** (~8 케이스 — testcontainers PG16):
   - INSERT 50 row + UPDATE 멱등 (NormalizedRanking × 50)
   - JSONB payload 쿼리 (`payload->>'cur_prc'` GIN index 활용)
   - lookup miss NULL
   - 5 ranking_type 분리 동시 적재
   - reference: `tests/integration/` 디렉토리 없으면 신규 + conftest engine fixture 재사용

### 사용자 메모리 정책 (다음 세션 자동 적용)

- `feedback_progress_visibility` — 체크리스트 + 한 줄 현황 가시화
- `feedback_chunk_split_for_pipelines` — D-1 옵션 A (통합) 사용자 합의 완료
- `feedback_ted_run_model_reporting` — Step 표 모델 명시 + Step 2a sonnet sub-agent 호출 누락 금지
- `feedback_keep_existing_workflow` — 풀 카탈로그 + ADR/STATUS/HANDOFF/CHANGELOG 3종 갱신
- `feedback_recommendation_over_question` — AskUserQuestion 4-option 추천 자제
- 글로벌 — 커밋 한글, 푸시 명시 요청 시만

### 핵심 reference 위치

- **plan doc**: `src/backend_kiwoom/docs/plans/phase-f-4-rankings.md` (D-1~D-14 + § 5 변경면)
- **endpoint reference**: `src/backend_kiwoom/docs/plans/endpoint-18-ka10027.md` (Phase F backbone) + 19~22 (차이점)
- **F-3 정착 패턴**: `app/application/dto/_shared.py` (SkipReason) + `app/application/dto/short_selling.py` (tuple errors_above_threshold + skipped_count property + `__all__`) + `app/application/service/short_selling_service.py` (`_empty_bulk_result` + 단건 D-7 catch + `# pragma: no cover` 마커)
- **Migration head**: `017_ka10001_numeric_precision` — 신규 = **018_ranking_snapshot**
- **STATUS.md**: `src/backend_kiwoom/STATUS.md` — chunk 완료 후 § 0/§1/§2/§4/§5/§6 갱신 (Step 5)
- **TaskCreate 13개** — Phase F-4 진행표 가시화 (#1 ~ #13)

### 운영 위험 / 주의

- **본 세션 코드 적용 안 됨** — TDD 테스트만. 컨테이너 redeploy 시점 = Phase F-4 chunk 완료 후 사용자 결정
- **5-15 자연 cron 검증은 F-3 효과만** (F-4 코드 미머지) — 별도 작업
- **Migration 018 dry-run** (Step 3-1 verification) — kiwoom-db `alembic upgrade head` smoke 필수. 운영 DB 적용은 redeploy 시점 따로

## Files Modified This Session

### Test 신규 6 파일 (~98 케이스 red)
- `src/backend_kiwoom/tests/test_migration_018.py` (+424줄, 9 케이스) — Migration 018 검증 (컬럼 / FK / UNIQUE 7 / 타입 NUMERIC(20,4) / GIN / partial index / downgrade)
- `src/backend_kiwoom/tests/test_ranking_snapshot_repository.py` (+421줄, 14 케이스) — upsert INSERT/UPDATE 멱등 / lookup miss NULL / NXT _NX 보존 / nested JSONB (D-9) / get_at_snapshot / 5 ranking_type 분리 / NUMERIC 정확성 / ON DELETE SET NULL
- `src/backend_kiwoom/tests/test_rkinfo_client.py` (+575줄, 25 케이스) — 5 fetch (ka10027 8건 풀 + ka10030 4건 + ka10031 3건 + ka10032 3건 + ka10023 3건 + 공통 4건)
- `src/backend_kiwoom/tests/test_records_ranking.py` (+292줄, 16 케이스) — 7 enum + 5 Row.to_payload + nested D-9 + extra=ignore + frozen
- `src/backend_kiwoom/tests/test_ranking_dto.py` (+143줄, 8 케이스) — Outcome frozen / Bulk tuple errors / aggregate properties
- `src/backend_kiwoom/tests/test_ranking_service.py` (+595줄, 22 케이스 통합) — ka10027 단건 7 + Bulk 5 + ka10030~23 차이점 7 + 공통 5

### Test 갱신 1 파일
- `src/backend_kiwoom/tests/test_stock_repository.py` (+77줄, +4 케이스) — `find_by_codes` bulk lookup 메서드 (정상 / 빈 / lookup miss / 중복 코드)

### Production 0 파일
(Step 0 TDD red 단계 — 구현 0)

### 미커밋 차이 (git status)
```
M  src/backend_kiwoom/tests/test_stock_repository.py
?? src/backend_kiwoom/tests/test_migration_018.py
?? src/backend_kiwoom/tests/test_ranking_dto.py
?? src/backend_kiwoom/tests/test_ranking_service.py
?? src/backend_kiwoom/tests/test_ranking_snapshot_repository.py
?? src/backend_kiwoom/tests/test_records_ranking.py
?? src/backend_kiwoom/tests/test_rkinfo_client.py
```

> **다음 세션이 즉시 진입 가능**: TaskCreate 13개 + 본 HANDOFF + plan doc `phase-f-4-rankings.md` + 본 세션 작성 7 파일이 컨텍스트 완비.

---

_Phase F-4 ted-run chunk 진행 중 (Step 0d 완료 / 0e 진입 직전). TDD 98 케이스 red 누적. Migration 번호 (018) + plan doc § 5.12 변형 (통합 1 파일) + find_by_codes bulk 신규 결정 — Step 5 (Ship) 에서 ADR § 48 일괄 기록 예정._
