# phase-h-integration.md — Phase H 통합 (백테스팅 view + 데이터 품질 리포트 + README/SPEC.md)

> Phase H = 25 endpoint 도입 완료 후의 **derived feature 통합 단계**. 코드 신규 추가는 view + 품질 SQL + 알람 + 문서가 주축. endpoint 추가 0건.
> **Grafana 대시보드는 본 chunk 범위 외** (사용자 명시 — 별도 마지막 chunk 로 재요청).
> 사용자 요청 (2026-05-15): F-4 마무리 → D-2 → G 완료를 전제로 Phase H 계획 수립부터 진행.

---

## 1. 메타

| 항목 | 값 |
|------|-----|
| Chunk ID | Phase H |
| 선행 chunk | **Phase F-4 (5 ranking) + D-2 (ka10080 분봉) + G (3 endpoint: ka10058/59/10131)** 전부 완료 |
| 후속 chunk | (선택) Phase H' — Grafana 대시보드 (사용자 마지막 chunk 로 재요청) |
| 분류 | 통합 / derived feature / 문서 |
| 우선순위 | P2 (백테스팅 가시화 + 데이터 신뢰도) |
| 출처 | `master.md` § 5 Phase H + § 3 NXT 수집 전략 + § 8.3 NXT 검증 시나리오 4 |
| 예상 규모 | view 4 + SQL 8~12 + 알람 1~2 + README/SPEC 갱신 = ~500-800 production line + ~300-500 test line (~1,000-1,300 lines) |
| ted-run 적용 여부 | ✅ (메모리 `feedback_ted_run_scope` — 새 코드 작업 대상) |
| 25 endpoint 진행률 | 100% 진입 후 작업 (선행 완료 전제) |

> **chunk 분할 검토**: 본 chunk 가 plan doc § 5 견적 ~1,000 line 라 단일 chunk 처리 가능. 단 사용자 결정 게이트 (§ 4) 가 많아 ted-run 진입 전 input 수집 필요.

---

## 2. 현황 (Phase H 진입 시 전제)

### 2.1 선행 chunk 완료 검증 (사용자 합의 / Step 0a 의 첫 작업)

본 chunk 진입 전 다음이 **이미 완료** 되어 있어야 한다:

| 선행 | 완료 시점 | 확인 방법 |
|------|-----------|-----------|
| Phase F-4 ✅ | (현재 진행 중, 미완료) | STATUS.md § 2 ka10027/30/31/32/23 5 endpoint 모두 ✅ 완료 row 이동 |
| Phase D-2 ka10080 분봉 ✅ | (현재 대기) | STATUS.md § 2 ka10080 ✅ 완료 row 이동 + 파티션 전략 ADR 기록 |
| Phase G ka10058/59/10131 ✅ | (현재 대기) | STATUS.md § 2 3 endpoint 모두 ✅ 완료 row 이동 |
| 25 endpoint 100% | F-4 + D-2 + G 합산 | STATUS.md § 0 25/25 (100%) 도달 |

> **본 chunk 는 25 endpoint 100% 도달 후에만 진입**. 미도달 상태로 진입하면 view 가 참조할 시계열 테이블 일부가 비어 있어 cross-check SQL 가 noise 만 생산.

### 2.2 기존 자산 (재사용)

| 자산 | 위치 | 본 chunk 활용 |
|------|------|--------------|
| `stock_price_krx` / `stock_price_nxt` (일/주/월/년봉) | `app/adapter/out/persistence/models/` | view `stock_price_combined` 의 KRX-uniform / NXT-fallback source |
| `stock_daily_flow` (KRX + NXT 분리, exchange_type 컬럼) | 동일 | view `daily_flow_combined` source |
| `ranking_snapshot` (Phase F-4 신규) | 동일 | quality report — 5 endpoint × 일별 row count 정합성 |
| `short_selling_kw` / `lending_balance_kw` | 동일 | quality report — partial threshold 위반 추세 |
| `investor_flow_daily` / `frgn_orgn_consecutive` (Phase G 신규) | 동일 | view `investor_summary` source |
| `sector_price_daily` (D-1) | 동일 | view 의 sector 매핑 |
| structlog + Telegram bot (BEARWATCH 채널) | `~/.claude/.../reference_telegram_bot.md` (사용자 메모리) | quality alert 채널 후보 |
| `app/adapter/web/routers/` 패턴 | FastAPI router | quality report endpoint (admin only) |
| testcontainers PG16 | tests/integration | view 정합성 통합 테스트 |

