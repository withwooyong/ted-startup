# Session Handoff

> Last updated: 2026-05-12 (KST, /handoff) — scheduler_enabled 활성 (Phase C 운영 본격 진입).
> Branch: `master`
> Latest commit: `<this commit>` (scheduler 활성 / .env.prod 9 env / ADR § 36)
> 미푸시 commit: **3 건** (`7f6beb5` 영숫자 백필 + `8c14aa3` cron shift + this commit — 사용자 명시 요청 시 push)

## Current Status

**Phase C 운영 본격 진입** — 8 cron scheduler 모두 활성 (sector / stock_master / fundamental / ohlcv_daily / daily_flow / weekly / monthly / yearly). 5-13 (수) 06:00 첫 OhlcvDaily cron 발화 예정. 1주 모니터 후 별도 chunk 에서 § 36.5 측정 결과 채움.

본 chunk 는 **코드 변경 0** — `.env.prod` 9 env (commit 외부) + plan doc + ADR § 36 + 3 문서. 테스트 변경 없음 (1059 그대로).

**사용자 최종 확인 (2026-05-12, 세션 종료)**: "앱 재시작 후 1주 모니터, 5-19 이후 § 36.5 측정 결과 채움" 동의 + 핸드오프/커밋/푸시 진행.

## Completed This Session

| # | Task | 결과 | Files |
|---|------|------|-------|
| 1 | 영숫자 백필 chunk | 0 failure / 47m 33s / 75K rows / ADR § 34 | 5 / `7f6beb5` |
| 2 | scheduler cron 시간 사용자 확인 → NXT 거래시간 충돌 발견 | 5-11 NXT 74 rows DB 검증 + plan doc | 0 |
| 3 | cron shift chunk | helper + 3 batch_job + 3 cron + 4 test + 1059 PASS (+13) / ADR § 35 | 14 / `8c14aa3` |
| 4 | scheduler 활성 — env 9건 추가 + 가이드 | .env.prod 편집 (commit 외부) + plan doc + ADR § 36 + 3 문서 | 4 + .env.prod |

## In Progress / Pending

| # | Task | Status | Notes |
|---|------|--------|-------|
| **1** | **(1주 후) § 36.5 측정 결과 채움** | **다음 chunk 1순위 (2026-05-19 이후)** | cron elapsed / NXT 정상 / failed / 알람 정량화 |
| 2 | 5-11 NXT 74 rows 보완 (사용자 수동) | 대기 | `backfill_ohlcv.py --start-date 2026-05-11 --end-date 2026-05-11 --alias prod` (--resume 미사용) |
| 3 | 사용자 앱 재시작 (.env.prod 변경 반영) | 대기 | uvicorn / docker / systemd 환경에 따라 |
| 4 | Phase D — ka10080 분봉 / ka20006 업종일봉 | 대기 | 대용량 파티션 결정 선행 |
| 5 | Phase E / F / G | 대기 | 신규 endpoint wave |
| 6 | KOSCOM cross-check 수동 | 대기 | 가설 B 최종 확정 |

## Key Decisions Made

1. **scheduler 활성 = .env.prod 9 env** — Claude 가 직접 .env.prod 편집 (사용자 동의). `KIWOOM_SCHEDULER_ENABLED=true` + 8 alias 모두 `prod` (DB 등록 자격증명)
2. **1주 후 측정은 별도 chunk** — 본 chunk 는 활성 + 가이드 + ADR § 36 placeholder. 2026-05-19 mon 이후 사용자 요청 시 § 36.5 채움
3. **사용자 앱 재시작 필요** — Claude 가 재시작 안 함. 사용자 환경 (uvicorn / docker / systemd) 에 따라 수동
4. **공휴일 calendar 무시 유지** — § 35 결정 그대로. 1주 모니터에서 빈 응답 패턴 관찰 후 별도 chunk 가능
5. **NXT scheduler 분리 (옵션 C) 미채택** — § 35 옵션 A (일괄 06:00) 그대로. 1주 후 측정에서 NXT 정상 적재 확인되면 분리 불필요

## Known Issues

| # | 항목 | 출처 | 결정 |
|---|------|------|------|
| **13** | 일간 cron 실측 (운영 cron elapsed) | dry-run § 20.4 → § 36 | 🔄 활성 완료 — 1주 후 측정 별도 chunk |
| **20** | NXT 우선주 sentinel 빈 row 1개 detection | § 32.3 + § 33.6 | LOW — 운영 영향 0 |
| **21** | 5-11 NXT 74 rows 보완 | § 35.8 | 사용자 수동 명령 |

## Context for Next Session

### 사용자의 의도

"scheduler_enabled 활성 + 1주 모니터 — env 1건. cron 06:00/06:30/sat 07:00 첫 발화 검증 + § 34 + § 35 정량화. Phase C 의 마지막 chunk" 명시. 4 분기 모두 추천 선택 — Claude 가 .env.prod 편집 / 1주 후 측정은 별도 chunk.

### 채택한 접근

1. **.env.prod 직접 편집** — Claude 가 9 env 추가 (commit 외부, .gitignore). 사용자 동의 받음
2. **plan doc + ADR § 36 (placeholder)** — 활성 + 가이드 + 1주 후 측정 SQL/표 placeholder. § 36.5 가 1주 후 채움
3. **단일 commit** — 4 문서 (commit 대상). .env.prod 는 commit 외부 — 사용자 환경 변경 직접
4. **앱 재시작은 사용자 책임** — Claude 가 자동 실행 안 함

### 사용자 환경 제약

- `.env.prod` 변경 적용 = 앱 재시작 필요. uvicorn / docker / systemd 환경 사용자 결정
- DB 등록 alias `prod` 1건만 → 8 cron 모두 `prod` 매핑
- KIWOOM_DEFAULT_ENV=prod 이미 설정됨 → 운영 키움 API (api.kiwoom.com) 호출

### 다음 세션 진입 시점 결정 필요

| 옵션 | 설명 | 비용 |
|------|------|------|
| **A. (1주 후) § 36.5 측정 결과 채움** | 5-19 mon 이후. 일간 cron elapsed / NXT 정상 / failed / 알람 SQL + 분석 | 측정 + 분석 |
| B. Phase D 진입 | ka10080 분봉 / ka20006 업종일봉 | 신규 도메인 + 파티션 |
| C. 5-11 NXT 보완 (사용자 수동) | 1 명령 ~44분 | 사용자 시간 |
| D. 공휴일 calendar 도입 | § 35 의 follow-up. 빈 응답 패턴 관찰 후 | 신규 chunk |

권장: **A** (5-19 이후) → **B** (Phase D)

### 운영 위험

- **앱 재시작 시점 우려**: 5-12 화 17:30 / 18:00 에 master/fundamental 발화 — 앱이 그 전에 떠있어야. 늦게 재시작하면 5-13 부터
- **첫 발화 5-13 (수) 06:00 OhlcvDaily**: base_date = 5-12 화 데이터 fetch. 5-12 NXT 거래 정상 마감 후라 안전
- **5-11 NXT 74 rows**: 본 chunk 활성으로 자연 보완 안 됨 — 별도 backfill 명령 필요 (--start-date 명시)
- **logger.error 알람 watch**: 사용자가 모니터링 필요. cron 첫 1주 watch 강력 권장

## Files Modified This Session

### Chunk 1 (`7f6beb5`) — 영숫자 백필 (이미 commit)
### Chunk 2 (`8c14aa3`) — cron shift (이미 commit)

### Chunk 3 (`<this commit>`) — scheduler 활성 — 4 files (+ .env.prod commit 외부)

- .env.prod (9 env 추가 — commit 외부, .gitignore)
- 신규 `src/backend_kiwoom/docs/plans/phase-c-scheduler-enable.md`
- 갱신 `docs/ADR/ADR-0001-backend-kiwoom-foundation.md` § 36
- 갱신 `src/backend_kiwoom/STATUS.md`
- 갱신 `HANDOFF.md` (본 파일)
- 갱신 `CHANGELOG.md`

### Verification

- 코드 변경 0 — ruff / mypy / pytest 재실행 불필요 (1059 그대로)

---

_Phase C 운영 본격 진입. 1주 모니터 후 별도 chunk 에서 § 36.5 측정 결과 채움._