### 2.3 본 chunk 신규 자산 (목표)

| 자산 | 종류 | 핵심 결정 |
|------|------|-----------|
| `stock_price_combined` view | DB view (마테리얼라이즈드 or 동적) | § 4 D-1 |
| `daily_flow_combined` view | DB view | § 4 D-1 동일 정책 |
| `data_quality_report` SQL 묶음 | `scripts/quality_report.py` CLI + admin endpoint | KRX vs NXT price diff / volume diff / cross-check |
| 알람 채널 wiring | structlog + Telegram bot | § 4 D-2 |
| README.md 갱신 | 25 endpoint 카탈로그 + 운영 런북 | § 4 D-3 |
| SPEC.md 신규 | architecture + endpoint table + DB schema | § 4 D-3 |

---

## 3. 범위 외 (out of scope)

| 항목 | 이유 | 후속 chunk |
|------|------|-----------|
| **Grafana 대시보드** | **사용자 명시 — 마지막 chunk 로 분리 요청 (2026-05-15)** | Phase H' (사용자 재요청 시) |
| 백테스팅 엔진 (vectorbt 통합) | view 가 source 만 제공. 엔진은 backend_py 의 BacktestEngineService 재사용 또는 별도 프로젝트 | 백테스팅 엔진 통합 chunk (별도) |
| 신규 endpoint 도입 | Phase H 는 derived only. endpoint 추가 0 | — |
| 자격증명 회전 / .env.prod 정리 | 운영 설정 (사용자 메모리 `feedback_ops_changes_after_dev`) — 전체 개발 종결 후 일괄 | secret 회전 chunk (별도) |
| KOSCOM cross-check 자동화 | 수동 검증 1~2건 (STATUS.md § 4 #1) — 자동화는 별도 검토 | KOSCOM cross-check 자동화 (선택) |
| SOR (`_AL`) 통합 수집 | master.md § 3.3 정기 수집 안 함 결정 | 검토 안 함 |
| 분봉 (ka10080) 의 derived feature | D-2 도입 후 분봉 derived view 는 별도 | 분봉 derived chunk (선택) |

---

## 4. 결정 게이트 (작성 시점 미확정 — ted-run input 직전 사용자 확정 필수)

본 chunk 는 **사용자 결정 4건** 없이 ted-run 진입 불가. 기존 chunk 패턴 (F-2 D-1~D-4, F-3 D-1~D-8, F-4 D-1~D-14) 와 동일.

### D-1 백테스팅 view 전략 — 마테리얼라이즈드 vs 동적

| 옵션 | 정의 | 장점 | 단점 |
|------|------|------|------|
| A — 마테리얼라이즈드 view (권장) | `CREATE MATERIALIZED VIEW` + 매일 06:30 KST `REFRESH MATERIALIZED VIEW CONCURRENTLY` cron | 조회 빠름 / 백테스팅 엔진 부담 0 / 인덱스 자유 | refresh 비용 (rows × N 일 / KRX 4078 × 3년 = ~4.5M row) / refresh 중 stale window |
| B — 동적 view | `CREATE VIEW` 매 조회 시 KRX/NXT LEFT JOIN 합성 | refresh 없음 / 항상 최신 | 조회 시 매번 JOIN 비용 / 백테스팅 엔진 query latency |
| C — 둘 다 (이중 트랙) | A + B 양쪽 제공. 백테스팅은 A, 운영 대시보드는 B | flexibility | 유지보수 부담 2배 / 일관성 검증 부담 |

**권고 default**: A (마테리얼라이즈드). 백테스팅 use case 가 read-heavy + batch 라 stale window 가 문제 안 됨.

**view 합성 정책** (D-1 부속):
- D-1.1 — KRX 가 있으면 KRX 우선, KRX 가 비고 NXT 만 있으면 NXT fallback (master.md § 3 추천)
- D-1.2 — KRX 와 NXT 둘 다 있으면 close_price diff > 5% 시 quality flag 컬럼에 표시 (master.md § 8.3 시나리오 4)
- D-1.3 — view 가 노출할 컬럼: trading_date, stock_id, open/high/low/close, volume, amount, source (KRX/NXT/COMBINED), quality_flag (NULL / DIFF_GT_5PCT / NXT_ONLY)

### D-2 데이터 품질 알람 채널

| 옵션 | 정의 | 장점 | 단점 |
|------|------|------|------|
| A — Telegram bot (BEARWATCH 채널) — 권장 | 사용자 메모리 `reference_telegram_bot` 의 봇 토큰 + chat_id 재사용. 알람 임계 위반 시 send_message | 즉시성 / 모바일 푸시 / 기존 인프라 재사용 | 외부 의존 (Telegram API outage 시 alert miss) |
| B — log only (structlog WARN/ERROR) | log aggregator 의 alert rule 로 분리 처리 | 외부 의존 0 | 사람이 log 를 봐야 함 / 운영 가시성 약함 |
| C — 둘 다 | A + B | 안전 | 중복 alarm noise |

**권고 default**: A (Telegram). 사용자가 이미 BEARWATCH 봇을 시그널 알림용으로 운영 중이라 인프라 재사용이 자연.

**알람 트리거** (D-2 부속):
- D-2.1 — KRX 와 NXT close_price diff > 5% (master.md § 8.3 시나리오 4) — 일별 합계 1건 메시지
- D-2.2 — 25 endpoint 의 일별 row count 가 기대치 (직전 5 영업일 median) 의 ±50% 이탈 — daily digest
- D-2.3 — `short_selling_kw` partial 5% threshold 위반 — Phase F-2 errors_above_threshold tuple 이용
- D-2.4 — `raw_response` 의 90일 retention 임박 row count

### D-3 SPEC.md 범위 / README.md 갱신 범위

| 옵션 | 정의 | 장점 | 단점 |
|------|------|------|------|
| A — SPEC.md 신규 + README.md 운영 런북 갱신 (권장) | SPEC.md = architecture 다이어그램 + 25 endpoint 표 + DB schema + ADR cross-ref. README.md = 빠른 시작 + 운영 명령 + Docker | 문서 역할 분리 명확 | 신규 SPEC.md 작성 ~300 line |
| B — README.md 전부 통합 (SPEC 신규 작성 안 함) | README.md 가 모든 것을 포함 | 단일 진실 | README 가 비대화 (>1,000 line) |
| C — docs/ 하위 분할 (architecture.md / endpoints.md / runbook.md) | 다수 분할 | 카테고리 명확 | 사용자가 찾기 힘듦 |

**권고 default**: A (master.md § 1.1 의 디렉토리 구조에 이미 `SPEC.md` 자리가 마련됨 — "본 문서가 코드 작성 후 갱신될 명세서").

### D-4 데이터 품질 cross-check SQL 자동화 주기

| 옵션 | 정의 | 장점 | 단점 |
|------|------|------|------|
| A — 일 1회 06:45 KST cron (권장) | view refresh 직후 + 06:00/06:30 cron 후 quality SQL 자동 실행 | 자연 sequencing / 매일 알람 | 토요일/일요일 알람 의미 약함 |
| B — 수동 admin endpoint only | `POST /admin/quality/report` 로 사람이 트리거 | 알람 noise 0 | 수동 — 사람이 호출 안 하면 무용지물 |
| C — 둘 다 (cron + 수동) | A + B | flexibility | 추가 비용 미미 |

**권고 default**: C (cron + 수동). 운영 default cron + 별도 검증 시 admin endpoint 도 제공.

---

## 5. 작업 분해 (Step 0~5 — ted-run 풀 파이프라인)

### Step 0 (TDD red 단계)

- 0a — 선행 검증 + § 4 D-1~D-4 사용자 확정 수집 + 본 plan doc § 6 갱신
- 0b — view migration 테스트 (`tests/test_migration_h_view.py`) — 마테리얼라이즈드 view 4개 (price daily/weekly/monthly + daily_flow) `CREATE` / `REFRESH` / index 검증
- 0c — quality SQL 테스트 (`tests/test_quality_report.py`) — 4 SQL × normal/anomaly 2 case = 8 case
- 0d — alert adapter 테스트 (`tests/test_telegram_alert.py`) — Telegram bot mock + send_message + retry on 429
- 0e — Router + CLI 테스트 (`tests/test_quality_router.py` + `tests/test_quality_cli.py`) — admin endpoint 4 + CLI flag 검증
- 0f — pytest -x red 확인

### Step 1 (구현 — green 도달)

| # | 산출 | 위치 |
|---|------|------|
| 1.1 | Migration 0XX_combined_view + 4 마테리얼라이즈드 view + index | `migrations/versions/` |
| 1.2 | `app/adapter/out/persistence/repositories/quality.py` — 4 quality SQL repository | 신규 |
| 1.3 | `app/application/service/quality_service.py` — quality report aggregator | 신규 |
| 1.4 | `app/adapter/out/notify/telegram.py` — Telegram bot send adapter (httpx + retry) | 신규 |
| 1.5 | `app/adapter/web/routers/quality.py` — admin endpoint 4 (status / refresh / report / alert-trigger) | 신규 |
| 1.6 | `app/batch/quality_job.py` + scheduler hook — 06:45 KST cron + view refresh hook 06:30 | 신규 |
| 1.7 | `scripts/quality_report.py` — CLI (--dry-run / --send-alert / --period) | 신규 |
| 1.8 | `README.md` 갱신 — 25 endpoint 표 + 운영 런북 + Docker | 갱신 |
| 1.9 | `SPEC.md` 신규 — architecture + 25 endpoint + DB schema + ADR cross-ref | 신규 |

**Migration 번호**: F-4 (018) + D-2 (019) + G (020 추정) → **본 chunk = 021_combined_view** (chunk 진입 시 head 재확인 필수).

### Step 2 (이중 리뷰)

| # | 단계 | 모델 |
|---|------|------|
| 2a R1 | 1차 리뷰 (python-reviewer) | sonnet |
| 2b R1 | 적대적 리뷰 (security-review — Telegram bot 토큰 노출 가능성 / view stale window race / refresh CONCURRENTLY 락 동작) | opus (force) |
| 2 fix R1 | HIGH/MEDIUM 수정 | opus |
| 2 R2 | 재리뷰 합의 | sonnet + opus |

### Step 3 (Verification 5관문)

- 3.1 — alembic upgrade head (testcontainers + 운영 DB dry-run)
- 3.2 — ruff clean + mypy strict 전체 files
- 3.3 — pytest 전체 PASS + coverage 86%+ 유지 (현재 86.56%)
- 3.4 — Telegram bot send 운영 검증 (mock channel 또는 BEARWATCH dry channel 1건)
- 3.5 — view refresh 실측 (KRX/NXT 풀 데이터 대상 — 예상 30s~2m)

### Step 4 (E2E)

⚪ 자동 생략 (백엔드 + 문서 only, UI 변경 0).

### Step 5 (Ship)

- 5.1 — ADR § 49 신규 (Phase H 결정 D-1~D-4 + 측정 결과 + inherit 사항)
- 5.2 — STATUS.md § 0/§1/§2/§4/§5/§6 갱신 (Phase H 완료 row 이동 + 25 endpoint 100% 도달)
- 5.3 — HANDOFF.md 직전 세션 단면
- 5.4 — CHANGELOG.md prepend
- 5.5 — README.md / SPEC.md 산출물 검토
- 5.6 — 한글 커밋 (사용자 push 명시 요청 시만 push)

---

## 6. 확정 결정 (작성 시점 미확정 — ted-run input 직전 사용자 확정 필요)

| ID | 항목 | 현재 상태 | ted-run 진입 시 결정 |
|----|------|----------|--------------------|
| D-1 | view 전략 (마테리얼라이즈드 vs 동적 vs 이중) | 미확정 — 권고 A | 사용자 확정 |
| D-1.1 | view 합성 정책 (KRX 우선 / NXT fallback) | 미확정 — 권고 master.md § 3 정합 | 사용자 확정 |
| D-1.2 | quality flag 임계 (close diff > 5%) | 미확정 — 권고 5% | 사용자 확정 (3% / 5% / 10% 옵션) |
| D-1.3 | view 노출 컬럼 | 미확정 — 권고 7 컬럼 | 사용자 확정 |
| D-2 | 알람 채널 (Telegram / log only / 둘 다) | 미확정 — 권고 A (Telegram) | 사용자 확정 |
| D-2.1~D-2.4 | 알람 트리거 4종 | 미확정 — 권고 4종 전부 | 사용자 확정 (포함/제외) |
| D-3 | SPEC.md 신규 + README.md 갱신 범위 | 미확정 — 권고 A | 사용자 확정 |
| D-4 | quality cron 주기 (일 1회 / 수동 / 둘 다) | 미확정 — 권고 C | 사용자 확정 |
| D-5 | retention 정책 (`raw_response` 90일 hard delete vs archive) | 미확정 — master.md § 4.2 기본 90일 | 사용자 확정 |
| D-6 | (선택) backfill view 적용 범위 — 일/주/월 모두 vs 일만 | 미확정 — 권고 일만 (주/월/년은 stale 허용도 높음) | 사용자 확정 |

---

## 7. 영향 범위 self-check (security-review 사전 점검)

| 영역 | 위험 | 완화 |
|------|------|------|
| Telegram bot 토큰 | bot token 이 .env.prod 의 secret. structlog 마스킹 필수 | `TELEGRAM_BOT_TOKEN` env 추가 — 로그 마스킹 패턴에 `telegram` / `chat_id` / `bot_token` 키워드 등록 |
| 마테리얼라이즈드 view refresh | refresh CONCURRENTLY 미사용 시 read 락 / refresh 중 stale read | `CONCURRENTLY` 키워드 필수 + UNIQUE index 사전 생성 |
| 알람 noise | 알람 임계 너무 낮으면 매일 noise — 운영 1주 후 임계 재조정 | 알람 트리거에 dry-run 모드 + cooldown (같은 종목 24h 1회) |
| quality SQL injection | admin endpoint param → SQL — params bind 필수 | `text(:param)` + bind / ORM 사용 |
| view 정합성 fragile | KRX/NXT 동시 백필 중 view refresh 시 partial state | refresh 는 cron 06:45 (06:00 KRX + 06:30 NXT 완료 후 — sequence 보장) |
| Telegram API outage | 알람 미발송 → 침묵 incident | retry 3회 + 실패 시 structlog ERROR + 운영 매일 digest 보강 |

---

## 8. DoD (완료 기준)

- [ ] § 4 D-1~D-6 사용자 확정 완료
- [ ] 4 마테리얼라이즈드 view 적용 (alembic head 갱신)
- [ ] 4 quality SQL + repository + service
- [ ] Telegram bot adapter + 4 알람 트리거 wiring (D-2 결정에 따라)
- [ ] admin endpoint 4 (status / refresh / report / alert-trigger)
- [ ] CLI `scripts/quality_report.py` (--dry-run / --send-alert / --period)
- [ ] 06:30 view refresh cron + 06:45 quality cron 등록
- [ ] README.md 갱신 + SPEC.md 신규
- [ ] R1+R2 양쪽 합의 PASS
- [ ] Verification 5관문 PASS (mypy strict + ruff + pytest + cov ≥ 86% + view refresh 실측)
- [ ] ADR § 49 신규 (D-1~D-6 + 측정 + inherit)
- [ ] STATUS.md 갱신 (25/25 endpoint 100% 도달 표시)
- [ ] 한글 커밋

---

## 9. 위험 / 의존성

| 위험 | 완화 |
|------|------|
| 선행 chunk (F-4 / D-2 / G) 미완료 진입 | § 2.1 검증 표 — Step 0a 의 첫 작업이 선행 완료 확인 + STATUS.md § 2 25/25 도달 확인 |
| view 가 참조하는 시계열 테이블 schema 변경 (예: ka10080 분봉 파티션 결정) | D-2 chunk 의 ADR 에 schema 동결 후 본 chunk 진입 |
| Telegram bot 토큰 회전 | 사용자 메모리 `feedback_ops_changes_after_dev` — 운영 설정 변경은 개발 종결 후. 본 chunk 는 기존 토큰 그대로 사용 |
| view refresh 실측 시간 미지 (3년 × 4078 KRX × 4 view = 잠재적 16M row scan) | Step 3.5 verification 에서 실측 후 cron timing 재조정 가능 |
| 알람 운영 임계 미확정 → noise | Step 5 후 1주 운영 모니터링 + 임계 재조정 별도 chunk |

---

## 10. 후속 chunk (Phase H 완료 후 후보)

| 순위 | chunk | 근거 |
|------|-------|------|
| 1 | **Phase H' — Grafana 대시보드** (사용자 마지막 chunk 로 재요청) | Phase H view + alert 위에 Grafana 가 시각화 layer |
| 2 | 백테스팅 엔진 통합 (vectorbt) | view 가 source 준비 완료 — 엔진 통합은 별도 프로젝트 가능 |
| 3 | secret 회전 (Telegram bot 토큰 포함) | 사용자 메모리 — 개발 종결 후 일괄 |
| 4 | KOSCOM cross-check 자동화 (STATUS.md § 4 #1) | 수동 검증 1~2건 → 자동화 검토 |
| 5 | 알람 임계 튜닝 (운영 1주 후) | noise 측정 후 임계 재조정 |

---

_본 plan doc 은 작성 시점 (2026-05-15) 에 선행 chunk (F-4 / D-2 / G) 가 모두 진행 중 또는 대기 상태. ted-run 진입은 선행 100% 완료 후. § 4 결정 게이트 6건 (D-1~D-6) 사용자 확정 필수._
